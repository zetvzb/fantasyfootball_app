from __future__ import annotations

import math
import re
from dataclasses import dataclass
from statistics import median
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src.historical_price_baseline import attach_historical_ranks


# league_key is deliberately excluded: with only two historical leagues it is a
# non-generalising intercept, and dropping it lets live inference run without
# threading league identity through the simulator. League behaviour is instead
# captured by the continuous cash/discretionary features below.
CATEGORICAL_FEATURES = ("position",)
NUMERIC_FEATURES = (
    "log_overall_rank",
    "overall_rank",
    "position_rank_numeric",
    "auction_stage",
    "rank_stage_interaction",
    "team_cash_per_spot",
    "team_cash_share",
    "team_open_spots_before",
    "team_legal_max_before",
    "league_cash_per_spot",
    "league_discretionary_per_spot",
    "position_sales_before",
    "position_average_price_before",
    "position_spend_share",
)


QUANTILES = (("low", 0.15), ("median", 0.50), ("high", 0.85))


def _position_rank_numeric(value: object) -> float:
    match = re.search(r"(\d+)", str(value or ""))
    return float(match.group(1)) if match else 0.0


@dataclass(frozen=True)
class ScenarioModelEvaluation:
    predictions: Tuple[dict, ...]
    metrics: Tuple[dict, ...]
    app_comparison: Tuple[dict, ...]
    unmatched_sales: int


def compare_with_baseline(
    scenario_metrics: Sequence[Mapping[str, object]],
    baseline_metrics: Sequence[Mapping[str, object]],
) -> Tuple[dict, ...]:
    baseline_by_season = {
        _integer(row.get("season")): row for row in baseline_metrics
    }
    comparisons = []
    for scenario in scenario_metrics:
        season = _integer(scenario.get("season"))
        baseline = baseline_by_season.get(season)
        if baseline is None:
            continue
        old_mae = _number(baseline.get("mean_absolute_error"))
        new_mae = _number(scenario.get("mean_absolute_error"))
        comparisons.append(
            {
                "season": season,
                "league_key": scenario.get("league_key"),
                "baseline_mean_absolute_error": old_mae,
                "scenario_mean_absolute_error": new_mae,
                "mae_improvement": round(old_mae - new_mae, 3),
                "mae_improvement_pct": round(
                    (old_mae - new_mae) / old_mae, 4
                ) if old_mae else 0.0,
                "baseline_bias": _number(baseline.get("mean_error_bias")),
                "scenario_bias": _number(scenario.get("mean_error_bias")),
                "baseline_interval_coverage": _number(
                    baseline.get("interval_coverage")
                ),
                "scenario_interval_coverage": _number(
                    scenario.get("interval_coverage")
                ),
            }
        )
    return tuple(comparisons)


