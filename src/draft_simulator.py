import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.auction_pool import normalize_player_name

from src.auction_values import (
    calculate_auction_values,
)

from src.bidder_threat import (
    build_team_need_profiles,
    calculate_bidder_threats,
)

from src.historical_market import (
    calculate_historical_market_values,
)

from src.live_draft import (
    add_live_sale,
    build_live_team_setups,
    calculate_room_spend_index,
    filter_sold_players,
)

from src.live_learning import (
    apply_live_manager_threat_adjustments,
    apply_live_market_calibration,
    build_live_market_calibration,
)

from src.nomination_strategy import (
    calculate_nomination_recommendations,
)

from src.recommendation import (
    calculate_bid_recommendations,
)

from src.roster_optimizer import (
    build_optimization_candidates,
    calculate_roster_aware_ceiling,
    optimize_remaining_roster,
)


# =========================================================
# RESULT OBJECTS
# =========================================================

@dataclass
class SimulationStep:
    sale_number: int

    player_name: str
    position: str

    manager_id: str

    price: int
    expected_market_value: float

    player_ceiling: int
    roster_aware_ceiling: Optional[int]

    winner_pre_sale_cash: int
    winner_pre_sale_open_spots: int
    winner_pre_sale_max_bid: int

    remaining_cash: int
    remaining_open_spots: int

    room_spend_index: Optional[float]
    live_room_multiplier: float

    optimizer_feasible: bool
    optimizer_utility: Optional[float]

    top_nomination: Optional[str]

    violations: List[str] = field(
        default_factory=list
    )


@dataclass
class SimulationResult:
    seed: int

    requested_sales: int
    completed_sales: int

    steps: List[
        SimulationStep
    ]

    simulated_sales: List

    violations: List[
        str
    ]

    final_team_setups: Dict

    final_position_signals: Dict[
        str,
        float,
    ]

    final_manager_signals: Dict[
        str,
        float,
    ]

    final_room_spend_index: Optional[float]

    final_optimizer_feasible: bool

    stopped_reason: Optional[str] = None


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


    return value


def weighted_choice(
    rng,
    items,
    weights,
):

    if not items:

        return None


    safe_weights = [
        max(
            0.0001,
            numeric(
                weight,
                0.0001,
            ),
        )

        for weight
        in weights
    ]


    total = sum(
        safe_weights
    )


    if total <= 0:

        return rng.choice(
            items
        )


    target = (
        rng.random()
        *
        total
    )


    running = 0.0


    for (
        item,
        weight,
    ) in zip(
        items,
        safe_weights,
    ):

        running += (
            weight
        )


        if (
            running
            >=
            target
        ):

            return item


    return items[
        -1
    ]


# =========================================================
# BUILD CURRENT ENGINE STATE
# =========================================================

