from types import SimpleNamespace

import pytest

from src.auction_pool import build_auction_pool
from src.college_domain import (
    CollegeDomainRules,
    apply_college_rules,
    apply_college_rules_for_startup,
    validate_college_promotions,
)
from src.draft_setup import build_team_draft_setup_from_setup_data
from src.league_profile import (
    AuctionRules,
    CollegeRules,
    LeagueProfile,
    ManagerIdentity,
    RosterRules,
)
from src.league_setup_data import (
    CollegeDraftPick,
    CollegeRight,
    CollegeThresholdRecord,
    LeagueSetupData,
    LeagueSetupStore,
    MANUAL_SOURCE,
    TeamBudget,
    WORKBOOK_SOURCE,
)


def _profile(
    *,
    enabled=True,
    capacity=6,
    rounds=3,
    pick_trading=True,
):
    return LeagueProfile(
        league_key="league",
        league_name="League",
        season=2026,
        source_mode="manual",
        roster=RosterRules(roster_size=10),
        auction=AuctionRules(base_budget=200, minimum_bid=1),
        college=CollegeRules(
            enabled=enabled,
            max_college_players=capacity if enabled else 0,
            draft_rounds=rounds if enabled else 0,
            eligibility_source="manual",
            college_pick_trading_enabled=pick_trading,
        ),
        managers={
            "team": ManagerIdentity(manager_id="team"),
            "other": ManagerIdentity(manager_id="other"),
        },
    )


def _right(index, manager_id="team", **overrides):
    values = {
        "manager_id": manager_id,
        "player_name": "College Player {0}".format(index),
        "status": "in_college",
        "eligibility_status": "unknown",
        "promotion_status": "taxi",
    }
    values.update(overrides)
    return CollegeRight(**values)


def test_bishop_style_six_player_capacity_is_valid_and_seven_is_rejected():
    profile = _profile(capacity=6)
    six = LeagueSetupData(
        league_key="league",
        college_players=[_right(index) for index in range(6)],
    )

    assert apply_college_rules(
        league_profile=profile,
        setup_data=six,
    ) is six

    seven = LeagueSetupData(
        league_key="league",
        college_players=[_right(index) for index in range(7)],
    )
    with pytest.raises(ValueError, match="maximum is 6"):
        apply_college_rules(
            league_profile=profile,
            setup_data=seven,
        )


def test_over_capacity_import_is_editable_at_startup_but_strict_on_save():
    profile = _profile(capacity=6)
    imported = LeagueSetupData(
        league_key="league",
        college_players=[
            _right(index, manager_id="other", source=WORKBOOK_SOURCE)
            for index in range(7)
        ],
    )

    startup = apply_college_rules_for_startup(
        league_profile=profile,
        setup_data=imported,
    )

    assert startup.setup_data.college_players == imported.college_players
    assert "maximum is 6" in startup.validation_error
    assert any("Pre-Draft review" in warning for warning in startup.setup_data.warnings)
    with pytest.raises(ValueError, match="maximum is 6"):
        apply_college_rules(league_profile=profile, setup_data=imported)


def test_over_capacity_opponent_import_does_not_block_team_auction_setup():
    profile = _profile(capacity=6)
    imported = LeagueSetupData(
        league_key="league",
        college_players=[
            _right(index, source=WORKBOOK_SOURCE)
            for index in range(7)
        ],
    )
    imported.budgets["team"] = TeamBudget(
        manager_id="team",
        amount=200,
        budget_kind="pre_keeper",
    )

    startup = apply_college_rules_for_startup(
        league_profile=profile,
        setup_data=imported,
    )
    team_setup = build_team_draft_setup_from_setup_data(
        manager_id="team",
        league_setup_data=startup.setup_data,
        selected_keeper_names=[],
        college_promotions=[],
        league_profile=profile,
    )

    assert team_setup.manager_id == "team"
    assert team_setup.auction_cash == 200
    assert team_setup.open_roster_spots == profile.roster.roster_size
    assert "maximum is 6" in startup.validation_error


