from __future__ import annotations

from dataclasses import dataclass

from oasis.aoasis.platform_output import AOasisPlatformOutput

SIGNAL_KEYWORDS = (
    "price",
    "warranty",
    "material",
    "trust",
    "premium",
    "share",
    "buy",
    "save",
    "durability",
    "proof",
)


@dataclass(frozen=True)
class AOasisEvidenceSummary:
    platforms: dict[str, dict[str, int]]
    signals: list[str]
    representative_quotes: list[str]


def build_evidence_summary(
    outputs: list[AOasisPlatformOutput],
    max_quotes: int = 6,
) -> AOasisEvidenceSummary:
    platform_totals = {
        output.platform: {
            "posts": output.totals.get("posts", 0),
            "actions": output.totals.get("actions", 0),
        } for output in outputs
    }
    texts = [
        text for output in outputs
        for text in _output_texts(output)
        if text.strip()
    ]
    signals = _extract_signals(texts)
    representative_quotes = _unique_ordered(texts)[:max_quotes]
    return AOasisEvidenceSummary(
        platforms=platform_totals,
        signals=signals,
        representative_quotes=representative_quotes,
    )


def build_scribe_markdown(summary: AOasisEvidenceSummary) -> str:
    platform_lines = [
        f"- {platform}: {totals['posts']} posts/comments, "
        f"{totals['actions']} actions"
        for platform, totals in summary.platforms.items()
    ]
    signal_lines = [f"- {signal}" for signal in summary.signals]
    quote_lines = [f"- {quote}" for quote in summary.representative_quotes]
    return "\n".join([
        "# A-Oasis Evidence Brief",
        "",
        "## Platforms",
        *(platform_lines or ["- none"]),
        "",
        "## Signals",
        *(signal_lines or ["- none detected"]),
        "",
        "## Representative Quotes",
        *(quote_lines or ["- none"]),
    ])


def _output_texts(output: AOasisPlatformOutput) -> list[str]:
    texts = []
    for post in output.posts:
        if post.content:
            texts.append(post.content)
        for comment in post.comments:
            if comment.content:
                texts.append(comment.content)
    for action in output.actions:
        if action.text:
            texts.append(action.text)
    return texts


def _extract_signals(texts: list[str]) -> list[str]:
    haystack = "\n".join(texts).lower()
    return [keyword for keyword in SIGNAL_KEYWORDS if keyword in haystack]


def _unique_ordered(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
