from src.college_domain import CollegeDomainRules
from src.college_promotion_recommendation import (
    CollegePromotionDecision,
    CollegePromotionInput,
    CollegePromotionReasonCode,
    build_college_promotion_recommendations,
    recommend_college_promotion,
)
from src.league_profile import (
    AuctionRules,
    CollegeRules,
    KeeperRules,
    LeagueProfile,
    RosterRules,
)
from src.league_setup_data import CollegeRight
from src.strategy_profile import StrategyMode, StrategyProfile
from src.valuation import PlayerValue


def _rules(enabled=True, capacity=6):
    return CollegeDomainRules(
        enabled=enabled,
        max_college_players=capacity if enabled else 0,
        draft_rounds=3 if enabled else 0,
        eligibility_source="manual",
        college_pick_trading_enabled=True,
        pre_draft_promotion_cost=0,
        during_draft_promotion_cost=0,
    )


def _strategy():
    return StrategyProfile(
        league_key="league",
        user_key="user",
        mode=StrategyMode.HYBRID,
        current_weight=0.5,
        future_weight=0.5,
    )


def _right(**overrides):
    values = {
        "manager_id": "team",
        "player_name": "Developmental Player",
        "position": "WR",
        "status": "in_nfl",
        "eligibility_status": "eligible",
        "promotion_status": "taxi",
    }
    values.update(overrides)
    return CollegeRight(**values)


def _input(**overrides):
    values = {
        "right": _right(),
        "rules": _rules(),
        "strategy_profile": _strategy(),
        "nfl_role_opportunity": 0.5,
        "draft_capital": 0.5,
        "current_projected_production": 50.0,
        "future_value": 50.0,
        "age": 22,
        "depth_chart_status": 0.5,
        "roster_need": 0.5,
        "promotion_timing": 1.0,
        "taxi_opportunity_cost": 50.0,
        "college_roster_count": 3,
    }
    values.update(overrides)
    return CollegePromotionInput(**values)


def test_clear_promote_case_uses_strong_current_and_future_signals():
    recommendation = recommend_college_promotion(
        _input(
            nfl_role_opportunity=1.0,
            draft_capital=1.0,
            current_projected_production=90.0,
            future_value=90.0,
            age=21,
            depth_chart_status=1.0,
            roster_need=1.0,
            taxi_opportunity_cost=90.0,
            college_roster_count=6,
        )
    )

    assert recommendation.decision is CollegePromotionDecision.PROMOTE_NOW
    assert recommendation.score >= 65
    assert CollegePromotionReasonCode.NFL_ROLE_READY in recommendation.reason_codes
    assert CollegePromotionReasonCode.CURRENT_PRODUCTION in recommendation.reason_codes
    assert CollegePromotionReasonCode.FUTURE_UPSIDE in recommendation.reason_codes
    assert CollegePromotionReasonCode.COLLEGE_CAPACITY_PRESSURE in (
        recommendation.reason_codes
    )
    assert "score" in recommendation.explanation


def test_clear_taxi_case_preserves_development_time():
    recommendation = recommend_college_promotion(
        _input(
            nfl_role_opportunity=0.10,
            draft_capital=0.10,
            current_projected_production=10.0,
            future_value=10.0,
            depth_chart_status=0.10,
            roster_need=0.10,
            taxi_opportunity_cost=10.0,
            college_roster_count=1,
        )
    )

    assert recommendation.decision is CollegePromotionDecision.LEAVE_ON_TAXI
    assert recommendation.score <= 42
    assert CollegePromotionReasonCode.NEEDS_DEVELOPMENT_TIME in (
        recommendation.reason_codes
    )


def test_not_eligible_case_is_a_hard_rule_not_a_low_numeric_score():
    recommendation = recommend_college_promotion(
        _input(
            right=_right(eligibility_status="ineligible"),
            nfl_role_opportunity=1.0,
            current_projected_production=100.0,
            future_value=100.0,
        )
    )

    assert recommendation.decision is CollegePromotionDecision.NOT_ELIGIBLE
    assert recommendation.score == 0
    assert recommendation.reason_codes == (
        CollegePromotionReasonCode.INELIGIBLE_BY_RULE,
    )


