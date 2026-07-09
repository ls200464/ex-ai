"""Unified message format for all chat data sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class UnifiedMessage:
    """Normalized message format regardless of source (WeChat/QQ/etc)."""

    sender_name: str
    sender_role: str  # "user" | "target" | "other"
    content: str
    content_type: str = "text"  # text | image_desc | voice_transcript | sticker | file
    original_timestamp: datetime | None = None
    raw_metadata: dict = field(default_factory=dict)


def _parse_timestamp(ts: object) -> datetime | None:
    """Parse a timestamp into a datetime object. Handles datetime, ISO string, and None."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        try:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            try:
                return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
    return None


def normalize_messages(
    raw_messages: list[dict],
    user_name: str,
    target_name: str,
) -> list[UnifiedMessage]:
    """Normalize raw parsed messages into UnifiedMessage format.

    Uses fuzzy matching: if a sender's name CONTAINS the target_name or vice versa,
    they're matched. This handles cases like "郑晨泽(1234567890)" vs "郑晨泽".

    Args:
        raw_messages: Raw messages from parser (with sender_name, content, timestamp)
        user_name: The name of the user (the person using this app)
        target_name: The name of the ex-partner (persona's display_name)

    Returns:
        List of normalized UnifiedMessage objects
    """
    # Collect all unique sender names and auto-detect roles if user/target are generic
    senders = list({msg.get("sender_name", "") for msg in raw_messages if msg.get("sender_name")})

    def _name_matches(sender: str, role_name: str) -> bool:
        """Fuzzy match: sender contains role_name or vice versa."""
        if not sender or not role_name:
            return False
        s = sender.lower().strip()
        r = role_name.lower().strip()
        # Skip generic placeholders
        if r in ("user", "target", "other", ""):
            return False
        return r in s or s in r

    def _determine_role(sender: str) -> str:
        if _name_matches(sender, target_name):
            return "target"
        if _name_matches(sender, user_name):
            return "user"

        # Auto-detect: if there are exactly 2 main speakers and neither matches,
        # use frequency: most frequent = likely target (the ex being analyzed)
        if len(senders) == 2 and target_name not in ("user", "target", "") and user_name not in ("user", "target", ""):
            # Can't determine — mark as "other" but this shouldn't happen with proper names
            return "other"

        # Fallback: try partial match with just the name part before any parens
        sender_clean = sender.split("(")[0].strip() if "(" in sender else sender
        if _name_matches(sender_clean, target_name):
            return "target"
        if _name_matches(sender_clean, user_name):
            return "user"

        return "other"

    result: list[UnifiedMessage] = []
    for msg in raw_messages:
        sender = msg.get("sender_name", "")
        role = _determine_role(sender)

        result.append(
            UnifiedMessage(
                sender_name=sender,
                sender_role=role,
                content=msg.get("content", ""),
                content_type=msg.get("content_type", "text"),
                original_timestamp=_parse_timestamp(msg.get("timestamp")),
                raw_metadata=msg.get("metadata", {}),
            )
        )
    return result
