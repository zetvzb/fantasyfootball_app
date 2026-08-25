from src.keeper_optimizer import (
    KeeperOptimizationInput,
    optimize_keeper_combinations,
)
from src.keeper_recommendation import (
    KeeperDecision,
    KeeperRecommendation,
)
from src.strategy_profile import StrategyMode, StrategyProfile


def _strategy():
    return StrategyProfile(
        league_key="league",
        user_key="user",
        mode=StrategyMode.HYBRID,
        current_weight=0.5,
        future_weight=0.5,
    )


def _recommendation(
    name,
    *,
    position="WR",
    cost=10,
    current=80,
    future=80,
    surplus=20,
    roster_fit=0.8,
):
    return KeeperRecommendation(
        manager_id="team",
        player_name=name,
        position=position,
        decision=KeeperDecision.KEEP,
        current_value=float(current),
        future_value=float(future),
        age=25,
        age_adjustment=1.0,
        age_adjusted_future_value=float(future),
        cost=int(cost),
        auction_value=float(cost + surplus),
        surplus=float(surplus),
        scarcity=0.8,
        roster_fit=float(roster_fit),
        strategy_score=75.0,
        reason_codes=(),
        explanation="test",
    )


def _inputs(recommendations, **overrides):
    values = {
        "manager_id": "team",
        "recommendations": tuple(recommendations),
        "strategy_profile": _strategy(),
        "pre_keeper_budget": 400,
        "roster_size": 10,
        "minimum_bid": 1,
        "max_keepers": 6,
        "starting_lineup": ("QB", "RB", "WR", "TE", "FLEX"),
    }
    values.update(overrides)
    return KeeperOptimizationInput(**values)


def test_five_beats_six_when_sixth_keeper_destroys_surplus_and_cash():
    recommendations = [
        _recommendation("Good {0}".format(index))
        for index in range(5)
    ]
    recommendations.append(
        _recommendation(
            "Bad Sixth",
            cost=60,
            current=10,
            future=10,
            surplus=-50,
        )
    )

    result = optimize_keeper_combinations(_inputs(recommendations))

    assert [scenario.keeper_count for scenario in result.scenarios] == [4, 5, 6]
    assert result.recommended_scenario.keeper_count == 5
    assert "Bad Sixth" not in result.recommended_scenario.keeper_names
    five = result.scenarios[1]
    six = result.scenarios[2]
    assert five.keeper_spend == 50
    assert five.remaining_cash == 350
    assert five.remaining_roster_spots == 5
    assert five.minimum_reserve == 5
    assert five.discretionary_cash == 345
    assert five.current_value == 400
    assert five.future_value == 400
    assert five.surplus == 100
    assert five.objective_score > six.objective_score


def test_six_beats_five_when_every_keeper_has_strong_surplus():
    recommendations = [
        _recommendation("Strong {0}".format(index))
        for index in range(6)
    ]

    result = optimize_keeper_combinations(_inputs(recommendations))

    five = result.scenarios[1]
    six = result.scenarios[2]
    assert result.recommended_scenario.keeper_count == 6
    assert six.surplus == 120
    assert five.opportunity_cost == 20
    assert six.opportunity_cost == 0
    assert six.objective_score > five.objective_score


def test_optimizer_evaluates_combinations_instead_of_greedy_individual_order():
    recommendations = [
        _recommendation("Quarterback", position="QB", current=50, future=50),
        _recommendation("Running Back", position="RB", current=50, future=50),
        _recommendation("Wide Receiver", position="WR", current=50, future=50),
        _recommendation("Tight End", position="TE", current=50, future=50),
        _recommendation("Extra Running Back", position="RB", current=51, future=51),
    ]

    result = optimize_keeper_combinations(
        _inputs(recommendations, target_counts=(4,))
    )

    selected = result.recommended_scenario.keeper_names
    assert "Tight End" in selected
    assert len(
        {
            recommendation.position
            for recommendation in recommendations
            if recommendation.player_name in selected
        }
    ) == 4
    assert result.combinations_evaluated == 5


def test_max_keeper_rule_filters_illegal_six_keeper_scenario():
    recommendations = [
        _recommendation("Candidate {0}".format(index))
        for index in range(6)
    ]

    result = optimize_keeper_combinations(
        _inputs(recommendations, max_keepers=5)
    )

    assert [scenario.keeper_count for scenario in result.scenarios] == [4, 5]


def test_minimum_bid_reserve_filters_cash_infeasible_combinations():
    recommendations = [
        _recommendation(
            "Expensive {0}".format(index),
            cost=16,
            surplus=5,
        )
        for index in range(6)
    ]

    result = optimize_keeper_combinations(
        _inputs(
            recommendations,
            pre_keeper_budget=100,
            roster_size=10,
            minimum_bid=2,
        )
    )

    assert [scenario.keeper_count for scenario in result.scenarios] == [4, 5]
    assert any("6-keeper" in warning for warning in result.warnings)


def test_unused_keeper_slots_are_roster_spots_not_bonus_money():
    recommendations = [
        _recommendation("Keeper {0}".format(index), cost=10)
        for index in range(6)
    ]

    result = optimize_keeper_combinations(_inputs(recommendations))
    four, unused_five, six = result.scenarios

    assert four.remaining_cash == 360
    assert six.remaining_cash == 340
    assert four.remaining_roster_spots == six.remaining_roster_spots + 2
    assert four.minimum_reserve == six.minimum_reserve + 2


def test_result_is_deterministic_for_same_candidate_set():
    recommendations = [
        _recommendation("Keeper {0}".format(index))
        for index in range(7)
    ]
    inputs = _inputs(recommendations)

    assert optimize_keeper_combinations(inputs) == optimize_keeper_combinations(
        inputs
    )