def test_no_devy_league_ignores_stale_rights_picks_and_thresholds():
    setup = LeagueSetupData(
        league_key="league",
        college_players=[_right(1)],
        college_picks=[
            CollegeDraftPick(
                manager_id="team",
                original_manager_id="team",
                season=2027,
                round_number=1,
            )
        ],
        college_thresholds=[
            CollegeThresholdRecord(
                manager_id="team",
                player_name="College Player 1",
                stat_name="games",
                current_value=1,
                threshold_value=3,
            )
        ],
    )

    normalized = apply_college_rules(
        league_profile=_profile(enabled=False),
        setup_data=setup,
    )

    assert normalized.college_players == []
    assert normalized.college_picks == []
    assert normalized.college_thresholds == []
    assert any("College/devy is disabled" in warning for warning in normalized.warnings)


def test_right_and_traded_pick_ownership_round_trip_with_provenance():
    right = _right(
        1,
        manager_id="other",
        status="in_nfl",
        eligibility_status="eligible",
        eligibility_detail="Commissioner confirmed",
        original_manager_id="team",
        trade_provenance="2026 offseason trade",
        sleeper_player_id="p1",
        position="WR",
        nfl_draft_round=1,
        nfl_draft_pick=12,
        future_values=(82.0, None, 76.0),
    )
    pick = CollegeDraftPick(
        manager_id="other",
        original_manager_id="team",
        season=2027,
        round_number=2,
        pick_number=3,
        trade_provenance="2026 offseason trade",
    )
    setup = LeagueSetupData(
        league_key="league",
        college_players=[right],
        college_picks=[pick],
    )

    restored = LeagueSetupData.from_dict(setup.to_dict())

    assert restored.college_players == [right]
    assert restored.college_picks == [pick]
    assert restored.college_players[0].is_traded is True
    assert restored.college_picks[0].is_traded is True
    assert restored.college_picks_for("other") == [pick]


def test_college_ownership_persists_across_store_restart(tmp_path):
    setup = LeagueSetupData(
        league_key="league",
        college_players=[
            _right(
                1,
                manager_id="other",
                original_manager_id="team",
                trade_provenance="Rights trade",
            )
        ],
        college_picks=[
            CollegeDraftPick(
                manager_id="other",
                original_manager_id="team",
                season=2027,
                round_number=1,
                trade_provenance="Pick trade",
            )
        ],
    )
    first_store = LeagueSetupStore(root=tmp_path)
    first_store.save(setup)

    restarted_store = LeagueSetupStore(root=tmp_path)
    restored = restarted_store.load("league")

    assert restored.college_players == setup.college_players
    assert restored.college_picks == setup.college_picks


def test_higher_priority_manual_records_transfer_right_and_pick_ownership():
    workbook = LeagueSetupData(
        league_key="league",
        college_players=[
            _right(1, manager_id="team", source=WORKBOOK_SOURCE)
        ],
        college_picks=[
            CollegeDraftPick(
                manager_id="team",
                original_manager_id="team",
                season=2027,
                round_number=1,
                source=WORKBOOK_SOURCE,
            )
        ],
    )
    manual = LeagueSetupData(
        league_key="league",
        college_players=[
            _right(
                1,
                manager_id="other",
                original_manager_id="team",
                source=MANUAL_SOURCE,
            )
        ],
        college_picks=[
            CollegeDraftPick(
                manager_id="other",
                original_manager_id="team",
                season=2027,
                round_number=1,
                source=MANUAL_SOURCE,
            )
        ],
    )

    merged = workbook.merged_with(manual)

    assert len(merged.college_players) == 1
    assert merged.college_players[0].manager_id == "other"
    assert len(merged.college_picks) == 1
    assert merged.college_picks[0].manager_id == "other"


