from dataclasses import dataclass
from typing import Dict, List, Optional

from src.auction_pool import (
    normalize_player_name,
)


# =========================================================
# DATA OBJECT
# =========================================================

@dataclass
class FantasyProsPlayerIntelligence:

    fantasypros_id: str

    player_name: str

    position: Optional[str]

    nfl_team: Optional[str]

    # Current-season value
    half_ecr: Optional[float]

    half_position_rank: Optional[float]

    # Dynasty / future value
    dynasty_ecr: Optional[float]

    dynasty_position_rank: Optional[float]

    # Market signal
    adp: Optional[float]

    # Expert uncertainty
    ecr_min: Optional[float]

    ecr_max: Optional[float]

    ecr_avg: Optional[float]

    ecr_std: Optional[float]


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

    return value


def nested_get(
    data: dict,
    *keys,
):

    current = data

    for key in keys:

        if not isinstance(
            current,
            dict,
        ):
            return None

        current = current.get(
            key
        )

        if current is None:
            return None

    return current


# =========================================================
# PLAYER METADATA LOOKUP
# =========================================================

def build_player_metadata_lookup(
    players_response: dict,
) -> Dict[str, dict]:

    result = {}

    for player in (
        players_response.get(
            "players",
            [],
        )
    ):

        player_id = (
            player.get(
                "player_id"
            )
        )

        if player_id is None:
            continue

        result[
            str(player_id)
        ] = player

    return result


# =========================================================
# NORMALIZE FULL FANTASYPROS DATA
# =========================================================

def normalize_fantasypros_intelligence(
    rankings_response: dict,
    players_response: dict,
) -> List[
    FantasyProsPlayerIntelligence
]:

    player_metadata = (
        build_player_metadata_lookup(
            players_response
        )
    )

    results = []


    for player in (
        rankings_response.get(
            "players",
            [],
        )
    ):

        player_id = (
            player.get(
                "id"
            )
        )

        player_name = (
            player.get(
                "player_name"
            )
        )

        if (
            player_id is None
            or not player_name
        ):
            continue


        fp_id = str(
            player_id
        )


        metadata = (
            player_metadata.get(
                fp_id,
                {},
            )
        )


        raw_position = (
            player.get(
                "position_id"
            )
            or metadata.get(
                "position_id"
            )
        )


        position = (
            normalize_position(
                raw_position
            )
        )


        team = (
            player.get(
                "team_id"
            )
            or metadata.get(
                "team_id"
            )
        )


        rank_data = (
            player.get(
                "rank",
                {},
            )
        )


        # =================================================
        # HALF-PPR CURRENT-SEASON ECR
        # =================================================

        half_ecr = numeric(
            nested_get(
                rank_data,
                "ECR",
                "HALF",
                "ALL",
            )
        )


        half_position_rank = None


        if raw_position:

            half_position_rank = numeric(
                nested_get(
                    rank_data,
                    "ECR",
                    "HALF",
                    raw_position,
                )
            )


        # =================================================
        # DYNASTY ECR
        # =================================================

        dynasty_ecr = numeric(
            nested_get(
                rank_data,
                "ECR",
                "DYN",
                "ALL",
            )
        )


        dynasty_position_rank = None


        if raw_position:

            dynasty_position_rank = numeric(
                nested_get(
                    rank_data,
                    "ECR",
                    "DYN",
                    raw_position,
                )
            )


        # =================================================
        # HALF-PPR EXPERT RANGE
        # =================================================

        ecr_min = numeric(
            nested_get(
                rank_data,
                "ECR_MIN",
                "HALF",
                "ALL",
            )
        )


        ecr_max = numeric(
            nested_get(
                rank_data,
                "ECR_MAX",
                "HALF",
                "ALL",
            )
        )


        ecr_avg = numeric(
            nested_get(
                rank_data,
                "ECR_AVG",
                "HALF",
                "ALL",
            )
        )


        ecr_std = numeric(
            nested_get(
                rank_data,
                "ECR_STD",
                "HALF",
                "ALL",
            )
        )


        # =================================================
        # ADP
        # =================================================

        adp = numeric(
            metadata.get(
                "rank_adp"
            )
        )


        results.append(
            FantasyProsPlayerIntelligence(
                fantasypros_id=(
                    fp_id
                ),
                player_name=(
                    player_name
                ),
                position=(
                    position
                ),
                nfl_team=(
                    team
                ),
                half_ecr=(
                    half_ecr
                ),
                half_position_rank=(
                    half_position_rank
                ),
                dynasty_ecr=(
                    dynasty_ecr
                ),
                dynasty_position_rank=(
                    dynasty_position_rank
                ),
                adp=(
                    adp
                ),
                ecr_min=(
                    ecr_min
                ),
                ecr_max=(
                    ecr_max
                ),
                ecr_avg=(
                    ecr_avg
                ),
                ecr_std=(
                    ecr_std
                ),
            )
        )


    return results


# =========================================================
# INDEX FOR AUCTION BOARD
# =========================================================

def build_intelligence_index(
    players: List[
        FantasyProsPlayerIntelligence
    ],
) -> Dict[
    str,
    FantasyProsPlayerIntelligence
]:

    result = {}


    for player in players:

        normalized_name = (
            normalize_player_name(
                player.player_name
            )
        )

        if not normalized_name:
            continue


        result[
            normalized_name
        ] = player


    return result