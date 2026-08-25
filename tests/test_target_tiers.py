from types import SimpleNamespace

from src.target_tiers import build_target_tier_board


def test_target_tiers_group_by_position_and_create_fallback_chain():
    candidates = [
        SimpleNamespace(player_name="A", position="WR", utility=100, expected_cost=40),
        SimpleNamespace(player_name="B", position="WR", utility=95, expected_cost=30),
        SimpleNamespace(player_name="C", position="WR", utility=70, expected_cost=18),
        SimpleNamespace(player_name="D", position="RB", utility=90, expected_cost=35),
    ]
    board = build_target_tier_board(candidates)
    assert [target.tier for target in board.by_position["WR"]] == [1, 1, 2]
    assert [target.player_name for target in board.fallback_chain("A")] == ["B", "C"]
    assert board.fallback_chain("D") == ()
