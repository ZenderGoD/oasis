from __future__ import annotations

from oasis.aoasis import AOasisRunConfig, estimate_run_cost


def test_estimate_run_cost_uses_known_model_rates():
    config = AOasisRunConfig(
        population_id="workspace",
        run_id="run",
        platforms=("twitter", "reddit", "instagram"),
        active_agents=10,
        duration_hours=2,
        model="moonshotai/kimi-k2.6",
    )

    estimate = estimate_run_cost(
        config,
        input_tokens_per_call=1000,
        output_tokens_per_call=250,
    )

    assert estimate.model == "moonshotai/kimi-k2.6"
    assert estimate.llm_calls == 60
    assert estimate.input_tokens == 60000
    assert estimate.output_tokens == 15000
    assert round(estimate.usd, 4) == 0.0968


def test_estimate_run_cost_marks_unknown_models_as_unpriced():
    config = AOasisRunConfig(
        population_id="workspace",
        run_id="run",
        model="local/test-model",
    )

    estimate = estimate_run_cost(config)

    assert estimate.usd is None
    assert estimate.rate_source == "unknown"
