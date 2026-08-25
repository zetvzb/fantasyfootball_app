from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Sequence, Tuple

from src.auction_pool import normalize_player_name


@dataclass(frozen=True)
class TierTarget:
    player_name: str
    position: str
    tier: int
    expected_price: int
    utility: float


@dataclass(frozen=True)
class TargetTierBoard:
    by_position: Mapping[str, Tuple[TierTarget, ...]]

    def fallback_chain(self, player_name: str, limit: int = 3) -> Tuple[TierTarget, ...]:
        key = normalize_player_name(player_name)
        for targets in self.by_position.values():
            for index, target in enumerate(targets):
                if normalize_player_name(target.player_name) == key:
                    return tuple(targets[index + 1:index + 1 + limit])
        return ()


def build_target_tier_board(candidates: Sequence[object]) -> TargetTierBoard:
    grouped: Dict[str, list] = {}
    for candidate in candidates:
        position = str(getattr(candidate, "position", "UNKNOWN")).upper()
        grouped.setdefault(position, []).append(candidate)
    board = {}
    for position, values in grouped.items():
        values.sort(key=lambda item: float(getattr(item, "utility", 0.0)), reverse=True)
        top = max(1.0, float(getattr(values[0], "utility", 0.0)))
        targets = []
        tier = 1
        previous = top
        for candidate in values:
            utility = float(getattr(candidate, "utility", 0.0))
            if targets and previous - utility > top * 0.15:
                tier += 1
            targets.append(
                TierTarget(
                    player_name=str(candidate.player_name),
                    position=position,
                    tier=tier,
                    expected_price=int(getattr(candidate, "expected_cost", 1)),
                    utility=utility,
                )
            )
            previous = utility
        board[position] = tuple(targets)
    return TargetTierBoard(by_position=board)
