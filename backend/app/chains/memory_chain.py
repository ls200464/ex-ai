"""Memory extraction chain — extracts relationship memories from chat messages."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Output schemas ─────────────────────────────────────


class ExtractedMemory(BaseModel):
    category: str = Field(description="One of: shared_experience, date, inside_joke, argument, sweet_moment, timeline_event")
    title: str = Field(description="Short title summarizing this memory")
    content: str = Field(description="Detailed description of the memory")
    participants: list[str] = Field(default_factory=list)
    occurred_at: str | None = Field(None, description="Date or approximate timeframe")
    location: str | None = Field(None)
    emotional_tone: str | None = Field(None, description="e.g. happy, sad, angry, nostalgic, bittersweet")
    importance: int = Field(default=5, ge=1, le=10)


class MemoryExtraction(BaseModel):
    memories: list[ExtractedMemory] = Field(default_factory=list)
    timeline_events: list[dict] = Field(default_factory=list)
    extraction_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


# ── Prompt ──────────────────────────────────────────────

MEMORY_SYSTEM_PROMPT = """You are a meticulous relationship archivist. Your job is to extract specific, concrete memories and shared experiences from chat messages between two people who were in a romantic relationship.

## Memory Categories

1. **shared_experience**: Trips, events, activities they did together
2. **date**: Specific important dates (anniversaries, first date, special occasions)
3. **inside_joke**: Private jokes, nicknames, references only they understand
4. **argument**: Conflicts, disagreements, their patterns and resolutions
5. **sweet_moment**: Romantic, tender, or particularly warm exchanges
6. **timeline_event**: Key milestones in the relationship timeline

## Instructions

- Extract memories from BOTH sides of the conversation
- Be specific — include details, context, and direct quotes when helpful
- **title**: REQUIRED — write a short descriptive title for each memory (5-15 words summarizing what happened)
- Rate importance 1-10 based on emotional weight and recurrence
- Note the emotional tone of each memory
- If a memory spans multiple messages, consolidate into one entry
- Build a timeline of key relationship events with approximate dates
- Output MUST be valid JSON matching the schema exactly. Every memory object MUST include: category, title, content, importance, emotional_tone

{format_instructions}"""


# ── Chain builder (requires LangChain) ──────────────────

def build_memory_chain(llm=None) -> Any:
    """Build the memory extraction chain. Requires langchain_core + langchain_anthropic/openai."""
    from app.chains.base import build_extraction_chain, create_llm
    return build_extraction_chain(
        system_prompt=MEMORY_SYSTEM_PROMPT,
        output_schema=MemoryExtraction,
        llm=llm or create_llm(),
    )
