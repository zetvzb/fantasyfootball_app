from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from src.auction_pool import (
    build_sleeper_name_index,
    find_sleeper_id,
    normalize_player_name,
)
from src.college_domain import (
    COLLEGE_ELIGIBILITY_ELIGIBLE,
    COLLEGE_PROMOTION_PROMOTED,
    COLLEGE_STAGE_IN_NFL,
    CollegeDomainRules,
)
from src.keeper_domain import (
    EXPLICIT_COST,
    KeeperContract,
    KeeperDomainRules,
)
from src.keeper_economics import (
    KeeperEconomicsProjection,
    project_keeper_economics,
)
from src.league_setup_data import CollegeRight
from src.strategy_profile import StrategyProfile
from src.valuation import PlayerValue


MAX_PROMOTED_KEEPER_BUDGET_SHARE = 0.30


class CollegePromotionDecision(str, Enum):
    PROMOTE_NOW = "PROMOTE NOW"
    LEAVE_ON_TAXI = "LEAVE ON TAXI"
    BORDERLINE = "BORDERLINE"
    NOT_ELIGIBLE = "NOT ELIGIBLE"


class CollegePromotionReasonCode(str, Enum):
    NO_DEVY_SYSTEM = "no_devy_system"
    NOT_IN_NFL = "not_in_nfl"
    INELIGIBLE_BY_RULE = "ineligible_by_rule"
    ELIGIBILITY_UNKNOWN = "eligibility_unknown"
    ALREADY_PROMOTED = "already_promoted"
    NFL_ROLE_READY = "nfl_role_ready"
    STRONG_DRAFT_CAPITAL = "strong_draft_capital"
    CURRENT_PRODUCTION = "current_production"
    FUTURE_UPSIDE = "future_upside"
    YOUTH_UPSIDE = "youth_upside"
    DEPTH_CHART_PATH = "depth_chart_path"
    ROSTER_NEED = "roster_need"
    PROMOTION_WINDOW = "promotion_window"
    POSITIVE_KEEPER_ECONOMICS = "positive_keeper_economics"
    NEGATIVE_KEEPER_ECONOMICS = "negative_keeper_economics"
    TAXI_OPPORTUNITY_COST = "taxi_opportunity_cost"
    COLLEGE_CAPACITY_PRESSURE = "college_capacity_pressure"
    NEEDS_DEVELOPMENT_TIME = "needs_development_time"
    MISSING_PROJECTION_DATA = "missing_projection_data"
    MISSING_DRAFT_CAPITAL = "missing_draft_capital"
    MISSING_DEPTH_CHART = "missing_depth_chart"


@dataclass(frozen=True)
class CollegePromotionInput:
    right: CollegeRight
    rules: CollegeDomainRules
    strategy_profile: StrategyProfile
    nfl_role_opportunity: float
    draft_capital: float
    current_projected_production: float
    future_value: float
    age: Optional[float]
    depth_chart_status: float
    roster_need: float
    promotion_timing: float
    taxi_opportunity_cost: float
    college_roster_count: int
    keeper_economics: Optional[KeeperEconomicsProjection] = None
    has_projection_data: bool = True
    has_draft_capital: bool = True
    has_depth_chart: bool = True


@dataclass(frozen=True)
class CollegePromotionRecommendation:
    manager_id: str
    player_name: str
    position: str
    decision: CollegePromotionDecision
    score: float
    nfl_role_opportunity: float
    draft_capital: float
    current_projected_production: float
    future_value: float
    age: Optional[float]
    age_score: float
    depth_chart_status: float
    roster_need: float
    promotion_timing: float
    taxi_opportunity_cost: float
    college_capacity_pressure: float
    keeper_economics: Optional[KeeperEconomicsProjection]
    reason_codes: Tuple[CollegePromotionReasonCode, ...]
    explanation: str


@dataclass(frozen=True)
class CollegePromotionRecommendationBatch:
    recommendations: Tuple[CollegePromotionRecommendation, ...]
    warnings: Tuple[str, ...] = ()


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _developmental_age_score(age: Optional[float]) -> float:
    if age is None:
        return 0.50
    numeric_age = float(age)
    if numeric_age <= 21:
        return 1.00
    if numeric_age <= 22:
        return 0.90
    if numeric_age <= 23:
        return 0.75
    if numeric_age <= 24:
        return 0.55
    return max(0.20, 0.45 - 0.08 * (numeric_age - 25))


