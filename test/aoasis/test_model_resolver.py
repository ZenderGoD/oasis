from __future__ import annotations

import sys

import pytest

from oasis.aoasis import worker_server
from oasis.aoasis.model_resolver import OpenRouterModelResolver


@pytest.fixture(autouse=True)
def clear_openrouter_env(monkeypatch):
    for name in (
        "OPENROUTER_API_KEY",
        "OPENROUTER_BASE_URL",
        "OPENROUTER_API_BASE_URL",
        "AOASIS_DEFAULT_MODEL",
        "OPENROUTER_MODEL",
        "OPENROUTER_APP_TITLE",
        "AOASIS_APP_TITLE",
        "OPENROUTER_REFERRER",
        "AOASIS_APP_REFERRER",
    ):
        monkeypatch.delenv(name, raising=False)


def test_openrouter_resolver_builds_backend_from_env(monkeypatch):
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        return {"backend": "created"}

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("AOASIS_DEFAULT_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://router.test/api/v1")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Atherum Test")
    monkeypatch.setenv("OPENROUTER_REFERRER", "https://app.test")

    resolver = OpenRouterModelResolver.from_env(model_factory=factory)

    assert resolver("request/model") == {"backend": "created"}
    assert calls == [
        {
            "model_platform": "openrouter",
            "model_type": "openai/gpt-4o-mini",
            "api_key": "sk-test",
            "url": "https://router.test/api/v1",
            "default_headers": {
                "HTTP-Referer": "https://app.test",
                "X-Title": "Atherum Test",
            },
        }
    ]


def test_openrouter_resolver_uses_openrouter_model_when_aoasis_default_absent(
    monkeypatch,
):
    calls = []

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4")

    resolver = OpenRouterModelResolver.from_env(
        model_factory=lambda **kwargs: calls.append(kwargs) or object())
    resolver("request/model")

    assert calls[0]["model_type"] == "anthropic/claude-sonnet-4"
    assert calls[0]["url"] == "https://openrouter.ai/api/v1"


def test_openrouter_resolver_falls_back_to_requested_model(monkeypatch):
    calls = []

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    resolver = OpenRouterModelResolver.from_env(
        model_factory=lambda **kwargs: calls.append(kwargs) or object())
    resolver("request/model")

    assert calls[0]["model_type"] == "request/model"


def test_openrouter_resolver_fails_lazily_with_clear_missing_key(
    monkeypatch,
):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    resolver = OpenRouterModelResolver.from_env(model_factory=lambda **_: None)

    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        resolver("request/model")


def test_worker_server_installs_default_resolver_for_llm_runtime(
    monkeypatch,
    tmp_path,
):
    sentinel_resolver = object()
    services = []

    class FakeService:
        def __init__(self, *args, **kwargs):
            services.append((args, kwargs))

    class FakeServer:
        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            pass

    monkeypatch.setattr(
        worker_server,
        "default_openrouter_model_resolver",
        lambda: sentinel_resolver,
    )
    monkeypatch.setattr(worker_server, "AOasisWorkerService", FakeService)
    monkeypatch.setattr(
        worker_server,
        "make_aoasis_worker_server",
        lambda *_: FakeServer(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_server",
            "--runtime",
            "oasis-llm",
            "--data-dir",
            str(tmp_path),
        ],
    )

    worker_server.main()

    assert services[0][1]["runtime_mode"] == "oasis-llm"
    assert services[0][1]["model_resolver"] is sentinel_resolver
