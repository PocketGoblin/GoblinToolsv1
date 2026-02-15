from __future__ import annotations

import re
import tkinter as tk
import urllib.parse
import webbrowser
from tkinter import ttk, messagebox

from core.error_goblin import ExplanationResult
from core.error_goblin.ai_client import AI_CONTEXT_CHAR_LIMIT
from core.error_goblin.explain import safe_explain_error
from core.error_goblin.parser import detect_engine
from goblintools.common import (
    BackgroundJobRunner,
    SECTION_GAP,
    SPACE_8,
    ShortcutManager,
    SURFACE_PAD,
    ShinyButton,
    ToolShell,
    ToastNotifier,
    get_theme_tokens,
    is_safe_mode,
    tool_title,
)

PATH_RE = re.compile(r'([A-Za-z]:\\[^:\n]+|/[^:\n]+)')
LINE_NO_RE = re.compile(r'(:\d+)(:\d+)?')


class ErrorGoblinWindow:
    def __init__(self, root, launcher_root=None):
        self.root = root
        self.launcher_root = launcher_root
        self.root.title(tool_title('Error Goblin', 'error_goblin'))
        self.root.geometry('1440x900')
        self.root.minsize(1180, 760)
        self.colors = get_theme_tokens()
        self.root.protocol('WM_DELETE_WINDOW', self.back_to_launcher)

        self.jobs = BackgroundJobRunner(self.root)
        self.toast = None
        self._busy = False
        self._busy_controls = []
        self._shortcut_tip = None
        self._search_menu = None
        self.shortcuts = ShortcutManager()
        self._safe_mode = is_safe_mode()

        self.engine_auto_var = tk.StringVar(value='unknown')
        self.engine_override_var = tk.StringVar(value='auto')
        self.use_ai_var = tk.BooleanVar(value=not self._safe_mode)
        self.summary_var = tk.StringVar(value='Paste an error and click Explain.')
        self.means_var = tk.StringVar(value='-')
        self.cause_var = tk.StringVar(value='-')
        self.step_var = tk.StringVar(value='-')
        self.conf_var = tk.StringVar(value='-')
        self.source_var = tk.StringVar(value='-')

        self._build_ui()
        self.shell.set_dirty(False)
        self.shortcuts.bind(self.root, '<Shift-Tab>', self._on_shortcut_toggle_help, description='Toggle shortcuts help')
        self.shortcuts.bind(self.root, '<ISO_Left_Tab>', self._on_shortcut_toggle_help)
        self.shortcuts.bind(self.root, '<Shift-I>', self._on_shortcut_toggle_inspector, description='Toggle inspector')
        self.shortcuts.bind(self.root, '<Shift-BackSpace>', self._on_shortcut_back_to_launcher, description='Back to launcher (confirm)')
        self.shortcuts.register_help('Ctrl+Shift+F', 'Search selected text in browser')
        self.shortcuts.register_help('Right-click editor', 'Search selected text')
        if self._safe_mode:
            self.shortcuts.register_help('Safe mode', 'AI fallback disabled')

    def _build_ui(self):
        self.shell = ToolShell(
            self.root,
            title=tool_title('Error Goblin', 'error_goblin'),
            title_icon='ERR',
            tool_id='error_goblin',
            colors=self.colors,
            on_back=self.back_to_launcher,
        )
        self.shell.set_rail_actions(
            [
                {'id': 'explain', 'label': 'Explain Error', 'icon': '>', 'command': self.on_explain},
                {'id': 'copy_report', 'label': 'Copy Full Report', 'icon': '>', 'command': self.copy_full_report},
                {'id': 'clear', 'label': 'Clear', 'icon': '>', 'command': self.clear_text},
            ]
        )

        workspace = self.shell.main
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(1, weight=1)

        top = ttk.Frame(workspace, style='Surface.TFrame', padding=SURFACE_PAD)
        top.grid(row=0, column=0, sticky='ew')
        top.columnconfigure(0, weight=1)
        ttk.Label(top, text='Paste Error Log', style='Section.TLabel').grid(row=0, column=0, sticky='w')

        self.clear_btn = ttk.Button(top, text='Clear', style='Ghost.TButton', command=self.clear_text)
        self.clear_btn.grid(row=0, column=1, sticky='e')
        self.explain_btn = ShinyButton(top, text='Explain', command=self.on_explain, width=170, height=36, colors=self.colors)
        self.explain_btn.grid(row=0, column=2, sticky='e', padx=(8, 0))
        self.explain_btn.configure(cursor='hand2')
        self._bind_ghost_feedback(self.clear_btn)

        editor_surface = ttk.Frame(workspace, style='Surface.TFrame', padding=(SURFACE_PAD, 0, SURFACE_PAD, SURFACE_PAD))
        editor_surface.grid(row=1, column=0, sticky='nsew')
        editor_surface.columnconfigure(0, weight=1)
        editor_surface.rowconfigure(0, weight=1)

        self.text = tk.Text(
            editor_surface,
            wrap=tk.WORD,
            bg=self.colors['surface'],
            fg=self.colors['text'],
            insertbackground=self.colors['accent_cyan'],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.colors['stroke'],
            highlightcolor=self.colors['accent_cyan'],
            font=('Consolas', 10),
            padx=10,
            pady=10,
        )
        self.text.grid(row=0, column=0, sticky='nsew')
        self.text.bind('<KeyRelease>', self._on_text_change)
        self._attach_search_actions(self.text, status_cb=self.set_status)
        yscroll = ttk.Scrollbar(editor_surface, orient=tk.VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky='ns')

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
        self.shortcut_hint.bind('<Button-1>', lambda _e: messagebox.showinfo('Error Goblin Shortcuts', self._shortcut_text()))
        self.status_label = tk.Label(status_surface, text='Goblin standing by', bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 9), anchor='w', justify=tk.LEFT, wraplength=320)
        self.status_label.pack(anchor='w')
        self.busy_bar = ttk.Progressbar(status_surface, orient=tk.HORIZONTAL, mode='indeterminate')
        self.busy_bar.pack(fill=tk.X, pady=(8, 0))
        self.busy_bar.pack_forget()

        ttk.Label(inspector, text='Engine', style='Section.TLabel').grid(row=2, column=0, sticky='w')
        engine_surface = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        engine_surface.grid(row=3, column=0, sticky='ew', pady=(SPACE_8, SECTION_GAP))
        engine_surface.columnconfigure(1, weight=1)
        tk.Label(engine_surface, text='Auto', bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w')
        tk.Label(engine_surface, textvariable=self.engine_auto_var, bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9)).grid(row=0, column=1, sticky='w')
        tk.Label(engine_surface, text='Override', bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 9)).grid(row=1, column=0, sticky='w', pady=(8, 0))
        self.engine_combo = ttk.Combobox(engine_surface, textvariable=self.engine_override_var, values=('auto', 'godot', 'python', 'unity'), state='readonly', width=12)
        self.engine_combo.grid(row=1, column=1, sticky='w', pady=(8, 0))
        self.use_ai_check = ttk.Checkbutton(engine_surface, text='Use AI fallback', variable=self.use_ai_var)
        self.use_ai_check.grid(row=2, column=0, columnspan=2, sticky='w', pady=(8, 0))
        if self._safe_mode:
            self.use_ai_check.configure(state='disabled')
        self.search_btn = ttk.Button(engine_surface, text='Search in Browser', style='Ghost.TButton', command=self.search_in_browser)
        self.search_btn.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        self._bind_ghost_feedback(self.search_btn)

        ttk.Label(inspector, text='Explanation', style='Section.TLabel').grid(row=4, column=0, sticky='w')
        out = ttk.Frame(inspector, style='Surface.TFrame', padding=SURFACE_PAD)
        out.grid(row=5, column=0, sticky='nsew')
        out.columnconfigure(0, weight=1)
        out.columnconfigure(1, weight=0)

        self.copy_report_btn = ttk.Button(out, text='Copy Full Report', style='Ghost.TButton', command=self.copy_full_report)
        self.copy_report_btn.grid(row=0, column=0, columnspan=2, sticky='e', pady=(0, 8))
        self._bind_ghost_feedback(self.copy_report_btn)

        self._add_field(out, 0, 'Summary', self.summary_var, start_row=1)
        self._add_field(out, 1, 'What It Means', self.means_var, start_row=1)
        self._add_field(out, 2, 'Likely Cause', self.cause_var, start_row=1)
        self._add_field(out, 3, 'First Step', self.step_var, start_row=1)
        self._add_field(out, 4, 'Confidence', self.conf_var, start_row=1)
        self._add_field(out, 5, 'Source', self.source_var, start_row=1)

        self._busy_controls.extend([self.clear_btn, self.engine_combo, self.use_ai_check, self.search_btn, self.copy_report_btn, self.text])
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

    def _add_field(self, parent, row, label, var, start_row=0):
        row_offset = start_row + (row * 2)
        wrap = 300
        tk.Label(parent, text=label, bg=self.colors['surface'], fg=self.colors['muted'], font=('Segoe UI', 8)).grid(row=row_offset, column=0, sticky='w', pady=((0 if row == 0 else 8), 0))
        body = tk.Label(parent, textvariable=var, bg=self.colors['surface'], fg=self.colors['text'], font=('Segoe UI', 9), wraplength=wrap, justify=tk.LEFT, anchor='w')
        body.grid(row=row_offset + 1, column=0, sticky='ew')
        copy_btn = ttk.Button(parent, text='Copy', style='Ghost.TButton', command=lambda v=var: self.copy_text(v.get()))
        copy_btn.grid(row=row_offset + 1, column=1, sticky='e', padx=(8, 0))
        self._bind_ghost_feedback(copy_btn)
        self._busy_controls.append(copy_btn)

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
            self.toast.show(text, duration_ms=1400)

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

    def _on_text_change(self, _event=None):
        raw = self.text.get('1.0', tk.END).strip()
        self.shell.set_dirty(bool(raw))

    def sanitize_for_search(self, text: str, max_len: int = 360) -> str:
        cleaned = (text or '').strip()
        if not cleaned:
            return ''
        cleaned = PATH_RE.sub('', cleaned)
        cleaned = LINE_NO_RE.sub('', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        if len(cleaned) > max_len:
            cleaned = cleaned[:max_len].rsplit(' ', 1)[0]
        return cleaned

    def get_selected_or_fallback(self) -> str:
        try:
            sel = self.text.get('sel.first', 'sel.last').strip()
            if sel:
                return sel
        except tk.TclError:
            pass
        return self.text.get('1.0', '10.0').strip()

    def open_search(self, query: str, engine: str = 'duckduckgo') -> bool:
        q = self.sanitize_for_search(query)
        if not q:
            return False
        enc = urllib.parse.quote_plus(q)
        url = f'https://www.google.com/search?q={enc}' if engine == 'google' else f'https://duckduckgo.com/?q={enc}'
        webbrowser.open(url)
        return True

    def search_in_browser(self, _event=None):
        query = self.get_selected_or_fallback()
        if self.open_search(query):
            self.set_status('Opened browser search')
            self.show_toast('Search opened')
        else:
            self.set_status('Search skipped: no usable query')
        return 'break'

    def _attach_search_actions(self, text_widget: tk.Text, status_cb=None):
        def do_search(_evt=None):
            query = self.get_selected_or_fallback()
            if self.open_search(query):
                if status_cb is not None:
                    status_cb('Opened browser search')
                self.show_toast('Search opened')
            else:
                if status_cb is not None:
                    status_cb('Search skipped: no usable query')
            return 'break'

        text_widget.bind('<Control-Shift-f>', do_search)
        text_widget.bind('<Control-Shift-F>', do_search)
        self._search_menu = tk.Menu(text_widget, tearoff=0)
        self._search_menu.add_command(label='Search selected text', command=self.search_in_browser)

        def on_context(evt):
            try:
                self._search_menu.tk_popup(evt.x_root, evt.y_root)
            finally:
                self._search_menu.grab_release()
            return 'break'

        text_widget.bind('<Button-3>', on_context)
        text_widget.bind('<Button-2>', on_context)

    def copy_text(self, value):
        self.root.clipboard_clear()
        self.root.clipboard_append(value or '')
        self.root.update_idletasks()
        self.set_status('Copied to clipboard')
        self.show_toast('Copied')

    def copy_full_report(self):
        report = (
            'Error Goblin Report\n'
            f'Engine (auto): {self.engine_auto_var.get()}\n'
            f'Engine (override): {self.engine_override_var.get()}\n'
            f'Summary: {self.summary_var.get()}\n'
            f'What It Means: {self.means_var.get()}\n'
            f'Likely Cause: {self.cause_var.get()}\n'
            f'First Step: {self.step_var.get()}\n'
            f'Confidence: {self.conf_var.get()}\n'
            f'Source: {self.source_var.get()}'
        )
        self.copy_text(report)

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
        self._set_widget_state(self.explain_btn, enabled=not busy)
        self.root.configure(cursor='watch' if busy else '')
        if busy:
            self.busy_bar.pack(fill=tk.X, pady=(8, 0))
            self.busy_bar.start(10)
        else:
            self.busy_bar.stop()
            self.busy_bar.pack_forget()
        if message:
            self.set_status(message)

    def clear_text(self):
        if self._busy:
            return
        self.text.delete('1.0', tk.END)
        self.engine_auto_var.set('unknown')
        self.summary_var.set('Paste an error and click Explain.')
        self.means_var.set('-')
        self.cause_var.set('-')
        self.step_var.set('-')
        self.conf_var.set('-')
        self.source_var.set('-')
        self.shell.set_dirty(False)
        self.set_status('Cleared')

    def on_explain(self):
        if self._busy:
            return
        raw = self.text.get('1.0', tk.END).strip()
        if not raw:
            messagebox.showinfo('Error Goblin', 'Paste error text first.')
            return
        auto = detect_engine(raw)
        self.engine_auto_var.set(auto)
        override = self.engine_override_var.get().strip().lower() or 'auto'
        use_ai = bool(self.use_ai_var.get())
        self.shell.set_dirty(True)
        if use_ai and len(raw) > AI_CONTEXT_CHAR_LIMIT:
            self._set_busy(True, f'Goblin decoding error... analyzing first {AI_CONTEXT_CHAR_LIMIT} chars for AI context.')
            self.show_toast('Long log: AI context truncated')
        else:
            self._set_busy(True, 'Goblin decoding error...')
        self.jobs.submit(self._explain_worker, self._on_explain_done, raw, override, use_ai)

    def _explain_worker(self, text, override, use_ai, progress=None):
        return safe_explain_error(text, engine_override=override, allow_ai=use_ai)

    def _on_explain_done(self, result):
        try:
            if not result.ok:
                if result.tb:
                    print(result.tb)
                self.set_status('Explain failed')
                messagebox.showerror('Error Goblin', str(result.error))
                return

            exp: ExplanationResult = result.value
            self.summary_var.set(exp.summary)
            self.means_var.set(exp.what_it_means)
            self.cause_var.set(exp.likely_cause)
            self.step_var.set(exp.first_step)
            self.conf_var.set(f'{exp.confidence:.2f}')
            self.source_var.set(exp.source)
            self.set_status(f"Explained via {exp.source} ({exp.engine})")
            self.show_toast('Explanation ready')
        finally:
            self._set_busy(False)


def open_tool_window(launcher_root):
    window = tk.Toplevel(launcher_root)
    ErrorGoblinWindow(window, launcher_root=launcher_root)
    return window


