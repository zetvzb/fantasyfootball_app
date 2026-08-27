from types import SimpleNamespace

from src.draft_setup import TeamDraftSetup
from src.historical_market import build_historical_market_model
from src.league_inflation import calculate_live_room_inflation
from src.league_profile import LeagueProfile, RosterRules
from src.league_setup_data import LeagueSetupData
from src.live_draft import LiveAuctionSale, build_live_team_setups
from src.live_learning import build_live_market_calibration
from src.run_hot import detect_run_hot
from src.workbook_enrichment import enrich_setup_from_optional_workbook


def _sale(number, player, manager, price, modeled, position="WR"):
    return LiveAuctionSale(number, player, position, manager, price, modeled)


def test_aggressive_and_passive_room_scenarios_move_calibration_oppositely():
    aggressive = build_live_market_calibration(
        [_sale(index, "A{0}".format(index), "buyer", 30, 20)
         for index in range(1, 7)]
    )
    passive = build_live_market_calibration(
        [_sale(index, "P{0}".format(index), "buyer", 10, 20)
         for index in range(1, 7)]
    )

    assert aggressive.overall.multiplier > 1.0
    assert passive.overall.multiplier < 1.0
    assert aggressive.manager_profiles["buyer"].multiplier > 1.0
    assert passive.manager_profiles["buyer"].multiplier < 1.0


def test_inflated_room_and_position_run_are_detected_together():
    sales = [
        _sale(1, "WR One", "one", 45, 30),
        _sale(2, "WR Two", "two", 30, 20),
    ]
    expected = {
        "wr one": SimpleNamespace(expected_market_value=30),
        "wr two": SimpleNamespace(expected_market_value=20),
    }
    inflation = calculate_live_room_inflation(
        live_sales=sales,
        expected_values=expected,
    )
    opponents = [
        SimpleNamespace(
            manager_id="manager-{0}".format(index),
            cash_strength=0.9,
            likely_positions=("WR",),
            likely_tiers=("starter",),
        )
        for index in range(3)
    ]
    run = detect_run_hot(
        opponent_profiles=opponents,
        available_tier_counts={("WR", "starter"): 2},
    )

    assert inflation.room_inflation_index == 1.5
    assert run.position_pressure["WR"] == 1.0
    assert "cash-rich teams" in run.warnings[0].warning


def test_unused_cash_and_unequal_budgets_preserve_reserve_semantics():
    rich = TeamDraftSetup(
        "rich", 200, roster_size=2, entering_auction_cash=200,
    )
    lean = TeamDraftSetup(
        "lean", 100, roster_size=2, entering_auction_cash=100,
    )
    sales = [
        _sale(1, "Rich One", "rich", 1, 10),
        _sale(2, "Rich Two", "rich", 1, 10),
    ]
    state = build_live_team_setups({"rich": rich, "lean": lean}, sales)

    assert state["rich"].open_roster_spots == 0
    assert state["rich"].live_cash == 198
    assert state["rich"].max_bid == 0
    assert state["lean"].max_bid == 99
    assert state["lean"].required_reserve == 2


def test_no_history_and_no_workbook_remain_operational():
    profile = LeagueProfile(
        league_key="minimal",
        league_name="Minimal",
        season=2026,
        source_mode="manual",
        roster=RosterRules(roster_size=5),
    )
    setup = LeagueSetupData(league_key="minimal")
    workbook = enrich_setup_from_optional_workbook(
        baseline=setup,
        league_profile=profile,
        workbook_path=None,
    )
    historical = build_historical_market_model([], {})

    assert workbook.loaded is False
    assert workbook.error is None
    assert historical.eligible_years == []
    assert historical.league_average_purchase == 0.0
