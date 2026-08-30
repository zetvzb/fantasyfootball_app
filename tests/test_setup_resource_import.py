from src.setup_resource_import import parse_setup_resource_rows


SLEEPER_PLAYERS = {
    "101": {"full_name": "Justin Jefferson", "position": "WR", "active": True},
    "102": {"full_name": "Kenneth Walker III", "position": "RB", "active": True},
}


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


def test_resource_import_matches_keepers_to_sleeper_and_flags_unmatched():
    result = parse_setup_resource_rows(
        [
            {"Type": "keeper", "Player": "Justin Jefferson", "Keeper Cost": 60},
            # Suffix mismatch -- exercises the same collision-safe matcher
            # used everywhere else, not a literal string match.
            {"Type": "keeper", "Player": "Kenneth Walker", "Keeper Cost": 10},
            {"Type": "keeper", "Player": "Totally Made Up Guy", "Keeper Cost": 5},
        ],
        manager_aliases={},
        default_manager_id="me",
        current_season=2026,
        sleeper_players=SLEEPER_PLAYERS,
    )

    by_name = {
        candidate.player_name: candidate for candidate in result.keeper_candidates
    }
    assert by_name["Justin Jefferson"].sleeper_player_id == "101"
    assert by_name["Kenneth Walker"].sleeper_player_id == "102"
    assert by_name["Totally Made Up Guy"].sleeper_player_id is None

    assert len(result.warnings) == 1
    assert "Totally Made Up Guy" in result.warnings[0]
    assert "Sleeper" in result.warnings[0]


def test_resource_import_skips_matching_when_no_sleeper_players_supplied():
    result = parse_setup_resource_rows(
        [
            {"Type": "keeper", "Player": "Anyone At All", "Keeper Cost": 5},
        ],
        manager_aliases={},
        default_manager_id="me",
        current_season=2026,
    )
    assert result.keeper_candidates[0].sleeper_player_id is None
    assert result.warnings == ()


def test_history_rows_without_type_column_are_detected_by_year_plus_price():
    result = parse_setup_resource_rows(
        [
            {"Team": "My Team", "Player": "Past Buy A",
             "Position": "RB", "Year": 2024, "Price": 40},
            {"Team": "My Team", "Player": "Past Buy B",
             "Position": "WR", "Year": 2025, "Price": "$18"},
            {"Team": "My Team", "Player": "A Keeper",
             "Position": "TE", "Keeper Cost": 12},
        ],
        manager_aliases={"my team": "me"},
        default_manager_id="me",
        current_season=2026,
    )

    sale_names = {s.player_name for s in result.historical_sales}
    assert sale_names == {"Past Buy A", "Past Buy B"}
    assert [s.year for s in result.historical_sales] == [2024, 2025]
    assert [k.player_name for k in result.keeper_candidates] == ["A Keeper"]
