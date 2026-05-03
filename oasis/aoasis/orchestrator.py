from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from oasis.aoasis.action_policy import platform_action_policy
from oasis.aoasis.run_config import AOasisRunConfig
from oasis.atherum import (
    AOASIS_VARIANT_NAME,
    AtherumPopulationStore,
    PersistentPopulationSnapshot,
    build_default_population,
    build_graph_from_population,
)
from oasis.social_agent.agent_graph import AgentGraph


@dataclass(frozen=True)
class AOasisPreparedRun:
    config: AOasisRunConfig
    population: PersistentPopulationSnapshot
    graph: AgentGraph


def prepare_aoasis_run(
    store: AtherumPopulationStore,
    config: AOasisRunConfig,
    seed: str = "default",
    model: Any = None,
) -> AOasisPreparedRun:
    try:
        population = store.load_population(config.population_id)
    except KeyError:
        profiles = build_default_population(
            population_id=config.population_id,
            count=config.active_agents,
            seed=seed,
        )
        population = store.ensure_population(
            population_id=config.population_id,
            agents=profiles,
            metadata={
                "variant": AOASIS_VARIANT_NAME,
                "config": config.to_worker_payload(),
            },
        )

    graph = build_graph_from_population(
        population.agents,
        recsys_type=_agent_recsys_type(config.platforms[0]),
        model=model,
        available_actions=platform_action_policy(config.platforms[0]),
    )
    return AOasisPreparedRun(config=config, population=population, graph=graph)


def _agent_recsys_type(platform: str) -> str:
    if platform == "reddit":
        return "reddit"
    return "twitter"
