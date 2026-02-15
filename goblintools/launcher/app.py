import tkinter as tk
from tkinter import ttk

from goblintools.common import (
    apply_suite_theme,
    APP_NAME,
    APP_VERSION,
    check_for_updates_async,
    has_7z_binary,
    has_api_key,
    is_safe_mode,
    tool_title,
    version_text,
)
from goblintools.common.metadata import iter_enabled_tools, load_master_metadata
from goblintools.palette_goblin import open_tool_window as open_palette_goblin_window
from goblintools.slicer_goblin import open_tool_window as open_slicer_goblin_window
from goblintools.tools.error_goblin_window import open_tool_window as open_error_goblin_window
from goblintools.tools.sort_goblin_window import open_tool_window as open_sort_goblin_window
from goblintools.tools.zip_goblin_window import open_tool_window as open_zip_goblin_window

HOVER_SETTLE_MS = 16
CARD_GAP_Y = 10

TOOL_OPENERS = {
    'palette_goblin': open_palette_goblin_window,
    'slicer_goblin': open_slicer_goblin_window,
    'zip_goblin': open_zip_goblin_window,
    'error_goblin': open_error_goblin_window,
    'sort_goblin': open_sort_goblin_window,
}

TOOL_GLYPHS = {
    'palette_goblin': 'PAL',
    'slicer_goblin': 'SLC',
    'zip_goblin': 'ZIP',
    'error_goblin': 'ERR',
    'sort_goblin': 'SRT',
}

TOOL_DESCRIPTIONS = {
    'palette_goblin': 'extract palettes',
    'slicer_goblin': 'slice sprite sheets',
    'zip_goblin': 'extract archives / pack zip or 7z',
    'error_goblin': 'decode engine errors',
    'sort_goblin': 'sort + rename safely',
}


class ToolCard(ttk.Frame):
    def __init__(self, parent, title: str, desc: str, command, *, glyph=''):
        super().__init__(parent, style='ToolCard.TFrame')
        self.command = command
        self._hovered = False
        self._leave_after_id = None
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)

        prefix = f'[{glyph}] ' if glyph else ''
        self.title_lbl = ttk.Label(self, text=f'{prefix}{title}', style='ToolCardTitle.TLabel')
        self.desc_lbl = ttk.Label(self, text=desc, style='ToolCardDesc.TLabel', wraplength=520, justify=tk.LEFT)
        self.arrow_lbl = ttk.Label(self, text='>', style='ToolCardArrow.TLabel')

        self.title_lbl.grid(row=0, column=0, sticky='w')
        self.desc_lbl.grid(row=1, column=0, sticky='w', pady=(4, 0))
        self.arrow_lbl.grid(row=0, column=1, rowspan=2, sticky='e', padx=(12, 0))

        self._bind_all_children()
        self.configure(takefocus=True)

    def _bind_all_children(self):
        widgets = (self, self.title_lbl, self.desc_lbl, self.arrow_lbl)
        for widget in widgets:
            widget.bind('<Enter>', self._on_enter)
            widget.bind('<Leave>', self._on_leave)
            widget.bind('<Button-1>', self._on_click)
        self.bind('<Return>', self._on_click)
        self.bind('<space>', self._on_click)

    def _is_pointer_inside(self) -> bool:
        x = self.winfo_pointerx()
        y = self.winfo_pointery()
        hovered = self.winfo_containing(x, y)
        while hovered is not None:
            if hovered == self:
                return True
            hovered = hovered.master
        return False

    def _on_enter(self, _event=None):
        if self._leave_after_id is not None:
            try:
                self.after_cancel(self._leave_after_id)
            except Exception:
                pass
            self._leave_after_id = None
        if self._hovered:
            return
        self._hovered = True
        self.configure(style='ToolCardHover.TFrame', cursor='hand2')
        self.title_lbl.configure(style='ToolCardTitleHover.TLabel')
        self.desc_lbl.configure(style='ToolCardDescHover.TLabel')
        self.arrow_lbl.configure(style='ToolCardArrowHover.TLabel')

    def _on_leave(self, _event=None):
        if self._leave_after_id is not None:
            try:
                self.after_cancel(self._leave_after_id)
            except Exception:
                pass
        self._leave_after_id = self.after(HOVER_SETTLE_MS, self._finalize_leave)

    def _finalize_leave(self):
        self._leave_after_id = None
        if self._is_pointer_inside():
            return
        if not self._hovered:
            return
        self._hovered = False
        self.configure(style='ToolCard.TFrame', cursor='')
        self.title_lbl.configure(style='ToolCardTitle.TLabel')
        self.desc_lbl.configure(style='ToolCardDesc.TLabel')
        self.arrow_lbl.configure(style='ToolCardArrow.TLabel')

    def _on_click(self, _event=None):
        if callable(self.command):
            self.command()


def _tkdnd_available(root: tk.Tk, safe_mode: bool) -> bool:
    if safe_mode:
        return False
    try:
        root.tk.call('package', 'require', 'tkdnd')
        return True
    except Exception:
        return False


def _tool_card_text(record: dict) -> tuple[str, str]:
    tool_id = str(record.get('tool_id', '')).strip()
    display_name = str(record.get('display_name') or record.get('name') or tool_id).strip()
    version = str(record.get('version') or '').strip()
    if version:
        display_name = f'{display_name} {version}'
    status = str(record.get('status', '')).strip().lower()
    is_experimental = bool(record.get('experimental', False)) or status == 'experimental'
    if is_experimental:
        display_name = f'{display_name} [EXPERIMENTAL]'
    description = str(record.get('description') or '')
    return display_name, description