def build_simulation_state(
    starting_team_setups,
    starting_pool_players,
    sales,
    sleeper_players,
    player_values,
    projection_index,
    fantasypros_index,
    historical_market_model,
    starting_total_auction_cash,
    my_manager_id,
):

    # =====================================================
    # LIVE TEAM STATE
    # =====================================================

    live_team_setups = (
        build_live_team_setups(
            starting_team_setups=(
                starting_team_setups
            ),
            sales=(
                sales
            ),
        )
    )


    # =====================================================
    # REMAINING PLAYER POOL
    # =====================================================

    available_players = (
        filter_sold_players(
            available_players=(
                starting_pool_players
            ),
            sales=(
                sales
            ),
        )
    )


    # =====================================================
    # LIVE LEARNING
    # =====================================================

    live_calibration = (
        build_live_market_calibration(
            sales
        )
    )


    # =====================================================
    # BASELINE VALUES
    # =====================================================

    auction_values = []


    if available_players:

        auction_values = (
            calculate_auction_values(
                available_players=(
                    available_players
                ),
                team_setups=(
                    live_team_setups
                ),
                player_values=(
                    player_values
                ),
                projection_index=(
                    projection_index
                ),
                fantasypros_index=(
                    fantasypros_index
                ),
            )
        )


    # =====================================================
    # HISTORICAL MARKET
    # =====================================================

    market_values = []


    if auction_values:

        market_values = (
            calculate_historical_market_values(
                auction_values=(
                    auction_values
                ),
                historical_model=(
                    historical_market_model
                ),
                current_total_auction_cash=(
                    starting_total_auction_cash
                ),
            )
        )


        market_values = (
            apply_live_market_calibration(
                market_values=(
                    market_values
                ),
                auction_values=(
                    auction_values
                ),
                calibration=(
                    live_calibration
                ),
            )
        )


    # =====================================================
    # NEEDS
    # =====================================================

    team_need_profiles = (
        build_team_need_profiles(
            team_setups=(
                live_team_setups
            ),
            sleeper_players=(
                sleeper_players
            ),
        )
    )


    # =====================================================
    # THREATS
    # =====================================================

    threat_summaries = []


    if auction_values:

        threat_summaries = (
            calculate_bidder_threats(
                available_players=(
                    available_players
                ),
                auction_values=(
                    auction_values
                ),
                market_values=(
                    market_values
                ),
                team_need_profiles=(
                    team_need_profiles
                ),
                historical_model=(
                    historical_market_model
                ),
                excluded_manager_id=(
                    my_manager_id
                ),
            )
        )


        threat_summaries = (
            apply_live_manager_threat_adjustments(
                threat_summaries=(
                    threat_summaries
                ),
                calibration=(
                    live_calibration
                ),
            )
        )


    # =====================================================
    # RECOMMENDATIONS
    # =====================================================

    recommendations = []


    if auction_values:

        recommendations = (
            calculate_bid_recommendations(
                available_players=(
                    available_players
                ),
                auction_values=(
                    auction_values
                ),
                market_values=(
                    market_values
                ),
                player_values=(
                    player_values
                ),
                threat_summaries=(
                    threat_summaries
                ),
                team_need_profiles=(
                    team_need_profiles
                ),
                my_manager_id=(
                    my_manager_id
                ),
            )
        )


    # =====================================================
    # NOMINATION STRATEGY
    # =====================================================

    nomination_recommendations = []


    if recommendations:

        nomination_recommendations = (
            calculate_nomination_recommendations(
                recommendations=(
                    recommendations
                ),
                threat_summaries=(
                    threat_summaries
                ),
                market_values=(
                    market_values
                ),
                live_team_setups=(
                    live_team_setups
                ),
                live_calibration=(
                    live_calibration
                ),
                my_manager_id=(
                    my_manager_id
                ),
            )
        )


    # =====================================================
    # ROSTER OPTIMIZER
    # =====================================================

    optimization_candidates = []


    if auction_values:

        optimization_candidates = (
            build_optimization_candidates(
                available_players=(
                    available_players
                ),
                auction_values=(
                    auction_values
                ),
                market_values=(
                    market_values
                ),
                recommendations=(
                    recommendations
                ),
                player_values=(
                    player_values
                ),
            )
        )


    my_live_setup = (
        live_team_setups.get(
            my_manager_id
        )
    )


    my_need_profile = (
        team_need_profiles.get(
            my_manager_id
        )
    )


    optimal_roster_plan = None


    if (
        my_live_setup
        and
        my_need_profile
        and
        optimization_candidates
    ):

        optimal_roster_plan = (
            optimize_remaining_roster(
                my_team_setup=(
                    my_live_setup
                ),
                my_need_profile=(
                    my_need_profile
                ),
                candidates=(
                    optimization_candidates
                ),
            )
        )


    return {
        "live_team_setups": (
            live_team_setups
        ),

        "available_players": (
            available_players
        ),

        "live_calibration": (
            live_calibration
        ),

        "auction_values": (
            auction_values
        ),

        "market_values": (
            market_values
        ),

        "team_need_profiles": (
            team_need_profiles
        ),

        "threat_summaries": (
            threat_summaries
        ),

        "recommendations": (
            recommendations
        ),

        "nomination_recommendations": (
            nomination_recommendations
        ),

        "optimization_candidates": (
            optimization_candidates
        ),

        "optimal_roster_plan": (
            optimal_roster_plan
        ),
    }


# =========================================================
# CHOOSE NOMINATED / SOLD PLAYER
# =========================================================

