from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class LivePriceThresholds:
    target_value: int
    soft_cap: int
    hard_cap: int
    explanation: str


class CurrentBidZone(str, Enum):
    VALUE = "VALUE"
    TARGET = "TARGET"
    SOFT_CAP = "SOFT CAP"
    HARD_CAP = "HARD CAP"
    PASS = "PASS"


@dataclass(frozen=True)
class CurrentBidDecision:
    current_bid: int
    zone: CurrentBidZone
    should_bid: bool
    dollars_to_hard_cap: int
    message: str


def evaluate_current_bid(
    current_bid: int,
    thresholds: LivePriceThresholds,
) -> CurrentBidDecision:
    bid = max(1, int(current_bid))
    if bid < thresholds.target_value:
        zone = CurrentBidZone.VALUE
        message = "Below target value; bidding retains the planned value edge."
    elif bid < thresholds.soft_cap:
        zone = CurrentBidZone.TARGET
        message = "Inside the target range; continue only while the roster fit holds."
    elif bid < thresholds.hard_cap:
        zone = CurrentBidZone.SOFT_CAP
        message = "Above the soft cap; only a deliberate exception supports another bid."
    elif bid == thresholds.hard_cap:
        zone = CurrentBidZone.HARD_CAP
        message = "At the hard cap. Do not bid again."
    else:
        zone = CurrentBidZone.PASS
        message = "Above the hard cap. Pass."
    return CurrentBidDecision(
        current_bid=bid,
        zone=zone,
        should_bid=bid < thresholds.hard_cap,
        dollars_to_hard_cap=max(0, thresholds.hard_cap - bid),
        message=message,
    )


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
