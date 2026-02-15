from __future__ import annotations

from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.sort_goblin import (  # noqa: E402
    apply_plan,
    build_sort_plan,
    build_sort_then_rename_plan,
    categorize,
    undo_plan,
    validate_plan,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def with_temp_workspace(fn):
    temp_root = ROOT / 'tests' / f'.tmp_sort_{uuid.uuid4().hex}'
    temp_root.mkdir(parents=True, exist_ok=False)
    try:
        return fn(temp_root)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_categorize():
    assert_true(categorize(Path('x.png')) == 'Images', 'png should map to Images')
    assert_true(categorize(Path('x.mp4')) == 'Videos', 'mp4 should map to Videos')
    assert_true(categorize(Path('x.py')) == 'Code', 'py should map to Code')
    assert_true(categorize(Path('x.unknown')) == 'Other', 'unknown should map to Other')


def test_sort_plan_and_undo():
    def run(root: Path):
        (root / 'a.png').write_text('a', encoding='utf-8')
        (root / 'b.mp4').write_text('b', encoding='utf-8')
        (root / 'c.txt').write_text('c', encoding='utf-8')
        (root / 'sub').mkdir()
        (root / 'sub' / 'inside.png').write_text('ignored', encoding='utf-8')

        plan = build_sort_plan(root)
        ok, errors = validate_plan(plan)
        assert_true(ok, f'sort plan invalid: {errors}')
        assert_true(any(dst.parent.name == 'Images' for _src, dst in plan.moves), 'expected image move')
        assert_true(any(dst.parent.name == 'Videos' for _src, dst in plan.moves), 'expected video move')
        assert_true(any(dst.parent.name == 'Documents' for _src, dst in plan.moves), 'expected document move')

        undo_mapping = apply_plan(plan)
        assert_true((root / 'Images' / 'a.png').exists(), 'sorted image missing')
        assert_true((root / 'Videos' / 'b.mp4').exists(), 'sorted video missing')
        assert_true((root / 'Documents' / 'c.txt').exists(), 'sorted doc missing')
        assert_true((root / 'sub' / 'inside.png').exists(), 'subfolder file should remain unchanged')

        undo_plan(undo_mapping)
        assert_true((root / 'a.png').exists(), 'undo should restore a.png')
        assert_true((root / 'b.mp4').exists(), 'undo should restore b.mp4')
        assert_true((root / 'c.txt').exists(), 'undo should restore c.txt')

    with_temp_workspace(run)


def test_sort_rename_collision_safe():
    def run(root: Path):
        (root / 'hero.png').write_text('1', encoding='utf-8')
        (root / 'villain.png').write_text('2', encoding='utf-8')
        (root / 'Images').mkdir()
        (root / 'Images' / 'asset_001.png').write_text('occupied', encoding='utf-8')

        plan = build_sort_then_rename_plan(
            root,
            {
                'base': 'asset',
                'start_index': 1,
                'pad_width': 3,
                'separator': '_',
                'preserve_extension': True,
                'sanitize': True,
                'include_optional_categories': True,
            },
        )
        ok, errors = validate_plan(plan)
        assert_true(ok, f'sort+rename plan invalid: {errors}')
        undo_mapping = apply_plan(plan)
        produced = sorted(p.name for p in (root / 'Images').glob('asset*.png'))
        assert_true('asset_001.png' in produced, 'existing file should remain')
        assert_true(any(name.startswith('asset_001 (') for name in produced) or 'asset_002.png' in produced, 'collision should be resolved')
        assert_true(len(undo_mapping) >= 2, 'expected undo mapping entries')
        undo_plan(undo_mapping)
        assert_true((root / 'hero.png').exists() and (root / 'villain.png').exists(), 'undo should restore original files')

    with_temp_workspace(run)


def main() -> int:
    tests = [test_categorize, test_sort_plan_and_undo, test_sort_rename_collision_safe]
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
    print(f'\nSort Goblin regression: {passed}/{total} passed, {failed} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
