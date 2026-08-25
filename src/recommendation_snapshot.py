from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class RecommendationSnapshot:
    player_name: str
    current_bid: int
    target_value: int
    soft_cap: int
    hard_cap: int
    decision: str
    alternatives: Tuple[Mapping[str, Any], ...]
    roster_state: Mapping[str, Any]
    budget_state: Mapping[str, Any]
    inflation_state: Mapping[str, Any]
    context_state: Mapping[str, Any]
    reasons: Tuple[str, ...]
    captured_at: Optional[str] = None

    def fingerprint(self) -> str:
        payload = self.to_dict()
        payload.pop("captured_at", None)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "player_name": self.player_name,
            "current_bid": self.current_bid,
            "target_value": self.target_value,
            "soft_cap": self.soft_cap,
            "hard_cap": self.hard_cap,
            "decision": self.decision,
            "alternatives": [dict(value) for value in self.alternatives],
            "roster_state": dict(self.roster_state),
            "budget_state": dict(self.budget_state),
            "inflation_state": dict(self.inflation_state),
            "context_state": dict(self.context_state),
            "reasons": list(self.reasons),
            "captured_at": self.captured_at,
        }


def build_recommendation_snapshot(
    context: Any,
    state: Any,
    current_bid: int,
    target_value: int,
    soft_cap: int,
    hard_cap: int,
    decision: str,
) -> RecommendationSnapshot:
    recommendation = state.recommendation
    live_setup = context.my_live_setup
    need_profile = context.my_need_profile
    context_adjustment = state.context_adjustment
    inflation = context.inflation_v2
    alternatives = tuple(
        {
            "player_name": alternative.player_name,
            "expected_price_low": alternative.expected_price_low,
            "expected_price_high": alternative.expected_price_high,
            "availability_probability": alternative.availability_probability,
        }
        for alternative in state.pass_alternatives
    )
    roster_state = {
        "manager_id": context.ACTIVE_MY_MANAGER_ID,
        "open_roster_spots": getattr(live_setup, "open_roster_spots", None),
        "position_need": getattr(need_profile, "position_need", {}),
    }
    budget_state = {
        "live_cash": getattr(live_setup, "live_cash", None),
        "discretionary_cash": getattr(live_setup, "discretionary_cash", None),
        "legal_max_bid": recommendation.legal_max_bid,
    }
    inflation_state = {
        "room_inflation_index": getattr(inflation, "room_inflation_index", None),
        "position": recommendation.position,
    }
    context_state = {
        "adjustment_pct": getattr(context_adjustment, "adjustment_pct", 0.0),
        "confidence": getattr(context_adjustment, "context_confidence", 0.0),
        "adjusted_ceiling": state.context_adjusted_ceiling,
    }
    return RecommendationSnapshot(
        player_name=recommendation.player_name,
        current_bid=int(current_bid),
        target_value=int(target_value),
        soft_cap=int(soft_cap),
        hard_cap=int(hard_cap),
        decision=str(decision),
        alternatives=alternatives,
        roster_state=roster_state,
        budget_state=budget_state,
        inflation_state=inflation_state,
        context_state=context_state,
        reasons=tuple(str(reason) for reason in recommendation.reasons),
    )
