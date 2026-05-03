from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from oasis.aoasis.artifacts import (
    AOasisEvidenceSummary,
    build_evidence_summary,
    build_scribe_markdown,
)
from oasis.aoasis.action_policy import platform_action_policy
from oasis.aoasis.cost import AOasisCostEstimate, estimate_run_cost
from oasis.aoasis.platform_output import (AOasisPlatformOutput,
                                          normalize_platform_db)
from oasis.aoasis.run_config import AOasisRunConfig
from oasis.atherum import AtherumPopulationStore, PersistentPopulationSnapshot
from oasis.environment.env import OasisEnv
from oasis.environment.env_action import ManualAction
from oasis.environment.env_action import LLMAction
from oasis.social_platform.typing import ActionType, DefaultPlatformType


@dataclass(frozen=True)
class AOasisRunResult:
    config: AOasisRunConfig
    outputs: dict[str, AOasisPlatformOutput]
    population: PersistentPopulationSnapshot
    evidence_summary: AOasisEvidenceSummary
    scribe_markdown: str
    cost_estimate: AOasisCostEstimate


def finalize_aoasis_run(
    store: AtherumPopulationStore,
    config: AOasisRunConfig,
    platform_db_paths: dict[str, str | Path],
) -> AOasisRunResult:
    outputs: dict[str, AOasisPlatformOutput] = {}
    population = store.load_population(config.population_id)
    for platform, db_path in platform_db_paths.items():
        normalized_platform = platform.strip().lower()
        outputs[normalized_platform] = normalize_platform_db(
            normalized_platform, db_path, population=population)
        population = store.record_platform_trace_result(
            population_id=config.population_id,
            run_id=f"{config.run_id}:{normalized_platform}",
            platform_db_path=db_path,
            scenario=config.private_context or config.public_seed,
            metadata={
                "variant": "A-Oasis",
                "platform": normalized_platform,
                "config": config.to_worker_payload(),
            },
        )

    evidence_summary = build_evidence_summary(list(outputs.values()))
    return AOasisRunResult(
        config=config,
        outputs=outputs,
        population=population,
        evidence_summary=evidence_summary,
        scribe_markdown=build_scribe_markdown(evidence_summary),
        cost_estimate=estimate_run_cost(config),
    )


def execute_aoasis_run(
    store: AtherumPopulationStore,
    config: AOasisRunConfig,
    work_dir: str | Path,
    seed: str = "default",
    model: object = None,
) -> AOasisRunResult:
    if config.execution_mode == "llm" and model is False:
        raise ValueError("LLM execution mode requires a real model backend")
    work_path = Path(work_dir)
    work_path.mkdir(parents=True, exist_ok=True)
    platform_db_paths = asyncio.run(
        _execute_aoasis_run_async(store, config, work_path, seed, model))
    return finalize_aoasis_run(
        store=store,
        config=config,
        platform_db_paths=platform_db_paths,
    )


async def _execute_aoasis_run_async(
    store: AtherumPopulationStore,
    config: AOasisRunConfig,
    work_dir: Path,
    seed: str,
    model: object,
) -> dict[str, Path]:
    from oasis.aoasis.orchestrator import prepare_aoasis_run

    platform_db_paths: dict[str, Path] = {}
    for platform in config.platforms:
        prepared = prepare_aoasis_run(
            store=store,
            config=_config_for_platform(config, platform),
            seed=seed,
            model=model,
        )
        db_path = work_dir / f"{config.run_id}-{platform}.db"
        if db_path.exists():
            db_path.unlink()
        env = OasisEnv(
            agent_graph=prepared.graph,
            platform=_platform_type_for(platform),
            database_path=str(db_path),
            semaphore=max(1, min(config.active_agents, 16)),
        )
        await env.reset()
        try:
            agents = [agent for _, agent in prepared.graph.get_agents()]
            if not agents:
                raise ValueError("A-Oasis run requires at least one agent")
            seed_agent = agents[0]
            seed_result = await seed_agent.perform_action_by_data(
                ActionType.CREATE_POST,
                content=_seed_content(config),
            )
            post_id = int(seed_result.get("post_id", 1))
            if config.execution_mode == "llm":
                await _run_llm_steps(env, agents[1:], config)
            else:
                reaction_actions = _reaction_actions(platform, post_id, config)
                if reaction_actions:
                    await env.step({
                        agent: action
                        for agent, action in zip(agents[1:], reaction_actions)
                    })
        finally:
            await env.close()
        platform_db_paths[platform] = db_path
    return platform_db_paths


def _platform_type_for(platform: str) -> DefaultPlatformType:
    if platform == "reddit":
        return DefaultPlatformType.REDDIT
    return DefaultPlatformType.TWITTER


def _config_for_platform(
    config: AOasisRunConfig,
    platform: str,
) -> AOasisRunConfig:
    return AOasisRunConfig(
        population_id=config.population_id,
        run_id=config.run_id,
        platforms=(platform, ),
        active_agents=config.active_agents,
        background_agents=config.background_agents,
        duration_hours=config.duration_hours,
        minutes_per_round=config.minutes_per_round,
        execution_mode=config.execution_mode,
        model=config.model,
        public_seed=config.public_seed,
        private_context=config.private_context,
        asset_context=dict(config.asset_context),
    )


def _seed_content(config: AOasisRunConfig) -> str:
    if config.public_seed.strip():
        return config.public_seed.strip()
    asset = config.asset_context
    asset_label = asset.get("fileName") or asset.get("storageId")
    if asset_label:
        return (
            f"New product creative under review: {asset_label}. "
            "What stands out, what feels credible, and what would people "
            "criticize before sharing or buying?")
    return (
        "New product creative under review. What stands out, what feels "
        "credible, and what would people criticize before sharing or buying?")


def _reaction_actions(
    platform: str,
    post_id: int,
    config: AOasisRunConfig,
) -> list[ManualAction]:
    if config.active_agents <= 1:
        return []
    if platform == "instagram":
        return [
            ManualAction(
                ActionType.LIKE_POST,
                {"post_id": post_id},
            ),
            ManualAction(
                ActionType.REPOST,
                {"post_id": post_id},
            ),
        ][:config.active_agents - 1]
    if platform == "twitter":
        return [
            ManualAction(
                ActionType.QUOTE_POST,
                {
                    "post_id": post_id,
                    "quote_content": (
                        "The visual hook matters, but I still need trust "
                        "signals before I would buy.")
                },
            ),
            ManualAction(
                ActionType.LIKE_POST,
                {"post_id": post_id},
            ),
        ][:config.active_agents - 1]
    return [
        ManualAction(
            ActionType.CREATE_COMMENT,
            {
                "post_id": post_id,
                "content": (
                    "I need clearer price, material proof, and warranty "
                    "signals before I would share or buy.")
            },
        ),
        ManualAction(
            ActionType.LIKE_POST,
            {"post_id": post_id},
        ),
    ][:config.active_agents - 1]


async def _run_llm_steps(
    env: OasisEnv,
    agents: list[object],
    config: AOasisRunConfig,
) -> None:
    if not agents:
        return
    allowed_actions = platform_action_policy(config.platforms[0])
    if not allowed_actions:
        return
    for _ in range(config.simulated_rounds()):
        await env.step({agent: LLMAction() for agent in agents})
