from __future__ import annotations

import json
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Conversation, Message, Persona, User
from app.schemas import (
    CorrectionRequest,
    MessageResponse,
    SendMessageRequest,
    SessionCreate,
    SessionDetail,
    SessionSummary,
)
from app.services.chat_service import ChatService
from app.utils.security import get_current_user

router = APIRouter()
chat_service = ChatService()


async def _generate_response(
    session_id: str,
    user_message: str,
    persona_id: str,
    db: AsyncSession,
):
    """SSE streaming generator for persona response using ChatService."""
    # Save user message
    user_msg = Message(
        id=str(uuid4()),
        conversation_id=session_id,
        role="user",
        content=user_message,
    )
    db.add(user_msg)
    await db.commit()

    # Build conversation history
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == session_id)
        .order_by(Message.created_at.asc())
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in history_result.scalars().all()
    ]

    # Stream via ChatService
    full_response = ""
    persona_msg_id = str(uuid4())

    async for event in chat_service.stream_response(
        persona_id=persona_id,
        user_message=user_message,
        conversation_history=history,
        db=db,
        persona_message_id=persona_msg_id,
    ):
        yield event

        # Parse token events to collect full response
        if event.startswith("data: "):
            try:
                data = json.loads(event[6:])
                if data.get("type") == "token":
                    full_response += data.get("token", "")
                elif data.get("type") == "done":
                    # Save persona message
                    persona_msg = Message(
                        id=persona_msg_id,
                        conversation_id=session_id,
                        role="persona",
                        content=data.get("full_text", full_response),
                        retrieved_memories=data.get("retrieved_memories", []),
                    )
                    db.add(persona_msg)
                    await db.commit()
            except (json.JSONDecodeError, KeyError):
                pass


@router.get("/personas/{persona_id}/conversations", response_model=List[SessionSummary])
async def list_conversations(persona_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verify persona belongs to user
    p = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    if not p.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Persona not found")

    result = await db.execute(
        select(Conversation)
        .where(Conversation.persona_id == persona_id)
        .order_by(Conversation.updated_at.desc())
    )
    sessions = result.scalars().all()
    return [SessionSummary.model_validate(s) for s in sessions]


@router.post("/personas/{persona_id}/conversations", response_model=SessionSummary, status_code=201)
async def create_conversation(persona_id: str, body: SessionCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verify persona exists and belongs to user
    persona_result = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    if not persona_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Persona not found")

    session = Conversation(
        id=str(uuid4()),
        persona_id=persona_id,
        title=body.title or "New conversation",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionSummary.model_validate(session)


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_messages(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    return [MessageResponse.model_validate(m) for m in messages]


@router.post("/personas/{persona_id}/chat")
async def chat_with_persona(
    persona_id: str,
    body: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message and get a streaming persona response via SSE."""
    # Verify persona exists and belongs to user
    persona_check = await db.execute(select(Persona).where(Persona.id == persona_id, Persona.user_id == current_user.id))
    if not persona_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Persona not found")

    # Find or create a conversation
    result = await db.execute(
        select(Conversation)
        .where(Conversation.persona_id == persona_id)
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()

    if not session:
        session = Conversation(
            id=str(uuid4()),
            persona_id=persona_id,
            title="New conversation",
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    return StreamingResponse(
        _generate_response(session.id, body.content, persona_id, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(session)
    await db.commit()


@router.delete("/messages/{message_id}", status_code=204)
async def delete_message(message_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a single message by ID."""
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    await db.delete(message)
    await db.commit()


@router.post("/conversations/{conversation_id}/correct")
async def correct_message(conversation_id: str, body: CorrectionRequest, db: AsyncSession = Depends(get_db)):
    """Process a correction to a persona's response and update the persona."""
    # Load the original message
    result = await db.execute(select(Message).where(Message.id == body.message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Load the conversation to get persona
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Use correction chain to analyze the correction (lazy import)
    try:
        from app.chains.correction_chain import build_correction_chain
        chain = build_correction_chain()
        correction_result = await chain.ainvoke({
            "input": json.dumps({
                "original_message": message.content,
                "user_correction": body.correction,
                "conversation_context": f"The user said the persona's response was wrong. Correction: {body.correction}",
            }),
        })
    except ImportError:
        correction_result = {
            "rule_type": "phrase_ban",
            "explanation": "LangChain not installed — correction stored as-is",
        }

    # Apply correction to persona layers if it's a behavior override
    persona_result = await db.execute(
        select(Persona).where(Persona.id == conversation.persona_id)
    )
    persona = persona_result.scalar_one_or_none()

    if persona and correction_result.get("rule_type") == "behavior_override":
        target_layer = correction_result.get("target_layer")
        layer_patch = correction_result.get("layer_patch")

        if target_layer and layer_patch and hasattr(persona, target_layer):
            current = getattr(persona, target_layer) or {}
            if isinstance(current, dict) and isinstance(layer_patch, dict):
                current.update(layer_patch)
                setattr(persona, target_layer, current)
                await db.commit()

    return {
        "status": "correction_recorded",
        "message_id": body.message_id,
        "rule_type": correction_result.get("rule_type"),
        "explanation": correction_result.get("explanation"),
    }
