import tkinter as tk
from tkinter import font, ttk, messagebox, simpledialog
import re
import json
import copy

class SpellSearchDialog(tk.Toplevel):
    def __init__(self, parent, spells_index, is_innate, callback):
        super().__init__(parent)
        self.title("Search Spell")
        self.spells_index = spells_index
        self.is_innate = is_innate
        self.callback = callback
        self.geometry("750x550")
        self.configure(bg="#2b2b2b")
        self.iid_map = {}

        self.school_map = {"A": "Abjuration", "C": "Conjuration", "D": "Divination", "E": "Enchantment", 
                           "I": "Illusion", "N": "Necromancy", "T": "Transmutation", "V": "Evocation", "P": "Psionic"}

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.filter_spells)
        e = tk.Entry(self, textvariable=self.search_var, font=("Georgia", 14), bg="#333", fg="white", insertbackground="white")
        e.pack(fill=tk.X, padx=10, pady=10)
        e.focus()

        columns = ("name", "level", "school", "source")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.tree.heading("name", text="Name", anchor="w")
        self.tree.heading("level", text="Level", anchor="center")
        self.tree.heading("school", text="School", anchor="w")
        self.tree.heading("source", text="Source", anchor="center")
        
        self.tree.column("name", width=300, anchor="w")
        self.tree.column("level", width=80, anchor="center")
        self.tree.column("school", width=150, anchor="w")
        self.tree.column("source", width=80, anchor="center")
        
        self.tree.tag_configure("evenrow", background="#2b2b2b", foreground="white")
        self.tree.tag_configure("oddrow", background="#363636", foreground="white")
        self.tree.bind("<Double-1>", lambda e: self.on_select())

        if self.is_innate:
            freq_frame = tk.Frame(self, bg="#2b2b2b")
            freq_frame.pack(fill=tk.X, padx=10, pady=10)
            tk.Label(freq_frame, text="Uses per day:", bg="#2b2b2b", fg="white", font=("Georgia", 12)).pack(side=tk.LEFT)
            
            self.freq_var = tk.IntVar(value=11)
            self.freq_label = tk.Label(freq_frame, text="At Will", bg="#2b2b2b", fg="#d9ad6c", font=("Georgia", 12, "bold"), width=8)
            self.freq_label.pack(side=tk.RIGHT)
            
            def on_slide(val):
                v = int(float(val))
                if v == 11: self.freq_label.config(text="At Will")
                else: self.freq_label.config(text=f"{v} / day")
                    
            self.slider = tk.Scale(freq_frame, from_=1, to=11, orient=tk.HORIZONTAL, variable=self.freq_var, command=on_slide, showvalue=0, bg="#2b2b2b", highlightthickness=0, troughcolor="#444")
            self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15)

        tk.Button(self, text="Add Selected", bg="#4a90e2", fg="white", font=("Arial", 11, "bold"), command=self.on_select).pack(pady=10)
        self.filter_spells()

    def filter_spells(self, *args):
        q = self.search_var.get().lower()
        for item in self.tree.get_children(): self.tree.delete(item)
        self.iid_map.clear()
        
        count = 0
        for s in self.spells_index:
            if q in s["name"].lower():
                lvl = s.get("level", 0)
                lvl_str = "Cantrip" if lvl == 0 else str(lvl)
                sch = self.school_map.get(s.get("school", ""), "Unknown")
                src = s.get("source", "Unknown")
                
                tag = "evenrow" if count % 2 == 0 else "oddrow"
                idx = str(count)
                self.tree.insert("", tk.END, iid=idx, values=(s["name"], lvl_str, sch, src), tags=(tag,))
                self.iid_map[idx] = s
                count += 1

    def on_select(self):
        sel = self.tree.selection()
        if sel:
            s_data = self.iid_map[sel[0]]
            if self.is_innate:
                v = self.freq_var.get()
                freq_str = "will" if v == 11 else str(v)
                self.callback(s_data, freq_str)
            else:
                self.callback(s_data)
            self.destroy()

