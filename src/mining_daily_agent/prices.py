"""Commodity price lookup service with explicit fixture fallback."""

from __future__ import annotations

import csv
import json
import os
from datetime import date, timedelta
from pathlib import Path

from mining_daily_agent.common import (
    PricePoint,
    ResponseFormat,
    TrendSummary,
    parse_date,
    project_root,
    to_json,
)

FIXTURE_PATH = project_root() / "data" / "fixtures" / "prices.json"
DEFAULT_UNITS = {
    "copper": "USD/t",
    "zinc": "USD/t",
    "nickel": "USD/t",
    "lithium": "CNY/t",
    "iron_ore": "USD/t",
}


class PriceLookupError(ValueError):
    """Raised when no price data can be found."""


def normalize_commodity(value: str) -> str:
    """Normalize commodity aliases into internal keys."""

    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "cu": "copper",
        "lme_copper": "copper",
        "zn": "zinc",
        "lme_zinc": "zinc",
        "ni": "nickel",
        "lme_nickel": "nickel",
        "li": "lithium",
        "shfe_lithium": "lithium",
        "iron": "iron_ore",
        "ironore": "iron_ore",
        "iron_ore": "iron_ore",
    }
    return aliases.get(normalized, normalized)


def _load_fixture_points(commodity: str) -> list[PricePoint]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    rows = payload["commodities"].get(commodity, [])
    return [
        PricePoint(
            commodity=commodity,
            date=row["date"],
            close=float(row["close"]),
            unit=row.get("unit", DEFAULT_UNITS.get(commodity, "")),
            source_url=row.get("source_url", "data/fixtures/prices.json"),
            source_type="reference_fixture",
        )
        for row in rows
    ]


def _load_csv_points(commodity: str) -> list[PricePoint]:
    csv_dir = os.getenv("PRICE_CSV_DIR")
    if not csv_dir:
        return []
    path = Path(csv_dir) / f"{commodity}.csv"
    if not path.exists():
        return []

    points: list[PricePoint] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            points.append(
                PricePoint(
                    commodity=commodity,
                    date=row["date"],
                    close=float(row["close"]),
                    unit=row.get("unit") or DEFAULT_UNITS.get(commodity, ""),
                    source_url=row.get("source_url") or str(path),
                    source_type="csv_input",
                )
            )
    return points


def _load_points(commodity: str) -> list[PricePoint]:
    points = _load_csv_points(commodity)
    if not points:
        points = _load_fixture_points(commodity)
    points.sort(key=lambda item: item.date)
    return points


def get_price_point(commodity: str, price_date: str | None = None) -> dict[str, object]:
    """Return the closest available price point on or before the requested date."""

    key = normalize_commodity(commodity)
    points = _load_points(key)
    if not points:
        raise PriceLookupError(f"No price data configured for commodity '{commodity}'.")

    requested = parse_date(price_date) if price_date else date.today()
    if requested is None:
        raise PriceLookupError(f"Invalid date '{price_date}'. Use YYYY-MM-DD.")

    candidates = [
        point
        for point in points
        if parse_date(point.date) and parse_date(point.date) <= requested
    ]
    if not candidates:
        candidates = points[:1]
    selected = candidates[-1]
    warnings = []
    if selected.source_type == "reference_fixture":
        warnings.append(
            "Using bundled reference fixture, not live LME/SHFE/Shanghai Metals Market data."
        )
    return {"requested_date": requested.isoformat(), "price": selected, "warnings": warnings}


def get_price_trend(commodity: str, days: int = 30) -> dict[str, object]:
    """Return price trend over the available lookback window."""

    key = normalize_commodity(commodity)
    points = _load_points(key)
    if len(points) < 2:
        raise PriceLookupError(f"Need at least two price points for '{commodity}' trend.")

    end = points[-1]
    end_date = parse_date(end.date)
    assert end_date is not None
    cutoff = end_date - timedelta(days=days)
    window = [
        point
        for point in points
        if parse_date(point.date) and parse_date(point.date) >= cutoff
    ]
    if len(window) < 2:
        window = points[-min(len(points), 2) :]
    start = window[0]
    change_abs = end.close - start.close
    change_pct = change_abs / start.close * 100 if start.close else 0.0
    if change_pct > 1:
        direction = "up"
    elif change_pct < -1:
        direction = "down"
    else:
        direction = "flat"

    warnings = []
    if end.source_type == "reference_fixture":
        warnings.append(
            "Using bundled reference fixture, not live LME/SHFE/Shanghai Metals Market data."
        )

    return {
        "trend": TrendSummary(
            commodity=key,
            days=days,
            start=start,
            end=end,
            change_abs=round(change_abs, 4),
            change_pct=round(change_pct, 2),
            direction=direction,
        ),
        "points": window,
        "warnings": warnings,
    }


def format_price(payload: dict[str, object], response_format: ResponseFormat) -> str:
    """Format one price point."""

    if response_format == ResponseFormat.JSON:
        return to_json(payload)
    price = payload["price"]
    lines = [f"# {price.commodity.title()} Price", ""]
    lines.append(f"Requested date: {payload['requested_date']}")
    lines.append(f"Observed date: {price.date}")
    lines.append(f"Close: **{price.close:,.2f} {price.unit}**")
    lines.append(f"Source: [{price.source_type}]({price.source_url})")
    if payload["warnings"]:
        lines.append("")
        lines.append("## Warnings")
        lines.extend(f"- {warning}" for warning in payload["warnings"])
    return "\n".join(lines)


def format_trend(payload: dict[str, object], response_format: ResponseFormat) -> str:
    """Format price trend output."""

    if response_format == ResponseFormat.JSON:
        return to_json(payload)
    trend = payload["trend"]
    lines = [f"# {trend.commodity.title()} {trend.days}-Day Trend", ""]
    lines.append(
        f"{trend.start.date}: {trend.start.close:,.2f} {trend.start.unit} -> "
        f"{trend.end.date}: {trend.end.close:,.2f} {trend.end.unit}"
    )
    lines.append(
        f"Change: **{trend.change_abs:,.2f} ({trend.change_pct:+.2f}%)**, "
        f"direction `{trend.direction}`"
    )
    lines.append(f"Source: [{trend.end.source_type}]({trend.end.source_url})")
    if payload["warnings"]:
        lines.append("")
        lines.append("## Warnings")
        lines.extend(f"- {warning}" for warning in payload["warnings"])
    return "\n".join(lines)
