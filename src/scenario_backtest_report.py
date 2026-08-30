from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping, Optional, Tuple


DEFAULT_REPORT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "ml_pipeline"
    / "canonical"
    / "scenario_model_report.json"
)


@dataclass(frozen=True)
class ScenarioBacktestSeason:
    season: int
    league_key: str
    prediction_count: int
    baseline_mae: float
    scenario_mae: float
    improvement_dollars: float
    improvement_pct: float
    scenario_bias: float
    interval_coverage: float


@dataclass(frozen=True)
class AppBacktestComparison:
    season: int
    league_key: str
    comparison_count: int
    app_mae: float
    scenario_mae: float
    improvement_pct: float


@dataclass(frozen=True)
class ScenarioBacktestReport:
    seasons: Tuple[ScenarioBacktestSeason, ...]
    app_comparisons: Tuple[AppBacktestComparison, ...]
    unmatched_sales: int


def _number(row: Mapping[str, object], key: str) -> float:
    try:
        return float(row.get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def load_scenario_backtest_report(
    path: Path = DEFAULT_REPORT_PATH,
) -> Optional[ScenarioBacktestReport]:
    """Load optional offline evaluation results without becoming a runtime dependency."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    metrics_by_key = {
        (int(_number(row, "season")), str(row.get("league_key") or "")): row
        for row in payload.get("metrics", [])
        if isinstance(row, Mapping)
    }
    seasons = []
    for comparison in payload.get("baseline_comparison", []):
        if not isinstance(comparison, Mapping):
            continue
        key = (
            int(_number(comparison, "season")),
            str(comparison.get("league_key") or ""),
        )
        metric = metrics_by_key.get(key)
        if metric is None:
            continue
        seasons.append(
            ScenarioBacktestSeason(
                season=key[0],
                league_key=key[1],
                prediction_count=int(_number(metric, "prediction_count")),
                baseline_mae=_number(comparison, "baseline_mean_absolute_error"),
                scenario_mae=_number(comparison, "scenario_mean_absolute_error"),
                improvement_dollars=_number(comparison, "mae_improvement"),
                improvement_pct=_number(comparison, "mae_improvement_pct"),
                scenario_bias=_number(comparison, "scenario_bias"),
                interval_coverage=_number(comparison, "scenario_interval_coverage"),
            )
        )
    app_comparisons = []
    for comparison in payload.get("app_comparison", []):
        if not isinstance(comparison, Mapping):
            continue
        app_mae = _number(comparison, "app_mean_absolute_error")
        scenario_mae = _number(comparison, "scenario_mean_absolute_error")
        app_comparisons.append(
            AppBacktestComparison(
                season=int(_number(comparison, "season")),
                league_key=str(comparison.get("league_key") or ""),
                comparison_count=int(_number(comparison, "comparison_count")),
                app_mae=app_mae,
                scenario_mae=scenario_mae,
                improvement_pct=(app_mae - scenario_mae) / app_mae if app_mae else 0.0,
            )
        )
    if not seasons:
        return None
    return ScenarioBacktestReport(
        seasons=tuple(seasons),
        app_comparisons=tuple(app_comparisons),
        unmatched_sales=int(payload.get("unmatched_sales", 0) or 0),
    )
