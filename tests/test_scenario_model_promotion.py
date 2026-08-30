from src.scenario_model_promotion import (
    PromotionStatus,
    evaluate_promotion_readiness,
)
from src.shadow_price_evaluation import ShadowPriceEvaluation


def _evaluation(count, app_mae=10.0, shadow_mae=8.0, bias=1.0, coverage=0.75):
    return ShadowPriceEvaluation(
        results=tuple(object() for _ in range(count)),
        app_mean_absolute_error=app_mae,
        shadow_mean_absolute_error=shadow_mae,
        app_bias=0.0,
        shadow_bias=bias,
        shadow_median_absolute_error=5.0,
        interval_coverage=coverage,
        blend_preview_mean_absolute_error=shadow_mae,
        blend_preview_bias=bias,
    )


def test_insufficient_sample_remains_in_shadow_mode():
    result = evaluate_promotion_readiness(_evaluation(29))
    assert result.status is PromotionStatus.SHADOW
    assert result.gates[0].passed is False


def test_all_quality_gates_make_model_ready_for_manual_trial_approval():
    result = evaluate_promotion_readiness(_evaluation(30))
    assert result.status is PromotionStatus.READY
    assert all(gate.passed for gate in result.gates)
    assert "approved" in result.recommendation


def test_sufficient_but_poor_evidence_blocks_promotion():
    result = evaluate_promotion_readiness(
        _evaluation(40, app_mae=10, shadow_mae=11, bias=4, coverage=0.5)
    )
    assert result.status is PromotionStatus.BLOCKED
    assert [gate.name for gate in result.gates if not gate.passed] == [
        "Preview MAE improvement", "Preview absolute bias",
        "Prediction-band coverage",
    ]
