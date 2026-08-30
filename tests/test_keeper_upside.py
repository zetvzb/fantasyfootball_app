from types import SimpleNamespace as N

from src.keeper_upside import build_keeper_stash_board


def _fp(half, dyn):
    return N(half_ecr=half, dynasty_ecr=dyn)


def test_board_surfaces_cheap_ascending_players_and_skips_expensive_or_washed():
    players = [
        N(player_name="Young Stud", position="WR"),
        N(player_name="Washed Vet", position="RB"),
        N(player_name="Pricey Star", position="RB"),
        N(player_name="Kicker Guy", position="K"),
        N(player_name="No Dynasty Data", position="WR"),
    ]
    market_value_index = {
        "young stud": N(expected_market_value=2.0),
        "washed vet": N(expected_market_value=2.0),
        "pricey star": N(expected_market_value=45.0),
        "kicker guy": N(expected_market_value=1.0),
        "no dynasty data": N(expected_market_value=1.0),
    }
    fantasypros_index = {
        "young stud": _fp(90, 35),      # redraft 90, dynasty 35 -> rising, cheap
        "washed vet": _fp(70, 160),     # dynasty far worse -> not a keeper
        "pricey star": _fp(8, 6),       # great but too expensive to be a "stash"
        "kicker guy": _fp(120, 120),
        "no dynasty data": N(half_ecr=100, dynasty_ecr=None),
    }

    board = build_keeper_stash_board(
        available_players=players,
        market_value_index=market_value_index,
        fantasypros_index=fantasypros_index,
        annual_escalation=10,
        average_team_budget=200.0,
    )

    names = [c.player_name for c in board]
    assert "Young Stud" in names
    assert "Washed Vet" not in names
    assert "Pricey Star" not in names  # filtered by max_acquisition_cost
    assert "Kicker Guy" not in names
    assert "No Dynasty Data" not in names

    stud = next(c for c in board if c.player_name == "Young Stud")
    assert stud.acquisition_cost == 2
    assert stud.next_year_keeper_cost == 12
    assert stud.keeper_surplus > 0
    assert stud.ascending_gap == 55.0


def test_eligible_positions_filters_out_positions_the_league_never_keeps():
    players = [
        N(player_name="Cheap QB", position="QB"),
        N(player_name="Cheap WR", position="WR"),
    ]
    mvi = {"cheap qb": N(expected_market_value=2.0), "cheap wr": N(expected_market_value=2.0)}
    fpi = {"cheap qb": _fp(90, 30), "cheap wr": _fp(90, 30)}

    board = build_keeper_stash_board(
        available_players=players,
        market_value_index=mvi,
        fantasypros_index=fpi,
        annual_escalation=10,
        average_team_budget=250.0,
        eligible_positions=["WR", "RB"],
    )

    names = [c.player_name for c in board]
    assert "Cheap WR" in names
    assert "Cheap QB" not in names


def test_board_sorted_by_surplus_desc():
    players = [
        N(player_name="A", position="WR"),
        N(player_name="B", position="WR"),
    ]
    mvi = {"a": N(expected_market_value=1.0), "b": N(expected_market_value=1.0)}
    fpi = {"a": _fp(50, 40), "b": _fp(30, 20)}
    board = build_keeper_stash_board(
        available_players=players,
        market_value_index=mvi,
        fantasypros_index=fpi,
        annual_escalation=10,
        average_team_budget=300.0,
    )
    assert [c.player_name for c in board] == ["B", "A"]
    assert board[0].keeper_surplus >= board[1].keeper_surplus
