import argparse
import sys
import json
import shutil 
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from pathlib import Path
from PIL import Image, ImageTk

import utils
import downloader
from models import Node
from stat_renderer import StatBlockRenderer, CombatRenderer
from dialogs import SpellSearchDialog, MonsterSearchDialog, EntitySelectionDialog

class DnDStatManager(tk.Tk):
    def __init__(self, root_dir):
        super().__init__()
        self.title("D&D Campaign Manager - Stat Blocks")
        self.geometry("1500x850")
        self.configure(bg="#fdf1dc")
        
        self.root_dir = Path(root_dir).resolve()
        
        self.map_dir = self.root_dir / "map"
        self.map_dir.mkdir(parents=True, exist_ok=True)
        (self.map_dir / "Monsters").mkdir(exist_ok=True)
        (self.map_dir / "NPCs").mkdir(exist_ok=True)
        (self.map_dir / "Combats").mkdir(exist_ok=True)
        
        self.spells_dir = self.root_dir / "spells"
        self.spells_dir.mkdir(parents=True, exist_ok=True)
        self.monsters_dir = self.root_dir / "Monsters"
        self.monsters_dir.mkdir(parents=True, exist_ok=True)
        self.npcs_dir = self.root_dir / "NPCs"
        self.npcs_dir.mkdir(parents=True, exist_ok=True)
        self.combats_dir = self.root_dir / "Combats"
        self.combats_dir.mkdir(parents=True, exist_ok=True)
        
        self.image_cache = []
        self.current_open_node = None
        
        self.monster_index = []
        if Path("monsters.json").exists():
            with open("monsters.json", "r", encoding="utf-8") as f:
                self.monster_index = json.load(f)

        self.spells_index = []
        if Path("spells.json").exists():
            with open("spells.json", "r", encoding="utf-8") as f:
                self.spells_index = json.load(f)

        self.query_blocks = []
        self.monster_query_blocks = []

        self._setup_ui()
        self.refresh_tree()

    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#fae6c5", foreground="black", rowheight=35, fieldbackground="#fdf1dc", font=("Georgia", 12), borderwidth=0)
        style.configure("Treeview.Heading", font=("Georgia", 13, "bold"), background="#fdf1dc", foreground="#7a200d")
        style.map("Treeview", background=[("selected", "#4a90e2")])

        self.paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)
        self.tree_frame = tk.Frame(self.paned_window, bg="#fae6c5")
        self.paned_window.add(self.tree_frame, weight=1)

        self.tree_canvas = tk.Canvas(self.tree_frame, bg="#fae6c5", highlightthickness=0)
        self.tree_scroll = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree_canvas.yview)
        self.tree_canvas.configure(yscrollcommand=self.tree_scroll.set)
        self.tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree_inner = tk.Frame(self.tree_canvas, bg="#fae6c5")
        self.tree_window = self.tree_canvas.create_window((0, 0), window=self.tree_inner, anchor="nw")
        self.tree_inner.bind("<Configure>", lambda e: self.tree_canvas.configure(scrollregion=self.tree_canvas.bbox("all")))
        self.tree_canvas.bind("<Configure>", lambda e: self.tree_canvas.itemconfig(self.tree_window, width=e.width))

        self.right_frame = tk.Frame(self.paned_window, bg="#fdf1dc")
        self.paned_window.add(self.right_frame, weight=3)
        
        self.stat_viewer = StatBlockRenderer(self.right_frame)
        self.stat_viewer.set_spell_callback(self.on_spell_clicked)
        self.stat_viewer.set_spells_index(self.spells_index)
        
        self.combat_viewer = CombatRenderer(
            self.right_frame, 
            open_statblock_cb=self._combat_open_statblock, 
            save_cb=self.save_combat_edits,
            add_bestiary_cb=self._combat_add_bestiary,
            add_camp_mon_cb=self._combat_add_camp_mon,
            add_camp_npc_cb=self._combat_add_camp_npc,
            cancel_cb=self.clear_viewer_and_tree
        )
        
        # Monster Panel Layout
        self.search_frame = tk.Frame(self.right_frame, bg="#fdf1dc")
        tk.Label(self.search_frame, text="Monster Database", font=("Georgia", 16, "bold"), bg="#fdf1dc", fg="#7a200d").pack(pady=10)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.apply_monster_query())
        self.search_entry = tk.Entry(self.search_frame, textvariable=self.search_var, font=("Georgia", 14), bg="#ffffff", fg="black", insertbackground="black")
        self.search_entry.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        m_tools = tk.Frame(self.search_frame, bg="#fdf1dc")
        m_tools.pack(fill=tk.X, padx=20, pady=(0, 5))
        for op in ["AND", "OR", "(", ")"]: 
            tk.Button(m_tools, text=op, bg="#e0cbb0", fg="black", font=("Arial", 9, "bold"), command=lambda o=op: self.add_mqblock(o)).pack(side=tk.LEFT, padx=2)
        tk.Button(m_tools, text="+ Filter", bg="#d9ad6c", fg="black", command=self.open_monster_filter_dialog).pack(side=tk.LEFT, padx=10)
        tk.Button(m_tools, text="Clear Filters", bg="#ff4d4d", fg="white", command=self.clear_mqblocks).pack(side=tk.RIGHT, padx=2)
        self.m_query_canvas_frame = tk.Frame(self.search_frame, bg="#f5e6ce", bd=1, relief=tk.SUNKEN)
        self.m_query_canvas_frame.pack(fill=tk.X, padx=20, pady=(0, 10), ipady=5)
        
        lb_f = tk.Frame(self.search_frame, bg="#fdf1dc")
        lb_f.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        self.monster_tree = ttk.Treeview(lb_f, columns=("name", "type", "cr", "source"), show="headings", selectmode="browse")
        self.monster_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for c, w in [("name", 300), ("type", 150), ("cr", 60), ("source", 80)]:
            self.monster_tree.heading(c, text=c.title(), anchor="center" if c in ["cr", "source"] else "w")
            self.monster_tree.column(c, width=w, anchor="center" if c in ["cr", "source"] else "w")
        self.monster_tree.tag_configure("evenrow", background="#f5e6ce", foreground="black")
        self.monster_tree.tag_configure("oddrow", background="#fae6c5", foreground="black")
        scr = ttk.Scrollbar(lb_f, orient="vertical", command=self.monster_tree.yview)
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.monster_tree.configure(yscrollcommand=scr.set)
        self.monster_tree.bind("<Double-1>", self.on_monster_selected)

        # FIXED: Explicit visual button layout target appended at the bottom to avoid awkward double clicks
        tk.Button(self.search_frame, text="Add Selected Monster", bg="#4a90e2", fg="white", font=("Arial", 11, "bold"), command=lambda: self.on_monster_selected(None)).pack(pady=10)

        # Spell Panel Frame Layout Setup
        self.spell_manager_frame = tk.Frame(self.right_frame, bg="#fdf1dc")
        tk.Label(self.spell_manager_frame, text="Spell Database", font=("Georgia", 16, "bold"), bg="#fdf1dc", fg="#7a200d").pack(pady=10)
        self.spell_search_var = tk.StringVar()
        self.spell_search_var.trace_add("write", lambda *a: self.apply_spell_query())
        tk.Entry(self.spell_manager_frame, textvariable=self.spell_search_var, font=("Georgia", 14), bg="#ffffff", fg="black", insertbackground="black").pack(fill=tk.X, padx=20, pady=(0, 10))
        q_tools = tk.Frame(self.spell_manager_frame, bg="#fdf1dc")
        q_tools.pack(fill=tk.X, padx=20, pady=(0, 5))
        for op in ["AND", "OR", "(", ")"]: 
            tk.Button(q_tools, text=op, bg="#e0cbb0", fg="black", font=("Arial", 9, "bold"), command=lambda o=op: self.add_qblock(o)).pack(side=tk.LEFT, padx=2)
        tk.Button(q_tools, text="+ Filter", bg="#d9ad6c", fg="black", command=self.open_filter_dialog).pack(side=tk.LEFT, padx=10)
        tk.Button(q_tools, text="Clear Filters", bg="#ff4d4d", fg="white", command=self.clear_qblocks).pack(side=tk.RIGHT, padx=2)
        self.query_canvas_frame = tk.Frame(self.spell_manager_frame, bg="#f5e6ce", bd=1, relief=tk.SUNKEN)
        self.query_canvas_frame.pack(fill=tk.X, padx=20, pady=(0, 10), ipady=5)

        s_lf = tk.Frame(self.spell_manager_frame, bg="#fdf1dc")
        s_lf.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        self.spell_tree = ttk.Treeview(s_lf, columns=("name", "level", "school", "source"), show="headings", selectmode="browse")
        self.spell_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for c, w in [("name", 300), ("level", 60), ("school", 150), ("source", 80)]:
            self.spell_tree.heading(c, text=c.title(), anchor="center" if c in ["level", "source"] else "w")
            self.spell_tree.column(c, width=w, anchor="center" if c in ["level", "source"] else "w")
        self.spell_tree.tag_configure("evenrow", background="#f5e6ce", foreground="black")
        self.spell_tree.tag_configure("oddrow", background="#fae6c5", foreground="black")
        s_scr = ttk.Scrollbar(s_lf, orient="vertical", command=self.spell_tree.yview)
        s_scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.spell_tree.configure(yscrollcommand=s_scr.set)
        self.spell_tree.bind("<Double-1>", self.on_spell_manager_selected)
        
        self.stat_viewer.pack(fill=tk.BOTH, expand=True)

    def _combat_open_statblock(self, target_name, folder_type):
        global_path = self.root_dir / folder_type / target_name
        # FIXED: Enforces that the lambda redirects back to the current active combat sheet
        self.display_monster_by_path(global_path, edit_mode=False, back_cb=lambda: self.display_combat(self.current_open_node) if self.current_open_node else None)
    
    def _get_entity_hp(self, target_name, folder_category):
        global_path = self.root_dir / folder_category / target_name / f"{target_name}.json"
        if global_path.exists():
            try:
                data = json.load(open(global_path, "r", encoding="utf-8"))
                return data.get("hp", {}).get("average", 10)
            except: return 10
        return 10

    def _combat_add_bestiary(self, combat_dir, callback):
        def on_monster_selected(monster_meta):
            try:
                global_monster_dir, safe_name = downloader.download_monster_data(monster_meta, self.monsters_dir)
                if not global_monster_dir: return
                hp = self._get_entity_hp(safe_name, "Monsters")
                combat_parent_path = combat_dir.parent
                if self.map_dir in combat_parent_path.parents or combat_parent_path == self.map_dir:
                    loc_folder = combat_parent_path.parent
                    local_ref_dir = loc_folder / "Monsters" / safe_name
                    local_ref_dir.mkdir(parents=True, exist_ok=True)
                    with open(local_ref_dir / "reference.json", "w", encoding="utf-8") as f:
                        json.dump({"type": "Monsters", "target": safe_name}, f, indent=4)
                callback(safe_name, "Monsters", hp)
                self.refresh_tree()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to download monster: {e}")
        MonsterSearchDialog(self, self.monster_index, on_monster_selected)

    def _combat_add_camp_mon(self, callback):
        def on_sel(target_name):
            hp = self._get_entity_hp(target_name, "Monsters")
            callback(target_name, "Monsters", hp)
        EntitySelectionDialog(self, self.monsters_dir, "Monsters", on_sel)

    def _combat_add_camp_npc(self, callback):
        def on_sel(target_name):
            hp = self._get_entity_hp(target_name, "NPCs")
            callback(target_name, "NPCs", hp)
        EntitySelectionDialog(self, self.npcs_dir, "NPCs", on_sel)

    def add_mqblock(self, b): self.monster_query_blocks.append(b); self.render_mqblocks(); self.apply_monster_query()
    def clear_mqblocks(self): self.monster_query_blocks.clear(); self.render_mqblocks(); self.apply_monster_query()
    def remove_mqblock(self, idx): self.monster_query_blocks.pop(idx); self.render_mqblocks(); self.apply_monster_query()
    def toggle_mqblock_op(self, idx): self.monster_query_blocks[idx] = "OR" if self.monster_query_blocks[idx] == "AND" else "AND"; self.render_mqblocks(); self.apply_monster_query()

    def render_mqblocks(self):
        for w in self.m_query_canvas_frame.winfo_children(): w.destroy()
        if not self.monster_query_blocks:
            tk.Label(self.m_query_canvas_frame, text="No active filters.", bg="#f5e6ce", fg="#555555", font=("Arial", 10, "italic")).pack(padx=10, pady=5)
            return
        for i, b in enumerate(self.monster_query_blocks):
            if isinstance(b, str):
                bg_col = "#ff4d4d" if b == "AND" else ("#4a90e2" if b == "OR" else "#e0cbb0")
                fg_col = "white" if b in ["AND", "OR"] else "black"
                btn = tk.Button(self.m_query_canvas_frame, text=b, bg=bg_col, fg=fg_col, font=("Arial", 9, "bold"))
                if b in ["AND", "OR"]:
                    btn.config(command=lambda idx=i: self.toggle_mqblock_op(idx))
                    btn.bind("<Button-3>", lambda e, idx=i: self.remove_mqblock(idx))
                else: btn.config(command=lambda idx=i: self.remove_mqblock(idx))
            else:
                text = f"CR {b['min']}-{b['max']}" if b["type"] == "cr" else f"{b['type'].title()}: {b['val']}"
                btn = tk.Button(self.m_query_canvas_frame, text=text, bg="#7a200d", fg="white", font=("Arial", 9, "bold"), command=lambda idx=i: self.remove_mqblock(idx))
            btn.pack(side=tk.LEFT, padx=2, pady=2)

    def open_monster_filter_dialog(self):
        d = tk.Toplevel(self)
        d.title("Build Monster Filter")
        d.geometry("460x600")
        d.configure(bg="#fdf1dc")
        
        tk.Label(d, text="Add Filter Conditions", bg="#fdf1dc", fg="#7a200d", font=("Georgia", 14, "bold")).pack(pady=10)
        
        logic_var = tk.StringVar(value="AND")
        def toggle_logic():
            if logic_var.get() == "AND":
                logic_var.set("OR")
                btn_logic.config(text="OR", bg="#4a90e2")
            else:
                logic_var.set("AND")
                btn_logic.config(text="AND", bg="#ff4d4d")
                
        btn_logic = tk.Button(d, text="AND", bg="#ff4d4d", fg="white", font=("Arial", 12, "bold"), width=10, command=toggle_logic)
        btn_logic.pack(pady=5)
        
        f = tk.Frame(d, bg="#fdf1dc")
        f.pack(fill=tk.BOTH, expand=True, padx=30)
        
        tk.Label(f, text="Min CR:", bg="#fdf1dc", fg="black", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="e", pady=8, padx=10)
        min_cr = tk.Scale(f, from_=0, to=30, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=160)
        min_cr.grid(row=0, column=1, sticky="w", pady=8, padx=10)
        
        tk.Label(f, text="Max CR:", bg="#fdf1dc", fg="black", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="e", pady=8, padx=10)
        max_cr = tk.Scale(f, from_=0, to=30, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=160)
        max_cr.set(30)
        max_cr.grid(row=1, column=1, sticky="w", pady=8, padx=10)

        tk.Label(f, text="Size:", bg="#fdf1dc", fg="black", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="e", pady=8, padx=10)
        size_v = ttk.Combobox(f, values=["All", "Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"], state="readonly", width=18)
        size_v.set("All")
        size_v.grid(row=2, column=1, sticky="w", pady=8, padx=10)

        tk.Label(f, text="Type:", bg="#fdf1dc", fg="black", font=("Arial", 10, "bold")).grid(row=3, column=0, sticky="e", pady=8, padx=10)
        type_v = ttk.Combobox(f, values=["All", "Aberration", "Beast", "Celestial", "Construct", "Dragon", "Elemental", "Fey", "Fiend", "Giant", "Humanoid", "Monstrosity", "Ooze", "Plant", "Undead"], state="readonly", width=18)
        type_v.set("All")
        type_v.grid(row=3, column=1, sticky="w", pady=8, padx=10)

        tk.Label(f, text="Alignment:", bg="#fdf1dc", fg="black", font=("Arial", 10, "bold")).grid(row=4, column=0, sticky="e", pady=8, padx=10)
        align_v = ttk.Combobox(f, values=["All", "Lawful Good", "Neutral Good", "Chaotic Good", "Lawful Neutral", "True Neutral", "Chaotic Neutral", "Lawful Evil", "Neutral Evil", "Chaotic Evil", "Unaligned", "Any"], state="readonly", width=18)
        align_v.set("All")
        align_v.grid(row=4, column=1, sticky="w", pady=8, padx=10)

        tk.Label(f, text="Environment:", bg="#fdf1dc", fg="black", font=("Arial", 10, "bold")).grid(row=5, column=0, sticky="e", pady=8, padx=10)
        env_v = ttk.Combobox(f, values=["All", "Arctic", "Coastal", "Desert", "Forest", "Grassland", "Hill", "Mountain", "Swamp", "Underdark", "Underwater", "Urban"], state="readonly", width=18)
        env_v.set("All")
        env_v.grid(row=5, column=1, sticky="w", pady=8, padx=10)
        
        def apply_f():
            filters = []
            if min_cr.get() > 0 or max_cr.get() < 30: filters.append({"type": "cr", "min": min_cr.get(), "max": max_cr.get()})
            if size_v.get() != "All": filters.append({"type": "size", "val": size_v.get()})
            if type_v.get() != "All": filters.append({"type": "type", "val": type_v.get()})
            if align_v.get() != "All": filters.append({"type": "align", "val": align_v.get()})
            if env_v.get() != "All": filters.append({"type": "env", "val": env_v.get().lower()})
                
            if not filters:
                d.destroy()
                return
                
            op = logic_var.get()
            if self.monster_query_blocks: self.monster_query_blocks.append(op)
            for i, f_block in enumerate(filters):
                self.monster_query_blocks.append(f_block)
                if i < len(filters) - 1: self.monster_query_blocks.append(op)
                    
            self.render_mqblocks()
            self.apply_monster_query()
            d.destroy()
            
        tk.Button(d, text="Apply Filters", bg="#d9ad6c", fg="black", font=("Arial", 11, "bold"), command=apply_f).pack(pady=20)

    def apply_monster_query(self):
        for item in self.monster_tree.get_children(): self.monster_tree.delete(item)
        q_str = self.search_var.get().lower()
        count = 0
        for m in self.monster_index:
            if q_str and q_str not in m["name"].lower(): continue
            if self.monster_query_blocks:
                expr = ""
                for b in self.monster_query_blocks:
                    if b in ["AND", "OR", "(", ")"]: expr += f" {b.lower()} "
                    else:
                        match = True
                        if b["type"] == "cr" and (utils.parse_cr(m.get("cr", "0")) < b["min"] or utils.parse_cr(m.get("cr", "0")) > b["max"]): match = False
                        elif b["type"] == "size" and m.get("size") != b["val"]: match = False
                        elif b["type"] == "type" and b["val"].lower() not in m.get("type", "").lower(): match = False
                        elif b["type"] == "align" and b["val"].lower() not in m.get("alignment", "").lower(): match = False
                        elif b["type"] == "env" and b["val"] not in m.get("environment", []): match = False
                        expr += " True " if match else " False "
                try:
                    if not eval(expr): continue
                except Exception: pass
            tag = "evenrow" if count % 2 == 0 else "oddrow"
            self.monster_tree.insert("", tk.END, values=(m["name"], m.get("type", "Unknown"), m.get("cr", "—"), m.get("source", "Unknown")), tags=(tag,))
            count += 1

    def open_spells_manager(self): self.stat_viewer.pack_forget(); self.combat_viewer.pack_forget(); self.search_frame.pack_forget(); self.spell_manager_frame.pack(fill=tk.BOTH, expand=True); self.apply_spell_query()
    def add_qblock(self, b): self.query_blocks.append(b); self.render_qblocks(); self.apply_spell_query()
    def clear_qblocks(self): self.query_blocks.clear(); self.render_qblocks(); self.apply_spell_query()
    def remove_qblock(self, idx): self.query_blocks.pop(idx); self.render_qblocks(); self.apply_spell_query()
    def toggle_qblock_op(self, idx): self.query_blocks[idx] = "OR" if self.query_blocks[idx] == "AND" else "AND"; self.render_qblocks(); self.apply_spell_query()

    def render_qblocks(self):
        for w in self.query_canvas_frame.winfo_children(): w.destroy()
        if not self.query_blocks:
            tk.Label(self.query_canvas_frame, text="No active filters.", bg="#f5e6ce", fg="#555555", font=("Arial", 10, "italic")).pack(padx=10, pady=5)
            return
        for i, b in enumerate(self.query_blocks):
            if isinstance(b, str):
                bg_col = "#ff4d4d" if b == "AND" else ("#4a90e2" if b == "OR" else "#e0cbb0")
                fg_col = "white" if b in ["AND", "OR"] else "black"
                btn = tk.Button(self.query_canvas_frame, text=b, bg=bg_col, fg=fg_col, font=("Arial", 9, "bold"))
                if b in ["AND", "OR"]:
                    btn.config(command=lambda idx=i: self.toggle_qblock_op(idx))
                    btn.bind("<Button-3>", lambda e, idx=i: self.remove_qblock(idx))
                else: btn.config(command=lambda idx=i: self.remove_qblock(idx))
            else:
                text = f"Lvl {b['min']}-{b['max']}" if b["type"] == "level" else f"{b['type'].title()}: {b['val']}"
                btn = tk.Button(self.query_canvas_frame, text=text, bg="#7a200d", fg="white", font=("Arial", 9, "bold"), command=lambda idx=i: self.remove_qblock(idx))
            btn.pack(side=tk.LEFT, padx=2, pady=2)

    def open_filter_dialog(self):
        d = tk.Toplevel(self)
        d.title("Build Filter")
        d.geometry("460x550")
        d.configure(bg="#fdf1dc")
        
        tk.Label(d, text="Add Filter Conditions", bg="#fdf1dc", fg="#7a200d", font=("Georgia", 14, "bold")).pack(pady=10)
        
        logic_var = tk.StringVar(value="AND")
        def toggle_logic():
            if logic_var.get() == "AND":
                logic_var.set("OR")
                btn_logic.config(text="OR", bg="#4a90e2")
            else:
                logic_var.set("AND")
                btn_logic.config(text="AND", bg="#ff4d4d")
                
        btn_logic = tk.Button(d, text="AND", bg="#ff4d4d", fg="white", font=("Arial", 12, "bold"), width=10, command=toggle_logic)
        btn_logic.pack(pady=5)
        
        f = tk.Frame(d, bg="#fdf1dc")
        f.pack(fill=tk.BOTH, expand=True, padx=30)
        
        tk.Label(f, text="Min Level:", bg="#fdf1dc", fg="black", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="e", pady=8, padx=10)
        min_v = tk.Scale(f, from_=0, to=12, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=160)
        min_v.grid(row=0, column=1, sticky="w", pady=8, padx=10)
        
        tk.Label(f, text="Max Level:", bg="#fdf1dc", fg="black", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="e", pady=8, padx=10)
        max_v = tk.Scale(f, from_=0, to=12, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=160)
        max_v.set(12)
        max_v.grid(row=1, column=1, sticky="w", pady=8, padx=10)

        tk.Label(f, text="School:", bg="#fdf1dc", fg="black", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="e", pady=8, padx=10)
        sch_v = ttk.Combobox(f, values=["All", "Abjuration", "Conjuration", "Divination", "Enchantment", "Illusion", "Necromancy", "Transmutation", "Evocation", "Psionic"], state="readonly", width=18)
        sch_v.set("All")
        sch_v.grid(row=2, column=1, sticky="w", pady=8, padx=10)

        tk.Label(f, text="Damage:", bg="#fdf1dc", fg="black", font=("Arial", 10, "bold")).grid(row=3, column=0, sticky="e", pady=8, padx=10)
        dmg_v = ttk.Combobox(f, values=["All", "Acid", "Bludgeoning", "Cold", "Fire", "Force", "Lightning", "Necrotic", "Piercing", "Poison", "Psychic", "Radiant", "Slashing", "Thunder"], state="readonly", width=18)
        dmg_v.set("All")
        dmg_v.grid(row=3, column=1, sticky="w", pady=8, padx=10)

        tk.Label(f, text="Save:", bg="#fdf1dc", fg="black", font=("Arial", 10, "bold")).grid(row=4, column=0, sticky="e", pady=8, padx=10)
        save_v = ttk.Combobox(f, values=["All", "Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"], state="readonly", width=18)
        save_v.set("All")
        save_v.grid(row=4, column=1, sticky="w", pady=8, padx=10)

        tk.Label(f, text="Concentration:", bg="#fdf1dc", fg="black", font=("Arial", 10, "bold")).grid(row=5, column=0, sticky="e", pady=8, padx=10)
        conc_v = ttk.Combobox(f, values=["All", "Yes", "No"], state="readonly", width=18)
        conc_v.set("All")
        conc_v.grid(row=5, column=1, sticky="w", pady=8, padx=10)
        
        def apply_f():
            filters = []
            if min_v.get() > 0 or max_v.get() < 12: filters.append({"type": "level", "min": min_v.get(), "max": max_v.get()})
            if sch_v.get() != "All":
                sch_map = {"Abjuration": "A", "Conjuration": "C", "Divination": "D", "Enchantment": "E", "Illusion": "I", "Necromancy": "N", "Transmutation": "T", "Evocation": "V", "Psionic": "P"}
                filters.append({"type": "school", "val": sch_map[sch_v.get()]})
            if dmg_v.get() != "All": filters.append({"type": "damage", "val": dmg_v.get().lower()})
            if save_v.get() != "All": filters.append({"type": "save", "val": save_v.get().lower()})
            if conc_v.get() != "All": filters.append({"type": "concentration", "val": conc_v.get() == "Yes"})
                
            if not filters:
                d.destroy()
                return
                
            op = logic_var.get()
            if self.query_blocks: self.query_blocks.append(op)
            for i, f_block in enumerate(filters):
                self.query_blocks.append(f_block)
                if i < len(filters) - 1: self.query_blocks.append(op)
                    
            self.render_qblocks()
            self.apply_spell_query()
            d.destroy()
            
        tk.Button(d, text="Apply Filters", bg="#d9ad6c", fg="black", font=("Arial", 11, "bold"), command=apply_f).pack(pady=20)

    def apply_spell_query(self):
        for item in self.spell_tree.get_children(): self.spell_tree.delete(item)
        q_str = self.spell_search_var.get().lower()
        count = 0
        for s in self.spells_index:
            if q_str and q_str not in s["name"].lower(): continue
            if self.query_blocks:
                expr = ""
                for b in self.query_blocks:
                    if b in ["AND", "OR", "(", ")"]: expr += f" {b.lower()} "
                    else:
                        m = True
                        if b["type"] == "level" and (s.get("level", 0) < b["min"] or s.get("level", 0) > b["max"]): m = False
                        elif b["type"] == "school" and s.get("school", "") != b["val"]: m = False
                        elif b["type"] == "damage" and b["val"] not in s.get("damageInflict", []): m = False
                        elif b["type"] == "save" and b["val"] not in s.get("savingThrow", []): m = False
                        elif b["type"] == "concentration" and s.get("duration", [{}])[0].get("concentration", False) != b["val"]: m = False
                        expr += " True " if m else " False "
                try:
                    if not eval(expr): continue
                except Exception: pass
            tag = "evenrow" if count % 2 == 0 else "oddrow"
            self.spell_tree.insert("", tk.END, values=(s["name"], "Cantrip" if s.get("level", 0) == 0 else str(s.get("level", 0)), utils.SCHOOL_MAP.get(s.get("school", ""), "Unknown"), s.get("source", "Unknown")), tags=(tag,))
            count += 1

    def on_spell_manager_selected(self, event):
        sel = self.spell_tree.selection()
        if not sel: return
        sn = self.spell_tree.item(sel[0])['values'][0]
        sd = next((s for s in self.spells_index if s["name"].lower() == sn.lower()), None)
        if sd: self.display_spell_by_data(sd, edit_mode=False, back_cb=self.open_spells_manager)

    def create_new_spell(self):
        sn = simpledialog.askstring("New Spell", "Enter a name for the new spell:")
        if not sn or not sn.strip() or any(s["name"].lower() == sn.lower() for s in self.spells_index): return
        sf = "".join([c for c in sn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        nd = {"name": sn, "source": "Custom", "level": 1, "school": "V", "time": [{"number": 1, "unit": "action"}], "range": {"type": "point", "distance": {"type": "feet", "amount": 60}}, "components": {"v": True, "s": True}, "duration": [{"type": "instant"}], "entries": ["Describe spell."]}
        self.spells_index.append(nd); self.spells_index = sorted(self.spells_index, key=lambda x: x["name"].lower())
        json.dump(nd, open(self.spells_dir / f"{sf}.json", "w", encoding="utf-8"), indent=4)
        json.dump(self.spells_index, open("spells.json", "w", encoding="utf-8"), indent=4)
        self.stat_viewer.set_spells_index(self.spells_index); self.refresh_tree()
        self.display_spell_by_data(nd, edit_mode=True, is_custom=True, back_cb=self.clear_viewer_and_tree)

    def display_spell_by_data(self, data, edit_mode=False, is_custom=False, back_cb=None):
        self.search_frame.pack_forget(); self.combat_viewer.pack_forget(); self.spell_manager_frame.pack_forget(); self.stat_viewer.pack(fill=tk.BOTH, expand=True)
        if edit_mode: self.stat_viewer.render_spell_edit_mode(data, self.save_spell_edits, back_cb)
        else:
            self.stat_viewer.render_spell(data, back_cb=back_cb)
            if is_custom: self.stat_viewer.add_custom_spell_buttons(data, lambda d: self.display_spell_by_data(d, edit_mode=True, is_custom=True, back_cb=back_cb), self.delete_custom_spell)

    def save_spell_edits(self, old_name, new_data):
        nn = new_data["name"]; sf = "".join([c for c in nn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
        if old_name and old_name.lower() != nn.lower():
            osf = "".join([c for c in old_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
            if (self.spells_dir / f"{osf}.json").exists(): (self.spells_dir / f"{osf}.json").unlink()
        t_idx = next((i for i, s in enumerate(self.spells_index) if s["name"].lower() == old_name.lower()), -1)
        if t_idx >= 0: self.spells_index[t_idx] = new_data
        else: self.spells_index.append(new_data)
        self.spells_index = sorted(self.spells_index, key=lambda x: x["name"].lower())
        json.dump(new_data, open(self.spells_dir / f"{sf}.json", "w", encoding="utf-8"), indent=4)
        json.dump(self.spells_index, open("spells.json", "w", encoding="utf-8"), indent=4)
        self.stat_viewer.set_spells_index(self.spells_index); self.refresh_tree()
        self.display_spell_by_data(new_data, edit_mode=False, is_custom=True, back_cb=self.clear_viewer_and_tree)

    def delete_custom_spell(self, s_data):
        if messagebox.askyesno("Confirm Delete", f"Delete spell '{s_data['name']}'?"):
            self.spells_index = [s for s in self.spells_index if s["name"].lower() != s_data["name"].lower()]
            sf = "".join([c for c in s_data["name"] if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
            if (self.spells_dir / f"{sf}.json").exists(): (self.spells_dir / f"{sf}.json").unlink()
            json.dump(self.spells_index, open("spells.json", "w", encoding="utf-8"), indent=4)
            self.stat_viewer.set_spells_index(self.spells_index); self.refresh_tree()
            self.open_spells_manager() if self.spell_manager_frame.winfo_ismapped() else self.clear_viewer_and_tree()

    def on_spell_clicked(self, s_name):
        sd = next((s for s in self.spells_index if s["name"].lower() == s_name.lower()), None)
        if not sd: messagebox.showinfo("Not Found", f"Run fetch_spells.py for '{s_name}'!"); return
        self.display_spell_by_data(sd, back_cb=lambda: self.display_monster(self.current_open_node) if self.current_open_node else None)

    def clear_viewer_and_tree(self): self.stat_viewer.pack_forget(); self.combat_viewer.pack_forget(); self.refresh_tree()
    def _get_open_paths(self, nodes): return {str(n.path) for n in nodes if n.is_open}.union(*(self._get_open_paths(n.children) for n in nodes))
    def _set_node_open(self, target, state, nodes=None):
        for n in (nodes if nodes is not None else getattr(self, 'nodes', [])):
            if n.path == target: n.is_open = state; return True
            if self._set_node_open(target, state, n.children): n.is_open = True; return True
        return False

    def on_monster_selected(self, event):
        selected_item = self.monster_tree.selection()
        if not selected_item: return
        item = self.monster_tree.item(selected_item[0])
        monster_meta = next((m for m in self.monster_index if m["name"] == item['values'][0] and m.get("source", "Unknown") == item['values'][3]), None)
        if not monster_meta: return
        
        try:
            global_monster_dir, safe_name = downloader.download_monster_data(monster_meta, self.monsters_dir)
            if not global_monster_dir: return
            
            if hasattr(self, 'current_target_folder') and (self.map_dir in self.current_target_folder.parents or self.current_target_folder == self.map_dir):
                local_ref_dir = self.current_target_folder / safe_name
                local_ref_dir.mkdir(parents=True, exist_ok=True)
                with open(local_ref_dir / "reference.json", "w", encoding="utf-8") as f:
                    json.dump({"type": "Monsters", "target": safe_name}, f, indent=4)
                final_display_path = local_ref_dir
            else:
                final_display_path = global_monster_dir

            self._set_node_open(self.current_target_folder if hasattr(self, 'current_target_folder') else self.monsters_dir, True)
            self.refresh_tree()
            self.display_monster_by_path(final_display_path, edit_mode=False)
        except Exception as ex:
            messagebox.showerror("Download Error", f"Failed: {ex}")

    def add_existing_reference(self, local_parent_path: Path):
        folder_category = local_parent_path.name
        global_source_dir = self.root_dir / folder_category
        
        if not global_source_dir.exists():
            messagebox.showerror("Error", f"Global storage directory '{folder_category}' missing.")
            return

        available_items = sorted([p.name for p in global_source_dir.iterdir() if p.is_dir()])
        if not available_items:
            messagebox.showinfo("Empty", f"No entities exist in global '{folder_category}' yet.\nCreate them globally or download from a database first.")
            return

        dialog = tk.Toplevel(self)
        dialog.title(f"Link Existing {folder_category[:-1]}")
        dialog.geometry("450x550")
        dialog.configure(bg="#fdf1dc")
        dialog.transient(self)
        
        dialog.wait_visibility()
        dialog.grab_set()

        tk.Label(dialog, text=f"Choose a global {folder_category[:-1]} to link:", bg="#fdf1dc", fg="#7a200d", font=("Georgia", 13, "bold")).pack(pady=10)
        
        listbox_frame = tk.Frame(dialog, bg="#fdf1dc")
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        tree = ttk.Treeview(listbox_frame, columns=("name",), show="headings", selectmode="browse")
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree.heading("name", text="Available Entities", anchor="w")
        tree.tag_configure("evenrow", background="#f5e6ce", foreground="black")
        tree.tag_configure("oddrow", background="#fae6c5", foreground="black")
        
        scroll = ttk.Scrollbar(listbox_frame, orient="vertical", command=tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scroll.set)
        
        for i, item in enumerate(available_items):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            tree.insert("", tk.END, values=(item,), tags=(tag,))

        def confirm_selection():
            sel = tree.selection()
            if not sel: return
            target_item_name = tree.item(sel[0])['values'][0]
            
            local_link_dir = local_parent_path / target_item_name
            if local_link_dir.exists():
                messagebox.showwarning("Duplicate", "This reference file link already exists in this folder.")
                dialog.destroy()
                return

            local_link_dir.mkdir(parents=True, exist_ok=True)
            with open(local_link_dir / "reference.json", "w", encoding="utf-8") as f:
                json.dump({"type": folder_category, "target": target_item_name}, f, indent=4)

            self._set_node_open(local_parent_path, True)
            self.refresh_tree()
            dialog.destroy()
            
            if folder_category == "Combats":
                self.display_combat_by_path(local_link_dir, edit_mode=False)
            else:
                self.display_monster_by_path(local_link_dir, edit_mode=False)

        tree.bind("<Double-1>", lambda e: confirm_selection())
        tk.Button(dialog, text="Link Selected", bg="#d9ad6c", fg="black", font=("Arial", 11, "bold"), command=confirm_selection).pack(pady=15)

    def create_new_combat(self, parent_path: Path):
        base_name = "New Combat"
        safe_name = base_name
        counter = 1
        while (self.combats_dir / safe_name).exists() or (parent_path / safe_name).exists():
            safe_name = f"{base_name} {counter}"
            counter += 1

        global_combat_dir = self.combats_dir / safe_name
        global_combat_dir.mkdir(parents=True, exist_ok=True)

        combat_data = {
            "name": safe_name,
            "location": parent_path.parent.name if self.map_dir in parent_path.parents else "Any",
            "time": "Any",
            "description": "None",
            "over": "No",
            "outcome": "None",
            "participants": []
        }

        with open(global_combat_dir / f"{safe_name}.json", "w", encoding="utf-8") as f:
            json.dump(combat_data, f, indent=4)

        # FIXED: Copies over utils/combat_icon.png automatically to assign the customized folder graphics
        combat_icon_src = Path("./utils/combat_icon.png")
        if combat_icon_src.exists():
            try:
                shutil.copy(combat_icon_src, global_combat_dir / "portrait.png")
                img = Image.open(combat_icon_src)
                img.thumbnail((64, 64))
                img.save(global_combat_dir / "icon.webp", "WEBP")
            except: pass

        if self.map_dir in parent_path.parents or parent_path == self.map_dir:
            local_ref_dir = parent_path / safe_name
            local_ref_dir.mkdir(parents=True, exist_ok=True)
            with open(local_ref_dir / "reference.json", "w", encoding="utf-8") as f:
                json.dump({"type": "Combats", "target": safe_name}, f, indent=4)
            display_path = local_ref_dir
        else:
            display_path = global_combat_dir

        self._set_node_open(parent_path, True)
        self.refresh_tree()
        self.display_combat_by_path(display_path)

    def save_combat_edits(self, old_dir: Path, new_data: dict):
        ref_file = old_dir / "reference.json"
        if ref_file.exists():
            with open(ref_file, "r", encoding="utf-8") as f:
                ref_data = json.load(f)
            g_type = ref_data.get("type")
            old_target_name = ref_data.get("target")
            global_dir = self.root_dir / g_type / old_target_name
            is_ref = True
        else:
            g_type = old_dir.parent.name
            old_target_name = old_dir.name
            global_dir = old_dir
            is_ref = False

        new_name = new_data.get("name", "Unknown Combat")
        new_safe_name = "".join([c for c in new_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
        if not new_safe_name: new_safe_name = "Unnamed"

        if new_safe_name != old_target_name:
            target_global_dir = global_dir.parent / new_safe_name
            if target_global_dir.exists() and target_global_dir != global_dir:
                messagebox.showerror("Error", f"A combat named {new_safe_name} already exists.")
                return

            old_json = global_dir / f"{old_target_name}.json"
            new_json = global_dir / f"{new_safe_name}.json" 
            if old_json.exists(): old_json.rename(new_json)

            global_dir.rename(target_global_dir)
            global_dir = target_global_dir

            for p in self.map_dir.rglob("reference.json"):
                try:
                    with open(p, "r", encoding="utf-8") as rf:
                        r_data = json.load(rf)
                    if r_data.get("type") == g_type and r_data.get("target") == old_target_name:
                        r_data["target"] = new_safe_name
                        with open(p, "w", encoding="utf-8") as wf: json.dump(r_data, wf, indent=4)
                        p.parent.rename(p.parent.parent / new_safe_name)
                except: pass

        with open(global_dir / f"{new_safe_name}.json", "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4)

        self.refresh_tree()
        final_display = (old_dir.parent / new_safe_name) if is_ref else global_dir
        self.display_combat_by_path(final_display, edit_mode=False)

    def display_combat_by_path(self, target_path: Path, edit_mode=False):
        def search_nodes(nodes):
            for n in nodes:
                if n.path == target_path and n.is_entity: return n
                res = search_nodes(n.children)
                if res: return res
            return None
        
        target_node = search_nodes(self.nodes)
        
        if not target_node:
            ref_json_path = target_path / "reference.json"
            if ref_json_path.exists():
                try:
                    with open(ref_json_path, "r", encoding="utf-8") as f:
                        ref_data = json.load(f)
                    global_folder = self.root_dir / ref_data.get("type", "") / ref_data.get("target", "")
                    jsons = list(global_folder.glob("*.json"))
                    if jsons:
                        target_node = Node(name=target_path.name, path=target_path, is_entity=True, level=0, stat_path=jsons[0])
                except: pass
            else:
                jsons = list(target_path.glob("*.json"))
                if jsons: 
                    target_node = Node(name=target_path.name, path=target_path, is_entity=True, level=0, stat_path=jsons[0])

        if target_node: 
            # FIXED: Removed edit_mode argument to match the unified display_combat signature
            self.display_combat(target_node)

    def display_combat(self, node: Node):
        self.current_open_node = node
        self.search_frame.pack_forget()
        self.spell_manager_frame.pack_forget()
        self.stat_viewer.pack_forget()
        self.combat_viewer.pack(fill=tk.BOTH, expand=True)
        if not node or not node.stat_path: return

        try:
            with open(node.stat_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # FIXED: Routes parameters directly to unified interactive workspace view
            self.combat_viewer.render_combat(data, node.path)
        except Exception as e: 
            print(f"Failed to load combat: {e}")

    def refresh_tree(self):
        open_paths = self._get_open_paths(getattr(self, 'nodes', []))
        
        map_node = Node(name="Map", path=self.map_dir, is_entity=False, level=0, icon_path=Path("./utils/map.png") if Path("./utils/map.png").exists() else None, is_open=str(self.map_dir) in open_paths)
        map_node.children = self.build_tree_model(self.map_dir, level=1, open_paths=open_paths)

        spell_node = Node(name="Spells", path=self.spells_dir, is_entity=False, level=0, icon_path=Path("./utils/spell.png") if Path("./utils/spell.png").exists() else None, is_open=str(self.spells_dir) in open_paths, action_type="open_spells")
        spell_node.children = self.build_tree_model(self.spells_dir, level=1, open_paths=open_paths)

        monsters_node = Node(name="Monsters", path=self.monsters_dir, is_entity=False, level=0, icon_path=Path("./utils/monster.png") if Path("./utils/monster.png").exists() else None, is_open=str(self.monsters_dir) in open_paths)
        monsters_node.children = self.build_tree_model(self.monsters_dir, level=1, open_paths=open_paths)

        npcs_node = Node(name="NPCs", path=self.npcs_dir, is_entity=False, level=0, icon_path=Path("./utils/npc.png") if Path("./utils/npc.png").exists() else None, is_open=str(self.npcs_dir) in open_paths)
        npcs_node.children = self.build_tree_model(self.npcs_dir, level=1, open_paths=open_paths)

        combats_node = Node(name="Combats", path=self.combats_dir, is_entity=False, level=0, icon_path=Path("./utils/combat.png") if Path("./utils/combat.png").exists() else None, is_open=str(self.combats_dir) in open_paths)
        combats_node.children = self.build_tree_model(self.combats_dir, level=1, open_paths=open_paths)
        
        self.nodes = [map_node, spell_node, monsters_node, npcs_node, combats_node]
        self.render_tree()

    def build_tree_model(self, path: Path, level: int, open_paths: set):
        nodes = []
        try: 
            all_items = sorted([p for p in path.iterdir()], key=lambda x: x.name.lower())
            dirs = [p for p in all_items if p.is_dir()]
            files = [p for p in all_items if p.is_file() and p.suffix == '.json']
        except PermissionError: return nodes

        for item in files:
            node = Node(name=item.stem, path=item, is_entity=True, level=level, icon_path=Path("./utils/spell_icon.png"), stat_path=item)
            nodes.append(node)

        for item in dirs:
            ref_json_path = item / "reference.json"
            if ref_json_path.exists():
                try:
                    with open(ref_json_path, "r", encoding="utf-8") as f:
                        ref_data = json.load(f)
                    global_folder = self.root_dir / ref_data.get("type", "") / ref_data.get("target", "")
                    if global_folder.exists():
                        g_jsons = list(global_folder.glob("*.json"))
                        g_webps = list(global_folder.glob("*.webp"))
                        if g_jsons:
                            node = Node(name=item.name, path=item, is_entity=True, level=level, icon_path=g_webps[0] if g_webps else None, stat_path=g_jsons[0])
                            nodes.append(node)
                            continue
                except: pass

            jsons = list(item.glob("*.json"))
            webps = list(item.glob("*.webp"))

            if jsons and not item.name in ["Monsters", "NPCs", "Combats"]:
                node = Node(name=item.name, path=item, is_entity=True, level=level, icon_path=webps[0] if webps else None, stat_path=jsons[0])
                nodes.append(node)
            else:
                icon_path = None
                is_core = item.name in ["Monsters", "NPCs", "Combats"]
                if is_core:
                    if item.name == "Monsters": icon_path = Path("./utils/monster.png")
                    elif item.name == "NPCs": icon_path = Path("./utils/npc.png")
                    elif item.name == "Combats": icon_path = Path("./utils/combat.png")
                
                if not icon_path or not icon_path.exists():
                    for ext in ['.png', '.webp', '.jpg']:
                        possible_icon = item / f"{item.name}{ext}"
                        if possible_icon.exists():
                            icon_path = possible_icon
                            break
                
                node = Node(name=item.name, path=item, is_entity=False, level=level, icon_path=icon_path, is_open=str(item) in open_paths)
                node.children = self.build_tree_model(item, level + 1, open_paths)
                nodes.append(node)

        action_map = {"Monsters": "new_monster", "NPCs": "new_npc", "Combats": "new_combat"}
        if path.name in action_map:
            nodes.append(Node(name="New", path=path, is_entity=False, level=level, action_type=action_map[path.name], icon_path=Path("./utils/new.png")))
            if self.map_dir in path.parents or path == self.map_dir:
                nodes.append(Node(name="Add Existing", path=path, is_entity=False, level=level, action_type="add_existing", icon_path=Path("./utils/new.png")))
        elif path == self.spells_dir:
            nodes.append(Node(name="New", path=path, is_entity=False, level=level, action_type="new_spell", icon_path=Path("./utils/new.png")))
        elif path == self.map_dir or (self.map_dir in path.parents and path.name not in action_map):
            nodes.append(Node(name="Add Location", path=path, is_entity=False, level=level, action_type="new_location", icon_path=Path("./utils/new.png")))
            
        return nodes

    def render_tree(self):
        for widget in self.tree_inner.winfo_children(): widget.destroy()
        self.image_cache.clear()

        def draw_node(node):
            row = tk.Frame(self.tree_inner, bg="#fae6c5")
            row.pack(fill=tk.X, pady=2)
            indent = node.level * 35 + 10
            
            is_action_btn = bool(node.action_type)
            text_font = ("Georgia", 13)
            text_color = "black"
            
            if not node.is_entity and not is_action_btn:
                text_font = ("Georgia", 15, "bold")
            if is_action_btn:
                text_font = ("Georgia", 13, "italic")

            if node.icon_path and node.icon_path.exists():
                try:
                    img = Image.open(node.icon_path).resize((44, 44), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.image_cache.append(photo)
                    icon_lbl = tk.Label(row, image=photo, bg="#fae6c5", cursor="hand2")
                except:
                    icon_lbl = tk.Label(row, text="?", width=4, height=2, bg="#444", fg="white", cursor="hand2")
            else:
                icon_text = "+" if is_action_btn else ("E" if node.is_entity else "📁")
                icon_lbl = tk.Label(row, text=icon_text, width=4, height=2, bg="#444", fg="white", cursor="hand2")
            
            icon_lbl.pack(side=tk.LEFT, padx=(indent, 15), pady=6)
            text_lbl = tk.Label(row, text=node.name, bg="#fae6c5", fg=text_color, font=text_font, cursor="hand2")
            text_lbl.pack(side=tk.LEFT, pady=6)

            del_btn = None
            if not is_action_btn and node.name not in ["Map", "Spells", "Monsters", "NPCs", "Combats"]:
                del_btn = tk.Label(row, text="X", bg="#fae6c5", fg="#ff4d4d", font=("Arial", 16, "bold"), cursor="hand2")
                del_btn.pack(side=tk.RIGHT, padx=15)
                del_btn.bind("<Enter>", lambda e: e.widget.configure(bg="#4a2222", fg="#ffffff"))
                del_btn.bind("<Leave>", lambda e: e.widget.configure(bg="#f5e6ce" if row.cget("bg") == "#f5e6ce" else "#fae6c5", fg="#ff4d4d"))

                def on_del_click(e, n=node):
                    target_type = "entry" if n.is_entity else "folder"
                    msg = f"Are you sure you want to delete this {target_type} '{n.name}'?\nThis will erase the directory and all its contents from your computer."
                    if messagebox.askyesno("Confirm Delete", msg):
                        try:
                            if n.path.is_file(): 
                                if n.path.parent == self.spells_dir:
                                    try:
                                        with open(n.stat_path, "r", encoding="utf-8") as f:
                                            del_data = json.load(f)
                                        del_name = del_data.get("name", "")
                                        self.spells_index = [s for s in self.spells_index if s["name"].lower() != del_name.lower()]
                                        with open("spells.json", "w", encoding="utf-8") as f:
                                            json.dump(self.spells_index, f, indent=4)
                                        self.stat_viewer.set_spells_index(self.spells_index)
                                    except Exception: pass
                                n.path.unlink()
                            else: 
                                if (n.path / "reference.json").exists():
                                    shutil.rmtree(n.path)
                                else:
                                    parent_domain = n.path.parent.name
                                    if parent_domain in ["Monsters", "NPCs", "Combats"]:
                                        global_id = n.path.name
                                        shutil.rmtree(n.path)
                                        for ref in self.map_dir.rglob("reference.json"):
                                            try:
                                                with open(ref, "r", encoding="utf-8") as rf:
                                                    r_data = json.load(rf)
                                                if r_data.get("type") == parent_domain and r_data.get("target") == global_id:
                                                    shutil.rmtree(ref.parent)
                                            except Exception: pass
                                    else:
                                        shutil.rmtree(n.path)

                            self.refresh_tree()
                            self.stat_viewer.pack_forget() 
                            self.combat_viewer.pack_forget()
                            if self.spell_manager_frame.winfo_ismapped(): self.apply_spell_query()
                            if self.search_frame.winfo_ismapped(): self.apply_monster_query()
                        except Exception as ex: messagebox.showerror("Error", f"Failed to delete:\n{ex}")
                del_btn.bind("<Button-1>", on_del_click)

            def on_enter(e): 
                row.configure(bg="#f5e6ce")
                icon_lbl.configure(bg="#f5e6ce")
                text_lbl.configure(bg="#f5e6ce")
                if del_btn and del_btn.cget("bg") != "#4a2222": del_btn.configure(bg="#f5e6ce")
            
            def on_leave(e): 
                row.configure(bg="#fae6c5")
                icon_lbl.configure(bg="#fae6c5")
                text_lbl.configure(bg="#fae6c5")
                if del_btn and del_btn.cget("bg") != "#4a2222": del_btn.configure(bg="#fae6c5")
                
            row.bind("<Enter>", on_enter)
            row.bind("<Leave>", on_leave)
            
            def on_click(e):
                if node.action_type == "new_location": self.create_new_location(node.path)
                elif node.action_type == "new_monster": self.show_search_panel(node.path)
                elif node.action_type == "new_npc": self.create_new_npc(node.path)
                elif node.action_type == "new_combat": self.create_new_combat(node.path)
                elif node.action_type == "add_existing": self.add_existing_reference(node.path)
                elif node.action_type == "open_spells": 
                    node.is_open = not node.is_open
                    self.open_spells_manager()
                    self.render_tree()
                elif node.action_type == "new_spell": self.create_new_spell()
                elif node.is_entity:
                    if node.path.parent == self.spells_dir:
                        with open(node.stat_path, "r", encoding="utf-8") as f:
                            self.display_spell_by_data(json.load(f), edit_mode=False, is_custom=True, back_cb=self.clear_viewer_and_tree)
                    else:
                        is_combat = False
                        if "Combats" in node.path.parts: is_combat = True
                        elif (node.path / "reference.json").exists():
                            with open(node.path / "reference.json", "r", encoding="utf-8") as f:
                                if json.load(f).get("type") == "Combats": is_combat = True
                        if is_combat:
                            self.display_combat(node)
                        else:
                            self.display_monster(node)
                else:
                    node.is_open = not node.is_open
                    self.render_tree()

            def on_icon_click(e):
                is_core_folder = (node.name in ["Monsters", "NPCs", "Combats", "Map", "Spells"])
                if not is_action_btn and not is_core_folder and node.path.parent != self.spells_dir: 
                    self.change_folder_icon(node)
                else: 
                    on_click(e)

            icon_lbl.bind("<Button-1>", on_icon_click)
            text_lbl.bind("<Button-1>", on_click)
            row.bind("<Button-1>", on_click)

            if not node.is_entity and node.is_open:
                for child in node.children: draw_node(child)

        for node in self.nodes: draw_node(node)

    def create_new_location(self, p_path: Path):
        fn = simpledialog.askstring("Add Location", "Location name:")
        if not fn or not fn.strip(): return
        sn = "".join([c for c in fn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        
        nd = p_path / sn
        nd.mkdir(parents=True, exist_ok=True)
        
        for sub in ["Monsters", "NPCs", "Combats"]: 
            (nd / sub).mkdir(parents=True, exist_ok=True)
            
        if Path("./utils/default.png").exists(): 
            try:
                img = Image.open("./utils/default.png")
                img.thumbnail((64, 64))
                img.save(nd / f"{sn}.png", "PNG")
            except Exception as e:
                print(f"Failed to save customized layout thumbnail icon: {e}")
                
        self._set_node_open(p_path, True)
        self.refresh_tree()

    def create_new_npc(self, parent_path: Path):
        base_name = "New NPC"
        safe_name = base_name
        counter = 1
        while (self.npcs_dir / safe_name).exists() or (parent_path / safe_name).exists():
            safe_name = f"{base_name} {counter}"
            counter += 1

        global_npc_dir = self.npcs_dir / safe_name
        global_npc_dir.mkdir(parents=True, exist_ok=True)

        npc_data = {
            "name": safe_name, "source": "Custom", "level": 1, "size": ["M"], "type": "humanoid",
            "alignment": ["N"], "ac": [10], "hp": {"average": 4, "formula": "1d8"},
            "speed": {"walk": 30}, "str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10,
            "action": [{"name": "Unarmed Strike", "entries": ["{@atk mw} {@hit 2} to hit, reach 5 ft., one target. {@h}1 bludgeoning damage."]}]
        }

        with open(global_npc_dir / f"{safe_name}.json", "w", encoding="utf-8") as f:
            json.dump(npc_data, f, indent=4)

        default_npc_icon = Path("./utils/default_npc.png")
        if default_npc_icon.exists():
            try:
                img = Image.open(default_npc_icon)
                img.save(global_npc_dir / "portrait.png", "PNG")
                img.thumbnail((64, 64))
                img.save(global_npc_dir / "icon.webp", "WEBP")
            except: pass

        if self.map_dir in parent_path.parents or parent_path == self.map_dir:
            local_ref_dir = parent_path / safe_name
            local_ref_dir.mkdir(parents=True, exist_ok=True)
            with open(local_ref_dir / "reference.json", "w", encoding="utf-8") as f:
                json.dump({"type": "NPCs", "target": safe_name}, f, indent=4)
            display_path = local_ref_dir
        else:
            display_path = global_npc_dir

        self._set_node_open(parent_path, True)
        self.refresh_tree()
        self.display_monster_by_path(display_path, edit_mode=True)

    def save_monster_edits(self, old_dir: Path, new_data: dict):
        ref_file = old_dir / "reference.json"
        if ref_file.exists():
            with open(ref_file, "r", encoding="utf-8") as f:
                ref_data = json.load(f)
            g_type = ref_data.get("type")
            old_target_name = ref_data.get("target")
            global_dir = self.root_dir / g_type / old_target_name
            is_ref = True
        else:
            g_type = old_dir.parent.name
            old_target_name = old_dir.name
            global_dir = old_dir
            is_ref = False

        new_name = new_data.get("name", "Unknown")
        new_safe_name = "".join([c for c in new_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
        if not new_safe_name: new_safe_name = "Unnamed"

        if new_safe_name != old_target_name:
            target_global_dir = global_dir.parent / new_safe_name
            if target_global_dir.exists() and target_global_dir != global_dir:
                messagebox.showerror("Error", f"An entry named {new_safe_name} already exists.")
                return

            old_json = global_dir / f"{old_target_name}.json"
            new_json = global_dir / f"{new_safe_name}.json" 
            if old_json.exists(): old_json.rename(new_json)

            global_dir.rename(target_global_dir)
            global_dir = target_global_dir

            for p in self.map_dir.rglob("reference.json"):
                try:
                    with open(p, "r", encoding="utf-8") as rf:
                        r_data = json.load(rf)
                    if r_data.get("type") == g_type and r_data.get("target") == old_target_name:
                        r_data["target"] = new_safe_name
                        with open(p, "w", encoding="utf-8") as wf: json.dump(r_data, wf, indent=4)
                        p.parent.rename(p.parent.parent / new_safe_name)
                except: pass

        with open(global_dir / f"{new_safe_name}.json", "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4)

        self.refresh_tree()
        final_display = (old_dir.parent / new_safe_name) if is_ref else global_dir
        self.display_monster_by_path(final_display, edit_mode=False)

    def display_monster_by_path(self, target_path: Path, edit_mode=False, back_cb=None):
        def search_nodes(nodes):
            for n in nodes:
                if n.path == target_path and n.is_entity: return n
                res = search_nodes(n.children)
                if res: return res
            return None
        
        target_node = search_nodes(self.nodes)
        
        if not target_node:
            ref_json_path = target_path / "reference.json"
            if ref_json_path.exists():
                try:
                    with open(ref_json_path, "r", encoding="utf-8") as f:
                        ref_data = json.load(f)
                    global_folder = self.root_dir / ref_data.get("type", "") / ref_data.get("target", "")
                    jsons = list(global_folder.glob("*.json"))
                    if jsons:
                        target_node = Node(name=target_path.name, path=target_path, is_entity=True, level=0, stat_path=jsons[0])
                except: pass
            else:
                jsons = list(target_path.glob("*.json"))
                if jsons: 
                    target_node = Node(name=target_path.name, path=target_path, is_entity=True, level=0, stat_path=jsons[0])

        if target_node: 
            # FIXED: Pass down back_cb reference safely through discovery layer
            self.display_monster(target_node, edit_mode, back_cb=back_cb)

    def display_monster(self, node: Node, edit_mode=False, back_cb=None):
        self.search_frame.pack_forget()
        self.spell_manager_frame.pack_forget()
        self.combat_viewer.pack_forget()
        self.stat_viewer.pack(fill=tk.BOTH, expand=True)
        if not node or not node.stat_path: return

        try:
            with open(node.stat_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            loc_name = node.path.parent.parent.name if len(node.path.parts) >= 3 else "Unknown"
            if edit_mode: 
                self.stat_viewer.render_edit_mode(data, node.path, loc_name, self.save_monster_edits, lambda: self.display_monster(node, edit_mode=False, back_cb=back_cb))
            else:
                self.stat_viewer.render_monster(data)
                # FIXED: Pass back_cb into add_top_buttons directly to align with updated layout parameters
                self.stat_viewer.add_top_buttons(node.path, self.view_full_portrait, lambda d: self.display_monster(node, edit_mode=True, back_cb=back_cb), back_cb=back_cb)
        except Exception as e: 
            print(f"Failed to load monster template page: {e}")
    def change_folder_icon(self, node: Node):
        fp = filedialog.askopenfilename(title="Select icon", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
        if not fp: return
        try:
            img = Image.open(fp)
            if node.is_entity:
                for e in ['.png', '.jpg', '.jpeg', '.webp']: [ (node.path / f"{pre}{e}").unlink() for pre in ["portrait", "icon"] if (node.path / f"{pre}{e}").exists() ]
                img.save(node.path / "portrait.png", "PNG"); img.thumbnail((64, 64)); img.save(node.path / "icon.webp", "WEBP")
            else:
                img.thumbnail((64, 64))
                for e in ['.png', '.jpg', '.jpeg', '.webp']: 
                    if (node.path / f"{node.name}{e}").exists(): (node.path / f"{node.name}{e}").unlink()
                img.save(node.path / f"{node.name}.png", "PNG")
            self.refresh_tree()
        except Exception as ex: messagebox.showerror("Error", str(ex))

    def show_search_panel(self, target: Path):
        self.current_target_folder = target
        self.stat_viewer.pack_forget()
        self.combat_viewer.pack_forget()
        self.spell_manager_frame.pack_forget()
        self.search_frame.pack(fill=tk.BOTH, expand=True)
        self.search_entry.delete(0, tk.END)
        self.apply_monster_query()
        self.search_entry.focus()

    def view_full_portrait(self, monster_dir):
        p = monster_dir / "portrait.png"
        if not p.exists(): messagebox.showinfo("Info", "No artwork found."); return
        ov = tk.Frame(self.right_frame, bg="black")
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        img = Image.open(p); img.thumbnail((800, 800)); timg = ImageTk.PhotoImage(img)
        l = tk.Label(ov, image=timg, bg="black"); l.image = timg; l.pack(expand=True)
        tk.Button(ov, text="CLOSE", command=ov.destroy, bg="#58180d", fg="white", font=("Georgia", 14)).place(x=20, y=20)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--path", default="./data")
    args = parser.parse_args()
    Path(args.path).mkdir(parents=True, exist_ok=True)
    Path("./utils").mkdir(exist_ok=True)
    DnDStatManager(args.path).mainloop()

if __name__ == "__main__":
    main()