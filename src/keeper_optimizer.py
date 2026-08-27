from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import List, Optional, Sequence, Tuple

from src.auction_pool import normalize_player_name
from src.keeper_recommendation import KeeperRecommendation
from src.strategy_profile import StrategyProfile


TARGET_KEEPER_COUNTS = (4, 5, 6)
CORE_POSITIONS = {"QB", "RB", "WR", "TE"}


@dataclass(frozen=True)
class KeeperOptimizationInput:
    manager_id: str
    recommendations: Tuple[KeeperRecommendation, ...]
    strategy_profile: StrategyProfile
    pre_keeper_budget: int
    roster_size: int
    minimum_bid: int
    max_keepers: int
    starting_lineup: Tuple[str, ...] = ()
    target_counts: Tuple[int, ...] = TARGET_KEEPER_COUNTS


@dataclass(frozen=True)
class KeeperCombinationScenario:
    keeper_count: int
    keeper_names: Tuple[str, ...]
    keeper_spend: int
    remaining_cash: int
    remaining_roster_spots: int
    minimum_reserve: int
    discretionary_cash: int
    current_value: float
    future_value: float
    surplus: float
    opportunity_cost: float
    roster_fit: float
    objective_score: float
    explanation: str


@dataclass(frozen=True)
class KeeperOptimizationResult:
    scenarios: Tuple[KeeperCombinationScenario, ...]
    recommended_scenario: Optional[KeeperCombinationScenario]
    combinations_evaluated: int
    warnings: Tuple[str, ...] = ()


def _validate_inputs(inputs: KeeperOptimizationInput) -> None:
    if inputs.pre_keeper_budget < 0:
        raise ValueError("Pre-keeper budget cannot be negative.")
    if inputs.roster_size < 0:
        raise ValueError("Roster size cannot be negative.")
    if inputs.minimum_bid < 0:
        raise ValueError("Minimum bid cannot be negative.")
    if inputs.max_keepers < 0:
        raise ValueError("Maximum keepers cannot be negative.")
    if inputs.strategy_profile.league_key == "":
        raise ValueError("Strategy profile league cannot be empty.")

    normalized_names = {
        normalize_player_name(recommendation.player_name)
        for recommendation in inputs.recommendations
    }
    if len(normalized_names) != len(inputs.recommendations):
        raise ValueError("Keeper candidates must be unique by player name.")
    if any(
        recommendation.manager_id != inputs.manager_id
        for recommendation in inputs.recommendations
    ):
        raise ValueError(
            "All keeper recommendations must belong to the optimized manager."
        )


def _combination_roster_fit(
    selected: Sequence[KeeperRecommendation],
    starting_lineup: Sequence[str],
) -> float:
    if not selected:
        return 0.0

    average_fit = sum(
        recommendation.roster_fit for recommendation in selected
    ) / len(selected)
    required_positions = {
        str(slot).upper()
        for slot in starting_lineup
        if str(slot).upper() in CORE_POSITIONS
    }
    if required_positions:
        selected_positions = {
            recommendation.position.upper() for recommendation in selected
        }
        coverage = len(
            required_positions.intersection(selected_positions)
        ) / len(required_positions)
    else:
        coverage = 0.5

    return max(0.0, min(1.0, 0.70 * average_fit + 0.30 * coverage))


