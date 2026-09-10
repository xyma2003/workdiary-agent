"""Timezone-aware helpers shared by enrichment, persistence, and the UI."""

from __future__ import annotations

from datetime import datetime
import logging
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


logger = logging.getLogger(__name__)


def resolve_timezone(timezone_name: str | None = None):
    """Resolve an IANA timezone, falling back to the machine's local timezone."""
    requested = (timezone_name or os.environ.get("WORKDIARY_TIMEZONE", "")).strip()
    if requested:
        try:
            return ZoneInfo(requested)
        except ZoneInfoNotFoundError:
            logger.warning("Unknown timezone %r; using the system timezone", requested)
    return datetime.now().astimezone().tzinfo


def work_date(timezone_name: str | None = None, *, now: datetime | None = None) -> str:
    """Return the ISO work date in the requested timezone."""
    timezone = resolve_timezone(timezone_name)
    current = datetime.now(timezone) if now is None else now.astimezone(timezone)
    return current.date().isoformat()