def choose_simulated_player(
    rng,
    recommendations,
    nomination_recommendations,
):

    if not recommendations:

        return None


    recommendation_lookup = {
        normalize_player_name(
            recommendation.player_name
        ): recommendation

        for recommendation
        in recommendations
    }


    nomination_lookup = {
        normalize_player_name(
            nomination.player_name
        ): nomination

        for nomination
        in nomination_recommendations
    }


    # =====================================================
    # MOST SIMULATED SALES COME FROM RELEVANT PLAYERS,
    # BUT WE STILL ALLOW RANDOM MID/LOW-TIER NOMINATIONS.
    # =====================================================

    candidates = sorted(
        recommendations,
        key=lambda recommendation: (
            numeric(
                recommendation
                .expected_market_value
            )
        ),
        reverse=True,
    )


    candidate_limit = min(
        80,
        len(
            candidates
        ),
    )


    candidates = candidates[
        :candidate_limit
    ]


    weights = []


    for recommendation in candidates:

        key = (
            normalize_player_name(
                recommendation.player_name
            )
        )


        nomination = (
            nomination_lookup.get(
                key
            )
        )


        market_value = max(
            1.0,
            numeric(
                recommendation
                .expected_market_value,
                1.0,
            ),
        )


        nomination_score = (
            numeric(
                nomination.nomination_score
            )
            if nomination
            else 25.0
        )


        # -------------------------------------------------
        # Expensive players are somewhat more likely early,
        # but not overwhelmingly so.
        # -------------------------------------------------

        market_weight = (
            math.sqrt(
                market_value
            )
        )


        nomination_weight = (
            1.0
            +
            nomination_score
            /
            100.0
        )


        noise = (
            0.80
            +
            rng.random()
            *
            0.40
        )


        weights.append(
            market_weight
            *
            nomination_weight
            *
            noise
        )


    return weighted_choice(
        rng=(
            rng
        ),
        items=(
            candidates
        ),
        weights=(
            weights
        ),
    )


# =========================================================
# GENERATE SIMULATED PRICE
# =========================================================

def generate_simulated_price(
    rng,
    expected_market_value,
    live_team_setups,
):

    expected_market = max(
        1.0,
        numeric(
            expected_market_value,
            1.0,
        ),
    )


    # =====================================================
    # PRICE NOISE
    #
    # Most sales land reasonably close to modeled market,
    # with enough variation to stress live learning.
    # =====================================================

    ratio = rng.gauss(
        1.00,
        0.13,
    )


    ratio = clamp(
        ratio,
        0.68,
        1.38,
    )


    proposed = max(
        1,
        int(
            round(
                expected_market
                *
                ratio
            )
        ),
    )


    legal_maxes = [
        int(
            setup.max_bid
        )

        for setup
        in live_team_setups.values()

        if (
            setup.open_roster_spots
            >
            0
            and
            setup.max_bid
            >= 1
        )
    ]


    if not legal_maxes:

        return None


    league_max = max(
        legal_maxes
    )


    return min(
        proposed,
        league_max,
    )


# =========================================================
# CALCULATE MANAGER WIN WEIGHT
# =========================================================

