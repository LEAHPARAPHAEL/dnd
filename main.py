import argparse
import sys
import json
import requests
import shutil 
import urllib.parse
import copy
import re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from pathlib import Path
from PIL import Image, ImageTk
from dataclasses import dataclass, field

from stat_renderer import StatBlockRenderer

@dataclass
class Node:
    name: str
    path: Path
    is_entity: bool 
    level: int
    is_open: bool = False
    icon_path: Path = None
    stat_path: Path = None
    action_type: str = ""  
    children: list = field(default_factory=list)

class DnDStatManager(tk.Tk):
    def __init__(self, root_dir):
        super().__init__()
        self.title("D&D Campaign Manager - Stat Blocks")
        self.geometry("1400x800")
        self.configure(bg="#1e1e1e")
        
        self.root_dir = Path(root_dir).resolve()
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

        self._setup_ui()
        self.refresh_tree()

    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", rowheight=35, fieldbackground="#1e1e1e", font=("Georgia", 12), borderwidth=0)
        style.configure("Treeview.Heading", font=("Georgia", 13, "bold"), background="#1e1e1e", foreground="#d9ad6c")
        style.map("Treeview", background=[("selected", "#4a90e2")])

        self.paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        self.tree_frame = tk.Frame(self.paned_window, bg="#2b2b2b")
        self.paned_window.add(self.tree_frame, weight=1)

        self.tree_canvas = tk.Canvas(self.tree_frame, bg="#2b2b2b", highlightthickness=0)
        self.tree_scroll = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree_canvas.yview)
        self.tree_canvas.configure(yscrollcommand=self.tree_scroll.set)

        self.tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree_inner = tk.Frame(self.tree_canvas, bg="#2b2b2b")
        self.tree_window = self.tree_canvas.create_window((0, 0), window=self.tree_inner, anchor="nw")

        self.tree_inner.bind("<Configure>", lambda e: self.tree_canvas.configure(scrollregion=self.tree_canvas.bbox("all")))
        self.tree_canvas.bind("<Configure>", lambda e: self.tree_canvas.itemconfig(self.tree_window, width=e.width))

        self.right_frame = tk.Frame(self.paned_window, bg="#1e1e1e")
        self.paned_window.add(self.right_frame, weight=3)
        
        self.stat_viewer = StatBlockRenderer(self.right_frame)
        self.stat_viewer.set_spell_callback(self.on_spell_clicked)
        self.stat_viewer.set_spells_index(self.spells_index)
        
        self.search_frame = tk.Frame(self.right_frame, bg="#1e1e1e")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.filter_monster_list)
        self.search_entry = tk.Entry(self.search_frame, textvariable=self.search_var, font=("Georgia", 14), bg="#333", fg="white", insertbackground="white")
        self.search_entry.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        self.listbox_frame = tk.Frame(self.search_frame, bg="#1e1e1e")
        self.listbox_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        columns = ("name", "type", "cr", "source")
        self.monster_tree = ttk.Treeview(self.listbox_frame, columns=columns, show="headings", selectmode="browse")
        self.monster_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.monster_tree.heading("name", text="Name", anchor="w")
        self.monster_tree.heading("type", text="Type", anchor="w")
        self.monster_tree.heading("cr", text="CR", anchor="center")
        self.monster_tree.heading("source", text="Source", anchor="center")
        self.monster_tree.column("name", width=300, anchor="w")
        self.monster_tree.column("type", width=150, anchor="w")
        self.monster_tree.column("cr", width=60, anchor="center")
        self.monster_tree.column("source", width=80, anchor="center")

        self.monster_tree.tag_configure("evenrow", background="#2b2b2b")
        self.monster_tree.tag_configure("oddrow", background="#363636")
        
        list_scroll = ttk.Scrollbar(self.listbox_frame, orient="vertical", command=self.monster_tree.yview)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.monster_tree.configure(yscrollcommand=list_scroll.set)
        self.monster_tree.bind("<Double-1>", self.on_monster_selected)
        
        self.stat_viewer.pack(fill=tk.BOTH, expand=True)
        self.current_target_folder = None

    def on_spell_clicked(self, spell_name):
        spell_data = next((s for s in self.spells_index if s["name"].lower() == spell_name.lower()), None)
        if not spell_data:
            messagebox.showinfo("Spell Not Found", f"Could not find data for '{spell_name}'. Make sure you have run fetch_spells.py!")
            return
        self.stat_viewer.render_spell(spell_data, back_callback=self.re_render_current_monster)
            
    def re_render_current_monster(self):
        if self.current_open_node: self.display_monster(self.current_open_node, edit_mode=False)

    def refresh_tree(self):
        open_paths = self._get_open_paths(getattr(self, 'nodes', []))
        self.nodes = self.build_tree_model(self.root_dir, level=0, open_paths=open_paths)
        self.render_tree()

    def _get_open_paths(self, nodes):
        paths = set()
        for node in nodes:
            if node.is_open: paths.add(str(node.path))
            paths.update(self._get_open_paths(node.children))
        return paths

    def _set_node_open(self, target_path: Path, open_state: bool, nodes=None):
        if nodes is None: nodes = getattr(self, 'nodes', [])
        for n in nodes:
            if n.path == target_path:
                n.is_open = open_state
                return True
            if self._set_node_open(target_path, open_state, n.children):
                n.is_open = True
                return True
        return False

    def build_tree_model(self, path: Path, level: int, open_paths: set):
        nodes = []
        try: items = sorted([p for p in path.iterdir() if p.is_dir()], key=lambda x: x.name.lower())
        except PermissionError: return nodes

        is_current_path_core = path.name in ["Monsters", "NPCs", "Combats"]

        for item in items:
            jsons = list(item.glob("*.json"))
            webps = list(item.glob("*.webp"))

            if jsons:
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
                
        if not is_current_path_core:
            btn_name = "New Location" if level == 0 else "New Sublocation"
            new_loc_btn = Node(name=btn_name, path=path, is_entity=False, level=level, action_type="new_location", icon_path=Path("./utils/new.png"))
            nodes.append(new_loc_btn)
        else:
            action_map = {"Monsters": "new_monster", "NPCs": "new_npc", "Combats": "new_combat"}
            if path.name in action_map:
                new_btn = Node(name="New", path=path, is_entity=False, level=level, action_type=action_map[path.name], icon_path=Path("./utils/new.png"))
                nodes.append(new_btn)
            
        return nodes

    def render_tree(self):
        for widget in self.tree_inner.winfo_children(): widget.destroy()
        self.image_cache.clear()

        def draw_node(node):
            row = tk.Frame(self.tree_inner, bg="#2b2b2b")
            row.pack(fill=tk.X, pady=2)
            indent = node.level * 35 + 10
            is_action_btn = bool(node.action_type)
            text_font = ("Georgia", 13)
            text_color = "#ffffff" if node.is_entity else "#aaaaaa"
            if not node.is_entity and not is_action_btn:
                text_font = ("Georgia", 15, "bold")
                text_color = "#ffffff"
            if is_action_btn:
                text_font = ("Georgia", 13, "italic")
                text_color = "#4a90e2"

            if node.icon_path and node.icon_path.exists():
                try:
                    img = Image.open(node.icon_path).resize((44, 44), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.image_cache.append(photo)
                    icon_lbl = tk.Label(row, image=photo, bg="#2b2b2b", cursor="hand2")
                except:
                    icon_lbl = tk.Label(row, text="?", width=4, height=2, bg="#444", fg="white", cursor="hand2")
            else:
                icon_text = "+" if is_action_btn else ("E" if node.is_entity else "📁")
                icon_lbl = tk.Label(row, text=icon_text, width=4, height=2, bg="#444", fg="white", cursor="hand2")
            
            icon_lbl.pack(side=tk.LEFT, padx=(indent, 15), pady=6)
            text_lbl = tk.Label(row, text=node.name, bg="#2b2b2b", fg=text_color, font=text_font, cursor="hand2")
            text_lbl.pack(side=tk.LEFT, pady=6)

            del_btn = None
            if not is_action_btn:
                is_core_folder = (node.name in ["Monsters", "NPCs", "Combats"])
                if not is_core_folder:
                    del_btn = tk.Label(row, text="X", bg="#2b2b2b", fg="#ff4d4d", font=("Arial", 16, "bold"), cursor="hand2")
                    del_btn.pack(side=tk.RIGHT, padx=15)
                    del_btn.bind("<Enter>", lambda e: e.widget.configure(bg="#4a2222", fg="#ffffff"))
                    del_btn.bind("<Leave>", lambda e: e.widget.configure(bg="#2b2b2b" if row.cget("bg") == "#2b2b2b" else "#3e3e42", fg="#ff4d4d"))

                    def on_del_click(e, n=node):
                        target_type = "entry" if n.is_entity else "folder"
                        msg = f"Are you sure you want to delete this {target_type} '{n.name}'?\nThis will erase the directory and all its contents from your computer."
                        if messagebox.askyesno("Confirm Delete", msg):
                            try:
                                shutil.rmtree(n.path)
                                self.refresh_tree()
                                self.stat_viewer.pack_forget() 
                            except Exception as ex: messagebox.showerror("Error", f"Failed to delete:\n{ex}")
                    del_btn.bind("<Button-1>", on_del_click)

            def on_enter(e): 
                row.configure(bg="#3e3e42")
                icon_lbl.configure(bg="#3e3e42")
                text_lbl.configure(bg="#3e3e42")
                if del_btn and del_btn.cget("bg") != "#4a2222": del_btn.configure(bg="#3e3e42")
            
            def on_leave(e): 
                row.configure(bg="#2b2b2b")
                icon_lbl.configure(bg="#2b2b2b")
                text_lbl.configure(bg="#2b2b2b")
                if del_btn and del_btn.cget("bg") != "#4a2222": del_btn.configure(bg="#2b2b2b")
                
            row.bind("<Enter>", on_enter)
            row.bind("<Leave>", on_leave)
            
            def on_click(e):
                if node.action_type == "new_location": self.create_new_location(node.path)
                elif node.action_type == "new_monster": self.show_search_panel(node.path)
                elif node.action_type == "new_npc": self.create_new_npc(node.path)
                elif node.action_type == "new_combat": pass  
                elif node.is_entity: self.display_monster(node)
                else:
                    node.is_open = not node.is_open
                    self.render_tree()

            def on_icon_click(e):
                is_core_folder = (node.name in ["Monsters", "NPCs", "Combats"])
                if not is_action_btn and not is_core_folder: 
                    self.change_folder_icon(node)
                else: 
                    on_click(e)

            icon_lbl.bind("<Button-1>", on_icon_click)
            text_lbl.bind("<Button-1>", on_click)
            row.bind("<Button-1>", on_click)

            if not node.is_entity and node.is_open:
                for child in node.children: draw_node(child)

        for node in self.nodes: draw_node(node)

    def create_new_location(self, parent_path: Path):
        folder_name = simpledialog.askstring("Add Location", "Enter the name of the new location:")
        if not folder_name or not folder_name.strip(): return
            
        safe_name = "".join([c for c in folder_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        if not safe_name: return

        new_dir = parent_path / safe_name
        new_dir.mkdir(parents=True, exist_ok=True)
        
        (new_dir / "Monsters").mkdir(exist_ok=True)
        (new_dir / "NPCs").mkdir(exist_ok=True)
        (new_dir / "Combats").mkdir(exist_ok=True)
        
        default_icon = Path("./utils/default.png")
        if default_icon.exists():
            try:
                img = Image.open(default_icon)
                img.thumbnail((64, 64))
                img.save(new_dir / f"{safe_name}.png", "PNG")
            except Exception as e: print(f"Failed to copy default icon: {e}")
                
        self._set_node_open(parent_path, True)
        self.refresh_tree()

    def create_new_npc(self, parent_path: Path):
        base_name = "New NPC"
        safe_name = base_name
        counter = 1
        while (parent_path / safe_name).exists():
            safe_name = f"{base_name} {counter}"
            counter += 1

        npc_dir = parent_path / safe_name
        npc_dir.mkdir(parents=True, exist_ok=True)

        npc_data = {
            "name": safe_name, "source": "Custom", "level": 1, "size": ["M"], "type": "humanoid",
            "alignment": ["N"], "ac": [10], "hp": {"average": 4, "formula": "1d8"},
            "speed": {"walk": 30}, "str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10,
            "action": [
                {
                    "name": "Unarmed Strike", 
                    "entries": ["{@atk mw} {@hit 2} to hit, reach 5 ft., one target. {@h}1 bludgeoning damage."]
                }
            ]
        }

        with open(npc_dir / f"{safe_name}.json", "w", encoding="utf-8") as f:
            json.dump(npc_data, f, indent=4)

        # Copy the default NPC icon
        default_npc_icon = Path("./utils/default_npc.png")
        if default_npc_icon.exists():
            try:
                img = Image.open(default_npc_icon)
                img.save(npc_dir / "portrait.png", "PNG")
                img.thumbnail((64, 64))
                img.save(npc_dir / "icon.webp", "WEBP")
            except Exception as e: print(f"Failed to copy default NPC icon: {e}")

        self._set_node_open(parent_path, True)
        self.refresh_tree()
        self.display_monster_by_path(npc_dir, edit_mode=True)

    def save_monster_edits(self, old_dir: Path, new_data: dict):
        old_safe_name = old_dir.name
        new_name = new_data.get("name", "Unknown")
        new_safe_name = "".join([c for c in new_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
        if not new_safe_name: new_safe_name = "Unnamed"

        if new_safe_name != old_safe_name:
            new_dir = old_dir.parent / new_safe_name
            if new_dir.exists() and new_dir != old_dir:
                messagebox.showerror("Error", f"A folder named {new_safe_name} already exists. Pick a different name.")
                return

            old_json = old_dir / f"{old_safe_name}.json"
            new_json = old_dir / f"{new_safe_name}.json" 
            if old_json.exists(): old_json.rename(new_json)

            old_dir.rename(new_dir)
            final_dir = new_dir
            final_json = new_dir / f"{new_safe_name}.json"
        else:
            final_dir = old_dir
            final_json = old_dir / f"{old_safe_name}.json"

        with open(final_json, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4)

        self.refresh_tree()
        self.display_monster_by_path(final_dir, edit_mode=False)

    def display_monster_by_path(self, target_path: Path, edit_mode=False):
        def search_nodes(nodes):
            for n in nodes:
                if n.path == target_path and n.is_entity: return n
                res = search_nodes(n.children)
                if res: return res
            return None
        
        target_node = search_nodes(self.nodes)
        if target_node: self.display_monster(target_node, edit_mode)

    def display_monster(self, node: Node, edit_mode=False):
        self.current_open_node = node
        self.search_frame.pack_forget()
        self.stat_viewer.pack(fill=tk.BOTH, expand=True)
        try:
            with open(node.stat_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if edit_mode:
                self.stat_viewer.render_edit_mode(data, node.path, self.save_monster_edits, lambda: self.display_monster(node, edit_mode=False))
            else:
                self.stat_viewer.render_monster(data)
                self.stat_viewer.add_top_buttons(node.path, self.view_full_portrait, lambda d: self.display_monster(node, edit_mode=True))
                
        except Exception as e:
            print(f"Failed to load: {e}")

    def change_folder_icon(self, node: Node):
        file_path = filedialog.askopenfilename(title=f"Select new portrait for {node.name}", filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")])
        if not file_path: return
            
        try:
            img = Image.open(file_path)
            if node.is_entity:
                for old_ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    old_p = node.path / f"portrait{old_ext}"
                    old_i = node.path / f"icon{old_ext}"
                    if old_p.exists(): old_p.unlink()
                    if old_i.exists(): old_i.unlink()
                img.save(node.path / "portrait.png", "PNG")
                img.thumbnail((64, 64))
                img.save(node.path / "icon.webp", "WEBP")
            else:
                img.thumbnail((64, 64))
                for old_ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    old_file = node.path / f"{node.name}{old_ext}"
                    if old_file.exists(): old_file.unlink()
                img.save(node.path / f"{node.name}.png", "PNG")
            self.refresh_tree()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to process image: {e}")

    def show_search_panel(self, target_path: Path):
        self.current_target_folder = target_path
        self.stat_viewer.pack_forget()
        self.search_frame.pack(fill=tk.BOTH, expand=True)
        self.search_entry.delete(0, tk.END)
        self.filter_monster_list()
        self.search_entry.focus()

    def filter_monster_list(self, *args):
        for item in self.monster_tree.get_children(): self.monster_tree.delete(item)
            
        search_term = self.search_var.get().lower()
        count = 0
        for m in self.monster_index:
            if search_term in m["name"].lower():
                tag = "evenrow" if count % 2 == 0 else "oddrow"
                self.monster_tree.insert("", tk.END, values=(m["name"], m.get("type", "Unknown"), m.get("cr", "—"), m.get("source", "Unknown")), tags=(tag,))
                count += 1

    def on_monster_selected(self, event):
        selected_item = self.monster_tree.selection()
        if not selected_item: return
        item = self.monster_tree.item(selected_item[0])
        monster_meta = next((m for m in self.monster_index if m["name"] == item['values'][0] and m.get("source", "Unknown") == item['values'][3]), None)
        if not monster_meta: return
        self.download_monster_data(monster_meta)

    def resolve_copy(self, child_data, headers):
        if "_copy" not in child_data: return child_data
        copy_info = child_data["_copy"]
        base_name = copy_info.get("name")
        base_source = copy_info.get("source", "Unknown").lower()

        url = f"https://5e.tools/data/bestiary/bestiary-{base_source}.json"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            book_data = response.json()
            
            base_monster = next((m for m in book_data.get("monster", []) if m.get("name") == base_name), None)
            if not base_monster: return child_data
                
            resolved = copy.deepcopy(base_monster)
            mods = copy_info.get("_mod", {})
            
            if "*" in mods:
                star_mods = mods["*"] if isinstance(mods["*"], list) else [mods["*"]]
                for global_mod in star_mods:
                    if isinstance(global_mod, dict) and global_mod.get("mode") == "replaceTxt":
                        rep = global_mod.get("replace", "")
                        with_txt = global_mod.get("with", "")
                        
                        def replace_in_strings(obj):
                            if isinstance(obj, dict): return {k: replace_in_strings(v) for k, v in obj.items()}
                            elif isinstance(obj, list): return [replace_in_strings(v) for v in obj]
                            elif isinstance(obj, str): return re.sub(re.escape(rep), with_txt, obj, flags=re.IGNORECASE)
                            else: return obj
                                
                        resolved = replace_in_strings(resolved)

            for mod_key, mod_val in mods.items():
                if mod_key == "*": continue
                mod_actions = mod_val if isinstance(mod_val, list) else [mod_val]
                for m_action in mod_actions:
                    if isinstance(m_action, str):
                        if m_action == "remove": resolved.pop(mod_key, None)
                        continue
                        
                    mode = m_action.get("mode")
                    if mode == "removeArr":
                        names = m_action.get("names", [])
                        if isinstance(names, str): names = [names]
                        if mod_key in resolved and isinstance(resolved[mod_key], list):
                            resolved[mod_key] = [item for item in resolved[mod_key] if not (isinstance(item, dict) and item.get("name") in names)]
                    elif mode == "appendArr":
                        items = m_action.get("items", [])
                        if isinstance(items, dict): items = [items]
                        if mod_key not in resolved: resolved[mod_key] = []
                        resolved[mod_key].extend(items)

            for k, v in child_data.items():
                if k != "_copy": resolved[k] = v

            return self.resolve_copy(resolved, headers)
        except Exception as e: return child_data

    def download_monster_data(self, monster_meta):
        name = monster_meta["name"]
        source = monster_meta.get("source", "").lower()
        if not source: return

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://5e.tools/'
        }
        url = f"https://5e.tools/data/bestiary/bestiary-{source}.json"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            book_data = response.json()
            monster_data = next((m for m in book_data.get("monster", []) if m.get("name") == name), None)
            if not monster_data: return

            monster_data = self.resolve_copy(monster_data, headers)

            safe_name = "".join([c for c in name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
            monster_dir = self.current_target_folder / safe_name
            monster_dir.mkdir(parents=True, exist_ok=True)

            with open(monster_dir / f"{safe_name}.json", "w", encoding="utf-8") as f:
                json.dump(monster_data, f, indent=4)

            safe_name_url = urllib.parse.quote(name)
            safe_source_url = urllib.parse.quote(monster_meta.get("source", "Unknown"))
            
            token_url = f"https://5e.tools/img/bestiary/tokens/{safe_source_url}/{safe_name_url}.webp"
            portrait_base = f"https://5e.tools/img/bestiary/{safe_source_url}/{safe_name_url}"

            try:
                t_res = requests.get(token_url, headers=headers, timeout=10)
                if t_res.status_code == 200:
                    from io import BytesIO
                    img = Image.open(BytesIO(t_res.content))
                    img.thumbnail((64, 64))
                    img.save(monster_dir / "icon.webp", "WEBP")
            except Exception as e: pass

            for ext in [".webp", ".png"]:
                try:
                    p_res = requests.get(f"{portrait_base}{ext}", headers=headers, timeout=10)
                    if p_res.status_code == 200:
                        with open(monster_dir / "portrait.png", "wb") as f:
                            f.write(p_res.content)
                        break 
                except: continue
            
            self._set_node_open(self.current_target_folder, True)
            self.refresh_tree()
            self.display_monster_by_path(monster_dir, edit_mode=False)

        except Exception as e:
            messagebox.showerror("Download Error", f"Failed: {e}")

    def view_full_portrait(self, monster_dir):
        portrait_path = monster_dir / "portrait.png"
        if not portrait_path.exists():
            messagebox.showinfo("Info", "No artwork found for this monster.")
            return

        overlay = tk.Frame(self.right_frame, bg="black")
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        img = Image.open(portrait_path)
        img.thumbnail((800, 800)) 
        tk_img = ImageTk.PhotoImage(img)
        
        lbl = tk.Label(overlay, image=tk_img, bg="black")
        lbl.image = tk_img
        lbl.pack(expand=True)

        close_btn = tk.Button(overlay, text="CLOSE", command=overlay.destroy, bg="#58180d", fg="white", font=("Georgia", 14))
        close_btn.place(x=20, y=20)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--path", default="./bestiary", help="Path to campaign root.")
    args = parser.parse_args()

    root_path = Path(args.path)
    root_path.mkdir(parents=True, exist_ok=True)
    Path("./utils").mkdir(exist_ok=True)

    app = DnDStatManager(root_path)
    app.mainloop()

if __name__ == "__main__":
    main()