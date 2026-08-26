from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Mapping, Sequence, Tuple

if TYPE_CHECKING:
    from src.historical_market import HistoricalMarketModel


@dataclass(frozen=True)
class ManagerTendencyObservation:
    manager_id: str
    season: int
    position: str
    tier: str
    auction_stage: str
    actual_price: float
    expected_price: float
    was_keeper: bool = False
    ending_cash: float = 0.0


@dataclass(frozen=True)
class ManagerTendencyProfileV2:
    manager_id: str
    observation_count: int
    confidence: float
    historical_aggression: float
    position_premiums: Tuple[Tuple[str, float], ...]
    stars_spend_share: float
    depth_spend_share: float
    auction_timing_share: Tuple[Tuple[str, float], ...]
    keeper_rate: float
    average_unused_cash: float


@dataclass(frozen=True)
class ManagerTendencyModelV2:
    profiles: Tuple[ManagerTendencyProfileV2, ...]
    warnings: Tuple[str, ...] = ()


def _weight(season: int, as_of_season: int, half_life_years: float) -> float:
    age = max(0, int(as_of_season) - int(season))
    return 0.5 ** (float(age) / max(0.1, float(half_life_years)))


def build_manager_tendency_model(
    observations: Sequence[ManagerTendencyObservation],
    *,
    as_of_season: int,
    half_life_years: float = 2.0,
) -> ManagerTendencyModelV2:
    grouped: Dict[str, list] = {}
    for observation in observations:
        grouped.setdefault(observation.manager_id, []).append(observation)
    profiles = []
    for manager_id, items in sorted(grouped.items()):
        weighted = [
            (item, _weight(item.season, as_of_season, half_life_years))
            for item in items
        ]
        total_weight = sum(weight for _, weight in weighted)
        expected = sum(item.expected_price * weight for item, weight in weighted)
        actual = sum(item.actual_price * weight for item, weight in weighted)
        position_totals: Dict[str, list] = {}
        stage_weights: Dict[str, float] = {}
        tier_spend: Dict[str, float] = {}
        keeper_weight = 0.0
        season_cash: Dict[int, Tuple[float, float]] = {}
        for item, weight in weighted:
            totals = position_totals.setdefault(item.position, [0.0, 0.0])
            totals[0] += item.actual_price * weight
            totals[1] += item.expected_price * weight
            stage_weights[item.auction_stage] = stage_weights.get(item.auction_stage, 0.0) + weight
            tier_spend[item.tier] = tier_spend.get(item.tier, 0.0) + item.actual_price * weight
            if item.was_keeper:
                keeper_weight += weight
            current_cash = season_cash.get(item.season)
            if current_cash is None:
                season_cash[item.season] = (item.ending_cash, weight)
        total_spend = sum(tier_spend.values())
        cash_weight = sum(weight for _, weight in season_cash.values())
        profiles.append(
            ManagerTendencyProfileV2(
                manager_id=manager_id,
                observation_count=len(items),
                confidence=round(total_weight / (total_weight + 8.0), 3),
                historical_aggression=round(actual / expected, 3) if expected else 1.0,
                position_premiums=tuple(
                    (position, round(values[0] / values[1], 3) if values[1] else 1.0)
                    for position, values in sorted(position_totals.items())
                ),
                stars_spend_share=round(tier_spend.get("star", 0.0) / total_spend, 3)
                if total_spend else 0.0,
                depth_spend_share=round(tier_spend.get("depth", 0.0) / total_spend, 3)
                if total_spend else 0.0,
                auction_timing_share=tuple(
                    (stage, round(weight / total_weight, 3))
                    for stage, weight in sorted(stage_weights.items())
                ),
                keeper_rate=round(keeper_weight / total_weight, 3) if total_weight else 0.0,
                average_unused_cash=round(
                    sum(cash * weight for cash, weight in season_cash.values()) / cash_weight,
                    2,
                ) if cash_weight else 0.0,
            )
        )
    return ManagerTendencyModelV2(tuple(profiles))


def build_tendency_observations_from_market(
    model: "HistoricalMarketModel",
) -> Tuple[ManagerTendencyObservation, ...]:
    """Derive tendency observations from recorded historical sales.

    This is the real, already-populated data source (the same sales that
    power the Historical Market view) -- nothing ever wrote to the
    ``manager_tendency_observations`` metadata key the model used to read
    from, so tendencies always came back empty regardless of how much
    draft history a league had.
    """

    observations = []
    for sale in model.mapped_sales:
        if sale.manager_id is None or not sale.position:
            continue
        profile = model.position_profiles.get(sale.position)
        if profile is None or profile.average_price <= 0:
            continue
        if sale.price >= profile.p75_price:
            tier = "star"
        elif sale.price >= profile.average_price:
            tier = "starter"
        else:
            tier = "depth"
        observations.append(
            ManagerTendencyObservation(
                manager_id=sale.manager_id,
                season=int(sale.year),
                position=sale.position,
                tier=tier,
                auction_stage="unknown",
                actual_price=float(sale.price),
                expected_price=float(profile.average_price),
            )
        )
    return tuple(observations)


def build_manager_tendencies_from_mappings(
    records: Sequence[Mapping[str, object]],
    *,
    as_of_season: int,
) -> ManagerTendencyModelV2:
    observations = []
    warnings = []
    for index, record in enumerate(records):
        try:
            observations.append(
                ManagerTendencyObservation(
                    manager_id=str(record["manager_id"]),
                    season=int(record["season"]),
                    position=str(record.get("position") or "UNKNOWN").upper(),
                    tier=str(record.get("tier") or "depth"),
                    auction_stage=str(record.get("auction_stage") or "unknown"),
                    actual_price=float(record["actual_price"]),
                    expected_price=float(record["expected_price"]),
                    was_keeper=bool(record.get("was_keeper", False)),
                    ending_cash=float(record.get("ending_cash", 0.0) or 0.0),
                )
            )
        except (KeyError, TypeError, ValueError):
            warnings.append("Manager tendency row {0} is invalid.".format(index + 1))
    model = build_manager_tendency_model(observations, as_of_season=as_of_season)
    return ManagerTendencyModelV2(model.profiles, tuple(warnings))