def _tool_specs_from_metadata() -> list[dict]:
    metadata = load_master_metadata()
    rows = []
    for record in iter_enabled_tools(metadata):
        tool_id = str(record.get('tool_id', '')).strip()
        opener = TOOL_OPENERS.get(tool_id)
        if opener is None:
            continue
        title, desc = _tool_card_text(record)
        rows.append(
            {
                'tool_id': tool_id,
                'title': title,
                'desc': desc,
                'glyph': str(record.get('glyph') or '').strip(),
                'opener': opener,
            }
        )
    return rows


def _fallback_tool_specs() -> list[dict]:
    return [
        {
            'tool_id': 'palette_goblin',
            'title': tool_title('Palette Goblin', 'palette_goblin'),
            'desc': TOOL_DESCRIPTIONS['palette_goblin'],
            'glyph': TOOL_GLYPHS['palette_goblin'],
            'opener': open_palette_goblin_window,
        },
        {
            'tool_id': 'slicer_goblin',
            'title': tool_title('Slicer Goblin', 'slicer_goblin'),
            'desc': TOOL_DESCRIPTIONS['slicer_goblin'],
            'glyph': TOOL_GLYPHS['slicer_goblin'],
            'opener': open_slicer_goblin_window,
        },
        {
            'tool_id': 'zip_goblin',
            'title': tool_title('Zip Goblin', 'zip_goblin'),
            'desc': TOOL_DESCRIPTIONS['zip_goblin'],
            'glyph': TOOL_GLYPHS['zip_goblin'],
            'opener': open_zip_goblin_window,
        },
        {
            'tool_id': 'error_goblin',
            'title': tool_title('Error Goblin', 'error_goblin'),
            'desc': TOOL_DESCRIPTIONS['error_goblin'],
            'glyph': TOOL_GLYPHS['error_goblin'],
            'opener': open_error_goblin_window,
        },
        {
            'tool_id': 'sort_goblin',
            'title': tool_title('Sort Goblin', 'sort_goblin'),
            'desc': TOOL_DESCRIPTIONS['sort_goblin'],
            'glyph': TOOL_GLYPHS['sort_goblin'],
            'opener': open_sort_goblin_window,
        },
    ]


def launch(*, safe_mode: bool | None = None):
    safe_mode = is_safe_mode() if safe_mode is None else bool(safe_mode)
    if safe_mode:
        root = tk.Tk()
    else:
        try:
            from tkinterdnd2 import TkinterDnD  # type: ignore

            root = TkinterDnD.Tk()
        except Exception:
            root = tk.Tk()
    root.title(tool_title(f'{APP_NAME} Launcher', 'launcher'))
    root.geometry('520x520')
    root.minsize(460, 460)
    apply_suite_theme(root)

    frame = ttk.Frame(root, style='Root.TFrame')
    frame.pack(fill=tk.BOTH, expand=True)

    header = ttk.Frame(frame, style='Root.TFrame', padding=(24, 24, 24, 8))
    header.pack(fill=tk.X)
    header.columnconfigure(0, weight=1)

    ttk.Label(header, text=APP_NAME, style='LauncherTitle.TLabel').grid(row=0, column=0, sticky='w')
    ttk.Label(header, text=f'Launch a tool   {version_text()}', style='LauncherSub.TLabel').grid(row=1, column=0, sticky='w', pady=(4, 0))
    updates_var = tk.StringVar(value='Updates: checking setup...')
    deps_var = tk.StringVar(value='Deps: checking...')
    ttk.Label(header, textvariable=updates_var, style='LauncherSub.TLabel').grid(row=0, column=1, sticky='e')
    ttk.Label(header, textvariable=deps_var, style='LauncherSub.TLabel').grid(row=1, column=1, sticky='e', pady=(4, 0))

    def _on_update_result(info):
        try:
            updates_var.set(info.status_text())
        except Exception:
            updates_var.set('Updates: unavailable')

    if safe_mode:
        updates_var.set('Updates: disabled (safe mode)')
    else:
        check_for_updates_async(APP_VERSION, _on_update_result, root=root)

    dnd_status = 'off (safe mode)' if safe_mode else ('ok' if _tkdnd_available(root, safe_mode=False) else 'missing')
    seven_zip_status = 'ok' if has_7z_binary() else 'missing'
    api_status = 'ok' if has_api_key() else 'missing'
    deps_var.set(f'Deps: DnD {dnd_status} | 7z {seven_zip_status} | API key {api_status}')

    cards = ttk.Frame(frame, style='Root.TFrame', padding=(24, 8, 24, 24))
    cards.pack(fill=tk.BOTH, expand=True)

    tool_specs = _tool_specs_from_metadata() or _fallback_tool_specs()
    for idx, spec in enumerate(tool_specs):
        pady = (0, CARD_GAP_Y) if idx < len(tool_specs) - 1 else (0, 0)
        ToolCard(
            cards,
            spec['title'],
            spec['desc'],
            lambda opener=spec['opener']: _open_tool(root, opener),
            glyph=spec['glyph'],
        ).pack(fill=tk.X, pady=pady)

    root.mainloop()


def _open_tool(root, tool_opener):
    root.withdraw()
    tool_opener(root)


if __name__ == '__main__':
    launch()
