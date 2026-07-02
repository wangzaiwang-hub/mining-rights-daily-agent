import pytest

from mining_daily_agent.briefing import generate_briefing


@pytest.mark.asyncio
async def test_generate_briefing_contains_required_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINING_AGENT_OFFLINE", "1")
    monkeypatch.setenv("REPORT_PDF_URL", "examples/sample_ni43101.txt")

    markdown = await generate_briefing("Pilbara lithium mine", days=7)

    assert "# Mining Rights Daily: Pilbara lithium mine" in markdown
    assert "## News Summary" in markdown
    assert "## Resource Data" in markdown
    assert "## Price Trend" in markdown
    assert "## Sources" in markdown
    assert "reference_fixture" in markdown
