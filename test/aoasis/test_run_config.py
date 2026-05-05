from __future__ import annotations

import pytest

from oasis.aoasis import AOasisRunConfig


def test_run_config_normalizes_platforms_and_builds_worker_payload():
    config = AOasisRunConfig(
        population_id="workspace-sneaker-audience",
        run_id="run-001",
        platforms=("Twitter", "instagram", "reddit", "twitter"),
        active_agents=24,
        background_agents=64,
        duration_hours=12,
        execution_mode="manual",
        model="google/gemini-3.1-flash-lite-preview",
        public_seed="New product creative under review.",
        private_context="Use the uploaded creative as private context.",
        asset_context={
            "fileName": "shoe.jpg",
            "mimeType": "image/jpeg",
            "storageId": "kg123",
        },
    )

    assert config.platforms == ("twitter", "instagram", "reddit")
    assert config.estimated_llm_calls() == 864
    assert config.to_worker_payload() == {
        "variant": "AOaSIS",
        "populationId": "workspace-sneaker-audience",
        "runId": "run-001",
        "platforms": ["twitter", "instagram", "reddit"],
        "activeAgents": 24,
        "backgroundAgents": 64,
        "durationHours": 12,
        "minutesPerRound": 60,
        "executionMode": "manual",
        "model": "google/gemini-3.1-flash-lite-preview",
        "publicSeed": "New product creative under review.",
        "privateContext": "Use the uploaded creative as private context.",
        "assetContext": {
            "fileName": "shoe.jpg",
            "mimeType": "image/jpeg",
            "storageId": "kg123",
        },
    }


def test_run_config_rejects_invalid_platforms_and_non_positive_counts():
    with pytest.raises(ValueError, match="Unsupported AOaSIS platform"):
        AOasisRunConfig(
            population_id="workspace",
            run_id="run",
            platforms=("linkedin", ),
        )

    with pytest.raises(ValueError, match="active_agents must be positive"):
        AOasisRunConfig(
            population_id="workspace",
            run_id="run",
            active_agents=0,
        )

    with pytest.raises(ValueError, match="duration_hours must be positive"):
        AOasisRunConfig(
            population_id="workspace",
            run_id="run",
            duration_hours=0,
        )

    with pytest.raises(ValueError, match="execution_mode must be"):
        AOasisRunConfig(
            population_id="workspace",
            run_id="run",
            execution_mode="random",
        )
