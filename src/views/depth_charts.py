from __future__ import annotations

from collections import defaultdict

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext

POSITION_ORDER = ("QB", "RB", "WR", "TE", "K")


def _injury_status(content: str) -> str:
    marker = "Sleeper injury status: "
    if marker not in content:
        return ""
    return content.split(marker, 1)[1].rstrip(".").strip()


def render_depth_charts_view(context: AppRuntimeContext) -> None:
    st.header("📋 NFL Depth Charts")
    st.caption(
        "Every active NFL team's depth chart, straight from Sleeper's "
        "own depth-chart order -- role labels (RB1, WR2, ...) and "
        "committee-risk flags use the same logic that powers the "
        "app's contextual player adjustments."
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

    by_team = defaultdict(list)
    for document in documents:
        team = document.nfl_team or "FA"
        by_team[team].append(document)

    teams = sorted(by_team)
    selected_team = st.selectbox("Team", options=teams, key="depth_charts::team")

    rows = []
    for document in by_team[selected_team]:
        metadata = document.metadata or {}
        rows.append(
            {
                "Pos": document.position,
                "Order": metadata.get("depth_chart_order"),
                "Role": metadata.get("role_label"),
                "Player": document.player_name,
                "Committee Risk": "Yes" if metadata.get("committee_risk") else "",
                "Injury Status": _injury_status(document.content),
            }
        )

    frame = pd.DataFrame(rows)
    if not frame.empty:
        position_rank = {
            position: index for index, position in enumerate(POSITION_ORDER)
        }
        frame["_pos_rank"] = frame["Pos"].map(
            lambda position: position_rank.get(position, len(POSITION_ORDER))
        )
        frame = frame.sort_values(["_pos_rank", "Order"]).drop(columns="_pos_rank")

    st.dataframe(frame, width="stretch", hide_index=True)
