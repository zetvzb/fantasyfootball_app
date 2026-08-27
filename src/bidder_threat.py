from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.auction_pool import (
    normalize_player_name,
)


# =========================================================
# LEAGUE ROSTER HEURISTICS
# =========================================================

CORE_STARTERS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "K": 1,
    "DEF": 1,
}

FLEX_POSITIONS = {
    "RB",
    "WR",
    "TE",
}

FLEX_SLOTS = 2


# These are not league rules.
# They are reasonable roster-depth targets used only
# for estimating how motivated a team may be to buy
# another player at a position.
TARGET_DEPTH = {
    "QB": 2,
    "RB": 5,
    "WR": 5,
    "TE": 2,
    "K": 1,
    "DEF": 1,
}


# =========================================================
# DATA OBJECTS
# =========================================================

@dataclass
class TeamNeedProfile:

    manager_id: str

    auction_cash: float

    open_spots: int

    max_bid: float

    protected_counts: Dict[
        str,
        int,
    ]

    starter_gaps: Dict[
        str,
        int,
    ]

    flex_gap: int

    need_scores: Dict[
        str,
        float,
    ]


@dataclass
class BidderThreat:

    manager_id: str

    player_name: str

    position: str

    threat_score: float

    threat_level: str

    need_score: float

    affordability_score: float

    cash_strength: float

    aggressiveness_score: float

    position_tendency_score: float

    star_chase_score: float

    auction_cash: float

    max_bid: float

    can_afford_market: bool

    reasons: List[str] = field(
        default_factory=list
    )


@dataclass
class PlayerThreatSummary:

    player_name: str

    position: str

    expected_market_value: float

    is_star: bool

    threats: List[
        BidderThreat
    ]

    top_manager_id: Optional[str]

    top_threat_score: float

    top_threat_level: str

    high_threat_count: int

    affordable_bidder_count: int


# =========================================================
# HELPERS
# =========================================================

def numeric(
    value,
    default=0.0,
) -> float:

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
    value: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def normalize_position(
    value,
) -> Optional[str]:

    if value is None:
        return None

    position = str(
        value
    ).upper()

    if position in {
        "DST",
        "D/ST",
    }:

        return "DEF"

    if position in {
        "QB",
        "RB",
        "WR",
        "TE",
        "K",
        "DEF",
    }:

        return position

    return None


def percentile(
    values: List[float],
    q: float,
) -> float:

    if not values:

        return 0.0

    ordered = sorted(
        values
    )

    if len(
        ordered
    ) == 1:

        return ordered[0]

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


def threat_level(
    score: float,
) -> str:

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
# TEAM NEED CALCULATION
# =========================================================

def calculate_need_scores(
    protected_counts: Dict[
        str,
        int,
    ],
    open_spots: int,
):

    starter_gaps = {}

    for (
        position,
        required,
    ) in CORE_STARTERS.items():

        starter_gaps[
            position
        ] = max(
            0,
            required
            -
            protected_counts.get(
                position,
                0,
            ),
        )

    # -----------------------------------------------------
    # FLEX ALLOCATION
    # -----------------------------------------------------

    core_filled = (
        min(
            protected_counts.get(
                "RB",
                0,
            ),
            2,
        )
        +
        min(
            protected_counts.get(
                "WR",
                0,
            ),
            2,
        )
        +
        min(
            protected_counts.get(
                "TE",
                0,
            ),
            1,
        )
    )

    total_flex_eligible = (
        protected_counts.get(
            "RB",
            0,
        )
        +
        protected_counts.get(
            "WR",
            0,
        )
        +
        protected_counts.get(
            "TE",
            0,
        )
    )

    extra_flex_players = max(
        0,
        total_flex_eligible
        -
        core_filled,
    )

    flex_filled = min(
        FLEX_SLOTS,
        extra_flex_players,
    )

    flex_gap = max(
        0,
        FLEX_SLOTS
        -
        flex_filled,
    )

    need_scores = {}

    for position in [
        "QB",
        "RB",
        "WR",
        "TE",
        "K",
        "DEF",
    ]:

        count = (
            protected_counts.get(
                position,
                0,
            )
        )

        starter_gap = (
            starter_gaps.get(
                position,
                0,
            )
        )

        # -------------------------------------------------
        # Missing required starter
        # -------------------------------------------------

        if starter_gap > 0:

            score = 1.0

        # -------------------------------------------------
        # FLEX still unfilled
        # -------------------------------------------------

        elif (
            position
            in FLEX_POSITIONS
            and
            flex_gap > 0
        ):

            score = 0.80

        # -------------------------------------------------
        # Depth
        # -------------------------------------------------

        else:

            target = (
                TARGET_DEPTH.get(
                    position,
                    count,
                )
            )

            depth_gap = max(
                0,
                target
                -
                count,
            )

            if position in {
                "K",
                "DEF",
            }:

                score = (
                    0.05
                    if count >= 1
                    else 1.0
                )

            elif depth_gap >= 2:

                score = 0.60

            elif depth_gap == 1:

                score = 0.40

            else:

                score = 0.15

        if open_spots <= 0:

            score = 0.0

        need_scores[
            position
        ] = score

    return (
        starter_gaps,
        flex_gap,
        need_scores,
    )


