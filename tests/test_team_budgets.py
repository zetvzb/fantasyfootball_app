import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.draft_setup import build_team_draft_setup
from src.league_data import KeeperOption, ManagerLeagueData
from src.league_setup_data import SourceInfo, TeamBudget
from src.league_setup_data import LeagueSetupData
from src.live_draft import LiveAuctionSale, build_live_team_setups


def _profile(roster_size=10, minimum_bid=1, max_keepers=6):
    return SimpleNamespace(
        auction=SimpleNamespace(minimum_bid=minimum_bid),
        roster=SimpleNamespace(roster_size=roster_size),
        keepers=SimpleNamespace(max_keepers=max_keepers),
    )


def _manager(manager_id, keeper_count=6):
    return ManagerLeagueData(
        manager_id=manager_id,
        spreadsheet_tab=manager_id,
        pre_keeper_budget=400,
        keeper_options=[
            KeeperOption(
                player_name="Keeper {0}".format(index),
                position="WR",
                keeper_cost=10,
                source_row=index,
            )
            for index in range(keeper_count)
        ],
    )


def _budget(manager_id, amount, kind="auction_cash"):
    return TeamBudget(
        manager_id=manager_id,
        amount=amount,
        budget_kind=kind,
        source=SourceInfo(
            source="manual",
            confidence=1.0,
            inferred=False,
            detail="Commissioner-entered budget",
        ),
    )


def test_unequal_team_budgets_and_provenance_survive_live_replay():
    profile = _profile(roster_size=5, minimum_bid=2)
    rich = build_team_draft_setup(
        "rich",
        _manager("rich", keeper_count=1),
        ["Keeper 0"],
        profile,
        team_budget=_budget("rich", 425),
    )
    lean = build_team_draft_setup(
        "lean",
        _manager("lean", keeper_count=1),
        ["Keeper 0"],
        profile,
        team_budget=_budget("lean", 380),
    )

    assert rich.entering_cash == 425
    assert lean.entering_cash == 380
    assert rich.keeper_commitments == lean.keeper_commitments == 10
    assert rich.required_reserve == lean.required_reserve == 8
    assert rich.budget_source == "manual"

    sales = [LiveAuctionSale(1, "Player A", "RB", "rich", 100)]
    first = build_live_team_setups({"rich": rich, "lean": lean}, sales)
    restarted = build_live_team_setups({"rich": rich, "lean": lean}, sales)

    assert first["rich"].live_cash == restarted["rich"].live_cash == 325
    assert first["rich"].required_reserve == 6
    assert first["rich"].discretionary_cash == 319
    assert first["lean"].live_cash == 380
    assert first["lean"].budget_source_detail == (
        "Commissioner-entered budget"
    )


def test_fewer_keepers_create_spots_not_bonus_cash():
    profile = _profile(roster_size=10, minimum_bid=1)
    manager = _manager("team")
    budget = _budget("team", 300)

    four = build_team_draft_setup(
        "team",
        manager,
        ["Keeper {0}".format(index) for index in range(4)],
        profile,
        team_budget=budget,
    )
    six = build_team_draft_setup(
        "team",
        manager,
        ["Keeper {0}".format(index) for index in range(6)],
        profile,
        team_budget=budget,
    )

    assert four.entering_cash == six.entering_cash == 300
    assert four.open_roster_spots == 6
    assert six.open_roster_spots == 4
    assert four.required_reserve == 6
    assert six.required_reserve == 4
    assert four.discretionary_cash == 294
    assert six.discretionary_cash == 296
    assert four.max_bid == 295
    assert six.max_bid == 297


def test_pre_keeper_cap_subtracts_commitments_once():
    setup = build_team_draft_setup(
        "team",
        _manager("team", keeper_count=2),
        ["Keeper 0", "Keeper 1"],
        _profile(roster_size=5),
        team_budget=_budget("team", 400, kind="pre_keeper"),
    )

    assert setup.keeper_commitments == 20
    assert setup.entering_cash == 380
    assert setup.pre_keeper_budget == 400


def test_entering_cash_must_cover_every_remaining_minimum_bid():
    with pytest.raises(ValueError, match="minimum-bid reserve"):
        build_team_draft_setup(
            "team",
            _manager("team", keeper_count=0),
            [],
            _profile(roster_size=5, minimum_bid=2),
            team_budget=_budget("team", 9),
        )


def test_budget_and_provenance_round_trip_through_setup_storage():
    budget = _budget("team", 425)
    setup = LeagueSetupData(
        league_key="league",
        budgets={"team": budget},
    )

    restored = LeagueSetupData.from_dict(setup.to_dict())

    assert restored.budgets["team"] == budget


def test_app_passes_normalized_setup_to_draft_builder_not_workbook_loader():
    app_tree = ast.parse(
        Path("app.py").read_text(encoding="utf-8")
    )
    calls_by_name = {}

    for node in ast.walk(app_tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            call_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
        else:
            continue
        calls_by_name.setdefault(call_name, []).append(
            {keyword.arg for keyword in node.keywords}
        )

    assert any(
        "league_setup_data" in keywords
        for keywords in calls_by_name["build_team_draft_setup_from_setup_data"]
    )
    assert all(
        "team_budget" not in keywords
        for keywords in calls_by_name.get("from_workbook", [])
    )
