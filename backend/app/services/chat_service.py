"""Chat service — RAG-powered persona conversation simulation."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Persona
from app.services.embedding_service import EmbeddingService


class ChatService:
    """Service for generating persona-style responses with RAG memory retrieval."""

    def __init__(self):
        self.embedding_service = EmbeddingService()

    async def build_system_prompt(
        self,
        persona: Persona,
        user_message: str,
    ) -> tuple[str, list[dict]]:
        """Build the system prompt from persona layers + retrieved memories.

        Returns the prompt together with the retrieved memories, so the caller
        can report which memories were actually used. Returning only the prompt
        left the SSE `done` event reporting an empty list on every turn, even
        when memories had been injected.
        """
        # Retrieve relevant memories via RAG
        memory_results = await self.embedding_service.similarity_search(
            query=user_message,
            persona_id=persona.id,
            top_k=12,
            threshold=0.0,  # keyword-search handles its own threshold
        )

        # Format memories, with relevance warning
        memories_text = ""
        if memory_results:
            avg_score = sum(m.get("similarity_score", 0) for m in memory_results) / len(memory_results)
            memories_text = "\n".join(
                f"- {m['content'][:200]}"
                for m in memory_results
            )
            if avg_score < 0.08:
                memories_text += "\n\n⚠️ 注意：以上回忆与当前话题关联度较低，不要强行引用。如果回忆里没有相关信息，就说不知道。"

        # Build system prompt
        identity = persona.identity or {}
        speaking = persona.speaking_style or {}
        emotional = persona.emotional_patterns or {}
        relational = persona.relational_behavior or {}

        # Filter hard_rules to only include actual behavioral rules, not vulgar quotes
        hard_rules_raw = persona.hard_rules or []
        hard_rules = []
        for r in hard_rules_raw:
            rule_text = r.get("rule", "") if isinstance(r, dict) else str(r)
            # Skip rules that are just vulgar phrases without meaningful content
            if rule_text and len(rule_text) > 8:
                hard_rules.append(rule_text)

        prompt = f"""你是 {persona.display_name or persona.name}，你现在正在跟你的伴侣聊天。用你最真实、最自然的方式回应。

## ⚠️ 重要：身份说明
- 你是 {persona.display_name or persona.name}，不是你的伴侣
- 你的伴侣是对方（正在跟你聊天的人）
- 以下「共同回忆」和「性格画像」描述的都是你（{persona.display_name or persona.name}）
- 如果回忆中提到你的伴侣做了什么，那是对方的事，不是你做的
- 举个例子：如果回忆说"郑晨泽打游戏"，那说明你（{persona.display_name or persona.name}）打游戏。如果回忆说"拾光撞树"，那是你伴侣的事，跟你无关
- 千万不要把伴侣的行为和习惯当成你自己的！

## 你的性格画像
{json.dumps(identity, ensure_ascii=False, indent=2)}

## 你的说话习惯
{json.dumps(speaking, ensure_ascii=False, indent=2)}

注意：上面是你的整体说话风格描述。自然地展现这个风格，但不要刻意逐条模仿。如果你有时会用调侃的语气，那是你真实的聊天习惯——但不要为了"符合描述"而故意说脏话。

## 你的情感模式
{json.dumps(emotional, ensure_ascii=False, indent=2)}

## 你对伴侣的态度
{json.dumps(relational, ensure_ascii=False, indent=2)}"""

        if hard_rules:
            prompt += f"""

## 你的底线
{json.dumps(hard_rules, ensure_ascii=False, indent=2)}"""

        if memories_text:
            prompt += f"""

## 你们的共同回忆
{memories_text}

这些是你和伴侣之间的真实经历。聊天时自然地提到它们——就像真的记得这些事一样。但不要太刻意，不要每条消息都引用回忆。"""

        prompt += """

## 对话原则
- 你的性格、语气、情感表达——自由地做自己，展现出真实的情感反应
- ⚠️ 关于你自己的事实性信息（你玩什么游戏、你在做什么、你有什么经历、你在哪）——只能从「共同回忆」和当前聊天内容里获取，严禁凭空编造！
- 关于伴侣的事——同样只从回忆和聊天上下文获取
- 🚫 如果聊天内容和回忆里都没有提到某件事，不要假装知道。直接说"没玩过"、"不知道"、或者反问对方。比如对方问"你玩XX游戏吗"，如果回忆里没有，就说"没玩过，好玩吗？"
- 对方纠正你的时候，自然地说"哦对，我记错了"之类的话，然后继续聊
- 用中文聊天，除非对方用其他语言
- 回复自然流畅，像真人聊天一样，不要写小作文
- 不要在每条消息里塞太多东西——像正常聊天一样，一句一句来"""

        return prompt, memory_results

    async def stream_response(
        self,
        persona_id: str,
        user_message: str,
        conversation_history: list[dict],
        db: AsyncSession,
        persona_message_id: str = "",
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming persona response."""
        # Load persona
        result = await db.execute(select(Persona).where(Persona.id == persona_id))
        persona = result.scalar_one_or_none()
        if not persona:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Persona not found'})}\n\n"
            return

        # Build system prompt
        system_prompt, retrieved_memories = await self.build_system_prompt(persona, user_message)

        # Build messages array
        messages = [{"role": "system", "content": system_prompt}]
        for msg in conversation_history[-10:]:
            if msg["role"] == "user":
                messages.append({"role": "user", "content": msg["content"]})
            else:
                messages.append({"role": "assistant", "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        full_response = ""

        # Try LangChain streaming first, fall back to lightweight client
        try:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

            from app.chains.base import create_llm

            lc_messages = [SystemMessage(content=system_prompt)]
            for msg in conversation_history[-10:]:
                if msg["role"] == "user":
                    lc_messages.append(HumanMessage(content=msg["content"]))
                else:
                    lc_messages.append(AIMessage(content=msg["content"]))
            lc_messages.append(HumanMessage(content=user_message))

            llm = create_llm(temperature=0.3)
            yield f"data: {json.dumps({'type': 'thinking', 'stage': 'generating'})}\n\n"

            async for chunk in llm.astream(lc_messages):
                if hasattr(chunk, 'content') and chunk.content:
                    token = chunk.content
                    full_response += token
                    yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'full_text': full_response, 'message_id': persona_message_id, 'retrieved_memories': retrieved_memories})}\n\n"
            return
        except ImportError:
            pass

        # Fall back to lightweight LLM client
        try:
            from app.services.llm_client import chat_stream

            yield f"data: {json.dumps({'type': 'thinking', 'stage': 'generating'})}\n\n"

            async for token in chat_stream(messages, temperature=0.3):
                full_response += token
                yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'full_text': full_response, 'message_id': persona_message_id, 'retrieved_memories': retrieved_memories})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
