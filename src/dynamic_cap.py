from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class DynamicCapInput:
    base_cap: int
    legal_max_bid: int
    need_score: float
    scarcity_score: float
    has_comparable_alternative: bool
    cash_flexibility: float
    auction_stage: float
    room_inflation_index: float
    current_weight: float
    future_weight: float
    future_value_score: float
    context_adjustment_pct: float


@dataclass(frozen=True)
class CapAdjustmentComponent:
    factor: str
    adjustment_pct: float
    explanation: str


@dataclass(frozen=True)
class DynamicCapResult:
    base_cap: int
    adjusted_cap: int
    total_adjustment_pct: float
    components: Tuple[CapAdjustmentComponent, ...]


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def adjust_dynamic_cap(inputs: DynamicCapInput) -> DynamicCapResult:
    components = []
    need = 0.06 * (_clamp(inputs.need_score) - 0.5)
    scarcity = 0.06 * (_clamp(inputs.scarcity_score) - 0.5)
    alternatives = -0.025 if inputs.has_comparable_alternative else 0.025
    cash = 0.03 * (_clamp(inputs.cash_flexibility) - 0.5)
    stage = _clamp(inputs.auction_stage)
    stage_scarcity = 0.035 * (stage - 0.5) * (_clamp(inputs.scarcity_score) - 0.25)
    inflation = max(-0.03, min(0.03, (float(inputs.room_inflation_index) - 1.0) * 0.12))
    future = 0.03 * (_clamp(inputs.future_value_score) - 0.5) * _clamp(inputs.future_weight)
    values = (
        ("roster_need", need, "Roster need adjusts urgency."),
        ("scarcity", scarcity, "Tier scarcity adjusts replacement risk."),
        ("alternatives", alternatives, "Comparable alternatives lower the cap."),
        ("cash", cash, "Cash flexibility is reserve-aware."),
        ("auction_stage", stage_scarcity, "Late-stage scarcity can increase urgency."),
        ("room_inflation", inflation, "Observed room inflation adjusts price expectations."),
        ("strategy_future", future, "Strategy-weighted future value changes optionality."),
        (
            "context",
            float(inputs.context_adjustment_pct),
            "Context is already reflected in the starting cap.",
        ),
    )
    for factor, value, explanation in values:
        components.append(
            CapAdjustmentComponent(factor, round(value, 4), explanation)
        )
    # Context is already in base_cap and is reported, not double-applied.
    total = max(-0.12, min(0.12, sum(value for _, value, _ in values[:-1])))
    adjusted = max(
        1,
        min(
            int(inputs.legal_max_bid),
            int(round(float(inputs.base_cap) * (1.0 + total))),
        ),
    )
    return DynamicCapResult(
        base_cap=int(inputs.base_cap),
        adjusted_cap=adjusted,
        total_adjustment_pct=round(total, 4),
        components=tuple(components),
    )
