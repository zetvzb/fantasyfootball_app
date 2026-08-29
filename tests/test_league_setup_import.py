import pandas as pd

from src.league_setup_import import parse_league_setup_workbook


def _sheet(rows):
    return pd.DataFrame(rows)


def test_settings_sheet_detects_scalar_fields():
    sheets = {
        "League Info": _sheet(
            [
                ["Setting", "Value"],
                ["League Name", "Yahoo Dynasty"],
                ["Season", 2026],
                ["Scoring", "Half PPR"],
                ["Roster Size", 18],
                ["Budget", 300],
                ["Minimum Bid", 1],
                ["Max Keepers", 5],
                ["Keeper Escalation", 11],
            ]
        )
    }
    result = parse_league_setup_workbook(sheets, current_season=2026)

    assert result.league_name.value == "Yahoo Dynasty"
    assert result.season.value == 2026
    assert result.scoring_format.value == "half_ppr"
    assert result.roster_size.value == 18
    assert result.auction_budget.value == 300
    assert result.minimum_bid.value == 1
    assert result.max_keepers.value == 5
    assert result.keeper_escalation.value == 11
    assert result.warnings == ()


def test_settings_sheet_warns_on_ambiguous_scoring_and_non_numeric_value():
    sheets = {
        "Settings": _sheet(
            [
                ["Field", "Value"],
                ["Scoring", "Standard"],
                ["Roster Size", "lots"],
            ]
        )
    }
    result = parse_league_setup_workbook(sheets, current_season=2026)

    assert result.scoring_format is None
    assert result.roster_size is None
    assert len(result.warnings) == 2


def test_teams_sheet_detects_names_budgets_and_current_team():
    sheets = {
        "Teams": _sheet(
            [
                ["Team", "Budget", "Current Team"],
                ["My Team", 250, "Yes"],
                ["Opponent 1", 200, ""],
                ["Opponent 2", 210, "no"],
            ]
        )
    }
    result = parse_league_setup_workbook(sheets, current_season=2026)

    assert result.team_names == ("My Team", "Opponent 1", "Opponent 2")
    assert result.team_budgets["My Team"].amount == 250
    assert result.team_budgets["My Team"].budget_kind == "auction_cash"
    assert result.current_team_guess == "My Team"


def test_player_type_sheet_is_returned_as_leftover_rows_not_teams():
    sheets = {
        "Keepers": _sheet(
            [
                ["Type", "Team", "Player", "Value"],
                ["keeper", "My Team", "Star Player", 80],
            ]
        )
    }
    result = parse_league_setup_workbook(sheets, current_season=2026)

    assert result.team_names == ()
    assert len(result.leftover_rows) == 1
    assert result.leftover_rows[0]["player"] == "Star Player"


def test_stacked_header_row_is_not_treated_as_a_team():
    # A second season's table repeats the header mid-sheet; the repeated
    # "Name" cell must not become a 13th team.
    sheets = {
        "Standings": _sheet(
            [
                ["Name", "2024 Points"],
                ["Alpha", 1500],
                ["Beta", 1400],
                ["Name", "2025 Points"],
                ["Alpha", 1600],
                ["Beta", 1300],
            ]
        )
    }
    result = parse_league_setup_workbook(sheets, current_season=2026)

    assert result.team_names == ("Alpha", "Beta")


def test_only_the_first_teams_sheet_is_authoritative():
    sheets = {
        "Standings": _sheet([["Name"], ["Alpha"], ["Beta"]]),
        "Money List": _sheet([["Name", "Money"], ["Al"], ["Bee"]]),
    }
    result = parse_league_setup_workbook(sheets, current_season=2026)

    assert result.team_names == ("Alpha", "Beta")


def test_headerless_tab_budget_is_reconciled_to_known_team_by_substring():
    sheets = {
        "Teams": _sheet([["Team"], ["Alpha"], ["Beta"]]),
        "Alpha Roster": _sheet(
            [
                ["Alpha's Team Page", None, None, None],
                ["Some Guy", "WR", 20, None],
                [None, None, None, None],
                [None, "Draft Budget", 250, None],
            ]
        ),
    }
    result = parse_league_setup_workbook(sheets, current_season=2026)

    assert result.team_budgets["Alpha"].amount == 250
    assert result.team_budgets["Alpha"].budget_kind == "auction_cash"


