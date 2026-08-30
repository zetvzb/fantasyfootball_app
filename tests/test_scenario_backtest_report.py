import json

from src.scenario_backtest_report import load_scenario_backtest_report


def test_loads_and_joins_backtest_metrics(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps({
        "metrics": [{
            "season": 2025, "league_key": "league", "prediction_count": 10,
        }],
        "baseline_comparison": [{
            "season": 2025, "league_key": "league",
            "baseline_mean_absolute_error": 12,
            "scenario_mean_absolute_error": 9,
            "mae_improvement": 3, "mae_improvement_pct": 0.25,
            "scenario_bias": -1, "scenario_interval_coverage": 0.8,
        }],
        "app_comparison": [{
            "season": 2025, "league_key": "league", "comparison_count": 8,
            "app_mean_absolute_error": 15, "scenario_mean_absolute_error": 10,
        }],
        "unmatched_sales": 2,
    }), encoding="utf-8")

    report = load_scenario_backtest_report(path)

    assert report is not None
    assert report.seasons[0].prediction_count == 10
    assert report.seasons[0].improvement_pct == 0.25
    assert round(report.app_comparisons[0].improvement_pct, 3) == 0.333
    assert report.unmatched_sales == 2


def test_missing_or_invalid_report_is_optional(tmp_path):
    assert load_scenario_backtest_report(tmp_path / "missing.json") is None
    invalid = tmp_path / "invalid.json"
    invalid.write_text("not json", encoding="utf-8")
    assert load_scenario_backtest_report(invalid) is None
