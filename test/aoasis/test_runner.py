from __future__ import annotations

import sqlite3

from oasis.aoasis import AOasisRunConfig, execute_aoasis_run, finalize_aoasis_run
from oasis.atherum import AtherumPopulationStore, build_default_population


def test_finalize_aoasis_run_normalizes_outputs_updates_memory_and_artifacts(
    tmp_path,
):
    store = AtherumPopulationStore(tmp_path / "population.db")
    store.ensure_population(
        "workspace-sneaker-audience",
        build_default_population(
            "workspace-sneaker-audience",
            count=1,
            seed="baseline",
        ),
    )
    platform_db = _create_trace_db(tmp_path)
    config = AOasisRunConfig(
        population_id="workspace-sneaker-audience",
        run_id="run-001",
        platforms=("instagram", ),
        active_agents=1,
        duration_hours=1,
        model="google/gemini-3.1-flash-lite-preview",
    )

    result = finalize_aoasis_run(
        store=store,
        config=config,
        platform_db_paths={"instagram": platform_db},
    )

    assert result.config is config
    assert result.outputs["instagram"].totals == {
        "posts": 1,
        "comments": 0,
        "actions": 1,
    }
    assert result.evidence_summary.platforms == {
        "instagram": {
            "posts": 1,
            "actions": 1,
        }
    }
    assert "# A-Oasis Evidence Brief" in result.scribe_markdown
    assert result.cost_estimate.llm_calls == 1
    updated = store.load_population("workspace-sneaker-audience")
    assert "Need warranty proof before I would save this." in (
        updated.agents[0].memories[0]
    )


def test_execute_aoasis_run_creates_platform_dbs_outputs_and_memory(tmp_path):
    store = AtherumPopulationStore(tmp_path / "population.db")
    config = AOasisRunConfig(
        population_id="workspace-sneaker-audience",
        run_id="run-002",
        platforms=("instagram", "reddit"),
        active_agents=3,
        duration_hours=1,
        public_seed="New sneaker creative: wave motif. Would you save or buy?",
        private_context="Evaluate trust cues and visual appeal.",
        model="google/gemini-3.1-flash-lite-preview",
    )

    result = execute_aoasis_run(
        store=store,
        config=config,
        work_dir=tmp_path / "runs",
        seed="baseline",
        model=False,
    )

    assert set(result.outputs) == {"instagram", "reddit"}
    assert result.outputs["instagram"].totals["posts"] >= 1
    assert result.outputs["reddit"].totals["posts"] >= 1
    assert "New sneaker creative" in result.outputs["instagram"].posts[0].content
    assert "New sneaker creative" in result.outputs["reddit"].posts[0].content
    assert "# A-Oasis Evidence Brief" in result.scribe_markdown
    assert result.cost_estimate.llm_calls == 6
    updated = store.load_population("workspace-sneaker-audience")
    assert any(agent.memories for agent in updated.agents)


def test_execute_aoasis_run_rejects_llm_mode_without_real_model(tmp_path):
    store = AtherumPopulationStore(tmp_path / "population.db")
    config = AOasisRunConfig(
        population_id="workspace-sneaker-audience",
        run_id="run-003",
        platforms=("twitter", ),
        active_agents=2,
        duration_hours=1,
        execution_mode="llm",
    )

    import pytest

    with pytest.raises(ValueError, match="LLM execution mode requires"):
        execute_aoasis_run(
            store=store,
            config=config,
            work_dir=tmp_path / "runs",
            model=False,
        )


def _create_trace_db(tmp_path):
    db_path = tmp_path / "instagram.db"
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
        "(0, 0, 'atherum_skeptic_buyer_000', 'Ari 000', '', '0')"
    )
    db.execute(
        "INSERT INTO post VALUES (1, 0, NULL, ?, NULL, '0', 4, 0, 2, 0)",
        ("Need warranty proof before I would save this.", ),
    )
    db.execute(
        "INSERT INTO trace VALUES (0, '0', 'create_post', ?)",
        ('{"content":"Need warranty proof before I would save this.",'
         '"post_id":1}', ),
    )
    db.commit()
    db.close()
    return db_path
