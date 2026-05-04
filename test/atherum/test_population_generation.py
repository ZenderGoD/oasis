from __future__ import annotations

from oasis.atherum import (
    ATHERUM_DEFAULT_ARCHETYPES,
    AtherumPopulationStore,
    build_default_population,
    build_graph_from_population,
)
from oasis.social_platform.channel import Channel


def test_default_population_is_deterministic_and_unique():
    first = build_default_population(
        population_id="workspace-sneaker-audience",
        count=6,
        seed="baseline",
    )
    second = build_default_population(
        population_id="workspace-sneaker-audience",
        count=6,
        seed="baseline",
    )

    assert first == second
    assert len({agent.stable_agent_id for agent in first}) == 6
    assert len({agent.numeric_agent_id for agent in first}) == 6
    assert first[0].stable_agent_id == (
        "workspace-sneaker-audience:baseline:slot-000"
    )


def test_population_profiles_include_human_like_preference_dimensions():
    profiles = build_default_population(
        population_id="workspace-sneaker-audience",
        count=1,
        seed="baseline",
    )

    agent = profiles[0]
    other_info = agent.profile["other_info"]
    atherum = agent.metadata["atherum"]

    assert other_info["gender"] == "unknown"
    assert other_info["country"] == "unknown"
    assert "Likes:" in other_info["user_profile"]
    assert "Dislikes:" in other_info["user_profile"]
    assert "Trust needs:" in other_info["user_profile"]
    assert "Decision style:" in other_info["user_profile"]
    assert atherum["archetype"] in {
        archetype.key for archetype in ATHERUM_DEFAULT_ARCHETYPES
    }
    assert len(atherum["interests"]) >= 2
    assert len(atherum["dislikes"]) >= 2
    assert len(atherum["trust_needs"]) >= 2
    assert atherum["action_bias"]["comment"] > 0


def test_population_profiles_include_society_and_platform_dimensions():
    profiles = build_default_population(
        population_id="workspace-sneaker-audience",
        count=8,
        seed="baseline",
    )

    first = profiles[0]
    first_profile = first.profile["other_info"]["user_profile"]
    first_atherum = first.metadata["atherum"]

    assert "Life role:" in first_profile
    assert "Social bubble:" in first_profile
    assert "Worldview:" in first_profile
    assert "Platform habits:" in first_profile
    assert first_atherum["life_role"]
    assert first_atherum["social_bubble"]
    assert first_atherum["worldview"]
    assert len(first_atherum["platform_habits"]) >= 2
    assert len({profile.metadata["atherum"]["social_bubble"]
                for profile in profiles}) >= 3


def test_population_cycles_archetypes_when_count_exceeds_default_set():
    profiles = build_default_population(
        population_id="workspace-sneaker-audience",
        count=len(ATHERUM_DEFAULT_ARCHETYPES) + 2,
        seed="baseline",
    )

    archetypes = [profile.metadata["atherum"]["archetype"]
                  for profile in profiles]

    assert archetypes[0] == archetypes[len(ATHERUM_DEFAULT_ARCHETYPES)]
    assert archetypes[1] == archetypes[len(ATHERUM_DEFAULT_ARCHETYPES) + 1]


def test_build_graph_from_population_uses_persistent_agent_ids():
    profiles = build_default_population(
        population_id="workspace-sneaker-audience",
        count=3,
        seed="baseline",
    )
    channel = Channel()

    graph = build_graph_from_population(
        profiles,
        channel=channel,
        recsys_type="reddit",
        model=False,
    )

    assert graph.get_num_nodes() == 3
    agent = graph.get_agent(profiles[0].numeric_agent_id)
    assert agent.social_agent_id == profiles[0].numeric_agent_id
    assert agent.user_info.user_name == profiles[0].user_name
    assert agent.channel is channel
    assert agent.user_info.recsys_type == "reddit"
    assert "Likes:" in agent.user_info.profile["other_info"]["user_profile"]


def test_build_graph_from_population_includes_persistent_memories(tmp_path):
    store = AtherumPopulationStore(tmp_path / "population.db")
    store.ensure_population(
        "workspace-sneaker-audience",
        build_default_population(
            population_id="workspace-sneaker-audience",
            count=1,
            seed="baseline",
        ),
    )
    snapshot = store.record_run_result(
        population_id="workspace-sneaker-audience",
        run_id="run-001",
        memory_updates={
            "workspace-sneaker-audience:baseline:slot-000": (
                "Previously objected to missing warranty proof."
            )
        },
    )

    graph = build_graph_from_population(
        snapshot.agents,
        channel=Channel(),
        recsys_type="reddit",
        model=False,
    )

    user_profile = graph.get_agent(0).user_info.profile["other_info"][
        "user_profile"
    ]
    assert "Persistent memory:" in user_profile
    assert "Previously objected to missing warranty proof." in user_profile
