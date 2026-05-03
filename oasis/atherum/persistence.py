from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from oasis.social_platform.config import UserInfo

DEFAULT_OTHER_INFO = {
    "gender": "unknown",
    "age": 0,
    "mbti": "unknown",
    "country": "unknown",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump_json(value: Mapping[str, Any] | None) -> str:
    return json.dumps(dict(value or {}), sort_keys=True)


def _load_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        raise ValueError("Expected stored JSON object")
    return loaded


def _clone_profile(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return json.loads(_dump_json(value))


@dataclass(frozen=True)
class PersistentAgentProfile:
    stable_agent_id: str
    numeric_agent_id: int
    user_name: str
    name: str
    description: str = ""
    profile: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PersistentAgentState:
    profile: PersistentAgentProfile
    memories: list[str] = field(default_factory=list)

    @property
    def stable_agent_id(self) -> str:
        return self.profile.stable_agent_id

    @property
    def numeric_agent_id(self) -> int:
        return self.profile.numeric_agent_id

    def to_user_info(self, recsys_type: str = "twitter") -> UserInfo:
        profile = _clone_profile(self.profile.profile)
        existing_other_info = profile.get("other_info")
        other_info = dict(DEFAULT_OTHER_INFO)
        if isinstance(existing_other_info, dict):
            other_info.update(existing_other_info)

        profile_parts = []
        existing_profile = other_info.get("user_profile")
        if existing_profile:
            profile_parts.append(str(existing_profile))
        if self.profile.description:
            profile_parts.append(self.profile.description)
        if self.memories:
            memory_text = "\n".join(f"- {memory}" for memory in self.memories)
            profile_parts.append(f"Persistent memory:\n{memory_text}")

        other_info["user_profile"] = "\n\n".join(profile_parts).strip()
        profile["other_info"] = other_info

        return UserInfo(
            user_name=self.profile.user_name,
            name=self.profile.name,
            description=self.profile.description,
            profile=profile,
            recsys_type=recsys_type,
        )


@dataclass(frozen=True)
class PersistentPopulationSnapshot:
    population_id: str
    metadata: dict[str, Any]
    agents: list[PersistentAgentState]


class AtherumPopulationStore:
    """SQLite store for stable Atherum-facing OASIS populations."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if self.db_path.parent != Path("."):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._ensure_schema()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "AtherumPopulationStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def ensure_population(
        self,
        population_id: str,
        agents: list[PersistentAgentProfile],
        metadata: Mapping[str, Any] | None = None,
    ) -> PersistentPopulationSnapshot:
        self._validate_agents(agents)
        now = _utc_now()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO atherum_populations (
                    population_id,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(population_id) DO UPDATE SET
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (population_id, _dump_json(metadata), now, now),
            )
            for agent in agents:
                self._conn.execute(
                    """
                    INSERT INTO atherum_agents (
                        population_id,
                        stable_agent_id,
                        numeric_agent_id,
                        user_name,
                        name,
                        description,
                        profile_json,
                        metadata_json,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(population_id, stable_agent_id)
                    DO UPDATE SET
                        numeric_agent_id = excluded.numeric_agent_id,
                        user_name = excluded.user_name,
                        name = excluded.name,
                        description = excluded.description,
                        profile_json = excluded.profile_json,
                        metadata_json = excluded.metadata_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        population_id,
                        agent.stable_agent_id,
                        agent.numeric_agent_id,
                        agent.user_name,
                        agent.name,
                        agent.description,
                        _dump_json(agent.profile),
                        _dump_json(agent.metadata),
                        now,
                        now,
                    ),
                )
        return self.load_population(population_id)

    def load_population(self, population_id: str) -> PersistentPopulationSnapshot:
        population = self._conn.execute(
            """
            SELECT population_id, metadata_json
            FROM atherum_populations
            WHERE population_id = ?
            """,
            (population_id, ),
        ).fetchone()
        if population is None:
            raise KeyError(f"Unknown population: {population_id}")

        agents = []
        rows = self._conn.execute(
            """
            SELECT *
            FROM atherum_agents
            WHERE population_id = ?
            ORDER BY numeric_agent_id ASC
            """,
            (population_id, ),
        ).fetchall()
        for row in rows:
            profile = PersistentAgentProfile(
                stable_agent_id=row["stable_agent_id"],
                numeric_agent_id=row["numeric_agent_id"],
                user_name=row["user_name"],
                name=row["name"],
                description=row["description"] or "",
                profile=_load_json(row["profile_json"]),
                metadata=_load_json(row["metadata_json"]),
            )
            memories = [
                memory_row["content"] for memory_row in self._conn.execute(
                    """
                    SELECT content
                    FROM atherum_agent_memories
                    WHERE population_id = ?
                      AND stable_agent_id = ?
                    ORDER BY id ASC
                    """,
                    (population_id, row["stable_agent_id"]),
                ).fetchall()
            ]
            agents.append(PersistentAgentState(profile=profile,
                                               memories=memories))

        return PersistentPopulationSnapshot(
            population_id=population["population_id"],
            metadata=_load_json(population["metadata_json"]),
            agents=agents,
        )

    def record_run_result(
        self,
        population_id: str,
        run_id: str,
        memory_updates: Mapping[str, str] | None = None,
        scenario: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> PersistentPopulationSnapshot:
        memory_updates = dict(memory_updates or {})
        known_agents = self._load_agent_ids(population_id)
        unknown_agents = sorted(set(memory_updates) - known_agents)
        if unknown_agents:
            raise ValueError(
                "Unknown persistent agent(s) for population "
                f"{population_id}: {', '.join(unknown_agents)}")

        now = _utc_now()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO atherum_runs (
                    run_id,
                    population_id,
                    scenario,
                    metadata_json,
                    started_at,
                    completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    scenario = excluded.scenario,
                    metadata_json = excluded.metadata_json,
                    completed_at = excluded.completed_at
                """,
                (run_id, population_id, scenario, _dump_json(metadata), now,
                 now),
            )
            for stable_agent_id, content in memory_updates.items():
                normalized = content.strip()
                if not normalized:
                    continue
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO atherum_agent_memories (
                        population_id,
                        stable_agent_id,
                        source_run_id,
                        content,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (population_id, stable_agent_id, run_id, normalized, now),
                )
        return self.load_population(population_id)

    def record_platform_trace_result(
        self,
        population_id: str,
        run_id: str,
        platform_db_path: str | Path,
        scenario: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> PersistentPopulationSnapshot:
        population = self.load_population(population_id)
        memory_updates = extract_memory_updates_from_trace(
            platform_db_path, population)
        return self.record_run_result(
            population_id=population_id,
            run_id=run_id,
            memory_updates=memory_updates,
            scenario=scenario,
            metadata=metadata,
        )

    def _load_agent_ids(self, population_id: str) -> set[str]:
        self._require_population(population_id)
        rows = self._conn.execute(
            """
            SELECT stable_agent_id
            FROM atherum_agents
            WHERE population_id = ?
            """,
            (population_id, ),
        ).fetchall()
        return {row["stable_agent_id"] for row in rows}

    def _require_population(self, population_id: str) -> None:
        row = self._conn.execute(
            """
            SELECT population_id
            FROM atherum_populations
            WHERE population_id = ?
            """,
            (population_id, ),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown population: {population_id}")

    @staticmethod
    def _validate_agents(agents: list[PersistentAgentProfile]) -> None:
        stable_ids = [agent.stable_agent_id for agent in agents]
        numeric_ids = [agent.numeric_agent_id for agent in agents]
        if len(stable_ids) != len(set(stable_ids)):
            raise ValueError("Persistent agent stable IDs must be unique")
        if len(numeric_ids) != len(set(numeric_ids)):
            raise ValueError("Persistent agent numeric IDs must be unique")

    def _ensure_schema(self) -> None:
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS atherum_populations (
            population_id TEXT PRIMARY KEY,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS atherum_agents (
            population_id TEXT NOT NULL,
            stable_agent_id TEXT NOT NULL,
            numeric_agent_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            profile_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (population_id, stable_agent_id),
            UNIQUE (population_id, numeric_agent_id),
            FOREIGN KEY (population_id)
                REFERENCES atherum_populations(population_id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS atherum_runs (
            run_id TEXT PRIMARY KEY,
            population_id TEXT NOT NULL,
            scenario TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            FOREIGN KEY (population_id)
                REFERENCES atherum_populations(population_id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS atherum_agent_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            population_id TEXT NOT NULL,
            stable_agent_id TEXT NOT NULL,
            source_run_id TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (
                population_id,
                stable_agent_id,
                source_run_id,
                content
            ),
            FOREIGN KEY (population_id, stable_agent_id)
                REFERENCES atherum_agents(population_id, stable_agent_id)
                ON DELETE CASCADE,
            FOREIGN KEY (source_run_id)
                REFERENCES atherum_runs(run_id)
                ON DELETE CASCADE
        );
        """)


def extract_memory_updates_from_trace(
    platform_db_path: str | Path,
    population: PersistentPopulationSnapshot,
    max_events_per_agent: int = 8,
    max_chars_per_event: int = 300,
) -> dict[str, str]:
    """Build per-agent memory snippets from an OASIS platform trace DB."""
    numeric_to_stable = {
        agent.numeric_agent_id: agent.stable_agent_id
        for agent in population.agents
    }
    updates: dict[str, list[str]] = {}
    db = sqlite3.connect(platform_db_path)
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute("""
            SELECT user.agent_id, trace.action, trace.info
            FROM trace
            JOIN user ON trace.user_id = user.user_id
            ORDER BY trace.rowid ASC
        """).fetchall()
    finally:
        db.close()

    for row in rows:
        stable_agent_id = numeric_to_stable.get(row["agent_id"])
        if stable_agent_id is None:
            continue
        content = _text_content_from_trace(row["info"])
        if content is None:
            continue
        event = f"{row['action']}: {_truncate(content, max_chars_per_event)}"
        agent_events = updates.setdefault(stable_agent_id, [])
        if len(agent_events) < max_events_per_agent:
            agent_events.append(event)

    return {
        stable_agent_id: "\n".join(events)
        for stable_agent_id, events in updates.items()
        if events
    }


def _text_content_from_trace(info_json: str) -> str | None:
    try:
        info = json.loads(info_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(info, dict):
        return None
    content = info.get("content") or info.get("quote_content")
    if not isinstance(content, str):
        return None
    normalized = " ".join(content.split())
    return normalized or None


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars - 1].rstrip() + "…"
