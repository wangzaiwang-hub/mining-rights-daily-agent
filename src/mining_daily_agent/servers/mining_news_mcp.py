"""MCP server exposing mining news tools."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mining_daily_agent.common import ResponseFormat
from mining_daily_agent.news import fetch_article as fetch_article_service
from mining_daily_agent.news import format_article, format_news_search, search_news

mcp = FastMCP("mining_news_mcp")


@mcp.tool(
    name="search",
    annotations={
        "title": "Search Mining News",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def search(
    query: Annotated[str, Field(description="Mining news query, e.g. 'Pilbara lithium'.")],
    days: Annotated[int, Field(description="Lookback window in days.", ge=1, le=90)] = 7,
    limit: Annotated[int, Field(description="Maximum articles to return.", ge=1, le=20)] = 10,
    response_format: Annotated[str, Field(description="'markdown' or 'json'.")] = "markdown",
) -> str:
    """Search recent mining news across configured RSS feeds."""

    payload = await search_news(query=query, days=days, limit=limit)
    return format_news_search(payload, ResponseFormat(response_format))


@mcp.tool(
    name="fetch_article",
    annotations={
        "title": "Fetch Mining Article",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fetch_article(
    url: Annotated[str, Field(description="Article URL from search results.")],
    response_format: Annotated[str, Field(description="'markdown' or 'json'.")] = "markdown",
) -> str:
    """Fetch a mining article and extract readable title/body text."""

    payload = await fetch_article_service(url)
    return format_article(payload, ResponseFormat(response_format))


def main() -> None:
    """Run stdio MCP server."""

    mcp.run()


if __name__ == "__main__":
    main()
