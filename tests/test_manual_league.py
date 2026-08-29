import pytest

from src.league_registry import LeagueRegistry
from src.league_setup_data import (
    HistoricalSale,
    KeeperRecord,
    LeagueSetupData,
    RosterPlayer,
    TeamBudget,
)
from src.manual_league import (
    build_manual_league_profile,
    manual_runtime_ids,
    permitted_setup_overrides,
)


def _profile(**overrides):
    values = {
        "league_name": "Yahoo Dynasty",
        "season": 2026,
        "team_names": ["My Team", "Opponent"],
        "current_team_name": "My Team",
        "scoring_format": "half_ppr",
        "roster_size": 18,
        "auction_budget": 300,
        "minimum_bid": 1,
        "max_keepers": 5,
        "keeper_escalation": 7,
    }
    values.update(overrides)
    return build_manual_league_profile(**values)


def test_manual_profile_contains_minimum_rules_and_no_sleeper_league_dependency():
    profile = _profile()
    assert profile.source_mode == "manual"
    assert profile.sleeper_league_id is None
    assert profile.sleeper_draft_id is None
    assert profile.scoring_label == "half_ppr"
    assert profile.auction.base_budget == 300
    assert profile.keepers.max_keepers == 5
    assert profile.keepers.escalation == 7
    assert profile.metadata["current_manager_id"] == "my_team"
    assert manual_runtime_ids(profile) == (
        "manual::manual_yahoo_dynasty_2026",
        "manual::manual_yahoo_dynasty_2026::2026",
    )


def test_manual_profile_scoring_covers_more_than_receptions():
    # A manual league's scoring settings used to contain only "rec",
    # which silently zeroed out passing/rushing/receiving yardage and
    # touchdowns anywhere those settings were applied to a projection.
    profile = _profile(scoring_format="ppr")
    raw = profile.scoring.raw
    assert raw["rec"] == 1.0
    for category in ("rush_yd", "rush_td", "rec_yd", "rec_td", "pass_yd", "pass_td"):
        assert category in raw
        assert raw[category] != 0


def test_manual_profile_persists_across_registry_restart(tmp_path):
    profile = _profile(scoring_format="ppr")
    LeagueRegistry(tmp_path).save(profile)
    restored = LeagueRegistry(tmp_path).load(profile.league_key)
    assert restored.league_key == profile.league_key
    assert restored.league_name == profile.league_name
    assert set(restored.managers) == set(profile.managers)
    assert restored.metadata == profile.metadata
    assert restored.scoring.reception_points == 1.0


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"team_names": ["Only"]}, "at least two teams"),
        ({"current_team_name": "Missing"}, "Current team"),
        ({"scoring_format": "standard"}, "PPR or Half PPR"),
    ],
)
def test_manual_profile_rejects_incomplete_minimum_setup(overrides, message):
    with pytest.raises(ValueError, match=message):
        _profile(**overrides)


def test_manual_league_keeps_budget_keeper_and_history_overrides():
    profile = _profile()
    setup = LeagueSetupData(
        league_key=profile.league_key,
        budgets={"my_team": TeamBudget("my_team", 275)},
        keepers=[KeeperRecord("my_team", "Keeper", cost=12)],
        historical_sales=[HistoricalSale(2025, "Past Buy", 20)],
    )
    assert permitted_setup_overrides(profile, setup) is setup


def _sleeper_profile():
    manual_profile = _profile()
    return manual_profile.__class__.from_dict(
        {
            **manual_profile.to_dict(),
            "source_mode": "sleeper",
            "sleeper_league_id": "league-1",
            "sleeper_draft_id": "draft-1",
        }
    )


def test_sleeper_league_keeps_manual_cost_overlay_but_drops_stale_keeper():
    sleeper_profile = _sleeper_profile()
    baseline = LeagueSetupData(
        league_key=sleeper_profile.league_key,
        keepers=[KeeperRecord("my_team", "Real Keeper", status="candidate")],
    )
    setup = LeagueSetupData(
        league_key=sleeper_profile.league_key,
        budgets={"my_team": TeamBudget("my_team", 275)},
        keepers=[
            KeeperRecord("my_team", "Real Keeper", cost=18, status="finalized"),
            KeeperRecord("my_team", "Stale Keeper", cost=12, status="finalized"),
        ],
        historical_sales=[HistoricalSale(2025, "Past Buy", 20)],
        metadata={"keepers_configured": True},
    )
    permitted = permitted_setup_overrides(sleeper_profile, setup, baseline=baseline)
    assert permitted.budgets["my_team"].amount == 275
    assert [sale.player_name for sale in permitted.historical_sales] == ["Past Buy"]
    assert [(k.player_name, k.cost) for k in permitted.keepers] == [("Real Keeper", 18)]
    assert permitted.metadata["keepers_configured"] is True


def test_sleeper_league_keeps_manual_keeper_still_on_roster_but_not_in_keeper_list():
    sleeper_profile = _sleeper_profile()
    baseline = LeagueSetupData(
        league_key=sleeper_profile.league_key,
        keepers=[KeeperRecord("my_team", "Real Keeper", status="candidate")],
        roster_players=[
            RosterPlayer("my_team", "Real Keeper"),
            RosterPlayer("my_team", "Rostered Keeper"),
        ],
    )
    setup = LeagueSetupData(
        league_key=sleeper_profile.league_key,
        keepers=[
            KeeperRecord("my_team", "Real Keeper", cost=18, status="finalized"),
            KeeperRecord("my_team", "Rostered Keeper", cost=12, status="finalized"),
            KeeperRecord("my_team", "Off Roster", cost=5, status="finalized"),
        ],
    )
    permitted = permitted_setup_overrides(sleeper_profile, setup, baseline=baseline)
    assert [k.player_name for k in permitted.keepers] == [
        "Real Keeper",
        "Rostered Keeper",
    ]
    # The dropped finalized keeper is surfaced as a warning, not silent.
    assert any("Off Roster" in warning for warning in permitted.warnings)


def test_sleeper_league_allows_manual_keepers_when_team_set_none_on_sleeper():
    sleeper_profile = _sleeper_profile()
    baseline = LeagueSetupData(
        league_key=sleeper_profile.league_key,
        keepers=[KeeperRecord("other_team", "Their Keeper", status="candidate")],
    )
    setup = LeagueSetupData(
        league_key=sleeper_profile.league_key,
        keepers=[KeeperRecord("my_team", "Hand Entered", cost=9, status="finalized")],
    )
    permitted = permitted_setup_overrides(sleeper_profile, setup, baseline=baseline)
    assert [(k.player_name, k.cost) for k in permitted.keepers] == [("Hand Entered", 9)]
    assert permitted.metadata["keepers_configured"] is True


def test_sleeper_league_without_baseline_drops_all_keepers():
    sleeper_profile = _sleeper_profile()
    setup = LeagueSetupData(
        league_key=sleeper_profile.league_key,
        keepers=[KeeperRecord("my_team", "Anything", cost=12, status="finalized")],
    )
    permitted = permitted_setup_overrides(sleeper_profile, setup)
    assert permitted.keepers == []
    assert permitted.metadata["keepers_configured"] is False
