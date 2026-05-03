from __future__ import annotations

from dataclasses import dataclass

from oasis.aoasis.run_config import AOasisRunConfig


MODEL_TOKEN_RATES_USD_PER_MILLION = {
    "moonshotai/kimi-k2.6": {
        "input": 0.74,
        "output": 3.49,
        "source": "configured",
    },
    "google/gemini-3.1-flash-lite-preview": {
        "input": 0.10,
        "output": 0.40,
        "source": "configured",
    },
}


@dataclass(frozen=True)
class AOasisCostEstimate:
    model: str
    llm_calls: int
    input_tokens: int
    output_tokens: int
    usd: float | None
    rate_source: str


def estimate_run_cost(
    config: AOasisRunConfig,
    input_tokens_per_call: int = 1200,
    output_tokens_per_call: int = 300,
) -> AOasisCostEstimate:
    llm_calls = config.estimated_llm_calls()
    input_tokens = llm_calls * input_tokens_per_call
    output_tokens = llm_calls * output_tokens_per_call
    rates = MODEL_TOKEN_RATES_USD_PER_MILLION.get(config.model)
    if rates is None:
        return AOasisCostEstimate(
            model=config.model,
            llm_calls=llm_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            usd=None,
            rate_source="unknown",
        )

    usd = ((input_tokens / 1_000_000) * rates["input"] +
           (output_tokens / 1_000_000) * rates["output"])
    return AOasisCostEstimate(
        model=config.model,
        llm_calls=llm_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        usd=usd,
        rate_source=str(rates["source"]),
    )
