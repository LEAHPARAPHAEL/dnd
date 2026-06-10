import argparse
import sys
import json
import shutil 
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from pathlib import Path
from PIL import Image, ImageTk

import utils.preprocess as preprocess
import downloader
from models import Node
from stat_renderer import StatBlockRenderer, CombatRenderer, AutoHeightText, MapGraphRenderer
from dialogs import SpellSearchDialog, MonsterSearchDialog, EntitySelectionDialog
import copy
from music_service import YouTubeMusicService
from music_panel import MusicManagerPanel


class SyncRef(str):
    """A string subclass that enables absolute-path graph synchronization.
    It passes string-type checks natively across Tkinter widgets, while 
    preserving absolute file system paths as attributes for background sweeps.
    """
    def __new__(cls, name, path):
        obj = super().__new__(cls, name)
        obj.path = str(Path(path).resolve())
        return obj

    def __reduce__(self):
        # Custom reducer to ensure deepcopy passes both name and path parameters
        return (SyncRef, (str(self), self.path))
    
class PageState:
    def __init__(self, node: Node, view_type: str, stat_path: Path = None, data: dict = None, prev=None):
        self.node = node
        self.view_type = view_type  
        self.stat_path = stat_path
        self.data = data
        self.prev = prev  

class DnDStatManager(tk.Tk):
    def __init__(self, root_dir):
        super().__init__()
        self.title("D&D Campaign Manager - Stat Blocks")
        self.geometry("1500x850")
        self.configure(bg="#fdf1dc")

        self.music_service = YouTubeMusicService()
        self.music_visible = False
        self.focused_page_state = None
        
        self.root_dir = Path(root_dir).resolve()
        
        # Initialize Core Master System Folders
        for d in ["map", "spells", "Monsters", "NPCs", "Combats", "Events", "Objects"]:
            setattr(self, f"{d.lower() if d != 'Monsters' and d != 'NPCs' else d.lower()}_dir", self.root_dir / d)
            getattr(self, f"{d.lower() if d != 'Monsters' and d != 'NPCs' else d.lower()}_dir").mkdir(parents=True, exist_ok=True)
                
        self.image_cache = []
        self.current_state = None  
        
        self.monster_index = json.load(open("monsters.json", "r", encoding="utf-8")) if Path("monsters.json").exists() else []
        self.spells_index = json.load(open("spells.json", "r", encoding="utf-8")) if Path("spells.json").exists() else []

        self.query_blocks = []
        self.monster_query_blocks = []

        self._setup_ui()
        self.refresh_tree()
        
        self.open_page(Node(name="Campaign Map", path=self.map_dir, is_entity=False, level=0), view_type="root_folder")
        
        self.bind_all("<MouseWheel>", self._global_mouse_wheel)
        self.bind_all("<Button-4>", self._global_mouse_wheel)
        self.bind_all("<Button-5>", self._global_mouse_wheel)
        self.bind_all("<Key>", self._on_global_key_shortcut)

    def _global_mouse_wheel(self, event):
        try:
            # Check if any viewer pane currently holds an active, open preview window instance
            active_popup = None
            if hasattr(self, 'stat_viewer') and getattr(self.stat_viewer, '_hover_popup', None):
                active_popup = self.stat_viewer._hover_popup
            elif hasattr(self, 'combat_viewer') and getattr(self.combat_viewer, '_hover_popup', None):
                active_popup = self.combat_viewer._hover_popup
            elif hasattr(self, 'map_graph_viewer') and getattr(self.map_graph_viewer, '_hover_popup', None):
                active_popup = self.map_graph_viewer._hover_popup
            elif hasattr(self, 'events_graph_viewer') and getattr(self.events_graph_viewer, '_hover_popup', None):
                active_popup = self.events_graph_viewer._hover_popup

            # If a hover popup exists, completely hijack the scroll signal and route it to its text panel
            if active_popup and active_popup.winfo_exists():
                units = -2 if event.num == 4 else 2 if event.num == 5 else -1 * (event.delta // 40)
                if hasattr(active_popup, 'target_text_widget') and active_popup.target_text_widget.winfo_exists():
                    active_popup.target_text_widget.yview_scroll(units, "units")
                return "break"
        except: pass

        # Guard rail checking loop for main text entries (Preserves original background layout protections)
        #if isinstance(event.widget, AutoHeightText): return
        
        try:
            hovered_widget = event.widget
            if not hovered_widget: return
            units = -2 if event.num == 4 else 2 if event.num == 5 else -1 * (event.delta // 40)

            cur = hovered_widget
            while cur:
                if cur == self.tree_frame:
                    v_top, v_bottom = self.tree_canvas.yview()
                    if v_top > 0.0 or v_bottom < 1.0: self.tree_canvas.yview_scroll(units, "units")
                    return
                if hasattr(cur, 'tree') and isinstance(cur, tk.Toplevel):
                    v_top, v_bottom = cur.tree.yview()
                    if v_top > 0.0 or v_bottom < 1.0: cur.tree.yview_scroll(units, "units")
                    return
                if isinstance(cur, tk.Toplevel) and hasattr(cur, 'canvas'):
                    try:
                        cur.canvas.yview_scroll(units, "units")
                        return "break"
                    except: pass
                if cur == self.right_frame:
                    if self.stat_viewer.winfo_ismapped():
                        if self.stat_viewer.edit_container.winfo_ismapped():
                            v_top, v_bottom = self.stat_viewer.edit_canvas.yview()
                            if v_top > 0.0 or v_bottom < 1.0: self.stat_viewer.edit_canvas.yview_scroll(units, "units")
                        else:
                            v_top, v_bottom = self.stat_viewer.text.yview()
                            if v_top > 0.0 or v_bottom < 1.0: self.stat_viewer.text.yview(tk.SCROLL, units, tk.UNITS)
                    elif self.combat_viewer.winfo_ismapped():
                        v_top, v_bottom = self.combat_viewer.main_canvas.yview()
                        if v_top > 0.0 or v_bottom < 1.0: self.combat_viewer.main_canvas.yview_scroll(units, "units")
                    elif self.search_frame.winfo_ismapped():
                        v_top, v_bottom = self.monster_tree.yview()
                        if v_top > 0.0 or v_bottom < 1.0: self.monster_tree.yview_scroll(units, "units")
                    elif self.spell_manager_frame.winfo_ismapped():
                        v_top, v_bottom = self.spell_tree.yview()
                        if v_top > 0.0 or v_bottom < 1.0: self.spell_tree.yview_scroll(units, "units")
                    elif hasattr(self, 'map_graph_viewer') and self.map_graph_viewer.winfo_ismapped():
                        self.map_graph_viewer.adjust_zoom(units)
                    elif hasattr(self, 'events_graph_viewer') and self.events_graph_viewer.winfo_ismapped():
                        self.events_graph_viewer.adjust_zoom(units)
                    return
                parent_id = cur.winfo_parent()
                if not parent_id: break
                cur = cur.nametowidget(parent_id)
        except: pass

    def _on_global_key_shortcut(self, event):
        """Processes global hotkey shortcuts across the entire app window layout."""
        try:
            if "shift" in event.keysym.lower() or event.state & 0x0001: 
                return
            # 1. Focus guard rail: Escape early if typing inside an active input text/entry frame
            focused = self.focus_get()
            if focused and isinstance(focused, (tk.Text, tk.Entry)):
                return

            key = event.keysym.lower()
            
            # Intercept and process local canvas tool commands first
            if hasattr(self, 'map_graph_viewer') and self.map_graph_viewer.winfo_ismapped():
                if self.map_graph_viewer.handle_shortcut(key):
                    return "break"
            if hasattr(self, 'events_graph_viewer') and self.events_graph_viewer.winfo_ismapped():
                if self.events_graph_viewer.handle_shortcut(key):
                    return "break"


            # 2. Page Navigation Routing Rules
            if key == 'm':
                self.open_page(Node(name="Campaign Map", path=self.map_dir, is_entity=False, level=0), view_type="root_folder")
                return "break"
            elif key == 'e':
                self.open_page(Node(name="Events", path=self.events_dir, is_entity=False, level=0), view_type="root_folder")
                return "break"
            elif key == 'b':
                self.open_page(Node(name="Monsters", path=self.monsters_dir, is_entity=False, level=0), view_type="root_folder")
                return "break"
            elif key == 'n':
                self.open_page(Node(name="NPCs", path=self.npcs_dir, is_entity=False, level=0), view_type="root_folder")
                return "break"
            elif key == 'c':
                self.open_page(Node(name="Combats", path=self.combats_dir, is_entity=False, level=0), view_type="root_folder")
                return "break"
                
            # 3. Structural Back Action Override Trigger
            elif key == 'escape':
                self.navigate_back()
                return "break"
                
            # 4. Sheet Page Deletion Action
            elif key == 'delete':
                self._delete_active_page_sheet()
                return "break"
            elif key == 'w':
                self.toggle_music_panel_visibility()
                return "break"
            elif key == 'f':
                # Toggle Focus Mode on the active viewing sheet node context
                if self.current_state and self.current_state.node:
                    if hasattr(self, 'focused_page_state') and self.focused_page_state and self.focused_page_state.node.path == self.current_state.node.path:
                        self.focused_page_state = None
                    else:
                        self.focused_page_state = self.current_state
                    
                    if self.focused_page_state and self.focused_page_state.node:
                        # Derive the target category matching your link routing framework rules
                        v_type = self.focused_page_state.view_type
                        cat = "Locations" if v_type == "location" else "Events" if v_type == "event" else v_type.title() + "s"
                        self.music_manager_ui.update_focus_link(self.focused_page_state.node.name, cat)
                    else:
                        self.music_manager_ui.update_focus_link(None, None)
                return "break"

            elif key == 'space':
                self.music_manager_ui._toggle_play_pause()
                return "break"

            elif key == 'right':
                self.music_manager_ui._skip_track()
                return "break"

            elif key == 'g':
                if hasattr(self, 'focused_page_state') and self.focused_page_state and self.focused_page_state.data:
                    self.music_manager_ui.add_all_tracks_from_external_data(self.focused_page_state.data)
                return "break"

            elif key == 'h':
                self.music_manager_ui._clear_queue_keep_current()
                return "break"
        except: pass

    def _delete_active_page_sheet(self):
        """Permanently unlinks and purges the active page file from memory and disk."""
        if not self.current_state or not self.current_state.node:
            return
            
        state = self.current_state
        node = state.node
        
        # Safeguard protection to block accidental deletion of core primary indexing root folders
        protected_roots = ["Map", "Events", "Objects", "Spells", "Monsters", "NPCs", "Combats", "Campaign Map"]
        
        # FIXED: Changed node.view_type to state.view_type
        if node.name in protected_roots or state.view_type == "root_folder":
            return

        if messagebox.askyesno("Confirm Delete", f"Delete permanently '{node.name}'?"):
            try:
                import shutil
                target_path = node.path.resolve()
                if node.path.is_file():
                    if node.path.parent == self.spells_dir:
                        try:
                            # FIXED: Changed node.stat_path to state.stat_path for stable lookup
                            self.spells_index = [s for s in self.spells_index if s["name"].lower() != json.load(open(state.stat_path, "r", encoding="utf-8")).get("name", "").lower()]
                            json.dump(self.spells_index, open("spells.json", "w", encoding="utf-8"), indent=4)
                            self.stat_viewer.set_spells_index(self.spells_index)
                        except: pass
                    node.path.unlink()
                else:
                    shutil.rmtree(node.path)
                    
                self.sync_reciprocal_relations(delete_path_prefix=target_path)
                self.refresh_tree_silent()
                self.clear_viewer_and_tree()
            except Exception as ex:
                messagebox.showerror("Error", f"Failed to delete sheet file: {ex}")

    def _get_open_paths(self, nodes):
        return {str(n.path) for n in nodes if n.is_open}.union(*(self._get_open_paths(n.children) for n in nodes))

    def _set_node_open(self, target, state, nodes=None):
        for n in (nodes if nodes is not None else getattr(self, 'nodes', [])):
            if n.path == target:    
                n.is_open = state; return True
            if self._set_node_open(target, state, n.children): 
                n.is_open = True; return True
        return False

    def show_search_panel(self, target_path=None): self.open_page(Node(name="Monsters", path=self.monsters_dir, is_entity=False, level=0), view_type="root_folder")
    def open_spells_manager(self): self.open_page(Node(name="Spells", path=self.spells_dir, is_entity=False, level=0), view_type="root_folder")

    def clear_viewer_and_tree(self):
        self.stat_viewer.pack_forget(); self.combat_viewer.pack_forget(); self.refresh_tree_silent()
        self.open_page(Node(name="Campaign Map", path=self.map_dir, is_entity=False, level=0), view_type="root_folder")

    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#fae6c5", foreground="black", rowheight=35, fieldbackground="#fdf1dc", font=("Georgia", 12), borderwidth=0)
        style.configure("Treeview.Heading", font=("Georgia", 13, "bold"), background="#fdf1dc", foreground="#7a200d")
        style.map("Treeview", background=[("selected", "#4a90e2")])

        self.paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL); self.paned_window.pack(fill=tk.BOTH, expand=True)
        self.tree_frame = tk.Frame(self.paned_window, bg="#fae6c5"); self.paned_window.add(self.tree_frame, weight=1)

        self.tree_canvas = tk.Canvas(self.tree_frame, bg="#fae6c5", highlightthickness=0)
        self.tree_scroll = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree_canvas.yview)
        self.tree_canvas.configure(yscrollcommand=self.tree_scroll.set)
        self.tree_scroll.pack(side=tk.RIGHT, fill=tk.Y); self.tree_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree_inner = tk.Frame(self.tree_canvas, bg="#fae6c5")
        self.tree_window = self.tree_canvas.create_window((0, 0), window=self.tree_inner, anchor="nw")
        self.tree_inner.bind("<Configure>", lambda e: self.tree_canvas.configure(scrollregion=self.tree_canvas.bbox("all")))
        self.tree_canvas.bind("<Configure>", lambda e: self.tree_canvas.itemconfig(self.tree_window, width=e.width))

        self.right_frame = tk.Frame(self.paned_window, bg="#fdf1dc"); self.paned_window.add(self.right_frame, weight=3)
        # Removed hardcoded height and pack_propagate restrictions so the navbar can grow vertically if text wraps
        self.nav_bar = tk.Frame(self.right_frame, bg="#fdf1dc")
        self.nav_bar.pack(fill=tk.X, padx=10, pady=5)
        
        self.back_btn = tk.Button(self.nav_bar, text="← BACK", bg="#58180d", fg="white", font=("Georgia", 10, "bold"), command=self.navigate_back)
        
        # Configure title label to use left-anchored expansion
        self.page_title_lbl = tk.Label(self.nav_bar, text="", font=("Georgia", 12, "bold"), bg="#fdf1dc", fg="#7a200d", anchor="w", justify=tk.LEFT)
        self.page_title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20, pady=2)

        # Dynamic binding to recalculate wraplength proportionally on window resizes
        def adjust_nav_title_wrap(event):
            avail_width = event.width - 140 # Leave a safe margin for the back button
            if avail_width > 50:
                self.page_title_lbl.configure(wraplength=avail_width)
        self.nav_bar.bind("<Configure>", adjust_nav_title_wrap)
        self.view_pane = tk.Frame(self.right_frame, bg="#fdf1dc"); self.view_pane.pack(fill=tk.BOTH, expand=True)
        
        self.stat_viewer = StatBlockRenderer(self.view_pane)
        self.stat_viewer.set_spell_callback(self.on_spell_clicked); self.stat_viewer.set_spells_index(self.spells_index); self.stat_viewer.set_location_link_callback(self.on_location_link_clicked)
        self.stat_viewer._hover_data_resolver = self.resolve_hover_data
        self.combat_viewer = CombatRenderer(self.view_pane, open_statblock_cb=self._combat_open_statblock, save_cb=self.save_combat_edits, add_bestiary_cb=self._combat_add_bestiary, add_camp_mon_cb=self._combat_add_camp_mon, add_camp_npc_cb=self._combat_add_camp_npc, cancel_cb=self.navigate_back)
        self.map_graph_viewer = MapGraphRenderer(self.view_pane, map_root_dir=self.map_dir, navigate_to_node_cb=lambda n: self.open_page(n, view_type="location", is_reference_click=True), mode = 'location')
        self.events_graph_viewer = MapGraphRenderer(self.view_pane, map_root_dir=self.events_dir, navigate_to_node_cb=lambda n: self.open_page(n, view_type="event", is_reference_click=True), mode = 'event')
        # Monsters Indexes Dashboard
        self.search_frame = tk.Frame(self.view_pane, bg="#fdf1dc")
        tk.Label(self.search_frame, text="Monster Database", font=("Georgia", 16, "bold"), bg="#fdf1dc", fg="#7a200d").pack(pady=10)
        self.search_var = tk.StringVar(); self.search_var.trace_add("write", lambda *a: self.apply_monster_query())
        self.search_entry = tk.Entry(self.search_frame, textvariable=self.search_var, font=("Georgia", 14), bg="#ffffff", fg="black", insertbackground="black"); self.search_entry.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        m_tools = tk.Frame(self.search_frame, bg="#fdf1dc"); m_tools.pack(fill=tk.X, padx=20, pady=(0, 5))
        for op in ["AND", "OR", "(", ")"]: tk.Button(m_tools, text=op, bg="#e0cbb0", fg="black", font=("Arial", 9, "bold"), command=lambda o=op: self._add_qblock_generic(self.monster_query_blocks, o, self.render_mqblocks, self.apply_monster_query)).pack(side=tk.LEFT, padx=2)
        tk.Button(m_tools, text="+ Filter", bg="#d9ad6c", fg="black", command=self.open_monster_filter_dialog).pack(side=tk.LEFT, padx=10)
        tk.Button(m_tools, text="Clear Filters", bg="#ff4d4d", fg="white", command=lambda: (self.monster_query_blocks.clear(), self.render_mqblocks(), self.apply_monster_query())).pack(side=tk.RIGHT, padx=2)
        self.m_query_canvas_frame = tk.Frame(self.search_frame, bg="#f5e6ce", bd=1, relief=tk.SUNKEN); self.m_query_canvas_frame.pack(fill=tk.X, padx=20, pady=(0, 10), ipady=5)
        
        lb_f = tk.Frame(self.search_frame, bg="#fdf1dc"); lb_f.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        self.monster_tree = ttk.Treeview(lb_f, columns=("name", "type", "cr", "source"), show="headings", selectmode="browse"); self.monster_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for c, w in [("name", 300), ("type", 150), ("cr", 60), ("source", 80)]:
            self.monster_tree.heading(c, text=c.title(), anchor="center" if c in ["cr", "source"] else "w"); self.monster_tree.column(c, width=w, anchor="center" if c in ["cr", "source"] else "w")
        self.monster_tree.tag_configure("evenrow", background="#f5e6ce", foreground="black"); self.monster_tree.tag_configure("oddrow", background="#fae6c5", foreground="black")
        scr = ttk.Scrollbar(lb_f, orient="vertical", command=self.monster_tree.yview); scr.pack(side=tk.RIGHT, fill=tk.Y); self.monster_tree.configure(yscrollcommand=scr.set); self.monster_tree.bind("<Double-1>", self.on_monster_selected)
        tk.Button(self.search_frame, text="Add Selected Monster", bg="#4a90e2", fg="white", font=("Arial", 11, "bold"), command=lambda: self.on_monster_selected(None)).pack(pady=10)

        # Spells Indexes Dashboard
        self.spell_manager_frame = tk.Frame(self.view_pane, bg="#fdf1dc")
        tk.Label(self.spell_manager_frame, text="Spell Database", font=("Georgia", 16, "bold"), bg="#fdf1dc", fg="#7a200d").pack(pady=10)
        self.spell_search_var = tk.StringVar(); self.spell_search_var.trace_add("write", lambda *a: self.apply_spell_query())
        tk.Entry(self.spell_manager_frame, textvariable=self.spell_search_var, font=("Georgia", 14), bg="#ffffff", fg="black", insertbackground="black").pack(fill=tk.X, padx=20, pady=(0, 10))
        q_tools = tk.Frame(self.spell_manager_frame, bg="#fdf1dc"); q_tools.pack(fill=tk.X, padx=20, pady=(0, 5))
        for op in ["AND", "OR", "(", ")"]: tk.Button(q_tools, text=op, bg="#e0cbb0", fg="black", font=("Arial", 9, "bold"), command=lambda o=op: self._add_qblock_generic(self.query_blocks, o, self.render_qblocks, self.apply_spell_query)).pack(side=tk.LEFT, padx=2)
        tk.Button(q_tools, text="+ Filter", bg="#d9ad6c", fg="black", command=self.open_filter_dialog).pack(side=tk.LEFT, padx=10)
        tk.Button(q_tools, text="Clear Filters", bg="#ff4d4d", fg="white", command=lambda: (self.query_blocks.clear(), self.render_qblocks(), self.apply_spell_query())).pack(side=tk.RIGHT, padx=2)
        self.query_canvas_frame = tk.Frame(self.spell_manager_frame, bg="#f5e6ce", bd=1, relief=tk.SUNKEN); self.query_canvas_frame.pack(fill=tk.X, padx=20, pady=(0, 10), ipady=5)

        s_lf = tk.Frame(self.spell_manager_frame, bg="#fdf1dc"); s_lf.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        self.spell_tree = ttk.Treeview(s_lf, columns=("name", "level", "school", "source"), show="headings", selectmode="browse"); self.spell_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for c, w in [("name", 300), ("level", 60), ("school", 150), ("source", 80)]:
            self.spell_tree.heading(c, text=c.title(), anchor="center" if c in ["level", "source"] else "w"); self.spell_tree.column(c, width=w, anchor="center" if c in ["level", "source"] else "w")
        self.spell_tree.tag_configure("evenrow", background="#f5e6ce", foreground="black"); self.spell_tree.tag_configure("oddrow", background="#fae6c5", foreground="black")
        s_scr = ttk.Scrollbar(s_lf, orient="vertical", command=self.spell_tree.yview); s_scr.pack(side=tk.RIGHT, fill=tk.Y); self.spell_tree.configure(yscrollcommand=s_scr.set); self.spell_tree.bind("<Double-1>", self.on_spell_manager_selected)

        self.placeholder_frame = tk.Frame(self.view_pane, bg="#fdf1dc"); self.placeholder_lbl = tk.Label(self.placeholder_frame, text="", font=("Georgia", 14, "italic"), bg="#fdf1dc", fg="black"); self.placeholder_lbl.pack(expand=True)
        def commit_music_metadata_changes(meta_dict):
            if self.current_state and self.current_state.data:
                self.current_state.data["music"] = meta_dict
                self._save_current_focused_sheet_data()
                self.music_manager_ui.sync_with_active_page_context(self.current_state.data)

        # NEW: Supplies hyperlinked action hooks directly to your audio engine frame
        def handle_focus_hyperlink_click(name, category):
            self.on_location_link_clicked(name, category)

        self.music_manager_ui = MusicManagerPanel(
            self.right_frame, 
            self.music_service, 
            commit_music_metadata_changes,
            handle_focus_hyperlink_click
        )

    def resolve_hover_data(self, prefix, name):
        """Fetches and inflates campaign JSON sheets on-the-fly for hover tooltips."""
        try:
            if prefix == "PATH_TAG":
                p = Path(name)
                sj = p / f"{p.name}.json"
                if sj.exists():
                    with open(sj, "r", encoding="utf-8") as f:
                        dtype = "event" if "events" in str(p).lower() else "location"
                        return self._inflate_refs(json.load(f)), dtype
                        
            elif prefix == "SPELL_TAG":
                sd = next((s for s in self.spells_index if s["name"].lower() == name.lower()), None)
                return copy.deepcopy(sd), "spell"
                
            elif prefix in ["LOC_MON_TAG", "LOC_NPC_TAG"]:
                folder = self.monsters_dir if prefix == "LOC_MON_TAG" else self.npcs_dir
                p = Path(name)
                if not p.exists(): p = folder / name
                jsons = list(p.glob("*.json")) if p.is_dir() else [p] if p.exists() else []
                if jsons:
                    with open(jsons[0], "r", encoding="utf-8") as f:
                        return self._inflate_refs(json.load(f)), ("monster" if prefix == "LOC_MON_TAG" else "npc")
                        
            elif prefix == "LOC_OBJ_TAG":
                p = Path(name)
                if not p.exists(): p = self.objects_dir / f"{name}.json"
                if p.exists():
                    with open(p, "r", encoding="utf-8") as f:
                        return self._inflate_refs(json.load(f)), "object"
                        
            elif prefix in ["LOC_EVT_TAG", "LOC_CONN_TAG"]:
                p = Path(name)
                if not p.exists():
                    p = self.events_dir / name
                    if not p.exists(): p = self.map_dir / name
                    if not p.exists():
                        found = list(self.events_dir.rglob(name)) + list(self.map_dir.rglob(name))
                        if found and found[0].is_dir(): p = found[0]
                sj = p / f"{p.name}.json"
                if sj.exists():
                    with open(sj, "r", encoding="utf-8") as f:
                        dtype = "event" if "events" in str(p).lower() else "location"
                        return self._inflate_refs(json.load(f)), dtype
        except Exception as e:
            print(f"Hover preview resolution failed: {e}")
        return None, None

    def _inflate_refs(self, data):
        """Recursively parses raw saved JSON objects and inflates path data strings into 
        SyncRef string subclass instances so they format natively as plain names in lists.
        """
        if not isinstance(data, dict): return data
        keys = ["monsters", "npcs", "combats", "events", "locations", "objects", "owners"]
        for k in keys:
            if k in data and isinstance(data[k], list):
                new_list = []
                for item in data[k]:
                    if isinstance(item, dict) and "name" in item and "path" in item:
                        new_list.append(SyncRef(item["name"], item["path"]))
                    elif isinstance(item, str) and item.strip():
                        p = Path(item)
                        name = p.stem if p.is_file() else p.name
                        new_list.append(SyncRef(name, str(p.resolve())))
                    else:
                        new_list.append(item)
                data[k] = new_list
        if "connections" in data and isinstance(data["connections"], list):
            for conn in data["connections"]:
                if isinstance(conn, dict) and "target" in conn:
                    t = conn["target"]
                    if isinstance(t, dict) and "name" in t and "path" in t:
                        conn["target"] = SyncRef(t["name"], t["path"])
                    elif isinstance(t, str) and t.strip():
                        p = Path(t)
                        name = p.stem if p.is_file() else p.name
                        conn["target"] = SyncRef(name, str(p.resolve()))
        return data

    def _serialize_refs(self, data):
        """Transforms tracking lists of SyncRef strings back into standard two-variable 
        dictionary objects right before saving them to disk.
        """
        if not isinstance(data, dict): return data
        keys = ["monsters", "npcs", "combats", "events", "locations", "objects", "owners"]
        for k in keys:
            if k in data and isinstance(data[k], list):
                new_list = []
                for item in data[k]:
                    if hasattr(item, "path"):
                        new_list.append({"name": str(item), "path": item.path})
                    elif isinstance(item, dict) and "name" in item and "path" in item:
                        new_list.append({"name": item["name"], "path": item["path"]})
                    elif isinstance(item, str) and item.strip():
                        p = Path(item)
                        name = p.stem if p.is_file() else p.name
                        new_list.append({"name": name, "path": str(p.resolve())})
                    else:
                        new_list.append(item)
                data[k] = new_list
        if "connections" in data and isinstance(data["connections"], list):
            for conn in data["connections"]:
                if isinstance(conn, dict) and "target" in conn:
                    t = conn["target"]
                    if hasattr(t, "path"):
                        conn["target"] = {"name": str(t), "path": t.path}
                    elif isinstance(t, dict) and "name" in t and "path" in t:
                        conn["target"] = {"name": t["name"], "path": t["path"]}
                    elif isinstance(t, str) and t.strip():
                        p = Path(t)
                        name = p.stem if p.is_file() else p.name
                        conn["target"] = {"name": name, "path": str(p.resolve())}
        return data

    def open_page(self, node: Node, view_type: str, stat_path: Path = None, data: dict = None, is_reference_click: bool = False):
        if is_reference_click:
            new_state = PageState(node, view_type, stat_path=stat_path, data=data, prev=self.current_state)
        else:
            if node.level == 0: new_state = PageState(node, view_type, stat_path=stat_path, data=data, prev=None)
            else:
                def build_virtual_chain(current_node, current_view_type, current_stat_path=None):
                    if current_node.level == 0: return PageState(current_node, current_view_type, stat_path=current_stat_path, prev=None)
                    p_path = current_node.path.parent; p_level = current_node.level - 1
                    p_name = "Campaign Map" if p_path == self.map_dir else p_path.name
                    p_type = "root_folder" if (p_path.resolve() == self.root_dir.resolve() or p_path.resolve() in [self.map_dir.resolve(), self.events_dir.resolve(), self.objects_dir.resolve(), self.spells_dir.resolve(), self.monsters_dir.resolve(), self.npcs_dir.resolve(), self.combats_dir.resolve()]) else "event" if (p_path.resolve() == self.events_dir.resolve() or self.events_dir in p_path.parents) else "location"
                    p_stat_json = p_path / f"{p_path.name}.json" if p_type in ["location", "event"] else None
                    parent_state = build_virtual_chain(Node(name=p_name, path=p_path, is_entity=False, level=p_level, stat_path=p_stat_json), p_type, p_stat_json)
                    return PageState(current_node, current_view_type, stat_path=current_stat_path, prev=parent_state)
                new_state = build_virtual_chain(node, view_type, stat_path); new_state.data = data
        self.current_state = new_state; self._show_current_state_view()

    def navigate_back(self):
        if self.current_state and self.current_state.prev:
            self.current_state = self.current_state.prev; self._show_current_state_view()

    def _show_current_state_view(self):
        # 1. Clear out all viewport panel states from the screen space partition layout
        for panel in [self.stat_viewer, self.combat_viewer, self.search_frame, self.spell_manager_frame, self.placeholder_frame, self.map_graph_viewer, self.events_graph_viewer]: 
            panel.pack_forget()
            
        if not self.current_state: return
        if self.current_state.prev is None: self.back_btn.pack_forget()
        else: self.back_btn.pack(side=tk.LEFT, padx=10, pady=2)

        state = self.current_state
        self.page_title_lbl.config(text=f"Viewing: {state.node.name}")

        # Local layout reference pointer to maintain standard layout states when music is hidden
        target_panel = None

        # 2. Inflate data parameters context definitions and assign the display tracking reference
        if state.view_type in ["monster", "npc"]:
            target_panel = self.stat_viewer
            try:
                with open(state.stat_path, "r", encoding="utf-8") as f: data = json.load(f)
                data = self._inflate_refs(data)
                state.data = data
                self.stat_viewer.render_monster(data, back_cb=self.navigate_back)
                self.stat_viewer.add_top_buttons(state.node.path, self.view_full_portrait, lambda d: self.display_monster(state.node, edit_mode=True, back_cb=self.navigate_back))
            except Exception as e: print(f"Error loading sheet: {e}")

        elif state.view_type == "combat":
            target_panel = self.combat_viewer
            try:
                with open(state.stat_path, "r", encoding="utf-8") as f: data = json.load(f)
                data = self._inflate_refs(data)
                state.data = data
                if hasattr(self.combat_viewer, 'original_data'):
                    delattr(self.combat_viewer, 'original_data')
                self.combat_viewer.render_combat(data, state.node.path)
            except Exception as e: print(f"Error loading combat: {e}")

        elif state.view_type == "spell":
            target_panel = self.stat_viewer
            spell_data = state.data or next((s for s in self.spells_index if s["name"].lower() == state.node.name.lower()), None)
            if spell_data:
                state.data = spell_data
                self.stat_viewer.render_spell(spell_data, back_callback=self.navigate_back)
                if spell_data.get("source") == "Custom":
                    self.stat_viewer.add_custom_spell_buttons(spell_data, edit_cb=lambda sd: self.stat_viewer.render_spell_edit_mode(sd, self.save_spell_edits, self.navigate_back), del_cb=self.delete_custom_spell)
            else: messagebox.showerror("Error", f"Spell lookup failed inside compendium.")

        elif state.node.path.resolve() == self.monsters_dir.resolve():
            target_panel = self.search_frame
            self.apply_monster_query()

        elif state.node.path.resolve() == self.spells_dir.resolve() or state.node.name == "Spells":
            target_panel = self.spell_manager_frame
            self.apply_spell_query()
            
        elif state.view_type in ["location", "event"]:
            target_panel = self.stat_viewer
            stat_path = state.node.stat_path or (state.node.path / f"{state.node.path.name}.json")
            if not stat_path.exists():
                default_data = {"name": state.node.name, "description": "", "monsters": [], "npcs": [], "combats": [], "events" if state.view_type == "location" else "locations": [], "objects": [], "connections": []}
                json.dump(default_data, open(stat_path, "w", encoding="utf-8"), indent=4); state.node.stat_path = stat_path
            try:
                with open(stat_path, "r", encoding="utf-8") as f: data = json.load(f)
                data = self._inflate_refs(data)
                state.data = data
                if state.view_type == "location": self.stat_viewer.render_location(data, back_cb=self.navigate_back)
                else: self.stat_viewer.render_event(data, back_cb=self.navigate_back)
                self.stat_viewer.add_location_top_buttons(state.node.path, lambda p: self._open_campaign_node_edit(state.node, stat_path, data, state.view_type == "location"))
            except Exception as e: print(f"Error loading tracking sheet: {e}")

        elif state.view_type == "object":
            target_panel = self.stat_viewer
            try:
                with open(state.stat_path, "r", encoding="utf-8") as f: data = json.load(f)
                data = self._inflate_refs(data)
                state.data = data
                self.stat_viewer.render_object(data, back_cb=self.navigate_back)
                self.stat_viewer.add_location_top_buttons(state.node.path, lambda p: self.open_object_edit(state.node, state.stat_path, data))
            except Exception as e: print(f"Error loading object: {e}")

        elif state.view_type == "root_folder" and state.node.path.resolve() == self.map_dir.resolve():
            target_panel = self.map_graph_viewer
            self.map_graph_viewer.draw_graph()
        
        elif state.view_type == "root_folder" and state.node.path.resolve() == self.events_dir.resolve():
            target_panel = self.events_graph_viewer
            self.events_graph_viewer.draw_graph()
        
        else:
            # FIX: Clean fallback text labeling works elegantly for all structural folders
            target_panel = self.placeholder_frame
            self.placeholder_lbl.config(text=f"Directory Workspace Zone: '{state.node.name}'\nPath: {state.node.path}")

        # EXTENSION REQUIREMENT: Lazy-load folder data configurations for directories or root pages
        if not state.data and state.node and state.node.path:
            dir_path = Path(state.node.path) if Path(state.node.path).is_dir() else Path(state.node.path).parent
            if dir_path.is_dir():
                meta_file = dir_path / "folder_metadata.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f: state.data = json.load(f)
                    except: state.data = {"name": state.node.name}
                else:
                    state.data = {"name": state.node.name}

        # 3. Handle conditional view packing geometry relative to the global visibility flag
        if hasattr(self, 'music_visible') and self.music_visible:
            self.music_manager_ui.pack(fill=tk.BOTH, expand=True)
            self.music_manager_ui.sync_with_active_page_context(state.data if state else None)
        else:
            self.music_manager_ui.pack_forget()
            if target_panel:
                target_panel.pack(fill=tk.BOTH, expand=True)

        self.after(50, self.focus_set)

    # chips trackers
    def _add_qblock_generic(self, storage, val, render_cb, query_cb): storage.append(val); render_cb(); query_cb()
    def _remove_qblock_generic(self, storage, idx, render_cb, query_cb): storage.pop(idx); render_cb(); query_cb()
    def _toggle_qblock_generic(self, storage, idx, render_cb, query_cb): storage[idx] = "OR" if storage[idx] == "AND" else "AND"; render_cb(); query_cb()

    def _render_qblocks_generic(self, target_frame, storage, remove_cb, toggle_cb):
        for w in target_frame.winfo_children(): w.destroy()
        if not storage:
            tk.Label(target_frame, text="No active filters.", bg="#f5e6ce", fg="#555555", font=("Arial", 10, "italic")).pack(padx=10, pady=5); return
        for i, b in enumerate(storage):
            if isinstance(b, str):
                btn = tk.Button(target_frame, text=b, bg="#ff4d4d" if b == "AND" else "#4a90e2" if b == "OR" else "#e0cbb0", fg="white" if b in ["AND", "OR"] else "black", font=("Arial", 9, "bold"))
                if b in ["AND", "OR"]:
                    btn.config(command=lambda idx=i: toggle_cb(idx)); btn.bind("<Button-3>", lambda e, idx=i: remove_cb(idx))
                else: btn.config(command=lambda idx=i: remove_cb(idx))
            else:
                text = f"CR {b['min']}-{b['max']}" if b["type"] == "cr" else f"Lvl {b['min']}-{b['max']}" if b["type"] == "level" else f"{b['type'].title()}: {b['val']}"
                btn = tk.Button(target_frame, text=text, bg="#7a200d", fg="white", font=("Arial", 9, "bold"), command=lambda idx=i: remove_cb(idx))
            btn.pack(side=tk.LEFT, padx=2, pady=2)

    def render_mqblocks(self): self._render_qblocks_generic(self.m_query_canvas_frame, self.monster_query_blocks, lambda idx: self._remove_qblock_generic(self.monster_query_blocks, idx, self.render_mqblocks, self.apply_monster_query), lambda idx: self._toggle_qblock_generic(self.monster_query_blocks, idx, self.render_mqblocks, self.apply_monster_query))
    def render_qblocks(self): self._render_qblocks_generic(self.query_canvas_frame, self.query_blocks, lambda idx: self._remove_qblock_generic(self.query_blocks, idx, self.render_qblocks, self.apply_spell_query), lambda idx: self._toggle_qblock_generic(self.query_blocks, idx, self.render_qblocks, self.apply_spell_query))

    def apply_monster_query(self):
        for item in self.monster_tree.get_children(): self.monster_tree.delete(item)
        q_str = self.search_var.get().lower(); count = 0
        for m in self.monster_index:
            if q_str and q_str not in m["name"].lower(): continue
            if self.monster_query_blocks:
                expr = ""
                for b in self.monster_query_blocks:
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
            self.monster_tree.insert("", tk.END, values=(m["name"], m.get("type", "Unknown"), m.get("cr", "—"), m.get("source", "Unknown")), tags=(tag,))
            count += 1

    def apply_spell_query(self):
        for item in self.spell_tree.get_children(): self.spell_tree.delete(item)
        q_str = self.spell_search_var.get().lower(); count = 0
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
                except: pass
            tag = "evenrow" if count % 2 == 0 else "oddrow"
            self.spell_tree.insert("", tk.END, values=(s["name"], "Cantrip" if s.get("level", 0) == 0 else str(s.get("level", 0)), preprocess.SCHOOL_MAP.get(s.get("school", ""), "Unknown"), s.get("source", "Unknown")), tags=(tag,))
            count += 1

    def open_monster_filter_dialog(self):
        d = tk.Toplevel(self); d.title("Build Monster Filter"); d.geometry("450x600"); d.configure(bg="#fdf1dc")
        logic_var = tk.StringVar(value="AND")
        btn_logic = tk.Button(d, text="AND", bg="#ff4d4d", fg="white", font=("Arial", 12, "bold"), width=10, command=lambda: (logic_var.set("OR") if logic_var.get() == "AND" else logic_var.set("AND"), btn_logic.config(text=logic_var.get(), bg="#4a90e2" if logic_var.get() == "OR" else "#ff4d4d")))
        btn_logic.pack(pady=15)
        f = tk.Frame(d, bg="#fdf1dc"); f.pack(anchor="center", padx=20, pady=10)
        row_idx = 0
        def factory(lbl, cls, **kw):
            nonlocal row_idx
            tk.Label(f, text=lbl, bg="#fdf1dc", fg="black", font=("Arial", 10, "bold"), width=16, anchor="e").grid(row=row_idx, column=0, padx=(0, 15), pady=8, sticky="e")
            w = cls(f, **kw); w.grid(row=row_idx, column=1, pady=8, sticky="w"); row_idx += 1; return w
        min_cr = factory("Minimum CR:", tk.Scale, from_=0, to=30, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=180)
        max_cr = factory("Maximum CR:", tk.Scale, from_=0, to=30, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=180); max_cr.set(30)
        size_v = factory("Size Category:", ttk.Combobox, values=["All", "Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"], state="readonly", width=22); size_v.set("All")
        type_v = factory("Creature Type:", ttk.Combobox, values=["All", "Aberration", "Beast", "Celestial", "Construct", "Dragon", "Elemental", "Fey", "Fiend", "Giant", "Humanoid", "Monstrosity", "Ooze", "Plant", "Undead"], state="readonly", width=22); type_v.set("All")
        align_v = factory("Alignment Profile:", ttk.Combobox, values=["All", "Lawful Good", "Neutral Good", "Chaotic Good", "Lawful Neutral", "True Neutral", "Chaotic Neutral", "Lawful Evil", "Neutral Evil", "Chaotic Evil", "Unaligned", "Any"], state="readonly", width=22); align_v.set("All")
        env_v = factory("Environment:", ttk.Combobox, values=["All", "Arctic", "Coastal", "Desert", "Forest", "Grassland", "Hill", "Mountain", "Swamp", "Underdark", "Underwater", "Urban"], state="readonly", width=22); env_v.set("All")
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
        btn_logic = tk.Button(d, text="AND", bg="#ff4d4d", fg="white", font=("Arial", 12, "bold"), width=10, command=lambda: (logic_var.set("OR") if logic_var.get() == "AND" else logic_var.set("AND"), btn_logic.config(text=logic_var.get(), bg="#4a90e2" if logic_var.get() == "OR" else "#ff4d4d")))
        btn_logic.pack(pady=15)
        f = tk.Frame(d, bg="#fdf1dc"); f.pack(anchor="center", padx=20, pady=10)
        row_idx = 0
        def factory(lbl, cls, **kw):
            nonlocal row_idx
            tk.Label(f, text=lbl, bg="#fdf1dc", fg="black", font=("Arial", 10, "bold"), width=16, anchor="e").grid(row=row_idx, column=0, padx=(0, 15), pady=8, sticky="e")
            w = cls(f, **kw); w.grid(row=row_idx, column=1, pady=8, sticky="w"); row_idx += 1; return w
        min_v = factory("Minimum Level:", tk.Scale, from_=0, to=12, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=180)
        max_v = factory("Maximum Level:", tk.Scale, from_=0, to=12, orient=tk.HORIZONTAL, bg="#fdf1dc", fg="black", highlightthickness=0, length=180); max_v.set(12)
        school_options = ["All"] + list(preprocess.SCHOOL_MAP.values())
        sch_v = factory("School:", ttk.Combobox, values=school_options, state="readonly", width=22); sch_v.set("All")
        dmg_v = factory("Damage Type:", ttk.Combobox, values=["All", "Acid", "Bludgeoning", "Cold", "Fire", "Force", "Lightning", "Necrotic", "Piercing", "Poison", "Psychic", "Radiant", "Slashing", "Thunder"], state="readonly", width=22); dmg_v.set("All")
        save_v = factory("Saving Throw:", ttk.Combobox, values=["All", "Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"], state="readonly", width=22); save_v.set("All")
        conc_v = factory("Concentration:", ttk.Combobox, values=["All", "Yes", "No"], state="readonly", width=22); conc_v.set("All")
        def apply_f():
            filters = []
            if min_v.get() > 0 or max_v.get() < 12: filters.append({"type": "level", "min": min_v.get(), "max": max_v.get()})
            if sch_v.get() != "All": filters.append({"type": "school", "val": preprocess.INV_SCHOOL_MAP[sch_v.get()]})
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

    def on_spell_manager_selected(self, event):
        sel = self.spell_tree.selection()
        if not sel: return
        sn = self.spell_tree.item(sel[0])['values'][0]; sd = next((s for s in self.spells_index if s["name"].lower() == sn.lower()), None)
        if sd: self.open_page(Node(name=sd["name"], path=self.spells_dir / f"{sd['name']}.json", is_entity=True, level=1), view_type="spell", stat_path=self.spells_dir / f"{sd['name']}.json", data=sd, is_reference_click=True)

    def create_new_spell(self):
        sn = simpledialog.askstring("New Spell", "Enter a name for the new spell:")
        if not sn or not sn.strip() or any(s["name"].lower() == sn.lower() for s in self.spells_index): return
        sf = "".join([c for c in sn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        nd = {"name": sn, "source": "Custom", "level": 1, "school": "V", "time": [{"number": 1, "unit": "action"}], "range": {"type": "point", "distance": {"type": "feet", "amount": 60}}, "components": {"v": True, "s": True}, "duration": [{"type": "instant"}], "entries": ["Describe spell."]}
        self.spells_index.append(nd); self.spells_index = sorted(self.spells_index, key=lambda x: x["name"].lower())
        json.dump(nd, open(self.spells_dir / f"{sf}.json", "w", encoding="utf-8"), indent=4); json.dump(self.spells_index, open("spells.json", "w", encoding="utf-8"), indent=4)
        self.stat_viewer.set_spells_index(self.spells_index); self.refresh_tree_silent()
        self.open_page(Node(name=sn, path=self.spells_dir / f"{sf}.json", is_entity=True, level=1), view_type="spell", stat_path=self.spells_dir / f"{sf}.json", data=nd, is_reference_click=False)

    def save_spell_edits(self, old_name, new_data):
        nn = new_data["name"]; sf = "".join([c for c in nn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
        if old_name and old_name.lower() != nn.lower():
            osf = "".join([c for c in old_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
            if (self.spells_dir / f"{osf}.json").exists(): (self.spells_dir / f"{osf}.json").unlink()
        t_idx = next((i for i, s in enumerate(self.spells_index) if s["name"].lower() == old_name.lower()), -1)
        if t_idx >= 0: self.spells_index[t_idx] = new_data
        else: self.spells_index.append(new_data)
        self.spells_index = sorted(self.spells_index, key=lambda x: x["name"].lower())
        json.dump(new_data, open(self.spells_dir / f"{sf}.json", "w", encoding="utf-8"), indent=4); json.dump(self.spells_index, open("spells.json", "w", encoding="utf-8"), indent=4)
        self.stat_viewer.set_spells_index(self.spells_index); self.refresh_tree_silent()
        self.open_page(Node(name=nn, path=self.spells_dir / f"{sf}.json", is_entity=True, level=1), view_type="spell", stat_path=self.spells_dir / f"{sf}.json", data=new_data, is_reference_click=False)

    def delete_custom_spell(self, s_data):
        if messagebox.askyesno("Confirm Delete", f"Delete spell '{s_data['name']}'?"):
            self.spells_index = [s for s in self.spells_index if s["name"].lower() != s_data["name"].lower()]
            sf = "".join([c for c in s_data["name"] if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
            if (self.spells_dir / f"{sf}.json").exists(): (self.spells_dir / f"{sf}.json").unlink()
            json.dump(self.spells_index, open("spells.json", "w", encoding="utf-8"), indent=4)
            self.stat_viewer.set_spells_index(self.spells_index); self.clear_viewer_and_tree()

    def on_spell_clicked(self, s_name):
        sd = next((s for s in self.spells_index if s["name"].lower() == s_name.lower()), None)
        if not sd: 
            messagebox.showinfo("Not Found", f"Spell reference '{s_name}' not found.")
            return
        self.open_page(Node(name=sd["name"], path=self.spells_dir / f"{sd['name']}.json", is_entity=True, level=1), view_type="spell", stat_path=self.spells_dir / f"{sd['name']}.json", data=sd, is_reference_click=True)

    def on_monster_selected(self, event=None):
        sel = self.monster_tree.selection()
        if not sel: return
        item = self.monster_tree.item(sel[0]); m_meta = next((m for m in self.monster_index if m["name"] == item['values'][0] and m.get("source", "Unknown") == item['values'][3]), None)
        if not m_meta: return
        try:
            g_dir, s_name = downloader.download_monster_data(m_meta, self.monsters_dir)
            if not g_dir: return
            self.refresh_tree_silent(); t_json = g_dir / f"{s_name}.json"
            self.open_page(Node(name=m_meta["name"], path=g_dir, is_entity=True, level=1, stat_path=t_json), view_type="monster", stat_path=t_json, is_reference_click=False)
        except Exception as e: messagebox.showerror("Error", f"Failed: {e}")

    def display_monster_by_path(self, target_path: Path, edit_mode=False, back_cb=None):
        def search(nodes):
            for n in nodes:
                if n.path == target_path and n.is_entity: return n
                res = search(n.children)
                if res: return res
            return None
        tn = search(self.nodes) or (Node(name=target_path.name, path=target_path, is_entity=True, level=0, stat_path=list(target_path.glob("*.json"))[0]) if list(target_path.glob("*.json")) else None)
        if tn: self.display_monster(tn, edit_mode, back_cb=back_cb)

    def display_monster(self, node: Node, edit_mode=False, back_cb=None):
        for f in [self.search_frame, self.spell_manager_frame, self.combat_viewer]: f.pack_forget()
        self.stat_viewer.pack(fill=tk.BOTH, expand=True)
        if not node or not node.stat_path: return
        try:
            with open(node.stat_path, "r", encoding="utf-8") as f: data = json.load(f)
            data = self._inflate_refs(data)
            l_name = node.path.parent.parent.name if len(node.path.parts) >= 3 else "Unknown"
            if edit_mode: self.stat_viewer.render_edit_mode(data, node.path, l_name, self.save_monster_edits, lambda: self.display_monster(node, edit_mode=False, back_cb=back_cb), add_existing_object_cb=lambda r: EntitySelectionDialog(self, self.objects_dir, "Objects", lambda name: r(SyncRef(name, str((self.objects_dir / f"{name}.json").resolve())))))
            else:
                self.stat_viewer.render_monster(data, back_cb=back_cb)
                self.stat_viewer.add_top_buttons(node.path, self.view_full_portrait, lambda d: self.display_monster(node, edit_mode=True, back_cb=back_cb))
        except Exception as e: print(f"Failed to load: {e}")

    def display_combat_by_path(self, target_path: Path, edit_mode=False):
        def search(nodes):
            for n in nodes:
                if n.path == target_path and n.is_entity: return n
                res = search(n.children)
                if res: return res
            return None
        tn = search(self.nodes) or (Node(name=target_path.name, path=target_path, is_entity=True, level=0, stat_path=list(target_path.glob("*.json"))[0]) if list(target_path.glob("*.json")) else None)
        if tn: self.display_combat(tn)

    def display_combat(self, node: Node):
        for f in [self.search_frame, self.spell_manager_frame, self.stat_viewer]: f.pack_forget()
        self.combat_viewer.pack(fill=tk.BOTH, expand=True)
        if not node or not node.stat_path: return
        try:
            with open(node.stat_path, "r", encoding="utf-8") as f: data = json.load(f)
            data = self._inflate_refs(data)
            if hasattr(self.combat_viewer, 'original_data'):
                delattr(self.combat_viewer, 'original_data')
            self.combat_viewer.render_combat(data, node.path)
        except Exception as e: print(f"Failed to load combat: {e}")

    def create_new_combat(self, parent_path: Path):
        base, safe, c = "New Combat", "New Combat", 1
        while (self.combats_dir / safe).exists(): 
            safe = f"{base} {c}"
            c += 1
        g_dir = self.combats_dir / safe; g_dir.mkdir(parents=True, exist_ok=True)
        c_data = {"name": safe, "location": "Any", "time": "Any", "description": "None", "over": "No", "outcome": "None", "participants": []}
        t_json = g_dir / f"{safe}.json"; json.dump(c_data, open(t_json, "w", encoding="utf-8"), indent=4)
        if Path("./assets/icons/combat_icon.png").exists():
            try:
                shutil.copy(Path("./assets/icons/combat_icon.png"), g_dir / "portrait.png")
                Image.open(Path("./assets/icons/combat_icon.png")).thumbnail((64, 64))
                Image.open(Path("./assets/icons/combat_icon.png")).save(g_dir / "icon.webp", "WEBP")
            except: pass
        self.refresh_tree_silent()
        self.open_page(Node(name=safe, path=g_dir, is_entity=True, level=1, stat_path=t_json), view_type="combat", stat_path=t_json, is_reference_click=False)

    def _combat_open_statblock(self, target_name, folder_type):
        # FIX COMBAT PARTICIPANTS AUTO-SAVE: Commit UI workspace properties 
        # down to disk before switching views so active items are never discarded
        if self.combat_viewer.winfo_ismapped():
            self.combat_viewer._sync_all_rows()
            c_data = self._serialize_refs(self.combat_viewer.current_data)
            try:
                json.dump(c_data, open(self.combat_viewer.combat_dir / f"{self.combat_viewer.combat_dir.name}.json", "w", encoding="utf-8"), indent=4)
            except: pass

        p = Path(target_name)
        if p.exists():
            jsons = list(p.glob("*.json")) if p.is_dir() else [p]
            if jsons: self.open_page(Node(name=p.name, path=p, is_entity=True, level=1, stat_path=jsons[0]), view_type="monster" if "monsters" in str(p).lower() else "npc", stat_path=jsons[0], is_reference_click=True)
        else:
            g_path = self.root_dir / folder_type / target_name; jsons = list(g_path.glob("*.json"))
            if jsons: self.open_page(Node(name=target_name, path=g_path, is_entity=True, level=1), view_type="monster" if folder_type == "Monsters" else "npc", stat_path=jsons[0], is_reference_click=True)

    def _combat_add_bestiary(self, combat_dir, callback):
        def on_selected(m):
            g_dir, s_name = downloader.download_monster_data(m, self.monsters_dir)
            if g_dir:
                self.refresh_tree_silent()
                callback(str(g_dir.resolve()), "Monsters")
        MonsterSearchDialog(self, self.monster_index, on_selected)

    def _combat_add_camp_mon(self, callback): 
        EntitySelectionDialog(self, self.monsters_dir, "Monsters", lambda tn: callback(str((self.monsters_dir / tn).resolve()), "Monsters"))

    def _combat_add_camp_npc(self, callback): 
        EntitySelectionDialog(self, self.npcs_dir, "NPCs", lambda tn: callback(str((self.npcs_dir / tn).resolve()), "NPCs"))

    def _get_entity_hp(self, target_name, folder_category):
        p = Path(target_name)
        if p.exists():
            gp = list(p.glob("*.json"))[0] if p.is_dir() else p
        else:
            gp = self.root_dir / folder_category / target_name / f"{target_name}.json"
        return json.load(open(gp, "r", encoding="utf-8")).get("hp", {}).get("average", 10) if gp.exists() else 10

    def create_new_npc(self, parent_path: Path):
        base, safe, c = "New NPC", "New NPC", 1
        while (self.npcs_dir / safe).exists(): 
            safe = f"{base} {c}"
            c += 1
        g_dir = self.npcs_dir / safe; g_dir.mkdir(parents=True, exist_ok=True)
        nd = {"name": safe, "source": "Custom", "level": 1, "size": ["M"], "type": "humanoid", "alignment": ["N"], "ac": [10], "hp": {"average": 4, "formula": "1d8"}, "speed": {"walk": 30}, "str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10, "action": [{"name": "Unarmed Strike", "entries": ["{@atk mw} {@hit 2} to hit, reach 5 ft., one target. {@h}1 bludgeoning damage."]}]}
        t_json = g_dir / f"{safe}.json"; json.dump(nd, open(t_json, "w", encoding="utf-8"), indent=4)
        if Path("./assets/icons/default_npc.png").exists():
            try:
                Image.open("./assets/icons/default_npc.png").save(g_dir / "portrait.png", "PNG")
                Image.open("./assets/icons/default_npc.png").thumbnail((64, 64))
                Image.open("./assets/icons/default_npc.png").save(g_dir / "icon.webp", "WEBP")
            except: pass
        self.refresh_tree_silent()
        self.open_page(Node(name=safe, path=g_dir, is_entity=True, level=1, stat_path=t_json), view_type="npc", stat_path=t_json, is_reference_click=False)

    def save_monster_edits(self, old_dir: Path, new_data: dict):
        old_name, nn = old_dir.name, new_data.get("name", "Unknown")
        ns = "".join([c for c in nn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip() or "Unnamed"
        g_dir = old_dir
        old_path = old_dir.resolve()
        if ns != old_name:
            target = g_dir.parent / ns
            if target.exists() and target != g_dir: 
                messagebox.showerror("Error", "An entry with that name already exists.")
                return
            if (g_dir / f"{old_name}.json").exists(): (g_dir / f"{old_name}.json").rename(g_dir / f"{ns}.json")
            g_dir.rename(target); g_dir = target
            
        new_data = self._serialize_refs(new_data)
        fj = g_dir / f"{ns}.json"; json.dump(new_data, open(fj, "w", encoding="utf-8"), indent=4)
        new_path = g_dir.resolve()
        self.sync_reciprocal_relations(old_path_prefix=old_path, new_path_prefix=new_path, saved_path=fj)
        self.refresh_tree_silent()
        self.open_page(Node(name=nn, path=g_dir, is_entity=True, level=1, stat_path=fj), view_type="monster" if "Monsters" in str(g_dir) else "npc", stat_path=fj, is_reference_click=False)

    def save_combat_edits(self, combat_dir: Path, new_data: dict):
        old_name, nn = combat_dir.name, new_data.get("name", "Unknown Combat")
        ns = "".join([c for c in nn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip() or "Unnamed"
        g_dir = combat_dir
        old_path = combat_dir.resolve()
        if ns != old_name:
            target = g_dir.parent / ns
            if target.exists() and target != g_dir: 
                messagebox.showerror("Error", "An entry with that name already exists.")
                return
            if (g_dir / f"{old_name}.json").exists(): (g_dir / f"{old_name}.json").rename(g_dir / f"{ns}.json")
            g_dir.rename(target); g_dir = target
            
        new_data = self._serialize_refs(new_data)
        fj = g_dir / f"{ns}.json"; json.dump(new_data, open(fj, "w", encoding="utf-8"), indent=4)
        new_path = g_dir.resolve()
        self.sync_reciprocal_relations(old_path_prefix=old_path, new_path_prefix=new_path, saved_path=fj)
        self.refresh_tree_silent()
        self.open_page(Node(name=nn, path=g_dir, is_entity=True, level=1, stat_path=fj), view_type="combat", stat_path=fj, is_reference_click=False)

    def create_new_location(self, p_path: Path):
        fn = simpledialog.askstring("Add Location", "Location name:")
        if not fn or not fn.strip(): return
        sn = "".join([c for c in fn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        nd = p_path / sn; nd.mkdir(parents=True, exist_ok=True)
        if Path("./assets/icons/map_icon.png").exists():
            try: Image.open("./assets/icons/map_icon.png").thumbnail((64,64)); Image.open("./assets/icons/map_icon.png").save(nd / f"{sn}.png", "PNG")
            except: pass
        self._set_node_open(p_path, True); self.refresh_tree_silent()
        
        # FIX: If the map graph layout workspace is open, refresh the canvas views instead of forcing a page jump
        if hasattr(self, 'map_graph_viewer') and self.map_graph_viewer.winfo_ismapped():
            self.map_graph_viewer.draw_graph()
        else:
            self.open_page(Node(name=fn, path=nd, is_entity=False, level=len(nd.relative_to(self.map_dir).parts)), view_type="location", is_reference_click=False)

    def refresh_tree(self): self.refresh_tree_silent()
        
    def refresh_tree_silent(self):
        op = self._get_open_paths(getattr(self, 'nodes', []))
        m_n = Node(name="Map", path=self.map_dir, is_entity=False, level=0, icon_path=Path("./assets/icons/map.png") if Path("./assets/icons/map.png").exists() else None, is_open=str(self.map_dir) in op)
        m_n.children = self.build_tree_model(self.map_dir, level=1, open_paths=op)
        e_n = Node(name="Events", path=self.events_dir, is_entity=False, level=0, icon_path=Path("./assets/icons/events.png") if Path("./assets/icons/events.png").exists() else None, is_open=str(self.events_dir) in op)
        e_n.children = self.build_tree_model(self.events_dir, level=1, open_paths=op)
        s_n = Node(name="Spells", path=self.spells_dir, is_entity=False, level=0, icon_path=Path("./assets/icons/spell.png") if Path("./assets/icons/spell.png").exists() else None, is_open=str(self.spells_dir) in op)
        s_n.children = self.build_tree_model(self.spells_dir, level=1, open_paths=op)
        mo_n = Node(name="Monsters", path=self.monsters_dir, is_entity=False, level=0, icon_path=Path("./assets/icons/monster.png") if Path("./assets/icons/monster.png").exists() else None, is_open=str(self.monsters_dir) in op)
        mo_n.children = self.build_tree_model(self.monsters_dir, level=1, open_paths=op)
        n_n = Node(name="NPCs", path=self.npcs_dir, is_entity=False, level=0, icon_path=Path("./assets/icons/npc.png") if Path("./assets/icons/npc.png").exists() else None, is_open=str(self.npcs_dir) in op)
        n_n.children = self.build_tree_model(self.npcs_dir, level=1, open_paths=op)
        c_n = Node(name="Combats", path=self.combats_dir, is_entity=False, level=0, icon_path=Path("./assets/icons/combat.png") if Path("./assets/icons/combat.png").exists() else None, is_open=str(self.combats_dir) in op)
        c_n.children = self.build_tree_model(self.combats_dir, level=1, open_paths=op)
        o_n = Node(name="Objects", path=self.objects_dir, is_entity=False, level=0, icon_path=Path("./assets/icons/objects.png") if Path("./assets/icons/objects.png").exists() else None, is_open=str(self.objects_dir) in op)
        o_n.children = self.build_tree_model(self.objects_dir, level=1, open_paths=op)
        self.nodes = [m_n, e_n, o_n, s_n, mo_n, n_n, c_n]; self.render_tree()

    def build_tree_model(self, path: Path, level: int, open_paths: set):
        nodes = []
        try: 
            items = sorted([p for p in path.iterdir()], key=lambda x: x.name.lower())
            dirs = [p for p in items if p.is_dir()]; files = [p for p in items if p.is_file() and p.suffix == '.json']
        except PermissionError: return nodes

        for item in files:
            if self.map_dir in item.parents or item.parent == self.map_dir or self.events_dir in item.parents or item.parent == self.events_dir: continue
            icon = Path("./assets/icons/object_icon.png") if item.parent == self.objects_dir else Path("./assets/icons/spell_icon.png")
            nodes.append(Node(name=item.stem, path=item, is_entity=True, level=level, icon_path=icon if icon.exists() else None, stat_path=item))

        for item in dirs:
            jsons, webps = list(item.glob("*.json")), list(item.glob("*.webp"))
            is_map, is_evt = (item == self.map_dir or self.map_dir in item.parents), (item == self.events_dir or self.events_dir in item.parents)
            if jsons and not is_map and not is_evt:
                nodes.append(Node(name=item.name, path=item, is_entity=True, level=level, icon_path=webps[0] if webps else None, stat_path=jsons[0]))
            else:
                icon_path = None
                if is_map or is_evt:
                    for ext in ['.png', '.webp', '.jpg']:
                        if (item / f"{item.name}{ext}").exists():
                            icon_path = item / f"{item.name}{ext}"
                            break
        
                # Fall back to global system default assets if no custom path icon is detected
                if not icon_path or not icon_path.exists():
                    icon_name = 'monster' if item==self.monsters_dir else 'npc' if item==self.npcs_dir else 'combat' if item==self.combats_dir else 'map_icon' if is_map else 'event_icon'
                    icon_path = Path(f"./assets/icons/{icon_name}.png")
                    if not icon_path.exists():
                        for ext in ['.png', '.webp', '.jpg']:
                            if (item / f"{item.name}{ext}").exists(): 
                                icon_path = item / f"{item.name}{ext}"
                                break
                node = Node(name=item.name, path=item, is_entity=False, level=level, icon_path=icon_path if icon_path.exists() else None, is_open=str(item) in open_paths)
                if is_map or is_evt:
                    if (item / f"{item.name}.json").exists(): node.stat_path = item / f"{item.name}.json"
                node.children = self.build_tree_model(item, level + 1, open_paths); nodes.append(node)

        for key, act in [("monsters", "new_monster"), ("npcs", "new_npc"), ("combats", "new_combat"), ("spells", "new_spell")]:
            if path == getattr(self, f"{key}_dir"): nodes.append(Node(name="New", path=path, is_entity=False, level=level, action_type=act, icon_path=Path("./assets/icons/new.png")))
        if path == self.map_dir or self.map_dir in path.parents: nodes.append(Node(name="Add Location", path=path, is_entity=False, level=level, action_type="new_location", icon_path=Path("./assets/icons/new.png")))
        elif path == self.events_dir or self.events_dir in path.parents: nodes.append(Node(name="Add Event", path=path, is_entity=False, level=level, action_type="new_event", icon_path=Path("./assets/icons/new.png")))
        elif path == self.objects_dir: nodes.append(Node(name="Add Object", path=path, is_entity=False, level=level, action_type="new_object", icon_path=Path("./assets/icons/new.png")))
        return nodes

    def render_tree(self):
        for widget in self.tree_inner.winfo_children(): widget.destroy()
        self.image_cache.clear()

        def draw_node(node):
            row = tk.Frame(self.tree_inner, bg="#fae6c5")
            row.pack(fill=tk.X, pady=2)
            indent = node.level * 35 + 10
            is_act = bool(node.action_type)
            f = ("Georgia", 13, "italic") if is_act else ("Georgia", 15, "bold") if (not node.is_entity and not is_act) else ("Georgia", 13)
            
            if node.icon_path and node.icon_path.exists():
                try:
                    img = Image.open(node.icon_path).resize((44, 44), Image.Resampling.LANCZOS); photo = ImageTk.PhotoImage(img)
                    self.image_cache.append(photo); icon_lbl = tk.Label(row, image=photo, bg="#fae6c5", cursor="hand2")
                except: icon_lbl = tk.Label(row, text="?", width=4, height=2, bg="#444", fg="white", cursor="hand2")
            else: icon_lbl = tk.Label(row, text="+" if is_act else "E" if node.is_entity else "📁", width=4, height=2, bg="#444", fg="white", cursor="hand2")
            
            icon_lbl.pack(side=tk.LEFT, padx=(indent, 15), pady=6)

            # Component A: Pack right-aligned delete button first to guarantee screen real estate allocation
            del_btn = None
            if not is_act and node.name not in ["Map", "Events", "Objects", "Spells", "Monsters", "NPCs", "Combats"]:
                del_btn = tk.Label(row, text="X", bg="#fae6c5", fg="#ff4d4d", font=("Arial", 16, "bold"), cursor="hand2")
                del_btn.pack(side=tk.RIGHT, padx=15)
                del_btn.bind("<Enter>", lambda e: e.widget.configure(bg="#4a2222", fg="#ffffff"))
                del_btn.bind("<Leave>", lambda e: e.widget.configure(bg="#f5e6ce" if row.cget("bg") == "#f5e6ce" else "#fae6c5", fg="#ff4d4d"))
                def on_del(e, node=node):
                    if messagebox.askyesno("Confirm Delete", f"Delete permanently '{node.name}'?"):
                        try:
                            target_path = node.path.resolve()
                            if node.path.is_file():
                                if node.path.parent == self.spells_dir:
                                    try:
                                        self.spells_index = [s for s in self.spells_index if s["name"].lower() != json.load(open(node.stat_path, "r", encoding="utf-8")).get("name", "").lower()]
                                        json.dump(self.spells_index, open("spells.json", "w", encoding="utf-8"), indent=4); self.stat_viewer.set_spells_index(self.spells_index)
                                    except: pass
                                node.path.unlink()
                            else: shutil.rmtree(node.path)
                            self.sync_reciprocal_relations(delete_path_prefix=target_path)
                            self.refresh_tree_silent(); self.clear_viewer_and_tree()
                        except Exception as ex: messagebox.showerror("Error", f"Failed: {ex}")
                del_btn.bind("<Button-1>", on_del)

            # Component B: Left-aligned Text Label scales dynamically into remaining middle row fractions
            text_lbl = tk.Label(row, text=node.name, bg="#fae6c5", fg="black", font=f, cursor="hand2", anchor="w", justify=tk.LEFT)
            text_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=6)

            # Dynamic Configuration hook adapts label wrapping width on sidebar resize events
            def adjust_label_wrap(event, lbl=text_lbl, ind=indent):
                # Calculate available text space (Row width minus indentation padding and static item boundaries)
                avail_space = event.width - ind - 110
                if avail_space > 40:
                    lbl.configure(wraplength=avail_space)
            row.bind("<Configure>", adjust_label_wrap)

            row.bind("<Enter>", lambda e: (row.configure(bg="#f5e6ce"), icon_lbl.configure(bg="#f5e6ce"), text_lbl.configure(bg="#f5e6ce"), del_btn.configure(bg="#f5e6ce") if del_btn else None))
            row.bind("<Leave>", lambda e: (row.configure(bg="#fae6c5"), icon_lbl.configure(bg="#fae6c5"), text_lbl.configure(bg="#fae6c5"), del_btn.configure(bg="#fae6c5") if del_btn else None))
            
            def click_router(e):
                if node.action_type:
                    if node.action_type == "new_location": self.create_new_location(node.path)
                    elif node.action_type == "new_event": self.create_new_event(node.path)
                    elif node.action_type == "new_object": self.create_new_object()
                    elif node.action_type == "new_monster": self.show_search_panel(node.path)
                    elif node.action_type == "new_npc": self.create_new_npc(node.path)
                    elif node.action_type == "new_combat": self.create_new_combat(node.path)
                    elif node.action_type == "new_spell": self.create_new_spell()
                elif node.is_entity:
                    if node.path.parent == self.spells_dir: self.open_page(node, view_type="spell", stat_path=node.stat_path)
                    elif node.path.parent == self.objects_dir: self.open_page(node, view_type="object", stat_path=node.stat_path)
                    else: self.open_page(node, view_type="combat" if "Combats" in str(node.path) else "npc" if "NPCs" in str(node.path) else "monster", stat_path=node.stat_path)
                else:
                    node.is_open = not node.is_open
                    if node.is_open:
                        def collapse_siblings(tree_nodes):
                            for tn in tree_nodes:
                                if tn.path != node.path and tn.path.parent == node.path.parent:
                                    tn.is_open = False
                                if tn.children:
                                    collapse_siblings(tn.children)
                        collapse_siblings(getattr(self, 'nodes', []))
                    if not node.is_open and self.current_state and self.current_state.node.path and (self.current_state.node.path == node.path or node.path in self.current_state.node.path.parents):
                        self.open_page(Node(name="Campaign Map", path=self.map_dir, is_entity=False, level=0), view_type="root_folder")

                    p_res = node.path.resolve()
                    roots = [self.map_dir.resolve(), self.events_dir.resolve(), self.objects_dir.resolve(), 
                             self.spells_dir.resolve(), self.monsters_dir.resolve(), self.npcs_dir.resolve(), self.combats_dir.resolve()]
                    
                    if p_res in roots:
                        vt = "root_folder"
                    elif self.map_dir in node.path.parents:
                        vt = "location"
                    elif self.events_dir in node.path.parents:
                        vt = "event"
                    else:
                        # Safe generic viewtype designation for NPC/Combat/Monster/Spell directory branches
                        vt = "directory"
                        
                    self.open_page(node, view_type=vt); self.refresh_tree_silent()

            icon_lbl.bind("<Button-1>", lambda e: click_router(e) if node.name in ["Monsters", "NPCs", "Combats", "Map", "Spells", "Events", "Objects"] or node.path.parent == self.spells_dir else self.change_folder_icon(node))
            text_lbl.bind("<Button-1>", click_router); row.bind("<Button-1>", click_router)
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
        if not p.exists(): 
            messagebox.showinfo("Info", "No artwork found.")
            return
        ov = tk.Frame(self.right_frame, bg="black"); ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        img = Image.open(p); img.thumbnail((800, 800)); timg = ImageTk.PhotoImage(img)
        l = tk.Label(ov, image=timg, bg="black"); l.image = timg; l.pack(expand=True)
        tk.Button(ov, text="CLOSE", command=ov.destroy, bg="#58180d", fg="white", font=("Georgia", 14)).place(x=20, y=20)

    def create_new_event(self, p_path: Path):
        fn = simpledialog.askstring("Add Event", "Event name:")
        if not fn or not fn.strip(): return
        sn = "".join([c for c in fn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        nd = p_path / sn; nd.mkdir(parents=True, exist_ok=True)
        if Path("./assets/icons/event_icon.png").exists():
            try: Image.open("./assets/icons/event_icon.png").thumbnail((64,64)); Image.open("./assets/icons/event_icon.png").save(nd / f"{sn}.png", "PNG")
            except: pass
        self._set_node_open(p_path, True); self.refresh_tree_silent()
        
        # FIX: If the events graph layout workspace is open, refresh the canvas views instead of forcing a page jump
        if hasattr(self, 'events_graph_viewer') and self.events_graph_viewer.winfo_ismapped():
            self.events_graph_viewer.draw_graph()
        else:
            self.open_page(Node(name=fn, path=nd, is_entity=False, level=len(nd.relative_to(self.events_dir).parts)), view_type="event", is_reference_click=False)

    def on_location_link_clicked(self, name, category):
        if self.stat_viewer.edit_container.winfo_ismapped():
            self.current_state.view_type = "location_edit" if self.current_state.view_type == "location" else "event_edit"
        
        p = Path(name)
        if p.exists():
            p_str = str(p.resolve()).lower()
            if "monsters" in p_str or "npcs" in p_str:
                jsons = list(p.glob("*.json"))
                if jsons: self.open_page(Node(name=p.name, path=p, is_entity=True, level=1, stat_path=jsons[0]), view_type="monster" if "monsters" in p_str else "npc", stat_path=jsons[0], is_reference_click=True)
            elif "combats" in p_str:
                jsons = list(p.glob("*.json"))
                if jsons: self.open_page(Node(name=p.name, path=p, is_entity=True, level=1, stat_path=jsons[0]), view_type="combat", stat_path=jsons[0], is_reference_click=True)
            elif "objects" in p_str:
                self.open_page(Node(name=p.stem, path=p, is_entity=True, level=1, stat_path=p), view_type="object", stat_path=p, is_reference_click=True)
            elif "map" in p_str or "events" in p_str:
                sj = p / f"{p.name}.json"
                self.open_page(Node(name=p.name, path=p, is_entity=False, level=len(p.relative_to(self.events_dir if "events" in p_str else self.map_dir).parts), stat_path=sj if sj.exists() else None), view_type="event" if "events" in p_str else "location", is_reference_click=True)
            return

        if category in ["Monsters", "NPCs"]:
            jsons = list(((self.monsters_dir if category == "Monsters" else self.npcs_dir) / name).glob("*.json"))
            if jsons: self.open_page(Node(name=name, path=jsons[0].parent, is_entity=True, level=1, stat_path=jsons[0]), view_type="monster" if category == "Monsters" else "npc", stat_path=jsons[0], is_reference_click=True)
        elif category == "Combats":
            jsons = list((self.combats_dir / name).glob("*.json"))
            if jsons: self.open_page(Node(name=name, path=jsons[0].parent, is_entity=True, level=1, stat_path=jsons[0]), view_type="combat", stat_path=jsons[0], is_reference_click=True)
        elif category in ["Events", "Locations"]:
            tp = (self.events_dir if category == "Events" else self.map_dir) / name
            if not tp.exists():
                found = list((self.events_dir if category == "Events" else self.map_dir).rglob(name))
                if found and found[0].is_dir(): tp = found[0]
            if tp.exists() and tp.is_dir():
                sj = tp / f"{tp.name}.json"
                self.open_page(Node(name=tp.name, path=tp, is_entity=False, level=len(tp.relative_to(self.events_dir if category == "Events" else self.map_dir).parts), stat_path=sj if sj.exists() else None), view_type="event" if category == "Events" else "location", is_reference_click=True)
        elif category == "Objects":
            tp = self.objects_dir / f"{name}.json"
            if tp.exists(): self.open_page(Node(name=tp.stem, path=tp, is_entity=True, level=1, stat_path=tp), view_type="object", stat_path=tp, is_reference_click=True)

    def _find_dir_by_name(self, name, base_dir):
        target = base_dir / name
        if target.exists(): return target.resolve()
        found = list(base_dir.rglob(name))
        if found and found[0].is_dir(): return found[0].resolve()
        return target.resolve()

    def _open_campaign_node_edit(self, node, stat_path, data, is_location):
        def on_save(current_dir, updated_data):
            updated_data = self._serialize_refs(updated_data)
            with open(stat_path, "w", encoding="utf-8") as f: 
                json.dump(updated_data, f, indent=4)
            
            old = current_dir.name
            nn = updated_data.get("name", old)
            ns = "".join([c for c in nn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip() or "Unnamed"
            fd, fj = current_dir, stat_path
            old_path = current_dir.resolve()
            
            if ns != old:
                target = current_dir.parent / ns
                if target.exists() and target != current_dir: 
                    messagebox.showerror("Error", "An entry with that name already exists.")
                    return
                if (current_dir / f"{old}.json").exists(): 
                    (current_dir / f"{old}.json").rename(current_dir / f"{ns}.json")
                current_dir.rename(target)
                fd, fj = target, target / f"{ns}.json"
                
            new_path = fd.resolve()
            self.sync_reciprocal_relations(old_path_prefix=old_path, new_path_prefix=new_path, saved_path=fj)
            self.refresh_tree_silent()
            self.open_page(Node(name=nn, path=fd, is_entity=False, level=len(fd.relative_to(self.map_dir if is_location else self.events_dir).parts), stat_path=fj), view_type="location" if is_location else "event", is_reference_click=False)
        
        kw = {
            "data": data, 
            "location_dir" if is_location else "event_dir": stat_path.parent, 
            "save_callback": on_save, 
            "cancel_callback": lambda: self._show_current_state_view(),
            "add_new_monster_cb": lambda r: MonsterSearchDialog(self, self.monster_index, lambda meta: r(SyncRef(meta["name"], str(downloader.download_monster_data(meta, self.monsters_dir)[0].resolve())))),
            "add_existing_monster_cb": lambda r: EntitySelectionDialog(self, self.monsters_dir, "Monsters", lambda name: r(SyncRef(name, str((self.monsters_dir / name).resolve())))),
            "add_existing_npc_cb": lambda r: EntitySelectionDialog(self, self.npcs_dir, "NPCs", lambda name: r(SyncRef(name, str((self.npcs_dir / name).resolve())))),
            "add_existing_combat_cb": lambda r: EntitySelectionDialog(self, self.combats_dir, "Combats", lambda name: r(SyncRef(name, str((self.combats_dir / name).resolve())))),
            "add_existing_object_cb": lambda r: EntitySelectionDialog(self, self.objects_dir, "Objects", lambda name: r(SyncRef(name, str((self.objects_dir / f"{name}.json").resolve())))),
            # FIXED: Removed the trailing .resolve() syntax artifact from the end of this line
            "add_connection_cb": lambda r: EntitySelectionDialog(self, self.map_dir if is_location else self.events_dir, "Locations" if is_location else "Events", lambda name: r(SyncRef(name, str(self._find_dir_by_name(name, self.map_dir if is_location else self.events_dir)))))
        }
        if is_location: 
            kw["add_existing_event_cb"] = lambda r: EntitySelectionDialog(self, self.events_dir, "Events", lambda name: r(SyncRef(name, str(self._find_dir_by_name(name, self.events_dir)))))
        else: 
            kw["add_existing_location_cb"] = lambda r: EntitySelectionDialog(self, self.map_dir, "Locations", lambda name: r(SyncRef(name, str(self._find_dir_by_name(name, self.map_dir)))))
            
        getattr(self.stat_viewer, f"render_{'location' if is_location else 'event'}_edit_mode")(**kw)

    def open_location_edit(self, node, stat_path, data): self._open_campaign_node_edit(node, stat_path, data, True)
    def open_event_edit(self, node, stat_path, data): self._open_campaign_node_edit(node, stat_path, data, False)

    def _has_path_ref(self, data_list, target_path):
        target_path_norm = str(Path(target_path).resolve()).lower()
        if isinstance(data_list, list):
            for item in data_list:
                if isinstance(item, dict):
                    p_val = item.get("path", item.get("target", ""))
                    if isinstance(p_val, dict): p_val = p_val.get("path", p_val.get("target", ""))
                    if isinstance(p_val, str) and str(Path(p_val).resolve()).lower() == target_path_norm: return True
                elif isinstance(item, str):
                    if str(Path(item).resolve()).lower() == target_path_norm: return True
        return False

    def _add_path_ref(self, data_list, target_name, target_path):
        if not self._has_path_ref(data_list, target_path):
            data_list.append({"name": target_name, "path": str(Path(target_path).resolve())})
            return True
        return False

    def sync_reciprocal_relations(self, old_path_prefix=None, new_path_prefix=None, delete_path_prefix=None, saved_path=None):
        all_json_files = list(self.root_dir.rglob("*.json"))
        
        if delete_path_prefix:
            delete_str = str(Path(delete_path_prefix).resolve()).lower()
            for p in all_json_files:
                try:
                    with open(p, "r", encoding="utf-8") as f: file_data = json.load(f)
                    if self._recursive_delete_refs(file_data, delete_str):
                        with open(p, "w", encoding="utf-8") as f: json.dump(file_data, f, indent=4)
                except Exception as e: print(f"Error filtering references: {e}")

        if old_path_prefix and new_path_prefix:
            old_str = str(Path(old_path_prefix).resolve()).lower()
            new_str = str(Path(new_path_prefix).resolve())
            if old_str != new_str.lower():
                for p in all_json_files:
                    try:
                        with open(p, "r", encoding="utf-8") as f: file_data = json.load(f)
                        if self._recursive_update_refs(file_data, old_str, new_str):
                            with open(p, "w", encoding="utf-8") as f: json.dump(file_data, f, indent=4)
                    except Exception as e: print(f"Error mapping references: {e}")

        # RULE 1 PATHS SYMMETRY ENGINE: Mesh cross-relations bidirectionally
        loc_map, evt_map, creature_map, obj_map = {}, {}, {}, {}
        for p in self.map_dir.rglob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f: loc_map[str(p.parent.resolve()).lower()] = (p, json.load(f))
            except: pass
        for p in self.events_dir.rglob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f: evt_map[str(p.parent.resolve()).lower()] = (p, json.load(f))
            except: pass
        for p in list(self.monsters_dir.rglob("*.json")) + list(self.npcs_dir.rglob("*.json")):
            try:
                with open(p, "r", encoding="utf-8") as f: creature_map[str(p.parent.resolve()).lower()] = (p, json.load(f))
            except: pass
        for p in self.objects_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f: obj_map[str(p.resolve()).lower()] = (p, json.load(f))
            except: pass

        saved_norm = str(Path(saved_path).resolve()).lower() if saved_path else None
        if saved_norm:
            saved_p_obj = Path(saved_norm)
            f_key = str(saved_p_obj.parent.resolve()).lower()
            o_key = str(saved_p_obj.resolve()).lower()
            s_str = str(saved_p_obj).lower()

            if f_key in loc_map and "map" in s_str:
                l_file, l_data = loc_map[f_key]
                l_name = l_data.get("name", saved_p_obj.parent.name)
                for e_k, (e_file, e_data) in evt_map.items():
                    e_name = e_data.get("name", Path(e_file).parent.name)
                    if self._has_path_ref(l_data.get("events", []), e_k):
                        if self._add_path_ref(e_data.setdefault("locations", []), l_name, saved_p_obj.parent):
                            json.dump(e_data, open(e_file, "w", encoding="utf-8"), indent=4)
                    else:
                        orig = len(e_data.get("locations", []))
                        e_data["locations"] = [i for i in e_data.get("locations", []) if not (isinstance(i, dict) and str(Path(i.get("path", "")).resolve()).lower() == f_key or isinstance(i, str) and str(Path(i).resolve()).lower() == f_key)]
                        if len(e_data["locations"]) != orig: json.dump(e_data, open(e_file, "w", encoding="utf-8"), indent=4)

            elif f_key in evt_map and "events" in s_str:
                e_file, e_data = evt_map[f_key]
                e_name = e_data.get("name", saved_p_obj.parent.name)
                for l_k, (l_file, l_data) in loc_map.items():
                    l_name = l_data.get("name", Path(l_file).parent.name)
                    if self._has_path_ref(e_data.get("locations", []), l_k):
                        if self._add_path_ref(l_data.setdefault("events", []), e_name, saved_p_obj.parent):
                            json.dump(l_data, open(l_file, "w", encoding="utf-8"), indent=4)
                    else:
                        orig = len(l_data.get("events", []))
                        l_data["events"] = [i for i in l_data.get("events", []) if not (isinstance(i, dict) and str(Path(i.get("path", "")).resolve()).lower() == f_key or isinstance(i, str) and str(Path(i).resolve()).lower() == f_key)]
                        if len(l_data["events"]) != orig: json.dump(l_data, open(l_file, "w", encoding="utf-8"), indent=4)

            elif f_key in creature_map and ("monsters" in s_str or "npcs" in s_str):
                c_file, c_data = creature_map[f_key]
                c_name = c_data.get("name", saved_p_obj.parent.name)
                for o_k, (o_file, o_data) in obj_map.items():
                    o_name = o_data.get("name", Path(o_file).stem)
                    if self._has_path_ref(c_data.get("objects", []), o_k):
                        if self._add_path_ref(o_data.setdefault("owners", []), c_name, saved_p_obj.parent):
                            json.dump(o_data, open(o_file, "w", encoding="utf-8"), indent=4)
                    else:
                        orig = len(o_data.get("owners", []))
                        o_data["owners"] = [i for i in o_data.get("owners", []) if not (isinstance(i, dict) and str(Path(i.get("path", "")).resolve()).lower() == f_key or isinstance(i, str) and str(Path(i).resolve()).lower() == f_key)]
                        if len(o_data["owners"]) != orig: json.dump(o_data, open(o_file, "w", encoding="utf-8"), indent=4)

            elif o_key in obj_map and "objects" in s_str:
                o_file, o_data = obj_map[o_key]
                o_name = o_data.get("name", saved_p_obj.stem)
                for c_k, (c_file, c_data) in creature_map.items():
                    c_name = c_data.get("name", Path(c_file).parent.name)
                    if self._has_path_ref(o_data.get("owners", []), c_k):
                        if self._add_path_ref(c_data.setdefault("objects", []), o_name, saved_p_obj):
                            json.dump(c_data, open(c_file, "w", encoding="utf-8"), indent=4)
                    else:
                        orig = len(c_data.get("objects", []))
                        c_data["objects"] = [i for i in c_data.get("objects", []) if not (isinstance(i, dict) and str(Path(i.get("path", "")).resolve()).lower() == o_key or isinstance(i, str) and str(Path(i).resolve()).lower() == o_key)]
                        if len(c_data["objects"]) != orig: json.dump(c_data, open(c_file, "w", encoding="utf-8"), indent=4)
        else:
            for l_k, (l_file, l_data) in loc_map.items():
                l_name = l_data.get("name", Path(l_file).parent.name)
                for e_k, (e_file, e_data) in evt_map.items():
                    e_name = e_data.get("name", Path(e_file).parent.name)
                    if self._has_path_ref(e_data.get("locations", []), l_k) or self._has_path_ref(l_data.get("events", []), e_k):
                        if self._add_path_ref(l_data.setdefault("events", []), e_name, Path(e_file).parent): json.dump(l_data, open(l_file, "w", encoding="utf-8"), indent=4)
                        if self._add_path_ref(e_data.setdefault("locations", []), l_name, Path(l_file).parent): json.dump(e_data, open(e_file, "w", encoding="utf-8"), indent=4)
            for c_k, (c_file, c_data) in creature_map.items():
                c_name = c_data.get("name", Path(c_file).parent.name)
                for o_k, (o_file, o_data) in obj_map.items():
                    o_name = o_data.get("name", Path(o_file).stem)
                    if self._has_path_ref(o_data.get("owners", []), c_k) or self._has_path_ref(c_data.get("objects", []), o_k):
                        if self._add_path_ref(c_data.setdefault("objects", []), o_name, Path(o_file)): json.dump(c_data, open(c_file, "w", encoding="utf-8"), indent=4)
                        if self._add_path_ref(o_data.setdefault("owners", []), c_name, Path(c_file).parent): json.dump(o_data, open(o_file, "w", encoding="utf-8"), indent=4)

    def _recursive_delete_refs(self, data, delete_str):
        modified = False
        delete_match = delete_str.replace('\\', '/').lower()
        
        if isinstance(data, dict):
            new_dict = {}
            for k, v in list(data.items()):
                k_norm = k.replace('\\', '/').lower()
                # 1. Clear keys from graph_layout.json if the path matches the deleted prefix
                if k_norm == delete_match or k_norm.startswith(delete_match + "/"):
                    modified = True
                    continue  # Purges the entry entirely from the dictionary context
                
                if isinstance(v, str):
                    v_norm = v.replace('\\', '/').lower()
                    if v_norm == delete_match or v_norm.startswith(delete_match + "/"):
                        v = ""
                        modified = True
                elif isinstance(v, list):
                    new_list = []
                    for item in v:
                        if isinstance(item, str):
                            item_norm = item.replace('\\', '/').lower()
                            if item_norm == delete_match or item_norm.startswith(delete_match + "/"):
                                modified = True
                                continue
                        elif isinstance(item, dict):
                            if self._recursive_delete_refs(item, delete_str):
                                modified = True
                        new_list.append(item)
                    v = new_list
                elif isinstance(v, dict):
                    if self._recursive_delete_refs(v, delete_str):
                        modified = True
                new_dict[k] = v
                
            # Mutate dictionary in place to maintain memory reference trees intact
            data.clear()
            data.update(new_dict)
            
        return modified

    def _recursive_update_refs(self, data, old_str, new_str):
        modified = False
        old_match = old_str.replace('\\', '/').lower()
        
        if isinstance(data, dict):
            new_dict = {}
            for k, v in list(data.items()):
                new_k = k
                k_norm = k.replace('\\', '/').lower()
                
                # 1. Rename dictionary keys (fixes graph_layout.json ghost nodes automatically)
                if k_norm == old_match:
                    new_k = new_str
                    modified = True
                elif k_norm.startswith(old_match + "/"):
                    new_k = new_str + k[len(old_str):]
                    modified = True
                
                if isinstance(v, str):
                    v_norm = v.replace('\\', '/').lower()
                    if v_norm == old_match:
                        v = new_str
                        modified = True
                    elif v_norm.startswith(old_match + "/"):
                        v = new_str + v[len(old_str):]
                        modified = True
                        
                    # Maintain the automatic display name matching logic for references
                    if new_k in ["path", "target"] and modified:
                        p = Path(v)
                        data["name"] = p.stem if p.is_file() else p.name
                elif isinstance(v, list):
                    for i in range(len(v)):
                        if isinstance(v[i], str):
                            vi_norm = v[i].replace('\\', '/').lower()
                            if vi_norm == old_match:
                                v[i] = new_str; modified = True
                            elif vi_norm.startswith(old_match + "/"):
                                v[i] = new_str + v[i][len(old_str):]; modified = True
                        elif isinstance(v[i], dict):
                            if self._recursive_update_refs(v[i], old_str, new_str):
                                modified = True
                elif isinstance(v, dict):
                    if self._recursive_update_refs(v, old_str, new_str):
                        modified = True
                        
                new_dict[new_k] = v
                
            # Mutate dictionary in place to maintain memory reference trees intact
            data.clear()
            data.update(new_dict)
            
        return modified
    
    def create_new_object(self):
        fn = simpledialog.askstring("Add Object", "Object name:")
        if not fn or not fn.strip(): return
        sn = "".join([c for c in fn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        target = self.objects_dir / f"{sn}.json"
        if target.exists(): 
            messagebox.showerror("Error", "Already exists.")
            return
        json.dump({"name": fn, "description": "", "effect": "", "owners": [], "trait": [], "action": [], "spellcasting": []}, open(target, "w", encoding="utf-8"), indent=4)
        self.refresh_tree_silent()
        self.open_page(Node(name=fn, path=target, is_entity=True, level=1, stat_path=target), view_type="object", stat_path=target, is_reference_click=False)

    def open_object_edit(self, node, stat_path, data):
        def on_save(obj_file, updated_data):
            updated_data = self._serialize_refs(updated_data)
            with open(stat_path, "w", encoding="utf-8") as f:
                json.dump(updated_data, f, indent=4)
            old = stat_path.stem
            nn = updated_data.get("name", old)
            ns = "".join([c for c in nn if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip() or "Unnamed"
            fj = stat_path
            old_path = stat_path.resolve()
            
            if ns != old:
                target = stat_path.parent / f"{ns}.json"
                if target.exists(): 
                    messagebox.showerror("Error", "An item configuration named that already exists.")
                    return
                stat_path.rename(target)
                fj = target
                
            new_path = fj.resolve()
            self.sync_reciprocal_relations(old_path_prefix=old_path, new_path_prefix=new_path, saved_path=fj)
            self.refresh_tree_silent()
            self.open_page(Node(name=nn, path=fj, is_entity=True, level=1, stat_path=fj), view_type="object", stat_path=fj, is_reference_click=False)
            
        self.stat_viewer.render_object_edit_mode(data, stat_path, on_save, lambda: self._show_current_state_view(), lambda r: EntitySelectionDialog(self, self.npcs_dir, "NPCs", lambda name: r(SyncRef(name, str((self.npcs_dir / name).resolve())))))

    def toggle_music_panel_visibility(self):
        """Swaps the entire right pane view between the active entity sheet and the music manager panel."""
        if not hasattr(self, 'music_visible'):
            self.music_visible = False
            
        if self.music_visible:
            self.music_visible = False
            self.music_manager_ui.pack_forget()
            
            # Re-pack the core layout components to occupy full frame again
            self.nav_bar.pack(fill=tk.X, padx=10, pady=5)
            self.view_pane.pack(fill=tk.BOTH, expand=True)
            self._show_current_state_view()
        else:
            self.music_visible = True
            
            # Conceal the navbar and view pane to prevent overlapping background elements
            self.nav_bar.pack_forget()
            self.view_pane.pack_forget()
            
            # Pack the music manager to take up 100% of the right frame dimensions
            self.music_manager_ui.pack(fill=tk.BOTH, expand=True)
            if self.current_state and self.current_state.data:
                self.music_manager_ui.sync_with_active_page_context(self.current_state.data)
            else:
                self.music_manager_ui.sync_with_active_page_context(None)
        return "break"

    def _save_current_focused_sheet_data(self):
        """Automated file serialization method that securely writes modifications 

        to disk, handling both standalone sheets and directory root metadata configurations.
        """
        if not self.current_state: return
        
        target_path = None
        is_directory_meta = False

        # Identify where to write changes safely
        if self.current_state.stat_path:
            target_path = Path(self.current_state.stat_path)
        elif self.current_state.node and self.current_state.node.path:
            dir_check = Path(self.current_state.node.path)
            if dir_check.is_dir():
                target_path = dir_check / "folder_metadata.json"
                is_directory_meta = True

        if not target_path: return

        try:
            if is_directory_meta:
                # Direct serialization for folder configurations (no complex references present)
                serialized_data = self.current_state.data
            else:
                # Standard structural entity configuration cleaning sequence
                serialized_data = self._serialize_refs(copy.deepcopy(self.current_state.data))
                
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(serialized_data, f, indent=4)
        except Exception as e:
            print(f"Failed to record workspace entity music metadata updates: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--path", default="./data")
    args = parser.parse_args(); Path(args.path).mkdir(parents=True, exist_ok=True); Path("./utils").mkdir(exist_ok=True)
    DnDStatManager(args.path).mainloop()

if __name__ == "__main__":
    main()