def _build_scenario(
    selected: Sequence[KeeperRecommendation],
    inputs: KeeperOptimizationInput,
) -> Optional[KeeperCombinationScenario]:
    keeper_count = len(selected)
    keeper_spend = sum(recommendation.cost for recommendation in selected)
    remaining_cash = inputs.pre_keeper_budget - keeper_spend
    remaining_spots = (
        inputs.roster_size
        - keeper_count
    )
    if remaining_spots < 0:
        return None
    minimum_reserve = remaining_spots * inputs.minimum_bid
    if remaining_cash < minimum_reserve:
        return None

    selected_names = {
        recommendation.player_name for recommendation in selected
    }
    excluded = [
        recommendation
        for recommendation in inputs.recommendations
        if recommendation.player_name not in selected_names
    ]
    current_value = sum(
        recommendation.current_value for recommendation in selected
    )
    future_value = sum(
        recommendation.age_adjusted_future_value
        for recommendation in selected
    )
    surplus = sum(recommendation.surplus for recommendation in selected)
    opportunity_cost = sum(
        max(0.0, recommendation.surplus)
        for recommendation in excluded
    )
    roster_fit = _combination_roster_fit(
        selected,
        inputs.starting_lineup,
    )
    strategy_value = (
        inputs.strategy_profile.current_weight * current_value
        + inputs.strategy_profile.future_weight * future_value
    )
    objective_score = (
        surplus
        + 0.10 * strategy_value
        + 5.0 * roster_fit
        - opportunity_cost
    )
    discretionary_cash = remaining_cash - minimum_reserve
    keeper_names = tuple(
        sorted(recommendation.player_name for recommendation in selected)
    )
    explanation = (
        "Keep {0}: spend ${1}, retain ${2} auction cash for {3} spots "
        "(${4} reserve), produce {5:.1f} current and {6:.1f} future value, "
        "{7}${8:.2f} surplus, and incur ${9:.2f} opportunity cost. "
        "Objective {10:.2f} uses the user's {11:.0%}/{12:.0%} "
        "current/future weights plus combination roster coverage."
    ).format(
        keeper_count,
        keeper_spend,
        remaining_cash,
        remaining_spots,
        minimum_reserve,
        current_value,
        future_value,
        "+" if surplus >= 0 else "-",
        abs(surplus),
        opportunity_cost,
        objective_score,
        inputs.strategy_profile.current_weight,
        inputs.strategy_profile.future_weight,
    )

    return KeeperCombinationScenario(
        keeper_count=keeper_count,
        keeper_names=keeper_names,
        keeper_spend=keeper_spend,
        remaining_cash=remaining_cash,
        remaining_roster_spots=remaining_spots,
        minimum_reserve=minimum_reserve,
        discretionary_cash=discretionary_cash,
        current_value=round(current_value, 2),
        future_value=round(future_value, 2),
        surplus=round(surplus, 2),
        opportunity_cost=round(opportunity_cost, 2),
        roster_fit=round(roster_fit, 3),
        objective_score=round(objective_score, 2),
        explanation=explanation,
    )


def optimize_keeper_combinations(
    inputs: KeeperOptimizationInput,
) -> KeeperOptimizationResult:
    """Exhaustively select the best legal combination for each target count."""

    _validate_inputs(inputs)
    legal_counts = tuple(
        sorted(
            {
                int(count)
                for count in inputs.target_counts
                if (
                    int(count) >= 0
                    and int(count) <= inputs.max_keepers
                    and int(count) <= len(inputs.recommendations)
                    and int(count) <= inputs.roster_size
                )
            }
        )
    )

    warnings: List[str] = []
    if not legal_counts:
        warnings.append(
            "No legal 4/5/6 keeper count is available for the configured "
            "maximum, roster size, and candidate pool."
        )

    best_by_count = []
    combinations_evaluated = 0
    for keeper_count in legal_counts:
        legal_scenarios = []
        for selected in combinations(inputs.recommendations, keeper_count):
            combinations_evaluated += 1
            scenario = _build_scenario(selected, inputs)
            if scenario is not None:
                legal_scenarios.append(scenario)

        if not legal_scenarios:
            warnings.append(
                "No {0}-keeper combination can satisfy the minimum-bid "
                "reserve.".format(keeper_count)
            )
            continue

        best_by_count.append(
            max(
                legal_scenarios,
                key=lambda scenario: (
                    scenario.objective_score,
                    scenario.surplus,
                    scenario.roster_fit,
                    scenario.remaining_cash,
                    tuple(
                        name.lower() for name in scenario.keeper_names
                    ),
                ),
            )
        )

    scenarios = tuple(
        sorted(best_by_count, key=lambda scenario: scenario.keeper_count)
    )
    recommended = (
        max(
            scenarios,
            key=lambda scenario: (
                scenario.objective_score,
                scenario.surplus,
                scenario.roster_fit,
                scenario.remaining_cash,
                -scenario.keeper_count,
            ),
        )
        if scenarios
        else None
    )
    return KeeperOptimizationResult(
        scenarios=scenarios,
        recommended_scenario=recommended,
        combinations_evaluated=combinations_evaluated,
        warnings=tuple(warnings),
    )
