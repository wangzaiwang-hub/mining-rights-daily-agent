"""Command-line Agent client for the mining rights daily workflow."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from mining_daily_agent.briefing import generate_briefing


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(
        description="Generate a mining rights daily Markdown briefing."
    )
    parser.add_argument(
        "--topic",
        required=True,
        help='Briefing topic, e.g. "Pilbara lithium mine".',
    )
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days.")
    parser.add_argument("--output", help="Optional Markdown output path.")
    return parser


async def run(topic: str, days: int, output: str | None = None) -> str:
    """Run the agent and optionally write the briefing to disk."""

    markdown = await generate_briefing(topic, days=days)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
    return markdown


def main() -> None:
    """CLI entry point."""

    args = build_parser().parse_args()
    markdown = asyncio.run(run(args.topic, args.days, args.output))
    print(markdown)


if __name__ == "__main__":
    main()
