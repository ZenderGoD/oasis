from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from camel.models.stub_model import StubModel

from oasis.atherum.persistence import (PersistentAgentProfile,
                                       PersistentAgentState)
from oasis.social_agent.agent import SocialAgent
from oasis.social_agent.agent_graph import AgentGraph
from oasis.social_platform.channel import Channel
from oasis.social_platform.typing import ActionType


@dataclass(frozen=True)
class AtherumAgentArchetype:
    key: str
    display_role: str
    life_role: str
    social_bubble: str
    temperament: str
    decision_style: str
    worldview: str
    interests: tuple[str, ...]
    dislikes: tuple[str, ...]
    trust_needs: tuple[str, ...]
    platform_habits: tuple[str, ...]
    action_bias: dict[str, float]
    mbti: str


ATHERUM_DEFAULT_ARCHETYPES = (
    AtherumAgentArchetype(
        key="skeptical_buyer",
        display_role="Skeptical Buyer",
        life_role="household budget owner comparing everyday purchases",
        social_bubble="value-seeking buyers",
        temperament="cautious, detail-oriented, risk-sensitive",
        decision_style="compares alternatives before sharing or buying",
        worldview="good products should prove utility before asking for trust",
        interests=("durability", "clear pricing", "warranty signals"),
        dislikes=("vague claims", "over-polished renders",
                  "hidden tradeoffs"),
        trust_needs=("material proof", "price anchor", "return policy"),
        platform_habits=(
            "reads comments before clicking through",
            "saves only when specs and price are clear",
            "pushes back on hype-first launch claims",
        ),
        action_bias={
            "comment": 0.48,
            "like": 0.08,
            "share": 0.04,
            "quote": 0.18,
            "refresh": 0.22,
        },
        mbti="ISTJ",
    ),
    AtherumAgentArchetype(
        key="visual_amplifier",
        display_role="Visual Amplifier",
        life_role="trend-forward creator curating visual finds",
        social_bubble="early visual adopters",
        temperament="novelty-seeking, aesthetic, socially responsive",
        decision_style="shares quickly when the visual hook feels fresh",
        worldview="distinctive creative earns attention before full proof arrives",
        interests=("visual polish", "limited drops", "feed appeal"),
        dislikes=("generic category templates", "flat lighting",
                  "low-status presentation"),
        trust_needs=("distinctive style", "brand specificity",
                     "social momentum"),
        platform_habits=(
            "reposts strong visuals early",
            "quotes launches with taste-led framing",
            "uses comments to test whether others feel the same pull",
        ),
        action_bias={
            "comment": 0.34,
            "like": 0.22,
            "share": 0.24,
            "quote": 0.12,
            "refresh": 0.08,
        },
        mbti="ENFP",
    ),
    AtherumAgentArchetype(
        key="brand_strategist",
        display_role="Brand Strategist",
        life_role="brand operator reading category and positioning signals",
        social_bubble="brand-literate strategists",
        temperament="analytical, positioning-aware, brand-loyal",
        decision_style="reads visual hierarchy and market fit first",
        worldview="creative should encode a coherent market promise",
        interests=("category clarity", "brand grammar", "trust cues"),
        dislikes=("positioning drift", "derivative motifs",
                  "unclear audience fit"),
        trust_needs=("coherent story", "brand mark", "audience signal"),
        platform_habits=(
            "writes critique threads",
            "quotes posts to name positioning risks",
            "tracks how first replies frame the brand",
        ),
        action_bias={
            "comment": 0.42,
            "like": 0.1,
            "share": 0.08,
            "quote": 0.24,
            "refresh": 0.16,
        },
        mbti="INFJ",
    ),
    AtherumAgentArchetype(
        key="practical_merchandiser",
        display_role="Retail Merchandiser",
        life_role="retail operator judging sell-through and shelf readiness",
        social_bubble="commercial pragmatists",
        temperament="pragmatic, price-aware, conversion-focused",
        decision_style="looks for shelf-readiness and purchase friction",
        worldview="attention only matters when it turns into qualified demand",
        interests=("conversion context", "use case clarity", "margin fit"),
        dislikes=("missing specs", "unclear price band",
                  "assets without scale"),
        trust_needs=("product context", "size/material cues",
                     "buyer proof"),
        platform_habits=(
            "comments with conversion objections",
            "shares only when the use case is obvious",
            "compares creative polish against likely margin and returns",
        ),
        action_bias={
            "comment": 0.44,
            "like": 0.1,
            "share": 0.08,
            "quote": 0.16,
            "refresh": 0.22,
        },
        mbti="ESTJ",
    ),
)


