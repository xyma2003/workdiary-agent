"""Freeze the evidence consumed by a report, independently of model calls."""

from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite
from urllib.parse import urlsplit

from .redaction import redact_secrets
from .time_utils import work_date


SNAPSHOT_VERSION = 1


def endpoint_identifier(value: object) -> str | None:
    """Keep only an endpoint origin; credentials, paths and queries stay private."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        host = parsed.hostname
        if ":" in host:
            host = f"[{host}]"
        port = f":{parsed.port}" if parsed.port is not None else ""
        return redact_secrets(f"{parsed.scheme}://{host}{port}")
    except ValueError:
        return None


def _text(value: object) -> str | None:
    return redact_secrets(value) if isinstance(value, str) else None


def _model_usage(records: object) -> list[dict]:
    """Serialize an explicit allowlist, never a client or environment dictionary."""
    if not isinstance(records, list):
        return []
    safe = []
    for item in records:
        if not isinstance(item, dict):
            continue
        record = {
            key: _text(item.get(key))
            for key in ("stage", "provider", "model")
        }
        record["endpoint"] = endpoint_identifier(item.get("endpoint"))
        for key in ("temperature", "timeout_seconds", "max_retries"):
            value = item.get(key)
            record[key] = (
                value if type(value) is int
                or (isinstance(value, float) and isfinite(value)) else None
            )
        safe.append(record)
    return safe


def snapshot_for_storage(state: dict) -> dict | None:
    """Return frozen sources plus observed model usage, or unknown legacy evidence.

    This deliberately never re-reads Git, provider settings, or input files.
    A checkpoint from before source capture remains unknown, even after resume.
    """
    source = state.get("source_snapshot")
    if not isinstance(source, dict) or source.get("schema_version") != SNAPSHOT_VERSION:
        return None
    git_source = source.get("git")
    if not isinstance(git_source, dict):
        return None
    result = {
        "schema_version": SNAPSHOT_VERSION,
        "captured_at": _text(source.get("captured_at")),
        "capture_status": source.get("capture_status")
        if source.get("capture_status") in {"complete", "partial"} else "partial",
        "raw_input": _text(source.get("raw_input")) or "",
        "data_input": _text(source.get("data_input")) or "",
        "git": {
            key: _text(git_source.get(key))
            for key in (
                "status", "repo_path", "requested_author", "resolved_author",
                "timezone", "report_date", "since", "until", "log",
            )
        },
        "model_usage": _model_usage(state.get("model_usage", [])),
    }
    return result


def capture_sources_node(state: dict) -> dict:
    """Checkpoint source material before the first fallible model invocation."""
    if isinstance(state.get("source_snapshot"), dict):
        # Re-entering the capture node must not silently refresh existing sources.
        return {}
    # Import lazily to preserve the existing public enrichment helpers.
    from .nodes.enrich import _read_git_log

    try:
        report_date = date.fromisoformat(state.get("date") or "").isoformat()
    except (TypeError, ValueError):
        report_date = work_date(state.get("timezone"))
    details: dict = {}
    log = _read_git_log(
        state.get("repo_path") or "",
        git_author=state.get("git_author"),
        timezone_name=state.get("timezone"),
        report_date=report_date,
        _details=details,
    )
    details["log"] = _text(log)
    raw = _text(state.get("raw_input")) or ""
    data = _text(state.get("data_input")) or ""
    source = {
        "schema_version": SNAPSHOT_VERSION,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "capture_status": "complete",
        "raw_input": raw,
        "data_input": data,
        "git": details,
    }
    # Normalize metadata as well as the material that downstream nodes consume.
    frozen = snapshot_for_storage({"source_snapshot": source})
    assert frozen is not None
    frozen.pop("model_usage")
    return {
        "source_snapshot": frozen,
        "raw_input": raw,
        "data_input": data,
        "git_log": frozen["git"]["log"],
        "model_usage": [],
        "date": report_date,
    }
