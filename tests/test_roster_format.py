from types import SimpleNamespace as N

from src.auction_values import calculate_auction_values
from src.roster_format import is_superflex, qb_starter_slots


def test_qb_starter_slots_and_superflex_detection():
    one_qb = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "K", "DEF"]
    assert qb_starter_slots(one_qb) == 1
    assert not is_superflex(one_qb)

    superflex = ["QB", "SUPER_FLEX", "RB", "RB", "WR", "WR", "TE", "FLEX"]
    assert qb_starter_slots(superflex) == 2
    assert is_superflex(superflex)

    two_qb = ["QB", "QB", "RB", "WR", "TE"]
    assert is_superflex(two_qb)

    assert not is_superflex(None)
    assert not is_superflex([])


def test_non_superflex_discounts_qb_dynasty_value():
    players = [
        N(player_name="Young QB", position="QB"),
        N(player_name="Anchor RB", position="RB"),
    ]
    team_setups = {
        "a": N(auction_cash=200, open_roster_spots=8, required_reserve=8, minimum_auction_bid=1),
        "b": N(auction_cash=200, open_roster_spots=8, required_reserve=8, minimum_auction_bid=1),
    }
    player_values = [
        N(player_name="Young QB", vorp=60.0, replacement_points=0.0),
        N(player_name="Anchor RB", vorp=120.0, replacement_points=0.0),
    ]
    fp = {
        "young qb": N(half_ecr=14, dynasty_ecr=2),   # elite dynasty rank
        "anchor rb": N(half_ecr=4, dynasty_ecr=8),
    }
    one_qb = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX"]
    superflex = ["QB", "SUPER_FLEX", "RB", "RB", "WR", "WR", "TE", "FLEX"]

    qb_1qb = {
        v.player_name: v.baseline_value
        for v in calculate_auction_values(players, team_setups, player_values, {}, fp, one_qb)
    }["Young QB"]
    qb_sf = {
        v.player_name: v.baseline_value
        for v in calculate_auction_values(players, team_setups, player_values, {}, fp, superflex)
    }["Young QB"]

    assert qb_1qb < qb_sf
