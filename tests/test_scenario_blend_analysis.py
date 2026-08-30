from src.scenario_blend_analysis import analyze_blend_sensitivity


def test_blend_sensitivity_evaluates_only_comparable_rows():
    rows = [
        {
            "league_key": "gdfm", "season": 2026, "winning_price": 20,
            "modeled_market_value": 10, "scenario_predicted_price": 20,
        },
        {
            "league_key": "gdfm", "season": 2026, "winning_price": 30,
            "modeled_market_value": 20, "scenario_predicted_price": 30,
        },
        {
            "league_key": "gdfm", "season": 2026, "winning_price": 5,
            "modeled_market_value": "", "scenario_predicted_price": 5,
        },
    ]

    report = analyze_blend_sensitivity(rows, weights=(0, 0.25, 1))

    assert [point.comparison_count for point in report.points] == [2, 2, 2]
    assert [point.mean_absolute_error for point in report.points] == [10, 7.5, 0]
    assert report.best_trial_points[0].ml_weight == 0.25


def test_trial_candidate_never_exceeds_weight_ceiling():
    rows = [{
        "league_key": "league", "season": 2026, "winning_price": 10,
        "modeled_market_value": 0, "scenario_predicted_price": 10,
    }]
    report = analyze_blend_sensitivity(rows, weights=(0.5, 1.0))
    assert report.best_trial_points == ()
