import tkinter as tk
from tkinter import ttk

SPACE_8 = 8
SPACE_12 = 12
SPACE_16 = 16
SECTION_GAP = SPACE_12
SURFACE_PAD = SPACE_12


# Neon Undercity token set
VOID_0 = '#070B14'
VOID_1 = '#0B1222'
SURFACE_1 = '#101A2E'
SURFACE_2 = '#14203A'
STROKE = '#213157'
TEXT = '#EAF2FF'
MUTED = '#7FA0D0'
ACCENT_MINT = '#3CFFB3'
MINT_DIM = '#1CCF88'
ACCENT_CYAN = '#00E5FF'
NEON_PINK = '#FF2E88'


def get_theme_tokens():
    return {
        'VOID_0': VOID_0,
        'VOID_1': VOID_1,
        'SURFACE_1': SURFACE_1,
        'SURFACE_2': SURFACE_2,
        'STROKE': STROKE,
        'TEXT': TEXT,
        'TEXT_MUTED': MUTED,
        'MUTED': MUTED,
        'ACCENT_MINT': ACCENT_MINT,
        'MINT_DIM': MINT_DIM,
        'ACCENT_CYAN': ACCENT_CYAN,
        'NEON_PINK': NEON_PINK,
        'ACCENT': ACCENT_MINT,
        # Compatibility aliases used by existing tools
        'BG0': VOID_0,
        'SURFACE1': SURFACE_1,
        'SURFACE2': SURFACE_2,
        'bg': VOID_0,
        'canvas_bg': VOID_1,
        'inspector': SURFACE_1,
        'surface': SURFACE_2,
        'surface_alt': '#1A2A4A',
        'text': TEXT,
        'muted': MUTED,
        'accent': ACCENT_MINT,
        'accent_soft': MINT_DIM,
        'accent_glow': '#69FFD0',
        'accent_cyan': ACCENT_CYAN,
        'shadow': '#060A12',
        'toast': '#102038',
        'stroke': STROKE,
    }


