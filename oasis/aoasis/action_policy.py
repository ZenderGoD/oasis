from __future__ import annotations

from oasis.social_platform.typing import ActionType


def platform_action_policy(platform: str) -> list[ActionType]:
    """Return the public actions an A-Oasis agent may use on a platform."""
    normalized_platform = platform.strip().lower()
    if normalized_platform == "twitter":
        return [
            ActionType.CREATE_POST,
            ActionType.LIKE_POST,
            ActionType.REPOST,
            ActionType.QUOTE_POST,
            ActionType.REFRESH,
            ActionType.DO_NOTHING,
            ActionType.FOLLOW,
        ]
    if normalized_platform == "reddit":
        return [
            ActionType.CREATE_POST,
            ActionType.CREATE_COMMENT,
            ActionType.LIKE_POST,
            ActionType.DISLIKE_POST,
            ActionType.LIKE_COMMENT,
            ActionType.DISLIKE_COMMENT,
            ActionType.REFRESH,
            ActionType.DO_NOTHING,
            ActionType.SEARCH_POSTS,
            ActionType.SEARCH_USER,
            ActionType.TREND,
            ActionType.FOLLOW,
            ActionType.MUTE,
        ]
    if normalized_platform == "instagram":
        return [
            ActionType.CREATE_POST,
            ActionType.LIKE_POST,
            ActionType.REPOST,
            ActionType.CREATE_COMMENT,
            ActionType.LIKE_COMMENT,
            ActionType.REFRESH,
            ActionType.DO_NOTHING,
            ActionType.FOLLOW,
        ]
    raise ValueError(f"Unsupported A-Oasis platform: {platform}")
