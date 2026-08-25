import pytest

from src.keeper_domain import (
    MIDSEASON_PICKUP,
    RETURNING_KEEPER,
    KeeperDomainRules,
    build_keeper_contract,
)
from src.keeper_economics import project_keeper_economics
from src.league_setup_data import KeeperRecord
from src.strategy_profile import StrategyMode, StrategyProfile


def _strategy(current=0.5, future=0.5):
    return StrategyProfile(
        league_key="league",
        user_key="user",
        mode=StrategyMode.HYBRID,
        current_weight=current,
        future_weight=future,
    )


def _rules(horizon=3, escalation=11, pickup_cost=10):
    return KeeperDomainRules(
        max_keepers=6,
        annual_escalation=escalation,
        midseason_pickup_cost=pickup_cost,
        future_horizon_years=horizon,
    )


def test_three_year_projection_reports_costs_surplus_break_even_and_runway():
    rules = _rules()
    contract = build_keeper_contract(
        KeeperRecord(
            manager_id="team",
            player_name="Veteran",
            cost_basis=RETURNING_KEEPER,
            prior_year_cost=24,
        ),
        rules,
    )

    projection = project_keeper_economics(
        contract=contract,
        rules=rules,
        projected_player_values=(80.0, 60.0, 50.0),
        strategy_profile=_strategy(),
    )

    assert [year.projected_cost for year in projection.years] == [35, 46, 57]
    assert [year.yearly_surplus for year in projection.years] == [45.0, 14.0, -7.0]
    assert [year.cumulative_surplus for year in projection.years] == [45.0, 59.0, 52.0]
    assert projection.cumulative_surplus == 52.0
    assert projection.break_even_year == 3
    assert projection.keeper_runway_years == 2
    assert "break-even year 3" in projection.explanation


def test_two_year_positive_projection_has_full_runway_and_no_break_even():
    rules = _rules(horizon=2, escalation=5)
    contract = build_keeper_contract(
        KeeperRecord(
            manager_id="team",
            player_name="Young Player",
            cost=10,
        ),
        rules,
    )

    projection = project_keeper_economics(
        contract=contract,
        rules=rules,
        projected_player_values=(30.0, 25.0),
        strategy_profile=_strategy(),
    )

    assert [year.projected_cost for year in projection.years] == [10, 15]
    assert projection.break_even_year is None
    assert projection.keeper_runway_years == 2
    assert projection.cumulative_surplus == 30.0


def test_pickup_uses_configured_price_then_transitions_to_custom_escalation():
    rules = _rules(escalation=7, pickup_cost=4)
    contract = build_keeper_contract(
        KeeperRecord(
            manager_id="team",
            player_name="Pickup",
            cost=999,
            cost_basis=MIDSEASON_PICKUP,
        ),
        rules,
    )

    projection = project_keeper_economics(
        contract=contract,
        rules=rules,
        projected_player_values=(30.0, 30.0, 30.0),
        strategy_profile=_strategy(),
    )

    assert contract.current_cost == 4
    assert [year.projected_cost for year in projection.years] == [4, 11, 18]


def test_strategy_adjustment_weights_current_and_future_surplus_explicitly():
    rules = _rules()
    contract = build_keeper_contract(
        KeeperRecord(
            manager_id="team",
            player_name="Strategy Player",
            cost=10,
        ),
        rules,
    )

    projection = project_keeper_economics(
        contract=contract,
        rules=rules,
        projected_player_values=(20.0, 31.0, 42.0),
        strategy_profile=_strategy(current=0.2, future=0.8),
    )

    assert [year.yearly_surplus for year in projection.years] == [10.0, 10.0, 10.0]
    assert [year.strategy_weight for year in projection.years] == [0.2, 0.4, 0.4]
    assert projection.strategy_adjusted_cumulative_surplus == 10.0


def test_projection_rejects_values_that_do_not_match_horizon():
    rules = _rules(horizon=3)
    contract = build_keeper_contract(
        KeeperRecord(
            manager_id="team",
            player_name="Invalid",
            cost=10,
        ),
        rules,
    )

    with pytest.raises(ValueError, match="exactly 3 years"):
        project_keeper_economics(
            contract=contract,
            rules=rules,
            projected_player_values=(20.0, 20.0),
            strategy_profile=_strategy(),
        )

    with pytest.raises(ValueError, match="cannot be negative"):
        project_keeper_economics(
            contract=contract,
            rules=rules,
            projected_player_values=(20.0, -1.0, 20.0),
            strategy_profile=_strategy(),
        )
