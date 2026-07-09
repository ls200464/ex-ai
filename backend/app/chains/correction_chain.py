"""Correction handler chain — processes user corrections to persona responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Output schemas ─────────────────────────────────────


class CorrectionResult(BaseModel):
    rule_type: str = Field(description="phrase_ban | phrase_replace | tone_adjust | behavior_override")
    trigger_text: str | None = Field(None)
    correction_text: str | None = Field(None)
    target_layer: str | None = Field(None, description="Which persona layer to patch")
    layer_patch: dict | None = Field(None, description="JSON patch for the target layer")
    explanation: str = ""
    priority: int = Field(default=0)


# ── Prompt ──────────────────────────────────────────────

CORRECTION_SYSTEM_PROMPT = """You analyze user corrections to AI-generated persona responses and convert them into structured correction rules.

## Rule Types

1. **phrase_ban**: The persona should NEVER say certain words/phrases. e.g., "they never say '亲爱的'"
2. **phrase_replace**: Replace one phrase with another. e.g., "they call me '猪' not '宝贝'"
3. **tone_adjust**: The tone is wrong — too formal, too casual, too cold, too warm
4. **behavior_override**: A deeper behavioral change — patch the persona layer JSON

## Instructions

- Analyze the original message and the correction
- Determine what type of rule this is
- For behavior_overrides, identify which persona layer (hard_rules/identity/speaking_style/emotional_patterns/relational_behavior) needs patching
- Generate a precise layer_patch JSON for behavior_overrides
- Be specific and minimal — don't over-correct

{format_instructions}"""


# ── Chain builder (requires LangChain) ──────────────────

def build_correction_chain(llm=None) -> Any:
    """Build the correction handler chain. Requires langchain_core."""
    from app.chains.base import build_extraction_chain, create_llm
    return build_extraction_chain(
        system_prompt=CORRECTION_SYSTEM_PROMPT,
        output_schema=CorrectionResult,
        llm=llm or create_llm(),
    )
