from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from src.auction_pool import normalize_player_name
from src.keeper_recommendation import KeeperRecommendation


DEFAULT_UPGRADE_TARGET_LIMIT = 10


@dataclass(frozen=True)
class KeeperUpgradeTarget:
    """One opponent keeper compared against your best player at the same
    position. Every opponent keeper is included -- this answers "is this
    simply better than what I have", not "would they realistically trade
    it away".
    """

    rank: int
    player_name: str
    position: str
    owner_manager_id: str
    owner_name: str
    strategy_score: float
    surplus: float
    cost: int
    my_player_name: Optional[str]
    my_strategy_score: Optional[float]
    score_advantage: float
    is_upgrade: bool


@dataclass(frozen=True)
class KeeperUpgradeTargetResult:
    targets: Tuple[KeeperUpgradeTarget, ...]
    warnings: Tuple[str, ...] = ()


def build_keeper_upgrade_targets(
    *,
    recommendations: Sequence[KeeperRecommendation],
    current_manager_id: str,
    manager_names: Mapping[str, str],
    limit: int = DEFAULT_UPGRADE_TARGET_LIMIT,
) -> KeeperUpgradeTargetResult:
    """Rank opponents' best keepers at each position against your own.

    Every opponent keeper recommendation is included (no protected-top-N
    filter), each compared to your highest strategy-score keeper at the
    same position. A position where you have no keeper candidate at all
    counts every opponent player there as an upgrade by default -- you
    have nothing to compare against, so anything fills a real hole.
    """

    if limit < 0:
        raise ValueError("Upgrade target limit cannot be negative.")

    my_best_by_position: Dict[str, KeeperRecommendation] = {}
    for recommendation in recommendations:
        if recommendation.manager_id != current_manager_id:
            continue
        current_best = my_best_by_position.get(recommendation.position)
        if (
            current_best is None
            or recommendation.strategy_score > current_best.strategy_score
        ):
            my_best_by_position[recommendation.position] = recommendation

    targets: List[KeeperUpgradeTarget] = []
    for recommendation in recommendations:
        if recommendation.manager_id == current_manager_id:
            continue
        my_best = my_best_by_position.get(recommendation.position)
        my_score = my_best.strategy_score if my_best is not None else None
        advantage = recommendation.strategy_score - (my_score or 0.0)
        targets.append(
            KeeperUpgradeTarget(
                rank=0,
                player_name=recommendation.player_name,
                position=recommendation.position,
                owner_manager_id=recommendation.manager_id,
                owner_name=manager_names.get(
                    recommendation.manager_id, recommendation.manager_id
                ),
                strategy_score=recommendation.strategy_score,
                surplus=recommendation.surplus,
                cost=recommendation.cost,
                my_player_name=(
                    my_best.player_name if my_best is not None else None
                ),
                my_strategy_score=my_score,
                score_advantage=advantage,
                is_upgrade=(my_score is None or recommendation.strategy_score > my_score),
            )
        )

    ranked = sorted(
        targets,
        key=lambda target: (
            not target.is_upgrade,
            -target.score_advantage,
            -target.strategy_score,
            normalize_player_name(target.player_name),
        ),
    )[:limit]

    warnings: List[str] = []
    if not my_best_by_position and targets:
        warnings.append(
            "You have no scored keeper candidates yet, so every opponent "
            "player below is shown as a potential upgrade by default."
        )

    return KeeperUpgradeTargetResult(
        targets=tuple(
            replace(target, rank=index)
            for index, target in enumerate(ranked, start=1)
        ),
        warnings=tuple(warnings),
    )


# =========================================================
# CASH-ADJUSTED TRADE EVALUATION
# =========================================================

@dataclass(frozen=True)
class KeeperTradeEvaluation:
    """A specific trade proposal: acquire `target` (plus cash) instead of
    keeping `current_keeper` (or filling an empty roster slot with them).
    """

    target_player_name: str
    target_owner_name: str
    target_auction_value: float
    target_strategy_score: float
    current_keeper_player_name: Optional[str]
    current_keeper_auction_value: float
    current_keeper_strategy_score: Optional[float]
    cash_offered: int
    value_delta: float
    net_value: float
    score_advantage: float
    verdict: str


def evaluate_keeper_trade(
    *,
    target: KeeperRecommendation,
    current_keeper: Optional[KeeperRecommendation],
    cash_offered: int,
    owner_name: str,
) -> KeeperTradeEvaluation:
    """Compare trading for `target` (plus a cash offer) against keeping
    `current_keeper` -- or filling an empty slot if you have none at that
    position.

    Trading for a keeper right means inheriting the target's own contract
    economics next year, so `target.auction_value` is the value gained and
    `cash_offered` is a one-time draft-day cost on top of it, not a
    recurring keeper cost.
    """

    if cash_offered < 0:
        raise ValueError("Cash offered cannot be negative.")

    current_value = (
        current_keeper.auction_value if current_keeper is not None else 0.0
    )
    current_score = (
        current_keeper.strategy_score if current_keeper is not None else None
    )

    value_delta = target.auction_value - current_value
    net_value = value_delta - cash_offered
    score_advantage = target.strategy_score - (current_score or 0.0)

    if net_value > 0 and score_advantage > 0:
        verdict = "Good Trade"
    elif net_value <= 0 and score_advantage <= 0:
        verdict = "Not Worth It"
    else:
        verdict = "Close Call -- mixed signal"

    return KeeperTradeEvaluation(
        target_player_name=target.player_name,
        target_owner_name=owner_name,
        target_auction_value=target.auction_value,
        target_strategy_score=target.strategy_score,
        current_keeper_player_name=(
            current_keeper.player_name if current_keeper is not None else None
        ),
        current_keeper_auction_value=current_value,
        current_keeper_strategy_score=current_score,
        cash_offered=cash_offered,
        value_delta=value_delta,
        net_value=net_value,
        score_advantage=score_advantage,
        verdict=verdict,
    )
