from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LivePriceThresholds:
    target_value: int
    soft_cap: int
    hard_cap: int
    explanation: str


def build_live_price_thresholds(
    *,
    expected_market_value: float,
    baseline_value: float,
    deterministic_ceiling: int,
    legal_max_bid: int,
) -> LivePriceThresholds:
    hard = max(1, min(int(deterministic_ceiling), int(legal_max_bid)))
    desired = int(round((float(expected_market_value) + float(baseline_value)) / 2.0))
    target = max(1, min(desired, hard))
    soft = max(target, min(hard, int(round(target + 0.65 * (hard - target)))))
    return LivePriceThresholds(
        target_value=target,
        soft_cap=soft,
        hard_cap=hard,
        explanation=(
            "Target blends expected market and model value; soft cap preserves "
            "most of the value edge; hard cap is the deterministic legal ceiling."
        ),
    )


def constrain_thresholds(
    thresholds: LivePriceThresholds,
    final_hard_cap: int,
) -> LivePriceThresholds:
    hard = max(1, int(final_hard_cap))
    target = min(thresholds.target_value, hard)
    soft = min(max(target, thresholds.soft_cap), hard)
    return LivePriceThresholds(target, soft, hard, thresholds.explanation)
