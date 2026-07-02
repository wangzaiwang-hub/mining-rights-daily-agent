from mining_daily_agent.prices import get_price_point, get_price_trend


def test_get_price_uses_closest_available_fixture_point() -> None:
    payload = get_price_point("lme copper", "2026-07-02")

    assert payload["price"].commodity == "copper"
    assert payload["price"].date == "2026-07-01"
    assert payload["warnings"]


def test_get_lithium_trend_direction() -> None:
    payload = get_price_trend("lithium", days=7)

    trend = payload["trend"]
    assert trend.commodity == "lithium"
    assert trend.direction == "down"
    assert trend.change_pct < 0
