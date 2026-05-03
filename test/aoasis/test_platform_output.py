from __future__ import annotations

import sqlite3

from oasis.aoasis import normalize_platform_db
from oasis.atherum import AtherumPopulationStore, build_default_population


def test_normalize_reddit_output_builds_thread_with_comments_and_actions(
    tmp_path,
):
    db_path = _create_social_db(tmp_path)

    output = normalize_platform_db("reddit", db_path)

    assert output.platform == "reddit"
    assert output.totals == {"posts": 1, "comments": 1, "actions": 3}
    assert output.posts[0].surface == "reddit_thread"
    assert output.posts[0].agent_id == 0
    assert output.posts[0].author_handle == "u/skeptic"
    assert output.posts[0].content == "Can this sneaker justify the premium?"
    assert output.posts[0].metrics == {
        "upvotes": 5,
        "downvotes": 2,
        "comments": 1,
        "shares": 1,
    }
    assert output.posts[0].comments[0].content == (
        "Only if the materials and warranty are clear."
    )
    assert output.posts[0].comments[0].agent_id == 1
    assert output.actions[0].action_type == "create_post"
    assert output.actions[0].agent_id == 0
    assert output.actions[0].text == "Can this sneaker justify the premium?"


def test_normalize_twitter_output_builds_feed_metrics(tmp_path):
    db_path = _create_social_db(tmp_path)

    output = normalize_platform_db("twitter", db_path)

    assert output.platform == "twitter"
    assert output.posts[0].surface == "twitter_feed"
    assert output.posts[0].metrics == {
        "likes": 5,
        "reposts": 1,
        "replies": 1,
        "quotes": 0,
    }
    assert output.posts[0].comments[0].surface == "twitter_reply"


def test_normalize_instagram_output_maps_visual_feed_metrics(tmp_path):
    db_path = _create_social_db(tmp_path)

    output = normalize_platform_db("instagram", db_path)

    assert output.platform == "instagram"
    assert output.posts[0].surface == "instagram_post"
    assert output.posts[0].metrics == {
        "likes": 5,
        "comments": 1,
        "shares": 1,
        "saves": 0,
    }
    assert output.posts[0].comments[0].surface == "instagram_comment"


def test_normalize_output_maps_population_stable_society_agent_ids(tmp_path):
    db_path = _create_social_db(tmp_path)
    store = AtherumPopulationStore(tmp_path / "population.db")
    population = store.ensure_population(
        "workspace-sneaker-audience",
        build_default_population(
            "workspace-sneaker-audience",
            count=2,
            seed="baseline",
        ),
    )

    output = normalize_platform_db("reddit", db_path, population=population)

    assert output.posts[0].stable_agent_id == (
        "workspace-sneaker-audience:baseline:slot-000"
    )
    assert output.posts[0].comments[0].stable_agent_id == (
        "workspace-sneaker-audience:baseline:slot-001"
    )
    assert output.actions[0].stable_agent_id == (
        "workspace-sneaker-audience:baseline:slot-000"
    )


def _create_social_db(tmp_path):
    db_path = tmp_path / "platform.db"
    db = sqlite3.connect(db_path)
    db.executescript("""
    CREATE TABLE user (
        user_id INTEGER PRIMARY KEY,
        agent_id INTEGER,
        user_name TEXT,
        name TEXT,
        bio TEXT,
        created_at TEXT
    );
    CREATE TABLE post (
        post_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        original_post_id INTEGER,
        content TEXT DEFAULT '',
        quote_content TEXT,
        created_at TEXT,
        num_likes INTEGER DEFAULT 0,
        num_dislikes INTEGER DEFAULT 0,
        num_shares INTEGER DEFAULT 0,
        num_reports INTEGER DEFAULT 0
    );
    CREATE TABLE comment (
        comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        user_id INTEGER,
        content TEXT,
        created_at TEXT,
        num_likes INTEGER DEFAULT 0,
        num_dislikes INTEGER DEFAULT 0
    );
    CREATE TABLE trace (
        user_id INTEGER,
        created_at TEXT,
        action TEXT,
        info TEXT
    );
    """)
    db.execute(
        "INSERT INTO user VALUES "
        "(1, 0, 'skeptic', 'Skeptic Buyer', '', '0'),"
        "(2, 1, 'visual', 'Visual Amplifier', '', '0')"
    )
    db.execute(
        """
        INSERT INTO post (
            post_id,
            user_id,
            original_post_id,
            content,
            quote_content,
            created_at,
            num_likes,
            num_dislikes,
            num_shares,
            num_reports
        )
        VALUES (1, 1, NULL, ?, NULL, '0', 5, 2, 1, 0)
        """,
        ("Can this sneaker justify the premium?", ),
    )
    db.execute(
        "INSERT INTO comment VALUES (1, 1, 2, ?, '1', 2, 0)",
        ("Only if the materials and warranty are clear.", ),
    )
    db.execute(
        "INSERT INTO trace VALUES (1, '0', 'create_post', ?)",
        ('{"content":"Can this sneaker justify the premium?","post_id":1}', ),
    )
    db.execute(
        "INSERT INTO trace VALUES (2, '1', 'create_comment', ?)",
        ('{"content":"Only if the materials and warranty are clear.",'
         '"comment_id":1}', ),
    )
    db.execute(
        "INSERT INTO trace VALUES (2, '2', 'like_post', ?)",
        ('{"post_id":1}', ),
    )
    db.commit()
    db.close()
    return db_path
