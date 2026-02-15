import tkinter as tk


class ShinyButton(tk.Canvas):
    def __init__(self, parent, text, command, width=220, height=38, colors=None):
        c = colors or {}
        parent_bg = c.get('SURFACE2', '#14203A')
        super().__init__(
            parent,
            width=width,
            height=height,
            highlightthickness=0,
            bd=0,
            relief=tk.FLAT,
            bg=parent_bg,
            cursor='hand2',
        )
        self._text = text
        self._command = command
        self._state = 'normal'
        self._hover = False
        self._press = False

        self._base = c.get('ACCENT_MINT', c.get('ACCENT', '#3CFFB3'))
        self._hover_color = '#59FFC3'
        self._press_color = c.get('MINT_DIM', '#1CCF88')
        self._disabled_color = '#2A5E4A'
        self._text_color = '#05120C'
        self._disabled_text = '#6E9B87'
        self._glow_inner = c.get('ACCENT_CYAN', '#00E5FF')
        self._glow_outer = '#1A6DA0'
        self._gloss = '#B8FFE3'
        self._stroke = '#235573'

        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<ButtonPress-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)
        self._draw()

    def set_state(self, state):
        self._state = state
        self.configure(cursor='hand2' if state == 'normal' else 'arrow')
        self._draw()

    def _round_rect(self, x1, y1, x2, y2, r, fill):
        self.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, style=tk.PIESLICE, fill=fill, outline=fill)
        self.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, style=tk.PIESLICE, fill=fill, outline=fill)
        self.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, style=tk.PIESLICE, fill=fill, outline=fill)
        self.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, style=tk.PIESLICE, fill=fill, outline=fill)
        self.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=fill)
        self.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=fill)

    def _round_rect_outline(self, x1, y1, x2, y2, r, color, width=1):
        self.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, style=tk.ARC, outline=color, width=width)
        self.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, style=tk.ARC, outline=color, width=width)
        self.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, style=tk.ARC, outline=color, width=width)
        self.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, style=tk.ARC, outline=color, width=width)
        self.create_line(x1 + r, y1, x2 - r, y1, fill=color, width=width)
        self.create_line(x1 + r, y2, x2 - r, y2, fill=color, width=width)
        self.create_line(x1, y1 + r, x1, y2 - r, fill=color, width=width)
        self.create_line(x2, y1 + r, x2, y2 - r, fill=color, width=width)

    def _draw(self):
        self.delete('all')
        w = int(self.cget('width'))
        h = int(self.cget('height'))
        radius = 10

        if self._state != 'normal':
            fill = self._disabled_color
            text_color = self._disabled_text
            glow_alpha = 0
        elif self._press:
            fill = self._press_color
            text_color = self._text_color
            glow_alpha = 1
        elif self._hover:
            fill = self._hover_color
            text_color = self._text_color
            glow_alpha = 2
        else:
            fill = self._base
            text_color = self._text_color
            glow_alpha = 1

        if glow_alpha >= 2:
            self._round_rect_outline(0, 0, w, h, radius + 1, self._glow_outer, width=1)
            self._round_rect_outline(2, 2, w - 2, h - 2, radius, self._glow_inner, width=1)
        elif glow_alpha == 1 and self._state == 'normal':
            self._round_rect_outline(2, 2, w - 2, h - 2, radius, self._stroke, width=1)

        self._round_rect(1, 1, w - 1, h - 1, radius, fill)
        # Gloss strip for subtle shiny effect
        gloss = self._gloss if self._state == 'normal' else '#4E7866'
        self._round_rect(3, 3, w - 3, int(h * 0.46), max(6, radius - 3), gloss)
        self._round_rect_outline(1, 1, w - 1, h - 1, radius, self._stroke, width=1)

        self.create_text(w // 2, h // 2 + 1, text=self._text, fill=text_color, font=('Segoe UI', 10))

    def _on_enter(self, _event):
        if self._state != 'normal':
            return
        self._hover = True
        self._draw()

    def _on_leave(self, _event):
        if self._state != 'normal':
            return
        self._hover = False
        self._press = False
        self._draw()

    def _on_press(self, _event):
        if self._state != 'normal':
            return
        self._press = True
        self._draw()

    def _on_release(self, event):
        if self._state != 'normal':
            return
        inside = 0 <= event.x <= int(self.cget('width')) and 0 <= event.y <= int(self.cget('height'))
        self._press = False
        self._draw()
        if inside and callable(self._command):
            self._command()


