import pytest

from src.league_registry import LeagueRegistry
from src.league_setup_data import (
    CollegeRight,
    HistoricalSale,
    KeeperRecord,
    LeagueSetupData,
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
        "max_devy_players": 3,
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
    assert profile.college.max_college_players == 3
    assert profile.metadata["current_manager_id"] == "my_team"
    assert manual_runtime_ids(profile) == (
        "manual::manual_yahoo_dynasty_2026",
        "manual::manual_yahoo_dynasty_2026::2026",
    )


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


def test_manual_league_keeps_budget_keeper_devy_and_history_overrides():
    profile = _profile()
    setup = LeagueSetupData(
        league_key=profile.league_key,
        budgets={"my_team": TeamBudget("my_team", 275)},
        keepers=[KeeperRecord("my_team", "Keeper", cost=12)],
        college_players=[CollegeRight("my_team", "Prospect")],
        historical_sales=[HistoricalSale(2025, "Past Buy", 20)],
    )
    assert permitted_setup_overrides(profile, setup) is setup


def test_sleeper_league_rejects_stale_manual_protected_player_overrides():
    manual_profile = _profile()
    sleeper_profile = manual_profile.__class__.from_dict(
        {
            **manual_profile.to_dict(),
            "source_mode": "sleeper",
            "sleeper_league_id": "league-1",
            "sleeper_draft_id": "draft-1",
        }
    )
    setup = LeagueSetupData(
        league_key=sleeper_profile.league_key,
        budgets={"my_team": TeamBudget("my_team", 275)},
        keepers=[KeeperRecord("my_team", "Stale Keeper", cost=12)],
        college_players=[CollegeRight("my_team", "Stale Prospect")],
        historical_sales=[HistoricalSale(2025, "Past Buy", 20)],
        metadata={"keepers_configured": True, "college_configured": True},
    )
    permitted = permitted_setup_overrides(sleeper_profile, setup)
    assert permitted.budgets["my_team"].amount == 275
    assert [sale.player_name for sale in permitted.historical_sales] == ["Past Buy"]
    assert permitted.keepers == []
    assert permitted.college_players == []
    assert permitted.metadata["keepers_configured"] is False
