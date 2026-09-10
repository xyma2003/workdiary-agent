"""Stable runtime data paths independent of the process working directory."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """Return the configured runtime data directory.

    Local source checkouts default to the repository root for backward
    compatibility. Deployments can set ``WORKDIARY_DATA_DIR`` to a durable,
    writable volume.
    """
    configured = os.environ.get("WORKDIARY_DATA_DIR", "").strip()
    return Path(configured).expanduser().resolve() if configured else PROJECT_ROOT


def data_path(filename: str) -> Path:
    """Return a path below the runtime data directory."""
    return data_dir() / filename
