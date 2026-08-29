from types import SimpleNamespace

import pytest

from src.draft_setup import build_team_draft_setup_from_setup_data
from src.keeper_domain import (
    MIDSEASON_PICKUP,
    RETURNING_KEEPER,
    KeeperDomainRules,
    build_keeper_contract,
)
from src.league_profile import KeeperRules, LeagueProfile, RosterRules
from src.league_setup_data import KeeperRecord, LeagueSetupData, TeamBudget


def _profile(max_keepers=6, horizon=3):
    return SimpleNamespace(
        auction=SimpleNamespace(base_budget=400, minimum_bid=1),
        roster=SimpleNamespace(roster_size=10),
        keepers=SimpleNamespace(
            max_keepers=max_keepers,
            escalation=11,
            midseason_pickup_cost=10,
            future_horizon_years=horizon,
        ),
    )


def _setup(*keepers):
    return LeagueSetupData(
        league_key="league",
        budgets={
            "team": TeamBudget(
                manager_id="team",
                amount=400,
                budget_kind="pre_keeper",
            )
        },
        keepers=list(keepers),
    )


def test_returning_keeper_uses_prior_year_cost_plus_league_escalation():
    keeper = KeeperRecord(
        manager_id="team",
        player_name="Returning Player",
        cost_basis=RETURNING_KEEPER,
        prior_year_cost=24,
    )

    team = build_team_draft_setup_from_setup_data(
        manager_id="team",
        league_setup_data=_setup(keeper),
        selected_keeper_names=[keeper.player_name],
        league_profile=_profile(),
    )

    assert team.keeper_commitments == 35
    assert team.entering_cash == 365
    assert team.keepers[0].contract.current_cost == 35


def test_midseason_pickup_costs_ten_next_season():
    keeper = KeeperRecord(
        manager_id="team",
        player_name="Waiver Find",
        cost=999,
        cost_basis=MIDSEASON_PICKUP,
    )

    contract = build_keeper_contract(
        keeper,
        KeeperDomainRules.from_league_profile(_profile()),
    )

    assert contract.current_cost == 10


def test_future_value_hooks_match_horizon():
    keeper = KeeperRecord(
        manager_id="team",
        player_name="Long-Term Keeper",
        cost=15,
        future_values=(40.0, None),
    )

    contract = build_keeper_contract(
        keeper,
        KeeperDomainRules.from_league_profile(_profile(horizon=3)),
    )

    assert contract.future_horizon_years == 3
    assert contract.future_values == (40.0, None, None)
    assert contract.future_value(1) == 40.0
    assert contract.future_value(3) is None


@pytest.mark.parametrize("horizon", [2, 3])
def test_future_horizon_supports_two_or_three_years(horizon):
    rules = KeeperDomainRules.from_league_profile(
        _profile(horizon=horizon)
    )
    contract = build_keeper_contract(
        KeeperRecord(
            manager_id="team",
            player_name="Future Player",
            cost=7,
        ),
        rules,
    )

    assert len(contract.future_values) == horizon


def test_configurable_keeper_max_is_enforced():
    keepers = [
        KeeperRecord(
            manager_id="team",
            player_name="Keeper {0}".format(index),
            cost=5,
        )
        for index in range(3)
    ]

    with pytest.raises(ValueError, match="Maximum keepers is 2"):
        build_team_draft_setup_from_setup_data(
            manager_id="team",
            league_setup_data=_setup(*keepers),
            selected_keeper_names=[keeper.player_name for keeper in keepers],
            league_profile=_profile(max_keepers=2),
        )


def test_no_budget_entered_yet_does_not_raise_even_below_reserve():
    # A fresh manual league's placeholder base_budget won't cover a real
    # roster's minimum-bid reserve -- that's expected pre-draft state
    # for every team until someone enters real budgets, not a setup
    # error, so it must not raise the way an explicitly-entered too-low
    # budget would.
    profile = _profile()
    profile.auction.base_budget = 1

    team = build_team_draft_setup_from_setup_data(
        manager_id="team",
        league_setup_data=LeagueSetupData(league_key="league", budgets={}),
        selected_keeper_names=[],
        league_profile=profile,
    )

    assert team.entering_cash == 1
    assert team.budget_source == "default"


def test_explicitly_entered_low_budget_still_raises():
    setup_data = LeagueSetupData(
        league_key="league",
        budgets={
            "team": TeamBudget(
                manager_id="team",
                amount=1,
                budget_kind="pre_keeper",
            )
        },
    )

    with pytest.raises(ValueError, match="minimum-bid reserve"):
        build_team_draft_setup_from_setup_data(
            manager_id="team",
            league_setup_data=setup_data,
            selected_keeper_names=[],
            league_profile=_profile(),
        )


def test_unused_keeper_slots_become_auction_spots_without_bonus_cash():
    keepers = [
        KeeperRecord(
            manager_id="team",
            player_name="Keeper {0}".format(index),
            cost=10,
        )
        for index in range(6)
    ]
    setup_data = _setup(*keepers)

    four = build_team_draft_setup_from_setup_data(
        manager_id="team",
        league_setup_data=setup_data,
        selected_keeper_names=[keeper.player_name for keeper in keepers[:4]],
        league_profile=_profile(),
    )
    six = build_team_draft_setup_from_setup_data(
        manager_id="team",
        league_setup_data=setup_data,
        selected_keeper_names=[keeper.player_name for keeper in keepers],
        league_profile=_profile(),
    )

    assert four.pre_keeper_budget == six.pre_keeper_budget == 400
    assert four.open_roster_spots == 6
    assert six.open_roster_spots == 4
    assert four.entering_cash == 360
    assert six.entering_cash == 340


def test_keeper_terms_round_trip_and_old_records_remain_explicit():
    configured = KeeperRecord(
        manager_id="team",
        player_name="Configured Keeper",
        cost=31,
        cost_basis=RETURNING_KEEPER,
        prior_year_cost=20,
        future_values=(50.0, 45.0),
    )
    restored = LeagueSetupData.from_dict(_setup(configured).to_dict())

    assert restored.keepers[0] == configured

    legacy = LeagueSetupData.from_dict(
        {
            "league_key": "league",
            "keepers": [
                {
                    "manager_id": "team",
                    "player_name": "Legacy Keeper",
                    "cost": 18,
                }
            ],
        }
    )
    assert legacy.keepers[0].cost_basis == "explicit"


def test_profile_keeper_rule_fields_round_trip():
    profile = LeagueProfile(
        league_key="league",
        league_name="League",
        season=2026,
        source_mode="manual",
        roster=RosterRules(roster_size=10),
        keepers=KeeperRules(
            enabled=True,
            max_keepers=4,
            escalation=11,
            midseason_pickup_cost=10,
            future_horizon_years=2,
        ),
    )

    restored = LeagueProfile.from_dict(profile.to_dict())

    assert restored.keepers == profile.keepers
