import sqlite3

import pytest

from src.draft_setup import TeamDraftSetup
from src.draft_store import DraftStore
from src.league_profile import (
    LeagueProfile,
    RosterRules,
    ScoringRules,
)


@pytest.mark.parametrize(
    "receptions,label",
    [(0, "standard"), (0.5, "half_ppr"), (1, "ppr"), (0.75, "custom")],
)
def test_scoring_profiles_classify_supported_and_custom_formats(receptions, label):
    rules = ScoringRules.from_sleeper({"rec": receptions, "pass_td": 6})
    assert rules.format_label == label
    assert rules.raw["pass_td"] == 6.0


def test_league_profiles_keep_identity_independent():
    first = LeagueProfile(
        league_key="first",
        league_name="First",
        season=2026,
        source_mode="manual",
        roster=RosterRules(roster_size=5),
    )
    second = LeagueProfile(
        league_key="second",
        league_name="Second",
        season=2026,
        source_mode="sleeper",
        roster=RosterRules(roster_size=20),
    )

    assert first.league_key != second.league_key
    assert first.roster.roster_size != second.roster.roster_size


@pytest.mark.parametrize(
    "cash,spots,minimum,reserve,max_bid",
    [(100, 5, 1, 5, 96), (100, 5, 2, 10, 92), (25, 1, 5, 5, 25)],
)
def test_budget_reserve_and_legal_max_matrix(cash, spots, minimum, reserve, max_bid):
    setup = TeamDraftSetup(
        manager_id="manager",
        pre_keeper_budget=cash,
        roster_size=spots,
        minimum_auction_bid=minimum,
        entering_auction_cash=cash,
    )
    assert setup.required_reserve == reserve
    assert setup.max_bid == max_bid


def test_legacy_sale_schema_migrates_without_losing_state(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(str(path)) as connection:
        connection.execute(
            """
            CREATE TABLE live_sales (
                sale_number INTEGER PRIMARY KEY,
                player_name TEXT NOT NULL,
                normalized_player_name TEXT NOT NULL UNIQUE,
                position TEXT NOT NULL,
                manager_id TEXT NOT NULL,
                price INTEGER NOT NULL,
                modeled_market_value REAL,
                do_not_exceed INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO live_sales (
                sale_number, player_name, normalized_player_name,
                position, manager_id, price
            ) VALUES (1, 'Player', 'player', 'WR', 'manager', 20)
            """
        )

    restored = DraftStore(str(path), "league", "draft", 2026).load_sales()
    assert len(restored) == 1
    assert restored[0].price == 20
    assert restored[0].source == "manual"
