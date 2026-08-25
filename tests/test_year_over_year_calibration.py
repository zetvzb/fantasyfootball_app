from src.live_draft import LiveAuctionSale
from src.year_over_year_calibration import (
    CompletedDraftSeason,
    build_year_over_year_calibration,
)


def _sale(number, player, position, manager, price, modeled):
    return LiveAuctionSale(number, player, position, manager, price, modeled)


def test_completed_drafts_calibrate_all_required_market_dimensions():
    calibration = build_year_over_year_calibration(
        [
            CompletedDraftSeason(
                2025,
                (
                    _sale(1, "WR One", "WR", "aggressive", 30, 20),
                    _sale(2, "RB One", "RB", "passive", 10, 10),
                ),
                {"rankings": {"WR One": 25, "RB One": 12}},
            ),
            CompletedDraftSeason(
                2026,
                (
                    _sale(1, "WR Two", "WR", "aggressive", 40, 25),
                    _sale(2, "RB Two", "RB", "passive", 20, 20),
                ),
                {"rankings": {"WR Two": 35, "RB Two": 18}},
            ),
        ]
    )

    assert [season.season for season in calibration.seasons] == [2025, 2026]
    assert calibration.inflation_multiplier > 1.0
    assert calibration.scarcity_multipliers["WR"] > calibration.scarcity_multipliers["RB"]
    assert calibration.manager_behavior["aggressive"].aggressiveness_multiplier > 1.0
    assert calibration.source_bias["rankings"] == 2.5
    assert calibration.price_distributions["ALL"].median == 25.0


def test_calibrated_price_applies_learned_adjustments_and_empty_history_is_neutral():
    empty = build_year_over_year_calibration([])
    assert empty.calibrated_price(20, "WR") == 20.0

    learned = build_year_over_year_calibration(
        [
            CompletedDraftSeason(
                2026,
                (_sale(1, "Player", "WR", "manager", 30, 20),),
                {"source": {"Player": 25}},
            )
        ]
    )
    assert learned.calibrated_price(20, "WR", "manager", "source") > 20
