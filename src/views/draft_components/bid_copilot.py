from __future__ import annotations

import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.live_cockpit import build_live_cockpit_summary
from src.price_thresholds import LivePriceThresholds, constrain_thresholds

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

    recommendation = state.recommendation
    thresholds = constrain_thresholds(
        LivePriceThresholds(
            target_value=recommendation.target_value or recommendation.do_not_exceed,
            soft_cap=recommendation.soft_cap or recommendation.do_not_exceed,
            hard_cap=recommendation.hard_cap or recommendation.do_not_exceed,
            explanation="Live cockpit thresholds.",
        ),
        state.final_do_not_exceed,
    )
    bid_key = context.runtime_identity.private_key(
        "current_bid_{0}".format(state.nominated_key)
    )
    summary = build_live_cockpit_summary(
        player_name=recommendation.player_name,
        current_bid=int(st.session_state.get(bid_key, 1)),
        target_value=thresholds.target_value,
        soft_cap=thresholds.soft_cap,
        hard_cap=thresholds.hard_cap,
        strategy=recommendation.strategy,
        reasons=getattr(recommendation, "reasons", ()),
        alternatives=state.pass_alternatives,
        regret_risk=state.pass_regret_risk.level,
        room_threat=float(getattr(state.threat_summary, "top_threat_score", 0.0) or 0.0),
    )
    st.markdown("### Decision Cockpit")
    columns = st.columns(6)
    columns[0].metric("Current Bid", "${0}".format(summary.current_bid))
    columns[1].metric("Target", "${0}".format(summary.target_value))
    columns[2].metric("Soft Cap", "${0}".format(summary.soft_cap))
    columns[3].metric("Hard Cap", "${0}".format(summary.hard_cap))
    columns[4].metric("Regret", summary.regret_risk)
    columns[5].metric("Room Threat", "{0:.0f}".format(summary.room_threat))
    st.markdown("## {0}".format(summary.decision))
    st.caption(
        "Why: {0} • Alternatives: {1}".format(
            summary.why,
            ", ".join(summary.alternatives) or "none comparable",
        )
    )
    pass_key = context.runtime_identity.private_key("last_passed_player")
    if st.button(
        "⏭️ PASS",
        key=context.runtime_identity.private_key(
            "pass_{0}".format(state.nominated_key)
        ),
    ):
        st.session_state[pass_key] = recommendation.player_name
    if st.session_state.get(pass_key) == recommendation.player_name:
        st.info("PASS recorded for this nomination; no sale was written.")


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
