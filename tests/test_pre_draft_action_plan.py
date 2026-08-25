from src.position_budgets import optimize_position_budgets
from src.pre_draft_action_plan import build_pre_draft_action_plan


def test_action_plan_composes_all_pre_draft_decisions():
    budgets = optimize_position_budgets(100, {"RB": 2, "WR": 2}, {"RB": 0.8, "WR": 0.6})
    plan = build_pre_draft_action_plan(
        "Balanced",
        budgets,
        {"Tier 1": ["A", "B"], "Tier 2": ["C"]},
        "Drain cash with X",
        ["C", "D"],
    )
    assert plan.recommended_strategy == "Balanced"
    assert plan.priority_tiers[0].player_names == ("A", "B")
    assert plan.nomination_plan == "Drain cash with X"
    assert plan.fallback_plan == ("C", "D")
    assert plan.budget_plan.minimum_reserve == 4
