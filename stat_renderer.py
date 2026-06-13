import tkinter as tk
from tkinter import font, ttk, messagebox, simpledialog
import re
import json
import copy
import utils.preprocess as preprocess
from dialogs import SpellSearchDialog, DepthsSelectionDialog, TerrainSettingsDialog, NodeIconSelectorDialog
from pathlib import Path
from PIL import Image, ImageTk
import shutil
from dialogs import EntitySelectionDialog


# ==================== CONDITIONS DATABASE ====================
CONDITIONS_DB = {
    "blinded": "A blinded creature can’t see and automatically fails any ability check that requires sight.\nAttack rolls against the creature have advantage, and the creature’s attack rolls have disadvantage.",
    "charmed": "A charmed creature can’t attack the charmer or target the charmer with harmful abilities or magical effects.\nThe charmer has advantage on any ability check to interact socially with the creature.",
    "deafened": "A deafened creature can’t hear and automatically fails any ability check that requires hearing.",
    "frightened": "A frightened creature has disadvantage on ability checks and attack rolls while the source of its fear is within line of sight.\nThe creature can’t willingly move closer to the source of its fear.",
    "grappled": "A grappled creature’s speed becomes 0, and it can’t benefit from any bonus to its speed.\nThe condition ends if the grappler is incapacitated (see the condition).\nThe condition also ends if an effect removes the grappled creature from the reach of the grappler or grappling effect, such as when a creature is hurled away by the thunderwave spell.",
    "incapacitated": "An incapacitated creature can’t take actions or reactions.",
    "invisible": "An invisible creature is impossible to see without the aid of magic or a special sense. For the purpose of hiding, the creature is heavily obscured. The creature’s location can be detected by any noise it makes or any tracks it leaves.\nAttack rolls against the creature have disadvantage, and the creature’s attack rolls have advantage.",
    "paralyzed": "A paralyzed creature is incapacitated (see the condition) and can’t move or speak.\nThe creature automatically fails Strength and Dexterity saving throws.\nAttack rolls against the creature have advantage.\nAny attack that hits the creature is a critical hit if the attacker is within 5 feet of the creature.",
    "petrified": "A petrified creature is transformed, along with any nonmagical object it is wearing or carrying, into a solid inanimate substance (usually stone). Its weight increases by a factor of ten, and it ceases aging.\nThe creature is incapacitated (see the condition), can’t move or speak, and is unaware of its surroundings.\nAttack rolls against the creature have advantage.\nThe creature automatically fails Strength and Dexterity saving throws.\nThe creature has resistance to all damage.\nThe creature is immune to poison and disease, although a poison or disease already in its system is suspended, not neutralized.",
    "poisoned": "A poisoned creature has disadvantage on attack rolls and ability checks.",
    "prone": "A prone creature’s only movement option is to crawl, unless it stands up and thereby ends the condition.\nThe creature has disadvantage on attack rolls.\nAn attack roll against the creature has advantage if the attacker is within 5 feet of the creature. Otherwise, the attack roll has disadvantage.",
    "restrained": "A restrained creature’s speed becomes 0, and it can’t benefit from any bonus to its speed.\nAttack rolls against the creature have advantage, and the creature’s attack rolls have disadvantage.\nThe creature has disadvantage on Dexterity saving throws.",
    "stunned": "A stunned creature is incapacitated (see the condition), can’t move, and can speak only falteringly.\nThe creature automatically fails Strength and Dexterity saving throws.\nAttack rolls against the creature have advantage.",
    "unconscious": "An unconscious creature is incapacitated (see the condition), can’t move or speak, and is unaware of its surroundings\nThe creature drops whatever it’s holding and falls prone.\nThe creature automatically fails Strength and Dexterity saving throws.\nAttack rolls against the creature have advantage.\nAny attack that hits the creature is a critical hit if the attacker is within 5 feet of the creature.",
    "exhaustion": "Some special abilities and environmental hazards, such as starvation and the long-­term effects of freezing or scorching temperatures, can lead to a special condition called exhaustion. Exhaustion is measured in six levels. An effect can give a creature one or more levels of exhaustion, as specified in the effect’s description.\n\nExhaustion Effects:\nLevel 1: Disadvantage on ability checks\nLevel 2: Speed halved\nLevel 3: Disadvantage on attack rolls and saving throws\nLevel 4: Hit point maximum halved\nLevel 5: Speed reduced to 0\nLevel 6: Death\n\nIf an already exhausted creature suffers another effect that causes exhaustion, its current level of exhaustion increases by the amount specified in the effect’s description.\n\nA creature suffers the effect of its current level of exhaustion as well as all lower levels. For example, a creature suffering level 2 exhaustion has its speed halved and has disadvantage on ability checks.\n\nAn effect that removes exhaustion reduces its level as specified in the effect’s description, with all exhaustion effects ending if a creature’s exhaustion level is reduced below 1.\n\nFinishing a long rest reduces a creature’s exhaustion level by 1, provided that the creature has also ingested some food and drink."
}

def clean_5etools_text_with_conditions(text):
    if not isinstance(text, str):
        return text
    # Intercept condition references and wrap into condition tags before 5etools utility standardizes them
    text = re.sub(r'{@condition ([^|}]+)[^}]*}', r'«CONDITION:\1»', text, flags=re.IGNORECASE)
    return preprocess.clean_5etools_text(text)


