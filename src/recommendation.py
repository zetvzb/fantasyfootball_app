from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.auction_pool import (
    normalize_player_name,
)


# =========================================================
# MODEL LIMITS
# =========================================================

MAX_MARKET_PREMIUM = 1.20


# =========================================================
# DATA OBJECT
# =========================================================

@dataclass
class BidRecommendation:

    player_name: str

    position: str

    expected_market_value: float

    baseline_value: float

    do_not_exceed: int

    legal_max_bid: int

    my_need_score: float

    scarcity_score: float

    threat_score: float

    value_edge: float

    alternative_player: Optional[str]

    alternative_market_value: Optional[float]

    alternative_vorp: Optional[float]

    player_vorp: Optional[float]

    strategy: str

    reasons: List[str] = field(
        default_factory=list
    )


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
    minimum=0.0,
    maximum=1.0,
):

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


# =========================================================
# BUILD LOOKUPS
# =========================================================

def build_value_lookup(
    values,
):

    return {
        normalize_player_name(
            value.player_name
        ): value

        for value
        in values
    }


# =========================================================
# SAME-POSITION ALTERNATIVES
# =========================================================

def build_position_alternatives(
    available_players,
    player_values,
    market_values,
):

    vorp_lookup = (
        build_value_lookup(
            player_values
        )
    )

    market_lookup = (
        build_value_lookup(
            market_values
        )
    )

    by_position = {}


    for player in available_players:

        position = (
            player.position
        )

        key = (
            normalize_player_name(
                player.player_name
            )
        )


        value = (
            vorp_lookup.get(
                key
            )
        )


        market = (
            market_lookup.get(
                key
            )
        )


        vorp = (
            numeric(
                value.vorp
            )
            if value
            else 0.0
        )


        market_price = (
            numeric(
                market.expected_market_value
            )
            if market
            else 1.0
        )


        by_position.setdefault(
            position,
            []
        ).append(
            {
                "player_name": (
                    player.player_name
                ),
                "vorp": (
                    vorp
                ),
                "market": (
                    market_price
                ),
            }
        )


    for position in by_position:

        by_position[
            position
        ].sort(
            key=lambda row: (
                row[
                    "vorp"
                ]
            ),
            reverse=True,
        )


    return by_position


# =========================================================
# SCARCITY
# =========================================================

def calculate_scarcity(
    player_name: str,
    position: str,
    alternatives_by_position,
):

    position_players = (
        alternatives_by_position.get(
            position,
            []
        )
    )


    if not position_players:

        return (
            0.0,
            None,
        )


    key = (
        normalize_player_name(
            player_name
        )
    )


    index = None


    for (
        player_index,
        candidate,
    ) in enumerate(
        position_players
    ):

        candidate_key = (
            normalize_player_name(
                candidate[
                    "player_name"
                ]
            )
        )


        if candidate_key == key:

            index = (
                player_index
            )

            break


    if index is None:

        return (
            0.0,
            None,
        )


    current = (
        position_players[
            index
        ]
    )


    # -----------------------------------------------------
    # NEXT AVAILABLE PLAYER
    # -----------------------------------------------------

    if (
        index + 1
        <
        len(
            position_players
        )
    ):

        next_player = (
            position_players[
                index + 1
            ]
        )

    else:

        next_player = None


    if next_player is None:

        return (
            1.0,
            None,
        )


    current_vorp = (
        numeric(
            current[
                "vorp"
            ]
        )
    )


    next_vorp = (
        numeric(
            next_player[
                "vorp"
            ]
        )
    )


    vorp_gap = max(
        0.0,
        current_vorp
        -
        next_vorp,
    )


    denominator = max(
        abs(
            current_vorp
        ),
        25.0,
    )


    gap_score = clamp(
        vorp_gap
        /
        denominator
    )


    # -----------------------------------------------------
    # NEARBY ALTERNATIVES
    #
    # Count players within 15 VORP.
    # -----------------------------------------------------

    nearby = 0


    for candidate in (
        position_players[
            index + 1:
        ]
    ):

        candidate_vorp = (
            numeric(
                candidate[
                    "vorp"
                ]
            )
        )


        if (
            current_vorp
            -
            candidate_vorp
            <= 15
        ):

            nearby += 1

        else:

            break


    alternative_pressure = (
        1.0
        -
        clamp(
            nearby
            /
            4.0
        )
    )


    scarcity = (
        0.70
        * gap_score
        +
        0.30
        * alternative_pressure
    )


    scarcity = (
        clamp(
            scarcity
        )
    )


    return (
        scarcity,
        next_player,
    )


