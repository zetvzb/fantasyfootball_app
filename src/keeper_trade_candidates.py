from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import DefaultDict, List, Mapping, Sequence, Tuple

from src.auction_pool import normalize_player_name
from src.keeper_recommendation import (
    KeeperReasonCode,
    KeeperRecommendation,
)


OPPONENT_PROTECTED_KEEPER_COUNT = 6
DEFAULT_TRADE_CANDIDATE_LIMIT = 10


@dataclass(frozen=True)
class KeeperTradeCandidate:
    rank: int
    player_name: str
    position: str
    owner_manager_id: str
    owner_name: str
    owner_keeper_rank: int
    owner_candidate_count: int
    strategy_score: float
    current_value: float
    future_value: float
    cost: int
    auction_value: float
    surplus: float
    rationale: str


@dataclass(frozen=True)
class KeeperTradeCandidateResult:
    candidates: Tuple[KeeperTradeCandidate, ...]
    opponents_evaluated: int
    recommendations_evaluated: int
    warnings: Tuple[str, ...] = ()


def _owner_sort_key(
    recommendation: KeeperRecommendation,
) -> tuple:
    return (
        -recommendation.strategy_score,
        -recommendation.surplus,
        -recommendation.age_adjusted_future_value,
        normalize_player_name(recommendation.player_name),
    )


def _candidate_sort_key(candidate: KeeperTradeCandidate) -> tuple:
    return (
        -candidate.strategy_score,
        -candidate.surplus,
        candidate.owner_keeper_rank,
        normalize_player_name(candidate.player_name),
        candidate.owner_manager_id,
    )


def _candidate_rationale(
    recommendation: KeeperRecommendation,
    owner_name: str,
    owner_rank: int,
    owner_count: int,
    protected_count: int,
) -> str:
    reasons: List[str] = [
        "ranks #{0} of {1} for {2}, outside that team's projected top {3}".format(
            owner_rank,
            owner_count,
            owner_name,
            protected_count,
        )
    ]

    reason_codes = set(recommendation.reason_codes)
    if KeeperReasonCode.NEGATIVE_SURPLUS in reason_codes:
        reasons.append(
            "the ${0} keeper cost exceeds the ${1:.2f} estimated auction value"
            .format(recommendation.cost, recommendation.auction_value)
        )
    elif KeeperReasonCode.POSITIVE_SURPLUS in reason_codes:
        reasons.append(
            "still offers ${0:.2f} projected surplus at a ${1} cost".format(
                recommendation.surplus,
                recommendation.cost,
            )
        )

    if KeeperReasonCode.FUTURE_UPSIDE in reason_codes:
        reasons.append("has future-value upside")
    if KeeperReasonCode.CURRENT_IMPACT in reason_codes:
        reasons.append("can contribute immediately")
    if KeeperReasonCode.AGE_UPSIDE in reason_codes:
        reasons.append("has favorable age optionality")
    if KeeperReasonCode.POSITION_SCARCITY in reason_codes:
        reasons.append("plays at a scarce position")

    reasons.append(
        "keeper-slot pressure may make the manager more willing to discuss a trade"
    )
    return "; ".join(reasons) + "."


def recommend_keeper_trade_candidates(
    *,
    recommendations: Sequence[KeeperRecommendation],
    current_manager_id: str,
    manager_names: Mapping[str, str],
    protected_count: int = OPPONENT_PROTECTED_KEEPER_COUNT,
    limit: int = DEFAULT_TRADE_CANDIDATE_LIMIT,
) -> KeeperTradeCandidateResult:
    """Find the best targets outside each opponent's strategy-score top six."""

    if protected_count < 0:
        raise ValueError("Protected keeper count cannot be negative.")
    if limit < 0:
        raise ValueError("Trade candidate limit cannot be negative.")

    by_manager: DefaultDict[str, List[KeeperRecommendation]] = defaultdict(list)
    for manager_id in manager_names:
        if manager_id != current_manager_id:
            by_manager[manager_id]
    seen = set()
    for recommendation in recommendations:
        if recommendation.manager_id == current_manager_id:
            continue
        identity = (
            recommendation.manager_id,
            normalize_player_name(recommendation.player_name),
        )
        if identity in seen:
            raise ValueError(
                "Opponent keeper recommendations must be unique by manager and player."
            )
        seen.add(identity)
        by_manager[recommendation.manager_id].append(recommendation)

    eligible = []
    warnings: List[str] = []
    recommendations_evaluated = 0
    for manager_id in sorted(by_manager):
        owner_recommendations = sorted(
            by_manager[manager_id],
            key=_owner_sort_key,
        )
        recommendations_evaluated += len(owner_recommendations)
        owner_name = manager_names.get(manager_id, manager_id)
        if len(owner_recommendations) <= protected_count:
            warnings.append(
                "{0} has only {1} scored keeper candidate(s), so none fall "
                "outside the projected top {2}.".format(
                    owner_name,
                    len(owner_recommendations),
                    protected_count,
                )
            )
            continue

        for index, recommendation in enumerate(
            owner_recommendations[protected_count:],
            start=protected_count + 1,
        ):
            eligible.append(
                KeeperTradeCandidate(
                    rank=0,
                    player_name=recommendation.player_name,
                    position=recommendation.position,
                    owner_manager_id=manager_id,
                    owner_name=owner_name,
                    owner_keeper_rank=index,
                    owner_candidate_count=len(owner_recommendations),
                    strategy_score=recommendation.strategy_score,
                    current_value=recommendation.current_value,
                    future_value=recommendation.age_adjusted_future_value,
                    cost=recommendation.cost,
                    auction_value=recommendation.auction_value,
                    surplus=recommendation.surplus,
                    rationale=_candidate_rationale(
                        recommendation,
                        owner_name,
                        index,
                        len(owner_recommendations),
                        protected_count,
                    ),
                )
            )

    ranked_candidates = []
    for rank, candidate in enumerate(
        sorted(eligible, key=_candidate_sort_key)[:limit],
        start=1,
    ):
        ranked_candidates.append(
            KeeperTradeCandidate(
                rank=rank,
                player_name=candidate.player_name,
                position=candidate.position,
                owner_manager_id=candidate.owner_manager_id,
                owner_name=candidate.owner_name,
                owner_keeper_rank=candidate.owner_keeper_rank,
                owner_candidate_count=candidate.owner_candidate_count,
                strategy_score=candidate.strategy_score,
                current_value=candidate.current_value,
                future_value=candidate.future_value,
                cost=candidate.cost,
                auction_value=candidate.auction_value,
                surplus=candidate.surplus,
                rationale=candidate.rationale,
            )
        )

    if by_manager and not ranked_candidates:
        warnings.append(
            "No opponent keeper candidates fall outside their projected top {0}."
            .format(protected_count)
        )

    return KeeperTradeCandidateResult(
        candidates=tuple(ranked_candidates),
        opponents_evaluated=len(by_manager),
        recommendations_evaluated=recommendations_evaluated,
        warnings=tuple(warnings),
    )
