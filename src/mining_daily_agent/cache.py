"""Small async-safe file cache for public HTTP reads."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from mining_daily_agent.common import project_root

DEFAULT_TTL_SECONDS = 60 * 30


def cache_dir() -> Path:
    """Return the configured cache directory."""

    configured = os.getenv("MINING_AGENT_CACHE_DIR")
    if configured:
        return Path(configured)
    return project_root() / ".cache" / "mining-daily-agent"


def cache_key(namespace: str, value: str) -> Path:
    """Build a stable cache path."""

    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return cache_dir() / namespace / digest


def read_cached(namespace: str, value: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> bytes | None:
    """Read cached bytes if the item exists and is fresh."""

    path = cache_key(namespace, value)
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > ttl_seconds:
        return None
    return path.read_bytes()


def write_cached(namespace: str, value: str, payload: bytes) -> None:
    """Write cached bytes."""

    path = cache_key(namespace, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
