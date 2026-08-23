from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from src.auction_pool import normalize_player_name
from src.league_config import MINIMUM_AUCTION_BID


# =========================================================
# DATA OBJECTS
# =========================================================

@dataclass
class LiveRosterPlayer:
    player_name: str
    position: str
    cost: int


@dataclass
class LiveAuctionSale:
    sale_number: int
    player_name: str
    position: str
    manager_id: str
    price: int
    modeled_market_value: Optional[float] = None
    do_not_exceed: Optional[int] = None


@dataclass
class LiveTeamDraftSetup:
    manager_id: str
    pre_keeper_budget: int

    original_keepers: list
    college_promotions: List[str]

    starting_auction_cash: int
    starting_open_roster_spots: int

    auction_cash: int
    open_roster_spots: int

    auction_players: List[LiveRosterPlayer]

    @property
    def keepers(self):
        """
        bidder_threat.py already counts setup.keepers.

        Returning original keepers + live auction purchases
        lets the need engine automatically account for
        players purchased during the auction.
        """

        return (
            list(self.original_keepers)
            +
            list(self.auction_players)
        )

    @property
    def max_bid(self):

        if self.open_roster_spots <= 0:
            return 0

        reserve_needed = (
            max(
                0,
                self.open_roster_spots - 1,
            )
            *
            MINIMUM_AUCTION_BID
        )

        return max(
            0,
            self.auction_cash
            -
            reserve_needed,
        )

    @property
    def purchased_count(self):

        return len(
            self.auction_players
        )


# =========================================================
# SERIALIZATION
# =========================================================

def sale_to_dict(
    sale: LiveAuctionSale,
):

    return asdict(
        sale
    )


def sale_from_dict(
    value: dict,
):

    return LiveAuctionSale(
        sale_number=int(
            value.get(
                "sale_number",
                0,
            )
        ),
        player_name=str(
            value.get(
                "player_name",
                ""
            )
        ),
        position=str(
            value.get(
                "position",
                ""
            )
        ),
        manager_id=str(
            value.get(
                "manager_id",
                ""
            )
        ),
        price=int(
            value.get(
                "price",
                0,
            )
        ),
        modeled_market_value=(
            value.get(
                "modeled_market_value"
            )
        ),
        do_not_exceed=(
            value.get(
                "do_not_exceed"
            )
        ),
    )


# =========================================================
# BUILD LIVE STATE
# =========================================================

def build_live_team_setups(
    starting_team_setups,
    sales: List[LiveAuctionSale],
) -> Dict[
    str,
    LiveTeamDraftSetup,
]:

    result = {}


    for (
        manager_id,
        setup,
    ) in starting_team_setups.items():

        result[
            manager_id
        ] = (
            LiveTeamDraftSetup(
                manager_id=(
                    manager_id
                ),
                pre_keeper_budget=(
                    int(
                        setup.pre_keeper_budget
                    )
                ),
                original_keepers=(
                    list(
                        getattr(
                            setup,
                            "keepers",
                            [],
                        )
                        or []
                    )
                ),
                college_promotions=(
                    list(
                        getattr(
                            setup,
                            "college_promotions",
                            [],
                        )
                        or []
                    )
                ),
                starting_auction_cash=(
                    int(
                        setup.auction_cash
                    )
                ),
                starting_open_roster_spots=(
                    int(
                        setup.open_roster_spots
                    )
                ),
                auction_cash=(
                    int(
                        setup.auction_cash
                    )
                ),
                open_roster_spots=(
                    int(
                        setup.open_roster_spots
                    )
                ),
                auction_players=[],
            )
        )


    seen_players = set()


    for sale in sorted(
        sales,
        key=lambda item: (
            item.sale_number
        ),
    ):

        key = (
            normalize_player_name(
                sale.player_name
            )
        )


        if key in seen_players:

            raise ValueError(
                f"{sale.player_name} appears "
                f"more than once in the live ledger."
            )


        if (
            sale.manager_id
            not in result
        ):

            raise ValueError(
                f"Unknown manager in sale ledger: "
                f"{sale.manager_id}"
            )


        team = (
            result[
                sale.manager_id
            ]
        )


        if team.open_roster_spots <= 0:

            raise ValueError(
                f"{sale.manager_id} has no "
                f"open roster spots."
            )


        if sale.price < MINIMUM_AUCTION_BID:

            raise ValueError(
                f"Sale price must be at least "
                f"${MINIMUM_AUCTION_BID}."
            )


        if sale.price > team.max_bid:

            raise ValueError(
                f"{sale.player_name} sold for "
                f"${sale.price}, but "
                f"{sale.manager_id}'s legal max "
                f"was ${team.max_bid}."
            )


        team.auction_cash -= (
            sale.price
        )

        team.open_roster_spots -= 1


        team.auction_players.append(
            LiveRosterPlayer(
                player_name=(
                    sale.player_name
                ),
                position=(
                    sale.position
                ),
                cost=(
                    sale.price
                ),
            )
        )


        seen_players.add(
            key
        )


    return result


