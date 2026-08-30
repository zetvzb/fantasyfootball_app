from src.historical_auction_state import replay_auction_states


def test_replay_builds_pre_sale_cash_reserve_stage_and_position_features():
    openings = [
        {
            "league_key": "league", "season": 2026, "manager_id": "a",
            "opening_cash": 20, "opening_roster_spots": 2, "minimum_bid": 1,
        },
        {
            "league_key": "league", "season": 2026, "manager_id": "b",
            "opening_cash": 10, "opening_roster_spots": 1, "minimum_bid": 1,
        },
    ]
    sales = [
        {
            "league_key": "league", "season": 2026, "overall_order": 1,
            "player_name": "WR One", "position": "WR", "winning_manager_id": "a",
            "winning_price": 8,
        },
        {
            "league_key": "league", "season": 2026, "overall_order": 2,
            "player_name": "WR Two", "position": "WR", "winning_manager_id": "b",
            "winning_price": 5,
        },
    ]

    result = replay_auction_states(sales, openings)

    assert result.valid
    first, second = result.features
    assert first["team_cash_before"] == 20
    assert first["team_legal_max_before"] == 19
    assert first["league_discretionary_cash_before"] == 27
    assert first["auction_stage"] == 0.0
    assert second["league_cash_before"] == 22
    assert second["position_sales_before"] == 1
    assert second["position_average_price_before"] == 8.0
    assert any(issue.code == "draft_has_unrecorded_slots" for issue in result.issues)


def test_replay_rejects_purchase_that_breaks_reserve():
    result = replay_auction_states(
        [{
            "league_key": "league", "season": 2026, "overall_order": 1,
            "player_name": "Player", "position": "RB", "winning_manager_id": "a",
            "winning_price": 10,
        }],
        [{
            "league_key": "league", "season": 2026, "manager_id": "a",
            "opening_cash": 10, "opening_roster_spots": 2, "minimum_bid": 1,
        }],
    )

    assert not result.valid
    assert any(issue.code == "sale_breaks_minimum_reserve" for issue in result.issues)
