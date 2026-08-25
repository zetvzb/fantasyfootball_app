from src.draft_store import DraftStore
from src.recommendation_snapshot import RecommendationSnapshot


def _snapshot(decision="BID", bid=10):
    return RecommendationSnapshot(
        player_name="Player One",
        current_bid=bid,
        target_value=12,
        soft_cap=15,
        hard_cap=18,
        decision=decision,
        alternatives=({"player_name": "Fallback", "availability_probability": 0.7},),
        roster_state={"open_roster_spots": 4},
        budget_state={"live_cash": 50, "discretionary_cash": 46},
        inflation_state={"room_inflation_index": 1.1},
        context_state={"adjustment_pct": -0.02},
        reasons=("scarce tier",),
    )


def test_snapshot_round_trip_is_idempotent_across_restart(tmp_path):
    path = tmp_path / "draft.db"
    store = DraftStore(str(path), "league", "draft", 2026)
    assert store.add_recommendation_snapshot(_snapshot())
    assert not store.add_recommendation_snapshot(_snapshot())
    restarted = DraftStore(str(path), "league", "draft", 2026)
    snapshots = restarted.load_recommendation_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].alternatives[0]["player_name"] == "Fallback"
    assert snapshots[0].roster_state["open_roster_spots"] == 4
    assert snapshots[0].captured_at is not None


def test_material_bid_or_decision_change_creates_new_snapshot(tmp_path):
    store = DraftStore(str(tmp_path / "draft.db"), "league", "draft", 2026)
    assert store.add_recommendation_snapshot(_snapshot())
    assert store.add_recommendation_snapshot(_snapshot(bid=11))
    assert store.add_recommendation_snapshot(_snapshot(decision="PASS"))
    assert len(store.load_recommendation_snapshots()) == 3
