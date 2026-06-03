import tkinter as tk
from tkinter import ttk
import utils

class SpellSearchDialog(tk.Toplevel):
    def __init__(self, parent, spells_index, is_innate, callback):
        super().__init__(parent)
        self.title("Search Spell")
        self.spells_index = spells_index
        self.is_innate = is_innate
        self.callback = callback
        self.geometry("750x650")
        self.configure(bg="#fdf1dc")
        self.iid_map = {}
        self.query_blocks = []

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.apply_spell_query())
        tk.Entry(self, textvariable=self.search_var, font=("Georgia", 14), bg="#ffffff", fg="black", insertbackground="black").pack(fill=tk.X, padx=10, pady=10)

        query_tools = tk.Frame(self, bg="#fdf1dc")
        query_tools.pack(fill=tk.X, padx=10, pady=(0, 5))
        for op in ["AND", "OR", "(", ")"]:
            tk.Button(query_tools, text=op, bg="#e0cbb0", fg="black", font=("Arial", 9, "bold"), command=lambda o=op: self.add_qblock(o)).pack(side=tk.LEFT, padx=2)
        tk.Button(query_tools, text="+ Filter", bg="#d9ad6c", fg="black", font=("Arial", 9, "bold"), command=self.open_filter_dialog).pack(side=tk.LEFT, padx=10)
        tk.Button(query_tools, text="Clear Filters", bg="#ff4d4d", fg="white", font=("Arial", 9, "bold"), command=self.clear_qblocks).pack(side=tk.RIGHT, padx=2)

        self.query_canvas_frame = tk.Frame(self, bg="#f5e6ce", bd=1, relief=tk.SUNKEN)
        self.query_canvas_frame.pack(fill=tk.X, padx=10, pady=(0, 10), ipady=5)

        self.tree = ttk.Treeview(self, columns=("name", "level", "school", "source"), show="headings", selectmode="browse")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        for col, w in [("name", 300), ("level", 80), ("school", 150), ("source", 80)]:
            self.tree.heading(col, text=col.title(), anchor="center" if col in ["level", "source"] else "w")
            self.tree.column(col, width=w, anchor="center" if col in ["level", "source"] else "w")
        
        self.tree.tag_configure("evenrow", background="#f5e6ce", foreground="black")
        self.tree.tag_configure("oddrow", background="#fae6c5", foreground="black")
        self.tree.bind("<Double-1>", lambda e: self.on_select())

        if self.is_innate:
            freq_frame = tk.Frame(self, bg="#fdf1dc")
            freq_frame.pack(fill=tk.X, padx=10, pady=10)
            tk.Label(freq_frame, text="Uses per day:", bg="#fdf1dc", fg="black", font=("Georgia", 12)).pack(side=tk.LEFT)
            self.freq_var = tk.IntVar(value=11)
            self.freq_label = tk.Label(freq_frame, text="At Will", bg="#fdf1dc", fg="#7a200d", font=("Georgia", 12, "bold"), width=8)
            self.freq_label.pack(side=tk.RIGHT)
            tk.Scale(freq_frame, from_=1, to=11, orient=tk.HORIZONTAL, variable=self.freq_var, showvalue=0, bg="#fdf1dc", highlightthickness=0, troughcolor="#e0cbb0",
                     command=lambda v: self.freq_label.config(text="At Will" if int(float(v)) == 11 else f"{int(float(v))} / day")).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15)

        tk.Button(self, text="Add Selected", bg="#4a90e2", fg="white", font=("Arial", 11, "bold"), command=self.on_select).pack(pady=10)
        self.apply_spell_query()

    def add_qblock(self, b_type):
        self.query_blocks.append(b_type)
        self.render_qblocks(); self.apply_spell_query()

    def clear_qblocks(self):
        self.query_blocks.clear()
        self.render_qblocks(); self.apply_spell_query()

    def remove_qblock(self, idx):
        self.query_blocks.pop(idx)
        self.render_qblocks(); self.apply_spell_query()

    def toggle_qblock_op(self, idx):
        self.query_blocks[idx] = "OR" if self.query_blocks[idx] == "AND" else "AND"
        self.render_qblocks(); self.apply_spell_query()

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
                else:
                    btn.config(command=lambda idx=i: self.remove_qblock(idx))
            else:
                text = f"Lvl {b['min']}-{b['max']}" if b["type"] == "level" else f"{b['type'].title()}: {b['val']}"
                btn = tk.Button(self.query_canvas_frame, text=text, bg="#7a200d", fg="white", font=("Arial", 9, "bold"), command=lambda idx=i: self.remove_qblock(idx))
            btn.pack(side=tk.LEFT, padx=2, pady=2)

    def open_filter_dialog(self):
        d = tk.Toplevel(self); d.title("Build Filter"); d.geometry("450x600"); d.configure(bg="#fdf1dc")
        
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
            if sch_v.get() != "All": filters.append({"type": "school", "val": utils.INV_SCHOOL_MAP[sch_v.get()]})
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
            
        tk.Button(d, text="Apply Filters", bg="#d9ad6c", font=("Arial", 11, "bold"), fg="black", command=apply_f).pack(pady=20)
    def apply_spell_query(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        self.iid_map.clear()
        q_str = self.search_var.get().lower()
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

class MonsterSearchDialog(tk.Toplevel):
    def __init__(self, parent, monster_index, callback):
        super().__init__(parent)
        self.title("Search Bestiary")
        self.monster_index = monster_index
        self.callback = callback
        self.geometry("850x700")
        self.configure(bg="#fdf1dc")
        self.iid_map = {}
        self.query_blocks = []

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.apply_query())
        tk.Entry(self, textvariable=self.search_var, font=("Georgia", 14), bg="#ffffff", fg="black", insertbackground="black").pack(fill=tk.X, padx=10, pady=10)

        query_tools = tk.Frame(self, bg="#fdf1dc")
        query_tools.pack(fill=tk.X, padx=10, pady=(0, 5))
        for op in ["AND", "OR", "(", ")"]:
            tk.Button(query_tools, text=op, bg="#e0cbb0", fg="black", font=("Arial", 9, "bold"), command=lambda o=op: self.add_qblock(o)).pack(side=tk.LEFT, padx=2)
        tk.Button(query_tools, text="+ Filter", bg="#d9ad6c", fg="black", font=("Arial", 9, "bold"), command=self.open_filter_dialog).pack(side=tk.LEFT, padx=10)
        tk.Button(query_tools, text="Clear Filters", bg="#ff4d4d", fg="white", font=("Arial", 9, "bold"), command=self.clear_qblocks).pack(side=tk.RIGHT, padx=2)

        self.query_canvas_frame = tk.Frame(self, bg="#f5e6ce", bd=1, relief=tk.SUNKEN)
        self.query_canvas_frame.pack(fill=tk.X, padx=10, pady=(0, 10), ipady=5)

        self.tree = ttk.Treeview(self, columns=("name", "type", "cr", "source"), show="headings", selectmode="browse")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        for col, w in [("name", 300), ("type", 150), ("cr", 60), ("source", 80)]:
            self.tree.heading(col, text=col.title(), anchor="center" if col in ["cr", "source"] else "w")
            self.tree.column(col, width=w, anchor="center" if col in ["cr", "source"] else "w")
        
        self.tree.tag_configure("evenrow", background="#f5e6ce", foreground="black")
        self.tree.tag_configure("oddrow", background="#fae6c5", foreground="black")
        self.tree.bind("<Double-1>", lambda e: self.on_select())

        tk.Button(self, text="Add Selected", bg="#4a90e2", fg="white", font=("Arial", 11, "bold"), command=self.on_select).pack(pady=10)
        self.apply_query()

    def add_qblock(self, b_type):
        self.query_blocks.append(b_type)
        self.render_qblocks(); self.apply_query()

    def clear_qblocks(self):
        self.query_blocks.clear()
        self.render_qblocks(); self.apply_query()

    def remove_qblock(self, idx):
        self.query_blocks.pop(idx)
        self.render_qblocks(); self.apply_query()

    def toggle_qblock_op(self, idx):
        self.query_blocks[idx] = "OR" if self.query_blocks[idx] == "AND" else "AND"
        self.render_qblocks(); self.apply_query()

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
                else:
                    btn.config(command=lambda idx=i: self.remove_qblock(idx))
            else:
                text = f"CR {b['min']}-{b['max']}" if b["type"] == "cr" else f"{b['type'].title()}: {b['val']}"
                btn = tk.Button(self.query_canvas_frame, text=text, bg="#7a200d", fg="white", font=("Arial", 9, "bold"), command=lambda idx=i: self.remove_qblock(idx))
            btn.pack(side=tk.LEFT, padx=2, pady=2)

    def open_filter_dialog(self):
        d = tk.Toplevel(self); d.title("Build Filter"); d.geometry("450x600"); d.configure(bg="#fdf1dc")
        
        logic_var = tk.StringVar(value="AND")
        btn_logic = tk.Button(d, text="AND", bg="#ff4d4d", fg="white", font=("Arial", 12, "bold"), width=10, 
                              command=lambda: (logic_var.set("OR") if logic_var.get() == "AND" else logic_var.set("AND"), 
                                               btn_logic.config(text=logic_var.get(), bg="#4a90e2" if logic_var.get() == "OR" else "#ff4d4d")))
        btn_logic.pack(pady=15)
        
        # FIXED: Master inner window frame structured cleanly with anchor="center" alignments
        f = tk.Frame(d, bg="#fdf1dc")
        f.pack(anchor="center", padx=20, pady=10)
        
        row_idx = 0
        def create_field(label_text, widget_class, **kwargs):
            nonlocal row_idx
            # Symmetric grid column offsets to ensure slider alignment properties work seamlessly
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
                if self.query_blocks: self.query_blocks.append(logic_var.get())
                for i, fb in enumerate(filters):
                    self.query_blocks.append(fb)
                    if i < len(filters) - 1: self.query_blocks.append(logic_var.get())
                self.render_qblocks(); self.apply_query()
            d.destroy()
            
        tk.Button(d, text="Apply Filters", bg="#d9ad6c", font=("Arial", 11, "bold"), fg="black", command=apply_f).pack(pady=20)

    def apply_query(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        self.iid_map.clear()
        q_str = self.search_var.get().lower()
        count = 0
        for m in self.monster_index:
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
                except Exception: pass
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

        # MODIFIED: Explicitly crawl nested location profiles in folders recursively
        if folder_category == "Locations":
            available_items = sorted([str(p.relative_to(global_source_dir)) for p in global_source_dir.rglob("*") if p.is_dir()])
        elif folder_category == "Objects":
            available_items = sorted([p.stem for p in global_source_dir.glob("*.json")])        
        else:
            available_items = sorted([p.name for p in global_source_dir.iterdir() if p.is_dir()])
            
        for i, item in enumerate(available_items):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            self.tree.insert("", tk.END, values=(item,), tags=(tag,))

        tk.Button(self, text="Link Selected", bg="#d9ad6c", fg="black", font=("Arial", 11, "bold"), command=self.confirm_selection).pack(pady=15)

    def confirm_selection(self):
        sel = self.tree.selection()
        if sel:
            target_item_name = self.tree.item(sel[0])['values'][0]
            self.callback(target_item_name)
            self.destroy()