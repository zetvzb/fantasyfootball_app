from src.dynamic_cap import DynamicCapInput, adjust_dynamic_cap


def _input(**overrides):
    values = dict(
        base_cap=50,
        legal_max_bid=100,
        need_score=0.5,
        scarcity_score=0.5,
        has_comparable_alternative=True,
        cash_flexibility=0.5,
        auction_stage=0.5,
        room_inflation_index=1.0,
        current_weight=0.6,
        future_weight=0.4,
        future_value_score=0.5,
        context_adjustment_pct=0.0,
    )
    values.update(overrides)
    return DynamicCapInput(**values)


def test_need_scarcity_inflation_cash_and_future_value_can_raise_cap():
    result = adjust_dynamic_cap(
        _input(
            need_score=1,
            scarcity_score=1,
            has_comparable_alternative=False,
            cash_flexibility=1,
            auction_stage=1,
            room_inflation_index=1.2,
            future_weight=0.7,
            future_value_score=1,
        )
    )
    assert result.adjusted_cap > result.base_cap
    assert result.total_adjustment_pct <= 0.12
    assert {component.factor for component in result.components} >= {
        "roster_need", "scarcity", "alternatives", "cash", "auction_stage",
        "room_inflation", "strategy_future", "context",
    }


def test_alternatives_low_need_and_deflation_lower_cap_but_respect_legal_bounds():
    result = adjust_dynamic_cap(
        _input(need_score=0, scarcity_score=0, room_inflation_index=0.8)
    )
    assert 1 <= result.adjusted_cap < result.base_cap
