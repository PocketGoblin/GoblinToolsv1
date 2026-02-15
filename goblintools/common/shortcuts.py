from __future__ import annotations


class ShortcutManager:
    def __init__(self):
        self._bindings: dict[object, list[tuple[str, str]]] = {}
        self._help_entries: list[tuple[str, str]] = []

    def bind(self, widget, sequence: str, callback, *, add: str = '+', description: str | None = None):
        funcid = widget.bind(sequence, callback, add=add)
        if funcid:
            self._bindings.setdefault(widget, []).append((sequence, funcid))
        if description:
            self.register_help(sequence, description)
        return funcid

    def register_help(self, sequence: str, description: str):
        entry = (sequence, description)
        if entry not in self._help_entries:
            self._help_entries.append(entry)

    def unbind_widget(self, widget):
        bindings = self._bindings.pop(widget, [])
        for sequence, funcid in bindings:
            try:
                widget.unbind(sequence, funcid)
            except Exception:
                pass

    def clear(self):
        widgets = list(self._bindings.keys())
        for widget in widgets:
            self.unbind_widget(widget)

    def help_text(self) -> str:
        if not self._help_entries:
            return ''
        return '\n'.join(f'{sequence}: {description}' for sequence, description in self._help_entries)
