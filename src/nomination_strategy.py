from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.auction_pool import normalize_player_name
from src.live_learning import price_tier


# =========================================================
# DATA OBJECT
# =========================================================

@dataclass
class NominationRecommendation:

    player_name: str
    position: str

    nomination_score: float
    action: str
    target_manager_id: Optional[str]
    reason: str

    expected_market_value: float
    do_not_exceed: int

    my_need_score: float
    my_interest_score: float

    opponent_need_score: float
    competition_score: float
    cash_drain_score: float

    live_market_heat: float

    top_opponent_id: Optional[str]
    top_opponent_threat: float

    affordable_bidders: int
    high_threat_bidders: int

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


def build_lookup(
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
# PERSONAL INTEREST
# =========================================================

def calculate_my_interest(
    recommendation,
):

    expected_market = max(
        1.0,
        numeric(
            recommendation
            .expected_market_value,
            1.0,
        ),
    )


    ceiling = numeric(
        recommendation
        .do_not_exceed,
        expected_market,
    )


    need = clamp(
        recommendation
        .my_need_score
    )


    # -----------------------------------------------------
    # HOW FAR ABOVE MARKET WE ARE WILLING TO GO
    # -----------------------------------------------------

    premium = (
        ceiling
        -
        expected_market
    ) / expected_market


    value_interest = clamp(
        (
            premium
            +
            0.10
        )
        /
        0.25
    )


    # -----------------------------------------------------
    # STRATEGY SIGNAL
    # -----------------------------------------------------

    strategy = str(
        recommendation.strategy
    ).upper()


    strategy_scores = {
        "AGGRESSIVE BUY": 1.00,
        "PURSUE": 0.85,
        "BUY AT MARKET": 0.70,
        "DISCIPLINED": 0.40,
        "LET SOMEONE ELSE PAY": 0.05,
    }


    strategy_interest = (
        strategy_scores.get(
            strategy,
            0.40,
        )
    )


    # -----------------------------------------------------
    # COMBINE
    # -----------------------------------------------------

    interest = (
        0.45
        * need
        +
        0.30
        * value_interest
        +
        0.25
        * strategy_interest
    )


    return clamp(
        interest
    )


# =========================================================
# LIVE MARKET HEAT
# =========================================================

def calculate_market_heat(
    player_name,
    position,
    expected_market_value,
    market_lookup,
    live_calibration,
):

    key = (
        normalize_player_name(
            player_name
        )
    )


    market = (
        market_lookup.get(
            key
        )
    )


    if market:

        live_multiplier = numeric(
            getattr(
                market,
                "live_multiplier",
                1.0,
            ),
            1.0,
        )

    else:

        live_multiplier = 1.0


    position_signal = (
        live_calibration
        .position_signals
        .get(
            position
        )
    )


    position_multiplier = (
        position_signal.multiplier
        if position_signal
        else 1.0
    )


    tier = (
        price_tier(
            expected_market_value
        )
    )


    tier_signal = (
        live_calibration
        .tier_signals
        .get(
            tier
        )
    )


    tier_multiplier = (
        tier_signal.multiplier
        if tier_signal
        else 1.0
    )


    heat = (
        0.50
        * live_multiplier
        +
        0.30
        * position_multiplier
        +
        0.20
        * tier_multiplier
    )


    return heat


# =========================================================
# ACTION LABEL
# =========================================================

def nomination_action(
    score,
    my_interest,
    market_heat,
):

    # -----------------------------------------------------
    # WE WANT HIM + MARKET IS SOFT
    # -----------------------------------------------------

    if (
        my_interest >= 0.65
        and
        market_heat <= 0.97
    ):

        return "BUY WINDOW"


    # -----------------------------------------------------
    # WE WANT HIM + MARKET IS HOT
    # -----------------------------------------------------

    if (
        my_interest >= 0.65
        and
        market_heat >= 1.03
    ):

        return "HOLD YOUR TARGET"


    # -----------------------------------------------------
    # CASH-DRAIN NOMINATIONS
    # -----------------------------------------------------

    if (
        score >= 75
        and
        my_interest <= 0.45
    ):

        return "DRAIN THE ROOM"


    if score >= 65:

        return "STRONG NOMINATION"


    if score >= 50:

        return "SOLID NOMINATION"


    if my_interest >= 0.65:

        return "PROTECT TARGET"


    return "LOW PRIORITY"


def nomination_strategy_mode(
    my_interest: float,
    market_heat: float,
    opponent_need: float,
    cash_drain: float,
    competition_score: float,
    top_opponent_id: Optional[str],
) -> str:
    """Choose one of the five explicit nomination strategies."""

    if my_interest >= 0.65:
        if market_heat <= 0.97:
            return "ACQUIRE TARGET"
        return "HIDE NEED"

    if top_opponent_id and opponent_need >= 0.70:
        return "ATTACK MANAGER"

    if cash_drain >= 0.62:
        return "DRAIN CASH"

    return "CREATE CHAOS"


# =========================================================
# NOMINATION ENGINE
# =========================================================

def calculate_nomination_recommendations(
    recommendations,
    threat_summaries,
    market_values,
    live_team_setups,
    live_calibration,
    my_manager_id,
) -> List[
    NominationRecommendation
]:

    threat_lookup = (
        build_lookup(
            threat_summaries
        )
    )


    market_lookup = (
        build_lookup(
            market_values
        )
    )


    if not recommendations:

        return []


    # =====================================================
    # NORMALIZATION BASELINES
    # =====================================================

    max_market_value = max(
        [
            numeric(
                recommendation
                .expected_market_value
            )

            for recommendation
            in recommendations
        ]
        or [
            1.0
        ]
    )


    opponent_count = max(
        1,
        len(
            live_team_setups
        )
        - 1,
    )


    results = []


    for recommendation in recommendations:

        key = (
            normalize_player_name(
                recommendation
                .player_name
            )
        )


        threat_summary = (
            threat_lookup.get(
                key
            )
        )


        expected_market = max(
            1.0,
            numeric(
                recommendation
                .expected_market_value,
                1.0,
            ),
        )


        # =================================================
        # MY INTEREST
        # =================================================

        my_interest = (
            calculate_my_interest(
                recommendation
            )
        )


        my_need = clamp(
            recommendation
            .my_need_score
        )


        # =================================================
        # OPPONENT DEMAND
        # =================================================

        opponent_need = 0.0

        competition_score = 0.0

        top_opponent_id = None

        top_opponent_threat = 0.0

        affordable_bidders = 0

        high_threat_bidders = 0


        if threat_summary:

            top_opponent_id = (
                threat_summary
                .top_manager_id
            )


            top_opponent_threat = (
                numeric(
                    threat_summary
                    .top_threat_score
                )
            )


            affordable_bidders = (
                threat_summary
                .affordable_bidder_count
            )


            high_threat_bidders = (
                threat_summary
                .high_threat_count
            )


            # ---------------------------------------------
            # TOP 3 NEED SCORES
            # ---------------------------------------------

            top_needs = sorted(
                [
                    numeric(
                        threat.need_score
                    )

                    for threat
                    in threat_summary.threats

                    if (
                        threat.manager_id
                        != my_manager_id
                    )
                ],
                reverse=True,
            )[:3]


            if top_needs:

                weights = [
                    0.50,
                    0.30,
                    0.20,
                ]


                weighted_need = 0.0

                weight_used = 0.0


                for (
                    index,
                    value,
                ) in enumerate(
                    top_needs
                ):

                    weight = (
                        weights[
                            index
                        ]
                    )


                    weighted_need += (
                        value
                        *
                        weight
                    )


                    weight_used += (
                        weight
                    )


                if weight_used > 0:

                    opponent_need = (
                        weighted_need
                        /
                        weight_used
                    )


            affordability_pressure = clamp(
                affordable_bidders
                /
                max(
                    1,
                    opponent_count
                    * 0.60,
                )
            )


            high_threat_pressure = clamp(
                high_threat_bidders
                /
                4.0
            )


            top_threat_pressure = clamp(
                top_opponent_threat
                /
                100.0
            )


            competition_score = (
                0.45
                * top_threat_pressure
                +
                0.30
                * affordability_pressure
                +
                0.25
                * high_threat_pressure
            )


        # =================================================
        # CASH DRAIN POTENTIAL
        # =================================================

        market_size_score = clamp(
            expected_market
            /
            max(
                max_market_value,
                1.0,
            )
        )


        wealthy_opponent_score = 0.0


        if (
            top_opponent_id
            and
            top_opponent_id
            in live_team_setups
        ):

            opponent_state = (
                live_team_setups[
                    top_opponent_id
                ]
            )


            all_opponent_cash = [
                numeric(
                    setup.auction_cash
                )

                for (
                    manager_id,
                    setup,
                ) in (
                    live_team_setups.items()
                )

                if (
                    manager_id
                    != my_manager_id
                )
            ]


            max_opponent_cash = max(
                all_opponent_cash
                or [
                    1.0
                ]
            )


            wealthy_opponent_score = clamp(
                numeric(
                    opponent_state
                    .auction_cash
                )
                /
                max(
                    max_opponent_cash,
                    1.0,
                )
            )


        cash_drain = (
            0.55
            * market_size_score
            +
            0.25
            * competition_score
            +
            0.20
            * wealthy_opponent_score
        )


        # =================================================
        # LIVE MARKET HEAT
        # =================================================

        live_heat = (
            calculate_market_heat(
                player_name=(
                    recommendation
                    .player_name
                ),
                position=(
                    recommendation
                    .position
                ),
                expected_market_value=(
                    expected_market
                ),
                market_lookup=(
                    market_lookup
                ),
                live_calibration=(
                    live_calibration
                ),
            )
        )


        # Turn roughly 0.90x - 1.10x into 0 - 1.
        market_heat_score = clamp(
            (
                live_heat
                -
                0.90
            )
            /
            0.20
        )


        # =================================================
        # LOW PERSONAL INTEREST IS GOOD FOR BAIT
        # =================================================

        low_interest_score = (
            1.0
            -
            my_interest
        )


        # =================================================
        # NOMINATION SCORE
        # =================================================

        nomination_score = (
            0.30
            * opponent_need
            +
            0.25
            * cash_drain
            +
            0.20
            * competition_score
            +
            0.10
            * market_heat_score
            +
            0.15
            * low_interest_score
        )


        nomination_score = (
            clamp(
                nomination_score
            )
            *
            100.0
        )


        # =================================================
        # TARGET PROTECTION
        # =================================================

        if (
            my_interest >= 0.70
            and
            live_heat >= 1.00
        ):

            nomination_score *= 0.65


        # =================================================
        # BUY WINDOW
        #
        # A player we like in a soft room is intentionally
        # surfaced despite the normal target-protection
        # penalty.
        # =================================================

        if (
            my_interest >= 0.65
            and
            live_heat <= 0.97
        ):

            nomination_score = max(
                nomination_score,
                68.0,
            )


        nomination_score = min(
            100.0,
            nomination_score,
        )


        action = nomination_strategy_mode(
            my_interest=my_interest,
            market_heat=live_heat,
            opponent_need=opponent_need,
            cash_drain=cash_drain,
            competition_score=competition_score,
            top_opponent_id=top_opponent_id,
        )


        # =================================================
        # REASONS
        # =================================================

        reasons = []


        if opponent_need >= 0.80:

            reasons.append(
                "multiple opponents have strong positional need"
            )

        elif opponent_need >= 0.60:

            reasons.append(
                "meaningful opponent positional demand"
            )


        if affordable_bidders >= 6:

            reasons.append(
                f"{affordable_bidders} opponents can afford market"
            )

        elif affordable_bidders >= 3:

            reasons.append(
                f"{affordable_bidders} viable bidders"
            )


        if high_threat_bidders >= 3:

            reasons.append(
                "several high-threat bidders"
            )


        if cash_drain >= 0.70:

            reasons.append(
                "strong opportunity to remove opponent cash"
            )


        if my_interest <= 0.30:

            reasons.append(
                "low value to your roster"
            )

        elif my_interest >= 0.70:

            reasons.append(
                "important target for your roster"
            )


        if live_heat >= 1.05:

            reasons.append(
                "2026 market is running hot for this asset"
            )

        elif live_heat <= 0.95:

            reasons.append(
                "2026 market currently looks soft"
            )


        if action == "HIDE NEED":

            reasons.append(
                "avoid exposing your target while competition is expensive"
            )


        if action == "ACQUIRE TARGET":

            reasons.append(
                "soft market may justify nominating your own target now"
            )


        reason = (
            reasons[0]
            if reasons
            else "creates uncertainty without exposing a priority target"
        )

        results.append(
            NominationRecommendation(
                player_name=(
                    recommendation.player_name
                ),
                position=(
                    recommendation.position
                ),
                nomination_score=(
                    nomination_score
                ),
                action=(
                    action
                ),
                target_manager_id=(
                    top_opponent_id
                    if action in ("ATTACK MANAGER", "DRAIN CASH")
                    else None
                ),
                reason=reason,
                expected_market_value=(
                    expected_market
                ),
                do_not_exceed=(
                    recommendation
                    .do_not_exceed
                ),
                my_need_score=(
                    my_need
                ),
                my_interest_score=(
                    my_interest
                ),
                opponent_need_score=(
                    opponent_need
                ),
                competition_score=(
                    competition_score
                ),
                cash_drain_score=(
                    cash_drain
                ),
                live_market_heat=(
                    live_heat
                ),
                top_opponent_id=(
                    top_opponent_id
                ),
                top_opponent_threat=(
                    top_opponent_threat
                ),
                affordable_bidders=(
                    affordable_bidders
                ),
                high_threat_bidders=(
                    high_threat_bidders
                ),
                reasons=(
                    reasons
                ),
            )
        )


    results.sort(
        key=lambda value: (
            value.nomination_score
        ),
        reverse=True,
    )


    return results


# =========================================================
# INDEX
# =========================================================

def build_nomination_index(
    nominations,
):

    return {
        normalize_player_name(
            recommendation.player_name
        ): recommendation

        for recommendation
        in nominations
    }
