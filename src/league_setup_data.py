from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Tuple

if TYPE_CHECKING:
    from src.league_data import LeagueWorkbookData
from src.league_profile import LeagueProfile


# =========================================================
# SOURCE / PROVENANCE
# =========================================================

SOURCE_PRIORITY = {
    "default": 100,
    "sleeper": 200,
    "workbook": 300,
    "import": 350,
    "manual": 400,
}


def normalize_player_name(
    value: Optional[str],
) -> str:

    if value is None:
        return ""

    text = str(
        value
    ).lower().strip()

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    return " ".join(
        text.split()
    )


@dataclass(frozen=True)
class SourceInfo:
    source: str
    confidence: float = 1.0
    inferred: bool = False
    detail: Optional[str] = None

    @property
    def priority(self) -> int:
        return SOURCE_PRIORITY.get(
            self.source,
            0,
        )


DEFAULT_SOURCE = SourceInfo(
    source="default",
    confidence=1.0,
    inferred=True,
    detail="League-wide default",
)

SLEEPER_SOURCE = SourceInfo(
    source="sleeper",
    confidence=0.95,
    inferred=False,
    detail="Sleeper league/roster data",
)

WORKBOOK_SOURCE = SourceInfo(
    source="workbook",
    confidence=1.0,
    inferred=False,
    detail="League workbook",
)

MANUAL_SOURCE = SourceInfo(
    source="manual",
    confidence=1.0,
    inferred=False,
    detail="User-entered setup data",
)


# =========================================================
# NORMALIZED SETUP OBJECTS
# =========================================================

@dataclass(frozen=True)
class TeamBudget:
    manager_id: str
    amount: int

    # "pre_keeper" means keeper salaries still need to be
    # subtracted. "auction_cash" means this is already the
    # cash available when the auction begins.
    budget_kind: str = "auction_cash"

    source: SourceInfo = field(
        default_factory=lambda: DEFAULT_SOURCE
    )


@dataclass(frozen=True)
class RosterPlayer:
    manager_id: str
    player_name: str
    position: Optional[str] = None
    sleeper_player_id: Optional[str] = None
    nfl_team: Optional[str] = None
    roster_status: str = "active"
    source: SourceInfo = field(
        default_factory=lambda: SLEEPER_SOURCE
    )


@dataclass(frozen=True)
class KeeperRecord:
    manager_id: str
    player_name: str
    position: Optional[str] = None
    cost: Optional[int] = None

    # explicit = cost is already the current keeper price
    # returning = prior_year_cost + the league escalation
    # midseason_pickup = the league's next-season pickup price
    cost_basis: str = "explicit"
    prior_year_cost: Optional[int] = None

    # Optional inputs for the later 2-3 year recommendation/economics engines.
    future_values: Tuple[Optional[float], ...] = ()

    # candidate = eligible/possible keeper
    # finalized = protected for this auction
    status: str = "finalized"

    sleeper_player_id: Optional[str] = None
    source: SourceInfo = field(
        default_factory=lambda: MANUAL_SOURCE
    )


@dataclass(frozen=True)
class HistoricalSale:
    year: int
    player_name: str
    price: int

    manager_id: Optional[str] = None
    manager_raw: Optional[str] = None
    position: Optional[str] = None

    source: SourceInfo = field(
        default_factory=lambda: MANUAL_SOURCE
    )