def test_headerless_tab_prefers_draft_budget_over_salary():
    sheets = {
        "Alpha": _sheet(
            [
                ["Salary", 400, None],
                ["Draft Budget", 350, None],
            ]
        )
    }
    result = parse_league_setup_workbook(sheets, current_season=2026)

    assert result.team_budgets["Alpha"].amount == 350
    assert result.team_budgets["Alpha"].budget_kind == "auction_cash"


def test_headerless_tab_falls_back_to_salary_as_pre_keeper_budget():
    sheets = {"Alpha": _sheet([["Salary", 400, None]])}
    result = parse_league_setup_workbook(sheets, current_season=2026)

    assert result.team_budgets["Alpha"].amount == 400
    assert result.team_budgets["Alpha"].budget_kind == "pre_keeper"


def test_ambiguous_sibling_tabs_are_dropped_with_a_warning():
    sheets = {
        "Teams": _sheet([["Team"], ["Mike"]]),
        "Mike C.": _sheet([["Draft Budget", 300, None]]),
        "Mike S.": _sheet([["Draft Budget", 310, None]]),
    }
    result = parse_league_setup_workbook(sheets, current_season=2026)

    assert "Mike" not in result.team_budgets
    assert any("Mike C." in warning and "Mike S." in warning for warning in result.warnings)


def test_unrelated_sheet_with_no_matching_team_is_ignored():
    sheets = {
        "Teams": _sheet([["Team"], ["Alpha"]]),
        "Trades": _sheet([["Notes"], ["Traded a pick"]]),
    }
    result = parse_league_setup_workbook(sheets, current_season=2026)

    assert result.team_names == ("Alpha",)
    assert result.team_budgets == {}


def test_per_manager_roster_tab_yields_keeper_leftover_rows():
    # Real workbooks tuck the Player/Position/Salary header below a title
    # row and a spacer -- not at row 0 like every other recognized shape.
    sheets = {
        "Teams": _sheet([["Team"], ["Alpha"]]),
        "Alpha Roster": _sheet(
            [
                ["Alpha's Team Page", None, None],
                [None, None, None],
                ["Player", "Position", "Salary"],
                ["Some Guy", "WR", 20],
                ["Other Guy", "RB", 15],
            ]
        ),
    }
    result = parse_league_setup_workbook(sheets, current_season=2026)

    keeper_rows = [row for row in result.leftover_rows if row["type"] == "keeper"]
    assert {row["player"] for row in keeper_rows} == {"Some Guy", "Other Guy"}
    assert all(row["team"] == "Alpha" for row in keeper_rows)


def test_duplicate_player_on_a_roster_tab_is_skipped_with_a_warning():
    sheets = {
        "Teams": _sheet([["Team"], ["Alpha"]]),
        "Alpha Roster": _sheet(
            [
                ["Alpha's Team Page", None, None],
                ["Player", "Position", "Salary"],
                ["Same Guy", "WR", 20],
                ["Same Guy", "WR", 20],
            ]
        ),
    }
    result = parse_league_setup_workbook(sheets, current_season=2026)

    keeper_rows = [row for row in result.leftover_rows if row["type"] == "keeper"]
    assert len(keeper_rows) == 1
    assert any("duplicate" in warning.lower() for warning in result.warnings)


def test_headerless_player_team_price_sheet_is_detected_as_history():
    sheets = {
        "Teams": _sheet([["Team"], ["Alpha"], ["Beta"]]),
        "'25 Draft": _sheet(
            [
                ["Player One", "Alpha", 11],
                ["Player Two", "Alpha", 21],
                ["Player Three", "Beta", 31],
                ["Player Four", "Beta", 41],
                ["Player Five", "Alpha", 5],
            ]
        ),
    }
    result = parse_league_setup_workbook(sheets, current_season=2026)

    history_rows = [row for row in result.leftover_rows if row["type"] == "history"]
    assert len(history_rows) == 5
    assert {row["player"] for row in history_rows} == {
        "Player One", "Player Two", "Player Three", "Player Four", "Player Five",
    }
    assert all(row["year"] == 2025 for row in history_rows)


def test_nothing_detected_from_an_empty_workbook():
    result = parse_league_setup_workbook({}, current_season=2026)

    assert result.league_name is None
    assert result.team_names == ()
    assert result.team_budgets == {}
    assert result.leftover_rows == ()
    assert result.warnings == ()
