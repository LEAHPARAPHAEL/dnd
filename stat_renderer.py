import tkinter as tk
from tkinter import font, ttk
import re

class StatBlockRenderer(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, bg="#fdf1dc", *args, **kwargs) 
        
        self.v_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.text = tk.Text(self, bg="#fdf1dc", wrap=tk.WORD, borderwidth=0, 
                            highlightthickness=0, padx=40, pady=40, 
                            yscrollcommand=self.v_scroll.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.v_scroll.config(command=self.text.yview)
        
        self.dividers = []
        self.text.bind("<Configure>", self.on_text_resize)
        
        self._setup_fonts_and_tags()

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

    def on_text_resize(self, event):
        new_width = max(10, event.width - 80)
        for div in self.dividers:
            div.configure(width=new_width)

    def insert_divider(self):
        current_width = max(10, self.text.winfo_width() - 80)
        divider = tk.Frame(self.text, height=3, bg="#d9ad6c", width=current_width)
        self.text.window_create(tk.END, window=divider)
        self.text.insert(tk.END, "\n")
        self.dividers.append(divider)

    def clean_5etools_text(self, text):
        replacements = {
            r'{@atk mw}': 'Melee Weapon Attack:',
            r'{@atk rw}': 'Ranged Weapon Attack:',
            r'{@atk mw,rw}': 'Melee or Ranged Weapon Attack:',
            r'{@atk ms}': 'Melee Spell Attack:',
            r'{@atk rs}': 'Ranged Spell Attack:',
            r'{@h}': 'Hit: ',
            r'{@hit (\d+)}': r'+\1',
            r'{@damage (.*?)}': r'\1',
            r'{@dc (\d+)}': r'DC \1',
            r'{@condition (.*?)(?:\|.*?)?}': r'\1',
            r'{@variantrule (.*?)(?:\|.*?)?}': r'\1',
            r'{@recharge\s*(\d*)}': lambda m: f"(Recharge {m.group(1)}-6)" if m.group(1) else "(Recharge 6)"
        }
        for pattern, repl in replacements.items():
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
            
        def save_replacer(match): return f"{match.group(1).capitalize()} Saving Throw:"
        text = re.sub(r'{@actSave (\w+)}', save_replacer, text)
        
        text = re.sub(r'{@\w+ ([^|}]+)[^}]*}', r'\1', text)
        return text

    def extract_entries(self, entries):
        if not entries: return ""
        if isinstance(entries, str): return self.clean_5etools_text(entries) + "\n"
        
        out = ""
        for entry in entries:
            if isinstance(entry, str):
                out += self.clean_5etools_text(entry) + "\n"
            elif isinstance(entry, dict):
                if entry.get("type") == "list":
                    for item in entry.get("items", []):
                        out += f"• {self.extract_entries([item]).strip()}\n"
                elif "entries" in entry:
                    if "name" in entry:
                        out += f"{self.clean_5etools_text(entry['name'])}. "
                    out += self.extract_entries(entry["entries"])
        return out

    def parse_complex_list(self, data_list):
        if not data_list: return ""
        if isinstance(data_list, str): return data_list
            
        out = []
        for item in data_list:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                if "special" in item:
                    out.append(str(item["special"]))
                else:
                    keys = [k for k in item.keys() if k not in ["note", "preNote", "cond"]]
                    if keys:
                        main_val = item[keys[0]]
                        main_str = ", ".join(main_val) if isinstance(main_val, list) else str(main_val)
                        if "note" in item:
                            main_str += f" ({item['note']})"
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
            mod = self.calculate_modifier(score)
            save_val = data.get("save", {}).get(stat, mod) 
            
            if isinstance(save_val, int) or (isinstance(save_val, str) and save_val.lstrip('-').isdigit()):
                save_val = f"+{save_val}" if int(save_val) >= 0 else str(save_val)

            tk.Label(grid, text=stat.upper(), font=self.body_bold, bg="#fdf1dc", fg="#58180d").grid(row=0, column=col)
            tk.Label(grid, text=str(score), font=self.body_font, bg="#fdf1dc").grid(row=1, column=col)
            tk.Label(grid, text=str(mod), font=self.body_font, bg="#fdf1dc").grid(row=2, column=col)
            tk.Label(grid, text=str(save_val), font=self.body_font, bg="#fdf1dc").grid(row=3, column=col)

        self.text.window_create(tk.END, window=grid)
        self.text.insert(tk.END, "\n")

    def _render_spellcasting(self, spellcasting_list):
        if not spellcasting_list: return
        
        for sc in spellcasting_list:
            name = self.clean_5etools_text(sc.get("name", "Spellcasting"))
            self.text.insert(tk.END, f"{name}\n", "bold") # Changed to match trait formatting
            
            headers = sc.get("headerEntries", [])
            header_text = " ".join([self.clean_5etools_text(h) for h in headers])
            self.text.insert(tk.END, f"{header_text}\n", "body_indented")
            
            if "will" in sc:
                spells = ", ".join([self.clean_5etools_text(s) for s in sc["will"]])
                self.text.insert(tk.END, f"At will: {spells}\n", "body_indented")
                
            if "daily" in sc:
                for freq, spells_list in sc["daily"].items():
                    freq_num = freq[0]
                    each = " each" if freq.endswith("e") else ""
                    spells = ", ".join([self.clean_5etools_text(s) for s in spells_list])
                    self.text.insert(tk.END, f"{freq_num}/day{each}: {spells}\n", "body_indented")
                    
            if "spells" in sc:
                levels = {"0": "Cantrips (at will)", "1": "1st level", "2": "2nd level", "3": "3rd level", 
                          "4": "4th level", "5": "5th level", "6": "6th level", "7": "7th level", 
                          "8": "8th level", "9": "9th level"}
                for level in range(10):
                    str_level = str(level)
                    if str_level in sc["spells"]:
                        level_data = sc["spells"][str_level]
                        lvl_str = levels.get(str_level, f"{level} level")
                        slots = level_data.get("slots")
                        if slots:
                            lvl_str += f" ({slots} slots)"
                        spells = ", ".join([self.clean_5etools_text(s) for s in level_data.get("spells", [])])
                        self.text.insert(tk.END, f"{lvl_str}: {spells}\n", "body_indented")
            
            self.text.insert(tk.END, "\n")

    def add_portrait_button(self, monster_dir, callback):
        """Adds a button to the top right to view artwork using absolute placement."""
        btn = tk.Button(self, text="VIEW ARTWORK", bg="#d9ad6c", fg="black", 
                        font=("Georgia", 10, "bold"), 
                        command=lambda: callback(monster_dir))
        
        # Place the button at the top-right (x=relative to right, y=offset from top)
        # We place it 50px from the right and 10px from the top
        btn.place(relx=1.0, x=-140, y=10, width=120, height=30)

    def render_monster(self, data):
        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.dividers.clear()

        # HEADER
        self.text.insert(tk.END, data.get("name", "Unknown Monster") + "\n", "title")
        
        size_map = {"T": "Tiny", "S": "Small", "M": "Medium", "L": "Large", "H": "Huge", "G": "Gargantuan"}
        size = size_map.get(data.get("size", ["M"])[0], "Medium")
        
        raw_type = data.get("type", "unknown")
        if isinstance(raw_type, dict):
            base_type = raw_type.get("type", "unknown")
            tags = raw_type.get("tags", [])
            m_type = f"{base_type} ({', '.join(tags)})" if tags else base_type
        else:
            m_type = str(raw_type)
        m_type = m_type.title()
        
        align_raw = data.get("alignment", ["N"])
        prefix = data.get("alignmentPrefix", "")
        
        if len(align_raw) > 0 and isinstance(align_raw[0], dict) and "special" in align_raw[0]:
            alignment = align_raw[0]["special"]
        else:
            align_map = {"L": "Lawful", "N": "Neutral", "C": "Chaotic", "G": "Good", "E": "Evil", "U": "Unaligned", "A": "Any"}
            clean_align = [a for a in align_raw if isinstance(a, str)]
            alignment = " ".join([align_map.get(a, a) for a in clean_align])
            
        full_alignment = f"{prefix}{alignment}"
        
        self.text.insert(tk.END, f"{size} {m_type}, {full_alignment}\n", "subtitle")
        self.insert_divider()

        # BASIC STATS 
        ac = data.get("ac", [10])[0]
        if isinstance(ac, dict):
            ac_val = str(ac.get("ac", ""))
            if "from" in ac:
                ac_val += f" ({self.clean_5etools_text(', '.join(ac['from']))})"
        else:
            ac_val = str(ac)
            
        self.text.insert(tk.END, "Armor Class: ", "bold")
        self.text.insert(tk.END, f"{ac_val}\n", "body")
        
        hp_data = data.get("hp", {})
        self.text.insert(tk.END, "Hit Points: ", "bold")
        self.text.insert(tk.END, f"{hp_data.get('average', 10)} ({hp_data.get('formula', '')})\n", "body")
        
        speed_data = data.get("speed", {})
        speeds = []
        for k, v in speed_data.items():
            if isinstance(v, bool): continue
            if isinstance(v, dict):
                val = f"{v.get('number', '')} ft. {v.get('condition', '')}".strip()
            else:
                val = f"{v} ft."
            speeds.append(val if k == "walk" else f"{k} {val}")
            
        self.text.insert(tk.END, "Speed: ", "bold")
        self.text.insert(tk.END, f"{', '.join(speeds)}\n", "body")
        self.insert_divider()

        # ABILITIES 
        self.build_ability_scores(data)
        self.insert_divider()

        # PROFICIENCIES
        if "skill" in data:
            skills_list = []
            for k, v in data["skill"].items():
                if k == "other":
                    for other_block in v:
                        if "oneOf" in other_block:
                            options = ", ".join([f"{ok.capitalize()} {ov}" for ok, ov in other_block["oneOf"].items()])
                            skills_list.append(f"plus one of the following: {options}")
                else:
                    skills_list.append(f"{k.capitalize()} {v}")
                    
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

        # PREPARE SPELLCASTING DATA
        sc_data = data.get("spellcasting", [])
        sc_traits = [sc for sc in sc_data if sc.get("displayAs", "trait") == "trait"]
        sc_actions = [sc for sc in sc_data if sc.get("displayAs") == "action"]
        sc_bonus = [sc for sc in sc_data if sc.get("displayAs") == "bonus"]
        sc_reactions = [sc for sc in sc_data if sc.get("displayAs") == "reaction"]

        # TRAITS
        if data.get("trait") or sc_traits:
            self.text.insert(tk.END, "TRAITS\n", "section_header")
            self.insert_divider()
            if sc_traits:
                self._render_spellcasting(sc_traits)
            if data.get("trait"):
                self._render_section(data["trait"])
                
        # ACTIONS
        if data.get("action") or sc_actions:
            self.text.insert(tk.END, "ACTIONS\n", "section_header")
            self.insert_divider()
            if sc_actions:
                self._render_spellcasting(sc_actions)
            if data.get("action"):
                self._render_section(data["action"])
                
        # BONUS ACTIONS
        if data.get("bonus") or sc_bonus:
            self.text.insert(tk.END, "BONUS ACTIONS\n", "section_header")
            self.insert_divider()
            if sc_bonus:
                self._render_spellcasting(sc_bonus)
            if data.get("bonus"):
                self._render_section(data["bonus"])
                
        # REACTIONS
        if data.get("reaction") or sc_reactions:
            self.text.insert(tk.END, "REACTIONS\n", "section_header")
            self.insert_divider()
            if sc_reactions:
                self._render_spellcasting(sc_reactions)
            if data.get("reaction"):
                self._render_section(data["reaction"])
        
        # LEGENDARY ACTIONS
        if "legendary" in data:
            self.text.insert(tk.END, "LEGENDARY ACTIONS\n", "section_header")
            self.insert_divider()
            self._render_section(data["legendary"])

        self.text.config(state=tk.DISABLED)

    def _render_section(self, entries_list):
        if not entries_list: return
        
        for item in entries_list:
            name = item.get("name", "")
            if name:
                self.text.insert(tk.END, f"{self.clean_5etools_text(name)}\n", "bold")
                
            content = self.extract_entries(item.get("entries", []))
            self.text.insert(tk.END, content, "body_indented")
            self.text.insert(tk.END, "\n")