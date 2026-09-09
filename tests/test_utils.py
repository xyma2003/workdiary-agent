"""Configuration safety tests."""

from unittest.mock import patch

import pytest

from workdiary_agent.utils import LLMConfigurationError, make_llm


_CONFIG_KEYS = (
    "LLM_PROVIDER",
    "LLM_TIMEOUT_SECONDS",
    "LLM_MAX_RETRIES",
    "OPENAI_API_KEY",
    "OPENAI_API_BASE",
    "OPENAI_MODEL",
    "SILICONFLOW_API_KEY",
    "SILICONFLOW_BASE_URL",
    "SILICONFLOW_MODEL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_CUSTOM_HEADERS",
)


def _clear_provider_env(monkeypatch):
    for key in _CONFIG_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_official_openai_key_never_defaults_to_siliconflow(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "official-key")

    with patch("langchain_openai.ChatOpenAI") as chat_openai:
        make_llm()

    kwargs = chat_openai.call_args.kwargs
    assert kwargs["api_key"] == "official-key"
    assert "base_url" not in kwargs


def test_siliconflow_requires_provider_specific_key(monkeypatch):
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "siliconflow")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-reused")

    with pytest.raises(LLMConfigurationError, match="SILICONFLOW_API_KEY"):
        make_llm()


def test_missing_provider_configuration_is_actionable(monkeypatch):
    _clear_provider_env(monkeypatch)

    with pytest.raises(LLMConfigurationError, match="Set LLM_PROVIDER"):
        make_llm()
