import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


# =========================================================
# ELIGIBLE AUCTION POSITIONS
# =========================================================

AUCTION_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
    "K",
    "DEF",
}


NFL_TEAM_NAMES = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs",
    "LV": "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE": "New England Patriots",
    "NO": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers",
    "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
}


# =========================================================
# DATA OBJECTS
# =========================================================

@dataclass
class AuctionPlayer:

    sleeper_id: str

    player_name: str

    position: str

    nfl_team: Optional[str]

    status: Optional[str]

    active: bool

    depth_chart_position: Optional[str] = None

    depth_chart_order: Optional[int] = None

    years_exp: Optional[int] = None

    age: Optional[int] = None


@dataclass
class AuctionPoolResult:

    available_players: List[AuctionPlayer]

    excluded_keepers: List[str]

    excluded_college: List[str]

    unmatched_keepers: List[str] = field(
        default_factory=list
    )

    unmatched_nfl_college: List[str] = field(
        default_factory=list
    )


# =========================================================
# NAME NORMALIZATION
# =========================================================

def normalize_player_name(
    value,
) -> str:
    """
    Normalize names between Sleeper and the workbook.

    Examples:

    Ja'Marr Chase -> jamarr chase
    D'Andre Swift -> dandre swift
    A.J. Brown -> aj brown
    """

    if value is None:
        return ""

    value = str(
        value
    ).lower().strip()

    # Remove punctuation but preserve spaces.
    value = re.sub(
        r"[^a-z0-9 ]",
        "",
        value,
    )

    # Collapse repeated whitespace.
    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# =========================================================
# SLEEPER PLAYER DISPLAY NAME
# =========================================================

def sleeper_player_name(
    player_id: str,
    player: dict,
) -> str:

    position = (
        player.get("position")
        or ""
    ).upper()

    team = (
        player.get("team")
        or player_id
    )

    if position == "DEF":

        return NFL_TEAM_NAMES.get(
            team,
            team,
        )

    full_name = (
        player.get("full_name")
        or ""
    ).strip()

    if full_name:
        return full_name

    first_name = (
        player.get("first_name")
        or ""
    )

    last_name = (
        player.get("last_name")
        or ""
    )

    constructed = (
        f"{first_name} {last_name}"
    ).strip()

    if constructed:
        return constructed

    return str(
        player_id
    )


# =========================================================
# SLEEPER NAME INDEX
# =========================================================

def build_sleeper_name_index(
    sleeper_players: Dict[str, dict],
) -> Dict[str, List[str]]:
    """
    Create:

    normalized name -> Sleeper player IDs

    We store a list because duplicate human names
    theoretically can exist.
    """

    index = {}

    for player_id, player in (
        sleeper_players.items()
    ):

        player_name = (
            sleeper_player_name(
                player_id,
                player,
            )
        )

        normalized = (
            normalize_player_name(
                player_name
            )
        )

        if not normalized:
            continue

        if normalized not in index:
            index[normalized] = []

        index[
            normalized
        ].append(
            player_id
        )

    return index


# =========================================================
# PROTECTED PLAYER LOOKUP
# =========================================================

def find_sleeper_id(
    player_name: str,
    name_index: Dict[
        str,
        List[str],
    ],
) -> Optional[str]:

    normalized = normalize_player_name(
        player_name
    )

    matches = name_index.get(
        normalized,
        [],
    )

    if len(matches) == 1:
        return matches[0]

    # If there are multiple players with the same
    # name we do NOT guess.
    return None


# =========================================================
# BUILD AUCTION POOL
# =========================================================

def build_auction_pool(
    sleeper_players: Dict[str, dict],
    league_data,
    team_setups,
) -> AuctionPoolResult:

    name_index = (
        build_sleeper_name_index(
            sleeper_players
        )
    )

    protected_sleeper_ids: Set[str] = set()

    excluded_keepers = []

    excluded_college = []

    unmatched_keepers = []

    unmatched_nfl_college = []


    # =====================================================
    # SELECTED KEEPERS
    # =====================================================

    for setup in team_setups.values():

        for keeper in setup.keepers:

            excluded_keepers.append(
                keeper.player_name
            )

            sleeper_id = (
                find_sleeper_id(
                    keeper.player_name,
                    name_index,
                )
            )

            if sleeper_id is None:

                unmatched_keepers.append(
                    keeper.player_name
                )

                continue

            protected_sleeper_ids.add(
                sleeper_id
            )


    # =====================================================
    # COLLEGE RIGHTS
    # =====================================================

    for college_player in (
        league_data.college_players
    ):

        excluded_college.append(
            college_player.player_name
        )

        explicit_sleeper_id = getattr(
            college_player,
            "sleeper_player_id",
            None,
        )
        sleeper_id = (
            str(explicit_sleeper_id)
            if explicit_sleeper_id is not None
            and str(explicit_sleeper_id) in sleeper_players
            else find_sleeper_id(
                college_player.player_name,
                name_index,
            )
        )

        if sleeper_id is not None:

            protected_sleeper_ids.add(
                sleeper_id
            )

        else:

            # Blue/in-college players may not exist
            # in Sleeper yet. That's perfectly normal.
            #
            # Gold/NFL players SHOULD normally exist.
            if (
                college_player.status
                == "in_nfl"
            ):

                unmatched_nfl_college.append(
                    college_player.player_name
                )


    # =====================================================
    # BUILD DRAFTABLE PLAYER UNIVERSE
    # =====================================================

    available_players = []


    for player_id, player in (
        sleeper_players.items()
    ):

        position = (
            player.get("position")
            or ""
        ).upper()


        # Only fantasy positions used by our league.
        if position not in AUCTION_POSITIONS:
            continue


        # Exclude inactive / historical Sleeper records.
        active = player.get(
            "active"
        )

        if active is False:
            continue


        # Protected keeper / college right.
        if (
            player_id
            in protected_sleeper_ids
        ):
            continue


        player_name = (
            sleeper_player_name(
                player_id,
                player,
            )
        )


        # Avoid unnamed garbage rows.
        if not player_name:
            continue


        available_players.append(
            AuctionPlayer(
                sleeper_id=player_id,
                player_name=player_name,
                position=position,
                nfl_team=(
                    player.get("team")
                ),
                status=(
                    player.get("status")
                ),
                active=(
                    True
                    if active is not False
                    else False
                ),
                depth_chart_position=(
                    player.get(
                        "depth_chart_position"
                    )
                ),
                depth_chart_order=(
                    player.get(
                        "depth_chart_order"
                    )
                ),
                years_exp=(
                    player.get(
                        "years_exp"
                    )
                ),
                age=(
                    player.get(
                        "age"
                    )
                ),
            )
        )


    # =====================================================
    # SORT
    # =====================================================

    position_order = {
        "QB": 1,
        "RB": 2,
        "WR": 3,
        "TE": 4,
        "K": 5,
        "DEF": 6,
    }


    available_players.sort(
        key=lambda player: (
            position_order.get(
                player.position,
                99,
            ),
            player.player_name,
        )
    )


    return AuctionPoolResult(
        available_players=available_players,
        excluded_keepers=excluded_keepers,
        excluded_college=excluded_college,
        unmatched_keepers=unmatched_keepers,
        unmatched_nfl_college=(
            unmatched_nfl_college
        ),
    )
