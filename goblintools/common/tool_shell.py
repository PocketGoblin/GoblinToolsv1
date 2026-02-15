import tkinter as tk
from tkinter import messagebox, ttk

from .prefs import get_pref, set_pref
from .theme import SPACE_8, SPACE_12, SPACE_16
from .ui_helpers import bind_button_feedback


class ToolShell(ttk.Frame):
    def __init__(
        self,
        parent,
        title,
        colors,
        on_back,
        tool_id=None,
        title_icon=None,
        rail_width=240,
        sidebar_width=340,
        inspector_open=False,
        mascot_shape='circle',
    ):
        super().__init__(parent, style='Root.TFrame', padding=0)
        self.colors = colors
        self._on_back = on_back
        self._status_var = tk.StringVar(value='Ready')
        self.tool_id = (tool_id or title.lower().replace(' ', '_')).strip()
        legacy_pref_key = f'{self.tool_id}.inspector_open'
        tool_prefs = get_pref(self.tool_id, {})
        if isinstance(tool_prefs, dict) and 'inspector_open' in tool_prefs:
            self._inspector_open = bool(tool_prefs.get('inspector_open'))
        else:
            self._inspector_open = bool(get_pref(legacy_pref_key, inspector_open))
        self._sidebar_width = int(sidebar_width)
        self._dirty = False
        self.confirm = _ToolShellConfirm(self)

        self.pack(fill=tk.BOTH, expand=True)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.header = ttk.Frame(self, style='Surface.TFrame', padding=(SPACE_12, SPACE_12))
        self.header.grid(row=0, column=0, sticky='ew')
        self.header.columnconfigure(0, weight=1)

        self.title_label = ttk.Label(self.header, text=title, style='Title.TLabel')
        self.title_label.grid(row=0, column=0, sticky='w')

        self.inspector_toggle_btn = ttk.Button(self.header, text='Inspector >', style='Ghost.TButton', width=12, command=self.toggle_inspector)
        self.inspector_toggle_btn.grid(row=0, column=1, sticky='e')
        bind_button_feedback(parent, self.inspector_toggle_btn, variant='ghost')

        body = ttk.Frame(self, style='Root.TFrame', padding=SPACE_12)
        body.grid(row=1, column=0, sticky='nsew')
        body.columnconfigure(0, weight=0, minsize=rail_width)
        body.columnconfigure(1, weight=0, minsize=2)
        body.columnconfigure(2, weight=1, minsize=640)
        body.columnconfigure(3, weight=0, minsize=0)
        body.rowconfigure(0, weight=1)

        self.rail = ttk.Frame(body, style='Surface.TFrame', padding=SPACE_12, width=rail_width)
        self.rail.grid(row=0, column=0, sticky='nsew', padx=(0, SPACE_12))
        self.rail.grid_propagate(False)
        self.rail.columnconfigure(0, weight=1)
        self.rail.rowconfigure(1, weight=1)

        top = ttk.Frame(self.rail, style='Surface.TFrame')
        top.grid(row=0, column=0, sticky='ew')
        top.columnconfigure(0, weight=1)

        mascot_wrap = tk.Frame(top, bg=colors['SURFACE2'], padx=4, pady=4, highlightthickness=0)
        mascot_wrap.grid(row=0, column=0, sticky='w')
        self.mascot = tk.Canvas(mascot_wrap, width=64, height=64, bg=colors['SURFACE2'], highlightthickness=0, bd=0)
        self.mascot.pack()
        if mascot_shape == 'rounded':
            self.mascot.create_rectangle(8, 8, 56, 56, fill=colors['SURFACE1'], outline='')
        else:
            self.mascot.create_oval(8, 8, 56, 56, fill=colors['SURFACE1'], outline='')

        title_text = f'{title_icon} {title}' if title_icon else title
        self.rail_tool_name = ttk.Label(top, text=title_text, style='Section.TLabel')
        self.rail_tool_name.grid(row=1, column=0, sticky='w', pady=(SPACE_8, 0))

        sep1 = tk.Frame(self.rail, bg=colors['STROKE'], height=1)
        sep1.grid(row=0, column=0, sticky='sew', pady=(92, 0))

        self.rail_mid = ttk.Frame(self.rail, style='Surface.TFrame', padding=(0, SPACE_12, 0, SPACE_12))
        self.rail_mid.grid(row=1, column=0, sticky='nsew')
        self.rail_mid.columnconfigure(0, weight=1)

        sep2 = tk.Frame(self.rail, bg=colors['STROKE'], height=1)
        sep2.grid(row=2, column=0, sticky='ew')

        bottom = ttk.Frame(self.rail, style='Surface.TFrame', padding=(0, SPACE_12, 0, 0))
        bottom.grid(row=3, column=0, sticky='ew')
        bottom.columnconfigure(0, weight=1)
        self.back_btn = ttk.Button(bottom, text='Back to Launcher', style='Ghost.TButton', command=self._handle_back)
        self.back_btn.grid(row=0, column=0, sticky='ew')
        bind_button_feedback(parent, self.back_btn, variant='ghost')

        self.rail_seam = tk.Frame(body, bg=colors['BG0'], width=2, highlightthickness=0, bd=0)
        self.rail_seam.grid(row=0, column=1, sticky='ns', padx=(0, SPACE_12))

        self.main = ttk.Frame(body, style='Workspace.TFrame')
        self.main.grid(row=0, column=2, sticky='nsew')

        self.sidebar_container = ttk.Frame(body, style='Inspector.TFrame', width=self._sidebar_width)
        self.sidebar_container.grid(row=0, column=3, sticky='nsew', padx=(SPACE_12, 0))
        self.sidebar_container.grid_propagate(False)

        self.sidebar = ttk.Frame(self.sidebar_container, style='Inspector.TFrame', padding=SPACE_16)
        self.sidebar.pack(fill=tk.BOTH, expand=True)

        status = ttk.Frame(self, style='Surface.TFrame', padding=(SPACE_12, SPACE_8))
        status.grid(row=2, column=0, sticky='ew')
        tk.Label(status, textvariable=self._status_var, bg=colors['SURFACE2'], fg=colors['TEXT_MUTED'], font=('Segoe UI', 9)).pack(anchor='w')

        self._apply_inspector_state()

    def _handle_back(self):
        if self.confirm._navigate_away():
            self._on_back()

    def set_status(self, text):
        self._status_var.set(text)

    def set_dirty(self, dirty: bool):
        self._dirty = bool(dirty)

    def is_dirty(self) -> bool:
        return self._dirty

    def set_rail_note(self, text):
        self._clear_rail_mid()
        tk.Label(
            self.rail_mid,
            text=text,
            bg=self.colors['SURFACE2'],
            fg=self.colors['TEXT_MUTED'],
            font=('Segoe UI', 9),
            justify=tk.LEFT,
            wraplength=190,
        ).grid(row=0, column=0, sticky='nw')

    def set_rail_actions(self, actions):
        self._clear_rail_mid()
        for i, action in enumerate(actions or []):
            self._render_rail_action(i, action)

    def add_rail_action(self, action):
        row = len(self.rail_mid.winfo_children())
        self._render_rail_action(row, action)

    def _render_rail_action(self, row, action):
        action_id = action.get('id', f'action_{row}')
        label = action.get('label', action_id)
        icon = action.get('icon')
        command = action.get('command')

        text = f'{icon}  {label}' if isinstance(icon, str) and icon else label
        btn = ttk.Button(self.rail_mid, text=text, style='Ghost.TButton', command=command)
        if icon is not None and not isinstance(icon, str):
            btn.configure(image=icon, compound=tk.LEFT)
            btn.image = icon
        btn.grid(row=row, column=0, sticky='ew', pady=(0, 8))
        bind_button_feedback(self.winfo_toplevel(), btn, variant='ghost')

    def toggle_inspector(self):
        self._inspector_open = not self._inspector_open
        tool_prefs = get_pref(self.tool_id, {})
        if not isinstance(tool_prefs, dict):
            tool_prefs = {}
        tool_prefs['inspector_open'] = self._inspector_open
        set_pref(self.tool_id, tool_prefs)
        self._apply_inspector_state()

    def _apply_inspector_state(self):
        if self._inspector_open:
            self.sidebar_container.grid()
            self.inspector_toggle_btn.configure(text='Inspector v')
        else:
            self.sidebar_container.grid_remove()
            self.inspector_toggle_btn.configure(text='Inspector >')

    def _clear_rail_mid(self):
        for child in self.rail_mid.winfo_children():
            child.destroy()


class _ToolShellConfirm:
    def __init__(self, shell: ToolShell):
        self.shell = shell

    def _navigate_away(self, title='Return to Launcher', message='Return to launcher now? Unsaved work may be lost.') -> bool:
        if not self.shell.is_dirty():
            return True
        return bool(messagebox.askyesno(title, message))


