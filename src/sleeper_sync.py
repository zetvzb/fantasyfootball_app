from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.auction_pool import normalize_player_name
from src.live_draft import add_live_sale
from src.sleeper_reconciliation import reconcile_sleeper_sales


# =========================================================
# DATA OBJECTS
# =========================================================

@dataclass
class SleeperAuctionPick:
    pick_no: int
    player_id: str
    player_name: str
    position: str
    manager_id: str
    price: int


@dataclass
class SleeperSyncResult:
    status: str
    message: str

    imported_player: Optional[str] = None
    imported_price: Optional[int] = None
    imported_manager_id: Optional[str] = None

    warnings: List[str] = field(
        default_factory=list
    )


# =========================================================
# HELPERS
# =========================================================

def normalize_position(
    value,
) -> Optional[str]:

    if value is None:
        return None

    value = str(
        value
    ).upper()

    if value in {
        "DST",
        "D/ST",
    }:
        return "DEF"

    if value in {
        "QB",
        "RB",
        "WR",
        "TE",
        "K",
        "DEF",
    }:
        return value

    return None


def parse_price(
    pick: dict,
) -> Optional[int]:
    """
    Sleeper's official API docs do not formally
    document an auction price field.

    Auction draft payloads commonly expose the
    winning amount under metadata.amount.

    We check several possible locations so the
    application fails gracefully if Sleeper changes
    or varies the payload.
    """

    metadata = (
        pick.get(
            "metadata"
        )
        or {}
    )

    settings = (
        pick.get(
            "settings"
        )
        or {}
    )

    candidates = [
        metadata.get(
            "amount"
        ),
        metadata.get(
            "price"
        ),
        metadata.get(
            "bid"
        ),

        pick.get(
            "amount"
        ),
        pick.get(
            "price"
        ),
        pick.get(
            "bid"
        ),

        settings.get(
            "amount"
        )
        if isinstance(
            settings,
            dict,
        )
        else None,

        settings.get(
            "price"
        )
        if isinstance(
            settings,
            dict,
        )
        else None,
    ]


    for value in candidates:

        if value is None:
            continue

        try:

            cleaned = str(
                value
            ).replace(
                "$",
                ""
            ).replace(
                ",",
                ""
            ).strip()

            price = int(
                round(
                    float(
                        cleaned
                    )
                )
            )

            if price >= 1:
                return price

        except (
            TypeError,
            ValueError,
        ):
            continue


    return None


# =========================================================
# MANAGER LOOKUP
# =========================================================

def build_roster_manager_lookup(
    managers,
) -> Dict[
    str,
    str,
]:

    result = {}


    for (
        manager_id,
        identity,
    ) in managers.items():

        roster_id = getattr(
            identity,
            "sleeper_roster_id",
            None,
        )

        if roster_id is None:
            continue

        result[
            str(
                roster_id
            )
        ] = manager_id


    return result


# =========================================================
# STARTING PLAYER LOOKUP
# =========================================================

def build_player_id_lookup(
    starting_pool_players,
):

    result = {}


    for player in starting_pool_players:

        sleeper_id = getattr(
            player,
            "sleeper_id",
            None,
        )

        if sleeper_id is None:
            continue


        result[
            str(
                sleeper_id
            )
        ] = player


    return result


# =========================================================
# PARSE SLEEPER PICKS
# =========================================================

def parse_sleeper_auction_picks(
    draft_picks: List[dict],
    starting_pool_players,
    sleeper_players: dict,
    managers,
) -> Tuple[
    List[
        SleeperAuctionPick
    ],
    List[str],
]:

    roster_manager_lookup = (
        build_roster_manager_lookup(
            managers
        )
    )


    auction_player_lookup = (
        build_player_id_lookup(
            starting_pool_players
        )
    )


    results = []

    warnings = []


    sorted_picks = sorted(
        draft_picks,
        key=lambda pick: (
            int(
                pick.get(
                    "pick_no",
                    999999,
                )
                or 999999
            )
        ),
    )


    for pick in sorted_picks:

        # -------------------------------------------------
        # KEEPERS ARE ALREADY HANDLED BY PRE-DRAFT SETUP
        # -------------------------------------------------

        if pick.get(
            "is_keeper"
        ):

            continue


        player_id = str(
            pick.get(
                "player_id",
                "",
            )
            or ""
        )


        if not player_id:

            continue


        roster_id = pick.get(
            "roster_id"
        )


        if roster_id is None:

            warnings.append(
                f"Sleeper pick "
                f"#{pick.get('pick_no')} "
                f"has no roster_id."
            )

            continue


        manager_id = (
            roster_manager_lookup.get(
                str(
                    roster_id
                )
            )
        )


        if manager_id is None:

            warnings.append(
                f"Sleeper pick "
                f"#{pick.get('pick_no')} "
                f"uses unknown roster "
                f"{roster_id}."
            )

            continue


        price = (
            parse_price(
                pick
            )
        )


        if price is None:

            warnings.append(
                f"Sleeper pick "
                f"#{pick.get('pick_no')} "
                f"does not contain a readable "
                f"auction price."
            )

            continue


        # -------------------------------------------------
        # USE OUR AUCTION POOL'S CANONICAL NAME IF POSSIBLE
        # -------------------------------------------------

        auction_player = (
            auction_player_lookup.get(
                player_id
            )
        )


        if auction_player:

            player_name = (
                auction_player
                .player_name
            )

            position = (
                auction_player
                .position
            )

        else:

            sleeper_player = (
                sleeper_players.get(
                    player_id,
                    {},
                )
            )


            metadata = (
                pick.get(
                    "metadata"
                )
                or {}
            )


            player_name = (
                sleeper_player.get(
                    "full_name"
                )
                or sleeper_player.get(
                    "search_full_name"
                )
            )


            if not player_name:

                first_name = (
                    metadata.get(
                        "first_name"
                    )
                    or ""
                )

                last_name = (
                    metadata.get(
                        "last_name"
                    )
                    or ""
                )

                player_name = (
                    f"{first_name} {last_name}"
                    .strip()
                )


            position = (
                normalize_position(
                    sleeper_player.get(
                        "position"
                    )
                    or metadata.get(
                        "position"
                    )
                )
            )


            if (
                not player_name
                or not position
            ):

                warnings.append(
                    f"Could not resolve Sleeper "
                    f"player {player_id}."
                )

                continue


        results.append(
            SleeperAuctionPick(
                pick_no=int(
                    pick.get(
                        "pick_no",
                        0,
                    )
                    or 0
                ),
                player_id=(
                    player_id
                ),
                player_name=(
                    player_name
                ),
                position=(
                    position
                ),
                manager_id=(
                    manager_id
                ),
                price=(
                    price
                ),
            )
        )


    return (
        results,
        warnings,
    )


