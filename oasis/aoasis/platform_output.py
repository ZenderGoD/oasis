from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oasis.atherum import PersistentPopulationSnapshot


@dataclass(frozen=True)
class AOasisSocialComment:
    comment_id: int
    surface: str
    author_name: str
    author_handle: str
    content: str
    created_at: str
    metrics: dict[str, int]
    agent_id: int | None = None
    stable_agent_id: str | None = None


@dataclass(frozen=True)
class AOasisSocialPost:
    post_id: int
    surface: str
    author_name: str
    author_handle: str
    content: str
    created_at: str
    metrics: dict[str, int]
    comments: list[AOasisSocialComment] = field(default_factory=list)
    original_post_id: int | None = None
    quote_content: str | None = None
    agent_id: int | None = None
    stable_agent_id: str | None = None


@dataclass(frozen=True)
class AOasisSocialAction:
    actor_name: str
    actor_handle: str
    action_type: str
    created_at: str
    text: str = ""
    target_id: int | None = None
    agent_id: int | None = None
    stable_agent_id: str | None = None


@dataclass(frozen=True)
class AOasisPlatformOutput:
    platform: str
    posts: list[AOasisSocialPost]
    actions: list[AOasisSocialAction]
    totals: dict[str, int]


def normalize_platform_db(
    platform: str,
    db_path: str | Path,
    population: PersistentPopulationSnapshot | None = None,
) -> AOasisPlatformOutput:
    normalized_platform = platform.strip().lower()
    if normalized_platform not in {"twitter", "reddit", "instagram"}:
        raise ValueError(f"Unsupported A-Oasis platform output: {platform}")

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        users = _load_users(db)
        stable_ids = _stable_agent_ids(population)
        comments_by_post = _load_comments_by_post(db, users,
                                                  stable_ids,
                                                  normalized_platform)
        posts = _load_posts(db, users, stable_ids, comments_by_post,
                            normalized_platform)
        actions = _load_actions(db, users, stable_ids)
    finally:
        db.close()

    return AOasisPlatformOutput(
        platform=normalized_platform,
        posts=posts,
        actions=actions,
        totals={
            "posts": len(posts),
            "comments": sum(len(post.comments) for post in posts),
            "actions": len(actions),
        },
    )


def _load_users(db: sqlite3.Connection) -> dict[int, sqlite3.Row]:
    rows = db.execute("SELECT * FROM user").fetchall()
    return {row["user_id"]: row for row in rows}


def _load_comments_by_post(
    db: sqlite3.Connection,
    users: dict[int, sqlite3.Row],
    stable_ids: dict[int, str],
    platform: str,
) -> dict[int, list[AOasisSocialComment]]:
    rows = db.execute("""
        SELECT *
        FROM comment
        ORDER BY created_at ASC, comment_id ASC
    """).fetchall()
    comments_by_post: dict[int, list[AOasisSocialComment]] = {}
    for row in rows:
        user = users.get(row["user_id"])
        agent_id = _agent_id(user)
        comments_by_post.setdefault(row["post_id"], []).append(
            AOasisSocialComment(
                comment_id=row["comment_id"],
                agent_id=agent_id,
                stable_agent_id=_stable_id(stable_ids, agent_id),
                surface=_comment_surface(platform),
                author_name=_user_name(user),
                author_handle=_user_handle(user, platform),
                content=row["content"] or "",
                created_at=str(row["created_at"]),
                metrics=_comment_metrics(row, platform),
            ))
    return comments_by_post


def _load_posts(
    db: sqlite3.Connection,
    users: dict[int, sqlite3.Row],
    stable_ids: dict[int, str],
    comments_by_post: dict[int, list[AOasisSocialComment]],
    platform: str,
) -> list[AOasisSocialPost]:
    rows = db.execute("""
        SELECT *
        FROM post
        WHERE original_post_id IS NULL
        ORDER BY created_at ASC, post_id ASC
    """).fetchall()
    posts = []
    for row in rows:
        user = users.get(row["user_id"])
        agent_id = _agent_id(user)
        comments = comments_by_post.get(row["post_id"], [])
        posts.append(
            AOasisSocialPost(
                post_id=row["post_id"],
                agent_id=agent_id,
                stable_agent_id=_stable_id(stable_ids, agent_id),
                surface=_post_surface(platform),
                author_name=_user_name(user),
                author_handle=_user_handle(user, platform),
                content=row["content"] or "",
                created_at=str(row["created_at"]),
                metrics=_post_metrics(row, comments, platform),
                comments=comments,
                original_post_id=row["original_post_id"],
                quote_content=row["quote_content"],
            ))
    return posts


