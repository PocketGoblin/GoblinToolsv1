from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.rename_goblin import (
    FileItem,
    apply_rename,
    generate_names,
    plan_rename,
    sanitize_name,
    undo_rename,
    validate,
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
    get_pref,
    set_pref,
    get_theme_tokens,
    tool_title,
)


IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tga', '.dds', '.svg'}


class SortGoblinWindow:
    def __init__(self, root, launcher_root=None):
        self.root = root
        self.launcher_root = launcher_root
        self.root.title(tool_title('Sort Goblin', 'rename_goblin'))
        self.root.geometry('1440x900')
        self.root.minsize(1180, 760)
        self.colors = get_theme_tokens()
        self.root.protocol('WM_DELETE_WINDOW', self.back_to_launcher)

        self.jobs = BackgroundJobRunner(self.root)
        self.toast = None
        self._busy = False
        self._busy_controls = []
        self._edit_entry = None
        self._shortcut_tip = None
        self.shortcuts = ShortcutManager()

        self.items: list[FileItem] = []
        self._tree_to_index: dict[str, int] = {}
        self._last_undo_plan: list[tuple[Path, Path]] = []
        self._pref_key = 'rename_goblin.settings'
        prefs = self._load_settings()
        self._hydrating_prefs = True

        self.images_only_var = tk.BooleanVar(value=bool(prefs.get('images_only', False)))
        self.ext_filter_var = tk.StringVar(value=str(prefs.get('ext_filter', '')))
        self.loaded_count_var = tk.StringVar(value='0 files loaded')
        self.base_var = tk.StringVar(value=str(prefs.get('base', 'asset')))
        self.start_var = tk.IntVar(value=int(prefs.get('start', 1)))
        self.pad_var = tk.IntVar(value=int(prefs.get('pad', 3)))
        self.separator_var = tk.StringVar(value=str(prefs.get('separator', '_')))
        self.keep_ext_var = tk.BooleanVar(value=bool(prefs.get('keep_ext', True)))
        self.sanitize_var = tk.BooleanVar(value=bool(prefs.get('sanitize', True)))
        self.find_var = tk.StringVar(value=str(prefs.get('find', '')))
        self.replace_var = tk.StringVar(value=str(prefs.get('replace', '')))
        self.issue_summary_var = tk.StringVar(value='issues: none')

        self._build_ui()
        self._bind_pref_traces()
        self.shortcuts.bind(self.root, '<Control-Return>', self._on_ctrl_enter, description='Apply Rename')
        self.shortcuts.bind(self.root, '<Shift-Tab>', self._on_shortcut_toggle_help, description='Toggle shortcuts help')
        self.shortcuts.bind(self.root, '<ISO_Left_Tab>', self._on_shortcut_toggle_help)
        self.shortcuts.bind(self.root, '<Shift-I>', self._on_shortcut_toggle_inspector, description='Toggle inspector')
        self.shortcuts.bind(self.root, '<Shift-BackSpace>', self._on_shortcut_back_to_launcher, description='Back to launcher (confirm)')
        self.shortcuts.register_help('Double-click New Name cell', 'Edit name')
        self.shortcuts.register_help('Enter (in editor)', 'Commit edit')
        self.shortcuts.register_help('Escape (in editor)', 'Cancel edit')
        self.shortcuts.register_help('Ctrl+A (in editor)', 'Select all text')
        self._hydrating_prefs = False
        self._update_apply_state({'valid': False, 'error_count': 0, 'change_count': 0, 'issues': {}})

    def _load_settings(self) -> dict:
        payload = get_pref(self._pref_key, {})
        return payload if isinstance(payload, dict) else {}

    def _save_settings(self):
        if self._hydrating_prefs:
            return
        try:
            payload = {
                'images_only': bool(self.images_only_var.get()),
                'ext_filter': self.ext_filter_var.get(),
                'base': self.base_var.get(),
                'start': int(self.start_var.get()),
                'pad': int(self.pad_var.get()),
                'separator': self.separator_var.get(),
                'keep_ext': bool(self.keep_ext_var.get()),
                'sanitize': bool(self.sanitize_var.get()),
                'find': self.find_var.get(),
                'replace': self.replace_var.get(),
            }
            set_pref(self._pref_key, payload)
        except Exception:
            pass

    def _bind_pref_traces(self):
        for var in (
            self.images_only_var,
            self.ext_filter_var,
            self.base_var,
            self.start_var,
            self.pad_var,
            self.separator_var,
            self.keep_ext_var,
            self.sanitize_var,
            self.find_var,
            self.replace_var,
        ):
            var.trace_add('write', lambda *_args: self._save_settings())

    def _build_ui(self):
        self.shell = ToolShell(
            self.root,
            title=tool_title('Sort Goblin', 'rename_goblin'),
            title_icon='REN',
            tool_id='rename_goblin',
            colors=self.colors,
            on_back=self.back_to_launcher,
        )
        self.shell.set_rail_actions(
            [
                {'id': 'select_folder', 'label': 'Select Folder', 'icon': '>', 'command': self.select_folder},
                {'id': 'select_files', 'label': 'Select Files', 'icon': '>', 'command': self.select_files},
                {'id': 'reset_all', 'label': 'Reset All', 'icon': '>', 'command': self.reset_all},
                {'id': 'apply', 'label': 'Apply Rename', 'icon': '>', 'command': self.on_apply},
                {'id': 'undo', 'label': 'Undo Last Rename', 'icon': '>', 'command': self.on_undo},
            ]
        )

        workspace = self.shell.main
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(0, weight=1)

        table_surface = ttk.Frame(workspace, style='Surface.TFrame', padding=SURFACE_PAD)
        table_surface.grid(row=0, column=0, sticky='nsew')
        table_surface.columnconfigure(0, weight=1)
        table_surface.rowconfigure(1, weight=1)

        ttk.Label(table_surface, text='Rename Preview', style='Section.TLabel').grid(row=0, column=0, sticky='w')

        table_wrap = ttk.Frame(table_surface, style='Surface.TFrame')
        table_wrap.grid(row=1, column=0, sticky='nsew', pady=(8, 0))
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_wrap,
            columns=('current', 'new', 'status'),
            show='headings',
            selectmode='extended',
        )
        self.tree.heading('current', text='Current Name')
        self.tree.heading('new', text='New Name')
        self.tree.heading('status', text='Status')
        self.tree.column('current', width=420, anchor='w')
        self.tree.column('new', width=420, anchor='w')
        self.tree.column('status', width=220, anchor='w')
        self.tree.tag_configure('row_even', background=self.colors['surface'])
        self.tree.tag_configure('row_odd', background=self.colors['surface_alt'])
        self.tree.tag_configure('invalid', background='#3A1A2A', foreground='#FFD9E7')
        self.tree.tag_configure('no_op', foreground=self.colors['muted'])
        self.tree.grid(row=0, column=0, sticky='nsew')
        self.tree.bind('<Double-1>', self.on_tree_double_click)

        tree_y = ttk.Scrollbar(table_wrap, orient=tk.VERTICAL, command=self.tree.yview)
        tree_x = ttk.Scrollbar(table_wrap, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_y.set, xscrollcommand=tree_x.set)
        tree_y.grid(row=0, column=1, sticky='ns')
        tree_x.grid(row=1, column=0, sticky='ew')

        inspector = self.shell.sidebar
        inspector.columnconfigure(0, weight=1)
        inspector.rowconfigure(9, weight=1)

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
        self.shortcut_hint.bind('<Button-1>', lambda _e: messagebox.showinfo('Sort Goblin Shortcuts', self._shortcut_text()))
        self.status_label = tk.Label(
            status_surface,
            text='Goblin standing by',
            bg=self.colors['surface'],
            fg=self.colors['muted'],
            font=('Segoe UI', 9),
            anchor='w',
            justify=tk.LEFT,
            wraplength=320,
        )
        self.status_label.pack(anchor='w')
        self.busy_bar = ttk.Progressbar(status_surface, orient=tk.HORIZONTAL, mode='indeterminate')
        self.busy_bar.pack(fill=tk.X, pady=(8, 0))
        self.busy_bar.pack_forget()

        ttk.Label(inspector, text='Input', style='Section.TLabel').grid(row=2, column=0, sticky='w')
        input_surface = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        input_surface.grid(row=3, column=0, sticky='ew', pady=(SPACE_8, SECTION_GAP))
        input_surface.columnconfigure(0, weight=1)
        input_surface.columnconfigure(1, weight=1)

        self.select_folder_btn = ttk.Button(input_surface, text='Select Folder', style='Ghost.TButton', command=self.select_folder)
        self.select_folder_btn.grid(row=0, column=0, sticky='ew', padx=(0, 4))
        self.select_files_btn = ttk.Button(input_surface, text='Select Files', style='Ghost.TButton', command=self.select_files)
        self.select_files_btn.grid(row=0, column=1, sticky='ew', padx=(4, 0))
        self.images_only_check = ttk.Checkbutton(input_surface, text='Images only', variable=self.images_only_var)
        self.images_only_check.grid(row=1, column=0, columnspan=2, sticky='w', pady=(8, 0))
        tk.Label(input_surface, text='Extensions', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(
            row=2, column=0, sticky='w', pady=(8, 0)
        )
        self.ext_filter_entry = ttk.Entry(input_surface, textvariable=self.ext_filter_var)
        self.ext_filter_entry.grid(row=2, column=1, sticky='ew', pady=(8, 0))
        tk.Label(
            input_surface,
            text='ex: .png,.json',
            bg=self.colors['surface'],
            fg=self.colors['muted'],
            font=('Segoe UI', 8),
        ).grid(row=3, column=0, columnspan=2, sticky='w', pady=(4, 0))
        tk.Label(input_surface, textvariable=self.loaded_count_var, bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 9)).grid(
            row=4, column=0, columnspan=2, sticky='w', pady=(6, 0)
        )

        ttk.Label(inspector, text='Generate', style='Section.TLabel').grid(row=4, column=0, sticky='w')
        gen_surface = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        gen_surface.grid(row=5, column=0, sticky='ew', pady=(SPACE_8, SECTION_GAP))
        gen_surface.columnconfigure(1, weight=1)

        tk.Label(gen_surface, text='Base', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w')
        self.base_entry = ttk.Entry(gen_surface, textvariable=self.base_var)
        self.base_entry.grid(row=0, column=1, sticky='ew', padx=(8, 0))

        tk.Label(gen_surface, text='Start', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=1, column=0, sticky='w', pady=(8, 0))
        self.start_spin = tk.Spinbox(
            gen_surface,
            from_=0,
            to=999999,
            textvariable=self.start_var,
            width=10,
            bg=self.colors['surface'],
            fg=self.colors['text'],
            insertbackground=self.colors['accent_cyan'],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.colors['stroke'],
            highlightcolor=self.colors['accent_cyan'],
        )
        self.start_spin.grid(row=1, column=1, sticky='w', padx=(8, 0), pady=(8, 0))

        tk.Label(gen_surface, text='Pad', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=2, column=0, sticky='w', pady=(8, 0))
        self.pad_spin = tk.Spinbox(
            gen_surface,
            from_=0,
            to=12,
            textvariable=self.pad_var,
            width=10,
            bg=self.colors['surface'],
            fg=self.colors['text'],
            insertbackground=self.colors['accent_cyan'],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.colors['stroke'],
            highlightcolor=self.colors['accent_cyan'],
        )
        self.pad_spin.grid(row=2, column=1, sticky='w', padx=(8, 0), pady=(8, 0))

        tk.Label(gen_surface, text='Separator', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=3, column=0, sticky='w', pady=(8, 0))
        self.separator_entry = ttk.Entry(gen_surface, textvariable=self.separator_var, width=10)
        self.separator_entry.grid(row=3, column=1, sticky='w', padx=(8, 0), pady=(8, 0))

        self.keep_ext_check = ttk.Checkbutton(gen_surface, text='Preserve extension', variable=self.keep_ext_var)
        self.keep_ext_check.grid(row=4, column=0, columnspan=2, sticky='w', pady=(8, 0))
        self.sanitize_check = ttk.Checkbutton(gen_surface, text='Sanitize names', variable=self.sanitize_var)
        self.sanitize_check.grid(row=5, column=0, columnspan=2, sticky='w', pady=(4, 0))
        self.generate_btn = ttk.Button(gen_surface, text='Preview Generate', style='Ghost.TButton', command=self.on_generate)
        self.generate_btn.grid(row=6, column=0, columnspan=2, sticky='ew', pady=(10, 0))

        ttk.Label(inspector, text='Find/Replace', style='Section.TLabel').grid(row=6, column=0, sticky='w')
        fr_surface = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        fr_surface.grid(row=7, column=0, sticky='ew', pady=(SPACE_8, SECTION_GAP))
        fr_surface.columnconfigure(1, weight=1)
        tk.Label(fr_surface, text='Find', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w')
        self.find_entry = ttk.Entry(fr_surface, textvariable=self.find_var)
        self.find_entry.grid(row=0, column=1, sticky='ew', padx=(8, 0))
        tk.Label(fr_surface, text='Replace', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=1, column=0, sticky='w', pady=(8, 0))
        self.replace_entry = ttk.Entry(fr_surface, textvariable=self.replace_var)
        self.replace_entry.grid(row=1, column=1, sticky='ew', padx=(8, 0), pady=(8, 0))
        self.find_replace_btn = ttk.Button(fr_surface, text='Apply Find/Replace', style='Ghost.TButton', command=self.on_find_replace)
        self.find_replace_btn.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(10, 0))

        ttk.Label(inspector, text='Apply', style='Section.TLabel').grid(row=8, column=0, sticky='w')
        apply_surface = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        apply_surface.grid(row=9, column=0, sticky='nsew')
        apply_surface.columnconfigure(0, weight=1)

        self.apply_btn = ShinyButton(apply_surface, text='Apply Rename', command=self.on_apply, width=260, height=40, colors=self.colors)
        self.apply_btn.grid(row=0, column=0, sticky='ew')
        self.undo_btn = ttk.Button(apply_surface, text='Undo Last Rename', style='Ghost.TButton', command=self.on_undo)
        self.undo_btn.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        self.reset_selected_btn = ttk.Button(apply_surface, text='Reset Selected', style='Ghost.TButton', command=self.reset_selected)
        self.reset_selected_btn.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        self.reset_all_btn = ttk.Button(apply_surface, text='Reset All', style='Ghost.TButton', command=self.reset_all)
        self.reset_all_btn.grid(row=3, column=0, sticky='ew', pady=(8, 0))
        self.copy_invalid_btn = ttk.Button(apply_surface, text='Copy Invalid Rows', style='Ghost.TButton', command=self.copy_invalid_rows)
        self.copy_invalid_btn.grid(row=4, column=0, sticky='ew', pady=(8, 0))
        tk.Label(apply_surface, textvariable=self.issue_summary_var, bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 9), justify=tk.LEFT, wraplength=300).grid(
            row=5, column=0, sticky='w', pady=(8, 0)
        )

        for btn in (
            self.select_folder_btn,
            self.select_files_btn,
            self.generate_btn,
            self.find_replace_btn,
            self.undo_btn,
            self.reset_selected_btn,
            self.reset_all_btn,
            self.copy_invalid_btn,
        ):
            bind_button_feedback(self.root, btn, variant='ghost')
        self.apply_btn.configure(cursor='hand2')

        self._busy_controls = [
            self.select_folder_btn,
            self.select_files_btn,
            self.images_only_check,
            self.ext_filter_entry,
            self.base_entry,
            self.start_spin,
            self.pad_spin,
            self.separator_entry,
            self.keep_ext_check,
            self.sanitize_check,
            self.generate_btn,
            self.find_entry,
            self.replace_entry,
            self.find_replace_btn,
            self.undo_btn,
            self.reset_selected_btn,
            self.reset_all_btn,
            self.copy_invalid_btn,
            self.tree,
        ]
        self.toast = ToastNotifier(self.root, bg=self.colors['toast'], fg=self.colors['text'])

    def back_to_launcher(self):
        self._close_editor()
        self._hide_shortcuts_tooltip()
        self.shortcuts.clear()
        self._save_settings()
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
        return self.shortcuts.help_text()

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
        self._set_widget_state(self.apply_btn, enabled=not busy)
        self.root.configure(cursor='watch' if busy else '')
        if busy:
            self.busy_bar.pack(fill=tk.X, pady=(8, 0))
            self.busy_bar.start(10)
        else:
            self.busy_bar.stop()
            self.busy_bar.pack_forget()
        if message:
            self.set_status(message)

    def _filter_paths(self, paths: list[Path]) -> list[Path]:
        ext_filter = self._parse_extension_filter(self.ext_filter_var.get())
        files = [p.absolute() for p in paths if p.is_file()]
        files = [p for p in files if self._matches_filters(p, bool(self.images_only_var.get()), ext_filter)]
        files.sort(key=lambda p: p.name.casefold())
        return files

    def _parse_extension_filter(self, value: str) -> set[str]:
        out = set()
        for raw in (value or '').split(','):
            ext = raw.strip().lower()
            if not ext:
                continue
            if not ext.startswith('.'):
                ext = f'.{ext}'
            out.add(ext)
        return out

    def _matches_filters(self, path: Path, images_only: bool, ext_filter: set[str]) -> bool:
        suffix = path.suffix.lower()
        if images_only and suffix not in IMAGE_SUFFIXES:
            return False
        if ext_filter and suffix not in ext_filter:
            return False
        return True

    def select_folder(self):
        if self._busy:
            return
        folder = filedialog.askdirectory(title='Select Folder')
        if not folder:
            return
        ext_filter = self._parse_extension_filter(self.ext_filter_var.get())
        self._set_busy(True, 'Goblin scanning folder...')
        self.jobs.submit(self._scan_folder_worker, self._on_scan_done, folder, bool(self.images_only_var.get()), ext_filter)

    def _scan_folder_worker(self, folder, images_only, ext_filter, progress=None):
        root = Path(folder)
        entries = [p for p in root.iterdir() if p.is_file()]
        entries = [p for p in entries if self._matches_filters(p, images_only, set(ext_filter or []))]
        entries.sort(key=lambda p: p.name.casefold())
        return entries

    def _on_scan_done(self, result):
        try:
            if not result.ok:
                if result.tb:
                    print(result.tb)
                messagebox.showerror('Sort Goblin', str(result.error))
                self.set_status('Failed to scan folder')
                return
            self.load_paths(result.value or [])
        finally:
            self._set_busy(False)

    def select_files(self):
        if self._busy:
            return
        selected = filedialog.askopenfilenames(title='Select Files')
        if not selected:
            return
        paths = [Path(p) for p in selected]
        self.load_paths(self._filter_paths(paths))

    def load_paths(self, paths: list[Path]):
        unique_paths = []
        seen = set()
        for path in paths:
            resolved = path.absolute()
            key = str(resolved).casefold()
            if key in seen:
                continue
            seen.add(key)
            unique_paths.append(resolved)
        self.items = [
            FileItem(
                path=path,
                current_name=path.name,
                ext=path.suffix.lower(),
                proposed_name=path.name,
                status='',
            )
            for path in unique_paths
        ]
        self._last_undo_plan = []
        self._revalidate_and_refresh()
        self.show_toast(f'Loaded {len(self.items)} file(s)')

    def on_generate(self):
        if self._busy:
            return
        if not self.items:
            messagebox.showinfo('Sort Goblin', 'Load files first.')
            return
        try:
            generate_names(
                self.items,
                base=self.base_var.get(),
                start_index=int(self.start_var.get()),
                pad_width=int(self.pad_var.get()),
                separator=self.separator_var.get(),
                keep_ext=bool(self.keep_ext_var.get()),
            )
            if self.sanitize_var.get():
                for item in self.items:
                    item.proposed_name = sanitize_name(item.proposed_name)
            self._revalidate_and_refresh()
        except Exception as exc:
            messagebox.showerror('Sort Goblin', f'Failed to generate names.\n{exc}')

    def on_find_replace(self):
        if self._busy:
            return
        if not self.items:
            messagebox.showinfo('Sort Goblin', 'Load files first.')
            return
        needle = self.find_var.get()
        replacement = self.replace_var.get()
        if not needle:
            messagebox.showinfo('Sort Goblin', 'Enter a Find value first.')
            return

        changed = 0
        for item in self.items:
            src_name = item.proposed_name or item.current_name
            stem = Path(src_name).stem
            ext = Path(src_name).suffix
            if needle not in stem:
                continue
            new_stem = stem.replace(needle, replacement)
            new_name = f'{new_stem}{ext}'
            if self.sanitize_var.get():
                new_name = sanitize_name(new_name)
            if new_name != item.proposed_name:
                item.proposed_name = new_name
                changed += 1

        self._revalidate_and_refresh()
        self.show_toast(f'Updated {changed} row(s)')

    def _revalidate_and_refresh(self):
        report = validate(self.items)
        self._refresh_tree()
        self.loaded_count_var.set(f'{len(self.items)} files loaded')
        self._update_apply_state(report)

    def _refresh_tree(self):
        self._close_editor()
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._tree_to_index = {}

        for idx, item in enumerate(self.items):
            iid = f'row_{idx}'
            self._tree_to_index[iid] = idx
            tags = ['row_even' if idx % 2 == 0 else 'row_odd']
            if item.status and item.status != 'no-op':
                tags.append('invalid')
            elif item.status == 'no-op':
                tags.append('no_op')
            self.tree.insert('', tk.END, iid=iid, values=(item.current_name, item.proposed_name, item.status), tags=tuple(tags))

    def _update_apply_state(self, report: dict):
        issues = report.get('issues', {})
        error_count = int(report.get('error_count', 0))
        change_count = int(report.get('change_count', 0))
        duplicate = int(issues.get('duplicate', 0))
        illegal = int(issues.get('illegal', 0))
        reserved = int(issues.get('reserved', 0))
        exists = int(issues.get('exists', 0))
        empty = int(issues.get('empty', 0))
        self.issue_summary_var.set(
            f'issues: dup {duplicate}, illegal {illegal}, reserved {reserved}, exists {exists}, empty {empty}'
        )
        can_apply = bool(report.get('valid')) and change_count > 0 and not self._busy
        self._set_widget_state(self.apply_btn, can_apply)
        self.undo_btn.configure(state=('normal' if (self._last_undo_plan and not self._busy) else 'disabled'))
        self.shell.set_dirty(change_count > 0)

        if not self.items:
            self.set_status('Load files to begin.')
            return
        if error_count > 0:
            details = []
            for key in ('duplicate', 'illegal', 'reserved', 'exists', 'empty'):
                count = int(issues.get(key, 0))
                if count:
                    details.append(f'{key}:{count}')
            detail_text = ', '.join(details) if details else 'validation errors'
            self.set_status(f'{error_count} issue(s): {detail_text}')
            return
        no_op = int(issues.get('no_op', 0))
        self.set_status(f'Ready: {change_count} rename(s), {no_op} unchanged')

    def on_tree_double_click(self, event):
        if self._busy:
            return
        region = self.tree.identify('region', event.x, event.y)
        if region != 'cell':
            return
        column = self.tree.identify_column(event.x)
        if column != '#2':
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self._begin_edit(iid)

    def _begin_edit(self, iid):
        self._close_editor()
        idx = self._tree_to_index.get(iid)
        if idx is None:
            return
        bbox = self.tree.bbox(iid, 'new')
        if not bbox:
            return
        x, y, width, height = bbox
        current_value = self.items[idx].proposed_name

        entry = ttk.Entry(self.tree)
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, current_value)
        entry.focus_set()
        entry.selection_range(0, tk.END)
        self._edit_entry = entry

        def commit(_event=None):
            if self._edit_entry is not entry:
                return
            new_value = entry.get()
            if self.sanitize_var.get():
                new_value = sanitize_name(new_value)
            self.items[idx].proposed_name = new_value
            self._close_editor()
            self._revalidate_and_refresh()

        def cancel(_event=None):
            if self._edit_entry is not entry:
                return
            self._close_editor()

        entry.bind('<Return>', commit)
        entry.bind('<Escape>', cancel)
        entry.bind('<FocusOut>', commit)
        entry.bind('<Control-a>', lambda _e: (entry.selection_range(0, tk.END), 'break')[1])

    def _close_editor(self):
        if self._edit_entry is not None:
            try:
                self._edit_entry.destroy()
            except Exception:
                pass
            self._edit_entry = None

    def on_apply(self):
        if self._busy:
            return
        if not self.items:
            messagebox.showinfo('Sort Goblin', 'Load files first.')
            return
        report = validate(self.items)
        self._refresh_tree()
        self._update_apply_state(report)
        if not report.get('valid'):
            messagebox.showerror('Sort Goblin', 'Resolve validation issues before applying.')
            return
        plan = plan_rename(self.items)
        if not plan:
            messagebox.showinfo('Sort Goblin', 'No file changes to apply.')
            return
        no_op = int(report.get('issues', {}).get('no_op', 0))
        if not messagebox.askyesno(
            'Sort Goblin',
            f'Apply {len(plan)} rename(s)?\nUnchanged rows: {no_op}',
        ):
            return
        self._set_busy(True, f'Applying {len(plan)} rename(s)...')
        self.jobs.submit(self._apply_worker, self._on_apply_done, plan)

    def _on_ctrl_enter(self, _event=None):
        self.on_apply()
        return 'break'

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

    def _apply_worker(self, rename_plan, progress=None):
        undo_plan = apply_rename(rename_plan)
        return {'undo_plan': undo_plan}

    def _on_apply_done(self, result):
        try:
            if not result.ok:
                if result.tb:
                    print(result.tb)
                messagebox.showerror('Sort Goblin', str(result.error))
                self.set_status('Rename failed')
                return
            undo_plan = (result.value or {}).get('undo_plan', [])
            self._last_undo_plan = list(undo_plan)
            old_to_new = {str(old.absolute()): new.absolute() for new, old in undo_plan}
            for item in self.items:
                src = str(item.path.absolute())
                if src in old_to_new:
                    new_path = old_to_new[src]
                    item.path = new_path
                    item.current_name = new_path.name
                    item.ext = new_path.suffix.lower()
                    item.proposed_name = new_path.name
                    item.status = ''

            self._revalidate_and_refresh()
            self.show_toast('Rename applied')
        finally:
            self._set_busy(False)

    def on_undo(self):
        if self._busy:
            return
        if not self._last_undo_plan:
            messagebox.showinfo('Sort Goblin', 'Nothing to undo.')
            return
        self._set_busy(True, 'Undoing last rename...')
        self.jobs.submit(self._undo_worker, self._on_undo_done, list(self._last_undo_plan))

    def reset_selected(self):
        if self._busy or not self.items:
            return
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo('Sort Goblin', 'Select one or more rows first.')
            return
        count = 0
        for iid in selection:
            idx = self._tree_to_index.get(iid)
            if idx is None:
                continue
            item = self.items[idx]
            item.proposed_name = item.current_name
            item.status = ''
            count += 1
        self._revalidate_and_refresh()
        self.show_toast(f'Reset {count} row(s)')

    def reset_all(self):
        if self._busy or not self.items:
            return
        for item in self.items:
            item.proposed_name = item.current_name
            item.status = ''
        self._revalidate_and_refresh()
        self.show_toast('Reset all rows')

    def copy_invalid_rows(self):
        invalid = [it for it in self.items if it.status and it.status != 'no-op']
        if not invalid:
            messagebox.showinfo('Sort Goblin', 'No invalid rows to copy.')
            return
        lines = [f'{it.current_name} -> {it.proposed_name} [{it.status}]' for it in invalid]
        payload = '\n'.join(lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(payload)
        self.root.update_idletasks()
        self.set_status(f'Copied {len(invalid)} invalid row(s)')
        self.show_toast('Invalid rows copied')

    def _undo_worker(self, undo_plan, progress=None):
        redo_plan = undo_rename(undo_plan)
        return {'undo_input': undo_plan, 'redo_plan': redo_plan}

    def _on_undo_done(self, result):
        try:
            if not result.ok:
                if result.tb:
                    print(result.tb)
                messagebox.showerror('Sort Goblin', str(result.error))
                self.set_status('Undo failed')
                return
            undo_input = (result.value or {}).get('undo_input', [])
            path_back_map = {str(src.absolute()): dst.absolute() for src, dst in undo_input}
            for item in self.items:
                src = str(item.path.absolute())
                if src in path_back_map:
                    restored = path_back_map[src]
                    item.path = restored
                    item.current_name = restored.name
                    item.ext = restored.suffix.lower()
                    item.proposed_name = restored.name
                    item.status = ''
            self._last_undo_plan = []
            self._revalidate_and_refresh()
            self.show_toast('Undo complete')
        finally:
            self._set_busy(False)

    def destroy(self):
        self._save_settings()
        self._close_editor()
        self._hide_shortcuts_tooltip()
        self.shortcuts.clear()


def open_tool_window(launcher_root):
    window = tk.Toplevel(launcher_root)
    SortGoblinWindow(window, launcher_root=launcher_root)
    return window


# Backward compatibility during transition.
RenameGoblinWindow = SortGoblinWindow