def _not_eligible_recommendation(
    inputs: CollegePromotionInput,
    reason_code: CollegePromotionReasonCode,
    reason: str,
) -> CollegePromotionRecommendation:
    return CollegePromotionRecommendation(
        manager_id=inputs.right.manager_id,
        player_name=inputs.right.player_name,
        position=str(inputs.right.position or "UNKNOWN").upper(),
        decision=CollegePromotionDecision.NOT_ELIGIBLE,
        score=0.0,
        nfl_role_opportunity=round(_clamp(inputs.nfl_role_opportunity, 0, 1), 3),
        draft_capital=round(_clamp(inputs.draft_capital, 0, 1), 3),
        current_projected_production=round(
            _clamp(inputs.current_projected_production, 0, 100),
            2,
        ),
        future_value=round(_clamp(inputs.future_value, 0, 100), 2),
        age=inputs.age,
        age_score=round(_developmental_age_score(inputs.age), 3),
        depth_chart_status=round(_clamp(inputs.depth_chart_status, 0, 1), 3),
        roster_need=round(_clamp(inputs.roster_need, 0, 1), 3),
        promotion_timing=round(_clamp(inputs.promotion_timing, 0, 1), 3),
        taxi_opportunity_cost=round(
            _clamp(inputs.taxi_opportunity_cost, 0, 100),
            2,
        ),
        college_capacity_pressure=0.0,
        keeper_economics=inputs.keeper_economics,
        reason_codes=(reason_code,),
        explanation="NOT ELIGIBLE: {0}".format(reason),
    )


