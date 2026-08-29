from __future__ import annotations

from collections import defaultdict
from typing import Optional

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext

MATRIX_COLUMNS = (
    "QB",
    "WR1",
    "WR2",
    "WR3",
    "TE",
    "RB1",
    "RB2",
    "RB3",
    "K",
)

# QB/TE/K are only ever shown at depth 1 -- there's no "QB2" column, so
# any role label past QB1/TE1/K1 just doesn't get a slot in the matrix.
SINGLE_SLOT_POSITIONS = {"QB", "TE", "K"}


def _matrix_column(position: str, role_label: str) -> Optional[str]:
    if position in SINGLE_SLOT_POSITIONS:
        return position if role_label == "{0}1".format(position) else None
    return role_label


def render_depth_charts_view(context: AppRuntimeContext) -> None:
    st.header("📋 NFL Depth Charts")
    st.caption(
        "Every active NFL team's depth chart, straight from Sleeper's "
        "own depth-chart order -- role labels (RB1, WR2, ...) use the "
        "same logic that powers the app's contextual player adjustments. "
        "Players already taken in your draft -- kept players included -- "
        "are shaded and struck through."
    )

    if context.depth_chart_error:
        st.warning(
            "Depth chart data failed to load: {0}".format(
                context.depth_chart_error
            )
        )

    documents = context.depth_chart_documents or []
    if not documents:
        st.info("No depth chart data is available right now.")
        return

    by_team_role = defaultdict(dict)
    for document in documents:
        team = document.nfl_team
        if not team:
            continue
        role_label = (document.metadata or {}).get("role_label")
        column = _matrix_column(document.position, role_label)
        if column not in MATRIX_COLUMNS:
            continue
        by_team_role[team][column] = document.player_name

    rows = []
    for team in sorted(by_team_role):
        row = {"Team": team}
        for column in MATRIX_COLUMNS:
            row[column] = by_team_role[team].get(column, "")
        rows.append(row)

    frame = pd.DataFrame(rows, columns=("Team",) + MATRIX_COLUMNS)

    taken_players = set(context.depth_chart_taken_players or ())

    def _shade_taken(value: object) -> str:
        if value and value in taken_players:
            return "background-color: rgba(220, 53, 69, 0.35); text-decoration: line-through;"
        return ""

    styled_frame = frame.style.map(_shade_taken, subset=list(MATRIX_COLUMNS))
    st.dataframe(styled_frame, width="stretch", hide_index=True)
