from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import settings


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid4())


# ─────────────────────────────────────────────── User ────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Any] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    personas: Mapped[Any] = relationship("Persona", back_populates="owner", cascade="all, delete-orphan")


# ────────────────────────────────────────────── Persona ──────────────────────────────────────────────

class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[Any] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[Any] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="creating")

    hard_rules: Mapped[Any] =mapped_column(JSON, default=list)
    identity: Mapped[Any] =mapped_column(JSON, default=dict)
    speaking_style: Mapped[Any] =mapped_column(JSON, default=dict)
    emotional_patterns: Mapped[Any] =mapped_column(JSON, default=dict)
    relational_behavior: Mapped[Any] =mapped_column(JSON, default=dict)

    tags: Mapped[Any] =mapped_column(JSON, default=list)
    avatar_url: Mapped[Any] = mapped_column(String(500), nullable=True)
    source_files: Mapped[Any] =mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owner: Mapped[Any] = relationship("User", back_populates="personas")
    memories: Mapped[Any] = relationship("Memory", back_populates="persona", cascade="all, delete-orphan")
    memory_chunks: Mapped[Any] = relationship("MemoryChunk", back_populates="persona", cascade="all, delete-orphan")
    conversations: Mapped[Any] = relationship("Conversation", back_populates="persona", cascade="all, delete-orphan")
    upload_tasks: Mapped[Any] = relationship("UploadTask", back_populates="persona", cascade="all, delete-orphan")


# ─────────────────────────────────────────────── Memory ──────────────────────────────────────────────

class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    persona_id: Mapped[str] = mapped_column(String(36), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[Any] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    participants: Mapped[Any] =mapped_column(JSON, default=list)
    occurred_at: Mapped[Any] = mapped_column(String(100), nullable=True)
    location: Mapped[Any] = mapped_column(String(200), nullable=True)
    emotional_tone: Mapped[Any] = mapped_column(String(50))
    importance: Mapped[int] = mapped_column(Integer, default=5)
    source_chunk_ids: Mapped[Any] =mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    persona: Mapped[Any] =relationship("Persona", back_populates="memories")
    chunks: Mapped[Any] = relationship("MemoryChunk", back_populates="memory")


# ──────────────────────────────────────────── MemoryChunk ────────────────────────────────────────────

class MemoryChunk(Base):
    __tablename__ = "memory_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    persona_id: Mapped[str] = mapped_column(String(36), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    memory_id: Mapped[Any] = mapped_column(String(36), ForeignKey("memories.id", ondelete="SET NULL"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(Text, nullable=True)
    chunk_index: Mapped[Any] = mapped_column(Integer)
    source_file: Mapped[Any] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    persona: Mapped[Any] =relationship("Persona", back_populates="memory_chunks")
    memory: Mapped[Any] =relationship("Memory", back_populates="chunks")


# ─────────────────────────────────────────── Conversation ────────────────────────────────────────────

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    persona_id: Mapped[str] = mapped_column(String(36), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[Any] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    persona: Mapped[Any] =relationship("Persona", back_populates="conversations")
    messages: Mapped[Any] = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


# ────────────────────────────────────────────── Message ──────────────────────────────────────────────

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_memories: Mapped[Any] =mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped[Any] =relationship("Conversation", back_populates="messages")


# ───────────────────────────────────────────── UploadTask ────────────────────────────────────────────

class UploadTask(Base):
    __tablename__ = "upload_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    persona_id: Mapped[Any] = mapped_column(String(36), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size: Mapped[Any] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    message_count: Mapped[Any] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Any] = mapped_column(Text, nullable=True)
    raw_data: Mapped[Any] =mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Any] = mapped_column(DateTime, nullable=True)

    persona: Mapped[Any] =relationship("Persona", back_populates="upload_tasks")
