from __future__ import annotations

import asyncio
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Persona, UploadTask, User
from app.schemas import UploadResponse, UploadStatusResponse
from app.utils.security import get_current_user

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "uploads")


async def _run_parsing(task_id: str, file_path: str, file_type: str, persona_id: str, db_url: str):
    """Background task: parse the uploaded file, update the UploadTask, then trigger extraction."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as db:
            # Load task
            result = await db.execute(select(UploadTask).where(UploadTask.id == task_id))
            task = result.scalar_one_or_none()
            if not task:
                return

            # Update status to parsing
            task.status = "parsing"
            await db.commit()

            # Choose parser based on file_type
            if file_type == "qq":
                from app.services.parser.qq import QQParser
                parser = QQParser()
            else:
                from app.services.parser.wechat import WeChatParser
                parser = WeChatParser()

            # Parse the file
            raw_messages = await parser.parse(file_path)

            # Convert datetime objects to ISO strings for JSON storage
            serializable_messages = []
            for msg in raw_messages:
                sm = dict(msg)
                if sm.get("timestamp"):
                    sm["timestamp"] = sm["timestamp"].isoformat()
                serializable_messages.append(sm)

            # Update task with parsed data
            task.raw_data = serializable_messages
            task.message_count = len(serializable_messages)
            task.status = "done"
            await db.commit()

        # After parsing, trigger extraction automatically
        try:
            from app.routers.extraction import _run_extraction
            await _run_extraction(persona_id, db_url)
        except Exception:
            pass  # Extraction failure shouldn't affect the upload/parse result

    except Exception as e:
        async with async_session() as db:
            result = await db.execute(select(UploadTask).where(UploadTask.id == task_id))
            task = result.scalar_one_or_none()
            if task:
                task.status = "error"
                task.error_message = str(e)
                await db.commit()
    finally:
        await engine.dispose()


@router.post("/personas/{persona_id}/upload", response_model=UploadResponse, status_code=201)
async def upload_file(
    persona_id: str,
    file: UploadFile,
    file_type: str = "wechat",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file_type not in ("wechat", "qq", "social", "photo"):
        raise HTTPException(status_code=400, detail=f"Unsupported file_type: {file_type}")

    # Verify persona belongs to user
    p = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    if not p.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Persona not found")

    task_id = str(uuid4())
    file_size = file.size

    # Save file
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    task = UploadTask(
        id=task_id,
        persona_id=persona_id,
        filename=file.filename or "unknown",
        file_type=file_type,
        file_size=file_size,
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Trigger async parsing + extraction in background
    from app.config import settings
    asyncio.create_task(_run_parsing(task_id, file_path, file_type, persona_id, settings.DATABASE_URL))

    return UploadResponse(
        upload_id=task.id,
        status=task.status,
        filename=task.filename,
        file_type=task.file_type,
        file_size=task.file_size,
        created_at=task.created_at,
    )


@router.get("/personas/{persona_id}/uploads")
async def list_uploads(persona_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verify persona belongs to user
    p = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    if not p.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Persona not found")
    result = await db.execute(
        select(UploadTask)
        .where(UploadTask.persona_id == persona_id)
        .order_by(UploadTask.created_at.desc())
    )
    tasks = result.scalars().all()
    return [
        UploadResponse(
            upload_id=t.id,
            status=t.status,
            filename=t.filename,
            file_type=t.file_type,
            file_size=t.file_size,
            created_at=t.created_at,
        )
        for t in tasks
    ]


@router.get("/upload/{task_id}/status", response_model=UploadStatusResponse)
async def get_upload_status(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UploadTask).where(UploadTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Upload task not found")

    progress_map = {
        "pending": 0.0,
        "parsing": 0.3,
        "parsed": 0.6,
        "extracting": 0.8,
        "done": 1.0,
        "error": 0.0,
    }

    return UploadStatusResponse(
        upload_id=task.id,
        status=task.status,
        progress_pct=progress_map.get(task.status, 0.0),
        stage=task.status,
        message_count=task.message_count,
        error_message=task.error_message,
    )
