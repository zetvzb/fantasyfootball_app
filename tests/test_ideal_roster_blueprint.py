from types import SimpleNamespace

from src.ideal_roster_blueprint import build_ideal_roster_blueprint


def test_blueprint_uses_expected_price_plan_and_non_rigid_alternatives():
    entry = SimpleNamespace(slot="WR1", position="WR", planned_cost=20, player_name="A")
    plan = SimpleNamespace(feasible=True, entries=[entry], planned_spend=20, cash_after_plan=5)
    candidates = [
        SimpleNamespace(player_name="A", position="WR", expected_cost=20, utility=10),
        SimpleNamespace(player_name="B", position="WR", expected_cost=21, utility=9),
        SimpleNamespace(player_name="C", position="WR", expected_cost=30, utility=20),
        SimpleNamespace(player_name="D", position="RB", expected_cost=10, utility=30),
    ]
    blueprint = build_ideal_roster_blueprint(plan, candidates)
    assert blueprint.feasible
    assert blueprint.slots[0].expected_price == 20
    assert blueprint.slots[0].preferred_player == "A"
    assert blueprint.slots[0].alternatives == ("B",)


def test_blueprint_handles_infeasible_plan():
    result = build_ideal_roster_blueprint(SimpleNamespace(feasible=False), [])
    assert not result.feasible
    assert result.slots == ()
