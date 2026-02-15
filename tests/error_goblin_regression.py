from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.error_goblin.explain import explain_error, safe_explain_error


@dataclass
class Case:
    name: str
    text: str
    expect_engine: str
    expect_source: str
    summary_has: str


CASES = [
    Case(
        name='python_module_not_found',
        text="ModuleNotFoundError: No module named 'tomli'",
        expect_engine='python',
        expect_source='local',
        summary_has='Import failed',
    ),
    Case(
        name='python_attribute',
        text="AttributeError: 'NoneType' object has no attribute 'split'",
        expect_engine='python',
        expect_source='local',
        summary_has='Missing attribute',
    ),
    Case(
        name='godot_invalid_set_index',
        text='Invalid set index "hp" (on base: "Dictionary").\nres://player.gd:18',
        expect_engine='godot',
        expect_source='local',
        summary_has='Invalid set index',
    ),
    Case(
        name='godot_parser_error',
        text='Parser Error: Expected ":" after "if" condition.\nres://enemy.gd:42',
        expect_engine='godot',
        expect_source='local',
        summary_has='parser error',
    ),
    Case(
        name='unity_unassigned_reference',
        text='UnassignedReferenceException: The variable target of Enemy has not been assigned.',
        expect_engine='unity',
        expect_source='local',
        summary_has='unassigned',
    ),
    Case(
        name='unity_scene_not_in_build_settings',
        text="Scene 'Arena' couldn't be loaded because it has not been added to the build settings",
        expect_engine='unity',
        expect_source='local',
        summary_has='Scene failed to load',
    ),
]


def run_cases() -> tuple[int, int]:
    passed = 0
    failed = 0
    for case in CASES:
        try:
            result = explain_error(case.text, engine_override='auto')
            assert result.engine == case.expect_engine, (
                f'engine mismatch: expected={case.expect_engine} got={result.engine}'
            )
            assert result.source == case.expect_source, (
                f'source mismatch: expected={case.expect_source} got={result.source}'
            )
            assert case.summary_has.lower() in result.summary.lower(), (
                f'summary mismatch: expected substring={case.summary_has!r} got={result.summary!r}'
            )
            passed += 1
            print(f'PASS {case.name}')
        except Exception as exc:
            failed += 1
            print(f'FAIL {case.name}: {exc}')
    return passed, failed


def run_ai_fallback_case() -> tuple[int, int]:
    # No API key expected in local dev by default; safe_explain_error should still return a structured result.
    text = 'Unhandled runtime failure with no known local pattern'
    result = safe_explain_error(text, engine_override='auto')
    passed = 0
    failed = 0
    if result.source == 'ai' and result.summary:
        print('PASS ai_fallback_shape')
        passed += 1
    else:
        print('FAIL ai_fallback_shape: safe fallback response malformed')
        failed += 1

    local_only = safe_explain_error(text, engine_override='auto', allow_ai=False)
    if local_only.source == 'local' and 'No strong local match' in local_only.summary:
        print('PASS local_only_mode')
        passed += 1
    else:
        print('FAIL local_only_mode: local-only fallback response malformed')
        failed += 1
    return passed, failed


def main() -> int:
    passed_1, failed_1 = run_cases()
    passed_2, failed_2 = run_ai_fallback_case()
    passed = passed_1 + passed_2
    failed = failed_1 + failed_2
    total = passed + failed
    print(f'\nError Goblin regression: {passed}/{total} passed, {failed} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
