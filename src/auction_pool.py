import difflib
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Set

# Below this similarity, two names are treated as unrelated rather than a
# likely typo/nickname variant across sources (e.g. a workbook vs Sleeper).
FUZZY_NAME_MATCH_CUTOFF = 0.84


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

    unmatched_keepers: List[str] = field(
        default_factory=list
    )


# =========================================================
# NAME NORMALIZATION
# =========================================================

_GENERATIONAL_SUFFIX = re.compile(r"\s+(jr|sr|ii|iii|iv)$")


@lru_cache(maxsize=8192)
def _normalize_player_name_cached(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9 ]", "", value)
    value = re.sub(r"\s+", " ", value)
    value = _GENERATIONAL_SUFFIX.sub("", value)
    return value.strip()


def normalize_player_name(
    value,
) -> str:
    """
    Normalize names between Sleeper and the workbook.

    Examples:

    Ja'Marr Chase -> jamarr chase
    D'Andre Swift -> dandre swift
    A.J. Brown -> aj brown

    Sources disagree on whether a generational suffix is included (Sleeper:
    "Kenneth Walker", FantasyPros: "Kenneth Walker III") -- stripped here so
    both sides key to the same identity instead of silently missing each
    other in every direct-dict lookup.

    Hot path: called tens of thousands of times per rerun (scarcity, threats,
    every value lookup), so the regex work is memoised on the raw string.
    """

    if value is None:
        return ""
    return _normalize_player_name_cached(str(value))


# A relocated franchise that kept its nickname (e.g. the Rams moving from
# St. Louis to LA) already resolves via the nickname alone. This only
# needs the old CITY, for long-running leagues whose draft-history sheets
# predate the move.
_RELOCATED_FRANCHISE_CITIES = {
    "LAR": ("St. Louis", "Los Angeles Rams"),
    "LAC": ("San Diego", "Los Angeles Chargers"),
    "LV": ("Oakland", "Las Vegas Raiders"),
}


def _build_defense_name_aliases() -> Dict[str, str]:
    """Map a bare city name or nickname (e.g. "Houston", "Texans") to the
    full team name Sleeper's own DEF entries use ("Houston Texans").

    Spreadsheets frequently record a defense as just the city -- normal
    player-name matching never resolves that against a real athlete, so
    without this it gets flagged as an unmatched keeper. A city shared by
    two franchises ("Los Angeles", "New York") is intentionally left out
    since there's no single team to guess; the nickname alone still
    resolves those unambiguously. A relocated franchise's old city (e.g.
    "St. Louis") is also included, for draft-history sheets old enough to
    predate the move.
    """

    aliases: Dict[str, str] = {}
    city_hits: Dict[str, int] = {}
    for full_name in NFL_TEAM_NAMES.values():
        city = " ".join(full_name.split()[:-1])
        city_hits[city] = city_hits.get(city, 0) + 1

    for full_name in NFL_TEAM_NAMES.values():
        words = full_name.split()
        city = " ".join(words[:-1])
        nickname = words[-1]
        normalized_full = normalize_player_name(full_name)
        if city_hits[city] == 1:
            aliases[normalize_player_name(city)] = normalized_full
        aliases[normalize_player_name(nickname)] = normalized_full

    for old_city, current_full_name in _RELOCATED_FRANCHISE_CITIES.values():
        aliases[normalize_player_name(old_city)] = normalize_player_name(
            current_full_name
        )

    return aliases


_NFL_DEFENSE_NAME_ALIASES = _build_defense_name_aliases()


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
    *,
    fuzzy: bool = True,
) -> Optional[str]:
    """Resolve an imported/workbook player name to a Sleeper player id.

    Tries an exact normalized-name match first. If nothing matches and
    ``fuzzy`` is enabled, falls back to the closest normalized name in the
    index (via difflib) when it's a confident, unique candidate above
    ``FUZZY_NAME_MATCH_CUTOFF`` -- this is what lets spreadsheet spelling
    variants/typos resolve without a human reviewing every import row.
    Multiple Sleeper players sharing the exact same normalized name are
    still never guessed between, exact or fuzzy.
    """

    normalized = normalize_player_name(
        player_name
    )
    normalized = _NFL_DEFENSE_NAME_ALIASES.get(normalized, normalized)

    matches = name_index.get(
        normalized,
        [],
    )

    if len(matches) == 1:
        return matches[0]

    if matches or not fuzzy or not normalized:
        # Either an exact ambiguous collision (do not guess) or nothing to
        # fuzzy-match against.
        return None

    close = difflib.get_close_matches(
        normalized,
        name_index.keys(),
        n=1,
        cutoff=FUZZY_NAME_MATCH_CUTOFF,
    )
    if not close:
        return None

    fuzzy_matches = name_index.get(close[0], [])
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]

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

    unmatched_keepers = []


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


        # Protected keeper.
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
        unmatched_keepers=unmatched_keepers,
    )
