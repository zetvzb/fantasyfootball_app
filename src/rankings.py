from dataclasses import dataclass
from typing import Dict, List, Optional

from src.auction_pool import (
    normalize_player_name,
)


@dataclass
class PlayerRanking:

    source: str

    player_name: str

    position: Optional[str]

    nfl_team: Optional[str]

    overall_rank: Optional[float]

    position_rank: Optional[float]

    tier: Optional[int]

    fantasypros_id: Optional[str]

    rank_min: Optional[float] = None

    rank_max: Optional[float] = None

    rank_std_dev: Optional[float] = None


# =========================================================
# NUMBER HELPERS
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


# =========================================================
# FANTASYPROS NORMALIZER
# =========================================================

def normalize_fantasypros_rankings(
    response: dict,
) -> List[PlayerRanking]:

    rankings = []

    players = response.get(
        "players",
        [],
    )

    for player in players:

        player_name = (
            player.get(
                "player_name"
            )
            or player.get(
                "name"
            )
        )

        if not player_name:
            continue

        ranking = PlayerRanking(
            source="FantasyPros",

            player_name=player_name,

            position=(
                player.get(
                    "player_position_id"
                )
                or player.get(
                    "position_id"
                )
                or player.get(
                    "position"
                )
            ),

            nfl_team=(
                player.get(
                    "player_team_id"
                )
                or player.get(
                    "team_id"
                )
                or player.get(
                    "team"
                )
            ),

            overall_rank=(
                numeric(
                    player.get(
                        "rank_ecr"
                    )
                )
                or numeric(
                    player.get(
                        "rank"
                    )
                )
            ),

            position_rank=(
                numeric(
                    player.get(
                        "pos_rank"
                    )
                )
                or numeric(
                    player.get(
                        "rank_position"
                    )
                )
            ),

            tier=(
                int(
                    player["tier"]
                )
                if player.get(
                    "tier"
                ) is not None
                else None
            ),

            fantasypros_id=(
                str(
                    player.get(
                        "player_id"
                    )
                )
                if player.get(
                    "player_id"
                ) is not None
                else None
            ),

            rank_min=(
                numeric(
                    player.get(
                        "rank_min"
                    )
                )
            ),

            rank_max=(
                numeric(
                    player.get(
                        "rank_max"
                    )
                )
            ),

            rank_std_dev=(
                numeric(
                    player.get(
                        "rank_std"
                    )
                )
                or numeric(
                    player.get(
                        "rank_std_dev"
                    )
                )
            ),
        )

        rankings.append(
            ranking
        )

    return rankings


# =========================================================
# INDEX
# =========================================================

def build_ranking_index(
    rankings: List[PlayerRanking],
) -> Dict[str, PlayerRanking]:

    return {
        normalize_player_name(
            ranking.player_name
        ): ranking

        for ranking in rankings
    }