import tkinter as tk
from tkinter import ttk
import utils.preprocess as preprocess
from pathlib import Path
from PIL import Image, ImageTk

class BaseSearchDialog(tk.Toplevel):
    """Abstract Parent Class consolidating common search indexing architectures, filter tool elements, and table rendering passes."""
    def __init__(self, parent, title, geometry, index_source, columns):
        super().__init__(parent)
        self.title(title)
        self.geometry(geometry)
        self.configure(bg="#fdf1dc")
        self.index_source = index_source
        self.columns = columns
        self.iid_map = {}
        self.query_blocks = []

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.apply_query_filter())
        tk.Entry(self, textvariable=self.search_var, font=("Georgia", 14), bg="#ffffff", fg="black", insertbackground="black").pack(fill=tk.X, padx=10, pady=10)

        self.query_tools = tk.Frame(self, bg="#fdf1dc")
        self.query_tools.pack(fill=tk.X, padx=10, pady=(0, 5))
        for op in ["AND", "OR", "(", ")"]:
            tk.Button(self.query_tools, text=op, bg="#e0cbb0", fg="black", font=("Arial", 9, "bold"), command=lambda o=op: self.add_qblock(o)).pack(side=tk.LEFT, padx=2)
        tk.Button(self.query_tools, text="+ Filter", bg="#d9ad6c", fg="black", font=("Arial", 9, "bold"), command=self.open_filter_dialog).pack(side=tk.LEFT, padx=10)
        tk.Button(self.query_tools, text="Clear Filters", bg="#ff4d4d", fg="white", font=("Arial", 9, "bold"), command=self.clear_qblocks).pack(side=tk.RIGHT, padx=2)

        self.query_canvas_frame = tk.Frame(self, bg="#f5e6ce", bd=1, relief=tk.SUNKEN)
        self.query_canvas_frame.pack(fill=tk.X, padx=10, pady=(0, 10), ipady=5)

        self.tree = ttk.Treeview(self, columns=list(columns.keys()), show="headings", selectmode="browse")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        for col, width in columns.items():
            self.tree.heading(col, text=col.title(), anchor="center" if col in ["level", "cr", "source"] else "w")
            self.tree.column(col, width=width, anchor="center" if col in ["level", "cr", "source"] else "w")
        
        self.tree.tag_configure("evenrow", background="#f5e6ce", foreground="black")
        self.tree.tag_configure("oddrow", background="#fae6c5", foreground="black")
        self.tree.bind("<Double-1>", lambda e: self.on_select())

    def add_qblock(self, b_type):
        self.query_blocks.append(b_type)
        self.render_qblocks()
        self.apply_query_filter()

    def clear_qblocks(self):
        self.query_blocks.clear()
        self.render_qblocks()
        self.apply_query_filter()

    def remove_qblock(self, idx):
        self.query_blocks.pop(idx)
        self.render_qblocks()
        self.apply_query_filter()

    def toggle_qblock_op(self, idx):
        self.query_blocks[idx] = "OR" if self.query_blocks[idx] == "AND" else "AND"
        self.render_qblocks()
        self.apply_query_filter()

    def render_qblocks(self):
        for w in self.query_canvas_frame.winfo_children(): 
            w.destroy()
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
                text = f"CR {b['min']}-{b['max']}" if b["type"] == "cr" else f"Lvl {b['min']}-{b['max']}" if b["type"] == "level" else f"{b['type'].title()}: {b['val']}"
                btn = tk.Button(self.query_canvas_frame, text=text, bg="#7a200d", fg="white", font=("Arial", 9, "bold"), command=lambda idx=i: self.remove_qblock(idx))
            btn.pack(side=tk.LEFT, padx=2, pady=2)

    def setup_filter_fields(self, d, logic_var, fields_builder_cb):
        btn_logic = tk.Button(d, text="AND", bg="#ff4d4d", fg="white", font=("Arial", 12, "bold"), width=10, 
                              command=lambda: (logic_var.set("OR") if logic_var.get() == "AND" else logic_var.set("AND"), 
                                               btn_logic.config(text=logic_var.get(), bg="#4a90e2" if logic_var.get() == "OR" else "#ff4d4d")))
        btn_logic.pack(pady=10)
        f = tk.Frame(d, bg="#fdf1dc")
        f.pack(fill=tk.BOTH, expand=True, padx=20)
        
        def create_field(label_text, widget_class, **kwargs):
            row_frame = tk.Frame(f, bg="#fdf1dc")
            row_frame.pack(anchor="center", pady=6)
            lbl = tk.Label(row_frame, text=label_text, bg="#fdf1dc", fg="black", font=("Arial", 10, "bold"), width=18, anchor="e")
            lbl.pack(side=tk.LEFT, padx=(0, 10))
            w = widget_class(row_frame, **kwargs)
            w.pack(side=tk.LEFT)
            return w
        fields_builder_cb(create_field)

    def process_and_apply_filters(self, filters, logic_var):
        if filters:
            if self.query_blocks: self.query_blocks.append(logic_var.get())
            for i, fb in enumerate(filters):
                self.query_blocks.append(fb)
                if i < len(filters) - 1: self.query_blocks.append(logic_var.get())
            self.render_qblocks()
            self.apply_query_filter()

    def open_filter_dialog(self): 
        raise NotImplementedError
    def apply_query_filter(self): 
        raise NotImplementedError
    def on_select(self): 
        raise NotImplementedError


