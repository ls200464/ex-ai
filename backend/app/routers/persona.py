from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Persona, User
from app.schemas import (
    PaginatedResponse,
    PaginationParams,
    PersonaCreate,
    PersonaDetail,
    PersonaSummary,
    PersonaUpdate,
)
from app.utils.security import get_current_user

router = APIRouter()


@router.get("/personas", response_model=PaginatedResponse[PersonaSummary])
async def list_personas(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Persona).where(Persona.user_id == current_user.id).order_by(Persona.updated_at.desc())
    if status:
        query = query.where(Persona.status == status)

    # Count
    count_query = select(Persona).where(Persona.user_id == current_user.id)
    if status:
        count_query = count_query.where(Persona.status == status)
    total = (await db.execute(count_query)).scalars().all()
    total_count = len(list(total))

    # Paginate
    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    personas = result.scalars().all()

    return PaginatedResponse(
        items=[PersonaSummary.model_validate(p) for p in personas],
        total=total_count,
        page=page,
        page_size=page_size,
    )


@router.post("/personas", response_model=PersonaDetail, status_code=201)
async def create_persona(body: PersonaCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    persona = Persona(
        id=str(uuid4()),
        user_id=current_user.id,
        name=body.name,
        display_name=body.display_name or body.name,
        status="creating",
    )
    db.add(persona)
    await db.commit()
    await db.refresh(persona)
    return PersonaDetail.model_validate(persona)


@router.get("/personas/{persona_id}", response_model=PersonaDetail)
async def get_persona(persona_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return PersonaDetail.model_validate(persona)


@router.patch("/personas/{persona_id}", response_model=PersonaDetail)
async def update_persona(persona_id: str, body: PersonaUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(persona, key, value)

    await db.commit()
    await db.refresh(persona)
    return PersonaDetail.model_validate(persona)


@router.delete("/personas/{persona_id}", status_code=204)
async def delete_persona(persona_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    await db.delete(persona)
    await db.commit()
