from __future__ import annotations

from pathlib import Path
import py_compile
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {'build', 'dist', '__pycache__', '.git'}


def iter_python_files(root: Path):
    for path in root.rglob('*.py'):
        rel_parts = path.relative_to(root).parts
        if any(part in EXCLUDED_DIRS for part in rel_parts):
            continue
        yield path


def compile_check() -> bool:
    print('== Compile check ==', flush=True)
    ok = True
    for py_file in sorted(iter_python_files(ROOT)):
        try:
            py_compile.compile(str(py_file), doraise=True)
        except Exception as exc:
            ok = False
            rel = py_file.relative_to(ROOT)
            print(f'FAIL compile: {rel} -> {exc}')
    if ok:
        print('PASS compile', flush=True)
    return ok


def _run_script(label: str, script_path: Path) -> bool:
    print(f'\n== {label} ==', flush=True)
    cmd = [sys.executable, str(script_path)]
    completed = subprocess.run(cmd, cwd=str(ROOT))
    return completed.returncode == 0


def regression_check() -> bool:
    ok_error = _run_script('Error Goblin regression', ROOT / 'tests' / 'error_goblin_regression.py')
    ok_rename = _run_script('Rename Goblin regression', ROOT / 'tests' / 'rename_goblin_regression.py')
    ok_sort = _run_script('Sort Goblin regression', ROOT / 'tests' / 'sort_goblin_regression.py')
    return ok_error and ok_rename and ok_sort


def main() -> int:
    ok_compile = compile_check()
    ok_regression = regression_check() if ok_compile else False

    print('\n== Summary ==')
    print(f'compile: {"PASS" if ok_compile else "FAIL"}')
    print(f'regression: {"PASS" if ok_regression else "FAIL"}')
    return 0 if (ok_compile and ok_regression) else 1


if __name__ == '__main__':
    raise SystemExit(main())
