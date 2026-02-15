from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import uuid


ILLEGAL_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_NAMES = {
    'con',
    'prn',
    'aux',
    'nul',
    'com1',
    'com2',
    'com3',
    'com4',
    'com5',
    'com6',
    'com7',
    'com8',
    'com9',
    'lpt1',
    'lpt2',
    'lpt3',
    'lpt4',
    'lpt5',
    'lpt6',
    'lpt7',
    'lpt8',
    'lpt9',
}


@dataclass
class FileItem:
    path: Path
    current_name: str
    ext: str
    proposed_name: str
    status: str = ''


def sanitize_name(name: str) -> str:
    cleaned = ILLEGAL_CHARS_RE.sub('_', (name or ''))
    cleaned = cleaned.rstrip(' .')
    return cleaned


def generate_names(
    items: list[FileItem],
    base: str,
    start_index: int,
    pad_width: int,
    separator: str,
    keep_ext: bool = True,
) -> list[FileItem]:
    base_value = (base or '').strip() or 'asset'
    index_value = max(0, int(start_index))
    width_value = max(0, int(pad_width))
    sep_value = separator or ''

    for offset, item in enumerate(items):
        number = str(index_value + offset).zfill(width_value) if width_value > 0 else str(index_value + offset)
        item.proposed_name = f'{base_value}{sep_value}{number}'
        if keep_ext:
            item.proposed_name += item.ext
        item.status = ''
    return items


def _status_is_error(status: str) -> bool:
    return bool(status and status != 'no-op')


def _is_reserved(name: str) -> bool:
    stem = Path(name).stem.casefold().strip()
    return stem in RESERVED_NAMES


def validate(items: list[FileItem]) -> dict:
    issues = {
        'empty': 0,
        'illegal': 0,
        'reserved': 0,
        'duplicate': 0,
        'exists': 0,
        'no_op': 0,
    }

    src_paths = {Path(item.path) for item in items}
    duplicate_buckets: dict[tuple[str, str], list[int]] = {}
    target_path_for_idx: dict[int, Path] = {}

    for idx, item in enumerate(items):
        proposed = item.proposed_name or ''
        item.status = ''

        if not proposed:
            item.status = 'empty name'
            issues['empty'] += 1
            continue
        if proposed in {'.', '..'}:
            item.status = 'illegal name'
            issues['illegal'] += 1
            continue
        if ILLEGAL_CHARS_RE.search(proposed) or proposed.rstrip(' .') != proposed:
            item.status = 'illegal chars'
            issues['illegal'] += 1
            continue
        if _is_reserved(proposed):
            item.status = 'reserved name'
            issues['reserved'] += 1
            continue

        dst = item.path.with_name(proposed)
        target_path_for_idx[idx] = dst

        dup_key = (str(dst.parent).casefold(), proposed.casefold())
        duplicate_buckets.setdefault(dup_key, []).append(idx)

        if proposed == item.current_name:
            item.status = 'no-op'
            issues['no_op'] += 1

    for _key, indexes in duplicate_buckets.items():
        if len(indexes) < 2:
            continue
        for idx in indexes:
            items[idx].status = 'duplicate target'
            issues['duplicate'] += 1

    for idx, dst in target_path_for_idx.items():
        item = items[idx]
        if _status_is_error(item.status):
            continue
        if dst in src_paths:
            continue
        if dst.exists():
            item.status = 'target exists'
            issues['exists'] += 1

    error_count = sum(1 for item in items if _status_is_error(item.status))
    change_count = sum(1 for item in items if item.proposed_name != item.current_name and not _status_is_error(item.status))
    return {
        'valid': error_count == 0,
        'error_count': error_count,
        'change_count': change_count,
        'issues': issues,
    }


def plan_rename(items: list[FileItem]) -> list[tuple[Path, Path]]:
    plan: list[tuple[Path, Path]] = []
    for item in items:
        if _status_is_error(item.status):
            continue
        if item.proposed_name == item.current_name:
            continue
        plan.append((Path(item.path), item.path.with_name(item.proposed_name)))
    return plan


def _unique_temp_path(src: Path) -> Path:
    while True:
        temp_name = f'.__goblintmp__{uuid.uuid4().hex}__{src.name}'
        candidate = src.with_name(temp_name)
        if not candidate.exists():
            return candidate


def apply_rename(plan: list[tuple[Path, Path]]) -> list[tuple[Path, Path]]:
    if not plan:
        return []

    normalized = [(Path(src), Path(dst)) for src, dst in plan]
    temp_map: dict[Path, Path] = {}
    moved_phase1: list[tuple[Path, Path]] = []
    moved_phase2: list[tuple[Path, Path]] = []

    try:
        for src, _dst in normalized:
            if not src.exists():
                raise FileNotFoundError(f'Missing source file: {src}')
            temp = _unique_temp_path(src)
            src.rename(temp)
            temp_map[src] = temp
            moved_phase1.append((temp, src))

        for src, dst in normalized:
            temp = temp_map[src]
            if dst.exists() and dst != temp:
                raise FileExistsError(f'Target already exists: {dst}')
            temp.rename(dst)
            moved_phase2.append((dst, src))
    except Exception:
        # Roll back phase 2 moves to temp names.
        for final_dst, original_src in reversed(moved_phase2):
            temp = temp_map.get(original_src)
            if temp is not None and final_dst.exists():
                final_dst.rename(temp)
        # Roll back all temp names to original sources.
        for temp, src in reversed(moved_phase1):
            if temp.exists():
                temp.rename(src)
        raise

    return moved_phase2


def undo_rename(last_plan_reverse: list[tuple[Path, Path]]) -> list[tuple[Path, Path]]:
    return apply_rename(last_plan_reverse)
