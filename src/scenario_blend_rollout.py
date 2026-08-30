from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.price_thresholds import LivePriceThresholds
from src.scenario_blend_preview import ScenarioBlendPreview
from src.scenario_model_promotion import PromotionReadiness, PromotionStatus


@dataclass(frozen=True)
class ScenarioBlendSetting:
    league_key: str
    user_key: str
    manager_id: str
    enabled: bool = False
    ml_weight: float = 0.25
    approved_model_version: str = ""
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class ScenarioBlendDecision:
    thresholds: LivePriceThresholds
    applied: bool
    reason: str


def apply_guarded_blend(
    base: LivePriceThresholds,
    preview: Optional[ScenarioBlendPreview],
    setting: Optional[ScenarioBlendSetting],
    readiness: PromotionReadiness,
    model_version: str,
) -> ScenarioBlendDecision:
    if setting is None or not setting.enabled:
        return ScenarioBlendDecision(base, False, "Blend rollout is not enabled.")
    if readiness.status is not PromotionStatus.READY:
        return ScenarioBlendDecision(
            base, False, "Prospective promotion gates are not READY."
        )
    if preview is None:
        return ScenarioBlendDecision(base, False, "No scenario prediction is available.")
    if setting.approved_model_version != str(model_version):
        return ScenarioBlendDecision(
            base, False, "The active model version is not the approved version."
        )
    return ScenarioBlendDecision(
        LivePriceThresholds(
            target_value=preview.target_value,
            soft_cap=preview.soft_cap,
            hard_cap=preview.hard_cap,
            explanation="Guarded 25% scenario blend after promotion approval.",
        ),
        True,
        "Approved 25% scenario blend is active.",
    )
