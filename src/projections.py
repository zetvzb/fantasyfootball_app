from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.auction_pool import (
    normalize_player_name,
)


# =========================================================
# DATA OBJECT
# =========================================================

@dataclass
class PlayerProjection:

    fantasypros_id: str

    player_name: str

    position: str

    nfl_team: Optional[str]

    stats: Dict[str, float]

    fantasypros_half_points: Optional[float]

    custom_points: Optional[float]

    custom_scoring_exact: bool

    scoring_breakdown: Dict[str, float] = field(
        default_factory=dict
    )

    scoring_warnings: List[str] = field(
        default_factory=list
    )


# =========================================================
# HELPERS
# =========================================================

def numeric(
    value,
) -> Optional[float]:

    if value is None:
        return None

    try:
        return float(value)

    except (
        ValueError,
        TypeError,
    ):
        return None


def normalize_position(
    value,
) -> str:

    value = str(
        value
        or ""
    ).upper()

    if value in {
        "DST",
        "D/ST",
    }:
        return "DEF"

    return value


def flatten_stats(
    raw_stats,
) -> Dict[str, float]:
    """
    FantasyPros has returned stats as both a dict
    and a list in different API schemas.

    Normalize either format into one dictionary.
    """

    if isinstance(
        raw_stats,
        dict,
    ):

        return {
            key: value
            for key, value
            in raw_stats.items()
        }


    if isinstance(
        raw_stats,
        list,
    ):

        result = {}

        for entry in raw_stats:

            if not isinstance(
                entry,
                dict,
            ):
                continue

            result.update(
                entry
            )

        return result


    return {}


# =========================================================
# SLEEPER -> FANTASYPROS STAT MAP
# =========================================================

SCORING_STAT_MAP = {

    # Passing
    "pass_yd": "pass_yds",
    "pass_td": "pass_tds",
    "pass_int": "pass_ints",

    # Rushing
    "rush_yd": "rush_yds",
    "rush_td": "rush_tds",

    # Receiving
    "rec": "rec_rec",
    "rec_yd": "rec_yds",
    "rec_td": "rec_tds",

    # Fumbles
    #
    # Only use this if FantasyPros actually supplies
    # a lost-fumble field.
    "fum_lost": "fumbles_lost",

    # Yardage bonuses
    "bonus_pass_yd_400": "pass_yds_400",

    "bonus_rush_yd_100": "rush_yds_100",
    "bonus_rush_yd_200": "rush_yds_200",

    "bonus_rec_yd_100": "rec_yds_100",
    "bonus_rec_yd_200": "rec_yds_200",
}


# Applied only when a league's scoring settings don't mention a category at
# all (not when a league explicitly sets it to 0). A manual/off-platform
# league's scoring settings historically only ever recorded reception
# points (see src/manual_league.py), so every other category silently
# scored as zero -- these are the same near-universal values Sleeper uses
# for an otherwise-unconfigured "standard" league.
STANDARD_SCORING_DEFAULTS = {
    "pass_yd": 0.04,
    "pass_td": 4,
    "pass_int": -2,
    "rush_yd": 0.1,
    "rush_td": 6,
    "rec_yd": 0.1,
    "rec_td": 6,
    "fum_lost": -2,
}


# =========================================================
# OFFENSIVE SCORING
# =========================================================

def score_offensive_projection(
    stats: Dict[str, float],
    scoring_settings: Dict[str, float],
) -> Tuple[
    float,
    Dict[str, float],
    List[str],
]:
    """
    Apply Sleeper scoring settings directly to
    FantasyPros projected statistics.

    Designed for QB/RB/WR/TE.
    """

    total = 0.0

    breakdown = {}

    warnings = []


    # -----------------------------------------------------
    # DIRECT STAT MAPPINGS
    # -----------------------------------------------------

    for (
        sleeper_scoring_key,
        fantasypros_stat_key,
    ) in SCORING_STAT_MAP.items():

        if sleeper_scoring_key in scoring_settings:
            scoring_value = numeric(
                scoring_settings.get(
                    sleeper_scoring_key
                )
            )
        else:
            scoring_value = STANDARD_SCORING_DEFAULTS.get(
                sleeper_scoring_key
            )

        if scoring_value is None:
            continue


        stat_value = numeric(
            stats.get(
                fantasypros_stat_key
            )
        )

        if stat_value is None:
            continue


        points = (
            scoring_value
            * stat_value
        )


        total += points


        breakdown[
            sleeper_scoring_key
        ] = points


    # -----------------------------------------------------
    # TWO-POINT CONVERSIONS
    #
    # FantasyPros may expose all offensive 2PT scores
    # together as "2pt_tds".
    #
    # Your league scores pass/rush/rec 2PT conversions
    # identically, so we can safely score it once.
    # -----------------------------------------------------

    two_point_projection = numeric(
        stats.get(
            "2pt_tds"
        )
    )


    two_point_weights = [
        numeric(
            scoring_settings.get(
                "pass_2pt"
            )
        ),
        numeric(
            scoring_settings.get(
                "rush_2pt"
            )
        ),
        numeric(
            scoring_settings.get(
                "rec_2pt"
            )
        ),
    ]


    two_point_weights = [
        value
        for value
        in two_point_weights
        if value is not None
    ]


    if (
        two_point_projection is not None
        and two_point_weights
    ):

        if (
            len(
                set(
                    two_point_weights
                )
            )
            == 1
        ):

            points = (
                two_point_projection
                * two_point_weights[0]
            )

            total += points

            breakdown[
                "2pt_conversions"
            ] = points


        else:

            warnings.append(
                "FantasyPros combines projected "
                "2-point conversions, but this "
                "league scores pass/rush/receive "
                "2PT conversions differently."
            )


    # -----------------------------------------------------
    # RETURN TD
    # -----------------------------------------------------

    return_tds = numeric(
        stats.get(
            "ret_tds"
        )
    )


    if return_tds is not None:

        return_td_weight = (
            numeric(
                scoring_settings.get(
                    "st_td"
                )
            )
            or numeric(
                scoring_settings.get(
                    "st_player_td"
                )
            )
        )


        if return_td_weight is not None:

            points = (
                return_tds
                * return_td_weight
            )

            total += points

            breakdown[
                "return_td"
            ] = points


    return (
        total,
        breakdown,
        warnings,
    )


