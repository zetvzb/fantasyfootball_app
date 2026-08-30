import json
import sqlite3
from pathlib import Path
from typing import Callable, Dict, List, Optional

from src.auction_pool import normalize_player_name
from src.live_draft import LiveAuctionSale
from src.recommendation_snapshot import RecommendationSnapshot
from src.scenario_blend_rollout import ScenarioBlendSetting


class DraftStore:

    def __init__(
        self,
        db_path: str,
        league_id: str,
        draft_id: str,
        season: int,
        checkpoint_callback: Optional[Callable[[], object]] = None,
    ):

        self.db_path = db_path

        self.league_id = str(
            league_id
        )

        self.draft_id = str(
            draft_id
        )

        self.season = int(
            season
        )

        self.private_scope = None
        self.checkpoint_callback = checkpoint_callback

        Path(
            db_path
        ).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.initialize()


    def _checkpoint(self) -> None:
        if self.checkpoint_callback is not None:
            self.checkpoint_callback()


    def bind_private_scope(self, private_scope: object) -> None:
        """Restrict private recommendation history to one runtime identity."""

        self.private_scope = private_scope


    def _connect(
        self,
    ):

        connection = sqlite3.connect(
            self.db_path
        )

        connection.row_factory = (
            sqlite3.Row
        )

        return connection


    # =====================================================
    # INITIALIZE DATABASE
    # =====================================================

    def initialize(
        self,
    ):

        with self._connect() as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS draft_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS recommendation_snapshots (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT NOT NULL UNIQUE,
                    player_name TEXT NOT NULL,
                    current_bid INTEGER NOT NULL,
                    target_value INTEGER NOT NULL,
                    soft_cap INTEGER NOT NULL,
                    hard_cap INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    alternatives_json TEXT NOT NULL,
                    roster_state_json TEXT NOT NULL,
                    budget_state_json TEXT NOT NULL,
                    inflation_state_json TEXT NOT NULL,
                    context_state_json TEXT NOT NULL,
                    reasons_json TEXT NOT NULL,
                    league_key TEXT NOT NULL DEFAULT '',
                    user_key TEXT NOT NULL DEFAULT '',
                    manager_id TEXT NOT NULL DEFAULT '',
                    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scenario_blend_settings (
                    league_key TEXT NOT NULL,
                    user_key TEXT NOT NULL,
                    manager_id TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    ml_weight REAL NOT NULL DEFAULT 0.25,
                    approved_model_version TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (league_key, user_key, manager_id)
                )
                """
            )

            snapshot_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(recommendation_snapshots)"
                ).fetchall()
            }
            for column_name in ("league_key", "user_key", "manager_id"):
                if column_name not in snapshot_columns:
                    connection.execute(
                        "ALTER TABLE recommendation_snapshots ADD COLUMN "
                        "{0} TEXT NOT NULL DEFAULT ''".format(column_name)
                    )


            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS team_setup (
                    manager_id TEXT PRIMARY KEY,
                    keepers_json TEXT NOT NULL,
                    college_promotions_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                )
                """
            )


            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS live_sales (
                    sale_number INTEGER PRIMARY KEY,
                    player_name TEXT NOT NULL,
                    normalized_player_name TEXT NOT NULL UNIQUE,
                    position TEXT NOT NULL,
                    manager_id TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    modeled_market_value REAL,
                    do_not_exceed INTEGER,
                    source TEXT NOT NULL DEFAULT 'manual',
                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            live_sale_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(live_sales)"
                ).fetchall()
            }
            if "source" not in live_sale_columns:
                connection.execute(
                    "ALTER TABLE live_sales "
                    "ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'"
                )


            metadata = {
                "league_id": (
                    self.league_id
                ),
                "draft_id": (
                    self.draft_id
                ),
                "season": (
                    str(
                        self.season
                    )
                ),
            }


            for (
                key,
                value,
            ) in metadata.items():

                connection.execute(
                    """
                    INSERT INTO draft_meta (
                        key,
                        value
                    )
                    VALUES (?, ?)
                    ON CONFLICT(key)
                    DO UPDATE SET
                        value = excluded.value
                    """,
                    (
                        key,
                        value,
                    ),
                )


    # =====================================================
    # TEAM SETUP
    # =====================================================

    def load_team_setups(
        self,
        warnings: Optional[List[str]] = None,
    ) -> Dict[
        str,
        dict,
    ]:
        """Load persisted per-team keeper selections.

        A corrupt ``keepers_json`` cell falls back to an empty list rather
        than raising, but that silently drops a team's finalized keepers --
        pass ``warnings`` to be told when it happens instead of it
        vanishing unnoticed. ``college_promotions_json`` is still written
        (empty) for schema compatibility with existing rows, but no longer
        read -- the college/devy system was removed.
        """

        result = {}


        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT
                    manager_id,
                    keepers_json
                FROM team_setup
                """
            ).fetchall()


        for row in rows:

            try:

                keepers = json.loads(
                    row[
                        "keepers_json"
                    ]
                )

            except Exception:

                keepers = []

                if warnings is not None:

                    warnings.append(
                        "Persisted keepers for manager '{0}' could not be "
                        "read and were treated as empty.".format(
                            row["manager_id"]
                        )
                    )


            result[
                row[
                    "manager_id"
                ]
            ] = {
                "keepers": (
                    keepers
                    if isinstance(
                        keepers,
                        list,
                    )
                    else []
                ),
            }


        return result


    def save_team_setup(
        self,
        manager_id: str,
        keepers: List[str],
    ):

        with self._connect() as connection:

            connection.execute(
                """
                INSERT INTO team_setup (
                    manager_id,
                    keepers_json,
                    college_promotions_json,
                    updated_at
                )
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)

                ON CONFLICT(manager_id)
                DO UPDATE SET
                    keepers_json =
                        excluded.keepers_json,
                    updated_at =
                        CURRENT_TIMESTAMP
                """,
                (
                    manager_id,
                    json.dumps(
                        list(
                            keepers
                        )
                    ),
                    "[]",
                ),
            )

        self._checkpoint()


    def clear_team_setups(
        self,
    ):

        with self._connect() as connection:

            connection.execute(
                """
                DELETE FROM team_setup
                """
            )

        self._checkpoint()


    # =====================================================
    # LIVE SALES
    # =====================================================

    def load_sales(
        self,
    ) -> List[
        LiveAuctionSale
    ]:

        sales = []


        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT
                    sale_number,
                    player_name,
                    position,
                    manager_id,
                    price,
                    modeled_market_value,
                    do_not_exceed
                    , source
                FROM live_sales
                ORDER BY sale_number
                """
            ).fetchall()


        for row in rows:

            sales.append(
                LiveAuctionSale(
                    sale_number=(
                        int(
                            row[
                                "sale_number"
                            ]
                        )
                    ),
                    player_name=(
                        row[
                            "player_name"
                        ]
                    ),
                    position=(
                        row[
                            "position"
                        ]
                    ),
                    manager_id=(
                        row[
                            "manager_id"
                        ]
                    ),
                    price=(
                        int(
                            row[
                                "price"
                            ]
                        )
                    ),
                    modeled_market_value=(
                        row[
                            "modeled_market_value"
                        ]
                    ),
                    do_not_exceed=(
                        row[
                            "do_not_exceed"
                        ]
                    ),
                    source=row["source"],
                )
            )


        return sales


    def add_sale(
        self,
        sale: LiveAuctionSale,
    ):

        normalized_name = (
            normalize_player_name(
                sale.player_name
            )
        )


        with self._connect() as connection:

            current_max = (
                connection.execute(
                    """
                    SELECT
                        MAX(sale_number)
                    AS max_sale
                    FROM live_sales
                    """
                ).fetchone()
            )


            max_sale = (
                current_max[
                    "max_sale"
                ]
            )


            expected_sale_number = (
                1
                if max_sale is None
                else int(
                    max_sale
                ) + 1
            )


            if (
                sale.sale_number
                != expected_sale_number
            ):

                raise ValueError(
                    "Sale ledger sequence mismatch. "
                    f"Expected sale "
                    f"#{expected_sale_number}, "
                    f"received "
                    f"#{sale.sale_number}."
                )


            existing = (
                connection.execute(
                    """
                    SELECT
                        sale_number
                    FROM live_sales
                    WHERE
                        normalized_player_name = ?
                    """,
                    (
                        normalized_name,
                    ),
                ).fetchone()
            )


            if existing:

                raise ValueError(
                    f"{sale.player_name} "
                    f"is already stored as sold."
                )


            connection.execute(
                """
                INSERT INTO live_sales (
                    sale_number,
                    player_name,
                    normalized_player_name,
                    position,
                    manager_id,
                    price,
                    modeled_market_value,
                    do_not_exceed
                    , source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sale.sale_number,
                    sale.player_name,
                    normalized_name,
                    sale.position,
                    sale.manager_id,
                    sale.price,
                    sale.modeled_market_value,
                    sale.do_not_exceed,
                    sale.source,
                ),
            )

        self._checkpoint()


    def replace_sales(
        self,
        sales: List[LiveAuctionSale],
    ) -> None:
        """Atomically replace the ledger with a validated reconciled state."""

        numbers = [int(sale.sale_number) for sale in sales]
        if numbers != list(range(1, len(sales) + 1)):
            raise ValueError("Replacement sale ledger must be sequential.")
        names = [normalize_player_name(sale.player_name) for sale in sales]
        if len(names) != len(set(names)):
            raise ValueError("Replacement sale ledger contains duplicate players.")

        with self._connect() as connection:
            connection.execute("DELETE FROM live_sales")
            connection.executemany(
                """
                INSERT INTO live_sales (
                    sale_number, player_name, normalized_player_name,
                    position, manager_id, price, modeled_market_value,
                    do_not_exceed, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        sale.sale_number,
                        sale.player_name,
                        normalize_player_name(sale.player_name),
                        sale.position,
                        sale.manager_id,
                        sale.price,
                        sale.modeled_market_value,
                        sale.do_not_exceed,
                        sale.source,
                    )
                    for sale in sales
                ],
            )

        self._checkpoint()


    def undo_last_sale(
        self,
    ) -> Optional[
        LiveAuctionSale
    ]:

        sales = (
            self.load_sales()
        )


        if not sales:

            return None


        last_sale = (
            sales[
                -1
            ]
        )


        with self._connect() as connection:

            connection.execute(
                """
                DELETE FROM live_sales
                WHERE sale_number = ?
                """,
                (
                    last_sale.sale_number,
                ),
            )

        self._checkpoint()
        return last_sale


    def reset_sales(
        self,
    ):

        with self._connect() as connection:

            connection.execute(
                """
                DELETE FROM live_sales
                """
            )

        self._checkpoint()


    # =====================================================
    # STATUS
    # =====================================================

    def sale_count(
        self,
    ) -> int:

        with self._connect() as connection:

            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS count
                FROM live_sales
                """
            ).fetchone()


        return int(
            row[
                "count"
            ]
        )

    def add_recommendation_snapshot(
        self,
        snapshot: RecommendationSnapshot,
    ) -> bool:
        if self.private_scope is not None:
            self.private_scope.require_resource(snapshot)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO recommendation_snapshots (
                    fingerprint, player_name, current_bid,
                    target_value, soft_cap, hard_cap, decision,
                    alternatives_json, roster_state_json, budget_state_json,
                    inflation_state_json, context_state_json, reasons_json,
                    league_key, user_key, manager_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.fingerprint(), snapshot.player_name,
                    snapshot.current_bid, snapshot.target_value,
                    snapshot.soft_cap, snapshot.hard_cap, snapshot.decision,
                    json.dumps(list(snapshot.alternatives), sort_keys=True),
                    json.dumps(dict(snapshot.roster_state), sort_keys=True),
                    json.dumps(dict(snapshot.budget_state), sort_keys=True),
                    json.dumps(dict(snapshot.inflation_state), sort_keys=True),
                    json.dumps(dict(snapshot.context_state), sort_keys=True),
                    json.dumps(list(snapshot.reasons)),
                    snapshot.league_key,
                    snapshot.user_key,
                    snapshot.manager_id,
                ),
            )
            inserted = cursor.rowcount == 1
        if inserted:
            self._checkpoint()
        return inserted

    def save_scenario_blend_setting(
        self,
        setting: ScenarioBlendSetting,
    ) -> ScenarioBlendSetting:
        if self.private_scope is not None:
            self.private_scope.require_resource(setting)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO scenario_blend_settings (
                    league_key, user_key, manager_id, enabled,
                    ml_weight, approved_model_version, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(league_key, user_key, manager_id) DO UPDATE SET
                    enabled = excluded.enabled,
                    ml_weight = excluded.ml_weight,
                    approved_model_version = excluded.approved_model_version,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    setting.league_key, setting.user_key, setting.manager_id,
                    int(setting.enabled), min(0.25, max(0.0, setting.ml_weight)),
                    setting.approved_model_version,
                ),
            )
        self._checkpoint()
        loaded = self.load_scenario_blend_setting(
            setting.league_key, setting.user_key, setting.manager_id
        )
        if loaded is None:
            raise ValueError("Scenario blend setting could not be saved.")
        return loaded

    def load_scenario_blend_setting(
        self,
        league_key: str,
        user_key: str,
        manager_id: str,
    ) -> Optional[ScenarioBlendSetting]:
        if self.private_scope is not None:
            self.private_scope.require(
                league_key=league_key, user_key=user_key, manager_id=manager_id
            )
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT league_key, user_key, manager_id, enabled, ml_weight,
                       approved_model_version, updated_at
                FROM scenario_blend_settings
                WHERE league_key = ? AND user_key = ? AND manager_id = ?
                """,
                (str(league_key), str(user_key), str(manager_id)),
            ).fetchone()
        if row is None:
            return None
        return ScenarioBlendSetting(
            league_key=row["league_key"], user_key=row["user_key"],
            manager_id=row["manager_id"], enabled=bool(row["enabled"]),
            ml_weight=float(row["ml_weight"]),
            approved_model_version=row["approved_model_version"],
            updated_at=row["updated_at"],
        )

    def load_recommendation_snapshots(
        self,
        league_key: Optional[str] = None,
        user_key: Optional[str] = None,
        manager_id: Optional[str] = None,
    ) -> List[RecommendationSnapshot]:
        filters = []
        parameters = []
        for column_name, value in (
            ("league_key", league_key),
            ("user_key", user_key),
            ("manager_id", manager_id),
        ):
            if value is not None:
                filters.append("{0} = ?".format(column_name))
                parameters.append(str(value))
        where_clause = (
            " WHERE {0}".format(" AND ".join(filters))
            if filters
            else ""
        )
        with self._connect() as connection:
            rows = connection.execute(
                (
                    """
                SELECT player_name, current_bid, target_value, soft_cap,
                       hard_cap, decision, alternatives_json,
                       roster_state_json, budget_state_json,
                       inflation_state_json, context_state_json,
                       reasons_json, captured_at, league_key, user_key,
                       manager_id
                FROM recommendation_snapshots
                """
                    + where_clause
                    + " ORDER BY snapshot_id"
                ),
                tuple(parameters),
            ).fetchall()
        return [
            RecommendationSnapshot(
                player_name=row["player_name"],
                current_bid=int(row["current_bid"]),
                target_value=int(row["target_value"]),
                soft_cap=int(row["soft_cap"]),
                hard_cap=int(row["hard_cap"]),
                decision=row["decision"],
                alternatives=tuple(json.loads(row["alternatives_json"])),
                roster_state=json.loads(row["roster_state_json"]),
                budget_state=json.loads(row["budget_state_json"]),
                inflation_state=json.loads(row["inflation_state_json"]),
                context_state=json.loads(row["context_state_json"]),
                reasons=tuple(json.loads(row["reasons_json"])),
                captured_at=row["captured_at"],
                league_key=row["league_key"],
                user_key=row["user_key"],
                manager_id=row["manager_id"],
            )
            for row in rows
        ]

    def load_private_recommendation_snapshots(
        self,
        league_key: str,
        user_key: str,
        manager_id: str,
    ) -> List[RecommendationSnapshot]:
        if self.private_scope is not None:
            self.private_scope.require(
                league_key=league_key,
                user_key=user_key,
                manager_id=manager_id,
            )
        return self.load_recommendation_snapshots(
            league_key=league_key,
            user_key=user_key,
            manager_id=manager_id,
        )
