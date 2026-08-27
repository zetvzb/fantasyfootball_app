from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from src.auction_pool import normalize_player_name


# =========================================================
# CONSTANTS
# =========================================================

FLEX_POSITIONS = {
    "RB",
    "WR",
    "TE",
}

FLEX_SLOT_POSITIONS = {
    "FLEX": {"RB", "WR", "TE"},
    "W/R/T": {"RB", "WR", "TE"},
    "REC_FLEX": {"WR", "TE"},
    "WRRB_FLEX": {"RB", "WR"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
    "SUPERFLEX": {"QB", "RB", "WR", "TE"},
    "OP": {"QB", "RB", "WR", "TE"},
}

BENCH_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
}

CORE_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
    "K",
    "DEF",
}

BEAM_WIDTH = 180
BRANCH_FACTOR = 24

MIN_BID = 1


# =========================================================
# DATA OBJECTS
# =========================================================

@dataclass
class OptimizationCandidate:
    player_name: str
    position: str

    expected_cost: int

    expected_market_value: float
    baseline_value: float
    do_not_exceed: int

    vorp: float

    utility: float


@dataclass
class RosterPlanEntry:
    slot: str

    player_name: str
    position: str

    planned_cost: int

    expected_market_value: float
    do_not_exceed: int

    baseline_value: float
    vorp: float

    utility: float

    is_filler: bool = False


@dataclass
class RosterOptimizationResult:
    feasible: bool

    starting_cash: int
    starting_open_spots: int

    planned_spend: int
    cash_after_plan: int

    total_utility: float

    entries: List[
        RosterPlanEntry
    ] = field(
        default_factory=list
    )

    warnings: List[str] = field(
        default_factory=list
    )


@dataclass
class RosterBuyScenario:
    player_name: str

    proposed_price: int

    pass_utility: float
    buy_utility: float

    utility_delta: float

    roster_aware_ceiling: int

    recommended_ceiling: int

    pass_plan: RosterOptimizationResult
    buy_plan: RosterOptimizationResult


# =========================================================
# INTERNAL BEAM STATE
# =========================================================

@dataclass
class BeamState:
    spent: int
    utility: float

    selected_keys: Tuple[
        str,
        ...
    ]

    entries: Tuple[
        RosterPlanEntry,
        ...
    ]


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


    if value in CORE_POSITIONS:

        return value


    return None


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
# BUILD OPTIMIZATION CANDIDATES
# =========================================================

def build_optimization_candidates(
    available_players,
    auction_values,
    market_values,
    recommendations,
    player_values,
) -> List[
    OptimizationCandidate
]:

    auction_lookup = (
        build_lookup(
            auction_values
        )
    )

    market_lookup = (
        build_lookup(
            market_values
        )
    )

    recommendation_lookup = (
        build_lookup(
            recommendations
        )
    )

    value_lookup = (
        build_lookup(
            player_values
        )
    )


    candidates = []


    for player in available_players:

        key = (
            normalize_player_name(
                player.player_name
            )
        )


        position = (
            normalize_position(
                player.position
            )
        )


        if position is None:

            continue


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


        recommendation = (
            recommendation_lookup.get(
                key
            )
        )


        player_value = (
            value_lookup.get(
                key
            )
        )


        if auction_value is None:

            continue


        expected_market = max(
            1.0,
            numeric(
                getattr(
                    market_value,
                    "expected_market_value",
                    None,
                ),
                numeric(
                    auction_value.baseline_value,
                    1.0,
                ),
            ),
        )


        baseline_value = max(
            0.0,
            numeric(
                auction_value.baseline_value
            ),
        )


        do_not_exceed = max(
            1,
            int(
                round(
                    numeric(
                        getattr(
                            recommendation,
                            "do_not_exceed",
                            None,
                        ),
                        expected_market,
                    )
                )
            ),
        )


        expected_cost = max(
            MIN_BID,
            int(
                round(
                    expected_market
                )
            ),
        )


        vorp = numeric(
            getattr(
                player_value,
                "vorp",
                None,
            )
        )


        # -------------------------------------------------
        # UTILITY
        #
        # Baseline value already represents the league's
        # current/future valuation mix.
        #
        # Small VORP component prevents two similarly priced
        # players from being treated as identical when one
        # is substantially stronger for the current season.
        # -------------------------------------------------

        utility = (
            baseline_value
            +
            0.035
            *
            max(
                vorp,
                0.0,
            )
        )


        candidates.append(
            OptimizationCandidate(
                player_name=(
                    player.player_name
                ),
                position=(
                    position
                ),
                expected_cost=(
                    expected_cost
                ),
                expected_market_value=(
                    expected_market
                ),
                baseline_value=(
                    baseline_value
                ),
                do_not_exceed=(
                    do_not_exceed
                ),
                vorp=(
                    vorp
                ),
                utility=(
                    utility
                ),
            )
        )


    return reduce_candidate_pool(
        candidates
    )


