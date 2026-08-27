from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from src.projections import PlayerProjection


# =========================================================
# CONSTANTS
# =========================================================

NUM_TEAMS = 12

CORE_STARTERS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
}

FLEX_PER_TEAM = 2

FLEX_POSITIONS = {
    "RB",
    "WR",
    "TE",
}


# =========================================================
# OBJECTS
# =========================================================

@dataclass
class ReplacementLevels:

    points_by_position: Dict[
        str,
        float,
    ]

    starter_demand: Dict[
        str,
        int,
    ]

    flex_allocations: Dict[
        str,
        int,
    ]


@dataclass
class PlayerValue:

    player_name: str

    position: str

    projected_points: float

    replacement_points: float

    vorp: float

    starter_rank: Optional[int]


# =========================================================
# ELIGIBLE PROJECTIONS
# =========================================================

def get_offensive_projections(
    projections: List[
        PlayerProjection
    ],
):

    result = {
        "QB": [],
        "RB": [],
        "WR": [],
        "TE": [],
    }


    for player in projections:

        if (
            player.position
            not in result
        ):
            continue

        if (
            player.custom_points
            is None
        ):
            continue

        result[
            player.position
        ].append(
            player
        )


    for position in result:

        result[
            position
        ].sort(
            key=lambda player: (
                player.custom_points
            ),
            reverse=True,
        )


    return result


# =========================================================
# REPLACEMENT LEVELS
# =========================================================

def calculate_replacement_levels(
    projections: List[
        PlayerProjection
    ],
    num_teams: int = NUM_TEAMS,
    starting_lineup: Optional[Sequence[str]] = None,
) -> ReplacementLevels:
    """
    Determine positional replacement levels.

    QB:
        1 starter x 12 teams.

    RB:
        2 starters x 12 teams.

    WR:
        2 starters x 12 teams.

    TE:
        1 starter x 12 teams.

    FLEX:
        2 x 12 = 24 additional starters.

    Flex allocations are determined dynamically
    by projected points among the RB/WR/TE players
    remaining after their mandatory starting slots.
    """

    grouped = (
        get_offensive_projections(
            projections
        )
    )


    # -----------------------------------------------------
    # CORE STARTER DEMAND
    # -----------------------------------------------------

    lineup = tuple(str(slot).upper() for slot in (starting_lineup or ()))
    core_starters = dict(CORE_STARTERS)
    flex_slot_eligibility = []
    if lineup:
        core_starters = {
            position: lineup.count(position)
            for position in CORE_STARTERS
        }
        flex_slot_types = {
            "FLEX": {"RB", "WR", "TE"},
            "W/R/T": {"RB", "WR", "TE"},
            "REC_FLEX": {"WR", "TE"},
            "WRRB_FLEX": {"RB", "WR"},
            "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
            "SUPERFLEX": {"QB", "RB", "WR", "TE"},
            "OP": {"QB", "RB", "WR", "TE"},
        }
        for slot in lineup:
            eligibility = flex_slot_types.get(slot)
            if eligibility:
                flex_slot_eligibility.append(eligibility)
    else:
        flex_slot_eligibility = [set(FLEX_POSITIONS)] * FLEX_PER_TEAM

    starter_demand = {
        position: (
            starters
            * num_teams
        )
        for (
            position,
            starters,
        ) in core_starters.items()
    }


    # -----------------------------------------------------
    # FLEX CANDIDATES
    # -----------------------------------------------------

    remaining_by_position = {
        position: list(players[starter_demand[position]:])
        for position, players in grouped.items()
    }
    flex_starters = []
    # Fill narrower slots first so a WR/TE-only slot cannot be consumed by a
    # player who was only needed for a later superflex opening.
    flex_slot_eligibility.sort(key=len)
    for eligibility in flex_slot_eligibility:
        for _ in range(num_teams):
            candidates = [
                players[0]
                for position, players in remaining_by_position.items()
                if position in eligibility and players
            ]
            if not candidates:
                break
            selected = max(candidates, key=lambda player: player.custom_points)
            flex_starters.append(selected)
            remaining_by_position[selected.position].pop(0)


    flex_allocations = Counter(
        player.position
        for player
        in flex_starters
    )


    # -----------------------------------------------------
    # FINAL STARTER DEMAND
    # -----------------------------------------------------

    final_demand = {
        position: demand + flex_allocations.get(position, 0)
        for position, demand in starter_demand.items()
    }


    # -----------------------------------------------------
    # FIRST NON-STARTER = REPLACEMENT PLAYER
    # -----------------------------------------------------

    replacement_points = {}


    for (
        position,
        demand,
    ) in final_demand.items():

        players = grouped[
            position
        ]


        if not players:

            replacement_points[
                position
            ] = 0.0

            continue


        # demand is also the zero-based index
        # of the first non-starting player.
        replacement_index = demand


        if (
            replacement_index
            < len(players)
        ):

            replacement_player = (
                players[
                    replacement_index
                ]
            )

        else:

            replacement_player = (
                players[-1]
            )


        replacement_points[
            position
        ] = float(
            replacement_player
            .custom_points
        )


    return ReplacementLevels(
        points_by_position=(
            replacement_points
        ),
        starter_demand=(
            final_demand
        ),
        flex_allocations=dict(
            flex_allocations
        ),
    )


# =========================================================
# PLAYER VORP
# =========================================================

def calculate_player_values(
    projections: List[
        PlayerProjection
    ],
    replacement_levels: ReplacementLevels,
) -> List[
    PlayerValue
]:

    values = []


    grouped = (
        get_offensive_projections(
            projections
        )
    )


    for (
        position,
        players,
    ) in grouped.items():

        replacement = (
            replacement_levels
            .points_by_position
            .get(
                position,
                0.0,
            )
        )


        for (
            index,
            player,
        ) in enumerate(
            players,
            start=1,
        ):

            projected_points = float(
                player.custom_points
            )


            vorp = (
                projected_points
                - replacement
            )


            values.append(
                PlayerValue(
                    player_name=(
                        player.player_name
                    ),
                    position=(
                        position
                    ),
                    projected_points=(
                        projected_points
                    ),
                    replacement_points=(
                        replacement
                    ),
                    vorp=(
                        vorp
                    ),
                    starter_rank=(
                        index
                    ),
                )
            )


    return values
