import io
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from goblintools.common import (
    BackgroundJobRunner,
    SECTION_GAP,
    ShortcutManager,
    SPACE_8,
    SPACE_16,
    SURFACE_PAD,
    ToolShell,
    ToastNotifier,
    ShinyButton,
    ask_directory,
    ask_image_file,
    get_theme_tokens,
    tool_title,
)


class SlicerGoblinApp:
    def __init__(self, root, launcher_root=None):
        self.root = root
        self.launcher_root = launcher_root
        self.root.title(tool_title('Slicer Goblin', 'slicer_goblin'))
        self.root.geometry('1440x900')
        self.root.minsize(1180, 760)
        self.colors = get_theme_tokens()
        self.root.protocol('WM_DELETE_WINDOW', self.back_to_launcher)

        self.source_image = None
        self.working_image = None
        self.display_image = None
        self.tk_image = None

        self.zoom = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 16.0

        self.draw_x = 0
        self.draw_y = 0
        self.draw_w = 0
        self.draw_h = 0

        self.grid_overlay_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value='Goblin standing by')

        self.cell_w_var = tk.IntVar(value=32)
        self.cell_h_var = tk.IntVar(value=32)
        self.offset_x_var = tk.IntVar(value=0)
        self.offset_y_var = tk.IntVar(value=0)

        self.export_dir = None
        self.export_dir_var = tk.StringVar(value='No export folder selected')

        self.slice_rects = []
        self.slices = []

        self.toast = None
        self.jobs = BackgroundJobRunner(self.root)
        self._busy = False
        self._busy_controls = []
        self._shortcut_tip = None
        self.shortcuts = ShortcutManager()

        self._build_ui()
        self._bind_live_updates()
        self.shell.set_dirty(False)
        self.shortcuts.bind(self.root, '<Shift-Tab>', self._on_shortcut_toggle_help, description='Toggle shortcuts help')
        self.shortcuts.bind(self.root, '<ISO_Left_Tab>', self._on_shortcut_toggle_help)
        self.shortcuts.bind(self.root, '<Shift-I>', self._on_shortcut_toggle_inspector, description='Toggle inspector')
        self.shortcuts.bind(self.root, '<Shift-BackSpace>', self._on_shortcut_back_to_launcher, description='Back to launcher (confirm)')

    def _build_ui(self):
        self.shell = ToolShell(
            self.root,
            title=tool_title('Slicer Goblin', 'slicer_goblin'),
            title_icon='SLC',
            tool_id='slicer_goblin',
            colors=self.colors,
            on_back=self.back_to_launcher,
        )
        self.shell.set_rail_actions([
            {'id': 'open_image', 'label': 'Open Image', 'icon': '>', 'command': self.open_image},
            {'id': 'slice_hoard', 'label': 'Slice Hoard', 'icon': '>', 'command': self.slice_hoard},
        ])
        workspace = self.shell.main
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(workspace, bg=self.colors['canvas_bg'], highlightthickness=0, relief=tk.FLAT, cursor='crosshair')
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.canvas.bind('<Configure>', lambda _e: self.render_canvas())
        self.canvas.bind('<MouseWheel>', self.on_mouse_wheel)

        toolbar = tk.Frame(workspace, bg=self.colors['surface'], padx=SPACE_8, pady=SPACE_8, highlightthickness=0)
        toolbar.place(x=SPACE_16, y=SPACE_16, anchor='nw')

        self.open_btn = ttk.Button(toolbar, text='Open Image', style='Ghost.TButton', command=self.open_image)
        self.open_btn.pack(side=tk.LEFT)

        self.remove_btn = ttk.Button(toolbar, text='Remove Background', style='Ghost.TButton', command=self.run_remove_bg)
        self.remove_btn.pack(side=tk.LEFT, padx=(SPACE_8, 0))

        self.zoom_label = tk.Label(toolbar, text='100%', bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 9), padx=SPACE_8)
        self.zoom_label.pack(side=tk.LEFT, padx=(SPACE_8, SPACE_8 // 2))

        self.grid_toggle = ttk.Checkbutton(toolbar, text='Grid Overlay', variable=self.grid_overlay_var, style='Floating.TCheckbutton', command=self.render_canvas)
        self.grid_toggle.pack(side=tk.LEFT, padx=(SPACE_8, 0))
        inspector = self.shell.sidebar
        inspector.columnconfigure(0, weight=1)

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
        self.shortcut_hint.bind('<Button-1>', lambda _e: messagebox.showinfo('Slicer Goblin Shortcuts', self._shortcut_text()))
        tk.Label(status_surface, textvariable=self.status_var, bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 9), justify=tk.LEFT, wraplength=320).pack(anchor='w')
        self.busy_bar = ttk.Progressbar(status_surface, orient=tk.HORIZONTAL, mode='indeterminate')
        self.busy_bar.pack(fill=tk.X, pady=(8, 0))
        self.busy_bar.pack_forget()

        ttk.Label(inspector, text='Slice Settings', style='Section.TLabel').grid(row=2, column=0, sticky='w')
        settings = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        settings.grid(row=3, column=0, sticky='ew', pady=(SPACE_8, SECTION_GAP))
        settings.columnconfigure(1, weight=1)

        self.cell_w_spin = self._add_number_field(settings, 0, 'Cell Width', self.cell_w_var)
        self.cell_h_spin = self._add_number_field(settings, 1, 'Cell Height', self.cell_h_var)
        self.offset_x_spin = self._add_number_field(settings, 2, 'Offset X', self.offset_x_var)
        self.offset_y_spin = self._add_number_field(settings, 3, 'Offset Y', self.offset_y_var)

        self.slice_btn = ShinyButton(settings, text='Slice Hoard', command=self.slice_hoard, width=236, height=40, colors=self.colors)
        self.slice_btn.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(12, 0))

        ttk.Label(inspector, text='Export', style='Section.TLabel').grid(row=4, column=0, sticky='w')
        export_surface = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        export_surface.grid(row=5, column=0, sticky='ew', pady=(SPACE_8, 0))
        export_surface.columnconfigure(0, weight=1)
        export_surface.columnconfigure(1, weight=1)

        self.export_folder_btn = ttk.Button(export_surface, text='Export Folder', style='Ghost.TButton', command=self.choose_export_folder)
        self.export_folder_btn.grid(row=0, column=0, sticky='ew', padx=(0, 4))
        self.export_zip_btn = ttk.Button(export_surface, text='Export ZIP', style='Ghost.TButton', command=self.export_zip)
        self.export_zip_btn.grid(row=0, column=1, sticky='ew', padx=(4, 0))

        tk.Label(export_surface, textvariable=self.export_dir_var, bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 8), anchor='w', justify=tk.LEFT, wraplength=320).grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 0))

        for btn in (self.open_btn, self.remove_btn, self.export_folder_btn, self.export_zip_btn):
            self._bind_ghost_feedback(btn)
        self.slice_btn.configure(cursor='hand2')
        self._busy_controls = [
            self.open_btn,
            self.remove_btn,
            self.grid_toggle,
            self.cell_w_spin,
            self.cell_h_spin,
            self.offset_x_spin,
            self.offset_y_spin,
            self.export_folder_btn,
            self.export_zip_btn,
        ]

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

    def _add_number_field(self, parent, row, label, var):
        tk.Label(parent, text=label, bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 10)).grid(row=row, column=0, sticky='w', pady=(0 if row == 0 else 8, 0), padx=(0, 8))
        spin = tk.Spinbox(
            parent,
            from_=0,
            to=4096,
            textvariable=var,
            width=8,
            bg=self.colors['surface_alt'],
            fg=self.colors['text'],
            insertbackground=self.colors['text'],
            highlightthickness=1,
            highlightbackground=self.colors['surface_alt'],
            highlightcolor=self.colors.get('accent_cyan', self.colors['accent']),
            relief=tk.FLAT,
        )
        spin.grid(row=row, column=1, sticky='w', pady=(0 if row == 0 else 8, 0))
        return spin

    def _bind_live_updates(self):
        for var in (self.cell_w_var, self.cell_h_var, self.offset_x_var, self.offset_y_var):
            var.trace_add('write', lambda *_args: self.render_canvas())

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

    def set_status(self, text):
        self.status_var.set(text)
        if hasattr(self, 'shell'):
            self.shell.set_status(text)

    def show_toast(self, text):
        if self.toast is not None:
            self.toast.show(text)

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
        self._set_widget_state(self.slice_btn, enabled=not busy)
        self.root.configure(cursor='watch' if busy else '')
        if busy:
            self.busy_bar.pack(fill=tk.X, pady=(8, 0))
            self.busy_bar.start(10)
        else:
            self.busy_bar.stop()
            self.busy_bar.pack_forget()
        if status:
            self.set_status(status)

    def _job_error(self, context, result):
        if result.tb:
            print(result.tb)
        self._set_busy(False)
        self.set_status(f'{context} failed')
        messagebox.showerror('Operation Error', f'{context} failed.\n{result.error}')

    def open_image(self):
        if self._busy:
            return
        file_path = ask_image_file(title='Open Image')
        if not file_path:
            return

        try:
            image = Image.open(file_path).convert('RGBA')
        except Exception as exc:
            messagebox.showerror('Open Error', f'Unable to open image:\n{exc}')
            return

        self.source_image = image.copy()
        self.working_image = image
        self.zoom = 1.0
        self.zoom_label.configure(text='100%')
        self.slice_rects = []
        self.slices = []
        self.render_canvas()
        self.shell.set_dirty(True)
        self.set_status(f'Goblin loaded {Path(file_path).name} ({image.width}x{image.height})')

    def on_mouse_wheel(self, event):
        if self.working_image is None:
            return
        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
        self.zoom_label.configure(text=f'{int(self.zoom * 100)}%')
        self.render_canvas()

    def render_canvas(self):
        self.canvas.delete('all')
        if self.working_image is None:
            return

        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        rw = max(1, int(self.working_image.width * self.zoom))
        rh = max(1, int(self.working_image.height * self.zoom))

        self.display_image = self.working_image.resize((rw, rh), Image.NEAREST)
        self.tk_image = ImageTk.PhotoImage(self.display_image)

        self.draw_x = max((cw - rw) // 2, 0)
        self.draw_y = max((ch - rh) // 2, 0)
        self.draw_w = rw
        self.draw_h = rh

        self.canvas.create_image(self.draw_x, self.draw_y, anchor=tk.NW, image=self.tk_image)

        if self.grid_overlay_var.get():
            self.draw_grid_overlay()

        if self.slice_rects:
            self.draw_slice_preview()

    def draw_grid_overlay(self):
        if self.working_image is None:
            return

        cell_w = max(1, int(self.cell_w_var.get() or 1))
        cell_h = max(1, int(self.cell_h_var.get() or 1))
        off_x = max(0, int(self.offset_x_var.get() or 0))
        off_y = max(0, int(self.offset_y_var.get() or 0))

        x = off_x
        while x <= self.working_image.width:
            sx = self.draw_x + int(x * self.zoom)
            self.canvas.create_line(sx, self.draw_y, sx, self.draw_y + self.draw_h, fill='#41506B')
            x += cell_w

        y = off_y
        while y <= self.working_image.height:
            sy = self.draw_y + int(y * self.zoom)
            self.canvas.create_line(self.draw_x, sy, self.draw_x + self.draw_w, sy, fill='#41506B')
            y += cell_h

    def draw_slice_preview(self):
        for x, y, w, h in self.slice_rects:
            sx1 = self.draw_x + int(x * self.zoom)
            sy1 = self.draw_y + int(y * self.zoom)
            sx2 = self.draw_x + int((x + w) * self.zoom)
            sy2 = self.draw_y + int((y + h) * self.zoom)
            self.canvas.create_rectangle(sx1, sy1, sx2, sy2, outline='#9FC4FF', width=1)

    def run_remove_bg(self):
        if self.source_image is None:
            messagebox.showinfo('No Image', 'Open an image first.')
            return
        if self._busy:
            return

        image = self.source_image.copy()
        self._set_busy(True, status='Goblin stripping background...')
        self.jobs.submit(self._remove_bg_worker, self._on_remove_bg_done, image)

    def _remove_bg_worker(self, source_image, progress=None):
        try:
            from rembg import remove
        except Exception:
            return {'missing_rembg': True}

        buf = io.BytesIO()
        source_image.save(buf, format='PNG')
        out = remove(buf.getvalue())
        image = Image.open(io.BytesIO(out)).convert('RGBA')
        return {'image': image}

    def _on_remove_bg_done(self, result):
        try:
            if not result.ok:
                self._job_error('Background removal', result)
                return

            payload = result.value or {}
            if payload.get('missing_rembg'):
                self.set_status('rembg missing')
                messagebox.showerror('Missing Dependency', 'rembg is not installed.\nInstall with: pip install rembg')
                return

            self.working_image = payload['image']
            self.slice_rects = []
            self.slices = []
            self.render_canvas()
            self.shell.set_dirty(True)
            self.set_status('Background removed')
            self.show_toast('Background removed')
        finally:
            self._set_busy(False)

    def compute_slices(self, image, cell_w, cell_h, off_x, off_y):
        if image is None:
            return [], []

        width, height = image.size
        slices = []
        rects = []

        for y in range(off_y, height, cell_h):
            for x in range(off_x, width, cell_w):
                box = (x, y, min(x + cell_w, width), min(y + cell_h, height))
                tile = image.crop(box)

                if tile.mode in ('RGBA', 'LA'):
                    alpha = tile.getchannel('A')
                    if alpha.getbbox() is None:
                        continue

                rects.append((box[0], box[1], box[2] - box[0], box[3] - box[1]))
                slices.append(tile)

        return slices, rects

    def slice_hoard(self):
        if self.working_image is None:
            messagebox.showinfo('No Image', 'Open an image first.')
            return
        if self._busy:
            return

        if not self.export_dir:
            self.choose_export_folder()
            if not self.export_dir:
                return

        image = self.working_image.copy()
        cell_w = max(1, int(self.cell_w_var.get() or 1))
        cell_h = max(1, int(self.cell_h_var.get() or 1))
        off_x = max(0, int(self.offset_x_var.get() or 0))
        off_y = max(0, int(self.offset_y_var.get() or 0))
        export_dir = Path(self.export_dir) if self.export_dir else None

        self._set_busy(True, status='Goblin slicing hoard...')
        self.jobs.submit(
            self._slice_worker,
            self._on_slice_done,
            image,
            cell_w,
            cell_h,
            off_x,
            off_y,
            export_dir,
            on_progress=self._on_slice_progress,
        )

    def _slice_worker(self, image, cell_w, cell_h, off_x, off_y, export_dir, progress=None):
        slices, rects = self.compute_slices(image, cell_w, cell_h, off_x, off_y)
        if export_dir and slices:
            if callable(progress):
                progress(f'Saving {len(slices)} slices...')
            self.save_slices_to_folder(export_dir, slices, progress=progress)
        return {'slices': slices, 'rects': rects, 'saved': bool(export_dir and slices)}

    def _on_slice_done(self, result):
        try:
            if not result.ok:
                self._job_error('Slice hoard', result)
                return

            payload = result.value or {}
            self.slices = payload.get('slices', [])
            self.slice_rects = payload.get('rects', [])
            self.render_canvas()
            self.shell.set_dirty(True)

            if not self.slices:
                self.set_status('No non-transparent slices found')
                self.show_toast('No slices exported')
                return

            if payload.get('saved'):
                self.set_status(f'Exported {len(self.slices)} slices')
                self.show_toast(f'Exported {len(self.slices)} slices')
            else:
                self.set_status(f'{len(self.slices)} slices ready')
                self.show_toast(f'{len(self.slices)} slices ready')
        finally:
            self._set_busy(False)

    def _on_slice_progress(self, message):
        if isinstance(message, str):
            self.set_status(message)

    def choose_export_folder(self):
        if self._busy:
            return
        export_dir = ask_directory(title='Select Export Folder')
        if not export_dir:
            return

        self.export_dir = Path(export_dir)
        self.export_dir_var.set(str(self.export_dir))
        self.shell.set_dirty(True)
        self.set_status(f'Export folder set: {self.export_dir.name}')

    def save_slices_to_folder(self, folder, slices, progress=None):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        for i, tile in enumerate(slices, start=1):
            tile.save(folder / f'slice_{i:04d}.png', format='PNG')
            if callable(progress) and (i % 50 == 0 or i == len(slices)):
                progress(f'Saving slices... {i}/{len(slices)}')

    def export_zip(self):
        if not self.slices:
            messagebox.showinfo('No Slices', 'Slice the image first.')
            return
        if self._busy:
            return

        if not self.export_dir:
            self.choose_export_folder()
            if not self.export_dir:
                return

        zip_path = Path(self.export_dir) / 'slicer_goblin_slices.zip'
        slices = list(self.slices)
        self._set_busy(True, status='Goblin packing ZIP...')
        self.jobs.submit(self._zip_worker, self._on_zip_done, slices, zip_path, on_progress=self._on_zip_progress)

    def _zip_worker(self, slices, zip_path, progress=None):
        total = len(slices)
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for i, tile in enumerate(slices, start=1):
                buf = io.BytesIO()
                tile.save(buf, format='PNG')
                zf.writestr(f'slice_{i:04d}.png', buf.getvalue())
                if callable(progress) and (i % 50 == 0 or i == total):
                    progress(f'Packing ZIP... {i}/{total}')
        return {'zip_path': zip_path}

    def _on_zip_done(self, result):
        try:
            if not result.ok:
                self._job_error('ZIP export', result)
                return
            payload = result.value or {}
            zip_path = payload.get('zip_path')
            name = zip_path.name if zip_path else 'slicer_goblin_slices.zip'
            self.shell.set_dirty(True)
            self.set_status(f'ZIP exported: {name}')
            self.show_toast('ZIP exported')
        finally:
            self._set_busy(False)

    def _on_zip_progress(self, message):
        if isinstance(message, str):
            self.set_status(message)


def open_tool_window(launcher_root):
    window = tk.Toplevel(launcher_root)
    SlicerGoblinApp(window, launcher_root=launcher_root)
    return window


def run():
    from goblintools.common import apply_suite_theme

    root = tk.Tk()
    apply_suite_theme(root)
    SlicerGoblinApp(root)
    root.mainloop()


if __name__ == '__main__':
    run()




