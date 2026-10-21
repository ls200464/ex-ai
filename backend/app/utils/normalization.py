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

    Sender names are matched against ``user_name`` and ``target_name`` by
    strength: an exact match wins, then a match after stripping a trailing
    account identifier (``"郑晨泽(1234567890)"`` vs ``"郑晨泽"``), then a plain
    containment match. Senders matching neither are labelled ``"other"``.

    Args:
        raw_messages: Raw messages from parser (with sender_name, content, timestamp)
        user_name: The name of the user (the person using this app)
        target_name: The name of the ex-partner (persona's display_name)

    Returns:
        List of normalized UnifiedMessage objects
    """
    def _strip_identifier(name: str) -> str:
        """Drop a trailing account identifier such as "(12345678)" or "（12345678）"."""
        for separator in ("(", "（"):
            if separator in name:
                name = name.split(separator)[0]
        return name.strip()

    def _match_strength(sender: str, role_name: str) -> int:
        """How strongly a sender name matches a role name.

        0 = no match, 1 = one contains the other, 2 = equal once the account
        identifier is stripped, 3 = exactly equal.

        Ranked rather than boolean, because a plain substring test lets a short
        role name capture an unrelated sender: with target "张三", the sender
        "张三丰" also contains it and both would be labelled "target".
        """
        if not sender or not role_name:
            return 0
        s = sender.lower().strip()
        r = role_name.lower().strip()
        # Skip generic placeholders
        if r in ("user", "target", "other", ""):
            return 0
        if s == r:
            return 3
        if _strip_identifier(s) == r:
            return 2
        if r in s or s in r:
            return 1
        return 0

    def _determine_role(sender: str) -> str:
        target_strength = _match_strength(sender, target_name)
        user_strength = _match_strength(sender, user_name)
        if target_strength == 0 and user_strength == 0:
            return "other"
        # Ties favour the target: the persona being rebuilt is what the
        # extraction pipeline cares about most.
        return "target" if target_strength >= user_strength else "user"

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
