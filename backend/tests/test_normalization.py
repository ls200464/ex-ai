"""Regression tests for sender-role assignment.

These cover the ranked matcher: a plain substring test made a short role name
capture an unrelated sender, and the account-id fallback was unreachable in the
common two-speaker case.
"""

from __future__ import annotations

from app.utils.normalization import normalize_messages


def _roles(raw, user_name, target_name):
    return [m.sender_role for m in normalize_messages(raw, user_name, target_name)]


def _msg(sender, content="x"):
    return {"sender_name": sender, "content": content, "timestamp": None}


def test_shared_prefix_names_are_not_both_the_target():
    """'张三丰' must not be classified as the target just because it contains '张三'."""
    roles = _roles([_msg("张三"), _msg("张三丰")], user_name="张三丰", target_name="张三")
    assert roles == ["target", "user"]


def test_exact_names_are_matched():
    roles = _roles([_msg("张三"), _msg("李四")], user_name="李四", target_name="张三")
    assert roles == ["target", "user"]


def test_account_identifier_is_stripped():
    roles = _roles([_msg("郑晨泽(1234567890)")], user_name="me", target_name="郑晨泽")
    assert roles == ["target"]


def test_fullwidth_account_identifier_is_stripped():
    roles = _roles([_msg("郑晨泽（1234567890）")], user_name="me", target_name="郑晨泽")
    assert roles == ["target"]


def test_unrelated_sender_is_other():
    roles = _roles([_msg("路人")], user_name="李四", target_name="张三")
    assert roles == ["other"]


def test_generic_placeholders_never_match():
    """Role names like 'user'/'target' are placeholders, not names to match."""
    roles = _roles([_msg("user")], user_name="user", target_name="target")
    assert roles == ["other"]


def test_timestamps_are_parsed_in_all_supported_forms():
    from datetime import datetime

    raw = [
        {"sender_name": "张三", "content": "x", "timestamp": "2023-01-15T14:30:25"},
        {"sender_name": "张三", "content": "x", "timestamp": "2023-01-15 14:30:25"},
        {"sender_name": "张三", "content": "x", "timestamp": datetime(2023, 1, 15)},
        {"sender_name": "张三", "content": "x", "timestamp": "not a date"},
    ]
    out = normalize_messages(raw, user_name="李四", target_name="张三")
    assert out[0].original_timestamp == datetime(2023, 1, 15, 14, 30, 25)
    assert out[1].original_timestamp == datetime(2023, 1, 15, 14, 30, 25)
    assert out[2].original_timestamp == datetime(2023, 1, 15)
    assert out[3].original_timestamp is None
