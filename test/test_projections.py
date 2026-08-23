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


fp_client = FantasyProsClient()

sleeper_client = SleeperClient()


league = sleeper_client.get_league(
    SLEEPER_LEAGUE_ID
)


scoring_settings = league.get(
    "scoring_settings",
    {},
)


response = (
    fp_client.get_preseason_projections(
        season=SEASON
    )
)


projections = (
    normalize_fantasypros_projections(
        response=response,
        scoring_settings=(
            scoring_settings
        ),
    )
)


print()
print("=" * 70)
print("PROJECTIONS")
print("=" * 70)

print(
    "FantasyPros returned:",
    len(
        response.get(
            "players",
            []
        )
    )
)

print(
    "Normalized:",
    len(
        projections
    )
)


print()
print("TOP 25 OFFENSIVE PROJECTIONS")
print("-" * 70)


offense = [
    player
    for player
    in projections
    if (
        player.position
        in {
            "QB",
            "RB",
            "WR",
            "TE",
        }
        and
        player.custom_points
        is not None
    )
]


offense.sort(
    key=lambda player: (
        player.custom_points
    ),
    reverse=True,
)


for player in offense[:25]:

    print(
        player.player_name,
        "|",
        player.position,
        "| Custom:",
        round(
            player.custom_points,
            2,
        ),
        "| FP Half:",
        player.fantasypros_half_points,
        "| Exact:",
        player.custom_scoring_exact,
    )