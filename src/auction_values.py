from dataclasses import dataclass
from typing import Dict, List, Optional

from src.auction_pool import (
    normalize_player_name,
)

from src.league_config import (
    MINIMUM_AUCTION_BID,
)


# =========================================================
# MODEL SETTINGS
# =========================================================

CURRENT_WEIGHT = 0.60
FUTURE_WEIGHT = 0.40

# A player just outside the expected-drafted pool is not worth the minimum
# bid. Keeper leagues routinely spend real money on upside backs and
# post-injury veterans who fall below a pure ECR cut. Give them a discounted
# read off their VORP -- anchored to the weakest player who did make the
# pool -- so the market model and nomination engine stop treating half the
# board as free.
OUT_OF_POOL_VALUE_FRACTION = 0.55


# =========================================================
# OUTPUT OBJECT
# =========================================================

@dataclass
class AuctionValue:

    player_name: str

    position: str

    projected_points: Optional[float]

    replacement_points: Optional[float]

    vorp: float

    dynasty_rank: Optional[float]

    current_share: float

    future_share: float

    blended_share: float

    baseline_value: float

    expected_to_be_drafted: bool


# =========================================================
# HELPERS
# =========================================================

def safe_float(
    value,
    default=0.0,
):

    if value is None:
        return default

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


# =========================================================
# BUILD EXPECTED DRAFT POOL
# =========================================================

def select_expected_draft_pool(
    available_players,
    fantasypros_index,
    total_open_spots: int,
    vorp_lookup=None,
):
    """
    Select the players most likely to occupy the
    remaining auction roster spots.

    Primary signal is Half-PPR ECR. Players FantasyPros has no ECR for
    (a thin or rate-limited response during a live draft, or simply an
    off-radar name) fall back to VORP order instead of the arbitrary
    order they arrive in -- otherwise a degraded FantasyPros pull
    silently pushes real contributors out of the pool and collapses
    their value to the minimum bid.
    """

    vorp_lookup = vorp_lookup or {}

    ranked = []

    unranked = []


    for player in available_players:

        key = normalize_player_name(
            player.player_name
        )

        fp = fantasypros_index.get(
            key
        )


        if (
            fp
            and
            fp.half_ecr is not None
        ):

            ranked.append(
                (
                    float(
                        fp.half_ecr
                    ),
                    player,
                )
            )

        else:

            player_value = vorp_lookup.get(key)
            unranked.append(
                (
                    -max(0.0, safe_float(getattr(player_value, "vorp", 0.0))),
                    player,
                )
            )


    ranked.sort(
        key=lambda item: (
            item[0]
        )
    )

    unranked.sort(
        key=lambda item: (
            item[0]
        )
    )


    ordered = [
        player
        for _, player
        in ranked
    ]


    ordered.extend(
        player
        for _, player
        in unranked
    )


    return ordered[
        :total_open_spots
    ]


# =========================================================
# AUCTION VALUE MODEL
# =========================================================