def _load_actions(
    db: sqlite3.Connection,
    users: dict[int, sqlite3.Row],
    stable_ids: dict[int, str],
) -> list[AOasisSocialAction]:
    rows = db.execute("""
        SELECT *
        FROM trace
        ORDER BY created_at ASC, rowid ASC
    """).fetchall()
    actions = []
    for row in rows:
        user = users.get(row["user_id"])
        agent_id = _agent_id(user)
        info = _safe_json(row["info"])
        actions.append(
            AOasisSocialAction(
                agent_id=agent_id,
                stable_agent_id=_stable_id(stable_ids, agent_id),
                actor_name=_user_name(user),
                actor_handle=_user_handle(user, "twitter"),
                action_type=row["action"],
                created_at=str(row["created_at"]),
                text=_action_text(info),
                target_id=_action_target(info),
            ))
    return actions


def _post_metrics(
    row: sqlite3.Row,
    comments: list[AOasisSocialComment],
    platform: str,
) -> dict[str, int]:
    if platform == "reddit":
        return {
            "upvotes": int(row["num_likes"] or 0),
            "downvotes": int(row["num_dislikes"] or 0),
            "comments": len(comments),
            "shares": int(row["num_shares"] or 0),
        }
    if platform == "instagram":
        return {
            "likes": int(row["num_likes"] or 0),
            "comments": len(comments),
            "shares": int(row["num_shares"] or 0),
            "saves": 0,
        }
    return {
        "likes": int(row["num_likes"] or 0),
        "reposts": int(row["num_shares"] or 0),
        "replies": len(comments),
        "quotes": 0,
    }


def _comment_metrics(row: sqlite3.Row, platform: str) -> dict[str, int]:
    if platform == "reddit":
        return {
            "upvotes": int(row["num_likes"] or 0),
            "downvotes": int(row["num_dislikes"] or 0),
        }
    return {"likes": int(row["num_likes"] or 0)}


def _post_surface(platform: str) -> str:
    return {
        "instagram": "instagram_post",
        "reddit": "reddit_thread",
        "twitter": "twitter_feed",
    }[platform]


def _comment_surface(platform: str) -> str:
    return {
        "instagram": "instagram_comment",
        "reddit": "reddit_comment",
        "twitter": "twitter_reply",
    }[platform]


def _user_name(user: sqlite3.Row | None) -> str:
    if user is None:
        return "Unknown"
    return user["name"] or user["user_name"] or f"Agent {user['agent_id']}"


def _agent_id(user: sqlite3.Row | None) -> int | None:
    if user is None:
        return None
    value = user["agent_id"]
    return int(value) if value is not None else None


def _user_handle(user: sqlite3.Row | None, platform: str) -> str:
    if user is None:
        return "@unknown" if platform != "reddit" else "u/unknown"
    handle = user["user_name"] or f"agent_{user['agent_id']}"
    if platform == "reddit":
        return f"u/{handle}"
    return f"@{handle}"


def _stable_agent_ids(
    population: PersistentPopulationSnapshot | None,
) -> dict[int, str]:
    if population is None:
        return {}
    return {
        agent.numeric_agent_id: agent.stable_agent_id
        for agent in population.agents
    }


def _stable_id(stable_ids: dict[int, str], agent_id: int | None) -> str | None:
    if agent_id is None:
        return None
    return stable_ids.get(agent_id)


def _safe_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _action_text(info: dict[str, Any]) -> str:
    value = info.get("content") or info.get("quote_content") or ""
    return value if isinstance(value, str) else ""


def _action_target(info: dict[str, Any]) -> int | None:
    for key in ("post_id", "comment_id", "quoted_id", "reposted_id"):
        value = info.get(key)
        if isinstance(value, int):
            return value
    return None
