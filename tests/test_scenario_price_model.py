from src.scenario_price_model import compare_with_baseline, evaluate_scenario_price_model


def _data():
    sales = []
    rankings = []
    for season, inflation in ((2024, 0), (2025, 4)):
        for index in range(40):
            player_id = "{0}-{1}".format(season, index)
            position = "WR" if index % 2 else "RB"
            rankings.append(
                {
                    "ranking_season": season,
                    "overall_rank": index + 1,
                    "position_rank": "{0}{1}".format(position, index + 1),
                    "player_name": player_id,
                    "sleeper_player_id": player_id,
                }
            )
            sales.append(
                {
                    "league_key": "league", "season": season,
                    "overall_order": index + 1, "player_name": player_id,
                    "sleeper_player_id": player_id, "position": position,
                    "winning_price": max(1, 50 - index + inflation),
                    "auction_stage": index / 40.0, "team_cash_before": 200,
                    "team_open_spots_before": 10, "team_legal_max_before": 191,
                    "league_cash_before": 2000, "league_open_spots_before": 100,
                    "league_discretionary_cash_before": 1900,
                    "position_sales_before": index // 2,
                    "position_spend_before": index * 10,
                    "position_average_price_before": 20,
                }
            )
    return sales, rankings


def test_scenario_model_uses_prior_seasons_and_emits_ordered_quantiles():
    sales, rankings = _data()
    result = evaluate_scenario_price_model(sales, rankings)

    assert result.unmatched_sales == 0
    assert len(result.predictions) == 40
    assert result.metrics[0]["season"] == 2025
    assert all(row["scenario_training_seasons"] == "2024" for row in result.predictions)
    assert all(
        row["scenario_low"] <= row["scenario_predicted_price"] <= row["scenario_high"]
        for row in result.predictions
    )
    assert all(row["scenario_low"] >= 1 for row in result.predictions)


def test_baseline_comparison_reports_mae_improvement():
    comparison = compare_with_baseline(
        [{"season": 2025, "league_key": "league", "mean_absolute_error": 8,
          "mean_error_bias": 1, "interval_coverage": 0.8}],
        [{"season": 2025, "mean_absolute_error": 10, "mean_error_bias": -3,
          "interval_coverage": 0.6}],
    )

    assert comparison[0]["mae_improvement"] == 2
    assert comparison[0]["mae_improvement_pct"] == 0.2
