from src.my_guys import MyGuysPreferences, MyGuysStore


def test_default_premium_is_zero_and_cap_never_exceeds_legal_max():
    default = MyGuysPreferences("league", "user", ("Player One",))
    assert default.adjusted_cap("Player One", 20, 30) == 20
    premium = MyGuysPreferences("league", "user", ("Player One",), 5)
    assert premium.adjusted_cap("player one", 20, 23) == 23
    assert premium.adjusted_cap("Other", 20, 30) == 20


def test_my_guys_are_namespaced_by_league_and_user(tmp_path):
    store = MyGuysStore(tmp_path)
    first = MyGuysPreferences("league-a", "user-1", ("A",), 2)
    second = MyGuysPreferences("league-a", "user-2", ("B",), 4)
    store.save(first)
    store.save(second)
    assert store.load("league-a", "user-1") == first
    assert store.load("league-a", "user-2") == second
    assert store.load("league-b", "user-1") is None
