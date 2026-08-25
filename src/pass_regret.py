from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass(frozen=True)
class PassRegretRisk:
    score: float
    level: str
    scarcity: float
    roster_need: float
    competitor_pressure: float
    alternative_risk: float
    tier_drop: float
    reasons: Tuple[str, ...]


def calculate_pass_regret_risk(
    *,
    scarcity: float,
    roster_need: float,
    competitor_pressure: float,
    player_vorp: float,
    alternatives: Sequence[object],
) -> PassRegretRisk:
    clamp = lambda value: max(0.0, min(1.0, float(value)))
    scarcity_value = clamp(scarcity)
    need_value = clamp(roster_need)
    competitor_value = clamp(float(competitor_pressure) / 100.0)
    best_availability = max(
        (float(item.availability_probability) for item in alternatives),
        default=0.0,
    )
    alternative_risk = 1.0 - best_availability
    best_vorp = max((float(item.vorp) for item in alternatives), default=0.0)
    tier_drop = clamp((float(player_vorp) - best_vorp) / max(1.0, abs(float(player_vorp))))
    score = 100.0 * (
        0.30 * scarcity_value
        + 0.25 * need_value
        + 0.20 * competitor_value
        + 0.15 * alternative_risk
        + 0.10 * tier_drop
    )
    level = "HIGH" if score >= 67 else "MEDIUM" if score >= 34 else "LOW"
    reasons = []
    if scarcity_value >= 0.65:
        reasons.append("The remaining tier is scarce.")
    if need_value >= 0.75:
        reasons.append("The player fills a major roster need.")
    if competitor_value >= 0.65:
        reasons.append("Competitor pressure is high.")
    if alternative_risk >= 0.60:
        reasons.append("Fallback availability is weak.")
    if tier_drop >= 0.30:
        reasons.append("Passing creates a meaningful value-tier drop.")
    if not reasons:
        reasons.append("Comparable paths remain available.")
    return PassRegretRisk(
        score=round(score, 1),
        level=level,
        scarcity=round(scarcity_value, 3),
        roster_need=round(need_value, 3),
        competitor_pressure=round(competitor_value, 3),
        alternative_risk=round(alternative_risk, 3),
        tier_drop=round(tier_drop, 3),
        reasons=tuple(reasons),
    )
