from dataclasses import dataclass
from types import SimpleNamespace

from src.historical_market import MarketAdjustedValue
from src.scenario_market_values import (
    apply_scenario_fair_values,
    build_scenario_feature_rows,
    contender_state,
)
from src.scenario_price_inference import ScenarioPricePrediction


@dataclass
class _Prediction:
    low: float
    predicted_price: float
    high: float
    model_version: str = "test-model"


class _FakeService:
    def __init__(self, price):
        self._price = price
        self.artifact_path = SimpleNamespace(is_file=lambda: True)

    def predict(self, row):
        if row is None:
            return None
        return ScenarioPricePrediction(
            low=self._price - 5,
            predicted_price=self._price,
            high=self._price + 5,
            model_version="test-model",
        )


def _team(manager_id, cash, spots):
    return SimpleNamespace(
        manager_id=manager_id,
        live_cash=cash,
        auction_cash=cash,
        open_roster_spots=spots,
        starting_open_roster_spots=12,
        discretionary_cash=max(0, cash - spots),
        max_bid=max(0, cash - max(0, spots - 1)),
    )


def test_contender_state_picks_a_cash_rich_bidder():
    teams = [_team("a", 20, 10), _team("b", 200, 10), _team("c", 120, 10)]
    state = contender_state(teams)
    assert state["cash"] == 200  # 75th percentile of cash-per-spot


def test_feature_rows_skip_unranked_and_carry_stage():
    teams = [_team("a", 100, 10), _team("b", 150, 10)]
    players = [
        SimpleNamespace(player_name="Ranked Guy", position="WR"),
        SimpleNamespace(player_name="Unranked Guy", position="RB"),
    ]
    fp_index = {"ranked guy": SimpleNamespace(half_ecr=15.0, half_position_rank=6.0)}
    sales = [SimpleNamespace(position="WR", price=40)]
    rows = build_scenario_feature_rows(players, teams, sales, fp_index)
    assert set(rows) == {"ranked guy"}
    row = rows["ranked guy"]
    assert row["position_sales_before"] == 1
    assert row["position_spend_before"] == 40
    assert 0.0 < row["auction_stage"] < 1.0


def test_apply_blends_prediction_into_expected_market_value():
    market = [
        MarketAdjustedValue(
            player_name="Ranked Guy",
            position="WR",
            baseline_value=10.0,
            historical_expected_price=12.0,
            historical_sample_size=5,
            historical_weight=0.3,
            expected_market_value=12.0,
        )
    ]
    rows = {"ranked guy": {"historical_overall_rank": 15.0, "position": "WR"}}
    blended, index = apply_scenario_fair_values(
        market, rows, ml_weight=0.5, service=_FakeService(30.0)
    )
    # 0.5 * 30 (ML) + 0.5 * 12 (rankings expected_market_value) = 21
    assert blended[0].expected_market_value == 21.0
    assert index["ranked guy"]["ml_predicted_price"] == 30.0
    assert index["ranked guy"]["rankings_value"] == 12.0


def test_apply_is_noop_without_rows():
    market = [
        MarketAdjustedValue("X", "WR", 10.0, None, 0, 0.0, 10.0),
    ]
    blended, index = apply_scenario_fair_values(
        market, {}, ml_weight=0.6, service=_FakeService(30.0)
    )
    assert blended == market
    assert index == {}
