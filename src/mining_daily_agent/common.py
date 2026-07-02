"""Shared types and formatting helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class ResponseFormat(StrEnum):
    """Supported MCP tool response formats."""

    MARKDOWN = "markdown"
    JSON = "json"


@dataclass(frozen=True)
class Citation:
    """Source citation used in tool and briefing outputs."""

    title: str
    url: str
    source_type: str


@dataclass(frozen=True)
class NewsArticle:
    """Normalized mining news article."""

    title: str
    url: str
    published_at: str
    source: str
    summary: str
    text: str = ""


@dataclass(frozen=True)
class ResourceEstimate:
    """One mineral resource estimate row extracted from a report."""

    category: str
    ore_mt: float | None
    grade: float | None
    grade_unit: str | None
    metal: float | None
    metal_unit: str | None
    page: int | None
    evidence: str


@dataclass(frozen=True)
class PricePoint:
    """One commodity price observation."""

    commodity: str
    date: str
    close: float
    unit: str
    source_url: str
    source_type: str


@dataclass(frozen=True)
class TrendSummary:
    """Commodity trend result."""

    commodity: str
    days: int
    start: PricePoint
    end: PricePoint
    change_abs: float
    change_pct: float
    direction: str


def project_root() -> Path:
    """Return the repository root by walking upward from this file."""

    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def utc_now_iso() -> str:
    """Return a compact UTC ISO timestamp."""

    return datetime.now(UTC).replace(microsecond=0).isoformat()


def parse_date(value: str | None) -> date | None:
    """Parse common ISO date strings into a date."""

    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def to_json(data: Any) -> str:
    """Serialize dataclasses and dates for stable JSON MCP responses."""

    def default(obj: Any) -> Any:
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Path):
            return str(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    return json.dumps(data, ensure_ascii=False, indent=2, default=default)


def bullet_escape(text: str) -> str:
    """Keep Markdown bullets single-line and readable."""

    return " ".join(text.split())
