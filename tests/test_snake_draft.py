from types import SimpleNamespace

import pytest

from src.snake_draft import (
    DraftBoardEntry,
    build_draft_board,
    build_roster_need,
    build_snake_draft_state,
    build_team_value_leaderboard,
    bye_week_stack_warnings,
    load_adp_distribution,
    load_bye_weeks,
    next_pick_no_for_slot,
    optimize_snake_roster_plan,
    pick_no_for_slot,
    slot_for_pick_no,
    survival_probability,
)


# =========================================================
# PICK ORDER MATH
# =========================================================

@pytest.mark.parametrize(
    "pick_no,team_count,expected",
    [
        (1, 4, (1, 1)),
        (4, 4, (1, 4)),
        (5, 4, (2, 4)),
        (8, 4, (2, 1)),
        (9, 4, (3, 1)),
    ],
)
def test_slot_for_pick_no_snakes_direction_each_round(pick_no, team_count, expected):
    assert slot_for_pick_no(pick_no, team_count) == expected


@pytest.mark.parametrize(
    "round_number,slot,team_count,expected_pick_no",
    [
        (1, 1, 4, 1),
        (1, 4, 4, 4),
        (2, 4, 4, 5),
        (2, 1, 4, 8),
        (3, 1, 4, 9),
    ],
)
def test_pick_no_for_slot_is_the_inverse_of_slot_for_pick_no(round_number, slot, team_count, expected_pick_no):
    assert pick_no_for_slot(round_number, slot, team_count) == expected_pick_no


def test_next_pick_no_for_slot_finds_the_wraparound_turn():
    # 12-team snake, slot 1: picks 1, 24, 25, 48, 49 ...
    assert next_pick_no_for_slot(2, 1, 12) == 24
    assert next_pick_no_for_slot(24, 1, 12) == 24
    assert next_pick_no_for_slot(25, 1, 12) == 25


# =========================================================
# STATE ASSEMBLY
# =========================================================

def _league_profile(team_count=4):
    managers = {
        "m{0}".format(index): SimpleNamespace(sleeper_roster_id=index)
        for index in range(1, team_count + 1)
    }
    return SimpleNamespace(
        roster=SimpleNamespace(roster_size=2, starting_lineup=("QB", "RB")),
        managers=managers,
    )


def _draft(team_count=4, rounds=2):
    return {
        "type": "snake",
        "slot_to_roster_id": {str(index): index for index in range(1, team_count + 1)},
        "settings": {"rounds": rounds},
    }


def _sleeper_players():
    return {
        "101": {"full_name": "Player One", "position": "RB"},
        "102": {"full_name": "Player Two", "position": "WR"},
    }


def test_state_with_no_picks_puts_manager_one_on_the_clock():
    state = build_snake_draft_state(
        draft=_draft(),
        picks=[],
        league_profile=_league_profile(),
        sleeper_players=_sleeper_players(),
        viewer_manager_id="m1",
    )

    assert state.current_pick_no == 1
    assert state.current_round == 1
    assert state.current_slot == 1
    assert state.current_manager_id == "m1"
    assert state.on_the_clock_is_me is True
    assert state.is_complete is False
    assert [pick.manager_id for pick in state.next_picks[:4]] == ["m1", "m2", "m3", "m4"]


def test_state_advances_past_made_picks_and_tracks_rosters():
    picks = [
        {"player_id": "101", "pick_no": 1, "round": 1, "draft_slot": 1, "roster_id": 1},
        {"player_id": "102", "pick_no": 2, "round": 1, "draft_slot": 2, "roster_id": 2},
    ]
    state = build_snake_draft_state(
        draft=_draft(),
        picks=picks,
        league_profile=_league_profile(),
        sleeper_players=_sleeper_players(),
        viewer_manager_id="m3",
    )

    assert state.current_pick_no == 3
    assert state.current_manager_id == "m3"
    assert state.drafted_player_ids == frozenset({"101", "102"})
    assert state.roster_by_manager["m1"][0].player_name == "Player One"
    assert state.roster_by_manager["m2"][0].position == "WR"
    assert state.viewer_slot == 3


def test_state_marks_draft_complete_once_every_pick_is_made():
    picks = [
        {"player_id": str(100 + index), "pick_no": index, "round": 1, "draft_slot": index, "roster_id": index}
        for index in range(1, 5)
    ] + [
        {"player_id": str(200 + index), "pick_no": 4 + index, "round": 2, "draft_slot": 5 - index, "roster_id": 5 - index}
        for index in range(1, 5)
    ]
    state = build_snake_draft_state(
        draft=_draft(rounds=2),
        picks=picks,
        league_profile=_league_profile(),
        sleeper_players={},
    )

    assert state.is_complete is True
    assert state.current_pick_no == 0
    assert state.next_picks == ()


