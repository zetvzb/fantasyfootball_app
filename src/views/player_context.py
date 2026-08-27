from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext


AUCTION_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF", "DST"}


def _player_options(
    sleeper_players: Dict[str, Any],
) -> Tuple[Tuple[str, str, Dict[str, Any]], ...]:
    options = []
    seen = set()
    for player_id, player in sleeper_players.items():
        position = str(player.get("position") or "").upper()
        name = str(player.get("full_name") or "").strip()
        if not name or position not in AUCTION_POSITIONS:
            continue
        # Exclude inactive / historical Sleeper records -- these are
        # frequently stale duplicate IDs (e.g. a second, retired entry
        # sharing a real player's name) that only confuse the picker.
        if player.get("active") is False:
            continue
        identity = (name.lower(), position)
        if identity in seen:
            continue
        seen.add(identity)
        options.append((name, str(player_id), player))
    return tuple(sorted(options, key=lambda item: item[0].lower()))


def _display_number(value: Optional[float], decimals: int = 1) -> str:
    if value is None:
        return "-"
    return ("{0:.%df}" % decimals).format(float(value))


def render_player_context_view(context: AppRuntimeContext) -> None:
    """Render player intelligence without requiring an active nomination."""

    st.header("🔎 Player Context")
    st.caption(
        "Search the Sleeper NFL player universe and retrieve the same "
        "FantasyPros rankings, projections, news, injury, role, and usage "
        "context used by the auction recommendation engine."
    )

    options = _player_options(dict(context.sleeper_players))
    if not options:
        st.warning("The Sleeper NFL player universe is unavailable.")
        return

    option_by_label = {
        "{0} · {1} · {2}".format(
            name,
            str(player.get("position") or "-").upper(),
            player.get("team") or "FA",
        ): (name, player_id, player)
        for name, player_id, player in options
    }
    state_key = (
        context.runtime_identity.private_key("player_context_search")
        if context.runtime_identity is not None
        else "player_context_search"
    )
    label = st.selectbox(
        "Player",
        options=list(option_by_label),
        index=None,
        placeholder="Type a player name",
        key=state_key,
    )
    if not label:
        st.info("Choose any NFL player to view their current context.")
        return

    player_name, player_id, player = option_by_label[label]
    normalized_name = context.normalize_player_name(player_name)
    fp = context.fantasypros_index.get(normalized_name)
    projection = context.projection_index.get(normalized_name)

    profile_1, profile_2, profile_3, profile_4 = st.columns(4)
    profile_1.metric("Position", player.get("position") or "-")
    profile_2.metric("NFL Team", player.get("team") or "FA")
    profile_3.metric("Age", player.get("age") or "-")
    profile_4.metric("Sleeper ID", player_id)

    ranking_1, ranking_2, ranking_3, ranking_4 = st.columns(4)
    ranking_1.metric("Half-PPR ECR", _display_number(getattr(fp, "half_ecr", None)))
    ranking_2.metric("Dynasty ECR", _display_number(getattr(fp, "dynasty_ecr", None)))
    ranking_3.metric("ADP", _display_number(getattr(fp, "adp", None)))
    ranking_4.metric(
        "League Projection",
        _display_number(getattr(projection, "custom_points", None)),
    )

    (
        summary,
        documents,
        lookup_name,
        news_count,
        injury_count,
        error,
    ) = context.get_targeted_player_context(
        fp=fp,
        auction_player_name=player_name,
        fantasypros_data=context.fantasypros_data,
        context_store=context.context_store,
    )

    if error:
        st.warning("Live player-context refresh was unavailable: {0}".format(error))

    st.markdown("### Context Summary")
    status_1, status_2, status_3 = st.columns(3)
    status_1.metric("Targeted News", news_count if news_count is not None else "-")
    status_2.metric(
        "Targeted Injuries",
        injury_count if injury_count is not None else "-",
    )
    status_3.metric("Stored Documents", len(documents))
    st.caption("Context lookup identity: {0}".format(lookup_name))

    score_1, score_2, score_3, score_4, score_5 = st.columns(5)
    score_1.metric("Role", "{0:+.2f}".format(summary.role_score))
    score_2.metric("Usage", "{0:+.2f}".format(summary.usage_score))
    score_3.metric("Health", "{0:+.2f}".format(summary.health_score))
    score_4.metric("Dynasty", "{0:+.2f}".format(summary.dynasty_score))
    score_5.metric("Overall", "{0:+.2f}".format(summary.overall_context_score))
    st.caption("Context confidence: {0:.0%}".format(summary.confidence))

    if summary.reasons:
        for reason in summary.reasons:
            st.write("• {0}".format(reason))
    elif not documents:
        st.info(
            "No stored or live context documents matched this player. "
            "Sleeper metadata, rankings, and projections remain available above."
        )

    rows = []
    for document in documents:
        rows.append(
            {
                "Published": getattr(document, "published_at", None),
                "Source": getattr(document, "source_name", None),
                "Type": getattr(document, "source_type", None),
                "Title": getattr(document, "title", None),
                "Evidence": getattr(document, "content", None),
                "URL": getattr(document, "url", None),
            }
        )
    if rows:
        st.markdown("### Source Documents")
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
