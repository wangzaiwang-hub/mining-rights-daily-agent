"""NI 43-101 style mineral resource extraction."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from mining_daily_agent.common import ResourceEstimate, ResponseFormat, project_root, to_json
from mining_daily_agent.http_client import FetchError, fetch_bytes, is_http_url

DEFAULT_REPORT = project_root() / "examples" / "sample_ni43101.txt"

RESOURCE_PATTERN = re.compile(
    r"(?P<category>indicated|inferred)\s+"
    r"(?P<ore>[\d,.]+)\s*(?:mt|million\s+tonnes?)\s+"
    r"(?P<grade>[\d,.]+)\s*(?P<grade_unit>g/t\s+au|%?\s*cu|%?\s*li2o|g/t|%)\s+"
    r"(?P<metal>[\d,.]+)\s*(?P<metal_unit>mt\s+lce|moz|koz|oz|kt|t)",
    re.IGNORECASE,
)


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def _normal_unit(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.upper().replace(" ", "").split())


def extract_text_from_pdf_bytes(payload: bytes) -> list[tuple[int, str]]:
    """Extract page text from a PDF payload."""

    reader = PdfReader(BytesIO(payload))
    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        pages.append((index, page.extract_text() or ""))
    return pages


def extract_rows_from_pages(pages: list[tuple[int, str]]) -> list[ResourceEstimate]:
    """Extract indicated/inferred resource rows from page text."""

    estimates: list[ResourceEstimate] = []
    for page_number, text in pages:
        compact = re.sub(r"\s+", " ", text)
        for match in RESOURCE_PATTERN.finditer(compact):
            evidence = match.group(0).strip()
            estimates.append(
                ResourceEstimate(
                    category=match.group("category").title(),
                    ore_mt=_number(match.group("ore")),
                    grade=_number(match.group("grade")),
                    grade_unit=_normal_unit(match.group("grade_unit")),
                    metal=_number(match.group("metal")),
                    metal_unit=_normal_unit(match.group("metal_unit")),
                    page=page_number,
                    evidence=evidence,
                )
            )
    return estimates


async def extract_resources(pdf_url: str | None = None) -> dict[str, object]:
    """Extract mineral resource rows from an HTTP/local PDF or text file."""

    target = pdf_url or str(DEFAULT_REPORT)
    warnings: list[str] = []
    source_type = "live_pdf" if is_http_url(target) else "local_file"

    try:
        payload = await fetch_bytes(target, ttl_seconds=24 * 3600)
    except FetchError as exc:
        if Path(DEFAULT_REPORT).exists():
            warnings.append(str(exc))
            warnings.append("Fell back to examples/sample_ni43101.txt.")
            target = str(DEFAULT_REPORT)
            payload = Path(DEFAULT_REPORT).read_bytes()
            source_type = "reference_fixture"
        else:
            raise

    if payload[:4] == b"%PDF":
        pages = extract_text_from_pdf_bytes(payload)
    else:
        text = payload.decode("utf-8", errors="replace")
        pages = [(1, text)]
        if "sample_ni43101" in target:
            source_type = "reference_fixture"

    estimates = extract_rows_from_pages(pages)
    abstain = len(estimates) == 0
    if abstain:
        warnings.append(
            "No Indicated/Inferred resource rows matched the extraction pattern; "
            "mark for manual review."
        )

    return {
        "source": target,
        "source_type": source_type,
        "abstain": abstain,
        "estimates": estimates,
        "warnings": warnings,
    }


def format_resources(payload: dict[str, object], response_format: ResponseFormat) -> str:
    """Format resource extraction output for an MCP tool."""

    if response_format == ResponseFormat.JSON:
        return to_json(payload)

    lines = ["# Mineral Resource Extraction", ""]
    lines.append(f"Source: `{payload['source']}`")
    lines.append(f"Source mode: `{payload['source_type']}`")
    lines.append(f"Abstain: `{payload['abstain']}`")
    if payload["warnings"]:
        lines.append("")
        lines.append("## Warnings")
        lines.extend(f"- {warning}" for warning in payload["warnings"])
    lines.append("")
    lines.append("## Extracted Rows")
    estimates = payload["estimates"]
    if not estimates:
        lines.append("- No rows extracted.")
    for row in estimates:
        page = f"page {row.page}" if row.page else "unknown page"
        lines.append(
            f"- **{row.category}** ({page}): ore {row.ore_mt} Mt, "
            f"grade {row.grade} {row.grade_unit}, metal {row.metal} {row.metal_unit}"
        )
        lines.append(f"  - Evidence: `{row.evidence}`")
    return "\n".join(lines)
