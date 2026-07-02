import pytest

from mining_daily_agent.news import fetch_article, search_news


@pytest.mark.asyncio
async def test_search_news_fixture_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINING_AGENT_OFFLINE", "1")
    monkeypatch.setenv("MINING_AGENT_ALLOW_FIXTURES", "1")

    payload = await search_news("Pilbara lithium", days=7)

    assert payload["source_type"] == "reference_fixture"
    assert payload["count"] >= 1


@pytest.mark.asyncio
async def test_fetch_fixture_article(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINING_AGENT_ALLOW_FIXTURES", "1")
    payload = await fetch_article("fixture://news/pilbara-lithium-resource-review")

    assert payload["source_type"] == "reference_fixture"
    assert "Pilbara" in payload["article"].title
