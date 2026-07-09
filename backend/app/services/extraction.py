"""Extraction service — orchestrates the persona + memory extraction pipeline.

Uses the lightweight LLM client by default; falls back to LangChain if installed.
"""

from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chains.persona_chain import (
    PERSONA_SYSTEM_PROMPT,
    EmotionalPatterns,
    HardRule,
    Identity,
    PersonaExtraction,
    RelationalBehavior,
    SpeakingStyle,
)
from app.chains.memory_chain import (
    MEMORY_SYSTEM_PROMPT,
    ExtractedMemory,
    MemoryExtraction,
)
from app.models import Memory, MemoryChunk, Persona
from app.services.embedding_service import EmbeddingService
from app.services.llm_client import extract_json
from app.utils.chunking import chunk_messages
from app.utils.normalization import UnifiedMessage


def _model_to_dict(obj) -> dict:
    """Convert a Pydantic model instance to dict, handling nested models."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    elif hasattr(obj, "dict"):
        return obj.dict()
    elif isinstance(obj, dict):
        return obj
    return {}


class ExtractionService:
    """Orchestrates the full extraction pipeline: raw messages → persona + memories + embeddings."""

    def __init__(self):
        self.embedding_service = EmbeddingService()

    async def extract_persona(
        self,
        persona_id: str,
        messages: list[UnifiedMessage],
        db: AsyncSession,
    ) -> dict:
        """Extract the 5-layer persona from chat messages."""
        # Prepare input: concatenate messages with sender labels
        conversation_text = "\n".join(
            f"[{m.sender_role}] {m.sender_name}: {m.content}" for m in messages
        )
        # Truncate if too long (rough estimate: ~12000 chars for persona analysis)
        if len(conversation_text) > 12000:
            conversation_text = conversation_text[-12000:]

        # Try LangChain first, fall back to lightweight client
        result = None
        try:
            from app.chains.persona_chain import build_persona_chain
            chain = build_persona_chain()
            result = await chain.ainvoke({"input": conversation_text})
        except (ImportError, Exception):
            pass

        if result is None or "error" in str(result):
            # Use lightweight LLM client
            try:
                result = await extract_json(
                    system_prompt=PERSONA_SYSTEM_PROMPT,
                    user_input=conversation_text,
                    temperature=0.5,
                )
            except Exception as e:
                return {"error": str(e)}

        # Validate and normalize the result
        persona_data = self._normalize_persona_result(result)

        # Update persona in DB
        persona_result = await db.execute(select(Persona).where(Persona.id == persona_id))
        persona = persona_result.scalar_one_or_none()
        if persona:
            persona.hard_rules = persona_data.get("hard_rules", [])
            persona.identity = persona_data.get("identity", {})
            persona.speaking_style = persona_data.get("speaking_style", {})
            persona.emotional_patterns = persona_data.get("emotional_patterns", {})
            persona.relational_behavior = persona_data.get("relational_behavior", {})
            persona.tags = persona_data.get("tags", [])
            persona.status = "ready"
            await db.commit()

        return persona_data

    async def extract_memories(
        self,
        persona_id: str,
        messages: list[UnifiedMessage],
        db: AsyncSession,
    ) -> list[dict]:
        """Extract relationship memories from chat messages and create embeddings."""
        embedding_service = self.embedding_service

        # Chunk messages for processing — adapt to conversation size
        total_chars = sum(len(m.content) for m in messages)
        chunk_size = max(8000, total_chars)  # Don't split if total fits in one chunk
        # Use large gap threshold for small conversations to preserve context
        gap_hours = 24.0 if total_chars < 20000 else 2.0
        chunks = chunk_messages(
            messages,
            max_chars=chunk_size,
            overlap=300,
            gap_threshold_hours=gap_hours,
        )
        all_memories: list[dict] = []

        for chunk in chunks:
            conversation_text = "\n".join(
                f"[{m.sender_role}] {m.sender_name}: {m.content}" for m in chunk
            )

            chunk_result = None
            try:
                from app.chains.memory_chain import build_memory_chain
                chain = build_memory_chain()
                chunk_result = await chain.ainvoke({"input": conversation_text})
            except (ImportError, Exception):
                pass

            if chunk_result is None or "error" in str(chunk_result):
                try:
                    chunk_result = await extract_json(
                        system_prompt=MEMORY_SYSTEM_PROMPT,
                        user_input=conversation_text,
                        temperature=0.5,
                    )
                except Exception:
                    continue

            # Handle both dict and list responses
            if isinstance(chunk_result, list):
                chunk_memories = chunk_result
            elif isinstance(chunk_result, dict):
                chunk_memories = chunk_result.get("memories", [])
            else:
                chunk_memories = []
            all_memories.extend(chunk_memories)

        # Deduplicate by title similarity against both current batch AND existing memories
        # Load existing memory titles from DB
        existing_result = await db.execute(
            select(Memory.title).where(Memory.persona_id == persona_id)
        )
        seen_titles = {row[0].lower() for row in existing_result.fetchall() if row[0]}
        unique_memories = []
        for mem in all_memories:
            if not isinstance(mem, dict):
                continue
            title = mem.get("title", "").strip()
            # Auto-generate title from content if LLM didn't provide one
            if not title:
                content = mem.get("content", "")
                if content:
                    title = content[:80] + ("..." if len(content) > 80 else "")
            # Normalize for dedup
            title_key = title.lower() if title else ""
            if title_key and title_key not in seen_titles:
                seen_titles.add(title_key)
                # Ensure the memory dict has a title field for DB save
                if not mem.get("title"):
                    mem["title"] = title
                unique_memories.append(mem)

        # Save to DB
        saved_memories = []
        for mem in unique_memories:
            if not isinstance(mem, dict):
                continue

            memory = Memory(
                id=str(uuid4()),
                persona_id=persona_id,
                category=mem.get("category", "shared_experience"),
                title=mem.get("title"),
                content=mem.get("content", ""),
                participants=mem.get("participants", []),
                occurred_at=mem.get("occurred_at"),
                location=mem.get("location"),
                emotional_tone=mem.get("emotional_tone"),
                importance=int(mem.get("importance", 5)),
            )
            db.add(memory)
            await db.flush()

            # Create chunk and embedding
            chunk = MemoryChunk(
                id=str(uuid4()),
                persona_id=persona_id,
                memory_id=memory.id,
                content=mem.get("content", ""),
                chunk_index=0,
            )
            db.add(chunk)
            await db.flush()

            # Generate embedding (deferred — we need the chunk ID first)
            try:
                embedding_vector = await embedding_service.embed_text(mem.get("content", ""))
                chunk.embedding = ",".join(str(x) for x in embedding_vector)
            except Exception:
                pass  # Embedding generation might fail if no API key configured

            saved_memories.append({
                "id": memory.id,
                "title": memory.title,
                "category": memory.category,
            })

        await db.commit()
        return saved_memories

    async def extract_all(
        self,
        persona_id: str,
        messages: list[UnifiedMessage],
        db: AsyncSession,
    ) -> dict:
        """Run full extraction: persona + memories."""
        persona_result = await self.extract_persona(persona_id, messages, db)
        memory_result = await self.extract_memories(persona_id, messages, db)
        return {
            "persona": persona_result,
            "memories_count": len(memory_result),
            "memories": memory_result,
        }

    def _normalize_persona_result(self, result: dict) -> dict:
        """Normalize the LLM output to match our Persona schema structure.

        The LLM may return slightly different key names or nested structures.
        This ensures the output always matches the expected 5-layer format.
        """
        if not isinstance(result, dict):
            return {
                "hard_rules": [],
                "identity": {},
                "speaking_style": {},
                "emotional_patterns": {},
                "relational_behavior": {},
                "tags": [],
            }

        # Normalize hard_rules: LLM may return a dict with sub-categories or a list
        hard_rules = result.get("hard_rules", [])
        if isinstance(hard_rules, dict):
            # LLM returned {category: [rules]} or {category: "description"}
            rules_list = []
            for key, val in hard_rules.items():
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            rules_list.append(item)
                        else:
                            rules_list.append({"rule": str(item), "priority": 5})
                elif isinstance(val, str):
                    rules_list.append({"rule": f"{key}: {val}", "priority": 5})
            hard_rules = rules_list
        elif isinstance(hard_rules, list):
            hard_rules = [
                r if isinstance(r, dict) else {"rule": str(r), "priority": 5}
                for r in hard_rules
            ]
        else:
            hard_rules = []

        # Ensure each layer is a dict with all expected keys present
        def _ensure_dict(data, defaults=None):
            if not isinstance(data, dict):
                return defaults or {}
            return data

        identity = _ensure_dict(result.get("identity"))
        speaking_style = _ensure_dict(result.get("speaking_style"))
        emotional_patterns = _ensure_dict(result.get("emotional_patterns"))
        relational_behavior = _ensure_dict(result.get("relational_behavior"))

        # Normalize tags: may be list of strings or list of dicts
        tags = result.get("tags", [])
        if isinstance(tags, list):
            tags = [
                t if isinstance(t, dict) else {"name": str(t)}
                for t in tags
            ]
        else:
            tags = []

        return {
            "hard_rules": hard_rules,
            "identity": identity,
            "speaking_style": speaking_style,
            "emotional_patterns": emotional_patterns,
            "relational_behavior": relational_behavior,
            "tags": tags,
        }
