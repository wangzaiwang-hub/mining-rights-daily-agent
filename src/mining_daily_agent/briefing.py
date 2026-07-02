"""Agent workflow that composes the three MCP-style services."""

from __future__ import annotations

import os
from datetime import date

from mining_daily_agent.news import fetch_article, search_news
from mining_daily_agent.pdf_resources import extract_resources
from mining_daily_agent.prices import get_price_trend, normalize_commodity


def commodities_for_topic(topic: str) -> list[str]:
    """Infer relevant commodity tools from the briefing topic."""

    normalized = topic.casefold()
    commodities: list[str] = []
    if any(term in normalized for term in ["lithium", "li", "pilbara"]):
        commodities.append("lithium")
    if any(term in normalized for term in ["copper", "cu"]):
        commodities.append("copper")
    if any(term in normalized for term in ["nickel", "ni"]):
        commodities.append("nickel")
    if any(term in normalized for term in ["zinc", "zn"]):
        commodities.append("zinc")
    if "iron" in normalized:
        commodities.append("iron_ore")
    return commodities or ["copper"]


def _risk_from_trend(direction: str, change_pct: float) -> str:
    if direction == "up" and change_pct >= 5:
        return (
            "Input or concentrate pricing is moving sharply upward; verify whether project "
            "economics assume stale price decks."
        )
    if direction == "down" and change_pct <= -5:
        return "Recent price weakness may pressure short-term sentiment and financing assumptions."
    return (
        "Price movement is not extreme in the available window, but live exchange data should "
        "be checked before investment use."
    )


async def generate_briefing(topic: str, days: int = 7) -> str:
    """Generate a cited Markdown mining-rights daily briefing."""

    news_payload = await search_news(topic, days=days, limit=5)
    enriched_articles = []
    for article in news_payload["articles"][:3]:
        fetched = await fetch_article(article.url)
        enriched_articles.append(fetched["article"])

    report_url = os.getenv("REPORT_PDF_URL")
    resource_payload = await extract_resources(report_url)

    commodity_keys = [normalize_commodity(item) for item in commodities_for_topic(topic)]
    trends = [get_price_trend(commodity, days=max(days, 7)) for commodity in commodity_keys]

    lines = [
        f"# Mining Rights Daily: {topic}",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        "## Executive Summary",
    ]
    if enriched_articles:
        top_titles = "; ".join(article.title for article in enriched_articles[:2])
        lines.append(f"- News signal: {top_titles}.")
    else:
        lines.append("- News signal: no matching live or fixture articles were available.")

    resource_rows = resource_payload["estimates"]
    if resource_rows:
        categories = ", ".join(sorted({row.category for row in resource_rows}))
        lines.append(
            f"- Resource signal: extracted {len(resource_rows)} rows covering "
            f"{categories} resources."
        )
    else:
        lines.append("- Resource signal: extractor abstained; report requires manual review.")

    for trend_payload in trends:
        trend = trend_payload["trend"]
        lines.append(
            f"- Price signal: {trend.commodity} moved {trend.change_pct:+.2f}% over "
            f"the available {trend.days}-day window."
        )

    lines.extend(["", "## News Summary"])
    if not enriched_articles:
        lines.append("- No news articles found.")
    for article in enriched_articles:
        summary = article.summary or article.text[:500]
        lines.append(f"- [{article.title}]({article.url})")
        lines.append(f"  - {summary[:420]}")

    lines.extend(["", "## Resource Data"])
    if not resource_rows:
        lines.append("- Abstain: no reliable Indicated/Inferred rows found.")
    for row in resource_rows:
        lines.append(
            f"- **{row.category}**: {row.ore_mt} Mt at {row.grade} {row.grade_unit}; "
            f"metal {row.metal} {row.metal_unit}. Evidence: `{row.evidence}`"
        )

    lines.extend(["", "## Price Trend"])
    for trend_payload in trends:
        trend = trend_payload["trend"]
        lines.append(
            f"- **{trend.commodity}**: {trend.start.date} "
            f"{trend.start.close:,.2f} {trend.start.unit} -> "
            f"{trend.end.date} {trend.end.close:,.2f} {trend.end.unit}; "
            f"{trend.change_pct:+.2f}% ({trend.direction})."
        )

    lines.extend(["", "## Risk Notes"])
    if news_payload["source_type"] != "live_rss":
        lines.append(
            "- News data came from a reference fixture; rerun with live RSS before "
            "submission to decision makers."
        )
    if resource_payload["abstain"]:
        lines.append(
            "- Resource extraction abstained; the PDF should be reviewed manually before "
            "publishing reserve/resource claims."
        )
    for trend_payload in trends:
        trend = trend_payload["trend"]
        lines.append(f"- {trend.commodity}: {_risk_from_trend(trend.direction, trend.change_pct)}")
        if trend_payload["warnings"]:
            lines.extend(f"  - Data warning: {warning}" for warning in trend_payload["warnings"])

    lines.extend(["", "## Sources"])
    for article in enriched_articles:
        lines.append(f"- News: [{article.title}]({article.url})")
    lines.append(
        f"- Resource report: `{resource_payload['source']}` "
        f"({resource_payload['source_type']})"
    )
    for trend_payload in trends:
        trend = trend_payload["trend"]
        lines.append(
            f"- Price: [{trend.commodity} {trend.end.date}]({trend.end.source_url}) "
            f"({trend.end.source_type})"
        )

    return "\n".join(lines) + "\n"