class SpellSearchDialog(BaseSearchDialog):
    def __init__(self, parent, spells_index, is_innate, callback):
        self.is_innate = is_innate
        self.callback = callback
        super().__init__(parent, "Search Spell", "750x650", spells_index, {"name": 300, "level": 80, "school": 150, "source": 80})
        
        if self.is_innate:
            self.freq_frame = tk.Frame(self, bg="#fdf1dc")
            self.freq_frame.pack(fill=tk.X, padx=10, pady=10)
            tk.Label(self.freq_frame, text="Uses per day:", bg="#fdf1dc", fg="black", font=("Georgia", 12)).pack(side=tk.LEFT)
            self.freq_var = tk.IntVar(value=11)
            self.freq_label = tk.Label(self.freq_frame, text="At Will", bg="#fdf1dc", fg="#7a200d", font=("Georgia", 12, "bold"), width=8)
            self.freq_label.pack(side=tk.RIGHT)
            tk.Scale(self.freq_frame, from_=1, to=11, orient=tk.HORIZONTAL, variable=self.freq_var, showvalue=0, bg="#fdf1dc", highlightthickness=0, troughcolor="#e0cbb0",
                     command=lambda v: self.freq_label.config(text="At Will" if int(float(v)) == 11 else f"{int(float(v))} / day")).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15)

        # ADDED BACK: Confirmation button for select clicks
        tk.Button(self, text="Select Spell", bg="#4a90e2", fg="white", font=("Arial", 11, "bold"), command=self.on_select).pack(pady=10)
        self.apply_query_filter()

    def open_filter_dialog(self):
        d = tk.Toplevel(self); d.title("Build Filter"); d.geometry("450x680"); d.configure(bg="#fdf1dc")
        logic_var = tk.StringVar(value="AND")
        
        def build_fields(factory):
            self._min_v = factory("Minimum Level:", tk.Scale, from_=0, to=12, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=180)
            self._max_v = factory("Maximum Level:", tk.Scale, from_=0, to=12, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=180)
            self._max_v.set(12)
            self._sch_v = factory("School:", ttk.Combobox, values=["All"] + list(preprocess.SCHOOL_MAP.values()), state="readonly", width=22)
            self._sch_v.set("All")
            self._dmg_v = factory("Damage Type:", ttk.Combobox, values=["All", "Acid", "Bludgeoning", "Cold", "Fire", "Force", "Lightning", "Necrotic", "Piercing", "Poison", "Psychic", "Radiant", "Slashing", "Thunder"], state="readonly", width=22)
            self._dmg_v.set("All")
            self._save_v = factory("Saving Throw:", ttk.Combobox, values=["All", "Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"], state="readonly", width=22)
            self._save_v.set("All")
            self._conc_v = factory("Concentration:", ttk.Combobox, values=["All", "Yes", "No"], state="readonly", width=22)
            self._conc_v.set("All")

        self.setup_filter_fields(d, logic_var, build_fields)

        def apply_action():
            filters = []
            if self._min_v.get() > 0 or self._max_v.get() < 12: filters.append({"type": "level", "min": self._min_v.get(), "max": self._max_v.get()})
            if self._sch_v.get() != "All": filters.append({"type": "school", "val": preprocess.INV_SCHOOL_MAP[self._sch_v.get()]})
            if self._dmg_v.get() != "All": filters.append({"type": "damage", "val": self._dmg_v.get().lower()})
            if self._save_v.get() != "All": filters.append({"type": "save", "val": self._save_v.get().lower()})
            if self._conc_v.get() != "All": filters.append({"type": "concentration", "val": self._conc_v.get() == "Yes"})
            self.process_and_apply_filters(filters, logic_var)
            d.destroy()
            
        tk.Button(d, text="Apply Filters", bg="#d9ad6c", font=("Arial", 11, "bold"), command=apply_action).pack(pady=15)

    def apply_query_filter(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        self.iid_map.clear()
        q_str = self.search_var.get().lower()
        count = 0
        for s in self.index_source:
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
                except: pass
            tag = "evenrow" if count % 2 == 0 else "oddrow"
            idx = str(count)
            self.tree.insert("", tk.END, iid=idx, values=(s["name"], "Cantrip" if s.get("level", 0) == 0 else str(s.get("level")), preprocess.SCHOOL_MAP.get(s.get("school", ""), "Unknown"), s.get("source", "Unknown")), tags=(tag,))
            self.iid_map[idx] = s; count += 1

    def on_select(self):
        sel = self.tree.selection()
        if sel:
            s_data = self.iid_map[sel[0]]
            if self.is_innate:
                v = self.freq_var.get()
                self.callback(s_data, "will" if v == 11 else str(v))
            else:
                self.callback(s_data)
            self.destroy()


class MonsterSearchDialog(BaseSearchDialog):
    def __init__(self, parent, monster_index, callback):
        self.callback = callback
        super().__init__(parent, "Search Bestiary", "850x700", monster_index, {"name": 300, "type": 150, "cr": 60, "source": 80})
        
        # ADDED BACK: Confirmation button for select clicks
        tk.Button(self, text="Select Monster", bg="#4a90e2", fg="white", font=("Arial", 11, "bold"), command=self.on_select).pack(pady=10)
        self.apply_query_filter()

    def open_filter_dialog(self):
        d = tk.Toplevel(self); d.title("Build Filter"); d.geometry("450x680"); d.configure(bg="#fdf1dc")
        logic_var = tk.StringVar(value="AND")
        
        def build_fields(factory):
            self._min_cr = factory("Minimum CR:", tk.Scale, from_=0, to=30, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=180)
            self._max_cr = factory("Maximum CR:", tk.Scale, from_=0, to=30, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=180)
            self._max_cr.set(30)
            self._size_v = factory("Size Category:", ttk.Combobox, values=["All", "Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"], state="readonly", width=22)
            self._size_v.set("All")
            self._type_v = factory("Creature Type:", ttk.Combobox, values=["All", "Aberration", "Beast", "Celestial", "Construct", "Dragon", "Elemental", "Fey", "Fiend", "Giant", "Humanoid", "Monstrosity", "Ooze", "Plant", "Undead"], state="readonly", width=22)
            self._type_v.set("All")
            self._align_v = factory("Alignment Profile:", ttk.Combobox, values=["All", "Lawful Good", "Neutral Good", "Chaotic Good", "Lawful Neutral", "True Neutral", "Chaotic Neutral", "Lawful Evil", "Neutral Evil", "Chaotic Evil", "Unaligned", "Any"], state="readonly", width=22)
            self._align_v.set("All")
            self._env_v = factory("Environment Context:", ttk.Combobox, values=["All", "Arctic", "Coastal", "Desert", "Forest", "Grassland", "Hill", "Mountain", "Swamp", "Underdark", "Underwater", "Urban"], state="readonly", width=22)
            self._env_v.set("All")

        self.setup_filter_fields(d, logic_var, build_fields)

        def apply_action():
            filters = []
            if self._min_cr.get() > 0 or self._max_cr.get() < 30: filters.append({"type": "cr", "min": self._min_cr.get(), "max": self._max_cr.get()})
            if self._size_v.get() != "All": filters.append({"type": "size", "val": self._size_v.get()})
            if self._type_v.get() != "All": filters.append({"type": "type", "val": self._type_v.get()})
            if self._align_v.get() != "All": filters.append({"type": "align", "val": self._align_v.get()})
            if self._env_v.get() != "All": filters.append({"type": "env", "val": self._env_v.get().lower()})
            self.process_and_apply_filters(filters, logic_var)
            d.destroy()
            
        tk.Button(d, text="Apply Filters", bg="#d9ad6c", font=("Arial", 11, "bold"), fg="black", command=apply_action).pack(pady=15)

    def apply_query_filter(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        self.iid_map.clear()
        q_str = self.search_var.get().lower()
        count = 0
        for m in self.index_source:
            if q_str and q_str not in m["name"].lower(): continue
            if self.query_blocks:
                expr = ""
                for b in self.query_blocks:
                    if b in ["AND", "OR", "(", ")"]: expr += f" {b.lower()} "
                    else:
                        match = True
                        if b["type"] == "cr" and (preprocess.parse_cr(m.get("cr", "0")) < b["min"] or preprocess.parse_cr(m.get("cr", "0")) > b["max"]): match = False
                        elif b["type"] == "size" and m.get("size") != b["val"]: match = False
                        elif b["type"] == "type" and b["val"].lower() not in m.get("type", "").lower(): match = False
                        elif b["type"] == "align" and b["val"].lower() not in m.get("alignment", "").lower(): match = False
                        elif b["type"] == "env" and b["val"] not in m.get("environment", []): match = False
                        expr += " True " if match else " False "
                try:
                    if not eval(expr): continue
                except: pass
            tag = "evenrow" if count % 2 == 0 else "oddrow"
            idx = str(count)
            self.tree.insert("", tk.END, iid=idx, values=(m["name"], m.get("type", "Unknown"), m.get("cr", "—"), m.get("source", "Unknown")), tags=(tag,))
            self.iid_map[idx] = m; count += 1

    def on_select(self):
        sel = self.tree.selection()
        if sel:
            m_data = self.iid_map[sel[0]]
            self.callback(m_data)
            self.destroy()


class EntitySelectionDialog(tk.Toplevel):
    def __init__(self, parent, global_source_dir, folder_category, callback):
        super().__init__(parent)
        self.title(f"Link Existing {folder_category[:-1]}")
        self.geometry("450x550")
        self.configure(bg="#fdf1dc")
        self.callback = callback
        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

        tk.Label(self, text=f"Choose a global {folder_category[:-1]} to link:", bg="#fdf1dc", fg="#7a200d", font=("Georgia", 13, "bold")).pack(pady=10)
        
        listbox_frame = tk.Frame(self, bg="#fdf1dc")
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        self.tree = ttk.Treeview(listbox_frame, columns=("name",), show="headings", selectmode="browse")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.heading("name", text="Available Entities", anchor="w")
        self.tree.tag_configure("evenrow", background="#f5e6ce", foreground="black")
        self.tree.tag_configure("oddrow", background="#fae6c5", foreground="black")
        
        scroll = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<Double-1>", lambda e: self.confirm_selection())

        available_items = []
        if folder_category == "Objects":
            for p in global_source_dir.glob("*.json"):
                available_items.append(p.stem)
        elif folder_category in ["Locations", "Events"]:
            for p in global_source_dir.rglob("*"):
                if p.is_dir():
                    available_items.append(p.name)
        else:
            for p in global_source_dir.iterdir():
                if p.is_dir():
                    available_items.append(p.name)

        available_items = sorted(list(set(available_items)), key=lambda x: x.lower())
        for i, item in enumerate(available_items):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            self.tree.insert("", tk.END, values=(item,), tags=(tag,))

        # ADDED BACK: Confirmation button for select clicks
        tk.Button(self, text="Link Selected", bg="#d9ad6c", fg="black", font=("Arial", 11, "bold"), command=self.confirm_selection).pack(pady=15)

    def confirm_selection(self):
        sel = self.tree.selection()
        if sel:
            target_item_name = self.tree.item(sel[0])['values'][0]
            self.callback(target_item_name)
            self.destroy()

class DepthsSelectionDialog(tk.Toplevel):
    def __init__(self, parent, current_depths, callback, is_priority=False):
        super().__init__(parent)
        label_text = "Priorities" if is_priority else "Depths"
        self.title(f"Select {label_text}")

        mx, my = self.winfo_pointerxy()
        self.geometry(f"380x480+{mx + 10}+{my + 10}")
        self.configure(bg="#fdf1dc")
        self.callback = callback
        self.transient(parent)
        self.grab_set()

        tk.Label(self, text=f"Select Location {label_text}", font=("Georgia", 13, "bold"), fg="#58180d", bg="#fdf1dc", pady=8).pack()
        
        list_frame = tk.Frame(self, bg="#fdf1dc")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas = tk.Canvas(list_frame, bg="#fae6c5", highlightthickness=1, highlightbackground="#d9ad6c")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.canvas.yview)

        scroll_inner = tk.Frame(self.canvas, bg="#fae6c5")
        window_item = self.canvas.create_window((0, 0), window=scroll_inner, anchor="nw")
        
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(window_item, width=e.width))
        scroll_inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # CHANGE: Append a "break" return string token to fully consume the mousewheel event sequence
        self.bind("<MouseWheel>", lambda event: [self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"), "break"][1])

        self.selected_depths = set(current_depths if current_depths else [0])

        def toggle_row(d_val, row_frame, lbl_widget, base_bg):
            if d_val in self.selected_depths:
                self.selected_depths.remove(d_val)
                row_frame.configure(bg=base_bg)
                lbl_widget.configure(bg=base_bg, fg="black")
            else:
                self.selected_depths.add(d_val)
                row_frame.configure(bg="#4a90e2")
                lbl_widget.configure(bg="#4a90e2", fg="white")

        for idx, d in enumerate(range(-20, 21)):
            base_bg = "#f5e6ce" if idx % 2 == 0 else "#fae6c5"
            
            r_frame = tk.Frame(scroll_inner, bg=base_bg, bd=0, padx=15, pady=6)
            r_frame.pack(fill=tk.X, expand=True)
            
            display_text = f"Priority {d}" if is_priority else f"Depth {d}"
            if d == 0:
                display_text = "Priority 0 (Default Baseline)" if is_priority else "Depth 0 (Default Surface)"
                
            lbl_widget = tk.Label(r_frame, text=display_text, font=("Times", 11, "bold"), bg=base_bg, fg="black", anchor="w")
            lbl_widget.pack(fill=tk.X, expand=True)
            
            if d in self.selected_depths:
                r_frame.configure(bg="#4a90e2")
                lbl_widget.configure(bg="#4a90e2", fg="white")
                
            r_frame.bind("<Button-1>", lambda e, val=d, rf=r_frame, lw=lbl_widget, bbg=base_bg: toggle_row(val, rf, lw, bbg))
            lbl_widget.bind("<Button-1>", lambda e, val=d, rf=r_frame, lw=lbl_widget, bbg=base_bg: toggle_row(val, rf, lw, bbg))

        def apply_selection():
            res = sorted(list(self.selected_depths))
            self.callback(res if res else [0])
            self.destroy()

        btn_frame = tk.Frame(self, bg="#fdf1dc", pady=10)
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text="Apply", font=("Arial", 10, "bold"), bg="#4a90e2", fg="white", width=10, command=apply_selection).pack(side=tk.LEFT, padx=35)
        tk.Button(btn_frame, text="Cancel", font=("Arial", 10, "bold"), bg="#58180d", fg="white", width=10, command=self.destroy).pack(side=tk.RIGHT, padx=35)

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import tkinter.colorchooser as colorchooser
import json
from pathlib import Path

class TerrainSettingsDialog(tk.Toplevel):
    def __init__(self, parent, current_size, current_color, callback):
        super().__init__(parent)
        self.parent = parent
        self.title("Terrain Configuration")
        mx, my = self.winfo_pointerxy()
        self.geometry(f"440x480+{mx + 10}+{my + 10}")
        self.configure(bg="#fdf1dc")
        self.callback = callback
        self.transient(parent)
        self.grab_set()

        self.selected_size = current_size
        self.selected_color = current_color
        self.focused_color_hex = None
        
        self.colors_path = Path(self.parent.map_root) / "terrain_colors.json"

        tk.Label(self, text="Terrain Configuration Master", font=("Georgia", 13, "bold"), fg="#58180d", bg="#fdf1dc", pady=6).pack()
        
        hint_lbl = "Click a swatch, then type a number (1-0) to bind it to a Quick-Bar slot.\nCustom colors appear first."
        tk.Label(self, text=hint_lbl, font=("Arial", 9, "italic"), fg="#7a200d", bg="#fdf1dc", justify="center").pack(pady=(0, 5))

        # Grid Color Scroll Panel Layout
        color_label_frame = tk.LabelFrame(self, text="Palette Asset Mapping Registry", font=("Georgia", 9, "bold"), bg="#fdf1dc", fg="#7a200d", padx=10, pady=5)
        color_label_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        add_frame = tk.Frame(color_label_frame, bg="#fdf1dc")
        add_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Button(add_frame, text="Delete", font=("Arial", 9, "bold"), bg="#ff4d4d", fg="white", command=self._delete_custom_color).pack(side=tk.RIGHT, padx=2)
        tk.Button(add_frame, text="Edit Selected", font=("Arial", 9, "bold"), bg="#dfa87a", fg="black", command=self._edit_custom_color).pack(side=tk.RIGHT, padx=2)
        tk.Button(add_frame, text="New Color", font=("Arial", 9, "bold"), bg="#4a90e2", fg="white", command=self._add_custom_color_wheel).pack(side=tk.RIGHT, padx=2)

        list_outer = tk.Frame(color_label_frame, bg="#fdf1dc")
        list_outer.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_outer)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas = tk.Canvas(list_outer, bg="#fae6c5", highlightthickness=1, highlightbackground="#d9ad6c")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.canvas.yview)

        self.scroll_inner = tk.Frame(self.canvas, bg="#fae6c5")
        self.window_item = self.canvas.create_window((0, 0), window=self.scroll_inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.window_item, width=e.width))

        self.map_colors = [
            ("#9ccca0", "Grassland"), ("#7aa37a", "Deep Forest"), ("#8bbbb0", "Swamp/Marsh"),
            ("#dfa87a", "Dirt Roads"), ("#cb7d6a", "Badlands/Clay"), ("#ebd391", "Desert Sand"),
            ("#9ac6e6", "Shallow Streams"), ("#6488a4", "Ocean Abyss"), ("#b399c7", "Arcane Waste"),
            ("#aeb6bf", "Stone Mountain"), ("#85929e", "Underdark Cavity")
        ]

        self.color_widgets = {}
        self._load_colors_config()
        self._build_color_grid()

        self._select_color(self.selected_color)
        self.bind("<Key>", self._on_key_assignment)

        # Action Control Row
        btn_frame = tk.Frame(self, bg="#fdf1dc")
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(15, 25), padx=15)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        tk.Button(btn_frame, text="Apply Settings", font=("Arial", 10, "bold"), bg="#2ecc71", fg="white", command=self._apply).grid(row=0, column=0, padx=20, sticky="ew")
        tk.Button(btn_frame, text="Cancel", font=("Arial", 10, "bold"), bg="#58180d", fg="white", command=self.destroy).grid(row=0, column=1, padx=20, sticky="ew")

    def _load_colors_config(self):
        self.custom_colors = []
        if self.colors_path.exists():
            try:
                with open(self.colors_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if isinstance(cfg, dict):
                        self.custom_colors = cfg.get("custom_palette", [])
                    else:
                        self.custom_colors = cfg
            except: pass

    def _save_colors_config(self):
        try:
            cfg = {
                "quick_slots": self.parent.quick_colors,
                "custom_palette": self.custom_colors
            }
            with open(self.colors_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
        except Exception as e: print(f"Failed configuration write sequence: {e}")

    def _build_color_grid(self):
        for w in self.scroll_inner.winfo_children(): w.destroy()
        self.color_widgets.clear()

        all_colors = [(c[0], c[1]) for c in self.custom_colors] + self.map_colors
        
        for i, (hex_c, label) in enumerate(all_colors):
            row = i // 3
            col = i % 3
            
            c_cell = tk.Frame(self.scroll_inner, bg="#fae6c5", padx=4, pady=4, bd=1, relief=tk.FLAT)
            c_cell.grid(row=row, column=col, sticky="nsew", padx=3, pady=2)
            
            sq = tk.Frame(c_cell, width=32, height=24, bg=hex_c, bd=1, relief=tk.SOLID)
            sq.pack(pady=2)
            sq.pack_propagate(False)
            
            slot_num = ""
            if hex_c.lower() in [qc.lower() for qc in self.parent.quick_colors]:
                idx = [qc.lower() for qc in self.parent.quick_colors].index(hex_c.lower())
                slot_num = str((idx + 1) % 10)
                
            sq_lbl = tk.Label(sq, text=slot_num, font=("Arial", 9, "bold"), bg=hex_c, fg="black" if hex_c.lower() != "#ffffff" else "gray")
            sq_lbl.pack(expand=True)
            
            lbl = tk.Label(c_cell, text=label, font=("Times", 9, "bold"), bg="#fae6c5", fg="black")
            lbl.pack()
            
            for w in [c_cell, sq, sq_lbl, lbl]:
                w.bind("<Button-1>", lambda e, hc=hex_c: self._focus_color_entry(hc))
            self.color_widgets[hex_c] = c_cell

        self.scroll_inner.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _focus_color_entry(self, hex_c):
        self.focused_color_hex = hex_c
        self._select_color(hex_c)
        for hc, cell in self.color_widgets.items():
            if hc.lower() == hex_c.lower():
                cell.configure(bd=1, relief=tk.SOLID, bg="#4a90e2")
            else:
                cell.configure(bd=1, relief=tk.FLAT, bg="#fae6c5")

    def _delete_custom_color(self):
        if not self.focused_color_hex:
            messagebox.showinfo("Note", "Please select a custom color from the grid panel first.")
            return
        
        target = next((c for c in self.custom_colors if c[0].lower() == self.focused_color_hex.lower()), None)
        if not target:
            messagebox.showwarning("Warning", "Baseline default palette textures cannot be deleted.")
            return
            
        if messagebox.askyesno("Confirm Delete", f"Delete custom texture color '{target[1]}' permanently from palette?"):
            for idx, qc in enumerate(self.parent.quick_colors):
                if qc.lower() == self.focused_color_hex.lower():
                    self.parent.quick_colors[idx] = "#ffffff"  
            
            self.custom_colors.remove(target)
            self._save_colors_config()
            self.focused_color_hex = None
            self._build_color_grid()

    def _add_custom_color_wheel(self):
        chosen = colorchooser.askcolor(title="Select Custom Pattern", parent=self)
        if not chosen or not chosen[1]: return
        hex_color = chosen[1]

        name = simpledialog.askstring("Label configuration", "Enter a name for this custom texture:", parent=self)
        name = name.strip() if (name and name.strip()) else f"Custom ({hex_color})"

        if any(c[0].lower() == hex_color.lower() for c in self.custom_colors):
            messagebox.showinfo("Note", "This precise tone code is already saved in your panel options!")
            return

        self.custom_colors.append([hex_color, name])
        self._save_colors_config()
        self._build_color_grid()
        self._focus_color_entry(hex_color)

    def _on_key_assignment(self, event):
        if not self.focused_color_hex: return
        key_map = {
            '1': 0, 'ampersand': 0, '2': 1, 'eacute': 1, '3': 2, 'quotedbl': 2,
            '4': 3, 'apostrophe': 3, '5': 4, 'parenleft': 4, '6': 5, 'minus': 5,
            '7': 6, 'egrave': 6, '8': 7, 'underscore': 7, '9': 8, 'ccedilla': 8,
            '0': 9, 'agrave': 9
        }
        sym = event.keysym.lower()
        if sym in key_map:
            slot_idx = key_map[sym]
            for idx, existing_hex in enumerate(self.parent.quick_colors):
                if existing_hex.lower() == self.focused_color_hex.lower():
                    self.parent.quick_colors[idx] = "#ffffff"
            
            self.parent.quick_colors[slot_idx] = self.focused_color_hex
            self._save_colors_config()
            self._build_color_grid()
            self._focus_color_entry(self.focused_color_hex)

    def _select_color(self, color_hex):
        self.selected_color = color_hex

    def _apply(self):
        self.callback(self.selected_size, self.selected_color)
        self.destroy()

    def _edit_custom_color(self):
        """Modifies both the color code and label parameters of an active custom swatch."""
        if not self.focused_color_hex:
            messagebox.showinfo("Note", "Please select a custom color from the grid panel first.")
            return
        
        # Verify the selected color resides in our user-defined registry array index
        target_idx = next((i for i, c in enumerate(self.custom_colors) if c[0].lower() == self.focused_color_hex.lower()), None)
        if target_idx is None:
            messagebox.showwarning("Warning", "Baseline default system palette colors cannot be edited.")
            return
            
        old_hex, old_name = self.custom_colors[target_idx]
        
        # Open color wheel pre-focused on the old hex choice parameters context
        chosen = colorchooser.askcolor(color=old_hex, title="Edit Custom Terrain Color", parent=self)
        if not chosen or not chosen[1]: return
        new_hex = chosen[1]

        # Prompt for a description name while pre-filling the original text as default
        name = simpledialog.askstring("Label Configuration", "Modify texture configuration description name:", initialvalue=old_name, parent=self)
        name = name.strip() if (name and name.strip()) else old_name

        # Synchronization: Update the parent hotbar live if this color was currently assigned to a slot
        for idx, qc in enumerate(self.parent.quick_colors):
            if qc.lower() == old_hex.lower():
                self.parent.quick_colors[idx] = new_hex

        # Commit updates directly back to config arrays
        self.custom_colors[target_idx] = [new_hex, name]
        self._save_colors_config()
        
        # Re-focus onto our newly mutated item entity definitions frame
        self.focused_color_hex = new_hex
        self._build_color_grid()
        self._focus_color_entry(new_hex)


class NodeIconSelectorDialog(tk.Toplevel):
    def __init__(self, parent, current_mode, callback):
        super().__init__(parent)
        self.title("Select Node Icon")
        mx, my = self.winfo_pointerxy()
        self.geometry(f"400x500+{mx + 10}+{my + 10}")
        self.configure(bg="#fdf1dc")
        self.transient(parent)
        self.grab_set()
        
        tk.Label(self, text="Choose Custom Icon Mark", font=("Georgia", 12, "bold"), fg="#58180d", bg="#fdf1dc", pady=10).pack()
        
        dir_name = "location_icons" if current_mode == "location" else "events_icons"
        self.target_dir = Path("assets/icons") / dir_name
        
        if not self.target_dir.exists():
            self.target_dir.mkdir(parents=True, exist_ok=True)
            
        outer_f = tk.Frame(self, bg="#fdf1dc")
        outer_f.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(outer_f)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas = tk.Canvas(outer_f, bg="#fae6c5", highlightthickness=1, highlightbackground="#d9ad6c")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.canvas.yview)
        
        inner_f = tk.Frame(self.canvas, bg="#fae6c5")
        window_item = self.canvas.create_window((0, 0), window=inner_f, anchor="nw")
        
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(window_item, width=e.width))
        inner_f.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        # CHANGE: Append a "break" return string token to fully consume the mousewheel event sequence
        self.bind("<MouseWheel>", lambda event: [self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"), "break"][1])

        # CHANGE: Distribute weights evenly so icons don't bunch up leaving an empty column space
        for c in range(4):
            inner_f.grid_columnconfigure(c, weight=1)

        
        pngs = sorted(list(self.target_dir.glob("*.png")))
        if not pngs:
            tk.Label(inner_f, text=f"No icons found inside\n{self.target_dir.as_posix()}", font=("Arial", 10, "italic"), bg="#fae6c5", fg="gray").pack(pady=40, expand=True)
        
        self._keep_alive_images = []
        for idx, p in enumerate(pngs):
            row = idx // 4
            col = idx % 4
            
            cell = tk.Frame(inner_f, bg="#fae6c5", padx=5, pady=5)
            cell.grid(row=row, column=col, sticky="nsew")
            
            try:
                pil_img = Image.open(p)
                pil_img.thumbnail((48, 48))
                tk_img = ImageTk.PhotoImage(pil_img)
                self._keep_alive_images.append(tk_img)
                
                btn = tk.Button(cell, image=tk_img, bg="#fdf1dc", activebackground="#4a90e2", command=lambda path=p: [callback(path), self.destroy()])
                btn.pack()
                
                lbl_text = p.stem[:10] + "..." if len(p.stem) > 12 else p.stem
                tk.Label(cell, text=lbl_text, font=("Arial", 8), bg="#fae6c5", fg="black").pack()
            except Exception as e:
                print(f"Failed loading dialog preview image: {e}")
                
        tk.Button(self, text="Cancel", font=("Arial", 10, "bold"), bg="#58180d", fg="white", command=self.destroy, pady=5).pack(pady=15)