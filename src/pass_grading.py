from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence, Tuple

from src.auction_pool import normalize_player_name
from src.recommendation_snapshot import RecommendationSnapshot


class PassGradeStatus(str, Enum):
    GRADED = "GRADED"
    PENDING = "PENDING"


@dataclass(frozen=True)
class PassGrade:
    player_name: str
    status: PassGradeStatus
    total_score: Optional[float]
    letter_grade: str
    target_sale_price: Optional[int]
    acquired_alternative: Optional[str]
    alternative_sale_price: Optional[int]
    discipline_score: Optional[float]
    availability_score: Optional[float]
    alternative_cost_score: Optional[float]
    reasons: Tuple[str, ...]


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


def grade_recorded_passes(
    sales: Sequence[object],
    snapshots: Sequence[RecommendationSnapshot],
    auction_complete: bool = False,
) -> Tuple[PassGrade, ...]:
    results = []
    seen = set()
    for snapshot in snapshots:
        if snapshot.decision.upper() != "PASS":
            continue
        sale_count = int(snapshot.roster_state.get("sale_count", 0) or 0)
        identity = (
            normalize_player_name(snapshot.player_name),
            snapshot.current_bid,
            sale_count,
        )
        if identity in seen:
            continue
        seen.add(identity)
        later_sales = [sale for sale in sales if int(sale.sale_number) > sale_count]
        target_sale = next(
            (
                sale for sale in later_sales
                if normalize_player_name(sale.player_name) == identity[0]
            ),
            None,
        )
        alternative_names = {
            normalize_player_name(value.get("player_name", ""))
            for value in snapshot.alternatives
        }
        alternative_sales = [
            sale for sale in later_sales
            if normalize_player_name(sale.player_name) in alternative_names
        ]
        if target_sale is None or (
            alternative_names and not alternative_sales and not auction_complete
        ):
            results.append(
                PassGrade(
                    snapshot.player_name, PassGradeStatus.PENDING, None, "PENDING",
                    int(target_sale.price) if target_sale is not None else None,
                    None, None, None, None, None,
                    ("Waiting for later target and alternative outcomes.",),
                )
            )
            continue
        target_price = int(target_sale.price)
        if target_price > snapshot.hard_cap:
            discipline = 100.0
        elif target_price > snapshot.soft_cap:
            discipline = 85.0
        elif target_price > snapshot.target_value:
            discipline = 65.0
        else:
            discipline = 25.0
        if alternative_sales:
            best_alternative = min(alternative_sales, key=lambda sale: int(sale.price))
            alternative_price = int(best_alternative.price)
            availability = 100.0
            cost_score = max(
                0.0,
                min(100.0, 100.0 - 5.0 * max(0, alternative_price - snapshot.target_value)),
            )
            alternative_name = best_alternative.player_name
        else:
            availability = 20.0
            cost_score = 20.0
            alternative_name = None
            alternative_price = None
        total = round(
            0.45 * discipline + 0.35 * availability + 0.20 * cost_score,
            1,
        )
        results.append(
            PassGrade(
                player_name=snapshot.player_name,
                status=PassGradeStatus.GRADED,
                total_score=total,
                letter_grade=_letter(total),
                target_sale_price=target_price,
                acquired_alternative=alternative_name,
                alternative_sale_price=alternative_price,
                discipline_score=discipline,
                availability_score=availability,
                alternative_cost_score=cost_score,
                reasons=(
                    "Target later sold for ${0} against a ${1} hard cap.".format(
                        target_price, snapshot.hard_cap
                    ),
                    "Later alternative availability scored {0:.0f}/100.".format(
                        availability
                    ),
                    "Alternative cost scored {0:.0f}/100.".format(cost_score),
                ),
            )
        )
    return tuple(results)
