import sqlite3

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from src.player_context import ContextDocument

from src.depth_chart_context import (
    canonical_player_name,
    is_active_player,
    normalize_position,
    numeric_int,
    sleeper_player_name,
)


SUPPORTED_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
    "K",
}


# =========================================================
# RESULT
# =========================================================

@dataclass
class DepthChartMovementResult:

    documents: List[
        ContextDocument
    ] = field(
        default_factory=list
    )

    baseline_players: int = 0
    changed_players: int = 0
    competition_events: int = 0
    removed_players: int = 0

    warnings: List[str] = field(
        default_factory=list
    )


# =========================================================
# TRACKER
# =========================================================

class DepthChartMovementTracker:

    def __init__(
        self,
        db_path="data/player_context.db",
    ):

        self.db_path = (
            db_path
        )

        self._ensure_schema()


    # =====================================================
    # DATABASE
    # =====================================================

    def _connect(
        self,
    ):

        connection = (
            sqlite3.connect(
                self.db_path
            )
        )

        connection.row_factory = (
            sqlite3.Row
        )

        return connection


    def _ensure_schema(
        self,
    ):

        with self._connect() as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                depth_chart_state (
                    sleeper_id TEXT PRIMARY KEY,
                    player_name TEXT NOT NULL,
                    team TEXT,
                    position TEXT,
                    depth_chart_order INTEGER,
                    depth_chart_position TEXT,
                    observed_at TEXT NOT NULL
                )
                """
            )


            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                depth_chart_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sleeper_id TEXT NOT NULL,
                    player_name TEXT NOT NULL,
                    team TEXT,
                    position TEXT,
                    depth_chart_order INTEGER,
                    depth_chart_position TEXT,
                    observed_at TEXT NOT NULL
                )
                """
            )


            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_depth_history_player
                ON depth_chart_history (
                    sleeper_id,
                    observed_at
                )
                """
            )


    # =====================================================
    # CURRENT SLEEPER SNAPSHOT
    # =====================================================

    def _build_current_states(
        self,
        sleeper_players,
        fantasypros_index=None,
    ):

        states = {}


        for (
            sleeper_id,
            player,
        ) in sleeper_players.items():

            if not isinstance(
                player,
                dict,
            ):

                continue


            if not is_active_player(
                player
            ):

                continue


            position = (
                normalize_position(
                    player.get(
                        "position"
                    )
                )
            )


            if (
                position
                not in SUPPORTED_POSITIONS
            ):

                continue


            team = str(
                player.get(
                    "team"
                )
                or
                ""
            ).upper()


            if not team:

                continue


            order = (
                numeric_int(
                    player.get(
                        "depth_chart_order"
                    )
                )
            )


            if order is None:

                continue


            raw_name = (
                sleeper_player_name(
                    player
                )
            )


            if not raw_name:

                continue


            player_name = (
                canonical_player_name(
                    sleeper_name=(
                        raw_name
                    ),
                    fantasypros_index=(
                        fantasypros_index
                    ),
                )
            )


            states[
                str(
                    sleeper_id
                )
            ] = {
                "sleeper_id": (
                    str(
                        sleeper_id
                    )
                ),
                "player_name": (
                    player_name
                ),
                "team": (
                    team
                ),
                "position": (
                    position
                ),
                "order": (
                    order
                ),
                "depth_chart_position": (
                    player.get(
                        "depth_chart_position"
                    )
                ),
            }


        return states


    # =====================================================
    # PREVIOUS STATE
    # =====================================================

    def _load_previous_states(
        self,
    ):

        previous = {}


        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT
                    sleeper_id,
                    player_name,
                    team,
                    position,
                    depth_chart_order,
                    depth_chart_position,
                    observed_at
                FROM depth_chart_state
                """
            ).fetchall()


        for row in rows:

            previous[
                row[
                    "sleeper_id"
                ]
            ] = {
                "sleeper_id": (
                    row[
                        "sleeper_id"
                    ]
                ),
                "player_name": (
                    row[
                        "player_name"
                    ]
                ),
                "team": (
                    row[
                        "team"
                    ]
                ),
                "position": (
                    row[
                        "position"
                    ]
                ),
                "order": (
                    row[
                        "depth_chart_order"
                    ]
                ),
                "depth_chart_position": (
                    row[
                        "depth_chart_position"
                    ]
                ),
                "observed_at": (
                    row[
                        "observed_at"
                    ]
                ),
            }


        return previous


    # =====================================================
    # STATE COMPARISON
    # =====================================================

    def _state_changed(
        self,
        old_state,
        new_state,
    ):

        return (
            old_state.get(
                "team"
            )
            !=
            new_state.get(
                "team"
            )

            or

            old_state.get(
                "position"
            )
            !=
            new_state.get(
                "position"
            )

            or

            old_state.get(
                "order"
            )
            !=
            new_state.get(
                "order"
            )

            or

            old_state.get(
                "depth_chart_position"
            )
            !=
            new_state.get(
                "depth_chart_position"
            )
        )


    # =====================================================
    # GROUP BY TEAM / POSITION
    # =====================================================

    def _group_states(
        self,
        states,
    ):

        groups = defaultdict(
            dict
        )


        for (
            sleeper_id,
            state,
        ) in states.items():

            key = (
                state.get(
                    "team"
                ),
                state.get(
                    "position"
                ),
            )


            groups[
                key
            ][
                sleeper_id
            ] = state


        return groups


    # =====================================================
    # MOVEMENT SIGNALS
    # =====================================================

    def _promotion_signals(
        self,
        position,
        old_order,
        new_order,
    ):

        role_signal = 0.20
        usage_signal = 0.15


        if new_order == 1:

            if position == "QB":

                role_signal = 0.90
                usage_signal = 0.75

            elif position == "RB":

                role_signal = 0.70
                usage_signal = 0.55

            elif position == "WR":

                role_signal = 0.65
                usage_signal = 0.40

            elif position == "TE":

                role_signal = 0.70
                usage_signal = 0.45

            elif position == "K":

                role_signal = 0.80
                usage_signal = 0.35


        elif new_order == 2:

            if position == "RB":

                role_signal = 0.40
                usage_signal = 0.30

            elif position == "WR":

                role_signal = 0.35
                usage_signal = 0.22

            elif position == "TE":

                role_signal = 0.20
                usage_signal = 0.12

            elif position == "QB":

                role_signal = 0.25
                usage_signal = 0.10


        elif new_order == 3:

            if position == "WR":

                role_signal = 0.25
                usage_signal = 0.15


        # Bigger jumps are more meaningful.

        jump_size = max(
            1,
            old_order
            -
            new_order,
        )


        jump_multiplier = min(
            1.25,
            1.0
            +
            0.08
            *
            (
                jump_size
                -
                1
            ),
        )


        return (
            min(
                1.0,
                role_signal
                *
                jump_multiplier,
            ),
            min(
                1.0,
                usage_signal
                *
                jump_multiplier,
            ),
        )


    def _demotion_signals(
        self,
        position,
        old_order,
        new_order,
    ):

        role_signal = -0.20
        usage_signal = -0.15


        if old_order == 1:

            if position == "QB":

                role_signal = -0.90
                usage_signal = -0.75

            elif position == "RB":

                role_signal = -0.70
                usage_signal = -0.55

            elif position == "WR":

                role_signal = -0.60
                usage_signal = -0.40

            elif position == "TE":

                role_signal = -0.70
                usage_signal = -0.45

            elif position == "K":

                role_signal = -0.80
                usage_signal = -0.35


        elif new_order >= 3:

            if position == "RB":

                role_signal = -0.40
                usage_signal = -0.35

            elif position == "WR":

                role_signal = -0.25
                usage_signal = -0.20

            elif position == "TE":

                role_signal = -0.35
                usage_signal = -0.30


        drop_size = max(
            1,
            new_order
            -
            old_order,
        )


        drop_multiplier = min(
            1.25,
            1.0
            +
            0.08
            *
            (
                drop_size
                -
                1
            ),
        )


        return (
            max(
                -1.0,
                role_signal
                *
                drop_multiplier,
            ),
            max(
                -1.0,
                usage_signal
                *
                drop_multiplier,
            ),
        )


    # =====================================================
    # COMPETITION EFFECT
    # =====================================================

    def _competition_signal(
        self,
        position,
        incumbent_order,
        competitor_order,
        added,
    ):

        if (
            incumbent_order
            is None
            or
            competitor_order
            is None
        ):

            return None


        # Ignore players too far down the chart.

        if (
            competitor_order
            >
            incumbent_order
            +
            2
        ):

            return None


        role = 0.0
        usage = 0.0


        # =================================================
        # QB
        # =================================================

        if position == "QB":

            if (
                incumbent_order == 1
                and
                competitor_order <= 2
            ):

                role = -0.08
                usage = -0.05


            elif (
                competitor_order
                <
                incumbent_order
            ):

                role = -0.30
                usage = -0.20


        # =================================================
        # RB
        # =================================================

        elif position == "RB":

            if (
                incumbent_order == 1
                and
                competitor_order == 2
            ):

                role = -0.10
                usage = -0.25


            elif (
                competitor_order
                <
                incumbent_order
            ):

                role = -0.30
                usage = -0.35


            elif (
                competitor_order
                ==
                incumbent_order
                +
                1
            ):

                role = -0.08
                usage = -0.18


        # =================================================
        # WR
        # =================================================

        elif position == "WR":

            if (
                incumbent_order <= 3
                and
                competitor_order <= 3
            ):

                role = -0.05
                usage = -0.12


            elif (
                competitor_order
                <
                incumbent_order
            ):

                role = -0.18
                usage = -0.18


        # =================================================
        # TE
        # =================================================

        elif position == "TE":

            if (
                incumbent_order == 1
                and
                competitor_order == 2
            ):

                role = -0.08
                usage = -0.18


            elif (
                competitor_order
                <
                incumbent_order
            ):

                role = -0.25
                usage = -0.25


        # =================================================
        # K
        # =================================================

        elif position == "K":

            if (
                incumbent_order == 1
                and
                competitor_order == 2
            ):

                role = -0.15
                usage = -0.08


        if (
            abs(
                role
            )
            <
            0.01
            and
            abs(
                usage
            )
            <
            0.01
        ):

            return None


        if not added:

            # Removing competition is positive,
            # but slightly smaller than the downside
            # of adding competition.

            role = (
                -role
                *
                0.85
            )

            usage = (
                -usage
                *
                0.85
            )


        return (
            role,
            usage,
        )


    # =====================================================
    # DOCUMENT BUILDERS
    # =====================================================

    def _movement_document(
        self,
        state,
        movement_type,
        role_signal,
        usage_signal,
        now,
        old_order=None,
        new_order=None,
        competitor=None,
    ):

        player_name = (
            state[
                "player_name"
            ]
        )


        team = (
            state[
                "team"
            ]
        )


        position = (
            state[
                "position"
            ]
        )


        timestamp_key = (
            now.strftime(
                "%Y%m%d%H%M%S%f"
            )
        )


        competitor_id = (
            competitor.get(
                "sleeper_id"
            )
            if competitor
            else "none"
        )


        document_id = (
            "depth-movement-"
            +
            state[
                "sleeper_id"
            ]
            +
            "-"
            +
            movement_type.lower()
            +
            "-"
            +
            str(
                competitor_id
            )
            +
            "-"
            +
            timestamp_key
        )


        if movement_type == "PROMOTED":

            title = (
                f"{player_name} promoted "
                f"from {position}{old_order} "
                f"to {position}{new_order}"
            )


            content = (
                f"Sleeper depth-chart movement: "
                f"{player_name} moved from "
                f"{position}{old_order} to "
                f"{position}{new_order} for {team}."
            )


        elif movement_type == "DEMOTED":

            title = (
                f"{player_name} demoted "
                f"from {position}{old_order} "
                f"to {position}{new_order}"
            )


            content = (
                f"Sleeper depth-chart movement: "
                f"{player_name} moved from "
                f"{position}{old_order} to "
                f"{position}{new_order} for {team}."
            )


        elif movement_type == "COMPETITION_ADDED":

            competitor_name = (
                competitor[
                    "player_name"
                ]
            )


            competitor_order = (
                competitor[
                    "order"
                ]
            )


            title = (
                f"Competition added for "
                f"{player_name}"
            )


            content = (
                f"{competitor_name} appeared in the "
                f"{team} {position} depth chart at "
                f"{position}{competitor_order}, creating "
                f"new competition for {player_name}, "
                f"currently {position}"
                f"{state['order']}."
            )


        elif movement_type == "COMPETITION_REMOVED":

            competitor_name = (
                competitor[
                    "player_name"
                ]
            )


            title = (
                f"Competition removed for "
                f"{player_name}"
            )


            content = (
                f"{competitor_name} disappeared from the "
                f"{team} {position} depth chart, reducing "
                f"competition for {player_name}."
            )


        elif movement_type == "STARTER_REMOVED":

            competitor_name = (
                competitor[
                    "player_name"
                ]
            )


            title = (
                f"Starter disappeared ahead of "
                f"{player_name}"
            )


            content = (
                f"Former {team} {position}1 "
                f"{competitor_name} disappeared from "
                f"the current depth chart. "
                f"{player_name} is now positioned for "
                f"additional opportunity."
            )


        else:

            title = (
                f"Depth chart change for "
                f"{player_name}"
            )


            content = (
                f"Sleeper recorded a depth-chart change "
                f"for {player_name}."
            )


        metadata = {
            "movement_type": (
                movement_type
            ),
            "sleeper_id": (
                state[
                    "sleeper_id"
                ]
            ),
            "team": (
                team
            ),
            "position": (
                position
            ),
            "old_order": (
                old_order
            ),
            "new_order": (
                new_order
            ),
        }


        if competitor:

            metadata.update(
                {
                    "competitor_id": (
                        competitor[
                            "sleeper_id"
                        ]
                    ),
                    "competitor_name": (
                        competitor[
                            "player_name"
                        ]
                    ),
                    "competitor_order": (
                        competitor[
                            "order"
                        ]
                    ),
                }
            )


        return (
            ContextDocument(
                document_id=(
                    document_id
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
                source_type=(
                    "depth_chart_movement"
                ),
                source_name=(
                    "Sleeper"
                ),
                title=(
                    title
                ),
                content=(
                    content
                ),
                published_at=(
                    now
                ),
                confidence=0.92,
                role_signal=(
                    role_signal
                ),
                usage_signal=(
                    usage_signal
                ),
                injury_signal=0.0,
                dynasty_signal=0.0,
                tags=[
                    "depth_chart",
                    "movement",
                    movement_type.lower(),
                    position.lower(),
                    team.lower(),
                ],
                metadata=(
                    metadata
                ),
            )
        )


    # =====================================================
    # PERSIST CURRENT STATE
    # =====================================================

    def _persist_states(
        self,
        previous,
        current,
        now,
    ):

        observed_at = (
            now.isoformat()
        )


        with self._connect() as connection:

            # Current-state table should represent
            # exactly what Sleeper reports now.

            connection.execute(
                """
                DELETE FROM depth_chart_state
                """
            )


            for state in current.values():

                connection.execute(
                    """
                    INSERT INTO depth_chart_state (
                        sleeper_id,
                        player_name,
                        team,
                        position,
                        depth_chart_order,
                        depth_chart_position,
                        observed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        state[
                            "sleeper_id"
                        ],
                        state[
                            "player_name"
                        ],
                        state[
                            "team"
                        ],
                        state[
                            "position"
                        ],
                        state[
                            "order"
                        ],
                        state.get(
                            "depth_chart_position"
                        ),
                        observed_at,
                    ),
                )


                old_state = (
                    previous.get(
                        state[
                            "sleeper_id"
                        ]
                    )
                )


                should_write_history = (
                    old_state is None
                    or
                    self._state_changed(
                        old_state,
                        state,
                    )
                )


                if should_write_history:

                    connection.execute(
                        """
                        INSERT INTO depth_chart_history (
                            sleeper_id,
                            player_name,
                            team,
                            position,
                            depth_chart_order,
                            depth_chart_position,
                            observed_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            state[
                                "sleeper_id"
                            ],
                            state[
                                "player_name"
                            ],
                            state[
                                "team"
                            ],
                            state[
                                "position"
                            ],
                            state[
                                "order"
                            ],
                            state.get(
                                "depth_chart_position"
                            ),
                            observed_at,
                        ),
                    )


    # =====================================================
    # MAIN PROCESS
    # =====================================================

    def process(
        self,
        sleeper_players,
        fantasypros_index=None,
    ):

        now = datetime.now(
            timezone.utc
        )


        result = (
            DepthChartMovementResult()
        )


        current = (
            self._build_current_states(
                sleeper_players=(
                    sleeper_players
                ),
                fantasypros_index=(
                    fantasypros_index
                ),
            )
        )


        previous = (
            self._load_previous_states()
        )


        if not current:

            result.warnings.append(
                "No usable Sleeper depth-chart states "
                "were found."
            )

            return result


        # =================================================
        # FIRST RUN = BASELINE ONLY
        # =================================================

        if not previous:

            result.baseline_players = (
                len(
                    current
                )
            )


            self._persist_states(
                previous={},
                current=(
                    current
                ),
                now=(
                    now
                ),
            )


            return result


        # =================================================
        # INDIVIDUAL PROMOTIONS / DEMOTIONS
        # =================================================

        for (
            sleeper_id,
            new_state,
        ) in current.items():

            old_state = (
                previous.get(
                    sleeper_id
                )
            )


            if old_state is None:

                continue


            if not self._state_changed(
                old_state,
                new_state,
            ):

                continue


            result.changed_players += 1


            # A team/position change is handled by other
            # context sources and group competition logic.

            if (
                old_state.get(
                    "team"
                )
                !=
                new_state.get(
                    "team"
                )
                or
                old_state.get(
                    "position"
                )
                !=
                new_state.get(
                    "position"
                )
            ):

                continue


            old_order = (
                old_state.get(
                    "order"
                )
            )


            new_order = (
                new_state.get(
                    "order"
                )
            )


            if (
                old_order is None
                or
                new_order is None
                or
                old_order
                ==
                new_order
            ):

                continue


            if new_order < old_order:

                (
                    role_signal,
                    usage_signal,
                ) = (
                    self._promotion_signals(
                        position=(
                            new_state[
                                "position"
                            ]
                        ),
                        old_order=(
                            old_order
                        ),
                        new_order=(
                            new_order
                        ),
                    )
                )


                result.documents.append(
                    self._movement_document(
                        state=(
                            new_state
                        ),
                        movement_type=(
                            "PROMOTED"
                        ),
                        role_signal=(
                            role_signal
                        ),
                        usage_signal=(
                            usage_signal
                        ),
                        now=(
                            now
                        ),
                        old_order=(
                            old_order
                        ),
                        new_order=(
                            new_order
                        ),
                    )
                )


            elif new_order > old_order:

                (
                    role_signal,
                    usage_signal,
                ) = (
                    self._demotion_signals(
                        position=(
                            new_state[
                                "position"
                            ]
                        ),
                        old_order=(
                            old_order
                        ),
                        new_order=(
                            new_order
                        ),
                    )
                )


                result.documents.append(
                    self._movement_document(
                        state=(
                            new_state
                        ),
                        movement_type=(
                            "DEMOTED"
                        ),
                        role_signal=(
                            role_signal
                        ),
                        usage_signal=(
                            usage_signal
                        ),
                        now=(
                            now
                        ),
                        old_order=(
                            old_order
                        ),
                        new_order=(
                            new_order
                        ),
                    )
                )


        # =================================================
        # TEAM/POSITION COMPETITION CHANGES
        # =================================================

        previous_groups = (
            self._group_states(
                previous
            )
        )


        current_groups = (
            self._group_states(
                current
            )
        )


        group_keys = (
            set(
                previous_groups.keys()
            )
            |
            set(
                current_groups.keys()
            )
        )


        for group_key in group_keys:

            old_group = (
                previous_groups.get(
                    group_key,
                    {},
                )
            )


            new_group = (
                current_groups.get(
                    group_key,
                    {},
                )
            )


            old_ids = set(
                old_group.keys()
            )


            new_ids = set(
                new_group.keys()
            )


            incumbents = (
                old_ids
                &
                new_ids
            )


            added_ids = (
                new_ids
                -
                old_ids
            )


            removed_ids = (
                old_ids
                -
                new_ids
            )


            # =============================================
            # COMPETITION ADDED
            # =============================================

            for added_id in added_ids:

                competitor = (
                    new_group[
                        added_id
                    ]
                )


                for incumbent_id in incumbents:

                    incumbent = (
                        new_group[
                            incumbent_id
                        ]
                    )


                    signals = (
                        self._competition_signal(
                            position=(
                                incumbent[
                                    "position"
                                ]
                            ),
                            incumbent_order=(
                                incumbent[
                                    "order"
                                ]
                            ),
                            competitor_order=(
                                competitor[
                                    "order"
                                ]
                            ),
                            added=True,
                        )
                    )


                    if signals is None:

                        continue


                    (
                        role_signal,
                        usage_signal,
                    ) = signals


                    result.documents.append(
                        self._movement_document(
                            state=(
                                incumbent
                            ),
                            movement_type=(
                                "COMPETITION_ADDED"
                            ),
                            role_signal=(
                                role_signal
                            ),
                            usage_signal=(
                                usage_signal
                            ),
                            now=(
                                now
                            ),
                            competitor=(
                                competitor
                            ),
                        )
                    )


                    result.competition_events += 1


            # =============================================
            # COMPETITION REMOVED
            # =============================================

            for removed_id in removed_ids:

                competitor = (
                    old_group[
                        removed_id
                    ]
                )


                for incumbent_id in incumbents:

                    incumbent = (
                        new_group[
                            incumbent_id
                        ]
                    )


                    signals = (
                        self._competition_signal(
                            position=(
                                incumbent[
                                    "position"
                                ]
                            ),
                            incumbent_order=(
                                incumbent[
                                    "order"
                                ]
                            ),
                            competitor_order=(
                                competitor[
                                    "order"
                                ]
                            ),
                            added=False,
                        )
                    )


                    if signals is None:

                        continue


                    (
                        role_signal,
                        usage_signal,
                    ) = signals


                    movement_type = (
                        "STARTER_REMOVED"

                        if (
                            competitor[
                                "order"
                            ]
                            ==
                            1
                        )

                        else

                        "COMPETITION_REMOVED"
                    )


                    if (
                        movement_type
                        ==
                        "STARTER_REMOVED"
                    ):

                        role_signal = max(
                            role_signal,
                            0.20,
                        )

                        usage_signal = max(
                            usage_signal,
                            0.25,
                        )


                    result.documents.append(
                        self._movement_document(
                            state=(
                                incumbent
                            ),
                            movement_type=(
                                movement_type
                            ),
                            role_signal=(
                                role_signal
                            ),
                            usage_signal=(
                                usage_signal
                            ),
                            now=(
                                now
                            ),
                            competitor=(
                                competitor
                            ),
                        )
                    )


                    result.competition_events += 1


        result.removed_players = len(
            set(
                previous.keys()
            )
            -
            set(
                current.keys()
            )
        )


        # =================================================
        # UPDATE BASELINE AFTER DETECTION
        # =================================================

        self._persist_states(
            previous=(
                previous
            ),
            current=(
                current
            ),
            now=(
                now
            ),
        )


        return result


    # =====================================================
    # DEBUG
    # =====================================================

    def state_count(
        self,
    ):

        with self._connect() as connection:

            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM depth_chart_state
                """
            ).fetchone()


        return int(
            row[
                "count"
            ]
        )