from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.sort_goblin import (
    CATEGORY_ORDER,
    FileEntry,
    OperationPlan,
    apply_plan,
    build_rename_plan,
    build_sort_plan,
    build_sort_then_rename_plan,
    categorize,
    undo_plan,
    validate_plan,
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
    get_pref,
    is_dnd_disabled,
    set_pref,
    get_theme_tokens,
    tool_title,
)


class SortGoblinWindow:
    def __init__(self, root, launcher_root=None):
        self.root = root
        self.launcher_root = launcher_root
        self.root.title(tool_title('Sort Goblin', 'sort_goblin'))
        self.root.geometry('1440x900')
        self.root.minsize(1180, 760)
        self.colors = get_theme_tokens()
        self.root.protocol('WM_DELETE_WINDOW', self._on_window_close_request)

        self.jobs = BackgroundJobRunner(self.root)
        self.toast = None
        self._busy = False
        self._busy_controls = []
        self._shortcut_tip = None
        self.shortcuts = ShortcutManager()

        self._pref_key = 'sort_goblin.settings'
        prefs = self._load_settings()
        self._hydrating_prefs = True

        self.selected_dir: Path | None = None
        self.current_plan: OperationPlan | None = None
        self.current_errors: list[str] = []
        self.preview_ready = False
        self.last_undo_mapping: list[tuple[Path, Path]] = []

        self.selected_path_var = tk.StringVar(value='No folder selected')
        self.folder_note_var = tk.StringVar(value='Top-level files only. Subfolders will not be modified.')
        self.summary_var = tk.StringVar(value='No preview yet.')
        self.mode_var = tk.StringVar(value=str(prefs.get('mode', 'sort')))
        self.include_optional_var = tk.BooleanVar(value=bool(prefs.get('include_optional_categories', True)))
        self.base_var = tk.StringVar(value=str(prefs.get('base', 'asset')))
        self.start_var = tk.IntVar(value=int(prefs.get('start_index', 1)))
        self.pad_var = tk.IntVar(value=int(prefs.get('pad_width', 3)))
        self.separator_var = tk.StringVar(value=str(prefs.get('separator', '_')))
        self.preserve_ext_var = tk.BooleanVar(value=bool(prefs.get('preserve_extension', True)))
        self.sanitize_var = tk.BooleanVar(value=bool(prefs.get('sanitize', True)))

        self._build_ui()
        self._bind_pref_traces()
        self.shortcuts.bind(self.root, '<Shift-Tab>', self._on_shortcut_toggle_help, description='Toggle shortcuts help')
        self.shortcuts.bind(self.root, '<ISO_Left_Tab>', self._on_shortcut_toggle_help)
        self.shortcuts.bind(self.root, '<Shift-I>', self._on_shortcut_toggle_inspector, description='Toggle inspector')
        self.shortcuts.bind(self.root, '<Shift-BackSpace>', self._on_shortcut_back_to_launcher, description='Back to launcher (confirm)')
        self.shortcuts.register_help('Drag folder into preview', 'Load folder')
        self._hydrating_prefs = False
        self._refresh_mode_sections()
        self._update_apply_state()

    def _load_settings(self) -> dict:
        payload = get_pref(self._pref_key, {})
        return payload if isinstance(payload, dict) else {}

    def _save_settings(self):
        if self._hydrating_prefs:
            return
        try:
            set_pref(
                self._pref_key,
                {
                    'mode': self.mode_var.get(),
                    'include_optional_categories': bool(self.include_optional_var.get()),
                    'base': self.base_var.get(),
                    'start_index': int(self.start_var.get()),
                    'pad_width': int(self.pad_var.get()),
                    'separator': self.separator_var.get(),
                    'preserve_extension': bool(self.preserve_ext_var.get()),
                    'sanitize': bool(self.sanitize_var.get()),
                },
            )
        except Exception:
            pass

    def _bind_pref_traces(self):
        for var in (
            self.mode_var,
            self.include_optional_var,
            self.base_var,
            self.start_var,
            self.pad_var,
            self.separator_var,
            self.preserve_ext_var,
            self.sanitize_var,
        ):
            var.trace_add('write', lambda *_args: self._save_settings())

    def _build_ui(self):
        self.shell = ToolShell(
            self.root,
            title=tool_title('Sort Goblin', 'sort_goblin'),
            title_icon='SRT',
            tool_id='sort_goblin',
            colors=self.colors,
            on_back=self.back_to_launcher,
        )
        self.shell.set_rail_actions(
            [
                {'id': 'select_folder', 'label': 'Select Folder', 'icon': '>', 'command': self.select_folder},
                {'id': 'preview', 'label': 'Preview', 'icon': '>', 'command': self.on_preview},
                {'id': 'apply', 'label': 'Apply', 'icon': '>', 'command': self.on_apply},
                {'id': 'undo', 'label': 'Undo Last', 'icon': '>', 'command': self.on_undo},
            ]
        )

        workspace = self.shell.main
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(0, weight=1)

        table_surface = ttk.Frame(workspace, style='Surface.TFrame', padding=SURFACE_PAD)
        table_surface.grid(row=0, column=0, sticky='nsew')
        table_surface.columnconfigure(0, weight=1)
        table_surface.rowconfigure(1, weight=1)

        ttk.Label(table_surface, text='Sort Preview', style='Section.TLabel').grid(row=0, column=0, sticky='w')

        table_wrap = ttk.Frame(table_surface, style='Surface.TFrame')
        table_wrap.grid(row=1, column=0, sticky='nsew', pady=(8, 0))
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_wrap,
            columns=('current', 'proposed', 'action', 'status'),
            show='headings',
            selectmode='extended',
        )
        self.tree.heading('current', text='Current')
        self.tree.heading('proposed', text='Proposed')
        self.tree.heading('action', text='Action')
        self.tree.heading('status', text='Status')
        self.tree.column('current', width=420, anchor='w')
        self.tree.column('proposed', width=420, anchor='w')
        self.tree.column('action', width=140, anchor='w')
        self.tree.column('status', width=220, anchor='w')
        self.tree.tag_configure('row_even', background=self.colors['surface'])
        self.tree.tag_configure('row_odd', background=self.colors['surface_alt'])
        self.tree.tag_configure('warn', background='#3A1A2A', foreground='#FFD9E7')
        self.tree.grid(row=0, column=0, sticky='nsew')

        tree_y = ttk.Scrollbar(table_wrap, orient=tk.VERTICAL, command=self.tree.yview)
        tree_x = ttk.Scrollbar(table_wrap, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_y.set, xscrollcommand=tree_x.set)
        tree_y.grid(row=0, column=1, sticky='ns')
        tree_x.grid(row=1, column=0, sticky='ew')
        self._enable_folder_drop([table_surface, table_wrap, self.tree])

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
        self.status_label = tk.Label(status_surface, text='Goblin standing by', bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 9), anchor='w', justify=tk.LEFT, wraplength=320)
        self.status_label.pack(anchor='w')
        self.busy_bar = ttk.Progressbar(status_surface, orient=tk.HORIZONTAL, mode='indeterminate')
        self.busy_bar.pack(fill=tk.X, pady=(8, 0))
        self.busy_bar.pack_forget()

        ttk.Label(inspector, text='Input', style='Section.TLabel').grid(row=2, column=0, sticky='w')
        input_surface = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        input_surface.grid(row=3, column=0, sticky='ew', pady=(SPACE_8, SECTION_GAP))
        input_surface.columnconfigure(0, weight=1)
        self.select_folder_btn = ttk.Button(input_surface, text='Select Folder', style='Ghost.TButton', command=self.select_folder)
        self.select_folder_btn.grid(row=0, column=0, sticky='ew')
        tk.Label(input_surface, textvariable=self.selected_path_var, bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 8), justify=tk.LEFT, wraplength=320).grid(row=1, column=0, sticky='w', pady=(8, 0))
        tk.Label(input_surface, textvariable=self.folder_note_var, bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 8), justify=tk.LEFT, wraplength=320).grid(row=2, column=0, sticky='w', pady=(4, 0))
        tk.Label(input_surface, textvariable=self.summary_var, bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9), justify=tk.LEFT, wraplength=320).grid(row=3, column=0, sticky='w', pady=(8, 0))

        ttk.Label(inspector, text='Mode', style='Section.TLabel').grid(row=4, column=0, sticky='w')
        mode_surface = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        mode_surface.grid(row=5, column=0, sticky='ew', pady=(SPACE_8, SECTION_GAP))
        ttk.Radiobutton(mode_surface, text='Sort only', value='sort', variable=self.mode_var, command=self._on_mode_change).grid(row=0, column=0, sticky='w')
        ttk.Radiobutton(mode_surface, text='Rename only', value='rename', variable=self.mode_var, command=self._on_mode_change).grid(row=1, column=0, sticky='w', pady=(6, 0))
        ttk.Radiobutton(mode_surface, text='Sort + Rename', value='sort_rename', variable=self.mode_var, command=self._on_mode_change).grid(row=2, column=0, sticky='w', pady=(6, 0))

        self.sort_opts_frame = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        self.sort_opts_frame.grid(row=6, column=0, sticky='ew', pady=(SPACE_8, SECTION_GAP))
        ttk.Label(self.sort_opts_frame, text='Sort Options', style='Section.TLabel').grid(row=0, column=0, sticky='w')
        tk.Label(self.sort_opts_frame, text='Top-level only (no recursion)', bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 8)).grid(row=1, column=0, sticky='w', pady=(6, 0))
        self.include_optional_check = ttk.Checkbutton(self.sort_opts_frame, text='Include Archives/Code/Audio categories', variable=self.include_optional_var)
        self.include_optional_check.grid(row=2, column=0, sticky='w', pady=(8, 0))

        self.rename_opts_frame = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        self.rename_opts_frame.grid(row=7, column=0, sticky='ew', pady=(SPACE_8, SECTION_GAP))
        self.rename_opts_frame.columnconfigure(1, weight=1)
        ttk.Label(self.rename_opts_frame, text='Rename Options', style='Section.TLabel').grid(row=0, column=0, columnspan=2, sticky='w')
        tk.Label(self.rename_opts_frame, text='Base', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=1, column=0, sticky='w', pady=(8, 0))
        self.base_entry = ttk.Entry(self.rename_opts_frame, textvariable=self.base_var)
        self.base_entry.grid(row=1, column=1, sticky='ew', padx=(8, 0), pady=(8, 0))
        tk.Label(self.rename_opts_frame, text='Start', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=2, column=0, sticky='w', pady=(8, 0))
        self.start_spin = tk.Spinbox(
            self.rename_opts_frame,
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
        self.start_spin.grid(row=2, column=1, sticky='w', padx=(8, 0), pady=(8, 0))
        tk.Label(self.rename_opts_frame, text='Pad', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=3, column=0, sticky='w', pady=(8, 0))
        self.pad_spin = tk.Spinbox(
            self.rename_opts_frame,
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
        self.pad_spin.grid(row=3, column=1, sticky='w', padx=(8, 0), pady=(8, 0))
        tk.Label(self.rename_opts_frame, text='Separator', bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=4, column=0, sticky='w', pady=(8, 0))
        self.separator_entry = ttk.Entry(self.rename_opts_frame, textvariable=self.separator_var, width=10)
        self.separator_entry.grid(row=4, column=1, sticky='w', padx=(8, 0), pady=(8, 0))
        self.preserve_ext_check = ttk.Checkbutton(self.rename_opts_frame, text='Preserve extension', variable=self.preserve_ext_var)
        self.preserve_ext_check.grid(row=5, column=0, columnspan=2, sticky='w', pady=(8, 0))
        self.sanitize_check = ttk.Checkbutton(self.rename_opts_frame, text='Sanitize names', variable=self.sanitize_var)
        self.sanitize_check.grid(row=6, column=0, columnspan=2, sticky='w', pady=(4, 0))

        ttk.Label(inspector, text='Apply', style='Section.TLabel').grid(row=8, column=0, sticky='w')
        apply_surface = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        apply_surface.grid(row=9, column=0, sticky='nsew')
        apply_surface.columnconfigure(0, weight=1)
        self.preview_btn = ttk.Button(apply_surface, text='Preview', style='Ghost.TButton', command=self.on_preview)
        self.preview_btn.grid(row=0, column=0, sticky='ew')
        self.apply_btn = ShinyButton(apply_surface, text='Apply', command=self.on_apply, width=260, height=40, colors=self.colors)
        self.apply_btn.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        self.undo_btn = ttk.Button(apply_surface, text='Undo Last', style='Ghost.TButton', command=self.on_undo)
        self.undo_btn.grid(row=2, column=0, sticky='ew', pady=(8, 0))

        for btn in (self.select_folder_btn, self.preview_btn, self.undo_btn):
            self._bind_ghost_feedback(btn)
        self.apply_btn.configure(cursor='hand2')

        self._busy_controls = [
            self.select_folder_btn,
            self.preview_btn,
            self.undo_btn,
            self.tree,
            self.include_optional_check,
            self.base_entry,
            self.start_spin,
            self.pad_spin,
            self.separator_entry,
            self.preserve_ext_check,
            self.sanitize_check,
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
        frame = tk.Frame(tip, bg=self.colors['surface_alt'], padx=8, pady=6, highlightthickness=1, highlightbackground=self.colors['accent_cyan'])
        frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(frame, text=self._shortcut_text(), bg=self.colors['surface_alt'], fg=self.colors['text'], font=('Segoe UI', 8), justify=tk.LEFT, anchor='w').pack(anchor='w')
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

    def _on_window_close_request(self):
        if self.shell.confirm._navigate_away():
            self.back_to_launcher()

    def back_to_launcher(self):
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

    def _refresh_mode_sections(self):
        mode = self.mode_var.get().strip().lower()
        if mode in ('sort', 'sort_rename'):
            self.sort_opts_frame.grid()
        else:
            self.sort_opts_frame.grid_remove()
        if mode in ('rename', 'sort_rename'):
            self.rename_opts_frame.grid()
        else:
            self.rename_opts_frame.grid_remove()
        self.preview_ready = False
        self.current_plan = None
        self.current_errors = []
        self._update_apply_state()

    def _on_mode_change(self):
        self._refresh_mode_sections()

    def _set_selected_dir(self, directory: Path, source_label: str = 'Folder selected', auto_preview: bool = True):
        self.selected_dir = directory.resolve()
        self.selected_path_var.set(str(self.selected_dir))
        self.preview_ready = False
        self.current_plan = None
        self.current_errors = []
        self.summary_var.set('Folder selected. Generating preview...')
        self._populate_preview([])
        self._update_apply_state()
        self.set_status(source_label)
        if auto_preview and not self._busy:
            self.on_preview()

    def select_folder(self):
        if self._busy:
            return
        folder = filedialog.askdirectory(title='Select Folder')
        if not folder:
            return
        self._set_selected_dir(Path(folder), source_label='Folder selected')

    def _enable_folder_drop(self, widgets: list[tk.Widget]):
        if is_dnd_disabled():
            return
        try:
            self.root.tk.call('package', 'require', 'tkdnd')
        except Exception:
            return
        cmd = self.root.register(self._on_drop_data)
        for widget in widgets:
            try:
                widget.tk.call('tkdnd::drop_target', 'register', widget._w, 'DND_Files')
                widget.tk.call('bind', widget._w, '<<Drop>>', f'{cmd} %D')
            except Exception:
                pass

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

    def _on_drop_data(self, raw_data: str):
        if self._busy:
            return 'break'
        dropped = self._parse_dropped_paths(raw_data)
        folders = [p for p in dropped if p.exists() and p.is_dir()]
        if not folders:
            self.show_toast('Drop a folder to load it')
            self.set_status('Drop ignored: no folder found')
            return 'break'
        target = folders[0]
        self._set_selected_dir(target, source_label='Folder dropped')
        ignored = max(0, len(dropped) - 1)
        if ignored:
            self.show_toast(f'Loaded first folder, ignored {ignored} extra item(s)')
        return 'break'


    def _build_plan_worker(self, selected_dir, mode, include_optional, rename_options, progress=None):
        root = Path(selected_dir)
        if mode == 'sort':
            plan = build_sort_plan(root, include_optional_categories=include_optional)
        elif mode == 'rename':
            files = [p for p in root.iterdir() if p.is_file()]
            files.sort(key=lambda p: p.name.casefold())
            entries = [
                FileEntry(path=p, name=p.name, ext=p.suffix.lower(), category=categorize(p, include_optional_categories=True), proposed_path=p, status='', action='')
                for p in files
            ]
            plan = build_rename_plan(entries, rename_options)
        else:
            opts = dict(rename_options)
            opts['include_optional_categories'] = include_optional
            plan = build_sort_then_rename_plan(root, opts)
        ok, errors = validate_plan(plan)
        return {'plan': plan, 'ok': ok, 'errors': errors}

    def on_preview(self):
        if self._busy:
            return
        if self.selected_dir is None:
            messagebox.showinfo('Sort Goblin', 'Select a folder first.')
            return
        mode = self.mode_var.get().strip().lower()
        rename_options = {
            'base': self.base_var.get(),
            'start_index': int(self.start_var.get()),
            'pad_width': int(self.pad_var.get()),
            'separator': self.separator_var.get(),
            'preserve_extension': bool(self.preserve_ext_var.get()),
            'sanitize': bool(self.sanitize_var.get()),
        }
        self._set_busy(True, 'Goblin organizing mess (preview)...')
        self.jobs.submit(
            self._build_plan_worker,
            self._on_preview_done,
            str(self.selected_dir),
            mode,
            bool(self.include_optional_var.get()),
            rename_options,
        )

    def _format_counts(self, counts: dict[str, int]) -> str:
        parts = []
        for category in CATEGORY_ORDER:
            count = int(counts.get(category, 0))
            if count > 0:
                parts.append(f'{category} ({count})')
        return ', '.join(parts) if parts else 'No files found.'

    def _to_relative(self, path: Path) -> str:
        if self.selected_dir is None:
            return str(path)
        try:
            return str(path.resolve().relative_to(self.selected_dir.resolve()))
        except Exception:
            return str(path)

    def _populate_preview(self, entries: list[FileEntry]):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for idx, entry in enumerate(entries):
            tags = ['row_even' if idx % 2 == 0 else 'row_odd']
            if entry.status:
                tags.append('warn')
            self.tree.insert(
                '',
                tk.END,
                values=(
                    self._to_relative(entry.path),
                    self._to_relative(entry.proposed_path),
                    entry.action,
                    entry.status,
                ),
                tags=tuple(tags),
            )

    def _on_preview_done(self, result):
        try:
            if not result.ok:
                if result.tb:
                    print(result.tb)
                messagebox.showerror('Sort Goblin', str(result.error))
                self.set_status('Preview failed')
                self.preview_ready = False
                self.current_plan = None
                self.current_errors = [str(result.error)]
                self._update_apply_state()
                return

            payload = result.value or {}
            plan = payload.get('plan')
            ok = bool(payload.get('ok'))
            errors = list(payload.get('errors') or [])
            self.current_plan = plan
            self.current_errors = errors
            self.preview_ready = True
            self._populate_preview(plan.entries if plan else [])
            if plan and plan.mode in ('sort', 'sort_rename'):
                self.summary_var.set(self._format_counts(plan.category_counts))
            else:
                self.summary_var.set(f'{len(plan.moves) if plan else 0} rename move(s) planned.')
            if not ok and errors:
                self.set_status(f'Preview has {len(errors)} validation issue(s)')
            else:
                self.set_status(f'Preview ready: {len(plan.moves) if plan else 0} operations')
            self._update_apply_state()
        finally:
            self._set_busy(False)

    def _update_apply_state(self):
        can_apply = bool(self.selected_dir and self.preview_ready and self.current_plan and not self.current_errors and self.current_plan.moves and not self._busy)
        self._set_widget_state(self.apply_btn, can_apply)
        self.undo_btn.configure(state=('normal' if (self.last_undo_mapping and not self._busy) else 'disabled'))
        dirty = bool(self.preview_ready or self.last_undo_mapping)
        self.shell.set_dirty(dirty)

    def on_apply(self):
        if self._busy:
            return
        if self.selected_dir is None:
            messagebox.showinfo('Sort Goblin', 'Select a folder first.')
            return
        if not self.preview_ready or self.current_plan is None:
            self.on_preview()
            return
        if self.current_errors:
            messagebox.showerror('Sort Goblin', '\n'.join(self.current_errors[:5]))
            return
        if not self.current_plan.moves:
            messagebox.showinfo('Sort Goblin', 'No operations to apply.')
            return
        if not messagebox.askyesno('Sort Goblin', f'Apply {len(self.current_plan.moves)} operation(s)?'):
            return
        self._set_busy(True, 'Goblin organizing mess...')
        self.jobs.submit(self._apply_worker, self._on_apply_done, self.current_plan)

    def _apply_worker(self, plan: OperationPlan, progress=None):
        undo_mapping = apply_plan(plan)
        return {'undo_mapping': undo_mapping}

    def _on_apply_done(self, result):
        try:
            if not result.ok:
                if result.tb:
                    print(result.tb)
                messagebox.showerror('Sort Goblin', str(result.error))
                self.set_status('Apply failed')
                return
            payload = result.value or {}
            self.last_undo_mapping = list(payload.get('undo_mapping') or [])
            self.preview_ready = False
            self.current_plan = None
            self.current_errors = []
            self._populate_preview([])
            self.summary_var.set('Applied. Preview again to inspect current state.')
            self.show_toast('Operation applied')
            self.set_status('Apply complete')
        finally:
            self._set_busy(False)
            self._update_apply_state()

    def on_undo(self):
        if self._busy:
            return
        if not self.last_undo_mapping:
            messagebox.showinfo('Sort Goblin', 'Nothing to undo.')
            return
        self._set_busy(True, 'Goblin undoing last operation...')
        self.jobs.submit(self._undo_worker, self._on_undo_done, list(self.last_undo_mapping))

    def _undo_worker(self, mapping, progress=None):
        redo = undo_plan(mapping)
        return {'redo': redo}

    def _on_undo_done(self, result):
        try:
            if not result.ok:
                if result.tb:
                    print(result.tb)
                messagebox.showerror('Sort Goblin', str(result.error))
                self.set_status('Undo failed')
                return
            self.last_undo_mapping = []
            self.preview_ready = False
            self.current_plan = None
            self.current_errors = []
            self._populate_preview([])
            self.summary_var.set('Undo complete. Preview again.')
            self.show_toast('Undo complete')
            self.set_status('Undo complete')
        finally:
            self._set_busy(False)
            self._update_apply_state()


def open_tool_window(launcher_root):
    window = tk.Toplevel(launcher_root)
    SortGoblinWindow(window, launcher_root=launcher_root)
    return window


