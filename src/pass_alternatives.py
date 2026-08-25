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
    availability_probability: float
    availability_label: str


def find_pass_alternatives(
    *,
    player_name: str,
    position: str,
    player_vorp: float,
    candidates: Sequence[object],
    limit: int = 4,
    auction_stage: float = 0.0,
    threat_score: float = 0.0,
    remaining_cash: float = 0.0,
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
        affordability = min(1.0, float(remaining_cash) / market) if remaining_cash > 0 else 0.5
        probability = max(
            0.05,
            min(
                0.95,
                0.82
                - 0.30 * max(0.0, min(1.0, float(auction_stage)))
                - 0.25 * max(0.0, min(1.0, float(threat_score) / 100.0))
                + 0.13 * affordability,
            ),
        )
        label = "HIGH" if probability >= 0.67 else "MEDIUM" if probability >= 0.34 else "LOW"
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
                availability_probability=round(probability, 3),
                availability_label=label,
            )
        )
    alternatives.sort(
        key=lambda item: (-item.comparability, item.expected_price_high, item.player_name)
    )
    return tuple(alternatives[:limit])