def manager_win_weight(
    manager_id,
    position,
    sale_price,
    live_team_setups,
    team_need_profiles,
    historical_market_model,
    live_calibration,
    my_manager_id,
    recommendation,
    roster_aware_ceiling,
):

    team = (
        live_team_setups.get(
            manager_id
        )
    )


    if team is None:

        return 0.0


    if (
        team.open_roster_spots
        <= 0
    ):

        return 0.0


    if (
        team.max_bid
        <
        sale_price
    ):

        return 0.0


    # =====================================================
    # USER SHOULD OBEY THE COPILOT
    # =====================================================

    if (
        manager_id
        ==
        my_manager_id
    ):

        if (
            roster_aware_ceiling
            is not None
            and
            sale_price
            >
            roster_aware_ceiling
        ):

            return 0.0


    need_profile = (
        team_need_profiles.get(
            manager_id
        )
    )


    need_score = 0.20


    if need_profile:

        need_score = numeric(
            need_profile
            .need_scores
            .get(
                position,
                0.20,
            ),
            0.20,
        )


    # =====================================================
    # CASH STRENGTH
    # =====================================================

    max_cash = max(
        [
            numeric(
                setup.auction_cash
            )

            for setup
            in live_team_setups.values()
        ]
        or [
            1.0
        ]
    )


    cash_strength = (
        numeric(
            team.auction_cash
        )
        /
        max(
            max_cash,
            1.0,
        )
    )


    # =====================================================
    # HISTORICAL AGGRESSION
    # =====================================================

    historical_profile = (
        historical_market_model
        .manager_profiles
        .get(
            manager_id
        )
    )


    historical_aggression = (
        numeric(
            historical_profile
            .aggressiveness_index,
            1.0,
        )
        if historical_profile
        else 1.0
    )


    # =====================================================
    # CURRENT AUCTION AGGRESSION
    # =====================================================

    live_profile = (
        live_calibration
        .manager_profiles
        .get(
            manager_id
        )
    )


    live_aggression = (
        numeric(
            live_profile.multiplier,
            1.0,
        )
        if live_profile
        else 1.0
    )


    weight = (
        0.40
        +
        2.00
        *
        need_score
        +
        0.50
        *
        cash_strength
        +
        0.70
        *
        max(
            historical_aggression
            -
            0.70,
            0.0,
        )
        +
        0.80
        *
        max(
            live_aggression
            -
            0.80,
            0.0,
        )
    )


    # =====================================================
    # USER STRATEGY
    # =====================================================

    if (
        manager_id
        ==
        my_manager_id
    ):

        strategy = str(
            recommendation.strategy
        ).upper()


        strategy_multiplier = {
            "AGGRESSIVE BUY": 1.55,
            "PURSUE": 1.35,
            "BUY AT MARKET": 1.15,
            "DISCIPLINED": 0.80,
            "LET SOMEONE ELSE PAY": 0.20,
        }.get(
            strategy,
            0.80,
        )


        weight *= (
            strategy_multiplier
        )


    return max(
        0.01,
        weight,
    )


# =========================================================
# CHOOSE WINNING MANAGER
# =========================================================

def choose_simulated_winner(
    rng,
    player_position,
    sale_price,
    live_team_setups,
    team_need_profiles,
    historical_market_model,
    live_calibration,
    my_manager_id,
    recommendation,
    roster_aware_ceiling,
):

    manager_ids = []

    weights = []


    for manager_id in (
        live_team_setups.keys()
    ):

        weight = (
            manager_win_weight(
                manager_id=(
                    manager_id
                ),
                position=(
                    player_position
                ),
                sale_price=(
                    sale_price
                ),
                live_team_setups=(
                    live_team_setups
                ),
                team_need_profiles=(
                    team_need_profiles
                ),
                historical_market_model=(
                    historical_market_model
                ),
                live_calibration=(
                    live_calibration
                ),
                my_manager_id=(
                    my_manager_id
                ),
                recommendation=(
                    recommendation
                ),
                roster_aware_ceiling=(
                    roster_aware_ceiling
                ),
            )
        )


        if weight > 0:

            manager_ids.append(
                manager_id
            )

            weights.append(
                weight
            )


    return weighted_choice(
        rng=(
            rng
        ),
        items=(
            manager_ids
        ),
        weights=(
            weights
        ),
    )


# =========================================================
# VALIDATE CURRENT SIMULATION STATE
# =========================================================

