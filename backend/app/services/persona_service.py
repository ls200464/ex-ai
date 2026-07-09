"""Persona service — business logic for persona management."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Persona


class PersonaService:
    """Service layer for persona CRUD operations."""

    async def get_persona(self, persona_id: str, db: AsyncSession) -> Persona | None:
        result = await db.execute(select(Persona).where(Persona.id == persona_id))
        return result.scalar_one_or_none()

    async def get_persona_by_name(self, name: str, db: AsyncSession) -> Persona | None:
        result = await db.execute(select(Persona).where(Persona.name == name))
        return result.scalar_one_or_none()

    async def list_personas(
        self,
        db: AsyncSession,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Persona], int]:
        query = select(Persona).order_by(Persona.updated_at.desc())
        count_query = select(Persona)

        if status:
            query = query.where(Persona.status == status)
            count_query = count_query.where(Persona.status == status)

        total_result = await db.execute(count_query)
        total = len(list(total_result.scalars().all()))

        offset = (page - 1) * page_size
        result = await db.execute(query.offset(offset).limit(page_size))
        personas = list(result.scalars().all())

        return personas, total

    async def update_status(
        self,
        persona_id: str,
        status: str,
        db: AsyncSession,
    ) -> Persona | None:
        persona = await self.get_persona(persona_id, db)
        if persona:
            persona.status = status
            await db.commit()
            await db.refresh(persona)
        return persona