# =========================================================
# BUILD TEAM NEED PROFILES
# =========================================================

def build_team_need_profiles(
    team_setups,
    sleeper_players: dict,
) -> Dict[
    str,
    TeamNeedProfile,
]:

    results = {}

    for (
        manager_id,
        setup,
    ) in team_setups.items():

        counts = {
            "QB": 0,
            "RB": 0,
            "WR": 0,
            "TE": 0,
            "K": 0,
            "DEF": 0,
        }

        # -------------------------------------------------
        # KEEPERS
        # -------------------------------------------------

        for keeper in (
            getattr(
                setup,
                "keepers",
                [],
            )
            or []
        ):

            position = (
                normalize_position(
                    getattr(
                        keeper,
                        "position",
                        None,
                    )
                )
            )

            if position:

                counts[
                    position
                ] += 1

        (
            starter_gaps,
            flex_gap,
            need_scores,
        ) = calculate_need_scores(
            protected_counts=(
                counts
            ),
            open_spots=(
                setup.open_roster_spots
            ),
        )

        results[
            manager_id
        ] = TeamNeedProfile(
            manager_id=(
                manager_id
            ),
            auction_cash=(
                numeric(
                    setup.auction_cash
                )
            ),
            open_spots=(
                int(
                    setup.open_roster_spots
                )
            ),
            max_bid=(
                numeric(
                    setup.max_bid
                )
            ),
            protected_counts=(
                counts
            ),
            starter_gaps=(
                starter_gaps
            ),
            flex_gap=(
                flex_gap
            ),
            need_scores=(
                need_scores
            ),
        )

    return results


# =========================================================
# LEAGUE POSITION TENDENCY BASELINES
# =========================================================

def build_league_position_spend_baseline(
    historical_model,
) -> Dict[
    str,
    float,
]:

    positions = [
        "QB",
        "RB",
        "WR",
        "TE",
        "K",
        "DEF",
    ]

    result = {}

    profiles = list(
        historical_model
        .manager_profiles
        .values()
    )

    if not profiles:

        return {
            position: 0.0
            for position
            in positions
        }

    for position in positions:

        total = sum(
            profile
            .position_spend_share
            .get(
                position,
                0.0,
            )

            for profile
            in profiles
        )

        result[
            position
        ] = (
            total
            /
            len(
                profiles
            )
        )

    return result


# =========================================================
# BIDDER THREAT ENGINE
# =========================================================

