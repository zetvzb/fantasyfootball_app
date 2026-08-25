from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class OpponentTargetProfile:
    manager_id: str
    likely_positions: Tuple[str, ...]
    likely_tiers: Tuple[str, ...]
    cash_strength: float
    need_strength: float
    confidence: float
    reasons: Tuple[str, ...]


def build_opponent_target_profiles(
    *,
    team_need_profiles: Mapping[str, object],
    current_manager_id: str,
    manager_tendency_profiles: Sequence[object] = (),
) -> Tuple[OpponentTargetProfile, ...]:
    """Estimate target archetypes and tiers without predicting exact bids."""

    tendency_index = {
        profile.manager_id: profile for profile in manager_tendency_profiles
    }
    max_cash = max(
        (float(profile.auction_cash) for profile in team_need_profiles.values()),
        default=1.0,
    )
    results = []
    for manager_id, need_profile in team_need_profiles.items():
        if manager_id == current_manager_id:
            continue
        tendency = tendency_index.get(manager_id)
        premiums = dict(getattr(tendency, "position_premiums", ()) or ())
        scored = []
        for position, need in need_profile.need_scores.items():
            premium = float(premiums.get(position, 1.0))
            scored.append((float(need) * (0.75 + 0.25 * premium), position))
        scored.sort(reverse=True)
        positions = tuple(position for score, position in scored[:3] if score > 0.15)
        max_bid = float(need_profile.max_bid)
        tiers = []
        if max_bid >= 40:
            tiers.append("elite")
        if max_bid >= 15:
            tiers.append("starter")
        tiers.append("depth")
        cash_strength = min(1.0, float(need_profile.auction_cash) / max(1.0, max_cash))
        need_strength = scored[0][0] if scored else 0.0
        confidence = min(
            1.0,
            0.45 + 0.30 * need_strength + 0.25 * float(getattr(tendency, "confidence", 0.0)),
        )
        reasons = [
            "Roster gaps point to {0}.".format(
                ", ".join(positions) if positions else "best-player-available depth"
            ),
            "Cash and legal max support {0} tiers.".format(", ".join(tiers)),
        ]
        if tendency is not None:
            reasons.append("Time-decayed manager history adjusts positional preference.")
        results.append(
            OpponentTargetProfile(
                manager_id=manager_id,
                likely_positions=positions,
                likely_tiers=tuple(tiers),
                cash_strength=round(cash_strength, 3),
                need_strength=round(need_strength, 3),
                confidence=round(confidence, 3),
                reasons=tuple(reasons),
            )
        )
    return tuple(sorted(results, key=lambda item: (-item.need_strength, item.manager_id)))
