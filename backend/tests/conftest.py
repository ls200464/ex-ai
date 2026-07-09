from __future__ import annotations

import pytest


@pytest.fixture
def sample_wechat_content() -> str:
    return """2023-01-15 14:30:25 小明
    你今天吃饭了吗？

2023-01-15 14:31:10 小红
    吃了，你呢？

2023-01-15 14:32:05 小明
    还没有，刚下班好累
    今天被老板骂了

2023-01-15 14:33:00 小红
    辛苦了宝贝，快去吃点东西吧
    我给你点了外卖
    """
