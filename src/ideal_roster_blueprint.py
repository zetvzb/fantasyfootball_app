from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass(frozen=True)
class BlueprintSlot:
    slot: str
    position: str
    expected_price: int
    preferred_player: str
    alternatives: Tuple[str, ...]


@dataclass(frozen=True)
class IdealRosterBlueprint:
    feasible: bool
    planned_spend: int
    cash_buffer: int
    slots: Tuple[BlueprintSlot, ...]


def build_ideal_roster_blueprint(
    optimized_plan: object,
    candidates: Sequence[object],
    alternative_limit: int = 3,
) -> IdealRosterBlueprint:
    if optimized_plan is None or not bool(getattr(optimized_plan, "feasible", False)):
        return IdealRosterBlueprint(False, 0, 0, ())
    slots = []
    for entry in getattr(optimized_plan, "entries", ()): 
        alternatives = sorted(
            (
                candidate for candidate in candidates
                if str(getattr(candidate, "position", "")) == str(entry.position)
                and str(getattr(candidate, "player_name", "")) != str(entry.player_name)
                and int(getattr(candidate, "expected_cost", 1)) <= max(1, int(entry.planned_cost * 1.15))
            ),
            key=lambda candidate: float(getattr(candidate, "utility", 0.0)),
            reverse=True,
        )[:alternative_limit]
        slots.append(
            BlueprintSlot(
                slot=str(entry.slot),
                position=str(entry.position),
                expected_price=int(entry.planned_cost),
                preferred_player=str(entry.player_name),
                alternatives=tuple(str(candidate.player_name) for candidate in alternatives),
            )
        )
    return IdealRosterBlueprint(
        feasible=True,
        planned_spend=int(getattr(optimized_plan, "planned_spend", 0)),
        cash_buffer=int(getattr(optimized_plan, "cash_after_plan", 0)),
        slots=tuple(slots),
    )
