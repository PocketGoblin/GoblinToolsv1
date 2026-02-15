from __future__ import annotations

import json
from pathlib import Path


def metadata_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / 'goblintools.master_metadata.json'


def load_master_metadata() -> dict:
    path = metadata_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def iter_enabled_tools(metadata: dict):
    tools = metadata.get('tools') if isinstance(metadata, dict) else None
    if not isinstance(tools, list):
        return []
    out = []
    for record in tools:
        if not isinstance(record, dict):
            continue
        if not bool(record.get('enabled', True)):
            continue
        if str(record.get('tool_id', '')).strip() == 'launcher':
            continue
        out.append(record)
    return out