def test_no_devy_league_returns_not_eligible_without_scoring_player_up():
    recommendation = recommend_college_promotion(
        _input(
            rules=_rules(enabled=False),
            nfl_role_opportunity=1.0,
            current_projected_production=100.0,
            future_value=100.0,
        )
    )

    assert recommendation.decision is CollegePromotionDecision.NOT_ELIGIBLE
    assert recommendation.reason_codes == (
        CollegePromotionReasonCode.NO_DEVY_SYSTEM,
    )


def test_full_college_roster_can_move_borderline_player_to_promote():
    base = {
        "nfl_role_opportunity": 0.70,
        "draft_capital": 0.70,
        "current_projected_production": 60.0,
        "future_value": 60.0,
        "age": 23,
        "depth_chart_status": 0.60,
        "roster_need": 0.60,
        "taxi_opportunity_cost": 50.0,
    }
    open_capacity = recommend_college_promotion(
        _input(college_roster_count=1, **base)
    )
    full_capacity = recommend_college_promotion(
        _input(college_roster_count=6, **base)
    )

    assert open_capacity.decision is CollegePromotionDecision.BORDERLINE
    assert full_capacity.decision is CollegePromotionDecision.PROMOTE_NOW
    assert full_capacity.score > open_capacity.score
    assert CollegePromotionReasonCode.COLLEGE_CAPACITY_PRESSURE in (
        full_capacity.reason_codes
    )


def _profile(enabled=True):
    return LeagueProfile(
        league_key="league",
        league_name="League",
        season=2026,
        source_mode="manual",
        roster=RosterRules(
            roster_size=10,
            starting_lineup=("QB", "RB", "WR", "TE"),
        ),
        auction=AuctionRules(base_budget=400, minimum_bid=1),
        keepers=KeeperRules(
            enabled=True,
            max_keepers=6,
            escalation=11,
            future_horizon_years=3,
        ),
        college=CollegeRules(
            enabled=enabled,
            max_college_players=6 if enabled else 0,
            draft_rounds=3 if enabled else 0,
            eligibility_source="manual",
            next_year_keeper_cost=10 if enabled else None,
        ),
    )


def test_repository_adapter_uses_live_signals_and_post_promotion_economics():
    batch = build_college_promotion_recommendations(
        college_rights=(
            _right(
                player_name="Ready Prospect",
                sleeper_player_id="p1",
                nfl_draft_round=1,
                future_values=(90.0, 85.0, 80.0),
            ),
        ),
        league_profile=_profile(),
        strategy_profile=_strategy(),
        player_values=(
            PlayerValue("Ready Prospect", "WR", 300.0, 200.0, 100.0, 1),
        ),
        fantasypros_index={},
        sleeper_players={
            "p1": {
                "full_name": "Ready Prospect",
                "position": "WR",
                "team": "CHI",
                "active": True,
                "age": 21,
                "depth_chart_order": 1,
            }
        },
        current_roster_positions=("QB", "RB"),
        auction_budget=400,
    )

    recommendation = batch.recommendations[0]
    assert recommendation.decision is CollegePromotionDecision.PROMOTE_NOW
    assert recommendation.keeper_economics is not None
    assert tuple(
        year.projected_cost for year in recommendation.keeper_economics.years
    ) == (10, 21, 32)
    assert CollegePromotionReasonCode.ROSTER_NEED in recommendation.reason_codes
    assert CollegePromotionReasonCode.POSITIVE_KEEPER_ECONOMICS in (
        recommendation.reason_codes
    )


def test_repository_adapter_returns_an_empty_warning_for_no_devy_league():
    batch = build_college_promotion_recommendations(
        college_rights=(_right(),),
        league_profile=_profile(enabled=False),
        strategy_profile=_strategy(),
        player_values=(),
        fantasypros_index={},
        sleeper_players={},
        current_roster_positions=(),
        auction_budget=400,
    )

    assert batch.recommendations == ()
    assert batch.warnings == ("College/devy is disabled for this league.",)
