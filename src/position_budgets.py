from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple


@dataclass(frozen=True)
class PositionBudgetBand:
    position: str
    open_spots: int
    minimum: int
    target: int
    maximum: int


@dataclass(frozen=True)
class PositionBudgetPlan:
    live_cash: int
    minimum_reserve: int
    discretionary_cash: int
    bands: Tuple[PositionBudgetBand, ...]


def optimize_position_budgets(
    live_cash: int,
    open_spots_by_position: Mapping[str, int],
    need_scores: Mapping[str, float],
    minimum_bid: int = 1,
) -> PositionBudgetPlan:
    open_spots = sum(max(0, int(value)) for value in open_spots_by_position.values())
    reserve = open_spots * int(minimum_bid)
    discretionary = max(0, int(live_cash) - reserve)
    weighted = {
        position: max(0.05, float(need_scores.get(position, 0.5))) * max(0, int(spots))
        for position, spots in open_spots_by_position.items()
        if int(spots) > 0
    }
    total_weight = sum(weighted.values()) or 1.0
    bands = []
    for position in sorted(weighted):
        spots = int(open_spots_by_position[position])
        base = spots * int(minimum_bid)
        share = discretionary * weighted[position] / total_weight
        target = base + int(round(share))
        flexibility = int(round(discretionary * 0.12))
        bands.append(
            PositionBudgetBand(
                position=position,
                open_spots=spots,
                minimum=base,
                target=min(int(live_cash), target),
                maximum=min(int(live_cash) - max(0, reserve - base), target + flexibility),
            )
        )
    return PositionBudgetPlan(
        live_cash=int(live_cash),
        minimum_reserve=reserve,
        discretionary_cash=discretionary,
        bands=tuple(bands),
    )
