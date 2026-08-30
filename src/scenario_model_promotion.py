from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from src.shadow_price_evaluation import ShadowPriceEvaluation


class PromotionStatus(str, Enum):
    SHADOW = "SHADOW"
    READY = "READY"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class PromotionPolicy:
    minimum_matched_sales: int = 30
    minimum_mae_improvement_pct: float = 0.05
    maximum_absolute_bias: float = 3.0
    minimum_interval_coverage: float = 0.65


@dataclass(frozen=True)
class PromotionGate:
    name: str
    passed: bool
    observed: Optional[float]
    requirement: str

    @property
    def observed_display(self) -> str:
        if self.observed is None:
            return "Not available"
        if self.name == "Matched sales":
            return str(int(self.observed))
        if self.name in {"Preview MAE improvement", "Prediction-band coverage"}:
            return "{0:.1%}".format(self.observed)
        return "${0:.2f}".format(self.observed)


@dataclass(frozen=True)
class PromotionReadiness:
    status: PromotionStatus
    gates: Tuple[PromotionGate, ...]
    recommendation: str


def evaluate_promotion_readiness(
    evaluation: ShadowPriceEvaluation,
    policy: PromotionPolicy = PromotionPolicy(),
) -> PromotionReadiness:
    count = len(evaluation.results)
    app_mae = evaluation.app_mean_absolute_error
    shadow_mae = evaluation.blend_preview_mean_absolute_error
    improvement = (
        (app_mae - shadow_mae) / app_mae
        if app_mae not in (None, 0) and shadow_mae is not None
        else None
    )
    absolute_bias = (
        abs(evaluation.blend_preview_bias)
        if evaluation.blend_preview_bias is not None else None
    )
    coverage = evaluation.interval_coverage
    gates = (
        PromotionGate(
            "Matched sales",
            count >= policy.minimum_matched_sales,
            float(count),
            "at least {0}".format(policy.minimum_matched_sales),
        ),
        PromotionGate(
            "Preview MAE improvement",
            improvement is not None
            and improvement >= policy.minimum_mae_improvement_pct,
            improvement,
            "at least {0:.0%}".format(policy.minimum_mae_improvement_pct),
        ),
        PromotionGate(
            "Preview absolute bias",
            absolute_bias is not None
            and absolute_bias <= policy.maximum_absolute_bias,
            absolute_bias,
            "no more than ${0:.2f}".format(policy.maximum_absolute_bias),
        ),
        PromotionGate(
            "Prediction-band coverage",
            coverage is not None and coverage >= policy.minimum_interval_coverage,
            coverage,
            "at least {0:.0%}".format(policy.minimum_interval_coverage),
        ),
    )
    if count < policy.minimum_matched_sales:
        return PromotionReadiness(
            PromotionStatus.SHADOW,
            gates,
            "Keep collecting live shadow observations before considering a blend.",
        )
    if all(gate.passed for gate in gates):
        return PromotionReadiness(
            PromotionStatus.READY,
            gates,
            "Evidence supports a separately approved, limited-weight blend trial.",
        )
    return PromotionReadiness(
        PromotionStatus.BLOCKED,
        gates,
        "Do not blend the model until every failed quality gate is resolved.",
    )
