from __future__ import annotations

from dataclasses import dataclass

from src.price_thresholds import LivePriceThresholds


DEFAULT_PREVIEW_WEIGHT = 0.25


@dataclass(frozen=True)
class ScenarioBlendPreview:
    target_value: int
    soft_cap: int
    hard_cap: int
    ml_weight: float

    def to_shadow_fields(self) -> dict:
        return {
            "blend_mode": "preview",
            "blend_weight": self.ml_weight,
            "blend_target_value": self.target_value,
            "blend_soft_cap": self.soft_cap,
            "blend_hard_cap": self.hard_cap,
        }


def build_scenario_blend_preview(
    thresholds: LivePriceThresholds,
    scenario_price: float,
    legal_max_bid: int,
    ml_weight: float = DEFAULT_PREVIEW_WEIGHT,
) -> ScenarioBlendPreview:
    """Shift the threshold ladder by a bounded blend of expected sale price."""
    weight = max(0.0, min(DEFAULT_PREVIEW_WEIGHT, float(ml_weight)))
    legal_max = max(1, int(legal_max_bid))
    target = max(
        1,
        min(
            legal_max,
            int(round(
                (1.0 - weight) * thresholds.target_value
                + weight * float(scenario_price)
            )),
        ),
    )
    delta = target - thresholds.target_value
    soft = max(target, min(legal_max, thresholds.soft_cap + delta))
    hard = max(soft, min(legal_max, thresholds.hard_cap + delta))
    return ScenarioBlendPreview(target, soft, hard, weight)
