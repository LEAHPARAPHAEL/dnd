import tkinter as tk

class CanvasSlider(tk.Frame):
    """A clean, modern Tkinter Canvas-based scale widget providing an aesthetic 

    round slider thumb handle that integrates with standard streaming polling logic.
    """
    def __init__(self, parent, from_=0, to=100, command=None, bg="#ebebeb", troughcolor="#d9ad6c", slidercolor="#4a90e2", height=24, **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        self.from_ = float(from_)
        self.to = float(to)
        self.command = command
        self.troughcolor = troughcolor
        self.slidercolor = slidercolor
        self.value = float(from_)
        
        self.canvas = tk.Canvas(self, height=height, bg=bg, highlightthickness=0)
        self.canvas.pack(fill=tk.X, expand=True)
        
        # Interactive mouse action routing handshakes
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._on_configure)
        
        self.padding = 12
        self.thumb_radius = 6
        
    def _on_configure(self, event):
        self.redraw()
        
    def redraw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= self.padding * 2:
            return
            
        track_y = h // 2
        # Draw sleek linear track trough
        self.canvas.create_line(self.padding, track_y, w - self.padding, track_y, fill=self.troughcolor, width=4, capstyle=tk.ROUND)
        
        val_range = self.to - self.from_
        pct = 0.0 if val_range == 0 else (self.value - self.from_) / val_range
            
        track_w = w - (self.padding * 2)
        thumb_x = self.padding + (pct * track_w)
        
        # Draw aesthetic round button thumb handle
        self.canvas.create_oval(
            thumb_x - self.thumb_radius, track_y - self.thumb_radius,
            thumb_x + self.thumb_radius, track_y + self.thumb_radius,
            fill=self.slidercolor, outline=self.slidercolor, activefill="#357abd"
        )
        
    def _get_val_from_x(self, x):
        w = self.canvas.winfo_width()
        track_w = w - (self.padding * 2)
        if track_w <= 0:
            return self.from_
        pct = (x - self.padding) / track_w
        pct = max(0.0, min(1.0, pct))
        return self.from_ + pct * (self.to - self.from_)
        
    def _on_press(self, event):
        self.event_generate("<ButtonPress-1>", x=event.x, y=event.y)

    def _on_click(self, event):
        self.value = self._get_val_from_x(event.x)
        self.redraw()
        if self.command:
            self.command(self.value)
            
    def _on_drag(self, event):
        self.value = self._get_val_from_x(event.x)
        self.redraw()
        if self.command:
            self.command(self.value)
            
    def _on_release(self, event):
        self.event_generate("<ButtonRelease-1>", x=event.x, y=event.y)
        
    def set(self, val):
        val = float(val)
        low, high = min(self.from_, self.to), max(self.from_, self.to)
        self.value = max(low, min(high, val))
        self.redraw()
        
    def get(self):
        return self.value
        
    def config(self, **kwargs):
        """Overwritten configuration dictionary mapping allows properties to be updated on-the-fly."""
        if 'to' in kwargs:
            self.to = float(kwargs.pop('to'))
        if 'from_' in kwargs:
            self.from_ = float(kwargs.pop('from_'))
        if 'command' in kwargs:
            self.command = kwargs.pop('command')
        self.redraw()

    def bind(self, sequence=None, func=None, add=None):
        """Overrides basic frame binding passes to forward interactive hooks to the canvas."""
        self.canvas.bind(sequence, func, add)
        return super().bind(sequence, func, add)