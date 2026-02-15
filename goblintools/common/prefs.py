import json
from pathlib import Path

PREFS_PATH = Path.home() / '.goblintools_prefs.json'


def _load_all():
    try:
        if not PREFS_PATH.exists():
            return {}
        return json.loads(PREFS_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_all(payload):
    try:
        PREFS_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    except Exception:
        pass


def get_pref(key, default=None):
    payload = _load_all()
    return payload.get(key, default)


def set_pref(key, value):
    payload = _load_all()
    payload[key] = value
    _save_all(payload)
