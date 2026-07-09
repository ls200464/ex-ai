from __future__ import annotations

from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Memory, MemoryChunk, Persona, User
from app.schemas import MemoryCreate, MemoryResponse, MemorySearchRequest, MemorySearchResult, MemoryUpdate, PaginatedResponse
from app.services.embedding_service import EmbeddingService
from app.utils.security import get_current_user

router = APIRouter()
embedding_service = EmbeddingService()


@router.get("/personas/{persona_id}/memories", response_model=PaginatedResponse[MemoryResponse])
async def list_memories(
    persona_id: str,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify persona belongs to user
    p = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    if not p.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Persona not found")
    query = select(Memory).where(Memory.persona_id == persona_id).order_by(Memory.created_at.desc())
    count_query = select(Memory).where(Memory.persona_id == persona_id)

    if category:
        query = query.where(Memory.category == category)
        count_query = count_query.where(Memory.category == category)

    total_result = await db.execute(count_query)
    total = len(list(total_result.scalars().all()))

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    memories = result.scalars().all()

    return PaginatedResponse(
        items=[MemoryResponse.model_validate(m) for m in memories],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(memory_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Memory).where(Memory.id == memory_id))
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    # Verify persona belongs to user
    p = await db.execute(select(Persona).where(Persona.id == memory.persona_id, Persona.user_id == current_user.id))
    if not p.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Memory not found")
    return MemoryResponse.model_validate(memory)


@router.post("/personas/{persona_id}/memories", response_model=MemoryResponse, status_code=201)
async def create_memory(persona_id: str, body: MemoryCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verify persona belongs to user
    p = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    if not p.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Persona not found")
    memory = Memory(
        id=str(uuid4()),
        persona_id=persona_id,
        **body.model_dump(),
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return MemoryResponse.model_validate(memory)


@router.patch("/memories/{memory_id}", response_model=MemoryResponse)
async def update_memory(memory_id: str, body: MemoryUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Memory).where(Memory.id == memory_id))
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    # Verify persona belongs to user
    p = await db.execute(select(Persona).where(Persona.id == memory.persona_id, Persona.user_id == current_user.id))
    if not p.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Memory not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(memory, key, value)

    await db.commit()
    await db.refresh(memory)
    return MemoryResponse.model_validate(memory)


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(memory_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Memory).where(Memory.id == memory_id))
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    # Verify persona belongs to user
    p = await db.execute(select(Persona).where(Persona.id == memory.persona_id, Persona.user_id == current_user.id))
    if not p.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Memory not found")
    await db.delete(memory)
    await db.commit()


@router.delete("/personas/{persona_id}/memories", status_code=204)
async def delete_all_memories(persona_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete all memories and their chunks for a persona. Use before re-extraction."""
    # Verify persona belongs to user
    p = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    if not p.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Persona not found")
    # Delete chunks first (foreign key to memories)
    chunks_result = await db.execute(
        select(MemoryChunk).where(MemoryChunk.persona_id == persona_id)
    )
    for chunk in chunks_result.scalars().all():
        await db.delete(chunk)

    # Delete memories
    mem_result = await db.execute(
        select(Memory).where(Memory.persona_id == persona_id)
    )
    for mem in mem_result.scalars().all():
        await db.delete(mem)

    await db.commit()


@router.post("/personas/{persona_id}/memories/search", response_model=List[MemorySearchResult])
async def search_memories(persona_id: str, body: MemorySearchRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Search memories using vector similarity (RAG retrieval).

    Returns memory results ranked by semantic similarity to the query,
    including the matching chunk content and similarity score.
    """
    # Verify persona belongs to user
    p = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    if not p.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Persona not found")
    # Use embedding service for semantic search
    chunk_results = await embedding_service.similarity_search(
        query=body.query,
        persona_id=persona_id,
        top_k=body.top_k,
        threshold=body.threshold,
    )

    if not chunk_results:
        return []

    # Load full memory objects for each matching chunk
    memory_ids = list(set(
        r["memory_id"] for r in chunk_results if r.get("memory_id")
    ))
    memory_map: dict[str, Memory] = {}
    if memory_ids:
        result = await db.execute(
            select(Memory).where(Memory.id.in_(memory_ids))
        )
        for mem in result.scalars().all():
            memory_map[mem.id] = mem

    # Build response
    search_results: list[MemorySearchResult] = []
    for cr in chunk_results:
        mem = memory_map.get(cr.get("memory_id") or "")
        if mem:
            search_results.append(MemorySearchResult(
                memory=MemoryResponse.model_validate(mem),
                chunk_content=cr["content"],
                similarity_score=cr["similarity_score"],
            ))
        else:
            # Chunk without a linked memory — still return the chunk content
            search_results.append(MemorySearchResult(
                memory=MemoryResponse(
                    id=cr.get("chunk_id", ""),
                    persona_id=persona_id,
                    category="orphan_chunk",
                    title=None,
                    content=cr["content"],
                    participants=[],
                    occurred_at=None,
                    location=None,
                    emotional_tone=None,
                    importance=5,
                    created_at=None,  # type: ignore[arg-type]
                ),
                chunk_content=cr["content"],
                similarity_score=cr["similarity_score"],
            ))

    return search_results
