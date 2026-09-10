"""Best-effort secret redaction before untrusted text reaches an LLM."""

from __future__ import annotations

import re


_REDACTED = "[REDACTED_SECRET]"
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [^-\n]*PRIVATE KEY-----.*?-----END [^-\n]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"\b(?:sk|sk-ant)-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}=*"),
    re.compile(
        r"(?i)(?<![A-Za-z0-9])(?:[A-Za-z0-9]+_)*"
        r"(?:api[_-]?key|access[_-]?token|auth[_-]?token|password)"
        r"\s*[:=]\s*['\"]?[^\s,'\";]{8,}"
    ),
)


def redact_secrets(value: object) -> str:
    """Return text with common credential formats replaced by a stable marker."""
    text = "" if value is None else str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text
