from src.league_profile import (
    AuctionRules,
    KeeperRules,
    LeagueProfile,
    ManagerIdentity,
    RosterRules,
    ScoringRules,
)
from src.league_setup_data import LeagueSetupData


def _profile(*, keepers_enabled=True):
    return LeagueProfile(
        league_key="league",
        league_name="League",
        season=2026,
        source_mode="sleeper",
        draft_format="auction",
        scoring=ScoringRules(reception_points=0.5, format_label="half_ppr"),
        roster=RosterRules(roster_size=18, starting_lineup=("QB", "RB", "WR")),
        auction=AuctionRules(base_budget=400, minimum_bid=1),
        keepers=KeeperRules(enabled=keepers_enabled, max_keepers=6),
        managers={
            "alpha": ManagerIdentity(manager_id="alpha", sleeper_roster_id=1),
            "bravo": ManagerIdentity(manager_id="bravo", sleeper_roster_id=2),
        },
    )


_PLAYERS = {
    "100": {"full_name": "Kept One", "position": "RB", "team": "BUF"},
    "200": {"full_name": "Kept Two", "position": "WR", "team": "CIN"},
    "300": {"full_name": "Not Kept", "position": "TE", "team": "KC"},
}


def _rosters():
    return [
        {"roster_id": 1, "players": ["100", "200", "300"], "keepers": ["100", "200"]},
        {"roster_id": 2, "players": ["300"], "keepers": []},
    ]


def test_from_sleeper_builds_keeper_candidates_from_roster_keepers():
    setup = LeagueSetupData.from_sleeper(
        league_profile=_profile(),
        rosters=_rosters(),
        sleeper_players=_PLAYERS,
    )

    alpha = setup.keepers_for("alpha")
    assert {k.player_name for k in alpha} == {"Kept One", "Kept Two"}
    assert all(k.status == "candidate" for k in alpha)
    assert all(k.cost is None for k in alpha)
    assert all(k.source.source == "sleeper" for k in alpha)
    assert {k.sleeper_player_id for k in alpha} == {"100", "200"}
    assert setup.keepers_for("bravo") == []
    # finalized_only never returns raw Sleeper candidates
    assert setup.keepers_for("alpha", finalized_only=True) == []


def test_from_sleeper_keeper_league_budget_is_pre_keeper():
    setup = LeagueSetupData.from_sleeper(
        league_profile=_profile(keepers_enabled=True),
        rosters=_rosters(),
        sleeper_players=_PLAYERS,
    )
    assert setup.budgets["alpha"].budget_kind == "pre_keeper"


def test_from_sleeper_non_keeper_league_budget_is_auction_cash():
    setup = LeagueSetupData.from_sleeper(
        league_profile=_profile(keepers_enabled=False),
        rosters=_rosters(),
        sleeper_players=_PLAYERS,
    )
    assert setup.budgets["alpha"].budget_kind == "auction_cash"
    # keepers are still ingested even if the profile has no keeper rules
    assert {k.player_name for k in setup.keepers_for("alpha")} == {
        "Kept One",
        "Kept Two",
    }
