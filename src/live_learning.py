import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.auction_pool import normalize_player_name


# =========================================================
# LIVE LEARNING CONSTANTS
# =========================================================

POSITION_PRIOR_STRENGTH = 6.0
TIER_PRIOR_STRENGTH = 8.0
MANAGER_PRIOR_STRENGTH = 5.0
MANAGER_POSITION_PRIOR_STRENGTH = 4.0
OVERALL_PRIOR_STRENGTH = 15.0

MIN_POSITION_MULTIPLIER = 0.85
MAX_POSITION_MULTIPLIER = 1.18

MIN_TIER_MULTIPLIER = 0.88
MAX_TIER_MULTIPLIER = 1.15

MIN_MANAGER_MULTIPLIER = 0.85
MAX_MANAGER_MULTIPLIER = 1.20

MIN_PLAYER_MARKET_MULTIPLIER = 0.85
MAX_PLAYER_MARKET_MULTIPLIER = 1.18


# =========================================================
# DATA OBJECTS
# =========================================================

@dataclass
class LiveSignal:
    sample_size: int

    actual_spend: float

    modeled_spend: float

    raw_ratio: float

    multiplier: float


@dataclass
class LiveManagerProfile:
    manager_id: str

    purchases: int

    actual_spend: float

    modeled_spend: float

    raw_ratio: float

    multiplier: float

    position_counts: Dict[
        str,
        int,
    ] = field(
        default_factory=dict
    )

    position_multipliers: Dict[
        str,
        float,
    ] = field(
        default_factory=dict
    )


@dataclass
class LiveMarketCalibration:
    overall: LiveSignal

    position_signals: Dict[
        str,
        LiveSignal,
    ]

    tier_signals: Dict[
        str,
        LiveSignal,
    ]

    manager_profiles: Dict[
        str,
        LiveManagerProfile,
    ]


@dataclass
class LiveAdjustedMarketValue:
    player_name: str

    position: str

    baseline_value: float

    historical_expected_price: Optional[float]

    historical_sample_size: int

    historical_weight: float

    pre_live_market_value: float

    expected_market_value: float

    live_multiplier: float

    position_multiplier: float

    tier_multiplier: float

    price_tier: str


# =========================================================
# HELPERS
# =========================================================

def numeric(
    value,
    default=0.0,
):

    if value is None:
        return default

    try:

        return float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return default


def clamp(
    value,
    minimum,
    maximum,
):

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def normalize_position(
    value,
):

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


# =========================================================
# PRICE TIERS
# =========================================================

def price_tier(
    modeled_market_value,
):

    value = numeric(
        modeled_market_value
    )


    if value >= 60:

        return "ELITE"


    if value >= 35:

        return "PREMIUM"


    if value >= 15:

        return "CORE"


    return "VALUE"


# =========================================================
# SHRUNK SIGNAL
# =========================================================

def build_signal(
    sales,
    prior_strength,
    minimum_multiplier,
    maximum_multiplier,
):

    usable_sales = [
        sale

        for sale
        in sales

        if (
            numeric(
                sale.modeled_market_value
            )
            > 0
            and
            numeric(
                sale.price
            )
            > 0
        )
    ]


    sample_size = len(
        usable_sales
    )


    if sample_size == 0:

        return (
            LiveSignal(
                sample_size=0,
                actual_spend=0.0,
                modeled_spend=0.0,
                raw_ratio=1.0,
                multiplier=1.0,
            )
        )


    actual_spend = sum(
        numeric(
            sale.price
        )

        for sale
        in usable_sales
    )


    modeled_spend = sum(
        numeric(
            sale.modeled_market_value
        )

        for sale
        in usable_sales
    )


    if modeled_spend <= 0:

        raw_ratio = 1.0

    else:

        raw_ratio = (
            actual_spend
            /
            modeled_spend
        )


    confidence = (
        sample_size
        /
        (
            sample_size
            +
            prior_strength
        )
    )


    multiplier = (
        1.0
        +
        (
            raw_ratio
            -
            1.0
        )
        *
        confidence
    )


    multiplier = clamp(
        multiplier,
        minimum_multiplier,
        maximum_multiplier,
    )


    return (
        LiveSignal(
            sample_size=(
                sample_size
            ),
            actual_spend=(
                actual_spend
            ),
            modeled_spend=(
                modeled_spend
            ),
            raw_ratio=(
                raw_ratio
            ),
            multiplier=(
                multiplier
            ),
        )
    )


