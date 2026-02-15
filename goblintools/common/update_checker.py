from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable

from .prefs import get_pref, set_pref


LOG = logging.getLogger(__name__)
DEFAULT_TIMEOUT_SECONDS = 2.5
UPDATE_PREF_KEY = 'updates.enabled'
UPDATE_TIMEOUT_PREF_KEY = 'updates.timeout_sec'


@dataclass
class UpdateInfo:
    current: str
    latest: str | None = None
    url: str | None = None
    notes: str = ''
    required: bool = False
    error: str = ''
    state: str = 'not_configured'

    def status_text(self) -> str:
        if self.state == 'disabled':
            return 'Updates: disabled'
        if self.state == 'not_configured':
            return 'Updates: not configured'
        if self.state == 'error':
            return f'Updates: error ({self.error})' if self.error else 'Updates: error'
        if self.state == 'available':
            latest = self.latest or 'unknown'
            return f'Updates: available ({latest})'
        if self.state == 'up_to_date':
            return f'Updates: up to date ({self.current})'
        return 'Updates: unknown'


def ensure_update_defaults() -> None:
    if get_pref(UPDATE_PREF_KEY, None) is None:
        set_pref(UPDATE_PREF_KEY, False)
    if get_pref(UPDATE_TIMEOUT_PREF_KEY, None) is None:
        set_pref(UPDATE_TIMEOUT_PREF_KEY, DEFAULT_TIMEOUT_SECONDS)


def check_for_updates_async(current_version: str, on_result: Callable[[UpdateInfo], None], *, root=None) -> None:
    ensure_update_defaults()
    enabled = bool(get_pref(UPDATE_PREF_KEY, False))
    timeout = float(get_pref(UPDATE_TIMEOUT_PREF_KEY, DEFAULT_TIMEOUT_SECONDS) or DEFAULT_TIMEOUT_SECONDS)
    LOG.debug('update check skeleton invoked: enabled=%s timeout=%s', enabled, timeout)

    info = UpdateInfo(current=current_version, state='not_configured' if enabled else 'disabled')

    if root is not None:
        root.after(0, lambda: on_result(info))
    else:
        on_result(info)

