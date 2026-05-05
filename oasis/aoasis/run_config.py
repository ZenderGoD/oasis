from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil
from typing import Any

from oasis.atherum import AOASIS_VARIANT_NAME

AOASIS_SUPPORTED_PLATFORMS = ("twitter", "instagram", "reddit")
AOASIS_EXECUTION_MODES = ("manual", "llm")


@dataclass(frozen=True)
class AOasisRunConfig:
    population_id: str
    run_id: str
    platforms: tuple[str, ...] = ("twitter", "reddit")
    active_agents: int = 24
    background_agents: int = 64
    duration_hours: int = 12
    minutes_per_round: int = 60
    execution_mode: str = "manual"
    model: str = "moonshotai/kimi-k2.6"
    public_seed: str = ""
    private_context: str = ""
    asset_context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "platforms",
                           _normalize_platforms(self.platforms))
        if self.active_agents <= 0:
            raise ValueError("active_agents must be positive")
        if self.background_agents < 0:
            raise ValueError("background_agents cannot be negative")
        if self.duration_hours <= 0:
            raise ValueError("duration_hours must be positive")
        if self.minutes_per_round <= 0:
            raise ValueError("minutes_per_round must be positive")
        object.__setattr__(self, "execution_mode",
                           self.execution_mode.strip().lower())
        if self.execution_mode not in AOASIS_EXECUTION_MODES:
            raise ValueError(
                f"execution_mode must be one of {AOASIS_EXECUTION_MODES}")
        if not self.model.strip():
            raise ValueError("model must be provided")

    def simulated_rounds(self) -> int:
        return ceil((self.duration_hours * 60) / self.minutes_per_round)

    def estimated_llm_calls(self) -> int:
        return (self.active_agents * len(self.platforms) *
                self.simulated_rounds())

    def to_worker_payload(self) -> dict[str, Any]:
        return {
            "variant": AOASIS_VARIANT_NAME,
            "populationId": self.population_id,
            "runId": self.run_id,
            "platforms": list(self.platforms),
            "activeAgents": self.active_agents,
            "backgroundAgents": self.background_agents,
            "durationHours": self.duration_hours,
            "minutesPerRound": self.minutes_per_round,
            "executionMode": self.execution_mode,
            "model": self.model,
            "publicSeed": self.public_seed,
            "privateContext": self.private_context,
            "assetContext": dict(self.asset_context),
        }


def _normalize_platforms(platforms: tuple[str, ...]) -> tuple[str, ...]:
    normalized = []
    for platform in platforms:
        value = platform.strip().lower()
        if value not in AOASIS_SUPPORTED_PLATFORMS:
            raise ValueError(f"Unsupported AOaSIS platform: {platform}")
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise ValueError("at least one platform is required")
    return tuple(normalized)
