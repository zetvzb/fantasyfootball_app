from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

from src.auction_pool import normalize_player_name


@dataclass(frozen=True)
class CompletedDraftSeason:
    season: int
    sales: Tuple[object, ...]
    source_estimates: Mapping[str, Mapping[str, float]]


@dataclass(frozen=True)
class PriceDistribution:
    sample_size: int
    minimum: float
    percentile_25: float
    median: float
    percentile_75: float
    maximum: float


@dataclass(frozen=True)
class ManagerCalibration:
    manager_id: str
    purchase_count: int
    average_price: float
    aggressiveness_multiplier: float


@dataclass(frozen=True)
class SeasonCalibration:
    season: int
    sale_count: int
    inflation_multiplier: float


@dataclass(frozen=True)
class YearOverYearCalibration:
    seasons: Tuple[SeasonCalibration, ...]
    inflation_multiplier: float
    scarcity_multipliers: Mapping[str, float]
    manager_behavior: Mapping[str, ManagerCalibration]
    source_bias: Mapping[str, float]
    price_distributions: Mapping[str, PriceDistribution]

    def calibrated_price(
        self,
        base_price: float,
        position: str,
        manager_id: str = "",
        source: str = "",
    ) -> float:
        source_adjustment = float(self.source_bias.get(source, 0.0))
        manager = self.manager_behavior.get(manager_id)
        manager_multiplier = (
            manager.aggressiveness_multiplier if manager is not None else 1.0
        )
        return round(
            max(
                0.0,
                (float(base_price) + source_adjustment)
                * self.inflation_multiplier
                * float(self.scarcity_multipliers.get(position, 1.0))
                * manager_multiplier,
            ),
            2,
        )


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(len(ordered) - 1, lower + 1)
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _distribution(values: Sequence[float]) -> PriceDistribution:
    ordered = sorted(float(value) for value in values)
    return PriceDistribution(
        sample_size=len(ordered),
        minimum=round(ordered[0], 2),
        percentile_25=round(_percentile(ordered, 0.25), 2),
        median=round(_percentile(ordered, 0.50), 2),
        percentile_75=round(_percentile(ordered, 0.75), 2),
        maximum=round(ordered[-1], 2),
    )


def build_year_over_year_calibration(
    completed_drafts: Sequence[CompletedDraftSeason],
) -> YearOverYearCalibration:
    """Learn deterministic market adjustments from completed draft ledgers."""

    all_sales = []
    season_results = []
    source_errors = {}
    for completed in sorted(completed_drafts, key=lambda value: value.season):
        sales = list(completed.sales)
        all_sales.extend(sales)
        ratios = [
            float(sale.price) / float(sale.modeled_market_value)
            for sale in sales
            if getattr(sale, "modeled_market_value", None)
            and float(sale.modeled_market_value) > 0
        ]
        season_results.append(
            SeasonCalibration(
                season=int(completed.season),
                sale_count=len(sales),
                inflation_multiplier=round(
                    sum(ratios) / len(ratios), 4
                ) if ratios else 1.0,
            )
        )
        sale_by_name = {
            normalize_player_name(sale.player_name): sale for sale in sales
        }
        for source, estimates in completed.source_estimates.items():
            for player_name, estimate in estimates.items():
                sale = sale_by_name.get(normalize_player_name(player_name))
                if sale is not None:
                    source_errors.setdefault(source, []).append(
                        float(sale.price) - float(estimate)
                    )

    modeled_ratios = [
        float(sale.price) / float(sale.modeled_market_value)
        for sale in all_sales
        if getattr(sale, "modeled_market_value", None)
        and float(sale.modeled_market_value) > 0
    ]
    overall_inflation = (
        sum(modeled_ratios) / len(modeled_ratios) if modeled_ratios else 1.0
    )
    overall_average = (
        sum(float(sale.price) for sale in all_sales) / len(all_sales)
        if all_sales else 0.0
    )

    prices_by_position = {}
    prices_by_manager = {}
    for sale in all_sales:
        prices_by_position.setdefault(str(sale.position), []).append(float(sale.price))
        prices_by_manager.setdefault(str(sale.manager_id), []).append(float(sale.price))

    scarcity = {
        position: round(
            (sum(prices) / len(prices)) / overall_average, 4
        ) if overall_average else 1.0
        for position, prices in prices_by_position.items()
    }
    managers = {
        manager_id: ManagerCalibration(
            manager_id=manager_id,
            purchase_count=len(prices),
            average_price=round(sum(prices) / len(prices), 2),
            aggressiveness_multiplier=round(
                (sum(prices) / len(prices)) / overall_average, 4
            ) if overall_average else 1.0,
        )
        for manager_id, prices in prices_by_manager.items()
    }
    distributions = {
        position: _distribution(prices)
        for position, prices in prices_by_position.items()
    }
    if all_sales:
        distributions["ALL"] = _distribution(
            [float(sale.price) for sale in all_sales]
        )

    return YearOverYearCalibration(
        seasons=tuple(season_results),
        inflation_multiplier=round(overall_inflation, 4),
        scarcity_multipliers=scarcity,
        manager_behavior=managers,
        source_bias={
            source: round(sum(errors) / len(errors), 2)
            for source, errors in source_errors.items()
            if errors
        },
        price_distributions=distributions,
    )
