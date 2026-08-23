import sys
from pathlib import Path


sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)


from src.config import (
    SEASON,
    SLEEPER_LEAGUE_ID,
)

from src.fantasypros_client import (
    FantasyProsClient,
)

from src.sleeper_client import (
    SleeperClient,
)

from src.projections import (
    normalize_fantasypros_projections,
)

from src.valuation import (
    calculate_player_values,
    calculate_replacement_levels,
)


fp = FantasyProsClient()

sleeper = SleeperClient()


league = sleeper.get_league(
    SLEEPER_LEAGUE_ID
)


projection_response = (
    fp.get_preseason_projections(
        season=SEASON
    )
)


projections = (
    normalize_fantasypros_projections(
        response=(
            projection_response
        ),
        scoring_settings=(
            league.get(
                "scoring_settings",
                {},
            )
        ),
    )
)


replacement = (
    calculate_replacement_levels(
        projections
    )
)


values = (
    calculate_player_values(
        projections=projections,
        replacement_levels=(
            replacement
        ),
    )
)


print()
print("=" * 70)
print("REPLACEMENT LEVELS")
print("=" * 70)

print(
    "Flex allocation:",
    replacement.flex_allocations
)

print(
    "Starter demand:",
    replacement.starter_demand
)


for position in [
    "QB",
    "RB",
    "WR",
    "TE",
]:

    print(
        position,
        ":",
        round(
            replacement
            .points_by_position[
                position
            ],
            2,
        ),
    )


print()
print("=" * 70)
print("TOP VORP")
print("=" * 70)


values.sort(
    key=lambda player: (
        player.vorp
    ),
    reverse=True,
)


for player in values[:30]:

    print(
        player.player_name,
        "|",
        player.position,
        "| Pts:",
        round(
            player.projected_points,
            1,
        ),
        "| Replacement:",
        round(
            player.replacement_points,
            1,
        ),
        "| VORP:",
        round(
            player.vorp,
            1,
        ),
    )