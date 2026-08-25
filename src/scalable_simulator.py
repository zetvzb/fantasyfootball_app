from __future__ import annotations

from dataclasses import dataclass
import random
from statistics import mean
from typing import Dict, Mapping, Sequence, Tuple


@dataclass(frozen=True)
class SimulationPlayer:
    player_name: str
    position: str
    expected_price: float
    price_stddev: float
    value: float


@dataclass(frozen=True)
class SimulationOutcome:
    spend: int
    roster: Tuple[str, ...]
    position_counts: Mapping[str, int]
    roster_value: float
    unspent_cash: int


@dataclass(frozen=True)
class SimulationSummary:
    seed: int
    simulation_count: int
    outcomes: Tuple[SimulationOutcome, ...]
    player_price_distributions: Mapping[str, Tuple[int, ...]]
    average_spend: float
    average_roster_value: float
    full_roster_rate: float


def run_simulations(
    players: Sequence[SimulationPlayer],
    budget: int,
    roster_spots: int,
    simulations: int = 1000,
    seed: int = 1,
) -> SimulationSummary:
    if simulations <= 0 or roster_spots <= 0 or budget < roster_spots:
        raise ValueError("Simulation count, roster spots, and budget must be legal.")
    rng = random.Random(seed)
    prices: Dict[str, list] = {player.player_name: [] for player in players}
    outcomes = []
    for _ in range(simulations):
        drawn = []
        for player in players:
            price = max(1, int(round(rng.gauss(player.expected_price, player.price_stddev))))
            prices[player.player_name].append(price)
            drawn.append((player, price))
        # Value efficiency with deterministic random tie-breaking per run.
        rng.shuffle(drawn)
        drawn.sort(key=lambda pair: pair[0].value / max(1, pair[1]), reverse=True)
        cash = int(budget)
        roster = []
        value = 0.0
        positions: Dict[str, int] = {}
        for player, price in drawn:
            open_after = roster_spots - len(roster) - 1
            if len(roster) >= roster_spots or price + open_after > cash:
                continue
            roster.append(player.player_name)
            value += player.value
            cash -= price
            positions[player.position] = positions.get(player.position, 0) + 1
        outcomes.append(
            SimulationOutcome(
                spend=budget - cash,
                roster=tuple(roster),
                position_counts=dict(positions),
                roster_value=round(value, 3),
                unspent_cash=cash,
            )
        )
    frozen_outcomes = tuple(outcomes)
    return SimulationSummary(
        seed=seed,
        simulation_count=simulations,
        outcomes=frozen_outcomes,
        player_price_distributions={key: tuple(values) for key, values in prices.items()},
        average_spend=mean(outcome.spend for outcome in frozen_outcomes),
        average_roster_value=mean(outcome.roster_value for outcome in frozen_outcomes),
        full_roster_rate=(
            sum(len(outcome.roster) == roster_spots for outcome in frozen_outcomes)
            / float(simulations)
        ),
    )
