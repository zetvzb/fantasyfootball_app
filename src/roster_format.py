"""Small helpers for reading league roster format."""

from __future__ import annotations

from typing import Iterable, Optional

_SUPERFLEX_SLOTS = {"SUPER_FLEX", "SUPERFLEX", "SFLEX", "OP", "Q/W/R/T", "QB/RB/WR/TE"}


def qb_starter_slots(starting_lineup: Optional[Iterable[str]]) -> int:
    """Number of lineup slots a QB can realistically fill each week.

    Counts dedicated QB slots plus any superflex/OP slot.
    """

    if not starting_lineup:
        return 1
    slots = [str(slot).upper().strip() for slot in starting_lineup]
    dedicated = sum(1 for slot in slots if slot == "QB")
    superflex = sum(1 for slot in slots if slot in _SUPERFLEX_SLOTS)
    return dedicated + superflex


def is_superflex(starting_lineup: Optional[Iterable[str]]) -> bool:
    """True when a team can start two or more QBs (superflex / 2-QB)."""

    return qb_starter_slots(starting_lineup) >= 2
