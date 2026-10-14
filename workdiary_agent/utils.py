# workdiary_agent/utils.py
"""Shared utilities for WorkDiary Agent nodes."""
import os
import math
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from .redaction import redact_secrets
from .source_snapshot import endpoint_identifier


_MODEL_USAGE: ContextVar[tuple[str, list[dict]] | None] = ContextVar(
    "workdiary_model_usage", default=None
)


@contextmanager
def collect_model_usage(stage: str):
    """Collect client configuration within one graph stage, including subgraphs."""
    records: list[dict] = []
    token = _MODEL_USAGE.set((stage, records))
    try:
        yield records
    finally:
        _MODEL_USAGE.reset(token)


def _record_model_usage(client, *, provider: str, model: str,
                        endpoint: str, temperature: float | None,
                        timeout: float, max_retries: int):
    """Observe only allowlisted metadata after a client was constructed."""
    collecting = _MODEL_USAGE.get()
    if collecting is None:
        return client
    stage, records = collecting
    model_attribute = "model" if provider == "anthropic" else "model_name"
    effective_model = getattr(client, model_attribute, None)
    if not isinstance(effective_model, str):
        effective_model = model
    endpoint_attribute = "anthropic_api_url" if provider == "anthropic" else "openai_api_base"
    effective_endpoint = getattr(client, endpoint_attribute, None)
    if not isinstance(effective_endpoint, str) or not effective_endpoint:
        effective_endpoint = endpoint
    records.append({
        "stage": stage,
        "provider": provider,
        "model": redact_secrets(effective_model),
        "endpoint": endpoint_identifier(effective_endpoint),
        "temperature": temperature,
        "timeout_seconds": timeout,
        "max_retries": max_retries,
    })
    return client


class LLMConfigurationError(RuntimeError):
    """Raised when the selected model provider is not configured safely."""


def _runtime_options() -> tuple[float, int]:
    try:
        timeout = float(os.environ.get("LLM_TIMEOUT_SECONDS", "60"))
        retries = int(os.environ.get("LLM_MAX_RETRIES", "2"))
    except ValueError as exc:
        raise LLMConfigurationError(
            "LLM_TIMEOUT_SECONDS and LLM_MAX_RETRIES must be numeric"
        ) from exc
    if not math.isfinite(timeout) or timeout <= 0 or retries < 0:
        raise LLMConfigurationError(
            "LLM_TIMEOUT_SECONDS must be positive and LLM_MAX_RETRIES must be non-negative"
        )
    return timeout, retries


def _resolve_provider() -> str:
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if provider:
        return provider
    if os.environ.get("SILICONFLOW_API_KEY"):
        return "siliconflow"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "anthropic"
    return ""


def validate_llm_configuration() -> str:
    """Validate local provider settings without making a network request."""
    provider = _resolve_provider()
    _runtime_options()

    if provider == "siliconflow" and not os.environ.get("SILICONFLOW_API_KEY", "").strip():
        raise LLMConfigurationError(
            "LLM_PROVIDER=siliconflow requires SILICONFLOW_API_KEY"
        )
    if provider in {"openai", "openai-compatible"}:
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            raise LLMConfigurationError(
                f"LLM_PROVIDER={provider} requires OPENAI_API_KEY"
            )
        if provider == "openai-compatible" and not os.environ.get(
            "OPENAI_API_BASE", ""
        ).strip():
            raise LLMConfigurationError(
                "LLM_PROVIDER=openai-compatible requires OPENAI_API_BASE"
            )
    elif provider == "anthropic":
        if not (
            os.environ.get("ANTHROPIC_API_KEY", "").strip()
            or os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
        ):
            raise LLMConfigurationError(
                "LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY or "
                "ANTHROPIC_AUTH_TOKEN"
            )
    elif provider != "siliconflow":
        raise LLMConfigurationError(
            "Set LLM_PROVIDER to siliconflow, openai, openai-compatible, or anthropic"
        )
    return provider


def make_llm():
    """Return an explicitly configured SiliconFlow, OpenAI, or Anthropic model.

    Provider-specific keys prevent an official OpenAI key from being sent to a
    third-party endpoint. ``LLM_PROVIDER`` is recommended; safe inference from
    provider-specific environment variables is retained for convenience.

    Anthropic mode supports two auth styles:
      - Standard: set ANTHROPIC_API_KEY, leave ANTHROPIC_CUSTOM_HEADERS unset.
      - Corporate proxy: set ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN. The
        token is mapped to an Authorization bearer header because ChatAnthropic
        does not expose the underlying SDK's auth_token parameter.

    ANTHROPIC_CUSTOM_HEADERS format — newline-separated 'Key: Value' pairs.
    """
    provider = validate_llm_configuration()
    timeout, max_retries = _runtime_options()

    if provider == "siliconflow":
        api_key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
        from langchain_openai import ChatOpenAI
        model = os.environ.get("SILICONFLOW_MODEL", "Qwen/Qwen3-32B")
        endpoint = os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        client = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=endpoint,
            temperature=0,
            timeout=timeout,
            max_retries=max_retries,
        )
        return _record_model_usage(
            client, provider=provider, model=model, endpoint=endpoint,
            temperature=0, timeout=timeout, max_retries=max_retries,
        )

    if provider in {"openai", "openai-compatible"}:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        from langchain_openai import ChatOpenAI
        kwargs = {
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "api_key": api_key,
            "temperature": 0,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        base_url = os.environ.get("OPENAI_API_BASE", "").strip()
        if base_url:
            kwargs["base_url"] = base_url
        client = ChatOpenAI(**kwargs)
        return _record_model_usage(
            client, provider=provider, model=kwargs["model"],
            endpoint=base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            temperature=0, timeout=timeout, max_retries=max_retries,
        )

    from langchain_anthropic import ChatAnthropic
    custom_headers_str = os.environ.get("ANTHROPIC_CUSTOM_HEADERS", "")
    headers: dict[str, str] = {}
    if custom_headers_str:
        for line in custom_headers_str.split("\n"):
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
    if auth_token and not anthropic_key:
        headers.setdefault("Authorization", f"Bearer {auth_token}")
    kwargs = {
        "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        "default_headers": headers,
        "timeout": timeout,
        "max_retries": max_retries,
    }
    if anthropic_key:
        kwargs["api_key"] = anthropic_key
    client = ChatAnthropic(**kwargs)
    return _record_model_usage(
        client, provider=provider, model=kwargs["model"],
        endpoint=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        temperature=None, timeout=timeout, max_retries=max_retries,
    )


def validate_repo_path(repo_path: str) -> str | None:
    """Validate and normalize a git repository path.

    Returns the resolved absolute path string if valid, None otherwise.
    This is input validation for a local application, not a security boundary.
    """
    if not repo_path or not repo_path.strip():
        return None
    try:
        resolved = Path(repo_path).expanduser().resolve()
        if not resolved.exists():
            return None
        if not resolved.is_dir():
            return None
        return str(resolved)
    except (OSError, ValueError):
        return None
