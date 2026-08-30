from src.price_thresholds import LivePriceThresholds
from src.scenario_blend_preview import build_scenario_blend_preview


def _thresholds(target=20, soft=25, hard=30):
    return LivePriceThresholds(target, soft, hard, "test")


def test_preview_shifts_threshold_ladder_without_exceeding_legal_max():
    preview = build_scenario_blend_preview(
        _thresholds(), scenario_price=40, legal_max_bid=33,
    )
    assert (preview.target_value, preview.soft_cap, preview.hard_cap) == (25, 30, 33)
    assert preview.ml_weight == 0.25
    assert preview.to_shadow_fields()["blend_mode"] == "preview"


def test_preview_weight_is_capped_at_conservative_trial_ceiling():
    preview = build_scenario_blend_preview(
        _thresholds(), scenario_price=40, legal_max_bid=100, ml_weight=0.75,
    )
    assert preview.ml_weight == 0.25
    assert preview.target_value == 25


def test_lower_scenario_price_preserves_ordered_positive_thresholds():
    preview = build_scenario_blend_preview(
        _thresholds(), scenario_price=1, legal_max_bid=100,
    )
    assert 1 <= preview.target_value <= preview.soft_cap <= preview.hard_cap
