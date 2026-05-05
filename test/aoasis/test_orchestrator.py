from __future__ import annotations

from oasis.aoasis import AOasisRunConfig, prepare_aoasis_run
from oasis.atherum import AtherumPopulationStore
from oasis.social_platform.typing import ActionType


def test_prepare_aoasis_run_creates_population_and_graph(tmp_path):
    store = AtherumPopulationStore(tmp_path / "population.db")
    config = AOasisRunConfig(
        population_id="workspace-sneaker-audience",
        run_id="run-001",
        active_agents=4,
        platforms=("reddit", ),
    )

    prepared = prepare_aoasis_run(
        store=store,
        config=config,
        seed="baseline",
        model=False,
    )

    assert prepared.config is config
    assert prepared.population.population_id == "workspace-sneaker-audience"
    assert len(prepared.population.agents) == 4
    assert prepared.graph.get_num_nodes() == 4
    assert prepared.population.metadata["variant"] == "AOaSIS"
    assert prepared.population.metadata["config"]["runId"] == "run-001"
    tool_names = {
        tool.func.__name__
        for tool in prepared.graph.get_agent(0).action_tools
    }
    assert ActionType.CREATE_COMMENT.value in tool_names
    assert ActionType.DISLIKE_POST.value in tool_names


def test_prepare_aoasis_run_filters_actions_by_platform(tmp_path):
    store = AtherumPopulationStore(tmp_path / "population.db")
    config = AOasisRunConfig(
        population_id="workspace-sneaker-audience",
        run_id="run-001",
        active_agents=2,
        platforms=("twitter", ),
    )

    prepared = prepare_aoasis_run(
        store=store,
        config=config,
        seed="baseline",
        model=False,
    )

    tool_names = {
        tool.func.__name__
        for tool in prepared.graph.get_agent(0).action_tools
    }
    assert ActionType.QUOTE_POST.value in tool_names
    assert ActionType.CREATE_COMMENT.value not in tool_names


def test_prepare_aoasis_run_reuses_existing_population_with_memory(tmp_path):
    store = AtherumPopulationStore(tmp_path / "population.db")
    config = AOasisRunConfig(
        population_id="workspace-sneaker-audience",
        run_id="run-002",
        active_agents=4,
        platforms=("reddit", ),
    )
    first = prepare_aoasis_run(
        store=store,
        config=config,
        seed="baseline",
        model=False,
    )
    store.record_run_result(
        population_id=config.population_id,
        run_id="prior-run",
        memory_updates={
            first.population.agents[0].stable_agent_id: (
                "Previously wanted clearer material proof."
            )
        },
    )

    prepared = prepare_aoasis_run(
        store=store,
        config=config,
        seed="different-seed-should-not-recreate",
        model=False,
    )

    assert len(prepared.population.agents) == 4
    user_profile = prepared.graph.get_agent(0).user_info.profile[
        "other_info"
    ]["user_profile"]
    assert "Previously wanted clearer material proof." in user_profile
