from src.price_thresholds import (
    CurrentBidZone,
    build_live_price_thresholds,
    constrain_thresholds,
    evaluate_current_bid,
)


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


def test_current_bid_recomputes_only_across_meaningful_threshold_zones():
    thresholds = build_live_price_thresholds(
        expected_market_value=30,
        baseline_value=40,
        deterministic_ceiling=50,
        legal_max_bid=50,
    )
    assert evaluate_current_bid(20, thresholds).zone is CurrentBidZone.VALUE
    assert evaluate_current_bid(thresholds.target_value, thresholds).zone is CurrentBidZone.TARGET
    assert evaluate_current_bid(thresholds.soft_cap, thresholds).zone is CurrentBidZone.SOFT_CAP
    assert evaluate_current_bid(50, thresholds).zone is CurrentBidZone.HARD_CAP
    assert evaluate_current_bid(51, thresholds).zone is CurrentBidZone.PASS
