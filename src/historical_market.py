from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from src.auction_pool import (
    normalize_player_name,
)


MIN_USABLE_YEAR_SALES = 20

MAX_HISTORICAL_WEIGHT = 0.35


# =========================================================
# HISTORICAL PLAYER NAME ALIASES
# =========================================================

HISTORICAL_PLAYER_ALIASES = {

    # Typos / punctuation
    "deandre swift": "dandre swift",
    "deebo samuels": "deebo samuel",
    "jerry juedy": "jerry jeudy",
    "keon colemon": "keon coleman",
    "breaelon allen": "braelon allen",
    "cj strahd": "cj stroud",
    "cedric tillmen": "cedric tillman",
    "jake furgeson": "jake ferguson",
    "travis swift:": "travis kelce",
    "Trevor Lawrence": "trevor lawrence",
    "Young Hoe Could": "younghoe koo",

    # Common shortened names
    "hurts": "jalen hurts",
    "monty": "david montgomery",

    # Sleeper naming differences
    "brian robinson jr": "brian robinson",
    "michael penix jr": "michael penix",

    # Nicknames
    "hollywood brown": "marquise brown",

    # Defenses
    "eagles": "philadelphia eagles",
    "packers": "green bay packers",

    # If "Travis Swift" = Travis Kelce in your sheet,
    # uncomment this:
    # "travis swift": "travis kelce",
}

def resolve_historical_player_key(
    player_name: str,
) -> str:

    key = normalize_player_name(
        player_name
    )

    return (
        HISTORICAL_PLAYER_ALIASES.get(
            key,
            key,
        )
    )


# =========================================================
# DATA OBJECTS
# =========================================================

@dataclass
class HistoricalSaleRecord:

    year: int

    player_name: str

    position: Optional[str]

    price: float

    manager_id: Optional[str]

    manager_raw: Optional[str]


@dataclass
class PositionMarketProfile:

    position: str

    sales_count: int

    average_price: float

    median_price: float

    p75_price: float

    p90_price: float

    max_price: float


@dataclass
class ManagerMarketProfile:

    manager_id: str

    sales_count: int

    total_spend: float

    average_price: float

    max_price: float

    confidence: float

    aggressiveness_index: float

    star_buy_rate: float

    star_chase_index: float

    position_spend_share: Dict[
        str,
        float,
    ]

    position_purchase_count: Dict[
        str,
        int,
    ]


@dataclass
class HistoricalMarketModel:

    eligible_years: List[int]

    excluded_years: List[int]

    year_sale_counts: Dict[
        int,
        int,
    ]

    year_total_spend: Dict[
        int,
        float,
    ]

    mapped_sales: List[
        HistoricalSaleRecord
    ]

    unmapped_sales_count: int

    position_profiles: Dict[
        str,
        PositionMarketProfile,
    ]

    manager_profiles: Dict[
        str,
        ManagerMarketProfile,
    ]

    league_average_purchase: float

    league_star_buy_rate: float


@dataclass
class MarketAdjustedValue:

    player_name: str

    position: str

    baseline_value: float

    historical_expected_price: Optional[float]

    historical_sample_size: int

    historical_weight: float

    expected_market_value: float


# =========================================================
# HELPERS
# =========================================================

def numeric(
    value,
) -> Optional[float]:

    if value is None:
        return None

    try:

        return float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


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


def percentile(
    values: List[float],
    q: float,
) -> float:
    """
    Linear percentile without requiring numpy.
    """

    if not values:

        return 0.0


    ordered = sorted(
        float(
            value
        )
        for value
        in values
    )


    if len(
        ordered
    ) == 1:

        return ordered[0]


    q = max(
        0.0,
        min(
            1.0,
            q,
        ),
    )


    index = (
        (
            len(
                ordered
            )
            - 1
        )
        * q
    )


    lower = int(
        index
    )

    upper = min(
        lower + 1,
        len(
            ordered
        )
        - 1,
    )


    fraction = (
        index
        - lower
    )


    return (
        ordered[
            lower
        ]
        +
        (
            ordered[
                upper
            ]
            -
            ordered[
                lower
            ]
        )
        * fraction
    )