def validate_simulation_state(
    starting_team_setups,
    live_team_setups,
    sales,
):

    violations = []


    # =====================================================
    # SALE NUMBERS
    # =====================================================

    expected_numbers = list(
        range(
            1,
            len(
                sales
            )
            +
            1,
        )
    )


    actual_numbers = [
        sale.sale_number

        for sale
        in sales
    ]


    if (
        actual_numbers
        !=
        expected_numbers
    ):

        violations.append(
            "Sale numbers are not sequential."
        )


    # =====================================================
    # DUPLICATE PLAYERS
    # =====================================================

    sold_keys = [
        normalize_player_name(
            sale.player_name
        )

        for sale
        in sales
    ]


    if (
        len(
            sold_keys
        )
        !=
        len(
            set(
                sold_keys
            )
        )
    ):

        violations.append(
            "Duplicate player sale detected."
        )


    # =====================================================
    # CASH CONSERVATION
    # =====================================================

    starting_cash = sum(
        setup.auction_cash

        for setup
        in starting_team_setups.values()
    )


    actual_spend = sum(
        sale.price

        for sale
        in sales
    )


    expected_remaining_cash = (
        starting_cash
        -
        actual_spend
    )


    actual_remaining_cash = sum(
        setup.auction_cash

        for setup
        in live_team_setups.values()
    )


    if (
        actual_remaining_cash
        !=
        expected_remaining_cash
    ):

        violations.append(
            (
                "Cash conservation failure: "
                f"expected ${expected_remaining_cash}, "
                f"found ${actual_remaining_cash}."
            )
        )


    # =====================================================
    # ROSTER SLOT CONSERVATION
    # =====================================================

    starting_spots = sum(
        setup.open_roster_spots

        for setup
        in starting_team_setups.values()
    )


    expected_open_spots = (
        starting_spots
        -
        len(
            sales
        )
    )


    actual_open_spots = sum(
        setup.open_roster_spots

        for setup
        in live_team_setups.values()
    )


    if (
        actual_open_spots
        !=
        expected_open_spots
    ):

        violations.append(
            (
                "Roster spot conservation failure: "
                f"expected {expected_open_spots}, "
                f"found {actual_open_spots}."
            )
        )


    # =====================================================
    # TEAM-LEVEL VALIDATION
    # =====================================================

    for (
        manager_id,
        setup,
    ) in live_team_setups.items():

        if (
            setup.auction_cash
            <
            0
        ):

            violations.append(
                (
                    f"{manager_id} has negative cash."
                )
            )


        if (
            setup.open_roster_spots
            <
            0
        ):

            violations.append(
                (
                    f"{manager_id} has negative "
                    f"open roster spots."
                )
            )


        if (
            setup.open_roster_spots
            >
            0
            and
            setup.auction_cash
            <
            setup.open_roster_spots
        ):

            violations.append(
                (
                    f"{manager_id} cannot reserve "
                    f"$1 for every open roster spot."
                )
            )


        if (
            setup.open_roster_spots
            >
            0
        ):

            expected_max_bid = (
                setup.auction_cash
                -
                (
                    setup.open_roster_spots
                    -
                    1
                )
            )


            if (
                setup.max_bid
                !=
                expected_max_bid
            ):

                violations.append(
                    (
                        f"{manager_id} legal max mismatch: "
                        f"expected ${expected_max_bid}, "
                        f"found ${setup.max_bid}."
                    )
                )


    return violations


# =========================================================
# RUN SIMULATION
# =========================================================

