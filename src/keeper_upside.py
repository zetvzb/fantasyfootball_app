"""End-of-draft keeper-stash board.

Late in an auction the money is gone and the roster spots left are $1-3
dart throws. Some of those darts are genuinely good young players whose
*future* value (dynasty rank) is far above what a $1-3 buy plus next
year's escalation will cost to keep. This module scores every remaining
player on exactly that: cheap now, clear keeper surplus next year.

It is deliberately simple and transparent -- a dynasty-rank -> dollars
tier map scaled to this league's budget, minus the projected keeper
cost -- so the board is explainable at the table during a live draft.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from src.auction_pool import normalize_player_name


# Fraction of an average team's auction budget a player of each dynasty
# tier is worth. Anchored to typical keeper-league auction behaviour and
# scaled per-league by the real average budget, so it works the same in a
# $200 room and a $400 room.
_DYNASTY_VALUE_TIERS: Tuple[Tuple[int, float], ...] = (
    (24, 0.16),
    (48, 0.090),
    (72, 0.055),
    (100, 0.030),
    (150, 0.015),
    (10_000, 0.006),
)

_KEEPER_IRRELEVANT_POSITIONS = {"K", "DEF", "DST"}


@dataclass(frozen=True)
class KeeperStashCandidate:
    player_name: str
    position: str

    acquisition_cost: int
    next_year_keeper_cost: int
    projected_next_year_value: int
    keeper_surplus: int
    surplus_multiple: float

    dynasty_ecr: Optional[float]
    half_ecr: Optional[float]
    ascending_gap: Optional[float]

    reasons: Tuple[str, ...] = ()


def _dynasty_value_dollars(dynasty_ecr: float, average_budget: float) -> float:
    for ceiling, fraction in _DYNASTY_VALUE_TIERS:
        if dynasty_ecr <= ceiling:
            return average_budget * fraction
    return average_budget * _DYNASTY_VALUE_TIERS[-1][1]


def build_keeper_stash_board(
    *,
    available_players: Sequence[object],
    market_value_index: dict,
    fantasypros_index: dict,
    annual_escalation: int,
    average_team_budget: float,
    max_acquisition_cost: int = 6,
    future_discount: float = 0.85,
    minimum_surplus: int = 4,
    limit: int = 15,
) -> List[KeeperStashCandidate]:
    """Rank remaining cheap players by projected next-year keeper surplus.

    ``average_team_budget`` is the starting (pre-spend) auction budget per
    team -- it scales the dynasty-value tiers to this league.
    """

    escalation = max(0, int(annual_escalation))
    average_budget = max(1.0, float(average_team_budget))

    results: List[KeeperStashCandidate] = []

    for player in available_players:
        position = str(getattr(player, "position", "") or "").upper()
        if position in _KEEPER_IRRELEVANT_POSITIONS:
            continue

        key = normalize_player_name(getattr(player, "player_name", ""))
        fp = fantasypros_index.get(key)
        dynasty_ecr = getattr(fp, "dynasty_ecr", None) if fp else None
        if dynasty_ecr is None:
            continue

        market = market_value_index.get(key)
        acquisition_cost = int(
            round(
                max(
                    1.0,
                    float(getattr(market, "expected_market_value", 1.0) or 1.0),
                )
            )
        )
        if acquisition_cost > max_acquisition_cost:
            continue

        next_year_keeper_cost = acquisition_cost + escalation
        projected_value = future_discount * _dynasty_value_dollars(
            float(dynasty_ecr), average_budget
        )
        keeper_surplus = int(round(projected_value - next_year_keeper_cost))

        half_ecr = getattr(fp, "half_ecr", None)
        ascending_gap = (
            float(half_ecr) - float(dynasty_ecr)
            if half_ecr is not None
            else None
        )

        # Keep it if the future math clears a real bar, or the market is
        # clearly ascending on a young player even if the surplus is thin.
        strong_ascension = ascending_gap is not None and ascending_gap >= 20.0
        if keeper_surplus < minimum_surplus and not strong_ascension:
            continue

        reasons: List[str] = []
        reasons.append(
            "buy ~${0}, keep next year at ${1} vs ~${2} projected value".format(
                acquisition_cost,
                next_year_keeper_cost,
                int(round(projected_value)),
            )
        )
        if ascending_gap is not None and ascending_gap >= 20.0:
            reasons.append(
                "dynasty rank {0:.0f} is well ahead of redraft rank "
                "{1:.0f} -- market is rising".format(dynasty_ecr, half_ecr)
            )
        elif ascending_gap is not None and ascending_gap >= 0.0:
            reasons.append(
                "dynasty rank {0:.0f} already at or above redraft value".format(
                    dynasty_ecr
                )
            )
        if keeper_surplus >= 15:
            reasons.append("large multi-year keeper surplus")

        results.append(
            KeeperStashCandidate(
                player_name=str(getattr(player, "player_name", "")),
                position=position,
                acquisition_cost=acquisition_cost,
                next_year_keeper_cost=next_year_keeper_cost,
                projected_next_year_value=int(round(projected_value)),
                keeper_surplus=keeper_surplus,
                surplus_multiple=round(
                    projected_value / max(1, next_year_keeper_cost), 2
                ),
                dynasty_ecr=float(dynasty_ecr),
                half_ecr=float(half_ecr) if half_ecr is not None else None,
                ascending_gap=ascending_gap,
                reasons=tuple(reasons),
            )
        )

    results.sort(
        key=lambda item: (item.keeper_surplus, item.ascending_gap or 0.0),
        reverse=True,
    )
    return results[:limit]
