"""Embedding service — generates and stores vector embeddings."""

from __future__ import annotations

import hashlib
import re

from app.config import settings

_IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

# Characters that separate tokens: whitespace, CJK punctuation, typographic
# quotes, and ASCII punctuation. Built with re.escape instead of a hand-escaped
# character class, and shared by both tokenizers — the previous version carried
# the same pattern twice, written as a single-quoted raw string containing `''`,
# which silently ended the literal and concatenated a second, non-raw fragment
# with invalid escapes (`\[`, `\]`) intended for a different quote character.
_SEPARATOR_CHARS = (
    "\u3000"                        # ideographic space
    "，。！？、；："
    "\u201c\u201d\u2018\u2019"      # curly double/single quotes
    "【】《》（）「」『』"
    "-.?!;:()[]{}"
    "\"'"
)
_WORD_SPLIT = re.compile("[" + re.escape(_SEPARATOR_CHARS) + r"\s]+")


class EmbeddingService:
    """Service for generating embeddings and performing similarity search."""

    def __init__(self):
        self._embeddings = None

    @property
    def embeddings(self):
        if self._embeddings is None:
            try:
                from app.chains.base import create_embeddings
                self._embeddings = create_embeddings()
            except ImportError:
                return None
        return self._embeddings

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for a single text."""
        emb = self.embeddings
        if emb is None:
            # Return a hash-based pseudo-embedding for keyword matching
            # This is NOT a real embedding, but enables basic retrieval
            return self._keyword_vector(text)
        try:
            return await emb.aembed_query(text)
        except Exception:
            return self._keyword_vector(text)

    @staticmethod
    def _keyword_vector(text: str, dims: int = 1536) -> list[float]:
        """Generate a pseudo-embedding from keyword hashing for fallback retrieval.

        Uses character bigram hashing to create a sparse vector that captures
        surface-level text similarity. Not as good as real embeddings, but
        MUCH better than zero vectors for retrieval.
        """
        result = [0.0] * dims
        text_lower = text.lower()
        # Hash character bigrams into vector dimensions
        for i in range(len(text_lower) - 1):
            bigram = text_lower[i:i+2]
            h = int(hashlib.md5(bigram.encode()).hexdigest()[:8], 16)
            idx = h % dims
            result[idx] += 1.0
        # Also hash individual words (split on whitespace and common CJK punctuation)
        for word in _WORD_SPLIT.split(text_lower):
            if len(word) >= 2:
                h = int(hashlib.md5(word.encode()).hexdigest()[:8], 16)
                idx = h % dims
                result[idx] += 2.0  # words get higher weight than bigrams
        # Normalize
        norm = (sum(x * x for x in result)) ** 0.5
        if norm > 0:
            result = [x / norm for x in result]
        return result

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for multiple texts."""
        emb = self.embeddings
        if emb is None:
            return [self._keyword_vector(t) for t in texts]
        try:
            return await emb.aembed_documents(texts)
        except Exception:
            return [self._keyword_vector(t) for t in texts]

    async def similarity_search(
        self,
        query: str,
        persona_id: str,
        top_k: int = 5,
        threshold: float = 0.7,
    ) -> list[dict]:
        """Search for similar memory chunks.

        Uses pgvector cosine similarity on PostgreSQL, or a basic
        cosine similarity on SQLite (in-memory computation).
        Falls back to keyword matching when embeddings are unavailable.
        """
        from sqlalchemy import select, text

        from app.database import async_session_factory
        from app.models import MemoryChunk

        query_embedding = await self.embed_text(query)

        async with async_session_factory() as session:
            if _IS_SQLITE:
                # SQLite: load all chunks and compute in Python
                result = await session.execute(
                    select(MemoryChunk).where(MemoryChunk.persona_id == persona_id)
                )
                chunks = result.scalars().all()

                # Embeddings are stored as comma-separated text. Rows that do not
                # parse are dropped, where a bare float() over every chunk used to
                # raise and abort the whole search.
                usable: list[tuple] = []
                for chunk in chunks:
                    chunk_emb = self._parse_embedding(chunk.embedding)
                    if chunk_emb is None or all(value == 0.0 for value in chunk_emb):
                        continue
                    if len(chunk_emb) != len(query_embedding):
                        # Different embedding model than the query (e.g. the
                        # provider or model setting changed). Cosine similarity
                        # would report 0.0 for every row, silently returning
                        # nothing, so treat these rows as unusable.
                        continue
                    usable.append((chunk, chunk_emb))

                if not usable:
                    # Use keyword-based matching instead of broken vector similarity
                    scored = self._keyword_search(query, chunks, top_k)
                else:
                    scored = []
                    for chunk, chunk_emb in usable:
                        similarity = self._cosine_similarity(query_embedding, chunk_emb)
                        if similarity >= threshold:
                            scored.append({
                                "chunk_id": chunk.id,
                                "memory_id": chunk.memory_id,
                                "content": chunk.content,
                                "similarity_score": round(similarity, 4),
                            })

                    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
                    scored = scored[:top_k]

                return scored
            else:
                # PostgreSQL + pgvector
                embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"
                sql = text("""
                    SELECT
                        mc.id AS chunk_id,
                        mc.memory_id,
                        mc.content,
                        1 - (mc.embedding <=> :embedding::vector) AS similarity
                    FROM memory_chunks mc
                    WHERE mc.persona_id = :persona_id
                      AND 1 - (mc.embedding <=> :embedding::vector) >= :threshold
                    ORDER BY similarity DESC
                    LIMIT :top_k
                """)
                result = await session.execute(
                    sql,
                    {
                        "embedding": embedding_str,
                        "persona_id": persona_id,
                        "threshold": threshold,
                        "top_k": top_k,
                    },
                )
                rows = result.fetchall()
                return [
                    {
                        "chunk_id": str(row.chunk_id),
                        "memory_id": str(row.memory_id) if row.memory_id else None,
                        "content": row.content,
                        "similarity_score": round(float(row.similarity), 4),
                    }
                    for row in rows
                ]

    @staticmethod
    def _keyword_search(
        query: str,
        chunks: list,
        top_k: int = 5,
    ) -> list[dict]:
        """Keyword-based search fallback when embeddings are unavailable.

        Uses overlapping word/character n-grams between query and chunk content
        to score relevance. Much better than returning nothing.
        """
        def tokenize(text: str) -> set:
            """Extract meaningful tokens from text."""
            # Split on whitespace and punctuation
            tokens = set()
            text_lower = text.lower()
            # Character bigrams (works for CJK and Latin text)
            for i in range(len(text_lower) - 1):
                tokens.add(text_lower[i:i+2])
            # Full words (2+ chars)
            for w in _WORD_SPLIT.split(text_lower):
                if len(w) >= 2:
                    tokens.add(w)
            return tokens

        query_tokens = tokenize(query)

        scored = []
        for chunk in chunks:
            chunk_tokens = tokenize(chunk.content)
            if not chunk_tokens:
                continue
            # Jaccard-like overlap score
            overlap = len(query_tokens & chunk_tokens)
            total = len(query_tokens | chunk_tokens)
            if total > 0:
                score = overlap / total
                if score > 0.02:  # very low threshold — keyword matching is sparse
                    scored.append({
                        "chunk_id": chunk.id,
                        "memory_id": chunk.memory_id,
                        "content": chunk.content,
                        "similarity_score": round(score, 4),
                    })

        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _parse_embedding(raw) -> list[float] | None:
        """Parse a stored comma-separated embedding, or None when unusable."""
        if not raw:
            return None
        try:
            values = [float(part) for part in raw.split(",")]
        except (AttributeError, ValueError):
            return None
        return values or None

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = (sum(x * x for x in a)) ** 0.5
        norm_b = (sum(x * x for x in b)) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