def build_default_population(
    population_id: str,
    count: int,
    seed: str = "default",
) -> list[PersistentAgentProfile]:
    if count < 0:
        raise ValueError("count must be non-negative")

    profiles = []
    for index in range(count):
        archetype = ATHERUM_DEFAULT_ARCHETYPES[
            index % len(ATHERUM_DEFAULT_ARCHETYPES)]
        numeric_agent_id = index
        stable_agent_id = f"{population_id}:{seed}:slot-{index:03d}"
        profile_digest = _short_digest(population_id, seed, index,
                                       archetype.key)
        user_name = f"atherum_{archetype.key}_{index:03d}"
        name = f"{_human_name(index, seed)} {index:03d}"
        description = (
            f"{archetype.display_role}: {archetype.temperament}. "
            f"Decision style: {archetype.decision_style}.")
        user_profile = _profile_text(archetype)
        profiles.append(
            PersistentAgentProfile(
                stable_agent_id=stable_agent_id,
                numeric_agent_id=numeric_agent_id,
                user_name=user_name,
                name=name,
                description=description,
                profile={
                    "other_info": {
                        "user_profile": user_profile,
                        "gender": "unknown",
                        "age": _deterministic_age(profile_digest),
                        "mbti": archetype.mbti,
                        "country": "unknown",
                    }
                },
                metadata={
                    "atherum": {
                        "archetype": archetype.key,
                        "role": archetype.display_role,
                        "life_role": archetype.life_role,
                        "social_bubble": archetype.social_bubble,
                        "temperament": archetype.temperament,
                        "decision_style": archetype.decision_style,
                        "worldview": archetype.worldview,
                        "interests": list(archetype.interests),
                        "dislikes": list(archetype.dislikes),
                        "trust_needs": list(archetype.trust_needs),
                        "platform_habits": list(archetype.platform_habits),
                        "action_bias": dict(archetype.action_bias),
                    }
                },
            ))
    return profiles


def build_graph_from_population(
    profiles: list[PersistentAgentProfile | PersistentAgentState],
    channel: Channel | None = None,
    recsys_type: str = "twitter",
    model: Any = None,
    available_actions: list[ActionType] | None = None,
) -> AgentGraph:
    graph = AgentGraph()
    shared_channel = channel or Channel()
    resolved_model = _resolve_graph_model(model)
    for profile in profiles:
        state = _state_for_profile(profile)
        agent = SocialAgent(
            agent_id=state.numeric_agent_id,
            user_info=state.to_user_info(recsys_type=recsys_type),
            channel=shared_channel,
            model=resolved_model,
            available_actions=available_actions,
        )
        graph.add_agent(agent)
    return graph


def _profile_text(archetype: AtherumAgentArchetype) -> str:
    return "\n".join([
        f"Role: {archetype.display_role}",
        f"Life role: {archetype.life_role}",
        f"Social bubble: {archetype.social_bubble}",
        f"Temperament: {archetype.temperament}",
        f"Decision style: {archetype.decision_style}",
        f"Worldview: {archetype.worldview}",
        f"Likes: {', '.join(archetype.interests)}",
        f"Dislikes: {', '.join(archetype.dislikes)}",
        f"Trust needs: {', '.join(archetype.trust_needs)}",
        f"Platform habits: {', '.join(archetype.platform_habits)}",
        "Behavior rule: react like a public social media user, not a test "
        "operator.",
    ])


def _short_digest(*parts: object) -> str:
    source = ":".join(str(part) for part in parts)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]


def _deterministic_age(digest: str) -> int:
    return 22 + int(digest[:4], 16) % 27


def _human_name(index: int, seed: str) -> str:
    names = ("Ari", "Mei", "Dev", "Priya", "Iris", "Jonah", "Nora",
             "Theo", "Zara", "Owen", "Lina", "Sofia")
    digest = _short_digest(seed, index)
    return names[int(digest[:4], 16) % len(names)]


def _resolve_graph_model(model: Any) -> Any:
    if model is False:
        return StubModel("stub")
    return model


def _state_for_profile(
    profile: PersistentAgentProfile | PersistentAgentState,
) -> PersistentAgentState:
    if isinstance(profile, PersistentAgentState):
        return profile
    return PersistentAgentState(profile=profile)
