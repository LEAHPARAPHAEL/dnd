import tkinter as tk
from tkinter import ttk
import utils

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
            self._sch_v = factory("School:", ttk.Combobox, values=["All"] + list(utils.SCHOOL_MAP.values()), state="readonly", width=22)
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
            if self._sch_v.get() != "All": filters.append({"type": "school", "val": utils.INV_SCHOOL_MAP[self._sch_v.get()]})
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
            self.tree.insert("", tk.END, iid=idx, values=(s["name"], "Cantrip" if s.get("level", 0) == 0 else str(s.get("level")), utils.SCHOOL_MAP.get(s.get("school", ""), "Unknown"), s.get("source", "Unknown")), tags=(tag,))
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
                        if b["type"] == "cr" and (utils.parse_cr(m.get("cr", "0")) < b["min"] or utils.parse_cr(m.get("cr", "0")) > b["max"]): match = False
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