@dataclass
class LeagueSetupData:
    league_key: str

    budgets: Dict[
        str,
        TeamBudget,
    ] = field(
        default_factory=dict
    )

    roster_players: List[
        RosterPlayer
    ] = field(
        default_factory=list
    )

    keepers: List[
        KeeperRecord
    ] = field(
        default_factory=list
    )

    historical_sales: List[
        HistoricalSale
    ] = field(
        default_factory=list
    )

    warnings: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, object] = field(
        default_factory=dict
    )

    # League-level list of players that are off the board for a reason the
    # app cannot infer (traded away in a keeper league, holdout, suspension).
    # Populated only by the manual override layer; excluded from the auction
    # pool / nominations / draft and shaded blue in the depth charts.
    unavailable_players: List[str] = field(
        default_factory=list
    )

    # =====================================================
    # CONVENIENCE
    # =====================================================

    def budget_for(
        self,
        manager_id: str,
        default: Optional[int] = None,
    ) -> Optional[int]:

        record = self.budgets.get(
            manager_id
        )

        if record is None:
            return default

        return int(
            record.amount
        )


    def keepers_for(
        self,
        manager_id: str,
        *,
        finalized_only: bool = False,
    ) -> List[KeeperRecord]:

        records = [
            keeper

            for keeper
            in self.keepers

            if keeper.manager_id
            == manager_id
        ]

        if finalized_only:

            records = [
                keeper

                for keeper
                in records

                if keeper.status
                == "finalized"
            ]

        return records


    def roster_for(
        self,
        manager_id: str,
    ) -> List[RosterPlayer]:

        return [
            player

            for player
            in self.roster_players

            if player.manager_id
            == manager_id
        ]


    @property
    def has_history(self) -> bool:
        return bool(
            self.historical_sales
        )


    @property
    def has_explicit_keepers(self) -> bool:

        return any(
            keeper.source.source
            in {
                "manual",
                "workbook",
                "import",
            }

            for keeper
            in self.keepers
        )


    @property
    def source_summary(self) -> Dict[str, int]:

        counts: Dict[str, int] = {}

        records = (
            list(
                self.budgets.values()
            )
            + self.roster_players
            + self.keepers
            + self.historical_sales
        )

        for record in records:

            source_name = (
                record.source.source
            )

            counts[
                source_name
            ] = (
                counts.get(
                    source_name,
                    0,
                )
                + 1
            )

        return counts


    # =====================================================
    # MERGE
    # =====================================================

    def merged_with(
        self,
        other: "LeagueSetupData",
    ) -> "LeagueSetupData":
        """
        Merge another setup object into this one.

        Higher-priority provenance wins:
        manual > import > workbook > Sleeper > default.

        This allows us to build a league progressively without
        coupling the recommendation engine to any one input
        format.
        """

        if (
            self.league_key
            != other.league_key
        ):

            raise ValueError(
                "Cannot merge setup data from "
                "different leagues."
            )


        budgets = dict(
            self.budgets
        )

        for (
            manager_id,
            record,
        ) in other.budgets.items():

            current = budgets.get(
                manager_id
            )

            if (
                current is None
                or
                record.source.priority
                >= current.source.priority
            ):

                budgets[
                    manager_id
                ] = record


        roster_players = _merge_records(
            self.roster_players,
            other.roster_players,
            key_func=_roster_key,
        )


        keepers = _merge_records(
            self.keepers,
            other.keepers,
            key_func=_keeper_key,
        )


        historical_sales = _merge_records(
            self.historical_sales,
            other.historical_sales,
            key_func=_history_key,
        )


        warnings = list(
            dict.fromkeys(
                self.warnings
                + other.warnings
            )
        )


        metadata = {
            **self.metadata,
            **other.metadata,
        }


        unavailable_players = list(
            dict.fromkeys(
                list(self.unavailable_players)
                + list(other.unavailable_players)
            )
        )


        return LeagueSetupData(
            league_key=(
                self.league_key
            ),
            budgets=budgets,
            roster_players=(
                roster_players
            ),
            keepers=keepers,
            historical_sales=(
                historical_sales
            ),
            warnings=warnings,
            metadata=metadata,
            unavailable_players=(
                unavailable_players
            ),
        )


    # =====================================================
    # SERIALIZATION
    # =====================================================

    def to_dict(self) -> dict:

        return asdict(
            self
        )


    @classmethod
    def from_dict(
        cls,
        payload: dict,
    ) -> "LeagueSetupData":

        budgets = {
            manager_id: TeamBudget(
                manager_id=record[
                    "manager_id"
                ],
                amount=int(
                    record[
                        "amount"
                    ]
                ),
                budget_kind=record.get(
                    "budget_kind",
                    "auction_cash",
                ),
                source=SourceInfo(
                    **record.get(
                        "source",
                        {
                            "source": "manual",
                        },
                    )
                ),
            )

            for (
                manager_id,
                record,
            ) in (
                payload.get(
                    "budgets"
                )
                or {}
            ).items()
        }


        return cls(
            league_key=str(
                payload[
                    "league_key"
                ]
            ),
            budgets=budgets,
            roster_players=[
                _roster_from_dict(
                    record
                )

                for record
                in (
                    payload.get(
                        "roster_players"
                    )
                    or []
                )
            ],
            keepers=[
                _keeper_from_dict(
                    record
                )

                for record
                in (
                    payload.get(
                        "keepers"
                    )
                    or []
                )
            ],
            historical_sales=[
                _history_from_dict(
                    record
                )

                for record
                in (
                    payload.get(
                        "historical_sales"
                    )
                    or []
                )
            ],
            warnings=list(
                payload.get(
                    "warnings"
                )
                or []
            ),
            metadata=dict(
                payload.get(
                    "metadata"
                )
                or {}
            ),
            unavailable_players=list(
                payload.get(
                    "unavailable_players"
                )
                or []
            ),
        )


    # =====================================================
    # SOURCE ADAPTERS
    # =====================================================

    @classmethod
    def from_sleeper(
        cls,
        league_profile: LeagueProfile,
        rosters: Iterable[dict],
        sleeper_players: Dict[str, dict],
        *,
        default_budget: Optional[int] = None,
    ) -> "LeagueSetupData":
        """
        Build the baseline setup from facts Sleeper can provide.

        Sleeper is authoritative for current roster membership,
        but roster membership is deliberately NOT treated as a
        finalized keeper decision. That distinction is preserved
        for the Pre-Draft Setup workflow.
        """

        if default_budget is None:

            default_budget = int(
                league_profile
                .auction
                .base_budget
            )


        manager_by_roster_id = {
            int(
                identity.sleeper_roster_id
            ): manager_id

            for (
                manager_id,
                identity,
            ) in (
                league_profile
                .managers
                .items()
            )

            if (
                identity.sleeper_roster_id
                is not None
            )
        }


        # In a keeper auction the Sleeper budget is the salary cap that
        # keeper costs are still subtracted from; without keepers it is
        # already the cash available when the auction starts.
        default_budget_kind = (
            "pre_keeper"
            if getattr(league_profile.keepers, "enabled", False)
            else "auction_cash"
        )
        budgets = {
            manager_id: TeamBudget(
                manager_id=(
                    manager_id
                ),
                amount=int(
                    default_budget
                ),
                budget_kind=(
                    default_budget_kind
                ),
                source=SourceInfo(
                    source="default",
                    confidence=1.0,
                    inferred=True,
                    detail=(
                        "General league auction "
                        "budget applied to all teams"
                    ),
                ),
            )

            for manager_id
            in league_profile.managers
        }


        roster_players: List[
            RosterPlayer
        ] = []

        # Sleeper carries pre-draft keeper picks on the roster object
        # (roster["keepers"] is a list of player ids). Sleeper is
        # authoritative for WHO is kept; it does not carry a keeper
        # salary, so these land as candidates for the Pre-Draft Setup
        # UI to attach an explicit cost to.
        keepers: List[
            KeeperRecord
        ] = []


        for roster in rosters:

            roster_id = roster.get(
                "roster_id"
            )

            if roster_id is None:
                continue


            manager_id = (
                manager_by_roster_id.get(
                    int(
                        roster_id
                    )
                )
            )

            if manager_id is None:
                continue


            for keeper_id in (
                roster.get("keepers") or []
            ):

                keeper_id = str(keeper_id)

                keeper_player = (
                    sleeper_players.get(
                        keeper_id,
                        {},
                    )
                )

                keeper_name = (
                    _sleeper_player_name(
                        keeper_id,
                        keeper_player,
                    )
                )

                if not keeper_name:
                    continue

                keepers.append(
                    KeeperRecord(
                        manager_id=(
                            manager_id
                        ),
                        player_name=(
                            keeper_name
                        ),
                        position=(
                            keeper_player.get(
                                "position"
                            )
                        ),
                        cost=None,
                        status="candidate",
                        sleeper_player_id=(
                            keeper_id
                        ),
                        source=SLEEPER_SOURCE,
                    )
                )


            active_ids = list(
                roster.get(
                    "players"
                )
                or []
            )

            reserve_ids = set(
                roster.get(
                    "reserve"
                )
                or []
            )

            taxi_ids = set(
                roster.get(
                    "taxi"
                )
                or []
            )


            for player_id in active_ids:

                player_id = str(
                    player_id
                )

                player = (
                    sleeper_players.get(
                        player_id,
                        {}
                    )
                )

                player_name = (
                    _sleeper_player_name(
                        player_id,
                        player,
                    )
                )

                if not player_name:
                    continue


                roster_status = "active"

                if player_id in taxi_ids:

                    roster_status = (
                        "taxi"
                    )

                elif player_id in reserve_ids:

                    roster_status = (
                        "reserve"
                    )


                roster_players.append(
                    RosterPlayer(
                        manager_id=(
                            manager_id
                        ),
                        player_name=(
                            player_name
                        ),
                        position=(
                            player.get(
                                "position"
                            )
                        ),
                        sleeper_player_id=(
                            player_id
                        ),
                        nfl_team=(
                            player.get(
                                "team"
                            )
                        ),
                        roster_status=(
                            roster_status
                        ),
                        source=SLEEPER_SOURCE,
                    )
                )


        return cls(
            league_key=(
                league_profile.league_key
            ),
            budgets=budgets,
            roster_players=(
                roster_players
            ),
            keepers=keepers,
            warnings=[],
            metadata={
                "baseline_source": (
                    "sleeper"
                ),
                "general_budget": int(
                    default_budget
                ),
            },
        )


    @classmethod
    def from_workbook(
        cls,
        league_profile: LeagueProfile,
        workbook_data: "LeagueWorkbookData",
    ) -> "LeagueSetupData":

        budgets: Dict[
            str,
            TeamBudget,
        ] = {}

        keepers: List[
            KeeperRecord
        ] = []


        for (
            manager_id,
            manager,
        ) in workbook_data.managers.items():

            budgets[
                manager_id
            ] = TeamBudget(
                manager_id=(
                    manager_id
                ),
                amount=int(
                    manager.pre_keeper_budget
                ),
                budget_kind=(
                    "pre_keeper"
                ),
                source=WORKBOOK_SOURCE,
            )


            for keeper in (
                manager.keeper_options
            ):

                keepers.append(
                    KeeperRecord(
                        manager_id=(
                            manager_id
                        ),
                        player_name=(
                            keeper.player_name
                        ),
                        position=(
                            keeper.position
                        ),
                        cost=(
                            keeper.keeper_cost
                        ),
                        status="candidate",
                        source=WORKBOOK_SOURCE,
                    )
                )


        historical_sales = [
            HistoricalSale(
                year=int(
                    sale.year
                ),
                player_name=(
                    sale.player_name
                ),
                price=int(
                    sale.price
                ),
                manager_id=(
                    sale.manager_id
                ),
                manager_raw=(
                    sale.manager_raw
                ),
                source=WORKBOOK_SOURCE,
            )

            for sale
            in workbook_data.historical_sales
        ]


        return cls(
            league_key=(
                league_profile.league_key
            ),
            budgets=budgets,
            keepers=keepers,
            historical_sales=(
                historical_sales
            ),
            warnings=list(
                workbook_data.warnings
            ),
            metadata={
                "workbook_loaded": True,
            },
        )


    # =====================================================
    # LEGACY ENGINE ADAPTER
    # =====================================================

    def to_legacy_workbook_data(
        self,
        league_profile: LeagueProfile,
    ) -> "LeagueWorkbookData":
        """
        Temporary adapter for the existing engine.

        app.py can now normalize all data sources first, while
        auction_pool, draft_setup, and historical_market keep
        consuming their current LeagueWorkbookData shape until
        those modules are migrated.
        """

        from src.league_data import (
            HistoricalAuctionSale,
            KeeperOption,
            LeagueWorkbookData,
            ManagerLeagueData,
        )

        managers: Dict[
            str,
            ManagerLeagueData,
        ] = {}


        for (
            manager_id,
            identity,
        ) in league_profile.managers.items():

            budget = self.budgets.get(
                manager_id
            )


            if budget is None:

                budget_amount = int(
                    league_profile
                    .auction
                    .base_budget
                )

                budget_kind = (
                    "auction_cash"
                )

            else:

                budget_amount = int(
                    budget.amount
                )

                budget_kind = (
                    budget.budget_kind
                )


            manager_keepers = (
                self.keepers_for(
                    manager_id
                )
            )


            # The legacy TeamDraftSetup subtracts selected
            # keeper salaries from pre_keeper_budget. If the
            # normalized budget is already auction cash, add
            # known keeper costs back so selecting those
            # keepers lands on the intended auction cash.
            if (
                budget_kind
                == "auction_cash"
            ):

                known_keeper_cost = sum(
                    int(
                        keeper.cost
                    )

                    for keeper
                    in manager_keepers

                    if (
                        keeper.cost
                        is not None
                    )
                )

                legacy_pre_keeper_budget = (
                    budget_amount
                    + known_keeper_cost
                )

            else:

                legacy_pre_keeper_budget = (
                    budget_amount
                )


            keeper_options = [
                KeeperOption(
                    player_name=(
                        keeper.player_name
                    ),
                    position=(
                        keeper.position
                        or ""
                    ),

                    # An inferred/entered keeper with unknown
                    # salary can still be protected while a
                    # league-wide starting auction budget is
                    # used. Zero is explicit and temporary;
                    # provenance retains that the true salary
                    # is unknown.
                    keeper_cost=(
                        int(
                            keeper.cost
                        )
                        if keeper.cost
                        is not None
                        else 0
                    ),
                    source_row=0,
                )

                for keeper
                in manager_keepers
            ]


            managers[
                manager_id
            ] = ManagerLeagueData(
                manager_id=(
                    manager_id
                ),
                spreadsheet_tab=(
                    identity.sleeper_team_name
                    or identity.sleeper_username
                    or manager_id
                ),
                pre_keeper_budget=int(
                    legacy_pre_keeper_budget
                ),
                keeper_options=(
                    keeper_options
                ),
            )


        historical_sales = [
            HistoricalAuctionSale(
                year=int(
                    sale.year
                ),
                player_name=(
                    sale.player_name
                ),
                price=int(
                    sale.price
                ),
                manager_id=(
                    sale.manager_id
                ),
                manager_raw=(
                    sale.manager_raw
                ),
                source_row=None,
            )

            for sale
            in self.historical_sales
        ]


        return LeagueWorkbookData(
            managers=managers,
            historical_sales=(
                historical_sales
            ),
            warnings=list(
                self.warnings
            ),
        )


