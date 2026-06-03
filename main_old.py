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

class PageState:
    """Linked list node representation to handle real-time state tracking history."""
    def __init__(self, node: Node, view_type: str, stat_path: Path = None, data: dict = None, prev=None):
        self.node = node
        self.view_type = view_type  # "root_folder", "location", "monster", "npc", "combat", "spell"
        self.stat_path = stat_path
        self.data = data
        self.prev = prev  # Pointer link reference to the preceding historical PageState node

class DnDStatManager(tk.Tk):
    def __init__(self, root_dir):
        super().__init__()
        self.title("D&D Campaign Manager - Stat Blocks")
        self.geometry("1500x850")
        self.configure(bg="#fdf1dc")
        
        self.root_dir = Path(root_dir).resolve()
        
        # Initialize Core Master System Folders
        self.map_dir = self.root_dir / "map"
        self.map_dir.mkdir(parents=True, exist_ok=True)
        self.spells_dir = self.root_dir / "spells"
        self.spells_dir.mkdir(parents=True, exist_ok=True)
        self.monsters_dir = self.root_dir / "Monsters"
        self.monsters_dir.mkdir(parents=True, exist_ok=True)
        self.npcs_dir = self.root_dir / "NPCs"
        self.npcs_dir.mkdir(parents=True, exist_ok=True)
        self.combats_dir = self.root_dir / "Combats"
        self.combats_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir = self.root_dir / "Events"
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.objects_dir = self.root_dir / "Objects"
        self.objects_dir.mkdir(parents=True, exist_ok=True)
                
        self.image_cache = []
        self.current_state = None  # Pointer head to track the active PageState node linked list
        
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
        
        # Set default homepage view to master map node path object
        initial_node = Node(name="Campaign Map", path=self.map_dir, is_entity=False, level=0)
        self.open_page(initial_node, view_type="root_folder")
        # Bind global mouse-wheel event scrolling directly
        self.bind_all("<MouseWheel>", self._global_mouse_wheel)
        self.bind_all("<Button-4>", self._global_mouse_wheel)
        self.bind_all("<Button-5>", self._global_mouse_wheel)

    def _global_mouse_wheel(self, event):
        """Redirects scrolling updates cleanly to panels beneath the mouse, ignoring non-scrollable panes."""
        try:
            hovered_widget = event.widget
            if not hovered_widget: return
            
            if event.num == 4: units = -2
            elif event.num == 5: units = 2
            else: units = -1 * (event.delta // 40)

            cur = hovered_widget
            while cur:
                if cur == self.tree_frame:
                    # Verify if the sidebar canvas height overflows the visible viewport frame
                    v_top, v_bottom = self.tree_canvas.yview()
                    if v_top > 0.0 or v_bottom < 1.0:
                        self.tree_canvas.yview_scroll(units, "units")
                    return
                
                if hasattr(cur, 'tree') and isinstance(cur, tk.Toplevel):
                    v_top, v_bottom = cur.tree.yview()
                    if v_top > 0.0 or v_bottom < 1.0:
                        cur.tree.yview_scroll(units, "units")
                    return
                
                if cur == self.right_frame:
                    if self.stat_viewer.winfo_ismapped():
                        if self.stat_viewer.edit_container.winfo_ismapped():
                            v_top, v_bottom = self.stat_viewer.edit_canvas.yview()
                            if v_top > 0.0 or v_bottom < 1.0:
                                self.stat_viewer.edit_canvas.yview_scroll(units, "units")
                        else:
                            v_top, v_bottom = self.stat_viewer.text.yview()
                            if v_top > 0.0 or v_bottom < 1.0:
                                self.stat_viewer.text.yview(tk.SCROLL, units, tk.UNITS)
                    elif self.combat_viewer.winfo_ismapped():
                        v_top, v_bottom = self.combat_viewer.main_canvas.yview()
                        if v_top > 0.0 or v_bottom < 1.0:
                            self.combat_viewer.main_canvas.yview_scroll(units, "units")
                    elif self.search_frame.winfo_ismapped():
                        v_top, v_bottom = self.monster_tree.yview()
                        if v_top > 0.0 or v_bottom < 1.0:
                            self.monster_tree.yview_scroll(units, "units")
                    elif self.spell_manager_frame.winfo_ismapped():
                        v_top, v_bottom = self.spell_tree.yview()
                        if v_top > 0.0 or v_bottom < 1.0:
                            self.spell_tree.yview_scroll(units, "units")
                    return
                
                parent_id = cur.winfo_parent()
                if not parent_id: break
                cur = cur.nametowidget(parent_id)
        except:
            pass

    def _get_open_paths(self, nodes):
        """Recursively gathers the string representation of paths for currently expanded tree nodes."""
        return {str(n.path) for n in nodes if n.is_open}.union(*(self._get_open_paths(n.children) for n in nodes))

    def _set_node_open(self, target, state, nodes=None):
        """Recursively forces a specific directory tree path to expand or collapse visually."""
        for n in (nodes if nodes is not None else getattr(self, 'nodes', [])):
            if n.path == target: 
                n.is_open = state
                return True
            if self._set_node_open(target, state, n.children): 
                n.is_open = True
                return True
        return False

    def show_search_panel(self, target_path=None):
        """Backwards-compatible bridge mapping legacy search panel triggers into page state tracking."""
        v_node = Node(name="Monsters", path=self.monsters_dir, is_entity=False, level=0)
        self.open_page(v_node, view_type="root_folder")

    def open_spells_manager(self):
        """Backwards-compatible bridge mapping legacy spells manager triggers into page state tracking."""
        v_node = Node(name="Spells", path=self.spells_dir, is_entity=False, level=0)
        self.open_page(v_node, view_type="root_folder")

    def clear_viewer_and_tree(self):
        """Standardized utility to clear view pane frames and reset path state tracking properties safely."""
        self.stat_viewer.pack_forget()
        self.combat_viewer.pack_forget()
        self.refresh_tree_silent()
        initial_node = Node(name="Campaign Map", path=self.map_dir, is_entity=False, level=0)
        self.open_page(initial_node, view_type="root_folder")

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
        
        # Unified layout top navigation bar container frame
        self.nav_bar = tk.Frame(self.right_frame, bg="#fdf1dc", height=40)
        self.nav_bar.pack(fill=tk.X, padx=10, pady=5)
        self.nav_bar.pack_propagate(False)
        
        self.back_btn = tk.Button(self.nav_bar, text="← BACK", bg="#58180d", fg="white", font=("Georgia", 10, "bold"), command=self.navigate_back)
        self.back_btn.pack(side=tk.LEFT, padx=10, pady=2)
        
        self.page_title_lbl = tk.Label(self.nav_bar, text="", font=("Georgia", 12, "bold"), bg="#fdf1dc", fg="#7a200d")
        self.page_title_lbl.pack(side=tk.LEFT, padx=20)
        
        # Viewer container viewport pane
        self.view_pane = tk.Frame(self.right_frame, bg="#fdf1dc")
        self.view_pane.pack(fill=tk.BOTH, expand=True)
        
        self.stat_viewer = StatBlockRenderer(self.view_pane)
        self.stat_viewer.set_spell_callback(self.on_spell_clicked)
        self.stat_viewer.set_spells_index(self.spells_index)
        self.stat_viewer.set_location_link_callback(self.on_location_link_clicked)
        
        self.combat_viewer = CombatRenderer(
            self.view_pane, 
            open_statblock_cb=self._combat_open_statblock, 
            save_cb=self.save_combat_edits,
            add_bestiary_cb=self._combat_add_bestiary,
            add_camp_mon_cb=self._combat_add_camp_mon,
            add_camp_npc_cb=self._combat_add_camp_npc,
            cancel_cb=self.navigate_back
        )
        
        # Monster Index Panel Setup
        self.search_frame = tk.Frame(self.view_pane, bg="#fdf1dc")
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
        tk.Button(self.search_frame, text="Add Selected Monster", bg="#4a90e2", fg="white", font=("Arial", 11, "bold"), command=lambda: self.on_monster_selected(None)).pack(pady=10)

        # Spell Index Panel Setup
        self.spell_manager_frame = tk.Frame(self.view_pane, bg="#fdf1dc")
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

        # Catchall Placeholder Panel View
        self.placeholder_frame = tk.Frame(self.view_pane, bg="#fdf1dc")
        self.placeholder_lbl = tk.Label(self.placeholder_frame, text="", font=("Georgia", 14, "italic"), bg="#fdf1dc", fg="black")
        self.placeholder_lbl.pack(expand=True)

    def open_page(self, node: Node, view_type: str, stat_path: Path = None, data: dict = None, is_reference_click: bool = False):
        """Builds and records historical navigation layers using the Linked List Strategy."""
        if is_reference_click:
            new_state = PageState(node, view_type, stat_path=stat_path, data=data, prev=self.current_state)
        else:
            if node.level == 0:
                new_state = PageState(node, view_type, stat_path=stat_path, data=data, prev=None)
            else:
                parent_path = node.path.parent
                parent_node = Node(name=parent_path.name, path=parent_path, is_entity=False, level=node.level - 1)
                parent_type = "root_folder" if (parent_path.resolve() == self.root_dir.resolve() or parent_path.resolve() in [self.map_dir.resolve(), self.events_dir.resolve(), self.spells_dir.resolve(), self.monsters_dir.resolve(), self.npcs_dir.resolve(), self.combats_dir.resolve()]) else "event" if (parent_path.resolve() == self.events_dir.resolve() or self.events_dir in parent_path.parents) else "location"
                virtual_parent = PageState(parent_node, parent_type, prev=None)
                new_state = PageState(node, view_type, stat_path=stat_path, data=data, prev=virtual_parent)

        self.current_state = new_state
        self._show_current_state_view()

    def navigate_back(self):
        """Traverses the navigation linked list backward cleanly."""
        if self.current_state and self.current_state.prev:
            self.current_state = self.current_state.prev
            self._show_current_state_view()

    def _show_current_state_view(self):
        """Draws the viewport window according to the current stack state layout rules."""
        for panel in [self.stat_viewer, self.combat_viewer, self.search_frame, self.spell_manager_frame, self.placeholder_frame]:
            panel.pack_forget()

        if not self.current_state:
            return

        if self.current_state.prev is None:
            self.back_btn.pack_forget()
        else:
            self.back_btn.pack(side=tk.LEFT, padx=10, pady=2)

        state = self.current_state
        self.page_title_lbl.config(text=f"Viewing: {state.node.name}")

        if state.view_type == "monster" or state.view_type == "npc":
            self.stat_viewer.pack(fill=tk.BOTH, expand=True)
            try:
                with open(state.stat_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.stat_viewer.render_monster(data, back_cb=self.navigate_back)
                self.stat_viewer.add_top_buttons(state.node.path, self.view_full_portrait, lambda d: self.display_monster(state.node, edit_mode=True, back_cb=self.navigate_back))
            except Exception as e:
                print(f"Error loading sheet: {e}")

        elif state.view_type == "combat":
            self.combat_viewer.pack(fill=tk.BOTH, expand=True)
            try:
                with open(state.stat_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.combat_viewer.render_combat(data, state.node.path)
            except Exception as e:
                print(f"Error loading combat: {e}")

        elif state.view_type == "spell":
            self.stat_viewer.pack(fill=tk.BOTH, expand=True)
            
            spell_data = None
            if state.data:
                spell_data = state.data
            else:
                spell_data = next((s for s in self.spells_index if s["name"].lower() == state.node.name.lower()), None)
                
            if spell_data:
                self.stat_viewer.render_spell(spell_data, back_callback=self.navigate_back)
                if spell_data.get("source") == "Custom":
                    self.stat_viewer.add_custom_spell_buttons(
                        spell_data,
                        edit_cb=lambda sd: self.stat_viewer.render_spell_edit_mode(sd, self.save_spell_edits, self.navigate_back),
                        del_cb=self.delete_custom_spell
                    )
            else:
                messagebox.showerror("Error", f"Spell lookup failed for '{state.node.name}' inside compendium index.")

        elif state.node.path.resolve() == self.monsters_dir.resolve():
            self.search_frame.pack(fill=tk.BOTH, expand=True)
            self.apply_monster_query()

        elif state.node.path.resolve() == self.spells_dir.resolve() or state.node.name == "Spells":
            self.spell_manager_frame.pack(fill=tk.BOTH, expand=True)
            self.apply_spell_query()
            
        # ADDED: Integrated workspace logic sheets for regional map data objects
        elif state.view_type == "location":
            self.stat_viewer.pack(fill=tk.BOTH, expand=True)
            stat_path = state.node.stat_path or (state.node.path / f"{state.node.path.name}.json")
            if not stat_path.exists():
                default_loc = {"name": state.node.name, "description": "", "monsters": [], "npcs": [], "combats": [], "events": [], "connections": []}
                with open(stat_path, "w", encoding="utf-8") as f:
                    json.dump(default_loc, f, indent=4)
                state.node.stat_path = stat_path
            try:
                with open(stat_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.stat_viewer.render_location(data, back_cb=self.navigate_back)
                self.stat_viewer.add_location_top_buttons(state.node.path, lambda p: self.open_location_edit(state.node, stat_path, data))
            except Exception as e:
                print(f"Error loading location: {e}")

        # ADDED: Integrated workspace logic sheets for campaign event logs
        elif state.view_type == "event":
            self.stat_viewer.pack(fill=tk.BOTH, expand=True)
            stat_path = state.node.stat_path or (state.node.path / f"{state.node.path.name}.json")
            if not stat_path.exists():
                default_evt = {"name": state.node.name, "description": "", "monsters": [], "npcs": [], "combats": [], "locations": [], "connections": []}
                with open(stat_path, "w", encoding="utf-8") as f:
                    json.dump(default_evt, f, indent=4)
                state.node.stat_path = stat_path
            try:
                with open(stat_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.stat_viewer.render_event(data, back_cb=self.navigate_back)
                self.stat_viewer.add_location_top_buttons(state.node.path, lambda p: self.open_event_edit(state.node, stat_path, data))
            except Exception as e:
                print(f"Error loading event: {e}")

        else:
            self.placeholder_frame.pack(fill=tk.BOTH, expand=True)
            self.placeholder_lbl.config(text=f"Location Directory Zone: '{state.node.name}'\nPath: {state.node.path}")
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
                btn = tk.Button(self.m_query_canvas_frame, text=b, bg="#ff4d4d" if b == "AND" else "#4a90e2" if b == "OR" else "#e0cbb0", fg="white" if b in ["AND", "OR"] else "black", font=("Arial", 9, "bold"))
                if b in ["AND", "OR"]:
                    btn.config(command=lambda idx=i: self.toggle_mqblock_op(idx))
                    btn.bind("<Button-3>", lambda e, idx=i: self.remove_mqblock(idx))
                else: btn.config(command=lambda idx=i: self.remove_mqblock(idx))
            else:
                text = f"CR {b['min']}-{b['max']}" if b["type"] == "cr" else f"{b['type'].title()}: {b['val']}"
                btn = tk.Button(self.m_query_canvas_frame, text=text, bg="#7a200d", fg="white", font=("Arial", 9, "bold"), command=lambda idx=i: self.remove_mqblock(idx))
            btn.pack(side=tk.LEFT, padx=2, pady=2)

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

    def add_qblock(self, b): self.query_blocks.append(b); self.render_qblocks(); self.apply_spell_query()
    def clear_qblocks(self): self.query_blocks.clear(); self.render_qblocks(); self.apply_spell_query()
    def remove_qblock(self, idx): self.query_blocks.pop(idx); self.render_qblocks(); self.apply_spell_query()
    def toggle_qblock_op(self, idx): self.query_blocks[idx] = "OR" if self.query_blocks[idx] == "AND" else "AND"; self.render_qblocks(); self.apply_spell_query()

    def open_monster_filter_dialog(self):
        d = tk.Toplevel(self); d.title("Build Monster Filter"); d.geometry("450x600"); d.configure(bg="#fdf1dc")
        logic_var = tk.StringVar(value="AND")
        btn_logic = tk.Button(d, text="AND", bg="#ff4d4d", fg="white", font=("Arial", 12, "bold"), width=10, 
                              command=lambda: (logic_var.set("OR") if logic_var.get() == "AND" else logic_var.set("AND"), 
                                               btn_logic.config(text=logic_var.get(), bg="#4a90e2" if logic_var.get() == "OR" else "#ff4d4d")))
        btn_logic.pack(pady=15)
        
        f = tk.Frame(d, bg="#fdf1dc")
        f.pack(anchor="center", padx=20, pady=10)
        
        row_idx = 0
        def create_field(label_text, widget_class, **kwargs):
            nonlocal row_idx
            lbl = tk.Label(f, text=label_text, bg="#fdf1dc", fg="black", font=("Arial", 10, "bold"), width=16, anchor="e")
            lbl.grid(row=row_idx, column=0, padx=(0, 15), pady=8, sticky="e")
            w = widget_class(f, **kwargs)
            w.grid(row=row_idx, column=1, pady=8, sticky="w")
            row_idx += 1
            return w

        min_cr = create_field("Minimum CR:", tk.Scale, from_=0, to=30, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=180)
        max_cr = create_field("Maximum CR:", tk.Scale, from_=0, to=30, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=180)
        max_cr.set(30)
        
        size_v = create_field("Size Category:", ttk.Combobox, values=["All", "Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"], state="readonly", width=22)
        size_v.set("All")
        
        type_v = create_field("Creature Type:", ttk.Combobox, values=["All", "Aberration", "Beast", "Celestial", "Construct", "Dragon", "Elemental", "Fey", "Fiend", "Giant", "Humanoid", "Monstrosity", "Ooze", "Plant", "Undead"], state="readonly", width=22)
        type_v.set("All")
        
        align_v = create_field("Alignment Profile:", ttk.Combobox, values=["All", "Lawful Good", "Neutral Good", "Chaotic Good", "Lawful Neutral", "True Neutral", "Chaotic Neutral", "Lawful Evil", "Neutral Evil", "Chaotic Evil", "Unaligned", "Any"], state="readonly", width=22)
        align_v.set("All")
        
        env_v = create_field("Environment:", ttk.Combobox, values=["All", "Arctic", "Coastal", "Desert", "Forest", "Grassland", "Hill", "Mountain", "Swamp", "Underdark", "Underwater", "Urban"], state="readonly", width=22)
        env_v.set("All")

        def apply_f():
            filters = []
            if min_cr.get() > 0 or max_cr.get() < 30: filters.append({"type": "cr", "min": min_cr.get(), "max": max_cr.get()})
            if size_v.get() != "All": filters.append({"type": "size", "val": size_v.get()})
            if type_v.get() != "All": filters.append({"type": "type", "val": type_v.get()})
            if align_v.get() != "All": filters.append({"type": "align", "val": align_v.get()})
            if env_v.get() != "All": filters.append({"type": "env", "val": env_v.get().lower()})
            if filters:
                op = logic_var.get()
                if self.monster_query_blocks: self.monster_query_blocks.append(op)
                for i, fb in enumerate(filters):
                    self.monster_query_blocks.append(fb)
                    if i < len(filters) - 1: self.monster_query_blocks.append(op)
                self.render_mqblocks(); self.apply_monster_query()
            d.destroy()
        tk.Button(d, text="Apply Filters", bg="#d9ad6c", font=("Arial", 11, "bold"), fg="black", command=apply_f).pack(pady=20)

    def open_filter_dialog(self):
        d = tk.Toplevel(self); d.title("Build Spell Filter"); d.geometry("450x600"); d.configure(bg="#fdf1dc")
        logic_var = tk.StringVar(value="AND")
        btn_logic = tk.Button(d, text="AND", bg="#ff4d4d", fg="white", font=("Arial", 12, "bold"), width=10, 
                              command=lambda: (logic_var.set("OR") if logic_var.get() == "AND" else logic_var.set("AND"), 
                                               btn_logic.config(text=logic_var.get(), bg="#4a90e2" if logic_var.get() == "OR" else "#ff4d4d")))
        btn_logic.pack(pady=15)
        
        f = tk.Frame(d, bg="#fdf1dc")
        f.pack(anchor="center", padx=20, pady=10)
        
        row_idx = 0
        def create_field(label_text, widget_class, **kwargs):
            nonlocal row_idx
            lbl = tk.Label(f, text=label_text, bg="#fdf1dc", fg="black", font=("Arial", 10, "bold"), width=16, anchor="e")
            lbl.grid(row=row_idx, column=0, padx=(0, 15), pady=8, sticky="e")
            w = widget_class(f, **kwargs)
            w.grid(row=row_idx, column=1, pady=8, sticky="w")
            row_idx += 1
            return w

        min_v = create_field("Minimum Level:", tk.Scale, from_=0, to=12, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=180)
        max_v = create_field("Maximum Level:", tk.Scale, from_=0, to=12, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=180)
        max_v.set(12)
        
        sch_v = create_field("School:", ttk.Combobox, values=["All"] + list(utils.SCHOOL_MAP.values()), state="readonly", width=22)
        sch_v.set("All")
        
        dmg_v = create_field("Damage Type:", ttk.Combobox, values=["All", "Acid", "Bludgeoning", "Cold", "Fire", "Force", "Lightning", "Necrotic", "Piercing", "Poison", "Psychic", "Radiant", "Slashing", "Thunder"], state="readonly", width=22)
        dmg_v.set("All")
        
        save_v = create_field("Saving Throw:", ttk.Combobox, values=["All", "Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"], state="readonly", width=22)
        save_v.set("All")
        
        conc_v = create_field("Concentration:", ttk.Combobox, values=["All", "Yes", "No"], state="readonly", width=22)
        conc_v.set("All")

        def apply_f():
            filters = []
            if min_v.get() > 0 or max_v.get() < 12: filters.append({"type": "level", "min": min_v.get(), "max": max_v.get()})
            if sch_v.get() != "All":
                filters.append({"type": "school", "val": utils.INV_SCHOOL_MAP[sch_v.get()]})
            if dmg_v.get() != "All": filters.append({"type": "damage", "val": dmg_v.get().lower()})
            if save_v.get() != "All": filters.append({"type": "save", "val": save_v.get().lower()})
            if conc_v.get() != "All": filters.append({"type": "concentration", "val": conc_v.get() == "Yes"})
            if filters:
                if self.query_blocks: self.query_blocks.append(logic_var.get())
                for i, fb in enumerate(filters):
                    self.query_blocks.append(fb)
                    if i < len(filters) - 1: self.query_blocks.append(logic_var.get())
                self.render_qblocks(); self.apply_spell_query()
            d.destroy()
        tk.Button(d, text="Apply Filters", bg="#d9ad6c", fg="black", font=("Arial", 11, "bold"), command=apply_f).pack(pady=20)

    def remove_qblock(self, idx):
        self.query_blocks.pop(idx)
        self.render_qblocks()
        self.apply_spell_query()

    def toggle_qblock_op(self, idx):
        self.query_blocks[idx] = "OR" if self.query_blocks[idx] == "AND" else "AND"
        self.render_qblocks()
        self.apply_spell_query()

    def render_qblocks(self):
        """Renders the query chips for the Spell manager in the main application right panel."""
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
                else:
                    btn.config(command=lambda idx=i: self.remove_qblock(idx))
            else:
                text = f"Lvl {b['min']}-{b['max']}" if b["type"] == "level" else f"{b['type'].title()}: {b['val']}"
                btn = tk.Button(self.query_canvas_frame, text=text, bg="#7a200d", fg="white", font=("Arial", 9, "bold"), command=lambda idx=i: self.remove_qblock(idx))
            btn.pack(side=tk.LEFT, padx=2, pady=2)

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
        if sd:
            v_node = Node(name=sd["name"], path=self.spells_dir / f"{sd['name']}.json", is_entity=True, level=1)
            self.open_page(v_node, view_type="spell", stat_path=self.spells_dir / f"{sd['name']}.json", data=sd, is_reference_click=True)

    def create_new_spell(self):
        sn = simpledialog.askstring("New Spell", "Enter a name for the new spell:")
        if not sn or not sn.strip() or any(s["name"].lower() == sn.lower() for s in self.spells_index): return
        sf = "".join([c for c in sn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        nd = {"name": sn, "source": "Custom", "level": 1, "school": "V", "time": [{"number": 1, "unit": "action"}], "range": {"type": "point", "distance": {"type": "feet", "amount": 60}}, "components": {"v": True, "s": True}, "duration": [{"type": "instant"}], "entries": ["Describe spell."]}
        self.spells_index.append(nd); self.spells_index = sorted(self.spells_index, key=lambda x: x["name"].lower())
        
        target_path = self.spells_dir / f"{sf}.json"
        json.dump(nd, open(target_path, "w", encoding="utf-8"), indent=4)
        json.dump(self.spells_index, open("spells.json", "w", encoding="utf-8"), indent=4)
        self.stat_viewer.set_spells_index(self.spells_index)
        self.refresh_tree_silent()
        
        v_node = Node(name=sn, path=target_path, is_entity=True, level=1)
        self.open_page(v_node, view_type="spell", stat_path=target_path, data=nd, is_reference_click=False)

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
        self.stat_viewer.set_spells_index(self.spells_index)
        self.refresh_tree_silent()
        
        v_node = Node(name=nn, path=self.spells_dir / f"{sf}.json", is_entity=True, level=1)
        self.open_page(v_node, view_type="spell", stat_path=self.spells_dir / f"{sf}.json", data=new_data, is_reference_click=False)

    def delete_custom_spell(self, s_data):
        if messagebox.askyesno("Confirm Delete", f"Delete spell '{s_data['name']}'?"):
            self.spells_index = [s for s in self.spells_index if s["name"].lower() != s_data["name"].lower()]
            sf = "".join([c for c in s_data["name"] if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
            if (self.spells_dir / f"{sf}.json").exists(): (self.spells_dir / f"{sf}.json").unlink()
            json.dump(self.spells_index, open("spells.json", "w", encoding="utf-8"), indent=4)
            self.stat_viewer.set_spells_index(self.spells_index)
            self.clear_viewer_and_tree()

    # FIXED: Re-injected verified on_spell_clicked reference handler to map lookups safely to navigation stack
    def on_spell_clicked(self, s_name):
        sd = next((s for s in self.spells_index if s["name"].lower() == s_name.lower()), None)
        if not sd: 
            messagebox.showinfo("Not Found", f"Spell reference '{s_name}' not found in database index.")
            return
        v_node = Node(name=sd["name"], path=self.spells_dir / f"{sd['name']}.json", is_entity=True, level=1)
        self.open_page(v_node, view_type="spell", stat_path=self.spells_dir / f"{sd['name']}.json", data=sd, is_reference_click=True)

    def on_monster_selected(self, event=None):
        selected_item = self.monster_tree.selection()
        if not selected_item: return
        item = self.monster_tree.item(selected_item[0])
        monster_meta = next((m for m in self.monster_index if m["name"] == item['values'][0] and m.get("source", "Unknown") == item['values'][3]), None)
        if not monster_meta: return
        
        try:
            global_monster_dir, safe_name = downloader.download_monster_data(monster_meta, self.monsters_dir)
            if not global_monster_dir: return
            self.refresh_tree_silent()
            
            target_json = global_monster_dir / f"{safe_name}.json"
            v_node = Node(name=monster_meta["name"], path=global_monster_dir, is_entity=True, level=1, stat_path=target_json)
            self.open_page(v_node, view_type="monster", stat_path=target_json, is_reference_click=False)
        except Exception as ex:
            messagebox.showerror("Download Error", f"Failed: {ex}")

    def display_monster_by_path(self, target_path: Path, edit_mode=False, back_cb=None):
        def search_nodes(nodes):
            for n in nodes:
                if n.path == target_path and n.is_entity: return n
                res = search_nodes(n.children)
                if res: return res
            return None
        target_node = search_nodes(self.nodes)
        if not target_node:
            jsons = list(target_path.glob("*.json"))
            if jsons: target_node = Node(name=target_path.name, path=target_path, is_entity=True, level=0, stat_path=jsons[0])
        if target_node: 
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
                self.stat_viewer.render_monster(data, back_cb=back_cb)
                self.stat_viewer.add_top_buttons(node.path, self.view_full_portrait, lambda d: self.display_monster(node, edit_mode=True, back_cb=back_cb))
        except Exception as e: 
            print(f"Failed to load: {e}")

    def display_combat_by_path(self, target_path: Path, edit_mode=False):
        def search_nodes(nodes):
            for n in nodes:
                if n.path == target_path and n.is_entity: return n
                res = search_nodes(n.children)
                if res: return res
            return None
        target_node = search_nodes(self.nodes)
        if not target_node:
            jsons = list(target_path.glob("*.json"))
            if jsons: target_node = Node(name=target_path.name, path=target_path, is_entity=True, level=0, stat_path=jsons[0])
        if target_node: 
            self.display_combat(target_node)

    def display_combat(self, node: Node):
        self.search_frame.pack_forget()
        self.spell_manager_frame.pack_forget()
        self.stat_viewer.pack_forget()
        self.combat_viewer.pack(fill=tk.BOTH, expand=True)
        if not node or not node.stat_path: return
        try:
            with open(node.stat_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.combat_viewer.render_combat(data, node.path)
        except Exception as e: 
            print(f"Failed to load combat: {e}")

    def create_new_combat(self, parent_path: Path):
        base_name = "New Combat"
        safe_name = base_name
        counter = 1
        while (self.combats_dir / safe_name).exists():
            safe_name = f"{base_name} {counter}"
            counter += 1

        global_combat_dir = self.combats_dir / safe_name
        global_combat_dir.mkdir(parents=True, exist_ok=True)

        combat_data = {
            "name": safe_name, "location": "Any", "time": "Any", "description": "None", "over": "No", "outcome": "None", "participants": []
        }

        target_json = global_combat_dir / f"{safe_name}.json"
        with open(target_json, "w", encoding="utf-8") as f:
            json.dump(combat_data, f, indent=4)

        combat_icon_src = Path("./utils/combat_icon.png")
        if combat_icon_src.exists():
            try:
                shutil.copy(combat_icon_src, global_combat_dir / "portrait.png")
                img = Image.open(combat_icon_src)
                img.thumbnail((64, 64))
                img.save(global_combat_dir / "icon.webp", "WEBP")
            except: pass

        self.refresh_tree_silent()
        v_node = Node(name=safe_name, path=global_combat_dir, is_entity=True, level=1, stat_path=target_json)
        self.open_page(v_node, view_type="combat", stat_path=target_json, is_reference_click=False)

    def _combat_open_statblock(self, target_name, folder_type):
        global_path = self.root_dir / folder_type / target_name
        jsons = list(global_path.glob("*.json"))
        if jsons:
            v_node = Node(name=target_name, path=global_path, is_entity=True, level=1)
            view_type = "monster" if folder_type == "Monsters" else "npc"
            self.open_page(v_node, view_type=view_type, stat_path=jsons[0], is_reference_click=True)

    def _combat_add_bestiary(self, combat_dir, callback):
        def on_monster_selected(monster_meta):
            try:
                global_monster_dir, safe_name = downloader.download_monster_data(monster_meta, self.monsters_dir)
                if not global_monster_dir: return
                hp = self._get_entity_hp(safe_name, "Monsters")
                callback(safe_name, "Monsters", hp)
                self.refresh_tree_silent()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to download monster: {e}")
        MonsterSearchDialog(self, self.monster_index, on_monster_selected)

    def _combat_add_camp_mon(self, callback):
        EntitySelectionDialog(self, self.monsters_dir, "Monsters", lambda tn: callback(tn, "Monsters", self._get_entity_hp(tn, "Monsters")))

    def _combat_add_camp_npc(self, callback):
        EntitySelectionDialog(self, self.npcs_dir, "NPCs", lambda tn: callback(tn, "NPCs", self._get_entity_hp(tn, "NPCs")))

    def _get_entity_hp(self, target_name, folder_category):
        global_path = self.root_dir / folder_category / target_name / f"{target_name}.json"
        if global_path.exists():
            try:
                with open(global_path, "r", encoding="utf-8") as f:
                    return json.load(f).get("hp", {}).get("average", 10)
            except: return 10
        return 10

    def create_new_npc(self, parent_path: Path):
        base_name = "New NPC"
        safe_name = base_name
        counter = 1
        while (self.npcs_dir / safe_name).exists():
            safe_name = f"{base_name} {counter}"
            counter += 1

        global_npc_dir = self.npcs_dir / safe_name
        global_npc_dir.mkdir(parents=True, exist_ok=True)

        npc_data = {
            "name": safe_name, "source": "Custom", "level": 1, "size": ["M"], "type": "humanoid", "alignment": ["N"], "ac": [10], "hp": {"average": 4, "formula": "1d8"}, "speed": {"walk": 30}, "str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10, "action": [{"name": "Unarmed Strike", "entries": ["{@atk mw} {@hit 2} to hit, reach 5 ft., one target. {@h}1 bludgeoning damage."]}]
        }

        target_json = global_npc_dir / f"{safe_name}.json"
        with open(target_json, "w", encoding="utf-8") as f:
            json.dump(npc_data, f, indent=4)

        default_npc_icon = Path("./utils/default_npc.png")
        if default_npc_icon.exists():
            try:
                img = Image.open(default_npc_icon)
                img.save(global_npc_dir / "portrait.png", "PNG")
                img.thumbnail((64, 64))
                img.save(global_npc_dir / "icon.webp", "WEBP")
            except: pass

        self.refresh_tree_silent()
        v_node = Node(name=safe_name, path=global_npc_dir, is_entity=True, level=1, stat_path=target_json)
        self.open_page(v_node, view_type="npc", stat_path=target_json, is_reference_click=False)

    def save_monster_edits(self, old_dir: Path, new_data: dict):
        old_target_name = old_dir.name
        new_name = new_data.get("name", "Unknown")
        new_safe_name = "".join([c for c in new_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
        if not new_safe_name: new_safe_name = "Unnamed"

        global_dir = old_dir
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

        final_json = global_dir / f"{new_safe_name}.json"
        with open(final_json, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4)

        self.refresh_tree_silent()
        v_node = Node(name=new_name, path=global_dir, is_entity=True, level=1, stat_path=final_json)
        self.open_page(v_node, view_type="monster" if "Monsters" in str(global_dir) else "npc", stat_path=final_json, is_reference_click=False)

    def save_combat_edits(self, combat_dir: Path, new_data: dict):
        old_target_name = combat_dir.name
        new_name = new_data.get("name", "Unknown Combat")
        new_safe_name = "".join([c for c in new_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
        if not new_safe_name: new_safe_name = "Unnamed"

        global_dir = combat_dir
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

        final_json = global_dir / f"{new_safe_name}.json"
        with open(final_json, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4)

        self.refresh_tree_silent()
        v_node = Node(name=new_name, path=global_dir, is_entity=True, level=1, stat_path=final_json)
        self.open_page(v_node, view_type="combat", stat_path=final_json, is_reference_click=False)

    def create_new_location(self, p_path: Path):
        fn = simpledialog.askstring("Add Location", "Location name:")
        if not fn or not fn.strip(): return
        sn = "".join([c for c in fn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        
        nd = p_path / sn
        nd.mkdir(parents=True, exist_ok=True)
        
        if Path("./utils/default.png").exists(): 
            try:
                img = Image.open("./utils/default.png")
                img.thumbnail((64, 64))
                img.save(nd / f"{sn}.png", "PNG")
            except Exception as e:
                print(f"Failed to save icon: {e}")
                
        self._set_node_open(p_path, True)
        self.refresh_tree_silent()
        
        v_node = Node(name=fn, path=nd, is_entity=False, level=len(nd.relative_to(self.map_dir).parts))
        self.open_page(v_node, view_type="location", is_reference_click=False)

    def refresh_tree(self):
        self.refresh_tree_silent()
        
    def refresh_tree_silent(self):
        open_paths = self._get_open_paths(getattr(self, 'nodes', []))
        
        map_node = Node(name="Map", path=self.map_dir, is_entity=False, level=0, icon_path=Path("./utils/map.png") if Path("./utils/map.png").exists() else None, is_open=str(self.map_dir) in open_paths)
        map_node.children = self.build_tree_model(self.map_dir, level=1, open_paths=open_paths)

        # ADDED: Root tree parsing layer tracking campaigns events files mappings
        events_node = Node(name="Events", path=self.events_dir, is_entity=False, level=0, icon_path=Path("./utils/events.png") if Path("./utils/events.png").exists() else None, is_open=str(self.events_dir) in open_paths)
        events_node.children = self.build_tree_model(self.events_dir, level=1, open_paths=open_paths)

        spell_node = Node(name="Spells", path=self.spells_dir, is_entity=False, level=0, icon_path=Path("./utils/spell.png") if Path("./utils/spell.png").exists() else None, is_open=str(self.spells_dir) in open_paths)
        spell_node.children = self.build_tree_model(self.spells_dir, level=1, open_paths=open_paths)

        monsters_node = Node(name="Monsters", path=self.monsters_dir, is_entity=False, level=0, icon_path=Path("./utils/monster.png") if Path("./utils/monster.png").exists() else None, is_open=str(self.monsters_dir) in open_paths)
        monsters_node.children = self.build_tree_model(self.monsters_dir, level=1, open_paths=open_paths)

        npcs_node = Node(name="NPCs", path=self.npcs_dir, is_entity=False, level=0, icon_path=Path("./utils/npc.png") if Path("./utils/npc.png").exists() else None, is_open=str(self.npcs_dir) in open_paths)
        npcs_node.children = self.build_tree_model(self.npcs_dir, level=1, open_paths=open_paths)

        combats_node = Node(name="Combats", path=self.combats_dir, is_entity=False, level=0, icon_path=Path("./utils/combat.png") if Path("./utils/combat.png").exists() else None, is_open=str(self.combats_dir) in open_paths)
        combats_node.children = self.build_tree_model(self.combats_dir, level=1, open_paths=open_paths)
        
        self.nodes = [map_node, events_node, spell_node, monsters_node, npcs_node, combats_node]
        self.render_tree()

    def build_tree_model(self, path: Path, level: int, open_paths: set):
        nodes = []
        try: 
            items = sorted([p for p in path.iterdir()], key=lambda x: x.name.lower())
            dirs = [p for p in items if p.is_dir()]
            files = [p for p in items if p.is_file() and p.suffix == '.json']
        except PermissionError: return nodes

        for item in files:
            # MODIFIED: Skip configuration manifest scripts located inside map or event layers
            if self.map_dir in item.parents or item.parent == self.map_dir or self.events_dir in item.parents or item.parent == self.events_dir:
                continue
            node = Node(name=item.stem, path=item, is_entity=True, level=level, icon_path=Path("./utils/spell_icon.png"), stat_path=item)
            nodes.append(node)

        for item in dirs:
            jsons = list(item.glob("*.json"))
            webps = list(item.glob("*.webp"))

            is_map_path = (item == self.map_dir or self.map_dir in item.parents)
            is_event_path = (item == self.events_dir or self.events_dir in item.parents)

            if jsons and not is_map_path and not is_event_path:
                node = Node(name=item.name, path=item, is_entity=True, level=level, icon_path=webps[0] if webps else None, stat_path=jsons[0])
                nodes.append(node)
            else:
                icon_path = None
                if item == self.monsters_dir: icon_path = Path("./utils/monster.png")
                elif item == self.npcs_dir: icon_path = Path("./utils/npc.png")
                elif item == self.combats_dir: icon_path = Path("./utils/combat.png")
                elif item == self.events_dir: icon_path = Path("./utils/events.png")
                
                if not icon_path or not icon_path.exists():
                    for ext in ['.png', '.webp', '.jpg']:
                        possible_icon = item / f"{item.name}{ext}"
                        if possible_icon.exists():
                            icon_path = possible_icon; break
                
                node = Node(name=item.name, path=item, is_entity=False, level=level, icon_path=icon_path, is_open=str(item) in open_paths)
                if is_map_path or is_event_path:
                    loc_json = item / f"{item.name}.json"
                    if loc_json.exists(): node.stat_path = loc_json
                node.children = self.build_tree_model(item, level + 1, open_paths)
                nodes.append(node)

        if path == self.monsters_dir:
            nodes.append(Node(name="New", path=path, is_entity=False, level=level, action_type="new_monster", icon_path=Path("./utils/new.png")))
        elif path == self.npcs_dir:
            nodes.append(Node(name="New", path=path, is_entity=False, level=level, action_type="new_npc", icon_path=Path("./utils/new.png")))
        elif path == self.combats_dir:
            nodes.append(Node(name="New", path=path, is_entity=False, level=level, action_type="new_combat", icon_path=Path("./utils/new.png")))
        elif path == self.spells_dir:
            nodes.append(Node(name="New", path=path, is_entity=False, level=level, action_type="new_spell", icon_path=Path("./utils/new.png")))
        elif path == self.map_dir or self.map_dir in path.parents:
            nodes.append(Node(name="Add Location", path=path, is_entity=False, level=level, action_type="new_location", icon_path=Path("./utils/new.png")))
        # ADDED: Sub-action leaf triggering nested Event creation
        elif path == self.events_dir or self.events_dir in path.parents:
            nodes.append(Node(name="Add Event", path=path, is_entity=False, level=level, action_type="new_event", icon_path=Path("./utils/new.png")))
            
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
            # MODIFIED: Include "Events" to avoid accidental deletions of root items
            if not is_action_btn and node.name not in ["Map", "Events", "Spells", "Monsters", "NPCs", "Combats"]:
                del_btn = tk.Label(row, text="X", bg="#fae6c5", fg="#ff4d4d", font=("Arial", 16, "bold"), cursor="hand2")
                del_btn.pack(side=tk.RIGHT, padx=15)
                del_btn.bind("<Enter>", lambda e: e.widget.configure(bg="#4a2222", fg="#ffffff"))
                del_btn.bind("<Leave>", lambda e: e.widget.configure(bg="#f5e6ce" if row.cget("bg") == "#f5e6ce" else "#fae6c5", fg="#ff4d4d"))

                def on_del_click(e, n=node):
                    msg = f"Are you sure you want to delete '{n.name}'?\nThis will erase the directory permanently."
                    if messagebox.askyesno("Confirm Delete", msg):
                        try:
                            if n.path.is_file(): 
                                if n.path.parent == self.spells_dir:
                                    try:
                                        with open(n.stat_path, "r", encoding="utf-8") as f:
                                            del_data = json.load(f)
                                        self.spells_index = [s for s in self.spells_index if s["name"].lower() != del_data.get("name", "").lower()]
                                        json.dump(self.spells_index, open("spells.json", "w", encoding="utf-8"), indent=4)
                                        self.stat_viewer.set_spells_index(self.spells_index)
                                    except: pass
                                n.path.unlink()
                            else: 
                                shutil.rmtree(n.path)
                            self.refresh_tree_silent()
                            self.clear_viewer_and_tree()
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
                elif node.action_type == "new_event": self.create_new_event(node.path)
                elif node.action_type == "new_monster": self.show_search_panel(node.path)
                elif node.action_type == "new_npc": self.create_new_npc(node.path)
                elif node.action_type == "new_combat": self.create_new_combat(node.path)
                elif node.action_type == "new_spell": self.create_new_spell()
                elif node.is_entity:
                    if node.path.parent == self.spells_dir:
                        self.open_page(node, view_type="spell", stat_path=node.stat_path, is_reference_click=False)
                    else:
                        v_type = "combat" if "Combats" in str(node.path) else "npc" if "NPCs" in str(node.path) else "monster"
                        self.open_page(node, view_type=v_type, stat_path=node.stat_path, is_reference_click=False)
                else:
                    node.is_open = not node.is_open
                    # FIXED: Transferred the closure guard here so it only triggers when a folder is explicitly closed via clicking
                    if not node.is_open:
                        if self.current_state and self.current_state.node.path:
                            if self.current_state.node.path == node.path or node.path in self.current_state.node.path.parents:
                                initial_node = Node(name="Campaign Map", path=self.map_dir, is_entity=False, level=0)
                                self.open_page(initial_node, view_type="root_folder")
                                
                    v_type = "root_folder" if node.path in [self.map_dir, self.events_dir, self.spells_dir, self.monsters_dir, self.npcs_dir, self.combats_dir] else "event" if "Events" in str(node.path) else "location"
                    self.open_page(node, view_type=v_type, is_reference_click=False)
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
            self.refresh_tree_silent()
        except Exception as ex: messagebox.showerror("Error", str(ex))

    def view_full_portrait(self, monster_dir):
        p = monster_dir / "portrait.png"
        if not p.exists(): messagebox.showinfo("Info", "No artwork found."); return
        ov = tk.Frame(self.right_frame, bg="black")
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        img = Image.open(p); img.thumbnail((800, 800)); timg = ImageTk.PhotoImage(img)
        l = tk.Label(ov, image=timg, bg="black"); l.image = timg; l.pack(expand=True)
        tk.Button(ov, text="CLOSE", command=ov.destroy, bg="#58180d", fg="white", font=("Georgia", 14)).place(x=20, y=20)

    def on_location_link_clicked(self, name, category):
        # MODIFIED: Flag if clicked from edit mode to return safely later
        if self.stat_viewer.edit_container.winfo_ismapped():
            if self.current_state.view_type == "location": self.current_state.view_type = "location_edit"
            elif self.current_state.view_type == "event": self.current_state.view_type = "event_edit"

        if category in ["Monsters", "NPCs"]:
            target_dir = (self.monsters_dir if category == "Monsters" else self.npcs_dir) / name
            jsons = list(target_dir.glob("*.json"))
            if jsons: self.open_page(Node(name=name, path=target_dir, is_entity=True, level=1, stat_path=jsons[0]), view_type="monster" if category == "Monsters" else "npc", stat_path=jsons[0], is_reference_click=True)
        elif category == "Combats":
            target_dir = self.combats_dir / name
            jsons = list(target_dir.glob("*.json"))
            if jsons: self.open_page(Node(name=name, path=target_dir, is_entity=True, level=1, stat_path=jsons[0]), view_type="combat", stat_path=jsons[0], is_reference_click=True)
        elif category == "Events":
            target_path = (self.events_dir / name).resolve()
            if target_path.exists():
                v_node = Node(name=target_path.name, path=target_path, is_entity=False, level=len(target_path.relative_to(self.events_dir).parts))
                stat_json = target_path / f"{target_path.name}.json"
                if stat_json.exists(): v_node.stat_path = stat_json
                self.open_page(v_node, view_type="event", is_reference_click=True)
        elif category == "Locations":
            target_path = (self.map_dir / name).resolve()
            if target_path.exists():
                v_node = Node(name=target_path.name, path=target_path, is_entity=False, level=len(target_path.relative_to(self.map_dir).parts))
                stat_json = target_path / f"{target_path.name}.json"
                if stat_json.exists(): v_node.stat_path = stat_json
                self.open_page(v_node, view_type="location", is_reference_click=True)

    def create_new_event(self, p_path: Path):
        fn = simpledialog.askstring("Add Event", "Event name:")
        if not fn or not fn.strip(): return
        sn = "".join([c for c in fn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        
        nd = p_path / sn
        nd.mkdir(parents=True, exist_ok=True)
        
        if Path("./utils/event_icon.png").exists(): 
            try:
                shutil.copy(Path("./utils/event_icon.png"), nd / f"{sn}.png")
            except: pass
                
        self._set_node_open(p_path, True)
        self.refresh_tree_silent()
        
        v_node = Node(name=fn, path=nd, is_entity=False, level=len(nd.relative_to(self.events_dir).parts))
        self.open_page(v_node, view_type="event", is_reference_click=False)

    def on_location_link_clicked(self, name, category):
        if category in ["Monsters", "NPCs"]:
            target_dir = (self.monsters_dir if category == "Monsters" else self.npcs_dir) / name
            jsons = list(target_dir.glob("*.json"))
            if jsons:
                self.open_page(Node(name=name, path=target_dir, is_entity=True, level=1, stat_path=jsons[0]), view_type="monster" if category == "Monsters" else "npc", stat_path=jsons[0], is_reference_click=True)
            else:
                messagebox.showinfo("Not Found", f"{category[:-1]} info for '{name}' was not found.")
        elif category == "Combats":
            target_dir = self.combats_dir / name
            jsons = list(target_dir.glob("*.json"))
            if jsons:
                self.open_page(Node(name=name, path=target_dir, is_entity=True, level=1, stat_path=jsons[0]), view_type="combat", stat_path=jsons[0], is_reference_click=True)
            else:
                messagebox.showinfo("Not Found", f"Combat record for '{name}' was not found.")
        elif category == "Events":
            target_path = (self.events_dir / name).resolve()
            if not target_path.exists():
                found = list(self.events_dir.rglob(name))
                if found and found[0].is_dir(): target_path = found[0]
            if target_path.exists() and target_path.is_dir():
                stat_json = target_path / f"{target_path.name}.json"
                self.open_page(Node(name=target_path.name, path=target_path, is_entity=False, level=len(target_path.relative_to(self.events_dir).parts), stat_path=stat_json if stat_json.exists() else None), view_type="event", is_reference_click=True)
            else:
                messagebox.showinfo("Not Found", f"Event mapping for '{name}' was not found.")
        elif category == "Locations":
            target_path = (self.map_dir / name).resolve()
            if not target_path.exists():
                found = list(self.map_dir.rglob(name))
                if found and found[0].is_dir(): target_path = found[0]
            if target_path.exists() and target_path.is_dir():
                stat_json = target_path / f"{target_path.name}.json"
                self.open_page(Node(name=target_path.name, path=target_path, is_entity=False, level=len(target_path.relative_to(self.map_dir).parts), stat_path=stat_json if stat_json.exists() else None), view_type="location", is_reference_click=True)
            else:
                messagebox.showinfo("Not Found", f"Map target location '{name}' was not found.")

    def open_location_edit(self, node, stat_path, data):
        def on_save(location_dir, updated_data):
            with open(stat_path, "w", encoding="utf-8") as f: json.dump(updated_data, f, indent=4)
            old_name = location_dir.name
            new_name = updated_data.get("name", old_name)
            new_safe = "".join([c for c in new_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip() or "Unnamed"
            final_dir, final_json = location_dir, stat_path
            if new_safe != old_name:
                target_dir = location_dir.parent / new_safe
                if target_dir.exists() and target_dir != location_dir:
                    messagebox.showerror("Error", f"A location named '{new_safe}' already exists here.")
                    return
                if (location_dir / f"{old_name}.json").exists(): (location_dir / f"{old_name}.json").rename(location_dir / f"{new_safe}.json")
                location_dir.rename(target_dir); final_dir = target_dir; final_json = target_dir / f"{new_safe}.json"
            self.sync_reciprocal_relations()
            self.refresh_tree_silent()
            self.open_page(Node(name=new_name, path=final_dir, is_entity=False, level=len(final_dir.relative_to(self.map_dir).parts), stat_path=final_json), view_type="location", is_reference_click=False)

        self.stat_viewer.render_location_edit_mode(
            data, stat_path.parent, on_save, lambda: self._show_current_state_view(),
            lambda row: MonsterSearchDialog(self, self.monster_index, lambda meta: row(downloader.download_monster_data(meta, self.monsters_dir)[1])),
            lambda row: EntitySelectionDialog(self, self.monsters_dir, "Monsters", row),
            lambda row: EntitySelectionDialog(self, self.npcs_dir, "NPCs", row),
            lambda row: EntitySelectionDialog(self, self.combats_dir, "Combats", row),
            lambda row: EntitySelectionDialog(self, self.events_dir, "Events", row),
            lambda row: EntitySelectionDialog(self, self.map_dir, "Locations", row)
        )

    def open_event_edit(self, node, stat_path, data):
        def on_save(event_dir, updated_data):
            with open(stat_path, "w", encoding="utf-8") as f: json.dump(updated_data, f, indent=4)
            old_name = event_dir.name
            new_name = updated_data.get("name", old_name)
            new_safe = "".join([c for c in new_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip() or "Unnamed"
            final_dir, final_json = event_dir, stat_path
            if new_safe != old_name:
                target_dir = event_dir.parent / new_safe
                if target_dir.exists() and target_dir != event_dir:
                    messagebox.showerror("Error", f"An event named '{new_safe}' already exists here.")
                    return
                if (event_dir / f"{old_name}.json").exists(): (event_dir / f"{old_name}.json").rename(event_dir / f"{new_safe}.json")
                event_dir.rename(target_dir); final_dir = target_dir; final_json = target_dir / f"{new_safe}.json"
            self.sync_reciprocal_relations()
            self.refresh_tree_silent()
            self.open_page(Node(name=new_name, path=final_dir, is_entity=False, level=len(final_dir.relative_to(self.events_dir).parts), stat_path=final_json), view_type="event", is_reference_click=False)

        self.stat_viewer.render_event_edit_mode(
            data, stat_path.parent, on_save, lambda: self._show_current_state_view(),
            lambda row: MonsterSearchDialog(self, self.monster_index, lambda meta: row(downloader.download_monster_data(meta, self.monsters_dir)[1])),
            lambda row: EntitySelectionDialog(self, self.monsters_dir, "Monsters", row),
            lambda row: EntitySelectionDialog(self, self.npcs_dir, "NPCs", row),
            lambda row: EntitySelectionDialog(self, self.combats_dir, "Combats", row),
            lambda row: EntitySelectionDialog(self, self.map_dir, "Locations", row),
            lambda row: EntitySelectionDialog(self, self.events_dir, "Events", row)
        )

    def sync_reciprocal_relations(self):
        """Processes cross-pollination linking between saved map objects and event data manifests."""
        loc_data_map, evt_data_map = {}, {}
        for p in self.map_dir.rglob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f: d = json.load(f)
                d.setdefault("events", []); loc_data_map[p] = d
            except: pass
        for p in self.events_dir.rglob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f: d = json.load(f)
                d.setdefault("locations", []); evt_data_map[p] = d
            except: pass

        for lp, ld in loc_data_map.items():
            for e_name in ld.get("events", []):
                for ep, ed in evt_data_map.items():
                    if ep.parent.name == e_name or str(ep.parent.relative_to(self.events_dir)) == e_name:
                        if lp.parent.name not in ed["locations"]: ed["locations"].append(lp.parent.name)

        for ep, ed in evt_data_map.items():
            for l_name in ed.get("locations", []):
                for lp, ld in loc_data_map.items():
                    if lp.parent.name == l_name or str(lp.parent.relative_to(self.map_dir)) == l_name:
                        if ep.parent.name not in ld["events"]: ld["events"].append(ep.parent.name)

        for p, d in loc_data_map.items():
            try:
                with open(p, "w", encoding="utf-8") as f: json.dump(d, f, indent=4)
            except: pass
        for p, d in evt_data_map.items():
            try:
                with open(p, "w", encoding="utf-8") as f: json.dump(d, f, indent=4)
            except: pass
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--path", default="./data")
    args = parser.parse_args()
    Path(args.path).mkdir(parents=True, exist_ok=True)
    Path("./utils").mkdir(exist_ok=True)
    DnDStatManager(args.path).mainloop()

if __name__ == "__main__":
    main()