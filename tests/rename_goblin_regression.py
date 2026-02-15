from __future__ import annotations

from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.rename_goblin import (  # noqa: E402
    FileItem,
    apply_rename,
    generate_names,
    plan_rename,
    sanitize_name,
    undo_rename,
    validate,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def with_temp_workspace(fn):
    temp_root = ROOT / 'tests' / f'.tmp_rename_{uuid.uuid4().hex}'
    temp_root.mkdir(parents=True, exist_ok=False)
    try:
        return fn(temp_root)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_sanitize():
    assert_true(sanitize_name('bad<>:"/\\|?*name  .') == 'bad_________name', 'sanitize_name failed illegal char cleanup')
    assert_true(sanitize_name('ok_name') == 'ok_name', 'sanitize_name changed safe name')


def test_validate_and_plan():
    def run(root: Path):
        a = root / 'a.png'
        b = root / 'b.png'
        conflict = root / 'exists.png'
        a.write_text('a', encoding='utf-8')
        b.write_text('b', encoding='utf-8')
        conflict.write_text('x', encoding='utf-8')

        items = [
            FileItem(path=a, current_name='a.png', ext='.png', proposed_name='asset_001.png'),
            FileItem(path=b, current_name='b.png', ext='.png', proposed_name='asset_001.png'),
        ]
        report = validate(items)
        assert_true(not report['valid'], 'duplicate targets should be invalid')
        assert_true(report['issues']['duplicate'] >= 2, 'duplicate issue count mismatch')

        items[1].proposed_name = 'con.png'
        report = validate(items)
        assert_true(not report['valid'], 'reserved names should be invalid')
        assert_true(report['issues']['reserved'] >= 1, 'reserved issue count mismatch')

        items[1].proposed_name = 'exists.png'
        report = validate(items)
        assert_true(not report['valid'], 'existing target should be invalid')
        assert_true(report['issues']['exists'] >= 1, 'exists issue count mismatch')

        items[1].proposed_name = 'asset_002.png'
        report = validate(items)
        assert_true(report['valid'], 'valid proposal should pass')
        plan = plan_rename(items)
        assert_true(len(plan) == 2, 'plan_rename expected two moves')
    with_temp_workspace(run)


def test_apply_and_undo():
    def run(root: Path):
        a = root / 'old_a.txt'
        b = root / 'old_b.txt'
        a.write_text('A', encoding='utf-8')
        b.write_text('B', encoding='utf-8')

        items = [
            FileItem(path=a, current_name=a.name, ext='.txt', proposed_name=a.name),
            FileItem(path=b, current_name=b.name, ext='.txt', proposed_name=b.name),
        ]
        generate_names(items, base='game_asset', start_index=1, pad_width=3, separator='_', keep_ext=True)
        report = validate(items)
        assert_true(report['valid'], 'generated names should be valid')
        rename_plan = plan_rename(items)

        undo_plan = apply_rename(rename_plan)
        assert_true((root / 'game_asset_001.txt').exists(), 'renamed file 1 missing')
        assert_true((root / 'game_asset_002.txt').exists(), 'renamed file 2 missing')
        assert_true(not a.exists() and not b.exists(), 'old files should not exist after apply')

        undo_rename(undo_plan)
        assert_true(a.exists() and b.exists(), 'undo should restore original files')
        assert_true(not (root / 'game_asset_001.txt').exists(), 'undo should remove generated names')
    with_temp_workspace(run)


def main() -> int:
    tests = [test_sanitize, test_validate_and_plan, test_apply_and_undo]
    passed = 0
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f'PASS {fn.__name__}')
            passed += 1
        except Exception as exc:
            print(f'FAIL {fn.__name__}: {exc}')
            failed += 1
    total = passed + failed
    print(f'\nRename Goblin regression: {passed}/{total} passed, {failed} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
