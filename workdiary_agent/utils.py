# workdiary_agent/utils.py
"""Shared utilities for WorkDiary Agent nodes."""
import os
from pathlib import Path

from langchain_anthropic import ChatAnthropic


def make_llm() -> ChatAnthropic:
    """Return ChatAnthropic with custom headers parsed from ANTHROPIC_CUSTOM_HEADERS env var.

    The environment variable is a newline-separated list of 'Key: Value' pairs.
    Required by the Meituan internal proxy (mcli.sankuai.com) to identify the caller.
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
