from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Sequence, Tuple

from src.scalable_simulator import SimulationPlayer, SimulationSummary, run_simulations


class OpeningStrategy(str, Enum):
    ELITE_RB = "elite-rb"
    ELITE_WR = "elite-wr"
    BALANCED = "balanced"
    VALUE_WAITING = "value-waiting"
    YOUTH_HEAVY = "youth-heavy"
    STARS_AND_SCRUBS = "stars-and-scrubs"


@dataclass(frozen=True)
class StrategyComparison:
    strategy: OpeningStrategy
    average_roster_value: float
    average_spend: float
    full_roster_rate: float
    summary: SimulationSummary


def _strategy_players(
    players: Sequence[SimulationPlayer], strategy: OpeningStrategy
) -> Tuple[SimulationPlayer, ...]:
    transformed = []
    prices = sorted((player.expected_price for player in players), reverse=True)
    star_line = prices[max(0, min(len(prices) - 1, len(prices) // 4))] if prices else 0
    for player in players:
        multiplier = 1.0
        if strategy == OpeningStrategy.ELITE_RB and player.position == "RB" and player.expected_price >= star_line:
            multiplier = 1.25
        elif strategy == OpeningStrategy.ELITE_WR and player.position == "WR" and player.expected_price >= star_line:
            multiplier = 1.25
        elif strategy == OpeningStrategy.VALUE_WAITING and player.expected_price < star_line:
            multiplier = 1.18
        elif strategy == OpeningStrategy.YOUTH_HEAVY:
            age = getattr(player, "age", 26.0)
            multiplier = 1.20 if age <= 25 else 0.9
        elif strategy == OpeningStrategy.STARS_AND_SCRUBS:
            multiplier = 1.22 if player.expected_price >= star_line else 0.92
        transformed.append(replace(player, value=player.value * multiplier))
    return tuple(transformed)


def compare_opening_strategies(
    players: Sequence[SimulationPlayer],
    budget: int,
    roster_spots: int,
    simulations: int = 500,
    seed: int = 1,
) -> Tuple[StrategyComparison, ...]:
    comparisons = []
    for offset, strategy in enumerate(OpeningStrategy):
        summary = run_simulations(
            _strategy_players(players, strategy),
            budget=budget,
            roster_spots=roster_spots,
            simulations=simulations,
            seed=seed + offset,
        )
        comparisons.append(
            StrategyComparison(
                strategy=strategy,
                average_roster_value=summary.average_roster_value,
                average_spend=summary.average_spend,
                full_roster_rate=summary.full_roster_rate,
                summary=summary,
            )
        )
    comparisons.sort(
        key=lambda result: (result.average_roster_value, result.full_roster_rate),
        reverse=True,
    )
    return tuple(comparisons)
