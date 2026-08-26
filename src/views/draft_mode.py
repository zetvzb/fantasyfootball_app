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


def _render_cockpit_status_bar(context: AppRuntimeContext) -> None:
    """Always-visible situational awareness -- cash, open spots, and the
    most recent sale -- so you never have to scroll to answer "where do
    things stand right now" while the clock is effectively running on
    every nomination.
    """

    my_live_setup = context.my_live_setup
    live_sales = context.live_sales

    status_columns = st.columns(4)
    status_columns[0].metric(
        "💰 My Live Cash",
        "${0}".format(my_live_setup.live_cash) if my_live_setup is not None else "—",
    )
    status_columns[1].metric(
        "🎯 Discretionary",
        "${0}".format(my_live_setup.discretionary_cash)
        if my_live_setup is not None
        else "—",
        help="Cash above the minimum-bid reserve for your remaining roster spots.",
    )
    status_columns[2].metric(
        "🪑 Open Spots",
        my_live_setup.open_roster_spots if my_live_setup is not None else "—",
    )
    status_columns[3].metric(
        "📜 Sales Recorded",
        len(live_sales),
    )

    if live_sales:
        last_sale = max(live_sales, key=lambda sale: sale.sale_number)
        owner = context.ACTIVE_MANAGERS.get(last_sale.manager_id)
        owner_name = (
            owner.sleeper_team_name or owner.sleeper_username
            if owner is not None
            else last_sale.manager_id
        )
        st.caption(
            "Last sale: **{0}** — ${1} to {2}".format(
                last_sale.player_name, last_sale.price, owner_name
            )
        )
    else:
        st.caption("No sales recorded yet this draft.")

    st.divider()


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

    _render_cockpit_status_bar(context)

    sale_input_mode = st.session_state.get(
        context.runtime_identity.private_key("sale_input_mode"),
        (
            "Sleeper Live Sync"
            if context.selected_league.source_mode == "sleeper"
            else "Manual Sale Entry"
        ),
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
