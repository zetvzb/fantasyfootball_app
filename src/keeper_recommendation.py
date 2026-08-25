from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from src.auction_pool import (
    build_sleeper_name_index,
    find_sleeper_id,
    normalize_player_name,
)
from src.fantasypros_intelligence import FantasyProsPlayerIntelligence
from src.keeper_domain import (
    KeeperContract,
    KeeperDomainRules,
    build_keeper_contract,
)
from src.league_profile import LeagueProfile
from src.league_setup_data import KeeperRecord
from src.strategy_profile import StrategyProfile
from src.valuation import PlayerValue


MAX_KEEPER_AUCTION_BUDGET_SHARE = 0.30


class KeeperDecision(str, Enum):
    KEEP = "keep"
    BORDERLINE = "borderline"
    PASS = "pass"


class KeeperReasonCode(str, Enum):
    POSITIVE_SURPLUS = "positive_surplus"
    NEGATIVE_SURPLUS = "negative_surplus"
    CURRENT_IMPACT = "current_impact"
    FUTURE_UPSIDE = "future_upside"
    AGE_UPSIDE = "age_upside"
    AGE_DECLINE = "age_decline"
    POSITION_SCARCITY = "position_scarcity"
    ROSTER_NEED = "roster_need"
    STRATEGY_ALIGNMENT = "strategy_alignment"
    MISSING_CURRENT_DATA = "missing_current_data"
    MISSING_FUTURE_DATA = "missing_future_data"


@dataclass(frozen=True)
class KeeperRecommendationInput:
    contract: KeeperContract
    strategy_profile: StrategyProfile
    position: str
    age: Optional[float]
    current_value: float
    future_value: float
    scarcity: float
    roster_fit: float
    auction_budget: int
    minimum_bid: int
    has_current_data: bool = True
    has_future_data: bool = True


@dataclass(frozen=True)
class KeeperRecommendation:
    manager_id: str
    player_name: str
    position: str
    decision: KeeperDecision
    current_value: float
    future_value: float
    age: Optional[float]
    age_adjustment: float
    age_adjusted_future_value: float
    cost: int
    auction_value: float
    surplus: float
    scarcity: float
    roster_fit: float
    strategy_score: float
    reason_codes: Tuple[KeeperReasonCode, ...]
    explanation: str


@dataclass(frozen=True)
class KeeperRecommendationBatch:
    recommendations: Tuple[KeeperRecommendation, ...]
    warnings: Tuple[str, ...] = ()


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def keeper_age_adjustment(position: str, age: Optional[float]) -> float:
    """Return a deterministic future-value multiplier by position and age."""

    if age is None:
        return 1.0

    normalized_position = str(position or "").upper()
    numeric_age = float(age)

    if normalized_position == "QB":
        if numeric_age <= 27:
            return 1.08
        if numeric_age <= 33:
            return 1.00
        if numeric_age <= 35:
            return 0.90
        return 0.78

    if normalized_position == "RB":
        if numeric_age <= 23:
            return 1.12
        if numeric_age <= 25:
            return 1.05
        if numeric_age <= 26:
            return 0.95
        if numeric_age <= 27:
            return 0.85
        return max(0.55, 0.80 - 0.05 * (numeric_age - 28))

    if normalized_position == "WR":
        if numeric_age <= 24:
            return 1.10
        if numeric_age <= 27:
            return 1.03
        if numeric_age <= 29:
            return 0.95
        return max(0.65, 0.90 - 0.05 * (numeric_age - 30))

    if normalized_position == "TE":
        if numeric_age <= 25:
            return 1.08
        if numeric_age <= 29:
            return 1.02
        if numeric_age <= 31:
            return 0.92
        return 0.80

    return 1.0