def recommend_college_promotion(
    inputs: CollegePromotionInput,
) -> CollegePromotionRecommendation:
    """Return an explainable deterministic Promote/Taxi recommendation."""

    if not inputs.rules.enabled:
        return _not_eligible_recommendation(
            inputs,
            CollegePromotionReasonCode.NO_DEVY_SYSTEM,
            "this league has no college/devy system.",
        )
    if inputs.right.promotion_status == COLLEGE_PROMOTION_PROMOTED:
        return _not_eligible_recommendation(
            inputs,
            CollegePromotionReasonCode.ALREADY_PROMOTED,
            "the player is already marked promoted.",
        )
    if inputs.right.status != COLLEGE_STAGE_IN_NFL:
        return _not_eligible_recommendation(
            inputs,
            CollegePromotionReasonCode.NOT_IN_NFL,
            "the player is not represented as an NFL player.",
        )
    if inputs.right.eligibility_status != COLLEGE_ELIGIBILITY_ELIGIBLE:
        reason_code = (
            CollegePromotionReasonCode.ELIGIBILITY_UNKNOWN
            if inputs.right.eligibility_status == "unknown"
            else CollegePromotionReasonCode.INELIGIBLE_BY_RULE
        )
        return _not_eligible_recommendation(
            inputs,
            reason_code,
            "league-specific promotion eligibility is {0}.".format(
                inputs.right.eligibility_status
            ),
        )

    role = _clamp(inputs.nfl_role_opportunity, 0.0, 1.0)
    draft_capital = _clamp(inputs.draft_capital, 0.0, 1.0)
    current_value = _clamp(inputs.current_projected_production, 0.0, 100.0)
    future_value = _clamp(inputs.future_value, 0.0, 100.0)
    age_score = _developmental_age_score(inputs.age)
    depth_chart = _clamp(inputs.depth_chart_status, 0.0, 1.0)
    roster_need = _clamp(inputs.roster_need, 0.0, 1.0)
    timing = _clamp(inputs.promotion_timing, 0.0, 1.0)
    taxi_cost = _clamp(inputs.taxi_opportunity_cost, 0.0, 100.0)
    capacity_pressure = _clamp(
        float(inputs.college_roster_count)
        / max(1.0, float(inputs.rules.max_college_players)),
        0.0,
        1.0,
    )
    strategy_value = (
        inputs.strategy_profile.current_weight * current_value
        + inputs.strategy_profile.future_weight * future_value
    )

    economics_score = 50.0
    economics_surplus = None
    if inputs.keeper_economics is not None:
        economics_surplus = inputs.keeper_economics.cumulative_surplus
        total_cost = sum(
            year.projected_cost for year in inputs.keeper_economics.years
        )
        economics_score = _clamp(
            50.0 + 50.0 * economics_surplus / max(1.0, float(total_cost)),
            0.0,
            100.0,
        )

    score = (
        0.29 * strategy_value
        + 13.0 * role
        + 8.0 * draft_capital
        + 5.0 * age_score
        + 9.0 * depth_chart
        + 10.0 * roster_need
        + 7.0 * timing
        + 0.10 * economics_score
        + 0.05 * taxi_cost
        + 4.0 * capacity_pressure
    )
    score = _clamp(score, 0.0, 100.0)

    if score >= 65.0:
        decision = CollegePromotionDecision.PROMOTE_NOW
    elif score <= 42.0:
        decision = CollegePromotionDecision.LEAVE_ON_TAXI
    else:
        decision = CollegePromotionDecision.BORDERLINE

    reason_codes: List[CollegePromotionReasonCode] = []
    if role >= 0.70:
        reason_codes.append(CollegePromotionReasonCode.NFL_ROLE_READY)
    if draft_capital >= 0.70:
        reason_codes.append(CollegePromotionReasonCode.STRONG_DRAFT_CAPITAL)
    if current_value >= 65.0:
        reason_codes.append(CollegePromotionReasonCode.CURRENT_PRODUCTION)
    if future_value >= 65.0:
        reason_codes.append(CollegePromotionReasonCode.FUTURE_UPSIDE)
    if age_score >= 0.75:
        reason_codes.append(CollegePromotionReasonCode.YOUTH_UPSIDE)
    if depth_chart >= 0.70:
        reason_codes.append(CollegePromotionReasonCode.DEPTH_CHART_PATH)
    if roster_need >= 0.70:
        reason_codes.append(CollegePromotionReasonCode.ROSTER_NEED)
    if timing >= 0.80:
        reason_codes.append(CollegePromotionReasonCode.PROMOTION_WINDOW)
    if economics_surplus is not None:
        reason_codes.append(
            CollegePromotionReasonCode.POSITIVE_KEEPER_ECONOMICS
            if economics_surplus >= 0
            else CollegePromotionReasonCode.NEGATIVE_KEEPER_ECONOMICS
        )
    if taxi_cost >= 65.0:
        reason_codes.append(CollegePromotionReasonCode.TAXI_OPPORTUNITY_COST)
    if capacity_pressure >= 0.90:
        reason_codes.append(CollegePromotionReasonCode.COLLEGE_CAPACITY_PRESSURE)
    if role <= 0.35 and current_value <= 40.0:
        reason_codes.append(CollegePromotionReasonCode.NEEDS_DEVELOPMENT_TIME)
    if not inputs.has_projection_data:
        reason_codes.append(CollegePromotionReasonCode.MISSING_PROJECTION_DATA)
    if not inputs.has_draft_capital:
        reason_codes.append(CollegePromotionReasonCode.MISSING_DRAFT_CAPITAL)
    if not inputs.has_depth_chart:
        reason_codes.append(CollegePromotionReasonCode.MISSING_DEPTH_CHART)

    economics_text = (
        "keeper cumulative surplus ${0:.2f}".format(economics_surplus)
        if economics_surplus is not None
        else "keeper economics unavailable"
    )
    explanation = (
        "{0}: score {1:.1f}/100 from strategy-adjusted production/future "
        "value {2:.1f}, NFL role {3:.0%}, draft capital {4:.0%}, depth-chart "
        "path {5:.0%}, roster need {6:.0%}, timing {7:.0%}, taxi opportunity "
        "cost {8:.0f}/100, capacity pressure {9:.0%}, and {10}."
    ).format(
        decision.value,
        score,
        strategy_value,
        role,
        draft_capital,
        depth_chart,
        roster_need,
        timing,
        taxi_cost,
        capacity_pressure,
        economics_text,
    )

    return CollegePromotionRecommendation(
        manager_id=inputs.right.manager_id,
        player_name=inputs.right.player_name,
        position=str(inputs.right.position or "UNKNOWN").upper(),
        decision=decision,
        score=round(score, 2),
        nfl_role_opportunity=round(role, 3),
        draft_capital=round(draft_capital, 3),
        current_projected_production=round(current_value, 2),
        future_value=round(future_value, 2),
        age=inputs.age,
        age_score=round(age_score, 3),
        depth_chart_status=round(depth_chart, 3),
        roster_need=round(roster_need, 3),
        promotion_timing=round(timing, 3),
        taxi_opportunity_cost=round(taxi_cost, 2),
        college_capacity_pressure=round(capacity_pressure, 3),
        keeper_economics=inputs.keeper_economics,
        reason_codes=tuple(reason_codes),
        explanation=explanation,
    )