def test_pick_rounds_and_trade_setting_are_enforced():
    traded_pick = CollegeDraftPick(
        manager_id="other",
        original_manager_id="team",
        season=2027,
        round_number=2,
    )
    setup = LeagueSetupData(
        league_key="league",
        college_picks=[traded_pick],
    )

    with pytest.raises(ValueError, match="disabled"):
        apply_college_rules(
            league_profile=_profile(pick_trading=False),
            setup_data=setup,
        )

    invalid_round = LeagueSetupData(
        league_key="league",
        college_picks=[
            CollegeDraftPick(
                manager_id="team",
                original_manager_id="team",
                season=2027,
                round_number=4,
            )
        ],
    )
    with pytest.raises(ValueError, match="configured 3 rounds"):
        apply_college_rules(
            league_profile=_profile(rounds=3),
            setup_data=invalid_round,
        )


def test_promotion_selection_requires_owned_non_ineligible_right():
    setup = LeagueSetupData(
        league_key="league",
        college_players=[
            _right(
                1,
                status="in_nfl",
                eligibility_status="eligible",
            ),
            _right(
                2,
                eligibility_status="ineligible",
            ),
        ],
    )

    resolved = validate_college_promotions(
        league_profile=_profile(),
        setup_data=setup,
        manager_id="team",
        promotion_names=["College Player 1"],
    )
    assert resolved[0].player_name == "College Player 1"

    with pytest.raises(ValueError, match="explicitly ineligible"):
        validate_college_promotions(
            league_profile=_profile(),
            setup_data=setup,
            manager_id="team",
            promotion_names=["College Player 2"],
        )
    with pytest.raises(ValueError, match="not a college right owned"):
        validate_college_promotions(
            league_profile=_profile(),
            setup_data=setup,
            manager_id="other",
            promotion_names=["College Player 1"],
        )

    setup.budgets["team"] = TeamBudget(
        manager_id="team",
        amount=200,
        budget_kind="pre_keeper",
    )
    team_setup = build_team_draft_setup_from_setup_data(
        manager_id="team",
        league_setup_data=setup,
        selected_keeper_names=[],
        college_promotions=["College Player 1"],
        league_profile=_profile(),
    )
    assert team_setup.college_promotions == ["College Player 1"]

    with pytest.raises(ValueError, match="explicitly ineligible"):
        build_team_draft_setup_from_setup_data(
            manager_id="team",
            league_setup_data=setup,
            selected_keeper_names=[],
            college_promotions=["College Player 2"],
            league_profile=_profile(),
        )


def test_all_college_rights_are_strictly_excluded_from_regular_auction_pool():
    setup = LeagueSetupData(
        league_key="league",
        college_players=[
            _right(
                1,
                status="in_nfl",
                promotion_status="promoted",
                eligibility_status="eligible",
                sleeper_player_id="p1",
            )
        ],
    )
    pool = build_auction_pool(
        sleeper_players={
            "p1": {
                "full_name": "Different Display Name",
                "position": "WR",
                "active": True,
                "team": "CHI",
            },
            "p2": {
                "full_name": "Auction Player",
                "position": "RB",
                "active": True,
                "team": "DAL",
            },
        },
        league_data=setup,
        team_setups={"team": SimpleNamespace(keepers=[])},
    )

    assert [player.player_name for player in pool.available_players] == [
        "Auction Player"
    ]
    assert pool.excluded_college == ["College Player 1"]


def test_college_rule_fields_round_trip_and_validate_source():
    profile = _profile()
    restored = LeagueProfile.from_dict(profile.to_dict())

    assert restored.college == profile.college
    assert CollegeDomainRules.from_league_profile(restored).max_college_players == 6

    invalid = _profile()
    invalid = LeagueProfile.from_dict(
        {
            **invalid.to_dict(),
            "college": {
                **invalid.to_dict()["college"],
                "eligibility_source": "magic",
            },
        }
    )
    with pytest.raises(ValueError, match="Unknown college eligibility source"):
        CollegeDomainRules.from_league_profile(invalid)
