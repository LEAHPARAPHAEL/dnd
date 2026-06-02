import tkinter as tk
from tkinter import font, ttk, messagebox
import re
import json
import copy
import utils
from dialogs import SpellSearchDialog

class StatBlockRenderer(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, bg="#fdf1dc", *args, **kwargs) 

        self.view_container = tk.Frame(self, bg="#fdf1dc"); self.view_container.pack(fill=tk.BOTH, expand=True)
        self.v_scroll = ttk.Scrollbar(self.view_container, orient=tk.VERTICAL); self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text = tk.Text(self.view_container, bg="#fdf1dc", wrap=tk.WORD, borderwidth=0, highlightthickness=0, padx=40, pady=40, yscrollcommand=self.v_scroll.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); self.v_scroll.config(command=self.text.yview)
        
        self.spell_callback = None; self.spells_index = []
        self._setup_fonts_and_tags()
        
        self.edit_container = tk.Frame(self, bg="#fdf1dc")
        self.edit_canvas = tk.Canvas(self.edit_container, bg="#fdf1dc", highlightthickness=0)
        self.edit_scroll = ttk.Scrollbar(self.edit_container, orient="vertical", command=self.edit_canvas.yview)
        self.edit_inner = tk.Frame(self.edit_canvas, bg="#fdf1dc", padx=40, pady=20)
        self.edit_scroll.pack(side=tk.RIGHT, fill=tk.Y); self.edit_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.edit_window = self.edit_canvas.create_window((0, 0), window=self.edit_inner, anchor="nw")
        self.edit_inner.bind("<Configure>", lambda e: self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all")))
        self.edit_canvas.bind("<Configure>", lambda e: self.edit_canvas.itemconfig(self.edit_window, width=e.width))
        self.edit_canvas.configure(yscrollcommand=self.edit_scroll.set)

        self.dividers = []; self.overlay_buttons = []
        self.text.bind("<Configure>", lambda e: [div.configure(width=max(10, e.width - 80)) for div in self.dividers])

    def set_spell_callback(self, cb): self.spell_callback = cb
    def set_spells_index(self, idx): self.spells_index = idx

    def _setup_fonts_and_tags(self):
        self.title_font = font.Font(family="Times", size=24, weight="bold")
        self.header_font = font.Font(family="Times", size=18, weight="bold") 
        self.body_font = font.Font(family="Times", size=13)
        self.body_bold = font.Font(family="Times", size=13, weight="bold")
        self.body_italic = font.Font(family="Times", size=13, slant="italic")
        
        self.text.tag_configure("title", font=self.title_font, foreground="#58180d", spacing3=5)
        self.text.tag_configure("subtitle", font=self.body_italic, foreground="black", spacing3=10)
        self.text.tag_configure("section_header", font=self.header_font, foreground="#7a200d", spacing1=15, spacing3=5)
        self.text.tag_configure("body", font=self.body_font, foreground="black", spacing3=3)
        self.text.tag_configure("bold", font=self.body_bold, foreground="black")
        self.text.tag_configure("body_indented", font=self.body_font, foreground="black", lmargin1=20, lmargin2=20, spacing3=8)
        self.text.tag_configure("spell_link", foreground="#4a90e2", underline=True)
        self.text.tag_bind("spell_link", "<Enter>", lambda e: self.text.config(cursor="hand2"))
        self.text.tag_bind("spell_link", "<Leave>", lambda e: self.text.config(cursor=""))
        self.text.tag_bind("spell_link", "<Button-1>", self._on_spell_click)

    def _on_spell_click(self, event):
        idx = self.text.index(f"@{event.x},{event.y}")
        for t in self.text.tag_names(idx):
            if t.startswith("SPELL_TAG:"):
                if self.spell_callback: self.spell_callback(t.split(":", 1)[1])
                break

    def insert_divider(self):
        div = tk.Frame(self.text, height=3, bg="#d9ad6c", width=max(10, self.text.winfo_width() - 80))
        self.text.window_create(tk.END, window=div); self.text.insert(tk.END, "\n"); self.dividers.append(div)

    def clear_overlays(self):
        for btn in self.overlay_buttons: btn.destroy()
        self.overlay_buttons.clear()

    def add_top_buttons(self, m_dir, view_cb, edit_cb, back_cb=None):
        """Unified header control bar rendering to handle back buttons cleanly."""
        self.clear_overlays()
        x_offset = -140
        
        b_view = tk.Button(self.view_container, text="VIEW ARTWORK", bg="#d9ad6c", fg="black", font=("Georgia", 10, "bold"), command=lambda: view_cb(m_dir))
        b_view.place(relx=1.0, x=x_offset, y=10, width=120, height=30)
        self.overlay_buttons.append(b_view)
        
        x_offset -= 90
        b_edit = tk.Button(self.view_container, text="EDIT", bg="#8a8a8a", fg="white", font=("Georgia", 10, "bold"), command=lambda: edit_cb(m_dir))
        b_edit.place(relx=1.0, x=x_offset, y=10, width=80, height=30)
        self.overlay_buttons.append(b_edit)
        
        if back_cb:
            x_offset -= 90
            b_back = tk.Button(self.view_container, text="BACK", bg="#58180d", fg="white", font=("Georgia", 10, "bold"), command=back_cb)
            b_back.place(relx=1.0, x=x_offset, y=10, width=80, height=30)
            self.overlay_buttons.append(b_back)

    def add_custom_spell_buttons(self, s_data, edit_cb, del_cb):
        self.clear_overlays()
        b_del = tk.Button(self.view_container, text="DELETE", bg="#ff4d4d", fg="white", font=("Georgia", 10, "bold"), command=lambda: del_cb(s_data))
        b_del.place(relx=1.0, x=-90, y=10, width=70, height=30)
        b_edit = tk.Button(self.view_container, text="EDIT", bg="#8a8a8a", fg="white", font=("Georgia", 10, "bold"), command=lambda: edit_cb(s_data))
        b_edit.place(relx=1.0, x=-170, y=10, width=70, height=30)
        self.overlay_buttons.extend([b_del, b_edit])

    def render_edit_mode(self, data, monster_dir, loc_name, save_callback, cancel_callback):
        self.clear_overlays()
        self.view_container.pack_forget()
        self.edit_container.pack(fill=tk.BOTH, expand=True)
        for widget in self.edit_inner.winfo_children(): widget.destroy()

        self.edit_data = copy.deepcopy(data)
        self.edit_refs = {} 

        top_frame = tk.Frame(self.edit_inner, bg="#fdf1dc")
        top_frame.pack(fill=tk.X, pady=(0, 20))
        tk.Label(top_frame, text="EDIT MONSTER", font=self.header_font, fg="#58180d", bg="#fdf1dc").pack(side=tk.LEFT)
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

        ac_val = self.edit_data.get("ac", [10])
        if isinstance(ac_val, list) and len(ac_val) > 0: ac_val = ac_val[0]
        if isinstance(ac_val, dict): ac_val = ac_val.get("ac", 10)
        tk.Label(basic_frame, text="Armor Class:", bg="#fdf1dc", font=self.body_bold).grid(row=row, column=0, sticky="e", padx=5, pady=2)
        ac_entry = tk.Entry(basic_frame, width=50, font=self.body_font)
        ac_entry.insert(0, str(ac_val))
        ac_entry.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        self.edit_refs["ac"] = ac_entry
        row += 1

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

        self.arrays_frame = tk.Frame(self.edit_inner, bg="#fdf1dc")
        self.arrays_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.array_refs = {}
        self.sc_refs = []
        self.rebuild_sc_hooks = []
        self.dialogue_refs = []
        
        self.build_dialogues_section(loc_name)

        def sync_all_sc():
            for sc_dict_ref, hdr_text, ab_var, dc_var, hit_var, slots_entries in self.sc_refs:
                try:
                    sc_dict_ref["headerEntries"] = [hdr_text.get("1.0", "end-1c").strip()]
                    sc_dict_ref["ability"] = ab_var.get().lower()
                    dc_val = dc_var.get().strip()
                    sc_dict_ref["custom_dc"] = int(dc_val) if dc_val.isdigit() else 10
                    hit_val = hit_var.get().strip()
                    sc_dict_ref["custom_hit"] = int(hit_val) if hit_val.lstrip('+-').isdigit() else 2
                    if "spells" in sc_dict_ref:
                        for lvl, se in slots_entries.items():
                            val = se.get().strip()
                            if val.isdigit() and lvl in sc_dict_ref["spells"]:
                                sc_dict_ref["spells"][lvl]["slots"] = int(val)
                except Exception: pass

        def rebuild_all_sc():
            sync_all_sc()
            self.sc_refs.clear()
            for hook in self.rebuild_sc_hooks: hook()

        for sec_key, sec_title in [("trait", "Traits"), ("action", "Actions"), ("bonus", "Bonus Actions"), ("reaction", "Reactions"), ("legendary", "Legendary Actions")]:
            self.build_array_section(sec_key, sec_title, rebuild_all_sc, sync_all_sc)
            
        rebuild_all_sc()

    def build_dialogues_section(self, def_loc):
        sec = tk.Frame(self.arrays_frame, bg="#fdf1dc", pady=10); sec.pack(fill=tk.X)
        hdr = tk.Frame(sec, bg="#fdf1dc"); hdr.pack(fill=tk.X); tk.Label(hdr, text="Dialogues", font=self.header_font, fg="#7a200d", bg="#fdf1dc").pack(side=tk.LEFT)
        items_c = tk.Frame(sec, bg="#fdf1dc"); items_c.pack(fill=tk.X)
        
        def add_dialogue(d=None):
            d = d or {}
            f = tk.Frame(items_c, bg="#e2f0d9", bd=1, relief=tk.SOLID, pady=10, padx=10); f.pack(fill=tk.X, pady=5)
            t = tk.Frame(f, bg="#e2f0d9"); t.pack(fill=tk.X)
            ne = tk.Entry(t, width=30); ne.insert(0, d.get("name", f"Dialogue with {self.edit_refs['name'].get()}")); ne.pack(side=tk.LEFT, padx=5)
            le = tk.Entry(t, width=15); le.insert(0, d.get("location", def_loc)); le.pack(side=tk.LEFT, padx=5)
            te = tk.Entry(t, width=15); te.insert(0, d.get("time", "Act 1")); te.pack(side=tk.LEFT, padx=5)
            txt = tk.Text(f, height=4, font=self.body_font, wrap=tk.WORD); txt.insert("1.0", "\n".join(d.get("entries", []))); txt.pack(fill=tk.X)
            tk.Button(t, text="X", bg="#ff4d4d", command=lambda: (f.destroy(), self.dialogue_refs.remove((ne, le, te, txt)))).pack(side=tk.RIGHT)
            self.dialogue_refs.append((ne, le, te, txt))
        tk.Button(hdr, text="+ Add Dialogue", bg="#d9ad6c", command=add_dialogue).pack(side=tk.LEFT, padx=15)
        for dg in self.edit_data.get("dialogues", []): add_dialogue(dg)

    def build_array_section(self, key, title, rebuild_all_sc, sync_all_sc):
        sec_frame = tk.Frame(self.arrays_frame, bg="#fdf1dc", pady=10)
        sec_frame.pack(fill=tk.X)
        header_frame = tk.Frame(sec_frame, bg="#fdf1dc")
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text=title, font=self.header_font, fg="#7a200d", bg="#fdf1dc").pack(side=tk.LEFT)
        
        btn_frame = tk.Frame(header_frame, bg="#fdf1dc")
        btn_frame.pack(side=tk.LEFT, padx=15)
        tk.Button(btn_frame, text="+ Add Field", bg="#d9ad6c", font=("Arial", 10, "bold"), command=lambda: add_item()).pack(side=tk.LEFT, padx=5)

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
                        sync_all_sc()
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
                                row = tk.Frame(spells_frame, bg="#f5e6ce", pady=4)
                                row.pack(fill=tk.X)
                                top_r = tk.Frame(row, bg="#f5e6ce")
                                top_r.pack(fill=tk.X)
                                tk.Label(top_r, text=f"Level {lvl}:", font=self.body_bold, bg="#f5e6ce", width=8, anchor="w").pack(side=tk.LEFT)
                                if lvl > 0:
                                    tk.Label(top_r, text="Slots:", bg="#f5e6ce").pack(side=tk.LEFT)
                                    se = tk.Entry(top_r, width=3)
                                    se.insert(0, str(lvl_data.get("slots", 0)))
                                    se.pack(side=tk.LEFT, padx=(0,10))
                                    slots_entries[lvl_str] = se
                                
                                spells_list = lvl_data.setdefault("spells", [])
                                calculated_height = max(2, (len(spells_list) // 3) + 1)
                                txt = tk.Text(row, height=calculated_height, bg="#f5e6ce", font=("Arial", 11), bd=0, wrap=tk.WORD, padx=4, pady=6)
                                txt.pack(fill=tk.X, padx=10, pady=2, expand=True)
                                
                                for s_idx, s_name in enumerate(spells_list):
                                    sf = tk.Frame(txt, bg="#e8d5b7", padx=2, pady=2, bd=1, relief=tk.RAISED)
                                    tk.Label(sf, text=utils.clean_5etools_text(s_name), bg="#e8d5b7", font=("Arial", 10)).pack(side=tk.LEFT)
                                    def make_spell_remover(level=lvl_str, index=s_idx):
                                        sync_all_sc()
                                        spells_dict[level]["spells"].pop(index)
                                        if not spells_dict[level]["spells"]: del spells_dict[level]
                                        rebuild_all_sc()
                                    tk.Button(sf, text="x", bg="#ff4d4d", fg="white", font=("Arial", 8), padx=2, pady=0, command=make_spell_remover).pack(side=tk.LEFT)
                                    txt.window_create(tk.END, window=sf)
                                    txt.insert(tk.END, "  ")
                                txt.config(state=tk.DISABLED)
                    else:
                        if "will" in sc_dict:
                            row = tk.Frame(spells_frame, bg="#f5e6ce", pady=4)
                            row.pack(fill=tk.X)
                            tk.Label(row, text="At will:", font=self.body_bold, bg="#f5e6ce", width=8, anchor="w").pack(anchor="w")
                            w_list = sc_dict["will"]
                            calculated_height = max(2, (len(w_list) // 3) + 1)
                            txt = tk.Text(row, height=calculated_height, bg="#f5e6ce", font=("Arial", 11), bd=0, wrap=tk.WORD, padx=4, pady=6)
                            txt.pack(fill=tk.X, padx=10, pady=2, expand=True)
                            for s_idx, s_name in enumerate(w_list):
                                sf = tk.Frame(txt, bg="#e8d5b7", padx=2, pady=2, bd=1, relief=tk.RAISED)
                                tk.Label(sf, text=utils.clean_5etools_text(s_name), bg="#e8d5b7", font=("Arial", 10)).pack(side=tk.LEFT)
                                def make_will_remover(index=s_idx):
                                    sync_all_sc()
                                    sc_dict["will"].pop(index)
                                    if not sc_dict["will"]: del sc_dict["will"]
                                    rebuild_all_sc()
                                tk.Button(sf, text="x", bg="#ff4d4d", fg="white", font=("Arial", 8), padx=2, pady=0, command=make_will_remover).pack(side=tk.LEFT)
                                txt.window_create(tk.END, window=sf)
                                txt.insert(tk.END, "  ")
                            txt.config(state=tk.DISABLED)

                        daily_dict = sc_dict.setdefault("daily", {})
                        for freq, spells_list in daily_dict.items():
                            row = tk.Frame(spells_frame, bg="#f5e6ce", pady=4)
                            row.pack(fill=tk.X)
                            tk.Label(row, text=f"{freq}/day:", font=self.body_bold, bg="#f5e6ce", width=8, anchor="w").pack(anchor="w")
                            calculated_height = max(2, (len(spells_list) // 3) + 1)
                            txt = tk.Text(row, height=calculated_height, bg="#f5e6ce", font=("Arial", 11), bd=0, wrap=tk.WORD, padx=4, pady=6)
                            txt.pack(fill=tk.X, padx=10, pady=2, expand=True)
                            for s_idx, s_name in enumerate(spells_list):
                                sf = tk.Frame(txt, bg="#e8d5b7", padx=2, pady=2, bd=1, relief=tk.RAISED)
                                tk.Label(sf, text=utils.clean_5etools_text(s_name), bg="#e8d5b7", font=("Arial", 10)).pack(side=tk.LEFT)
                                def make_daily_remover(f=freq, index=s_idx):
                                    sync_all_sc()
                                    daily_dict[f].pop(index)
                                    if not daily_dict[f]: del daily_dict[f]
                                    rebuild_all_sc()
                                tk.Button(sf, text="x", bg="#ff4d4d", fg="white", font=("Arial", 8), padx=2, pady=0, command=make_daily_remover).pack(side=tk.LEFT)
                                txt.window_create(tk.END, window=sf)
                                txt.insert(tk.END, "  ")
                            txt.config(state=tk.DISABLED)

                    def add_spell_to_block(block_ref=sc_dict):
                        def on_spell_selected(spell_data, freq=None):
                            sync_all_sc()
                            spell_name = spell_data["name"].lower()
                            formatted_spell = f"{{@spell {spell_name}}}"
                            
                            def is_dupe(arr): return any(formatted_spell.lower() == e.lower() for e in arr)
                            
                            if not is_innate_block:
                                lvl = spell_data.get("level", 0)
                                sdict = block_ref.setdefault("spells", {})
                                ldict = sdict.setdefault(str(lvl), {"spells": []})
                                if not is_dupe(ldict["spells"]):
                                    ldict["spells"].append(formatted_spell)
                                if lvl > 0 and "slots" not in ldict: ldict["slots"] = 1
                                rebuild_all_sc()
                            else:
                                if freq == "will": 
                                    w_list = block_ref.setdefault("will", [])
                                    if not is_dupe(w_list): w_list.append(formatted_spell)
                                else: 
                                    d_list = block_ref.setdefault("daily", {}).setdefault(freq, [])
                                    if not is_dupe(d_list): d_list.append(formatted_spell)
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
            for tag, tag_name in utils.INV_ATTACK_TAGS.items():
                if entries_str.startswith(tag):
                    found_atk = tag_name
                    entries_str = entries_str[len(tag):].lstrip()
                    break
                    
            tk.Label(top, text="Attack Type:", bg="#f5e6ce", font=self.body_bold).pack(side=tk.LEFT, padx=(15, 2))
            atk_var = tk.StringVar(value=found_atk)
            atk_cb = ttk.Combobox(top, textvariable=atk_var, values=list(utils.ATTACK_TAGS.keys()), state="readonly", width=18)
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

    def _handle_gui_save(self, m_dir, save_cb):
        d = self.edit_data
        for k, en in self.edit_refs.items():
            if k in ["ac", "hp_formula"]: continue
            v = en.get().strip()
            d[k] = int(v) if k == "level" and v.isdigit() else json.loads(v) if v.startswith(("{", "[")) else v
        
        d["size"] = [utils.SIZE_MAP.get(self.size_var.get(), "M")]
        d["alignment"] = utils.ALIGN_MAP.get(self.align_var.get(), ["N"])
        d["ac"] = [int(self.edit_refs["ac"].get())] if self.edit_refs["ac"].get().isdigit() else [self.edit_refs["ac"].get()]
        hf = self.edit_refs["hp_formula"].get().strip()
        d["hp"] = {"average": utils.calculate_avg(hf) if hf else 10, "formula": hf}

        ns = {}
        for tv, ve, ce, _ in self.speed_refs:
            if tv.get() and ve.get(): ns[tv.get()] = {"number": int(ve.get()) if ve.get().isdigit() else ve.get(), "condition": ce.get()} if ce.get() else (int(ve.get()) if ve.get().isdigit() else ve.get())
        if self.can_hover_var.get(): ns["canHover"] = True
        if ns: d["speed"] = ns
        else: d.pop("speed", None)

        svs, mo = {}, {}
        for s, (v, m, sa) in self.edit_ability_refs.items():
            d[s] = int(v.get()) if v.get().isdigit() else 10
            if m.get(): mo[s] = m.get()
            if sa.get(): svs[s] = sa.get()
        if svs: d["save"] = svs
        else: d.pop("save", None)
        if mo: d["modOverride"] = mo
        else: d.pop("modOverride", None)

        for sc, h_t, ab_v, dc_v, ht_v, sl in self.sc_refs:
            sc["headerEntries"] = [h_t.get("1.0", "end-1c").strip()]; sc["ability"] = ab_v.get().lower()
            sc["custom_dc"] = int(dc_v.get()) if dc_v.get().isdigit() else 10
            sc["custom_hit"] = int(ht_v.get()) if ht_v.get().lstrip('+-').isdigit() else 2
            if "spells" in sc:
                for lvl, se in sl.items():
                    if se.get().isdigit(): sc["spells"][lvl]["slots"] = int(se.get())

        pd = []
        for ne, le, te, txt in self.dialogue_refs:
            if ne.get() or txt.get("1.0", "end-1c"): pd.append({"name": ne.get(), "location": le.get(), "time": te.get(), "entries": txt.get("1.0", "end-1c").strip().split("\n")})
        if pd: d["dialogues"] = pd
        else: d.pop("dialogues", None)

        for k, items in self.array_refs.items():
            pi = []
            for ne, av, txt, he, re_en, fe, te in items:
                desc = txt.get("1.0", "end-1c").strip().replace("@attack_hit", f"{{@hit {he.get()}}}").replace("@attack_reach", re_en.get())
                if fe.get():
                    dmg = f"{{@h}}{utils.calculate_avg(fe.get())} ({{@damage {fe.get()}}})" if 'd' in fe.get().lower() else f"{{@h}}{fe.get()}"
                    desc = desc.replace("{@attack_dmg}", f"{dmg} {te.get()} damage." if te.get() else f"{dmg} damage.").replace("..", ".")
                else: desc = desc.replace("{@attack_dmg}", "")
                if av.get() != "None": desc = f"{utils.ATTACK_TAGS[av.get()]} {desc}"
                if ne.get() or desc: pi.append({"name": ne.get(), "entries": json.loads(desc) if desc.startswith("[") else desc.split("\n")})
            if pi: d[k] = pi
            else: d.pop(k, None)

        save_cb(m_dir, d)

    def _cancel_edit(self, cancel_cb):
        self.edit_container.pack_forget(); self.view_container.pack(fill=tk.BOTH, expand=True); cancel_cb()

    def insert_text_with_links(self, text, base_tags):
        base_tags = (base_tags,) if isinstance(base_tags, str) else base_tags
        for part in re.split(r'(«SPELL:[^»]+»)', text):
            if part.startswith("«SPELL:") and part.endswith("»"):
                self.text.insert(tk.END, part[7:-1], base_tags + ("spell_link", f"SPELL_TAG:{part[7:-1].lower()}"))
            elif part: self.text.insert(tk.END, part, base_tags)

    def extract_entries(self, entries):
        import utils
        if not entries: return ""
        if isinstance(entries, str): return utils.clean_5etools_text(entries) + "\n"
        out = ""
        for entry in entries:
            if isinstance(entry, str): out += utils.clean_5etools_text(entry) + "\n"
            elif isinstance(entry, dict):
                if entry.get("type") == "list":
                    for item in entry.get("items", []): out += f"• {self.extract_entries([item]).strip()}\n"
                elif "entries" in entry:
                    if "name" in entry: out += f"{utils.clean_5etools_text(entry['name'])}. "
                    out += self.extract_entries(entry["entries"])
        return out

    def build_ability_scores(self, data):
        import utils
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
            if not mod: mod = utils.calculate_modifier(score)
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
        import utils
        if not spellcasting_list: return
        
        def get_ordinal(n):
            try:
                n = int(n)
                if 11 <= (n % 100) <= 13: return f"{n}th-level"
                return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}-level"
            except: return f"{n}-level"

        for sc in spellcasting_list:
            name = utils.clean_5etools_text(sc.get("name", "Spellcasting"))
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
                
            header_text = " ".join([utils.clean_5etools_text(h) for h in formatted_headers])
            self.insert_text_with_links(f"{header_text}\n", "body_indented")
            
            if "will" in sc:
                spells = ", ".join([utils.clean_5etools_text(s) for s in sc["will"]])
                self.insert_text_with_links(f"At will: {spells}\n", "body_indented")
            if "daily" in sc:
                for freq, spells_list in sc["daily"].items():
                    freq_num = freq[0]
                    each = " each" if freq.endswith("e") else ""
                    spells = ", ".join([utils.clean_5etools_text(s) for s in spells_list])
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
                        spells = ", ".join([utils.clean_5etools_text(s) for s in level_data.get("spells", [])])
                        self.insert_text_with_links(f"{lvl_str}: {spells}\n", "body_indented")
            self.text.insert(tk.END, "\n")

    def _render_section(self, entries_list):
        import utils
        if not entries_list: return
        for item in entries_list:
            name = item.get("name", "")
            if name: self.text.insert(tk.END, f"{utils.clean_5etools_text(name)}\n", "bold")
            content = self.extract_entries(item.get("entries", []))
            self.insert_text_with_links(content, "body_indented")
            self.text.insert(tk.END, "\n")

    def render_monster(self, data, back_cb=None):
        import utils
        self.clear_overlays()
        self.edit_container.pack_forget()
        self.view_container.pack(fill=tk.BOTH, expand=True)

        if back_cb:
            btn_back = tk.Button(self.view_container, text="BACK", bg="#58180d", fg="white", font=("Georgia", 10, "bold"), command=back_cb)
            btn_back.place(relx=1.0, x=-100, y=10, width=80, height=30)
            self.overlay_buttons.append(btn_back)

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
            # FIXED: Corrected self.clean_5etools_text to utils.clean_5etools_text
            if "from" in ac: ac_val += f" ({utils.clean_5etools_text(', '.join(ac['from']))})"
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
            self.text.insert(tk.END, f"{utils.parse_complex_list(data['resist'])}\n", "body")
        if "immune" in data:
            self.text.insert(tk.END, "Damage Immunities: ", "bold")
            self.text.insert(tk.END, f"{utils.parse_complex_list(data['immune'])}\n", "body")
        if "conditionImmune" in data:
            self.text.insert(tk.END, "Condition Immunities: ", "bold")
            self.text.insert(tk.END, f"{utils.parse_complex_list(data['conditionImmune'])}\n", "body")
        if "senses" in data:
            senses = utils.parse_complex_list(data["senses"])
            passive = data.get("passive", 10)
            self.text.insert(tk.END, "Senses: ", "bold")
            self.text.insert(tk.END, f"{senses}, passive Perception {passive}\n", "body")
        if "languages" in data:
            self.text.insert(tk.END, "Languages: ", "bold")
            self.text.insert(tk.END, f"{utils.parse_complex_list(data['languages'])}\n", "body")
        if "cr" in data:
            cr_val = data["cr"].get("cr", data["cr"]) if isinstance(data["cr"], dict) else data["cr"]
            self.text.insert(tk.END, "Challenge: ", "bold")
            self.text.insert(tk.END, f"{cr_val}\n", "body")

        self.insert_divider()

        global_level = data.get("level", 1)
        dialogues = data.get("dialogues", [])

        if dialogues:
            self.text.insert(tk.END, "DIALOGUES\n", "section_header")
            self.insert_divider()
            for d in dialogues:
                self.text.insert(tk.END, f"{utils.clean_5etools_text(d.get('name', 'Dialogue'))}\n", "bold")
                loc = d.get('location', '')
                if loc: self.text.insert(tk.END, f"{loc}\n", "body_italic")
                time_val = d.get('time', '')
                if time_val: self.text.insert(tk.END, f"{time_val}\n", "body_italic")
                self.insert_text_with_links(self.extract_entries(d.get("entries", [])), "body_indented")
                self.text.insert(tk.END, "\n")

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

    def render_spell(self, data, back_cb=None):
        import utils
        self.clear_overlays()
        self.edit_container.pack_forget()
        self.view_container.pack(fill=tk.BOTH, expand=True)

        if back_cb:
            btn_back = tk.Button(self.view_container, text="BACK", bg="#58180d", fg="white", font=("Georgia", 10, "bold"), command=back_cb)
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
            time_str += f", {utils.clean_5etools_text(time_data['condition'])}"
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

    def render_spell_edit_mode(self, data, save_cb, cancel_cb):
        self.clear_overlays(); self.view_container.pack_forget(); self.edit_container.pack(fill=tk.BOTH, expand=True)
        for w in self.edit_inner.winfo_children(): w.destroy()
        self.edit_data = copy.deepcopy(data); self.edit_refs = {}; self.original_spell_name = self.edit_data.get("name", "Unknown Spell")

        top = tk.Frame(self.edit_inner, bg="#fdf1dc"); top.pack(fill=tk.X, pady=(0, 20))
        tk.Label(top, text="EDIT SPELL", font=self.header_font, fg="#58180d", bg="#fdf1dc").pack(side=tk.LEFT)
        tk.Button(top, text="SAVE", bg="#4a90e2", fg="white", command=lambda: self._handle_spell_save(save_cb)).pack(side=tk.RIGHT, padx=5)
        tk.Button(top, text="CANCEL", bg="#58180d", fg="white", command=lambda: self._cancel_edit(cancel_cb)).pack(side=tk.RIGHT, padx=5)

        base_f = tk.Frame(self.edit_inner, bg="#fdf1dc"); base_f.pack(fill=tk.X, pady=10)
        for r, (lbl, key, w) in enumerate([("Name:", "name", 50), ("Source:", "source", 50), ("Page:", "page", 10), ("Level (0=Cantrip):", "level", 10)]):
            tk.Label(base_f, text=lbl, bg="#fdf1dc", font=self.body_bold).grid(row=r, column=0, sticky="e", padx=5, pady=2)
            en = tk.Entry(base_f, width=w, font=self.body_font); en.insert(0, str(self.edit_data.get(key, ""))); en.grid(row=r, column=1, sticky="w", padx=5, pady=2); self.edit_refs[key] = en

        r = 4; tk.Label(base_f, text="School:", bg="#fdf1dc", font=self.body_bold).grid(row=r, column=0, sticky="e", padx=5, pady=2)
        self.spell_school_var = tk.StringVar(value=utils.SCHOOL_MAP.get(self.edit_data.get("school", "A"), "Abjuration"))
        ttk.Combobox(base_f, textvariable=self.spell_school_var, values=list(utils.SCHOOL_MAP.values()), state="readonly", width=15).grid(row=r, column=1, sticky="w", padx=5, pady=2); r+=1

        tm = self.edit_data.get("time", [{}])[0]; tk.Label(base_f, text="Cast Time:", bg="#fdf1dc", font=self.body_bold).grid(row=r, column=0, sticky="e", padx=5, pady=2)
        tf = tk.Frame(base_f, bg="#fdf1dc"); tf.grid(row=r, column=1, sticky="w", padx=5, pady=2); r+=1
        self.t_num_var = tk.StringVar(value=str(tm.get("number", 1))); tk.Entry(tf, textvariable=self.t_num_var, width=5).pack(side=tk.LEFT)
        self.t_unit_var = tk.StringVar(value=tm.get("unit", "action")); ttk.Combobox(tf, textvariable=self.t_unit_var, values=["action", "bonus", "reaction", "minute", "hour"], state="readonly", width=10).pack(side=tk.LEFT, padx=5)
        self.t_cond_var = tk.StringVar(value=tm.get("condition", "")); tk.Entry(tf, textvariable=self.t_cond_var, width=25).pack(side=tk.LEFT, padx=5)

        rg = self.edit_data.get("range", {}); dst = rg.get("distance", {}); tk.Label(base_f, text="Range:", bg="#fdf1dc", font=self.body_bold).grid(row=r, column=0, sticky="e", padx=5, pady=2)
        rf = tk.Frame(base_f, bg="#fdf1dc"); rf.grid(row=r, column=1, sticky="w", padx=5, pady=2); r+=1
        self.r_type_var = tk.StringVar(value=rg.get("type", "point")); ttk.Combobox(rf, textvariable=self.r_type_var, values=["point", "cone", "cube", "cylinder", "line", "sphere", "hemisphere", "radius"], state="readonly", width=10).pack(side=tk.LEFT)
        self.r_amt_var = tk.StringVar(value=str(dst.get("amount", ""))); tk.Entry(rf, textvariable=self.r_amt_var, width=5).pack(side=tk.LEFT, padx=2)
        self.r_unit_var = tk.StringVar(value=dst.get("type", "feet")); ttk.Combobox(rf, textvariable=self.r_unit_var, values=["feet", "miles", "touch", "self", "sight", "unlimited"], state="readonly", width=8).pack(side=tk.LEFT, padx=5)

        cp = self.edit_data.get("components", {}); tk.Label(base_f, text="Components:", bg="#fdf1dc", font=self.body_bold).grid(row=r, column=0, sticky="e", padx=5, pady=2)
        cf = tk.Frame(base_f, bg="#fdf1dc"); cf.grid(row=r, column=1, sticky="w", padx=5, pady=2); r+=1
        self.c_v_var = tk.BooleanVar(value="v" in cp); tk.Checkbutton(cf, text="V", variable=self.c_v_var, bg="#fdf1dc").pack(side=tk.LEFT)
        self.c_s_var = tk.BooleanVar(value="s" in cp); tk.Checkbutton(cf, text="S", variable=self.c_s_var, bg="#fdf1dc").pack(side=tk.LEFT)
        self.c_m_var = tk.StringVar(value=cp["m"].get("text", cp["m"].get("item","")) if isinstance(cp.get("m"), dict) else cp.get("m","")); tk.Entry(cf, textvariable=self.c_m_var, width=30).pack(side=tk.LEFT, padx=5)

        dr = self.edit_data.get("duration", [{}])[0]; tk.Label(base_f, text="Duration:", bg="#fdf1dc", font=self.body_bold).grid(row=r, column=0, sticky="e", padx=5, pady=2)
        df = tk.Frame(base_f, bg="#fdf1dc"); df.grid(row=r, column=1, sticky="w", padx=5, pady=2)
        self.d_type_var = tk.StringVar(value=dr.get("type", "timed")); ttk.Combobox(df, textvariable=self.d_type_var, values=["timed", "instant", "permanent", "special"], state="readonly", width=10).pack(side=tk.LEFT)
        self.d_amt_var = tk.StringVar(value=str(dr.get("duration", {}).get("amount", "1"))); tk.Entry(df, textvariable=self.d_amt_var, width=5).pack(side=tk.LEFT, padx=2)
        self.d_unit_var = tk.StringVar(value=dr.get("duration", {}).get("type", "minute")); ttk.Combobox(df, textvariable=self.d_unit_var, values=["round", "minute", "hour", "day"], state="readonly", width=8).pack(side=tk.LEFT, padx=5)
        self.d_conc_var = tk.BooleanVar(value=dr.get("concentration", False)); tk.Checkbutton(df, text="Concentration", variable=self.d_conc_var, bg="#fdf1dc").pack(side=tk.LEFT)

        tk.Label(self.edit_inner, text="Description:", bg="#fdf1dc", font=self.body_bold).pack(anchor="w", padx=5)
        self.spell_desc_text = tk.Text(self.edit_inner, height=15, font=self.body_font, wrap=tk.WORD)
        self.spell_desc_text.insert("1.0", "\n".join([json.dumps(e) if isinstance(e, dict) else e for e in self.edit_data.get("entries", [])]) if isinstance(self.edit_data.get("entries"), list) else str(self.edit_data.get("entries","")))
        self.spell_desc_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _handle_spell_save(self, save_cb):
        d = self.edit_data; d["name"] = self.edit_refs["name"].get().strip(); d["source"] = self.edit_refs["source"].get().strip()
        d["level"] = int(self.edit_refs["level"].get().strip()) if self.edit_refs["level"].get().strip().isdigit() else 0
        if self.edit_refs["page"].get().strip().isdigit(): d["page"] = int(self.edit_refs["page"].get().strip())
        
        d["school"] = utils.INV_SCHOOL_MAP.get(self.spell_school_var.get(), "A")
        td = {"number": int(self.t_num_var.get().strip()) if self.t_num_var.get().strip().isdigit() else 1, "unit": self.t_unit_var.get().strip()}
        if self.t_cond_var.get().strip(): td["condition"] = self.t_cond_var.get().strip()
        d["time"] = [td]
        
        rd = {"type": self.r_unit_var.get().strip()}
        if self.r_amt_var.get().strip().isdigit(): rd["amount"] = int(self.r_amt_var.get().strip())
        d["range"] = {"type": self.r_type_var.get().strip(), "distance": rd}
        
        cmps = {}
        if self.c_v_var.get(): cmps["v"] = True
        if self.c_s_var.get(): cmps["s"] = True
        if self.c_m_var.get().strip(): cmps["m"] = self.c_m_var.get().strip()
        d["components"] = cmps
        
        dd = {"type": self.d_type_var.get().strip()}
        if self.d_conc_var.get(): dd["concentration"] = True
        if self.d_type_var.get().strip() == "timed": dd["duration"] = {"type": self.d_unit_var.get().strip(), "amount": int(self.d_amt_var.get().strip()) if self.d_amt_var.get().strip().isdigit() else 1}
        d["duration"] = [dd]
        d["entries"] = [json.loads(line) if line.startswith(("{", "[")) else line for line in self.spell_desc_text.get("1.0", "end-1c").strip().split("\n") if line]
        
        save_cb(self.original_spell_name, d)

class CombatRenderer(tk.Frame):
    def __init__(self, parent, open_statblock_cb, save_cb, add_bestiary_cb, add_camp_mon_cb, add_camp_npc_cb, cancel_cb, *args, **kwargs):
        super().__init__(parent, bg="#fdf1dc", *args, **kwargs)
        self.open_statblock_cb = open_statblock_cb
        self.save_cb = save_cb
        self.add_bestiary_cb = add_bestiary_cb
        self.add_camp_mon_cb = add_camp_mon_cb
        self.add_camp_npc_cb = add_camp_npc_cb
        self.cancel_cb = cancel_cb

        self.header_font = font.Font(family="Times", size=18, weight="bold") 
        self.body_font = font.Font(family="Times", size=13)
        self.body_bold = font.Font(family="Times", size=13, weight="bold")
        self.body_italic = font.Font(family="Times", size=13, slant="italic")
        
        self.main_canvas = tk.Canvas(self, bg="#fdf1dc", highlightthickness=0)
        self.main_scroll = ttk.Scrollbar(self, orient="vertical", command=self.main_canvas.yview)
        self.main_inner = tk.Frame(self.main_canvas, bg="#fdf1dc", padx=40, pady=20)
        self.main_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.main_window = self.main_canvas.create_window((0, 0), window=self.main_inner, anchor="nw")
        
        self.main_inner.bind("<Configure>", lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))
        self.main_canvas.bind("<Configure>", lambda e: self.main_canvas.itemconfig(self.main_window, width=e.width))
        self.main_canvas.configure(yscrollcommand=self.main_scroll.set)
        
        self.participant_rows = []

    def render_combat(self, combat_data, combat_dir):
        self.combat_dir = combat_dir
        if not hasattr(self, 'original_data') or self.combat_dir != combat_dir:
            self.original_data = copy.deepcopy(combat_data)
            self.current_data = copy.deepcopy(combat_data)
            
        self._redraw_workspace()

    def _sync_top_metadata(self):
        if hasattr(self, 'name_txt'):
            self.current_data["name"] = self.name_txt.get("1.0", "end-1c").strip()
            self.current_data["location"] = self.loc_txt.get("1.0", "end-1c").strip()
            self.current_data["time"] = self.time_txt.get("1.0", "end-1c").strip()
            self.current_data["description"] = self.desc_txt.get("1.0", "end-1c").strip()
            self.current_data["over"] = self.over_var.get()
            self.current_data["outcome"] = self.out_txt.get("1.0", "end-1c").strip()

    def _sync_all_rows(self):
        self._sync_top_metadata()
        for r in self.participant_rows:
            p = r["data"]
            p["name"] = r["name_var"].get().strip()
            p["side"] = r["side_var"].get()
            p["dead"] = r["dead_var"].get()
            
            i_val = r["init_en"].get().strip()
            if i_val == "" or not i_val.lstrip('-').isdigit():
                p["init"] = 0
            else:
                p["init"] = int(i_val)
                
            h_val = r["hp_en"].get().strip()
            p["hp"] = int(h_val) if h_val.lstrip('-').isdigit() else 0

    def _realtime_sort(self, event=None):
        """Re-orders combat panels dynamically using pack order sorting to maintain keyboard input focus."""
        # Capture the widget that currently has active focus before altering layout structure
        focused_widget = self.focus_get()
        
        self._sync_all_rows()
        
        self.participant_rows.sort(key=lambda r: r["data"].get("init", 0), reverse=True)
        self.current_data["participants"] = [r["data"] for r in self.participant_rows]
        
        for r in self.participant_rows:
            r["frame"].pack_forget()
        for r in self.participant_rows:
            r["frame"].pack(fill=tk.X, pady=4)
            
        # FIXED: Explicitly restore focus state back to the original entry field to allow seamless typing
        if focused_widget:
            try: focused_widget.focus_set()
            except: pass

    def _redraw_workspace(self):
        for w in self.main_inner.winfo_children(): w.destroy()
        self.participant_rows.clear()

        top_frame = tk.Frame(self.main_inner, bg="#fdf1dc")
        top_frame.pack(fill=tk.X, pady=(0, 20))
        tk.Label(top_frame, text="LIVE COMBAT WORKSPACE", font=self.header_font, fg="#58180d", bg="#fdf1dc").pack(side=tk.LEFT)
        
        def save_action():
            self._sync_all_rows()
            self.current_data["participants"].sort(key=lambda x: x.get("init", 0), reverse=True)
            self.original_data = copy.deepcopy(self.current_data)
            self.save_cb(self.combat_dir, self.current_data)
            self._redraw_workspace()

        def cancel_action():
            self.current_data = copy.deepcopy(self.original_data)
            self.cancel_cb()

        tk.Button(top_frame, text="SAVE", bg="#4a90e2", fg="white", font=("Georgia", 10, "bold"), command=save_action).pack(side=tk.RIGHT, padx=5)
        tk.Button(top_frame, text="CANCEL", bg="#58180d", fg="white", font=("Georgia", 10, "bold"), command=cancel_action).pack(side=tk.RIGHT, padx=5)

        fields_f = tk.Frame(self.main_inner, bg="#fdf1dc")
        fields_f.pack(fill=tk.X, pady=10)
        fields_f.grid_columnconfigure(1, weight=1)

        tk.Label(fields_f, text="Name:", bg="#fdf1dc", font=self.body_bold).grid(row=0, column=0, sticky="ne", pady=4)
        self.name_txt = tk.Text(fields_f, width=40, height=1, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
        self.name_txt.insert("1.0", self.current_data.get("name", ""))
        self.name_txt.grid(row=0, column=1, sticky="w", padx=10, pady=4)

        tk.Label(fields_f, text="Location:", bg="#fdf1dc", font=self.body_bold).grid(row=1, column=0, sticky="ne", pady=4)
        self.loc_txt = tk.Text(fields_f, width=40, height=1, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
        self.loc_txt.insert("1.0", self.current_data.get("location", ""))
        self.loc_txt.grid(row=1, column=1, sticky="w", padx=10, pady=4)

        tk.Label(fields_f, text="Time:", bg="#fdf1dc", font=self.body_bold).grid(row=2, column=0, sticky="ne", pady=4)
        self.time_txt = tk.Text(fields_f, width=40, height=1, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
        self.time_txt.insert("1.0", self.current_data.get("time", ""))
        self.time_txt.grid(row=2, column=1, sticky="w", padx=10, pady=4)

        tk.Label(fields_f, text="Description:", bg="#fdf1dc", font=self.body_bold).grid(row=3, column=0, sticky="ne", pady=4)
        self.desc_txt = tk.Text(fields_f, width=60, height=2, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
        self.desc_txt.insert("1.0", self.current_data.get("description", ""))
        self.desc_txt.grid(row=3, column=1, sticky="w", padx=10, pady=4)

        tk.Label(fields_f, text="Over:", bg="#fdf1dc", font=self.body_bold).grid(row=4, column=0, sticky="ne", pady=4)
        self.over_var = tk.StringVar(value=self.current_data.get("over", "No"))
        ttk.Combobox(fields_f, textvariable=self.over_var, values=["Yes", "No"], state="readonly", width=10).grid(row=4, column=1, sticky="w", padx=10, pady=4)

        tk.Label(fields_f, text="Outcome:", bg="#fdf1dc", font=self.body_bold).grid(row=5, column=0, sticky="ne", pady=4)
        self.out_txt = tk.Text(fields_f, width=60, height=2, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
        self.out_txt.insert("1.0", self.current_data.get("outcome", ""))
        self.out_txt.grid(row=5, column=1, sticky="w", padx=10, pady=4)

        tk.Label(self.main_inner, text="COMBATANTS", font=self.header_font, fg="#58180d", bg="#fdf1dc").pack(anchor="w", pady=(20, 5))
        btn_f = tk.Frame(self.main_inner, bg="#fdf1dc")
        btn_f.pack(fill=tk.X, pady=5)

        def append_combatant(target_name, folder_type, hp_val):
            self._sync_all_rows()
            new_fighter = {
                "name": target_name, "target": target_name, "type": folder_type,
                "side": "Enemy" if folder_type == "Monsters" else "Neutral",
                "init": 0, "hp": hp_val, "max_hp": hp_val, "dead": False
            }
            self.current_data.setdefault("participants", []).append(new_fighter)
            self.current_data["participants"].sort(key=lambda x: x.get("init", 0), reverse=True)
            self._redraw_workspace()

        tk.Button(btn_f, text="+ New Monster", bg="#d9ad6c", fg="black", font=("Arial", 9, "bold"), command=lambda: self.add_bestiary_cb(self.combat_dir, append_combatant)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_f, text="+ Add Existing Monster", bg="#d9ad6c", fg="black", font=("Arial", 9, "bold"), command=lambda: self.add_camp_mon_cb(append_combatant)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_f, text="+ Add NPC", bg="#d9ad6c", fg="black", font=("Arial", 9, "bold"), command=lambda: self.add_camp_npc_cb(append_combatant)).pack(side=tk.LEFT, padx=5)

        self.parts_frame = tk.Frame(self.main_inner, bg="#fdf1dc")
        self.parts_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        for p_data in self.current_data.get("participants", []):
            self._build_live_participant_panel(p_data)

    def _build_live_participant_panel(self, p):
        def get_panel_color(side, is_dead):
            if is_dead: return "#333333"
            return {"Ally": "#4a90e2", "Enemy": "#ff4d4d", "Neutral": "#8a8a8a"}.get(side, "#8a8a8a")

        initial_color = get_panel_color(p.get("side", "Neutral"), p.get("dead", False))
        panel = tk.Frame(self.parts_frame, bg=initial_color, pady=10, padx=15, bd=1, relief=tk.SOLID)
        panel.pack(fill=tk.X, pady=4)

        name_var = tk.StringVar(value=p["name"])
        name_en = tk.Entry(panel, textvariable=name_var, font=("Georgia", 12, "bold"), width=18, bg="white", fg="black", insertbackground="black")
        name_en.pack(side=tk.LEFT, padx=5)

        btn_stats = tk.Button(panel, text="STATS", bg="#fae6c5", fg="black", font=("Arial", 9, "bold"), command=lambda: (self._sync_all_rows(), self.open_statblock_cb(p["target"], p["type"])))
        btn_stats.pack(side=tk.LEFT, padx=10)

        d_var = tk.BooleanVar(value=p.get("dead", False))
        s_var = tk.StringVar(value=p.get("side", "Neutral"))

        side_cb = ttk.Combobox(panel, textvariable=s_var, values=["Ally", "Enemy", "Neutral"], state="readonly", width=10)
        side_cb.pack(side=tk.LEFT, padx=10)

        def update_colors(event=None):
            new_color = get_panel_color(s_var.get(), d_var.get())
            panel.configure(bg=new_color)
            for child in panel.winfo_children():
                if isinstance(child, (tk.Label, tk.Checkbutton)):
                    child.configure(bg=new_color, activebackground=new_color)

        side_cb.bind("<<ComboboxSelected>>", lambda e: (update_colors(), self._realtime_sort()))

        def delete_combatant():
            self._sync_all_rows()
            self.current_data["participants"].remove(p)
            self.current_data["participants"].sort(key=lambda x: x.get("init", 0), reverse=True)
            self._redraw_workspace()

        tk.Button(panel, text="DELETE", bg="#d9534f", fg="white", font=("Arial", 8, "bold"), command=delete_combatant).pack(side=tk.RIGHT, padx=5)

        lbl_max = tk.Label(panel, text=f"/ {p.get('max_hp', 10)}", bg=initial_color, fg="white", font=("Arial", 11, "bold"))
        lbl_max.pack(side=tk.RIGHT)
        hp_en = tk.Entry(panel, width=4, font=("Arial", 11, "bold"), justify="center")
        hp_en.insert(0, str(p.get("hp", 10)))
        hp_en.pack(side=tk.RIGHT, padx=5)
        lbl_hp = tk.Label(panel, text="HP:", bg=initial_color, fg="white", font=("Arial", 11, "bold"))
        lbl_hp.pack(side=tk.RIGHT, padx=2)

        init_en = tk.Entry(panel, width=3, font=("Arial", 11, "bold"), justify="center")
        init_en.insert(0, str(p.get("init", 0)))
        init_en.pack(side=tk.RIGHT, padx=15)
        lbl_init = tk.Label(panel, text="Init:", bg=initial_color, fg="white", font=("Arial", 11, "bold"))
        lbl_init.pack(side=tk.RIGHT)

        init_en.bind("<KeyRelease>", self._realtime_sort)

        tk.Checkbutton(panel, text="DEAD", variable=d_var, bg=initial_color, fg="white", selectcolor="#222", activebackground=initial_color, activeforeground="white", font=("Arial", 9, "bold"), command=update_colors).pack(side=tk.RIGHT, padx=10)

        row_info = {
            "data": p, "frame": panel, "name_var": name_var, "side_var": s_var,
            "init_en": init_en, "hp_en": hp_en, "dead_var": d_var,
            "lbl_init": lbl_init, "lbl_hp": lbl_hp, "lbl_max": lbl_max
        }
        self.participant_rows.append(row_info)