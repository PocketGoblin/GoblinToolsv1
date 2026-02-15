import tkinter as tk

BUTTON_HOVER_DELAY_MS = 96


class ToastNotifier:
    def __init__(self, root, bg, fg):
        self.root = root
        self._clear_job = None
        self.label = tk.Label(
            root,
            text='',
            bg=bg,
            fg=fg,
            font=('Segoe UI', 9),
            padx=10,
            pady=6,
            relief=tk.FLAT,
            bd=0,
        )

    def show(self, text, duration_ms=1600):
        self.label.configure(text=text)
        self.label.place(relx=1.0, rely=1.0, x=-14, y=-14, anchor='se')
        if self._clear_job is not None:
            self.root.after_cancel(self._clear_job)
        self._clear_job = self.root.after(duration_ms, self.label.place_forget)


def bind_button_feedback(root, button, variant='ghost'):
    if variant == 'tool':
        hover_style = 'ToolHover.TButton'
        base_style = 'Tool.TButton'
    elif variant == 'primary':
        hover_style = 'PrimaryHover.TButton'
        base_style = 'Primary.TButton'
    else:
        hover_style = 'GhostHover.TButton'
        base_style = 'Ghost.TButton'
    state = {'job': None}

    def on_enter(_event):
        button.configure(cursor='hand2')
        if state['job'] is not None:
            root.after_cancel(state['job'])
        state['job'] = root.after(BUTTON_HOVER_DELAY_MS, lambda: button.configure(style=hover_style))

    def on_leave(_event):
        if state['job'] is not None:
            root.after_cancel(state['job'])
            state['job'] = None
        button.configure(style=base_style)

    button.bind('<Enter>', on_enter)
    button.bind('<Leave>', on_leave)
