from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from src.auction_pool import normalize_player_name


@dataclass(frozen=True)
class BaselineEvaluation:
    predictions: Tuple[dict, ...]
    metrics: Tuple[dict, ...]
    unmatched_sales: int


def _integer(value: object) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(len(ordered) - 1, lower + 1)
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def attach_historical_ranks(
    sales: Sequence[Mapping[str, object]],
    rankings: Sequence[Mapping[str, object]],
) -> Tuple[List[dict], int]:
    by_id: Dict[Tuple[int, str], Mapping[str, object]] = {}
    by_name: Dict[Tuple[int, str], Mapping[str, object]] = {}
    for ranking in rankings:
        season = _integer(ranking.get("ranking_season"))
        rank = _integer(ranking.get("overall_rank"))
        if season is None or rank is None:
            continue
        player_id = str(ranking.get("sleeper_player_id") or "")
        if player_id:
            by_id[(season, player_id)] = ranking
        name = normalize_player_name(str(ranking.get("player_name") or ""))
        if name:
            by_name[(season, name)] = ranking

    joined = []
    unmatched = 0
    for sale in sales:
        season = _integer(sale.get("season")) or 0
        player_id = str(sale.get("sleeper_player_id") or "")
        ranking = by_id.get((season, player_id)) if player_id else None
        if ranking is None:
            ranking = by_name.get(
                (season, normalize_player_name(str(sale.get("player_name") or "")))
            )
        if ranking is None:
            unmatched += 1
            continue
        joined.append(
            {
                **dict(sale),
                "historical_overall_rank": _integer(ranking.get("overall_rank")),
                "historical_position_rank": str(ranking.get("position_rank") or ""),
                "ranking_date": str(ranking.get("ranking_date") or ""),
            }
        )
    return joined, unmatched


def _neighbor_prices(
    target: Mapping[str, object],
    training: Sequence[Mapping[str, object]],
    neighbor_count: int,
) -> List[float]:
    target_rank = max(1, _integer(target.get("historical_overall_rank")) or 1)
    target_position = str(target.get("position") or "")
    same_position = [
        row for row in training if str(row.get("position") or "") == target_position
    ]
    candidates = same_position if len(same_position) >= 5 else list(training)
    ordered = sorted(
        candidates,
        key=lambda row: abs(
            math.log(max(1, _integer(row.get("historical_overall_rank")) or 1))
            - math.log(target_rank)
        ),
    )
    return [float(row["winning_price"]) for row in ordered[:neighbor_count]]


def evaluate_rank_price_baseline(
    sales: Sequence[Mapping[str, object]],
    rankings: Sequence[Mapping[str, object]],
    neighbor_count: int = 25,
) -> BaselineEvaluation:
    joined, unmatched = attach_historical_ranks(sales, rankings)
    predictions = []
    seasons = sorted({_integer(row.get("season")) or 0 for row in joined})
    for test_season in seasons:
        training = [
            row for row in joined
            if (_integer(row.get("season")) or 0) < test_season
        ]
        if not training:
            continue
        for target in [
            row for row in joined
            if (_integer(row.get("season")) or 0) == test_season
        ]:
            prices = _neighbor_prices(target, training, neighbor_count)
            if not prices:
                continue
            actual = float(target["winning_price"])
            predicted = float(median(prices))
            low = _percentile(prices, 0.25)
            high = _percentile(prices, 0.75)
            predictions.append(
                {
                    **dict(target),
                    "baseline_predicted_price": round(predicted, 2),
                    "baseline_low": round(low, 2),
                    "baseline_high": round(high, 2),
                    "baseline_error": round(predicted - actual, 2),
                    "baseline_absolute_error": round(abs(predicted - actual), 2),
                    "baseline_interval_hit": low <= actual <= high,
                    "baseline_training_seasons": ",".join(
                        str(season) for season in sorted(
                            {_integer(row.get("season")) or 0 for row in training}
                        )
                    ),
                }
            )

    metrics = []
    for season in sorted({_integer(row.get("season")) or 0 for row in predictions}):
        values = [
            row for row in predictions
            if (_integer(row.get("season")) or 0) == season
        ]
        metrics.append(
            {
                "season": season,
                "league_key": values[0]["league_key"],
                "prediction_count": len(values),
                "mean_absolute_error": round(
                    sum(float(row["baseline_absolute_error"]) for row in values)
                    / len(values), 3
                ),
                "median_absolute_error": round(
                    median(float(row["baseline_absolute_error"]) for row in values), 3
                ),
                "mean_error_bias": round(
                    sum(float(row["baseline_error"]) for row in values) / len(values),
                    3,
                ),
                "interval_coverage": round(
                    sum(bool(row["baseline_interval_hit"]) for row in values)
                    / len(values),
                    3,
                ),
            }
        )
    return BaselineEvaluation(tuple(predictions), tuple(metrics), unmatched)