def run_draft_simulation(
    number_of_sales,
    seed,
    starting_team_setups,
    starting_pool_players,
    sleeper_players,
    player_values,
    projection_index,
    fantasypros_index,
    historical_market_model,
    starting_total_auction_cash,
    my_manager_id,
    initial_sales=None,
):

    rng = random.Random(
        int(
            seed
        )
    )


    simulated_sales = list(
        initial_sales
        or []
    )


    starting_sim_sale_count = len(
        simulated_sales
    )


    requested_sales = int(
        number_of_sales
    )


    simulation_steps = []

    all_violations = []

    stopped_reason = None


    # =====================================================
    # RUN N SALES
    # =====================================================

    for simulation_index in range(
        requested_sales
    ):

        # =================================================
        # BUILD THE EXACT CURRENT ENGINE STATE
        # =================================================

        try:

            state = (
                build_simulation_state(
                    starting_team_setups=(
                        starting_team_setups
                    ),
                    starting_pool_players=(
                        starting_pool_players
                    ),
                    sales=(
                        simulated_sales
                    ),
                    sleeper_players=(
                        sleeper_players
                    ),
                    player_values=(
                        player_values
                    ),
                    projection_index=(
                        projection_index
                    ),
                    fantasypros_index=(
                        fantasypros_index
                    ),
                    historical_market_model=(
                        historical_market_model
                    ),
                    starting_total_auction_cash=(
                        starting_total_auction_cash
                    ),
                    my_manager_id=(
                        my_manager_id
                    ),
                )
            )

        except Exception as error:

            stopped_reason = (
                "Engine-state rebuild failed: "
                f"{error}"
            )

            all_violations.append(
                stopped_reason
            )

            break


        recommendations = (
            state[
                "recommendations"
            ]
        )


        if not recommendations:

            stopped_reason = (
                "No recommendation candidates remained."
            )

            break


        # =================================================
        # PICK NEXT PLAYER
        # =================================================

        recommendation = (
            choose_simulated_player(
                rng=(
                    rng
                ),
                recommendations=(
                    recommendations
                ),
                nomination_recommendations=(
                    state[
                        "nomination_recommendations"
                    ]
                ),
            )
        )


        if recommendation is None:

            stopped_reason = (
                "Unable to select a player."
            )

            break


        player_name = (
            recommendation.player_name
        )


        position = normalize_position(
            recommendation.position
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
        # ROSTER-AWARE USER CEILING
        # =================================================

        roster_aware_ceiling = None


        my_setup = (
            state[
                "live_team_setups"
            ].get(
                my_manager_id
            )
        )


        my_need = (
            state[
                "team_need_profiles"
            ].get(
                my_manager_id
            )
        )


        if (
            my_setup
            and
            my_need
            and
            state[
                "optimization_candidates"
            ]
        ):

            try:

                (
                    calculated_ceiling,
                    _,
                ) = (
                    calculate_roster_aware_ceiling(
                        player_name=(
                            player_name
                        ),
                        my_team_setup=(
                            my_setup
                        ),
                        my_need_profile=(
                            my_need
                        ),
                        candidates=(
                            state[
                                "optimization_candidates"
                            ]
                        ),
                        existing_do_not_exceed=(
                            recommendation
                            .do_not_exceed
                        ),
                    )
                )


                if (
                    calculated_ceiling
                    >
                    0
                ):

                    roster_aware_ceiling = int(
                        calculated_ceiling
                    )

            except Exception:

                roster_aware_ceiling = None


        # =================================================
        # GENERATE SALE PRICE
        # =================================================

        sale_price = (
            generate_simulated_price(
                rng=(
                    rng
                ),
                expected_market_value=(
                    expected_market
                ),
                live_team_setups=(
                    state[
                        "live_team_setups"
                    ]
                ),
            )
        )


        if sale_price is None:

            stopped_reason = (
                "No manager can legally purchase "
                "another player."
            )

            break


        # =================================================
        # CHOOSE WINNER
        # =================================================

        winner_id = (
            choose_simulated_winner(
                rng=(
                    rng
                ),
                player_position=(
                    position
                ),
                sale_price=(
                    sale_price
                ),
                live_team_setups=(
                    state[
                        "live_team_setups"
                    ]
                ),
                team_need_profiles=(
                    state[
                        "team_need_profiles"
                    ]
                ),
                historical_market_model=(
                    historical_market_model
                ),
                live_calibration=(
                    state[
                        "live_calibration"
                    ]
                ),
                my_manager_id=(
                    my_manager_id
                ),
                recommendation=(
                    recommendation
                ),
                roster_aware_ceiling=(
                    roster_aware_ceiling
                ),
            )
        )


        # =================================================
        # IF GENERATED PRICE IS TOO HIGH FOR ALL
        # DISCIPLINED BIDDERS, LOWER UNTIL SOMEONE CAN WIN
        # =================================================

        if winner_id is None:

            price_attempt = int(
                sale_price
            )


            while (
                winner_id is None
                and
                price_attempt
                >
                1
            ):

                price_attempt -= 1


                winner_id = (
                    choose_simulated_winner(
                        rng=(
                            rng
                        ),
                        player_position=(
                            position
                        ),
                        sale_price=(
                            price_attempt
                        ),
                        live_team_setups=(
                            state[
                                "live_team_setups"
                            ]
                        ),
                        team_need_profiles=(
                            state[
                                "team_need_profiles"
                            ]
                        ),
                        historical_market_model=(
                            historical_market_model
                        ),
                        live_calibration=(
                            state[
                                "live_calibration"
                            ]
                        ),
                        my_manager_id=(
                            my_manager_id
                        ),
                        recommendation=(
                            recommendation
                        ),
                        roster_aware_ceiling=(
                            roster_aware_ceiling
                        ),
                    )
                )


            sale_price = (
                price_attempt
            )


        if winner_id is None:

            stopped_reason = (
                f"No legal winner found for "
                f"{player_name}."
            )

            all_violations.append(
                stopped_reason
            )

            break


        winner_pre_state = (
            state[
                "live_team_setups"
            ][
                winner_id
            ]
        )


        pre_cash = int(
            winner_pre_state
            .auction_cash
        )


        pre_spots = int(
            winner_pre_state
            .open_roster_spots
        )


        pre_max_bid = int(
            winner_pre_state
            .max_bid
        )


        # =================================================
        # RECORD IN-MEMORY SALE
        #
        # IMPORTANT: NO SQLITE CALL HERE.
        # =================================================

        try:

            simulated_sales = (
                add_live_sale(
                    starting_team_setups=(
                        starting_team_setups
                    ),
                    existing_sales=(
                        simulated_sales
                    ),
                    player_name=(
                        player_name
                    ),
                    position=(
                        position
                    ),
                    manager_id=(
                        winner_id
                    ),
                    price=(
                        int(
                            sale_price
                        )
                    ),
                    modeled_market_value=(
                        expected_market
                    ),
                    do_not_exceed=(
                        roster_aware_ceiling
                        if (
                            roster_aware_ceiling
                            is not None
                        )
                        else (
                            recommendation
                            .do_not_exceed
                        )
                    ),
                )
            )

        except Exception as error:

            stopped_reason = (
                f"Sale recording failed for "
                f"{player_name}: {error}"
            )

            all_violations.append(
                stopped_reason
            )

            break


        # =================================================
        # REBUILD EVERYTHING AFTER THE SALE
        # =================================================

        try:

            post_state = (
                build_simulation_state(
                    starting_team_setups=(
                        starting_team_setups
                    ),
                    starting_pool_players=(
                        starting_pool_players
                    ),
                    sales=(
                        simulated_sales
                    ),
                    sleeper_players=(
                        sleeper_players
                    ),
                    player_values=(
                        player_values
                    ),
                    projection_index=(
                        projection_index
                    ),
                    fantasypros_index=(
                        fantasypros_index
                    ),
                    historical_market_model=(
                        historical_market_model
                    ),
                    starting_total_auction_cash=(
                        starting_total_auction_cash
                    ),
                    my_manager_id=(
                        my_manager_id
                    ),
                )
            )

        except Exception as error:

            stopped_reason = (
                "Post-sale engine rebuild failed after "
                f"{player_name}: {error}"
            )

            all_violations.append(
                stopped_reason
            )

            break


        # =================================================
        # VALIDATE
        # =================================================

        step_violations = (
            validate_simulation_state(
                starting_team_setups=(
                    starting_team_setups
                ),
                live_team_setups=(
                    post_state[
                        "live_team_setups"
                    ]
                ),
                sales=(
                    simulated_sales
                ),
            )
        )


        # -------------------------------------------------
        # SPECIFIC SALE LEGAL MAX CHECK
        # -------------------------------------------------

        if (
            sale_price
            >
            pre_max_bid
        ):

            step_violations.append(
                (
                    f"{winner_id} paid "
                    f"${sale_price} but pre-sale "
                    f"legal max was ${pre_max_bid}."
                )
            )


        # =================================================
        # CURRENT OPTIMIZER STATUS
        # =================================================

        current_plan = (
            post_state[
                "optimal_roster_plan"
            ]
        )


        optimizer_feasible = bool(
            current_plan
            and
            current_plan.feasible
        )


        optimizer_utility = (
            current_plan.total_utility
            if (
                current_plan
                and
                current_plan.feasible
            )
            else None
        )


        # =================================================
        # CURRENT TOP NOMINATION
        # =================================================

        top_nomination = None


        if (
            post_state[
                "nomination_recommendations"
            ]
        ):

            top_nomination = (
                post_state[
                    "nomination_recommendations"
                ][
                    0
                ]
                .player_name
            )


        # =================================================
        # LIVE METRICS
        # =================================================

        remaining_cash = sum(
            setup.auction_cash

            for setup
            in (
                post_state[
                    "live_team_setups"
                ].values()
            )
        )


        remaining_open_spots = sum(
            setup.open_roster_spots

            for setup
            in (
                post_state[
                    "live_team_setups"
                ].values()
            )
        )


        room_index = (
            calculate_room_spend_index(
                simulated_sales
            )
        )


        room_multiplier = (
            post_state[
                "live_calibration"
            ]
            .overall
            .multiplier
        )


        sale_number = len(
            simulated_sales
        )


        simulation_steps.append(
            SimulationStep(
                sale_number=(
                    sale_number
                ),
                player_name=(
                    player_name
                ),
                position=(
                    position
                ),
                manager_id=(
                    winner_id
                ),
                price=(
                    int(
                        sale_price
                    )
                ),
                expected_market_value=(
                    expected_market
                ),
                player_ceiling=(
                    int(
                        recommendation
                        .do_not_exceed
                    )
                ),
                roster_aware_ceiling=(
                    roster_aware_ceiling
                ),
                winner_pre_sale_cash=(
                    pre_cash
                ),
                winner_pre_sale_open_spots=(
                    pre_spots
                ),
                winner_pre_sale_max_bid=(
                    pre_max_bid
                ),
                remaining_cash=(
                    remaining_cash
                ),
                remaining_open_spots=(
                    remaining_open_spots
                ),
                room_spend_index=(
                    room_index
                ),
                live_room_multiplier=(
                    room_multiplier
                ),
                optimizer_feasible=(
                    optimizer_feasible
                ),
                optimizer_utility=(
                    optimizer_utility
                ),
                top_nomination=(
                    top_nomination
                ),
                violations=(
                    step_violations
                ),
            )
        )


        for violation in (
            step_violations
        ):

            all_violations.append(
                (
                    f"Sale {sale_number}: "
                    f"{violation}"
                )
            )


    # =====================================================
    # FINAL STATE
    # =====================================================

    final_state = (
        build_simulation_state(
            starting_team_setups=(
                starting_team_setups
            ),
            starting_pool_players=(
                starting_pool_players
            ),
            sales=(
                simulated_sales
            ),
            sleeper_players=(
                sleeper_players
            ),
            player_values=(
                player_values
            ),
            projection_index=(
                projection_index
            ),
            fantasypros_index=(
                fantasypros_index
            ),
            historical_market_model=(
                historical_market_model
            ),
            starting_total_auction_cash=(
                starting_total_auction_cash
            ),
            my_manager_id=(
                my_manager_id
            ),
        )
    )


    position_signals = {
        position: signal.multiplier

        for (
            position,
            signal,
        ) in (
            final_state[
                "live_calibration"
            ]
            .position_signals
            .items()
        )
    }


    manager_signals = {
        manager_id: profile.multiplier

        for (
            manager_id,
            profile,
        ) in (
            final_state[
                "live_calibration"
            ]
            .manager_profiles
            .items()
        )
    }


    final_plan = (
        final_state[
            "optimal_roster_plan"
        ]
    )


    return (
        SimulationResult(
            seed=(
                int(
                    seed
                )
            ),
            requested_sales=(
                requested_sales
            ),
            completed_sales=(
                len(
                    simulated_sales
                )
                -
                starting_sim_sale_count
            ),
            steps=(
                simulation_steps
            ),
            simulated_sales=(
                simulated_sales
            ),
            violations=(
                all_violations
            ),
            final_team_setups=(
                final_state[
                    "live_team_setups"
                ]
            ),
            final_position_signals=(
                position_signals
            ),
            final_manager_signals=(
                manager_signals
            ),
            final_room_spend_index=(
                calculate_room_spend_index(
                    simulated_sales
                )
            ),
            final_optimizer_feasible=(
                bool(
                    final_plan
                    and
                    final_plan.feasible
                )
            ),
            stopped_reason=(
                stopped_reason
            ),
        )
    )