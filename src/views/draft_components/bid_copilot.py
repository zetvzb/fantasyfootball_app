from __future__ import annotations

import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.draft_strategist import AuctionStrategistService
from src.live_cockpit import build_live_cockpit_summary
from src.live_evidence import evidence_section
from src.price_thresholds import LivePriceThresholds, constrain_thresholds
from src.recommendation_snapshot import build_recommendation_snapshot

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
    snapshot = build_recommendation_snapshot(
        context=context,
        state=state,
        current_bid=summary.current_bid,
        target_value=summary.target_value,
        soft_cap=summary.soft_cap,
        hard_cap=summary.hard_cap,
        decision=summary.decision,
    )
    try:
        context.draft_store.add_recommendation_snapshot(snapshot)
    except (OSError, ValueError) as error:
        st.warning("Recommendation snapshot could not be saved: {0}".format(error))
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
    st.markdown("### 🤖 Auction Strategist")
    st.caption(
        "A read-only agent inspects this deterministic price decision, your "
        "cash/roster state, and pass alternatives. It cannot bid or record a sale."
    )
    strategist_key = context.runtime_identity.private_key(
        "auction_strategist::{0}::{1}".format(
            state.nominated_key, summary.current_bid
        )
    )
    if st.button(
        "Ask Auction Strategist",
        key=context.runtime_identity.private_key(
            "ask_auction_strategist::{0}".format(state.nominated_key)
        ),
    ):
        with st.spinner("Reviewing price, roster state, and alternatives..."):
            st.session_state[strategist_key] = (
                AuctionStrategistService().recommend_auction(
                    summary=summary,
                    bid_state=state,
                    team_setup=context.my_live_setup,
                    source_mode=context.ACTIVE_LEAGUE_PROFILE.source_mode,
                )
            )
    strategist = st.session_state.get(strategist_key)
    if strategist is not None:
        message = "{0} {1} — max ${2} — {3} confidence".format(
            strategist.decision,
            strategist.player_name,
            strategist.max_bid,
            strategist.confidence.upper(),
        )
        if strategist.decision == "PASS":
            st.warning(message)
        elif strategist.decision == "CAUTION":
            st.info(message)
        else:
            st.success(message)
        st.write(strategist.explanation)
        if strategist.alternatives:
            st.caption("Fallbacks: {0}".format(" → ".join(strategist.alternatives)))
        if strategist.warning:
            st.warning(strategist.warning)
        elif strategist.source == "openai":
            st.caption(
                "AI advisory via {0}; deterministic caps unchanged."
                .format(strategist.model)
            )
    pass_key = context.runtime_identity.private_key("last_passed_player")
    if st.button(
        "⏭️ PASS",
        key=context.runtime_identity.private_key(
            "pass_{0}".format(state.nominated_key)
        ),
    ):
        st.session_state[pass_key] = recommendation.player_name
        pass_snapshot = build_recommendation_snapshot(
            context=context,
            state=state,
            current_bid=summary.current_bid,
            target_value=summary.target_value,
            soft_cap=summary.soft_cap,
            hard_cap=summary.hard_cap,
            decision="PASS",
        )
        context.draft_store.add_recommendation_snapshot(pass_snapshot)
    if st.session_state.get(pass_key) == recommendation.player_name:
        st.info("PASS recorded for this nomination; no sale was written.")


    render_price_decision(
        context,
        state,
    )


    scenario_section = evidence_section("scenario")
    with st.expander(scenario_section.label, expanded=scenario_section.expanded):
        render_buy_vs_pass(context, state)

    context_section = evidence_section("context")
    with st.expander(context_section.label, expanded=context_section.expanded):
        render_player_context(context, state)

    signals_section = evidence_section("signals")
    with st.expander(signals_section.label, expanded=signals_section.expanded):
        render_signals_intelligence(context, state)


    render_bidder_threats(
        context,
        state,
    )


    render_manual_sale(
        context,
        state,
        sale_input_mode,
    )
