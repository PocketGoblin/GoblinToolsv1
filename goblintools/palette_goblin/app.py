import colorsys
import json
import math
import random
from collections import Counter
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk
from goblintools.common import (
    BackgroundJobRunner,
    SECTION_GAP,
    ShortcutManager,
    SPACE_8,
    SPACE_12,
    SPACE_16,
    SURFACE_PAD,
    ToolShell,
    ToastNotifier,
    ShinyButton,
    ask_directory,
    ask_image_file,
    get_theme_tokens,
    tool_title,
    write_hex_lines,
    write_json_file,
)

MAX_CLUSTER_SAMPLES = 20000
MAX_UNIQUE_SCAN_PIXELS = 300000
HOARD_PATH = Path('.palette_goblin_hoard.json')
GRID_SIZE = 16
LOUPE_SCALE = 10
LOUPE_RADIUS = 8


def rgb_to_hex(rgb):
    return '#{:02X}{:02X}{:02X}'.format(*rgb)


def hex_to_rgb(hex_value):
    value = hex_value.strip().lstrip('#')
    if len(value) != 6:
        raise ValueError('HEX must be 6 characters')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def color_distance(c1, c2):
    return math.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2)


def merge_colors_with_frequency(colors, frequency_map, tolerance):
    if not colors:
        return []

    groups = []
    for color in colors:
        weight = int(frequency_map.get(color, 1))
        placed = False
        for group in groups:
            if color_distance(color, group['center']) <= tolerance:
                group['items'].append((color, weight))
                total_weight = sum(w for _, w in group['items'])
                r = sum(c[0] * w for c, w in group['items']) // total_weight
                g = sum(c[1] * w for c, w in group['items']) // total_weight
                b = sum(c[2] * w for c, w in group['items']) // total_weight
                group['center'] = (r, g, b)
                group['freq'] += weight
                placed = True
                break
        if not placed:
            groups.append({'center': color, 'items': [(color, weight)], 'freq': weight})

    return [(g['center'], g['freq']) for g in groups]


def sample_pixels(image, limit):
    pixels = list(image.getdata())
    if len(pixels) <= limit:
        return pixels
    return random.sample(pixels, limit)


def extract_unique_palette(image, count):
    total_pixels = image.size[0] * image.size[1]
    pixels = list(image.getdata())

    if total_pixels > MAX_UNIQUE_SCAN_PIXELS:
        pixels = random.sample(pixels, MAX_UNIQUE_SCAN_PIXELS)

    freq = Counter(pixels)
    common = freq.most_common(count)
    return [c for c, _ in common], {c: f for c, f in common}


def extract_dominant_palette(image, count):
    pixels = sample_pixels(image, MAX_CLUSTER_SAMPLES)
    if not pixels:
        return [], {}

    k = max(1, min(count, len(pixels)))
    centroids = random.sample(pixels, k)

    for _ in range(12):
        clusters = [[] for _ in range(k)]
        for px in pixels:
            distances = [color_distance(px, c) for c in centroids]
            idx = distances.index(min(distances))
            clusters[idx].append(px)

        new_centroids = []
        for i, cluster in enumerate(clusters):
            if not cluster:
                new_centroids.append(centroids[i])
                continue
            r = int(sum(p[0] for p in cluster) / len(cluster))
            g = int(sum(p[1] for p in cluster) / len(cluster))
            b = int(sum(p[2] for p in cluster) / len(cluster))
            new_centroids.append((r, g, b))

        if new_centroids == centroids:
            break
        centroids = new_centroids

    frequency_map = {}
    for px in pixels:
        distances = [color_distance(px, c) for c in centroids]
        idx = distances.index(min(distances))
        center = centroids[idx]
        frequency_map[center] = frequency_map.get(center, 0) + 1

    sorted_centers = sorted(frequency_map.items(), key=lambda item: item[1], reverse=True)
    sorted_centers = sorted_centers[:count]
    return [c for c, _ in sorted_centers], {c: f for c, f in sorted_centers}


def hsv_sort_key(color, mode):
    r, g, b = color
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    if mode == 'Hue':
        return (h, s, v)
    if mode == 'Brightness':
        return (v, s, h)
    if mode == 'Saturation':
        return (s, v, h)
    return (0, 0, 0)


