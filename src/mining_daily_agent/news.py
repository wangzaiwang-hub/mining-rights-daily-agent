"""Mining news search and article fetching service."""

from __future__ import annotations

import email.utils
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import feedparser
from bs4 import BeautifulSoup

from mining_daily_agent.common import (
    NewsArticle,
    ResponseFormat,
    bullet_escape,
    project_root,
    to_json,
)
from mining_daily_agent.http_client import FetchError, fetch_text, is_http_url

DEFAULT_FEEDS = ["https://www.mining.com/feed/"]
FIXTURE_PATH = project_root() / "data" / "fixtures" / "news.json"
QUERY_STOPWORDS = {
    "mine",
    "mines",
    "mining",
    "mineral",
    "minerals",
    "project",
    "daily",
    "today",
}


def configured_feeds() -> list[str]:
    """Return configured RSS feeds."""

    if os.getenv("MINING_AGENT_OFFLINE") == "1":
        return []
    raw = os.getenv("MINING_NEWS_FEEDS")
    if not raw:
        return DEFAULT_FEEDS
    return [part.strip() for part in raw.split(",") if part.strip()]


def _parse_feed_date(entry: object) -> datetime:
    published = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if published:
        try:
            parsed = email.utils.parsedate_to_datetime(published)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except (TypeError, ValueError):
            pass
    return datetime.now(UTC)


def _matches(article: NewsArticle, query: str) -> bool:
    terms = [
        term.casefold()
        for term in query.replace("-", " ").replace("_", " ").split()
        if len(term) > 2 and term.casefold() not in QUERY_STOPWORDS
    ]
    if not terms:
        return True
    haystack = f"{article.title} {article.summary} {article.text}".casefold()
    matches = sum(1 for term in terms if term in haystack)
    required = 1 if len(terms) <= 2 else 2
    return matches >= required


def _load_fixture_articles() -> list[NewsArticle]:
    import json

    if not FIXTURE_PATH.exists():
        return []
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [NewsArticle(**item) for item in payload["articles"]]


async def search_news(query: str, days: int = 7, limit: int = 10) -> dict[str, object]:
    """Search configured mining RSS feeds with explicit fixture fallback."""

    cutoff = datetime.now(UTC) - timedelta(days=days)
    articles: list[NewsArticle] = []
    warnings: list[str] = []
    source_type = "live_rss"

    for feed_url in configured_feeds():
        try:
            feed_text = await fetch_text(feed_url, ttl_seconds=900)
            parsed = feedparser.parse(feed_text)
            for entry in parsed.entries:
                published = _parse_feed_date(entry)
                if published < cutoff:
                    continue
                article = NewsArticle(
                    title=getattr(entry, "title", "Untitled"),
                    url=getattr(entry, "link", feed_url),
                    published_at=published.isoformat(),
                    source=urlparse(feed_url).netloc or feed_url,
                    summary=BeautifulSoup(
                        getattr(entry, "summary", ""),
                        "html.parser",
                    ).get_text(" "),
                )
                if _matches(article, query):
                    articles.append(article)
        except FetchError as exc:
            warnings.append(str(exc))

    if not articles:
        source_type = "reference_fixture"
        if configured_feeds():
            warnings.append("No live RSS matches found; using bundled reference fixture.")
        articles = [article for article in _load_fixture_articles() if _matches(article, query)]

    articles = sorted(articles, key=lambda item: item.published_at, reverse=True)[:limit]
    return {
        "query": query,
        "days": days,
        "source_type": source_type,
        "count": len(articles),
        "articles": articles,
        "warnings": warnings,
    }


async def fetch_article(url: str) -> dict[str, object]:
    """Fetch and extract article title/text from a URL or fixture URL."""

    warnings: list[str] = []
    source_type = "live_html" if is_http_url(url) else "local_or_fixture"

    fixture_match = next(
        (article for article in _load_fixture_articles() if article.url == url),
        None,
    )
    if fixture_match and not is_http_url(url):
        return {"article": fixture_match, "source_type": "reference_fixture", "warnings": warnings}

    try:
        html = await fetch_text(url, ttl_seconds=3600)
    except FetchError as exc:
        if fixture_match:
            warnings.append(str(exc))
            warnings.append("Fell back to bundled fixture article text.")
            return {
                "article": fixture_match,
                "source_type": "reference_fixture",
                "warnings": warnings,
            }
        raise

    soup = BeautifulSoup(html, "html.parser")
    title = (
        soup.find("meta", property="og:title")
        or soup.find("h1")
        or soup.find("title")
    )
    if title and title.has_attr("content"):
        title_text = title.get("content")
    elif title:
        title_text = title.get_text(" ", strip=True)
    else:
        title_text = url
    nodes = soup.select("article p") or soup.select("main p") or soup.select("p")
    text = "\n".join(node.get_text(" ", strip=True) for node in nodes)
    summary = text[:500]
    article = NewsArticle(
        title=title_text or url,
        url=url,
        published_at="",
        source=urlparse(url).netloc or Path(url).name,
        summary=summary,
        text=text,
    )
    return {"article": article, "source_type": source_type, "warnings": warnings}


def format_news_search(payload: dict[str, object], response_format: ResponseFormat) -> str:
    """Format news search output for an MCP tool."""

    if response_format == ResponseFormat.JSON:
        return to_json(payload)

    lines = [f"# Mining News Search: {payload['query']}", ""]
    lines.append(f"Window: last {payload['days']} days")
    lines.append(f"Source mode: `{payload['source_type']}`")
    if payload["warnings"]:
        lines.append("")
        lines.append("## Warnings")
        lines.extend(f"- {warning}" for warning in payload["warnings"])
    lines.append("")
    lines.append("## Results")
    articles = payload["articles"]
    if not articles:
        lines.append("- No matching articles found.")
    for index, article in enumerate(articles, start=1):
        lines.append(f"{index}. [{article.title}]({article.url})")
        lines.append(f"   - Published: {article.published_at or 'unknown'}")
        lines.append(f"   - Summary: {bullet_escape(article.summary)[:320]}")
    return "\n".join(lines)


def format_article(payload: dict[str, object], response_format: ResponseFormat) -> str:
    """Format article fetch output for an MCP tool."""

    if response_format == ResponseFormat.JSON:
        return to_json(payload)
    article = payload["article"]
    lines = [f"# {article.title}", "", f"Source: [{article.source}]({article.url})"]
    lines.append(f"Source mode: `{payload['source_type']}`")
    if payload["warnings"]:
        lines.append("")
        lines.append("## Warnings")
        lines.extend(f"- {warning}" for warning in payload["warnings"])
    lines.append("")
    lines.append(article.text or article.summary or "No extracted body text.")
    return "\n".join(lines)
