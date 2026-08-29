from __future__ import annotations

from collections import defaultdict
from typing import Dict, Optional

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.auction_pool import normalize_player_name
from src.depth_chart_context import normalize_position
from src.depth_chart_pdf import build_depth_chart_pdf

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

_UNAVAILABLE_CSS = "background-color: rgba(13, 110, 253, 0.30);"
_TAKEN_CSS = (
    "background-color: rgba(220, 53, 69, 0.35); text-decoration: line-through;"
)


def _matrix_column(position: str, role_label: str) -> Optional[str]:
    if position in SINGLE_SLOT_POSITIONS:
        return position if role_label == "{0}1".format(position) else None
    return role_label


def _position_rank_map(ranking_ensemble) -> Dict[str, int]:
    """Rank every player within their position by the combined ranking
    ensemble (equal-weighted Sleeper + FantasyPros consensus).

    Returns normalized player name -> 1-indexed positional rank.
    """

    if ranking_ensemble is None:
        return {}

    by_position: Dict[str, list] = defaultdict(list)
    for ranking in getattr(ranking_ensemble, "rankings", ()) or ():
        position = normalize_position(getattr(ranking, "position", None))
        if not position:
            continue
        by_position[position].append(ranking)

    ranks: Dict[str, int] = {}
    for players in by_position.values():
        ordered = sorted(players, key=lambda item: item.ensemble_rank)
        for index, ranking in enumerate(ordered, start=1):
            key = normalize_player_name(ranking.player_name)
            if key and key not in ranks:
                ranks[key] = index
    return ranks


def render_depth_charts_view(context: AppRuntimeContext) -> None:
    st.header("📋 NFL Depth Charts")
    st.caption(
        "Every active NFL team's depth chart, straight from Sleeper's "
        "own depth-chart order -- role labels (RB1, WR2, ...) use the "
        "same logic that powers the app's contextual player adjustments. "
        "Each name carries its (#x) rank within its position from the "
        "combined ranking ensemble. Players already taken in your draft -- "
        "kept players included -- are shaded red and struck through; "
        "players marked unavailable in League Setup Data are shaded blue."
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

    position_ranks = _position_rank_map(context.ranking_ensemble)

    by_team_role: Dict[str, Dict[str, str]] = defaultdict(dict)
    for document in documents:
        team = document.nfl_team
        if not team:
            continue
        role_label = (document.metadata or {}).get("role_label")
        column = _matrix_column(document.position, role_label)
        if column not in MATRIX_COLUMNS:
            continue
        name = document.player_name
        rank = position_ranks.get(normalize_player_name(name))
        display = "{0} (#{1})".format(name, rank) if rank else name
        by_team_role[team][column] = display

    rows = []
    for team in sorted(by_team_role):
        row = {"Team": team}
        for column in MATRIX_COLUMNS:
            row[column] = by_team_role[team].get(column, "")
        rows.append(row)

    frame = pd.DataFrame(rows, columns=("Team",) + MATRIX_COLUMNS)

    taken_players = {
        normalize_player_name(name)
        for name in (context.depth_chart_taken_players or ())
    }
    unavailable_players = {
        normalize_player_name(name)
        for name in (context.unavailable_player_names or ())
    }

    def _base_name(value: object) -> str:
        text = str(value or "")
        if text.endswith(")") and " (#" in text:
            text = text[: text.rfind(" (#")]
        return normalize_player_name(text)

    def _style_cell(value: object) -> str:
        if not value:
            return ""
        key = _base_name(value)
        # Blue wins over red when a player is both taken and unavailable.
        if key in unavailable_players:
            return _UNAVAILABLE_CSS
        if key in taken_players:
            return _TAKEN_CSS
        return ""

    styled_frame = frame.style.map(_style_cell, subset=list(MATRIX_COLUMNS))
    st.dataframe(styled_frame, width="stretch", hide_index=True)

    try:
        pdf_bytes = build_depth_chart_pdf(
            columns=("Team",) + MATRIX_COLUMNS,
            rows=rows,
            taken_keys=taken_players,
            unavailable_keys=unavailable_players,
            normalize=normalize_player_name,
        )
    except Exception as error:  # pragma: no cover - defensive
        st.caption("PDF export is unavailable: {0}".format(error))
    else:
        st.download_button(
            "⬇️ Export as PDF",
            data=pdf_bytes,
            file_name="nfl_depth_charts.pdf",
            mime="application/pdf",
        )