class PaletteGoblinApp:
    def __init__(self, root, launcher_root=None):
        self.root = root
        self.launcher_root = launcher_root
        self.root.title(tool_title('Palette Goblin', 'palette_goblin'))
        self.root.geometry('1440x900')
        self.root.minsize(1180, 760)
        self.colors = get_theme_tokens()
        self.style = ttk.Style()
        self.root.protocol('WM_DELETE_WINDOW', self.back_to_launcher)

        self.image_path = None
        self.original_image = None
        self.display_image = None
        self.tk_image = None
        self.canvas_image_id = None

        self.zoom = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 20.0

        self.draw_x = 0
        self.draw_y = 0
        self.draw_w = 0
        self.draw_h = 0

        self.picked_colors_raw = []
        self.extracted_colors_raw = []
        self.picked_freq_raw = {}
        self.extracted_freq_raw = {}

        self.picked_groups = []
        self.extracted_groups = []

        self.last_sample_var = tk.StringVar(value='No pigment sampled yet')
        self.mode_var = tk.StringVar(value='Unique')
        self.n_colors_var = tk.IntVar(value=16)
        self.tolerance_var = tk.IntVar(value=0)
        self.sort_var = tk.StringVar(value='Frequency')
        self.grid_snap_var = tk.BooleanVar(value=False)

        self.toast = None
        self.hover_job = None
        self.hover_pos = None
        self.jobs = BackgroundJobRunner(self.root)
        self._busy = False
        self._busy_controls = []
        self._shortcut_tip = None
        self.shortcuts = ShortcutManager()
        self._dedup_req_id = 0
        self._dedup_after_id = None

        self._build_ui()
        self.load_hoard()
        self.apply_dedup()
        self.shortcuts.bind(self.root, '<Shift-Tab>', self._on_shortcut_toggle_help, description='Toggle shortcuts help')
        self.shortcuts.bind(self.root, '<ISO_Left_Tab>', self._on_shortcut_toggle_help)
        self.shortcuts.bind(self.root, '<Shift-I>', self._on_shortcut_toggle_inspector, description='Toggle inspector')
        self.shortcuts.bind(self.root, '<Shift-BackSpace>', self._on_shortcut_back_to_launcher, description='Back to launcher (confirm)')
        self.shell.set_dirty(False)

    def _build_ui(self):
        self.shell = ToolShell(
            self.root,
            title=tool_title('Palette Goblin', 'palette_goblin'),
            title_icon='PAL',
            tool_id='palette_goblin',
            colors=self.colors,
            on_back=self.back_to_launcher,
        )
        self.shell.set_rail_actions([
            {'id': 'open_image', 'label': 'Open Image', 'icon': '>', 'command': self.open_image},
            {'id': 'extract', 'label': 'Extract Palette', 'icon': '>', 'command': self.extract_palette},
        ])
        workspace = self.shell.main
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(workspace, bg=self.colors['canvas_bg'], highlightthickness=0, relief=tk.FLAT, cursor='crosshair')
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.canvas.bind('<Motion>', self.on_canvas_hover)
        self.canvas.bind('<Leave>', self.on_canvas_leave)
        self.canvas.bind('<Configure>', lambda _e: self.render_image())

        floating = tk.Frame(
            workspace,
            bg=self.colors['surface'],
            padx=SPACE_8,
            pady=SPACE_8,
            highlightthickness=0,
        )
        floating.place(x=SPACE_16, y=SPACE_16, anchor='nw')

        self.open_btn = ttk.Button(floating, text='Open', style='Ghost.TButton', command=self.open_image)
        self.open_btn.pack(side=tk.LEFT)
        self.zoom_out_btn = ttk.Button(floating, text='-', width=3, style='Ghost.TButton', command=lambda: self.adjust_zoom(0.9))
        self.zoom_out_btn.pack(side=tk.LEFT, padx=(SPACE_8, 0))
        self.zoom_in_btn = ttk.Button(floating, text='+', width=3, style='Ghost.TButton', command=lambda: self.adjust_zoom(1.1))
        self.zoom_in_btn.pack(side=tk.LEFT, padx=(SPACE_8 // 2, 0))
        self.reset_btn = ttk.Button(floating, text='Reset', style='Ghost.TButton', command=self.reset_zoom)
        self.reset_btn.pack(side=tk.LEFT, padx=(SPACE_8, 0))
        self.zoom_label = tk.Label(floating, text='100%', bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 9), padx=SPACE_8)
        self.zoom_label.pack(side=tk.LEFT, padx=(SPACE_8, SPACE_8 // 2))

        ttk.Checkbutton(
            floating,
            text='Grid 16',
            variable=self.grid_snap_var,
            style='Floating.TCheckbutton',
            command=self.on_grid_snap_toggle,
        ).pack(side=tk.LEFT, padx=(SPACE_8, 0))

        inspector = self.shell.sidebar
        inspector.columnconfigure(0, weight=1)
        inspector.rowconfigure(7, weight=1, minsize=220)

        ttk.Label(inspector, text='Status', style='Section.TLabel').grid(row=0, column=0, sticky='w')

        status_surface = tk.Frame(inspector, bg=self.colors['surface'], padx=SURFACE_PAD, pady=SURFACE_PAD, highlightthickness=0)
        status_surface.grid(row=1, column=0, sticky='ew', pady=(SPACE_8, SECTION_GAP))
        self.shortcut_hint = tk.Label(
            status_surface,
            text='Shortcuts ?',
            bg=self.colors['surface'],
            fg=self.colors['accent_cyan'],
            font=('Segoe UI', 8),
            cursor='hand2',
        )
        self.shortcut_hint.pack(anchor='e')
        self.shortcut_hint.bind('<Enter>', self._show_shortcuts_tooltip)
        self.shortcut_hint.bind('<Leave>', self._hide_shortcuts_tooltip)
        self.shortcut_hint.bind('<Button-1>', lambda _e: messagebox.showinfo('Palette Goblin Shortcuts', self._shortcut_text()))
        tk.Label(
            status_surface,
            textvariable=self.last_sample_var,
            bg=self.colors['surface'],
            fg=self.colors['muted'],
            font=('Segoe UI', 9),
            justify=tk.LEFT,
            wraplength=320,
            anchor='w',
        ).pack(anchor='w')
        self.busy_bar = ttk.Progressbar(status_surface, orient=tk.HORIZONTAL, mode='indeterminate')
        self.busy_bar.pack(fill=tk.X, pady=(8, 0))
        self.busy_bar.pack_forget()

        ttk.Label(inspector, text='Loupe', style='Section.TLabel').grid(row=2, column=0, sticky='w')
        loupe_frame = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        loupe_frame.grid(row=3, column=0, sticky='ew', pady=(SPACE_8, SECTION_GAP))

        loupe_size = (LOUPE_RADIUS * 2 + 1) * LOUPE_SCALE
        self.loupe_canvas = tk.Canvas(
            loupe_frame,
            width=loupe_size,
            height=loupe_size,
            bg=self.colors['canvas_bg'],
            highlightthickness=0,
        )
        self.loupe_canvas.pack(pady=(4, 2), anchor='w')
        self.loupe_label = tk.Label(loupe_frame, text='Hover image to inspect pixel', bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 9))
        self.loupe_label.pack(anchor='w')

        ttk.Label(inspector, text='Sampling', style='Section.TLabel').grid(row=4, column=0, sticky='w')
        extractor = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        extractor.grid(row=5, column=0, sticky='ew', pady=(SPACE_8, SECTION_GAP))
        extractor.columnconfigure(1, weight=1)

        tk.Label(extractor, text='Mode', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 10)).grid(row=0, column=0, sticky='w', padx=(0, 8))
        self.mode_combo = ttk.Combobox(extractor, textvariable=self.mode_var, values=('Unique', 'Dominant'), state='readonly', width=12)
        self.mode_combo.grid(row=0, column=1, sticky='w')

        tk.Label(extractor, text='N Colors', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 10)).grid(row=1, column=0, sticky='w', pady=(8, 0))
        self.n_spin = tk.Spinbox(
            extractor,
            from_=1,
            to=256,
            textvariable=self.n_colors_var,
            width=8,
            bg=self.colors['surface_alt'],
            fg=self.colors['text'],
            insertbackground=self.colors['text'],
            highlightthickness=1,
            highlightbackground=self.colors['surface_alt'],
            highlightcolor=self.colors.get('accent_cyan', self.colors['accent']),
            relief=tk.FLAT,
        )
        self.n_spin.grid(row=1, column=1, sticky='w', pady=(8, 0))

        tk.Label(extractor, text='Sort', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 10)).grid(row=2, column=0, sticky='w', pady=(8, 0))
        self.sort_combo = ttk.Combobox(extractor, textvariable=self.sort_var, values=('Frequency', 'Hue', 'Brightness', 'Saturation'), state='readonly', width=12)
        self.sort_combo.grid(row=2, column=1, sticky='w', pady=(8, 0))
        self.sort_combo.bind('<<ComboboxSelected>>', lambda _e: self.apply_dedup())

        self.extract_btn = ShinyButton(extractor, text='Extract Palette', command=self.extract_palette, width=236, height=40, colors=self.colors)
        self.extract_btn.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(12, 0))

        tolerance_frame = ttk.Frame(inspector, style='Inspector.TFrame')
        tolerance_frame.grid(row=6, column=0, sticky='ew')
        tolerance_frame.columnconfigure(0, weight=1)
        ttk.Label(tolerance_frame, text='Dedup Tolerance', style='Section.TLabel').grid(row=0, column=0, sticky='w')
        self.tolerance_label = ttk.Label(tolerance_frame, text='0', style='Muted.TLabel')
        self.tolerance_label.grid(row=0, column=1, sticky='e')
        self.tolerance_scale = ttk.Scale(tolerance_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.tolerance_var, command=self.on_tolerance_change)
        self.tolerance_scale.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(4, 0))

        palettes = ttk.Frame(inspector, style='Inspector.TFrame')
        palettes.grid(row=7, column=0, sticky='nsew', pady=(SECTION_GAP, 0))
        palettes.columnconfigure(0, weight=1)
        palettes.rowconfigure(1, weight=1)
        palettes.rowconfigure(3, weight=0)

        stack_header = ttk.Frame(palettes, style='Inspector.TFrame')
        stack_header.grid(row=0, column=0, sticky='ew')
        stack_header.columnconfigure(0, weight=1)
        ttk.Label(stack_header, text='Palette Stack', style='Section.TLabel').grid(row=0, column=0, sticky='w')
        self.copy_all_btn = ttk.Button(stack_header, text='Copy All', style='Ghost.TButton', command=self.copy_all_palette_hex)
        self.copy_all_btn.grid(row=0, column=1, sticky='e')

        self.stack_surface = ttk.Frame(palettes, style='Surface.TFrame', padding=6)
        self.stack_surface.grid(row=1, column=0, sticky='nsew', pady=(6, 10))
        palettes.rowconfigure(1, minsize=150)

        self.stack_canvas = tk.Canvas(
            self.stack_surface,
            bg=self.colors['surface'],
            highlightthickness=0,
            bd=0,
        )
        self.stack_scroll = ttk.Scrollbar(self.stack_surface, orient=tk.VERTICAL, command=self.stack_canvas.yview)
        self.stack_canvas.configure(yscrollcommand=self.stack_scroll.set)
        self.stack_canvas.grid(row=0, column=0, sticky='nsew')
        self.stack_scroll.grid(row=0, column=1, sticky='ns')
        self.stack_surface.columnconfigure(0, weight=1)
        self.stack_surface.rowconfigure(0, weight=1)

        self.stack_inner = tk.Frame(self.stack_canvas, bg=self.colors['surface'], highlightthickness=0, bd=0)
        self.stack_window = self.stack_canvas.create_window((0, 0), window=self.stack_inner, anchor='nw')
        self.stack_inner.bind('<Configure>', lambda _e: self.stack_canvas.configure(scrollregion=self.stack_canvas.bbox('all')))
        self.stack_canvas.bind('<Configure>', lambda e: self.stack_canvas.itemconfigure(self.stack_window, width=e.width))
        self._bind_stack_scroll()

        ttk.Label(palettes, text='Extracted Palette', style='Section.TLabel').grid(row=2, column=0, sticky='w')
        self.extracted_tray = ttk.Frame(palettes, style='Surface.TFrame', padding=8)
        self.extracted_tray.grid(row=3, column=0, sticky='nsew', pady=(6, 8))
        palettes.rowconfigure(3, minsize=72)

        export_bar = ttk.Frame(inspector, style='Surface.TFrame', padding=6)
        export_bar.grid(row=8, column=0, sticky='ew', pady=(12, 0))
        export_bar.columnconfigure(0, weight=1)
        export_bar.columnconfigure(1, weight=1)
        export_bar.columnconfigure(2, weight=1)
        self.export_json_btn = ttk.Button(export_bar, text='JSON', style='Ghost.TButton', command=self.export_json)
        self.export_json_btn.grid(row=0, column=0, sticky='ew', padx=(0, 4))
        self.export_txt_btn = ttk.Button(export_bar, text='TXT', style='Ghost.TButton', command=self.export_txt)
        self.export_txt_btn.grid(row=0, column=1, sticky='ew', padx=4)
        self.export_godot_btn = ttk.Button(export_bar, text='Godot', style='Ghost.TButton', command=self.export_godot_json)
        self.export_godot_btn.grid(row=0, column=2, sticky='ew', padx=(4, 0))

        for btn in (self.open_btn, self.zoom_out_btn, self.zoom_in_btn, self.reset_btn, self.export_json_btn, self.export_txt_btn, self.export_godot_btn):
            self._bind_ghost_feedback(btn)
        self._bind_ghost_feedback(self.copy_all_btn)
        self.extract_btn.configure(cursor='hand2')
        self._busy_controls = [
            self.open_btn,
            self.zoom_out_btn,
            self.zoom_in_btn,
            self.reset_btn,
            self.mode_combo,
            self.n_spin,
            self.sort_combo,
            self.tolerance_scale,
            self.export_json_btn,
            self.export_txt_btn,
            self.export_godot_btn,
            self.copy_all_btn,
        ]

        tk.Label(inspector, text='Use controls to extract and export your hoard.', bg=self.colors['inspector'], fg=self.colors['muted'], font=('Segoe UI', 9)).grid(row=9, column=0, sticky='w', pady=(8, 0))

        self.toast = ToastNotifier(self.root, bg=self.colors['toast'], fg=self.colors['text'])

    def _bind_ghost_feedback(self, button):
        state = {'job': None}

        def on_enter(_event):
            button.configure(cursor='hand2')
            if state['job'] is not None:
                self.root.after_cancel(state['job'])
                state['job'] = None
            button.configure(style='GhostHover.TButton')

        def on_leave(_event):
            if state['job'] is not None:
                self.root.after_cancel(state['job'])
                state['job'] = None
            button.configure(style='Ghost.TButton', cursor='')

        button.bind('<Enter>', on_enter, add='+')
        button.bind('<Leave>', on_leave, add='+')

    def set_status(self, text):
        if hasattr(self, 'shell'):
            self.shell.set_status(text)

    def show_toast(self, text):
        if self.toast is not None:
            self.toast.show(text, duration_ms=1600)

    def _shortcut_text(self) -> str:
        text = self.shortcuts.help_text()
        return text if text else 'No shortcuts registered yet.'

    def _show_shortcuts_tooltip(self, _event=None):
        self._hide_shortcuts_tooltip()
        x = self.shortcut_hint.winfo_rootx()
        y = self.shortcut_hint.winfo_rooty() + self.shortcut_hint.winfo_height() + SPACE_8
        tip = tk.Toplevel(self.root)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f'+{x}+{y}')
        frame = tk.Frame(
            tip,
            bg=self.colors['surface_alt'],
            padx=8,
            pady=6,
            highlightthickness=1,
            highlightbackground=self.colors['accent_cyan'],
        )
        frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            frame,
            text=self._shortcut_text(),
            bg=self.colors['surface_alt'],
            fg=self.colors['text'],
            font=('Segoe UI', 8),
            justify=tk.LEFT,
            anchor='w',
        ).pack(anchor='w')
        self._shortcut_tip = tip

    def _hide_shortcuts_tooltip(self, _event=None):
        if self._shortcut_tip is not None:
            try:
                self._shortcut_tip.destroy()
            except Exception:
                pass
            self._shortcut_tip = None

    def _on_shortcut_toggle_help(self, _event=None):
        if self._shortcut_tip is None:
            self._show_shortcuts_tooltip()
        else:
            self._hide_shortcuts_tooltip()
        return 'break'

    def _on_shortcut_toggle_inspector(self, _event=None):
        self.shell.toggle_inspector()
        return 'break'

    def _on_shortcut_back_to_launcher(self, _event=None):
        if self.shell.confirm._navigate_away():
            self.back_to_launcher()
        return 'break'

    def _set_widget_state(self, widget, enabled):
        state = 'normal' if enabled else 'disabled'
        if isinstance(widget, ShinyButton):
            widget.set_state(state)
            return
        try:
            widget.configure(state=state)
        except Exception:
            pass

    def _set_busy(self, busy, status=None):
        self._busy = busy
        for widget in self._busy_controls:
            self._set_widget_state(widget, enabled=not busy)
        self._set_widget_state(self.extract_btn, enabled=not busy)
        self.root.configure(cursor='watch' if busy else '')
        if busy:
            self.busy_bar.pack(fill=tk.X, pady=(8, 0))
            self.busy_bar.start(10)
        else:
            self.busy_bar.stop()
            self.busy_bar.pack_forget()
        if status:
            self.set_status(status)

    def _handle_job_error(self, context, result):
        if result.tb:
            print(result.tb)
        self._set_busy(False)
        self.set_status(f'{context} failed')
        messagebox.showerror('Operation Error', f'{context} failed.\n{result.error}')

    def on_grid_snap_toggle(self):
        if self.grid_snap_var.get():
            self.set_status('Goblin aligned sampling to 16x16 grid')
        else:
            self.set_status('Goblin returned to freehand sampling')
        self.shell.set_dirty(True)

    def back_to_launcher(self):
        self._hide_shortcuts_tooltip()
        self.shortcuts.clear()
        try:
            self.root.destroy()
        finally:
            if self.launcher_root is not None and self.launcher_root.winfo_exists():
                self.launcher_root.deiconify()
                self.launcher_root.lift()
                try:
                    self.launcher_root.focus_force()
                except Exception:
                    pass

    def open_image(self):
        if self._busy:
            return
        file_path = ask_image_file(title='Open Image')
        if not file_path:
            return

        try:
            image = Image.open(file_path).convert('RGB')
        except Exception as exc:
            messagebox.showerror('Error', f'Unable to open image:\n{exc}')
            return

        self.image_path = file_path
        self.original_image = image
        self.zoom = 1.0
        self.zoom_label.configure(text='100%')

        self.extracted_colors_raw = []
        self.extracted_freq_raw = {}
        self.apply_dedup()

        self.render_image()
        self.shell.set_dirty(True)
        self.set_status(f'Goblin opened {Path(file_path).name} ({image.width}x{image.height})')
    def render_image(self):
        if self.original_image is None:
            self.canvas.delete('all')
            return

        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        rw = max(1, int(self.original_image.width * self.zoom))
        rh = max(1, int(self.original_image.height * self.zoom))

        self.display_image = self.original_image.resize((rw, rh), Image.NEAREST)
        self.tk_image = ImageTk.PhotoImage(self.display_image)

        self.canvas.delete('all')
        self.draw_x = max((cw - rw) // 2, 0)
        self.draw_y = max((ch - rh) // 2, 0)
        self.draw_w = rw
        self.draw_h = rh
        self.canvas_image_id = self.canvas.create_image(self.draw_x, self.draw_y, anchor=tk.NW, image=self.tk_image)

    def adjust_zoom(self, factor):
        if self.original_image is None:
            return
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
        self.zoom_label.configure(text=f'{int(self.zoom * 100)}%')
        self.render_image()

    def reset_zoom(self):
        if self.original_image is None:
            return
        self.zoom = 1.0
        self.zoom_label.configure(text='100%')
        self.render_image()

    def canvas_to_image_coords(self, x, y):
        if self.original_image is None:
            return None
        if not (self.draw_x <= x < self.draw_x + self.draw_w and self.draw_y <= y < self.draw_y + self.draw_h):
            return None

        ox = int((x - self.draw_x) / self.zoom)
        oy = int((y - self.draw_y) / self.zoom)
        if self.grid_snap_var.get():
            ox = (ox // GRID_SIZE) * GRID_SIZE
            oy = (oy // GRID_SIZE) * GRID_SIZE

        ox = max(0, min(self.original_image.width - 1, ox))
        oy = max(0, min(self.original_image.height - 1, oy))
        return ox, oy

    def on_canvas_hover(self, event):
        self.hover_pos = self.canvas_to_image_coords(event.x, event.y)
        if self.hover_job is None:
            self.hover_job = self.root.after(16, self._consume_hover)

    def _consume_hover(self):
        self.hover_job = None
        if self.hover_pos is None:
            self.on_canvas_leave()
            return
        self.render_loupe(*self.hover_pos)

    def on_canvas_leave(self, _event=None):
        self.hover_pos = None
        self.loupe_canvas.delete('all')
        self.loupe_label.configure(text='Hover image to inspect pixel')

    def render_loupe(self, ox, oy):
        if self.original_image is None:
            return

        patch_size = LOUPE_RADIUS * 2 + 1
        patch = Image.new('RGB', (patch_size, patch_size), (0, 0, 0))

        for py in range(patch_size):
            for px in range(patch_size):
                sx = max(0, min(self.original_image.width - 1, ox + px - LOUPE_RADIUS))
                sy = max(0, min(self.original_image.height - 1, oy + py - LOUPE_RADIUS))
                patch.putpixel((px, py), self.original_image.getpixel((sx, sy)))

        zoomed = patch.resize((patch_size * LOUPE_SCALE, patch_size * LOUPE_SCALE), Image.NEAREST)
        self.loupe_photo = ImageTk.PhotoImage(zoomed)

        self.loupe_canvas.delete('all')
        self.loupe_canvas.create_image(0, 0, anchor=tk.NW, image=self.loupe_photo)
        center = LOUPE_RADIUS * LOUPE_SCALE
        self.loupe_canvas.create_rectangle(center, center, center + LOUPE_SCALE, center + LOUPE_SCALE, outline='#B7C2D3', width=2)

        rgb = self.original_image.getpixel((ox, oy))
        self.loupe_label.configure(text=f"{rgb_to_hex(rgb)}  RGB{rgb}  @({ox},{oy})")

    def on_canvas_click(self, event):
        if self.original_image is None:
            return

        pos = self.canvas_to_image_coords(event.x, event.y)
        if pos is None:
            return

        ox, oy = pos
        rgb = self.original_image.getpixel((ox, oy))
        hex_value = rgb_to_hex(rgb)
        self.last_sample_var.set(f'Sampled {hex_value} | RGB{rgb} @ ({ox}, {oy})')

        self.picked_colors_raw.append(rgb)
        self.picked_freq_raw = dict(Counter(self.picked_colors_raw))
        self.save_hoard()
        self.apply_dedup()

        self.copy_to_clipboard(hex_value)
        self.show_toast(f'Copied {hex_value}')
        self.shell.set_dirty(True)
        self.set_status(f'Goblin pocketed {hex_value}')

    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()

    def on_tolerance_change(self, _event=None):
        value = int(self.tolerance_var.get())
        self.tolerance_label.configure(text=str(value))
        self.apply_dedup()

    def apply_dedup(self, animate=False, on_done=None):
        if self._dedup_after_id is not None:
            self.root.after_cancel(self._dedup_after_id)
            self._dedup_after_id = None
        self._dedup_after_id = self.root.after(60, lambda: self._queue_dedup(animate=animate, on_done=on_done))

    def _queue_dedup(self, animate=False, on_done=None):
        self._dedup_after_id = None
        tolerance = int(self.tolerance_var.get())
        sort_mode = self.sort_var.get()
        picked_freq = dict(self.picked_freq_raw or dict(Counter(self.picked_colors_raw)))
        extracted_freq = dict(self.extracted_freq_raw or {})
        extracted_colors = list(self.extracted_colors_raw or [])

        self._dedup_req_id += 1
        req_id = self._dedup_req_id
        self.jobs.submit(
            self._dedup_worker,
            lambda result: self._on_dedup_done(req_id, result, animate, on_done),
            tolerance,
            sort_mode,
            picked_freq,
            extracted_colors,
            extracted_freq,
        )

    def _dedup_worker(self, tolerance, sort_mode, picked_freq, extracted_colors, extracted_freq, progress=None):
        picked = merge_colors_with_frequency(list(picked_freq.keys()), picked_freq, tolerance)
        extracted = merge_colors_with_frequency(extracted_colors, extracted_freq, tolerance)
        if sort_mode == 'Frequency':
            picked_sorted = sorted(picked, key=lambda item: item[1], reverse=True)
            extracted_sorted = sorted(extracted, key=lambda item: item[1], reverse=True)
        else:
            picked_sorted = sorted(picked, key=lambda item: hsv_sort_key(item[0], sort_mode))
            extracted_sorted = sorted(extracted, key=lambda item: hsv_sort_key(item[0], sort_mode))
        return {'picked': picked_sorted, 'extracted': extracted_sorted}

    def _on_dedup_done(self, req_id, result, animate, on_done=None):
        if req_id != self._dedup_req_id:
            if callable(on_done):
                on_done()
            return
        if not result.ok:
            if result.tb:
                print(result.tb)
            self.set_status('Dedup update failed')
            if callable(on_done):
                on_done()
            return

        payload = result.value or {}
        self.picked_groups = payload.get('picked', [])
        self.extracted_groups = payload.get('extracted', [])
        self.render_palette_stack(self.extracted_groups)
        self.render_swatch_tray(self.extracted_tray, self.extracted_groups, animate=animate, empty_text='Goblin awaits shiny pigments.')
        if callable(on_done):
            on_done()

    def render_palette_stack(self, color_groups):
        for child in self.stack_inner.winfo_children():
            child.destroy()

        if not color_groups:
            tk.Label(
                self.stack_inner,
                text='Goblin awaits shiny pigments.',
                bg=self.colors['surface'],
                fg=self.colors['muted'],
                font=('Segoe UI', 9),
                anchor='w',
                justify=tk.LEFT,
            ).grid(row=0, column=0, sticky='w', padx=8, pady=8)
            return

        for i, (color, _freq) in enumerate(color_groups):
            hex_value = rgb_to_hex(color)
            row = tk.Frame(self.stack_inner, bg=self.colors['surface'], padx=8, pady=6, highlightthickness=0, bd=0)
            row.grid(row=i, column=0, sticky='ew', pady=(0, 4))
            row.columnconfigure(1, weight=1)

            swatch = tk.Canvas(row, width=16, height=16, bg=self.colors['surface'], highlightthickness=0, bd=0)
            swatch.create_rectangle(1, 1, 15, 15, fill=hex_value, outline=self.colors['shadow'])
            swatch.grid(row=0, column=0, sticky='w', padx=(0, 8))

            label = tk.Label(row, text=hex_value, bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9))
            label.grid(row=0, column=1, sticky='w')

            btn = ttk.Button(row, text='copy', style='Ghost.TButton', command=lambda v=hex_value, r=row: self.copy_palette_hex(v, r), width=5)
            btn.grid(row=0, column=2, sticky='e')
            self._bind_ghost_feedback(btn)

            def on_copy(_event, value=hex_value, row_ref=row):
                self.copy_palette_hex(value, row_ref)

            for widget in (row, swatch, label):
                widget.configure(cursor='hand2')
                widget.bind('<Button-1>', on_copy)
            for widget in (row, swatch, label, btn):
                widget.bind('<MouseWheel>', self._on_stack_mousewheel)
                widget.bind('<Button-4>', self._on_stack_mousewheel)
                widget.bind('<Button-5>', self._on_stack_mousewheel)

        self.stack_inner.update_idletasks()
        self.stack_canvas.configure(scrollregion=self.stack_canvas.bbox('all'))

    def copy_palette_hex(self, hex_value, row=None):
        self.copy_to_clipboard(hex_value)
        if row is not None:
            row.configure(bg=self.colors['surface_alt'])
            self.root.after(130, lambda r=row: r.configure(bg=self.colors['surface']) if r.winfo_exists() else None)
        self.set_status(f'Copied {hex_value}')
        self.show_toast(f'Copied {hex_value}')

    def copy_all_palette_hex(self):
        if not self.extracted_groups:
            self.set_status('No extracted palette to copy')
            return
        text = '\n'.join(rgb_to_hex(c) for c, _ in self.extracted_groups)
        self.copy_to_clipboard(text)
        self.set_status(f'Copied {len(self.extracted_groups)} hex codes')
        self.show_toast('Copied palette stack')

    def _bind_stack_scroll(self):
        for widget in (self.stack_canvas, self.stack_inner):
            widget.bind('<MouseWheel>', self._on_stack_mousewheel)
            widget.bind('<Button-4>', self._on_stack_mousewheel)
            widget.bind('<Button-5>', self._on_stack_mousewheel)

    def _on_stack_mousewheel(self, event):
        if not self.stack_canvas.winfo_exists():
            return
        if event.num == 4:
            delta = -1
        elif event.num == 5:
            delta = 1
        else:
            delta = -1 if event.delta > 0 else 1
        self.stack_canvas.yview_scroll(delta, 'units')
        return 'break'

    def extract_palette(self):
        if self.original_image is None:
            messagebox.showinfo('No Image', 'Open an image first.')
            return
        if self._busy:
            return

        try:
            n_colors = max(1, int(self.n_colors_var.get()))
        except Exception:
            messagebox.showerror('Invalid Input', 'N Colors must be an integer.')
            return

        mode = self.mode_var.get()
        image = self.original_image.copy()
        self._set_busy(True, status='Goblin sorting pigments...')
        self.jobs.submit(self._extract_palette_worker, self._on_extract_done, image, mode, n_colors)

    def _extract_palette_worker(self, image, mode, n_colors, progress=None):
        if mode == 'Unique':
            colors, freq = extract_unique_palette(image, n_colors)
        else:
            colors, freq = extract_dominant_palette(image, n_colors)
        return {'colors': colors, 'freq': freq}

    def _on_extract_done(self, result):
        try:
            if not result.ok:
                if result.tb:
                    print(result.tb)
                self.set_status('Palette extraction failed')
                messagebox.showerror('Operation Error', f'Palette extraction failed.\n{result.error}')
                return

            payload = result.value or {}
            self.extracted_colors_raw = payload.get('colors', [])
            self.extracted_freq_raw = payload.get('freq', {})

            def finish_extract():
                self.shell.set_dirty(True)
                self.set_status(f'Palette forged with {len(self.extracted_groups)} tones')
                self.show_toast('Palette extracted')

            self.apply_dedup(
                animate=True,
                on_done=finish_extract,
            )
        finally:
            self._set_busy(False)

    def render_swatch_tray(self, tray, color_groups, animate=False, empty_text='Goblin awaits shiny pigments.'):
        for child in tray.winfo_children():
            child.destroy()

        if not color_groups:
            tk.Label(
                tray,
                text=empty_text,
                bg=self.colors['surface'],
                fg=self.colors['muted'],
                font=('Segoe UI', 9),
            ).pack(anchor='w', pady=4)
            return

        for i, (color, freq) in enumerate(color_groups):
            hex_value = rgb_to_hex(color)
            card = tk.Frame(
                tray,
                bg=self.colors['surface'],
                padx=10,
                pady=8,
                highlightthickness=0,
            )
            card.grid(row=i, column=0, sticky='ew', pady=4)

            sw = tk.Canvas(card, width=32, height=32, bg=self.colors['surface'], highlightthickness=0, bd=0)
            sw.create_oval(1, 1, 31, 31, fill=hex_value, outline=self.colors['shadow'], width=1)
            sw.pack(side=tk.LEFT, padx=(0, 10))

            info = tk.Frame(card, bg=self.colors['surface'])
            info.pack(side=tk.LEFT)
            tk.Label(info, text=hex_value, bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).pack(anchor='w')
            tk.Label(info, text=f'RGB{color}  Freq:{freq}', bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 8)).pack(anchor='w')

            self.bind_swatch_events(card, sw, info, hex_value)

            if animate:
                self.animate_card_entry(card, i)

    def animate_card_entry(self, card, index):
        offsets = [16, 10, 6, 3, 0]

        def step(pos):
            card.grid_configure(padx=offsets[pos])
            if pos + 1 < len(offsets):
                self.root.after(30, lambda: step(pos + 1))

        self.root.after(34 * index, lambda: step(0))

    def bind_swatch_events(self, card, swatch, info, hex_value):
        hover_token = {'job': None}

        def apply_hover_state(hovered):
            bg = self.colors['surface_alt'] if hovered else self.colors['surface']
            card.configure(bg=bg)
            info.configure(bg=bg)
            for child in info.winfo_children():
                child.configure(bg=bg)

        def on_enter(_event):
            if hover_token['job'] is not None:
                self.root.after_cancel(hover_token['job'])
            hover_token['job'] = self.root.after(150, lambda: apply_hover_state(True))

        def on_leave(_event):
            if hover_token['job'] is not None:
                self.root.after_cancel(hover_token['job'])
                hover_token['job'] = None
            apply_hover_state(False)

        def on_click(_event):
            self.on_swatch_click(hex_value, card)

        for widget in (card, swatch, info):
            widget.configure(cursor='hand2')
            widget.bind('<Enter>', on_enter)
            widget.bind('<Leave>', on_leave)
            widget.bind('<Button-1>', on_click)

    def on_swatch_click(self, hex_value, card):
        def paint_card(bg):
            card.configure(bg=bg)
            for child in card.winfo_children():
                try:
                    child.configure(bg=bg)
                except Exception:
                    pass
                for nested in child.winfo_children():
                    try:
                        nested.configure(bg=bg)
                    except Exception:
                        pass

        self.copy_to_clipboard(hex_value)
        paint_card('#253042')
        self.root.after(150, lambda: paint_card(self.colors['surface']))
        self.show_toast(f'Copied {hex_value}')
        self.set_status(f'Goblin copied {hex_value}')

    def export_json(self):
        export_dir = ask_directory(title='Select Export Folder')
        if not export_dir:
            return

        payload = {
            'image': self.image_path,
            'dedup_tolerance': int(self.tolerance_var.get()),
            'sort_mode': self.sort_var.get(),
            'picked_colors': [
                {'hex': rgb_to_hex(c), 'rgb': {'r': c[0], 'g': c[1], 'b': c[2]}, 'freq': f}
                for c, f in self.picked_groups
            ],
            'extracted_palette': [
                {'hex': rgb_to_hex(c), 'rgb': {'r': c[0], 'g': c[1], 'b': c[2]}, 'freq': f}
                for c, f in self.extracted_groups
            ],
        }

        out_path = Path(export_dir) / 'palette_goblin_export.json'
        try:
            write_json_file(out_path, payload)
            self.shell.set_dirty(True)
            self.set_status(f'JSON exported to {out_path.name}')
            self.show_toast('Exported JSON')
        except Exception as exc:
            messagebox.showerror('Export Error', f'Failed exporting JSON:\n{exc}')

    def export_godot_json(self):
        export_dir = ask_directory(title='Select Export Folder')
        if not export_dir:
            return

        payload = {
            'format': 'palette_goblin_godot',
            'version': 1,
            'name': 'Palette Goblin Export',
            'colors': [rgb_to_hex(c) for c, _ in self.extracted_groups],
            'picked_colors': [rgb_to_hex(c) for c, _ in self.picked_groups],
        }

        out_path = Path(export_dir) / 'palette_goblin_godot.json'
        try:
            write_json_file(out_path, payload)
            self.shell.set_dirty(True)
            self.set_status(f'Godot preset exported to {out_path.name}')
            self.show_toast('Exported Godot preset')
        except Exception as exc:
            messagebox.showerror('Export Error', f'Failed exporting Godot JSON:\n{exc}')

    def export_txt(self):
        export_dir = ask_directory(title='Select Export Folder')
        if not export_dir:
            return

        extracted_path = Path(export_dir) / 'extracted_palette.txt'
        picked_path = Path(export_dir) / 'picked_colors.txt'

        try:
            write_hex_lines(extracted_path, [rgb_to_hex(c) for c, _ in self.extracted_groups])
            write_hex_lines(picked_path, [rgb_to_hex(c) for c, _ in self.picked_groups])
            self.shell.set_dirty(True)
            self.set_status('Text swatches exported')
            self.show_toast('Exported TXT')
        except Exception as exc:
            messagebox.showerror('Export Error', f'Failed exporting TXT:\n{exc}')

    def save_hoard(self):
        payload = {'picked_colors': [rgb_to_hex(c) for c in self.picked_colors_raw]}
        try:
            HOARD_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        except Exception:
            pass

    def load_hoard(self):
        if not HOARD_PATH.exists():
            return

        try:
            payload = json.loads(HOARD_PATH.read_text(encoding='utf-8'))
            restored = []
            for hex_value in payload.get('picked_colors', []):
                try:
                    restored.append(hex_to_rgb(hex_value))
                except Exception:
                    continue

            self.picked_colors_raw = restored
            self.picked_freq_raw = dict(Counter(self.picked_colors_raw))
            if restored:
                self.set_status(f'Restored hoard with {len(restored)} picked entries')
        except Exception:
            self.set_status('Hoard file was malformed, starting fresh')


def open_tool_window(launcher_root):
    window = tk.Toplevel(launcher_root)
    PaletteGoblinApp(window, launcher_root=launcher_root)
    return window


def main():
    from goblintools.common import apply_suite_theme

    root = tk.Tk()
    apply_suite_theme(root)
    PaletteGoblinApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()