class AutoHeightText(tk.Text):
    def __init__(self, master=None, canvas_to_refresh=None, **kwargs):
        kwargs.setdefault("height", 1)
        if "justify" in kwargs:
            kwargs.pop("justify")  # Strip unsupported entry configs from native text elements
        super().__init__(master, **kwargs)
        self.canvas_to_refresh = canvas_to_refresh
        self._last_width = 0
        
        self.bind("<KeyRelease>", lambda e=None: self.adjust_height())
        self.bind("<Configure>", self._on_configure)
        self.bind("<<Modified>>", self._on_modified)
        self.bind("<Map>", lambda e=None: self.after(10, self.adjust_height))

    def _on_configure(self, event):
        if event.width != self._last_width:
            self._last_width = event.width
            self.adjust_height()

    def _on_modified(self, event):
        if self.edit_modified():
            self.adjust_height()
            self.edit_modified(False)

    def insert(self, index, chars=None, *args, **kwargs):
        # Translate integer indexing safely to text metrics index bounds
        if isinstance(index, int):
            index = "1.0" if index == 0 else f"1.0 + {index} chars"
        if chars is None:
            super().insert(index, *args, **kwargs)
        else:
            super().insert(index, chars, *args, **kwargs)
        self.adjust_height()

    def delete(self, index1, index2=None, *args, **kwargs):
        if isinstance(index1, int):
            index1 = "1.0"
        if isinstance(index2, int) or index2 == tk.END:
            index2 = tk.END
        super().delete(index1, index2, *args, **kwargs)
        self.adjust_height()

    def get(self, index1=None, index2=None, *args, **kwargs):
        if index1 is None:
            return super().get("1.0", "end-1c")
        return super().get(index1, index2, *args, **kwargs)

    def adjust_height(self):
        """Optimized layout engine that computes bounds strictly via text splits,
        completely skipping expensive displayline lookups or sub-window checks.
        """
        if not self.canvas_to_refresh:
            return

        try:
            font_obj = font.Font(font=self.cget("font"))
            char_width = font_obj.measure("m") or 8
        except Exception:
            char_width = 8

        w = self.winfo_width()
        chars_per_line = max(10, w // char_width) if w > 20 else 60

        text_content = self.get("1.0", "end-1c")
        total_lines = 0
        
        for line in text_content.split("\n"):
            if not line:
                total_lines += 1
            else:
                total_lines += max(1, (len(line) + chars_per_line - 1) // chars_per_line)

        total_lines = max(1, total_lines)

        if total_lines != int(self.cget("height")):
            self.configure(height=total_lines)
            if self.canvas_to_refresh:
                self.canvas_to_refresh.update_idletasks()
                self.canvas_to_refresh.configure(scrollregion=self.canvas_to_refresh.bbox("all"))


class ChipFlowFrame(tk.Frame):
    """A high-performance horizontal flow layout frame for spell chips.
    It calculates boundaries instantly using required dimensions and flows components smoothly.
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.widgets = []
        self.bind("<Configure>", lambda e: self.rearrange())

    def add_widget(self, w):
        self.widgets.append(w)
        self.rearrange()

    def rearrange(self):
        width = self.winfo_width()
        if width <= 1:
            self.after(10, self._do_rearrange)
            return
        self._do_rearrange()

    def _do_rearrange(self):
        width = self.winfo_width()
        if width <= 1: return
        
        x, y = 0, 0
        row_h = 0
        for w in self.widgets:
            if not w.winfo_exists(): continue
            w_w = w.winfo_reqwidth()
            w_h = w.winfo_reqheight()
            
            if x + w_w > width and x > 0:
                x = 0
                y += row_h + 4
                row_h = 0
                
            w.place(x=x, y=y, width=w_w, height=w_h)
            x += w_w + 6
            row_h = max(row_h, w_h)
            
        total_h = y + row_h
        if total_h < 30: total_h = 30
        if int(self.cget("height")) != total_h:
            self.config(height=total_h)


class StatBlockRenderer(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, bg="#fdf1dc", *args, **kwargs) 

        self.view_container = tk.Frame(self, bg="#fdf1dc")
        self.view_container.pack(fill=tk.BOTH, expand=True)
        self.v_scroll = ttk.Scrollbar(self.view_container, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.spell_callback = None; self.spells_index = []
        
        self.edit_container = tk.Frame(self, bg="#fdf1dc")
        self.edit_canvas = tk.Canvas(self.edit_container, bg="#fdf1dc", highlightthickness=0)
        self.edit_scroll = ttk.Scrollbar(self.edit_container, orient="vertical", command=self.edit_canvas.yview)
        self.edit_inner = tk.Frame(self.edit_canvas, bg="#fdf1dc", padx=40, pady=20)
        self.edit_scroll.pack(side=tk.RIGHT, fill=tk.Y); self.edit_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.edit_window = self.edit_canvas.create_window((0, 0), window=self.edit_inner, anchor="nw")
        self.edit_inner.bind("<Configure>", lambda e=None: self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all")))
        self.edit_canvas.bind("<Configure>", lambda e=None: self.edit_canvas.itemconfig(self.edit_window, width=e.width))
        self.edit_canvas.configure(yscrollcommand=self.edit_scroll.set)

        self.dividers = []; self.overlay_buttons = []
        self.text = AutoHeightText(self.view_container, canvas_to_refresh=self.edit_canvas, bg="#fdf1dc", wrap=tk.WORD, borderwidth=0, highlightthickness=0, padx=40, pady=40, yscrollcommand=self.v_scroll.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._setup_fonts_and_tags()
        self.v_scroll.config(command=self.text.yview)
        self.text.bind("<Configure>", lambda e=None: [div.configure(width=max(10, e.width - 80)) for div in self.dividers if div.winfo_exists()])

        def redirect_scroll_to_popup(event):
            if hasattr(self, "_hover_popup") and self._hover_popup and self._hover_popup.winfo_exists():
                units = -2 if event.num == 4 else 2 if event.num == 5 else -1 * (event.delta // 40)
                if hasattr(self._hover_popup, 'target_text_widget') and self._hover_popup.target_text_widget.winfo_exists():
                    self._hover_popup.target_text_widget.yview_scroll(units, "units")
                return "break"  # Prevents the main text page from scrolling
                
        self.text.bind("<MouseWheel>", redirect_scroll_to_popup)
        self.text.bind("<Button-4>", redirect_scroll_to_popup)
        self.text.bind("<Button-5>", redirect_scroll_to_popup)

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
        self.text.tag_configure("spell_link", font=self.body_font, foreground="#4a90e2", underline=True)
        
        self.text.tag_bind("spell_link", "<Enter>", lambda e: [self.text.config(cursor="hand2"), self._on_link_enter(e)])
        self.text.tag_bind("spell_link", "<Leave>", lambda e: [self.text.config(cursor=""), self._on_link_leave(e)])
        self.text.tag_bind("spell_link", "<Motion>", self._on_link_motion)
        self.text.tag_bind("spell_link", "<Button-1>", self._on_spell_click)

    def _on_link_enter(self, event):
        self._handle_link_hover(event)

    def _on_link_motion(self, event):
        self._handle_link_hover(event)

    def _on_link_leave(self, event):
        if hasattr(self, "_hover_popup") and self._hover_popup:
            try: self._hover_popup.destroy()
            except: pass
            self._hover_popup = None
            self._hover_target = None

    def _handle_link_hover(self, event):
        idx = self.text.index(f"@{event.x},{event.y}")
        tags = self.text.tag_names(idx)
        target_tag = None
        valid_prefixes = ["SPELL_TAG:", "CONDITION_TAG:", "LOC_MON_TAG:", "LOC_NPC_TAG:", "LOC_COMBAT_TAG:", "LOC_EVT_TAG:", "LOC_OBJ_TAG:", "LOC_CONN_TAG:"]
        for t in tags:
            if ":" in t and any(t.startswith(p) for p in valid_prefixes):
                target_tag = t
                break
        if not target_tag:
            self._on_link_leave(None)
            return

        scr_w = self.winfo_screenwidth()
        scr_h = self.winfo_screenheight()
        popup_w = int(scr_w * 2 / 5)
        popup_h = int(scr_h * 2 / 5)

        mid_x = scr_w / 2
        mid_y = scr_h / 2
        x_pos = event.x_root + 15 if event.x_root < mid_x else event.x_root - popup_w - 15
        y_pos = event.y_root + 15 if event.y_root < mid_y else event.y_root - popup_h - 15

        if hasattr(self, "_hover_target") and self._hover_target == target_tag:
            if hasattr(self, "_hover_popup") and self._hover_popup:
                self._hover_popup.geometry(f"{popup_w}x{popup_h}+{x_pos}+{y_pos}")
            return

        self._on_link_leave(None)
        self._hover_target = target_tag
        prefix, name = target_tag.split(":", 1)
        
        popup = tk.Toplevel(self)
        popup.is_hover_popup = True  
        popup.wm_overrideredirect(True)
        popup.configure(bg="#fdf1dc", bd=2, relief=tk.SOLID)
        popup.geometry(f"{popup_w}x{popup_h}+{x_pos}+{y_pos}")
        self._hover_popup = popup

        if prefix == "CONDITION_TAG":
            from stat_renderer import CONDITIONS_DB
            desc = CONDITIONS_DB.get(name.lower().strip(), "No description available.")
            txt = tk.Text(popup, font=("Times", 12), wrap=tk.WORD, bg="#fdf1dc", bd=0, highlightthickness=0)
            txt.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
            txt.insert("1.0", name.title(), "title")
            txt.tag_configure("title", font=("Georgia", 14, "bold"), foreground="#58180d")
            txt.insert(tk.END, f"\n\n{desc}")
            txt.config(state=tk.DISABLED)
            # ADD THIS LINE RIGHT HERE:
            popup.target_text_widget = txt
        else:
            toplevel = self.winfo_toplevel()
            if hasattr(toplevel, "resolve_hover_data"):
                data, dtype = toplevel.resolve_hover_data(prefix, name)
                if data:
                    mini_viewer = StatBlockRenderer(popup)
                    mini_viewer.pack(fill=tk.BOTH, expand=True)
                    mini_viewer.clear_overlays()
                    mini_viewer.text.adjust_height = lambda: None
                    mini_viewer.text.configure(height=1)
                    if dtype == "spell": mini_viewer.render_spell(data)
                    elif dtype in ["monster", "npc"]: mini_viewer.render_monster(data)
                    elif dtype == "location": mini_viewer.render_location(data)
                    elif dtype == "event": mini_viewer.render_event(data)
                    elif dtype == "object": mini_viewer.render_object(data)
                    # ADD THIS LINE RIGHT HERE:
                    popup.target_text_widget = mini_viewer.text
                else:
                    tk.Label(popup, text=f"Profile '{name}' not found.", bg="#fdf1dc", font=("Arial", 11, "italic")).pack(padx=20, pady=20)

    def _optimize_and_refresh_layout(self):
        """Performs a single optimized batch layout pass for all text fields and scrollable frames."""
        self.edit_inner.update_idletasks()
        
        def process_widget(w):
            if isinstance(w, AutoHeightText):
                w.adjust_height()
            for child in w.winfo_children():
                process_widget(child)
                
        process_widget(self.edit_inner)
        self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all"))

    def insert_divider(self):
        w = self.text.winfo_width()
        width_val = max(10, w - 80) if w > 20 else 600
        div = tk.Frame(self.text, height=3, bg="#d9ad6c", width=width_val)
        self.text.window_create(tk.END, window=div); self.text.insert(tk.END, "\n"); self.dividers.append(div)

    def clear_overlays(self):
        for btn in self.overlay_buttons: btn.destroy()
        self.overlay_buttons.clear()

    def add_top_buttons(self, m_dir, view_cb, edit_cb):
        self.clear_overlays()
        b_view = tk.Button(self.view_container, text="VIEW ARTWORK", bg="#d9ad6c", fg="black", font=("Georgia", 10, "bold"), command=lambda: view_cb(m_dir))
        b_view.place(relx=1.0, x=-140, y=10, width=120, height=30)
        b_edit = tk.Button(self.view_container, text="EDIT", bg="#8a8a8a", fg="white", font=("Georgia", 10, "bold"), command=lambda: edit_cb(m_dir))
        b_edit.place(relx=1.0, x=-230, y=10, width=80, height=30)
        self.overlay_buttons.extend([b_view, b_edit])

    def add_custom_spell_buttons(self, s_data, edit_cb, del_cb):
        self.clear_overlays()
        b_del = tk.Button(self.view_container, text="DELETE", bg="#ff4d4d", fg="white", font=("Georgia", 10, "bold"), command=lambda: del_cb(s_data))
        b_del.place(relx=1.0, x=-90, y=10, width=70, height=30)
        b_edit = tk.Button(self.view_container, text="EDIT", bg="#8a8a8a", fg="white", font=("Georgia", 10, "bold"), command=lambda: edit_cb(s_data))
        b_edit.place(relx=1.0, x=-170, y=10, width=70, height=30)
        self.overlay_buttons.extend([b_del, b_edit])

    def add_custom_object_buttons(self, o_data, edit_cb, del_cb):
        self.clear_overlays()
        b_del = tk.Button(self.view_container, text="DELETE", bg="#ff4d4d", fg="white", font=("Georgia", 10, "bold"), command=lambda: del_cb(o_data))
        b_del.place(relx=1.0, x=-90, y=10, width=70, height=30)
        b_edit = tk.Button(self.view_container, text="EDIT", bg="#8a8a8a", fg="white", font=("Georgia", 10, "bold"), command=lambda: edit_cb(o_data))
        b_edit.place(relx=1.0, x=-170, y=10, width=70, height=30)
        self.overlay_buttons.extend([b_del, b_edit])

    def render_edit_mode(self, data, monster_dir, loc_name, save_callback, cancel_callback, add_existing_object_cb=None):
        self.clear_overlays()
        self.view_container.pack_forget()
        self.edit_container.pack(fill=tk.BOTH, expand=True)
        for widget in self.edit_inner.winfo_children(): widget.destroy()

        self.is_object_mode = False
        self.edit_data = copy.deepcopy(data); self.edit_refs = {}

        top_frame = tk.Frame(self.edit_inner, bg="#fdf1dc"); top_frame.pack(fill=tk.X, pady=(0, 20))
        tk.Label(top_frame, text="EDIT MONSTER / NPC", font=self.header_font, fg="#58180d", bg="#fdf1dc").pack(side=tk.LEFT)
        tk.Button(top_frame, text="SAVE", bg="#4a90e2", fg="white", font=("Georgia", 10, "bold"), command=lambda: self._handle_gui_save(monster_dir, save_callback)).pack(side=tk.RIGHT, padx=5)
        tk.Button(top_frame, text="CANCEL", bg="#58180d", fg="white", font=("Georgia", 10, "bold"), command=cancel_callback).pack(side=tk.RIGHT, padx=5)

        basic_frame = tk.Frame(self.edit_inner, bg="#fdf1dc"); basic_frame.pack(fill=tk.X, pady=10)
        row = 0
        def add_basic_field(label_text, key, width=50):
            nonlocal row
            tk.Label(basic_frame, text=label_text, bg="#fdf1dc", font=self.body_bold, fg="black").grid(row=row, column=0, sticky="e", padx=5, pady=2)
            val = self.edit_data.get(key, "")
            if isinstance(val, (dict, list)): val = json.dumps(val)
            entry = AutoHeightText(basic_frame, canvas_to_refresh=self.edit_canvas, width=width, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
            entry.insert(0, str(val)); entry.grid(row=row, column=1, sticky="w", padx=5, pady=2)
            self.edit_refs[key] = entry; row += 1

        add_basic_field("Name:", "name"); add_basic_field("Level:", "level", width=10); add_basic_field("Source:", "source"); add_basic_field("Challenge Rating:", "cr", width=10)

        ac_val = self.edit_data.get("ac", [10])
        if isinstance(ac_val, list) and len(ac_val) > 0: ac_val = ac_val[0]
        if isinstance(ac_val, dict): ac_val = ac_val.get("ac", 10)
        tk.Label(basic_frame, text="Armor Class:", bg="#fdf1dc", font=self.body_bold, fg="black").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        ac_entry = AutoHeightText(basic_frame, canvas_to_refresh=self.edit_canvas, width=50, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
        ac_entry.insert(0, str(ac_val)); ac_entry.grid(row=row, column=1, sticky="w", padx=5, pady=2); self.edit_refs["ac"] = ac_entry; row += 1

        hp_formula = self.edit_data.get("hp", {}).get("formula", "1d8")
        tk.Label(basic_frame, text="Hit Points (Formula):", bg="#fdf1dc", font=self.body_bold, fg="black").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        hp_entry = AutoHeightText(basic_frame, canvas_to_refresh=self.edit_canvas, width=50, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
        hp_entry.insert(0, str(hp_formula)); hp_entry.grid(row=row, column=1, sticky="w", padx=5, pady=2); self.edit_refs["hp_formula"] = hp_entry; row += 1

        ui_frame = tk.Frame(self.edit_inner, bg="#fdf1dc"); ui_frame.pack(fill=tk.X, pady=5)
        tk.Label(ui_frame, text="Size:", bg="#fdf1dc", font=self.body_bold, fg="black").pack(side=tk.LEFT, padx=(5,2))
        self.size_map = {"Tiny": "T", "Small": "S", "Medium": "M", "Large": "L", "Huge": "H", "Gargantuan": "G"}
        inv_size_map = {v: k for k, v in self.size_map.items()}
        cur_size = self.edit_data.get("size", ["M"])
        if isinstance(cur_size, list): cur_size = cur_size[0]
        self.size_var = tk.StringVar(value=inv_size_map.get(cur_size, "Medium"))
        ttk.Combobox(ui_frame, textvariable=self.size_var, values=list(self.size_map.keys()), state="readonly", width=12).pack(side=tk.LEFT, padx=(0, 20))
        
        tk.Label(ui_frame, text="Alignment:", bg="#fdf1dc", font=self.body_bold, fg="black").pack(side=tk.LEFT, padx=(5,2))
        self.align_map = {
            "Lawful Good": ["L", "G"], "Neutral Good": ["N", "G"], "Chaotic Good": ["C", "G"],
            "Lawful Neutral": ["L", "N"], "True Neutral": ["N"], "Chaotic Neutral": ["C", "N"],
            "Lawful Evil": ["L", "E"], "Neutral Evil": ["N", "E"], "Chaotic Evil": ["C", "E"],
            "Unaligned": ["U"], "Any": ["A"]
        }
        cur_align = self.edit_data.get("alignment", ["N"]); align_str = "True Neutral"
        for k, v in self.align_map.items():
            if v == cur_align: align_str = k; break
        self.align_var = tk.StringVar(value=align_str)
        ttk.Combobox(ui_frame, textvariable=self.align_var, values=list(self.align_map.keys()), state="readonly", width=15).pack(side=tk.LEFT)

        speed_master = tk.Frame(self.edit_inner, bg="#fdf1dc", pady=10); speed_master.pack(fill=tk.X)
        tk.Label(speed_master, text="Speeds:", bg="#fdf1dc", font=self.body_bold, fg="black").pack(side=tk.LEFT, anchor="n")
        self.speed_frame = tk.Frame(speed_master, bg="#fdf1dc"); self.speed_frame.pack(side=tk.LEFT, padx=10); self.speed_refs = []

        def add_speed_row(s_type="walk", s_val="", s_cond=""):
            row = tk.Frame(self.speed_frame, bg="#fdf1dc"); row.pack(fill=tk.X, pady=2)
            t_var = tk.StringVar(value=s_type); ttk.Combobox(row, textvariable=t_var, values=["walk", "fly", "swim", "climb", "burrow"], width=8, state="readonly").pack(side=tk.LEFT, padx=2)
            v_en = AutoHeightText(row, canvas_to_refresh=self.edit_canvas, width=5, font=self.body_font, bd=1, relief=tk.SOLID)
            v_en.insert(0, str(s_val)); v_en.pack(side=tk.LEFT, padx=2)
            tk.Label(row, text="ft.", bg="#fdf1dc", fg="black").pack(side=tk.LEFT)
            c_en = AutoHeightText(row, canvas_to_refresh=self.edit_canvas, width=15, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
            c_en.insert(0, str(s_cond)); c_en.pack(side=tk.LEFT, padx=2)
            def remove():
                row.pack_forget(); row.destroy(); self.speed_refs.remove((t_var, v_en, c_en, row))
            tk.Button(row, text="X", bg="#ff4d4d", fg="white", font=("Arial", 8, "bold"), command=remove).pack(side=tk.LEFT, padx=5)
            self.speed_refs.append((t_var, v_en, c_en, row))

        self.can_hover_var = tk.BooleanVar(value=False)
        tk.Checkbutton(speed_master, text="Can Hover", variable=self.can_hover_var, bg="#fdf1dc", fg="black", activebackground="#fdf1dc").pack(side=tk.LEFT, padx=10)
        tk.Button(speed_master, text="+ Add Speed", bg="#d9ad6c", font=("Arial", 9, "bold"), command=add_speed_row).pack(side=tk.LEFT)

        for k, v in self.edit_data.get("speed", {}).items():
            if k == "canHover": self.can_hover_var.set(v)
            elif isinstance(v, dict): add_speed_row(k, v.get("number", ""), v.get("condition", ""))
            else: add_speed_row(k, v, "")

        abilities_frame = tk.Frame(self.edit_inner, bg="#fdf1dc"); abilities_frame.pack(fill=tk.X, pady=15)
        tk.Label(abilities_frame, text="Value", bg="#fdf1dc", font=self.body_italic, fg="#555").grid(row=1, column=0, sticky="e", padx=(0,5))
        tk.Label(abilities_frame, text="Mod Override", bg="#fdf1dc", font=self.body_italic, fg="#555").grid(row=2, column=0, sticky="e", padx=(0,5))
        tk.Label(abilities_frame, text="Save Override", bg="#fdf1dc", font=self.body_italic, fg="#555").grid(row=3, column=0, sticky="e", padx=(0,5))

        self.edit_ability_refs = {}
        for i, stat in enumerate(["str", "dex", "con", "int", "wis", "cha"]):
            tk.Label(abilities_frame, text=stat.upper(), bg="#fdf1dc", font=self.body_bold, fg="black").grid(row=0, column=i+1, padx=5)
            v_en = tk.Entry(abilities_frame, width=6, font=self.body_font, bd=1, relief=tk.SOLID); v_en.insert(0, str(self.edit_data.get(stat, 10))); v_en.grid(row=1, column=i+1, padx=5, pady=2)
            m_en = tk.Entry(abilities_frame, width=6, font=self.body_font, bd=1, relief=tk.SOLID); m_en.insert(0, str(self.edit_data.get("modOverride", {}).get(stat, ""))); m_en.grid(row=2, column=i+1, padx=5, pady=2)
            s_en = tk.Entry(abilities_frame, width=6, font=self.body_font, bd=1, relief=tk.SOLID); s_en.insert(0, str(self.edit_data.get("save", {}).get(stat, ""))); s_en.grid(row=3, column=i+1, padx=5, pady=2)
            self.edit_ability_refs[stat] = (v_en, m_en, s_en)

        self.arrays_frame = tk.Frame(self.edit_inner, bg="#fdf1dc"); self.arrays_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.array_refs = {}; self.sc_refs = []; self.rebuild_sc_hooks = []; self.dialogue_refs = []
        
        self.build_dialogues_section(loc_name)

        self.creature_object_items = []
        if add_existing_object_cb:
            obj_sec = tk.Frame(self.arrays_frame, bg="#fdf1dc", pady=5); obj_sec.pack(fill=tk.X)
            obj_hdr = tk.Frame(obj_sec, bg="#fdf1dc"); obj_hdr.pack(fill=tk.X)
            tk.Label(obj_hdr, text="Objects / Possessions:", font=self.body_bold, bg="#fdf1dc", fg="#7a200d").pack(side=tk.LEFT)
            obj_lst = tk.Frame(obj_sec, bg="#fdf1dc"); obj_lst.pack(fill=tk.X)
            
            def draw_obj_row_creature(name):
                row = tk.Frame(obj_lst, bg="#e0cbb0", pady=4, padx=10, bd=1, relief=tk.SOLID); row.pack(fill=tk.X, pady=2)
                tk.Label(row, text=name, font=self.body_bold, bg="#e0cbb0", fg="black").pack(side=tk.LEFT)
                item_dict = {"name": name, "frame": row}; self.creature_object_items.append(item_dict)
                tk.Button(row, text="X", bg="#ff4d4d", fg="white", font=("Arial", 8, "bold"), 
                          command=lambda: (row.pack_forget(), row.destroy(), self.creature_object_items.remove(item_dict), self.edit_inner.update_idletasks(), self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all")))).pack(side=tk.RIGHT)
                self.edit_inner.update_idletasks(); self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all"))
                
            tk.Button(obj_hdr, text="+ Add Object", bg="#d9ad6c", font=("Arial", 8, "bold"), command=lambda: add_existing_object_cb(draw_obj_row_creature)).pack(side=tk.LEFT, padx=10)
            for obj in self.edit_data.get("objects", []): draw_obj_row_creature(obj)

        def sync_all_sc():
            for sc_dict_ref, _, ab_var, dc_var, hit_var, slots_entries in self.sc_refs:
                try:
                    sc_dict_ref["ability"] = ab_var.get().lower() if ab_var else "int"
                    dc_val = dc_var.get().strip() if dc_var else "10"
                    sc_dict_ref["custom_dc"] = int(dc_val) if dc_val.isdigit() else 10
                    hit_val = hit_var.get().strip() if hit_var else "2"
                    sc_dict_ref["custom_hit"] = int(hit_val) if hit_val.lstrip('+-').isdigit() else 2
                    if "spells" in sc_dict_ref:
                        for lvl, se in slots_entries.items():
                            val = se.get().strip()
                            if val.isdigit() and lvl in sc_dict_ref["spells"]: sc_dict_ref["spells"][lvl]["slots"] = int(val)
                except Exception: pass

        def rebuild_all_sc():
            sync_all_sc()
            self.sc_refs.clear()
            for hook in self.rebuild_sc_hooks: hook()
            self._optimize_and_refresh_layout()

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
            t = tk.Frame(f, bg="#e2f0d9", pady=2); t.pack(fill=tk.X)
            
            tk.Label(t, text="Name:", bg="#e2f0d9", font=self.body_bold, fg="black").pack(side=tk.LEFT, padx=2)
            ne = AutoHeightText(t, canvas_to_refresh=self.edit_canvas, width=22, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
            ne.insert(0, d.get("name", f"Dialogue with {self.edit_refs['name'].get()}")); ne.pack(side=tk.LEFT, padx=4)
            
            tk.Label(t, text="Location:", bg="#e2f0d9", font=self.body_bold, fg="black").pack(side=tk.LEFT, padx=2)
            le = AutoHeightText(t, canvas_to_refresh=self.edit_canvas, width=15, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
            le.insert(0, d.get("location", def_loc)); le.pack(side=tk.LEFT, padx=4)
            
            tk.Label(t, text="Event:", bg="#e2f0d9", font=self.body_bold, fg="black").pack(side=tk.LEFT, padx=2)
            te = AutoHeightText(t, canvas_to_refresh=self.edit_canvas, width=15, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
            te.insert(0, d.get("time", "Act 1")); te.pack(side=tk.LEFT, padx=4)
            
            tk.Label(f, text="Description:", bg="#e2f0d9", font=self.body_italic, fg="black").pack(anchor="w", pady=(5,0))
            txt = AutoHeightText(f, canvas_to_refresh=self.edit_canvas, height=1, font=self.body_font, wrap=tk.WORD); txt.insert("1.0", "\n".join(d.get("entries", []))); txt.pack(fill=tk.X)
            
            tk.Button(t, text="X", bg="#ff4d4d", command=lambda: (f.pack_forget(), f.destroy(), self.dialogue_refs.remove((ne, le, te, txt)), self.edit_inner.update_idletasks(), self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all")))).pack(side=tk.RIGHT)
            self.dialogue_refs.append((ne, le, te, txt))
        tk.Button(hdr, text="+ Add Dialogue", bg="#d9ad6c", command=add_dialogue).pack(side=tk.LEFT, padx=15)
        for dg in self.edit_data.get("dialogues", []): add_dialogue(dg)

    def _render_campaign_node(self, data, sections):
        """Unified shared renderer parsing layout elements smoothly for campaign location metrics or storyline events logs."""
        self.clear_overlays()
        self.edit_container.pack_forget()
        self.view_container.pack(fill=tk.BOTH, expand=True)
        
        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.dividers.clear()
        
        self.text.insert(tk.END, data.get("name", "Unknown Profile") + "\n", "title")
        self.insert_divider()
        
        if "priority" in data:
            p_list = data.get("priority", [0])
            self.text.insert(tk.END, "Priority: ", "bold")
            self.text.insert(tk.END, ", ".join(map(str, sorted(p_list))) + "\n\n", "body")
            self.insert_divider()
        elif "depths" in data:
            depths_list = data.get("depths", [0])
            self.text.insert(tk.END, "Depths: ", "bold")
            self.text.insert(tk.END, ", ".join(map(str, sorted(depths_list))) + "\n\n", "body")
            self.insert_divider()

        desc = data.get("description", "")
        if desc: 
            self.text.insert(tk.END, desc + "\n\n", "body")
            self.insert_divider()

        for key, heading, tag_prefix in sections:
            items = data.get(key, [])
            if items:
                self.text.insert(tk.END, f"{heading}\n", "section_header")
                self.insert_divider()
                for item in items:
                    name = item if isinstance(item, str) else item.get("name", "")
                    self.text.insert(tk.END, "• ")
                    self.text.insert(tk.END, name, ("spell_link", f"{tag_prefix}:{name}"))
                    self.text.insert(tk.END, "\n", "body")
                self.text.insert(tk.END, "\n")

        connections = data.get("connections", [])
        if connections:
            is_loc = any("events" in p[0].lower() for p in sections)
            self.text.insert(tk.END, f"Connected {'locations' if is_loc else 'events'}\n", "section_header")
            self.insert_divider()
            for conn in connections:
                target = conn.get("target", "")
                c_desc = conn.get("description", "")
                self.text.insert(tk.END, "• ")
                self.text.insert(tk.END, target, ("spell_link", f"{'LOC_CONN_TAG' if is_loc else 'LOC_EVT_TAG'}:{target}"))
                if c_desc: 
                    self.text.insert(tk.END, f" : {c_desc}", "body")
                self.text.insert(tk.END, "\n", "body")
            self.text.insert(tk.END, "\n")
            
        self.text.config(state=tk.DISABLED)

    def render_location(self, data, back_cb=None):
        self._render_campaign_node(data, [("monsters", "Monsters", "LOC_MON_TAG"), ("npcs", "Npcs", "LOC_NPC_TAG"), ("combats", "Combats", "LOC_COMBAT_TAG"), ("events", "Related events", "LOC_EVT_TAG"), ("objects", "Objects", "LOC_OBJ_TAG")])

    def render_event(self, data, back_cb=None):
        self._render_campaign_node(data, [("monsters", "Monsters", "LOC_MON_TAG"), ("npcs", "Npcs", "LOC_NPC_TAG"), ("combats", "Combats", "LOC_COMBAT_TAG"), ("locations", "Locations", "LOC_CONN_TAG"), ("objects", "Objects", "LOC_OBJ_TAG")])

    def _render_campaign_node_edit(self, data, is_location, save_callback, cancel_callback, callbacks_dict):
        """Unified edit dashboard renderer handling input form updates symmetrically for campaign sub-elements maps/events."""
        self.clear_overlays(); self.view_container.pack_forget(); self.edit_container.pack(fill=tk.BOTH, expand=True)
        for widget in self.edit_inner.winfo_children(): widget.destroy()

        self.edit_data = copy.deepcopy(data)
        keys = ["monsters", "npcs", "combats", "events" if is_location else "locations", "objects", "connections"]
        for k in keys: self.edit_data.setdefault(k, [])

        top_frame = tk.Frame(self.edit_inner, bg="#fdf1dc"); top_frame.pack(fill=tk.X, pady=(0, 20))
        tk.Label(top_frame, text=f"EDIT {'LOCATION' if is_location else 'EVENT'} PROFILE", font=self.header_font, fg="#58180d", bg="#fdf1dc").pack(side=tk.LEFT)
        
        storage = {k: [] for k in keys}
        def handle_save():
            self.edit_data["name"] = name_entry.get().strip(); self.edit_data["description"] = desc_text.get("1.0", "end-1c").strip()
            
            if is_location:
                self.edit_data["depths"] = self.current_location_depths if getattr(self, 'current_location_depths', None) else [0]
            else:
                self.edit_data["priority"] = self.current_event_priorities if getattr(self, 'current_event_priorities', None) else [0]
            
            for k in keys[:-1]: self.edit_data[k] = [m["name"] for m in storage[k]]
            self.edit_data["connections"] = [{"target": c["target"], "description": c["desc_entry"].get().strip()} for c in storage["connections"]]
            save_callback(callbacks_dict["dir"], self.edit_data)

        tk.Button(top_frame, text="SAVE", bg="#4a90e2", fg="white", font=("Georgia", 10, "bold"), command=handle_save).pack(side=tk.RIGHT, padx=5)
        tk.Button(top_frame, text="CANCEL", bg="#58180d", fg="white", font=("Georgia", 10, "bold"), command=cancel_callback).pack(side=tk.RIGHT, padx=5)

        basic_frame = tk.Frame(self.edit_inner, bg="#fdf1dc"); basic_frame.pack(fill=tk.X, pady=10)
        tk.Label(basic_frame, text="Name:", bg="#fdf1dc", font=self.body_bold, fg="black").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        name_entry = AutoHeightText(basic_frame, canvas_to_refresh=self.edit_canvas, width=50, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
        name_entry.insert(0, self.edit_data.get("name", callbacks_dict["dir"].name)); name_entry.grid(row=0, column=1, sticky="w", padx=5, pady=2)

        tk.Label(basic_frame, text="Description:", bg="#fdf1dc", font=self.body_bold, fg="black").grid(row=1, column=0, sticky="ne", padx=5, pady=2)
        desc_text = AutoHeightText(basic_frame, canvas_to_refresh=self.edit_canvas, width=50, height=1, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
        desc_text.insert("1.0", self.edit_data.get("description", "")); desc_text.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        if is_location:
            self.current_location_depths = self.edit_data.get("depths", [0])
            if not self.current_location_depths: self.current_location_depths = [0]
            tk.Label(basic_frame, text="Depths:", bg="#fdf1dc", font=self.body_bold, fg="black").grid(row=2, column=0, sticky="e", padx=5, pady=2)
            depths_panel = tk.Frame(basic_frame, bg="#fdf1dc")
            depths_panel.grid(row=2, column=1, sticky="w", padx=5, pady=2)
            depths_lbl = tk.Label(depths_panel, text=", ".join(map(str, self.current_location_depths)), font=self.body_font, bg="#fae6c5", fg="black", bd=1, relief=tk.SOLID, padx=10, pady=2)
            depths_lbl.pack(side=tk.LEFT, padx=(0, 10))
            def on_dialog_depths_applied(new_depths):
                self.current_location_depths = new_depths
                depths_lbl.config(text=", ".join(map(str, new_depths)))
            btn_depths = tk.Button(depths_panel, text="Select Depths", font=("Arial", 9, "bold"), bg="#d9ad6c", command=lambda: DepthsSelectionDialog(self, self.current_location_depths, on_dialog_depths_applied, is_priority=False))
            btn_depths.pack(side=tk.LEFT)
        else:
            self.current_event_priorities = self.edit_data.get("priority", [0])
            if not self.current_event_priorities: self.current_event_priorities = [0]
            tk.Label(basic_frame, text="Priority:", bg="#fdf1dc", font=self.body_bold, fg="black").grid(row=2, column=0, sticky="e", padx=5, pady=2)
            priority_panel = tk.Frame(basic_frame, bg="#fdf1dc")
            priority_panel.grid(row=2, column=1, sticky="w", padx=5, pady=2)
            priority_lbl = tk.Label(priority_panel, text=", ".join(map(str, self.current_event_priorities)), font=self.body_font, bg="#fae6c5", fg="black", bd=1, relief=tk.SOLID, padx=10, pady=2)
            priority_lbl.pack(side=tk.LEFT, padx=(0, 10))
            def on_dialog_priorities_applied(new_priorities):
                self.current_event_priorities = new_priorities
                priority_lbl.config(text=", ".join(map(str, new_priorities)))
            btn_priority = tk.Button(priority_panel, text="Select Priorities", font=("Arial", 9, "bold"), bg="#d9ad6c", command=lambda: DepthsSelectionDialog(self, self.current_event_priorities, on_dialog_priorities_applied, is_priority=True))
            btn_priority.pack(side=tk.LEFT)

        def make_section(title_text):
            sec_frame = tk.Frame(self.edit_inner, bg="#fdf1dc", pady=5); sec_frame.pack(fill=tk.X)
            hdr_frame = tk.Frame(sec_frame, bg="#fdf1dc"); hdr_frame.pack(fill=tk.X)
            tk.Label(hdr_frame, text=title_text, font=self.body_bold, bg="#fdf1dc", fg="#7a200d").pack(side=tk.LEFT)
            return hdr_frame, tk.Frame(sec_frame, bg="#fdf1dc")

        def draw_simple_row(list_frame, name, storage_list):
            row = tk.Frame(list_frame, bg="#e0cbb0", pady=4, padx=10, bd=1, relief=tk.SOLID)
            row.pack(fill=tk.X, pady=2)
            item_dict = {"name": name, "frame": row}
            storage_list.append(item_dict)
            
            # Pack deletion action trigger button first
            tk.Button(row, text="X", bg="#ff4d4d", fg="white", font=("Arial", 8, "bold"), 
                      command=lambda: (row.pack_forget(), row.destroy(), storage_list.remove(item_dict), 
                                      self.edit_inner.update_idletasks(), 
                                      self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all")))).pack(side=tk.RIGHT)
            
            # Label expands flexibly up to the button
            tk.Label(row, text=name, font=self.body_bold, bg="#e0cbb0", fg="black", anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.edit_inner.update_idletasks()
            self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all"))

        def draw_connection_row(list_frame, target, description=""):
            row = tk.Frame(list_frame, bg="#f5e6ce", pady=6, padx=10, bd=1, relief=tk.SOLID)
            row.pack(fill=tk.X, pady=2)
            
            # Pack right side boundary elements first
            tk.Button(row, text="X", bg="#ff4d4d", fg="white", font=("Arial", 8, "bold"), 
                      command=lambda: (row.pack_forget(), row.destroy(), storage["connections"].remove(item_dict), 
                                      self.edit_inner.update_idletasks(), 
                                      self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all")))).pack(side=tk.RIGHT)
            
            tk.Label(row, text=f"Route To: {target}", font=self.body_bold, bg="#f5e6ce", fg="black", anchor="w").pack(side=tk.LEFT, padx=5)
            
            # Entry box shifts width dynamically with layout frame scaling proportions
            desc_en = AutoHeightText(row, canvas_to_refresh=self.edit_canvas, width=20, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
            desc_en.insert(0, description)
            desc_en.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            item_dict = {"target": target, "desc_entry": desc_en, "frame": row}
            storage["connections"].append(item_dict)
            self.edit_inner.update_idletasks()
            self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all"))

        m_hdr, m_lst = make_section("Monsters:"); m_lst.pack(fill=tk.X)
        tk.Button(m_hdr, text="+ New", bg="#d9ad6c", font=("Arial", 8, "bold"), command=lambda: callbacks_dict["new_mon"](lambda n: draw_simple_row(m_lst, n, storage["monsters"]))).pack(side=tk.LEFT, padx=5)
        tk.Button(m_hdr, text="+ Existing", bg="#d9ad6c", font=("Arial", 8, "bold"), command=lambda: callbacks_dict["exist_mon"](lambda n: draw_simple_row(m_lst, n, storage["monsters"]))).pack(side=tk.LEFT, padx=2)
        for m in self.edit_data["monsters"]: draw_simple_row(m_lst, m, storage["monsters"])

        for k, label, cb_key in [("npcs", "NPCs:", "exist_npc"), ("combats", "Combats:", "exist_combat"), ("objects", "Objects:", "exist_obj")]:
            hdr, lst = make_section(label)
            lst.pack(fill=tk.X)
            tk.Button(
                hdr, 
                text=f"+ Add {label[:-1]}", 
                bg="#d9ad6c", 
                font=("Arial", 8, "bold"), 
                command=lambda ck=cb_key, l=lst, key=k: callbacks_dict[ck](lambda n: draw_simple_row(l, n, storage[key]))
            ).pack(side=tk.LEFT, padx=5)
            for item in self.edit_data[k]: 
                draw_simple_row(lst, item, storage[k])

        alt_key = "events" if is_location else "locations"
        hdr, lst = make_section("Related Events:" if is_location else "Locations:"); lst.pack(fill=tk.X)
        tk.Button(hdr, text=f"+ Add {'Event' if is_location else 'Location'}", bg="#d9ad6c", font=("Arial", 8, "bold"), command=lambda: callbacks_dict["exist_alt"](lambda n: draw_simple_row(lst, n, storage[alt_key]))).pack(side=tk.LEFT, padx=5)
        for alt in self.edit_data[alt_key]: draw_simple_row(lst, alt, storage[alt_key])

        conn_hdr, conn_lst = make_section("Connected Map Locations:" if is_location else "Connected Events:"); conn_lst.pack(fill=tk.X)
        tk.Button(conn_hdr, text="+ Add Connection", bg="#d9ad6c", font=("Arial", 8, "bold"), command=lambda: callbacks_dict["add_conn"](lambda target: draw_connection_row(conn_lst, target))).pack(side=tk.LEFT, padx=5)
        for conn in self.edit_data["connections"]: draw_connection_row(conn_lst, conn.get("target", ""), conn.get("description", ""))

        self.edit_inner.update_idletasks(); self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all"))

    def render_location_edit_mode(self, data, location_dir, save_callback, cancel_callback, add_new_monster_cb, add_existing_monster_cb, add_existing_npc_cb, add_existing_combat_cb, add_existing_event_cb, add_existing_object_cb, add_connection_cb):
        self._render_campaign_node_edit(data, True, save_callback, cancel_callback, {"dir": location_dir, "new_mon": add_new_monster_cb, "exist_mon": add_existing_monster_cb, "exist_npc": add_existing_npc_cb, "exist_combat": add_existing_combat_cb, "exist_alt": add_existing_event_cb, "exist_obj": add_existing_object_cb, "add_conn": add_connection_cb})

    def render_event_edit_mode(self, data, event_dir, save_callback, cancel_callback, add_new_monster_cb, add_existing_monster_cb, add_existing_npc_cb, add_existing_combat_cb, add_existing_location_cb, add_existing_object_cb, add_connection_cb):
        self._render_campaign_node_edit(data, False, save_callback, cancel_callback, {"dir": event_dir, "new_mon": add_new_monster_cb, "exist_mon": add_existing_monster_cb, "exist_npc": add_existing_npc_cb, "exist_combat": add_existing_combat_cb, "exist_alt": add_existing_location_cb, "exist_obj": add_existing_object_cb, "add_conn": add_connection_cb})

    def build_array_section(self, key, title, rebuild_all_sc, sync_all_sc):
        import utils.preprocess as preprocess
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
    
        is_obj = getattr(self, 'is_object_mode', False)
        
        if sc_type:
            btn_title = f"+ Add {'Slots' if sc_type=='slots' else 'Limited'} Spellcasting" if is_obj else f"+ Add {'Slots' if sc_type=='slots' else 'Innate'} Spellcasting"
            btn_add_sc = tk.Button(btn_frame, text=btn_title, bg="#d9ad6c", font=("Arial", 10, "bold"))
            btn_add_sc.pack(side=tk.LEFT, padx=5)
            
            def rebuild_local_sc():
                for row in sc_container.winfo_children():
                    if isinstance(row, tk.Frame) and row.winfo_children():
                        row.pack_forget()
                        row.destroy()

                sc_data = self.edit_data.get("spellcasting", [])
                has_matching = False
                
                for i, sc_dict in enumerate(sc_data):
                    block_name = sc_dict.get("name", "").lower()
                    display_as = sc_dict.get("displayAs", "")
                    is_innate_block = (display_as in ["action", "object_innate", "innate"]) or ("innate" in block_name)
                    
                    if (sc_type == "slots" and is_innate_block) or (sc_type == "innate" and not is_innate_block): 
                        continue
                    
                    has_matching = True
                    block = tk.Frame(sc_container, bg="#f5e6ce", bd=1, relief=tk.SOLID, pady=10, padx=10)
                    block.pack(fill=tk.X, pady=5)
                    top = tk.Frame(block, bg="#f5e6ce")
                    top.pack(fill=tk.X)
                    
                    lbl_text = ("Limited Spellcasting" if is_innate_block else "Slots Spellcasting") if is_obj else ("Innate Spellcasting" if is_innate_block else "Slots Spellcasting")
                    tk.Label(top, text=lbl_text, font=self.body_bold, bg="#f5e6ce", fg="black").pack(side=tk.LEFT)

                    def make_remover(idx=i, target_block=block):
                        sync_all_sc()
                        self.edit_data["spellcasting"].pop(idx)
                        target_block.pack_forget() 
                        rebuild_all_sc()
                    tk.Button(top, text="X Remove Block", bg="#ff4d4d", fg="white", font=("Arial", 9, "bold"), command=make_remover).pack(side=tk.RIGHT)
                    
                    if not is_obj:
                        param_row = tk.Frame(block, bg="#f5e6ce")
                        param_row.pack(fill=tk.X, pady=5)
                        
                        tk.Label(param_row, text="Ability:", bg="#f5e6ce", font=self.body_bold, fg="black").pack(side=tk.LEFT)
                        ab_var = tk.StringVar(value=sc_dict.get("ability", "int").capitalize())
                        ttk.Combobox(param_row, textvariable=ab_var, values=["Int", "Wis", "Cha", "Str", "Dex", "Con"], state="readonly", width=5).pack(side=tk.LEFT, padx=(2, 10))

                        tk.Label(param_row, text="Save DC:", bg="#f5e6ce", font=self.body_bold, fg="black").pack(side=tk.LEFT)
                        dc_en = AutoHeightText(param_row, canvas_to_refresh=self.edit_canvas, width=4, font=self.body_font, bd=1, relief=tk.SOLID)
                        dc_en.insert(0, str(sc_dict.get("custom_dc", 10)))
                        dc_en.pack(side=tk.LEFT, padx=(2, 10))

                        tk.Label(param_row, text="To Hit:", bg="#f5e6ce", font=self.body_bold, fg="black").pack(side=tk.LEFT)
                        hit_en = AutoHeightText(param_row, canvas_to_refresh=self.edit_canvas, width=4, font=self.body_font, bd=1, relief=tk.SOLID)
                        hit_en.insert(0, str(sc_dict.get("custom_hit", 2)))
                        hit_en.pack(side=tk.LEFT, padx=(2, 10))
                    else:
                        ab_var, dc_en, hit_en = None, None, None

                    lbl_title = "Description:" if is_obj else "Header Template:"
                    tk.Label(block, text=lbl_title, bg="#f5e6ce", font=self.body_italic, fg="black").pack(anchor="w")
                    hdr_text = AutoHeightText(block, canvas_to_refresh=self.edit_canvas, height=1, font=self.body_font, wrap=tk.WORD)
                    hdr_text.insert("1.0", " ".join(sc_dict.get("headerEntries", [])))
                    hdr_text.pack(fill=tk.X, pady=(0, 5))

                    slots_entries = {}
                    spells_frame = tk.Frame(block, bg="#f5e6ce")
                    spells_frame.pack(fill=tk.X, pady=5)

                    if not is_innate_block:
                        spells_dict = sc_dict.setdefault("spells", {})
                        for lvl in range(12):
                            lvl_str = str(lvl)
                            if lvl_str in spells_dict:
                                lvl_data = spells_dict[lvl_str]
                                spells_list = lvl_data.setdefault("spells", [])
                                if not spells_list: continue
                                    
                                row = tk.Frame(spells_frame, bg="#f5e6ce", pady=4)
                                row.pack(fill=tk.X)
                                
                                tk.Label(row, text=f"Level {lvl}:", font=self.body_bold, bg="#f5e6ce", fg="black", width=8, anchor="w").pack(side=tk.LEFT, anchor="n")
                                
                                if lvl > 0 and not is_obj:
                                    tk.Label(row, text="Slots:", bg="#f5e6ce", fg="black").pack(side=tk.LEFT, padx=2, anchor="n")
                                    se = AutoHeightText(row, canvas_to_refresh=self.edit_canvas, width=3, font=self.body_font, bd=1, relief=tk.SOLID)
                                    se.insert(0, str(lvl_data.get("slots", 0)))
                                    se.pack(side=tk.LEFT, padx=(0,10), anchor="n")
                                    slots_entries[lvl_str] = se
                                
                                txt_wrap = ChipFlowFrame(row, bg="#f5e6ce", height=30)
                                txt_wrap.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, anchor="n")
                                
                                for s_idx, s_name in enumerate(spells_list):
                                    sf = tk.Frame(txt_wrap, bg="#e8d5b7", padx=4, pady=2, bd=1, relief=tk.RAISED)
                                    tk.Label(sf, text=preprocess.clean_spell_display_name(s_name), bg="#e8d5b7", font=("Arial", 10), fg="black").pack(side=tk.LEFT)
                                    
                                    def make_slots_remover(l=lvl_str, idx=s_idx, target_sc=sc_dict):
                                        sync_all_sc()
                                        if l in target_sc.get("spells", {}):
                                            spell_list = target_sc["spells"][l].get("spells", [])
                                            if idx < len(spell_list):
                                                spell_list.pop(idx)
                                            if not spell_list:
                                                target_sc["spells"].pop(l)
                                        rebuild_local_sc()

                                    tk.Button(sf, text="x", bg="#ff4d4d", fg="white", font=("Arial", 8), command=make_slots_remover).pack(side=tk.LEFT, padx=(4,0))
                                    txt_wrap.add_widget(sf)
                    else:
                        if "will" in sc_dict and sc_dict["will"]:
                            row = tk.Frame(spells_frame, bg="#f5e6ce", pady=4)
                            row.pack(fill=tk.X)
                            
                            tk.Label(row, text="At will:", font=self.body_bold, bg="#f5e6ce", fg="black", width=8, anchor="w").pack(side=tk.LEFT, anchor="n")
                            txt_wrap = ChipFlowFrame(row, bg="#f5e6ce", height=30)
                            txt_wrap.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, anchor="n")
                            
                            for s_idx, s_name in enumerate(sc_dict["will"]):
                                sf = tk.Frame(txt_wrap, bg="#e8d5b7", padx=4, pady=2, bd=1, relief=tk.RAISED)
                                tk.Label(sf, text=preprocess.clean_spell_display_name(s_name), bg="#e8d5b7", font=("Arial", 10), fg="black").pack(side=tk.LEFT)
                                
                                def make_will_remover(idx=s_idx, target_sc=sc_dict):
                                    sync_all_sc()
                                    if "will" in target_sc and idx < len(target_sc["will"]):
                                        target_sc["will"].pop(idx)
                                        if not target_sc["will"]:
                                            target_sc.pop("will", None)
                                    rebuild_all_sc()

                                tk.Button(sf, text="x", bg="#ff4d4d", fg="white", font=("Arial", 8), command=make_will_remover).pack(side=tk.LEFT, padx=(4,0))
                                txt_wrap.add_widget(sf)
                        if "daily" in sc_dict and sc_dict["daily"]:
                            for freq in list(sc_dict["daily"].keys()):
                                if sc_dict["daily"][freq]:
                                    spells_list = sc_dict["daily"][freq]
                                    row = tk.Frame(spells_frame, bg="#f5e6ce", pady=8)
                                    row.pack(fill=tk.X)
                                    tk.Label(row, text=f"{freq}/day:", font=self.body_bold, bg="#f5e6ce", fg="black", width=8, anchor="w").pack(side=tk.LEFT, anchor="n")
                                    txt_wrap = ChipFlowFrame(row, bg="#f5e6ce", height=30)
                                    txt_wrap.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, anchor="n")
                                    for s_idx, s_name in enumerate(spells_list):
                                        sf = tk.Frame(txt_wrap, bg="#e8d5b7", padx=4, pady=2, bd=1, relief=tk.RAISED)
                                        tk.Label(sf, text=preprocess.clean_spell_display_name(s_name), bg="#e8d5b7", font=("Arial", 10), fg="black").pack(side=tk.LEFT)
                                        
                                        def make_daily_remover(f=freq, index=s_idx, target_sc=sc_dict):
                                            sync_all_sc()
                                            if f in target_sc.get("daily", {}):
                                                daily_list = target_sc["daily"][f]
                                                if index < len(daily_list):
                                                    daily_list.pop(index)
                                                if not daily_list:
                                                    target_sc["daily"].pop(f)
                                            rebuild_local_sc()
                                            
                                        tk.Button(sf, text="x", bg="#ff4d4d", fg="white", font=("Arial", 8), padx=2, command=make_daily_remover).pack(side=tk.LEFT, padx=(4,0))
                                        txt_wrap.add_widget(sf)

                    def add_spell_to_block(block_ref=sc_dict, innate_flag=is_innate_block):
                        def on_spell_selected(spell_data, freq=None):
                            sync_all_sc()
                            spell_name = spell_data["name"].lower()
                            formatted = f"{{@spell {spell_name}}}"
                            if not innate_flag:
                                lvl = spell_data.get("level", 0)
                                ldict = block_ref.setdefault("spells", {}).setdefault(str(lvl), {"spells": []})
                                if formatted not in ldict["spells"]: 
                                    ldict["spells"].append(formatted)
                                    if lvl > 0 and "slots" not in ldict: ldict["slots"] = 1
                            else:
                                if freq == "will":
                                    if formatted not in block_ref.setdefault("will", []): block_ref["will"].append(formatted)
                                else:
                                    if formatted not in block_ref.setdefault("daily", {}).setdefault(freq, []): block_ref["daily"][freq].append(formatted)
                            rebuild_all_sc()
                        SpellSearchDialog(self, self.spells_index, innate_flag, on_spell_selected)

                    tk.Button(block, text="+ Add Spell", bg="#4a90e2", fg="white", font=("Arial", 9, "bold"), command=add_spell_to_block).pack(pady=5)
                    self.sc_refs.append((sc_dict, hdr_text, ab_var, dc_en, hit_en, slots_entries))
                
                btn_add_sc.config(state=tk.DISABLED if has_matching else tk.NORMAL)

            self.rebuild_sc_hooks.append(rebuild_local_sc)

            def add_sc_block():
                if is_obj:
                    self.edit_data.setdefault("spellcasting", []).append({
                        "name": "Limited Spellcasting" if sc_type == "innate" else "Spellcasting",
                        "type": "spellcasting", "headerEntries": [""], "spells": {},
                        "displayAs": "object_innate" if sc_type == "innate" else "object_slots"
                    })
                else:
                    name = self.edit_refs["name"].get().strip() or "creature"
                    if sc_type == "slots":
                        default_header = f"{name} is a @level spellcaster. Its spellcasting ability is @ability (spell save {{@custom_dc}}, {{@custom_hit}} to hit with spell attacks). {name} has the following spells prepared:"
                        self.edit_data.setdefault("spellcasting", []).append({
                            "name": "Spellcasting", "type": "spellcasting", "headerEntries": [default_header], 
                            "ability": "int", "custom_dc": 10, "custom_hit": 2, "spells": {}, "displayAs": "trait"
                        })
                    else:
                        default_header = f"{name} casts one of the following spells, using @ability as the spellcasting ability (spell save {{@custom_dc}}, {{@custom_hit}} to hit with spell attacks):"
                        self.edit_data.setdefault("spellcasting", []).append({
                            "name": "Innate Spellcasting", "type": "spellcasting", "headerEntries": [default_header], 
                            "ability": "int", "custom_dc": 10, "custom_hit": 2, "displayAs": "innate"
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
            
            tk.Label(top, text="Name:", bg="#f5e6ce", font=self.body_bold, fg="black").pack(side=tk.LEFT)
            name_entry = AutoHeightText(top, canvas_to_refresh=self.edit_canvas, width=30, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
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
                dmg_m3 = re.search(r'{@h}(.*?)(w+ [a-zA-Z])', entries_str)
                if dmg_m3:
                    dmg_form_val = dmg_m3.group(1).strip()
                    entries_str = entries_str.replace(f"{{@h}}{dmg_form_val}", "{@attack_dmg}")
                else:
                    entries_str = entries_str.replace("{@h}", "{@attack_dmg}")

            found_atk = "None"
            for tag, tag_name in preprocess.INV_ATTACK_TAGS.items():
                if entries_str.startswith(tag):
                    found_atk = tag_name
                    entries_str = entries_str[len(tag):].lstrip()
                    break
                    
            tk.Label(top, text="Attack Type:", bg="#f5e6ce", font=self.body_bold, fg="black").pack(side=tk.LEFT, padx=(15, 2))
            atk_var = tk.StringVar(value=found_atk)
            atk_cb = ttk.Combobox(top, textvariable=atk_var, values=list(preprocess.ATTACK_TAGS.keys()), state="readonly", width=18)
            atk_cb.pack(side=tk.LEFT, padx=5)
            
            def remove_item():
                item_frame.pack_forget() 
                item_frame.destroy()
                self.array_refs[key].remove((name_entry, atk_var, desc_text, hit_en, reach_en, dmg_form_en, dmg_type_en))
                self.edit_inner.update_idletasks() 
                self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all"))
                
            tk.Button(top, text="X Remove", bg="#ff4d4d", fg="white", font=("Arial", 9, "bold"), command=remove_item).pack(side=tk.RIGHT)
            
            atk_params_frame = tk.Frame(item_frame, bg="#f5e6ce")
            atk_params_frame.pack(fill=tk.X, pady=2)
            
            tk.Label(atk_params_frame, text="Hit Mod:", bg="#f5e6ce", font=self.body_italic, fg="black").pack(side=tk.LEFT)
            hit_en = AutoHeightText(atk_params_frame, canvas_to_refresh=self.edit_canvas, width=5, font=self.body_font, bd=1, relief=tk.SOLID)
            hit_en.insert(0, hit_val)
            hit_en.pack(side=tk.LEFT, padx=(2, 10))
            
            tk.Label(atk_params_frame, text="Reach:", bg="#f5e6ce", font=self.body_italic, fg="black").pack(side=tk.LEFT)
            reach_en = AutoHeightText(atk_params_frame, canvas_to_refresh=self.edit_canvas, width=8, font=self.body_font, bd=1, relief=tk.SOLID)
            reach_en.insert(0, reach_val)
            reach_en.pack(side=tk.LEFT, padx=(2, 10))
            
            tk.Label(atk_params_frame, text="Dmg Formula:", bg="#f5e6ce", font=self.body_italic, fg="black").pack(side=tk.LEFT)
            dmg_form_en = AutoHeightText(atk_params_frame, canvas_to_refresh=self.edit_canvas, width=8, font=self.body_font, bd=1, relief=tk.SOLID)
            dmg_form_en.insert(0, dmg_form_val)
            dmg_form_en.pack(side=tk.LEFT, padx=(2, 10))
            
            tk.Label(atk_params_frame, text="Dmg Type:", bg="#f5e6ce", font=self.body_italic, fg="black").pack(side=tk.LEFT)
            dmg_type_en = AutoHeightText(atk_params_frame, canvas_to_refresh=self.edit_canvas, width=12, font=self.body_font, bd=1, relief=tk.SOLID)
            dmg_type_en.insert(0, dmg_type_val)
            dmg_type_en.pack(side=tk.LEFT, padx=(2, 10))

            tk.Label(item_frame, text="Description / Entries:", bg="#f5e6ce", font=self.body_italic, fg="black").pack(anchor="w", pady=(5,0))
            desc_text = AutoHeightText(item_frame, canvas_to_refresh=self.edit_canvas, height=1, font=self.body_font, wrap=tk.WORD)
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
        
        d["size"] = [preprocess.SIZE_MAP.get(self.size_var.get(), "M")]
        d["alignment"] = preprocess.ALIGN_MAP.get(self.align_var.get(), ["N"])
        d["ac"] = [int(self.edit_refs["ac"].get())] if self.edit_refs["ac"].get().isdigit() else [self.edit_refs["ac"].get()]
        hf = self.edit_refs["hp_formula"].get().strip()
        d["hp"] = {"average": preprocess.calculate_avg(hf) if hf else 10, "formula": hf}

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
            sc["headerEntries"] = [h_t.get("1.0", "end-1c").strip()]
            if not getattr(self, 'is_object_mode', False):
                sc["ability"] = ab_v.get().lower() if ab_v else "int"
                sc["custom_dc"] = int(dc_v.get()) if dc_v and dc_v.get().isdigit() else 10
                sc["custom_hit"] = int(ht_v.get()) if ht_v and ht_v.get().lstrip('+-').isdigit() else 2
                if "displayAs" not in sc:
                    sc["displayAs"] = "innate" if "innate" in sc.get("name", "").lower() else "trait"
            if "spells" in sc:
                for lvl, se in sl.items():
                    if se.get().isdigit(): sc["spells"][lvl]["slots"] = int(se.get())

        pd = []
        for ne, le, te, txt in self.dialogue_refs:
            if ne.get() or txt.get("1.0", "end-1c"): pd.append({"name": ne.get(), "location": le.get(), "time": te.get(), "entries": txt.get("1.0", "end-1c").strip().split("\n")})
        if pd: d["dialogues"] = pd
        else: d.pop("dialogues", None)

        if hasattr(self, 'creature_object_items') and self.creature_object_items:
            d["objects"] = [o["name"] for o in self.creature_object_items]
        else:
            d.pop("objects", None)

        for k, items in self.array_refs.items():
            pi = []
            for ne, av, txt, he, re_en, fe, te in items:
                desc = txt.get("1.0", "end-1c").strip().replace("@attack_hit", f"{{@hit {he.get()}}}").replace("@attack_reach", re_en.get())
                if fe.get():
                    dmg = f"{{@h}}{preprocess.calculate_avg(fe.get())} ({{@damage {fe.get()}}})" if 'd' in fe.get().lower() else f"{{@h}}{fe.get()}"
                    desc = desc.replace("{@attack_dmg}", f"{dmg} {te.get()} damage." if te.get() else f"{dmg} damage.").replace("..", ".")
                else: desc = desc.replace("{@attack_dmg}", "")
                if av.get() != "None": desc = f"{preprocess.ATTACK_TAGS[av.get()]} {desc}"
                if ne.get() or desc: pi.append({"name": ne.get(), "entries": json.loads(desc) if desc.startswith("[") else desc.split("\n")})
            if pi: d[k] = pi
            else: d.pop(k, None)

        save_cb(m_dir, d)

    def _cancel_edit(self, cancel_cb):
        self.edit_container.pack_forget(); self.view_container.pack(fill=tk.BOTH, expand=True); cancel_cb()

    def insert_text_with_links(self, text, base_tags):
        base_tags = (base_tags,) if isinstance(base_tags, str) else base_tags
        pattern = r'(«(?:SPELL|MONSTER|NPC|COMBAT|EVENT|OBJECT|LOCATION|CONDITION):[^»]+»)'
        tag_map = {
            "SPELL": "SPELL_TAG", "MONSTER": "LOC_MON_TAG", "NPC": "LOC_NPC_TAG",
            "COMBAT": "LOC_COMBAT_TAG", "EVENT": "LOC_EVT_TAG", "OBJECT": "LOC_OBJ_TAG",
            "LOCATION": "LOC_CONN_TAG", "CONDITION": "CONDITION_TAG"
        }
        
        for part in re.split(pattern, text):
            if part.startswith("«") and part.endswith("»"):
                content = part[1:-1]
                if ":" in content:
                    t_type, t_val = content.split(":", 1)
                    prefix = tag_map.get(t_type.upper(), "SPELL_TAG")
                    self.text.insert(tk.END, t_val, base_tags + ("spell_link", f"{prefix}:{t_val}"))
                else:
                    self.text.insert(tk.END, content, base_tags)
            elif part:
                self.text.insert(tk.END, part, base_tags)

    def extract_entries(self, entries):
        if not entries: return ""
        if isinstance(entries, str): return clean_5etools_text_with_conditions(entries) + "\n"
        out = ""
        for entry in entries:
            if isinstance(entry, str): out += clean_5etools_text_with_conditions(entry) + "\n"
            elif isinstance(entry, dict):
                if entry.get("type") == "list":
                    for item in entry.get("items", []): 
                        out += f"• {self.extract_entries([item]).strip()}\n"
                elif entry.get("type") == "item" or "entry" in entry:
                    item_str = ""
                    if "name" in entry:
                        item_str += f"{clean_5etools_text_with_conditions(entry['name'])}. "
                    if "entry" in entry:
                        if isinstance(entry["entry"], str):
                            item_str += clean_5etools_text_with_conditions(entry["entry"])
                        elif isinstance(entry["entry"], list):
                            item_str += self.extract_entries(entry["entry"]).strip()
                    out += item_str + "\n"
                elif "entries" in entry:
                    if "name" in entry: out += f"{clean_5etools_text_with_conditions(entry['name'])}. "
                    out += self.extract_entries(entry["entries"])
        return out

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
            if not mod: mod = preprocess.calculate_modifier(score)
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
            name = clean_5etools_text_with_conditions(sc.get("name", "Spellcasting"))
            self.text.insert(tk.END, f"{name}. ", "bold") 
            
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
                
            header_text = " ".join([clean_5etools_text_with_conditions(h) for h in formatted_headers])
            self.insert_text_with_links(f"{header_text}\n", "body")
            
            if "will" in sc:
                spells = ", ".join([clean_5etools_text_with_conditions(s) for s in sc["will"]])
                self.insert_text_with_links(f"• At will: {spells}\n", "body_indented")
            if "daily" in sc:
                for freq, spells_list in sc["daily"].items():
                    freq_num = freq[0]
                    each = " each" if freq.endswith("e") else ""
                    spells = ", ".join([clean_5etools_text_with_conditions(s) for s in spells_list])
                    self.insert_text_with_links(f"• {freq_num}/day{each}: {spells}\n", "body_indented")
            if "spells" in sc:
                levels = {"0": "Cantrips (at will)", "1": "1st level", "2": "2nd level", "3": "3rd level", "4": "4th level", "5": "5th level", "6": "6th level", "7": "7th level", "8": "8th level", "9": "9th level"}
                for level in range(10):
                    str_level = str(level)
                    if str_level in sc["spells"]:
                        level_data = sc["spells"][str_level]
                        lvl_str = levels.get(str_level, f"{level} level")
                        slots = level_data.get("slots")
                        if slots: lvl_str += f" ({slots} slots)"
                        spells = ", ".join([clean_5etools_text_with_conditions(s) for s in level_data.get("spells", [])])
                        self.insert_text_with_links(f"• {lvl_str}: {spells}\n", "body_indented")
            self.text.insert(tk.END, "\n")

    def _render_section(self, entries_list):
        if not entries_list: return
        for item in entries_list:
            name = item.get("name", "")
            if name: self.text.insert(tk.END, f"{clean_5etools_text_with_conditions(name)}. ", "bold")
            content = self.extract_entries(item.get("entries", []))
            self.insert_text_with_links(content, "body")
            self.text.insert(tk.END, "\n")

    def render_monster(self, data, back_cb=None):
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
            if "from" in ac: ac_val += f" ({clean_5etools_text_with_conditions(', '.join(ac['from']))})"
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
            self.text.insert(tk.END, f"{preprocess.parse_complex_list(data['resist'])}\n", "body")
        if "immune" in data:
            self.text.insert(tk.END, "Damage Immunities: ", "bold")
            self.text.insert(tk.END, f"{preprocess.parse_complex_list(data['immune'])}\n", "body")
        if "conditionImmune" in data:
            self.text.insert(tk.END, "Condition Immunities: ", "bold")
            self.text.insert(tk.END, f"{preprocess.parse_complex_list(data['conditionImmune'])}\n", "body")
        if "senses" in data:
            senses = preprocess.parse_complex_list(data["senses"])
            passive = data.get("passive", 10)
            self.text.insert(tk.END, "Senses: ", "bold")
            self.text.insert(tk.END, f"{senses}, passive Perception {passive}\n", "body")
        if "languages" in data:
            self.text.insert(tk.END, "Languages: ", "bold")
            self.text.insert(tk.END, f"{preprocess.parse_complex_list(data['languages'])}\n", "body")
            
        if "level" in data and data["level"] not in ["", None]:
            self.text.insert(tk.END, "Level: ", "bold")
            self.text.insert(tk.END, f"{data['level']}\n", "body")
        if "cr" in data and data["cr"] not in ["", None, "—"]:
            cr_val = data["cr"].get("cr", data["cr"]) if isinstance(data["cr"], dict) else data["cr"]
            self.text.insert(tk.END, "CR: ", "bold")
            self.text.insert(tk.END, f"{cr_val}\n", "body")

        global_level = data.get("level", 1)
        dialogues = data.get("dialogues", [])

        if dialogues:
            self.text.insert(tk.END, "Dialogues\n", "section_header")
            self.insert_divider()
            for d in dialogues:
                self.text.insert(tk.END, f"{clean_5etools_text_with_conditions(d.get('name', 'Dialogue'))}\n", "bold")
                loc = d.get('location', '')
                time_val = d.get('time', '')
                if loc or time_val:
                    self.text.insert(tk.END, f"Location: {loc} | Event: {time_val}\n", "body")
                self.insert_text_with_links(self.extract_entries(d.get("entries", [])), "body")
                self.text.insert(tk.END, "\n")

        objects = data.get("objects", [])
        if objects:
            self.text.insert(tk.END, "Objects\n", "section_header")
            self.insert_divider()
            for o_name in objects:
                self.text.insert(tk.END, "• ")
                self.text.insert(tk.END, o_name, ("spell_link", f"LOC_OBJ_TAG:{o_name}"))
                self.text.insert(tk.END, "\n", "body")
            self.text.insert(tk.END, "\n")

        sc_data = data.get("spellcasting", [])
        sc_traits = [sc for sc in sc_data if sc.get("displayAs", "trait") in ["trait", "object_slots"] and "innate" not in sc.get("name", "").lower()]
        sc_actions = [sc for sc in sc_data if sc.get("displayAs") in ["action", "object_innate", "innate"] or "innate" in sc.get("name", "").lower()]
        sc_bonus = [sc for sc in sc_data if sc.get("displayAs") == "bonus"]
        sc_reactions = [sc for sc in sc_data if sc.get("displayAs") == "reaction"]

        if data.get("trait") or sc_traits:
            self.text.insert(tk.END, "Traits\n", "section_header")
            self.insert_divider()
            if sc_traits: self._render_spellcasting(sc_traits, global_level)
            if data.get("trait"): self._render_section(data["trait"])
                
        if data.get("action") or sc_actions:
            self.text.insert(tk.END, "Actions\n", "section_header")
            self.insert_divider()
            if sc_actions: self._render_spellcasting(sc_actions, global_level)
            if data.get("action"): self._render_section(data["action"])
                
        if data.get("bonus") or sc_bonus:
            self.text.insert(tk.END, "Bonus actions\n", "section_header")
            self.insert_divider()
            if sc_bonus: self._render_spellcasting(sc_bonus, global_level)
            if data.get("bonus"): self._render_section(data["bonus"])
                
        if data.get("reaction") or sc_reactions:
            self.text.insert(tk.END, "Reactions\n", "section_header")
            self.insert_divider()
            if sc_reactions: self._render_spellcasting(sc_reactions, global_level)
            if data.get("reaction"): self._render_section(data["reaction"])
        
        if "legendary" in data:
            self.text.insert(tk.END, "Legendary actions\n", "section_header")
            self.insert_divider()
            self._render_section(data["legendary"])

        self.text.config(state=tk.DISABLED)

    def render_spell(self, data, back_callback=None):
        self.clear_overlays()
        self.edit_container.pack_forget()
        self.view_container.pack(fill=tk.BOTH, expand=True)

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
            time_str += f", {clean_5etools_text_with_conditions(time_data['condition'])}"
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
            en = AutoHeightText(base_f, canvas_to_refresh=self.edit_canvas, width=w, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
            en.insert(0, str(self.edit_data.get(key, ""))); en.grid(row=r, column=1, sticky="w", padx=5, pady=2); self.edit_refs[key] = en

        r = 4; tk.Label(base_f, text="School:", bg="#fdf1dc", font=self.body_bold).grid(row=r, column=0, sticky="e", padx=5, pady=2)
        self.spell_school_var = tk.StringVar(value=preprocess.SCHOOL_MAP.get(self.edit_data.get("school", "A"), "Abjuration"))
        ttk.Combobox(base_f, textvariable=self.spell_school_var, values=list(preprocess.SCHOOL_MAP.values()), state="readonly", width=15).grid(row=r, column=1, sticky="w", padx=5, pady=2); r+=1

        tm = self.edit_data.get("time", [{}])[0]; tk.Label(base_f, text="Cast Time:", bg="#fdf1dc", font=self.body_bold).grid(row=r, column=0, sticky="e", padx=5, pady=2)
        tf = tk.Frame(base_f, bg="#fdf1dc"); tf.grid(row=r, column=1, sticky="w", padx=5, pady=2); r+=1
        self.t_num_var = AutoHeightText(tf, canvas_to_refresh=self.edit_canvas, width=5, font=self.body_font, bd=1, relief=tk.SOLID)
        self.t_num_var.insert(0, str(tm.get("number", 1))); self.t_num_var.pack(side=tk.LEFT)
        self.t_unit_var = tk.StringVar(value=tm.get("unit", "action")); ttk.Combobox(tf, textvariable=self.t_unit_var, values=["action", "bonus", "reaction", "minute", "hour"], state="readonly", width=10).pack(side=tk.LEFT, padx=5)
        self.t_cond_var = AutoHeightText(tf, canvas_to_refresh=self.edit_canvas, width=25, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
        self.t_cond_var.insert(0, tm.get("condition", "")); self.t_cond_var.pack(side=tk.LEFT, padx=5)

        rg = self.edit_data.get("range", {}); dst = rg.get("distance", {}); tk.Label(base_f, text="Range:", bg="#fdf1dc", font=self.body_bold).grid(row=r, column=0, sticky="e", padx=5, pady=2)
        rf = tk.Frame(base_f, bg="#fdf1dc"); rf.grid(row=r, column=1, sticky="w", padx=5, pady=2); r+=1
        self.r_type_var = tk.StringVar(value=rg.get("type", "point")); ttk.Combobox(rf, textvariable=self.r_type_var, values=["point", "cone", "cube", "cylinder", "line", "sphere", "hemisphere", "radius"], state="readonly", width=10).pack(side=tk.LEFT)
        self.r_amt_var = AutoHeightText(rf, canvas_to_refresh=self.edit_canvas, width=5, font=self.body_font, bd=1, relief=tk.SOLID)
        self.r_amt_var.insert(0, str(dst.get("amount", ""))); self.r_amt_var.pack(side=tk.LEFT, padx=2)
        self.r_unit_var = tk.StringVar(value=dst.get("type", "feet")); ttk.Combobox(rf, textvariable=self.r_unit_var, values=["feet", "miles", "touch", "self", "sight", "unlimited"], state="readonly", width=8).pack(side=tk.LEFT, padx=5)

        cp = self.edit_data.get("components", {}); tk.Label(base_f, text="Components:", bg="#fdf1dc", font=self.body_bold).grid(row=r, column=0, sticky="e", padx=5, pady=2)
        cf = tk.Frame(base_f, bg="#fdf1dc"); cf.grid(row=r, column=1, sticky="w", padx=5, pady=2); r+=1
        self.c_v_var = tk.BooleanVar(value="v" in cp); tk.Checkbutton(cf, text="V", variable=self.c_v_var, bg="#fdf1dc").pack(side=tk.LEFT)
        self.c_s_var = tk.BooleanVar(value="s" in cp); tk.Checkbutton(cf, text="S", variable=self.c_s_var, bg="#fdf1dc").pack(side=tk.LEFT)
        self.c_m_var = AutoHeightText(cf, canvas_to_refresh=self.edit_canvas, width=30, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
        self.c_m_var.insert(0, cp["m"].get("text", cp["m"].get("item","")) if isinstance(cp.get("m"), dict) else cp.get("m","")); self.c_m_var.pack(side=tk.LEFT, padx=5)

        dr = self.edit_data.get("duration", [{}])[0]; tk.Label(base_f, text="Duration:", bg="#fdf1dc", font=self.body_bold).grid(row=r, column=0, sticky="e", padx=5, pady=2)
        df = tk.Frame(base_f, bg="#fdf1dc"); df.grid(row=r, column=1, sticky="w", padx=5, pady=2)
        self.d_type_var = tk.StringVar(value=dr.get("type", "timed")); ttk.Combobox(df, textvariable=self.d_type_var, values=["timed", "instant", "permanent", "special"], state="readonly", width=10).pack(side=tk.LEFT)
        self.d_amt_var = AutoHeightText(df, canvas_to_refresh=self.edit_canvas, width=5, font=self.body_font, bd=1, relief=tk.SOLID)
        self.d_amt_var.insert(0, str(dr.get("duration", {}).get("amount", "1"))); self.d_amt_var.pack(side=tk.LEFT, padx=2)
        self.d_unit_var = tk.StringVar(value=dr.get("duration", {}).get("type", "minute")); ttk.Combobox(df, textvariable=self.d_unit_var, values=["round", "minute", "hour", "day"], state="readonly", width=8).pack(side=tk.LEFT, padx=5)
        self.d_conc_var = tk.BooleanVar(value=dr.get("concentration", False)); tk.Checkbutton(df, text="Concentration", variable=self.d_conc_var, bg="#fdf1dc").pack(side=tk.LEFT)

        tk.Label(self.edit_inner, text="Description:", bg="#fdf1dc", font=self.body_bold).pack(anchor="w", padx=5)
        self.spell_desc_text = AutoHeightText(self.edit_inner, canvas_to_refresh=self.edit_canvas, height=1, font=self.body_font, wrap=tk.WORD)
        self.spell_desc_text.insert("1.0", "\n".join([json.dumps(e) if isinstance(e, dict) else e for e in self.edit_data.get("entries", [])]) if isinstance(self.edit_data.get("entries"), list) else str(self.edit_data.get("entries","")))
        self.spell_desc_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _handle_spell_save(self, save_cb):
        d = self.edit_data; d["name"] = self.edit_refs["name"].get().strip(); d["source"] = self.edit_refs["source"].get().strip()
        d["level"] = int(self.edit_refs["level"].get().strip()) if self.edit_refs["level"].get().strip().isdigit() else 0
        if self.edit_refs["page"].get().strip().isdigit(): d["page"] = int(self.edit_refs["page"].get().strip())
        
        d["school"] = preprocess.INV_SCHOOL_MAP.get(self.spell_school_var.get(), "A")
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

    def _show_condition_helper(self, cond_name):
        key = cond_name.lower().strip()
        desc = CONDITIONS_DB.get(key, "No description available for this condition.")
        
        top = tk.Toplevel(self)
        top.title(f"Condition: {cond_name.title()}")
        top.geometry("450x350")
        top.configure(bg="#fdf1dc")
        
        lbl_title = tk.Label(top, text=cond_name.title(), font=("Georgia", 16, "bold"), fg="#58180d", bg="#fdf1dc", pady=10)
        lbl_title.pack()
        
        txt_frame = tk.Frame(top, bg="#fdf1dc", padx=15, pady=5)
        txt_frame.pack(fill=tk.BOTH, expand=True)
        
        scroll = ttk.Scrollbar(txt_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        txt = tk.Text(txt_frame, font=("Times", 12), wrap=tk.WORD, bg="#fae6c5", fg="black", bd=1, relief=tk.SOLID, yscrollcommand=scroll.set)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=txt.yview)
        
        txt.insert("1.0", desc)
        txt.config(state=tk.DISABLED)
        
        btn_close = tk.Button(top, text="Close", font=("Arial", 10, "bold"), bg="#58180d", fg="white", command=top.destroy, pady=5)
        btn_close.pack(pady=10)

    def _on_spell_click(self, event):
        idx = self.text.index(f"@{event.x},{event.y}")
        for t in self.text.tag_names(idx):
            if t.startswith("SPELL_TAG:"):
                if self.spell_callback: self.spell_callback(t.split(":", 1)[1])
                break
            elif t.startswith("CONDITION_TAG:"):
                self._show_condition_helper(t.split(":", 1)[1])
                break
            elif t.startswith("LOC_MON_TAG:"):
                if hasattr(self, 'location_link_callback') and self.location_link_callback:
                    self.location_link_callback(t.split(":", 1)[1], "Monsters")
                break
            elif t.startswith("LOC_NPC_TAG:"):
                if hasattr(self, 'location_link_callback') and self.location_link_callback:
                    self.location_link_callback(t.split(":", 1)[1], "NPCs")
                break
            elif t.startswith("LOC_COMBAT_TAG:"):
                if hasattr(self, 'location_link_callback') and self.location_link_callback:
                    self.location_link_callback(t.split(":", 1)[1], "Combats")
                break
            elif t.startswith("LOC_EVT_TAG:"):
                if hasattr(self, 'location_link_callback') and self.location_link_callback:
                    self.location_link_callback(t.split(":", 1)[1], "Events")
                break
            elif t.startswith("LOC_OBJ_TAG:"):
                if hasattr(self, 'location_link_callback') and self.location_link_callback:
                    self.location_link_callback(t.split(":", 1)[1], "Objects")
                break
            elif t.startswith("LOC_CONN_TAG:"):
                if hasattr(self, 'location_link_callback') and self.location_link_callback:
                    self.location_link_callback(t.split(":", 1)[1], "Locations")
                break

    def set_location_link_callback(self, cb):
        self.location_link_callback = cb

    def add_location_top_buttons(self, l_dir, edit_cb):
        self.clear_overlays()
        b_edit = tk.Button(self.view_container, text="EDIT", bg="#8a8a8a", fg="white", font=("Georgia", 10, "bold"), command=lambda: edit_cb(l_dir))
        b_edit.place(relx=1.0, x=-100, y=10, width=80, height=30)
        self.overlay_buttons.append(b_edit)

    def render_object(self, data, back_cb=None):
        self.clear_overlays()
        self.edit_container.pack_forget()
        self.view_container.pack(fill=tk.BOTH, expand=True)

        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.dividers.clear()

        self.text.insert(tk.END, data.get("name", "Unknown Object") + "\n", "title")
        
        source = data.get("source", "")
        page = data.get("page", "")
        src_str = f"{source} p. {page}\n" if page else f"{source}\n" if source else ""
        if src_str:
            self.text.insert(tk.END, src_str, "subtitle")

        i_type = "Wondrous Item" if data.get("wondrous") else data.get("type", "Wondrous Item")
        rarity = str(data.get("rarity", "Common")).title()
        
        req_attune = data.get("reqAttune") or data.get("attunement_details")
        attune_str = ""
        if data.get("attunement") or req_attune:
            if isinstance(req_attune, str) and req_attune.strip() and req_attune.strip().lower() != "true":
                attune_text = req_attune.strip()
                if attune_text.lower().startswith("by "):
                    attune_text = "By " + attune_text[3:]
                attune_str = f" (Requires Attunement {attune_text})"
            else:
                attune_str = " (Requires Attunement)"
                
        # FIXED: Changed from unconfigured "body_bold" tag to the configured "bold" tag
        self.text.insert(tk.END, f"{i_type}, {rarity}{attune_str}\n", "subtitle")
        self.insert_divider()

        desc_list = data.get("entries", []) or data.get("description", [])
        if isinstance(desc_list, str):
            desc_list = [desc_list]
            
        if desc_list:
            for entry in desc_list:
                # Routes processing through the recursive layout element walker
                self._render_custom_entry_element(entry)

        effect = data.get("effect", "")
        if effect:
            self.text.insert(tk.END, "Effect\n", "section_header")
            self.insert_divider()
            self.insert_text_with_links(effect + "\n\n", "body")

        owners = data.get("owners", [])
        if owners:
            self.text.insert(tk.END, "Owner(s)\n", "section_header")
            self.insert_divider()
            for o in owners:
                self.text.insert(tk.END, "• ")
                self.text.insert(tk.END, o, ("spell_link", f"LOC_NPC_TAG:{o}"))
                self.text.insert(tk.END, "\n", "body")
            self.text.insert(tk.END, "\n")

        global_level = data.get("level", 1)
        sc_data = data.get("spellcasting", [])
        sc_traits = [sc for sc in sc_data if sc.get("displayAs", "trait") in ["trait", "object_slots"] and "innate" not in sc.get("name", "").lower()]
        sc_actions = [sc for sc in sc_data if sc.get("displayAs") in ["action", "object_innate", "innate"] or "innate" in sc.get("name", "").lower()]

        if data.get("trait") or sc_traits:
            self.text.insert(tk.END, "Traits\n", "section_header")
            self.insert_divider()
            if sc_traits: self._render_spellcasting(sc_traits, global_level)
            if data.get("trait"): self._render_section(data["trait"])
                
        if data.get("action") or sc_actions:
            self.text.insert(tk.END, "Actions\n", "section_header")
            self.insert_divider()
            if sc_actions: self._render_spellcasting(sc_actions, global_level)
            if data.get("action"): self._render_section(data["action"])

        self.text.config(state=tk.DISABLED)

    def render_object_edit_mode(self, data, save_callback, cancel_callback, add_existing_npc_cb):
        self.clear_overlays()
        self.view_container.pack_forget()
        self.edit_container.pack(fill=tk.BOTH, expand=True)
        for widget in self.edit_inner.winfo_children(): widget.destroy()

        self.is_object_mode = True
        self.edit_data = copy.deepcopy(data)
        self.original_object_name = self.edit_data.get("name", "Unknown Object")
        for k in ["owners", "trait", "action", "spellcasting"]:
            self.edit_data.setdefault(k, [])

        self.array_refs = {}
        self.sc_refs = []
        self.rebuild_sc_hooks = []

        top_frame = tk.Frame(self.edit_inner, bg="#fdf1dc")
        top_frame.pack(fill=tk.X, pady=(0, 20))
        tk.Label(top_frame, text="EDIT OBJECT PROFILE", font=self.header_font, fg="#58180d", bg="#fdf1dc").pack(side=tk.LEFT)
        
        owner_items = []
        
        def sync_all_sc():
            for sc_dict_ref, _, ab_var, dc_var, hit_var, slots_entries in self.sc_refs:
                try:
                    if getattr(self, 'is_object_mode', False):
                        sc_dict_ref["name"] = "Spellcasting"
                except Exception: pass

        def rebuild_all_sc():
            sync_all_sc()
            self.sc_refs.clear()
            for hook in self.rebuild_sc_hooks: hook()
            self._optimize_and_refresh_layout()

        def handle_save():
            self.edit_data["name"] = name_entry.get().strip()
            self.edit_data["source"] = source_entry.get().strip()
            
            p_val = page_entry.get().strip()
            if p_val.isdigit(): self.edit_data["page"] = int(p_val)
            elif "page" in self.edit_data: self.edit_data.pop("page", None)
                
            self.edit_data["type"] = type_entry.get().strip()
            self.edit_data["rarity"] = rarity_entry.get().strip().lower()
            
            # --- Synchronize Decomposed Attunement Fields Safely ---
            is_attuned = bool(attune_var.get())
            try:
                detail_txt = attune_details_entry.get("1.0", "end-1c").strip()
            except:
                detail_txt = attune_details_entry.get().strip()
                
            self.edit_data["attunement"] = is_attuned
            self.edit_data["attunement_details"] = detail_txt if is_attuned else ""
            if is_attuned:
                self.edit_data["reqAttune"] = detail_txt if detail_txt else True
            else:
                self.edit_data["reqAttune"] = False

            desc_val = desc_text.get("1.0", "end-1c").strip()
            self.edit_data["entries"] = [line for line in desc_val.split("\n") if line]
            
            self.edit_data["effect"] = effect_text.get("1.0", "end-1c").strip()
            self.edit_data["owners"] = [o["name"] for o in owner_items]
            sync_all_sc()
            
            for k, items in self.array_refs.items():
                pi = []
                for ne, av, txt, he, re_en, fe, te in items:
                    desc = txt.get("1.0", "end-1c").strip().replace("@attack_hit", f"{{@hit {he.get()}}}").replace("@attack_reach", re_en.get())
                    if fe.get():
                        dmg = f"{{@h}}{preprocess.calculate_avg(fe.get())} ({{@damage {fe.get()}}})" if 'd' in fe.get().lower() else f"{{@h}}{fe.get()}"
                        desc = desc.replace("{@attack_dmg}", f"{dmg} {te.get()} damage." if te.get() else f"{dmg} damage.").replace("..", ".")
                    else: desc = desc.replace("{@attack_dmg}", "")
                    if av.get() != "None": desc = f"{preprocess.ATTACK_TAGS[av.get()]} {desc}"
                    if ne.get() or desc: pi.append({"name": ne.get(), "entries": json.loads(desc) if desc.startswith("[") else desc.split("\n")})
                if pi: self.edit_data[k] = pi
                else: self.edit_data.pop(k, None)
                
            save_callback(self.original_object_name, self.edit_data)

        tk.Button(top_frame, text="SAVE", bg="#4a90e2", fg="white", font=("Georgia", 10, "bold"), command=handle_save).pack(side=tk.RIGHT, padx=5)
        tk.Button(top_frame, text="CANCEL", bg="#58180d", fg="white", font=("Georgia", 10, "bold"), command=lambda: self._cancel_edit(cancel_callback)).pack(side=tk.RIGHT, padx=5)

        basic_frame = tk.Frame(self.edit_inner, bg="#fdf1dc")
        basic_frame.pack(fill=tk.X, pady=10)
        
        # Grid Field Generation Matrix Array Loop
        fields = [
            ("Name:", "name", self.edit_data.get("name", self.original_object_name), 50),
            ("Source:", "source", self.edit_data.get("source", "Custom"), 50),
            ("Page:", "page", str(self.edit_data.get("page", "")), 10),
            ("Type:", "type", "Wondrous Item" if self.edit_data.get("wondrous") else self.edit_data.get("type", "Wondrous Item"), 50),
            ("Rarity:", "rarity", str(self.edit_data.get("rarity", "Common")).title(), 50)
        ]
        
        refs = {}
        for idx, (label_txt, dict_key, initial_val, width_val) in enumerate(fields):
            tk.Label(basic_frame, text=label_txt, bg="#fdf1dc", font=self.body_bold, fg="black").grid(row=idx, column=0, sticky="e", padx=5, pady=2)
            en = AutoHeightText(basic_frame, canvas_to_refresh=self.edit_canvas, width=width_val, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
            en.insert(0, str(initial_val))
            en.grid(row=idx, column=1, sticky="w", padx=5, pady=2)
            refs[dict_key] = en
            
        name_entry, source_entry, page_entry, type_entry, rarity_entry = refs["name"], refs["source"], refs["page"], refs["type"], refs["rarity"]

        # --- Explicit Decomposed Attunement Grid Row Creation (Row 5) ---
        tk.Label(basic_frame, text="Attunement:", bg="#fdf1dc", font=self.body_bold, fg="black").grid(row=5, column=0, sticky="e", padx=5, pady=2)
        attune_frame = tk.Frame(basic_frame, bg="#fdf1dc")
        attune_frame.grid(row=5, column=1, sticky="w", padx=5, pady=2)

        # Deconstruct boolean initial checking state
        has_attune_init = bool(self.edit_data.get("attunement") or self.edit_data.get("reqAttune"))
        attune_var = tk.BooleanVar(value=has_attune_init)
        attune_chk = tk.Checkbutton(attune_frame, variable=attune_var, bg="#fdf1dc", activebackground="#fdf1dc")
        attune_chk.pack(side=tk.LEFT)

        # Deconstruct initial textual requirements strings
        init_details = self.edit_data.get("attunement_details", "")
        if not init_details and isinstance(self.edit_data.get("reqAttune"), str):
            init_details = self.edit_data["reqAttune"]

        attune_details_entry = AutoHeightText(attune_frame, canvas_to_refresh=self.edit_canvas, width=40, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
        attune_details_entry.insert(0, str(init_details))
        attune_details_entry.pack(side=tk.LEFT, padx=(5, 0))

        # Adjust the description and effect row layouts to populate next sequence indices (Rows 6 & 7)
        tk.Label(basic_frame, text="Description Entries:", bg="#fdf1dc", font=self.body_bold, fg="black").grid(row=6, column=0, sticky="ne", padx=5, pady=2)
        desc_text = AutoHeightText(basic_frame, canvas_to_refresh=self.edit_canvas, width=60, height=1, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
        
        raw_entries = self.edit_data.get("entries", [])
        desc_init = "\n".join(raw_entries) if isinstance(raw_entries, list) else str(raw_entries)
        desc_text.insert("1.0", desc_init)
        desc_text.grid(row=6, column=1, sticky="w", padx=5, pady=2)

        tk.Label(basic_frame, text="Effect Summary:", bg="#fdf1dc", font=self.body_bold, fg="black").grid(row=7, column=0, sticky="ne", padx=5, pady=2)
        effect_text = AutoHeightText(basic_frame, canvas_to_refresh=self.edit_canvas, width=60, height=1, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
        effect_text.insert("1.0", self.edit_data.get("effect", ""))
        effect_text.grid(row=7, column=1, sticky="w", padx=5, pady=2)

        def make_section(title_text):
            sec_frame = tk.Frame(self.edit_inner, bg="#fdf1dc", pady=5)
            sec_frame.pack(fill=tk.X)
            hdr_frame = tk.Frame(sec_frame, bg="#fdf1dc")
            hdr_frame.pack(fill=tk.X)
            tk.Label(hdr_frame, text=title_text, font=self.body_bold, bg="#fdf1dc", fg="#7a200d").pack(side=tk.LEFT)
            list_frame = tk.Frame(sec_frame, bg="#fdf1dc")
            list_frame.pack(fill=tk.X)
            return hdr_frame, list_frame

        def draw_simple_row(list_frame, name, storage_list):
            row = tk.Frame(list_frame, bg="#e0cbb0", pady=4, padx=10, bd=1, relief=tk.SOLID)
            row.pack(fill=tk.X, pady=2)
            item_dict = {"name": name, "frame": row}
            storage_list.append(item_dict)
            tk.Button(row, text="X", bg="#ff4d4d", fg="white", font=("Arial", 8, "bold"), command=lambda: (row.pack_forget(), row.destroy(), storage_list.remove(item_dict), self.edit_inner.update_idletasks(), self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all")))).pack(side=tk.RIGHT)
            tk.Label(row, text=name, font=self.body_bold, bg="#e0cbb0", fg="black", anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.edit_inner.update_idletasks()
            self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all"))

        o_hdr, o_lst = make_section("Owner(s):")
        tk.Button(o_hdr, text="+ Add Owner", bg="#d9ad6c", font=("Arial", 8, "bold"), command=lambda: add_existing_npc_cb(lambda n: draw_simple_row(o_lst, n, owner_items))).pack(side=tk.LEFT, padx=5)
        for o in self.edit_data.get("owners", []): 
            draw_simple_row(o_lst, o, owner_items)

        self.arrays_frame = tk.Frame(self.edit_inner, bg="#fdf1dc")
        self.arrays_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        for sec_key, sec_title in [("trait", "Traits"), ("action", "Actions")]:
            self.build_array_section(sec_key, sec_title, rebuild_all_sc, sync_all_sc)
            
        rebuild_all_sc()
        self.edit_inner.update_idletasks()
        self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all"))

    def _insert_text_with_links_to_widget(self, widget, text, base_tags):
        base_tags = (base_tags,) if isinstance(base_tags, str) else base_tags
        pattern = r'(«(?:SPELL|MONSTER|NPC|COMBAT|EVENT|OBJECT|LOCATION|CONDITION):[^»]+»)'
        tag_map = {
            "SPELL": "SPELL_TAG", "MONSTER": "LOC_MON_TAG", "NPC": "LOC_NPC_TAG",
            "COMBAT": "LOC_COMBAT_TAG", "EVENT": "LOC_EVT_TAG", "OBJECT": "LOC_OBJ_TAG",
            "LOCATION": "LOC_CONN_TAG", "CONDITION": "CONDITION_TAG"
        }
        for part in re.split(pattern, text):
            if part.startswith("«") and part.endswith("»"):
                content = part[1:-1]
                if ":" in content:
                    t_type, t_val = content.split(":", 1)
                    prefix = tag_map.get(t_type.upper(), "SPELL_TAG")
                    widget.insert(tk.END, t_val, base_tags + ("spell_link", f"{prefix}:{t_val}"))
                else:
                    widget.insert(tk.END, content, base_tags)
            elif part:
                widget.insert(tk.END, part, base_tags)

    def _handle_cell_link_hover(self, event, widget):
        idx = widget.index(f"@{event.x},{event.y}")
        tags = widget.tag_names(idx)
        target_tag = None
        valid_prefixes = ["SPELL_TAG:", "CONDITION_TAG:", "LOC_MON_TAG:", "LOC_NPC_TAG:", "LOC_COMBAT_TAG:", "LOC_EVT_TAG:", "LOC_OBJ_TAG:", "LOC_CONN_TAG:"]
        for t in tags:
            if ":" in t and any(t.startswith(p) for p in valid_prefixes):
                target_tag = t
                break
        if not target_tag:
            self._on_link_leave(None)
            return

        scr_w, scr_h = self.winfo_screenwidth(), self.winfo_screenheight()
        popup_w, popup_h = int(scr_w * 2 / 5), int(scr_h * 2 / 5)
        x_pos = event.x_root + 15 if event.x_root < (scr_w / 2) else event.x_root - popup_w - 15
        y_pos = event.y_root + 15 if event.y_root < (scr_h / 2) else event.y_root - popup_h - 15

        if hasattr(self, "_hover_target") and self._hover_target == target_tag:
            if hasattr(self, "_hover_popup") and self._hover_popup:
                self._hover_popup.geometry(f"{popup_w}x{popup_h}+{x_pos}+{y_pos}")
            return

        self._on_link_leave(None)
        self._hover_target = target_tag
        prefix, name = target_tag.split(":", 1)
        
        popup = tk.Toplevel(self)
        popup.is_hover_popup = True  
        popup.wm_overrideredirect(True)
        popup.configure(bg="#fdf1dc", bd=2, relief=tk.SOLID)
        popup.geometry(f"{popup_w}x{popup_h}+{x_pos}+{y_pos}")
        self._hover_popup = popup

        if prefix == "CONDITION_TAG":
            from stat_renderer import CONDITIONS_DB
            desc = CONDITIONS_DB.get(name.lower().strip(), "No description available.")
            txt = tk.Text(popup, font=("Times", 12), wrap=tk.WORD, bg="#fdf1dc", bd=0, highlightthickness=0)
            txt.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
            txt.insert("1.0", name.title(), "title")
            txt.tag_configure("title", font=("Georgia", 14, "bold"), foreground="#58180d")
            txt.insert(tk.END, f"\n\n{desc}")
            txt.config(state=tk.DISABLED)
            popup.target_text_widget = txt
        else:
            toplevel = self.winfo_toplevel()
            if hasattr(toplevel, "resolve_hover_data"):
                data, dtype = toplevel.resolve_hover_data(prefix, name)
                if data:
                    mini_viewer = StatBlockRenderer(popup)
                    mini_viewer.pack(fill=tk.BOTH, expand=True)
                    mini_viewer.clear_overlays()
                    mini_viewer.text.adjust_height = lambda: None
                    mini_viewer.text.configure(height=1)
                    if dtype == "spell": mini_viewer.render_spell(data)
                    elif dtype in ["monster", "npc"]: mini_viewer.render_monster(data)
                    elif dtype == "location": mini_viewer.render_location(data)
                    elif dtype == "event": mini_viewer.render_event(data)
                    elif dtype == "object": mini_viewer.render_object(data)
                    popup.target_text_widget = mini_viewer.text
                else:
                    tk.Label(popup, text=f"Profile '{name}' not found.", bg="#fdf1dc", font=("Arial", 11, "italic")).pack(padx=20, pady=20)

    def _on_cell_link_click(self, event, widget):
        idx = widget.index(f"@{event.x},{event.y}")
        for t in widget.tag_names(idx):
            if t.startswith("SPELL_TAG:"):
                if self.spell_callback: self.spell_callback(t.split(":", 1)[1])
                break
            elif t.startswith("CONDITION_TAG:"):
                self._show_condition_helper(t.split(":", 1)[1])
                break
            elif t.startswith("LOC_MON_TAG:"):
                if hasattr(self, 'location_link_callback') and self.location_link_callback:
                    self.location_link_callback(t.split(":", 1)[1], "Monsters")
                break
            elif t.startswith("LOC_NPC_TAG:"):
                if hasattr(self, 'location_link_callback') and self.location_link_callback:
                    self.location_link_callback(t.split(":", 1)[1], "NPCs")
                break
            elif t.startswith("LOC_COMBAT_TAG:"):
                if hasattr(self, 'location_link_callback') and self.location_link_callback:
                    self.location_link_callback(t.split(":", 1)[1], "Combats")
                break
            elif t.startswith("LOC_EVT_TAG:"):
                if hasattr(self, 'location_link_callback') and self.location_link_callback:
                    self.location_link_callback(t.split(":", 1)[1], "Events")
                break
            elif t.startswith("LOC_OBJ_TAG:"):
                if hasattr(self, 'location_link_callback') and self.location_link_callback:
                    self.location_link_callback(t.split(":", 1)[1], "Objects")
                break
            elif t.startswith("LOC_CONN_TAG:"):
                if hasattr(self, 'location_link_callback') and self.location_link_callback:
                    self.location_link_callback(t.split(":", 1)[1], "Locations")
                break

    def _render_custom_entry_element(self, entry):
        if not entry:
            return
        if isinstance(entry, str):
            # ADDED NOTE TRANSLATION: Catches note formatting blocks inline safely
            entry = re.sub(r'{@note (.*?)}', r'\1', entry, flags=re.IGNORECASE)
            cleaned_str = preprocess.clean_5etools_text(entry)
            self.insert_text_with_links(cleaned_str + "\n\n", "body")
            return
            
        if isinstance(entry, dict):
            e_type = entry.get("type")
            
            # --- Render Nested Lists ---
            if e_type == "list":
                items = entry.get("items", [])
                cols_count = entry.get("columns", 1)
                
                # Expand list elements across multi-column grids if defined
                if isinstance(cols_count, int) and cols_count > 1:
                    list_frame = tk.Frame(self.text, bg="#fdf1dc")
                    for c_idx in range(cols_count):
                        list_frame.grid_columnconfigure(c_idx, weight=1, uniform="list_col")
                        
                    for idx, item in enumerate(items):
                        row = idx // cols_count
                        col = idx % cols_count
                        
                        raw_txt = str(item.get("entry", item) if isinstance(item, dict) else item)
                        raw_txt = re.sub(r'{@note (.*?)}', r'\1', raw_txt, flags=re.IGNORECASE)
                        cleaned_item = preprocess.clean_5etools_text(raw_txt)
                        
                        # Pack individual item cell label fields cleanly
                        cell_lbl = tk.Label(list_frame, text=f"• {cleaned_item}", font=self.body_font, bg="#fdf1dc", fg="black", anchor="w", justify=tk.LEFT, padx=10, pady=2)
                        cell_lbl.grid(row=row, column=col, sticky="w")
                        
                        # If child strings contain inline hyperlink brackets, parse mouse triggers onto them
                        if "«" in cleaned_item and "»" in cleaned_item:
                            cell_lbl.config(fg="#4a90e2", cursor="hand2")
                            # Extract link string parameter tokens
                            m = re.search(r'«([^:]+):([^»]+)»', cleaned_item)
                            if m:
                                t_type, t_val = m.group(1), m.group(2)
                                cell_lbl.bind("<Button-1>", lambda e, val=t_val: self.spell_callback(val) if self.spell_callback else None)
                                
                    self.text.window_create(tk.END, window=list_frame)
                    self.text.insert(tk.END, "\n\n")
                else:
                    # Fallback to default continuous single vertical track layout formatting
                    for item in items:
                        if isinstance(item, str):
                            item = re.sub(r'{@note (.*?)}', r'\1', item, flags=re.IGNORECASE)
                            self.text.insert(tk.END, "  • ", "body")
                            self.insert_text_with_links(preprocess.clean_5etools_text(item) + "\n", "body")
                        elif isinstance(item, dict) and item.get("type") == "item":
                            self.text.insert(tk.END, "  • ", "body")
                            name = item.get("name")
                            if name:
                                self.insert_text_with_links(preprocess.clean_5etools_text(name) + ": ", "bold")
                            
                            sub_entries = item.get("entries", [])
                            if isinstance(sub_entries, list):
                                for sub_idx, sub in enumerate(sub_entries):
                                    cleaned_sub = preprocess.clean_5etools_text(str(sub))
                                    self.insert_text_with_links(cleaned_sub, "body")
                                    if sub_idx < len(sub_entries) - 1:
                                        self.text.insert(tk.END, "\n    ", "body")
                            else:
                                self.insert_text_with_links(preprocess.clean_5etools_text(str(sub_entries)), "body")
                            self.text.insert(tk.END, "\n")
                    self

            # --- Render Nested Sub-Entries / Inset Structural Content Blocks ---
            elif e_type in ["entries", "inset"]:
                name = entry.get("name")
                if name:
                    tag_type = "bold" if e_type == "inset" else "section_header"
                    self.text.insert(tk.END, f"{name}\n", tag_type)
                    self.insert_divider()
                
                sub_entries = entry.get("entries", [])
                if isinstance(sub_entries, list):
                    for sub in sub_entries:
                        self._render_custom_entry_element(sub)
                else:
                    self._render_custom_entry_element(str(sub_entries))
                return

            # --- Render Adaptive Columns Tables Grid ---
            elif e_type == "table":
                caption = entry.get("caption")
                if caption:
                    self.text.insert(tk.END, f"{caption}\n", "bold")
                
                labels = entry.get("colLabels", [])
                rows = entry.get("rows", [])
                col_styles = entry.get("colStyles", [])
                
                w_width = self.text.winfo_width()
                text_width = max(200, w_width - 80) if w_width > 20 else 600
                try:
                    font_obj = font.Font(font=self.body_font)
                    char_width = font_obj.measure("m") or 8
                except:
                    char_width = 8
                
                max_cols = max(len(labels), len(rows[0]) if rows else 0)
                usable_pixel_width = max(100, text_width - (max_cols * 24))
                total_char_width = usable_pixel_width // char_width
                
                col_weights = []
                for col_idx in range(max_cols):
                    weight = 1
                    if col_idx < len(col_styles):
                        w_match = re.search(r'col-(\d+)', col_styles[col_idx])
                        if w_match:
                            weight = int(w_match.group(1))
                    col_weights.append(weight)
                total_weight = sum(col_weights) or 1

                table_frame = tk.Frame(self.text, bg="#d9ad6c", bd=1, relief=tk.SOLID)
                
                for col_idx in range(max_cols):
                    col_pixel_width = int(usable_pixel_width * col_weights[col_idx] // total_weight)
                    table_frame.grid_columnconfigure(col_idx, minsize=col_pixel_width, weight=col_weights[col_idx])
                    
                def cell_scroll_router(event):
                    if hasattr(self, "_hover_popup") and self._hover_popup and self._hover_popup.winfo_exists():
                        units = -2 if event.num == 4 else 2 if event.num == 5 else -1 * (event.delta // 40)
                        if hasattr(self._hover_popup, 'target_text_widget') and self._hover_popup.target_text_widget.winfo_exists():
                            self._hover_popup.target_text_widget.yview_scroll(units, "units")
                        return "break"
                    units = -2 if event.num == 4 else 2 if event.num == 5 else -1 * (event.delta // 40)
                    self.text.yview_scroll(units, "units")
                    return "break"

                for col_idx, label in enumerate(labels):
                    col_pixel_width = int(usable_pixel_width * col_weights[col_idx] // total_weight)
                    cleaned_lbl = preprocess.clean_5etools_text(str(label))
                    hdr_lbl = tk.Label(table_frame, text=cleaned_lbl, font=self.body_bold, bg="#e0cbb0", fg="black", 
                                       padx=10, pady=6, anchor="w", justify=tk.LEFT, wraplength=max(20, col_pixel_width - 20))
                    hdr_lbl.grid(row=0, column=col_idx, sticky="nsew", padx=1, pady=1)
                    
                for row_idx, row in enumerate(rows):
                    bg_color = "#fdf1dc" if row_idx % 2 == 0 else "#fae6c5"
                    for col_idx in range(min(len(row), max_cols)):
                        cell_raw = row[col_idx]
                        
                        # UNIFIED PARSING ENGINE: Process dictionary cells vs raw text strings interchangeably
                        if isinstance(cell_raw, dict) and cell_raw.get("type") == "cell":
                            # Pull only the item card name entry description text natively
                            cleaned_cell = preprocess.clean_5etools_text(str(cell_raw.get("entry", "")))
                        elif isinstance(cell_raw, dict):
                            cleaned_cell = preprocess.clean_5etools_text(str(cell_raw.get("entry", cell_raw)))
                        else:
                            # Direct String evaluation (Captures XDMG columns like "Balance", "Comet" directly)
                            cleaned_cell = preprocess.clean_5etools_text(str(cell_raw))
                        
                        # STRIP DICE INDEX HEADERS AND INDEX RANGES OUT COMPLETELY:
                        # This strips out range lines like "01-05" or "89-96" and drops em-dashes completely
                        if re.match(r'^\d+-\d+$', cleaned_cell.strip()) or cleaned_cell.strip() == "—" or cleaned_cell.strip() == "\u2014":
                            cleaned_cell = "" # Leaves the roll column cell blank as per instructions
                        
                        col_pixel_width = int(usable_pixel_width * col_weights[col_idx] // total_weight)
                        col_char_width = max(4, col_pixel_width // char_width)
                        
                        lines_count = cleaned_cell.split("\n")
                        h_estimate = 0
                        for line in lines_count:
                            h_estimate += max(1, (len(line) + col_char_width - 1) // col_char_width)
                        
                        cell_txt = tk.Text(table_frame, font=self.body_font, bg=bg_color, fg="black", wrap=tk.WORD, 
                                           width=1, height=max(1, h_estimate), bd=0, highlightthickness=0, padx=10, pady=6)
                        cell_txt.grid(row=row_idx + 1, column=col_idx, sticky="nsew", padx=1, pady=1)
                        
                        cell_txt.tag_configure("spell_link", font=self.body_font, foreground="#4a90e2", underline=True)
                        cell_txt.tag_configure("bold", font=self.body_bold, foreground="black")
                        cell_txt.tag_bind("spell_link", "<Enter>", lambda e, w=cell_txt: [w.config(cursor="hand2"), self._handle_cell_link_hover(e, w)])
                        cell_txt.tag_bind("spell_link", "<Leave>", lambda e, w=cell_txt: [w.config(cursor=""), self._on_link_leave(e)])
                        cell_txt.tag_bind("spell_link", "<Motion>", lambda e, w=cell_txt: self._handle_cell_link_hover(e, w))
                        cell_txt.tag_bind("spell_link", "<Button-1>", lambda e, w=cell_txt: self._on_cell_link_click(e, w))
                        
                        self._insert_text_with_links_to_widget(cell_txt, cleaned_cell, "body")
                        cell_txt.config(state=tk.DISABLED)
                        
                        cell_txt.bind("<MouseWheel>", cell_scroll_router)
                        cell_txt.bind("<Button-4>", cell_scroll_router)
                        cell_txt.bind("<Button-5>", cell_scroll_router)
                        
                self.text.window_create(tk.END, window=table_frame)
                self.text.insert(tk.END, "\n")
                
                footnotes = entry.get("footnotes", [])
                if footnotes:
                    self.text.insert(tk.END, "\n", "body")
                    for fn in footnotes:
                        cleaned_fn = preprocess.clean_5etools_text(str(fn))
                        self.text.insert(tk.END, f"{cleaned_fn}\n", "subtitle")
                
                self.text.insert(tk.END, "\n")
                return

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
        self.body_link = font.Font(family="Times", size=13, underline=True)
        
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
        self.selected_row_info = None
        self.edit_mode = False


    def _fetch_max_hp(self, target_path):
        p = Path(target_path)
        if not p.exists(): return 10
        try:
            json_path = list(p.glob("*.json"))[0] if p.is_dir() else p
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f).get("hp", {}).get("average", 10)
        except: pass
        return 10

    def _sync_top_metadata(self):
        if getattr(self, 'edit_mode', False):
            if hasattr(self, 'name_txt'):
                self.current_data["name"] = self.name_txt.get("1.0", "end-1c").strip()
            if hasattr(self, 'time_txt'):
                self.current_data["time"] = self.time_txt.get("1.0", "end-1c").strip()
            if hasattr(self, 'desc_txt'):
                self.current_data["description"] = self.desc_txt.get("1.0", "end-1c").strip()
            if hasattr(self, 'over_var'):
                self.current_data["over"] = "Yes" if self.over_var.get() else "No"
            if hasattr(self, 'out_txt'):
                self.current_data["outcome"] = self.out_txt.get("1.0", "end-1c").strip()
            if hasattr(self, 'combat_location_items'):
                self.current_data["locations"] = [l["name"] for l in self.combat_location_items]

    def _sync_all_rows(self):
        self._sync_top_metadata()
        for r in self.participant_rows:
            p = r["data"]
            p["name"] = r["name_var"].get().strip()
            p["side"] = r["side_var"].get()
            p["dead"] = r["dead_var"].get()
            p["statuses"] = r.get("active_statuses", [])
            
            i_val = r["init_en"].get().strip()
            p["init"] = int(i_val) if i_val.lstrip('-').isdigit() else 0
                
            h_val = r["hp_en"].get().strip()
            curr_hp = int(h_val) if h_val.lstrip('-').isdigit() else 0
            max_hp = self._fetch_max_hp(p.get("target", ""))
            
            p["damage"] = max_hp - curr_hp

    def render_combat(self, combat_data, combat_dir):
        # Fix: Always refresh current view data when switching back to display mode to clear stale states
        if not hasattr(self, 'original_data') or self.combat_dir != combat_dir or not self.edit_mode:
            self.original_data = copy.deepcopy(combat_data)
            self.current_data = copy.deepcopy(combat_data)
        self.combat_dir = combat_dir
        self._redraw_workspace()

    def _auto_save(self):
        """Saves current interactive workspace properties down to disk automatically."""
        self._sync_all_rows()
        self.current_data["participants"].sort(key=lambda x: x.get("init", 0), reverse=True)
        if not self.edit_mode:
            self.original_data = copy.deepcopy(self.current_data)
        try:
            self.save_cb(self.combat_dir, self.current_data, background=True)
        except TypeError:
            self.save_cb(self.combat_dir, self.current_data)

    def _modify_selected_hp(self, delta):
        if not self.selected_row_info:
            messagebox.showinfo("Selection Required", "Please click on a combatant's panel first to select them.")
            return
        try:
            hp_widget = self.selected_row_info["hp_en"]
            current_hp_text = hp_widget.get().strip()
            current_hp = int(current_hp_text) if current_hp_text.lstrip('-').isdigit() else 0
            
            new_hp = current_hp + delta
            if new_hp < 0: 
                new_hp = 0
            
            hp_widget.delete(0, tk.END)
            hp_widget.insert(0, str(new_hp))
            
            if "update_colors_cb" in self.selected_row_info:
                self.selected_row_info["update_colors_cb"]()
            self._auto_save() # Auto-save HP changes
        except Exception: pass

    def _realtime_sort(self, event=None):
        try: focused_widget = self.focus_get()
        except: focused_widget = None
            
        self._sync_all_rows()
        self.participant_rows.sort(key=lambda r: r["data"].get("init", 0), reverse=True)
        self.current_data["participants"] = [r["data"] for r in self.participant_rows]
        
        for r in self.participant_rows: r["frame"].pack_forget()
        for r in self.participant_rows: r["frame"].pack(fill=tk.X, pady=4)
            
        if focused_widget and focused_widget.winfo_exists():
            try: focused_widget.focus_set()
            except: pass
        self._auto_save() # Auto-save adjustments to initiative orders or alignment side states

    def _open_status_dialog(self, row_info):
        from stat_renderer import CONDITIONS_DB
        dialog = tk.Toplevel(self)
        dialog.title(f"Statuses: {row_info['name_var'].get()}")
        dialog.geometry("380x460")
        dialog.configure(bg="#fdf1dc")
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="Select Status Effects", font=("Georgia", 13, "bold"), fg="#58180d", bg="#fdf1dc", pady=8).pack(side=tk.TOP)
        current_active = set(s.lower().strip() for s in row_info.get("active_statuses", []))
        selected_conds = set(current_active)

        def apply_selection():
            row_info["active_statuses"] = [c.title() for c in sorted(list(CONDITIONS_DB.keys())) if c in selected_conds]
            self._refresh_status_chips_display(row_info)
            self._auto_save() # Auto-save applied status effects
            dialog.destroy()

        btn_frame = tk.Frame(dialog, bg="#fdf1dc", pady=10)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Button(btn_frame, text="Apply", font=("Arial", 10, "bold"), bg="#4a90e2", fg="white", width=10, command=apply_selection).pack(side=tk.LEFT, padx=35)
        tk.Button(btn_frame, text="Cancel", font=("Arial", 10, "bold"), bg="#58180d", fg="white", width=10, command=dialog.destroy).pack(side=tk.RIGHT, padx=35)

        list_frame = tk.Frame(dialog, bg="#fdf1dc")
        list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=15, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(list_frame, bg="#fae6c5", highlightthickness=1, highlightbackground="#d9ad6c")
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.config(command=canvas.yview)

        scroll_inner = tk.Frame(canvas, bg="#fae6c5")
        window_item = canvas.create_window((0, 0), window=scroll_inner, anchor="nw")
        
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(window_item, width=e.width))
        scroll_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        dialog.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        def toggle_row(cond_key, row_frame, lbl_widget, base_bg):
            if cond_key in selected_conds:
                selected_conds.remove(cond_key)
                row_frame.configure(bg=base_bg)
                lbl_widget.configure(bg=base_bg, fg="black")
            else:
                selected_conds.add(cond_key)
                row_frame.configure(bg="#4a90e2")
                lbl_widget.configure(bg="#4a90e2", fg="white")

        for idx, cond in enumerate(sorted(list(CONDITIONS_DB.keys()))):
            base_bg = "#f5f5f5" if idx % 2 == 0 else "#e0e0e0"
            r_frame = tk.Frame(scroll_inner, bg=base_bg, bd=0, padx=15, pady=6)
            r_frame.pack(fill=tk.X, expand=True)
            lbl_widget = tk.Label(r_frame, text=cond.title(), font=("Times", 11, "bold"), bg=base_bg, fg="black", anchor="w")
            lbl_widget.pack(fill=tk.X, expand=True)
            if cond in selected_conds:
                r_frame.configure(bg="#4a90e2")
                lbl_widget.configure(bg="#4a90e2", fg="white")
            r_frame.bind("<Button-1>", lambda e, c=cond, rf=r_frame, lw=lbl_widget, bbg=base_bg: toggle_row(c, rf, lw, bbg))
            lbl_widget.bind("<Button-1>", lambda e, c=cond, rf=r_frame, lw=lbl_widget, bbg=base_bg: toggle_row(c, rf, lw, bbg))

    def _change_selected_state(self, state_type):
        if not self.selected_row_info:
            messagebox.showinfo("Selection Required", "Please click on a combatant's panel first to select them.")
            return
        if state_type == "Dead":
            self.selected_row_info["dead_var"].set(True)
        else:
            self.selected_row_info["side_var"].set(state_type)
            self.selected_row_info["dead_var"].set(False)
            
        if "update_colors_cb" in self.selected_row_info:
            self.selected_row_info["update_colors_cb"]()
        self._realtime_sort()

    def _on_top_init_changed(self, event=None):
        if not self.selected_row_info: return
        val = self.top_init_combo.get()
        self.selected_row_info["init_en"].delete(0, tk.END)
        self.selected_row_info["init_en"].insert(0, val)
        self._realtime_sort()

    def _show_condition_helper(self, cond_name):
        from stat_renderer import CONDITIONS_DB
        key = cond_name.lower().strip()
        desc = CONDITIONS_DB.get(key, "No description available for this condition.")
        
        top = tk.Toplevel(self)
        top.title(f"Condition: {cond_name.title()}")
        top.geometry("450x350")
        top.configure(bg="#fdf1dc")
        top.transient(self)
        top.grab_set()
        
        lbl_title = tk.Label(top, text=cond_name.title(), font=("Georgia", 16, "bold"), fg="#58180d", bg="#fdf1dc", pady=10)
        lbl_title.pack()
        
        txt_frame = tk.Frame(top, bg="#fdf1dc", padx=15, pady=5)
        txt_frame.pack(fill=tk.BOTH, expand=True)
        
        scroll = ttk.Scrollbar(txt_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        txt = tk.Text(txt_frame, font=("Times", 12), wrap=tk.WORD, bg="#fae6c5", fg="black", bd=1, relief=tk.SOLID, yscrollcommand=scroll.set)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=txt.yview)
        
        txt.insert("1.0", desc)
        txt.config(state=tk.DISABLED)
        
        btn_close = tk.Button(top, text="Close", font=("Arial", 10, "bold"), bg="#58180d", fg="white", command=top.destroy, pady=5)
        btn_close.pack(pady=10)

    def _redraw_workspace(self):
        for w in self.main_inner.winfo_children(): w.destroy()
        self.participant_rows.clear()
        self.selected_row_info = None

        top_frame = tk.Frame(self.main_inner, bg="#fdf1dc")
        top_frame.pack(fill=tk.X, pady=(0, 20))
        tk.Label(top_frame, text="LIVE COMBAT WORKSPACE", font=self.header_font, fg="#58180d", bg="#fdf1dc").pack(side=tk.LEFT)
        
        def save_action():
            self._sync_all_rows()
            self.current_data["participants"].sort(key=lambda x: x.get("init", 0), reverse=True)
            self.original_data = copy.deepcopy(self.current_data)
            # Triggers non-background open_page navigation flow back into clean view mode
            self.save_cb(self.combat_dir, self.current_data)

        def cancel_action():
            self.current_data = copy.deepcopy(self.original_data)
            self.edit_mode = False
            self._redraw_workspace()

        def edit_action():
            self.edit_mode = True
            self._redraw_workspace()

        if self.edit_mode:
            tk.Button(top_frame, text="SAVE", bg="#4a90e2", fg="white", font=("Georgia", 10, "bold"), command=save_action).pack(side=tk.RIGHT, padx=5)
            tk.Button(top_frame, text="CANCEL", bg="#58180d", fg="white", font=("Georgia", 10, "bold"), command=cancel_action).pack(side=tk.RIGHT, padx=5)
        else:
            tk.Button(top_frame, text="EDIT", bg="#8a8a8a", fg="white", font=("Georgia", 10, "bold"), command=edit_action).pack(side=tk.RIGHT, padx=5)

        fields_f = tk.Frame(self.main_inner, bg="#fdf1dc")
        fields_f.pack(fill=tk.X, pady=10)
        fields_f.grid_columnconfigure(1, weight=1)

        if self.edit_mode:
            # Edit Mode Input Fields (Rows 0 to 4)
            for r, (lbl, key, w) in enumerate([("Name:", "name", 40), ("Time:", "time", 40), ("Description:", "description", 60)]):
                tk.Label(fields_f, text=lbl, bg="#fdf1dc", font=self.body_bold).grid(row=r, column=0, sticky="ne", pady=4)
                txt = AutoHeightText(fields_f, canvas_to_refresh=self.main_canvas, width=w, height=1, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
                txt.insert("1.0", self.current_data.get(key, ""))
                txt.grid(row=r, column=1, sticky="w", padx=10, pady=4)
                if key == "name": self.name_txt = txt
                elif key == "time": self.time_txt = txt
                elif key == "description": self.desc_txt = txt

            tk.Label(fields_f, text="Over:", bg="#fdf1dc", font=self.body_bold).grid(row=3, column=0, sticky="ne", pady=4)
            self.over_var = tk.BooleanVar(value=self.current_data.get("over", "No") == "Yes")
            tk.Checkbutton(fields_f, variable=self.over_var, bg="#fdf1dc", activebackground="#fdf1dc").grid(row=3, column=1, sticky="w", padx=10, pady=4)

            tk.Label(fields_f, text="Outcome:", bg="#fdf1dc", font=self.body_bold).grid(row=4, column=0, sticky="ne", pady=4)
            self.out_txt = AutoHeightText(fields_f, canvas_to_refresh=self.main_canvas, width=60, height=1, font=self.body_font, wrap=tk.WORD, bd=1, relief=tk.SOLID)
            self.out_txt.insert("1.0", self.current_data.get("outcome", ""))
            self.out_txt.grid(row=4, column=1, sticky="w", padx=10, pady=4)
            
            
            tk.Label(fields_f, text="Locations:", bg="#fdf1dc", font=self.body_bold).grid(row=5, column=0, sticky="ne", pady=4)
            loc_sec_frame = tk.Frame(fields_f, bg="#fdf1dc")
            # Changed from sticky="w" to sticky="ew" to take up full available frame width
            loc_sec_frame.grid(row=5, column=1, sticky="ew", padx=10, pady=4)
            
            self.combat_location_items = []
            loc_lst = tk.Frame(loc_sec_frame, bg="#fdf1dc")
            
            def draw_loc_row(name):
                loc_name = name.get("name") if isinstance(name, dict) else str(name)
                row = tk.Frame(loc_lst, bg="#e0cbb0", pady=4, padx=10, bd=1, relief=tk.SOLID)
                # Enforce horizontal filling across full panel space
                row.pack(fill=tk.X, expand=True, pady=2)
                tk.Label(row, text=loc_name, font=self.body_bold, bg="#e0cbb0", fg="black").pack(side=tk.LEFT)
                item_dict = {"name": name, "frame": row}
                self.combat_location_items.append(item_dict)
                tk.Button(row, text="X", bg="#ff4d4d", fg="white", font=("Arial", 8, "bold"), 
                          command=lambda: (row.pack_forget(), row.destroy(), self.combat_location_items.remove(item_dict), self.main_inner.update_idletasks(), self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))).pack(side=tk.RIGHT)
                loc_lst.pack(fill=tk.X, expand=True)
                self.main_inner.update_idletasks()
                self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

            toplevel = self.winfo_toplevel()
            map_dir = getattr(toplevel, "map_dir", None)
            
            def add_location_action():
                from dialogs import EntitySelectionDialog
                from main import SyncRef
                EntitySelectionDialog(toplevel, map_dir, "Locations", lambda name: draw_loc_row(SyncRef(name, str(toplevel._find_dir_by_name(name, map_dir)))))

            tk.Button(loc_sec_frame, text="+ Add Location", bg="#d9ad6c", font=("Arial", 8, "bold"), 
                      command=add_location_action).pack(side=tk.TOP, anchor="w")
            loc_lst.pack(fill=tk.X, expand=True, pady=4)
            for loc in self.current_data.get("locations", []): 
                draw_loc_row(loc)
        else:
            # Display Mode Dashboard Read-Only Text Labels
            for r, (lbl, key) in enumerate([("Name:", "name"), ("Time:", "time"), ("Description:", "description"), ("Over:", "over"), ("Outcome:", "outcome")]):
                tk.Label(fields_f, text=lbl, bg="#fdf1dc", font=self.body_bold).grid(row=r, column=0, sticky="nw", pady=2)
                val_text = str(self.current_data.get(key, ""))
                tk.Label(fields_f, text=val_text, bg="#fdf1dc", font=self.body_font, fg="black", justify=tk.LEFT, anchor="w", wraplength=600).grid(row=r, column=1, sticky="w", padx=10, pady=2)

            # --- Location Row Hyperlink Formatting under Display Mode (Separate Bulleted Rows) ---
            tk.Label(fields_f, text="Locations:", bg="#fdf1dc", font=self.body_bold).grid(row=5, column=0, sticky="nw", pady=2)
            locs_frame = tk.Frame(fields_f, bg="#fdf1dc")
            locs_frame.grid(row=5, column=1, sticky="ew", padx=10, pady=2)
            
            locs_list = self.current_data.get("locations", [])
            if not locs_list:
                tk.Label(locs_frame, text="None", bg="#fdf1dc", font=self.body_italic, fg="black").pack(anchor="w")
            else:
                for loc in locs_list:
                    # Render each element on its own individual horizontal layout row line
                    row_f = tk.Frame(locs_frame, bg="#fdf1dc")
                    row_f.pack(fill=tk.X, anchor="w", pady=1)
                    
                    # Prepend standard entity bullet point character matching render_campaign_node architecture
                    tk.Label(row_f, text="• ", bg="#fdf1dc", font=self.body_bold, fg="black").pack(side=tk.LEFT)
                    
                    loc_name = loc.get("name") if isinstance(loc, dict) else str(loc)
                    loc_target = loc.get("path") if isinstance(loc, dict) else (getattr(loc, "path", None) or loc_name)
                    
                    lbl_link = tk.Label(row_f, text=loc_name, bg="#fdf1dc", fg="#4a90e2", font=self.body_link, cursor="hand2")
                    lbl_link.pack(side=tk.LEFT)
                    
                    # Bind navigation and minirenderer hover tooltips onto individual items cleanly
                    lbl_link.bind("<Button-1>", lambda e, path=loc_target: getattr(self.winfo_toplevel(), "on_location_link_clicked")(path, "Locations"))
                    lbl_link.bind("<Enter>", lambda e, lt=loc_target: self._on_location_hover_enter(e, lt))
                    lbl_link.bind("<Motion>", lambda e, lt=loc_target: self._on_location_hover_motion(e, lt))
                    lbl_link.bind("<Leave>", self._on_location_hover_leave)

        # The combat tracker section below remains fully interactive in both modes
        tk.Label(self.main_inner, text="COMBATANTS", font=self.header_font, fg="#58180d", bg="#fdf1dc").pack(anchor="w", pady=(20, 5))
        controls_row1 = tk.Frame(self.main_inner, bg="#fdf1dc")
        controls_row1.pack(fill=tk.X, pady=2)

        # --- COMBATANTS LIST SECTION CONTROLS ---
        def append_combatant(target_path, folder_type):
            self._sync_all_rows()
            p_obj = Path(target_path)
            short_name = p_obj.stem if p_obj.is_file() else p_obj.name
            new_fighter = {
                "name": short_name, "target": str(p_obj.resolve()), "type": folder_type,
                "side": "Enemy" if folder_type == "Monsters" else "Neutral",
                "init": 0, "damage": 0, "dead": False, "statuses": []
            }
            self.current_data.setdefault("participants", []).append(new_fighter)
            self.current_data["participants"].sort(key=lambda x: x.get("init", 0), reverse=True)
            self._auto_save() # Auto-save added combatants
            self._redraw_workspace()


        tk.Button(controls_row1, text="+ New Monster", bg="#d9ad6c", fg="black", font=("Arial", 9, "bold"), command=lambda: self.add_bestiary_cb(self.combat_dir, append_combatant)).pack(side=tk.LEFT, padx=3)
        tk.Button(controls_row1, text="+ Add Existing Monster", bg="#d9ad6c", fg="black", font=("Arial", 9, "bold"), command=lambda: self.add_camp_mon_cb(append_combatant)).pack(side=tk.LEFT, padx=3)
        tk.Button(controls_row1, text="+ Add NPC", bg="#d9ad6c", fg="black", font=("Arial", 9, "bold"), command=lambda: self.add_camp_npc_cb(append_combatant)).pack(side=tk.LEFT, padx=3)

        controls_row2 = tk.Frame(self.main_inner, bg="#fdf1dc", pady=5)
        controls_row2.pack(fill=tk.X, pady=(2, 10))

        tk.Label(controls_row2, text="Initiative:", bg="#fdf1dc", font=("Arial", 9, "bold"), fg="#58180d").pack(side=tk.LEFT, padx=(3, 2))
        init_vals = [str(i) for i in range(-5, 31)]
        self.top_init_combo = ttk.Combobox(controls_row2, values=init_vals, state="readonly", width=5)
        self.top_init_combo.pack(side=tk.LEFT, padx=2)
        self.top_init_combo.bind("<<ComboboxSelected>>", self._on_top_init_changed)

        self.top_status_btn = tk.Button(controls_row2, text="STATUSES", bg="#fae6c5", fg="black", font=("Arial", 9, "bold"), command=lambda: self._open_status_dialog(self.selected_row_info) if self.selected_row_info else messagebox.showinfo("Selection Required", "Please select a combatant row first."))
        self.top_status_btn.pack(side=tk.LEFT, padx=15)

        tk.Label(controls_row2, text="Quick HP:", bg="#fdf1dc", font=("Arial", 9, "bold"), fg="#58180d").pack(side=tk.LEFT, padx=(5, 2))
        for mod in [1, 5, 10]:
            tk.Button(controls_row2, text=f"+{mod}", bg="#5cb85c", fg="white", font=("Arial", 9, "bold"), width=4, command=lambda m=mod: self._modify_hp_via_top(m)).pack(side=tk.LEFT, padx=1)
        for mod in [1, 5, 10]:
            tk.Button(controls_row2, text=f"-{mod}", bg="#d9534f", fg="white", font=("Arial", 9, "bold"), width=4, command=lambda m=mod: self._modify_hp_via_top(-m)).pack(side=tk.LEFT, padx=1)

        tk.Label(controls_row2, text="Set State:", bg="#fdf1dc", font=("Arial", 9, "bold"), fg="#58180d").pack(side=tk.LEFT, padx=(15, 2))
        tk.Button(controls_row2, text="Ally", bg="#4a90e2", fg="white", font=("Arial", 9, "bold"), command=lambda: self._change_selected_state("Ally")).pack(side=tk.LEFT, padx=1)
        tk.Button(controls_row2, text="Neutral", bg="#8a8a8a", fg="white", font=("Arial", 9, "bold"), command=lambda: self._change_selected_state("Neutral")).pack(side=tk.LEFT, padx=1)
        tk.Button(controls_row2, text="Enemy", bg="#ff4d4d", fg="white", font=("Arial", 9, "bold"), command=lambda: self._change_selected_state("Enemy")).pack(side=tk.LEFT, padx=1)
        tk.Button(controls_row2, text="Dead", bg="#333333", fg="white", font=("Arial", 9, "bold"), command=lambda: self._change_selected_state("Dead")).pack(side=tk.LEFT, padx=1)

        self.parts_frame = tk.Frame(self.main_inner, bg="#fdf1dc")
        self.parts_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        for p_data in self.current_data.get("participants", []):
            self._build_live_participant_panel(p_data)

    def _modify_hp_via_top(self, delta):
        self._modify_selected_hp(delta)


    def _refresh_status_chips_display(self, row_info):
        sb = row_info["status_box"]
        sb.config(state=tk.NORMAL)
        sb.delete("1.0", tk.END)
        active_list = row_info.get("active_statuses", [])
        if not active_list:
            sb.adjust_height()
            sb.config(state=tk.DISABLED)
            return
        for i, cond_name in enumerate(active_list):
            if i > 0: sb.insert(tk.END, ", ", "normal_text")
            tag_name = f"STATUS_LINK:{cond_name}"
            sb.insert(tk.END, cond_name, (tag_name, "status_link"))
            sb.tag_configure(tag_name, foreground="#ffffff", underline=True, font=("Times", 13, "bold"))
        sb.adjust_height()
        sb.config(state=tk.DISABLED)

    def _select_combatant_row(self, row_info):
        if self.selected_row_info and self.selected_row_info["frame"].winfo_exists():
            self.selected_row_info["frame"].configure(highlightthickness=2, highlightbackground="black", highlightcolor="black")
        self.selected_row_info = row_info
        row_info["frame"].configure(highlightthickness=2, highlightbackground="yellow", highlightcolor="yellow")
        curr_init = str(row_info["init_en"].get().strip())
        if curr_init in [str(i) for i in range(-5, 31)]: self.top_init_combo.set(curr_init)
        else: self.top_init_combo.set("0")

    def _build_live_participant_panel(self, p):
        def get_panel_color(side, is_dead):
            if is_dead: return "#333333"
            return {"Ally": "#4a90e2", "Enemy": "#ff4d4d", "Neutral": "#8a8a8a"}.get(side, "#8a8a8a")

        initial_color = get_panel_color(p.get("side", "Neutral"), p.get("dead", False))
        panel = tk.Frame(self.parts_frame, bg=initial_color, pady=8, padx=12, bd=1, relief=tk.SOLID, highlightthickness=2, highlightbackground="black", highlightcolor="black")
        panel.pack(fill=tk.X, pady=4)

        init_hidden_entry = tk.Entry(self) 
        init_hidden_entry.insert(0, str(p.get("init", 0)))
        d_var = tk.BooleanVar(value=p.get("dead", False))
        s_var = tk.StringVar(value=p.get("side", "Neutral"))
        row_info = {"data": p, "frame": panel, "active_statuses": p.get("statuses", []), "init_en": init_hidden_entry, "dead_var": d_var, "side_var": s_var}
        panel.bind("<Button-1>", lambda e: self._select_combatant_row(row_info))

        def delete_combatant():
            self._sync_all_rows()
            if self.selected_row_info == row_info: self.selected_row_info = None
            self.current_data["participants"].remove(p)
            self.current_data["participants"].sort(key=lambda x: x.get("init", 0), reverse=True)
            self._auto_save() # Auto-save row removals
            self._redraw_workspace()

        tk.Button(panel, text="DELETE", bg="#d9534f", fg="white", font=("Arial", 8, "bold"), width=8, command=delete_combatant).pack(side=tk.RIGHT, padx=5)

        hp_container = tk.Frame(panel, bg=initial_color, width=110)
        hp_container.pack_propagate(False)
        hp_container.pack(side=tk.RIGHT, padx=10, fill=tk.Y)
        hp_container.bind("<Button-1>", lambda e: self._select_combatant_row(row_info))

        max_hp = self._fetch_max_hp(p.get("target", ""))
        current_hp = max_hp - p.get("damage", 0)

        lbl_max = tk.Label(hp_container, text=f"/ {max_hp}", bg=initial_color, fg="white", font=("Arial", 10, "bold"))
        lbl_max.pack(side=tk.RIGHT)
        lbl_max.bind("<Button-1>", lambda e: self._select_combatant_row(row_info))

        hp_en = AutoHeightText(hp_container, canvas_to_refresh=self.main_canvas, width=4, font=("Arial", 10, "bold"), bd=1, relief=tk.SOLID)
        hp_en.insert(0, str(current_hp))
        hp_en.pack(side=tk.RIGHT, padx=2)
        
        lbl_hp = tk.Label(hp_container, text="HP:", bg=initial_color, fg="white", font=("Arial", 10, "bold"))
        lbl_hp.pack(side=tk.RIGHT, padx=1)
        lbl_hp.bind("<Button-1>", lambda e: self._select_combatant_row(row_info))

        name_en = AutoHeightText(panel, canvas_to_refresh=self.main_canvas, font=("Georgia", 11, "bold"), width=25, bg="white", fg="black", insertbackground="black", bd=1, relief=tk.SOLID)
        name_en.insert(0, p["name"])
        name_en.pack(side=tk.LEFT, padx=5)
        name_en.bind("<Button-1>", lambda e: [self._select_combatant_row(row_info), "continue"][1])

        btn_stats = tk.Button(panel, text="STATS", bg="#fae6c5", fg="black", font=("Arial", 8, "bold"), width=6, command=lambda: (self._sync_all_rows(), self.open_statblock_cb(p["target"], p["type"])))
        btn_stats.pack(side=tk.LEFT, padx=5)
        btn_stats.bind("<Enter>", lambda e, pd=p: self._on_stats_btn_hover_enter(e, pd))
        btn_stats.bind("<Leave>", lambda e: self._on_stats_btn_hover_leave(e))
        btn_stats.bind("<Motion>", lambda e: self._on_stats_btn_hover_motion(e))

        status_box = AutoHeightText(panel, canvas_to_refresh=self.main_canvas, width=15, bg=initial_color, fg="white", bd=0, highlightthickness=0, wrap=tk.WORD)
        status_box.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        row_info["status_box"] = status_box
        
        def custom_adjust_height():
            try:
                text_content = status_box.get("1.0", "end-1c")
                if not text_content.strip():
                    status_box.configure(height=1); return
                pixel_width = status_box.winfo_width()
                chars_per_line = max(10, pixel_width // 12) if pixel_width > 50 else 22  
                total_lines = 0
                for line in text_content.split("\n"):
                    if not line: total_lines += 1
                    else: total_lines += max(1, (len(line) + chars_per_line - 1) // chars_per_line)
                total_lines = max(1, total_lines)
                if total_lines != int(status_box.cget("height")):
                    status_box.configure(height=total_lines)
                    if self.main_canvas:
                        self.main_canvas.update_idletasks()
                        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
            except Exception: pass
            
        status_box.adjust_height = custom_adjust_height
        
        def handle_status_box_interaction(event):
            self._select_combatant_row(row_info)
            idx = status_box.index(f"@{event.x},{event.y}")
            for tag in status_box.tag_names(idx):
                if tag.startswith("STATUS_LINK:"):
                    self._show_condition_helper(tag.split(":", 1)[1]); return "break"
        status_box.bind("<Button-1>", handle_status_box_interaction)
        status_box.tag_bind("status_link", "<Enter>", lambda e, sb=status_box: self._handle_status_hover(e, sb))
        status_box.tag_bind("status_link", "<Leave>", lambda e: self._on_status_hover_leave(e))
        status_box.tag_bind("status_link", "<Motion>", lambda e, sb=status_box: self._handle_status_hover(e, sb))

        def update_colors():
            new_color = get_panel_color(s_var.get(), d_var.get())
            panel.configure(bg=new_color)
            status_box.configure(bg=new_color)
            hp_container.configure(bg=new_color)
            lbl_max.configure(bg=new_color)
            lbl_hp.configure(bg=new_color)
            if self.selected_row_info == row_info: panel.configure(highlightbackground="yellow", highlightcolor="yellow")
            else: panel.configure(highlightbackground="black", highlightcolor="black")
            self._refresh_status_chips_display(row_info)
            for child in panel.winfo_children():
                if isinstance(child, tk.Label): child.configure(bg=new_color, activebackground=new_color)

        row_info.update({"name_var": name_en, "hp_en": hp_en, "lbl_hp": lbl_hp, "lbl_max": lbl_max, "update_colors_cb": update_colors})
        self.participant_rows.append(row_info)
        update_colors()

    def _on_status_hover_leave(self, event):
        if hasattr(self, "_hover_popup") and self._hover_popup:
            try: self._hover_popup.destroy()
            except: pass
            self._hover_popup, self._hover_target = None, None

    def _handle_status_hover(self, event, sb):
        idx = sb.index(f"@{event.x},{event.y}"); tags = sb.tag_names(idx); target_tag = next((t for t in tags if t.startswith("STATUS_LINK:")), None)
        if not target_tag: self._on_status_hover_leave(None); return
        scr_w, scr_h = self.winfo_screenwidth(), self.winfo_screenheight()
        popup_w, popup_h = int(scr_w * 2 / 5), int(scr_h * 2 / 5)
        x_pos = event.x_root + 15 if event.x_root < (scr_w / 2) else event.x_root - popup_w - 15
        y_pos = event.y_root + 15 if event.y_root < (scr_h / 2) else event.y_root - popup_h - 15
        if hasattr(self, "_hover_target") and self._hover_target == target_tag:
            if hasattr(self, "_hover_popup") and self._hover_popup: self._hover_popup.geometry(f"{popup_w}x{popup_h}+{x_pos}+{y_pos}")
            return
        self._on_status_hover_leave(None); self._hover_target = target_tag; cond_name = target_tag.split(":", 1)[1]
        popup = tk.Toplevel(self); popup.is_hover_popup = True; popup.wm_overrideredirect(True)
        popup.configure(bg="#fdf1dc", bd=2, relief=tk.SOLID); popup.geometry(f"{popup_w}x{popup_h}+{x_pos}+{y_pos}"); self._hover_popup = popup
        from stat_renderer import CONDITIONS_DB
        desc = CONDITIONS_DB.get(cond_name.lower().strip(), "No description available.")
        txt = tk.Text(popup, font=("Times", 12), wrap=tk.WORD, bg="#fdf1dc", bd=0, highlightthickness=0)
        txt.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        txt.insert("1.0", cond_name.title(), "title")
        txt.tag_configure("title", font=("Georgia", 13, "bold"), foreground="#58180d")
        txt.insert(tk.END, f"\n\n{desc}"); txt.config(state=tk.DISABLED); popup.target_text_widget = txt

    def _on_stats_btn_hover_enter(self, event, p_data): self._handle_stats_btn_hover(event, p_data)
    def _on_stats_btn_hover_motion(self, event):
        if hasattr(self, "_stats_hover_data"): self._handle_stats_btn_hover(event, self._stats_hover_data)
    def _on_stats_btn_hover_leave(self, event):
        if hasattr(self, "_hover_popup") and self._hover_popup:
            try: self._hover_popup.destroy()
            except: pass
            self._hover_popup, self._hover_target = None, None
        if hasattr(self, "_stats_hover_data"): delattr(self, "_stats_hover_data")

    def _handle_stats_btn_hover(self, event, p_data):
        self._stats_hover_data = p_data; target_tag = f"STATS_BTN:{p_data['target']}:{p_data['type']}"
        scr_w, scr_h = self.winfo_screenwidth(), self.winfo_screenheight()
        popup_w, popup_h = int(scr_w * 2 / 5), int(scr_h * 2 / 5)
        x_pos = event.x_root + 15 if event.x_root < (scr_w / 2) else event.x_root - popup_w - 15
        y_pos = event.y_root + 15 if event.y_root < (scr_h / 2) else event.y_root - popup_h - 15
        if hasattr(self, "_hover_target") and self._hover_target == target_tag:
            if hasattr(self, "_hover_popup") and self._hover_popup: self._hover_popup.geometry(f"{popup_w}x{popup_h}+{x_pos}+{y_pos}")
            return
        if hasattr(self, "_hover_popup") and self._hover_popup:
            try: self._hover_popup.destroy()
            except: pass
        self._hover_target = target_tag; popup = tk.Toplevel(self); popup.is_hover_popup = True; popup.wm_overrideredirect(True)
        popup.configure(bg="#fdf1dc", bd=2, relief=tk.SOLID); popup.geometry(f"{popup_w}x{popup_h}+{x_pos}+{y_pos}"); self._hover_popup = popup
        prefix = "LOC_MON_TAG" if p_data['type'] == "Monsters" else "LOC_NPC_TAG"
        name = p_data['target']; toplevel = self.winfo_toplevel()
        if hasattr(toplevel, "resolve_hover_data"):
            data, dtype = toplevel.resolve_hover_data(prefix, name)
            if data:
                mini_viewer = StatBlockRenderer(popup); mini_viewer.pack(fill=tk.BOTH, expand=True); mini_viewer.clear_overlays()
                mini_viewer.text.adjust_height = lambda: None; mini_viewer.text.configure(height=1); mini_viewer.render_monster(data); popup.target_text_widget = mini_viewer.text
            else: tk.Label(popup, text=f"Stats for '{p_data['name']}' not found.", bg="#fdf1dc", font=("Arial", 11, "italic")).pack(padx=20, pady=20)

    def _on_location_hover_enter(self, event, loc_target):
        self._handle_location_hover(event, loc_target)

    def _on_location_hover_motion(self, event, loc_target):
        self._handle_location_hover(event, loc_target)

    def _on_location_hover_leave(self, event):
        if hasattr(self, "_hover_popup") and self._hover_popup:
            try: self._hover_popup.destroy()
            except: pass
            self._hover_popup, self._hover_target = None, None

    def _handle_location_hover(self, event, loc_target):
        if not loc_target: return
        scr_w, scr_h = self.winfo_screenwidth(), self.winfo_screenheight()
        popup_w, popup_h = int(scr_w * 2 / 5), int(scr_h * 2 / 5)
        x_pos = event.x_root + 15 if event.x_root < (scr_w / 2) else event.x_root - popup_w - 15
        y_pos = event.y_root + 15 if event.y_root < (scr_h / 2) else event.y_root - popup_h - 15
        
        target_tag = f"COMBAT_LOC_HOVER:{loc_target}"
        if hasattr(self, "_hover_target") and self._hover_target == target_tag:
            if hasattr(self, "_hover_popup") and self._hover_popup:
                self._hover_popup.geometry(f"{popup_w}x{popup_h}+{x_pos}+{y_pos}")
            return
            
        self._on_location_hover_leave(None)
        self._hover_target = target_tag
        
        popup = tk.Toplevel(self)
        popup.is_hover_popup = True
        popup.wm_overrideredirect(True)
        popup.configure(bg="#fdf1dc", bd=2, relief=tk.SOLID)
        popup.geometry(f"{popup_w}x{popup_h}+{x_pos}+{y_pos}")
        self._hover_popup = popup
        
        toplevel = self.winfo_toplevel()
        if hasattr(toplevel, "resolve_hover_data"):
            data, dtype = toplevel.resolve_hover_data("LOC_CONN_TAG", str(loc_target))
            if data:
                from stat_renderer import StatBlockRenderer
                mini_viewer = StatBlockRenderer(popup)
                mini_viewer.pack(fill=tk.BOTH, expand=True)
                mini_viewer.clear_overlays()
                mini_viewer.text.adjust_height = lambda: None
                mini_viewer.text.configure(height=1)
                if dtype == "location": mini_viewer.render_location(data)
                elif dtype == "event": mini_viewer.render_event(data)
                popup.target_text_widget = mini_viewer.text
            else:
                tk.Label(popup, text=f"Profile '{loc_target}' not found.", bg="#fdf1dc", font=("Arial", 11, "italic")).pack(padx=20, pady=20)


import math
import json
import networkx as nx
from pathlib import Path
import tkinter as tk
from tkinter import font, ttk, messagebox, simpledialog
from dialogs import TerrainSettingsDialog

class MapGraphRenderer(tk.Frame):
    def __init__(self, parent, map_root_dir, navigate_to_node_cb, mode="location", *args, **kwargs):
        super().__init__(parent, bg="#fdf1dc", *args, **kwargs)
        self.map_root = Path(map_root_dir).resolve()
        self.navigate_cb = navigate_to_node_cb
        self.layout_path = self.map_root / "graph_layout.json"
        
        # Branch variables based on the active mode context
        self.mode = mode  # "location" or "event"
        self.label_prefix = "Layer" if self.mode == "location" else "Priority"
        self.data_key = "depths" if self.mode == "location" else "priority"
        self.node_sizes = {}

        # Active Mode Controllers
        self.current_mode = "select"  # "select", "edge", "parent", "new", "delete", "terrain"
        self.selected_node_id = None
        self.selected_edge_id = None  
        self._edge_start_node = None
        self._new_node_parent_id = None
        self.nodes_map = {}

        # Quick Access Terrain Hotbar Configuration Arrays
        self.terrain_size = 20       
        self.terrain_color = "#9ccca0" 
        self.terrain_path = self.map_root / "terrain_data.json"
        self.colors_path = self.map_root / "terrain_colors.json"
        
        self.quick_colors = [
            "#9ccca0", "#7aa37a", "#8bbbb0", "#dfa87a", "#cb7d6a",
            "#ebd391", "#9ac6e6", "#6488a4", "#b399c7", "#aeb6bf"
        ]
        
        self._terrain_image = None
        self._img_origin_x = 0
        self._img_origin_y = 0
        
        self._load_terrain_colors_config()
        self._load_terrain_data()  
        self._cached_pre_shift_mode = "select"

        # Live State Tracking & Event Skipping Flags
        self._drag_node_id = None
        self._drag_start_x = 0
        self._drag_start_y = 0
        self.node_centers = {}
        self.edge_registry = []  
        self._current_tooltip_text = ""
        self._is_panning = False  
        self._skip_canvas_press = False  
        
        # Matrix Zoom Variables
        self.zoom_level = 1.0
        self.MIN_ZOOM = 0.3
        self.MAX_ZOOM = 3.0
        
        # Layout metrics
        self.current_file_ref_width = 1000
        self._last_canvas_width = 0
        self._last_canvas_height = 0

        # Layer tracking managers
        self.visible_layers = set()
        self.visible_layers_initialized = False

        # Filtering Control Top Panel Bar
        self.layers_frame = tk.Frame(self, bg="#fdf1dc")
        self.layers_frame.pack(side=tk.TOP, fill=tk.X, pady=(5, 2))

        # Viewport Structure
        self.canvas = tk.Canvas(self, bg="#fdf1dc", highlightthickness=0)
        self.h_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.v_scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        self.canvas.configure(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Interactive Event Bindings
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.type = "MapGraphRenderer"
        
        # Node Dragging Handles
        self.canvas.tag_bind("drag_handle", "<ButtonPress-1>", self._on_node_press)
        self.canvas.tag_bind("drag_handle", "<B1-Motion>", self._on_node_motion)
        self.canvas.tag_bind("drag_handle", "<ButtonRelease-1>", self._on_node_release)
        
        # Connection click handles
        self.canvas.tag_bind("edge", "<ButtonPress-1>", self._on_edge_press)
        
        # Background Panning Tool Hooks
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press, add="+")
        self.canvas.bind("<B1-Motion>", self._on_canvas_motion, add="+")
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release, add="+")
        
        # Tooltip Interactivity Tags
        self.canvas.tag_bind("node", "<Enter>", self._on_node_hover_enter)
        self.canvas.tag_bind("node", "<Leave>", self._on_node_hover_leave)
        self.canvas.tag_bind("node", "<Motion>", self._on_node_hover_motion)
        
        self.canvas.tag_bind("link", "<Enter>", self._on_node_hover_enter)
        self.canvas.tag_bind("link", "<Leave>", self._on_node_hover_leave)
        self.canvas.tag_bind("link", "<Motion>", self._on_node_hover_motion)

        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set(), add="+")
        self.winfo_toplevel().bind("<KeyPress-Shift_L>", lambda e: self._fluid_enter_terrain_brush(), add="+")
        self.winfo_toplevel().bind("<KeyRelease-Shift_L>", lambda e: self._fluid_exit_terrain_brush(), add="+")
        self.winfo_toplevel().bind("<KeyPress-Shift_R>", lambda e: self._fluid_enter_terrain_brush(), add="+")
        self.winfo_toplevel().bind("<KeyRelease-Shift_R>", lambda e: self._fluid_exit_terrain_brush(), add="+")
        self.bind("<Destroy>", lambda e: self.save_terrain_to_disk())

    def _load_terrain_colors_config(self):
        if self.colors_path.exists():
            try:
                with open(self.colors_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if isinstance(cfg, dict) and "quick_slots" in cfg:
                        self.quick_colors = cfg["quick_slots"]
            except: pass

    def _on_canvas_press(self, event):
        if not self.nodes_map and self.current_mode != "new": return
        if self._skip_canvas_press:
            self._skip_canvas_press = False; return
        if self._drag_node_id is not None: return
            
        if self.current_mode == "terrain" or (event.state & 0x0001):
            if self.current_mode != "terrain":
                self._cached_pre_shift_mode = self.current_mode
                self.current_mode = "terrain"; self.canvas.config(cursor="crosshair"); self.draw_graph()
            self._paint_brush_grid_cells(event.x, event.y); return

        clicked_items = self.canvas.find_withtag("current")
        if clicked_items:
            tags = self.canvas.gettags(clicked_items[0])
            if any(t in tags for t in ["drag_handle", "node", "link", "edge"]): return
        
        if self.current_mode == "new":
            cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            parent_path = Path(self._new_node_parent_id) if self._new_node_parent_id else self.map_root
            self._handle_canvas_new_node_creation(parent_path, cx, cy)
            self._new_node_parent_id = None; self.current_mode = "select"; self.draw_graph(); return

        self._is_panning = True; self.canvas.scan_mark(event.x, event.y)

    def _on_canvas_motion(self, event):
        if self.current_mode == "terrain" or (event.state & 0x0001):
            self._paint_brush_grid_cells(event.x, event.y); return
        if self._is_panning: self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_canvas_release(self, event): self._is_panning = False

    def adjust_zoom(self, units):
        factor = 1.1 if units < 0 else 0.9; new_zoom = self.zoom_level * factor
        if self.MIN_ZOOM <= new_zoom <= self.MAX_ZOOM: self.zoom_level = new_zoom; self.draw_graph(redraw_controls=False)

    def toggle_edge_mode(self):
        if self.current_mode == "edge": self.current_mode = "select"; self._edge_start_node = None
        else:
            self.current_mode = "edge"
            if self.selected_node_id: self._edge_start_node = self.selected_node_id; self.selected_node_id = None  
            else: self._edge_start_node = None
        self._new_node_parent_id = None; self.draw_graph()

    def toggle_parent_mode(self):
        if self.current_mode == "parent": self.current_mode = "select"; self._edge_start_node = None
        else:
            self.current_mode = "parent"
            if self.selected_node_id: self._edge_start_node = self.selected_node_id; self.selected_node_id = None  
            else: self._edge_start_node = None
        self._new_node_parent_id = None; self.draw_graph()

    def toggle_new_mode(self):
        if self.current_mode == "new": self.current_mode = "select"; self._new_node_parent_id = None
        else:
            self.current_mode = "new"
            if self.selected_node_id: self._new_node_parent_id = self.selected_node_id; self.selected_node_id = None  
            else: self._new_node_parent_id = None
        self._edge_start_node = None; self.draw_graph()

    def toggle_delete_mode(self):
        if self.selected_node_id:
            self._delete_node(self.selected_node_id); self.selected_node_id = None; self.current_mode = "select"; self.draw_graph()
        elif self.selected_edge_id:
            u, v = self.selected_edge_id
            if str(Path(v).parent.resolve()) == str(Path(u).resolve()):
                if messagebox.askyesno("Confirm Detach", f"Remove parent relation? This will move '{Path(v).name}' to the root folder."):
                    self._skip_canvas_press = True; self._remove_parent_child_edge(u, v)
            else:
                if messagebox.askyesno("Confirm Delete", "Delete this connection permanently?"):
                    self._skip_canvas_press = True; self._delete_edge_connection(u, v)
            self.selected_edge_id = None; self.current_mode = "select"; self.draw_graph()
        else:
            self.current_mode = "delete" if self.current_mode != "delete" else "select"
            self._edge_start_node = None; self._new_node_parent_id = None; self.draw_graph()

    def handle_shortcut(self, key):
        """Intercepts system hotkey triggers from the main app window routing pipeline."""

        if self.selected_node_id:
            if key in ['plus', 'equal', 'add']:
                self._adjust_selected_node_depth(1)
                return True
            elif key in ['minus', 'underscore', 'subtract']:
                self._adjust_selected_node_depth(-1)
                return True
            elif key in ['Up', 'up']:
                cur_size = self.node_sizes.get(self.selected_node_id, 32)
                new_size = min(80, cur_size + 8)
                if new_size != cur_size:
                    self.node_sizes[self.selected_node_id] = new_size
                    current_width = max(100, self.canvas.winfo_width())
                    self._write_current_layout_to_disk(current_width, dragged_id=self.selected_node_id)
                    self.draw_graph()
                return True
            elif key in ['Down', 'down']:
                cur_size = self.node_sizes.get(self.selected_node_id, 32)
                new_size = max(24, cur_size - 8)
                if new_size != cur_size:
                    self.node_sizes[self.selected_node_id] = new_size
                    current_width = max(100, self.canvas.winfo_width())
                    self._write_current_layout_to_disk(current_width, dragged_id=self.selected_node_id)
                    self.draw_graph()
                return True

        # FALLBACK: If no node profile is selected, keys map to the hotbar palette swatches
        key_map = {
            '1': 0, 'ampersand': 0, '2': 1, 'eacute': 1, '3': 2, 'quotedbl': 2,
            '4': 3, 'apostrophe': 3, '5': 4, 'parenleft': 4, '6': 5, 'minus': 5,
            '7': 6, 'egrave': 6, '8': 7, 'underscore': 7, '9': 8, 'ccedilla': 8,
            '0': 9, 'agrave': 9
        }
        if key in key_map:
            self.terrain_color = self.quick_colors[key_map[key]]
            self.draw_graph()
            return True
        elif key == 'x':
            self.terrain_color = "#ffffff"  # Eraser selection shortcut
            self.draw_graph()
            return True
        elif key == 'i': self.open_node_icon_selector(); return True
        elif key == 'l': self.toggle_edge_mode(); return True
        elif key == 'p': self.toggle_parent_mode(); return True
        elif key == 'a': self.toggle_new_mode(); return True
        elif key in ['delete', 'backspace']: self.toggle_delete_mode(); return True
        
        # Fallback depth options if explicit modification keys are used without a selected node
        elif key in ['plus', 'equal', 'add']: self._adjust_selected_node_depth(1); return True
        elif key in ['minus', 'underscore', 'subtract']: self._adjust_selected_node_depth(-1); return True
        elif key == 't': self.open_terrain_settings_panel(); return True
        return False

    def recenter_view(self):
        try:
            scroll_region_str = self.canvas.cget("scrollregion")
            if not scroll_region_str: return
            sr = [float(x) for x in scroll_region_str.split()]
            if len(sr) == 4:
                sr_x1, sr_y1, sr_x2, sr_y2 = sr
                sr_w = sr_x2 - sr_x1; sr_h = sr_y2 - sr_y1
                if sr_w > 0 and sr_h > 0:
                    self.canvas.xview_moveto(max(0.0, min(1.0, (0.0 - sr_x1) / sr_w)))
                    self.canvas.yview_moveto(max(0.0, min(1.0, (0.0 - sr_y1) / sr_h)))
        except Exception: pass

    def _toggle_layer(self, layer):
        if layer in self.visible_layers: self.visible_layers.remove(layer)
        else: self.visible_layers.add(layer)
        self.draw_graph()

    def _get_layer_color(self, layer):
        colors = {0: "#FFB300", 1: "#2ECC71", 2: "#00E5FF", -1: "#E74C3C", -2: "#9B59B6", -3: "#FF5722"}
        if layer in colors: return colors[layer]
        palette = ["#f4ccd6", "#e1f5fe", "#efebe9", "#f1f8e9", "#fffde7", "#f3e5f5"]
        return palette[abs(layer) % len(palette)]

    def _on_canvas_resize(self, event):
        if event.width != self._last_canvas_width or event.height != self._last_canvas_height:
            self._last_canvas_width = event.width; self._last_canvas_height = event.height; self.draw_graph()

    def draw_graph(self, redraw_controls=True):
        self._on_node_hover_leave(None); self._is_panning = False
        self.canvas.delete("all"); self.node_centers.clear(); self.edge_registry.clear(); self.nodes_map.clear()
        
        self._collect_nodes(self.map_root, self.nodes_map)

        current_canvas_width = self.canvas.winfo_width()
        if current_canvas_width <= 1: current_canvas_width = self.current_file_ref_width
        scale_factor = current_canvas_width / self.current_file_ref_width

        sorted_layers = []
        if self.nodes_map:
            all_layers = set()
            for info in self.nodes_map.values(): all_layers.update(info.get("depths", [0]))
            sorted_layers = sorted(list(all_layers))
            if not self.visible_layers_initialized:
                self.visible_layers = set(sorted_layers); self.visible_layers_initialized = True
            else: self.visible_layers = self.visible_layers.intersection(all_layers)
        else:
            # --- FIXED: RESET INITIALIZATION ENGINE WHEN DIRECTORY IS EMPTY ---
            self.visible_layers_initialized = False

        if redraw_controls:
            for widget in self.layers_frame.winfo_children(): widget.destroy()
            
            row1 = tk.Frame(self.layers_frame, bg="#fdf1dc"); row1.pack(fill=tk.X, side=tk.TOP)
            row2 = tk.Frame(self.layers_frame, bg="#fdf1dc"); row2.pack(fill=tk.X, side=tk.TOP, pady=3)
            row3 = tk.Frame(self.layers_frame, bg="#fdf1dc"); row3.pack(fill=tk.X, side=tk.TOP)

            if sorted_layers:
                tk.Label(row1, text=f"{self.label_prefix}:", font=("Georgia", 9, "bold"), bg="#fdf1dc", fg="#58180d").pack(side=tk.LEFT, padx=(10, 5))
                
                filters_frame = tk.Frame(row1, bg="#fdf1dc")
                filters_frame.pack(side=tk.LEFT, padx=5)
                
                for layer in sorted_layers:
                    is_on = layer in self.visible_layers
                    if is_on:
                        btn = tk.Button(filters_frame, text=str(layer), bg="#4a90e2", fg="white", 
                                        font=("Arial", 8, "bold"), width=3, relief=tk.RAISED,
                                        command=lambda l=layer: self._toggle_layer(l))
                    else:
                        btn = tk.Button(filters_frame, text=str(layer), font=("Arial", 8, "bold"), 
                                        width=3, relief=tk.SUNKEN,
                                        command=lambda l=layer: self._toggle_layer(l))
                    btn.pack(side=tk.LEFT, padx=2)

            tk.Button(row1, text="Recenter (0,0)", bg="#4a90e2", fg="white", font=("Arial", 8, "bold"), command=self.recenter_view).pack(side=tk.LEFT, padx=(12, 2))
            
            for mode_lbl, mode_val, bg_c in [("Edge (L)", "edge", "#4a90e2"), ("Parent (P)", "parent", "#4a90e2"), ("New (A)", "new", "#2ecc71"), ("Icon (I)", "icon", "#dfa87a"), ("Delete (Del)", "delete", "#ff4d4d")]:
                is_active = (self.current_mode == mode_val)
                if mode_val == "icon":
                    cmd = self.open_node_icon_selector
                else:
                    cmd = getattr(self, f"toggle_{mode_val}_mode") if mode_val != "parent" else self.toggle_parent_mode
                tk.Button(row1, text=mode_lbl, bg=bg_c if is_active else "#e0cbb0", fg="white" if is_active else "black", font=("Arial", 8, "bold"), command=cmd).pack(side=tk.LEFT, padx=2)

            tk.Label(row2, text="Quick Palette:", font=("Georgia", 9, "bold"), bg="#fdf1dc", fg="#58180d").pack(side=tk.LEFT, padx=(10, 5))
            for idx, qc_hex in enumerate(self.quick_colors):
                display_num = str((idx + 1) % 10); is_active_color = (self.terrain_color.lower() == qc_hex.lower())
                sq_frame = tk.Frame(row2, width=22, height=18, bg=qc_hex, bd=2 if is_active_color else 1, relief=tk.SOLID if is_active_color else tk.GROOVE)
                sq_frame.pack(side=tk.LEFT, padx=2); sq_frame.pack_propagate(False)
                lbl_num = tk.Label(sq_frame, text=display_num, font=("Arial", 7, "bold"), bg=qc_hex, fg="black")
                lbl_num.pack(expand=True)
                for w in [sq_frame, lbl_num]: w.bind("<Button-1>", lambda e, hc=qc_hex: [setattr(self, 'terrain_color', hc), self.draw_graph(redraw_controls=True)])

            is_eraser_active = (self.terrain_color.lower() == "#ffffff")
            er_frame = tk.Frame(row2, width=22, height=18, bg="#ffffff", bd=2 if is_eraser_active else 1, relief=tk.SOLID if is_eraser_active else tk.GROOVE)
            er_frame.pack(side=tk.LEFT, padx=(6, 2)); er_frame.pack_propagate(False)
            lbl_er = tk.Label(er_frame, text="X", font=("Arial", 7, "bold"), bg="#ffffff", fg="red")
            lbl_er.pack(expand=True)
            for w in [er_frame, lbl_er]: w.bind("<Button-1>", lambda e: [setattr(self, 'terrain_color', '#ffffff'), self.draw_graph(redraw_controls=True)])

            try:
                hex_strip = self.terrain_color.lstrip('#')
                text_fg = "white" if (int(hex_strip[0:2],16)*0.299 + int(hex_strip[2:4],16)*0.587 + int(hex_strip[4:6],16)*0.114) < 130 else "black"
            except: text_fg = "black"
            tk.Button(row2, text="Select Master...", bg=self.terrain_color, fg=text_fg, font=("Arial", 8, "bold"), command=self.open_terrain_settings_panel).pack(side=tk.LEFT, padx=12)

            tk.Label(row3, text="Brush Radius:", font=("Georgia", 9, "bold"), bg="#fdf1dc", fg="#58180d").pack(side=tk.LEFT, padx=(10, 5))
            for size_val in [10, 20, 50, 100]:
                is_sz_active = (self.terrain_size == size_val)
                tk.Button(row3, text=f"{size_val}px", bg="#4a90e2" if is_sz_active else "#e0cbb0", fg="white" if is_sz_active else "black",
                          font=("Arial", 8, "bold"), command=lambda sv=size_val: [setattr(self, 'terrain_size', sv), self.draw_graph(redraw_controls=True)]).pack(side=tk.LEFT, padx=2)

        if not self.nodes_map: return

        sf = scale_factor; zl = self.zoom_level; self._render_terrain_image(sf, zl)

        if self.current_mode == "terrain":
            scroll_region_str = self.canvas.cget("scrollregion")
            sx1, sy1, sx2, sy2 = [int(float(x)) for x in scroll_region_str.split()] if scroll_region_str else (-2000, -2000, 4000, 4000)
            unscaled_block = self.terrain_size
            for ux in range(-500, 500):
                gx = int(ux * unscaled_block * sf * zl)
                if sx1 <= gx <= sx2: self.canvas.create_line(gx, sy1, gx, sy2, fill="#d9ad6c", width=1, dash=(2, 4), tags="assistance_line")
            for uy in range(-500, 500):
                gy = int(uy * unscaled_block * sf * zl)
                if sy1 <= gy <= sy2: self.canvas.create_line(sx1, gy, sx2, gy, fill="#d9ad6c", width=1, dash=(2, 4), tags="assistance_line")

        G = nx.DiGraph()
        for path_str, info in self.nodes_map.items(): G.add_node(path_str, name=info["name"], node_obj=info["node"])
        for path_str, info in self.nodes_map.items():
            for target_item, desc in info["connections"]:
                t_path = target_item.get("path", target_item.get("target", "")) if isinstance(target_item, dict) else str(target_item)
                t_path_str = str(Path(t_path).resolve()).lower()
                target_path = next((p for p in self.nodes_map.keys() if p.lower() == t_path_str), None)
                if target_path: G.add_edge(path_str, target_path, type="connection", description=desc)
        for path_str, info in self.nodes_map.items():
            parent_path_str = str(Path(path_str).parent)
            if parent_path_str in self.nodes_map: G.add_edge(parent_path_str, path_str, type="structure")

        saved_nodes = {}
        if self.layout_path.exists():
            try:
                with open(self.layout_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "reference_width" in data and "nodes" in data:
                        self.current_file_ref_width = data["reference_width"]; saved_nodes = data["nodes"]
            except: pass

        is_planar, _ = nx.check_planarity(G)
        raw_pos = nx.planar_layout(G) if is_planar else nx.spring_layout(G, k=1.8, iterations=100, seed=42)
        x_vals = [c[0] for c in raw_pos.values()]; y_vals = [c[1] for c in raw_pos.values()]
        min_x, max_x = min(x_vals), max(x_vals); min_y, max_y = min(y_vals), max(y_vals)
        x_range = (max_x - min_x) if max_x != min_x else 1; y_range = (max_y - min_y) if max_y != min_y else 1
        self.node_radius = int(16 * self.zoom_level)  
        needs_save_update = False

        # --- FIXED: REUNITE THE VISIBILITY PIPELINES ACROSS LOCATIONS & EVENTS WITH CONSTRAINTS ---
        intrinsically_visible = set()
        for path_str, info in self.nodes_map.items():
            if any(d in self.visible_layers for d in info.get("depths", [0])): intrinsically_visible.add(path_str)

        extra_visible = set()
        for u, v, edge_data in G.edges(data=True):
            etype = edge_data.get("type")
            if etype == "connection":
                # Relationship edges lookups pull nodes symmetrically into view
                if u in intrinsically_visible: extra_visible.add(v)
                if v in intrinsically_visible: extra_visible.add(u)
            elif etype == "structure":
                # Hierarchy: u is parent, v is child. 
                # Parents can look down to see children, but hidden children never auto-expand under active parents.
                if v in intrinsically_visible: extra_visible.add(u)

        visible_nodes = intrinsically_visible.union(extra_visible)
        # -----------------------------------------------------------------------------------------

        for node_id in G.nodes:
            if node_id not in visible_nodes: continue
            node_size = saved_nodes.get(node_id, {}).get("size", 32)
            self.node_sizes[node_id] = node_size
            
            if node_id in saved_nodes and isinstance(saved_nodes[node_id], dict) and "x" in saved_nodes[node_id]:
                center_x = int(saved_nodes[node_id]["x"] * scale_factor * self.zoom_level)
                center_y = int(saved_nodes[node_id]["y"] * scale_factor * self.zoom_level)
            else:
                coords = raw_pos[node_id]; norm_x = (coords[0] - min_x) / x_range; norm_y = (coords[1] - min_y) / y_range
                base_x, base_y = int((0.15 + norm_x * 0.70) * 1000), int((0.15 + norm_y * 0.70) * 800)
                center_x, center_y = int(base_x * scale_factor * self.zoom_level), int(base_y * scale_factor * self.zoom_level)
                saved_nodes[node_id] = {"x": base_x, "y": base_y, "size": node_size}; needs_save_update = True
            self.node_centers[node_id] = [center_x, center_y]

        if needs_save_update: self._write_current_layout_to_disk(current_canvas_width)

        arrow_padding = self.node_radius + max(2, int(4 * scale_factor * self.zoom_level))
        edge_thickness = max(1, int(1.2 * self.zoom_level))
        
        for u, v, edge_data in G.edges(data=True):
            if u not in visible_nodes or v not in visible_nodes: continue
            if u in self.node_centers and v in self.node_centers:
                ux, uy = self.node_centers[u]; vx, vy = self.node_centers[v]
                desc = edge_data.get("description", ""); dx, dy = vx - ux, vy - uy; length = math.hypot(dx, dy) or 1
                
                # DYNAMIC REQUIREMENT: Fetch individual padding metrics per source/target pair
                rad_u = int((self.node_sizes.get(u, 32) / 2) * self.zoom_level)
                rad_v = int((self.node_sizes.get(v, 32) / 2) * self.zoom_level)
                
                arrow_padding_u = rad_u + max(2, int(4 * scale_factor * self.zoom_level))
                arrow_padding_v = rad_v + max(2, int(4 * scale_factor * self.zoom_level))
                
                is_edge_selected = (self.selected_edge_id == (u, v))
                if is_edge_selected:
                    current_fill = "#ff9900"; current_thick = max(4, int(5 * self.zoom_level))
                else:
                    if edge_data.get("type") == "structure":
                        current_fill = "#ffffff"; current_thick = max(1, int(1.0 * self.zoom_level))
                    else:
                        current_fill = "#000000"; current_thick = edge_thickness
                
                a_shape = (max(5, int(7 * self.zoom_level)), max(6, int(8 * self.zoom_level)), max(2, int(2.5 * self.zoom_level)))
                
                if edge_data.get("type") == "connection":
                    if G.has_edge(v, u) and G[v][u].get("type") == "connection":
                        mid_x, mid_y = (ux + vx) / 2, (uy + vy) / 2
                        nx_val, ny_val = -dy / length, dx / length
                        ctrl_x = mid_x + nx_val * (35 * self.zoom_level)
                        ctrl_y = mid_y + ny_val * (35 * self.zoom_level)
                        tdx, tdy = vx - ctrl_x, vy - ctrl_y; t_length = math.hypot(tdx, tdy) or 1
                        
                        end_x = vx - (tdx / t_length) * arrow_padding_v if t_length > arrow_padding_v else vx
                        end_y = vy - (tdy / t_length) * arrow_padding_v if t_length > arrow_padding_v else vy
                        
                        fdx, fdy = ctrl_x - ux, ctrl_y - uy
                        f_length = math.hypot(fdx, fdy) or 1
                        start_x = ux + (fdx / f_length) * arrow_padding_u if f_length > arrow_padding_u else ux
                        start_y = uy + (fdy / f_length) * arrow_padding_u if f_length > arrow_padding_u else uy
                        
                        line_id = self.canvas.create_line(start_x, start_y, ctrl_x, ctrl_y, end_x, end_y, smooth=True, arrow=tk.LAST, fill=current_fill, width=current_thick, dash=(4, 4), arrowshape=a_shape, tags=(f"from:{u}", f"to:{v}", "edge"))
                        self.edge_registry.append({"id": line_id, "u": u, "v": v, "curved": True, "padding_u": arrow_padding_u, "padding_v": arrow_padding_v})
                    else:
                        end_x = vx - (dx / length) * arrow_padding_v if length > arrow_padding_v else vx
                        end_y = vy - (dy / length) * arrow_padding_v if length > arrow_padding_v else vy
                        
                        start_x = ux + (dx / length) * arrow_padding_u if length > arrow_padding_u else ux
                        start_y = uy + (dy / length) * arrow_padding_u if length > arrow_padding_u else uy
                        
                        line_id = self.canvas.create_line(start_x, start_y, end_x, end_y, arrow=tk.LAST, fill=current_fill, width=current_thick, dash=(4, 4), arrowshape=a_shape, tags=(f"from:{u}", f"to:{v}", "edge"))
                        self.edge_registry.append({"id": line_id, "u": u, "v": v, "curved": False, "padding_u": arrow_padding_u, "padding_v": arrow_padding_v})
                    if desc:
                        self.canvas.tag_bind(line_id, "<Enter>", lambda e, lid=line_id, d=desc: self._on_edge_enter(e, lid, d))
                        self.canvas.tag_bind(line_id, "<Motion>", self._on_edge_motion)
                        self.canvas.tag_bind(line_id, "<Leave>", lambda e, lid=line_id: self._on_edge_leave(e, lid))
                else:
                    end_x = vx - (dx / length) * arrow_padding_v if length > arrow_padding_v else vx
                    end_y = vy - (dy / length) * arrow_padding_v if length > arrow_padding_v else vy
                    
                    start_x = ux + (dx / length) * arrow_padding_u if length > arrow_padding_u else ux
                    start_y = uy + (dy / length) * arrow_padding_u if length > arrow_padding_u else uy
                    
                    line_id = self.canvas.create_line(start_x, start_y, end_x, end_y, fill=current_fill, dash=(4, 4), width=current_thick, arrow=tk.LAST, arrowshape=a_shape, tags=(f"from:{u}", f"to:{v}", "edge"))
                    self.edge_registry.append({"id": line_id, "u": u, "v": v, "curved": False, "padding_u": arrow_padding_u, "padding_v": arrow_padding_v})

        font_size = max(7, int(9 * self.zoom_level))
        for node_id, (center_x, center_y) in self.node_centers.items():
            if node_id not in visible_nodes: continue
            info = self.nodes_map[node_id]; node_obj = info["node"]
            bg_color = self._get_layer_color(info.get("depths", [0])[0])
            is_slc = (node_id == self.selected_node_id) or (node_id == self._edge_start_node) or (node_id == self._new_node_parent_id)
            
            # Look up dynamic sizes and calculate radius metric variables locally
            n_size = self.node_sizes.get(node_id, 32)
            n_radius = int((n_size / 2) * self.zoom_level)
            text_offset = n_radius + max(4, int(8 * scale_factor * self.zoom_level))
            
            node_tags = ("node", "drag_handle", f"path:{node_id}", f"group:{node_id}")
            
            img_obj = self._get_node_icon_image(node_id, n_size) # PASS TARGET INDIVIDUAL SIZE
            if img_obj:
                self.canvas.create_image(center_x, center_y, image=img_obj, tags=node_tags)
                if is_slc:
                    self.canvas.create_rectangle(center_x - n_radius - 2, center_y - n_radius - 2, 
                                                 center_x + n_radius + 2, center_y + n_radius + 2, 
                                                 outline="#4a90e2", width=3, tags=node_tags)
            else:
                border_w = 4 if is_slc else (1 if node_obj.is_entity else 2)
                outline_color = "#4a90e2" if is_slc else "#58180d"
                self.canvas.create_oval(center_x - n_radius, center_y - n_radius, center_x + n_radius, center_y + n_radius, 
                                        fill=bg_color, outline=outline_color, width=border_w, tags=node_tags)
            # --- FIXED: UNNESTED OUTSIDE THE IF/ELSE GEOMETRY CHECKER ---
            dx_sum, dy_sum = 0, 0
            for neighbor in G.neighbors(node_id):
                if neighbor not in visible_nodes: continue
                nx_c, ny_c = self.node_centers[neighbor]
                ndx, ndy = nx_c - center_x, ny_c - center_y
                dist = math.hypot(ndx, ndy) or 1
                dx_sum += ndx / dist; dy_sum += ndy / dist
            for predecessor in G.predecessors(node_id):
                if predecessor not in visible_nodes: continue
                px_c, py_c = self.node_centers[predecessor]; ndx, ndy = px_c - center_x, py_c - center_y; dist = math.hypot(ndx, ndy) or 1
                dx_sum += ndx / dist; dy_sum += ndy / dist

            text_x, text_y = center_x, (center_y - text_offset if dy_sum >= 0 else center_y + text_offset)
            text_anchor = tk.S if dy_sum >= 0 else tk.N  

            text_id = self.canvas.create_text(text_x, text_y, text=info["name"], font=("Georgia", font_size, "bold", "underline"), 
                                              fill="#4a90e2", width=int(120*self.zoom_level), justify="center", anchor=text_anchor, tags=("link", node_id, f"group:{node_id}"))
            self.canvas.tag_bind(text_id, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
            self.canvas.tag_bind(text_id, "<Leave>", lambda e: self.canvas.config(cursor=""))
            
            def on_text_link_click(e, n_obj=node_obj):
                if self.current_mode == "select": self.navigate_cb(n_obj)
                else: self._on_node_press(e)
                return "break"
            self.canvas.tag_bind(text_id, "<Button-1>", on_text_link_click)

        self.canvas.tag_raise("edge"); self.canvas.tag_raise("node"); self.canvas.tag_raise("link")
        self._update_scroll_region()

    def _update_scroll_region(self):
        if not self.node_centers:
            self.canvas.configure(scrollregion=(0, 0, 1000, 800)); return
        cx_vals = [c[0] for c in self.node_centers.values()]; cy_vals = [c[1] for c in self.node_centers.values()]
        frame_w, frame_h = max(100, self.canvas.winfo_width()), max(100, self.canvas.winfo_height())
        min_region_x, max_region_x = min(cx_vals) - (frame_w / 2), max(cx_vals) + (frame_w / 2)
        min_region_y, max_region_y = min(cy_vals) - (frame_h / 2), max(cy_vals) + (frame_h / 2)
        if min_region_x > 0: min_region_x = 0
        if min_region_y > 0: min_region_y = 0
        if max_region_x < frame_w: max_region_x = frame_w
        if max_region_y < frame_h: max_region_y = frame_h
        self.canvas.configure(scrollregion=(min_region_x, min_region_y, max_region_x, max_region_y))

    def _on_edge_enter(self, event, line_id, description):
        if self.selected_edge_id != (self.canvas.gettags(line_id)[0].split("from:",1)[1], self.canvas.gettags(line_id)[1].split("to:",1)[1]):
            self.canvas.itemconfig(line_id, fill="#4a90e2", width=max(2, int(3.5*self.zoom_level)))
        self.canvas.config(cursor="hand2"); self._show_tooltip(event, description)

    def _on_edge_motion(self, event): self._show_tooltip(event, None)
    def _on_edge_leave(self, event, line_id):
        tags = self.canvas.gettags(line_id)
        if tags and len(tags) >= 2:
            u = tags[0].split("from:", 1)[1]; v = tags[1].split("to:", 1)[1]
            if self.selected_edge_id == (u, v):
                self.canvas.itemconfig(line_id, fill="#ff9900", width=max(4, int(5 * self.zoom_level)))
                self.canvas.config(cursor=""); self.canvas.delete("tooltip"); return
        self.canvas.itemconfig(line_id, fill="#000000", width=max(1, int(2*self.zoom_level)))
        self.canvas.config(cursor=""); self.canvas.delete("tooltip")

    def _show_tooltip(self, event, description):
        self.canvas.delete("tooltip")
        if description is None: description = self._current_tooltip_text
        else: self._current_tooltip_text = description
        if not description.strip(): return
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        t_id = self.canvas.create_text(cx + 15, cy + 15, text=description, font=("Arial", 10, "bold"), fill="black", anchor="nw", width=220, tags="tooltip")
        bbox = self.canvas.bbox(t_id)
        if bbox:
            bg_id = self.canvas.create_rectangle(bbox[0]-6, bbox[1]-4, bbox[2]+6, bbox[3]+4, fill="#fae6c5", outline="#7a200d", width=1, tags="tooltip")
            self.canvas.tag_lower(bg_id, t_id)

    def _on_edge_press(self, event):
        item = self.canvas.find_withtag("current")[0]; tags = self.canvas.gettags(item)
        from_tag = next((t for t in tags if t.startswith("from:")), None)
        to_tag = next((t for t in tags if t.startswith("to:")), None)
        if not (from_tag and to_tag): return "break"
        u = from_tag.split("from:", 1)[1]; v = to_tag.split("to:", 1)[1]; self._skip_canvas_press = True
        
        if self.current_mode == "delete":
            if str(Path(v).parent.resolve()) == str(Path(u).resolve()):
                if messagebox.askyesno("Confirm Detach", f"Remove parent relation? This will move '{Path(v).name}' to the root folder."):
                    self._remove_parent_child_edge(u, v); self._edge_start_node = None; self.current_mode = "select"; self.draw_graph()
            else:
                if messagebox.askyesno("Confirm Delete", "Delete this connection permanently?"):
                    self._delete_edge_connection(u, v); self._edge_start_node = None; self.current_mode = "select"; self.draw_graph()
            return "break"
        elif self.current_mode == "select":
            self.selected_node_id = None
            self.selected_edge_id = None if self.selected_edge_id == (u, v) else (u, v)
            self.draw_graph(); return "break"
        return "break"

    def _on_node_press(self, event):
        item = self.canvas.find_withtag("current")[0]
        path_tag = next((t for t in self.canvas.gettags(item) if t.startswith("path:")), None)
        if not path_tag: return
        node_id = path_tag.split("path:", 1)[1]; self._skip_canvas_press = True
        
        if self.current_mode == "edge":
            if self._edge_start_node is None:
                self._edge_start_node = node_id
                self.draw_graph()  # FIXED: Call draw_graph instead of itemconfig
            else:
                if self._edge_start_node != node_id: self._create_edge_connection(self._edge_start_node, node_id)
                self._edge_start_node = None; self.current_mode = "select"; self.draw_graph()
            return "break"
        
        elif self.current_mode == "parent":
            if self._edge_start_node is None:
                self._edge_start_node = node_id
                self.draw_graph()  # FIXED: Call draw_graph instead of itemconfig
            else:
                if self._edge_start_node != node_id: self._create_parent_child_relation(self._edge_start_node, node_id)
                self._edge_start_node = None; self.current_mode = "select"; self.draw_graph()
            return "break"
            
        elif self.current_mode == "new":
            self._new_node_parent_id = None if self._new_node_parent_id == node_id else node_id
            self.draw_graph(); return "break"
            
        elif self.current_mode == "delete":
            self._delete_node(node_id); self.current_mode = "select"; return "break"
            
        else: 
            self._drag_node_id = node_id; self._drag_start_x = self.canvas.canvasx(event.x); self._drag_start_y = self.canvas.canvasy(event.y)
            self._is_panning = False; self.selected_edge_id = None  
            
            if self.selected_node_id == node_id:
                self.selected_node_id = None
            else:
                self.selected_node_id = node_id
                
            #self.draw_graph()  # FIXED: Redraw canvas to update selections cleanly
            return "break"

    def _on_node_motion(self, event):
        if self.current_mode != "select" or not self._drag_node_id: return
        cur_x, cur_y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        dx, dy = cur_x - self._drag_start_x, cur_y - self._drag_start_y
        proposed_x = self.node_centers[self._drag_node_id][0] + dx
        proposed_y = self.node_centers[self._drag_node_id][1] + dy
        self.canvas.move(f"group:{self._drag_node_id}", dx, dy)
        self.node_centers[self._drag_node_id][0] = proposed_x; self.node_centers[self._drag_node_id][1] = proposed_y

        for edge in self.edge_registry:
            if edge["u"] == self._drag_node_id or edge["v"] == self._drag_node_id:
                ux, uy = self.node_centers[edge["u"]]; vx, vy = self.node_centers[edge["v"]]
                
                # FIX: Extract the specialized source/target padding thresholds safely
                p_u = edge.get("padding_u", edge.get("padding", 16))
                p_v = edge.get("padding_v", edge.get("padding", 16))
                
                lx, ly = vx - ux, vy - uy; length = math.hypot(lx, ly) or 1
                if edge["curved"]:
                    mid_x, mid_y = (ux + vx) / 2, (uy + vy) / 2
                    nx_val, ny_val = -ly / length, lx / length
                    ctrl_x, ctrl_y = mid_x + nx_val * (35 * self.zoom_level), mid_y + ny_val * (35 * self.zoom_level)
                    tdx, tdy = vx - ctrl_x, vy - ctrl_y; t_length = math.hypot(tdx, tdy) or 1
                    end_x = vx - (tdx / t_length) * p_v if t_length > p_v else vx
                    end_y = vy - (tdy / t_length) * p_v if t_length > p_v else vy
                    
                    # Apply padded source node dynamic offset coordinates
                    fdx, fdy = ctrl_x - ux, ctrl_y - uy
                    f_length = math.hypot(fdx, fdy) or 1
                    start_x = ux + (fdx / f_length) * p_u if f_length > p_u else ux
                    start_y = uy + (fdy / f_length) * p_u if f_length > p_u else uy
                    
                    self.canvas.coords(edge["id"], start_x, start_y, ctrl_x, ctrl_y, end_x, end_y)
                else:
                    end_x = vx - (lx / length) * p_v if length > p_v else vx
                    end_y = vy - (ly / length) * p_v if length > p_v else vy
                    
                    # Apply padded source node dynamic offset coordinates
                    start_x = ux + (lx / length) * p_u if length > p_u else ux
                    start_y = uy + (ly / length) * p_u if length > p_u else uy
                    
                    self.canvas.coords(edge["id"], start_x, start_y, end_x, end_y)
                    
        self._drag_start_x, self._drag_start_y = cur_x, cur_y; self._update_scroll_region()

    def _on_node_release(self, event):
        if self.current_mode != "select" or not self._drag_node_id: return
        dragged_id = self._drag_node_id; self._drag_node_id = None
        current_width = max(100, self.canvas.winfo_width())
        self._write_current_layout_to_disk(current_width, dragged_id=dragged_id); self.draw_graph()

    def _create_edge_connection(self, source_id, target_id):
        source_info = self.nodes_map.get(source_id); target_info = self.nodes_map.get(target_id)
        if not source_info or not target_info: return
        stat_path = source_info["node"].stat_path
        if not stat_path or not Path(stat_path).exists():
            stat_path = Path(source_id) / f"{Path(source_id).name}.json"
            default_data = {"name": source_info["name"], "description": "", "monsters": [], "npcs": [], "combats": [], "events" if self.mode == "location" else "locations": [], "objects": [], "connections": []}
            with open(stat_path, "w", encoding="utf-8") as f: json.dump(default_data, f, indent=4)
        try:
            with open(stat_path, "r", encoding="utf-8") as f: data = json.load(f)
            if "connections" not in data: data["connections"] = []
            if not any(str(Path(c.get("target", {}).get("path") if isinstance(c.get("target"), dict) else c.get("target", "")).resolve()).lower() == str(Path(target_id).resolve()).lower() for c in data["connections"]):
                data["connections"].append({"target": {"name": target_info["name"], "path": str(Path(target_id).resolve())}, "description": ""})
                with open(stat_path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)
        except Exception as e: print(f"Edge creation save operation failed: {e}")

    def _delete_edge_connection(self, source_id, target_id):
        source_info = self.nodes_map.get(source_id)
        if not source_info: return
        stat_path = source_info["node"].stat_path
        if not stat_path or not Path(stat_path).exists(): return
        try:
            with open(stat_path, "r", encoding="utf-8") as f: data = json.load(f)
            if "connections" in data:
                orig_len = len(data["connections"])
                data["connections"] = [c for c in data["connections"] if str(Path(c.get("target", {}).get("path") if isinstance(c.get("target"), dict) else c.get("target", "")).resolve()).lower() != str(Path(target_id).resolve()).lower()]
                if len(data["connections"]) != orig_len:
                    with open(stat_path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)
                    toplevel = self.winfo_toplevel()
                    if hasattr(toplevel, "refresh_tree_silent"): toplevel.refresh_tree_silent()
        except Exception as e: print(f"Edge compilation deletion aborted: {e}")

    def _adjust_selected_node_depth(self, delta):
        if not self.selected_node_id: return
        info = self.nodes_map.get(self.selected_node_id)
        if not info or not info["node"].stat_path: return
        stat_path = Path(info["node"].stat_path)
        if not stat_path.exists(): return
        try:
            with open(stat_path, "r", encoding="utf-8") as f: data = json.load(f)
            depths = data.get(self.data_key, [0])
            if not isinstance(depths, list): depths = [depths]
            data[self.data_key] = [d + delta for d in depths]
            with open(stat_path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)
            self.draw_graph()
        except Exception as e: print(f"Failed depth modification: {e}")

    def _remove_parent_child_edge(self, parent_id, child_id):
        import shutil
        old_child_path = Path(child_id); new_child_path = self.map_root / old_child_path.name
        if new_child_path.exists(): messagebox.showerror("Error", f"A node named '{old_child_path.name}' already exists at the root."); return
        try:
            shutil.move(str(old_child_path), str(new_child_path)); toplevel = self.winfo_toplevel()
            if hasattr(toplevel, "sync_reciprocal_relations"):
                toplevel.sync_reciprocal_relations(old_path_prefix=old_child_path, new_path_prefix=new_child_path)
                toplevel.refresh_tree_silent()
                # FIXED: Removed clear_viewer_and_tree() here as well
        except Exception as e: messagebox.showerror("Error", f"Failed moving node to root: {e}")

    def _create_parent_child_relation(self, parent_id, child_id):
        import shutil
        old_child_path = Path(child_id); new_child_path = Path(parent_id) / old_child_path.name

        if parent_id == child_id or Path(parent_id).resolve() == Path(child_id).resolve():
            messagebox.showerror("Error", "A map node entity cannot become its own parent destination.")
            return "break"
        if Path(child_id).resolve() in Path(parent_id).resolve().parents:
            messagebox.showerror("Error", "Cycle detected: A map node cannot be nested inside one of its own descendants.")
            return "break"
            
        if new_child_path.exists(): messagebox.showerror("Error", f"A node named '{old_child_path.name}' already exists inside that parent."); return
        try:
            shutil.move(str(old_child_path), str(new_child_path)); toplevel = self.winfo_toplevel()
            if hasattr(toplevel, "sync_reciprocal_relations"):
                toplevel.sync_reciprocal_relations(old_path_prefix=old_child_path, new_path_prefix=new_child_path)
                toplevel.refresh_tree_silent()
                # FIXED: Removed clear_viewer_and_tree() here as well
        except Exception as e: messagebox.showerror("Error", f"Failed nesting parent relation: {e}")

    def _handle_canvas_new_node_creation(self, parent_path, cx, cy):
        title = "Add Location" if self.mode == "location" else "Add Event"
        lbl_text = "Location Name:" if self.mode == "location" else "Event Name:"
        default_icon_path = Path("assets/icons/location_icons/default.png") if self.mode == "location" else Path("assets/icons/events_icons/default.png")
        
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("400x220")
        dialog.configure(bg="#fdf1dc")
        
        # CHANGE: Extract pointer location on the display to place layout next to cursor
        mx, my = self.winfo_pointerxy()
        dialog.geometry(f"400x220+{mx + 10}+{my + 10}")
        
        dialog.transient(self)
        dialog.grab_set()
        
        chosen_icon_path = [default_icon_path]
        
        f_row = tk.Frame(dialog, bg="#fdf1dc")
        f_row.pack(fill=tk.X, padx=15, pady=15)
        tk.Label(f_row, text=lbl_text, font=("Georgia", 11, "bold"), bg="#fdf1dc", fg="black").pack(side=tk.LEFT, padx=(0, 10))
        name_ent = tk.Entry(f_row, font=("Arial", 11), bd=1, relief=tk.SOLID)
        name_ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        i_row = tk.Frame(dialog, bg="#fdf1dc")
        i_row.pack(fill=tk.X, padx=15, pady=5)
        tk.Label(i_row, text="Node Icon:", font=("Georgia", 11, "bold"), bg="#fdf1dc", fg="black").pack(side=tk.LEFT, padx=(0, 10))
        
        img_lbl = tk.Label(i_row, bg="#fae6c5", bd=1, relief=tk.SOLID, cursor="hand2")
        img_lbl.pack(side=tk.LEFT)
        
        def update_preview_icon(p_path):
            try:
                if not Path(p_path).exists():
                    Path(p_path).parent.mkdir(parents=True, exist_ok=True)
                    src_fallback = Path("./assets/icons/map_icon.png") if self.mode == "location" else Path("./assets/icons/event_icon.png")
                    if src_fallback.exists(): shutil.copy(str(src_fallback), str(p_path))
                pil_img = Image.open(p_path)
                pil_img.thumbnail((32, 32))
                tk_img = ImageTk.PhotoImage(pil_img)
                img_lbl.configure(image=tk_img)
                img_lbl.image = tk_img
            except:
                img_lbl.configure(text="Pick Icon", font=("Arial", 9), padx=5, pady=5)
                
        update_preview_icon(chosen_icon_path[0])
        
        def choose_icon_action():
            def on_choice(path):
                chosen_icon_path[0] = Path(path)
                update_preview_icon(path)
            from dialogs import NodeIconSelectorDialog
            NodeIconSelectorDialog(dialog, self.mode, on_choice)
            
        img_lbl.bind("<Button-1>", lambda e: choose_icon_action())
        tk.Button(i_row, text="Change...", font=("Arial", 9), command=choose_icon_action).pack(side=tk.LEFT, padx=10)
        
        def on_confirm():
            fn = name_ent.get().strip()
            if not fn: return
            sn = "".join([c for c in fn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
            nd = parent_path / sn
            if nd.exists():
                messagebox.showerror("Error", "A node path configuration conflict exists.")
                return
            nd.mkdir(parents=True, exist_ok=True)
            
            if chosen_icon_path[0].exists():
                try: shutil.copy(str(chosen_icon_path[0]), str(nd / f"{sn}.png"))
                except Exception as e: print(f"Asset directory copy failed: {e}")
                    
            active_layers = sorted(list(self.visible_layers)) if self.visible_layers else [0]
            stat_json = nd / f"{sn}.json"
            default_data = {"name": fn, "description": "", "monsters": [], "npcs": [], "combats": [], "events" if self.mode == "location" else "locations": [], "objects": [], "connections": [], self.data_key: active_layers}
            with open(stat_json, "w", encoding="utf-8") as f: json.dump(default_data, f, indent=4)
                
            current_width = max(100, self.canvas.winfo_width())
            sf = current_width / self.current_file_ref_width if self.current_file_ref_width > 0 else 1.0
            zl = self.zoom_level if self.zoom_level > 0 else 1.0
            base_x, base_y = int(round(cx / (sf * zl))), int(round(cy / (sf * zl)))
            
            saved_nodes = {}
            if self.layout_path.exists():
                try:
                    with open(self.layout_path, "r", encoding="utf-8") as f: saved_nodes = json.load(f).get("nodes", {})
                except: pass
            saved_nodes[str(nd)] = {"x": base_x, "y": base_y}
            with open(self.layout_path, "w", encoding="utf-8") as f: json.dump({"reference_width": self.current_file_ref_width, "nodes": saved_nodes}, f, indent=4)
                
            toplevel = self.winfo_toplevel()
            if hasattr(toplevel, "refresh_tree_silent"): toplevel.refresh_tree_silent()
            dialog.destroy()
            self.current_mode = "select"
            self.draw_graph()
            
        tk.Button(dialog, text="Confirm & Create", font=("Arial", 10, "bold"), bg="#2ecc71", fg="white", command=on_confirm).pack(side=tk.BOTTOM, pady=15)
        dialog.wait_window()

    def _delete_node(self, node_id):
        info = self.nodes_map.get(node_id)
        if not info: return
        if messagebox.askyesno("Confirm Delete", f"Delete permanently '{info['name']}'?"):
            try:
                import shutil
                node_path = Path(node_id); target_path = node_path.resolve()
                if node_path.is_file(): node_path.unlink()
                else: shutil.rmtree(node_path)
                
                toplevel = self.winfo_toplevel()
                if hasattr(toplevel, "sync_reciprocal_relations"): 
                    toplevel.sync_reciprocal_relations(delete_path_prefix=target_path)
                if hasattr(toplevel, "refresh_tree_silent"): 
                    toplevel.refresh_tree_silent()

                self.draw_graph()
            except Exception as ex: messagebox.showerror("Error", f"Purge routine aborted: {ex}")

    def _write_current_layout_to_disk(self, current_width, dragged_id=None):
        saved_nodes = {}
        if self.layout_path.exists():
            try:
                with open(self.layout_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "reference_width" in data and "nodes" in data: saved_nodes = data["nodes"]
            except: pass
        sf = current_width / self.current_file_ref_width if self.current_file_ref_width > 0 else 1.0
        zl = self.zoom_level if self.zoom_level > 0 else 1.0
        
        # Helper configuration to maintain and store custom individual sizes
        def get_node_entry(nid, cx, cy):
            base_size = self.node_sizes.get(nid, saved_nodes.get(nid, {}).get("size", 32))
            return {"x": int(round(cx / (sf * zl))), "y": int(round(cy / (sf * zl))), "size": base_size}

        if dragged_id and dragged_id in self.node_centers:
            cx, cy = self.node_centers[dragged_id]
            saved_nodes[dragged_id] = get_node_entry(dragged_id, cx, cy)
        else:
            for nid, (cx, cy) in self.node_centers.items(): 
                saved_nodes[nid] = get_node_entry(nid, cx, cy)
        try:
            with open(self.layout_path, "w", encoding="utf-8") as f: json.dump({"reference_width": self.current_file_ref_width, "nodes": saved_nodes}, f, indent=4)
        except Exception as e: print(f"Failed layout write: {e}")

    def _collect_nodes(self, current_path: Path, nodes_map: dict, level=0):
        from models import Node
        if current_path != self.map_root:
            jsons = list(current_path.glob("*.json"))
            stat_path = jsons[0] if jsons else (current_path / f"{current_path.name}.json" if (current_path / f"{current_path.name}.json").exists() else None)
            display_name = current_path.name; connections = []; depths = [0]
            if stat_path and stat_path.exists():
                try:
                    with open(stat_path, "r", encoding="utf-8") as f:
                        m_data = json.load(f); display_name = m_data.get("name", display_name)
                        connections = [(c.get("target"), c.get("description", "")) for c in m_data.get("connections", []) if c.get("target")]
                        depths = m_data.get(self.data_key, [0])
                        if not isinstance(depths, list): depths = [depths]
                except: pass
            nodes_map[str(current_path)] = {"node": Node(name=display_name, path=current_path, is_entity=bool(jsons), level=level, stat_path=stat_path), "name": display_name, "connections": connections, "depths": depths}
        if current_path.is_dir():
            for sub_p in current_path.iterdir():
                if sub_p.is_dir(): self._collect_nodes(sub_p, nodes_map, level + 1)

    def _on_node_hover_enter(self, event): self._handle_node_hover(event)
    def _on_node_hover_motion(self, event): self._handle_node_hover(event)
    def _on_node_hover_leave(self, event):
        if hasattr(self, "_hover_popup") and self._hover_popup:
            try: self._hover_popup.destroy()
            except: pass
            self._hover_popup, self._hover_target = None, None

    def _handle_node_hover(self, event):
        if self._drag_node_id or self._is_panning or self.current_mode != "select":  self._on_node_hover_leave(None); return
        items = self.canvas.find_withtag("current")
        if not items: self._on_node_hover_leave(None); return
        item = items[0]; tags = self.canvas.gettags(item); node_id = None
        for t in tags:
            if t.startswith("path:"): node_id = t.split("path:", 1)[1]; break
        if not node_id:
            for t in tags:
                if t not in ["link", "current", "edge", "node", "drag_handle"] and not t.startswith("group:"): node_id = t; break
        if not node_id: self._on_node_hover_leave(None); return
        scr_w, scr_h = self.winfo_screenwidth(), self.winfo_screenheight()
        popup_w, popup_h = int(scr_w * 2 / 5), int(scr_h * 2 / 5)
        x_pos = event.x_root + 15 if event.x_root < (scr_w / 2) else event.x_root - popup_w - 15
        y_pos = event.y_root + 15 if event.y_root < (scr_h / 2) else event.y_root - popup_h - 15

        if hasattr(self, "_hover_target") and self._hover_target == node_id:
            if hasattr(self, "_hover_popup") and self._hover_popup: self._hover_popup.geometry(f"{popup_w}x{popup_h}+{x_pos}+{y_pos}")
            return
        self._on_node_hover_leave(None); self._hover_target = node_id
        popup = tk.Toplevel(self); popup.is_hover_popup = True; popup.wm_overrideredirect(True)
        popup.configure(bg="#fdf1dc", bd=2, relief=tk.SOLID); popup.geometry(f"{popup_w}x{popup_h}+{x_pos}+{y_pos}")
        self._hover_popup = popup

        toplevel = self.winfo_toplevel()
        if hasattr(toplevel, "resolve_hover_data"):
            data, dtype = toplevel.resolve_hover_data("PATH_TAG", node_id)
            if data:
                from stat_renderer import StatBlockRenderer
                mini_viewer = StatBlockRenderer(popup); mini_viewer.pack(fill=tk.BOTH, expand=True); mini_viewer.clear_overlays()
                mini_viewer.text.adjust_height = lambda: None; mini_viewer.text.configure(height=1)
                if dtype == "location": mini_viewer.render_location(data)
                elif dtype == "event": mini_viewer.render_event(data)
                popup.target_text_widget = mini_viewer.text
            else: tk.Label(popup, text="No detailed tracker sheet for this node.", bg="#fdf1dc", font=("Arial", 11, "italic")).pack(padx=20, pady=20)

    def open_terrain_settings_panel(self):
        def on_settings_applied(new_size, new_color): self.terrain_size = new_size; self.terrain_color = new_color; self.draw_graph()
        TerrainSettingsDialog(self, self.terrain_size, self.terrain_color, on_settings_applied)

    def _fluid_enter_terrain_brush(self):
        if self.current_mode != "terrain":
            focused = self.winfo_toplevel().focus_get()
            if focused and isinstance(focused, (tk.Text, tk.Entry)): return 
            self._cached_pre_shift_mode = self.current_mode
            self.current_mode = "terrain"; self.canvas.config(cursor="crosshair"); self.draw_graph()

    def _fluid_exit_terrain_brush(self):
        if self.current_mode == "terrain":
            self.current_mode = self._cached_pre_shift_mode; self.canvas.config(cursor="")
            active_layer = str(min(self.visible_layers) if self.visible_layers else 0)
            self._compress_terrain_layer(active_layer); self.save_terrain_to_disk(); self.draw_graph()

    def _render_terrain_image(self, sf, zl):
        self.canvas.delete("background_texture")
        active_layer = str(min(self.visible_layers) if self.visible_layers else 0)
        layer_prefix = f"{active_layer}:"; active_cells = {}
        for k, v in self.working_grid.items():
            if k.startswith(layer_prefix): coord_part = k.split(":", 1)[1]; cx, cy = map(int, coord_part.split(",")); active_cells[(cx, cy)] = v
        if not active_cells: self._terrain_image = None; self._img_origin_x = 0; self._img_origin_y = 0; return
        xs = [c[0] for c in active_cells.keys()]; ys = [c[1] for c in active_cells.keys()]
        min_cx, max_cx = min(xs) - 2, max(xs) + 2; min_cy, max_cy = min(ys) - 2, max(ys) + 2
        self._img_origin_x = int(min_cx * 10 * sf * zl); self._img_origin_y = int(min_cy * 10 * sf * zl)
        max_vx, max_vy = int((max_cx + 1) * 10 * sf * zl), int((max_cy + 1) * 10 * sf * zl)
        img_w, img_h = max_vx - self._img_origin_x, max_vy - self._img_origin_y
        if img_w <= 0 or img_h <= 0: return
        self._terrain_image = tk.PhotoImage(width=img_w, height=img_h)
        for (cx, cy), color in active_cells.items():
            x1 = int(cx * 10 * sf * zl) - self._img_origin_x; y1 = int(cy * 10 * sf * zl) - self._img_origin_y
            x2 = int((cx + 1) * 10 * sf * zl) - self._img_origin_x; y2 = int((cy + 1) * 10 * sf * zl) - self._img_origin_y
            if x2 > x1 and y2 > y1: self._terrain_image.put(color, to=(x1, y1, x2, y2))
        self.canvas.create_image(self._img_origin_x, self._img_origin_y, image=self._terrain_image, anchor="nw", tags="background_texture")
        self.canvas.tag_lower("background_texture")

    def _paint_brush_grid_cells(self, x_pos, y_pos):
        current_width = max(100, self.canvas.winfo_width())
        sf = current_width / self.current_file_ref_width if self.current_file_ref_width > 0 else 1.0
        zl = self.zoom_level if self.zoom_level > 0 else 1.0
        cx, cy = self.canvas.canvasx(x_pos), self.canvas.canvasy(y_pos)
        unscaled_cx, unscaled_cy = cx / (sf * zl), cy / (sf * zl)
        block_size = self.terrain_size; bx = int(unscaled_cx // block_size) * block_size; by = int(unscaled_cy // block_size) * block_size
        active_layer = str(min(self.visible_layers) if self.visible_layers else 0); modified = False
        for x in range(bx, bx + block_size, 10):
            for y in range(by, by + block_size, 10):
                grid_key = f"{active_layer}:{x//10},{y//10}"
                if self.terrain_color == "#ffffff":
                    if grid_key in self.working_grid: del self.working_grid[grid_key]; modified = True
                elif self.working_grid.get(grid_key) != self.terrain_color: self.working_grid[grid_key] = self.terrain_color; modified = True
        if modified:
            vx1, vy1 = int(bx * sf * zl), int(by * sf * zl); vx2, vy2 = int((bx + block_size) * sf * zl), int((by + block_size) * sf * zl)
            if (hasattr(self, "_terrain_image") and self._terrain_image and self._img_origin_x <= vx1 and self._img_origin_y <= vy1 and (vx2 - self._img_origin_x) <= self._terrain_image.width() and (vy2 - self._img_origin_y) <= self._terrain_image.height()):
                lx1, ly1 = vx1 - self._img_origin_x, vy1 - self._img_origin_y; lx2, ly2 = vx2 - self._img_origin_x, vy2 - self._img_origin_y
                self._terrain_image.put("#fdf1dc" if self.terrain_color == "#ffffff" else self.terrain_color, to=(lx1, ly1, lx2, ly2))
            else: self._render_terrain_image(sf, zl)
            self.canvas.tag_raise("assistance_line"); self.canvas.tag_raise("node"); self.canvas.tag_raise("link")

    def _load_terrain_data(self):
        self.working_grid = {}; self.compressed_rects = {}
        if self.terrain_path.exists():
            try:
                with open(self.terrain_path, "r", encoding="utf-8") as f: self.compressed_rects = json.load(f)
                for layer, rect_list in self.compressed_rects.items():
                    for r in rect_list:
                        rx, ry, rw, rh, color = r["x"], r["y"], r["w"], r["h"], r["color"]
                        for x in range(rx, rx + rw):
                            for y in range(ry, ry + rh): self.working_grid[f"{layer}:{x},{y}"] = color
            except Exception as e: print(f"Failed parsing terrain data: {e}"); self.working_grid, self.compressed_rects = {}, {}

    def _compress_terrain_layer(self, layer_str):
        layer_prefix = f"{layer_str}:"; cells_by_color = {}
        for key, color in self.working_grid.items():
            if key.startswith(layer_prefix):
                coord_part = key.split(":", 1)[1]; cx, cy = map(int, coord_part.split(",")); cells_by_color.setdefault(color, []).append((cx, cy))
        layer_rectangles = []
        for color, coords in cells_by_color.items():
            by_y = {}
            for cx, cy in coords: by_y.setdefault(cy, []).append(cx)
            spans_by_y = {}
            for cy, x_list in by_y.items():
                x_list.sort(); spans = []
                if not x_list: continue
                start_x, prev_x = x_list[0], x_list[0]
                for cx in x_list[1:]:
                    if cx == prev_x + 1: prev_x = cx
                    else: spans.append((start_x, prev_x)); start_x, prev_x = cx, cx
                spans.append((start_x, prev_x)); spans_by_y[cy] = spans
            consumed_spans = set(); sorted_ys = sorted(spans_by_y.keys())
            for cy in sorted_ys:
                for start_x, end_x in spans_by_y[cy]:
                    if (cy, start_x, end_x) in consumed_spans: continue
                    h, next_y = 1, cy + 1
                    while next_y in spans_by_y and (start_x, end_x) in spans_by_y[next_y]:
                        if (next_y, start_x, end_x) not in consumed_spans: h, next_y = h + 1, next_y + 1
                        else: break
                    for ry in range(cy, cy + h): consumed_spans.add((ry, start_x, end_x))
                    layer_rectangles.append({"x": start_x, "y": cy, "w": end_x - start_x + 1, "h": h, "color": color})
        self.compressed_rects[layer_str] = layer_rectangles

    def save_terrain_to_disk(self):
        active_layers = set(key.split(":", 1)[0] for key in self.working_grid.keys())
        self.compressed_rects = {k: v for k, v in self.compressed_rects.items() if k in active_layers}
        for layer in active_layers: self._compress_terrain_layer(layer)
        try:
            with open(self.terrain_path, "w", encoding="utf-8") as f: json.dump(self.compressed_rects, f, indent=4)
        except Exception as e: print(f"Failed landscape structural data serialization: {e}")

    def _get_node_icon_image(self, node_id, base_size=32):
        """Fetches hardware-optimized visual pointers from memory cache, 
        with automatic fallback to default profile assets.
        """
        # QUALITY ENHANCEMENT: Incorporate individual unscaled base_size into cache keys
        cache_key = (node_id, self.zoom_level, base_size)
        if hasattr(self, "_icon_image_cache") and cache_key in self._icon_image_cache:
            return self._icon_image_cache[cache_key]
            
        if not hasattr(self, "_icon_image_cache"):
            self._icon_image_cache = {}
            
        img_path = None
        node_path = Path(node_id)
        if node_path.exists() and node_path.is_dir():
            pngs = list(node_path.glob("*.png"))
            if pngs:
                img_path = pngs[0]
                
        if not img_path:
            if self.mode == "location":
                img_path = Path("./assets/icons/map_icon.png")
            else:
                img_path = Path("./assets/icons/event_icon.png")
                
        if not img_path.exists():
            return None
            
        try:
            pil_img = Image.open(img_path)
            # Resize directly from full resolution disk file to avoid texture scaling artifacts
            size = max(10, int(base_size * self.zoom_level))
            pil_img = pil_img.resize((size, size), Image.Resampling.LANCZOS)
            
            tk_img = ImageTk.PhotoImage(pil_img)
            self._icon_image_cache[cache_key] = tk_img
            return tk_img
        except Exception as e:
            print(f"Error compiling visual image resource cache: {e}")
            return None

    def open_node_icon_selector(self):
        """Launches the custom icon dashboard panel and copies choices to disk."""
        if not self.selected_node_id:
            messagebox.showinfo("Selection Required", "Please select a node on the canvas layout first.")
            return
            
        def on_icon_chosen(chosen_path):
            node_dir = Path(self.selected_node_id)
            if node_dir.exists() and node_dir.is_dir():
                # Purge historical items to prevent overlap drift anomalies
                for old_png in node_dir.glob("*.png"):
                    try: old_png.unlink()
                    except: pass
                
                dest_path = node_dir / f"{node_dir.name}.png"
                try:
                    shutil.copy(str(chosen_path), str(dest_path))
                    if hasattr(self, "_icon_image_cache"):
                        self._icon_image_cache.clear() # Force redrawing fresh graphics
                    self.draw_graph()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed updating node custom asset icon: {e}")
                    
        NodeIconSelectorDialog(self, self.mode, on_icon_chosen)


