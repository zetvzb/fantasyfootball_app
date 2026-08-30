from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from src.app_runtime import AppRuntimeContext
from src.auction_agent_context import append_agent_context, format_agent_context
from src.keyboard_shortcuts import build_shortcut_script, shortcut_help

from .draft_components import (
    render_auction_board,
    render_bid_copilot,
    render_keeper_stash_board,
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

    model = context.historical_market_model
    if model is not None and not getattr(model, "eligible_years", None):
        st.warning(
            "No historical auction prices are loaded for this league, so "
            "market values and nomination prices are running **uncalibrated** "
            "-- pure projection/VORP with no correction toward what your room "
            "actually pays. Expect elite prices to read high and mid-round "
            "prices to read low. Add past sales under League Setup → History "
            "to fix this.",
            icon="⚠️",
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
        "Two decision points: nobody's on the clock -- decide who to "
        "nominate -- or a player is up -- decide bid or pass. Everything "
        "else is reference, one click away below."
    )

    _render_cockpit_status_bar(context)

    context_key = context.runtime_identity.private_key("auction_agent_context")
    context_input_key = context.runtime_identity.private_key("auction_agent_context_input")
    messages = list(st.session_state.get(context_key, []))
    with st.expander("💬 Tell the copilot what you know", expanded=False):
        st.caption(
            "Add injuries, room behavior, your preferences, or anything that should "
            "affect the next nomination or buy/pass judgment. Context never overrides "
            "the deterministic hard cap."
        )
        with st.form(
            context.runtime_identity.private_key("auction_agent_context_form"),
            clear_on_submit=True,
        ):
            message = st.text_input(
                "Context for the agent",
                placeholder="Example: Manager 7 is aggressively chasing running backs.",
                key=context_input_key,
            )
            submitted = st.form_submit_button("Send to copilot")
        if submitted and message.strip():
            messages = append_agent_context(messages, message)
            st.session_state[context_key] = messages
            st.rerun()
        for item in messages:
            st.info(item)
        if messages and st.button(
            "Clear context",
            key=context.runtime_identity.private_key("clear_auction_agent_context"),
        ):
            st.session_state[context_key] = []
            st.rerun()
    agent_context = format_agent_context(messages)

    sale_input_mode = st.session_state.get(
        context.runtime_identity.private_key("sale_input_mode"),
        (
            "Sleeper Live Sync"
            if context.selected_league.source_mode == "sleeper"
            else "Manual Sale Entry"
        ),
    )

    # =========================================================
    # DECISION POINT 1 -- WHO TO NOMINATE
    #
    # Always shown first, above the fold: it answers "what do I do
    # right now" the moment nobody has a player up, instead of making
    # that decision the last thing on the page.
    # =========================================================

    render_nomination_strategy(context, agent_context)

    # Endgame targeting aid: cheap players left who project as positive
    # keeper value next year. Collapsed early, auto-opens once the room's
    # money is mostly spent.
    render_keeper_stash_board(context)

    # =========================================================
    # DECISION POINT 2 -- BID OR PASS ON THE CURRENT NOMINATION
    #
    # render_bid_copilot renders nothing if no player is selected as
    # nominated, so the two decision points never fight for space.
    # =========================================================

    render_bid_copilot(
        context,
        sale_input_mode,
        agent_context,
    )

    st.markdown('<div id="auction-sale-entry"></div>', unsafe_allow_html=True)
    render_sale_input(context)

    # =========================================================
    # REFERENCE & TOOLS -- collapsed by default
    #
    # Room state, the full remaining-roster optimizer, and the
    # 400+ row draftable-player board are all genuinely useful, but
    # not part of either decision point above and expensive enough
    # (an exhaustive beam search, a full-pool table) that computing
    # them on every keystroke elsewhere in the cockpit is wasted work.
    # Gating them behind real toggles -- not just a visually-collapsed
    # expander, which still runs its body every rerun -- is what
    # actually skips that cost until you ask for it.
    # =========================================================

    st.divider()
    st.markdown("### 📊 Reference & Tools")

    with st.expander("👥 Live Team State (cash, needs, every manager)"):
        render_live_team_state(context)

    with st.expander("💵 Room Economics (inflation, calibration)"):
        render_live_economy(context)

    with st.expander("🧩 Optimal Remaining Roster"):
        show_roster_plan = st.toggle(
            "Compute optimal remaining roster",
            value=False,
            help="Runs a full beam search over your remaining picks.",
            key=context.runtime_identity.private_key(
                "draft_mode_show_roster_plan"
            ),
        )
        if show_roster_plan:
            render_roster_plan(context)
        else:
            st.caption("Toggle on to compute -- skipped by default for speed.")

    with st.expander("📋 Full Auction Board (every available player)"):
        show_auction_board = st.toggle(
            "Show full auction board",
            value=False,
            help="Renders every draftable player -- hundreds of rows.",
            key=context.runtime_identity.private_key(
                "draft_mode_show_auction_board"
            ),
        )
        if show_auction_board:
            render_auction_board(context)
        else:
            st.caption("Toggle on to render -- skipped by default for speed.")

    with st.sidebar.expander("⌨️ Keyboard Shortcuts"):
        for line in shortcut_help():
            st.caption(line)
        st.caption("Shortcuts are disabled while typing or editing a field.")
    components.html(build_shortcut_script(), height=0, width=0)