def descending_curve_value(
    values: List[float],
    position_index: int,
    total_current_players: int,
) -> Optional[float]:
    """
    Map a current player's within-position rank
    to the same point on a historical price curve.

    Example:
        Current RB1 gets historical top-end RB price.
        Current RB20 gets a mid/lower historical RB price.
    """

    if not values:

        return None


    ordered = sorted(
        values,
        reverse=True,
    )


    if (
        total_current_players <= 1
        or
        len(
            ordered
        ) == 1
    ):

        return ordered[0]


    current_percentile = (
        position_index
        /
        (
            total_current_players
            - 1
        )
    )


    historical_index = (
        current_percentile
        *
        (
            len(
                ordered
            )
            - 1
        )
    )


    lower = int(
        historical_index
    )

    upper = min(
        lower + 1,
        len(
            ordered
        )
        - 1,
    )


    fraction = (
        historical_index
        - lower
    )


    return (
        ordered[
            lower
        ]
        +
        (
            ordered[
                upper
            ]
            -
            ordered[
                lower
            ]
        )
        * fraction
    )


# =========================================================
# SLEEPER PLAYER POSITION LOOKUP
# =========================================================

def build_position_lookup(
    sleeper_players: dict,
) -> Dict[
    str,
    str,
]:

    result = {}


    for player in (
        sleeper_players.values()
    ):

        if not isinstance(
            player,
            dict,
        ):

            continue


        position = (
            normalize_position(
                player.get(
                    "position"
                )
            )
        )


        if position is None:

            continue


        player_name = (
            player.get(
                "full_name"
            )
            or player.get(
                "search_full_name"
            )
        )


        if not player_name:

            first_name = (
                player.get(
                    "first_name"
                )
                or ""
            )

            last_name = (
                player.get(
                    "last_name"
                )
                or ""
            )

            player_name = (
                f"{first_name} {last_name}"
                .strip()
            )


        if not player_name:

            continue


        normalized = (
            normalize_player_name(
                player_name
            )
        )


        if normalized:

            result[
                normalized
            ] = position


    return result


# =========================================================
# BUILD HISTORICAL MODEL
# =========================================================