def apply_suite_theme(root):
    style = ttk.Style()
    style.theme_use('clam')
    colors = get_theme_tokens()

    root.configure(bg=colors['VOID_0'])

    style.configure('Root.TFrame', background=colors['VOID_0'])
    style.configure('Workspace.TFrame', background=colors['SURFACE_1'])
    style.configure('Inspector.TFrame', background=colors['SURFACE_1'])
    style.configure('Surface.TFrame', background=colors['SURFACE_2'])
    style.configure('Card.TFrame', background=colors['SURFACE_1'])

    style.configure('TLabel', background=colors['SURFACE_1'], foreground=colors['TEXT'], font=('Segoe UI', 10))
    style.configure('Body.TLabel', background=colors['SURFACE_1'], foreground=colors['TEXT'], font=('Segoe UI', 10))
    style.configure('Muted.TLabel', background=colors['SURFACE_1'], foreground=colors['MUTED'], font=('Segoe UI', 9))
    style.configure('Title.TLabel', background=colors['SURFACE_1'], foreground=colors['TEXT'], font=('Segoe UI Semibold', 17))
    style.configure('Section.TLabel', background=colors['SURFACE_1'], foreground=colors['TEXT'], font=('Segoe UI Semibold', 13))

    style.configure('LauncherTitle.TLabel', background=colors['VOID_0'], foreground=colors['TEXT'], font=('Segoe UI Semibold', 18))
    style.configure('LauncherSub.TLabel', background=colors['VOID_0'], foreground=colors['MUTED'], font=('Segoe UI', 10))
    style.configure('ToolDesc.TLabel', background=colors['SURFACE_1'], foreground=colors['MUTED'], font=('Segoe UI', 9))
    style.configure('ToolCard.TFrame', background=colors['SURFACE_2'], padding=16)
    style.configure('ToolCardHover.TFrame', background='#1E3157', padding=16)
    style.configure('ToolCardTitle.TLabel', background=colors['SURFACE_2'], foreground=colors['TEXT'], font=('Segoe UI Semibold', 12))
    style.configure('ToolCardTitleHover.TLabel', background='#1E3157', foreground=colors['TEXT'], font=('Segoe UI Semibold', 12))
    style.configure('ToolCardDesc.TLabel', background=colors['SURFACE_2'], foreground=colors['MUTED'], font=('Segoe UI', 10))
    style.configure('ToolCardDescHover.TLabel', background='#1E3157', foreground=colors['TEXT'], font=('Segoe UI', 10))
    style.configure('ToolCardArrow.TLabel', background=colors['SURFACE_2'], foreground=colors['ACCENT_CYAN'], font=('Segoe UI Semibold', 14))
    style.configure('ToolCardArrowHover.TLabel', background='#1E3157', foreground=colors['ACCENT_CYAN'], font=('Segoe UI Semibold', 14))

    style.configure(
        'Ghost.TButton',
        background=colors['SURFACE_2'],
        foreground=colors['TEXT'],
        borderwidth=0,
        lightcolor=colors['SURFACE_2'],
        darkcolor=colors['SURFACE_2'],
        bordercolor=colors['SURFACE_2'],
        focusthickness=0,
        focuscolor=colors['ACCENT_CYAN'],
        font=('Segoe UI Semibold', 9),
        padding=(11, 8),
        relief=tk.FLAT,
    )
    style.map(
        'Ghost.TButton',
        background=[('active', '#1E3157'), ('pressed', '#172948')],
        foreground=[('active', colors['TEXT']), ('pressed', colors['TEXT'])],
        bordercolor=[('focus', colors['ACCENT_CYAN']), ('active', colors['STROKE'])],
    )

    style.configure(
        'GhostHover.TButton',
        background=colors['surface_alt'],
        foreground=colors['ACCENT_CYAN'],
        borderwidth=0,
        lightcolor=colors['surface_alt'],
        darkcolor=colors['surface_alt'],
        bordercolor=colors['ACCENT_CYAN'],
        focusthickness=0,
        focuscolor=colors['ACCENT_CYAN'],
        font=('Segoe UI Semibold', 9),
        padding=(11, 8),
        relief=tk.FLAT,
    )
    style.map(
        'GhostHover.TButton',
        background=[('active', colors['surface_alt']), ('pressed', '#172948')],
        foreground=[('active', colors['ACCENT_CYAN']), ('pressed', colors['TEXT'])],
        bordercolor=[('focus', colors['ACCENT_CYAN']), ('active', colors['ACCENT_CYAN'])],
    )

    style.configure(
        'Primary.TButton',
        background=colors['ACCENT_MINT'],
        foreground='#05130E',
        borderwidth=0,
        focuscolor=colors['ACCENT_CYAN'],
        font=('Segoe UI Semibold', 10),
        padding=(15, 10),
    )
    style.map(
        'Primary.TButton',
        background=[('active', '#58FFC1'), ('pressed', '#22C485'), ('disabled', '#295647')],
        foreground=[('active', '#04120B'), ('pressed', '#04120B'), ('disabled', '#6F9083')],
    )

    style.configure('Tool.TButton', background=colors['SURFACE_2'], foreground=colors['TEXT'], padding=(12, 10), font=('Segoe UI Semibold', 10))
    style.map(
        'Tool.TButton',
        background=[('active', '#1E3157'), ('pressed', '#172948')],
        foreground=[('active', colors['ACCENT_CYAN']), ('pressed', colors['TEXT'])],
    )
    style.configure(
        'ToolHover.TButton',
        background=colors['surface_alt'],
        foreground=colors['ACCENT_CYAN'],
        borderwidth=0,
        lightcolor=colors['surface_alt'],
        darkcolor=colors['surface_alt'],
        bordercolor=colors['ACCENT_CYAN'],
        focusthickness=0,
        focuscolor=colors['ACCENT_CYAN'],
        font=('Segoe UI Semibold', 10),
        padding=(12, 10),
        relief=tk.FLAT,
    )
    style.map(
        'ToolHover.TButton',
        background=[('active', colors['surface_alt']), ('pressed', '#172948')],
        foreground=[('active', colors['ACCENT_CYAN']), ('pressed', colors['TEXT'])],
        bordercolor=[('focus', colors['ACCENT_CYAN']), ('active', colors['ACCENT_CYAN'])],
    )

    # Guardrail fallback so any unstyled ttk.Button doesn't flash white on hover.
    style.map(
        'TButton',
        background=[('active', colors['SURFACE_2']), ('pressed', '#172948')],
        foreground=[('active', colors['TEXT']), ('pressed', colors['TEXT'])],
    )

    style.configure(
        'TCombobox',
        fieldbackground=colors['SURFACE_2'],
        background=colors['SURFACE_2'],
        foreground=colors['TEXT'],
        selectforeground=colors['TEXT'],
        insertcolor=colors['ACCENT_CYAN'],
        arrowcolor=colors['MUTED'],
        bordercolor=colors['STROKE'],
        lightcolor=colors['SURFACE_2'],
        darkcolor=colors['SURFACE_2'],
        focuscolor=colors['ACCENT_CYAN'],
    )
    style.map(
        'TCombobox',
        fieldbackground=[('readonly', colors['SURFACE_2']), ('focus', '#1A2B4C')],
        foreground=[('focus', colors['ACCENT_CYAN']), ('readonly', colors['TEXT'])],
    )
    style.configure(
        'TEntry',
        fieldbackground=colors['SURFACE_2'],
        foreground=colors['TEXT'],
        insertcolor=colors['ACCENT_CYAN'],
        bordercolor=colors['STROKE'],
        lightcolor=colors['SURFACE_2'],
        darkcolor=colors['SURFACE_2'],
        focuscolor=colors['ACCENT_CYAN'],
    )
    style.map('TEntry', bordercolor=[('focus', colors['ACCENT_CYAN'])], foreground=[('focus', colors['TEXT'])])
    style.configure('TCheckbutton', background=colors['SURFACE_1'], foreground=colors['MUTED'], font=('Segoe UI', 9))
    style.configure('Floating.TCheckbutton', background=colors['SURFACE_2'], foreground=colors['MUTED'], font=('Segoe UI', 9))
    style.map(
        'TCheckbutton',
        foreground=[('active', colors['ACCENT_CYAN']), ('selected', colors['TEXT'])],
    )
    style.map(
        'Floating.TCheckbutton',
        foreground=[('active', colors['ACCENT_CYAN']), ('selected', colors['TEXT'])],
    )

    # Treeview color pass for dark neon cohesion
    style.configure(
        'Treeview',
        background=colors['SURFACE_2'],
        fieldbackground=colors['SURFACE_2'],
        foreground=colors['TEXT'],
        bordercolor=colors['STROKE'],
        lightcolor=colors['SURFACE_2'],
        darkcolor=colors['SURFACE_2'],
        rowheight=24,
        font=('Segoe UI', 9),
    )
    style.map(
        'Treeview',
        background=[('selected', '#1E3157')],
        foreground=[('selected', colors['ACCENT_CYAN'])],
    )
    style.configure(
        'Treeview.Heading',
        background=colors['SURFACE_1'],
        foreground=colors['MUTED'],
        bordercolor=colors['STROKE'],
        lightcolor=colors['SURFACE_1'],
        darkcolor=colors['SURFACE_1'],
        relief=tk.FLAT,
        font=('Segoe UI Semibold', 9),
    )
    style.map(
        'Treeview.Heading',
        background=[('active', '#162744')],
        foreground=[('active', colors['ACCENT_CYAN'])],
    )

    # Global scrollbar skin (defaults + explicit cyber aliases)
    trough = colors['VOID_1']
    thumb = colors['STROKE']
    hover = colors['ACCENT_CYAN']
    press = colors['ACCENT_MINT']
    arrow = colors['MUTED']
    common_scroll = {
        'troughcolor': trough,
        'background': thumb,
        'bordercolor': trough,
        'lightcolor': trough,
        'darkcolor': trough,
        'arrowcolor': arrow,
        'gripcount': 0,
        'relief': tk.FLAT,
        'width': 10,
    }

    # Default styles so every ttk.Scrollbar picks up the skin automatically.
    style.configure('TScrollbar', **common_scroll)
    style.map(
        'TScrollbar',
        background=[('active', hover), ('pressed', press)],
        arrowcolor=[('active', hover), ('pressed', press)],
    )
    style.configure('Vertical.TScrollbar', **common_scroll)
    style.map(
        'Vertical.TScrollbar',
        background=[('active', hover), ('pressed', press)],
        arrowcolor=[('active', hover), ('pressed', press)],
    )
    style.configure('Horizontal.TScrollbar', **common_scroll)
    style.map(
        'Horizontal.TScrollbar',
        background=[('active', hover), ('pressed', press)],
        arrowcolor=[('active', hover), ('pressed', press)],
    )

    # Named aliases for explicit use when needed.
    style.configure('Cyber.Vertical.TScrollbar', **common_scroll)
    style.map(
        'Cyber.Vertical.TScrollbar',
        background=[('active', hover), ('pressed', press)],
        arrowcolor=[('active', hover), ('pressed', press)],
    )
    style.configure('Cyber.Horizontal.TScrollbar', **common_scroll)
    style.map(
        'Cyber.Horizontal.TScrollbar',
        background=[('active', hover), ('pressed', press)],
        arrowcolor=[('active', hover), ('pressed', press)],
    )

    return style, colors


def apply_palette_theme(root):
    return apply_suite_theme(root)
