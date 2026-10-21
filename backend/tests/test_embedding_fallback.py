"""Regression tests for the keyword/embedding fallback path.

The fallback runs whenever no embedding provider is configured, so it is the
code path most users hit. It previously carried a hand-escaped tokenizer regex
in two places and parsed stored embeddings without guarding against bad data.
"""

from __future__ import annotations

import pytest

from app.services.embedding_service import EmbeddingService


class _FakeChunk:
    def __init__(self, content: str, chunk_id: str = "id") -> None:
        self.content = content
        self.id = chunk_id
        self.memory_id = None


def test_tokenizer_splits_typographic_quotes_and_apostrophes():
    from app.services.embedding_service import _WORD_SPLIT

    parts = _WORD_SPLIT.split("他说“你好”don't 停")
    assert "你好" in parts
    assert "don" in parts
    assert "t" in parts


def test_keyword_vector_is_unit_length_and_deterministic():
    first = EmbeddingService._keyword_vector("我们一起去过北京")
    second = EmbeddingService._keyword_vector("我们一起去过北京")
    assert first == second
    assert len(first) == 1536
    assert abs(sum(x * x for x in first) ** 0.5 - 1.0) < 1e-9


def test_keyword_vector_handles_empty_text():
    vector = EmbeddingService._keyword_vector("")
    assert len(vector) == 1536
    assert all(value == 0.0 for value in vector)


def test_parse_embedding_accepts_valid_data():
    assert EmbeddingService._parse_embedding("1.0,2.0,-3.5") == [1.0, 2.0, -3.5]


@pytest.mark.parametrize("bad", ["", None, "1.0,abc", "1.0,", "NaN,", "[]"])
def test_parse_embedding_rejects_junk_without_raising(bad):
    assert EmbeddingService._parse_embedding(bad) is None


def test_cosine_similarity_bounds():
    sim = EmbeddingService._cosine_similarity
    assert sim([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert sim([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert sim([0.0, 0.0], [1.0, 0.0]) == 0.0
    # Dimension mismatch must not raise.
    assert sim([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_keyword_search_ranks_the_relevant_chunk_first():
    chunks = [
        _FakeChunk("数据库索引优化的注意事项", "c1"),
        _FakeChunk("我们一起去过北京看雪", "c2"),
        _FakeChunk("今天中午吃什么好呢", "c3"),
    ]
    results = EmbeddingService._keyword_search("还记得北京那次吗", chunks, top_k=3)
    assert results
    assert "北京" in results[0]["content"]


def test_keyword_search_respects_top_k():
    chunks = [_FakeChunk("北京" * 5, f"c{i}") for i in range(10)]
    results = EmbeddingService._keyword_search("北京", chunks, top_k=3)
    assert len(results) == 3


def test_keyword_search_skips_chunks_without_tokens():
    chunks = [_FakeChunk("", "empty"), _FakeChunk("北京见", "c2")]
    results = EmbeddingService._keyword_search("北京", chunks, top_k=5)
    assert all(result["chunk_id"] != "empty" for result in results)
