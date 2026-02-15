from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess


class ArchiveEngineError(RuntimeError):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def find_7z_binary() -> str:
    bundled_variants = [
        _repo_root() / 'tools' / '7zip' / '7z.exe',
        _repo_root() / 'tools' / '7-Zip' / '7z.exe',
    ]
    for bundled in bundled_variants:
        if bundled.exists():
            return str(bundled)

    system = shutil.which('7z')
    if system:
        return system

    raise ArchiveEngineError(
        '7-Zip was not found. Place 7z at tools/7zip/7z.exe or install 7z on PATH.'
    )


def _run_7z(args: list[str]) -> subprocess.CompletedProcess:
    exe = find_7z_binary()
    cmd = [exe] + args
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or '').strip()
        raise ArchiveEngineError(err or f'7z failed with code {proc.returncode}')
    return proc


def _parse_slt(output: str, archive_path: Path) -> list[dict]:
    entries = []
    block = {}

    def flush():
        nonlocal block
        if not block:
            return
        raw_path = block.get('Path')
        if not raw_path:
            block = {}
            return
        # Skip archive metadata block
        if Path(raw_path) == archive_path and 'Type' in block:
            block = {}
            return

        is_dir = block.get('Folder', '').strip() == '+'
        if not is_dir and block.get('Attributes', '').startswith('D'):
            is_dir = True

        try:
            size = int(block.get('Size', '0') or '0')
        except ValueError:
            size = 0

        entries.append(
            {
                'path': raw_path.replace('\\', '/'),
                'size': size,
                'modified': block.get('Modified', ''),
                'is_dir': is_dir,
            }
        )
        block = {}

    for line in output.splitlines():
        line = line.rstrip('\r\n')
        if not line.strip():
            flush()
            continue
        if ' = ' in line:
            k, v = line.split(' = ', 1)
            block[k.strip()] = v.strip()

    flush()
    return entries


def list_archive(path: str | os.PathLike) -> list[dict]:
    archive_path = Path(path).resolve()
    if not archive_path.exists():
        raise ArchiveEngineError(f'Archive not found: {archive_path}')

    proc = _run_7z(['l', '-slt', str(archive_path)])
    return _parse_slt(proc.stdout, archive_path)


def _validate_member_path(member: str):
    if not member or not member.strip():
        raise ArchiveEngineError('Archive entry contains an empty path.')
    normalized = member.replace('\\', '/')
    if re.match(r'^[A-Za-z]:', normalized):
        raise ArchiveEngineError(f'Blocked unsafe archive path: {member}')

    p = PurePosixPath(normalized)
    if p.is_absolute() or '..' in p.parts:
        raise ArchiveEngineError(f'Blocked unsafe archive path: {member}')


def _validate_members_safe(members: list[str]):
    for m in members:
        _validate_member_path(m)


def _normalize_output_dir(out_dir: str | os.PathLike) -> Path:
    out_path = Path(out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)
    return out_path


def extract_all(path: str | os.PathLike, out_dir: str | os.PathLike, password: str | None = None):
    archive_path = Path(path).resolve()
    out_path = _normalize_output_dir(out_dir)
    entries = list_archive(archive_path)
    _validate_members_safe([e['path'] for e in entries if e.get('path')])

    args = ['x', str(archive_path), f'-o{out_path}', '-y']
    if password:
        args.append(f'-p{password}')
    _run_7z(args)
    return {'count': len(entries), 'output_dir': str(out_path)}


def extract_selected(
    path: str | os.PathLike,
    out_dir: str | os.PathLike,
    members: list[str],
    password: str | None = None,
):
    archive_path = Path(path).resolve()
    out_path = _normalize_output_dir(out_dir)
    members = [m for m in members if m]
    if not members:
        raise ArchiveEngineError('No archive members were selected.')
    _validate_members_safe(members)

    args = ['x', str(archive_path), f'-o{out_path}', '-y']
    if password:
        args.append(f'-p{password}')
    args.extend(members)
    _run_7z(args)
    return {'count': len(members), 'output_dir': str(out_path)}


def create_archive(
    out_path: str | os.PathLike,
    input_paths: list[str | os.PathLike],
    format: str = 'zip',
    level: str = 'normal',
):
    fmt = (format or 'zip').lower()
    if fmt not in ('zip', '7z'):
        raise ArchiveEngineError('Unsupported format. Use zip or 7z.')

    level_map = {
        'store': '0',
        'fast': '3',
        'normal': '5',
        'maximum': '7',
        'ultra': '9',
    }
    mx = level_map.get((level or 'normal').lower(), '5')

    in_paths = [str(Path(p).resolve()) for p in input_paths if p]
    if not in_paths:
        raise ArchiveEngineError('No input files/folders provided for archive creation.')
    for p in in_paths:
        if not Path(p).exists():
            raise ArchiveEngineError(f'Input path not found: {p}')

    target = Path(out_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    args = ['a', str(target), f'-t{fmt}', f'-mx={mx}', '-y'] + in_paths
    _run_7z(args)
    return {'archive': str(target), 'count': len(in_paths)}