def _draft_capital_score(round_number: Optional[int]) -> Tuple[float, bool]:
    if round_number is None or int(round_number) <= 0:
        return 0.50, False
    return (
        {
            1: 1.00,
            2: 0.85,
            3: 0.70,
            4: 0.55,
            5: 0.40,
            6: 0.25,
            7: 0.15,
        }.get(int(round_number), 0.10),
        True,
    )


def _depth_chart_score(order: Optional[int]) -> Tuple[float, bool]:
    if order is None or int(order) <= 0:
        return 0.40, False
    return (
        {1: 1.00, 2: 0.70, 3: 0.40}.get(int(order), 0.20),
        True,
    )


def _roster_need_score(
    position: str,
    current_roster_positions: Sequence[str],
    starting_lineup: Sequence[str],
) -> float:
    normalized_position = str(position or "").upper()
    required = Counter(str(slot).upper() for slot in starting_lineup)
    rostered = Counter(str(value).upper() for value in current_roster_positions)
    if required.get(normalized_position, 0) > rostered.get(normalized_position, 0):
        return 1.0
    if normalized_position in {"RB", "WR", "TE"} and any(
        slot in required for slot in ("FLEX", "W/R/T")
    ):
        return 0.70
    if normalized_position in {"QB", "RB", "WR", "TE"} and any(
        slot in required for slot in ("SUPER_FLEX", "SFLEX", "Q/W/R/T")
    ):
        return 0.70
    return 0.35


def _future_value_score(
    right: CollegeRight,
    fantasypros: Optional[Any],
    dynasty_rank_ceiling: float,
) -> Tuple[float, bool]:
    explicit = [value for value in right.future_values if value is not None]
    if explicit:
        return _clamp(sum(float(value) for value in explicit) / len(explicit), 0, 100), True
    dynasty_rank = getattr(fantasypros, "dynasty_ecr", None)
    if dynasty_rank is None or float(dynasty_rank) <= 0:
        return 0.0, False
    value = 100.0 * (
        dynasty_rank_ceiling + 1.0 - float(dynasty_rank)
    ) / max(1.0, dynasty_rank_ceiling)
    return _clamp(value, 0, 100), True


