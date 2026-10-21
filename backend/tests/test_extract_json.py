"""Regression tests for structured-JSON extraction.

Both failure modes covered here used to escape as the wrong exception:
an unclosed code fence raised ``ValueError: substring not found`` from
``str.index``, and invalid JSON inside a fence leaked a raw ``JSONDecodeError``
out of the ``except`` handler. Callers could not distinguish a malformed model
response from a bug in this module.
"""

from __future__ import annotations

import json

import pytest

from app.services import llm_client


def _stub(monkeypatch, content: str) -> None:
    async def fake_chat_completion(*args, **kwargs):
        return {"content": content, "model": "stub", "usage": {}, "raw": {}}

    monkeypatch.setattr(llm_client, "chat_completion", fake_chat_completion)


async def _extract(monkeypatch, content: str):
    _stub(monkeypatch, content)
    return await llm_client.extract_json("system prompt", "user input")


async def test_plain_json_is_parsed(monkeypatch):
    assert await _extract(monkeypatch, '{"name": "雨天"}') == {"name": "雨天"}


async def test_fenced_json_with_language_tag(monkeypatch):
    content = '```json\n{"a": 1}\n```'
    assert await _extract(monkeypatch, content) == {"a": 1}


async def test_fenced_json_without_language_tag(monkeypatch):
    content = '```\n{"a": 1}\n```'
    assert await _extract(monkeypatch, content) == {"a": 1}


async def test_unclosed_fence_still_parses_complete_json(monkeypatch):
    """A response truncated after the brace but before the fence can recover."""
    content = '```json\n{"a": 1}'
    assert await _extract(monkeypatch, content) == {"a": 1}


async def test_unclosed_fence_with_truncated_json_raises_descriptive_error(monkeypatch):
    content = '```json\n{"a": 1'
    with pytest.raises(ValueError, match="Could not parse JSON"):
        await _extract(monkeypatch, content)


async def test_invalid_json_inside_fence_raises_descriptive_error(monkeypatch):
    content = '```json\n{not valid json}\n```'
    with pytest.raises(ValueError, match="Could not parse JSON"):
        await _extract(monkeypatch, content)


async def test_trailing_comma_is_repaired(monkeypatch):
    assert await _extract(monkeypatch, '{"a": 1,}') == {"a": 1}
    assert await _extract(monkeypatch, '{"items": [1, 2,]}') == {"items": [1, 2]}


async def test_trailing_comma_inside_fence_is_repaired(monkeypatch):
    content = '```json\n{"a": 1,}\n```'
    assert await _extract(monkeypatch, content) == {"a": 1}


async def test_failure_preserves_the_parse_cause(monkeypatch):
    content = "totally not json"
    with pytest.raises(ValueError) as excinfo:
        await _extract(monkeypatch, content)
    assert isinstance(excinfo.value.__cause__, json.JSONDecodeError)


@pytest.mark.parametrize(
    "content",
    ['{"a": "值"}', '```json\n{"a": "值"}\n```', '  {"a": "值"}  '],
)
async def test_unicode_payloads_round_trip(monkeypatch, content):
    assert await _extract(monkeypatch, content) == {"a": "值"}
