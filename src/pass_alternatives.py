from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from src.auction_pool import normalize_player_name


@dataclass(frozen=True)
class PassAlternative:
    player_name: str
    position: str
    expected_price_low: int
    expected_price_high: int
    vorp: float
    comparability: float
    rationale: str


def find_pass_alternatives(
    *,
    player_name: str,
    position: str,
    player_vorp: float,
    candidates: Sequence[object],
    limit: int = 4,
) -> Tuple[PassAlternative, ...]:
    alternatives = []
    target_key = normalize_player_name(player_name)
    denominator = max(1.0, abs(float(player_vorp)))
    for candidate in candidates:
        if normalize_player_name(candidate.player_name) == target_key:
            continue
        if str(candidate.position) != str(position):
            continue
        comparability = max(0.0, 1.0 - abs(float(candidate.vorp) - player_vorp) / denominator)
        if comparability < 0.45:
            continue
        market = max(1.0, float(candidate.expected_market_value))
        alternatives.append(
            PassAlternative(
                player_name=candidate.player_name,
                position=position,
                expected_price_low=max(1, int(round(market * 0.85))),
                expected_price_high=max(1, int(round(market * 1.15))),
                vorp=round(float(candidate.vorp), 2),
                comparability=round(comparability, 3),
                rationale="Comparable {0} production at an expected ${1}-${2}.".format(
                    position,
                    max(1, int(round(market * 0.85))),
                    max(1, int(round(market * 1.15))),
                ),
            )
        )
    alternatives.sort(
        key=lambda item: (-item.comparability, item.expected_price_high, item.player_name)
    )
    return tuple(alternatives[:limit])