def recommend_keeper(
    inputs: KeeperRecommendationInput,
) -> KeeperRecommendation:
    """Score one keeper using only explicit numeric inputs and fixed rules."""

    current_value = _clamp(inputs.current_value, 0.0, 100.0)
    future_value = _clamp(inputs.future_value, 0.0, 100.0)
    scarcity = _clamp(inputs.scarcity, 0.0, 1.0)
    roster_fit = _clamp(inputs.roster_fit, 0.0, 1.0)
    age_adjustment = keeper_age_adjustment(inputs.position, inputs.age)
    adjusted_future = _clamp(
        future_value * age_adjustment,
        0.0,
        100.0,
    )

    neutral_value = (
        0.45 * current_value
        + 0.45 * adjusted_future
        + 0.10 * scarcity * 100.0
    )
    auction_ceiling = max(
        float(inputs.minimum_bid),
        float(inputs.auction_budget) * MAX_KEEPER_AUCTION_BUDGET_SHARE,
    )
    auction_value = float(inputs.minimum_bid) + (
        auction_ceiling - float(inputs.minimum_bid)
    ) * (neutral_value / 100.0)
    surplus = auction_value - float(inputs.contract.current_cost)

    strategy_value = (
        inputs.strategy_profile.current_weight * current_value
        + inputs.strategy_profile.future_weight * adjusted_future
    )
    surplus_signal = _clamp(
        50.0 + 50.0 * surplus / max(1.0, auction_ceiling),
        0.0,
        100.0,
    )
    strategy_score = _clamp(
        0.55 * strategy_value
        + 0.20 * surplus_signal
        + 0.15 * scarcity * 100.0
        + 0.10 * roster_fit * 100.0,
        0.0,
        100.0,
    )

    if surplus >= 0.0 and strategy_score >= 60.0:
        decision = KeeperDecision.KEEP
    elif surplus < (-0.10 * auction_ceiling) or strategy_score < 45.0:
        decision = KeeperDecision.PASS
    else:
        decision = KeeperDecision.BORDERLINE

    reason_codes: List[KeeperReasonCode] = []
    reason_codes.append(
        KeeperReasonCode.POSITIVE_SURPLUS
        if surplus >= 0.0
        else KeeperReasonCode.NEGATIVE_SURPLUS
    )
    if current_value >= 65.0:
        reason_codes.append(KeeperReasonCode.CURRENT_IMPACT)
    if adjusted_future >= 65.0:
        reason_codes.append(KeeperReasonCode.FUTURE_UPSIDE)
    if age_adjustment > 1.02:
        reason_codes.append(KeeperReasonCode.AGE_UPSIDE)
    elif age_adjustment < 0.98:
        reason_codes.append(KeeperReasonCode.AGE_DECLINE)
    if scarcity >= 0.70:
        reason_codes.append(KeeperReasonCode.POSITION_SCARCITY)
    if roster_fit >= 0.80:
        reason_codes.append(KeeperReasonCode.ROSTER_NEED)
    if strategy_value >= 65.0:
        reason_codes.append(KeeperReasonCode.STRATEGY_ALIGNMENT)
    if not inputs.has_current_data:
        reason_codes.append(KeeperReasonCode.MISSING_CURRENT_DATA)
    if not inputs.has_future_data:
        reason_codes.append(KeeperReasonCode.MISSING_FUTURE_DATA)

    explanation = (
        "{0}: current {1:.0f}/100, future {2:.0f}/100 after a {3:.2f}x "
        "age adjustment, and estimated auction value ${4:.2f} versus "
        "${5} cost ({6}${7:.2f} surplus). Scarcity {8:.0%}, roster fit "
        "{9:.0%}, strategy score {10:.1f}/100. Auction value uses a "
        "45% current / 45% adjusted-future / 10% scarcity blend against "
        "a 30% team-budget ceiling; strategy scoring applies the user's "
        "{11:.0%} current / {12:.0%} future weights plus surplus, scarcity, "
        "and fit."
    ).format(
        decision.value.upper(),
        current_value,
        adjusted_future,
        age_adjustment,
        auction_value,
        inputs.contract.current_cost,
        "+" if surplus >= 0 else "-",
        abs(surplus),
        scarcity,
        roster_fit,
        strategy_score,
        inputs.strategy_profile.current_weight,
        inputs.strategy_profile.future_weight,
    )

    return KeeperRecommendation(
        manager_id=inputs.contract.manager_id,
        player_name=inputs.contract.player_name,
        position=inputs.position,
        decision=decision,
        current_value=round(current_value, 2),
        future_value=round(future_value, 2),
        age=inputs.age,
        age_adjustment=round(age_adjustment, 3),
        age_adjusted_future_value=round(adjusted_future, 2),
        cost=inputs.contract.current_cost,
        auction_value=round(auction_value, 2),
        surplus=round(surplus, 2),
        scarcity=round(scarcity, 3),
        roster_fit=round(roster_fit, 3),
        strategy_score=round(strategy_score, 2),
        reason_codes=tuple(reason_codes),
        explanation=explanation,
    )


def _future_value_score(
    contract: KeeperContract,
    fantasypros: Optional[FantasyProsPlayerIntelligence],
    dynasty_rank_ceiling: float,
) -> Tuple[float, bool]:
    explicit_values = [
        value for value in contract.future_values if value is not None
    ]
    if explicit_values:
        return (
            _clamp(sum(explicit_values) / len(explicit_values), 0.0, 100.0),
            True,
        )
    dynasty_rank = getattr(fantasypros, "dynasty_ecr", None)
    if dynasty_rank is None or float(dynasty_rank) <= 0:
        return 0.0, False
    score = 100.0 * (
        dynasty_rank_ceiling + 1.0 - float(dynasty_rank)
    ) / max(1.0, dynasty_rank_ceiling)
    return _clamp(score, 0.0, 100.0), True


