# workdiary_agent/utils.py
"""Shared utilities for WorkDiary Agent nodes."""
import os
from pathlib import Path

from langchain_anthropic import ChatAnthropic


def make_llm() -> ChatAnthropic:
    """Return ChatAnthropic with optional custom headers for proxy environments.

    Supports two auth modes:
      - Standard: set ANTHROPIC_API_KEY, leave ANTHROPIC_CUSTOM_HEADERS unset.
      - Corporate proxy: set ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN (picked up
        automatically by the anthropic SDK), and ANTHROPIC_CUSTOM_HEADERS for any
        extra headers the proxy requires.

    ANTHROPIC_CUSTOM_HEADERS format — newline-separated 'Key: Value' pairs:
        X-Custom-Header: my-value
        X-Another-Header: another-value

    If ANTHROPIC_CUSTOM_HEADERS is not set, no extra headers are added and
    standard API key auth works as-is.
    """
    custom_headers_str = os.environ.get("ANTHROPIC_CUSTOM_HEADERS", "")
    headers: dict[str, str] = {}
    if custom_headers_str:
        for line in custom_headers_str.split("\n"):
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
    return ChatAnthropic(model="claude-sonnet-4-5", default_headers=headers)


def validate_repo_path(repo_path: str) -> str | None:
    """Validate and normalize a git repository path.

    Returns the resolved absolute path string if valid, None otherwise.
    Uses pathlib to prevent path traversal attacks.
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
