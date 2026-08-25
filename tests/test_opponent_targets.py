from types import SimpleNamespace

from src.opponent_targets import build_opponent_target_profiles


def test_profiles_use_needs_cash_tiers_and_history_without_exact_bids():
    needs = {
        "me": SimpleNamespace(auction_cash=100, max_bid=90, need_scores={"WR": 1}),
        "opp": SimpleNamespace(
            auction_cash=80,
            max_bid=45,
            need_scores={"WR": 0.9, "RB": 0.4, "TE": 0.1},
        ),
    }
    tendency = SimpleNamespace(
        manager_id="opp",
        confidence=0.8,
        position_premiums=(("WR", 1.2),),
    )

    profiles = build_opponent_target_profiles(
        team_need_profiles=needs,
        current_manager_id="me",
        manager_tendency_profiles=(tendency,),
    )

    assert len(profiles) == 1
    assert profiles[0].likely_positions[0] == "WR"
    assert profiles[0].likely_tiers == ("elite", "starter", "depth")
    assert profiles[0].cash_strength == 0.8
    assert "bid" not in " ".join(profiles[0].reasons).lower()
