import sys
from pathlib import Path


sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)


from src.config import (
    SLEEPER_LEAGUE_ID,
)

from src.league_data import (
    LeagueDataLoader,
)

from src.sleeper_client import (
    SleeperClient,
)

from src.historical_market import (
    build_historical_market_model,
    build_position_lookup,
    resolve_historical_player_key,
)


# =========================================================
# LOAD DATA
# =========================================================

loader = LeagueDataLoader(
    "data/league.xlsx"
)


league_data = (
    loader.load()
)


sleeper = (
    SleeperClient()
)


sleeper_players = (
    sleeper.get_players()
)


# =========================================================
# BUILD MODEL
# =========================================================

model = (
    build_historical_market_model(
        historical_sales=(
            league_data
            .historical_sales
        ),
        sleeper_players=(
            sleeper_players
        ),
    )
)


# =========================================================
# YEAR QUALITY
# =========================================================

print()

print(
    "=" * 70
)

print(
    "HISTORICAL MARKET"
)

print(
    "=" * 70
)


print(
    "Eligible years:",
    model.eligible_years,
)


print(
    "Excluded years:",
    model.excluded_years,
)


print()

print(
    "YEAR COUNTS"
)

print(
    "-" * 70
)


for year in sorted(
    model.year_sale_counts
):

    print(
        year,
        "| Sales:",
        model.year_sale_counts[
            year
        ],
        "| Spend: $",
        round(
            model.year_total_spend[
                year
            ],
            2,
        ),
    )


print()

print(
    "Mapped sales:",
    len(
        model.mapped_sales
    ),
)


print(
    "Unmapped sales:",
    model.unmapped_sales_count,
)


# =========================================================
# POSITION MARKET
# =========================================================

print()

print(
    "=" * 70
)

print(
    "POSITION MARKET"
)

print(
    "=" * 70
)


for position in [
    "QB",
    "RB",
    "WR",
    "TE",
    "K",
    "DEF",
]:

    profile = (
        model.position_profiles.get(
            position
        )
    )


    if not profile:

        continue


    print(
        position,
        "| N:",
        profile.sales_count,
        "| Avg: $",
        round(
            profile.average_price,
            2,
        ),
        "| Median: $",
        round(
            profile.median_price,
            2,
        ),
        "| P75: $",
        round(
            profile.p75_price,
            2,
        ),
        "| P90: $",
        round(
            profile.p90_price,
            2,
        ),
        "| Max: $",
        round(
            profile.max_price,
            2,
        ),
    )


# =========================================================
# MANAGER BEHAVIOR
# =========================================================

print()

print(
    "=" * 70
)

print(
    "MANAGER BEHAVIOR"
)

print(
    "=" * 70
)


manager_profiles = list(
    model.manager_profiles.values()
)


manager_profiles.sort(
    key=lambda profile: (
        profile.aggressiveness_index
    ),
    reverse=True,
)


for profile in (
    manager_profiles
):

    position_shares = sorted(
        profile
        .position_spend_share
        .items(),
        key=lambda item: (
            item[1]
        ),
        reverse=True,
    )


    top_position = (
        position_shares[0][0]
        if position_shares
        else "-"
    )


    top_position_share = (
        position_shares[0][1]
        if position_shares
        else 0.0
    )


    print(
        profile.manager_id,
        "| Buys:",
        profile.sales_count,
        "| Avg: $",
        round(
            profile.average_price,
            2,
        ),
        "| Max: $",
        round(
            profile.max_price,
            2,
        ),
        "| Agg:",
        round(
            profile.aggressiveness_index,
            2,
        ),
        "| Star:",
        round(
            profile.star_chase_index,
            2,
        ),
        "| Top Position:",
        top_position,
        (
            f"{top_position_share:.0%}"
        ),
    )

    from src.auction_pool import (
    normalize_player_name,
)

print()
print("=" * 70)
print("UNMAPPED 2025 SALES")
print("=" * 70)


position_lookup = (
    build_position_lookup(
        sleeper_players
    )
)


unmapped = []


for sale in (
    league_data.historical_sales
):

    if sale.year != 2025:
        continue


    key = resolve_historical_player_key(
    sale.player_name
)


    if (
        key
        not in position_lookup
    ):

        unmapped.append(
            sale
        )


unmapped.sort(
    key=lambda sale: (
        sale.price
    ),
    reverse=True,
)


for sale in unmapped:

    print(
        sale.player_name,
        "| $",
        sale.price,
        "| Manager:",
        sale.manager_id
        or sale.manager_raw,
    )