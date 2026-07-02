# RUN

## 1. Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## 2. Generate a briefing

```powershell
python -m mining_daily_agent.agent --topic "Pilbara lithium mine" --days 7 --output examples/pilbara_report.md
```

Open `examples/pilbara_report.md` to inspect the generated Markdown report.

## 3. Run tests

```powershell
pytest
```

## 4. Run the MCP servers

Each MCP server uses stdio transport:

```powershell
python -m mining_daily_agent.servers.mining_news_mcp
python -m mining_daily_agent.servers.mineral_pdf_mcp
python -m mining_daily_agent.servers.lme_price_mcp
```

Use `mcp-config.json` as the Claude Desktop / Cursor config template. Update the absolute project
path if you clone the repository somewhere else.

## 5. Docker path

```powershell
docker compose up --build agent-demo
```

This writes the demo briefing to `/app/examples/pilbara_report.md` inside the container and prints
it to stdout.

## Data configuration

Optional environment variables:

- `MINING_AGENT_OFFLINE=1`: force fixture mode for repeatable demos.
- `MINING_AGENT_ALLOW_FIXTURES=1`: allow reference fixture fallback when live sources have no match.
- `MINING_NEWS_FEEDS`: comma-separated RSS feed URLs. Defaults to `https://www.mining.com/feed/`.
- `REPORT_PDF_URL`: URL or local path to a public mineral resource PDF/text file. Defaults to
  Pilbara Minerals' 2025 annual report.
- `PRICE_CSV_DIR`: directory containing `copper.csv`, `zinc.csv`, etc. with columns
  `date,close,source_url`. Optional; live Westmetall/SunSirs sources are used first when available.
- `MINING_AGENT_CACHE_DIR`: cache directory. Defaults to `.cache/mining-daily-agent`.
