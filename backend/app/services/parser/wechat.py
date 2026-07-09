"""WeChat chat record parser.

Handles the standard WeChat "Export Chat History" .txt format:
    YYYY-MM-DD HH:MM:SS SenderName
    Message content
"""

from __future__ import annotations

import re
from datetime import datetime

from app.services.parser.base import BaseParser


class WeChatParser(BaseParser):
    """Parse WeChat exported .txt chat records."""

    # Pattern: "2023-01-15 14:30:25 SenderName"
    MSG_HEADER = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.+?)$")

    # System message pattern (no sender)
    SYSTEM_MSG = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.+)$")

    async def parse(self, file_path: str) -> list[dict]:
        messages: list[dict] = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="gbk") as f:
                lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            match = self.MSG_HEADER.match(line)
            if match:
                timestamp_str = match.group(1)
                sender = match.group(2).strip()

                # Collect message content (may span multiple lines until next header)
                content_lines: list[str] = []
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if not next_line:
                        i += 1
                        continue
                    if self.MSG_HEADER.match(next_line):
                        break
                    content_lines.append(next_line)
                    i += 1

                content = "\n".join(content_lines)
                if content:
                    try:
                        ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        ts = None

                    messages.append({
                        "sender_name": sender,
                        "content": content,
                        "timestamp": ts,
                        "content_type": "text",
                    })
            else:
                # System message or continuation
                i += 1

        return messages

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith((".txt",))
