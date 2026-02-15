from __future__ import annotations

from dataclasses import dataclass
import os

from .ai_client import AIClientError, ai_explain
from .parser import detect_engine, parse_error
from .rules import match_godot_rule, match_python_rule, match_unity_rule


@dataclass
class ExplanationResult:
    engine: str
    summary: str
    what_it_means: str
    likely_cause: str
    first_step: str
    confidence: float
    source: str  # "local" | "ai"


def _from_rule(engine: str, rule: dict) -> ExplanationResult:
    return ExplanationResult(
        engine=engine,
        summary=rule['summary'],
        what_it_means=rule['what_it_means'],
        likely_cause=rule['likely_cause'],
        first_step=rule['first_step'],
        confidence=float(rule.get('confidence', 0.75)),
        source='local',
    )


def _local_match(text: str, engine: str) -> ExplanationResult | None:
    if engine == 'godot':
        rule = match_godot_rule(text)
        return _from_rule(engine, rule) if rule else None
    if engine == 'python':
        rule = match_python_rule(text)
        return _from_rule(engine, rule) if rule else None
    if engine == 'unity':
        rule = match_unity_rule(text)
        return _from_rule(engine, rule) if rule else None

    # unknown: try all
    for eng, fn in (('godot', match_godot_rule), ('python', match_python_rule), ('unity', match_unity_rule)):
        rule = fn(text)
        if rule:
            return _from_rule(eng, rule)
    return None


def explain_error(text: str, engine_override: str | None = None, allow_ai: bool = True) -> ExplanationResult:
    raw = (text or '').strip()
    if not raw:
        raise ValueError('Paste error text first.')

    parsed = parse_error(raw)
    engine = (engine_override or '').strip().lower()
    if not engine or engine == 'auto':
        engine = parsed.engine_guess

    local = _local_match(raw, engine)
    if local and local.confidence >= 0.75:
        return local

    safe_mode = str(os.getenv('GOBLINTOOLS_SAFE_MODE', '')).strip().lower() in {'1', 'true', 'yes', 'on'}
    if safe_mode:
        allow_ai = False

    if not allow_ai:
        return ExplanationResult(
            engine=(engine or parsed.engine_guess or 'unknown'),
            summary='No strong local match.',
            what_it_means='The error did not match a high-confidence built-in rule.',
            likely_cause='This issue may require project-specific context or AI-assisted interpretation.',
            first_step='Enable AI fallback for deeper analysis, or provide a fuller stack trace and relevant code line.',
            confidence=0.35,
            source='local',
        )

    ai = ai_explain(raw, engine, parsed.key_lines, parsed.stack_frames)
    try:
        conf = float(ai.get('confidence', 0.6))
    except Exception:
        conf = 0.6
    conf = max(0.0, min(1.0, conf))
    return ExplanationResult(
        engine=engine,
        summary=str(ai.get('summary', 'No summary provided.')),
        what_it_means=str(ai.get('what_it_means', 'No explanation provided.')),
        likely_cause=str(ai.get('likely_cause', 'No likely cause provided.')),
        first_step=str(ai.get('first_step', 'No first step provided.')),
        confidence=conf,
        source='ai',
    )


def safe_explain_error(text: str, engine_override: str | None = None, allow_ai: bool = True) -> ExplanationResult:
    try:
        return explain_error(text, engine_override=engine_override, allow_ai=allow_ai)
    except AIClientError:
        fallback_engine = (engine_override or '').strip().lower()
        if not fallback_engine or fallback_engine == 'auto':
            fallback_engine = detect_engine(text)
        return ExplanationResult(
            engine=(fallback_engine or 'unknown'),
            summary='Could not use AI fallback.',
            what_it_means='No strong local match and AI fallback failed.',
            likely_cause='Missing/invalid API key, network issue, or malformed AI response.',
            first_step='Set goblintools_api_key and retry. If already set, verify internet access.',
            confidence=0.2,
            source='ai',
        )