# =========================================================
# BUILD LIVE MARKET CALIBRATION
# =========================================================

def build_live_market_calibration(
    sales,
):

    usable_sales = [
        sale

        for sale
        in sales

        if (
            numeric(
                sale.modeled_market_value
            )
            > 0
            and
            numeric(
                sale.price
            )
            > 0
        )
    ]


    # =====================================================
    # OVERALL ROOM
    # =====================================================

    overall = (
        build_signal(
            sales=(
                usable_sales
            ),
            prior_strength=(
                OVERALL_PRIOR_STRENGTH
            ),
            minimum_multiplier=0.92,
            maximum_multiplier=1.08,
        )
    )


    # =====================================================
    # POSITION SIGNALS
    # =====================================================

    position_groups = {}


    for sale in usable_sales:

        position = (
            normalize_position(
                sale.position
            )
        )


        if position is None:

            continue


        position_groups.setdefault(
            position,
            []
        ).append(
            sale
        )


    position_signals = {}


    for (
        position,
        position_sales,
    ) in position_groups.items():

        position_signals[
            position
        ] = (
            build_signal(
                sales=(
                    position_sales
                ),
                prior_strength=(
                    POSITION_PRIOR_STRENGTH
                ),
                minimum_multiplier=(
                    MIN_POSITION_MULTIPLIER
                ),
                maximum_multiplier=(
                    MAX_POSITION_MULTIPLIER
                ),
            )
        )


    # =====================================================
    # TIER SIGNALS
    # =====================================================

    tier_groups = {}


    for sale in usable_sales:

        tier = (
            price_tier(
                sale.modeled_market_value
            )
        )


        tier_groups.setdefault(
            tier,
            []
        ).append(
            sale
        )


    tier_signals = {}


    for (
        tier,
        tier_sales,
    ) in tier_groups.items():

        tier_signals[
            tier
        ] = (
            build_signal(
                sales=(
                    tier_sales
                ),
                prior_strength=(
                    TIER_PRIOR_STRENGTH
                ),
                minimum_multiplier=(
                    MIN_TIER_MULTIPLIER
                ),
                maximum_multiplier=(
                    MAX_TIER_MULTIPLIER
                ),
            )
        )


    # =====================================================
    # MANAGER SIGNALS
    # =====================================================

    manager_groups = {}


    for sale in usable_sales:

        manager_groups.setdefault(
            sale.manager_id,
            []
        ).append(
            sale
        )


    manager_profiles = {}


    for (
        manager_id,
        manager_sales,
    ) in manager_groups.items():

        manager_signal = (
            build_signal(
                sales=(
                    manager_sales
                ),
                prior_strength=(
                    MANAGER_PRIOR_STRENGTH
                ),
                minimum_multiplier=(
                    MIN_MANAGER_MULTIPLIER
                ),
                maximum_multiplier=(
                    MAX_MANAGER_MULTIPLIER
                ),
            )
        )


        manager_position_groups = {}


        for sale in manager_sales:

            position = (
                normalize_position(
                    sale.position
                )
            )


            if position is None:

                continue


            manager_position_groups.setdefault(
                position,
                []
            ).append(
                sale
            )


        position_counts = {}

        position_multipliers = {}


        for (
            position,
            manager_position_sales,
        ) in manager_position_groups.items():

            signal = (
                build_signal(
                    sales=(
                        manager_position_sales
                    ),
                    prior_strength=(
                        MANAGER_POSITION_PRIOR_STRENGTH
                    ),
                    minimum_multiplier=(
                        MIN_MANAGER_MULTIPLIER
                    ),
                    maximum_multiplier=(
                        MAX_MANAGER_MULTIPLIER
                    ),
                )
            )


            position_counts[
                position
            ] = (
                signal.sample_size
            )


            position_multipliers[
                position
            ] = (
                signal.multiplier
            )


        manager_profiles[
            manager_id
        ] = (
            LiveManagerProfile(
                manager_id=(
                    manager_id
                ),
                purchases=(
                    manager_signal
                    .sample_size
                ),
                actual_spend=(
                    manager_signal
                    .actual_spend
                ),
                modeled_spend=(
                    manager_signal
                    .modeled_spend
                ),
                raw_ratio=(
                    manager_signal
                    .raw_ratio
                ),
                multiplier=(
                    manager_signal
                    .multiplier
                ),
                position_counts=(
                    position_counts
                ),
                position_multipliers=(
                    position_multipliers
                ),
            )
        )


    return (
        LiveMarketCalibration(
            overall=(
                overall
            ),
            position_signals=(
                position_signals
            ),
            tier_signals=(
                tier_signals
            ),
            manager_profiles=(
                manager_profiles
            ),
        )
    )