def calculate_bidder_threats(
    available_players,
    auction_values,
    market_values,
    team_need_profiles,
    historical_model,
    excluded_manager_id=None,
) -> List[
    PlayerThreatSummary
]:

    auction_lookup = {
        normalize_player_name(
            value.player_name
        ): value

        for value
        in auction_values
    }

    market_lookup = {
        normalize_player_name(
            value.player_name
        ): value

        for value
        in market_values
    }

    # -----------------------------------------------------
    # STAR THRESHOLD
    # -----------------------------------------------------

    expected_prices = []

    for value in auction_values:

        if not (
            value.expected_to_be_drafted
        ):

            continue

        key = (
            normalize_player_name(
                value.player_name
            )
        )

        market_value = (
            market_lookup.get(
                key
            )
        )

        if market_value:

            expected_prices.append(
                numeric(
                    market_value
                    .expected_market_value
                )
            )

    star_threshold = percentile(
        expected_prices,
        0.80,
    )

    # -----------------------------------------------------
    # CASH BASELINE
    # -----------------------------------------------------

    max_cash = max(
        [
            profile.auction_cash

            for profile
            in team_need_profiles.values()
        ]
        or [
            1.0
        ]
    )

    # -----------------------------------------------------
    # POSITION TENDENCY BASELINE
    # -----------------------------------------------------

    league_position_baseline = (
        build_league_position_spend_baseline(
            historical_model
        )
    )

    results = []

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

        market_value = (
            market_lookup.get(
                key
            )
        )

        auction_value = (
            auction_lookup.get(
                key
            )
        )

        if market_value:

            expected_market = numeric(
                market_value
                .expected_market_value,
                1.0,
            )

        elif auction_value:

            expected_market = numeric(
                auction_value
                .baseline_value,
                1.0,
            )

        else:

            expected_market = 1.0

        is_star = (
            expected_market
            >= star_threshold
            and
            star_threshold > 0
        )

        threats = []

        for (
            manager_id,
            team,
        ) in (
            team_need_profiles.items()
        ):

            if (
                excluded_manager_id
                and
                manager_id
                == excluded_manager_id
            ):

                continue

            if team.open_spots <= 0:

                continue

            # =============================================
            # ROSTER NEED
            # =============================================

            need_score = (
                team.need_scores.get(
                    position,
                    0.0,
                )
            )

            # =============================================
            # AFFORDABILITY
            # =============================================

            if expected_market <= 1:

                affordability = 1.0

            else:

                affordability = clamp(
                    team.max_bid
                    /
                    expected_market
                )

            can_afford_market = (
                team.max_bid
                >= expected_market
            )

            # =============================================
            # CASH STRENGTH
            # =============================================

            cash_strength = (
                clamp(
                    team.auction_cash
                    /
                    max(
                        max_cash,
                        1.0,
                    )
                )
            )

            # =============================================
            # HISTORICAL BEHAVIOR
            # =============================================

            historical_profile = (
                historical_model
                .manager_profiles
                .get(
                    manager_id
                )
            )

            if historical_profile:

                aggressiveness_score = clamp(
                    0.50
                    +
                    (
                        historical_profile
                        .aggressiveness_index
                        -
                        1.0
                    )
                    * 1.20
                )

                manager_position_share = (
                    historical_profile
                    .position_spend_share
                    .get(
                        position,
                        0.0,
                    )
                )

                league_position_share = (
                    league_position_baseline
                    .get(
                        position,
                        0.0,
                    )
                )

                if league_position_share > 0:

                    position_ratio = (
                        manager_position_share
                        /
                        league_position_share
                    )

                    position_tendency = clamp(
                        0.50
                        +
                        0.30
                        *
                        (
                            position_ratio
                            -
                            1.0
                        )
                    )

                else:

                    position_tendency = 0.50

                star_chase = clamp(
                    0.50
                    +
                    0.50
                    *
                    (
                        historical_profile
                        .star_chase_index
                        -
                        1.0
                    )
                )

            else:

                aggressiveness_score = 0.50

                position_tendency = 0.50

                star_chase = 0.50

            # =============================================
            # THREAT SCORE
            # =============================================

            score = (
                0.35
                * need_score
                +
                0.25
                * affordability
                +
                0.15
                * cash_strength
                +
                0.15
                * aggressiveness_score
                +
                0.10
                * position_tendency
            )

            # Star chasing matters more for elite assets.
            if is_star:

                star_multiplier = (
                    0.90
                    +
                    0.20
                    * star_chase
                )

                score *= (
                    star_multiplier
                )

            # Suppress teams that cannot realistically
            # get close to the expected closing price.
            if (
                expected_market > 1
                and
                team.max_bid
                <
                expected_market
                * 0.50
            ):

                score *= 0.60

            threat_score = (
                clamp(
                    score
                )
                * 100.0
            )

            # =============================================
            # REASONS
            # =============================================

            reasons = []

            if (
                team.starter_gaps.get(
                    position,
                    0,
                )
                > 0
            ):

                reasons.append(
                    f"needs {position} starter"
                )

            elif (
                position
                in FLEX_POSITIONS
                and
                team.flex_gap > 0
            ):

                reasons.append(
                    "still needs FLEX help"
                )

            elif need_score >= 0.60:

                reasons.append(
                    f"needs {position} depth"
                )

            if can_afford_market:

                reasons.append(
                    "can afford projected market"
                )

            else:

                reasons.append(
                    (
                        f"max bid ${team.max_bid:.0f} "
                        f"below market"
                    )
                )

            if (
                historical_profile
                and
                historical_profile
                .aggressiveness_index
                >= 1.10
            ):

                reasons.append(
                    "historically aggressive"
                )

            if position_tendency >= 0.70:

                reasons.append(
                    f"historically favors {position}"
                )

            if (
                is_star
                and
                historical_profile
                and
                historical_profile
                .star_chase_index
                >= 1.10
            ):

                reasons.append(
                    "historical star chaser"
                )

            threats.append(
                BidderThreat(
                    manager_id=(
                        manager_id
                    ),
                    player_name=(
                        player.player_name
                    ),
                    position=(
                        position
                    ),
                    threat_score=(
                        threat_score
                    ),
                    threat_level=(
                        threat_level(
                            threat_score
                        )
                    ),
                    need_score=(
                        need_score
                    ),
                    affordability_score=(
                        affordability
                    ),
                    cash_strength=(
                        cash_strength
                    ),
                    aggressiveness_score=(
                        aggressiveness_score
                    ),
                    position_tendency_score=(
                        position_tendency
                    ),
                    star_chase_score=(
                        star_chase
                    ),
                    auction_cash=(
                        team.auction_cash
                    ),
                    max_bid=(
                        team.max_bid
                    ),
                    can_afford_market=(
                        can_afford_market
                    ),
                    reasons=(
                        reasons
                    ),
                )
            )

        threats.sort(
            key=lambda threat: (
                threat.threat_score
            ),
            reverse=True,
        )

        if threats:

            top_manager_id = (
                threats[
                    0
                ].manager_id
            )

            top_score = (
                threats[
                    0
                ].threat_score
            )

            top_level = (
                threats[
                    0
                ].threat_level
            )

        else:

            top_manager_id = None

            top_score = 0.0

            top_level = "NONE"

        high_threat_count = len(
            [
                threat

                for threat
                in threats

                if (
                    threat.threat_score
                    >= 60
                )
            ]
        )

        affordable_bidder_count = len(
            [
                threat

                for threat
                in threats

                if (
                    threat.can_afford_market
                )
            ]
        )

        results.append(
            PlayerThreatSummary(
                player_name=(
                    player.player_name
                ),
                position=(
                    position
                ),
                expected_market_value=(
                    expected_market
                ),
                is_star=(
                    is_star
                ),
                threats=(
                    threats
                ),
                top_manager_id=(
                    top_manager_id
                ),
                top_threat_score=(
                    top_score
                ),
                top_threat_level=(
                    top_level
                ),
                high_threat_count=(
                    high_threat_count
                ),
                affordable_bidder_count=(
                    affordable_bidder_count
                ),
            )
        )

    return results


def build_threat_index(
    summaries: List[
        PlayerThreatSummary
    ],
) -> Dict[
    str,
    PlayerThreatSummary,
]:

    return {
        normalize_player_name(
            summary.player_name
        ): summary

        for summary
        in summaries
    }