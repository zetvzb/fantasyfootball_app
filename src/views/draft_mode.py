from __future__ import annotations

import streamlit as st

from src.app_runtime import AppRuntimeContext

from .draft_components import (
    render_auction_board,
    render_bid_copilot,
    render_live_economy,
    render_live_team_state,
    render_nomination_strategy,
    render_roster_plan,
    render_sale_input,
)


def render_draft_mode_view(
    context: AppRuntimeContext,
) -> None:

    st.header(
        "🚨 Draft Mode"
    )

    st.caption(
        "Live auction cockpit: room economics, "
        "nominations, bid ceilings, roster optimization, "
        "Sleeper sync, and current team state."
    )

    render_live_economy(
        context
    )

    render_roster_plan(
        context
    )

    render_nomination_strategy(
        context
    )

    sale_input_mode = (
        render_sale_input(
            context
        )
    )

    render_bid_copilot(
        context,
        sale_input_mode,
    )

    render_live_team_state(
        context
    )

    render_auction_board(
        context
    )
