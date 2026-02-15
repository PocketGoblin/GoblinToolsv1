from __future__ import annotations

import json
import os
from urllib import request, error


class AIClientError(RuntimeError):
    pass


AI_CONTEXT_CHAR_LIMIT = 12000


def _api_key() -> str:
    key = os.getenv('goblintools_api_key') or os.getenv('GOBLINTOOLS_API_KEY')
    if not key:
        raise AIClientError('Missing API key. Set goblintools_api_key environment variable.')
    return key.strip()


def _extract_json(text: str) -> dict:
    text = (text or '').strip()
    if not text:
        raise AIClientError('AI returned empty output.')
    try:
        return json.loads(text)
    except Exception:
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise AIClientError('AI output was not valid JSON.')


def ai_explain(error_text: str, engine: str, key_lines: list[str], stack_frames: list[str]) -> dict:
    key = _api_key()
    prompt = (
        'You are Error Goblin. Return JSON only, no prose, no markdown.\n'
        'Required keys exactly: summary, what_it_means, likely_cause, first_step, confidence.\n'
        'confidence must be a float between 0 and 1.\n'
        f'Engine guess: {engine}\n'
        f'Key lines: {key_lines}\n'
        f'Stack frames: {stack_frames[:8]}\n'
        'Error text follows:\n'
        f'{error_text[:AI_CONTEXT_CHAR_LIMIT]}'
    )

    payload = {
        'model': 'gpt-4o-mini',
        'messages': [
            {'role': 'system', 'content': 'Return JSON only.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.2,
        'response_format': {'type': 'json_object'},
    }

    req = request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with request.urlopen(req, timeout=35) as resp:
            body = resp.read().decode('utf-8', errors='replace')
    except error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise AIClientError(f'AI request failed: HTTP {exc.code}. {detail[:300]}') from exc
    except Exception as exc:
        raise AIClientError(f'AI request failed: {exc}') from exc

    try:
        data = json.loads(body)
        content = data['choices'][0]['message']['content']
    except Exception as exc:
        raise AIClientError('Unexpected AI response format.') from exc

    parsed = _extract_json(content)
    for key_name in ('summary', 'what_it_means', 'likely_cause', 'first_step', 'confidence'):
        if key_name not in parsed:
            raise AIClientError(f'AI output missing key: {key_name}')
    return parsed