# =========================================================
# REDUCE SEARCH SPACE
# =========================================================

def reduce_candidate_pool(
    candidates,
):

    selected = {}


    # -----------------------------------------------------
    # BEST PLAYERS BY POSITION
    # -----------------------------------------------------

    for position in CORE_POSITIONS:

        positional = [
            player

            for player
            in candidates

            if (
                player.position
                ==
                position
            )
        ]


        positional.sort(
            key=lambda player: (
                player.utility
            ),
            reverse=True,
        )


        for player in (
            positional[
                :20
            ]
        ):

            selected[
                normalize_player_name(
                    player.player_name
                )
            ] = player


    # -----------------------------------------------------
    # BEST VALUE / SURPLUS TARGETS
    # -----------------------------------------------------

    value_candidates = sorted(
        candidates,
        key=lambda player: (
            (
                player.do_not_exceed
                -
                player.expected_cost
            ),
            player.utility,
        ),
        reverse=True,
    )


    for player in (
        value_candidates[
            :30
        ]
    ):

        selected[
            normalize_player_name(
                player.player_name
            )
        ] = player


    # -----------------------------------------------------
    # CHEAP ENDGAME OPTIONS
    # -----------------------------------------------------

    cheap_candidates = sorted(
        candidates,
        key=lambda player: (
            player.expected_cost,
            -player.utility,
        ),
    )


    for player in (
        cheap_candidates[
            :30
        ]
    ):

        selected[
            normalize_player_name(
                player.player_name
            )
        ] = player


    return list(
        selected.values()
    )


# =========================================================
# BUILD REQUIRED SLOT LIST
# =========================================================

def build_remaining_slots(
    open_spots,
    starter_gaps,
    flex_gap,
    flex_gaps=None,
):

    slots = []


    for position in [
        "QB",
        "RB",
        "WR",
        "TE",
    ]:

        gap = int(
            starter_gaps.get(
                position,
                0,
            )
            or 0
        )


        for _ in range(
            gap
        ):

            slots.append(
                position
            )


    resolved_flex_gaps = dict(flex_gaps or {})
    if not resolved_flex_gaps and flex_gap:
        resolved_flex_gaps["FLEX"] = int(flex_gap)
    for slot, gap in sorted(
        resolved_flex_gaps.items(),
        key=lambda item: len(FLEX_SLOT_POSITIONS.get(item[0], ())),
    ):
        for _ in range(int(gap or 0)):
            slots.append(slot)


    for position in [
        "K",
        "DEF",
    ]:

        gap = int(
            starter_gaps.get(
                position,
                0,
            )
            or 0
        )


        for _ in range(
            gap
        ):

            slots.append(
                position
            )


    bench_slots = max(
        0,
        int(
            open_spots
        )
        -
        len(
            slots
        ),
    )


    for _ in range(
        bench_slots
    ):

        slots.append(
            "BENCH"
        )


    return slots


# =========================================================
# SLOT ELIGIBILITY
# =========================================================

def candidate_eligible(
    candidate,
    slot,
):

    if slot in FLEX_SLOT_POSITIONS:
        return candidate.position in FLEX_SLOT_POSITIONS[slot]


    if slot == "BENCH":

        return (
            candidate.position
            in BENCH_POSITIONS
        )


    return (
        candidate.position
        ==
        slot
    )


# =========================================================
# SLOT MULTIPLIER
# =========================================================

def slot_multiplier(
    slot,
    position,
):

    if slot == "BENCH":

        if position in {
            "RB",
            "WR",
        }:

            return 0.82


        if position == "TE":

            return 0.76


        if position == "QB":

            return 0.68


        return 0.60


    if slot in FLEX_SLOT_POSITIONS:

        return 0.95


    return 1.0


# =========================================================
# CANDIDATE RANK
# =========================================================

