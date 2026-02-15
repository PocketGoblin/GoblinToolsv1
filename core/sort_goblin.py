from __future__ import annotations

from dataclasses import dataclass, field
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

CATEGORY_ORDER = ['Images', 'Videos', 'Audio', 'Documents', 'Archives', 'Code', 'Other']

CATEGORY_EXTENSIONS = {
    'Images': {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tga', '.tiff', '.tif', '.svg'},
    'Videos': {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v'},
    'Audio': {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac'},
    'Documents': {'.pdf', '.txt', '.md', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'},
    'Archives': {'.zip', '.7z', '.rar', '.tar', '.gz', '.bz2', '.xz'},
    'Code': {'.py', '.js', '.ts', '.json', '.yml', '.yaml', '.cs', '.gd', '.gdshader', '.cpp', '.h', '.java'},
}

OPTIONAL_BUCKETS = {'Archives', 'Code', 'Audio'}


@dataclass
class FileEntry:
    path: Path
    name: str
    ext: str
    category: str
    proposed_path: Path
    status: str = ''
    action: str = ''


@dataclass
class OperationPlan:
    mode: str
    root_dir: Path
    entries: list[FileEntry]
    moves: list[tuple[Path, Path]]
    category_counts: dict[str, int] = field(default_factory=dict)


def sanitize_name(name: str) -> str:
    cleaned = ILLEGAL_CHARS_RE.sub('_', (name or ''))
    cleaned = cleaned.rstrip(' .')
    if not cleaned:
        cleaned = 'unnamed'
    if Path(cleaned).stem.casefold() in RESERVED_NAMES:
        cleaned = f'{Path(cleaned).stem}_'
        suffix = Path(name).suffix
        if suffix:
            cleaned += suffix
    return cleaned


def categorize(path: Path, include_optional_categories: bool = True) -> str:
    ext = path.suffix.lower()
    for category in CATEGORY_ORDER:
        if category == 'Other':
            continue
        if ext in CATEGORY_EXTENSIONS[category]:
            if not include_optional_categories and category in OPTIONAL_BUCKETS:
                return 'Other'
            return category
    return 'Other'


def resolve_collision(dst_path: Path, used_keys: set[str] | None = None) -> Path:
    candidate = dst_path
    stem = dst_path.stem
    suffix = dst_path.suffix
    parent = dst_path.parent
    idx = 2
    while True:
        key = str(candidate).casefold()
        occupied = candidate.exists() or (used_keys is not None and key in used_keys)
        if not occupied:
            return candidate
        candidate = parent / f'{stem} ({idx}){suffix}'
        idx += 1


def _list_top_level_files(dir_path: Path) -> list[Path]:
    root = Path(dir_path)
    if not root.exists() or not root.is_dir():
        raise NotADirectoryError(f'Not a directory: {root}')
    files = [p for p in root.iterdir() if p.is_file()]
    files.sort(key=lambda p: p.name.casefold())
    return files


def _ensure_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _normalize_destinations(moves: list[tuple[Path, Path]]) -> list[tuple[Path, Path]]:
    src_keys = {str(src.resolve()).casefold() for src, _ in moves}
    used_keys = set()
    normalized: list[tuple[Path, Path]] = []
    for src, dst in moves:
        candidate = Path(dst)
        while True:
            key = str(candidate.resolve()).casefold()
            exists_conflict = candidate.exists() and key not in src_keys
            if key in used_keys or exists_conflict:
                candidate = resolve_collision(candidate, used_keys)
                continue
            break
        used_keys.add(str(candidate.resolve()).casefold())
        normalized.append((Path(src), candidate))
    return normalized


def _build_entries_for_sort(root: Path, include_optional_categories: bool) -> tuple[list[FileEntry], dict[str, int]]:
    files = _list_top_level_files(root)
    counts = {category: 0 for category in CATEGORY_ORDER}
    entries: list[FileEntry] = []
    for src in files:
        category = categorize(src, include_optional_categories=include_optional_categories)
        counts[category] += 1
        dst = root / category / src.name
        action = 'Move' if dst != src else 'No-op'
        entries.append(
            FileEntry(
                path=src,
                name=src.name,
                ext=src.suffix.lower(),
                category=category,
                proposed_path=dst,
                status='',
                action=action,
            )
        )
    return entries, counts


def _rename_name_for_index(
    ext: str,
    index: int,
    base: str,
    start_index: int,
    pad_width: int,
    separator: str,
    preserve_extension: bool,
    sanitize: bool,
) -> str:
    safe_base = (base or '').strip() or 'asset'
    safe_sep = separator or ''
    n = start_index + index
    number = str(n).zfill(max(0, int(pad_width))) if int(pad_width) > 0 else str(n)
    proposed = f'{safe_base}{safe_sep}{number}'
    if preserve_extension:
        proposed += ext
    if sanitize:
        proposed = sanitize_name(proposed)
    if Path(proposed).stem.casefold() in RESERVED_NAMES:
        proposed = f'{Path(proposed).stem}_{Path(proposed).suffix}'
    return proposed


def build_sort_plan(dir_path: Path, include_optional_categories: bool = True) -> OperationPlan:
    root = Path(dir_path).resolve()
    entries, counts = _build_entries_for_sort(root, include_optional_categories=include_optional_categories)
    move_candidates = [(entry.path, entry.proposed_path) for entry in entries if entry.path != entry.proposed_path]
    moves = _normalize_destinations(move_candidates)
    dst_by_src = {str(src.resolve()).casefold(): dst for src, dst in moves}
    for entry in entries:
        key = str(entry.path.resolve()).casefold()
        if key in dst_by_src:
            entry.proposed_path = dst_by_src[key]
            entry.action = 'Move'
        else:
            entry.action = 'No-op'
    return OperationPlan(mode='sort', root_dir=root, entries=entries, moves=moves, category_counts=counts)


def build_rename_plan(file_entries: list[FileEntry], rename_options: dict) -> OperationPlan:
    if not file_entries:
        raise ValueError('No file entries to rename.')
    root = file_entries[0].path.parent.resolve()
    entries: list[FileEntry] = []
    moves: list[tuple[Path, Path]] = []
    start = int(rename_options.get('start_index', 1))
    pad = int(rename_options.get('pad_width', 3))
    base = str(rename_options.get('base', 'asset'))
    sep = str(rename_options.get('separator', '_'))
    keep_ext = bool(rename_options.get('preserve_extension', True))
    sanitize = bool(rename_options.get('sanitize', True))

    ordered = sorted(file_entries, key=lambda e: e.path.name.casefold())
    for idx, src_entry in enumerate(ordered):
        new_name = _rename_name_for_index(src_entry.ext, idx, base, start, pad, sep, keep_ext, sanitize)
        dst = src_entry.path.with_name(new_name)
        action = 'Rename' if dst != src_entry.path else 'No-op'
        entry = FileEntry(
            path=src_entry.path,
            name=src_entry.name,
            ext=src_entry.ext,
            category=src_entry.category,
            proposed_path=dst,
            status='',
            action=action,
        )
        entries.append(entry)
        if action != 'No-op':
            moves.append((src_entry.path, dst))

    moves = _normalize_destinations(moves)
    dst_by_src = {str(src.resolve()).casefold(): dst for src, dst in moves}
    for entry in entries:
        key = str(entry.path.resolve()).casefold()
        if key in dst_by_src:
            entry.proposed_path = dst_by_src[key]
            entry.action = 'Rename'
    return OperationPlan(mode='rename', root_dir=root, entries=entries, moves=moves, category_counts={})


def build_sort_then_rename_plan(dir_path: Path, options: dict) -> OperationPlan:
    sort_plan = build_sort_plan(dir_path, include_optional_categories=bool(options.get('include_optional_categories', True)))
    start = int(options.get('start_index', 1))
    base = str(options.get('base', 'asset'))
    pad = int(options.get('pad_width', 3))
    sep = str(options.get('separator', '_'))
    keep_ext = bool(options.get('preserve_extension', True))
    sanitize = bool(options.get('sanitize', True))

    entries: list[FileEntry] = []
    moves: list[tuple[Path, Path]] = []
    counts = dict(sort_plan.category_counts)
    per_cat_index = {cat: start for cat in CATEGORY_ORDER}

    ordered = sorted(sort_plan.entries, key=lambda e: (e.category, e.path.name.casefold()))
    for entry in ordered:
        moved_path = entry.proposed_path
        idx_value = per_cat_index.get(entry.category, start)
        per_cat_index[entry.category] = idx_value + 1
        rename_name = _rename_name_for_index(entry.ext, idx_value - start, base, start, pad, sep, keep_ext, sanitize)
        renamed_path = moved_path.with_name(rename_name)
        action = 'Move+Rename'
        if moved_path == entry.path and renamed_path == entry.path:
            action = 'No-op'
        elif moved_path == entry.path and renamed_path != entry.path:
            action = 'Rename'
        elif moved_path != entry.path and renamed_path == moved_path:
            action = 'Move'
        entries.append(
            FileEntry(
                path=entry.path,
                name=entry.name,
                ext=entry.ext,
                category=entry.category,
                proposed_path=renamed_path,
                status='',
                action=action,
            )
        )
        if renamed_path != entry.path:
            moves.append((entry.path, renamed_path))

    moves = _normalize_destinations(moves)
    dst_by_src = {str(src.resolve()).casefold(): dst for src, dst in moves}
    for entry in entries:
        key = str(entry.path.resolve()).casefold()
        if key in dst_by_src:
            dst = dst_by_src[key]
            if dst.parent != entry.path.parent and dst.name != entry.path.name:
                entry.action = 'Move+Rename'
            elif dst.parent != entry.path.parent:
                entry.action = 'Move'
            elif dst.name != entry.path.name:
                entry.action = 'Rename'
            entry.proposed_path = dst
        else:
            entry.action = 'No-op'

    return OperationPlan(mode='sort_rename', root_dir=Path(dir_path).resolve(), entries=entries, moves=moves, category_counts=counts)


def validate_plan(plan: OperationPlan) -> tuple[bool, list[str]]:
    errors: list[str] = []
    root = plan.root_dir.resolve()
    seen_dst: set[str] = set()

    for src, dst in plan.moves:
        if not src.exists():
            errors.append(f'Missing source: {src}')
        if not _ensure_within_root(src, root):
            errors.append(f'Source outside root: {src}')
        if not _ensure_within_root(dst, root):
            errors.append(f'Destination outside root: {dst}')
        key = str(dst.resolve()).casefold()
        if key in seen_dst:
            errors.append(f'Duplicate destination: {dst}')
        seen_dst.add(key)
    return len(errors) == 0, errors


def _tmp_path_for(src: Path) -> Path:
    while True:
        candidate = src.with_name(f'.__sortgoblin_tmp__{uuid.uuid4().hex}__{src.name}')
        if not candidate.exists():
            return candidate


def apply_plan(plan: OperationPlan) -> list[tuple[Path, Path]]:
    ok, errors = validate_plan(plan)
    if not ok:
        raise RuntimeError('; '.join(errors))
    if not plan.moves:
        return []

    mapping = [(Path(src).resolve(), Path(dst).resolve()) for src, dst in plan.moves]
    temp_for_src: dict[Path, Path] = {}
    phase1_done: list[tuple[Path, Path]] = []
    phase2_done: list[tuple[Path, Path]] = []

    try:
        for src, _dst in mapping:
            temp = _tmp_path_for(src)
            src.rename(temp)
            temp_for_src[src] = temp
            phase1_done.append((temp, src))

        for src, dst in mapping:
            temp = temp_for_src[src]
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                dst = resolve_collision(dst)
            temp.rename(dst)
            phase2_done.append((src, dst))
    except Exception:
        for original_src, final_dst in reversed(phase2_done):
            temp = temp_for_src.get(original_src)
            if temp is not None and final_dst.exists():
                final_dst.rename(temp)
        for temp, src in reversed(phase1_done):
            if temp.exists():
                temp.rename(src)
        raise

    return phase2_done


def undo_plan(undo_mapping: list[tuple[Path, Path]]) -> list[tuple[Path, Path]]:
    if not undo_mapping:
        return []
    reverse_plan = OperationPlan(
        mode='undo',
        root_dir=Path(undo_mapping[0][0]).resolve().parent,
        entries=[],
        moves=[(final, original) for original, final in undo_mapping],
        category_counts={},
    )
    return apply_plan(reverse_plan)
