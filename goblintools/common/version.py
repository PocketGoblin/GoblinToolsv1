from __future__ import annotations

APP_NAME = 'GoblinTools'
APP_VERSION = 'v1.0.0'
BUILD_STAMP = 'v1.0.0'

TOOL_VERSIONS = {
    'launcher': APP_VERSION,
    'palette_goblin': APP_VERSION,
    'slicer_goblin': APP_VERSION,
    'zip_goblin': APP_VERSION,
    'error_goblin': APP_VERSION,
    'sort_goblin': APP_VERSION,
    'rename_goblin': APP_VERSION,
}


def tool_version(tool_id: str) -> str:
    return TOOL_VERSIONS.get(tool_id, APP_VERSION)


def tool_title(tool_name: str, tool_id: str) -> str:
    return f'{tool_name} {tool_version(tool_id)}'


def version_text() -> str:
    return APP_VERSION