def _number(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _integer(value: object) -> int:
    return int(_number(value))


def _feature_row(row: Mapping[str, object]) -> dict:
    rank = max(1.0, _number(row.get("historical_overall_rank")))
    stage = _number(row.get("auction_stage"))
    team_cash = _number(row.get("team_cash_before"))
    team_spots = max(1.0, _number(row.get("team_open_spots_before")))
    league_cash = max(1.0, _number(row.get("league_cash_before")))
    league_spots = max(1.0, _number(row.get("league_open_spots_before")))
    position_spend = _number(row.get("position_spend_before"))
    return {
        "position": str(row.get("position") or "UNKNOWN"),
        "log_overall_rank": math.log(rank),
        "overall_rank": rank,
        "position_rank_numeric": _position_rank_numeric(
            row.get("historical_position_rank")
        ),
        "auction_stage": stage,
        "rank_stage_interaction": math.log(rank) * stage,
        "team_cash_per_spot": team_cash / team_spots,
        "team_cash_share": team_cash / league_cash,
        "team_open_spots_before": team_spots,
        "team_legal_max_before": _number(row.get("team_legal_max_before")),
        "league_cash_per_spot": league_cash / league_spots,
        "league_discretionary_per_spot": (
            _number(row.get("league_discretionary_cash_before")) / league_spots
        ),
        "position_sales_before": _number(row.get("position_sales_before")),
        "position_average_price_before": _number(
            row.get("position_average_price_before")
        ),
        "position_spend_share": position_spend / league_cash,
    }


def _frame(rows: Sequence[Mapping[str, object]]) -> pd.DataFrame:
    return pd.DataFrame([_feature_row(row) for row in rows])


def _model(alpha: float) -> Pipeline:
    preprocess = ColumnTransformer(
        [
            (
                "categories",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                list(CATEGORICAL_FEATURES),
            ),
            (
                "numbers",
                SimpleImputer(strategy="median"),
                list(NUMERIC_FEATURES),
            ),
        ]
    )
    # Tuned by walk-forward season CV (scripts/tune_scenario_price_model.py):
    # deeper shrinkage + larger leaves generalise better on the small history.
    regressor = GradientBoostingRegressor(
        loss="quantile",
        alpha=alpha,
        n_estimators=300,
        learning_rate=0.08,
        max_depth=2,
        min_samples_leaf=15,
        random_state=42,
    )
    return Pipeline([("preprocess", preprocess), ("regressor", regressor)])


def train_quantile_models(
    training: Sequence[Mapping[str, object]],
) -> Dict[str, Pipeline]:
    """Fit the three deployable price quantiles from leakage-safe rows."""
    if len(training) < 30:
        raise ValueError("At least 30 ranked auction sales are required to train.")
    features = _frame(training)
    targets = np.asarray(
        [_number(row.get("winning_price")) for row in training]
    )
    fitted = {}
    for label, alpha in QUANTILES:
        model = _model(alpha)
        model.fit(features, targets)
        fitted[label] = model
    return fitted


def predict_quantiles(
    models: Mapping[str, Pipeline],
    row: Mapping[str, object],
) -> Tuple[float, float, float]:
    """Predict ordered low/median/high prices bounded by the legal maximum."""
    frame = _frame([row])
    legal_max = max(1.0, _number(row.get("team_legal_max_before")))
    ordered = sorted(
        max(1.0, min(legal_max, float(models[label].predict(frame)[0])))
        for label in ("low", "median", "high")
    )
    return tuple(round(value, 2) for value in ordered)


def predict_quantiles_batch(
    models: Mapping[str, Pipeline],
    rows: Sequence[Mapping[str, object]],
) -> List[Tuple[float, float, float]]:
    """Vectorised ``predict_quantiles`` -- one sklearn call per quantile for the
    whole list instead of one per row. Same clamp + ordering semantics."""
    if not rows:
        return []
    frame = _frame(rows)
    legal_max = np.array(
        [max(1.0, _number(row.get("team_legal_max_before"))) for row in rows]
    )
    columns = np.vstack(
        [
            np.clip(models[label].predict(frame), 1.0, legal_max)
            for label in ("low", "median", "high")
        ]
    )
    columns.sort(axis=0)
    return [
        (round(float(low), 2), round(float(mid), 2), round(float(high), 2))
        for low, mid, high in columns.T
    ]


def _fit_predict(
    training: Sequence[Mapping[str, object]],
    targets: Sequence[Mapping[str, object]],
    alpha: float,
) -> np.ndarray:
    model = _model(alpha)
    model.fit(
        _frame(training),
        np.asarray([_number(row.get("winning_price")) for row in training]),
    )
    return model.predict(_frame(targets))


def _metrics(rows: Sequence[Mapping[str, object]]) -> dict:
    errors = [float(row["scenario_error"]) for row in rows]
    absolute = [abs(value) for value in errors]
    return {
        "prediction_count": len(rows),
        "mean_absolute_error": round(sum(absolute) / len(absolute), 3),
        "median_absolute_error": round(median(absolute), 3),
        "mean_error_bias": round(sum(errors) / len(errors), 3),
        "interval_coverage": round(
            sum(bool(row["scenario_interval_hit"]) for row in rows) / len(rows),
            3,
        ),
    }


def evaluate_scenario_price_model(
    auction_features: Sequence[Mapping[str, object]],
    rankings: Sequence[Mapping[str, object]],
) -> ScenarioModelEvaluation:
    joined, unmatched = attach_historical_ranks(auction_features, rankings)
    predictions = []
    seasons = sorted({_integer(row.get("season")) for row in joined})
    for test_season in seasons:
        training = [row for row in joined if _integer(row.get("season")) < test_season]
        targets = [row for row in joined if _integer(row.get("season")) == test_season]
        if len(training) < 30 or not targets:
            continue
        low_values = _fit_predict(training, targets, QUANTILES[0][1])
        median_values = _fit_predict(training, targets, QUANTILES[1][1])
        high_values = _fit_predict(training, targets, QUANTILES[2][1])
        training_seasons = ",".join(
            str(value) for value in sorted({_integer(row.get("season")) for row in training})
        )
        for target, raw_low, raw_median, raw_high in zip(
            targets, low_values, median_values, high_values
        ):
            legal_max = max(1.0, _number(target.get("team_legal_max_before")))
            ordered = sorted(
                max(1.0, min(legal_max, float(value)))
                for value in (raw_low, raw_median, raw_high)
            )
            low, predicted, high = ordered
            actual = _number(target.get("winning_price"))
            predictions.append(
                {
                    **dict(target),
                    "scenario_low": round(low, 2),
                    "scenario_predicted_price": round(predicted, 2),
                    "scenario_high": round(high, 2),
                    "scenario_error": round(predicted - actual, 2),
                    "scenario_absolute_error": round(abs(predicted - actual), 2),
                    "scenario_interval_hit": low <= actual <= high,
                    "scenario_training_seasons": training_seasons,
                }
            )

    metrics = []
    for season in sorted({_integer(row.get("season")) for row in predictions}):
        values = [row for row in predictions if _integer(row.get("season")) == season]
        metrics.append(
            {
                "season": season,
                "league_key": values[0]["league_key"],
                **_metrics(values),
            }
        )

    app_comparison = []
    for season in sorted({_integer(row.get("season")) for row in predictions}):
        values = [
            row for row in predictions
            if _integer(row.get("season")) == season
            and row.get("modeled_market_value") not in (None, "")
        ]
        if not values:
            continue
        app_errors = [
            _number(row.get("modeled_market_value")) - _number(row.get("winning_price"))
            for row in values
        ]
        app_comparison.append(
            {
                "season": season,
                "league_key": values[0]["league_key"],
                "comparison_count": len(values),
                "app_mean_absolute_error": round(
                    sum(abs(value) for value in app_errors) / len(app_errors), 3
                ),
                "app_mean_error_bias": round(sum(app_errors) / len(app_errors), 3),
                "scenario_mean_absolute_error": _metrics(values)["mean_absolute_error"],
                "scenario_mean_error_bias": _metrics(values)["mean_error_bias"],
            }
        )

    return ScenarioModelEvaluation(
        tuple(predictions), tuple(metrics), tuple(app_comparison), unmatched
    )