def candidate_slot_score(
    candidate,
    slot,
):

    multiplier = (
        slot_multiplier(
            slot,
            candidate.position,
        )
    )


    surplus = max(
        0,
        candidate.do_not_exceed
        -
        candidate.expected_cost,
    )


    affordability_bonus = (
        0.15
        *
        surplus
    )


    return (
        candidate.utility
        *
        multiplier
        +
        affordability_bonus
    )


# =========================================================
# FILLER
# =========================================================

def build_filler_entry(
    slot,
    index,
):

    if slot == "FLEX":

        position = "RB/WR/TE"

    elif slot == "BENCH":

        position = "ANY"

    else:

        position = slot


    return (
        RosterPlanEntry(
            slot=(
                slot
            ),
            player_name=(
                f"$1 {slot} fallback"
            ),
            position=(
                position
            ),
            planned_cost=1,
            expected_market_value=1.0,
            do_not_exceed=1,
            baseline_value=0.0,
            vorp=0.0,
            utility=0.0,
            is_filler=True,
        )
    )


# =========================================================
# PRUNE BEAM
# =========================================================

def prune_states(
    states,
    beam_width=BEAM_WIDTH,
):

    if len(
        states
    ) <= beam_width:

        return states


    best_utility = sorted(
        states,
        key=lambda state: (
            state.utility
        ),
        reverse=True,
    )


    best_efficiency = sorted(
        states,
        key=lambda state: (
            state.utility
            /
            max(
                state.spent,
                1,
            )
        ),
        reverse=True,
    )


    utility_count = int(
        beam_width
        *
        0.72
    )


    efficiency_count = (
        beam_width
        -
        utility_count
    )


    selected = {}



    for state in (
        best_utility[
            :utility_count
        ]
        +
        best_efficiency[
            :efficiency_count
        ]
    ):

        key = (
            state.spent,
            state.selected_keys,
        )


        existing = (
            selected.get(
                key
            )
        )


        if (
            existing is None
            or
            state.utility
            >
            existing.utility
        ):

            selected[
                key
            ] = state


    result = list(
        selected.values()
    )


    result.sort(
        key=lambda state: (
            state.utility
        ),
        reverse=True,
    )


    return result[
        :beam_width
    ]


# =========================================================
# APPLY FORCED PLAYER TO NEEDS
# =========================================================

def apply_forced_position(
    position,
    starter_gaps,
    flex_gap,
):

    gaps = dict(
        starter_gaps
    )


    flex_remaining = int(
        flex_gap
        or 0
    )


    multiplier = 0.78

    forced_slot = "BENCH"


    if (
        position
        in gaps
        and
        gaps.get(
            position,
            0,
        )
        > 0
    ):

        gaps[
            position
        ] -= 1

        forced_slot = position

        multiplier = 1.0


    elif (
        position
        in FLEX_POSITIONS
        and
        flex_remaining
        > 0
    ):

        flex_remaining -= 1

        forced_slot = "FLEX"

        multiplier = 0.95


    return (
        gaps,
        flex_remaining,
        forced_slot,
        multiplier,
    )


# =========================================================
# OPTIMIZE REMAINING ROSTER
# =========================================================

