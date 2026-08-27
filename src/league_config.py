from dataclasses import dataclass
from typing import Optional


# =========================================================
# LEAGUE STRUCTURE
# =========================================================

ROSTER_SIZE = 18

STARTING_LINEUP = [
    "QB",
    "RB",
    "RB",
    "WR",
    "WR",
    "TE",
    "FLEX",
    "FLEX",
    "K",
    "DEF",
]

BENCH_SLOTS = 8

IR_SLOTS = 2

MINIMUM_AUCTION_BID = 1

BASE_AUCTION_BUDGET = 400


# =========================================================
# KEEPERS
# =========================================================

MAX_KEEPERS = 6

KEEPER_ESCALATION = 11

KEEPER_LOCK_HOURS_BEFORE_DRAFT = 48


# =========================================================
# MODEL WEIGHTS
# =========================================================

CURRENT_SEASON_WEIGHT = 0.60

FUTURE_VALUE_WEIGHT = 0.40


# =========================================================
# HISTORICAL DATA
# =========================================================

HISTORICAL_DRAFT_SHEETS = {
    2023: "23 Draft",
    2024: "24 Draft",
    2025: "25 Draft",
}

DRAFT_START_MARKER = "Start of Draft"

# 2025 contains the winning manager.
# 2023/2024 are still useful for league-wide price history.
MANAGER_HISTORY_START_YEAR = 2025


# =========================================================
# MANAGER IDENTITIES
# =========================================================

@dataclass(frozen=True)
class ManagerIdentity:
    manager_id: str
    spreadsheet_tab: str
    sleeper_roster_id: int
    sleeper_username: str
    sleeper_team_name: str
    historical_aliases: tuple[str, ...]


MANAGERS = {

    "derek": ManagerIdentity(
        manager_id="derek",
        spreadsheet_tab="Derek",
        sleeper_roster_id=1,
        sleeper_username="DMicka2014",
        sleeper_team_name="Super Ja’MARRio Bros",
        historical_aliases=("Derek",),
    ),

    "troy_l": ManagerIdentity(
        manager_id="troy_l",
        spreadsheet_tab="Troy L",
        sleeper_roster_id=2,
        sleeper_username="troylecroy4",
        sleeper_team_name="Redneck cop",
        historical_aliases=("Troy",),
    ),

    "autrey": ManagerIdentity(
        manager_id="autrey",
        spreadsheet_tab="Autrey",
        sleeper_roster_id=3,
        sleeper_username="fritz314",
        sleeper_team_name="Time to Throw a Dart-y",
        historical_aliases=("Fritz",),
    ),

    "seth": ManagerIdentity(
        manager_id="seth",
        spreadsheet_tab="Seth",
        sleeper_roster_id=4,
        sleeper_username="bugsymeyer",
        sleeper_team_name="Protostars",
        historical_aliases=("Seth",),
    ),

    "tallevast": ManagerIdentity(
        manager_id="tallevast",
        spreadsheet_tab="Tallevast",
        sleeper_roster_id=5,
        sleeper_username="zeke11111",
        sleeper_team_name="Tally",
        historical_aliases=("Zach",),
    ),

    "jaylen": ManagerIdentity(
        manager_id="jaylen",
        spreadsheet_tab="Jaylen",
        sleeper_roster_id=6,
        sleeper_username="jaylenh22",
        sleeper_team_name="The Fighting Jaylen’s",
        historical_aliases=("Jaylen",),
    ),

    "ernest": ManagerIdentity(
        manager_id="ernest",
        spreadsheet_tab="Ernest",
        sleeper_roster_id=7,
        sleeper_username="Econcialdi",
        sleeper_team_name="No knees and a dream",
        historical_aliases=("Ern", "Ernest"),
    ),

    "ted_d": ManagerIdentity(
        manager_id="ted_d",
        spreadsheet_tab="Ted D",
        sleeper_roster_id=8,
        sleeper_username="redbavarian10",
        sleeper_team_name="redbavarian10",
        historical_aliases=("Ryan",),
    ),

    "stephen_m": ManagerIdentity(
        manager_id="stephen_m",
        spreadsheet_tab="Stephen M",
        sleeper_roster_id=9,
        sleeper_username="ItsPete17",
        sleeper_team_name="LIGMA",
        historical_aliases=("Pete",),
    ),

    "brandon": ManagerIdentity(
        manager_id="brandon",
        spreadsheet_tab="Brandon",
        sleeper_roster_id=10,
        sleeper_username="WhiteTrashTank",
        sleeper_team_name="Lol Fuck This Sport",
        historical_aliases=("Brandon",),
    ),

    "nobs": ManagerIdentity(
        manager_id="nobs",
        spreadsheet_tab="Nobs",
        sleeper_roster_id=11,
        sleeper_username="nobZ24",
        sleeper_team_name="Likely Baked",
        historical_aliases=("Nobs",),
    ),

    "josh_cosey": ManagerIdentity(
        manager_id="josh_cosey",
        spreadsheet_tab="Josh Cosey",
        sleeper_roster_id=12,
        sleeper_username="Jcoz15",
        sleeper_team_name="Jcoz15",
        historical_aliases=("Cosey",),
    ),
}


MY_MANAGER_ID = "tallevast"


# =========================================================
# ALIAS LOOKUPS
# =========================================================

HISTORICAL_MANAGER_ALIASES = {}

for manager_id, manager in MANAGERS.items():

    for alias in manager.historical_aliases:

        HISTORICAL_MANAGER_ALIASES[
            alias.strip().lower()
        ] = manager_id


def resolve_historical_manager(
        alias: str) -> Optional[str]:

    if not alias:
        return None

    return HISTORICAL_MANAGER_ALIASES.get(
        alias.strip().lower()
    )