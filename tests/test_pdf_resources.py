from pathlib import Path

import pytest

from mining_daily_agent.pdf_resources import extract_resources


@pytest.mark.asyncio
async def test_extract_resources_from_sample_text() -> None:
    payload = await extract_resources(str(Path("examples/sample_ni43101.txt")))

    assert payload["abstain"] is False
    categories = {row.category for row in payload["estimates"]}
    assert {"Indicated", "Inferred"} <= categories
    assert any(row.ore_mt == 214.0 and row.metal_unit == "MTLCE" for row in payload["estimates"])
    assert any(row.grade_unit == "G/TAU" for row in payload["estimates"])
