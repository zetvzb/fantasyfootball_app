from __future__ import annotations

import streamlit as st

from src.app_runtime import AppRuntimeContext

from .bid_components import (
    build_bid_player_state,
    render_bidder_threats,
    render_buy_vs_pass,
    render_manual_sale,
    render_player_context,
    render_price_decision,
    render_signals_intelligence,
)


def render_bid_copilot(
    context: AppRuntimeContext,
    sale_input_mode: str,
) -> None:

    st.divider()

    st.header(
        "💰 Live Bid Copilot"
    )


    state = (
        build_bid_player_state(
            context
        )
    )


    if state is None:

        return


    render_price_decision(
        context,
        state,
    )


    render_buy_vs_pass(
        context,
        state,
    )


    render_player_context(
        context,
        state,
    )


    render_signals_intelligence(
        context,
        state,
    )


    render_bidder_threats(
        context,
        state,
    )


    render_manual_sale(
        context,
        state,
        sale_input_mode,
    )