def optimize_remaining_roster(
    my_team_setup,
    my_need_profile,
    candidates,
    forced_player_name=None,
    forced_price=None,
    excluded_player_names=None,
    beam_width=BEAM_WIDTH,
    branch_factor=BRANCH_FACTOR,
):

    warnings = []


    starting_cash = int(
        my_team_setup.auction_cash
    )


    starting_open_spots = int(
        my_team_setup.open_roster_spots
    )


    starter_gaps = dict(
        my_need_profile.starter_gaps
    )


    flex_gap = int(
        my_need_profile.flex_gap
        or 0
    )


    excluded_keys = {
        normalize_player_name(
            player_name
        )

        for player_name
        in (
            excluded_player_names
            or []
        )
    }


    candidate_lookup = {
        normalize_player_name(
            candidate.player_name
        ): candidate

        for candidate
        in candidates
    }


    forced_entry = None

    forced_utility = 0.0


    remaining_cash = (
        starting_cash
    )


    remaining_spots = (
        starting_open_spots
    )


    # =====================================================
    # FORCE A SPECIFIC PURCHASE
    # =====================================================

    if forced_player_name:

        forced_key = (
            normalize_player_name(
                forced_player_name
            )
        )


        forced_candidate = (
            candidate_lookup.get(
                forced_key
            )
        )


        if forced_candidate is None:

            return (
                RosterOptimizationResult(
                    feasible=False,
                    starting_cash=(
                        starting_cash
                    ),
                    starting_open_spots=(
                        starting_open_spots
                    ),
                    planned_spend=0,
                    cash_after_plan=(
                        starting_cash
                    ),
                    total_utility=0.0,
                    warnings=[
                        (
                            f"{forced_player_name} "
                            f"is not available to the optimizer."
                        )
                    ],
                )
            )


        price = int(
            forced_price
            if forced_price
            is not None
            else forced_candidate.expected_cost
        )


        if price < 1:

            price = 1


        if (
            remaining_spots
            <= 0
        ):

            return (
                RosterOptimizationResult(
                    feasible=False,
                    starting_cash=(
                        starting_cash
                    ),
                    starting_open_spots=(
                        starting_open_spots
                    ),
                    planned_spend=0,
                    cash_after_plan=(
                        starting_cash
                    ),
                    total_utility=0.0,
                    warnings=[
                        "No roster spots remain."
                    ],
                )
            )


        legal_max = int(
            my_team_setup.max_bid
        )


        if price > legal_max:

            return (
                RosterOptimizationResult(
                    feasible=False,
                    starting_cash=(
                        starting_cash
                    ),
                    starting_open_spots=(
                        starting_open_spots
                    ),
                    planned_spend=0,
                    cash_after_plan=(
                        starting_cash
                    ),
                    total_utility=0.0,
                    warnings=[
                        (
                            f"${price} exceeds your "
                            f"legal maximum of "
                            f"${legal_max}."
                        )
                    ],
                )
            )


        (
            starter_gaps,
            flex_gap,
            forced_slot,
            forced_multiplier,
        ) = (
            apply_forced_position(
                position=(
                    forced_candidate.position
                ),
                starter_gaps=(
                    starter_gaps
                ),
                flex_gap=(
                    flex_gap
                ),
            )
        )


        forced_utility = (
            forced_candidate.utility
            *
            forced_multiplier
        )


        forced_entry = (
            RosterPlanEntry(
                slot=(
                    forced_slot
                ),
                player_name=(
                    forced_candidate.player_name
                ),
                position=(
                    forced_candidate.position
                ),
                planned_cost=(
                    price
                ),
                expected_market_value=(
                    forced_candidate.expected_market_value
                ),
                do_not_exceed=(
                    forced_candidate.do_not_exceed
                ),
                baseline_value=(
                    forced_candidate.baseline_value
                ),
                vorp=(
                    forced_candidate.vorp
                ),
                utility=(
                    forced_utility
                ),
                is_filler=False,
            )
        )


        remaining_cash -= (
            price
        )


        remaining_spots -= 1


        excluded_keys.add(
            forced_key
        )


    # =====================================================
    # BUILD REMAINING SLOT LIST
    # =====================================================

    slots = (
        build_remaining_slots(
            open_spots=(
                remaining_spots
            ),
            starter_gaps=(
                starter_gaps
            ),
            flex_gap=(
                flex_gap
            ),
        )
    )


    minimum_required_cash = len(
        slots
    )


    if (
        remaining_cash
        <
        minimum_required_cash
    ):

        return (
            RosterOptimizationResult(
                feasible=False,
                starting_cash=(
                    starting_cash
                ),
                starting_open_spots=(
                    starting_open_spots
                ),
                planned_spend=(
                    starting_cash
                    -
                    remaining_cash
                ),
                cash_after_plan=(
                    remaining_cash
                ),
                total_utility=(
                    forced_utility
                ),
                entries=(
                    [
                        forced_entry
                    ]
                    if forced_entry
                    else []
                ),
                warnings=[
                    (
                        "Not enough cash remains "
                        "to reserve $1 for every "
                        "open roster spot."
                    )
                ],
            )
        )


    usable_candidates = [
        candidate

        for candidate
        in candidates

        if (
            normalize_player_name(
                candidate.player_name
            )
            not in excluded_keys
        )
    ]


    # =====================================================
    # INITIAL BEAM
    # =====================================================

    beam = [
        BeamState(
            spent=0,
            utility=0.0,
            selected_keys=tuple(),
            entries=tuple(),
        )
    ]


    # =====================================================
    # FILL EACH SLOT
    # =====================================================

    for (
        slot_index,
        slot,
    ) in enumerate(
        slots
    ):

        remaining_slot_count = (
            len(
                slots
            )
            -
            slot_index
            -
            1
        )


        eligible = [
            candidate

            for candidate
            in usable_candidates

            if candidate_eligible(
                candidate,
                slot,
            )
        ]


        eligible.sort(
            key=lambda candidate: (
                candidate_slot_score(
                    candidate,
                    slot,
                )
            ),
            reverse=True,
        )


        eligible = (
            eligible[
                :branch_factor
            ]
        )


        next_states = []


        for state in beam:

            selected = set(
                state.selected_keys
            )


            # =============================================
            # REAL PLAYER OPTIONS
            # =============================================

            for candidate in eligible:

                key = (
                    normalize_player_name(
                        candidate.player_name
                    )
                )


                if key in selected:

                    continue


                # -----------------------------------------
                # Don't plan to pay expected market above
                # our own ceiling.
                # -----------------------------------------

                if (
                    candidate.expected_cost
                    >
                    candidate.do_not_exceed
                ):

                    continue


                new_spent = (
                    state.spent
                    +
                    candidate.expected_cost
                )


                # -----------------------------------------
                # MUST PRESERVE $1 FOR EVERY REMAINING SLOT
                # -----------------------------------------

                if (
                    new_spent
                    +
                    remaining_slot_count
                    >
                    remaining_cash
                ):

                    continue


                multiplier = (
                    slot_multiplier(
                        slot,
                        candidate.position,
                    )
                )


                utility = (
                    candidate.utility
                    *
                    multiplier
                )


                entry = (
                    RosterPlanEntry(
                        slot=(
                            slot
                        ),
                        player_name=(
                            candidate.player_name
                        ),
                        position=(
                            candidate.position
                        ),
                        planned_cost=(
                            candidate.expected_cost
                        ),
                        expected_market_value=(
                            candidate.expected_market_value
                        ),
                        do_not_exceed=(
                            candidate.do_not_exceed
                        ),
                        baseline_value=(
                            candidate.baseline_value
                        ),
                        vorp=(
                            candidate.vorp
                        ),
                        utility=(
                            utility
                        ),
                        is_filler=False,
                    )
                )


                next_states.append(
                    BeamState(
                        spent=(
                            new_spent
                        ),
                        utility=(
                            state.utility
                            +
                            utility
                        ),
                        selected_keys=(
                            state.selected_keys
                            +
                            (
                                key,
                            )
                        ),
                        entries=(
                            state.entries
                            +
                            (
                                entry,
                            )
                        ),
                    )
                )


            # =============================================
            # $1 FALLBACK OPTION
            # =============================================

            filler_spent = (
                state.spent
                +
                1
            )


            if (
                filler_spent
                +
                remaining_slot_count
                <=
                remaining_cash
            ):

                filler = (
                    build_filler_entry(
                        slot=(
                            slot
                        ),
                        index=(
                            slot_index
                        ),
                    )
                )


                next_states.append(
                    BeamState(
                        spent=(
                            filler_spent
                        ),
                        utility=(
                            state.utility
                        ),
                        selected_keys=(
                            state.selected_keys
                        ),
                        entries=(
                            state.entries
                            +
                            (
                                filler,
                            )
                        ),
                    )
                )


        if not next_states:

            warnings.append(
                (
                    f"No feasible paths remained "
                    f"while filling {slot}."
                )
            )

            break


        beam = (
            prune_states(
                next_states,
                beam_width=(
                    beam_width
                ),
            )
        )


    # =====================================================
    # FINAL RESULT
    # =====================================================

    if not beam:

        return (
            RosterOptimizationResult(
                feasible=False,
                starting_cash=(
                    starting_cash
                ),
                starting_open_spots=(
                    starting_open_spots
                ),
                planned_spend=0,
                cash_after_plan=(
                    starting_cash
                ),
                total_utility=0.0,
                warnings=(
                    warnings
                ),
            )
        )


    best = max(
        beam,
        key=lambda state: (
            state.utility
        ),
    )


    entries = list(
        best.entries
    )


    forced_spend = 0


    if forced_entry:

        entries.insert(
            0,
            forced_entry
        )

        forced_spend = (
            forced_entry.planned_cost
        )


    planned_spend = (
        forced_spend
        +
        best.spent
    )


    total_utility = (
        forced_utility
        +
        best.utility
    )


    return (
        RosterOptimizationResult(
            feasible=True,
            starting_cash=(
                starting_cash
            ),
            starting_open_spots=(
                starting_open_spots
            ),
            planned_spend=(
                planned_spend
            ),
            cash_after_plan=(
                starting_cash
                -
                planned_spend
            ),
            total_utility=(
                total_utility
            ),
            entries=(
                entries
            ),
            warnings=(
                warnings
            ),
        )
    )


