from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass
class ParsedError:
    engine_guess: str
    key_lines: list[str]
    stack_frames: list[str]


def detect_engine(text: str) -> str:
    t = (text or '').lower()
    if any(
        k in t
        for k in (
            'godot',
            'res://',
            '.gd:',
            'invalid get index',
            'invalid set index',
            'base nil',
            'parser error',
            'attempt to call function',
            'nonexistent function',
        )
    ):
        return 'godot'
    if any(
        k in t
        for k in (
            'unity',
            'nullreferenceexception',
            'missingreferenceexception',
            'unassignedreferenceexception',
            'missingcomponentexception',
            'argumentnullexception',
            'indexoutofrangeexception',
            'assets/',
        )
    ):
        return 'unity'
    if any(
        k in t
        for k in (
            'traceback (most recent call last)',
            'keyerror:',
            'typeerror:',
            'attributeerror:',
            'nameerror:',
            'modulenotfounderror:',
            'importerror:',
            'jsondecodeerror:',
            'filenotfounderror:',
            'syntaxerror:',
            'indentationerror:',
        )
    ):
        return 'python'
    return 'unknown'


def extract_key_lines(text: str) -> list[str]:
    lines = [ln.strip() for ln in (text or '').splitlines() if ln.strip()]
    score_terms = (
        'error',
        'exception',
        'traceback',
        'invalid',
        'null',
        'nil',
        'not found',
        'failed',
        'typeerror',
        'keyerror',
        'indexerror',
        'attributeerror',
        'nameerror',
        'importerror',
        'modulenotfounderror',
        'jsondecodeerror',
        'syntaxerror',
        'indentationerror',
        'filenotfounderror',
    )
    scored = []
    for ln in lines:
        low = ln.lower()
        score = sum(1 for s in score_terms if s in low)
        if score > 0:
            scored.append((score, ln))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = [ln for _s, ln in scored[:6]]
    return out if out else lines[:4]


def extract_stack_frames(text: str) -> list[str]:
    lines = [ln.rstrip() for ln in (text or '').splitlines()]
    frames = []
    py_frame = re.compile(r'^\s*File\s+".*?", line \d+')
    gd_frame = re.compile(r'.+\.gd:\d+')
    unity_frame = re.compile(r'^\s*at\s+.+\(.+:\d+\)')
    for ln in lines:
        if py_frame.search(ln) or gd_frame.search(ln) or unity_frame.search(ln):
            frames.append(ln.strip())
    return frames[:20]


def parse_error(text: str) -> ParsedError:
    return ParsedError(
        engine_guess=detect_engine(text),
        key_lines=extract_key_lines(text),
        stack_frames=extract_stack_frames(text),
    )
