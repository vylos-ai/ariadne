import pytest
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from ariadne.llm import build_model, configure_observability


def test_build_model_default_when_nothing_set(monkeypatch):
    monkeypatch.delenv("ARIADNE_LLM_MODEL", raising=False)
    monkeypatch.delenv("ARIADNE_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("ARIADNE_LLM_API_KEY", raising=False)

    model = build_model()

    assert model == "anthropic:claude-opus-4-8"


def test_build_model_uses_model_env_when_base_url_unset(monkeypatch):
    monkeypatch.setenv("ARIADNE_LLM_MODEL", "anthropic:claude-sonnet-4-5")
    monkeypatch.delenv("ARIADNE_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("ARIADNE_LLM_API_KEY", raising=False)

    model = build_model()

    assert model == "anthropic:claude-sonnet-4-5"


def test_build_model_returns_openai_chat_model_when_base_url_set(monkeypatch):
    monkeypatch.setenv("ARIADNE_LLM_MODEL", "llama3")
    monkeypatch.setenv("ARIADNE_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("ARIADNE_LLM_API_KEY", "ollama-key")

    model = build_model()

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "llama3"
    provider = model._provider
    assert isinstance(provider, OpenAIProvider)
    assert str(provider.base_url).rstrip("/") == "http://localhost:11434/v1"


def test_build_model_explicit_kwargs_take_precedence_over_env(monkeypatch):
    monkeypatch.setenv("ARIADNE_LLM_MODEL", "env-model")
    monkeypatch.setenv("ARIADNE_LLM_BASE_URL", "http://env-base-url/v1")
    monkeypatch.setenv("ARIADNE_LLM_API_KEY", "env-key")

    model = build_model(
        model="explicit-model",
        base_url="http://explicit-base-url/v1",
        api_key="explicit-key",
    )

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "explicit-model"
    provider = model._provider
    assert isinstance(provider, OpenAIProvider)
    assert str(provider.base_url).rstrip("/") == "http://explicit-base-url/v1"


def test_build_model_explicit_model_only_no_base_url(monkeypatch):
    monkeypatch.delenv("ARIADNE_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("ARIADNE_LLM_API_KEY", raising=False)

    model = build_model(model="anthropic:claude-opus-4-8")

    assert model == "anthropic:claude-opus-4-8"


def test_build_model_raises_when_base_url_set_without_explicit_model(monkeypatch):
    monkeypatch.delenv("ARIADNE_LLM_MODEL", raising=False)
    monkeypatch.setenv("ARIADNE_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("ARIADNE_LLM_API_KEY", "ollama-key")

    with pytest.raises(ValueError, match="ARIADNE_LLM_MODEL"):
        build_model()


def test_configure_observability_is_noop_when_unset(monkeypatch):
    monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
    monkeypatch.delenv("ARIADNE_TRACE", raising=False)
    calls = []
    monkeypatch.setattr(
        "ariadne.llm.logfire.configure", lambda **kwargs: calls.append("configure")
    )
    monkeypatch.setattr(
        "ariadne.llm.logfire.instrument_pydantic_ai",
        lambda: calls.append("instrument"),
    )

    configure_observability()

    assert calls == []


def test_configure_observability_activates_when_token_set(monkeypatch):
    monkeypatch.setenv("LOGFIRE_TOKEN", "fake-token")
    monkeypatch.delenv("ARIADNE_TRACE", raising=False)
    calls = []
    monkeypatch.setattr(
        "ariadne.llm.logfire.configure", lambda **kwargs: calls.append("configure")
    )
    monkeypatch.setattr(
        "ariadne.llm.logfire.instrument_pydantic_ai",
        lambda: calls.append("instrument"),
    )

    configure_observability()

    assert calls == ["configure", "instrument"]


def test_configure_observability_activates_when_trace_flag_set(monkeypatch):
    monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
    monkeypatch.setenv("ARIADNE_TRACE", "1")
    calls = []
    monkeypatch.setattr(
        "ariadne.llm.logfire.configure", lambda **kwargs: calls.append("configure")
    )
    monkeypatch.setattr(
        "ariadne.llm.logfire.instrument_pydantic_ai",
        lambda: calls.append("instrument"),
    )

    configure_observability()

    assert calls == ["configure", "instrument"]


def test_configure_observability_swallows_configure_exception(monkeypatch, capsys):
    monkeypatch.setenv("ARIADNE_TRACE", "1")

    def boom(**kwargs):
        raise RuntimeError("logfire backend unreachable")

    monkeypatch.setattr("ariadne.llm.logfire.configure", boom)
    monkeypatch.setattr(
        "ariadne.llm.logfire.instrument_pydantic_ai",
        lambda: pytest.fail("should not be reached when configure raises"),
    )

    configure_observability()  # must not raise
