from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass(frozen=True)
class LiveCockpitSummary:
    player_name: str
    current_bid: int
    target_value: int
    soft_cap: int
    hard_cap: int
    decision: str
    why: str
    alternatives: Tuple[str, ...]
    regret_risk: str
    room_threat: float


def build_live_cockpit_summary(
    player_name: str,
    current_bid: int,
    target_value: int,
    soft_cap: int,
    hard_cap: int,
    strategy: str,
    reasons: Sequence[str],
    alternatives: Sequence[object],
    regret_risk: str,
    room_threat: float,
) -> LiveCockpitSummary:
    if current_bid > hard_cap:
        decision = "PASS"
    elif current_bid > soft_cap:
        decision = "CAUTION"
    elif current_bid <= target_value:
        decision = "BID"
    else:
        decision = "DISCIPLINED BID"
    return LiveCockpitSummary(
        player_name=player_name,
        current_bid=int(current_bid),
        target_value=int(target_value),
        soft_cap=int(soft_cap),
        hard_cap=int(hard_cap),
        decision=decision,
        why="; ".join(reasons) if reasons else strategy,
        alternatives=tuple(str(item.player_name) for item in alternatives[:3]),
        regret_risk=str(regret_risk),
        room_threat=float(room_threat),
    )
