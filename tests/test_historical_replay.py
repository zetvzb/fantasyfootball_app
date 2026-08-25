import pytest

from src.historical_replay import (
    PreSaleRecommendation,
    replay_historical_sales,
)
from src.live_draft import LiveAuctionSale


def _sale(number, player, price):
    return LiveAuctionSale(number, player, "WR", "manager", price)


def test_replay_generates_recommendation_before_each_sale_without_lookahead():
    observed = []

    def recommend(state, nomination):
        observed.append(
            (state.sale_number, len(state.completed_sales), nomination.player_name)
        )
        target = 10 + len(state.completed_sales)
        return PreSaleRecommendation(
            nomination.player_name, target, target + 2, target + 5, "BID"
        )

    result = replay_historical_sales(
        [_sale(2, "Second", 20), _sale(1, "First", 10)],
        recommend,
    )

    assert observed == [(1, 0, "First"), (2, 1, "Second")]
    assert [event.player_name for event in result.evaluations] == ["First", "Second"]
    assert result.mean_absolute_price_error == 4.5
    assert result.hard_cap_coverage == 0.5


def test_replay_supports_skipped_recommendations_and_rejects_duplicate_sales():
    result = replay_historical_sales([_sale(1, "Player", 10)], lambda *_: None)
    assert result.evaluations == ()

    with pytest.raises(ValueError, match="unique sale numbers"):
        replay_historical_sales(
            [_sale(1, "One", 10), _sale(1, "Two", 12)],
            lambda *_: None,
        )


def test_replay_rejects_recommendation_for_a_different_nominee():
    with pytest.raises(ValueError, match="match the nominated player"):
        replay_historical_sales(
            [_sale(1, "One", 10)],
            lambda *_: PreSaleRecommendation("Two", 10, 12, 15, "BID"),
        )
