from __future__ import annotations

from oasis.aoasis import (
    AOasisPlatformOutput,
    AOasisSocialAction,
    AOasisSocialPost,
    build_evidence_summary,
    build_scribe_markdown,
)


def test_build_evidence_summary_extracts_platform_totals_and_common_signals():
    outputs = [
        AOasisPlatformOutput(
            platform="reddit",
            posts=[
                AOasisSocialPost(
                    post_id=1,
                    surface="reddit_thread",
                    author_name="Skeptic",
                    author_handle="u/skeptic",
                    content="Need price, warranty, and material proof.",
                    created_at="0",
                    metrics={"upvotes": 3, "downvotes": 0, "comments": 0},
                )
            ],
            actions=[
                AOasisSocialAction(
                    actor_name="Skeptic",
                    actor_handle="u/skeptic",
                    action_type="create_post",
                    created_at="0",
                    text="Need price, warranty, and material proof.",
                )
            ],
            totals={"posts": 1, "comments": 0, "actions": 1},
        )
    ]

    summary = build_evidence_summary(outputs)

    assert summary.platforms == {"reddit": {"posts": 1, "actions": 1}}
    assert "price" in summary.signals
    assert "warranty" in summary.signals
    assert summary.representative_quotes == [
        "Need price, warranty, and material proof."
    ]


def test_build_scribe_markdown_is_llm_ready():
    summary = build_evidence_summary([
        AOasisPlatformOutput(
            platform="instagram",
            posts=[],
            actions=[],
            totals={"posts": 0, "comments": 0, "actions": 0},
        )
    ])

    markdown = build_scribe_markdown(summary)

    assert "# A-Oasis Evidence Brief" in markdown
    assert "instagram" in markdown
    assert "Signals" in markdown