class StatBlockRenderer(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, bg="#fdf1dc", *args, **kwargs) 

        # VIEW MODE
        self.view_container = tk.Frame(self, bg="#fdf1dc")
        self.view_container.pack(fill=tk.BOTH, expand=True)
        self.v_scroll = ttk.Scrollbar(self.view_container, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text = tk.Text(self.view_container, bg="#fdf1dc", wrap=tk.WORD, borderwidth=0, highlightthickness=0, padx=40, pady=40, yscrollcommand=self.v_scroll.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.v_scroll.config(command=self.text.yview)
        
        self.spell_callback = None
        self.spells_index = []
        self._setup_fonts_and_tags()
        
        # EDIT MODE
        self.edit_container = tk.Frame(self, bg="#fdf1dc")
        self.edit_canvas = tk.Canvas(self.edit_container, bg="#fdf1dc", highlightthickness=0)
        self.edit_scroll = ttk.Scrollbar(self.edit_container, orient="vertical", command=self.edit_canvas.yview)
        self.edit_inner = tk.Frame(self.edit_canvas, bg="#fdf1dc", padx=40, pady=20)
        self.edit_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.edit_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.edit_window = self.edit_canvas.create_window((0, 0), window=self.edit_inner, anchor="nw")
        self.edit_inner.bind("<Configure>", lambda e: self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all")))
        self.edit_canvas.bind("<Configure>", lambda e: self.edit_canvas.itemconfig(self.edit_window, width=e.width))
        self.edit_canvas.configure(yscrollcommand=self.edit_scroll.set)

        self.dividers = []
        self.overlay_buttons = []
        self.text.bind("<Configure>", self.on_text_resize)

    def set_spell_callback(self, callback): self.spell_callback = callback
    def set_spells_index(self, index): self.spells_index = index

    def _setup_fonts_and_tags(self):
        base_font = "Times"
        self.title_font = font.Font(family=base_font, size=24, weight="bold")
        self.header_font = font.Font(family=base_font, size=18, weight="bold") 
        self.body_font = font.Font(family=base_font, size=13)
        self.body_bold = font.Font(family=base_font, size=13, weight="bold")
        self.body_italic = font.Font(family=base_font, size=13, slant="italic")
        
        dnd_red = "#58180d"
        dnd_bordeaux = "#7a200d"
        
        self.text.tag_configure("title", font=self.title_font, foreground=dnd_red, spacing3=5)
        self.text.tag_configure("subtitle", font=self.body_italic, foreground="black", spacing3=10)
        self.text.tag_configure("section_header", font=self.header_font, foreground=dnd_bordeaux, spacing1=15, spacing3=5)
        self.text.tag_configure("body", font=self.body_font, foreground="black", spacing3=3)
        self.text.tag_configure("bold", font=self.body_bold, foreground="black")
        self.text.tag_configure("body_indented", font=self.body_font, foreground="black", lmargin1=20, lmargin2=20, spacing3=8)

        self.text.tag_configure("spell_link", foreground="#4a90e2", underline=True)
        self.text.tag_bind("spell_link", "<Enter>", lambda e: self.text.config(cursor="hand2"))
        self.text.tag_bind("spell_link", "<Leave>", lambda e: self.text.config(cursor=""))
        self.text.tag_bind("spell_link", "<Button-1>", self._on_spell_click)

    def _on_spell_click(self, event):
        index = self.text.index(f"@{event.x},{event.y}")
        for tag in self.text.tag_names(index):
            if tag.startswith("SPELL_TAG:"):
                spell_name = tag.split(":", 1)[1]
                if self.spell_callback: self.spell_callback(spell_name)
                break

    def on_text_resize(self, event):
        new_width = max(10, event.width - 80)
        for div in self.dividers: div.configure(width=new_width)

    def insert_divider(self):
        current_width = max(10, self.text.winfo_width() - 80)
        divider = tk.Frame(self.text, height=3, bg="#d9ad6c", width=current_width)
        self.text.window_create(tk.END, window=divider)
        self.text.insert(tk.END, "\n")
        self.dividers.append(divider)

    def clear_overlays(self):
        for btn in self.overlay_buttons: btn.destroy()
        self.overlay_buttons.clear()

    def add_top_buttons(self, monster_dir, view_callback, edit_callback):
        self.clear_overlays()
        btn_view = tk.Button(self.view_container, text="VIEW ARTWORK", bg="#d9ad6c", fg="black", font=("Georgia", 10, "bold"), command=lambda: view_callback(monster_dir))
        btn_view.place(relx=1.0, x=-140, y=10, width=120, height=30)
        btn_edit = tk.Button(self.view_container, text="EDIT", bg="#8a8a8a", fg="white", font=("Georgia", 10, "bold"), command=lambda: edit_callback(monster_dir))
        btn_edit.place(relx=1.0, x=-230, y=10, width=80, height=30)
        self.overlay_buttons.extend([btn_view, btn_edit])

    # ==========================================
    # VISUAL EDIT MODE (GUI Form)
    # ==========================================
    def render_edit_mode(self, data, monster_dir, save_callback, cancel_callback):
        self.clear_overlays()
        self.view_container.pack_forget()
        self.edit_container.pack(fill=tk.BOTH, expand=True)

        for widget in self.edit_inner.winfo_children(): widget.destroy()

        self.edit_data = copy.deepcopy(data)
        self.edit_refs = {} 

        top_frame = tk.Frame(self.edit_inner, bg="#fdf1dc")
        top_frame.pack(fill=tk.X, pady=(0, 20))
        tk.Label(top_frame, text="EDIT MODE", font=self.header_font, fg="#58180d", bg="#fdf1dc").pack(side=tk.LEFT)
        tk.Button(top_frame, text="SAVE", bg="#4a90e2", fg="white", font=("Georgia", 10, "bold"), command=lambda: self._handle_gui_save(monster_dir, save_callback)).pack(side=tk.RIGHT, padx=5)
        tk.Button(top_frame, text="CANCEL", bg="#58180d", fg="white", font=("Georgia", 10, "bold"), command=lambda: self._cancel_edit(cancel_callback)).pack(side=tk.RIGHT, padx=5)

        basic_frame = tk.Frame(self.edit_inner, bg="#fdf1dc")
        basic_frame.pack(fill=tk.X, pady=10)

        row = 0
        def add_basic_field(label_text, key, width=50):
            nonlocal row
            tk.Label(basic_frame, text=label_text, bg="#fdf1dc", font=self.body_bold).grid(row=row, column=0, sticky="e", padx=5, pady=2)
            val = self.edit_data.get(key, "")
            if isinstance(val, (dict, list)): val = json.dumps(val)
            entry = tk.Entry(basic_frame, width=width, font=self.body_font)
            entry.insert(0, str(val))
            entry.grid(row=row, column=1, sticky="w", padx=5, pady=2)
            self.edit_refs[key] = entry
            row += 1

        add_basic_field("Name:", "name")
        add_basic_field("Level:", "level", width=10)
        add_basic_field("Source:", "source")
        add_basic_field("Challenge Rating:", "cr", width=10)

        # Smart AC Parser
        ac_val = self.edit_data.get("ac", [10])
        if isinstance(ac_val, list) and len(ac_val) > 0: ac_val = ac_val[0]
        if isinstance(ac_val, dict): ac_val = ac_val.get("ac", 10)
        tk.Label(basic_frame, text="Armor Class:", bg="#fdf1dc", font=self.body_bold).grid(row=row, column=0, sticky="e", padx=5, pady=2)
        ac_entry = tk.Entry(basic_frame, width=50, font=self.body_font)
        ac_entry.insert(0, str(ac_val))
        ac_entry.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        self.edit_refs["ac"] = ac_entry
        row += 1

        # Smart HP Parser
        hp_formula = self.edit_data.get("hp", {}).get("formula", "1d8")
        tk.Label(basic_frame, text="Hit Points (Formula):", bg="#fdf1dc", font=self.body_bold).grid(row=row, column=0, sticky="e", padx=5, pady=2)
        hp_entry = tk.Entry(basic_frame, width=50, font=self.body_font)
        hp_entry.insert(0, str(hp_formula))
        hp_entry.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        self.edit_refs["hp_formula"] = hp_entry
        row += 1

        ui_frame = tk.Frame(self.edit_inner, bg="#fdf1dc")
        ui_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(ui_frame, text="Size:", bg="#fdf1dc", font=self.body_bold).pack(side=tk.LEFT, padx=(5,2))
        self.size_map = {"Tiny": "T", "Small": "S", "Medium": "M", "Large": "L", "Huge": "H", "Gargantuan": "G"}
        inv_size_map = {v: k for k, v in self.size_map.items()}
        cur_size = self.edit_data.get("size", ["M"])
        if isinstance(cur_size, list): cur_size = cur_size[0]
        self.size_var = tk.StringVar(value=inv_size_map.get(cur_size, "Medium"))
        ttk.Combobox(ui_frame, textvariable=self.size_var, values=list(self.size_map.keys()), state="readonly", width=12).pack(side=tk.LEFT, padx=(0, 20))
        
        tk.Label(ui_frame, text="Alignment:", bg="#fdf1dc", font=self.body_bold).pack(side=tk.LEFT, padx=(5,2))
        self.align_map = {
            "Lawful Good": ["L", "G"], "Neutral Good": ["N", "G"], "Chaotic Good": ["C", "G"],
            "Lawful Neutral": ["L", "N"], "True Neutral": ["N"], "Chaotic Neutral": ["C", "N"],
            "Lawful Evil": ["L", "E"], "Neutral Evil": ["N", "E"], "Chaotic Evil": ["C", "E"],
            "Unaligned": ["U"], "Any": ["A"]
        }
        cur_align = self.edit_data.get("alignment", ["N"])
        align_str = "True Neutral"
        for k, v in self.align_map.items():
            if v == cur_align:
                align_str = k
                break
        self.align_var = tk.StringVar(value=align_str)
        ttk.Combobox(ui_frame, textvariable=self.align_var, values=list(self.align_map.keys()), state="readonly", width=15).pack(side=tk.LEFT)

        speed_master = tk.Frame(self.edit_inner, bg="#fdf1dc", pady=10)
        speed_master.pack(fill=tk.X)
        tk.Label(speed_master, text="Speeds:", bg="#fdf1dc", font=self.body_bold).pack(side=tk.LEFT, anchor="n")
        
        self.speed_frame = tk.Frame(speed_master, bg="#fdf1dc")
        self.speed_frame.pack(side=tk.LEFT, padx=10)
        self.speed_refs = []

        def add_speed_row(s_type="walk", s_val="", s_cond=""):
            row = tk.Frame(self.speed_frame, bg="#fdf1dc")
            row.pack(fill=tk.X, pady=2)
            t_var = tk.StringVar(value=s_type)
            ttk.Combobox(row, textvariable=t_var, values=["walk", "fly", "swim", "climb", "burrow"], width=8, state="readonly").pack(side=tk.LEFT, padx=2)
            v_en = tk.Entry(row, width=5)
            v_en.insert(0, str(s_val))
            v_en.pack(side=tk.LEFT, padx=2)
            tk.Label(row, text="ft.", bg="#fdf1dc").pack(side=tk.LEFT)
            c_en = tk.Entry(row, width=15)
            c_en.insert(0, str(s_cond))
            c_en.pack(side=tk.LEFT, padx=2)
            def remove():
                row.destroy()
                self.speed_refs.remove((t_var, v_en, c_en, row))
            tk.Button(row, text="X", bg="#ff4d4d", fg="white", font=("Arial", 8, "bold"), command=remove).pack(side=tk.LEFT, padx=5)
            self.speed_refs.append((t_var, v_en, c_en, row))

        self.can_hover_var = tk.BooleanVar(value=False)
        tk.Checkbutton(speed_master, text="Can Hover", variable=self.can_hover_var, bg="#fdf1dc").pack(side=tk.LEFT, padx=10)
        tk.Button(speed_master, text="+ Add Speed", bg="#d9ad6c", font=("Arial", 9, "bold"), command=add_speed_row).pack(side=tk.LEFT)

        for k, v in self.edit_data.get("speed", {}).items():
            if k == "canHover": self.can_hover_var.set(v)
            elif isinstance(v, dict): add_speed_row(k, v.get("number", ""), v.get("condition", ""))
            else: add_speed_row(k, v, "")

        abilities_frame = tk.Frame(self.edit_inner, bg="#fdf1dc")
        abilities_frame.pack(fill=tk.X, pady=15)
        
        tk.Label(abilities_frame, text="Value", bg="#fdf1dc", font=self.body_italic, fg="#555").grid(row=1, column=0, sticky="e", padx=(0,5))
        tk.Label(abilities_frame, text="Mod Override", bg="#fdf1dc", font=self.body_italic, fg="#555").grid(row=2, column=0, sticky="e", padx=(0,5))
        tk.Label(abilities_frame, text="Save Override", bg="#fdf1dc", font=self.body_italic, fg="#555").grid(row=3, column=0, sticky="e", padx=(0,5))

        self.edit_ability_refs = {}
        for i, stat in enumerate(["str", "dex", "con", "int", "wis", "cha"]):
            tk.Label(abilities_frame, text=stat.upper(), bg="#fdf1dc", font=self.body_bold).grid(row=0, column=i+1, padx=5)
            v_en = tk.Entry(abilities_frame, width=6, justify="center", font=self.body_font)
            v_en.insert(0, str(self.edit_data.get(stat, 10)))
            v_en.grid(row=1, column=i+1, padx=5, pady=2)
            m_en = tk.Entry(abilities_frame, width=6, justify="center", font=self.body_font)
            m_en.insert(0, str(self.edit_data.get("modOverride", {}).get(stat, "")))
            m_en.grid(row=2, column=i+1, padx=5, pady=2)
            s_en = tk.Entry(abilities_frame, width=6, justify="center", font=self.body_font)
            s_en.insert(0, str(self.edit_data.get("save", {}).get(stat, "")))
            s_en.grid(row=3, column=i+1, padx=5, pady=2)
            self.edit_ability_refs[stat] = (v_en, m_en, s_en)

        self.attack_tags = {"None": "", "Melee Weapon": "{@atk mw}", "Ranged Weapon": "{@atk rw}", "Melee/Ranged Weapon": "{@atk mw,rw}", "Melee Spell": "{@atk ms}", "Ranged Spell": "{@atk rs}", "Melee/Ranged Spell": "{@atk ms,rs}"}
        self.inv_attack_tags = {v: k for k, v in self.attack_tags.items() if v}

        self.arrays_frame = tk.Frame(self.edit_inner, bg="#fdf1dc")
        self.arrays_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.array_refs = {}
        self.sc_refs = []
        self.rebuild_sc_hooks = []
        
        def rebuild_all_sc():
            self.sc_refs.clear()
            for hook in self.rebuild_sc_hooks: hook()

        for sec_key, sec_title in [("trait", "Traits"), ("action", "Actions"), ("bonus", "Bonus Actions"), ("reaction", "Reactions"), ("legendary", "Legendary Actions")]:
            self.build_array_section(sec_key, sec_title, rebuild_all_sc)
            
        rebuild_all_sc()

    def build_array_section(self, key, title, rebuild_all_sc):
        sec_frame = tk.Frame(self.arrays_frame, bg="#fdf1dc", pady=10)
        sec_frame.pack(fill=tk.X)
        header_frame = tk.Frame(sec_frame, bg="#fdf1dc")
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text=title, font=self.header_font, fg="#7a200d", bg="#fdf1dc").pack(side=tk.LEFT)
        
        btn_frame = tk.Frame(header_frame, bg="#fdf1dc")
        btn_frame.pack(side=tk.LEFT, padx=15)
        tk.Button(btn_frame, text="+ Add Field", bg="#d9ad6c", font=("Arial", 10, "bold"), command=lambda: add_item()).pack(side=tk.LEFT, padx=5)

        # Embedded Spellcasting UI
        sc_type = "slots" if key == "trait" else ("innate" if key == "action" else None)
        sc_container = tk.Frame(sec_frame, bg="#fdf1dc")
        sc_container.pack(fill=tk.X)
        
        if sc_type:
            btn_add_sc = tk.Button(btn_frame, text=f"+ Add {'Slots' if sc_type=='slots' else 'Innate'} Spellcasting", bg="#d9ad6c", font=("Arial", 10, "bold"))
            btn_add_sc.pack(side=tk.LEFT, padx=5)
            
            def rebuild_local_sc():
                for w in sc_container.winfo_children(): w.destroy()
                sc_data = self.edit_data.get("spellcasting", [])
                has_matching = False
                
                for i, sc_dict in enumerate(sc_data):
                    is_innate_block = sc_dict.get("displayAs") == "action"
                    if (sc_type == "slots" and is_innate_block) or (sc_type == "innate" and not is_innate_block): continue
                    
                    has_matching = True
                    for h_i, h_str in enumerate(sc_dict.get("headerEntries", [])):
                        if "{@custom_dc}" not in h_str:
                            dc_match = re.search(r'{@dc (\d+)}', h_str)
                            if dc_match:
                                sc_dict["custom_dc"] = int(dc_match.group(1))
                                sc_dict["headerEntries"][h_i] = re.sub(r'{@dc \d+}', '{@custom_dc}', sc_dict["headerEntries"][h_i])
                        if "{@custom_hit}" not in h_str:
                            hit_match = re.search(r'{@hit (\d+)}', h_str)
                            if hit_match:
                                sc_dict["custom_hit"] = int(hit_match.group(1))
                                sc_dict["headerEntries"][h_i] = re.sub(r'{@hit \d+}', '{@custom_hit}', sc_dict["headerEntries"][h_i])

                    block = tk.Frame(sc_container, bg="#f5e6ce", bd=1, relief=tk.SOLID, pady=10, padx=10)
                    block.pack(fill=tk.X, pady=5)
                    top = tk.Frame(block, bg="#f5e6ce")
                    top.pack(fill=tk.X)
                    tk.Label(top, text="Innate Spellcasting" if is_innate_block else "Slots Spellcasting", font=self.body_bold, bg="#f5e6ce").pack(side=tk.LEFT)

                    def make_remover(idx=i):
                        self.edit_data["spellcasting"].pop(idx)
                        rebuild_all_sc()
                    tk.Button(top, text="X Remove Block", bg="#ff4d4d", fg="white", font=("Arial", 9, "bold"), command=make_remover).pack(side=tk.RIGHT)
                    
                    param_row = tk.Frame(block, bg="#f5e6ce")
                    param_row.pack(fill=tk.X, pady=5)
                    
                    tk.Label(param_row, text="Ability:", bg="#f5e6ce", font=self.body_bold).pack(side=tk.LEFT)
                    ab_var = tk.StringVar(value=sc_dict.get("ability", "int").capitalize())
                    ttk.Combobox(param_row, textvariable=ab_var, values=["Int", "Wis", "Cha", "Str", "Dex", "Con"], state="readonly", width=5).pack(side=tk.LEFT, padx=(2, 10))

                    tk.Label(param_row, text="Save DC:", bg="#f5e6ce", font=self.body_bold).pack(side=tk.LEFT)
                    dc_var = tk.StringVar(value=str(sc_dict.get("custom_dc", 10)))
                    tk.Entry(param_row, textvariable=dc_var, width=4).pack(side=tk.LEFT, padx=(2, 10))

                    tk.Label(param_row, text="To Hit:", bg="#f5e6ce", font=self.body_bold).pack(side=tk.LEFT)
                    hit_var = tk.StringVar(value=str(sc_dict.get("custom_hit", 2)))
                    tk.Entry(param_row, textvariable=hit_var, width=4).pack(side=tk.LEFT, padx=(2, 10))

                    tk.Label(block, text="Header Template:", bg="#f5e6ce", font=self.body_italic).pack(anchor="w")
                    hdr_text = tk.Text(block, height=3, font=self.body_font, wrap=tk.WORD)
                    hdr_text.insert("1.0", " ".join(sc_dict.get("headerEntries", [])))
                    hdr_text.pack(fill=tk.X, pady=(0, 5))

                    slots_entries = {}
                    spells_frame = tk.Frame(block, bg="#f5e6ce")
                    spells_frame.pack(fill=tk.X, pady=5)

                    if not is_innate_block:
                        spells_dict = sc_dict.setdefault("spells", {})
                        for lvl in range(10):
                            lvl_str = str(lvl)
                            if lvl_str in spells_dict:
                                lvl_data = spells_dict[lvl_str]
                                row = tk.Frame(spells_frame, bg="#f5e6ce", pady=2)
                                row.pack(fill=tk.X)
                                tk.Label(row, text=f"Level {lvl}:", font=self.body_bold, bg="#f5e6ce", width=8, anchor="w").pack(side=tk.LEFT)
                                if lvl > 0:
                                    tk.Label(row, text="Slots:", bg="#f5e6ce").pack(side=tk.LEFT)
                                    se = tk.Entry(row, width=3)
                                    se.insert(0, str(lvl_data.get("slots", 0)))
                                    se.pack(side=tk.LEFT, padx=(0,10))
                                spells_list = lvl_data.setdefault("spells", [])
                                for s_idx, s_name in enumerate(spells_list):
                                    sf = tk.Frame(row, bg="#e8d5b7", padx=2, pady=2, bd=1, relief=tk.RAISED)
                                    sf.pack(side=tk.LEFT, padx=2)
                                    tk.Label(sf, text=self.clean_5etools_text(s_name), bg="#e8d5b7", font=("Arial", 9)).pack(side=tk.LEFT)
                                    def make_spell_remover(level=lvl_str, index=s_idx):
                                        spells_dict[level]["spells"].pop(index)
                                        if not spells_dict[level]["spells"]: del spells_dict[level]
                                        rebuild_all_sc()
                                    tk.Button(sf, text="x", bg="#ff4d4d", fg="white", font=("Arial", 7), padx=2, pady=0, command=make_spell_remover).pack(side=tk.LEFT)
                    else:
                        if "will" in sc_dict:
                            row = tk.Frame(spells_frame, bg="#f5e6ce", pady=2)
                            row.pack(fill=tk.X)
                            tk.Label(row, text="At will:", font=self.body_bold, bg="#f5e6ce", width=8, anchor="w").pack(side=tk.LEFT)
                            for s_idx, s_name in enumerate(sc_dict["will"]):
                                sf = tk.Frame(row, bg="#e8d5b7", padx=2, pady=2, bd=1, relief=tk.RAISED)
                                sf.pack(side=tk.LEFT, padx=2)
                                tk.Label(sf, text=self.clean_5etools_text(s_name), bg="#e8d5b7", font=("Arial", 9)).pack(side=tk.LEFT)
                                def make_will_remover(index=s_idx):
                                    sc_dict["will"].pop(index)
                                    if not sc_dict["will"]: del sc_dict["will"]
                                    rebuild_all_sc()
                                tk.Button(sf, text="x", bg="#ff4d4d", fg="white", font=("Arial", 7), padx=2, pady=0, command=make_will_remover).pack(side=tk.LEFT)

                        daily_dict = sc_dict.setdefault("daily", {})
                        for freq, spells_list in daily_dict.items():
                            row = tk.Frame(spells_frame, bg="#f5e6ce", pady=2)
                            row.pack(fill=tk.X)
                            tk.Label(row, text=f"{freq}/day:", font=self.body_bold, bg="#f5e6ce", width=8, anchor="w").pack(side=tk.LEFT)
                            for s_idx, s_name in enumerate(spells_list):
                                sf = tk.Frame(row, bg="#e8d5b7", padx=2, pady=2, bd=1, relief=tk.RAISED)
                                sf.pack(side=tk.LEFT, padx=2)
                                tk.Label(sf, text=self.clean_5etools_text(s_name), bg="#e8d5b7", font=("Arial", 9)).pack(side=tk.LEFT)
                                def make_daily_remover(f=freq, index=s_idx):
                                    daily_dict[f].pop(index)
                                    if not daily_dict[f]: del daily_dict[f]
                                    rebuild_all_sc()
                                tk.Button(sf, text="x", bg="#ff4d4d", fg="white", font=("Arial", 7), padx=2, pady=0, command=make_daily_remover).pack(side=tk.LEFT)

                    def add_spell_to_block(block_ref=sc_dict):
                        def on_spell_selected(spell_data, freq=None):
                            spell_name = spell_data["name"].lower()
                            formatted_spell = f"{{@spell {spell_name}}}"
                            if not is_innate_block:
                                lvl = spell_data.get("level", 0)
                                sdict = block_ref.setdefault("spells", {})
                                ldict = sdict.setdefault(str(lvl), {"spells": []})
                                ldict["spells"].append(formatted_spell)
                                if lvl > 0 and "slots" not in ldict: ldict["slots"] = 1
                                rebuild_all_sc()
                            else:
                                if freq == "will": block_ref.setdefault("will", []).append(formatted_spell)
                                else: block_ref.setdefault("daily", {}).setdefault(freq, []).append(formatted_spell)
                                rebuild_all_sc()
                        SpellSearchDialog(self, self.spells_index, is_innate_block, on_spell_selected)

                    tk.Button(block, text="+ Add Spell", bg="#4a90e2", fg="white", font=("Arial", 9, "bold"), command=add_spell_to_block).pack(pady=5)
                    self.sc_refs.append((sc_dict, hdr_text, ab_var, dc_var, hit_var, slots_entries))
                    
                btn_add_sc.config(state=tk.DISABLED if has_matching else tk.NORMAL)
            
            self.rebuild_sc_hooks.append(rebuild_local_sc)
            
            def add_sc_block():
                name = self.edit_refs["name"].get().strip() or "creature"
                if sc_type == "slots":
                    default_header = f"{name} is a @level spellcaster. Its spellcasting ability is @ability (spell save {{@custom_dc}}, {{@custom_hit}} to hit with spell attacks). {name} has the following spells prepared:"
                    self.edit_data.setdefault("spellcasting", []).append({
                        "name": "Spellcasting", "type": "spellcasting", "headerEntries": [default_header], 
                        "ability": "int", "custom_dc": 10, "custom_hit": 2, "spells": {}
                    })
                else:
                    default_header = f"{name} casts one of the following spells, using @ability as the spellcasting ability (spell save {{@custom_dc}}, {{@custom_hit}} to hit with spell attacks):"
                    self.edit_data.setdefault("spellcasting", []).append({
                        "name": "Innate Spellcasting", "type": "spellcasting", "headerEntries": [default_header], 
                        "ability": "int", "custom_dc": 10, "custom_hit": 2, "displayAs": "action"
                    })
                rebuild_all_sc()
            btn_add_sc.config(command=add_sc_block)

        items_container = tk.Frame(sec_frame, bg="#fdf1dc")
        items_container.pack(fill=tk.X)
        self.array_refs[key] = []
        
        def add_item(name="", entries_str=""):
            item_frame = tk.Frame(items_container, bg="#f5e6ce", bd=1, relief=tk.SOLID, pady=10, padx=10)
            item_frame.pack(fill=tk.X, pady=5)
            top = tk.Frame(item_frame, bg="#f5e6ce")
            top.pack(fill=tk.X)
            
            tk.Label(top, text="Name:", bg="#f5e6ce", font=self.body_bold).pack(side=tk.LEFT)
            name_entry = tk.Entry(top, width=30, font=self.body_font)
            name_entry.insert(0, name)
            name_entry.pack(side=tk.LEFT, padx=5)

            # Smart Extraction for Attacks
            hit_val, reach_val, dmg_form_val, dmg_type_val = "", "", "", ""
            
            hit_m = re.search(r'{@hit ([^}]+)}', entries_str)
            if hit_m:
                hit_val = hit_m.group(1)
                entries_str = re.sub(r'{@hit [^}]+}', '@attack_hit', entries_str, count=1)
                
            reach_m = re.search(r'reach (\d+(?:/\d+)?) ft\.', entries_str)
            if reach_m:
                reach_val = reach_m.group(1)
                entries_str = re.sub(r'reach \d+(?:/\d+)? ft\.', 'reach @attack_reach ft.', entries_str, count=1)
                
            dmg_m1 = re.search(r'{@h}\d+\s*\({@damage\s*([^}]+)}\)\s*(.*?)damage(?:\.)?', entries_str)
            dmg_m2 = re.search(r'{@h}(\d+)\s+(.*?)damage(?:\.)?', entries_str)
            
            if dmg_m1:
                dmg_form_val = dmg_m1.group(1).strip()
                dmg_type_val = dmg_m1.group(2).strip()
                entries_str = entries_str.replace(dmg_m1.group(0), "{@attack_dmg}")
            elif dmg_m2:
                dmg_form_val = dmg_m2.group(1).strip()
                dmg_type_val = dmg_m2.group(2).strip()
                entries_str = entries_str.replace(dmg_m2.group(0), "{@attack_dmg}")
            elif "{@h}" in entries_str:
                dmg_m3 = re.search(r'{@h}(.*?)(?=\s+[a-zA-Z])', entries_str)
                if dmg_m3:
                    dmg_form_val = dmg_m3.group(1).strip()
                    entries_str = entries_str.replace(f"{{@h}}{dmg_form_val}", "{@attack_dmg}")
                else:
                    entries_str = entries_str.replace("{@h}", "{@attack_dmg}")

            found_atk = "None"
            for tag, tag_name in self.inv_attack_tags.items():
                if entries_str.startswith(tag):
                    found_atk = tag_name
                    entries_str = entries_str[len(tag):].lstrip()
                    break
                    
            tk.Label(top, text="Attack Type:", bg="#f5e6ce", font=self.body_bold).pack(side=tk.LEFT, padx=(15, 2))
            atk_var = tk.StringVar(value=found_atk)
            atk_cb = ttk.Combobox(top, textvariable=atk_var, values=list(self.attack_tags.keys()), state="readonly", width=18)
            atk_cb.pack(side=tk.LEFT, padx=5)
            
            def remove_item():
                item_frame.destroy()
                self.array_refs[key].remove((name_entry, atk_var, desc_text, hit_en, reach_en, dmg_form_en, dmg_type_en))
            tk.Button(top, text="X Remove", bg="#ff4d4d", fg="white", font=("Arial", 9, "bold"), command=remove_item).pack(side=tk.RIGHT)
            
            atk_params_frame = tk.Frame(item_frame, bg="#f5e6ce")
            atk_params_frame.pack(fill=tk.X, pady=2)
            
            tk.Label(atk_params_frame, text="Hit Mod:", bg="#f5e6ce", font=self.body_italic).pack(side=tk.LEFT)
            hit_en = tk.Entry(atk_params_frame, width=5)
            hit_en.insert(0, hit_val)
            hit_en.pack(side=tk.LEFT, padx=(2, 10))
            
            tk.Label(atk_params_frame, text="Reach:", bg="#f5e6ce", font=self.body_italic).pack(side=tk.LEFT)
            reach_en = tk.Entry(atk_params_frame, width=8)
            reach_en.insert(0, reach_val)
            reach_en.pack(side=tk.LEFT, padx=(2, 10))
            
            tk.Label(atk_params_frame, text="Dmg Formula:", bg="#f5e6ce", font=self.body_italic).pack(side=tk.LEFT)
            dmg_form_en = tk.Entry(atk_params_frame, width=8)
            dmg_form_en.insert(0, dmg_form_val)
            dmg_form_en.pack(side=tk.LEFT, padx=(2, 10))
            
            tk.Label(atk_params_frame, text="Dmg Type:", bg="#f5e6ce", font=self.body_italic).pack(side=tk.LEFT)
            dmg_type_en = tk.Entry(atk_params_frame, width=12)
            dmg_type_en.insert(0, dmg_type_val)
            dmg_type_en.pack(side=tk.LEFT, padx=(2, 10))

            tk.Label(item_frame, text="Description / Entries:", bg="#f5e6ce", font=self.body_italic).pack(anchor="w", pady=(5,0))
            desc_text = tk.Text(item_frame, height=4, font=self.body_font, wrap=tk.WORD)
            desc_text.insert("1.0", entries_str)
            desc_text.pack(fill=tk.X)
            
            self.array_refs[key].append((name_entry, atk_var, desc_text, hit_en, reach_en, dmg_form_en, dmg_type_en))
            
        for item in self.edit_data.get(key, []):
            if isinstance(item, str): add_item(name="", entries_str=item)
            elif isinstance(item, dict):
                name = item.get("name", "")
                entries_list = item.get("entries", [])
                if isinstance(entries_list, list) and all(isinstance(e, str) for e in entries_list): entries_str = "\n".join(entries_list)
                else: entries_str = json.dumps(entries_list, indent=2)
                add_item(name, entries_str)

    def _handle_gui_save(self, monster_dir, save_callback):
        data = self.edit_data
        
        def calculate_avg(formula):
            if formula.isdigit(): return int(formula)
            match = re.match(r'(\d+)d(\d+)(?:\s*([+-])\s*(\d+))?', formula.replace(' ', ''))
            if match:
                n_dice, d_size, m_sign = int(match.group(1)), int(match.group(2)), match.group(3)
                m_val = int(match.group(4)) if match.group(4) else 0
                avg = int(n_dice * ((d_size + 1) / 2.0))
                if m_sign == '+': avg += m_val
                elif m_sign == '-': avg -= m_val
                return avg
            return 0
            
        for key, entry in self.edit_refs.items():
            if key in ["ac", "hp_formula"]: continue 
            val = entry.get().strip()
            if key == "level": data[key] = int(val) if val.isdigit() else 1
            elif val.startswith("{") or val.startswith("["):
                try: data[key] = json.loads(val)
                except: data[key] = val
            else: data[key] = val
                
        data["size"] = [self.size_map.get(self.size_var.get(), "M")]
        data["alignment"] = self.align_map.get(self.align_var.get(), ["N"])
        
        ac_str = self.edit_refs["ac"].get().strip()
        if ac_str.isdigit(): data["ac"] = [int(ac_str)]
        else: data["ac"] = [ac_str]
        
        hp_form = self.edit_refs["hp_formula"].get().strip()
        data["hp"] = {"average": calculate_avg(hp_form) if hp_form else 10, "formula": hp_form}

        new_speed = {}
        for t_var, v_en, c_en, _ in self.speed_refs:
            t = t_var.get().strip()
            v = v_en.get().strip()
            c = c_en.get().strip()
            if not t or not v: continue
            if v.isdigit(): v = int(v)
            if c: new_speed[t] = {"number": v, "condition": c}
            else: new_speed[t] = v
        if self.can_hover_var.get(): new_speed["canHover"] = True
        if new_speed: data["speed"] = new_speed
        else: data.pop("speed", None)

        saves, mod_overrides = {}, {}
        for stat, refs in self.edit_ability_refs.items():
            val = refs[0].get().strip()
            data[stat] = int(val) if val.isdigit() else 10
            mod = refs[1].get().strip()
            if mod: mod_overrides[stat] = mod
            save = refs[2].get().strip()
            if save: saves[stat] = save
            
        if saves: data["save"] = saves
        else: data.pop("save", None)
        if mod_overrides: data["modOverride"] = mod_overrides
        else: data.pop("modOverride", None)

        sc_data = []
        for sc_dict, hdr_text, ab_var, dc_var, hit_var, slots_entries in self.sc_refs:
            sc_dict["headerEntries"] = [hdr_text.get("1.0", "end-1c").strip()]
            sc_dict["ability"] = ab_var.get().lower()
            
            dc_val = dc_var.get().strip()
            sc_dict["custom_dc"] = int(dc_val) if dc_val.isdigit() else 10
            
            hit_val = hit_var.get().strip()
            sc_dict["custom_hit"] = int(hit_val) if hit_val.lstrip('+-').isdigit() else 2

            if "spells" in sc_dict:
                for lvl, se in slots_entries.items():
                    val = se.get().strip()
                    if val.isdigit(): sc_dict["spells"][lvl]["slots"] = int(val)
            sc_data.append(sc_dict)
            
        if sc_data: data["spellcasting"] = sc_data
        else: data.pop("spellcasting", None)

        for key, items in self.array_refs.items():
            parsed_items = []
            for name_entry, atk_var, desc_text, hit_en, reach_en, dmg_form_en, dmg_type_en in items:
                name = name_entry.get().strip()
                desc = desc_text.get("1.0", "end-1c").strip()
                atk_val = atk_var.get()
                
                h_val = hit_en.get().strip()
                r_val = reach_en.get().strip()
                f_val = dmg_form_en.get().strip()
                t_val = dmg_type_en.get().strip()
                
                desc = desc.replace("@attack_hit", f"{{@hit {h_val}}}")
                desc = desc.replace("@attack_reach", r_val)
                
                if f_val:
                    avg = calculate_avg(f_val)
                    dmg_str = f"{{@h}}{avg} ({{@damage {f_val}}})" if 'd' in f_val.lower() else f"{{@h}}{f_val}"
                    if t_val: dmg_str += f" {t_val} damage."
                    else: dmg_str += " damage."
                    desc = desc.replace("{@attack_dmg}", dmg_str)
                    desc = desc.replace("..", ".") 
                else:
                    desc = desc.replace("{@attack_dmg}", "")

                if atk_val != "None": desc = f"{self.attack_tags[atk_val]} {desc}"
                if not name and not desc: continue
                
                if desc.startswith("[") and desc.endswith("]"):
                    try: entries = json.loads(desc)
                    except: entries = desc.split("\n")
                else: entries = desc.split("\n")
                parsed_items.append({"name": name, "entries": entries})
            if parsed_items: data[key] = parsed_items
            else: data.pop(key, None) 
                
        save_callback(monster_dir, data)

    def _cancel_edit(self, cancel_callback):
        self.edit_container.pack_forget()
        self.view_container.pack(fill=tk.BOTH, expand=True)
        cancel_callback()

    # ==========================================
    # RENDER MODE LOGIC (View Mode)
    # ==========================================
    def clean_5etools_text(self, text):
        replacements = {
            r'{@atk mw}': 'Melee Weapon Attack:', r'{@atk rw}': 'Ranged Weapon Attack:',
            r'{@atk mw,rw}': 'Melee or Ranged Weapon Attack:', r'{@atk ms}': 'Melee Spell Attack:',
            r'{@atk rs}': 'Ranged Spell Attack:', r'{@atk ms,rs}': 'Melee or Ranged Spell Attack:',
            r'{@h}': 'Hit: ', r'{@hit (\d+)}': r'+\1', r'{@damage (.*?)}': r'\1',
            r'{@dc (\d+)}': r'DC \1', r'{@condition (.*?)(?:\|.*?)?}': r'\1', r'{@variantrule (.*?)(?:\|.*?)?}': r'\1',
            r'{@recharge\s*(\d*)}': lambda m: f"(Recharge {m.group(1)}-6)" if m.group(1) else "(Recharge 6)"
        }
        text = re.sub(r'{@spell ([^|}]+)[^}]*}', r'«SPELL:\1»', text, flags=re.IGNORECASE)
        for pattern, repl in replacements.items(): text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
        def save_replacer(match): return f"{match.group(1).capitalize()} Saving Throw:"
        text = re.sub(r'{@actSave (\w+)}', save_replacer, text)
        text = re.sub(r'{@\w+ ([^|}]+)[^}]*}', r'\1', text)
        return text

    def insert_text_with_links(self, text, base_tags):
        if isinstance(base_tags, str): base_tags = (base_tags,)
        parts = re.split(r'(«SPELL:[^»]+»)', text)
        for part in parts:
            if part.startswith("«SPELL:") and part.endswith("»"):
                spell_name = part[7:-1]
                spell_tag = f"SPELL_TAG:{spell_name.lower()}"
                self.text.insert(tk.END, spell_name, base_tags + ("spell_link", spell_tag))
            elif part: self.text.insert(tk.END, part, base_tags)

    def extract_entries(self, entries):
        if not entries: return ""
        if isinstance(entries, str): return self.clean_5etools_text(entries) + "\n"
        out = ""
        for entry in entries:
            if isinstance(entry, str): out += self.clean_5etools_text(entry) + "\n"
            elif isinstance(entry, dict):
                if entry.get("type") == "list":
                    for item in entry.get("items", []): out += f"• {self.extract_entries([item]).strip()}\n"
                elif "entries" in entry:
                    if "name" in entry: out += f"{self.clean_5etools_text(entry['name'])}. "
                    out += self.extract_entries(entry["entries"])
        return out

    def parse_complex_list(self, data_list):
        if not data_list: return ""
        if isinstance(data_list, str): return data_list
        out = []
        for item in data_list:
            if isinstance(item, str): out.append(item)
            elif isinstance(item, dict):
                if "special" in item: out.append(str(item["special"]))
                else:
                    keys = [k for k in item.keys() if k not in ["note", "preNote", "cond"]]
                    if keys:
                        main_val = item[keys[0]]
                        main_str = ", ".join(main_val) if isinstance(main_val, list) else str(main_val)
                        if "note" in item: main_str += f" ({item['note']})"
                        out.append(main_str)
        res = ", ".join(out)
        return res[0].upper() + res[1:] if res else ""

    def calculate_modifier(self, score):
        mod = (score - 10) // 2
        return f"+{mod}" if mod >= 0 else str(mod)

    def build_ability_scores(self, data):
        grid = tk.Frame(self.text, bg="#fdf1dc", pady=10)
        stats = ["str", "dex", "con", "int", "wis", "cha"]
        tk.Label(grid, text="Value", font=self.body_italic, bg="#fdf1dc", fg="#555").grid(row=1, column=0, sticky="e", padx=(0, 10))
        tk.Label(grid, text="Mod", font=self.body_italic, bg="#fdf1dc", fg="#555").grid(row=2, column=0, sticky="e", padx=(0, 10))
        tk.Label(grid, text="Save", font=self.body_italic, bg="#fdf1dc", fg="#555").grid(row=3, column=0, sticky="e", padx=(0, 10))
        
        for i, stat in enumerate(stats):
            col = i + 1 
            grid.grid_columnconfigure(col, weight=1, minsize=60)
            score = data.get(stat, 10)
            mod = data.get("modOverride", {}).get(stat, "")
            if not mod: mod = self.calculate_modifier(score)
            save_val = data.get("save", {}).get(stat, "")
            if not save_val: save_val = mod 
            if isinstance(save_val, int) or (isinstance(save_val, str) and save_val.lstrip('-').isdigit()):
                save_val = f"+{save_val}" if int(save_val) >= 0 else str(save_val)

            tk.Label(grid, text=stat.upper(), font=self.body_bold, bg="#fdf1dc", fg="#58180d").grid(row=0, column=col)
            tk.Label(grid, text=str(score), font=self.body_font, bg="#fdf1dc").grid(row=1, column=col)
            tk.Label(grid, text=str(mod), font=self.body_font, bg="#fdf1dc").grid(row=2, column=col)
            tk.Label(grid, text=str(save_val), font=self.body_font, bg="#fdf1dc").grid(row=3, column=col)

        self.text.window_create(tk.END, window=grid)
        self.text.insert(tk.END, "\n")

    def _render_spellcasting(self, spellcasting_list, caster_level):
        if not spellcasting_list: return
        
        def get_ordinal(n):
            try:
                n = int(n)
                if 11 <= (n % 100) <= 13: return f"{n}th-level"
                return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}-level"
            except: return f"{n}-level"

        for sc in spellcasting_list:
            name = self.clean_5etools_text(sc.get("name", "Spellcasting"))
            self.text.insert(tk.END, f"{name}\n", "bold") 
            
            headers = sc.get("headerEntries", [])
            formatted_headers = []
            for h in headers:
                lvl_str = get_ordinal(caster_level)
                ab = sc.get("ability", "int").capitalize()
                ab_long = {"Int": "Intelligence", "Wis": "Wisdom", "Cha": "Charisma"}.get(ab, ab)
                dc = sc.get("custom_dc", 10)
                hit = sc.get("custom_hit", 2)
                
                h = h.replace("@level", lvl_str)
                h = h.replace("@ability", ab_long)
                h = h.replace("{@custom_dc}", f"{{@dc {dc}}}")
                h = h.replace("{@custom_hit}", f"{{@hit {hit}}}")
                formatted_headers.append(h)
                
            header_text = " ".join([self.clean_5etools_text(h) for h in formatted_headers])
            self.insert_text_with_links(f"{header_text}\n", "body_indented")
            
            if "will" in sc:
                spells = ", ".join([self.clean_5etools_text(s) for s in sc["will"]])
                self.insert_text_with_links(f"At will: {spells}\n", "body_indented")
            if "daily" in sc:
                for freq, spells_list in sc["daily"].items():
                    freq_num = freq[0]
                    each = " each" if freq.endswith("e") else ""
                    spells = ", ".join([self.clean_5etools_text(s) for s in spells_list])
                    self.insert_text_with_links(f"{freq_num}/day{each}: {spells}\n", "body_indented")
            if "spells" in sc:
                levels = {"0": "Cantrips (at will)", "1": "1st level", "2": "2nd level", "3": "3rd level", "4": "4th level", "5": "5th level", "6": "6th level", "7": "7th level", "8": "8th level", "9": "9th level"}
                for level in range(10):
                    str_level = str(level)
                    if str_level in sc["spells"]:
                        level_data = sc["spells"][str_level]
                        lvl_str = levels.get(str_level, f"{level} level")
                        slots = level_data.get("slots")
                        if slots: lvl_str += f" ({slots} slots)"
                        spells = ", ".join([self.clean_5etools_text(s) for s in level_data.get("spells", [])])
                        self.insert_text_with_links(f"{lvl_str}: {spells}\n", "body_indented")
            self.text.insert(tk.END, "\n")

    def render_monster(self, data):
        self.clear_overlays()
        self.edit_container.pack_forget()
        self.view_container.pack(fill=tk.BOTH, expand=True)

        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.dividers.clear()

        self.text.insert(tk.END, data.get("name", "Unknown Monster") + "\n", "title")
        size_map = {"T": "Tiny", "S": "Small", "M": "Medium", "L": "Large", "H": "Huge", "G": "Gargantuan"}
        size = size_map.get(data.get("size", ["M"])[0], "Medium")
        
        raw_type = data.get("type", "unknown")
        if isinstance(raw_type, dict):
            base_type = raw_type.get("type", "unknown")
            tags = raw_type.get("tags", [])
            m_type = f"{base_type} ({', '.join(tags)})" if tags else base_type
        else: m_type = str(raw_type)
        m_type = m_type.title()
        
        align_raw = data.get("alignment", ["N"])
        prefix = data.get("alignmentPrefix", "")
        if len(align_raw) > 0 and isinstance(align_raw[0], dict) and "special" in align_raw[0]: alignment = align_raw[0]["special"]
        else:
            align_map = {"L": "Lawful", "N": "Neutral", "C": "Chaotic", "G": "Good", "E": "Evil", "U": "Unaligned", "A": "Any"}
            clean_align = [a for a in align_raw if isinstance(a, str)]
            alignment = " ".join([align_map.get(a, a) for a in clean_align])
            
        self.text.insert(tk.END, f"{size} {m_type}, {prefix}{alignment}\n", "subtitle")
        self.insert_divider()

        ac = data.get("ac", [10])[0]
        if isinstance(ac, dict):
            ac_val = str(ac.get("ac", ""))
            if "from" in ac: ac_val += f" ({self.clean_5etools_text(', '.join(ac['from']))})"
        else: ac_val = str(ac)
            
        self.text.insert(tk.END, "Armor Class: ", "bold")
        self.text.insert(tk.END, f"{ac_val}\n", "body")
        
        hp_data = data.get("hp", {})
        self.text.insert(tk.END, "Hit Points: ", "bold")
        self.text.insert(tk.END, f"{hp_data.get('average', 10)} ({hp_data.get('formula', '')})\n", "body")
        
        speed_data = data.get("speed", {})
        speeds = []
        for k, v in speed_data.items():
            if isinstance(v, bool): continue
            if isinstance(v, dict): val = f"{v.get('number', '')} ft. {v.get('condition', '')}".strip()
            else: val = f"{v} ft."
            speeds.append(val if k == "walk" else f"{k} {val}")
            
        self.text.insert(tk.END, "Speed: ", "bold")
        self.text.insert(tk.END, f"{', '.join(speeds)}\n", "body")
        self.insert_divider()

        self.build_ability_scores(data)
        self.insert_divider()

        if "skill" in data:
            skills_list = []
            for k, v in data["skill"].items():
                if k == "other":
                    for other_block in v:
                        if "oneOf" in other_block:
                            options = ", ".join([f"{ok.capitalize()} {ov}" for ok, ov in other_block["oneOf"].items()])
                            skills_list.append(f"plus one of the following: {options}")
                else: skills_list.append(f"{k.capitalize()} {v}")
            self.text.insert(tk.END, "Skills: ", "bold")
            self.text.insert(tk.END, f"{', '.join(skills_list)}\n", "body")
            
        if "resist" in data:
            self.text.insert(tk.END, "Damage Resistances: ", "bold")
            self.text.insert(tk.END, f"{self.parse_complex_list(data['resist'])}\n", "body")
        if "immune" in data:
            self.text.insert(tk.END, "Damage Immunities: ", "bold")
            self.text.insert(tk.END, f"{self.parse_complex_list(data['immune'])}\n", "body")
        if "conditionImmune" in data:
            self.text.insert(tk.END, "Condition Immunities: ", "bold")
            self.text.insert(tk.END, f"{self.parse_complex_list(data['conditionImmune'])}\n", "body")
        if "senses" in data:
            senses = self.parse_complex_list(data["senses"])
            passive = data.get("passive", 10)
            self.text.insert(tk.END, "Senses: ", "bold")
            self.text.insert(tk.END, f"{senses}, passive Perception {passive}\n", "body")
        if "languages" in data:
            self.text.insert(tk.END, "Languages: ", "bold")
            self.text.insert(tk.END, f"{self.parse_complex_list(data['languages'])}\n", "body")
        if "cr" in data:
            cr_val = data["cr"].get("cr", data["cr"]) if isinstance(data["cr"], dict) else data["cr"]
            self.text.insert(tk.END, "Challenge: ", "bold")
            self.text.insert(tk.END, f"{cr_val}\n", "body")

        self.insert_divider()

        global_level = data.get("level", 1)

        sc_data = data.get("spellcasting", [])
        sc_traits = [sc for sc in sc_data if sc.get("displayAs", "trait") == "trait"]
        sc_actions = [sc for sc in sc_data if sc.get("displayAs") == "action"]
        sc_bonus = [sc for sc in sc_data if sc.get("displayAs") == "bonus"]
        sc_reactions = [sc for sc in sc_data if sc.get("displayAs") == "reaction"]

        if data.get("trait") or sc_traits:
            self.text.insert(tk.END, "TRAITS\n", "section_header")
            self.insert_divider()
            if sc_traits: self._render_spellcasting(sc_traits, global_level)
            if data.get("trait"): self._render_section(data["trait"])
                
        if data.get("action") or sc_actions:
            self.text.insert(tk.END, "ACTIONS\n", "section_header")
            self.insert_divider()
            if sc_actions: self._render_spellcasting(sc_actions, global_level)
            if data.get("action"): self._render_section(data["action"])
                
        if data.get("bonus") or sc_bonus:
            self.text.insert(tk.END, "BONUS ACTIONS\n", "section_header")
            self.insert_divider()
            if sc_bonus: self._render_spellcasting(sc_bonus, global_level)
            if data.get("bonus"): self._render_section(data["bonus"])
                
        if data.get("reaction") or sc_reactions:
            self.text.insert(tk.END, "REACTIONS\n", "section_header")
            self.insert_divider()
            if sc_reactions: self._render_spellcasting(sc_reactions, global_level)
            if data.get("reaction"): self._render_section(data["reaction"])
        
        if "legendary" in data:
            self.text.insert(tk.END, "LEGENDARY ACTIONS\n", "section_header")
            self.insert_divider()
            self._render_section(data["legendary"])

        self.text.config(state=tk.DISABLED)

    def _render_section(self, entries_list):
        if not entries_list: return
        for item in entries_list:
            name = item.get("name", "")
            if name: self.text.insert(tk.END, f"{self.clean_5etools_text(name)}\n", "bold")
            content = self.extract_entries(item.get("entries", []))
            self.insert_text_with_links(content, "body_indented")
            self.text.insert(tk.END, "\n")

    # ==========================================
    # SPELLS RENDERER
    # ==========================================
    def render_spell(self, data, back_callback=None):
        self.clear_overlays()
        self.edit_container.pack_forget()
        self.view_container.pack(fill=tk.BOTH, expand=True)

        if back_callback:
            btn_back = tk.Button(self.view_container, text="BACK", bg="#58180d", fg="white", font=("Georgia", 10, "bold"), command=back_callback)
            btn_back.place(relx=1.0, x=-100, y=10, width=80, height=30)
            self.overlay_buttons.append(btn_back)

        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.dividers.clear()

        self.text.insert(tk.END, data.get("name", "Unknown Spell") + "\n", "title")
        source = data.get("source", "Unknown")
        page = data.get("page", "")
        self.text.insert(tk.END, f"{source}\n", "subtitle")
        if page: self.text.insert(tk.END, f"p{page}\n", "subtitle")
            
        level = data.get("level", 0)
        school_map = {"A": "Abjuration", "C": "Conjuration", "D": "Divination", "E": "Enchantment", "I": "Illusion", "N": "Necromancy", "T": "Transmutation", "V": "Evocation", "P": "Psionic"}
        school = school_map.get(data.get("school", ""), "Unknown School")
        
        if level == 0: lvl_str = f"{school} cantrip"
        else: lvl_str = f"Level {level} {school}"
        self.text.insert(tk.END, f"{lvl_str}\n", "body_bold")
        self.insert_divider()
        
        time_data = data.get("time", [{}])[0]
        t_num = time_data.get("number", 1)
        t_unit = time_data.get("unit", "action")
        
        if t_num == 1 and t_unit in ["action", "bonus", "reaction"]:
            time_str = t_unit.title()
            if t_unit == "bonus": time_str = "Bonus Action"
        else:
            time_str = f"{t_num} {t_unit}"
            if t_num > 1: time_str += "s"
            
        self.text.insert(tk.END, "Casting Time: ", "bold")
        if "condition" in time_data:
            time_str += f", {self.clean_5etools_text(time_data['condition'])}"
        self.insert_text_with_links(f"{time_str}\n", "body")
        
        range_data = data.get("range", {})
        r_type = range_data.get("type", "")
        dist = range_data.get("distance", {})
        d_type = dist.get("type", "")
        d_amt = dist.get("amount", "")
        
        if d_type == "touch": range_str = "Touch"
        elif d_type == "self": range_str = "Self"
        elif d_type in ["feet", "miles"]: range_str = f"{d_amt} {d_type}"
        else: range_str = str(d_type).title()
        
        if r_type in ["cone", "cube", "cylinder", "line", "sphere", "hemisphere", "radius"]:
             range_str = f"Self ({d_amt}-foot {r_type})"
             
        self.text.insert(tk.END, "Range: ", "bold")
        self.text.insert(tk.END, f"{range_str}\n", "body")
        
        comp_data = data.get("components", {})
        comps = []
        if "v" in comp_data: comps.append("V")
        if "s" in comp_data: comps.append("S")
        if "m" in comp_data:
            m = comp_data["m"]
            if isinstance(m, dict): comps.append(f"M ({m.get('text', m.get('item', ''))})")
            else: comps.append(f"M ({m})")
                
        self.text.insert(tk.END, "Components: ", "bold")
        self.text.insert(tk.END, f"{', '.join(comps)}\n", "body")
        
        dur_data = data.get("duration", [{}])[0]
        dur_type = dur_data.get("type", "")
        dur_str = ""
        if dur_data.get("concentration"): dur_str += "Concentration, up to "
        
        if dur_type == "timed":
            d_amt = dur_data.get("duration", {}).get("amount", 1)
            d_unit = dur_data.get("duration", {}).get("type", "minute")
            dur_str += f"{d_amt} {d_unit}"
            if d_amt > 1: dur_str += "s"
        elif dur_type == "instant": dur_str += "Instantaneous"
        elif dur_type == "permanent":
            if dur_data.get("ends"):
                if [e for e in dur_data["ends"] if e == "dispel"]: dur_str += "Until dispelled"
                else: dur_str += "Permanent"
            else: dur_str += "Permanent"
        else: dur_str += "Special"
            
        self.text.insert(tk.END, "Duration: ", "bold")
        self.text.insert(tk.END, f"{dur_str}\n", "body")
        self.insert_divider()
        
        desc = self.extract_entries(data.get("entries", []))
        self.insert_text_with_links(desc, "body")
        
        higher = data.get("entriesHigherLevel", [])
        if higher:
            self.text.insert(tk.END, "\n")
            for h in higher:
                self.text.insert(tk.END, f"{h.get('name', 'At Higher Levels')}. ", "bold")
                self.insert_text_with_links(self.extract_entries(h.get("entries", [])), "body")
                self.text.insert(tk.END, "\n")
                
        self.text.config(state=tk.DISABLED)