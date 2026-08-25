from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class FantasyProsDataHealth:
    rankings_count: int
    metadata_count: int
    projections_count: int
    intelligence_count: int
    current_ecr_count: int
    dynasty_ecr_count: int
    scored_projection_count: int
    api_limited: bool

    @property
    def usable(self) -> bool:
        return (
            self.rankings_count > 0
            and self.intelligence_count > 0
            and self.current_ecr_count > 0
            and self.projections_count > 0
            and self.scored_projection_count > 0
        )

    @property
    def summary(self) -> str:
        summary = (
            "{0} rankings ({1} current ECR, {2} dynasty), "
            "{3} metadata, {4} projections ({5} scored)"
        ).format(
            self.rankings_count,
            self.current_ecr_count,
            self.dynasty_ecr_count,
            self.metadata_count,
            self.projections_count,
            self.scored_projection_count,
        )
        if self.api_limited:
            return summary + " • FantasyPros public API tier limited"
        return summary


def validate_fantasypros_data(
    rankings_response: Mapping[str, object],
    players_response: Mapping[str, object],
    projection_response: Mapping[str, object],
    intelligence: Sequence[object],
    projections: Sequence[object],
) -> FantasyProsDataHealth:
    health = FantasyProsDataHealth(
        rankings_count=len(rankings_response.get("players", []) or []),
        metadata_count=len(players_response.get("players", []) or []),
        projections_count=len(projection_response.get("players", []) or []),
        intelligence_count=len(intelligence),
        current_ecr_count=sum(getattr(row, "half_ecr", None) is not None for row in intelligence),
        dynasty_ecr_count=sum(getattr(row, "dynasty_ecr", None) is not None for row in intelligence),
        scored_projection_count=sum(getattr(row, "custom_points", None) is not None for row in projections),
        api_limited=any(
            bool(response.get("public_api_limited", False))
            for response in (rankings_response, players_response, projection_response)
        ),
    )
    if not health.usable:
        raise ValueError("FantasyPros returned no usable rankings/projections: {0}".format(health.summary))
    return health
