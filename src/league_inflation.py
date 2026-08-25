from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence, Tuple

from src.auction_pool import normalize_player_name


@dataclass(frozen=True)
class InflationObservation:
    season: int
    position: str
    tier: str
    auction_stage: str
    expected_price: float
    actual_price: float

    @property
    def inflation_index(self) -> float:
        return self.actual_price / self.expected_price if self.expected_price > 0 else 1.0


@dataclass(frozen=True)
class InflationSegment:
    season: Optional[int]
    position: str
    tier: str
    auction_stage: str
    sample_size: int
    expected_spend: float
    actual_spend: float
    inflation_index: float


@dataclass(frozen=True)
class LeagueInflationModelV2:
    overall_inflation_index: float
    observations: Tuple[InflationObservation, ...]
    segments: Tuple[InflationSegment, ...]


@dataclass(frozen=True)
class LiveRoomInflation:
    sales_count: int
    expected_spend: float
    actual_spend: float
    room_inflation_index: float
    by_position: Tuple[InflationSegment, ...]
    unmapped_sales: Tuple[str, ...]


def build_league_inflation_model(
    observations: Sequence[InflationObservation],
) -> LeagueInflationModelV2:
    valid = tuple(item for item in observations if item.expected_price > 0)
    expected = sum(item.expected_price for item in valid)
    actual = sum(item.actual_price for item in valid)
    grouped: Dict[Tuple[int, str, str, str], list] = {}
    for item in valid:
        grouped.setdefault(
            (item.season, item.position, item.tier, item.auction_stage), []
        ).append(item)
    segments = []
    for (season, position, tier, stage), items in sorted(grouped.items()):
        segment_expected = sum(item.expected_price for item in items)
        segment_actual = sum(item.actual_price for item in items)
        segments.append(
            InflationSegment(
                season=season,
                position=position,
                tier=tier,
                auction_stage=stage,
                sample_size=len(items),
                expected_spend=round(segment_expected, 2),
                actual_spend=round(segment_actual, 2),
                inflation_index=round(segment_actual / segment_expected, 3),
            )
        )
    return LeagueInflationModelV2(
        overall_inflation_index=round(actual / expected, 3) if expected else 1.0,
        observations=valid,
        segments=tuple(segments),
    )


def calculate_live_room_inflation(
    *,
    live_sales: Sequence[object],
    expected_values: Mapping[str, object],
) -> LiveRoomInflation:
    observations = []
    unmapped = []
    sale_count = len(live_sales)
    for index, sale in enumerate(live_sales):
        value = expected_values.get(normalize_player_name(sale.player_name))
        expected = getattr(value, "expected_market_value", None)
        if expected is None or float(expected) <= 0:
            unmapped.append(sale.player_name)
            continue
        stage_share = float(index) / max(1, sale_count)
        stage = "early" if stage_share < 0.33 else "middle" if stage_share < 0.67 else "late"
        expected_float = float(expected)
        tier = "elite" if expected_float >= 40 else "starter" if expected_float >= 15 else "depth"
        observations.append(
            InflationObservation(
                season=int(getattr(sale, "season", 0) or 0),
                position=str(getattr(sale, "position", "UNKNOWN") or "UNKNOWN"),
                tier=tier,
                auction_stage=stage,
                expected_price=expected_float,
                actual_price=float(sale.price),
            )
        )
    model = build_league_inflation_model(observations)
    position_groups: Dict[str, list] = {}
    for item in observations:
        position_groups.setdefault(item.position, []).append(item)
    by_position = tuple(
        InflationSegment(
            season=None,
            position=position,
            tier="all",
            auction_stage="live",
            sample_size=len(items),
            expected_spend=round(sum(item.expected_price for item in items), 2),
            actual_spend=round(sum(item.actual_price for item in items), 2),
            inflation_index=round(
                sum(item.actual_price for item in items)
                / sum(item.expected_price for item in items),
                3,
            ),
        )
        for position, items in sorted(position_groups.items())
    )
    return LiveRoomInflation(
        sales_count=len(observations),
        expected_spend=round(sum(item.expected_price for item in observations), 2),
        actual_spend=round(sum(item.actual_price for item in observations), 2),
        room_inflation_index=model.overall_inflation_index,
        by_position=by_position,
        unmapped_sales=tuple(unmapped),
    )
