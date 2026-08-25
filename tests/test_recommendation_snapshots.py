from src.draft_store import DraftStore
from src.recommendation_snapshot import RecommendationSnapshot
from src.recommendation_snapshot import build_recommendation_snapshot
from types import SimpleNamespace


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


def _private_snapshot(league, user, manager, bid=10):
    snapshot = _snapshot(bid=bid)
    return RecommendationSnapshot(
        **{
            **snapshot.to_dict(),
            "alternatives": snapshot.alternatives,
            "reasons": snapshot.reasons,
            "league_key": league,
            "user_key": user,
            "manager_id": manager,
        }
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


def test_snapshot_adapter_captures_live_need_scores_for_purchase_fit():
    recommendation = SimpleNamespace(
        player_name="Player One",
        position="WR",
        legal_max_bid=30,
        reasons=["WR need"],
    )
    state = SimpleNamespace(
        recommendation=recommendation,
        pass_alternatives=[],
        context_adjustment=SimpleNamespace(
            adjustment_pct=0.0,
            context_confidence=0.5,
        ),
        context_adjusted_ceiling=25,
    )
    context = SimpleNamespace(
        ACTIVE_MY_MANAGER_ID="me",
        live_sales=[object(), object()],
        my_live_setup=SimpleNamespace(
            open_roster_spots=4,
            live_cash=50,
            discretionary_cash=46,
        ),
        my_need_profile=SimpleNamespace(need_scores={"WR": 0.9}),
        inflation_v2=SimpleNamespace(room_inflation_index=1.1),
        runtime_identity=SimpleNamespace(
            league=SimpleNamespace(league_key="league"),
            current=SimpleNamespace(user_key="user", manager_id="me"),
        ),
    )
    snapshot = build_recommendation_snapshot(
        context, state, 15, 20, 24, 28, "BID"
    )
    assert snapshot.roster_state["position_need"] == {"WR": 0.9}
    assert snapshot.roster_state["sale_count"] == 2
    assert (snapshot.league_key, snapshot.user_key, snapshot.manager_id) == (
        "league", "user", "me"
    )


def test_private_recommendation_history_filters_by_league_user_and_manager(tmp_path):
    store = DraftStore(str(tmp_path / "draft.db"), "league-a", "draft", 2026)
    first = _private_snapshot("league-a", "user-1", "manager-1", bid=10)
    other_user = _private_snapshot("league-a", "user-2", "manager-2", bid=11)
    other_league = _private_snapshot("league-b", "user-1", "manager-1", bid=12)
    for snapshot in (first, other_user, other_league):
        assert store.add_recommendation_snapshot(snapshot)

    first_results = store.load_private_recommendation_snapshots(
        "league-a", "user-1", "manager-1"
    )
    assert len(first_results) == 1
    assert first_results[0].current_bid == 10
    assert first_results[0].user_key == "user-1"
    assert [value.current_bid for value in store.load_private_recommendation_snapshots(
        "league-a", "user-2", "manager-2"
    )] == [11]
