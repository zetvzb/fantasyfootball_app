from src.setup_resource_import import parse_setup_resource_rows


def test_resource_import_supports_keeper_and_history_rows_and_warns_on_devy():
    result = parse_setup_resource_rows(
        [
            {"Type": "keeper", "Team": "My Team", "Player": "Keeper",
             "Position": "WR", "Value": 80, "Keeper Cost": 15},
            {"Type": "devy", "Team": "Opponent", "Player": "Prospect",
             "Position": "RB", "Value": 70, "Status": "in_college"},
            {"Type": "history", "Team": "My Team", "Player": "Past Buy",
             "Position": "QB", "Year": 2025, "Price": "$22"},
        ],
        manager_aliases={"my team": "me", "opponent": "them"},
        default_manager_id="me",
        current_season=2026,
    )

    assert result.keeper_candidates[0].player_name == "Keeper"
    assert result.keeper_candidates[0].cost == 15
    assert result.keeper_candidates[0].future_values == (80.0,)
    assert result.historical_sales[0].price == 22
    assert len(result.warnings) == 1
    assert "devy" in result.warnings[0].lower()


def test_resource_defaults_unassigned_keeper_to_current_manager_and_warns_bad_rows():
    result = parse_setup_resource_rows(
        [
            {"Player": "Unassigned", "Value": 50},
            {"Type": "history", "Player": "No Price"},
            {"Team": "Unknown", "Player": "Unknown Team"},
        ],
        manager_aliases={},
        default_manager_id="me",
        current_season=2026,
    )
    assert result.keeper_candidates[0].manager_id == "me"
    assert len(result.warnings) == 2


def test_resource_import_preserves_zero_cost_and_zero_history_price():
    result = parse_setup_resource_rows(
        [
            {"Type": "keeper", "Player": "Free Keeper", "Keeper Cost": 0},
            {"Type": "history", "Player": "Free Buy", "Price": 0},
        ],
        manager_aliases={},
        default_manager_id="me",
        current_season=2026,
    )
    assert result.keeper_candidates[0].cost == 0
    assert result.historical_sales[0].price == 0
