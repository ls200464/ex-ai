"""Regression tests for the chunking strategies."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.utils.chunking import (
    chunk_by_characters,
    chunk_by_time_gap,
    chunk_messages,
)
from app.utils.normalization import UnifiedMessage


def _msgs(count: int, size: int, sender: str = "a") -> list[UnifiedMessage]:
    return [UnifiedMessage(sender_name=sender, sender_role="user", content="x" * size)
            for _ in range(count)]


def test_chunk_size_is_respected():
    chunks = chunk_by_characters(_msgs(10, 100), chunk_size=300, overlap=50)
    assert len(chunks) > 1
    for chunk in chunks:
        assert sum(len(m.content) for m in chunk) <= 300


def test_overlap_larger_than_chunk_does_not_duplicate_everything():
    """An overlap >= chunk_size used to carry the whole chunk forward, so each
    chunk grew instead of advancing and duplicate content multiplied."""
    messages = _msgs(6, 10)
    chunks = chunk_by_characters(messages, chunk_size=20, overlap=500)
    copies = sum(len(chunk) for chunk in chunks)
    assert copies <= len(messages) * 3
    assert len(chunks) <= len(messages)


def test_overlap_is_clamped_not_rejected():
    chunks = chunk_by_characters(_msgs(4, 10), chunk_size=25, overlap=10_000)
    assert chunks


def test_single_message_larger_than_chunk_still_produces_a_chunk():
    chunks = chunk_by_characters(_msgs(1, 1000), chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0][0].content == "x" * 1000


def test_invalid_chunk_size_is_rejected():
    with pytest.raises(ValueError):
        chunk_by_characters(_msgs(2, 10), chunk_size=0)
    with pytest.raises(ValueError):
        chunk_by_characters(_msgs(2, 10), chunk_size=-5)


def test_empty_input_returns_no_chunks():
    assert chunk_by_characters([], chunk_size=100, overlap=10) == []
    assert chunk_by_time_gap([]) == []


def test_time_gap_splits_conversations():
    start = datetime(2023, 1, 15, 10, 0, 0)
    messages = [
        UnifiedMessage("a", "user", "one", original_timestamp=start),
        UnifiedMessage("a", "user", "two", original_timestamp=start + timedelta(minutes=5)),
        UnifiedMessage("a", "user", "three", original_timestamp=start + timedelta(hours=5)),
    ]
    chunks = chunk_by_time_gap(messages, gap_threshold_hours=2.0)
    assert len(chunks) == 2
    assert [m.content for m in chunks[0]] == ["one", "two"]
    assert [m.content for m in chunks[1]] == ["three"]


def test_missing_timestamps_stay_together():
    messages = [
        UnifiedMessage("a", "user", "one"),
        UnifiedMessage("a", "user", "two"),
    ]
    assert len(chunk_by_time_gap(messages, gap_threshold_hours=2.0)) == 1


def test_chunk_messages_never_returns_empty_chunks():
    chunks = chunk_messages(_msgs(12, 100), max_chars=300, overlap=50)
    assert chunks
    assert all(chunk for chunk in chunks)
