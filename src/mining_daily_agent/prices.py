"""Commodity price lookup service using live public sources or user-provided CSV files."""

from __future__ import annotations

import csv
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from mining_daily_agent.common import (
    PricePoint,
    ResponseFormat,
    TrendSummary,
    parse_date,
    to_json,
)
from mining_daily_agent.http_client import FetchError, fetch_text

WESTMETALL_FIELDS = {
    "copper": "LME_Cu_cash",
    "zinc": "LME_Zn_cash",
    "nickel": "LME_Ni_cash",
}
SUNSIRS_LITHIUM_URL = "https://www.sunsirs.com/uk/prodetail-1162.html"
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


def _parse_decimal(value: str) -> float:
    return float(value.replace(",", "").strip())


def _parse_westmetall_date(value: str) -> str:
    parsed = datetime.strptime(value.strip(), "%d. %B %Y")
    return parsed.date().isoformat()


async def _load_westmetall_points(commodity: str) -> list[PricePoint]:
    field = WESTMETALL_FIELDS.get(commodity)
    if not field:
        return []
    source_url = f"https://www.westmetall.com/en/markdaten.php?action=table&field={field}"
    try:
        html = await fetch_text(source_url, ttl_seconds=3600)
    except FetchError as exc:
        raise PriceLookupError(f"Could not fetch real LME data from Westmetall: {exc}") from exc

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        raise PriceLookupError("Westmetall response did not contain an LME data table.")

    points: list[PricePoint] = []
    for row in table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
        if len(cells) < 2 or cells[0].casefold() == "date":
            continue
        try:
            points.append(
                PricePoint(
                    commodity=commodity,
                    date=_parse_westmetall_date(cells[0]),
                    close=_parse_decimal(cells[1]),
                    unit="USD/t",
                    source_url=source_url,
                    source_type="live_westmetall_lme",
                )
            )
        except ValueError:
            continue
    return points


async def _load_sunsirs_lithium_points() -> list[PricePoint]:
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0, headers=headers) as client:
        first = await client.get(SUNSIRS_LITHIUM_URL)
        first.raise_for_status()
        cookie_match = re.search(r'var _0x2 = "([0-9a-f]+)"', first.text)
        if cookie_match:
            second = await client.get(
                SUNSIRS_LITHIUM_URL,
                headers={**headers, "Cookie": f"HW_CHECK={cookie_match.group(1)}"},
            )
            second.raise_for_status()
            html = second.text
        else:
            html = first.text

    soup = BeautifulSoup(html, "html.parser")
    points: list[PricePoint] = []
    for row in soup.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
        if len(cells) < 4 or cells[0].casefold() == "commodity":
            continue
        if "lithium carbonate" not in cells[0].casefold():
            continue
        try:
            points.append(
                PricePoint(
                    commodity="lithium",
                    date=date.fromisoformat(cells[3]).isoformat(),
                    close=_parse_decimal(cells[2]),
                    unit="CNY/t",
                    source_url=SUNSIRS_LITHIUM_URL,
                    source_type="live_sunsirs_spot",
                )
            )
        except ValueError:
            continue
    return points


async def _load_points(commodity: str) -> list[PricePoint]:
    points = _load_csv_points(commodity)
    if points:
        points.sort(key=lambda item: item.date)
        return points

    if commodity == "lithium":
        points = await _load_sunsirs_lithium_points()
    else:
        points = await _load_westmetall_points(commodity)
    if not points:
        raise PriceLookupError(
            f"No real price source configured for '{commodity}'. "
            "Set PRICE_CSV_DIR to a directory containing a commodity CSV "
            "with columns date,close,unit,source_url."
        )
    points.sort(key=lambda item: item.date)
    return points


async def get_price_point(commodity: str, price_date: str | None = None) -> dict[str, object]:
    """Return the closest available price point on or before the requested date."""

    key = normalize_commodity(commodity)
    points = await _load_points(key)
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
    return {"requested_date": requested.isoformat(), "price": selected, "warnings": warnings}


async def get_price_trend(commodity: str, days: int = 30) -> dict[str, object]:
    """Return price trend over the available lookback window."""

    key = normalize_commodity(commodity)
    points = await _load_points(key)
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