# =========================================================
# ROSTER-AWARE CEILING
# =========================================================

def calculate_roster_aware_ceiling(
    player_name,
    my_team_setup,
    my_need_profile,
    candidates,
    existing_do_not_exceed,
):

    key = (
        normalize_player_name(
            player_name
        )
    )


    candidate_lookup = {
        normalize_player_name(
            candidate.player_name
        ): candidate

        for candidate
        in candidates
    }


    target = (
        candidate_lookup.get(
            key
        )
    )


    if target is None:

        return (
            0,
            None,
        )


    # =====================================================
    # BEST PLAN IF WE PASS
    # =====================================================

    pass_plan = (
        optimize_remaining_roster(
            my_team_setup=(
                my_team_setup
            ),
            my_need_profile=(
                my_need_profile
            ),
            candidates=(
                candidates
            ),
            excluded_player_names=[
                player_name
            ],
        )
    )


    if not pass_plan.feasible:

        return (
            int(
                existing_do_not_exceed
            ),
            pass_plan,
        )


    legal_max = int(
        my_team_setup.max_bid
    )


    search_max = min(
        legal_max,
        int(
            existing_do_not_exceed
        ),
    )


    if search_max < 1:

        return (
            0,
            pass_plan,
        )


    # =====================================================
    # BINARY SEARCH
    #
    # Highest price at which buying the player still
    # produces at least as much whole-roster utility
    # as passing.
    # =====================================================

    low = 1

    high = search_max

    best_price = 0


    tolerance = 0.25


    while (
        low
        <=
        high
    ):

        mid = (
            low
            +
            high
        ) // 2


        buy_plan = (
            optimize_remaining_roster(
                my_team_setup=(
                    my_team_setup
                ),
                my_need_profile=(
                    my_need_profile
                ),
                candidates=(
                    candidates
                ),
                forced_player_name=(
                    player_name
                ),
                forced_price=(
                    mid
                ),
            )
        )


        if not buy_plan.feasible:

            high = (
                mid
                -
                1
            )

            continue


        if (
            buy_plan.total_utility
            +
            tolerance
            >=
            pass_plan.total_utility
        ):

            best_price = (
                mid
            )

            low = (
                mid
                +
                1
            )

        else:

            high = (
                mid
                -
                1
            )


    return (
        best_price,
        pass_plan,
    )


