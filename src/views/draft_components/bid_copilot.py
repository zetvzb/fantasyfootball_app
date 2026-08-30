from __future__ import annotations

import streamlit as st

from src.agent_cache import auction_advice_fingerprint
from src.app_runtime import AppRuntimeContext
from src.draft_strategist import AuctionStrategistService
from src.live_cockpit import build_live_cockpit_summary
from src.live_evidence import evidence_section
from src.price_thresholds import LivePriceThresholds, constrain_thresholds
from src.recommendation_snapshot import build_recommendation_snapshot
from src.scenario_fair_value import scenario_ml_weight
from src.scenario_price_inference import (
    ScenarioPriceInferenceService,
    build_live_feature_row,
)

from .bid_components import (
    build_bid_player_state,
    render_buy_vs_pass,
    render_manual_sale,
    render_player_context,
    render_price_decision,
    render_signals_intelligence,
)


def render_bid_copilot(
    context: AppRuntimeContext,
    sale_input_mode: str,
    user_context: str = "",
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

    nominated_team = (
        getattr(state.fp, "nfl_team", None)
        or getattr(state.projection, "nfl_team", None)
    )
    position_team = " · ".join(
        part
        for part in (recommendation.position, nominated_team)
        if part
    )
    st.subheader(recommendation.player_name)
    if position_team:
        st.caption(position_team)

    thresholds = constrain_thresholds(
        LivePriceThresholds(
            target_value=recommendation.target_value or recommendation.do_not_exceed,
            soft_cap=recommendation.soft_cap or recommendation.do_not_exceed,
            hard_cap=recommendation.hard_cap or recommendation.do_not_exceed,
            explanation="Live cockpit thresholds.",
        ),
        state.live_hard_cap,
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
    # Transparency read-out: the Target/Soft/Hard caps above already use the
    # ML+rankings blend (applied upstream in the market-value pipeline). Here we
    # just surface the two inputs for the nominated player. Inference must never
    # interrupt the deterministic cockpit, so it is wrapped defensively.
    scenario_price = None
    try:
        features = build_live_feature_row(context, state)
        if features is not None:
            prediction = ScenarioPriceInferenceService().predict(features)
            if prediction is not None:
                rankings_value = float(
                    getattr(recommendation, "baseline_value", 0.0) or 0.0
                )
                scenario_price = {
                    "mode": "blended",
                    "model_version": prediction.model_version,
                    "ml_low": prediction.low,
                    "ml_predicted_price": prediction.predicted_price,
                    "ml_high": prediction.high,
                    "rankings_value": round(rankings_value, 2),
                    "blended_value": round(
                        float(recommendation.expected_market_value or 0.0), 2
                    ),
                    "ml_weight": scenario_ml_weight(),
                }
    except Exception:
        scenario_price = None
    # Capture the cockpit's read on this nomination, but only when the
    # decision-relevant inputs (player, live bid, decision) actually move --
    # not on every rerun. The full-state fingerprint used to churn on
    # inflation-index float drift, writing a fresh row (and firing a durable
    # checkpoint) many times per nomination, which is most of what made the
    # cockpit slow. Post-draft grading only keeps the latest snapshot per
    # player, so one row per distinct bid is all it needs.
    snapshot_guard_key = context.runtime_identity.private_key("last_snapshot_signature")
    snapshot_signature = (
        state.nominated_key,
        int(summary.current_bid),
        str(summary.decision),
        tuple(sorted((scenario_price or {}).items())),
    )
    if st.session_state.get(snapshot_guard_key) != snapshot_signature:
        snapshot = build_recommendation_snapshot(
            context=context,
            state=state,
            current_bid=summary.current_bid,
            target_value=summary.target_value,
            soft_cap=summary.soft_cap,
            hard_cap=summary.hard_cap,
            decision=summary.decision,
            shadow_price=scenario_price,
        )
        try:
            context.draft_store.add_recommendation_snapshot(snapshot)
            st.session_state[snapshot_guard_key] = snapshot_signature
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
    if scenario_price is not None:
        with st.expander("🔬 Price model: ML vs rankings", expanded=False):
            price_columns = st.columns(3)
            price_columns[0].metric(
                "ML price",
                "${0:.0f}".format(scenario_price["ml_predicted_price"]),
                help="Model range ${0:.0f}–${1:.0f}".format(
                    scenario_price["ml_low"], scenario_price["ml_high"]
                ),
            )
            price_columns[1].metric(
                "Baseline (VORP/ECR)",
                "${0:.0f}".format(scenario_price["rankings_value"]),
            )
            price_columns[2].metric(
                "Market value used",
                "${0:.0f}".format(scenario_price["blended_value"]),
            )
            st.caption(
                "Market value blends the ML price ({0:.0%} weight) with this "
                "league's pricing history, then the live-room calibration "
                "adjusts it. The Target / Soft / Hard caps above use that "
                "value; the deterministic engine then adjusts for need, threat "
                "and scarcity.".format(scenario_price["ml_weight"])
            )
    st.markdown("## {0}".format(summary.decision))
    st.caption(
        "Why: {0} • Alternatives: {1}".format(
            summary.why,
            ", ".join(summary.alternatives) or "none comparable",
        )
    )
    st.markdown("### 🤖 What To Do")
    st.caption(
        "Automatically updated when the nominated player or current bid changes. "
        "The strategist cannot bid or record a sale."
    )
    strategist_key = context.runtime_identity.private_key(
        "auction_strategist::{0}".format(
            auction_advice_fingerprint(
                summary=summary,
                bid_state=state,
                team_setup=context.my_live_setup,
                source_mode=context.ACTIVE_LEAGUE_PROFILE.source_mode,
                user_context=user_context,
            )
        )
    )
    if strategist_key not in st.session_state:
        with st.spinner("Reviewing price, roster state, and alternatives..."):
            st.session_state[strategist_key] = (
                AuctionStrategistService().recommend_auction(
                    summary=summary,
                    bid_state=state,
                    team_setup=context.my_live_setup,
                    source_mode=context.ACTIVE_LEAGUE_PROFILE.source_mode,
                    user_context=user_context,
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
            shadow_price=scenario_price,
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


    render_manual_sale(
        context,
        state,
        sale_input_mode,
    )
