from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

ModelFactory = Callable[..., object]


@dataclass(frozen=True)
class OpenRouterModelResolver:
    """Lazy CAMEL backend resolver for OpenRouter chat models."""

    api_key: str | None
    base_url: str
    default_model: str | None = None
    app_title: str | None = None
    referrer: str | None = None
    model_factory: ModelFactory | None = None

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        model_factory: ModelFactory | None = None,
    ) -> "OpenRouterModelResolver":
        values = env or os.environ
        return cls(
            api_key=_env_value(values, "OPENROUTER_API_KEY"),
            base_url=(
                _env_value(values, "OPENROUTER_BASE_URL")
                or _env_value(values, "OPENROUTER_API_BASE_URL")
                or OPENROUTER_DEFAULT_BASE_URL
            ),
            default_model=(
                _env_value(values, "AOASIS_DEFAULT_MODEL")
                or _env_value(values, "OPENROUTER_MODEL")
            ),
            app_title=(
                _env_value(values, "OPENROUTER_APP_TITLE")
                or _env_value(values, "AOASIS_APP_TITLE")
            ),
            referrer=(
                _env_value(values, "OPENROUTER_REFERRER")
                or _env_value(values, "AOASIS_APP_REFERRER")
            ),
            model_factory=model_factory,
        )

    def __call__(self, requested_model: str) -> object:
        if not self.api_key:
            raise RuntimeError(
                "AOaSIS LLM runtime requires OPENROUTER_API_KEY to create "
                "the default OpenRouter model backend.")

        model_name = self.default_model or requested_model.strip()
        if not model_name:
            raise RuntimeError(
                "AOaSIS LLM runtime requires a model name. Set "
                "AOASIS_DEFAULT_MODEL or OPENROUTER_MODEL.")

        kwargs: dict[str, Any] = {
            "model_platform": "openrouter",
            "model_type": model_name,
            "api_key": self.api_key,
            "url": self.base_url,
        }
        headers = self._default_headers()
        if headers:
            kwargs["default_headers"] = headers

        factory = self.model_factory or _camel_model_factory
        return factory(**kwargs)

    def _default_headers(self) -> dict[str, str]:
        headers = {}
        if self.referrer:
            headers["HTTP-Referer"] = self.referrer
        if self.app_title:
            headers["X-Title"] = self.app_title
        return headers


def default_openrouter_model_resolver() -> OpenRouterModelResolver:
    return OpenRouterModelResolver.from_env()


def _camel_model_factory(**kwargs: Any) -> object:
    from camel.models import ModelFactory as CamelModelFactory

    return CamelModelFactory.create(**kwargs)


def _env_value(values: Mapping[str, str], name: str) -> str | None:
    value = values.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None
