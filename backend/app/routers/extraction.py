from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Persona, UploadTask, User
from app.schemas import ExtractionStatus
from app.services.extraction import ExtractionService
from app.utils.normalization import UnifiedMessage, normalize_messages
from app.utils.security import get_current_user

router = APIRouter()
extraction_service = ExtractionService()

# In-memory task tracker: maps persona_id → task info
_tasks: dict[str, dict] = {}


async def _run_extraction(persona_id: str, db_url: str):
    """Background extraction task."""
    task_info = {"status": "processing", "progress_pct": 0, "stage": "loading"}
    _tasks[persona_id] = task_info

    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        engine = create_async_engine(db_url)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as db:
            # Load persona to get display_name for role matching
            persona_result = await db.execute(select(Persona).where(Persona.id == persona_id))
            persona = persona_result.scalar_one_or_none()
            target_name = persona.display_name if persona else persona_id

            # Load messages from upload tasks that have parsed data
            _tasks[persona_id]["stage"] = "loading_messages"
            _tasks[persona_id]["progress_pct"] = 0.1

            result = await db.execute(
                select(UploadTask).where(
                    UploadTask.persona_id == persona_id,
                    UploadTask.raw_data.isnot(None),
                )
            )
            upload_tasks = result.scalars().all()

            all_messages: list[UnifiedMessage] = []
            for task in upload_tasks:
                if task.raw_data:
                    messages = normalize_messages(
                        task.raw_data if isinstance(task.raw_data, list) else [],
                        user_name="拾光",  # We don't know the user's name — use auto-detect
                        target_name=target_name,
                    )
                    all_messages.extend(messages)

            if not all_messages:
                _tasks[persona_id] = {
                    "status": "failed",
                    "progress_pct": 0,
                    "stage": "error",
                    "error": "No parsed messages found. Upload and parse chat records first.",
                }
                return

            _tasks[persona_id]["stage"] = "extracting_persona"
            _tasks[persona_id]["progress_pct"] = 0.3

            # Extract persona
            await extraction_service.extract_persona(persona_id, all_messages, db)

            _tasks[persona_id]["stage"] = "extracting_memories"
            _tasks[persona_id]["progress_pct"] = 0.6

            # Extract memories
            await extraction_service.extract_memories(persona_id, all_messages, db)

            # Update persona status
            persona_result = await db.execute(select(Persona).where(Persona.id == persona_id))
            persona = persona_result.scalar_one_or_none()
            if persona:
                persona.status = "ready"
                await db.commit()

            _tasks[persona_id] = {
                "status": "completed",
                "progress_pct": 1.0,
                "stage": "done",
            }

        await engine.dispose()
    except Exception as e:
        _tasks[persona_id] = {
            "status": "failed",
            "progress_pct": 0,
            "stage": "error",
            "error": str(e),
        }


@router.post("/personas/{persona_id}/extract/persona")
async def extract_persona(persona_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Trigger persona extraction for a persona."""
    from app.config import settings

    # Verify persona exists and belongs to user
    result = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Persona not found")

    asyncio.create_task(_run_extraction(persona_id, settings.DATABASE_URL))
    return {"status": "extraction_started", "persona_id": persona_id}


@router.post("/personas/{persona_id}/extract/memories")
async def extract_memories(persona_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Trigger memory extraction for a persona."""
    result = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Persona not found")

    from app.config import settings

    asyncio.create_task(_run_extraction(persona_id, settings.DATABASE_URL))
    return {"status": "extraction_started", "persona_id": persona_id}


@router.post("/personas/{persona_id}/extract/all")
async def extract_all(persona_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Trigger full extraction (persona + memories) for a persona."""
    result = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Persona not found")

    from app.config import settings

    asyncio.create_task(_run_extraction(persona_id, settings.DATABASE_URL))
    return {"status": "extraction_started", "persona_id": persona_id}


@router.get("/personas/{persona_id}/extract/status", response_model=ExtractionStatus)
async def get_extraction_status(persona_id: str):
    """Get extraction progress for a persona."""
    task_info = _tasks.get(persona_id)
    if task_info:
        return ExtractionStatus(
            task_id=persona_id,
            status=task_info.get("status", "idle"),
            progress_pct=task_info.get("progress_pct", 0),
            stage=task_info.get("stage"),
            error=task_info.get("error"),
        )
    return ExtractionStatus(
        task_id=persona_id,
        status="idle",
        progress_pct=0,
        stage=None,
    )