# =========================================================
# AVAILABLE PLAYER FILTER
# =========================================================

def filter_sold_players(
    available_players,
    sales: List[
        LiveAuctionSale
    ],
):

    sold_keys = {
        normalize_player_name(
            sale.player_name
        )

        for sale
        in sales
    }


    return [
        player

        for player
        in available_players

        if (
            normalize_player_name(
                player.player_name
            )
            not in sold_keys
        )
    ]


# =========================================================
# RECORD SALE
# =========================================================

def add_live_sale(
    starting_team_setups,
    existing_sales: List[
        LiveAuctionSale
    ],
    player_name: str,
    position: str,
    manager_id: str,
    price: int,
    modeled_market_value=None,
    do_not_exceed=None,
):

    current_state = (
        build_live_team_setups(
            starting_team_setups=(
                starting_team_setups
            ),
            sales=(
                existing_sales
            ),
        )
    )


    if (
        manager_id
        not in current_state
    ):

        raise ValueError(
            "Unknown winning manager."
        )


    player_key = (
        normalize_player_name(
            player_name
        )
    )


    for sale in existing_sales:

        if (
            normalize_player_name(
                sale.player_name
            )
            ==
            player_key
        ):

            raise ValueError(
                f"{player_name} has already been sold."
            )


    team = (
        current_state[
            manager_id
        ]
    )


    price = int(
        price
    )


    if price < MINIMUM_AUCTION_BID:

        raise ValueError(
            f"Minimum bid is "
            f"${MINIMUM_AUCTION_BID}."
        )


    if team.open_roster_spots <= 0:

        raise ValueError(
            "That team has no open roster spots."
        )


    if price > team.max_bid:

        raise ValueError(
            f"Illegal bid. "
            f"That team's current maximum is "
            f"${team.max_bid}."
        )


    new_sale = (
        LiveAuctionSale(
            sale_number=(
                len(
                    existing_sales
                )
                + 1
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
            modeled_market_value=(
                modeled_market_value
            ),
            do_not_exceed=(
                do_not_exceed
            ),
        )
    )


    return (
        list(
            existing_sales
        )
        +
        [
            new_sale
        ]
    )


# =========================================================
# ROOM SPENDING INDEX
# =========================================================

def calculate_room_spend_index(
    sales: List[
        LiveAuctionSale
    ],
) -> Optional[float]:

    actual = 0.0

    modeled = 0.0


    for sale in sales:

        if (
            sale.modeled_market_value
            is None
        ):

            continue


        if (
            sale.modeled_market_value
            <= 0
        ):

            continue


        actual += (
            sale.price
        )

        modeled += (
            float(
                sale.modeled_market_value
            )
        )


    if modeled <= 0:

        return None


    return (
        actual
        /
        modeled
    )