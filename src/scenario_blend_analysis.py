from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence, Tuple


DEFAULT_PREDICTIONS_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "ml_pipeline"
    / "canonical"
    / "scenario_model_predictions.csv"
)
DEFAULT_WEIGHTS = (0.0, 0.10, 0.20, 0.25, 0.50, 1.0)


@dataclass(frozen=True)
class BlendSensitivityPoint:
    league_key: str
    season: int
    ml_weight: float
    comparison_count: int
    mean_absolute_error: float
    mean_error_bias: float
    improvement_vs_app_pct: float


@dataclass(frozen=True)
class BlendSensitivityReport:
    points: Tuple[BlendSensitivityPoint, ...]
    maximum_trial_weight: float
    best_trial_points: Tuple[BlendSensitivityPoint, ...]


def _number(value: object) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def analyze_blend_sensitivity(
    rows: Sequence[Mapping[str, object]],
    weights: Sequence[float] = DEFAULT_WEIGHTS,
    maximum_trial_weight: float = 0.25,
) -> BlendSensitivityReport:
    comparable = []
    for row in rows:
        app_value = _number(row.get("modeled_market_value"))
        ml_value = _number(row.get("scenario_predicted_price"))
        actual = _number(row.get("winning_price"))
        if app_value is None or ml_value is None or actual is None:
            continue
        comparable.append((row, app_value, ml_value, actual))
    points = []
    groups = sorted({
        (str(row.get("league_key") or ""), int(float(row.get("season") or 0)))
        for row, _, _, _ in comparable
    })
    for league_key, season in groups:
        group = [
            value for value in comparable
            if str(value[0].get("league_key") or "") == league_key
            and int(float(value[0].get("season") or 0)) == season
        ]
        app_mae = sum(abs(app - actual) for _, app, _, actual in group) / len(group)
        for raw_weight in weights:
            weight = max(0.0, min(1.0, float(raw_weight)))
            errors = [
                ((1.0 - weight) * app + weight * ml) - actual
                for _, app, ml, actual in group
            ]
            mae = sum(abs(error) for error in errors) / len(errors)
            points.append(
                BlendSensitivityPoint(
                    league_key=league_key,
                    season=season,
                    ml_weight=weight,
                    comparison_count=len(group),
                    mean_absolute_error=round(mae, 3),
                    mean_error_bias=round(sum(errors) / len(errors), 3),
                    improvement_vs_app_pct=round(
                        (app_mae - mae) / app_mae if app_mae else 0.0, 4
                    ),
                )
            )
    best_trial_points = []
    for league_key, season in groups:
        candidates = [
            point for point in points
            if point.league_key == league_key
            and point.season == season
            and 0.0 < point.ml_weight <= maximum_trial_weight
        ]
        if candidates:
            best_trial_points.append(
                min(candidates, key=lambda point: point.mean_absolute_error)
            )
    return BlendSensitivityReport(
        points=tuple(points),
        maximum_trial_weight=maximum_trial_weight,
        best_trial_points=tuple(best_trial_points),
    )


def load_blend_sensitivity_report(
    path: Path = DEFAULT_PREDICTIONS_PATH,
) -> Optional[BlendSensitivityReport]:
    path = Path(path)
    if not path.is_file():
        return None
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            report = analyze_blend_sensitivity(list(csv.DictReader(handle)))
    except (OSError, ValueError, TypeError):
        return None
    return report if report.points else None
