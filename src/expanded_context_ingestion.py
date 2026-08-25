from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence, Tuple

from src.auction_pool import normalize_player_name
from src.player_context import ContextDocument, clamp, parse_datetime


class ContextSignalKind(str, Enum):
    INJURY_HISTORY = "injury_history"
    OFF_FIELD = "off_field"
    PRESEASON_HYPE = "preseason_hype"
    SNAP_SHARE = "snap_share"
    TARGET_SHARE = "target_share"
    ROUTE_SHARE = "route_share"
    OFFENSIVE_LINE = "offensive_line"
    COACHING_CHANGE = "coaching_change"
    STRENGTH_OF_SCHEDULE = "strength_of_schedule"
    DEPTH_CHART = "depth_chart"


@dataclass(frozen=True)
class ContextIngestionBatch:
    documents: Tuple[ContextDocument, ...]
    warnings: Tuple[str, ...]


def _signals(kind: ContextSignalKind, direction: float) -> Tuple[float, float, float, float]:
    value = clamp(direction)
    if kind is ContextSignalKind.INJURY_HISTORY:
        return 0.0, 0.0, value, value * 0.35
    if kind is ContextSignalKind.OFF_FIELD:
        return value * 0.35, 0.0, 0.0, value
    if kind is ContextSignalKind.PRESEASON_HYPE:
        return value * 0.65, value * 0.35, 0.0, value * 0.25
    if kind in (
        ContextSignalKind.SNAP_SHARE,
        ContextSignalKind.TARGET_SHARE,
        ContextSignalKind.ROUTE_SHARE,
    ):
        return value * 0.25, value, 0.0, 0.0
    if kind is ContextSignalKind.OFFENSIVE_LINE:
        return value * 0.35, value * 0.65, 0.0, 0.0
    if kind is ContextSignalKind.COACHING_CHANGE:
        return value * 0.70, value * 0.30, 0.0, value * 0.20
    if kind is ContextSignalKind.STRENGTH_OF_SCHEDULE:
        return 0.0, value, 0.0, 0.0
    return value, value * 0.20, 0.0, 0.0


def ingest_structured_context(
    records: Sequence[Mapping[str, Any]],
    *,
    source_name: str = "structured_import",
) -> ContextIngestionBatch:
    """Normalize optional structured football context into stored documents."""

    documents = []
    warnings = []
    for index, record in enumerate(records):
        player_name = str(record.get("player_name") or "").strip()
        try:
            kind = ContextSignalKind(str(record.get("signal_type") or ""))
        except ValueError:
            warnings.append("Row {0}: unknown context signal type.".format(index + 1))
            continue
        if not normalize_player_name(player_name):
            warnings.append("Row {0}: missing player name.".format(index + 1))
            continue
        try:
            direction = clamp(float(record.get("direction", 0.0)))
            confidence = clamp(float(record.get("confidence", 0.75)), 0.0, 1.0)
        except (TypeError, ValueError):
            warnings.append("Row {0}: direction/confidence must be numeric.".format(index + 1))
            continue
        role, usage, injury, dynasty = _signals(kind, direction)
        title = str(record.get("title") or kind.value.replace("_", " ").title())
        content = str(record.get("content") or title)
        source = str(record.get("source_name") or source_name)
        document_id = str(
            record.get("document_id")
            or "structured:{0}:{1}:{2}".format(
                normalize_player_name(player_name).replace(" ", "-"),
                kind.value,
                index,
            )
        )
        documents.append(
            ContextDocument(
                document_id=document_id,
                player_name=player_name,
                position=record.get("position"),
                nfl_team=record.get("nfl_team"),
                source_type=(
                    "injury" if kind is ContextSignalKind.INJURY_HISTORY else
                    "depth_chart" if kind is ContextSignalKind.DEPTH_CHART else
                    "usage" if kind in (
                        ContextSignalKind.SNAP_SHARE,
                        ContextSignalKind.TARGET_SHARE,
                        ContextSignalKind.ROUTE_SHARE,
                        ContextSignalKind.STRENGTH_OF_SCHEDULE,
                    ) else "news"
                ),
                source_name=source,
                title=title,
                content=content,
                published_at=parse_datetime(record.get("published_at")),
                url=record.get("url"),
                confidence=confidence,
                role_signal=role,
                usage_signal=usage,
                injury_signal=injury,
                dynasty_signal=dynasty,
                tags=[kind.value],
                metadata={
                    **dict(record.get("metadata") or {}),
                    "signal_type": kind.value,
                    "direction": direction,
                },
            )
        )
    return ContextIngestionBatch(tuple(documents), tuple(warnings))