def _roster_fit_score(
    position: str,
    candidate_name: str,
    keeper_records: Sequence[KeeperRecord],
    starting_lineup: Sequence[str],
) -> float:
    slots = [str(slot).upper() for slot in starting_lineup]
    if not slots:
        return 0.50

    other_positions = Counter(
        str(record.position or "").upper()
        for record in keeper_records
        if (
            record.status == "finalized"
            and normalize_player_name(record.player_name)
            != normalize_player_name(candidate_name)
        )
    )
    normalized_position = str(position or "").upper()
    direct_need = slots.count(normalized_position)
    if other_positions.get(normalized_position, 0) < direct_need:
        return 1.0

    flex_positions = {"RB", "WR", "TE"}
    superflex_positions = {"QB", "RB", "WR", "TE"}
    flexible_need = 0
    eligible_positions = set()
    if normalized_position in flex_positions:
        flexible_need += sum(
            slots.count(slot) for slot in ("FLEX", "W/R/T")
        )
        eligible_positions.update(flex_positions)
    if normalized_position in superflex_positions:
        flexible_need += sum(
            slots.count(slot) for slot in ("SUPER_FLEX", "SFLEX", "Q/W/R/T")
        )
        eligible_positions.update(superflex_positions)

    if flexible_need > 0:
        required_eligible = flexible_need + sum(
            slots.count(eligible) for eligible in eligible_positions
        )
        kept_eligible = sum(
            other_positions.get(eligible, 0) for eligible in eligible_positions
        )
        if kept_eligible < required_eligible:
            return 0.80

    return 0.45


def build_keeper_recommendations(
    *,
    keeper_records: Sequence[KeeperRecord],
    league_profile: LeagueProfile,
    strategy_profile: StrategyProfile,
    player_values: Sequence[PlayerValue],
    fantasypros_index: Mapping[str, FantasyProsPlayerIntelligence],
    sleeper_players: Mapping[str, Mapping[str, Any]],
    auction_budget: int,
) -> KeeperRecommendationBatch:
    """Adapt repository data into deterministic recommendations for one team."""

    if strategy_profile.league_key != league_profile.league_key:
        raise ValueError(
            "Strategy profile league does not match keeper recommendation league."
        )

    rules = KeeperDomainRules.from_league_profile(league_profile)
    player_value_index = {
        normalize_player_name(value.player_name): value
        for value in player_values
    }
    max_vorp = max(
        (max(0.0, float(value.vorp)) for value in player_values),
        default=0.0,
    )
    position_max_vorp = {}
    for value in player_values:
        position = str(value.position or "").upper()
        position_max_vorp[position] = max(
            position_max_vorp.get(position, 0.0),
            max(0.0, float(value.vorp)),
        )

    dynasty_ranks = [
        float(value.dynasty_ecr)
        for value in fantasypros_index.values()
        if value.dynasty_ecr is not None and float(value.dynasty_ecr) > 0
    ]
    dynasty_rank_ceiling = max(dynasty_ranks, default=1.0)
    sleeper_name_index = build_sleeper_name_index(dict(sleeper_players))

    recommendations = []
    warnings = []
    for record in keeper_records:
        try:
            contract = build_keeper_contract(record, rules)
        except ValueError as error:
            warnings.append("{0}: {1}".format(record.player_name, error))
            continue

        key = normalize_player_name(record.player_name)
        current_data = player_value_index.get(key)
        fantasypros = fantasypros_index.get(key)
        sleeper_id = record.sleeper_player_id or find_sleeper_id(
            record.player_name,
            sleeper_name_index,
        )
        sleeper_data = sleeper_players.get(str(sleeper_id), {})
        position = str(
            record.position
            or getattr(current_data, "position", "")
            or getattr(fantasypros, "position", "")
            or sleeper_data.get("position")
            or "UNKNOWN"
        ).upper()

        current_vorp = max(
            0.0,
            float(getattr(current_data, "vorp", 0.0) or 0.0),
        )
        current_value = (
            100.0 * current_vorp / max_vorp if max_vorp > 0 else 0.0
        )
        future_value, has_future_data = _future_value_score(
            contract,
            fantasypros,
            dynasty_rank_ceiling,
        )

        raw_age = sleeper_data.get("age")
        try:
            age = float(raw_age) if raw_age is not None else None
        except (TypeError, ValueError):
            age = None

        position_peak = position_max_vorp.get(position, 0.0)
        scarcity = (
            current_vorp / position_peak if position_peak > 0 else 0.0
        )
        roster_fit = _roster_fit_score(
            position,
            record.player_name,
            keeper_records,
            league_profile.roster.starting_lineup,
        )

        recommendations.append(
            recommend_keeper(
                KeeperRecommendationInput(
                    contract=contract,
                    strategy_profile=strategy_profile,
                    position=position,
                    age=age,
                    current_value=current_value,
                    future_value=future_value,
                    scarcity=scarcity,
                    roster_fit=roster_fit,
                    auction_budget=int(auction_budget),
                    minimum_bid=int(league_profile.auction.minimum_bid),
                    has_current_data=current_data is not None,
                    has_future_data=has_future_data,
                )
            )
        )

    recommendations.sort(
        key=lambda recommendation: (
            -recommendation.strategy_score,
            -recommendation.surplus,
            recommendation.player_name,
        )
    )
    return KeeperRecommendationBatch(
        recommendations=tuple(recommendations),
        warnings=tuple(warnings),
    )