def build_historical_market_model(
    historical_sales,
    sleeper_players: dict,
    min_sales_per_year: int = MIN_USABLE_YEAR_SALES,
) -> HistoricalMarketModel:

    position_lookup = (
        build_position_lookup(
            sleeper_players
        )
    )


    # -----------------------------------------------------
    # RAW YEAR COUNTS / SPEND
    # -----------------------------------------------------

    sales_by_year = (
        defaultdict(
            list
        )
    )


    for sale in historical_sales:

        price = numeric(
            sale.price
        )


        if (
            price is None
            or price <= 0
        ):

            continue


        sales_by_year[
            int(
                sale.year
            )
        ].append(
            sale
        )


    year_sale_counts = {
        year: len(
            sales
        )

        for (
            year,
            sales,
        ) in sales_by_year.items()
    }


    year_total_spend = {}


    for (
        year,
        sales,
    ) in sales_by_year.items():

        year_total_spend[
            year
        ] = sum(
            numeric(
                sale.price
            )
            or 0.0

            for sale
            in sales
        )


    eligible_years = sorted(
        year

        for (
            year,
            count,
        ) in year_sale_counts.items()

        if (
            count
            >= min_sales_per_year
        )
    )


    excluded_years = sorted(
        year

        for year
        in year_sale_counts

        if (
            year
            not in eligible_years
        )
    )


    # -----------------------------------------------------
    # MAP HISTORICAL PLAYER -> CURRENT POSITION
    # -----------------------------------------------------

    mapped_sales = []

    unmapped_sales_count = 0


    for year in eligible_years:

        for sale in (
            sales_by_year[
                year
            ]
        ):

            normalized_name = (
    resolve_historical_player_key(
        sale.player_name
    )
)


            position = (
                position_lookup.get(
                    normalized_name
                )
            )


            if position is None:

                unmapped_sales_count += 1

                continue


            price = numeric(
                sale.price
            )


            mapped_sales.append(
                HistoricalSaleRecord(
                    year=(
                        int(
                            year
                        )
                    ),
                    player_name=(
                        sale.player_name
                    ),
                    position=(
                        position
                    ),
                    price=(
                        float(
                            price
                        )
                    ),
                    manager_id=(
                        sale.manager_id
                    ),
                    manager_raw=(
                        sale.manager_raw
                    ),
                )
            )


    # -----------------------------------------------------
    # LEAGUE PRICE STATISTICS
    # -----------------------------------------------------

    mapped_prices = [
        sale.price
        for sale
        in mapped_sales
    ]


    if mapped_prices:

        league_average_purchase = (
            sum(
                mapped_prices
            )
            /
            len(
                mapped_prices
            )
        )

    else:

        league_average_purchase = 0.0


    # -----------------------------------------------------
    # POSITION PRICE PROFILES
    # -----------------------------------------------------

    position_prices = (
        defaultdict(
            list
        )
    )


    for sale in mapped_sales:

        if sale.position:

            position_prices[
                sale.position
            ].append(
                sale.price
            )


    position_profiles = {}


    for (
        position,
        prices,
    ) in position_prices.items():

        position_profiles[
            position
        ] = (
            PositionMarketProfile(
                position=(
                    position
                ),
                sales_count=(
                    len(
                        prices
                    )
                ),
                average_price=(
                    sum(
                        prices
                    )
                    /
                    len(
                        prices
                    )
                ),
                median_price=(
                    percentile(
                        prices,
                        0.50,
                    )
                ),
                p75_price=(
                    percentile(
                        prices,
                        0.75,
                    )
                ),
                p90_price=(
                    percentile(
                        prices,
                        0.90,
                    )
                ),
                max_price=(
                    max(
                        prices
                    )
                ),
            )
        )


    # -----------------------------------------------------
    # STAR PURCHASE THRESHOLDS BY YEAR
    # -----------------------------------------------------

    star_threshold_by_year = {}


    for year in eligible_years:

        prices = [
            numeric(
                sale.price
            )

            for sale
            in sales_by_year[
                year
            ]
        ]


        prices = [
            float(
                value
            )

            for value
            in prices

            if value is not None
        ]


        star_threshold_by_year[
            year
        ] = percentile(
            prices,
            0.80,
        )


    # -----------------------------------------------------
    # LEAGUE STAR RATE
    # -----------------------------------------------------

    star_results = []


    for sale in mapped_sales:

        threshold = (
            star_threshold_by_year.get(
                sale.year
            )
        )


        if threshold is None:

            continue


        star_results.append(
            1.0
            if (
                sale.price
                >= threshold
            )
            else 0.0
        )


    if star_results:

        league_star_buy_rate = (
            sum(
                star_results
            )
            /
            len(
                star_results
            )
        )

    else:

        league_star_buy_rate = 0.20


    # -----------------------------------------------------
    # MANAGER PROFILES
    # -----------------------------------------------------

    manager_sales = (
        defaultdict(
            list
        )
    )


    for sale in mapped_sales:

        if sale.manager_id:

            manager_sales[
                sale.manager_id
            ].append(
                sale
            )


    manager_profiles = {}


    for (
        manager_id,
        sales,
    ) in manager_sales.items():

        prices = [
            sale.price
            for sale
            in sales
        ]


        sales_count = len(
            sales
        )


        total_spend = sum(
            prices
        )


        average_price = (
            total_spend
            /
            sales_count
        )


        confidence = (
            sales_count
            /
            (
                sales_count
                + 8.0
            )
        )


        # -----------------------------------------------
        # Aggressiveness
        #
        # > 1.0 = historically spends more per purchase
        # < 1.0 = historically spends less per purchase
        #
        # Shrink toward neutral 1.0.
        # -----------------------------------------------

        if (
            league_average_purchase
            > 0
        ):

            raw_aggressiveness = (
                average_price
                /
                league_average_purchase
            )

        else:

            raw_aggressiveness = 1.0


        aggressiveness_index = (
            1.0
            +
            confidence
            *
            (
                raw_aggressiveness
                - 1.0
            )
        )


        # -----------------------------------------------
        # STAR CHASING
        # -----------------------------------------------

        manager_star_flags = []


        for sale in sales:

            threshold = (
                star_threshold_by_year.get(
                    sale.year
                )
            )


            if threshold is None:

                continue


            manager_star_flags.append(
                1.0
                if (
                    sale.price
                    >= threshold
                )
                else 0.0
            )


        if manager_star_flags:

            raw_star_rate = (
                sum(
                    manager_star_flags
                )
                /
                len(
                    manager_star_flags
                )
            )

        else:

            raw_star_rate = (
                league_star_buy_rate
            )


        shrunk_star_rate = (
            league_star_buy_rate
            +
            confidence
            *
            (
                raw_star_rate
                -
                league_star_buy_rate
            )
        )


        if (
            league_star_buy_rate
            > 0
        ):

            star_chase_index = (
                shrunk_star_rate
                /
                league_star_buy_rate
            )

        else:

            star_chase_index = 1.0


        # -----------------------------------------------
        # POSITION TENDENCIES
        # -----------------------------------------------

        position_spend = (
            defaultdict(
                float
            )
        )

        position_count = (
            defaultdict(
                int
            )
        )


        for sale in sales:

            if not sale.position:

                continue


            position_spend[
                sale.position
            ] += (
                sale.price
            )


            position_count[
                sale.position
            ] += 1


        position_spend_share = {}


        if total_spend > 0:

            for (
                position,
                spend,
            ) in position_spend.items():

                position_spend_share[
                    position
                ] = (
                    spend
                    /
                    total_spend
                )


        manager_profiles[
            manager_id
        ] = (
            ManagerMarketProfile(
                manager_id=(
                    manager_id
                ),
                sales_count=(
                    sales_count
                ),
                total_spend=(
                    total_spend
                ),
                average_price=(
                    average_price
                ),
                max_price=(
                    max(
                        prices
                    )
                ),
                confidence=(
                    confidence
                ),
                aggressiveness_index=(
                    aggressiveness_index
                ),
                star_buy_rate=(
                    shrunk_star_rate
                ),
                star_chase_index=(
                    star_chase_index
                ),
                position_spend_share=(
                    dict(
                        position_spend_share
                    )
                ),
                position_purchase_count=(
                    dict(
                        position_count
                    )
                ),
            )
        )


    return HistoricalMarketModel(
        eligible_years=(
            eligible_years
        ),
        excluded_years=(
            excluded_years
        ),
        year_sale_counts=(
            dict(
                year_sale_counts
            )
        ),
        year_total_spend=(
            dict(
                year_total_spend
            )
        ),
        mapped_sales=(
            mapped_sales
        ),
        unmapped_sales_count=(
            unmapped_sales_count
        ),
        position_profiles=(
            position_profiles
        ),
        manager_profiles=(
            manager_profiles
        ),
        league_average_purchase=(
            league_average_purchase
        ),
        league_star_buy_rate=(
            league_star_buy_rate
        ),
    )


