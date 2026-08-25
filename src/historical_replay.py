from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ReplayNomination:
    player_name: str
    position: str


@dataclass(frozen=True)
class ReplayState:
    completed_sales: Tuple[object, ...]
    sale_number: int


@dataclass(frozen=True)
class PreSaleRecommendation:
    player_name: str
    target_value: int
    soft_cap: int
    hard_cap: int
    decision: str
    explanation: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ReplayEvaluation:
    sale_number: int
    player_name: str
    actual_price: int
    actual_manager_id: str
    recommendation: PreSaleRecommendation
    price_error: int
    within_hard_cap: bool


@dataclass(frozen=True)
class HistoricalReplayResult:
    evaluations: Tuple[ReplayEvaluation, ...]
    mean_absolute_price_error: float
    hard_cap_coverage: float


RecommendationBuilder = Callable[
    [ReplayState, ReplayNomination],
    Optional[PreSaleRecommendation],
]


def replay_historical_sales(
    sales: Sequence[object],
    recommendation_builder: RecommendationBuilder,
) -> HistoricalReplayResult:
    """Replay a ledger in order and evaluate recommendations made pre-sale."""

    ordered = sorted(sales, key=lambda sale: int(sale.sale_number))
    sale_numbers = [int(sale.sale_number) for sale in ordered]
    if len(sale_numbers) != len(set(sale_numbers)):
        raise ValueError("Historical replay requires unique sale numbers.")

    completed = []
    evaluations = []
    for sale in ordered:
        state = ReplayState(
            completed_sales=tuple(completed),
            sale_number=int(sale.sale_number),
        )
        nomination = ReplayNomination(
            player_name=str(sale.player_name),
            position=str(sale.position),
        )
        recommendation = recommendation_builder(state, nomination)
        if recommendation is not None:
            if recommendation.player_name != nomination.player_name:
                raise ValueError(
                    "Replay recommendation must match the nominated player."
                )
            actual_price = int(sale.price)
            evaluations.append(
                ReplayEvaluation(
                    sale_number=int(sale.sale_number),
                    player_name=nomination.player_name,
                    actual_price=actual_price,
                    actual_manager_id=str(sale.manager_id),
                    recommendation=recommendation,
                    price_error=actual_price - recommendation.target_value,
                    within_hard_cap=actual_price <= recommendation.hard_cap,
                )
            )
        completed.append(sale)

    absolute_errors = [abs(result.price_error) for result in evaluations]
    coverage = [result.within_hard_cap for result in evaluations]
    return HistoricalReplayResult(
        evaluations=tuple(evaluations),
        mean_absolute_price_error=round(
            sum(absolute_errors) / len(absolute_errors), 2
        ) if absolute_errors else 0.0,
        hard_cap_coverage=round(
            sum(coverage) / len(coverage), 4
        ) if coverage else 0.0,
    )
