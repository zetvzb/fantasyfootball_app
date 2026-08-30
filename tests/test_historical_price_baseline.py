from src.historical_price_baseline import evaluate_rank_price_baseline


def test_rank_price_baseline_uses_only_prior_seasons_and_reports_metrics():
    rankings = []
    sales = []
    for season, price_offset in ((2024, 0), (2025, 5)):
        for rank in range(1, 7):
            player_id = "{0}-{1}".format(season, rank)
            rankings.append(
                {
                    "ranking_season": season,
                    "overall_rank": rank,
                    "position_rank": "WR{0}".format(rank),
                    "player_name": player_id,
                    "sleeper_player_id": player_id,
                }
            )
            sales.append(
                {
                    "league_key": "league", "season": season,
                    "player_name": player_id, "sleeper_player_id": player_id,
                    "position": "WR", "winning_price": 50 - rank + price_offset,
                }
            )

    result = evaluate_rank_price_baseline(sales, rankings, neighbor_count=3)

    assert len(result.predictions) == 6
    assert result.unmatched_sales == 0
    assert result.metrics[0]["season"] == 2025
    assert all(
        prediction["baseline_training_seasons"] == "2024"
        for prediction in result.predictions
    )


def test_rank_join_falls_back_to_normalized_player_name():
    result = evaluate_rank_price_baseline(
        [
            {"league_key": "x", "season": 2024, "player_name": "A.J. Player",
             "sleeper_player_id": "", "position": "RB", "winning_price": 10},
            {"league_key": "x", "season": 2025, "player_name": "AJ Player",
             "sleeper_player_id": "", "position": "RB", "winning_price": 12},
        ],
        [
            {"ranking_season": 2024, "overall_rank": 10,
             "player_name": "AJ Player", "sleeper_player_id": ""},
            {"ranking_season": 2025, "overall_rank": 9,
             "player_name": "A.J. Player", "sleeper_player_id": ""},
        ],
    )

    assert result.unmatched_sales == 0
    assert len(result.predictions) == 1
