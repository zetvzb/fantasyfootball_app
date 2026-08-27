from types import SimpleNamespace

import pytest

from src.snake_draft import (
    build_draft_board,
    build_roster_need,
    build_snake_draft_state,
    optimize_snake_roster_plan,
    pick_no_for_slot,
    slot_for_pick_no,
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
    assert board[0].utility == pytest.approx(40.0)


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
