"""Chat history chunking strategies for LLM context windows."""

from __future__ import annotations

from datetime import timedelta

from app.utils.normalization import UnifiedMessage


def chunk_by_characters(
    messages: list[UnifiedMessage],
    chunk_size: int = 5000,
    overlap: int = 500,
) -> list[list[UnifiedMessage]]:
    """Chunk messages by character count with overlap.

    ``overlap`` is clamped to stay strictly below ``chunk_size``. Without that
    clamp an overlap at least as large as the window lets the carry-over take
    the whole previous chunk, so every chunk grows instead of advancing and the
    output balloons quadratically in chunk count and duplicated content.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    overlap = max(0, min(overlap, chunk_size - 1))

    chunks: list[list[UnifiedMessage]] = []
    current_chunk: list[UnifiedMessage] = []
    current_len = 0

    for msg in messages:
        msg_len = len(msg.content)
        if current_len + msg_len > chunk_size and current_chunk:
            chunks.append(current_chunk)
            # Keep last few messages for overlap
            overlap_len = 0
            overlap_messages: list[UnifiedMessage] = []
            for m in reversed(current_chunk):
                if overlap_len + len(m.content) > overlap:
                    break
                overlap_messages.insert(0, m)
                overlap_len += len(m.content)
            current_chunk = overlap_messages
            current_len = overlap_len
        current_chunk.append(msg)
        current_len += msg_len

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def chunk_by_time_gap(
    messages: list[UnifiedMessage],
    gap_threshold_hours: float = 2.0,
) -> list[list[UnifiedMessage]]:
    """Chunk messages by time gaps (e.g., conversations separated by >2 hours)."""
    if not messages:
        return []

    chunks: list[list[UnifiedMessage]] = []
    current_chunk: list[UnifiedMessage] = [messages[0]]

    for i in range(1, len(messages)):
        prev_ts = messages[i - 1].original_timestamp
        curr_ts = messages[i].original_timestamp

        if prev_ts and curr_ts:
            gap = (curr_ts - prev_ts).total_seconds() / 3600
            if gap > gap_threshold_hours:
                chunks.append(current_chunk)
                current_chunk = []
        current_chunk.append(messages[i])

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def chunk_messages(
    messages: list[UnifiedMessage],
    max_chars: int = 5000,
    overlap: int = 500,
    gap_threshold_hours: float = 2.0,
) -> list[list[UnifiedMessage]]:
    """Smart chunking: first by time gaps, then by character count for long segments."""
    time_chunks = chunk_by_time_gap(messages, gap_threshold_hours)

    final_chunks: list[list[UnifiedMessage]] = []
    for tc in time_chunks:
        total_len = sum(len(m.content) for m in tc)
        if total_len > max_chars:
            final_chunks.extend(chunk_by_characters(tc, max_chars, overlap))
        else:
            final_chunks.append(tc)

    return final_chunks
