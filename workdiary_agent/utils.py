# workdiary_agent/utils.py
"""Shared utilities for WorkDiary Agent nodes."""
import os
from pathlib import Path


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
    return timeout, retries


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
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if not provider:
        if os.environ.get("SILICONFLOW_API_KEY"):
            provider = "siliconflow"
        elif os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
        elif os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            provider = "anthropic"

    timeout, max_retries = _runtime_options()

    if provider == "siliconflow":
        api_key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
        if not api_key:
            raise LLMConfigurationError(
                "LLM_PROVIDER=siliconflow requires SILICONFLOW_API_KEY"
            )
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.environ.get("SILICONFLOW_MODEL", "Qwen/Qwen3-32B"),
            api_key=api_key,
            base_url=os.environ.get(
                "SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"
            ),
            temperature=0,
            timeout=timeout,
            max_retries=max_retries,
        )

    if provider in {"openai", "openai-compatible"}:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise LLMConfigurationError(
                f"LLM_PROVIDER={provider} requires OPENAI_API_KEY"
            )
        from langchain_openai import ChatOpenAI
        kwargs = {
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "api_key": api_key,
            "temperature": 0,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        base_url = os.environ.get("OPENAI_API_BASE", "").strip()
        if provider == "openai-compatible" and not base_url:
            raise LLMConfigurationError(
                "LLM_PROVIDER=openai-compatible requires OPENAI_API_BASE"
            )
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)

    if provider != "anthropic":
        raise LLMConfigurationError(
            "Set LLM_PROVIDER to siliconflow, openai, openai-compatible, or anthropic"
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
    if not anthropic_key and not auth_token:
        raise LLMConfigurationError(
            "LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN"
        )
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
    return ChatAnthropic(**kwargs)


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
