"""MCP server exposing commodity price tools."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mining_daily_agent.common import ResponseFormat
from mining_daily_agent.prices import format_price, format_trend, get_price_point, get_price_trend

mcp = FastMCP("lme_price_mcp")


@mcp.tool(
    name="get_price",
    annotations={
        "title": "Get Commodity Price",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def get_price(
    commodity: Annotated[str, Field(description="Commodity, e.g. copper, zinc, nickel, lithium.")],
    date: Annotated[str, Field(description="Requested date in YYYY-MM-DD format.")] = "",
    response_format: Annotated[str, Field(description="'markdown' or 'json'.")] = "markdown",
) -> str:
    """Get the closest available commodity price on or before a requested date."""

    payload = get_price_point(commodity, date or None)
    return format_price(payload, ResponseFormat(response_format))


@mcp.tool(
    name="get_trend",
    annotations={
        "title": "Get Commodity Trend",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def get_trend(
    commodity: Annotated[str, Field(description="Commodity, e.g. copper, zinc, nickel, lithium.")],
    days: Annotated[int, Field(description="Lookback window in days.", ge=2, le=365)] = 30,
    response_format: Annotated[str, Field(description="'markdown' or 'json'.")] = "markdown",
) -> str:
    """Get commodity price trend over the available lookback window."""

    payload = get_price_trend(commodity, days=days)
    return format_trend(payload, ResponseFormat(response_format))


def main() -> None:
    """Run stdio MCP server."""

    mcp.run()


if __name__ == "__main__":
    main()
