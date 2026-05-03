from __future__ import annotations

from oasis.aoasis import platform_action_policy
from oasis.social_platform.typing import ActionType


def test_platform_action_policy_returns_platform_specific_actions():
    twitter_actions = platform_action_policy("twitter")
    reddit_actions = platform_action_policy("reddit")
    instagram_actions = platform_action_policy("instagram")

    assert ActionType.QUOTE_POST in twitter_actions
    assert ActionType.CREATE_COMMENT not in twitter_actions
    assert ActionType.CREATE_COMMENT in reddit_actions
    assert ActionType.DISLIKE_POST in reddit_actions
    assert ActionType.LIKE_POST in instagram_actions
    assert ActionType.REPOST in instagram_actions
    assert ActionType.DISLIKE_POST not in instagram_actions


def test_platform_action_policy_rejects_unknown_platform():
    import pytest

    with pytest.raises(ValueError, match="Unsupported A-Oasis platform"):
        platform_action_policy("linkedin")
