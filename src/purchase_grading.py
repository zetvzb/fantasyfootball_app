from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from src.auction_pool import normalize_player_name
from src.recommendation_snapshot import RecommendationSnapshot


@dataclass(frozen=True)
class PurchaseGradeInput:
    price: int
    target_value: int
    soft_cap: int
    hard_cap: int
    roster_fit: float
    actual_alternative_costs: Tuple[int, ...] = ()
    downstream_outcome_score: float = 50.0


@dataclass(frozen=True)
class PurchaseGrade:
    player_name: str
    sale_number: int
    total_score: float
    letter_grade: str
    price_discipline_score: float
    roster_fit_score: float
    alternative_score: float
    downstream_score: float
    reasons: Tuple[str, ...]


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _letter(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def grade_purchase(inputs: PurchaseGradeInput) -> Tuple[float, str, Tuple[float, ...], Tuple[str, ...]]:
    if inputs.price <= inputs.target_value:
        price_score = 100.0
    elif inputs.price <= inputs.soft_cap:
        price_score = 85.0
    elif inputs.price <= inputs.hard_cap:
        price_score = 65.0
    else:
        overage = inputs.price - inputs.hard_cap
        price_score = _clamp(50.0 - 8.0 * overage)
    fit_score = _clamp(inputs.roster_fit * 100.0)
    if inputs.actual_alternative_costs:
        best_alternative = min(inputs.actual_alternative_costs)
        alternative_score = _clamp(
            70.0 + 4.0 * (best_alternative - inputs.price)
        )
    else:
        alternative_score = 75.0
    downstream_score = _clamp(inputs.downstream_outcome_score)
    total = round(
        0.35 * price_score
        + 0.25 * fit_score
        + 0.15 * alternative_score
        + 0.25 * downstream_score,
        1,
    )
    reasons = (
        "Price {0} the hard cap.".format(
            "stayed within" if inputs.price <= inputs.hard_cap else "exceeded"
        ),
        "Roster-fit score {0:.0f}/100.".format(fit_score),
        "Alternative-cost score {0:.0f}/100.".format(alternative_score),
        "Downstream outcome score {0:.0f}/100.".format(downstream_score),
    )
    return total, _letter(total), (
        price_score, fit_score, alternative_score, downstream_score
    ), reasons


def grade_recorded_purchases(
    sales: Sequence[object],
    snapshots: Sequence[RecommendationSnapshot],
) -> Tuple[PurchaseGrade, ...]:
    snapshot_by_player = {}
    for snapshot in snapshots:
        snapshot_by_player[normalize_player_name(snapshot.player_name)] = snapshot
    sale_by_player = {
        normalize_player_name(sale.player_name): sale for sale in sales
    }
    results = []
    for sale in sales:
        snapshot = snapshot_by_player.get(normalize_player_name(sale.player_name))
        if snapshot is None:
            continue
        alternative_costs = tuple(
            int(sale_by_player[name].price)
            for name in (
                normalize_player_name(value.get("player_name", ""))
                for value in snapshot.alternatives
            )
            if name in sale_by_player
        )
        position_need = snapshot.roster_state.get("position_need", {}) or {}
        roster_fit = float(position_need.get(sale.position, 0.5))
        later_sales = [
            later for later in sales
            if later.manager_id == sale.manager_id
            and later.sale_number > sale.sale_number
            and later.modeled_market_value
        ]
        downstream = 50.0
        if later_sales:
            downstream = sum(
                _clamp(
                    50.0
                    + 50.0
                    * (float(later.modeled_market_value) - float(later.price))
                    / max(1.0, float(later.modeled_market_value))
                )
                for later in later_sales
            ) / len(later_sales)
        total, letter, components, reasons = grade_purchase(
            PurchaseGradeInput(
                price=int(sale.price),
                target_value=snapshot.target_value,
                soft_cap=snapshot.soft_cap,
                hard_cap=snapshot.hard_cap,
                roster_fit=roster_fit,
                actual_alternative_costs=alternative_costs,
                downstream_outcome_score=downstream,
            )
        )
        results.append(
            PurchaseGrade(
                player_name=sale.player_name,
                sale_number=int(sale.sale_number),
                total_score=total,
                letter_grade=letter,
                price_discipline_score=components[0],
                roster_fit_score=components[1],
                alternative_score=components[2],
                downstream_score=components[3],
                reasons=reasons,
            )
        )
    return tuple(results)