# =========================================================
# HISTORICAL MARKET VALUE CALIBRATION
# =========================================================

def calculate_historical_market_values(
    auction_values,
    historical_model: HistoricalMarketModel,
    current_total_auction_cash: float,
) -> List[
    MarketAdjustedValue
]:
    """
    Take the deterministic Baseline $ and calibrate it
    toward prices this league has historically paid.

    Historical prices are first scaled into the current
    draft's auction economy.

    The historical signal is capped at 35% so league
    history can calibrate the model but cannot overpower
    projections / VORP / dynasty value.
    """

    if (
        not historical_model
        .eligible_years
    ):

        return [
            MarketAdjustedValue(
                player_name=(
                    value.player_name
                ),
                position=(
                    value.position
                ),
                baseline_value=(
                    value.baseline_value
                ),
                historical_expected_price=None,
                historical_sample_size=0,
                historical_weight=0.0,
                expected_market_value=(
                    value.baseline_value
                ),
            )

            for value
            in auction_values
        ]


    # -----------------------------------------------------
    # SCALE EACH HISTORICAL YEAR TO CURRENT AUCTION CASH
    # -----------------------------------------------------

    scaled_position_prices = (
        defaultdict(
            list
        )
    )


    for sale in (
        historical_model
        .mapped_sales
    ):

        historical_year_spend = (
            historical_model
            .year_total_spend
            .get(
                sale.year,
                0.0,
            )
        )


        if (
            historical_year_spend
            <= 0
        ):

            continue


        scale = (
            current_total_auction_cash
            /
            historical_year_spend
        )


        scaled_price = (
            sale.price
            * scale
        )


        if sale.position:

            scaled_position_prices[
                sale.position
            ].append(
                scaled_price
            )


    # -----------------------------------------------------
    # CURRENT DRAFTABLE PLAYERS BY POSITION
    # -----------------------------------------------------

    current_by_position = (
        defaultdict(
            list
        )
    )


    for value in auction_values:

        if not (
            value.expected_to_be_drafted
        ):

            continue


        current_by_position[
            value.position
        ].append(
            value
        )


    for position in (
        current_by_position
    ):

        current_by_position[
            position
        ].sort(
            key=lambda item: (
                item.baseline_value
            ),
            reverse=True,
        )


    current_rank_lookup = {}


    for (
        position,
        values,
    ) in current_by_position.items():

        total_position_players = len(
            values
        )


        for (
            index,
            value,
        ) in enumerate(
            values
        ):

            current_rank_lookup[
                normalize_player_name(
                    value.player_name
                )
            ] = (
                position,
                index,
                total_position_players,
            )


    # -----------------------------------------------------
    # CALIBRATE EACH PLAYER
    # -----------------------------------------------------

    results = []


    for value in auction_values:

        key = (
            normalize_player_name(
                value.player_name
            )
        )


        historical_expected = None

        historical_weight = 0.0

        historical_sample_size = 0


        rank_info = (
            current_rank_lookup.get(
                key
            )
        )


        if rank_info:

            (
                position,
                index,
                total_position_players,
            ) = rank_info


            historical_prices = (
                scaled_position_prices.get(
                    position,
                    []
                )
            )


            historical_sample_size = len(
                historical_prices
            )


            if (
                historical_sample_size
                >= 5
            ):

                historical_expected = (
                    descending_curve_value(
                        values=(
                            historical_prices
                        ),
                        position_index=(
                            index
                        ),
                        total_current_players=(
                            total_position_players
                        ),
                    )
                )


                sample_confidence = (
                    historical_sample_size
                    /
                    (
                        historical_sample_size
                        + 20.0
                    )
                )


                historical_weight = (
                    MAX_HISTORICAL_WEIGHT
                    *
                    sample_confidence
                )


        if historical_expected is None:

            expected_market_value = (
                value.baseline_value
            )


        else:

            expected_market_value = (
                (
                    1.0
                    -
                    historical_weight
                )
                *
                value.baseline_value
                +
                historical_weight
                *
                historical_expected
            )


        results.append(
            MarketAdjustedValue(
                player_name=(
                    value.player_name
                ),
                position=(
                    value.position
                ),
                baseline_value=(
                    value.baseline_value
                ),
                historical_expected_price=(
                    historical_expected
                ),
                historical_sample_size=(
                    historical_sample_size
                ),
                historical_weight=(
                    historical_weight
                ),
                expected_market_value=(
                    expected_market_value
                ),
            )
        )


    return results