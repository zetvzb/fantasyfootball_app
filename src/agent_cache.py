from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence


def _fingerprint(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def nomination_advice_fingerprint(
    candidates: Sequence[Any],
    user_context: str = "",
) -> str:
    return _fingerprint(
        {
            "context": str(user_context).strip()[:2000],
            "candidates": [
                {
                    "player": item.player_name,
                    "position": item.position,
                    "score": item.nomination_score,
                    "action": item.action,
                    "reason": item.reason,
                    "market": item.expected_market_value,
                    "ceiling": item.do_not_exceed,
                    "target": item.target_manager_id,
                }
                for item in candidates[:5]
            ],
        }
    )


def auction_advice_fingerprint(
    summary: Any,
    bid_state: Any,
    team_setup: Any,
    source_mode: str,
    user_context: str = "",
) -> str:
    recommendation = bid_state.recommendation
    return _fingerprint(
        {
            "player": summary.player_name,
            "current_bid": summary.current_bid,
            "target": summary.target_value,
            "soft_cap": summary.soft_cap,
            "hard_cap": summary.hard_cap,
            "decision": summary.decision,
            "regret": summary.regret_risk,
            "room_threat": summary.room_threat,
            "source_mode": str(source_mode),
            "live_cash": getattr(team_setup, "live_cash", 0),
            "open_spots": getattr(team_setup, "open_roster_spots", 0),
            "discretionary_cash": getattr(team_setup, "discretionary_cash", 0),
            "legal_max": recommendation.legal_max_bid,
            "strategy": recommendation.strategy,
            "reasons": list(recommendation.reasons),
            "alternatives": [
                {
                    "player": item.player_name,
                    "low": item.expected_price_low,
                    "high": item.expected_price_high,
                    "availability": item.availability_probability,
                }
                for item in bid_state.pass_alternatives[:3]
            ],
            "context": str(user_context).strip()[:2000],
        }
    )