# =========================================================
# APPLY LIVE MARKET LEARNING
# =========================================================

def apply_live_market_calibration(
    market_values,
    auction_values,
    calibration,
):
    """
    Redistribute remaining market dollars based on
    live position/tier behavior.

    IMPORTANT:
    The calculation is budget-neutral.

    Example:
        RBs running +10% does NOT create new auction
        dollars. It shifts a greater share of the
        existing remaining market toward RBs.

    Live remaining-cash inflation/deflation is already
    captured by calculate_auction_values().
    """

    auction_lookup = {
        normalize_player_name(
            value.player_name
        ): value

        for value
        in auction_values
    }


    provisional = []


    for market in market_values:

        key = (
            normalize_player_name(
                market.player_name
            )
        )


        auction_value = (
            auction_lookup.get(
                key
            )
        )


        pre_live = max(
            1.0,
            numeric(
                market.expected_market_value,
                1.0,
            ),
        )


        position = (
            normalize_position(
                market.position
            )
            or market.position
        )


        tier = (
            price_tier(
                pre_live
            )
        )


        position_signal = (
            calibration
            .position_signals
            .get(
                position
            )
        )


        tier_signal = (
            calibration
            .tier_signals
            .get(
                tier
            )
        )


        position_multiplier = (
            position_signal.multiplier
            if position_signal
            else 1.0
        )


        tier_multiplier = (
            tier_signal.multiplier
            if tier_signal
            else 1.0
        )


        # Position behavior gets slightly more weight
        # than tier behavior.
        raw_multiplier = (
            1.0
            +
            0.60
            *
            (
                position_multiplier
                -
                1.0
            )
            +
            0.40
            *
            (
                tier_multiplier
                -
                1.0
            )
        )


        raw_multiplier = (
            clamp(
                raw_multiplier,
                MIN_PLAYER_MARKET_MULTIPLIER,
                MAX_PLAYER_MARKET_MULTIPLIER,
            )
        )


        expected_to_be_drafted = (
            bool(
                auction_value
                and
                auction_value
                .expected_to_be_drafted
            )
        )


        provisional.append(
            {
                "market": (
                    market
                ),
                "key": (
                    key
                ),
                "pre_live": (
                    pre_live
                ),
                "position": (
                    position
                ),
                "tier": (
                    tier
                ),
                "position_multiplier": (
                    position_multiplier
                ),
                "tier_multiplier": (
                    tier_multiplier
                ),
                "raw_multiplier": (
                    raw_multiplier
                ),
                "expected_to_be_drafted": (
                    expected_to_be_drafted
                ),
            }
        )


    # =====================================================
    # BUDGET-NEUTRAL NORMALIZATION
    # =====================================================

    pre_total = sum(
        row[
            "pre_live"
        ]

        for row
        in provisional

        if row[
            "expected_to_be_drafted"
        ]
    )


    raw_post_total = sum(
        row[
            "pre_live"
        ]
        *
        row[
            "raw_multiplier"
        ]

        for row
        in provisional

        if row[
            "expected_to_be_drafted"
        ]
    )


    if (
        pre_total > 0
        and
        raw_post_total > 0
    ):

        normalization_factor = (
            pre_total
            /
            raw_post_total
        )

    else:

        normalization_factor = 1.0


    results = []


    for row in provisional:

        market = (
            row[
                "market"
            ]
        )


        pre_live = (
            row[
                "pre_live"
            ]
        )


        if row[
            "expected_to_be_drafted"
        ]:

            live_multiplier = (
                row[
                    "raw_multiplier"
                ]
                *
                normalization_factor
            )


            live_value = max(
                1.0,
                pre_live
                *
                live_multiplier,
            )

        else:

            live_multiplier = 1.0

            live_value = (
                pre_live
            )


        results.append(
            LiveAdjustedMarketValue(
                player_name=(
                    market.player_name
                ),
                position=(
                    market.position
                ),
                baseline_value=(
                    market.baseline_value
                ),
                historical_expected_price=(
                    market
                    .historical_expected_price
                ),
                historical_sample_size=(
                    market
                    .historical_sample_size
                ),
                historical_weight=(
                    market
                    .historical_weight
                ),
                pre_live_market_value=(
                    pre_live
                ),
                expected_market_value=(
                    live_value
                ),
                live_multiplier=(
                    live_multiplier
                ),
                position_multiplier=(
                    row[
                        "position_multiplier"
                    ]
                ),
                tier_multiplier=(
                    row[
                        "tier_multiplier"
                    ]
                ),
                price_tier=(
                    row[
                        "tier"
                    ]
                ),
            )
        )


    return results


