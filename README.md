# Mining Rights Daily Agent

This repository implements interview task #2: an MCP-based "mining rights daily"
agent that composes three MCP servers into a Markdown briefing workflow.

## What is included

- `mining-news-mcp`: tools `search(query, days)` and `fetch_article(url)`.
- `mineral-pdf-mcp`: tool `extract_resources(pdf_url)` for NI 43-101 style resource tables.
- `lme-price-mcp`: tools `get_price(commodity, date)` and `get_trend(commodity, days)`.
- `mining-daily-agent`: deterministic Agent client that plans tool calls and writes a cited
  Markdown briefing.
- `mcp-config.json`: local stdio MCP configuration for Claude Desktop / Cursor.
- `docker-compose.yml`: one-command demo runner.
- `tests/`: focused unit tests for extraction, price trends, and briefing generation.

## Design choices

The implementation is intentionally conservative. External mining data sources can be unstable,
blocked, or rate limited during a take-home review, so every integration returns explicit source
metadata and warnings. Offline fixtures are marked as `reference_fixture` and are never presented
as live market data.

The agent can run without model API keys. That keeps the 5-minute reviewer path reliable while
still preserving the MCP shape of the solution. If desired, an LLM synthesis layer can be added
behind the existing `generate_briefing` boundary.

See [RUN.md](RUN.md) for setup and validation commands.
