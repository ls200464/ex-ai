from __future__ import annotations

import tempfile

import pytest

from app.services.parser.wechat import WeChatParser


@pytest.mark.asyncio
async def test_wechat_parser_parses_messages():
    content = """2023-01-15 14:30:25 SenderA
Hello there

2023-01-15 14:31:10 SenderB
Hi! How are you?
I'm doing great today

2023-01-15 14:32:05 SenderA
That's wonderful to hear
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(content)
        f.flush()
        parser = WeChatParser()
        messages = await parser.parse(f.name)

    assert len(messages) == 3
    assert messages[0]["sender_name"] == "SenderA"
    assert messages[0]["content"] == "Hello there"
    assert messages[1]["content"] == "Hi! How are you?\nI'm doing great today"
    assert messages[2]["sender_name"] == "SenderA"