def build_college_promotion_recommendations(
    *,
    college_rights: Sequence[CollegeRight],
    league_profile: Any,
    strategy_profile: StrategyProfile,
    player_values: Sequence[PlayerValue],
    fantasypros_index: Mapping[str, Any],
    sleeper_players: Mapping[str, Mapping[str, Any]],
    current_roster_positions: Sequence[str],
    auction_budget: int,
) -> CollegePromotionRecommendationBatch:
    """Adapt repository data into recommendations for one manager's rights."""

    rules = CollegeDomainRules.from_league_profile(league_profile)
    if not rules.enabled:
        return CollegePromotionRecommendationBatch(
            recommendations=(),
            warnings=("College/devy is disabled for this league.",),
        )
    if not college_rights:
        return CollegePromotionRecommendationBatch(
            recommendations=(),
            warnings=("No college/devy rights are recorded for this manager.",),
        )

    value_index = {
        normalize_player_name(value.player_name): value for value in player_values
    }
    max_vorp = max(
        (max(0.0, float(value.vorp)) for value in player_values),
        default=0.0,
    )
    dynasty_ranks = [
        float(value.dynasty_ecr)
        for value in fantasypros_index.values()
        if getattr(value, "dynasty_ecr", None) is not None
        and float(value.dynasty_ecr) > 0
    ]
    dynasty_ceiling = max(dynasty_ranks, default=1.0)
    sleeper_name_index = build_sleeper_name_index(dict(sleeper_players))
    keeper_rules = KeeperDomainRules.from_league_profile(league_profile)
    recommendations = []
    college_roster_count = sum(
        1 for right in college_rights if right.promotion_status != COLLEGE_PROMOTION_PROMOTED
    )

    for right in college_rights:
        normalized_name = normalize_player_name(right.player_name)
        current_data = value_index.get(normalized_name)
        fantasypros = fantasypros_index.get(normalized_name)
        sleeper_id = right.sleeper_player_id or find_sleeper_id(
            right.player_name,
            sleeper_name_index,
        )
        sleeper_data = sleeper_players.get(str(sleeper_id), {})
        position = str(
            right.position
            or getattr(current_data, "position", "")
            or getattr(fantasypros, "position", "")
            or sleeper_data.get("position")
            or "UNKNOWN"
        ).upper()
        if right.position is None and position != "UNKNOWN":
            right = replace(right, position=position)

        current_vorp = max(0.0, float(getattr(current_data, "vorp", 0.0) or 0.0))
        current_value = 100.0 * current_vorp / max_vorp if max_vorp > 0 else 0.0
        future_value, has_future = _future_value_score(
            right,
            fantasypros,
            dynasty_ceiling,
        )
        draft_round_raw = (
            right.nfl_draft_round
            or sleeper_data.get("draft_round")
            or (sleeper_data.get("metadata") or {}).get("draft_round")
        )
        try:
            draft_round = int(draft_round_raw) if draft_round_raw is not None else None
        except (TypeError, ValueError):
            draft_round = None
        draft_capital, has_draft_capital = _draft_capital_score(draft_round)
        depth_order_raw = sleeper_data.get("depth_chart_order")
        try:
            depth_order = int(depth_order_raw) if depth_order_raw is not None else None
        except (TypeError, ValueError):
            depth_order = None
        depth_chart, has_depth_chart = _depth_chart_score(depth_order)
        raw_age = sleeper_data.get("age")
        try:
            age = float(raw_age) if raw_age is not None else None
        except (TypeError, ValueError):
            age = None
        active_nfl_player = (
            right.status == COLLEGE_STAGE_IN_NFL
            and sleeper_data.get("active") is not False
            and bool(sleeper_data.get("team"))
        )
        role = _clamp(
            (0.55 if active_nfl_player else 0.20) + 0.45 * depth_chart,
            0,
            1,
        )
        roster_need = _roster_need_score(
            position,
            current_roster_positions,
            league_profile.roster.starting_lineup,
        )
        capacity_pressure = _clamp(
            college_roster_count / max(1.0, float(rules.max_college_players)),
            0,
            1,
        )
        taxi_cost = _clamp(0.60 * current_value + 40.0 * capacity_pressure, 0, 100)
        timing = (
            1.0
            if right.status == COLLEGE_STAGE_IN_NFL
            and right.eligibility_status == COLLEGE_ELIGIBILITY_ELIGIBLE
            else 0.0
        )

        economics = None
        next_year_cost = league_profile.college.next_year_keeper_cost
        if next_year_cost is not None:
            ceiling = max(
                float(league_profile.auction.minimum_bid),
                float(auction_budget) * MAX_PROMOTED_KEEPER_BUDGET_SHARE,
            )
            normalized_values = [current_value]
            normalized_values.extend(
                value if value is not None else future_value
                for value in right.future_values
            )
            normalized_values.extend(
                [future_value] * keeper_rules.future_horizon_years
            )
            projected_dollar_values = tuple(
                float(league_profile.auction.minimum_bid)
                + (ceiling - float(league_profile.auction.minimum_bid))
                * (_clamp(value, 0, 100) / 100.0)
                for value in normalized_values[: keeper_rules.future_horizon_years]
            )
            economics = project_keeper_economics(
                contract=KeeperContract(
                    manager_id=right.manager_id,
                    player_name=right.player_name,
                    position=position,
                    cost_basis=EXPLICIT_COST,
                    current_cost=int(next_year_cost),
                    prior_year_cost=None,
                    tenure_years=0,
                    future_horizon_years=keeper_rules.future_horizon_years,
                    future_values=tuple(
                        None for _ in range(keeper_rules.future_horizon_years)
                    ),
                ),
                rules=keeper_rules,
                projected_player_values=projected_dollar_values,
                strategy_profile=strategy_profile,
            )

        recommendations.append(
            recommend_college_promotion(
                CollegePromotionInput(
                    right=right,
                    rules=rules,
                    strategy_profile=strategy_profile,
                    nfl_role_opportunity=role,
                    draft_capital=draft_capital,
                    current_projected_production=current_value,
                    future_value=future_value,
                    age=age,
                    depth_chart_status=depth_chart,
                    roster_need=roster_need,
                    promotion_timing=timing,
                    taxi_opportunity_cost=taxi_cost,
                    college_roster_count=college_roster_count,
                    keeper_economics=economics,
                    has_projection_data=(current_data is not None or has_future),
                    has_draft_capital=has_draft_capital,
                    has_depth_chart=has_depth_chart,
                )
            )
        )

    recommendations.sort(
        key=lambda recommendation: (
            recommendation.decision is CollegePromotionDecision.NOT_ELIGIBLE,
            -recommendation.score,
            recommendation.player_name,
        )
    )
    return CollegePromotionRecommendationBatch(
        recommendations=tuple(recommendations),
    )
