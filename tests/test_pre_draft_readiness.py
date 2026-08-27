from types import SimpleNamespace

from src.league_profile import (
    AuctionRules,
    KeeperRules,
    LeagueProfile,
    ManagerIdentity,
    RosterRules,
    ScoringRules,
)
from src.league_setup_data import HistoricalSale, LeagueSetupData, TeamBudget
from src.pre_draft_readiness import ReadinessStatus, build_pre_draft_readiness


def _profile(*, roster_size=10, starting_lineup=("QB", "RB", "WR")):
    return LeagueProfile(
        league_key="league",
        league_name="League",
        season=2026,
        source_mode="manual",
        scoring=ScoringRules(reception_points=0.5, format_label="half_ppr"),
        roster=RosterRules(
            roster_size=roster_size,
            starting_lineup=starting_lineup,
        ),
        auction=AuctionRules(base_budget=400, minimum_bid=1),
        keepers=KeeperRules(enabled=True, max_keepers=6),
        managers={
            "one": ManagerIdentity(manager_id="one"),
            "two": ManagerIdentity(manager_id="two"),
        },
    )


def _readiness(*, profile=None, setup=None, team_setups=None):
    return build_pre_draft_readiness(
        league_profile=profile or _profile(),
        league_setup_data=setup
        or LeagueSetupData(
            league_key="league",
            budgets={
                "one": TeamBudget("one", 400),
                "two": TeamBudget("two", 400),
            },
            historical_sales=[HistoricalSale(2025, "Player", 20)],
            metadata={"keepers_configured": True},
        ),
        team_setups=team_setups
        or {"one": SimpleNamespace(), "two": SimpleNamespace()},
        persisted_setup={},
        sleeper_player_count=5000,
        projection_count=300,
        setup_source_summary={"manual": 2, "sleeper": 20},
        workbook_loaded=False,
    )


def test_complete_setup_is_ready_and_exposes_every_required_area():
    readiness = _readiness()

    assert readiness.ready_for_draft is True
    assert {check.key for check in readiness.checks} == {
        "scoring",
        "roster",
        "budgets",
        "keepers",
        "freshness",
        "history",
        "sources",
    }
    assert readiness.check("budgets").status is ReadinessStatus.READY


def test_missing_team_budget_and_setup_block_draft_readiness():
    setup = LeagueSetupData(
        league_key="league",
        budgets={"one": TeamBudget("one", 400)},
        metadata={"keepers_configured": True},
    )

    readiness = _readiness(
        setup=setup,
        team_setups={"one": SimpleNamespace()},
    )

    assert readiness.ready_for_draft is False
    assert readiness.check("budgets").status is ReadinessStatus.BLOCKED
    assert "two" in readiness.check("budgets").detail


def test_optional_history_and_unconfirmed_zero_keepers_warn_without_blocking():
    setup = LeagueSetupData(
        league_key="league",
        budgets={
            "one": TeamBudget("one", 400),
            "two": TeamBudget("two", 400),
        },
    )

    readiness = _readiness(setup=setup)

    assert readiness.ready_for_draft is True
    assert readiness.check("history").status is ReadinessStatus.WARNING
    assert readiness.check("keepers").status is ReadinessStatus.WARNING


def test_impossible_roster_shape_blocks_readiness():
    readiness = _readiness(
        profile=_profile(roster_size=2, starting_lineup=("QB", "RB", "WR"))
    )

    assert readiness.ready_for_draft is False
    assert readiness.check("roster").status is ReadinessStatus.BLOCKED