# =========================================================
# PERSISTENCE FOR MANUAL / IMPORTED OVERRIDES
# =========================================================

class LeagueSetupStore:

    def __init__(
        self,
        root="data/league_setup",
        checkpoint_callback=None,
    ):

        self.root = Path(
            root
        )
        self.checkpoint_callback = checkpoint_callback

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )


    @staticmethod
    def _safe_key(
        league_key: str,
    ) -> str:

        safe = re.sub(
            r"[^A-Za-z0-9_-]+",
            "_",
            str(
                league_key
            ),
        ).strip("_")

        return safe or "league"


    def path_for(
        self,
        league_key: str,
    ) -> Path:

        return (
            self.root
            / (
                f"{self._safe_key(league_key)}"
                ".json"
            )
        )


    def exists(
        self,
        league_key: str,
    ) -> bool:

        return self.path_for(
            league_key
        ).exists()


    def load(
        self,
        league_key: str,
    ) -> LeagueSetupData:

        path = self.path_for(
            league_key
        )

        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        return LeagueSetupData.from_dict(
            payload
        )


    def load_optional(
        self,
        league_key: str,
    ) -> Optional[LeagueSetupData]:

        if not self.exists(
            league_key
        ):

            return None

        return self.load(
            league_key
        )


    def save(
        self,
        data: LeagueSetupData,
    ) -> Path:

        path = self.path_for(
            data.league_key
        )

        path.write_text(
            json.dumps(
                data.to_dict(),
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        if self.checkpoint_callback is not None:
            self.checkpoint_callback()

        return path


    def delete(self, league_key: str) -> None:
        path = self.path_for(league_key)
        if path.exists():
            path.unlink()
            if self.checkpoint_callback is not None:
                self.checkpoint_callback()


# =========================================================
# MERGE KEYS
# =========================================================

def _merge_records(
    left,
    right,
    *,
    key_func,
):

    merged = {
        key_func(
            record
        ): record

        for record
        in left
    }


    for record in right:

        key = key_func(
            record
        )

        current = merged.get(
            key
        )

        if (
            current is None
            or
            record.source.priority
            >= current.source.priority
        ):

            merged[
                key
            ] = record


    return list(
        merged.values()
    )


def _roster_key(
    record: RosterPlayer,
) -> Tuple[str, str]:

    identity = (
        record.sleeper_player_id
        or
        normalize_player_name(
            record.player_name
        )
    )

    return (
        record.manager_id,
        str(
            identity
        ),
    )


def _keeper_key(
    record: KeeperRecord,
) -> Tuple[str, str]:

    return (
        record.manager_id,
        normalize_player_name(
            record.player_name
        ),
    )


def _history_key(
    record: HistoricalSale,
) -> Tuple[int, str, str]:

    return (
        int(
            record.year
        ),
        normalize_player_name(
            record.player_name
        ),
        str(
            record.manager_id
            or record.manager_raw
            or ""
        ).lower().strip(),
    )


# =========================================================
# DICT HELPERS
# =========================================================

def _source_from_dict(
    record: dict,
    default_source: str,
) -> SourceInfo:

    return SourceInfo(
        **record.get(
            "source",
            {
                "source": (
                    default_source
                ),
            },
        )
    )


def _roster_from_dict(
    record: dict,
) -> RosterPlayer:

    return RosterPlayer(
        manager_id=record[
            "manager_id"
        ],
        player_name=record[
            "player_name"
        ],
        position=record.get(
            "position"
        ),
        sleeper_player_id=record.get(
            "sleeper_player_id"
        ),
        nfl_team=record.get(
            "nfl_team"
        ),
        roster_status=record.get(
            "roster_status",
            "active",
        ),
        source=_source_from_dict(
            record,
            "sleeper",
        ),
    )


def _keeper_from_dict(
    record: dict,
) -> KeeperRecord:

    cost = record.get(
        "cost"
    )
    prior_year_cost = record.get(
        "prior_year_cost"
    )

    return KeeperRecord(
        manager_id=record[
            "manager_id"
        ],
        player_name=record[
            "player_name"
        ],
        position=record.get(
            "position"
        ),
        cost=(
            int(
                cost
            )
            if cost
            is not None
            else None
        ),
        cost_basis=record.get(
            "cost_basis",
            "explicit",
        ),
        prior_year_cost=(
            int(prior_year_cost)
            if prior_year_cost is not None
            else None
        ),
        future_values=tuple(
            record.get(
                "future_values",
                (),
            )
            or ()
        ),
        status=record.get(
            "status",
            "finalized",
        ),
        sleeper_player_id=record.get(
            "sleeper_player_id"
        ),
        source=_source_from_dict(
            record,
            "manual",
        ),
    )


def _history_from_dict(
    record: dict,
) -> HistoricalSale:

    return HistoricalSale(
        year=int(
            record[
                "year"
            ]
        ),
        player_name=record[
            "player_name"
        ],
        price=int(
            record[
                "price"
            ]
        ),
        manager_id=record.get(
            "manager_id"
        ),
        manager_raw=record.get(
            "manager_raw"
        ),
        position=record.get(
            "position"
        ),
        source=_source_from_dict(
            record,
            "manual",
        ),
    )


def _sleeper_player_name(
    player_id: str,
    player: dict,
) -> str:

    full_name = player.get(
        "full_name"
    )

    if full_name:

        return str(
            full_name
        ).strip()


    first_name = (
        player.get(
            "first_name"
        )
        or ""
    )

    last_name = (
        player.get(
            "last_name"
        )
        or ""
    )

    combined = (
        f"{first_name} "
        f"{last_name}"
    ).strip()

    if combined:

        return combined


    team = player.get(
        "team"
    )

    position = (
        player.get(
            "position"
        )
        or ""
    ).upper()


    if (
        position
        in {
            "DEF",
            "DST",
        }
        and
        team
    ):

        return str(
            team
        )


    return str(
        player_id
    )
