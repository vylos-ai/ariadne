"""LLM model factory.

Single place a model is configured, built on Pydantic AI. Swap the LLM by
changing only environment variables (base URL, API key, model name) — no
source edits required.
"""

import os

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

DEFAULT_MODEL = "anthropic:claude-opus-4-8"


def build_model(
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> str | OpenAIChatModel:
    """Build a Pydantic AI model from explicit args or environment variables.

    Explicit keyword args take precedence over environment variables.

    - `ARIADNE_LLM_MODEL` — model name (default: `anthropic:claude-opus-4-8`)
    - `ARIADNE_LLM_BASE_URL` — OpenAI-compatible endpoint. If set, returns an
      `OpenAIChatModel` wired to an `OpenAIProvider`. If unset, returns the
      provider-prefixed model string unchanged so pydantic-ai resolves it
      natively (keeps the existing `ANTHROPIC_API_KEY` flow working).
    - `ARIADNE_LLM_API_KEY` — key for the OpenAI-compatible endpoint.
    """
    explicit_model = model or os.environ.get("ARIADNE_LLM_MODEL")
    resolved_base_url = base_url or os.environ.get("ARIADNE_LLM_BASE_URL")
    resolved_api_key = api_key or os.environ.get("ARIADNE_LLM_API_KEY")

    if not resolved_base_url:
        return explicit_model or DEFAULT_MODEL

    if not explicit_model:
        raise ValueError(
            "ARIADNE_LLM_BASE_URL is set but no model was given. An "
            "OpenAI-compatible endpoint needs an unprefixed model name — "
            "set ARIADNE_LLM_MODEL (or pass model=...) instead of relying "
            "on the default provider-prefixed model."
        )

    return OpenAIChatModel(
        explicit_model,
        provider=OpenAIProvider(base_url=resolved_base_url, api_key=resolved_api_key),
    )
