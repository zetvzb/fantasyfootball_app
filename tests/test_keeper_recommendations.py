import pytest

from src.fantasypros_intelligence import FantasyProsPlayerIntelligence
from src.keeper_domain import KeeperContract
from src.keeper_recommendation import (
    KeeperDecision,
    KeeperReasonCode,
    KeeperRecommendationInput,
    build_keeper_recommendations,
    keeper_age_adjustment,
    recommend_keeper,
)
from src.league_profile import (
    AuctionRules,
    KeeperRules,
    LeagueProfile,
    RosterRules,
)
from src.league_setup_data import KeeperRecord
from src.strategy_profile import StrategyMode, StrategyProfile
from src.valuation import PlayerValue


def _strategy(mode=StrategyMode.HYBRID, current=0.5, future=0.5):
    return StrategyProfile(
        league_key="league",
        user_key="user",
        mode=mode,
        current_weight=current,
        future_weight=future,
    )


def _contract(cost=10, position="RB", future_values=()):
    return KeeperContract(
        manager_id="team",
        player_name="Test Player",
        position=position,
        cost_basis="explicit",
        current_cost=cost,
        prior_year_cost=None,
        future_horizon_years=3,
        future_values=future_values,
    )


def _input(**overrides):
    values = {
        "contract": _contract(),
        "strategy_profile": _strategy(),
        "position": "RB",
        "age": 22,
        "current_value": 85.0,
        "future_value": 80.0,
        "scarcity": 0.90,
        "roster_fit": 1.0,
        "auction_budget": 400,
        "minimum_bid": 1,
    }
    values.update(overrides)
    return KeeperRecommendationInput(**values)


def _fantasypros(name, position, dynasty_rank):
    return FantasyProsPlayerIntelligence(
        fantasypros_id=name,
        player_name=name,
        position=position,
        nfl_team=None,
        half_ecr=None,
        half_position_rank=None,
        dynasty_ecr=dynasty_rank,
        dynasty_position_rank=None,
        adp=None,
        ecr_min=None,
        ecr_max=None,
        ecr_avg=None,
        ecr_std=None,
    )


def _league_profile(escalation=11, pickup_cost=10, horizon=3):
    return LeagueProfile(
        league_key="league",
        league_name="Test League",
        season=2026,
        source_mode="manual",
        roster=RosterRules(
            roster_size=10,
            starting_lineup=("QB", "RB", "RB", "WR", "WR", "TE", "FLEX"),
        ),
        auction=AuctionRules(base_budget=400, minimum_bid=1),
        keepers=KeeperRules(
            enabled=True,
            max_keepers=6,
            escalation=escalation,
            midseason_pickup_cost=pickup_cost,
            future_horizon_years=horizon,
        ),
    )


def test_high_value_young_keeper_has_typed_keep_recommendation_and_reasons():
    recommendation = recommend_keeper(_input())

    assert recommendation.decision is KeeperDecision.KEEP
    assert recommendation.current_value == 85.0
    assert recommendation.future_value == 80.0
    assert recommendation.age_adjustment == 1.12
    assert recommendation.age_adjusted_future_value == 89.6
    assert recommendation.cost == 10
    assert recommendation.auction_value > recommendation.cost
    assert recommendation.surplus > 0
    assert recommendation.scarcity == 0.9
    assert recommendation.roster_fit == 1.0
    assert recommendation.strategy_score > 60
    assert KeeperReasonCode.POSITIVE_SURPLUS in recommendation.reason_codes
    assert KeeperReasonCode.AGE_UPSIDE in recommendation.reason_codes
    assert KeeperReasonCode.POSITION_SCARCITY in recommendation.reason_codes
    assert "strategy score" in recommendation.explanation
    assert recommendation.economics is not None
    assert recommendation.economics.horizon_years == 3
    assert len(recommendation.economics.years) == 3
    assert recommendation.economics.years[0].projected_cost == 10
    assert recommendation.economics.years[1].projected_cost == 21


def test_age_adjustment_is_position_specific_and_reduces_old_rb_future_value():
    assert keeper_age_adjustment("QB", 34) == 0.90
    assert keeper_age_adjustment("RB", 22) == 1.12
    assert keeper_age_adjustment("RB", 30) == pytest.approx(0.70)
    assert keeper_age_adjustment("WR", 25) == 1.03
    assert keeper_age_adjustment("TE", None) == 1.0

    young = recommend_keeper(_input(age=22))
    old = recommend_keeper(_input(age=30))

    assert young.age_adjusted_future_value > old.age_adjusted_future_value
    assert young.auction_value > old.auction_value
    assert KeeperReasonCode.AGE_DECLINE in old.reason_codes


def test_strategy_weights_change_numeric_score_without_changing_raw_inputs():
    win_now = recommend_keeper(
        _input(
            strategy_profile=_strategy(
                StrategyMode.WIN_NOW,
                current=0.80,
                future=0.20,
            ),
            current_value=90,
            future_value=30,
            age=None,
        )
    )
    win_later = recommend_keeper(
        _input(
            strategy_profile=_strategy(
                StrategyMode.WIN_LATER,
                current=0.20,
                future=0.80,
            ),
            current_value=90,
            future_value=30,
            age=None,
        )
    )

    assert win_now.current_value == win_later.current_value == 90
    assert win_now.future_value == win_later.future_value == 30
    assert win_now.auction_value == win_later.auction_value
    assert win_now.strategy_score > win_later.strategy_score


