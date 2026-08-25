from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from src.keeper_domain import KeeperContract, KeeperDomainRules
from src.strategy_profile import StrategyProfile


@dataclass(frozen=True)
class KeeperYearEconomics:
    """One season of a keeper's projected contract economics."""

    year: int
    projected_cost: int
    projected_player_value: float
    yearly_surplus: float
    cumulative_surplus: float
    strategy_weight: float
    strategy_adjusted_surplus: float
    cumulative_strategy_adjusted_surplus: float


@dataclass(frozen=True)
class KeeperEconomicsProjection:
    """Deterministic 2-3 year keeper cost and value projection."""

    manager_id: str
    player_name: str
    horizon_years: int
    years: Tuple[KeeperYearEconomics, ...]
    cumulative_surplus: float
    strategy_adjusted_cumulative_surplus: float
    break_even_year: Optional[int]
    keeper_runway_years: int
    explanation: str


def _strategy_weights(
    strategy_profile: StrategyProfile,
    horizon_years: int,
) -> Tuple[float, ...]:
    future_year_count = horizon_years - 1
    future_year_weight = (
        strategy_profile.future_weight / future_year_count
    )
    return (strategy_profile.current_weight,) + (
        future_year_weight,
    ) * future_year_count


def project_keeper_economics(
    *,
    contract: KeeperContract,
    rules: KeeperDomainRules,
    projected_player_values: Tuple[float, ...],
    strategy_profile: StrategyProfile,
) -> KeeperEconomicsProjection:
    """Project costs and surplus for the configured keeper horizon.

    Year 1 is the upcoming keeper season represented by ``current_cost``.
    A mid-season pickup therefore starts at the configured pickup price and
    transitions to ordinary annual escalation beginning in year 2.
    """

    rules.validate()
    if contract.future_horizon_years != rules.future_horizon_years:
        raise ValueError(
            "Keeper contract and league rule horizons must match."
        )
    if len(projected_player_values) != rules.future_horizon_years:
        raise ValueError(
            "Projected player values must contain exactly {0} years.".format(
                rules.future_horizon_years
            )
        )
    if any(float(value) < 0.0 for value in projected_player_values):
        raise ValueError("Projected player values cannot be negative.")

    strategy_weights = _strategy_weights(
        strategy_profile,
        rules.future_horizon_years,
    )
    yearly_results = []
    cumulative_surplus = 0.0
    cumulative_strategy_surplus = 0.0
    break_even_year = None
    keeper_runway_years = 0
    runway_open = True

    for index, raw_player_value in enumerate(projected_player_values):
        year = index + 1
        projected_cost = (
            contract.current_cost + index * rules.annual_escalation
        )
        player_value = float(raw_player_value)
        yearly_surplus = player_value - float(projected_cost)
        cumulative_surplus += yearly_surplus
        strategy_weight = strategy_weights[index]
        strategy_surplus = yearly_surplus * strategy_weight
        cumulative_strategy_surplus += strategy_surplus

        if yearly_surplus <= 0.0 and break_even_year is None:
            break_even_year = year
        if runway_open and yearly_surplus > 0.0:
            keeper_runway_years += 1
        else:
            runway_open = False

        yearly_results.append(
            KeeperYearEconomics(
                year=year,
                projected_cost=projected_cost,
                projected_player_value=round(player_value, 2),
                yearly_surplus=round(yearly_surplus, 2),
                cumulative_surplus=round(cumulative_surplus, 2),
                strategy_weight=round(strategy_weight, 4),
                strategy_adjusted_surplus=round(strategy_surplus, 2),
                cumulative_strategy_adjusted_surplus=round(
                    cumulative_strategy_surplus,
                    2,
                ),
            )
        )

    break_even_text = (
        "year {0}".format(break_even_year)
        if break_even_year is not None
        else "beyond the projection horizon"
    )
    explanation = (
        "{0}-year projection: ${1:.2f} cumulative surplus, ${2:.2f} "
        "strategy-adjusted surplus, break-even {3}, and {4} year(s) "
        "of positive-surplus keeper runway. Costs begin at ${5} and "
        "escalate ${6} annually."
    ).format(
        rules.future_horizon_years,
        cumulative_surplus,
        cumulative_strategy_surplus,
        break_even_text,
        keeper_runway_years,
        contract.current_cost,
        rules.annual_escalation,
    )

    return KeeperEconomicsProjection(
        manager_id=contract.manager_id,
        player_name=contract.player_name,
        horizon_years=rules.future_horizon_years,
        years=tuple(yearly_results),
        cumulative_surplus=round(cumulative_surplus, 2),
        strategy_adjusted_cumulative_surplus=round(
            cumulative_strategy_surplus,
            2,
        ),
        break_even_year=break_even_year,
        keeper_runway_years=keeper_runway_years,
        explanation=explanation,
    )