# =========================================================
# ROSTER NEED
# =========================================================

def test_roster_need_reports_open_starter_and_flex_gaps():
    need = build_roster_need(
        drafted_positions=["QB", "RB"],
        starting_lineup=("QB", "RB", "RB", "WR", "FLEX"),
        roster_size=6,
    )

    assert need.starter_gaps == {"QB": 0, "RB": 1, "WR": 1}
    assert need.flex_gap == 1
    assert need.open_spots == 4


def test_roster_need_credits_surplus_flex_eligible_players_toward_flex_gap():
    need = build_roster_need(
        drafted_positions=["QB", "RB", "RB", "RB"],
        starting_lineup=("QB", "RB", "RB", "FLEX"),
        roster_size=4,
    )

    assert need.starter_gaps == {"QB": 0, "RB": 0}
    assert need.flex_gap == 0


def test_superflex_gap_is_filled_by_surplus_qb_and_boosts_qb_when_open():
    open_need = build_roster_need(
        drafted_positions=["QB", "RB"],
        starting_lineup=("QB", "RB", "SUPER_FLEX"),
        roster_size=4,
    )
    assert open_need.flex_gaps == {"SUPER_FLEX": 1}

    board = build_draft_board(
        player_values=[
            _player_value("Available QB", "QB", 40.0),
            _player_value("Available WR", "WR", 42.0),
        ],
        drafted_player_names=[],
        roster_need=open_need,
    )
    assert board[0].player_name == "Available WR"
    assert all(entry.need_bonus == 3.0 for entry in board)

    filled_need = build_roster_need(
        drafted_positions=["QB", "QB", "RB"],
        starting_lineup=("QB", "RB", "SUPER_FLEX"),
        roster_size=4,
    )
    assert filled_need.flex_gap == 0
    assert filled_need.flex_gaps == {}


def test_restricted_receiver_flex_does_not_boost_running_back():
    need = build_roster_need(
        drafted_positions=["RB"],
        starting_lineup=("RB", "REC_FLEX"),
        roster_size=3,
    )
    board = build_draft_board(
        player_values=[
            _player_value("Running Back", "RB", 40.0),
            _player_value("Wide Receiver", "WR", 38.0),
        ],
        drafted_player_names=[],
        roster_need=need,
    )
    assert board[0].player_name == "Wide Receiver"
    assert board[0].need_bonus == 3.0
    assert board[1].need_bonus == 0.0


# =========================================================
# DRAFT BOARD
# =========================================================

def _player_value(player_name, position, vorp):
    return SimpleNamespace(
        player_name=player_name,
        position=position,
        vorp=vorp,
        projected_points=vorp + 100,
    )


def test_draft_board_excludes_drafted_players_and_ranks_by_utility():
    values = [
        _player_value("Taken Player", "RB", 50.0),
        _player_value("Best Available", "WR", 40.0),
        _player_value("Second Best", "QB", 35.0),
    ]

    board = build_draft_board(
        player_values=values,
        drafted_player_names=["Taken Player"],
    )

    assert [entry.player_name for entry in board] == ["Best Available", "Second Best"]
    # Only one startable player remains at WR, so the scarcity bonus (capped
    # at SCARCITY_WEIGHT=4.0, ramping in below SCARCITY_FLOOR=10 remaining)
    # is near its max: 4.0 * (10 - 1) / 10 = 3.6.
    assert board[0].scarcity_bonus == pytest.approx(3.6)
    assert board[0].utility == pytest.approx(43.6)


def test_draft_board_boosts_players_who_fill_an_open_starter_need():
    values = [
        _player_value("Elite RB", "RB", 50.0),
        _player_value("Needed QB", "QB", 45.0),
    ]
    need = build_roster_need(
        drafted_positions=["RB"],
        starting_lineup=("QB", "RB"),
        roster_size=2,
    )

    board = build_draft_board(
        player_values=values,
        drafted_player_names=[],
        roster_need=need,
    )

    assert board[0].player_name == "Needed QB"
    assert board[0].need_bonus > 0
    assert board[1].need_bonus == 0


# =========================================================
# REMAINING ROSTER PLAN
# =========================================================

def test_optimize_snake_roster_plan_fills_every_open_slot_with_best_available():
    board = build_draft_board(
        player_values=[
            _player_value("Star QB", "QB", 50.0),
            _player_value("Good RB", "RB", 45.0),
            _player_value("Good WR", "WR", 40.0),
            _player_value("Bench RB", "RB", 20.0),
        ],
        drafted_player_names=[],
    )
    need = build_roster_need(
        drafted_positions=[],
        starting_lineup=("QB", "RB", "WR"),
        roster_size=4,
    )

    plan = optimize_snake_roster_plan(roster_need=need, draft_board=board)

    assert plan.feasible is True
    assert len(plan.entries) == 4
    assigned_names = {entry.player_name for entry in plan.entries}
    assert assigned_names == {"Star QB", "Good RB", "Good WR", "Bench RB"}
    assert not any(entry.is_filler for entry in plan.entries)