# =========================================================
# SYNC NEXT SALE
# =========================================================

def sync_next_sleeper_sale(
    draft_picks,
    starting_team_setups,
    starting_pool_players,
    sleeper_players,
    managers,
    existing_sales,
    recommendation_index,
    draft_store,
) -> SleeperSyncResult:
    """
    Import at most ONE unseen Sleeper sale.

    This is deliberate.

    After importing a sale Streamlit performs a full
    rerun, which recalculates:
      - remaining cash
      - roster needs
      - scarcity
      - market values
      - bidder threats
      - DO NOT EXCEED

    The next Sleeper sale is then imported against
    the newly recalculated state.

    This preserves proper sequential draft learning
    even when the app needs to catch up on several
    Sleeper picks.
    """

    (
        sleeper_sales,
        warnings,
    ) = parse_sleeper_auction_picks(
        draft_picks=(
            draft_picks
        ),
        starting_pool_players=(
            starting_pool_players
        ),
        sleeper_players=(
            sleeper_players
        ),
        managers=(
            managers
        ),
    )


    existing_lookup = {
        normalize_player_name(
            sale.player_name
        ): sale

        for sale
        in existing_sales
    }


    for sleeper_sale in (
        sleeper_sales
    ):

        key = (
            normalize_player_name(
                sleeper_sale.player_name
            )
        )


        existing = (
            existing_lookup.get(
                key
            )
        )


        # =================================================
        # PLAYER ALREADY EXISTS IN OUR LEDGER
        # =================================================

        if existing:

            same_manager = (
                existing.manager_id
                ==
                sleeper_sale.manager_id
            )

            same_price = (
                int(
                    existing.price
                )
                ==
                int(
                    sleeper_sale.price
                )
            )


            if same_manager and same_price and existing.source == "sleeper":

                # Manual entry and Sleeper agree.
                continue


            reconciliation = reconcile_sleeper_sales(
                existing_sales,
                [sleeper_sale],
            )
            draft_store.replace_sales(list(reconciliation.sales))
            change = reconciliation.changes[0]
            return (
                SleeperSyncResult(
                    status="reconciled",
                    message=(
                        f"{change.detail} {sleeper_sale.player_name}: "
                        f"${sleeper_sale.price} to {sleeper_sale.manager_id}."
                    ),
                    warnings=(
                        warnings
                    ),
                )
            )


        # =================================================
        # NEW SLEEPER SALE
        # =================================================

        recommendation = (
            recommendation_index.get(
                key
            )
        )


        modeled_market = None

        do_not_exceed = None


        if recommendation:

            modeled_market = (
                recommendation
                .expected_market_value
            )

            do_not_exceed = (
                recommendation
                .do_not_exceed
            )


        try:

            updated_sales = (
                add_live_sale(
                    starting_team_setups=(
                        starting_team_setups
                    ),
                    existing_sales=(
                        existing_sales
                    ),
                    player_name=(
                        sleeper_sale
                        .player_name
                    ),
                    position=(
                        sleeper_sale
                        .position
                    ),
                    manager_id=(
                        sleeper_sale
                        .manager_id
                    ),
                    price=(
                        sleeper_sale
                        .price
                    ),
                    modeled_market_value=(
                        modeled_market
                    ),
                    do_not_exceed=(
                        do_not_exceed
                    ),
                )
            )


            new_sale = (
                updated_sales[
                    -1
                ]
            )

            new_sale.source = "sleeper"


            draft_store.add_sale(
                new_sale
            )


            return (
                SleeperSyncResult(
                    status="imported",
                    message=(
                        f"Imported "
                        f"{sleeper_sale.player_name} "
                        f"for "
                        f"${sleeper_sale.price}."
                    ),
                    imported_player=(
                        sleeper_sale
                        .player_name
                    ),
                    imported_price=(
                        sleeper_sale
                        .price
                    ),
                    imported_manager_id=(
                        sleeper_sale
                        .manager_id
                    ),
                    warnings=(
                        warnings
                    ),
                )
            )


        except ValueError as error:

            return (
                SleeperSyncResult(
                    status="conflict",
                    message=(
                        f"Could not import "
                        f"{sleeper_sale.player_name}: "
                        f"{error}"
                    ),
                    warnings=(
                        warnings
                    ),
                )
            )


    return (
        SleeperSyncResult(
            status="no_change",
            message=(
                "Sleeper and the local ledger "
                "are currently synchronized."
            ),
            warnings=(
                warnings
            ),
        )
    )