# =========================================================
# STRATEGY LABEL
# =========================================================

def recommendation_strategy(
    expected_market,
    ceiling,
    need,
):

    if ceiling >= (
        expected_market
        * 1.08
    ):

        if need >= 0.80:

            return "AGGRESSIVE BUY"

        return "PURSUE"


    if ceiling >= expected_market:

        return "BUY AT MARKET"


    if ceiling >= (
        expected_market
        * 0.90
    ):

        return "DISCIPLINED"


    return "LET SOMEONE ELSE PAY"


# =========================================================
# FINAL RECOMMENDATION ENGINE
# =========================================================

def calculate_bid_recommendations(
    available_players,
    auction_values,
    market_values,
    player_values,
    threat_summaries,
    team_need_profiles,
    my_manager_id,
    run_hot_position_pressure=None,
) -> List[
    BidRecommendation
]:

    auction_lookup = (
        build_value_lookup(
            auction_values
        )
    )

    market_lookup = (
        build_value_lookup(
            market_values
        )
    )

    vorp_lookup = (
        build_value_lookup(
            player_values
        )
    )

    threat_lookup = (
        build_value_lookup(
            threat_summaries
        )
    )

    run_hot_position_pressure = run_hot_position_pressure or {}


    alternatives_by_position = (
        build_position_alternatives(
            available_players=(
                available_players
            ),
            player_values=(
                player_values
            ),
            market_values=(
                market_values
            ),
        )
    )


    my_team = (
        team_need_profiles.get(
            my_manager_id
        )
    )


    if my_team is None:

        return []


    legal_max = int(
        my_team.max_bid
    )


    results = []


    for player in available_players:

        key = (
            normalize_player_name(
                player.player_name
            )
        )


        auction_value = (
            auction_lookup.get(
                key
            )
        )


        market_value = (
            market_lookup.get(
                key
            )
        )


        player_value = (
            vorp_lookup.get(
                key
            )
        )


        threat = (
            threat_lookup.get(
                key
            )
        )


        if auction_value is None:

            continue


        baseline = (
            numeric(
                auction_value
                .baseline_value,
                1.0,
            )
        )


        if market_value:

            expected_market = (
                numeric(
                    market_value
                    .expected_market_value,
                    baseline,
                )
            )

        else:

            expected_market = (
                baseline
            )


        # =================================================
        # PERSONAL NEED
        # =================================================

        need = (
            my_team
            .need_scores
            .get(
                player.position,
                0.0,
            )
        )


        # =================================================
        # SCARCITY / NEXT OPTION
        # =================================================

        (
            scarcity,
            next_player,
        ) = calculate_scarcity(
            player_name=(
                player.player_name
            ),
            position=(
                player.position
            ),
            alternatives_by_position=(
                alternatives_by_position
            ),
        )


        # =================================================
        # COMPETITION
        # =================================================

        threat_score = (
            numeric(
                threat.top_threat_score
            )
            if threat
            else 0.0
        )


        threat_fraction = (
            clamp(
                threat_score
                /
                100.0
            )
        )


        # =================================================
        # FAIR VALUE ANCHOR
        #
        # Market gets more weight because that estimates
        # what this specific league will pay.
        #
        # Baseline prevents league behavior from causing
        # us to blindly follow historical overpayment.
        # =================================================

        fair_anchor = (
            0.65
            * expected_market
            +
            0.35
            * baseline
        )


        # =================================================
        # NEED ADJUSTMENT
        #
        # Low need can push us below market.
        # High need allows modest premium.
        # =================================================

        need_multiplier = (
            0.92
            +
            0.13
            * need
        )


        # =================================================
        # SCARCITY ADJUSTMENT
        # =================================================

        scarcity_multiplier = (
            1.0
            +
            0.10
            * scarcity
        )


        # =================================================
        # BIDDER PRESSURE
        #
        # Competition alone should NOT cause us to wildly
        # overpay.
        #
        # It only matters when:
        # - we need the player
        # - alternatives are scarce
        # =================================================

        competition_premium = (
            0.03
            *
            threat_fraction
            *
            need
            *
            scarcity
        )


        competition_multiplier = (
            1.0
            +
            competition_premium
        )

        run_hot_pressure = clamp(
            numeric(run_hot_position_pressure.get(player.position, 0.0))
        )
        run_hot_multiplier = 1.0 + 0.05 * run_hot_pressure * need * scarcity


        # =================================================
        # RAW PERSONAL CEILING
        # =================================================

        raw_ceiling = (
            fair_anchor
            *
            need_multiplier
            *
            scarcity_multiplier
            *
            competition_multiplier
            *
            run_hot_multiplier
        )


        # =================================================
        # PREVENT RUNAWAY OVERPAYMENT
        # =================================================

        market_cap = (
            expected_market
            *
            MAX_MARKET_PREMIUM
        )


        raw_ceiling = min(
            raw_ceiling,
            market_cap,
        )


        # =================================================
        # LEGAL MAX BID
        # =================================================

        final_ceiling = min(
            raw_ceiling,
            legal_max,
        )


        do_not_exceed = max(
            1,
            int(
                round(
                    final_ceiling
                )
            ),
        )


        # =================================================
        # VALUE EDGE
        # =================================================

        value_edge = (
            do_not_exceed
            -
            expected_market
        )


        # =================================================
        # NEXT OPTION
        # =================================================

        alternative_name = None

        alternative_market = None

        alternative_vorp = None


        if next_player:

            alternative_name = (
                next_player[
                    "player_name"
                ]
            )

            alternative_market = (
                numeric(
                    next_player[
                        "market"
                    ]
                )
            )

            alternative_vorp = (
                numeric(
                    next_player[
                        "vorp"
                    ]
                )
            )


        # =================================================
        # EXPLANATION
        # =================================================

        reasons = []


        if need >= 0.95:

            reasons.append(
                f"major {player.position} need"
            )

        elif need >= 0.75:

            reasons.append(
                f"meaningful {player.position} need"
            )

        elif need <= 0.25:

            reasons.append(
                f"low {player.position} need"
            )


        if scarcity >= 0.70:

            reasons.append(
                "major drop to next option"
            )

        elif scarcity >= 0.40:

            reasons.append(
                "limited alternatives"
            )

        elif scarcity <= 0.20:

            reasons.append(
                "similar alternatives remain"
            )


        if threat_score >= 75:

            reasons.append(
                "very strong bidder competition"
            )

        elif threat_score >= 60:

            reasons.append(
                "strong bidder competition"
            )

        if run_hot_pressure >= 0.5:
            reasons.append("cash-rich teams overlap on a scarce positional tier")


        if baseline > (
            expected_market
            * 1.08
        ):

            reasons.append(
                "model value exceeds expected market"
            )


        if expected_market > (
            baseline
            * 1.15
        ):

            reasons.append(
                "market appears expensive versus model"
            )


        if (
            do_not_exceed
            >= legal_max
        ):

            reasons.append(
                "limited by legal max bid"
            )


        if next_player:

            reasons.append(
                (
                    f"next {player.position}: "
                    f"{alternative_name}"
                )
            )


        strategy = (
            recommendation_strategy(
                expected_market=(
                    expected_market
                ),
                ceiling=(
                    do_not_exceed
                ),
                need=(
                    need
                ),
            )
        )


        results.append(
            BidRecommendation(
                player_name=(
                    player.player_name
                ),
                position=(
                    player.position
                ),
                expected_market_value=(
                    expected_market
                ),
                baseline_value=(
                    baseline
                ),
                do_not_exceed=(
                    do_not_exceed
                ),
                legal_max_bid=(
                    legal_max
                ),
                my_need_score=(
                    need
                ),
                scarcity_score=(
                    scarcity
                ),
                threat_score=(
                    threat_score
                ),
                value_edge=(
                    value_edge
                ),
                alternative_player=(
                    alternative_name
                ),
                alternative_market_value=(
                    alternative_market
                ),
                alternative_vorp=(
                    alternative_vorp
                ),
                player_vorp=(
                    player_value.vorp
                    if player_value
                    else None
                ),
                strategy=(
                    strategy
                ),
                reasons=(
                    reasons
                ),
            )
        )


    return results


# =========================================================
# INDEX
# =========================================================

def build_recommendation_index(
    recommendations,
):

    return {
        normalize_player_name(
            recommendation.player_name
        ): recommendation

        for recommendation
        in recommendations
    }
