from src.price_thresholds import build_live_price_thresholds, constrain_thresholds


def test_target_soft_and_hard_caps_are_ordered_and_legally_bounded():
    thresholds = build_live_price_thresholds(
        expected_market_value=30,
        baseline_value=40,
        deterministic_ceiling=50,
        legal_max_bid=45,
    )

    assert thresholds.target_value == 35
    assert thresholds.target_value <= thresholds.soft_cap <= thresholds.hard_cap
    assert thresholds.hard_cap == 45


def test_final_context_or_roster_cap_constrains_all_thresholds():
    original = build_live_price_thresholds(
        expected_market_value=30,
        baseline_value=40,
        deterministic_ceiling=50,
        legal_max_bid=50,
    )
    constrained = constrain_thresholds(original, 25)
    assert (constrained.target_value, constrained.soft_cap, constrained.hard_cap) == (25, 25, 25)
