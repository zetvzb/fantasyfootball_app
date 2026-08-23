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
    build_projection_index,
    normalize_fantasypros_projections,
)

from src.valuation import (
    calculate_player_values,
    calculate_replacement_levels,
)

from src.fantasypros_intelligence import (
    build_intelligence_index,
    normalize_fantasypros_intelligence,
)


fp = FantasyProsClient()

sleeper = SleeperClient()


# =========================================================
# SLEEPER
# =========================================================

league = sleeper.get_league(
    SLEEPER_LEAGUE_ID
)


# =========================================================
# FANTASYPROS INTELLIGENCE
# =========================================================

rankings_response = (
    fp.get_rankings(
        season=SEASON
    )
)


players_response = (
    fp.get_players_with_ecr()
)


intelligence = (
    normalize_fantasypros_intelligence(
        rankings_response=(
            rankings_response
        ),
        players_response=(
            players_response
        ),
    )
)


intelligence_index = (
    build_intelligence_index(
        intelligence
    )
)


# =========================================================
# PROJECTIONS
# =========================================================

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


projection_index = (
    build_projection_index(
        projections
    )
)


# =========================================================
# VORP
# =========================================================

replacement_levels = (
    calculate_replacement_levels(
        projections
    )
)


player_values = (
    calculate_player_values(
        projections=projections,
        replacement_levels=(
            replacement_levels
        ),
    )
)


print()
print(
    "Projection players:",
    len(projections),
)

print(
    "FantasyPros intelligence:",
    len(intelligence),
)

print()
print(
    "Auction-value module ready."
)

print(
    "Next test happens through Streamlit "
    "because it needs the selected keepers "
    "and actual team_setups."
)