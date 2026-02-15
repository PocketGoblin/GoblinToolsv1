from __future__ import annotations

import os
import shutil
from pathlib import Path


SAFE_MODE_ENV = 'GOBLINTOOLS_SAFE_MODE'
DISABLE_DND_ENV = 'GOBLINTOOLS_DISABLE_DND'


def _is_truthy(value: str | None) -> bool:
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def is_safe_mode() -> bool:
    return _is_truthy(os.getenv(SAFE_MODE_ENV))


def set_safe_mode(enabled: bool) -> None:
    if enabled:
        os.environ[SAFE_MODE_ENV] = '1'
        os.environ[DISABLE_DND_ENV] = '1'
    else:
        os.environ.pop(SAFE_MODE_ENV, None)
        os.environ.pop(DISABLE_DND_ENV, None)


def is_dnd_disabled() -> bool:
    return _is_truthy(os.getenv(DISABLE_DND_ENV)) or is_safe_mode()


def has_api_key() -> bool:
    key = os.getenv('goblintools_api_key') or os.getenv('GOBLINTOOLS_API_KEY')
    return bool(str(key or '').strip())


def has_7z_binary() -> bool:
    repo_root = Path(__file__).resolve().parents[2]
    bundled = [
        repo_root / 'tools' / '7zip' / '7z.exe',
        repo_root / 'tools' / '7-Zip' / '7z.exe',
    ]
    if any(path.exists() for path in bundled):
        return True
    return bool(shutil.which('7z'))