def test_optimize_snake_roster_plan_never_double_books_a_player_across_slots():
    board = build_draft_board(
        player_values=[
            _player_value("Only RB", "RB", 30.0),
        ],
        drafted_player_names=[],
    )
    need = build_roster_need(
        drafted_positions=[],
        starting_lineup=("RB", "FLEX"),
        roster_size=2,
    )

    plan = optimize_snake_roster_plan(roster_need=need, draft_board=board)

    filled = [entry for entry in plan.entries if not entry.is_filler]
    assert len(filled) == 1
    assert sum(1 for entry in plan.entries if entry.is_filler) == 1


def test_optimize_snake_roster_plan_is_noop_with_no_open_spots():
    need = build_roster_need(
        drafted_positions=["QB"],
        starting_lineup=("QB",),
        roster_size=1,
    )

    plan = optimize_snake_roster_plan(roster_need=need, draft_board=[])

    assert plan.feasible is True
    assert plan.entries == ()
    assert plan.total_utility == 0.0


# =========================================================
# BYE WEEK AWARENESS
# =========================================================

def test_load_bye_weeks_returns_empty_for_missing_file():
    assert load_bye_weeks("data/does_not_exist.csv") == {}


def test_bye_week_stack_warnings_flags_third_player_on_same_bye():
    candidates = [
        DraftBoardEntry("Third Bye Wk 11", "WR", 20.0, 0.0, 20.0, 150.0),
        DraftBoardEntry("Clean Bye Wk 7", "WR", 18.0, 0.0, 18.0, 140.0),
    ]
    bye_weeks = {
        "already rostered one": 11,
        "already rostered two": 11,
        "third bye wk 11": 11,
        "clean bye wk 7": 7,
    }

    warnings = bye_week_stack_warnings(
        candidates=candidates,
        my_drafted_player_names=["Already Rostered One", "Already Rostered Two"],
        bye_weeks=bye_weeks,
    )

    assert "Third Bye Wk 11" in warnings
    assert "Clean Bye Wk 7" not in warnings


def test_bye_week_stack_warnings_empty_when_no_bye_data():
    candidates = [DraftBoardEntry("Nobody", "WR", 20.0, 0.0, 20.0, 150.0)]
    assert bye_week_stack_warnings(
        candidates=candidates, my_drafted_player_names=[], bye_weeks={}
    ) == {}


# =========================================================
# RUNOUT RISK
# =========================================================

def test_survival_probability_is_near_certain_well_before_average_rank():
    prob = survival_probability(average_rank=30.0, rank_stddev=5.0, target_pick_no=5)
    assert prob > 0.99


def test_survival_probability_is_near_zero_well_after_average_rank():
    prob = survival_probability(average_rank=5.0, rank_stddev=1.0, target_pick_no=30)
    assert prob < 0.01


def test_survival_probability_is_roughly_even_at_average_rank():
    prob = survival_probability(average_rank=20.0, rank_stddev=5.0, target_pick_no=20)
    assert prob == pytest.approx(0.5, abs=0.01)


def test_load_adp_distribution_returns_empty_for_missing_file():
    assert load_adp_distribution("data/does_not_exist.csv") == {}


# =========================================================
# TEAM VALUE LEADERBOARD
# =========================================================

def test_team_value_leaderboard_sums_vorp_per_manager_and_sorts_descending():
    roster_by_manager = {
        "alice": (
            SimpleNamespace(player_name="Star Player", position="RB"),
            SimpleNamespace(player_name="Bench Guy", position="WR"),
        ),
        "bob": (SimpleNamespace(player_name="Solid Pick", position="QB"),),
    }
    player_values = [
        _player_value("Star Player", "RB", 50.0),
        _player_value("Bench Guy", "WR", 10.0),
        _player_value("Solid Pick", "QB", 30.0),
    ]

    leaderboard = build_team_value_leaderboard(
        roster_by_manager=roster_by_manager, player_values=player_values
    )

    assert [entry.manager_id for entry in leaderboard] == ["alice", "bob"]
    assert leaderboard[0].total_vorp == pytest.approx(60.0)
    assert leaderboard[0].picks_made == 2
    assert leaderboard[1].total_vorp == pytest.approx(30.0)


def test_team_value_leaderboard_ignores_unmatched_players():
    roster_by_manager = {
        "alice": (SimpleNamespace(player_name="Ghost Player", position="RB"),),
    }
    leaderboard = build_team_value_leaderboard(
        roster_by_manager=roster_by_manager, player_values=[]
    )
    assert leaderboard[0].total_vorp == 0.0
    assert leaderboard[0].picks_made == 1