def calculate_auction_values(
    available_players,
    team_setups,
    player_values,
    projection_index,
    fantasypros_index,
) -> List[AuctionValue]:

    # -----------------------------------------------------
    # ACTUAL AUCTION ECONOMY
    # -----------------------------------------------------

    total_auction_cash = sum(
        setup.auction_cash
        for setup
        in team_setups.values()
    )


    total_open_spots = sum(
        setup.open_roster_spots
        for setup
        in team_setups.values()
    )


    reserve_dollars = sum(
        getattr(
            setup,
            "required_reserve",
            setup.open_roster_spots * MINIMUM_AUCTION_BID,
        )
        for setup in team_setups.values()
    )

    minimum_bid = min(
        (
            int(getattr(setup, "minimum_auction_bid", MINIMUM_AUCTION_BID))
            for setup in team_setups.values()
        ),
        default=MINIMUM_AUCTION_BID,
    )


    discretionary_dollars = max(
        0,
        total_auction_cash
        - reserve_dollars,
    )


    # -----------------------------------------------------
    # VORP LOOKUP
    # -----------------------------------------------------

    vorp_lookup = {
        normalize_player_name(
            player.player_name
        ): player
        for player
        in player_values
    }


    # -----------------------------------------------------
    # EXPECTED PLAYERS ACTUALLY DRAFTED
    # -----------------------------------------------------

    expected_draft_pool = (
        select_expected_draft_pool(
            available_players=(
                available_players
            ),
            fantasypros_index=(
                fantasypros_index
            ),
            total_open_spots=(
                total_open_spots
            ),
            vorp_lookup=(
                vorp_lookup
            ),
        )
    )


    expected_names = {
        normalize_player_name(
            player.player_name
        )
        for player
        in expected_draft_pool
    }


    # -----------------------------------------------------
    # RAW CURRENT / FUTURE SCORES
    # -----------------------------------------------------

    current_raw: Dict[
        str,
        float,
    ] = {}


    future_raw: Dict[
        str,
        float,
    ] = {}


    for player in expected_draft_pool:

        key = normalize_player_name(
            player.player_name
        )


        # CURRENT YEAR
        # -----------------------------------------------

        player_value = (
            vorp_lookup.get(
                key
            )
        )


        if player_value:

            current_raw[
                key
            ] = max(
                0.0,
                safe_float(
                    player_value.vorp
                ),
            )

        else:

            current_raw[
                key
            ] = 0.0


        # DYNASTY
        # -----------------------------------------------

        fp = fantasypros_index.get(
            key
        )


        dynasty_rank = None


        if fp:

            dynasty_rank = (
                fp.dynasty_ecr
            )


        if (
            dynasty_rank is None
            or
            player.position
            in {
                "K",
                "DEF",
            }
        ):

            future_raw[
                key
            ] = 0.0

        else:

            # Convert dynasty rank into a 0-1
            # value inside the size of this
            # league's remaining draft pool.

            percentile = max(
                0.0,
                (
                    total_open_spots
                    + 1
                    - float(
                        dynasty_rank
                    )
                )
                / max(
                    1,
                    total_open_spots,
                ),
            )


            # Square it to give more separation
            # to true elite dynasty assets.

            future_raw[
                key
            ] = (
                percentile
                ** 2
            )


    # -----------------------------------------------------
    # NORMALIZE BOTH SIGNALS
    # -----------------------------------------------------

    total_current = sum(
        current_raw.values()
    )


    total_future = sum(
        future_raw.values()
    )


    current_share = {}


    future_share = {}


    for key in expected_names:

        if total_current > 0:

            current_share[
                key
            ] = (
                current_raw.get(
                    key,
                    0.0,
                )
                / total_current
            )

        else:

            current_share[
                key
            ] = 0.0


        if total_future > 0:

            future_share[
                key
            ] = (
                future_raw.get(
                    key,
                    0.0,
                )
                / total_future
            )

        else:

            future_share[
                key
            ] = 0.0


    # -----------------------------------------------------
    # OUT-OF-POOL ANCHORS
    #
    # The weakest player who still made the expected pool sets the
    # reference point for everyone just below the cut: their spend
    # premium and their VORP. Out-of-pool players are priced as a
    # discounted fraction of that floor, scaled by their own VORP.
    # -----------------------------------------------------

    def _low_percentile(values, fraction=0.15):
        """A robust 'weak end of the pool' anchor -- the single minimum is
        too noisy (and often a sub-dollar rounding artifact)."""

        positive = sorted(value for value in values if value > 0)
        if not positive:
            return 0.0
        index = min(len(positive) - 1, int(len(positive) * fraction))
        return positive[index]

    expected_premiums = [
        discretionary_dollars
        * (
            CURRENT_WEIGHT * current_share.get(key, 0.0)
            + FUTURE_WEIGHT * future_share.get(key, 0.0)
        )
        for key in expected_names
    ]

    pool_floor_premium = _low_percentile(expected_premiums)

    pool_reference_vorp = _low_percentile(
        [
            max(
                0.0,
                safe_float(getattr(vorp_lookup.get(key), "vorp", 0.0)),
            )
            for key in expected_names
        ]
    )


    # -----------------------------------------------------
    # CREATE VALUES FOR EVERY AVAILABLE PLAYER
    # -----------------------------------------------------

    results = []


    for player in available_players:

        key = normalize_player_name(
            player.player_name
        )


        expected = (
            key
            in expected_names
        )


        projection = (
            projection_index.get(
                key
            )
        )


        value_data = (
            vorp_lookup.get(
                key
            )
        )


        fp = (
            fantasypros_index.get(
                key
            )
        )


        current = (
            current_share.get(
                key,
                0.0,
            )
        )


        future = (
            future_share.get(
                key,
                0.0,
            )
        )


        blended = (
            CURRENT_WEIGHT
            * current
            +
            FUTURE_WEIGHT
            * future
        )


        if expected:

            baseline_value = (
                minimum_bid
                +
                discretionary_dollars
                * blended
            )

        else:

            player_vorp = max(
                0.0,
                safe_float(
                    getattr(value_data, "vorp", 0.0)
                ),
            )

            if (
                player_vorp > 0
                and pool_reference_vorp > 0
                and pool_floor_premium > 0
            ):

                vorp_ratio = min(
                    1.0,
                    player_vorp / pool_reference_vorp,
                )

                baseline_value = (
                    minimum_bid
                    + OUT_OF_POOL_VALUE_FRACTION
                    * pool_floor_premium
                    * vorp_ratio
                )

            else:

                baseline_value = float(
                    minimum_bid
                )


        results.append(
            AuctionValue(
                player_name=(
                    player.player_name
                ),
                position=(
                    player.position
                ),
                projected_points=(
                    projection.custom_points
                    if projection
                    else None
                ),
                replacement_points=(
                    value_data
                    .replacement_points
                    if value_data
                    else None
                ),
                vorp=(
                    value_data.vorp
                    if value_data
                    else 0.0
                ),
                dynasty_rank=(
                    fp.dynasty_ecr
                    if fp
                    else None
                ),
                current_share=(
                    current
                ),
                future_share=(
                    future
                ),
                blended_share=(
                    blended
                ),
                baseline_value=(
                    baseline_value
                ),
                expected_to_be_drafted=(
                    expected
                ),
            )
        )


    return results
