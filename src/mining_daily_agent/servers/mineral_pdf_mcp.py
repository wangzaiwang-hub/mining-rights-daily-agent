"""MCP server exposing NI 43-101 resource extraction."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mining_daily_agent.common import ResponseFormat
from mining_daily_agent.pdf_resources import extract_resources as extract_resources_service
from mining_daily_agent.pdf_resources import format_resources

mcp = FastMCP("mineral_pdf_mcp")


@mcp.tool(
    name="extract_resources",
    annotations={
        "title": "Extract NI 43-101 Resources",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def extract_resources(
    pdf_url: Annotated[
        str,
        Field(description="HTTP(S) URL or local path to a PDF/text report."),
    ] = "examples/sample_ni43101.txt",
    response_format: Annotated[str, Field(description="'markdown' or 'json'.")] = "markdown",
) -> str:
    """Extract Indicated/Inferred resource rows from an NI 43-101 style report."""

    payload = await extract_resources_service(pdf_url)
    return format_resources(payload, ResponseFormat(response_format))


def main() -> None:
    """Run stdio MCP server."""

    mcp.run()


if __name__ == "__main__":
    main()
