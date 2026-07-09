"""Abstract base parser for chat data sources."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseParser(ABC):
    """Base class for all chat log parsers."""

    @abstractmethod
    async def parse(self, file_path: str) -> list[dict]:
        """Parse a file and return a list of raw message dicts.

        Each dict should have: sender_name, content, timestamp (optional), content_type (optional)
        """
        ...

    @abstractmethod
    def supports(self, file_path: str) -> bool:
        """Check if this parser supports the given file."""
        ...
