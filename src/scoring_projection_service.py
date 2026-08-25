from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from src.projections import PlayerProjection, normalize_fantasypros_projections
from src.valuation import (
    PlayerValue,
    ReplacementLevels,
    calculate_player_values,
    calculate_replacement_levels,
)


@dataclass(frozen=True)
class LeagueScoringProjectionResult:
    projections: Tuple[PlayerProjection, ...]
    replacement_levels: ReplacementLevels
    player_values: Tuple[PlayerValue, ...]
    exact_projection_count: int
    fallback_projection_count: int


def build_league_scoring_projection(
    *,
    projection_response: dict,
    scoring_settings: Dict[str, float],
    num_teams: int,
) -> LeagueScoringProjectionResult:
    """Run raw stats through league scoring and replacement-level value."""

    projections = normalize_fantasypros_projections(
        response=projection_response,
        scoring_settings=scoring_settings,
    )
    replacement_levels = calculate_replacement_levels(
        projections,
        num_teams=num_teams,
    )
    player_values = calculate_player_values(
        projections=projections,
        replacement_levels=replacement_levels,
    )
    return LeagueScoringProjectionResult(
        projections=tuple(projections),
        replacement_levels=replacement_levels,
        player_values=tuple(player_values),
        exact_projection_count=sum(
            1 for projection in projections if projection.custom_scoring_exact
        ),
        fallback_projection_count=sum(
            1 for projection in projections if not projection.custom_scoring_exact
        ),
    )
