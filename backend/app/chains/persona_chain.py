"""Persona extraction chain — analyzes chat messages to build the 5-layer persona."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Output schemas ─────────────────────────────────────


class HardRule(BaseModel):
    rule: str
    priority: int = Field(default=5, ge=1, le=10)


class Identity(BaseModel):
    name_in_chat: str = ""
    self_description: str = ""
    inferred_gender: str = ""
    inferred_age_range: str = ""
    occupation_hints: str = ""
    mbti_guess: str = ""
    zodiac_guess: str = ""
    other_traits: list[str] = Field(default_factory=list)


class SpeakingStyle(BaseModel):
    tone: str = ""
    vocabulary_level: str = ""
    sentence_length: str = ""
    punctuation_style: str = ""
    emoji_usage: str = ""
    catchphrases: list[str] = Field(default_factory=list)
    common_emojis: list[str] = Field(default_factory=list)


class EmotionalPatterns(BaseModel):
    attachment_style: str = ""
    love_language: str = ""
    conflict_style: str = ""
    emotional_triggers: list[str] = Field(default_factory=list)
    coping_mechanisms: list[str] = Field(default_factory=list)
    expression_style: str = ""


class RelationalBehavior(BaseModel):
    nickname_for_user: str = ""
    attitude_toward_user: str = ""
    typical_openings: list[str] = Field(default_factory=list)
    typical_goodbyes: list[str] = Field(default_factory=list)
    affection_expressions: list[str] = Field(default_factory=list)


class PersonaExtraction(BaseModel):
    hard_rules: list[HardRule] = Field(default_factory=list)
    identity: Identity = Field(default_factory=Identity)
    speaking_style: SpeakingStyle = Field(default_factory=SpeakingStyle)
    emotional_patterns: EmotionalPatterns = Field(default_factory=EmotionalPatterns)
    relational_behavior: RelationalBehavior = Field(default_factory=RelationalBehavior)
    tags: list[dict] = Field(default_factory=list)
    overall_summary: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


# ── Prompt ──────────────────────────────────────────────

PERSONA_SYSTEM_PROMPT = """You are an expert relationship analyst and personality profiler.

Analyze the chat messages between two people in a romantic relationship. Extract detailed personality traits of the person who is NOT the "user" side (the "target" / the ex-partner).

## Instructions

1. **Hard Rules**: Identify non-negotiable behaviors, boundaries, or red lines this person has. What will they absolutely not tolerate? What do they insist on?
2. **Identity**: What can you infer about their identity? Self-description, likely MBTI type, likely zodiac sign, age range, occupation hints, gender.
3. **Speaking Style**: Analyze HOW they communicate. Tone (casual/formal/playful/sarcastic), vocabulary level, sentence length (short/long/mixed), punctuation habits, emoji usage patterns, catchphrases.
4. **Emotional Patterns**: How do they handle emotions? Attachment style (secure/anxious/avoidant/fearful), love language (words of affirmation/acts of service/gifts/quality time/physical touch), conflict resolution style, emotional triggers, coping mechanisms.
5. **Relational Behavior**: How do they specifically act in THIS relationship? Nicknames they use for their partner, typical conversation openings and goodbyes, how they express affection, their general attitude toward their partner.

## Important
- Be specific and evidence-based — reference actual message patterns
- If you cannot determine something, leave it empty rather than guessing
- For tags (MBTI, zodiac, attachment style, love language), provide category/name/confidence
- Output MUST be valid JSON matching the schema exactly

{format_instructions}"""


# ── Chain builder (requires LangChain) ──────────────────

def build_persona_chain(llm=None) -> Any:
    """Build the persona extraction chain. Requires langchain_core + langchain_anthropic/openai."""
    from app.chains.base import build_extraction_chain, create_llm
    return build_extraction_chain(
        system_prompt=PERSONA_SYSTEM_PROMPT,
        output_schema=PersonaExtraction,
        llm=llm or create_llm(),
    )