# =========================================================
# THREAT LABEL
# =========================================================

def live_threat_level(
    score,
):

    if score >= 75:
        return "VERY HIGH"

    if score >= 60:
        return "HIGH"

    if score >= 45:
        return "MODERATE"

    if score >= 30:
        return "LOW"

    return "MINIMAL"


# =========================================================
# APPLY LIVE MANAGER BEHAVIOR TO BIDDER THREAT
# =========================================================

def apply_live_manager_threat_adjustments(
    threat_summaries,
    calibration,
):
    """
    Historical manager behavior remains the prior.

    Current-auction manager behavior is a modest overlay.
    """

    results = copy.deepcopy(
        threat_summaries
    )


    for summary in results:

        position = (
            normalize_position(
                summary.position
            )
        )


        for threat in (
            summary.threats
        ):

            manager_profile = (
                calibration
                .manager_profiles
                .get(
                    threat.manager_id
                )
            )


            if manager_profile is None:

                continue


            manager_multiplier = (
                manager_profile
                .multiplier
            )


            position_multiplier = (
                manager_profile
                .position_multipliers
                .get(
                    position,
                    1.0,
                )
            )


            combined_behavior = (
                1.0
                +
                0.70
                *
                (
                    manager_multiplier
                    -
                    1.0
                )
                +
                0.30
                *
                (
                    position_multiplier
                    -
                    1.0
                )
            )


            # Only a portion of the learned behavior
            # feeds into bidder threat.
            threat_adjustment = (
                1.0
                +
                0.40
                *
                (
                    combined_behavior
                    -
                    1.0
                )
            )


            threat.threat_score = (
                clamp(
                    threat.threat_score
                    *
                    threat_adjustment,
                    0.0,
                    100.0,
                )
            )


            threat.threat_level = (
                live_threat_level(
                    threat.threat_score
                )
            )


            # =============================================
            # EXPLANATION
            # =============================================

            if (
                manager_profile.purchases
                >= 2
            ):

                if (
                    manager_profile.multiplier
                    >= 1.05
                ):

                    threat.reasons.append(
                        "2026 bidding above model"
                    )


                elif (
                    manager_profile.multiplier
                    <= 0.95
                ):

                    threat.reasons.append(
                        "2026 conserving cash"
                    )


            position_sample = (
                manager_profile
                .position_counts
                .get(
                    position,
                    0,
                )
            )


            if (
                position_sample
                >= 2
            ):

                if (
                    position_multiplier
                    >= 1.06
                ):

                    threat.reasons.append(
                        f"2026 attacking {position}"
                    )


                elif (
                    position_multiplier
                    <= 0.94
                ):

                    threat.reasons.append(
                        f"2026 avoiding {position} premiums"
                    )


        # =================================================
        # RE-SORT AFTER LIVE ADJUSTMENT
        # =================================================

        summary.threats.sort(
            key=lambda threat: (
                threat.threat_score
            ),
            reverse=True,
        )


        if summary.threats:

            summary.top_manager_id = (
                summary
                .threats[
                    0
                ]
                .manager_id
            )


            summary.top_threat_score = (
                summary
                .threats[
                    0
                ]
                .threat_score
            )


            summary.top_threat_level = (
                summary
                .threats[
                    0
                ]
                .threat_level
            )


        else:

            summary.top_manager_id = None

            summary.top_threat_score = 0.0

            summary.top_threat_level = "NONE"


        summary.high_threat_count = len(
            [
                threat

                for threat
                in summary.threats

                if (
                    threat.threat_score
                    >= 60
                )
            ]
        )


    return results