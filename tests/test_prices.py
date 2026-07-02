import pytest

from mining_daily_agent.prices import get_price_point, get_price_trend


@pytest.mark.asyncio
async def test_get_price_uses_live_lme_point() -> None:
    payload = await get_price_point("lme copper", "2026-07-02")

    assert payload["price"].commodity == "copper"
    assert payload["price"].date == "2026-07-01"
    assert payload["price"].source_type == "live_westmetall_lme"


@pytest.mark.asyncio
async def test_get_lithium_trend_uses_live_sunsirs() -> None:
    payload = await get_price_trend("lithium", days=7)

    trend = payload["trend"]
    assert trend.commodity == "lithium"
    assert trend.end.source_type == "live_sunsirs_spot"
