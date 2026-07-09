from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field


# ── Common ──────────────────────────────────────────────

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None


class TaskStatus(BaseModel):
    task_id: str
    status: str  # pending | processing | completed | failed
    progress_pct: float = 0.0
    stage: str | None = None
    error: str | None = None


# ── Persona ─────────────────────────────────────────────

class PersonaCreate(BaseModel):
    name: str = Field(..., max_length=100, pattern=r"^[a-z0-9-]+$")
    display_name: str | None = Field(None, max_length=100)


class PersonaUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    status: str | None = None
    hard_rules: list[dict] | None = None
    identity: dict | None = None
    speaking_style: dict | None = None
    emotional_patterns: dict | None = None
    relational_behavior: dict | None = None
    tags: list[dict] | None = None


class PersonaSummary(BaseModel):
    id: str
    name: str
    display_name: str | None
    status: str
    tags: list[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PersonaDetail(BaseModel):
    id: str
    name: str
    display_name: str | None
    status: str
    hard_rules: list[dict]
    identity: dict
    speaking_style: dict
    emotional_patterns: dict
    relational_behavior: dict
    tags: list[dict]
    avatar_url: str | None
    source_files: list[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Memory ──────────────────────────────────────────────

class MemoryCreate(BaseModel):
    category: str = Field(..., max_length=50)
    title: str | None = Field(None, max_length=200)
    content: str
    participants: list[str] = []
    occurred_at: str | None = None
    location: str | None = None
    emotional_tone: str | None = None
    importance: int = Field(default=5, ge=1, le=10)


class MemoryUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    importance: int | None = Field(None, ge=1, le=10)
    emotional_tone: str | None = None


class MemoryResponse(BaseModel):
    id: str
    persona_id: str
    category: str
    title: str | None
    content: str
    participants: list[dict]
    occurred_at: str | None
    location: str | None
    emotional_tone: str | None
    importance: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class MemorySearchResult(BaseModel):
    memory: MemoryResponse
    chunk_content: str
    similarity_score: float


# ── Upload ──────────────────────────────────────────────

class UploadResponse(BaseModel):
    upload_id: str
    status: str
    filename: str
    file_type: str
    file_size: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadStatusResponse(BaseModel):
    upload_id: str
    status: str
    progress_pct: float
    stage: str | None
    message_count: int | None
    error_message: str | None


# ── Chat ────────────────────────────────────────────────

class SessionCreate(BaseModel):
    title: str | None = Field(None, max_length=200)


class SessionSummary(BaseModel):
    id: str
    persona_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionDetail(BaseModel):
    id: str
    persona_id: str
    title: str | None
    messages: list["MessageResponse"] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    retrieved_memories: list[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    content: str


class CorrectionRequest(BaseModel):
    message_id: str
    correction: str


# ── Extraction ──────────────────────────────────────────

class ExtractionStatus(BaseModel):
    task_id: str
    status: str
    progress_pct: float
    stage: str | None  # chunking | analyzing_persona | analyzing_memories | embedding | done
    error: str | None = None
