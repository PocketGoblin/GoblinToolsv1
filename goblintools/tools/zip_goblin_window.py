from pathlib import Path
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.archive_engine import (
    create_archive,
    extract_all,
    extract_selected,
    list_archive,
)
from goblintools.common import (
    BackgroundJobRunner,
    SECTION_GAP,
    SPACE_8,
    ShortcutManager,
    SURFACE_PAD,
    ShinyButton,
    ToolShell,
    ToastNotifier,
    bind_button_feedback,
    get_theme_tokens,
    is_dnd_disabled,
    tool_title,
)


ARCHIVE_FILETYPES = [('Archives', '*.zip;*.7z;*.rar;*.tar;*.gz;*.bz2;*.xz;*.tgz;*.tbz2;*.txz;*.iso;*.cab;*.arj;*.lzh;*.z'), ('All Files', '*.*')]
SUPPORTED_ARCHIVE_SUFFIXES = {
    '.zip',
    '.7z',
    '.rar',
    '.tar',
    '.gz',
    '.bz2',
    '.xz',
    '.tgz',
    '.tbz2',
    '.txz',
    '.iso',
    '.cab',
    '.arj',
    '.lzh',
    '.z',
}


class ZipGoblinWindow:
    def __init__(self, root, launcher_root=None):
        self.root = root
        self.launcher_root = launcher_root
        self.root.title(tool_title('Zip Goblin', 'zip_goblin'))
        self.root.geometry('1440x900')
        self.root.minsize(1180, 760)
        self.colors = get_theme_tokens()
        self.root.protocol('WM_DELETE_WINDOW', self.back_to_launcher)

        self.jobs = BackgroundJobRunner(self.root)
        self.toast = None
        self._busy = False
        self._busy_controls = []
        self._shortcut_tip = None
        self._drop_ready = False
        self.shortcuts = ShortcutManager()

        self.archive_path = None
        self.archive_entries = []
        self.tree_id_to_member = {}

        self.output_dir = None
        self.output_var = tk.StringVar(value='No output folder selected')
        self.password_var = tk.StringVar(value='')
        self.create_name_var = tk.StringVar(value='goblin_pack')
        self.create_format_var = tk.StringVar(value='zip')
        self.create_level_var = tk.StringVar(value='normal')

        self.input_paths = []

        self._build_ui()
        self.shell.set_dirty(False)
        self.shortcuts.bind(self.root, '<Shift-Tab>', self._on_shortcut_toggle_help, description='Toggle shortcuts help')
        self.shortcuts.bind(self.root, '<ISO_Left_Tab>', self._on_shortcut_toggle_help)
        self.shortcuts.bind(self.root, '<Shift-I>', self._on_shortcut_toggle_inspector, description='Toggle inspector')
        self.shortcuts.bind(self.root, '<Shift-BackSpace>', self._on_shortcut_back_to_launcher, description='Back to launcher (confirm)')
        self.shortcuts.register_help('Drag archive into workspace', 'Open archive')
        if not self._drop_ready:
            self.shortcuts.register_help('Drag-and-drop', 'Unavailable (tkdnd missing)')

    def _build_ui(self):
        self.shell = ToolShell(
            self.root,
            title=tool_title('Zip Goblin', 'zip_goblin'),
            title_icon='ZIP',
            tool_id='zip_goblin',
            colors=self.colors,
            on_back=self.back_to_launcher,
        )
        self.shell.set_rail_actions(
            [
                {'id': 'open_archive', 'label': 'Open Archive', 'icon': '>', 'command': self.open_archive},
                {'id': 'extract_all', 'label': 'Extract All', 'icon': '>', 'command': self.on_extract_all},
                {'id': 'create_archive', 'label': 'Create Archive', 'icon': '>', 'command': self.on_create_archive},
            ]
        )

        workspace = self.shell.main
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(0, weight=1)

        table_surface = ttk.Frame(workspace, style='Surface.TFrame', padding=SURFACE_PAD)
        table_surface.grid(row=0, column=0, sticky='nsew')
        table_surface.columnconfigure(0, weight=1)
        table_surface.rowconfigure(1, weight=1)

        ttk.Label(table_surface, text='Archive Contents', style='Section.TLabel').grid(row=0, column=0, sticky='w')

        table_wrap = ttk.Frame(table_surface, style='Surface.TFrame')
        table_wrap.grid(row=1, column=0, sticky='nsew', pady=(8, 0))
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_wrap,
            columns=('name', 'size', 'modified'),
            show='headings',
            selectmode='extended',
        )
        self.tree.heading('name', text='Name')
        self.tree.heading('size', text='Size')
        self.tree.heading('modified', text='Modified')
        self.tree.column('name', width=520, anchor='w')
        self.tree.column('size', width=110, anchor='e')
        self.tree.column('modified', width=180, anchor='w')
        self.tree.tag_configure('row_even', background=self.colors['surface'])
        self.tree.tag_configure('row_odd', background=self.colors['surface_alt'])
        self.tree.grid(row=0, column=0, sticky='nsew')

        tree_y = ttk.Scrollbar(table_wrap, orient=tk.VERTICAL, command=self.tree.yview)
        tree_x = ttk.Scrollbar(table_wrap, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_y.set, xscrollcommand=tree_x.set)
        tree_y.grid(row=0, column=1, sticky='ns')
        tree_x.grid(row=1, column=0, sticky='ew')
        self._drop_ready = self._enable_archive_drop([table_surface, table_wrap, self.tree])

        inspector = self.shell.sidebar
        inspector.columnconfigure(0, weight=1)
        inspector.rowconfigure(5, weight=1)

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
        self.shortcut_hint.bind('<Button-1>', lambda _e: messagebox.showinfo('Zip Goblin Shortcuts', self._shortcut_text()))
        self.status_label = tk.Label(status_surface, text='Goblin standing by', bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 9), anchor='w', justify=tk.LEFT, wraplength=320)
        self.status_label.pack(anchor='w')
        self.busy_bar = ttk.Progressbar(status_surface, orient=tk.HORIZONTAL, mode='indeterminate')
        self.busy_bar.pack(fill=tk.X, pady=(8, 0))
        self.busy_bar.pack_forget()

        ttk.Label(inspector, text='Archive', style='Section.TLabel').grid(row=2, column=0, sticky='w')
        archive_surface = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        archive_surface.grid(row=3, column=0, sticky='ew', pady=(SPACE_8, SECTION_GAP))
        archive_surface.columnconfigure(0, weight=1)
        archive_surface.columnconfigure(1, weight=1)

        self.open_btn = ttk.Button(archive_surface, text='Open Archive', style='Ghost.TButton', command=self.open_archive)
        self.open_btn.grid(row=0, column=0, columnspan=2, sticky='ew')
        self.extract_all_btn = ttk.Button(archive_surface, text='Extract All', style='Ghost.TButton', command=self.on_extract_all)
        self.extract_all_btn.grid(row=1, column=0, sticky='ew', pady=(8, 0), padx=(0, 4))
        self.extract_sel_btn = ttk.Button(archive_surface, text='Extract Selected', style='Ghost.TButton', command=self.on_extract_selected)
        self.extract_sel_btn.grid(row=1, column=1, sticky='ew', pady=(8, 0), padx=(4, 0))

        self.output_btn = ttk.Button(archive_surface, text='Output Folder', style='Ghost.TButton', command=self.choose_output_dir)
        self.output_btn.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        tk.Label(archive_surface, textvariable=self.output_var, bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 8), wraplength=300, justify=tk.LEFT).grid(row=3, column=0, columnspan=2, sticky='w', pady=(6, 0))

        tk.Label(archive_surface, text='Password (optional)', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=4, column=0, columnspan=2, sticky='w', pady=(8, 0))
        self.password_entry = ttk.Entry(archive_surface, textvariable=self.password_var)
        self.password_entry.grid(row=5, column=0, columnspan=2, sticky='ew', pady=(4, 0))
        self.default_apps_btn = ttk.Button(
            archive_surface,
            text='Make Zip Goblin Default',
            style='Ghost.TButton',
            command=self.open_default_apps_settings,
        )
        self.default_apps_btn.grid(row=6, column=0, columnspan=2, sticky='ew', pady=(8, 0))

        ttk.Label(inspector, text='Create Archive', style='Section.TLabel').grid(row=4, column=0, sticky='w')
        create_surface = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        create_surface.grid(row=5, column=0, sticky='nsew')
        create_surface.columnconfigure(0, weight=1)
        create_surface.rowconfigure(5, weight=1)

        input_buttons = ttk.Frame(create_surface, style='Surface.TFrame')
        input_buttons.grid(row=0, column=0, sticky='ew')
        input_buttons.columnconfigure(0, weight=1)
        input_buttons.columnconfigure(1, weight=1)
        self.add_file_btn = ttk.Button(input_buttons, text='Add File', style='Ghost.TButton', command=self.add_input_file)
        self.add_file_btn.grid(row=0, column=0, sticky='ew', padx=(0, 4))
        self.add_folder_btn = ttk.Button(input_buttons, text='Add Folder', style='Ghost.TButton', command=self.add_input_folder)
        self.add_folder_btn.grid(row=0, column=1, sticky='ew', padx=(4, 0))

        self.input_list = tk.Listbox(create_surface, height=5, bg=self.colors['surface_alt'], fg=self.colors['text'], selectbackground='#1E3157', relief=tk.FLAT, highlightthickness=0)
        self.input_list.grid(row=1, column=0, sticky='nsew', pady=(8, 0))

        self.remove_input_btn = ttk.Button(create_surface, text='Remove Selected Input', style='Ghost.TButton', command=self.remove_input_path)
        self.remove_input_btn.grid(row=2, column=0, sticky='ew', pady=(8, 0))

        tk.Label(create_surface, text='Output Name', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=3, column=0, sticky='w', pady=(8, 0))
        self.create_name_entry = ttk.Entry(create_surface, textvariable=self.create_name_var)
        self.create_name_entry.grid(row=4, column=0, sticky='ew', pady=(4, 0))

        row_opts = ttk.Frame(create_surface, style='Surface.TFrame')
        row_opts.grid(row=6, column=0, sticky='ew', pady=(8, 0))
        row_opts.columnconfigure(1, weight=1)
        row_opts.columnconfigure(3, weight=1)
        tk.Label(row_opts, text='Format', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w')
        self.format_combo = ttk.Combobox(row_opts, textvariable=self.create_format_var, values=('zip', '7z'), state='readonly', width=8)
        self.format_combo.grid(row=0, column=1, sticky='ew', padx=(6, 12))
        tk.Label(row_opts, text='Level', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=0, column=2, sticky='w')
        self.level_combo = ttk.Combobox(row_opts, textvariable=self.create_level_var, values=('store', 'fast', 'normal', 'maximum', 'ultra'), state='readonly', width=10)
        self.level_combo.grid(row=0, column=3, sticky='ew', padx=(6, 0))

        self.create_btn = ShinyButton(create_surface, text='Create Archive', command=self.on_create_archive, width=260, height=40, colors=self.colors)
        self.create_btn.grid(row=7, column=0, sticky='ew', pady=(12, 0))

        for btn in (
            self.open_btn,
            self.extract_all_btn,
            self.extract_sel_btn,
            self.output_btn,
            self.default_apps_btn,
            self.add_file_btn,
            self.add_folder_btn,
            self.remove_input_btn,
        ):
            bind_button_feedback(self.root, btn, variant='ghost')
        self.create_btn.configure(cursor='hand2')

        self._busy_controls = [
            self.open_btn,
            self.extract_all_btn,
            self.extract_sel_btn,
            self.output_btn,
            self.default_apps_btn,
            self.password_entry,
            self.add_file_btn,
            self.add_folder_btn,
            self.remove_input_btn,
            self.create_name_entry,
            self.format_combo,
            self.level_combo,
        ]

        self.toast = ToastNotifier(self.root, bg=self.colors['toast'], fg=self.colors['text'])

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
        self.status_label.configure(text=text)
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

    def _set_busy(self, busy, message=None):
        self._busy = busy
        for w in self._busy_controls:
            self._set_widget_state(w, enabled=not busy)
        self._set_widget_state(self.create_btn, enabled=not busy)
        self.root.configure(cursor='watch' if busy else '')
        if busy:
            self.busy_bar.pack(fill=tk.X, pady=(8, 0))
            self.busy_bar.start(10)
        else:
            self.busy_bar.stop()
            self.busy_bar.pack_forget()
        if message:
            self.set_status(message)

    def _job_failed(self, context, result):
        if result.tb:
            print(result.tb)
        msg = str(result.error) if result.error else f'{context} failed'
        self.set_status(msg)
        messagebox.showerror('Zip Goblin', msg)

    def choose_output_dir(self):
        if self._busy:
            return
        folder = filedialog.askdirectory(title='Choose Output Folder')
        if not folder:
            return
        self.output_dir = Path(folder).resolve()
        self.output_var.set(str(self.output_dir))
        self.shell.set_dirty(True)
        self.set_status(f'Output set: {self.output_dir.name}')

    def open_default_apps_settings(self):
        if sys.platform != 'win32':
            messagebox.showinfo('Zip Goblin', 'Default app registration shortcut is available on Windows only.')
            return
        try:
            # Prefer direct file-type association page.
            subprocess.Popen(
                ['control.exe', '/name', 'Microsoft.DefaultPrograms', '/page', 'pageFileAssoc'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.set_status('Opened file-type defaults. Set Zip Goblin for .zip, .7z, .rar.')
            self.show_toast('Default apps opened')
        except Exception:
            try:
                os.startfile('ms-settings:defaultapps')
                self.set_status('Opened Windows Default apps. Set Zip Goblin for .zip, .7z, .rar.')
                self.show_toast('Default apps opened')
            except Exception as exc:
                messagebox.showerror('Zip Goblin', f'Could not open Default apps settings.\n{exc}')

    def open_archive(self):
        if self._busy:
            return
        file_path = filedialog.askopenfilename(title='Open Archive', filetypes=ARCHIVE_FILETYPES)
        if not file_path:
            return
        self._open_archive_path(Path(file_path), source_label='Archive selected')

    def _open_archive_path(self, archive_path: Path, source_label: str = 'Archive selected'):
        self.archive_path = archive_path.resolve()
        self.shell.set_dirty(True)
        self._set_busy(True, 'Goblin rummaging archive...')
        self.jobs.submit(self._list_worker, self._on_list_done, str(self.archive_path))
        self.set_status(source_label)

    def _enable_archive_drop(self, widgets: list[tk.Widget]) -> bool:
        if is_dnd_disabled():
            return False
        try:
            self.root.tk.call('package', 'require', 'tkdnd')
        except Exception:
            return False
        cmd = self.root.register(self._on_drop_archive_data)
        any_bound = False
        for widget in widgets:
            try:
                widget.tk.call('tkdnd::drop_target', 'register', widget._w, 'DND_Files')
                widget.tk.call('bind', widget._w, '<<Drop>>', f'{cmd} %D')
                try:
                    widget.bind('<<Drop>>', self._on_drop_archive_event, add='+')
                except Exception:
                    pass
                any_bound = True
            except Exception:
                pass
        return any_bound

    def _on_drop_archive_event(self, event):
        data = getattr(event, 'data', '')
        return self._on_drop_archive_data(str(data or ''))

    def _parse_dropped_paths(self, raw_data: str) -> list[Path]:
        if not raw_data:
            return []
        try:
            parts = list(self.root.tk.splitlist(raw_data))
        except Exception:
            parts = [raw_data]
        out: list[Path] = []
        for item in parts:
            text = str(item).strip()
            if text.startswith('{') and text.endswith('}'):
                text = text[1:-1]
            if text:
                out.append(Path(text).expanduser())
        return out

    def _is_supported_archive(self, path: Path) -> bool:
        return path.is_file() and path.suffix.lower() in SUPPORTED_ARCHIVE_SUFFIXES

    def _on_drop_archive_data(self, raw_data: str):
        if self._busy:
            return 'break'
        dropped = self._parse_dropped_paths(raw_data)
        archives = [p for p in dropped if p.exists() and self._is_supported_archive(p)]
        if not archives:
            self.show_toast('Drop a supported archive file')
            self.set_status('Drop ignored: no supported archive found')
            return 'break'
        self._open_archive_path(archives[0], source_label='Archive dropped')
        ignored = max(0, len(dropped) - 1)
        if ignored:
            self.show_toast(f'Opened first archive, ignored {ignored} extra item(s)')
        return 'break'

    def _list_worker(self, archive_path, progress=None):
        entries = list_archive(archive_path)
        return {'archive': archive_path, 'entries': entries}

    def _on_list_done(self, result):
        try:
            if not result.ok:
                self._job_failed('List archive', result)
                return

            payload = result.value or {}
            self.archive_entries = payload.get('entries', [])
            self._populate_tree(self.archive_entries)
            self.shell.set_dirty(True)
            self.set_status(f'Listed {len(self.archive_entries)} items')
            self.show_toast('Archive listed')
        finally:
            self._set_busy(False)

    def _populate_tree(self, entries):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree_id_to_member = {}
        for i, e in enumerate(entries):
            path = e.get('path', '')
            size = e.get('size', 0)
            modified = e.get('modified', '')
            name = f'{path}/' if e.get('is_dir') and not str(path).endswith('/') else path
            iid = f'row_{i}'
            self.tree_id_to_member[iid] = path
            tag = 'row_even' if i % 2 == 0 else 'row_odd'
            self.tree.insert('', tk.END, iid=iid, values=(name, self._format_size(size), modified), tags=(tag,))

    def _format_size(self, n):
        try:
            n = int(n)
        except Exception:
            return '0 B'
        for unit in ('B', 'KB', 'MB', 'GB'):
            if n < 1024:
                return f'{n:.0f} {unit}'
            n /= 1024
        return f'{n:.1f} TB'

    def _require_archive_and_output(self):
        if not self.archive_path:
            messagebox.showinfo('Zip Goblin', 'Open an archive first.')
            return False
        if not self.output_dir:
            self.choose_output_dir()
            if not self.output_dir:
                return False
        return True

    def on_extract_all(self):
        if self._busy:
            return
        if not self._require_archive_and_output():
            return
        archive = str(self.archive_path)
        out_dir = str(self.output_dir)
        password = self.password_var.get().strip() or None
        self._set_busy(True, 'Goblin extracting all treasure...')
        self.jobs.submit(self._extract_all_worker, self._on_extract_done, archive, out_dir, password)

    def _extract_all_worker(self, archive, out_dir, password, progress=None):
        return extract_all(archive, out_dir, password=password)

    def on_extract_selected(self):
        if self._busy:
            return
        if not self._require_archive_and_output():
            return
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo('Zip Goblin', 'Select one or more archive entries first.')
            return
        members = [self.tree_id_to_member.get(iid, '') for iid in selection]
        members = [m for m in members if m]
        archive = str(self.archive_path)
        out_dir = str(self.output_dir)
        password = self.password_var.get().strip() or None
        self._set_busy(True, 'Goblin extracting selected treasure...')
        self.jobs.submit(self._extract_selected_worker, self._on_extract_done, archive, out_dir, members, password)

    def _extract_selected_worker(self, archive, out_dir, members, password, progress=None):
        return extract_selected(archive, out_dir, members, password=password)

    def _on_extract_done(self, result):
        try:
            if not result.ok:
                self._job_failed('Extract archive', result)
                return
            payload = result.value or {}
            count = payload.get('count', 0)
            self.shell.set_dirty(True)
            self.set_status(f'Extracted {count} item(s)')
            self.show_toast('Extraction complete')
        finally:
            self._set_busy(False)

    def add_input_file(self):
        if self._busy:
            return
        file_path = filedialog.askopenfilename(title='Add File to Archive')
        if not file_path:
            return
        self._append_input_path(file_path)

    def add_input_folder(self):
        if self._busy:
            return
        folder = filedialog.askdirectory(title='Add Folder to Archive')
        if not folder:
            return
        self._append_input_path(folder)

    def _append_input_path(self, p):
        path = str(Path(p).resolve())
        if path in self.input_paths:
            return
        self.input_paths.append(path)
        self.input_list.insert(tk.END, path)
        self.shell.set_dirty(True)

    def remove_input_path(self):
        if self._busy:
            return
        selection = self.input_list.curselection()
        if not selection:
            return
        idx = selection[0]
        self.input_list.delete(idx)
        del self.input_paths[idx]
        self.shell.set_dirty(True)

    def on_create_archive(self):
        if self._busy:
            return
        if not self.output_dir:
            self.choose_output_dir()
            if not self.output_dir:
                return
        if not self.input_paths:
            messagebox.showinfo('Zip Goblin', 'Add at least one input file/folder.')
            return

        name = (self.create_name_var.get() or '').strip()
        if not name:
            messagebox.showerror('Zip Goblin', 'Output name is required.')
            return
        fmt = self.create_format_var.get().strip().lower() or 'zip'
        level = self.create_level_var.get().strip().lower() or 'normal'
        suffix = f'.{fmt}'
        if not name.lower().endswith(suffix):
            name += suffix
        out_path = str((self.output_dir / name).resolve())
        inputs = list(self.input_paths)

        self._set_busy(True, 'Goblin packing treasure...')
        self.shell.set_dirty(True)
        self.jobs.submit(self._create_worker, self._on_create_done, out_path, inputs, fmt, level)

    def _create_worker(self, out_path, inputs, fmt, level, progress=None):
        return create_archive(out_path, inputs, format=fmt, level=level)

    def _on_create_done(self, result):
        try:
            if not result.ok:
                self._job_failed('Create archive', result)
                return
            payload = result.value or {}
            archive = payload.get('archive', 'archive')
            self.shell.set_dirty(True)
            self.set_status(f'Created {Path(archive).name}')
            self.show_toast('Archive created')
        finally:
            self._set_busy(False)


def open_tool_window(launcher_root):
    window = tk.Toplevel(launcher_root)
    ZipGoblinWindow(window, launcher_root=launcher_root)
    return window


