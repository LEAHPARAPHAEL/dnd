import tkinter as tk
from tkinter import ttk, messagebox
import random
import threading
import urllib.request
from pathlib import Path
from PIL import Image, ImageTk
import vlc
from music_service import YouTubeMusicService
from utils.slider import CanvasSlider # Import your round canvas slider

class MusicManagerPanel(tk.Frame):
    def __init__(self, parent, music_service: YouTubeMusicService, on_save_music_meta_cb, on_focus_link_click_cb, *args, **kwargs):
        super().__init__(parent, bg="#fae6c5", bd=1, relief=tk.SOLID, *args, **kwargs)
        self.service = music_service
        self.on_save_music_meta_cb = on_save_music_meta_cb 
        self.on_focus_link_click_cb = on_focus_link_click_cb 
        
        self.current_page_data = None
        self.current_playlist_id = None
        
        # Audio Engine State Data Models
        self.playback_queue = []
        self.current_playing_track = None
        self.is_playing = False
        self.is_repeat_enabled = False
        self.selected_playlist_track = None
        self.selected_queue_idx = None 
        self.loaded_tracks_cache = []
        
        # Active Focus Mode State Trackers
        self.focus_target_name = None
        self.focus_target_category = None
        
        # Marquee Text Rolling State Machine Properties
        self.marquee_offset = 0
        self.marquee_wait_ticks = 0

        # Artwork Persistent Object Cache (Prevents Garbage Collection)
        self.icon_image_cache = {}
        self.is_scrubbing = False

        # Preload Graphic UI Icons off disk safely into memory layout buckets
        self.ui_icons = {}
        self._preload_graphic_ui_components()

        # Live Player Audio Engine Configuration Subsystem Handshakes
        self.audio_player = vlc.MediaPlayer()
        self.audio_player.audio_set_volume(70)

        # Header Title Area
        header = tk.Frame(self, bg="#58180d", pady=6)
        header.pack(fill=tk.X, side=tk.TOP)
        tk.Label(header, text="CAMPAIGN AUDIO ENGINE", font=("Georgia", 11, "bold"), fg="white", bg="#58180d").pack(side=tk.LEFT, padx=10)

        # Main Split Frame Environment Area
        self.splitter = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg="#d9ad6c", sashwidth=4)
        self.splitter.pack(fill=tk.BOTH, expand=True, pady=2)

        # ------------------ LEFT SIDE: PLAYBACK QUEUE MANAGEMENT ------------------
        self.left_pane = tk.Frame(self.splitter, bg="#fdf1dc", padx=10, pady=10)
        
        # Focused Target Descriptor Link Area
        self.focus_link_frame = tk.Frame(self.left_pane, bg="#fdf1dc")
        self.focus_link_frame.pack(fill=tk.X, pady=(0, 5))
        tk.Label(self.focus_link_frame, text="🎯 Focused : ", font=("Georgia", 10, "bold"), bg="#fdf1dc", fg="#58180d").pack(side=tk.LEFT)
        
        self.hyperlink_lbl = tk.Label(self.focus_link_frame, text="None (Press 'F' on any page)", font=("Georgia", 10, "italic"), bg="#fdf1dc", fg="gray", cursor="hand2")
        self.hyperlink_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor="w")
        self.hyperlink_lbl.bind("<Button-1>", self._on_focus_link_label_clicked)

        tk.Label(self.left_pane, text="Live Playback Queue", font=("Georgia", 10, "bold"), bg="#fdf1dc", fg="#58180d").pack(anchor="w")
        
        # Unified Enlarged Horizontal Button Control Dashboard Panel
        q_btns = tk.Frame(self.left_pane, bg="#fdf1dc")
        q_btns.pack(fill=tk.X, pady=(5, 2))
        
        self.btn_play_pause = tk.Button(q_btns, image=self.ui_icons.get("play"), bg="#e0cbb0", bd=1, relief=tk.RAISED, command=self._toggle_play_pause)
        self.btn_play_pause.pack(side=tk.LEFT, padx=2)
        
        tk.Button(q_btns, image=self.ui_icons.get("skip"), bg="#e0cbb0", bd=1, relief=tk.RAISED, command=self._skip_track).pack(side=tk.LEFT, padx=2)
        tk.Button(q_btns, image=self.ui_icons.get("shuffle"), bg="#e0cbb0", bd=1, relief=tk.RAISED, command=self._shuffle_queue).pack(side=tk.LEFT, padx=2)
        
        self.btn_repeat = tk.Button(q_btns, image=self.ui_icons.get("loop_off"), bg="#e0cbb0", bd=1, relief=tk.RAISED, command=self._toggle_repeat)
        self.btn_repeat.pack(side=tk.LEFT, padx=2)
        
        tk.Button(q_btns, image=self.ui_icons.get("up"), bg="#e0cbb0", bd=1, relief=tk.RAISED, command=self._move_queue_up).pack(side=tk.LEFT, padx=2)
        tk.Button(q_btns, image=self.ui_icons.get("down"), bg="#e0cbb0", bd=1, relief=tk.RAISED, command=self._move_queue_down).pack(side=tk.LEFT, padx=2)
        tk.Button(q_btns, image=self.ui_icons.get("delete"), bg="#e0cbb0", bd=1, relief=tk.RAISED, command=self._remove_queue_item).pack(side=tk.LEFT, padx=2)
        
        # Clear button is packed next to controls
        tk.Button(q_btns, image=self.ui_icons.get("delete"), bg="#ff4d4d", bd=1, relief=tk.RAISED, command=self._clear_queue).pack(side=tk.LEFT, padx=12)

        # ====== NOW PLAYING MASTER DECK PANEL ======
        self.now_playing_frame = tk.Frame(self.left_pane, bg="#ebebeb", bd=1, relief=tk.SOLID, pady=10, padx=10)
        self.now_playing_frame.pack(fill=tk.X, pady=(5, 10))
        
        meta_row = tk.Frame(self.now_playing_frame, bg="#ebebeb")
        meta_row.pack(fill=tk.X)
        
        self.now_playing_icon = tk.Label(meta_row, text="📻", font=("Arial", 20), bg="#ebebeb")
        self.now_playing_icon.pack(side=tk.LEFT, padx=(0, 10))
        
        text_block = tk.Frame(meta_row, bg="#ebebeb")
        text_block.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.now_playing_title = tk.Label(text_block, text="Distributed Stack Queue Empty", font=("Georgia", 11, "bold"), bg="#ebebeb", fg="#7a200d", anchor="w", justify=tk.LEFT)
        self.now_playing_title.pack(fill=tk.X)
        self.now_playing_author = tk.Label(text_block, text="No active track loaded. Select entries from the playlist context.", font=("Georgia", 9, "italic"), bg="#ebebeb", fg="#555555", anchor="w", justify=tk.LEFT)
        self.now_playing_author.pack(fill=tk.X, pady=(2, 5))

        # UPGRADE: Aesthetic Round-Thumb Canvas Slider for Timeline Progress Tracking
        progress_row = tk.Frame(self.now_playing_frame, bg="#ebebeb")
        progress_row.pack(fill=tk.X, pady=5)
        
        self.progress_scale = CanvasSlider(progress_row, from_=0, to=100, bg="#ebebeb")
        self.progress_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.progress_scale.bind("<ButtonPress-1>", lambda e: setattr(self, 'is_scrubbing', True))
        self.progress_scale.bind("<ButtonRelease-1>", self._on_progress_scrub_end)

        self.time_lbl = tk.Label(progress_row, text="0:00 / 0:00", font=("Arial", 9, "bold"), bg="#ebebeb", fg="#444444")
        self.time_lbl.pack(side=tk.RIGHT)

        # UPGRADE: Aesthetic Round-Thumb Canvas Slider for Hardware Volume Modifiers
        volume_row = tk.Frame(self.now_playing_frame, bg="#ebebeb")
        volume_row.pack(fill=tk.X, pady=(5, 0))
        
        # FIX: Replaced the old static text label legend string with your volume image icon facing
        self.vol_icon_lbl = tk.Label(volume_row, image=self.ui_icons.get("volume"), bg="#ebebeb")
        self.vol_icon_lbl.pack(side=tk.LEFT, padx=(0, 5))
        
        self.volume_scale = CanvasSlider(volume_row, from_=0, to=100, bg="#ebebeb")
        self.volume_scale.set(70)
        self.volume_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.volume_scale.config(command=lambda val: self.audio_player.audio_set_volume(int(float(val))))

        # Uniform Column Headers for Queue List View
        q_headers = tk.Frame(self.left_pane, bg="#d9ad6c", bd=1, relief=tk.SOLID)
        q_headers.pack(fill=tk.X, pady=(0, 0))
        q_headers.grid_columnconfigure(0, weight=1, uniform="queue_col")
        q_headers.grid_columnconfigure(1, weight=1, uniform="queue_col")
        tk.Label(q_headers, text="Upcoming Title", font=("Georgia", 9, "bold"), bg="#d9ad6c", fg="black", anchor="w", padx=64, pady=4).grid(row=0, column=0, sticky="ew")
        tk.Label(q_headers, text="Author", font=("Georgia", 9, "bold"), bg="#d9ad6c", fg="black", anchor="w", padx=8, pady=4).grid(row=0, column=1, sticky="ew")

        # Scrollable Viewport Structure for upcoming track items
        self.queue_container = tk.Frame(self.left_pane, bg="#ffffff", bd=1, relief=tk.SOLID)
        self.queue_container.pack(fill=tk.BOTH, expand=True, pady=(2, 5))

        self.queue_canvas = tk.Canvas(self.queue_container, bg="#ffffff", highlightthickness=0)
        self.queue_scroll = ttk.Scrollbar(self.queue_container, orient="vertical", command=self.queue_canvas.yview)
        self.queue_canvas.configure(yscrollcommand=self.queue_scroll.set)
        self.queue_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.queue_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.queue_inner = tk.Frame(self.queue_canvas, bg="#ffffff")
        self.queue_window = self.queue_canvas.create_window((0, 0), window=self.queue_inner, anchor="nw")
        self.queue_inner.bind("<Configure>", lambda e: self.queue_canvas.configure(scrollregion=self.queue_canvas.bbox("all")))
        self.queue_canvas.bind("<Configure>", lambda e: self.queue_canvas.itemconfig(self.queue_window, width=e.width))

        # ------------------ RIGHT SIDE: PAGE PLAYLIST CONTROL ------------------
        self.right_pane = tk.Frame(self.splitter, bg="#fdf1dc", padx=10, pady=10)
        self.playlist_title_lbl = tk.Label(self.right_pane, text="Active Page Playlist: None", font=("Georgia", 10, "bold"), bg="#fdf1dc", fg="#58180d")
        self.playlist_title_lbl.pack(anchor="w")
        
        p_btns = tk.Frame(self.right_pane, bg="#fdf1dc")
        p_btns.pack(fill=tk.X, pady=(5, 2))
        
        self.btn_link = tk.Button(p_btns, image=self.ui_icons.get("link"), bg="#d9ad6c", bd=1, relief=tk.RAISED, command=self._link_existing_playlist)
        self.btn_link.pack(side=tk.LEFT, padx=2)
        
        tk.Button(p_btns, image=self.ui_icons.get("add_one"), bg="#dfa87a", bd=1, relief=tk.RAISED, command=self._add_selected_to_queue).pack(side=tk.LEFT, padx=2)
        tk.Button(p_btns, image=self.ui_icons.get("add_all"), bg="#dfa87a", bd=1, relief=tk.RAISED, command=self._add_all_to_queue).pack(side=tk.LEFT, padx=2)
        
        headers_frame = tk.Frame(self.right_pane, bg="#d9ad6c", bd=1, relief=tk.SOLID)
        headers_frame.pack(fill=tk.X, pady=(5, 0))
        headers_frame.grid_columnconfigure(0, weight=1, uniform="playlist_col")
        headers_frame.grid_columnconfigure(1, weight=1, uniform="playlist_col")
        tk.Label(headers_frame, text="Title", font=("Georgia", 9, "bold"), bg="#d9ad6c", fg="black", anchor="w", padx=64, pady=4).grid(row=0, column=0, sticky="ew")
        tk.Label(headers_frame, text="Author", font=("Georgia", 9, "bold"), bg="#d9ad6c", fg="black", anchor="w", padx=8, pady=4).grid(row=0, column=1, sticky="ew")

        self.playlist_container = tk.Frame(self.right_pane, bg="#ffffff", bd=1, relief=tk.SOLID)
        self.playlist_container.pack(fill=tk.BOTH, expand=True, pady=(2, 5))

        self.playlist_canvas = tk.Canvas(self.playlist_container, bg="#ffffff", highlightthickness=0)
        self.playlist_scroll = ttk.Scrollbar(self.playlist_container, orient="vertical", command=self.playlist_canvas.yview)
        self.playlist_canvas.configure(yscrollcommand=self.playlist_scroll.set)
        self.playlist_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.playlist_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.playlist_inner = tk.Frame(self.playlist_canvas, bg="#ffffff")
        self.playlist_window = self.playlist_canvas.create_window((0, 0), window=self.playlist_inner, anchor="nw")
        self.playlist_inner.bind("<Configure>", lambda e: self.playlist_canvas.configure(scrollregion=self.playlist_canvas.bbox("all")))
        self.playlist_canvas.bind("<Configure>", lambda e: self.playlist_canvas.itemconfig(self.playlist_window, width=e.width))

        # Safe fallback method restores main.py scrolling engine when leaving frame splits
        def _restore_global_scroll(e):
            master = self.winfo_toplevel()
            if hasattr(master, '_global_mouse_wheel'):
                master.bind_all("<MouseWheel>", master._global_mouse_wheel)
                master.bind_all("<Button-4>", master._global_mouse_wheel)
                master.bind_all("<Button-5>", master._global_mouse_wheel)

        self.playlist_container.bind("<Enter>", lambda e: self.playlist_canvas.bind_all("<MouseWheel>", lambda ev: self.playlist_canvas.yview_scroll(-1 * (ev.delta // 120), "units")))
        self.playlist_container.bind("<Leave>", _restore_global_scroll)
        self.queue_container.bind("<Enter>", lambda e: self.queue_canvas.bind_all("<MouseWheel>", lambda ev: self.queue_canvas.yview_scroll(-1 * (ev.delta // 120), "units")))
        self.queue_container.bind("<Leave>", _restore_global_scroll)
        
        self.splitter.add(self.left_pane, minsize=260, stretch="always")
        self.splitter.add(self.right_pane, minsize=260, stretch="always")
        
        self.after(250, self._start_live_audio_monitor)

    def _preload_graphic_ui_components(self):
        """Pre-buffers enlarged visual image asset facings directly from your local assets folder."""
        icon_mapping = {
            "play": "play.png", "pause": "pause.png", "skip": "skip.png", "shuffle": "shuffle.png",
            "loop_on": "infinity.png", "loop_off": "one.png", "up": "up.png", "down": "down.png",
            "delete": "cross.png", "link": "link.png", "add_one": "add_one.png", "add_all": "add_all.png",
            "volume": "volume.png" # Loaded from assets/ui/volume.png
        }
        for key, filename in icon_mapping.items():
            p = Path("assets/ui") / filename
            if p.exists():
                try:
                    img = Image.open(p).resize((24, 24), Image.Resampling.LANCZOS)
                    self.ui_icons[key] = ImageTk.PhotoImage(img)
                except Exception as e: print(f"Failed loading button image asset {filename}: {e}")

    def update_focus_link(self, name, category):
        self.focus_target_name = name
        self.focus_target_category = category
        if name:
            self.hyperlink_lbl.config(text=name, fg="#4a90e2", font=("Georgia", 10, "underline"))
        else:
            self.hyperlink_lbl.config(text="None (Press 'F' on any page)", fg="gray", font=("Georgia", 10, "italic"))

    def _on_focus_link_label_clicked(self, event):
        if self.focus_target_name and self.focus_target_category:
            self.on_focus_link_click_cb(self.focus_target_name, self.focus_target_category)

    def sync_with_active_page_context(self, page_data: dict):
        self.current_page_data = page_data
        self.selected_playlist_track = None
        self.loaded_tracks_cache = []
        for widget in self.playlist_inner.winfo_children(): widget.destroy()
            
        if not page_data:
            self.playlist_title_lbl.config(text="No active profile sheet focused.")
            return

        music_meta = page_data.get("music", {})
        self.current_playlist_id = music_meta.get("playlist_id")
        playlist_name = music_meta.get("playlist_name", "Untitled DND Collection")

        if self.current_playlist_id:
            self.playlist_title_lbl.config(text=f"Loading: {playlist_name}...")
            loading_lbl = tk.Label(self.playlist_inner, text="⏳ Loading tracks from YouTube Music...", font=("Georgia", 11, "italic"), bg="#ffffff", fg="gray")
            loading_lbl.pack(pady=30)
            threading.Thread(target=self._async_fetch_playlist_tracks, args=(self.current_playlist_id,), daemon=True).start()
        else:
            self.playlist_title_lbl.config(text="No Playlist linked to this entry.")

    def _async_fetch_playlist_tracks(self, playlist_id):
        try: tracks = self.service.get_playlist_tracks(playlist_id)
        except Exception as e: tracks = []
        self.loaded_tracks_cache = tracks
        if tracks: self._cache_playlist_thumbnails(tracks)
        self.after(0, self._refresh_playlist_view, playlist_id)

    def _refresh_playlist_view(self, playlist_id=None):
        if playlist_id and self.current_playlist_id != playlist_id: return 
        for widget in self.playlist_inner.winfo_children(): widget.destroy()
        if not self.current_page_data: return
            
        music_meta = self.current_page_data.get("music", {})
        playlist_name = music_meta.get("playlist_name", "Untitled DND Collection")
        self.playlist_title_lbl.config(text=f"Playlist: {playlist_name}")
        
        for idx, track in enumerate(self.loaded_tracks_cache):
            base_bg = "#f5e6ce" if idx % 2 == 0 else "#fae6c5"
            
            row_frame = tk.Frame(self.playlist_inner, bg=base_bg, bd=1, relief=tk.SOLID)
            row_frame.pack(fill=tk.X, pady=1, padx=2)
            
            icon_container = tk.Frame(row_frame, bg=base_bg, width=54, height=44)
            icon_container.pack_propagate(False)
            icon_container.pack(side=tk.LEFT, padx=2)
            
            v_id = track.get("videoId")
            icon_photo = self.icon_image_cache.get(v_id)
            if icon_photo:
                icon_lbl = tk.Label(icon_container, image=icon_photo, bg=base_bg)
            else:
                icon_lbl = tk.Label(icon_container, text="🎵", font=("Arial", 11), bg=base_bg, fg="#7a200d")
            icon_lbl.pack(expand=True)

            text_container = tk.Frame(row_frame, bg=base_bg)
            text_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            text_container.grid_columnconfigure(0, weight=1, uniform="playlist_col")
            text_container.grid_columnconfigure(1, weight=1, uniform="playlist_col")
            
            t_title = track.get("title", "Unknown Track")
            t_artist = ", ".join([a.get("name", "") for a in track.get("artists", [])]) if track.get("artists") else "Unknown Artist"
            
            t_lbl = tk.Label(text_container, text=t_title, bg=base_bg, fg="black", font=("Georgia", 10, "bold"), anchor="w", justify=tk.LEFT, padx=8, pady=6)
            t_lbl.grid(row=0, column=0, sticky="new")
            
            a_lbl = tk.Label(text_container, text=t_artist, bg=base_bg, fg="#444444", font=("Georgia", 10), anchor="w", justify=tk.LEFT, padx=8, pady=6)
            a_lbl.grid(row=0, column=1, sticky="new")
            
            def _make_click_handler(t_ref=track, f_ref=row_frame, b_bg=base_bg):
                return lambda event: self._select_playlist_row(t_ref, f_ref, b_bg)
                
            for widget in [row_frame, icon_container, icon_lbl, text_container, t_lbl, a_lbl]:
                widget.bind("<Button-1>", _make_click_handler())
            
            def _create_wrap_closure(l1=t_lbl, l2=a_lbl):
                return lambda e: [l1.config(wraplength=e.width // 2 - 20), l2.config(wraplength=e.width // 2 - 20)]
            text_container.bind("<Configure>", _create_wrap_closure())

    def _select_playlist_row(self, track, frame, baseline_bg):
        for row in self.playlist_inner.winfo_children():
            if hasattr(row, 'assigned_baseline_bg'):
                row.configure(bg=row.assigned_baseline_bg)
                self._set_widget_bg_recursive(row, row.assigned_baseline_bg, is_selected=False)
        frame.assigned_baseline_bg = baseline_bg
        self.selected_playlist_track = track
        frame.configure(bg="#4a90e2")
        self._set_widget_bg_recursive(frame, "#4a90e2", is_selected=True)

    def _set_widget_bg_recursive(self, widget, bg_color, is_selected=False):
        for child in widget.winfo_children():
            if isinstance(child, (tk.Frame, tk.Label)):
                child.configure(bg=bg_color)
                if isinstance(child, tk.Label):
                    if is_selected: child.configure(fg="white")
                    else:
                        font_str = str(child.cget("font"))
                        if "bold" in font_str: child.configure(fg="black")
                        elif "italic" in font_str: child.configure(fg="#555555")
                        else: child.configure(fg="#444444" if bg_color != "#ebebeb" else "#555555")
            self._set_widget_bg_recursive(child, bg_color, is_selected)

    def _refresh_queue_view(self):
        for widget in self.queue_inner.winfo_children(): widget.destroy()
        
        if self.current_playing_track:
            artists = ", ".join([a.get("name", "") for a in self.current_playing_track.get('artists', [])]) if self.current_playing_track.get('artists') else "Unknown Artist"
            self.now_playing_author.config(text=f"Author: {artists}", font=("Georgia", 10, "bold"), fg="black")
            
            v_id = self.current_playing_track.get("videoId")
            icon_photo = self.icon_image_cache.get(v_id)
            if icon_photo:
                self.now_playing_icon.config(image=icon_photo, text="", width=44, height=44)
                self.now_playing_icon.image = icon_photo
            else:
                self.now_playing_icon.config(image="", text="🎵", font=("Arial", 20), width=0, height=0)
        else:
            self.now_playing_title.config(text="Distributed Stack Queue Empty", fg="#7a200d")
            self.now_playing_author.config(text="No tracks loaded. Select files via list rows or hit 'Add All'.", font=("Georgia", 9, "italic"), fg="#555555")
            self.now_playing_icon.config(image="", text="📻", font=("Arial", 20), width=0, height=0)
            self.time_lbl.config(text="0:00 / 0:00")
            self.progress_scale.set(0)

        for idx, track in enumerate(self.playback_queue):
            bg_color = "#f5e6ce" if idx % 2 == 0 else "#fae6c5"
            
            row_frame = tk.Frame(self.queue_inner, bg=bg_color, bd=1, relief=tk.SOLID)
            row_frame.pack(fill=tk.X, pady=1, padx=2)
            
            icon_container = tk.Frame(row_frame, bg=bg_color, width=54, height=44)
            icon_container.pack_propagate(False)
            icon_container.pack(side=tk.LEFT, padx=2)
            
            v_id = track.get("videoId")
            icon_photo = self.icon_image_cache.get(v_id)
            if icon_photo:
                icon_lbl = tk.Label(icon_container, image=icon_photo, bg=bg_color)
            else:
                icon_lbl = tk.Label(icon_container, text="🎵", font=("Arial", 11), bg=bg_color, fg="#7a200d")
            icon_lbl.pack(expand=True)

            text_container = tk.Frame(row_frame, bg=bg_color)
            text_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            text_container.grid_columnconfigure(0, weight=1, uniform="queue_col")
            text_container.grid_columnconfigure(1, weight=1, uniform="queue_col")
            
            t_title = track.get("title", "Unknown Track")
            t_artist = ", ".join([a.get("name", "") for a in track.get("artists", [])]) if track.get("artists") else "Unknown Artist"
            
            t_lbl = tk.Label(text_container, text=t_title, bg=bg_color, fg="black", font=("Georgia", 10), anchor="w", justify=tk.LEFT, padx=8, pady=4)
            t_lbl.grid(row=0, column=0, sticky="nsew")
            
            a_lbl = tk.Label(text_container, text=t_artist, bg=bg_color, fg="#555555", font=("Georgia", 9), anchor="w", justify=tk.LEFT, padx=8, pady=4)
            a_lbl.grid(row=0, column=1, sticky="nsew")
            
            def _make_queue_click_handler(q_idx=idx, f_ref=row_frame, b_bg=bg_color):
                return lambda event: self._select_queue_row(q_idx, f_ref, b_bg)
                
            for widget in [row_frame, icon_container, icon_lbl, text_container, t_lbl, a_lbl]:
                widget.bind("<Button-1>", _make_queue_click_handler())
            
            def _create_wrap_closure(l1=t_lbl, l2=a_lbl):
                return lambda e: [l1.config(wraplength=e.width // 2 - 20), l2.config(wraplength=e.width // 2 - 20)]
            text_container.bind("<Configure>", _create_wrap_closure())
            
        if hasattr(self, 'selected_queue_idx') and self.selected_queue_idx is not None:
            children = self.queue_inner.winfo_children()
            if 0 <= self.selected_queue_idx < len(children):
                target_frame = children[self.selected_queue_idx]
                target_frame.configure(bg="#4a90e2")
                self._set_widget_bg_recursive(target_frame, "#4a90e2", is_selected=True)

    def _select_queue_row(self, idx, frame, baseline_bg):
        self.selected_queue_idx = idx
        for row in self.queue_inner.winfo_children():
            if hasattr(row, 'assigned_baseline_bg'):
                row.configure(bg=row.assigned_baseline_bg)
                self._set_widget_bg_recursive(row, row.assigned_baseline_bg, is_selected=False)
        frame.assigned_baseline_bg = baseline_bg
        frame.configure(bg="#4a90e2")
        self._set_widget_bg_recursive(frame, "#4a90e2", is_selected=True)

    def _move_queue_up(self):
        idx = getattr(self, 'selected_queue_idx', None)
        if idx is None or idx <= 0 or idx >= len(self.playback_queue): return
        self.playback_queue[idx], self.playback_queue[idx-1] = self.playback_queue[idx-1], self.playback_queue[idx]
        self.selected_queue_idx = idx - 1
        self._refresh_queue_view()

    def _move_queue_down(self):
        idx = getattr(self, 'selected_queue_idx', None)
        if idx is None or idx < 0 or idx >= len(self.playback_queue) - 1: return
        self.playback_queue[idx], self.playback_queue[idx+1] = self.playback_queue[idx+1], self.playback_queue[idx]
        self.selected_queue_idx = idx + 1
        self._refresh_queue_view()

    def _remove_queue_item(self):
        idx = getattr(self, 'selected_queue_idx', None)
        if idx is None or idx < 0 or idx >= len(self.playback_queue): return
        self.playback_queue.pop(idx)
        self.selected_queue_idx = None
        self._refresh_queue_view()

    def add_all_tracks_from_external_data(self, page_data):
        if not page_data: return
        music_meta = page_data.get("music", {})
        playlist_id = music_meta.get("playlist_id")
        if playlist_id:
            def fetch_job():
                try:
                    tracks = self.service.get_playlist_tracks(playlist_id)
                    if tracks:
                        self._cache_playlist_thumbnails(tracks)
                        self.after(0, self._append_batch_to_queue, tracks)
                except Exception as e: print(f"Hotkey track injection failed: {e}")
            threading.Thread(target=fetch_job, daemon=True).start()
            
    def _append_batch_to_queue(self, tracks):
        for t in tracks: self.playback_queue.append(t)
        self._refresh_queue_view()
        if not self.current_playing_track and self.is_playing: self._advance_queue_sequence()

    # ------------------ AUDIO RUNTIME CORE ENGINE ------------------
    def _toggle_play_pause(self):
        if not self.current_playing_track and self.playback_queue:
            self.current_playing_track = self.playback_queue.pop(0)

        if not self.current_playing_track:
            messagebox.showinfo("Queue Empty", "Please load tracks into the queue workspace first.")
            return

        self.is_playing = not self.is_playing
        self.btn_play_pause.config(image=self.ui_icons.get("pause") if self.is_playing else self.ui_icons.get("play"))
        
        if self.is_playing:
            if not self.audio_player.get_media():
                v_id = self.current_playing_track.get("videoId")
                stream_url = self.service.get_stream_url(v_id)
                if stream_url: 
                    self.audio_player.set_mrl(stream_url)
                    self.marquee_offset = 0
                    self.marquee_wait_ticks = 4
                else:
                    self.is_playing = False
                    self.btn_play_pause.config(image=self.ui_icons.get("play"))
                    return
            self.audio_player.play()
        else:
            self.audio_player.pause()
        self._refresh_queue_view()

    def _skip_track(self):
        self.audio_player.pause()
        self.audio_player.stop()
        self.audio_player.set_media(None)
        self._advance_queue_sequence()

    def _advance_queue_sequence(self):
        if self.current_playing_track and self.is_repeat_enabled:
            self.playback_queue.append(self.current_playing_track)
        if self.playback_queue:
            self.current_playing_track = self.playback_queue.pop(0)
            self.marquee_offset = 0
            self.marquee_wait_ticks = 4
            if self.is_playing:
                v_id = self.current_playing_track.get("videoId")
                stream_url = self.service.get_stream_url(v_id)
                if stream_url:
                    self.audio_player.set_mrl(stream_url)
                    self.audio_player.play()
                else: self._advance_queue_sequence()
        else:
            self.current_playing_track = None
            self.is_playing = False
            self.audio_player.pause()
            self.audio_player.stop()
            self.audio_player.set_media(None)
            self.btn_play_pause.config(image=self.ui_icons.get("play"))
        self._refresh_queue_view()

    def _on_progress_scrub_end(self, event):
        if self.current_playing_track and self.audio_player.get_length() > 0:
            target_seconds = self.progress_scale.get()
            self.audio_player.set_time(int(target_seconds * 1000))
        self.is_scrubbing = False

    def _start_live_audio_monitor(self):
        """Monitors media state, tracking natural advances, ticking marquees, and progress ticks."""
        if self.audio_player.get_media():
            if self.audio_player.get_state() == vlc.State.Ended:
                self._advance_queue_sequence()
            elif not self.is_scrubbing:
                total_ms = self.audio_player.get_length()
                current_ms = self.audio_player.get_time()
                if total_ms > 0:
                    total_sec = total_ms // 1000
                    current_sec = current_ms // 1000
                    self.progress_scale.config(to=total_sec)
                    self.progress_scale.set(current_sec)
                    self.time_lbl.config(text=f"{current_sec // 60}:{current_sec % 60:02d} / {total_sec // 60}:{total_sec % 60:02d}")

        # FIX: Expanded custom marquee tracking slices characters all the way to 45 columns, looping back continuously
        if self.current_playing_track:
            full_title = self.current_playing_track.get('title', 'Unknown Title')
            status_prefix = "▶ " if self.is_playing else "⏸ "
            
            if len(full_title) <= 45:
                self.now_playing_title.config(text=f"{status_prefix}{full_title}")
            else:
                if self.marquee_wait_ticks > 0:
                    self.marquee_wait_ticks -= 1
                else:
                    self.marquee_offset += 1
                    # Scroll all the way out, then snap cleanly right back to index 0
                    max_offset = len(full_title) - 45
                    if self.marquee_offset > max_offset:
                        self.marquee_offset = 0
                        self.marquee_wait_ticks = 8 # brief pause at beginning before re-scrolling
                
                visible_chunk = full_title[self.marquee_offset : self.marquee_offset + 45]
                self.now_playing_title.config(text=f"{status_prefix}{visible_chunk}")

        self.after(250, self._start_live_audio_monitor)

    def _cache_playlist_thumbnails(self, tracks):
        def download_job():
            cache_dir = Path("assets/music_cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            for track in tracks:
                v_id = track.get("videoId")
                if not v_id or (cache_dir / f"{v_id}.png").exists(): continue
                thumbs = track.get("thumbnails", [])
                if not thumbs or not thumbs[0].get("url"): continue
                try:
                    req = urllib.request.Request(thumbs[0]["url"], headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response:
                        img = Image.open(response)
                        w, h = img.size
                        if w > 0:
                            new_h = int(h * (44 / w))
                            img = img.resize((44, new_h), Image.Resampling.LANCZOS)
                        img.save(cache_dir / f"{v_id}.png", "PNG")
                except: pass
            self.after(0, self._load_cached_images_to_memory)
        threading.Thread(target=download_job, daemon=True).start()

    def _load_cached_images_to_memory(self):
        cache_dir = Path("assets/music_cache")
        if not cache_dir.exists(): return
        all_checks = self.loaded_tracks_cache + self.playback_queue + ([self.current_playing_track] if self.current_playing_track else [])
        for track in all_checks:
            v_id = track.get("videoId")
            if v_id and v_id not in self.icon_image_cache and (cache_dir / f"{v_id}.png").exists():
                try: self.icon_image_cache[v_id] = ImageTk.PhotoImage(Image.open(cache_dir / f"{v_id}.png"))
                except: pass
        self._refresh_playlist_view()
        self._refresh_queue_view()

    def _toggle_repeat(self):
        self.is_repeat_enabled = not self.is_repeat_enabled
        self.btn_repeat.config(image=self.ui_icons.get("loop_on") if self.is_repeat_enabled else self.ui_icons.get("loop_off"))

    def _shuffle_queue(self):
        random.shuffle(self.playback_queue)
        self._refresh_queue_view()

    def _add_selected_to_queue(self):
        if not self.selected_playlist_track:
            messagebox.showinfo("Selection Required", "Please click on a specific song from the playlist grid first.")
            return
        self.playback_queue.append(self.selected_playlist_track)
        self._refresh_queue_view()
        if not self.current_playing_track and self.is_playing: self._advance_queue_sequence()

    def _add_all_to_queue(self):
        if not self.loaded_tracks_cache: return
        for track in self.loaded_tracks_cache: self.playback_queue.append(track)
        self._refresh_queue_view()
        if not self.current_playing_track and self.is_playing: self._advance_queue_sequence()

    def _clear_queue_keep_current(self):
        self.playback_queue.clear()
        self.selected_queue_idx = None
        self._refresh_queue_view()

    def _clear_queue(self):
        self.audio_player.pause()
        self.audio_player.stop()
        self.audio_player.set_media(None)
        self.playback_queue.clear()
        self.current_playing_track = None
        self.is_playing = False
        self.selected_queue_idx = None
        self.btn_play_pause.config(image=self.ui_icons.get("play"))
        self._refresh_queue_view()

    # ------------------ SELECTION POPUP MODAL ------------------
    def _create_optimized_popup(self, button_widget, window_title):
        popup = tk.Toplevel(self)
        popup.title(window_title)
        popup.configure(bg="#fdf1dc")
        popup.withdraw()
        popup.transient(self.winfo_toplevel())
        popup.grab_set()

        self.update_idletasks()
        button_widget.update_idletasks()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        target_h = int(screen_h * 0.38)
        target_w = int(target_h * (3 / 5))

        btn_x = button_widget.winfo_rootx()
        btn_y = button_widget.winfo_rooty()
        btn_w = button_widget.winfo_width()
        btn_h = button_widget.winfo_height()
        mid_x = screen_w / 2
        mid_y = screen_h / 2

        if btn_x >= mid_x and btn_y < mid_y:
            pop_x = btn_x + btn_w - target_w
            pop_y = btn_y + btn_h
        elif btn_x < mid_x and btn_y < mid_y:
            pop_x = btn_x
            pop_y = btn_y + btn_h
        elif btn_x >= mid_x and btn_y >= mid_y:
            pop_x = btn_x + btn_w - target_w
            pop_y = btn_y - target_h
        else:
            pop_x = btn_x
            pop_y = btn_y - target_h

        popup.geometry(f"{target_w}x{target_h}+{pop_x}+{pop_y}")
        popup.deiconify()
        return popup

    def _link_existing_playlist(self):
        if self.current_page_data is None: return
        try: playlists = self.service.api.get_library_playlists()
        except Exception as e:
            if "invalid argument" in str(e).lower() or "400" in str(e):
                messagebox.showerror("YouTube Music OAuth Limitation", "YouTube returned an 'Invalid Argument (HTTP 400)' error.")
            else:
                messagebox.showerror("API Connection Error", f"Could not access YouTube Music Library: {e}")
            return

        if not playlists:
            messagebox.showinfo("Library Empty", "No playlists discovered inside your connected YouTube Music account library.")
            return

        selector = self._create_optimized_popup(self.btn_link, "Link Library Playlist")
        tk.Label(selector, text="Select Account Playlist to Link", font=("Georgia", 11, "bold"), bg="#fdf1dc", fg="#58180d", pady=8).pack()

        listbox = tk.Listbox(selector, bg="#fae6c5", font=("Arial", 10), bd=1, relief=tk.SOLID)
        listbox.pack(fill=tk.BOTH, expand=True, padx=12, pady=5)

        for pl in playlists:
            title = pl.get("title", "Untitled Playlist")
            track_count = pl.get("count", 0)
            listbox.insert(tk.END, f"🎵 {title} ({track_count} tracks)")

        def confirm_selection():
            selection = listbox.curselection()
            if not selection: return
            chosen_index = selection[0]
            selected_playlist = playlists[chosen_index]
            
            updated_meta = {
                "playlist_id": selected_playlist["playlistId"],
                "playlist_name": selected_playlist.get("title", "Linked Playlist Collection")
            }
            self.on_save_music_meta_cb(updated_meta)
            selector.destroy()

        tk.Button(selector, text="Link Selection", font=("Arial", 10, "bold"), bg="#2ecc71", fg="white", bd=1, relief=tk.RAISED, command=confirm_selection).pack(pady=12)