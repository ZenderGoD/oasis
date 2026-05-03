from __future__ import annotations

import pytest

from oasis.atherum import (
    AtherumPopulationStore,
    PersistentAgentProfile,
    extract_memory_updates_from_trace,
)


def test_ensure_population_is_idempotent_and_preserves_memory(tmp_path):
    store = AtherumPopulationStore(tmp_path / "atherum_population.db")
    agents = [
        PersistentAgentProfile(
            stable_agent_id="workspace-001",
            numeric_agent_id=1,
            user_name="agent_1",
            name="Mira",
            description="A visually driven early adopter.",
            profile={"other_info": {"age": 29, "country": "US"}},
        ),
        PersistentAgentProfile(
            stable_agent_id="workspace-002",
            numeric_agent_id=2,
            user_name="agent_2",
            name="Dev",
            description="A practical buyer focused on price and durability.",
        ),
    ]

    first = store.ensure_population(
        "workspace-main",
        agents,
        metadata={"workspaceId": "workspace-main"},
    )
    store.record_run_result(
        population_id="workspace-main",
        run_id="run-001",
        memory_updates={
            "workspace-001": "Prefers polished product imagery when trust cues are visible.",
        },
    )

    second = store.ensure_population(
        "workspace-main",
        [
            PersistentAgentProfile(
                stable_agent_id="workspace-001",
                numeric_agent_id=1,
                user_name="agent_1",
                name="Mira Updated",
                description="Updated description.",
            ),
            agents[1],
        ],
    )
    store.record_run_result(
        population_id="workspace-main",
        run_id="run-001",
        memory_updates={
            "workspace-001": "Prefers polished product imagery when trust cues are visible.",
        },
    )

    assert first.population_id == second.population_id == "workspace-main"
    assert [agent.stable_agent_id for agent in second.agents] == [
        "workspace-001",
        "workspace-002",
    ]
    assert second.agents[0].profile.name == "Mira Updated"
    assert second.agents[0].memories == [
        "Prefers polished product imagery when trust cues are visible."
    ]


def test_agent_state_materializes_reddit_user_info_with_required_profile_defaults(
    tmp_path,
):
    store = AtherumPopulationStore(tmp_path / "atherum_population.db")
    snapshot = store.ensure_population(
        "workspace-main",
        [
            PersistentAgentProfile(
                stable_agent_id="workspace-001",
                numeric_agent_id=7,
                user_name="agent_7",
                name="Priya",
                description="Conversion-focused reviewer.",
                profile={"other_info": {"mbti": "INTJ"}},
            )
        ],
    )
    store.record_run_result(
        population_id="workspace-main",
        run_id="run-002",
        memory_updates={
            "workspace-001": "Recently criticized vague premium pricing.",
        },
    )

    state = store.load_population("workspace-main").agents[0]
    user_info = state.to_user_info(recsys_type="reddit")

    assert user_info.user_name == "agent_7"
    assert user_info.name == "Priya"
    assert user_info.recsys_type == "reddit"
    assert user_info.profile["other_info"]["gender"] == "unknown"
    assert user_info.profile["other_info"]["age"] == 0
    assert user_info.profile["other_info"]["mbti"] == "INTJ"
    assert user_info.profile["other_info"]["country"] == "unknown"
    assert "Conversion-focused reviewer." in user_info.profile["other_info"][
        "user_profile"
    ]
    assert "Recently criticized vague premium pricing." in user_info.profile[
        "other_info"
    ]["user_profile"]


def test_record_run_result_rejects_unknown_agents(tmp_path):
    store = AtherumPopulationStore(tmp_path / "atherum_population.db")
    store.ensure_population(
        "workspace-main",
        [
            PersistentAgentProfile(
                stable_agent_id="workspace-001",
                numeric_agent_id=1,
                user_name="agent_1",
                name="Mira",
            )
        ],
    )

    with pytest.raises(ValueError, match="Unknown persistent agent"):
        store.record_run_result(
            population_id="workspace-main",
            run_id="run-003",
            memory_updates={"workspace-missing": "No matching agent."},
        )


def test_extract_memory_updates_from_trace_groups_textual_agent_actions(
    tmp_path,
):
    platform_db = _create_platform_trace_db(tmp_path)

    store = AtherumPopulationStore(tmp_path / "atherum_population.db")
    snapshot = store.ensure_population(
        "workspace-main",
        [
            PersistentAgentProfile(
                stable_agent_id="workspace-001",
                numeric_agent_id=7,
                user_name="agent_7",
                name="Priya",
            )
        ],
    )

    updates = extract_memory_updates_from_trace(platform_db, snapshot)

    assert updates == {
        "workspace-001": (
            "create_post: This launch looks polished but needs price proof.\n"
            "create_comment: Specs and warranty would change my view."
        )
    }


def test_record_platform_trace_result_persists_extracted_agent_memory(tmp_path):
    platform_db = _create_platform_trace_db(tmp_path)
    store = AtherumPopulationStore(tmp_path / "atherum_population.db")
    store.ensure_population(
        "workspace-main",
        [
            PersistentAgentProfile(
                stable_agent_id="workspace-001",
                numeric_agent_id=7,
                user_name="agent_7",
                name="Priya",
            )
        ],
    )

    snapshot = store.record_platform_trace_result(
        population_id="workspace-main",
        run_id="run-004",
        platform_db_path=platform_db,
        scenario="Product creative review",
    )

    assert snapshot.agents[0].memories == [
        (
            "create_post: This launch looks polished but needs price proof.\n"
            "create_comment: Specs and warranty would change my view."
        )
    ]


def test_atherum_persistence_api_is_exported_from_package_root():
    import oasis

    assert oasis.AtherumPopulationStore is AtherumPopulationStore


def _create_platform_trace_db(tmp_path):
    platform_db = tmp_path / "platform.db"
    import sqlite3

    db = sqlite3.connect(platform_db)
    db.executescript("""
    CREATE TABLE user (
        user_id INTEGER PRIMARY KEY,
        agent_id INTEGER,
        user_name TEXT,
        name TEXT,
        bio TEXT,
        created_at TEXT
    );
    CREATE TABLE trace (
        user_id INTEGER,
        created_at TEXT,
        action TEXT,
        info TEXT
    );
    """)
    db.execute(
        "INSERT INTO user (user_id, agent_id, user_name, name, bio, created_at)"
        " VALUES (1, 7, 'agent_7', 'Priya', '', '0')"
    )
    db.execute(
        "INSERT INTO trace (user_id, created_at, action, info)"
        " VALUES (1, '0', 'create_post', ?)",
        ('{"content":"This launch looks polished but needs price proof."}', ),
    )
    db.execute(
        "INSERT INTO trace (user_id, created_at, action, info)"
        " VALUES (1, '1', 'like_post', ?)",
        ('{"post_id": 1}', ),
    )
    db.execute(
        "INSERT INTO trace (user_id, created_at, action, info)"
        " VALUES (1, '2', 'create_comment', ?)",
        ('{"content":"Specs and warranty would change my view."}', ),
    )
    db.commit()
    db.close()
    return platform_db
