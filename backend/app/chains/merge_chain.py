"""Incremental merge chain — merges new extraction results with existing data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Output schemas ─────────────────────────────────────


class MergeConflict(BaseModel):
    field: str
    existing_value: str
    new_value: str
    recommendation: str  # "keep_existing" | "replace" | "merge" | "needs_review"
    reasoning: str


class MergeResult(BaseModel):
    merged_persona: dict = Field(default_factory=dict)
    new_memories: list[dict] = Field(default_factory=list)
    updated_memories: list[dict] = Field(default_factory=list)
    conflicts: list[MergeConflict] = Field(default_factory=list)
    summary: str = ""


# ── Prompt ──────────────────────────────────────────────

MERGE_SYSTEM_PROMPT = """You are a data reconciliation specialist. Your job is to merge newly extracted persona traits and relationship memories with existing data.

## Rules

1. **New information > Contradicting old**: If new analysis contradicts previous, prefer the new UNLESS the old was manually confirmed
2. **Merge complementary**: If new and old cover different aspects of the same trait, combine them
3. **Flag conflicts**: If there's a genuine contradiction, flag it for review
4. **Dedup memories**: If a new memory describes the same event as an existing one, merge details rather than creating a duplicate
5. **Preserve manual edits**: Never override fields that were manually edited by the user

Output MUST be valid JSON matching the schema exactly.

{format_instructions}"""


# ── Chain builder (requires LangChain) ──────────────────

def build_merge_chain(llm=None) -> Any:
    """Build the incremental merge chain. Requires langchain_core."""
    from app.chains.base import build_extraction_chain, create_llm
    return build_extraction_chain(
        system_prompt=MERGE_SYSTEM_PROMPT,
        output_schema=MergeResult,
        llm=llm or create_llm(),
    )