# =========================================================
# BUY VS PASS SCENARIO
# =========================================================

def compare_buy_vs_pass(
    player_name,
    proposed_price,
    my_team_setup,
    my_need_profile,
    candidates,
    existing_do_not_exceed,
):

    pass_plan = (
        optimize_remaining_roster(
            my_team_setup=(
                my_team_setup
            ),
            my_need_profile=(
                my_need_profile
            ),
            candidates=(
                candidates
            ),
            excluded_player_names=[
                player_name
            ],
        )
    )


    buy_plan = (
        optimize_remaining_roster(
            my_team_setup=(
                my_team_setup
            ),
            my_need_profile=(
                my_need_profile
            ),
            candidates=(
                candidates
            ),
            forced_player_name=(
                player_name
            ),
            forced_price=(
                int(
                    proposed_price
                )
            ),
        )
    )


    (
        roster_ceiling,
        _,
    ) = (
        calculate_roster_aware_ceiling(
            player_name=(
                player_name
            ),
            my_team_setup=(
                my_team_setup
            ),
            my_need_profile=(
                my_need_profile
            ),
            candidates=(
                candidates
            ),
            existing_do_not_exceed=(
                existing_do_not_exceed
            ),
        )
    )


    final_ceiling = min(
        int(
            existing_do_not_exceed
        ),
        int(
            roster_ceiling
        ),
    )


    utility_delta = (
        buy_plan.total_utility
        -
        pass_plan.total_utility
    )


    return (
        RosterBuyScenario(
            player_name=(
                player_name
            ),
            proposed_price=(
                int(
                    proposed_price
                )
            ),
            pass_utility=(
                pass_plan.total_utility
            ),
            buy_utility=(
                buy_plan.total_utility
            ),
            utility_delta=(
                utility_delta
            ),
            roster_aware_ceiling=(
                roster_ceiling
            ),
            recommended_ceiling=(
                final_ceiling
            ),
            pass_plan=(
                pass_plan
            ),
            buy_plan=(
                buy_plan
            ),
        )
    )
