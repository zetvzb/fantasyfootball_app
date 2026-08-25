from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple


@dataclass(frozen=True)
class RunHotWarning:
    position: str
    tier: str
    competing_managers: Tuple[str, ...]
    available_players: int
    pressure_score: float
    warning: str


@dataclass(frozen=True)
class RunHotResult:
    warnings: Tuple[RunHotWarning, ...]
    position_pressure: Mapping[str, float]


def detect_run_hot(
    *,
    opponent_profiles: Sequence[object],
    available_tier_counts: Mapping[Tuple[str, str], int],
    minimum_cash_strength: float = 0.65,
) -> RunHotResult:
    warnings = []
    position_pressure = {}
    for (position, tier), available in sorted(available_tier_counts.items()):
        competitors = tuple(
            profile.manager_id
            for profile in opponent_profiles
            if float(profile.cash_strength) >= minimum_cash_strength
            and position in profile.likely_positions
            and tier in profile.likely_tiers
        )
        if len(competitors) < 2 or available > len(competitors):
            continue
        pressure = min(1.0, len(competitors) / max(1.0, float(available + 1)))
        warnings.append(
            RunHotWarning(
                position=position,
                tier=tier,
                competing_managers=competitors,
                available_players=int(available),
                pressure_score=round(pressure, 3),
                warning=(
                    "{0} cash-rich teams overlap on {1} {2} targets with only "
                    "{3} option(s) available.".format(
                        len(competitors), position, tier, available
                    )
                ),
            )
        )
        position_pressure[position] = max(position_pressure.get(position, 0.0), pressure)
    return RunHotResult(tuple(warnings), position_pressure)


def build_available_tier_counts(market_values: Sequence[object]) -> Mapping[Tuple[str, str], int]:
    counts = {}
    for value in market_values:
        price = float(value.expected_market_value)
        tier = "elite" if price >= 40 else "starter" if price >= 15 else "depth"
        key = (str(value.position), tier)
        counts[key] = counts.get(key, 0) + 1
    return counts