def test_expensive_low_value_keeper_is_a_deterministic_pass():
    inputs = _input(
        contract=_contract(cost=100),
        current_value=15,
        future_value=10,
        scarcity=0.1,
        roster_fit=0.45,
        age=30,
    )

    first = recommend_keeper(inputs)
    second = recommend_keeper(inputs)

    assert first == second
    assert first.decision is KeeperDecision.PASS
    assert first.surplus < 0
    assert KeeperReasonCode.NEGATIVE_SURPLUS in first.reason_codes


def test_missing_optional_value_inputs_are_explicit_reason_codes():
    recommendation = recommend_keeper(
        _input(
            current_value=0,
            future_value=0,
            has_current_data=False,
            has_future_data=False,
        )
    )

    assert KeeperReasonCode.MISSING_CURRENT_DATA in recommendation.reason_codes
    assert KeeperReasonCode.MISSING_FUTURE_DATA in recommendation.reason_codes


def test_repository_adapter_builds_sorted_recommendations_from_real_models():
    keepers = [
        KeeperRecord(
            manager_id="team",
            player_name="Young Star",
            position="WR",
            cost=12,
            status="candidate",
            sleeper_player_id="p1",
        ),
        KeeperRecord(
            manager_id="team",
            player_name="Veteran",
            position="WR",
            cost=40,
            status="candidate",
            sleeper_player_id="p2",
        ),
    ]
    player_values = [
        PlayerValue("Young Star", "WR", 300, 200, 100, 1),
        PlayerValue("Veteran", "WR", 220, 200, 20, 20),
    ]
    fantasypros = {
        "young star": _fantasypros("Young Star", "WR", 1),
        "veteran": _fantasypros("Veteran", "WR", 100),
    }
    sleeper_players = {
        "p1": {"full_name": "Young Star", "position": "WR", "age": 23},
        "p2": {"full_name": "Veteran", "position": "WR", "age": 31},
    }

    batch = build_keeper_recommendations(
        keeper_records=keepers,
        league_profile=_league_profile(),
        strategy_profile=_strategy(),
        player_values=player_values,
        fantasypros_index=fantasypros,
        sleeper_players=sleeper_players,
        auction_budget=400,
    )

    assert batch.warnings == ()
    assert [item.player_name for item in batch.recommendations] == [
        "Young Star",
        "Veteran",
    ]
    assert batch.recommendations[0].age == 23
    assert batch.recommendations[0].current_value == 100
    assert batch.recommendations[0].future_value == 100
    assert batch.recommendations[0].roster_fit == 1.0


def test_explicit_future_hooks_override_rank_derived_future_value():
    keeper = KeeperRecord(
        manager_id="team",
        player_name="Hook Player",
        position="RB",
        cost=10,
        future_values=(80.0, 70.0, None),
    )
    batch = build_keeper_recommendations(
        keeper_records=[keeper],
        league_profile=_league_profile(),
        strategy_profile=_strategy(),
        player_values=[],
        fantasypros_index={
            "hook player": _fantasypros("Hook Player", "RB", 500),
        },
        sleeper_players={},
        auction_budget=400,
    )

    assert batch.recommendations[0].future_value == 75.0


def test_adapter_passes_custom_pickup_and_escalation_rules_to_economics():
    keeper = KeeperRecord(
        manager_id="team",
        player_name="Pickup Player",
        position="RB",
        cost=999,
        cost_basis="midseason_pickup",
    )

    batch = build_keeper_recommendations(
        keeper_records=[keeper],
        league_profile=_league_profile(escalation=7, pickup_cost=4),
        strategy_profile=_strategy(),
        player_values=[],
        fantasypros_index={},
        sleeper_players={},
        auction_budget=400,
    )

    economics = batch.recommendations[0].economics
    assert economics is not None
    assert [year.projected_cost for year in economics.years] == [4, 11, 18]


def test_invalid_keeper_cost_is_reported_without_losing_valid_results():
    records = [
        KeeperRecord(
            manager_id="team",
            player_name="Missing Cost",
            position="RB",
            cost=None,
        ),
        KeeperRecord(
            manager_id="team",
            player_name="Valid Keeper",
            position="WR",
            cost=5,
        ),
    ]

    batch = build_keeper_recommendations(
        keeper_records=records,
        league_profile=_league_profile(),
        strategy_profile=_strategy(),
        player_values=[],
        fantasypros_index={},
        sleeper_players={},
        auction_budget=400,
    )

    assert [item.player_name for item in batch.recommendations] == [
        "Valid Keeper"
    ]
    assert "Missing Cost" in batch.warnings[0]


def test_adapter_rejects_strategy_from_another_league():
    strategy = StrategyProfile(
        league_key="other-league",
        user_key="user",
        mode=StrategyMode.HYBRID,
        current_weight=0.5,
        future_weight=0.5,
    )

    with pytest.raises(ValueError, match="does not match"):
        build_keeper_recommendations(
            keeper_records=[],
            league_profile=_league_profile(),
            strategy_profile=strategy,
            player_values=[],
            fantasypros_index={},
            sleeper_players={},
            auction_budget=400,
        )
