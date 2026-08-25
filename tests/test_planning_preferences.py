from src.planning_preferences import (
    PlanningPreferences,
    PlanningPreferencesStore,
    SavedBudgetBand,
    SavedPriorityTier,
)


def _preferences(league="league-a", user="user-1", manager="manager-1"):
    return PlanningPreferences(
        league_key=league,
        user_key=user,
        manager_id=manager,
        recommended_strategy="Hybrid",
        budget_bands=(SavedBudgetBand("WR", 2, 40, 50),),
        priority_tiers=(SavedPriorityTier("Priority", ("Player One",)),),
        nomination_plan="Drain cash",
        fallback_plan=("Player Two",),
    )


def test_planning_preferences_survive_restart_and_preserve_typed_plan(tmp_path):
    preferences = _preferences()
    PlanningPreferencesStore(tmp_path).save(preferences)
    restored = PlanningPreferencesStore(tmp_path).load(
        "league-a", "user-1", "manager-1"
    )
    assert restored == preferences
    assert restored.budget_bands[0].target == 40
    assert restored.priority_tiers[0].player_names == ("Player One",)


def test_planning_preferences_are_scoped_by_league_user_and_manager(tmp_path):
    store = PlanningPreferencesStore(tmp_path)
    values = (
        _preferences(),
        _preferences(user="user-2", manager="manager-2"),
        _preferences(league="league-b"),
    )
    for value in values:
        store.save(value)

    assert store.load("league-a", "user-1", "manager-1") == values[0]
    assert store.load("league-a", "user-2", "manager-2") == values[1]
    assert store.load("league-b", "user-1", "manager-1") == values[2]
    assert store.load("league-a", "user-1", "manager-2") is None
    assert len(list(tmp_path.glob("*.json"))) == 3
