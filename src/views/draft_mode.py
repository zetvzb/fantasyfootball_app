from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from src.app_runtime import AppRuntimeContext
from src.keyboard_shortcuts import build_shortcut_script, shortcut_help

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

    sale_input_mode = st.session_state.get(
        context.runtime_identity.private_key("sale_input_mode"),
        "Sleeper Live Sync",
    )

    render_bid_copilot(
        context,
        sale_input_mode,
    )

    render_live_economy(context)
    render_roster_plan(context)
    st.markdown('<div id="auction-nomination"></div>', unsafe_allow_html=True)
    render_nomination_strategy(context)
    st.markdown('<div id="auction-sale-entry"></div>', unsafe_allow_html=True)
    render_sale_input(context)

    render_live_team_state(
        context
    )

    render_auction_board(
        context
    )

    with st.sidebar.expander("⌨️ Keyboard Shortcuts"):
        for line in shortcut_help():
            st.caption(line)
        st.caption("Shortcuts are disabled while typing or editing a field.")
    components.html(build_shortcut_script(), height=0, width=0)