# =========================================================
# KICKER SCORING
# =========================================================

def score_kicker_projection(
    stats: Dict[str, float],
) -> Tuple[
    Optional[float],
    Dict[str, float],
    List[str],
]:
    """
    FantasyPros preseason K projections generally
    provide aggregate FG totals, not enough distance
    buckets to reproduce this league's custom scoring.

    Use FantasyPros supplied fantasy points as the
    temporary fallback.
    """

    fallback = (
        numeric(
            stats.get(
                "points_half"
            )
        )
        or numeric(
            stats.get(
                "points"
            )
        )
    )


    return (
        fallback,
        {},
        [
            (
                "Kicker projection uses FantasyPros "
                "fallback points because projected "
                "field goals are not separated into "
                "this league's distance buckets."
            )
        ],
    )


# =========================================================
# DEFENSE SCORING
# =========================================================

def score_defense_projection(
    stats: Dict[str, float],
) -> Tuple[
    Optional[float],
    Dict[str, float],
    List[str],
]:
    """
    FantasyPros provides projected average points
    allowed, sacks, INTs, etc.

    The league's points-allowed scoring is bracketed,
    so average projected points allowed cannot be
    converted exactly into expected fantasy points.
    """

    fallback = (
        numeric(
            stats.get(
                "points_half"
            )
        )
        or numeric(
            stats.get(
                "points"
            )
        )
    )


    return (
        fallback,
        {},
        [
            (
                "Defense projection uses FantasyPros "
                "fallback points because points-allowed "
                "bonuses/penalties are nonlinear."
            )
        ],
    )


# =========================================================
# NORMALIZE PROJECTION RESPONSE
# =========================================================

def normalize_fantasypros_projections(
    response: dict,
    scoring_settings: Dict[str, float],
) -> List[PlayerProjection]:

    results = []


    for player in (
        response.get(
            "players",
            []
        )
    ):

        player_id = (
            player.get(
                "fpid"
            )
            or player.get(
                "player_id"
            )
        )


        player_name = (
            player.get(
                "name"
            )
            or player.get(
                "player_name"
            )
        )


        position = (
            normalize_position(
                player.get(
                    "position_id"
                )
            )
        )


        if (
            player_id is None
            or not player_name
            or not position
        ):
            continue


        stats = flatten_stats(
            player.get(
                "stats",
                {},
            )
        )


        fp_half_points = numeric(
            stats.get(
                "points_half"
            )
        )


        if position in {
            "QB",
            "RB",
            "WR",
            "TE",
        }:

            (
                custom_points,
                breakdown,
                warnings,
            ) = score_offensive_projection(
                stats=stats,
                scoring_settings=(
                    scoring_settings
                ),
            )

            exact = True


        elif position == "K":

            (
                custom_points,
                breakdown,
                warnings,
            ) = score_kicker_projection(
                stats
            )

            exact = False


        elif position == "DEF":

            (
                custom_points,
                breakdown,
                warnings,
            ) = score_defense_projection(
                stats
            )

            exact = False


        else:

            continue


        results.append(
            PlayerProjection(
                fantasypros_id=(
                    str(
                        player_id
                    )
                ),
                player_name=(
                    player_name
                ),
                position=(
                    position
                ),
                nfl_team=(
                    player.get(
                        "team_id"
                    )
                ),
                stats=(
                    stats
                ),
                fantasypros_half_points=(
                    fp_half_points
                ),
                custom_points=(
                    custom_points
                ),
                custom_scoring_exact=(
                    exact
                ),
                scoring_breakdown=(
                    breakdown
                ),
                scoring_warnings=(
                    warnings
                ),
            )
        )


    return results


# =========================================================
# NAME INDEX
# =========================================================

def build_projection_index(
    projections: List[
        PlayerProjection
    ],
) -> Dict[
    str,
    PlayerProjection
]:

    result = {}


    for projection in projections:

        normalized_name = (
            normalize_player_name(
                projection.player_name
            )
        )


        if not normalized_name:
            continue


        result[
            normalized_name
        ] = projection


    return result