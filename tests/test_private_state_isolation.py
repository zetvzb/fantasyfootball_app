from types import SimpleNamespace

import pytest

from src.draft_store import DraftStore
from src.my_guys import MyGuysPreferences, MyGuysStore
from src.planning_preferences import PlanningPreferences, PlanningPreferencesStore
from src.private_state import (
    PrivateStateAccess,
    PrivateStateIsolationError,
    PrivateStateScope,
)
from src.recommendation_snapshot import RecommendationSnapshot
from src.strategy_profile import StrategyMode, StrategyProfile, StrategyProfileStore


def _access(league="league", user="user-1", manager="manager-1"):
    runtime = SimpleNamespace(
        league=SimpleNamespace(league_key=league),
        current=SimpleNamespace(user_key=user, manager_id=manager),
    )
    return PrivateStateAccess.from_runtime_identity(runtime)


def _snapshot(user="user-1", manager="manager-1"):
    return RecommendationSnapshot(
        player_name="Player",
        current_bid=1,
        target_value=2,
        soft_cap=3,
        hard_cap=4,
        decision="BID",
        alternatives=(),
        roster_state={},
        budget_state={},
        inflation_state={},
        context_state={},
        reasons=(),
        league_key="league",
        user_key=user,
        manager_id=manager,
    )


def test_private_access_rejects_cross_user_strategy_and_my_guys(tmp_path):
    access = _access()
    strategy_store = StrategyProfileStore(tmp_path / "strategy")
    my_guys_store = MyGuysStore(tmp_path / "my-guys")
    own_strategy = StrategyProfile.for_mode("league", "user-1", StrategyMode.HYBRID)
    own_guys = MyGuysPreferences("league", "user-1", ("Player",), 2)

    access.save_strategy(strategy_store, own_strategy)
    access.save_my_guys(my_guys_store, own_guys)
    assert access.load_strategy(strategy_store) == own_strategy
    assert access.load_my_guys(my_guys_store) == own_guys

    with pytest.raises(PrivateStateIsolationError):
        access.save_strategy(
            strategy_store,
            StrategyProfile.for_mode("league", "user-2", StrategyMode.WIN_NOW),
        )
    with pytest.raises(PrivateStateIsolationError):
        access.save_my_guys(
            my_guys_store,
            MyGuysPreferences("league", "user-2", ("Secret",), 10),
        )


def test_private_access_rejects_cross_manager_planning(tmp_path):
    access = _access()
    store = PlanningPreferencesStore(tmp_path)
    own = PlanningPreferences("league", "user-1", "manager-1", "Hybrid")
    access.save_planning(store, own)
    assert access.load_planning(store) == own

    with pytest.raises(PrivateStateIsolationError, match="another manager"):
        access.save_planning(
            store,
            PlanningPreferences("league", "user-1", "manager-2", "Win Now"),
        )


def test_bound_draft_store_cannot_write_or_read_another_users_history(tmp_path):
    store = DraftStore(str(tmp_path / "draft.db"), "league", "draft", 2026)
    scope = PrivateStateScope("league", "user-1", "manager-1")
    store.bind_private_scope(scope)
    assert store.add_recommendation_snapshot(_snapshot()) is True
    assert len(store.load_private_recommendation_snapshots(
        "league", "user-1", "manager-1"
    )) == 1

    with pytest.raises(PrivateStateIsolationError):
        store.add_recommendation_snapshot(_snapshot("user-2", "manager-2"))
    with pytest.raises(PrivateStateIsolationError):
        store.load_private_recommendation_snapshots(
            "league", "user-2", "manager-2"
        )
