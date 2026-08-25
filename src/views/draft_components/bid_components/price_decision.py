from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.price_thresholds import (
    LivePriceThresholds,
    constrain_thresholds,
    evaluate_current_bid,
)

from .state import BidPlayerState


def render_price_decision(
    context: AppRuntimeContext,
    state: BidPlayerState,
) -> None:

    context_adjusted_ceiling = (
        state.context_adjusted_ceiling
    )

    context_adjustment = (
        state.context_adjustment
    )

    final_do_not_exceed = (
        state.final_do_not_exceed
    )

    nominated_key = (
        state.nominated_key
    )

    nomination_info = (
        state.nomination_info
    )

    player_level_ceiling = (
        state.player_level_ceiling
    )

    recommendation = (
        state.recommendation
    )

    thresholds = constrain_thresholds(
        LivePriceThresholds(
            target_value=recommendation.target_value or recommendation.do_not_exceed,
            soft_cap=recommendation.soft_cap or recommendation.do_not_exceed,
            hard_cap=recommendation.hard_cap or recommendation.do_not_exceed,
            explanation="Three explicit live bidding thresholds.",
        ),
        final_do_not_exceed,
    )

    roster_ceiling = (
        state.roster_ceiling
    )

    roster_ceiling_available = (
        state.roster_ceiling_available
    )

    selected_market = (
        state.selected_market
    )

    dynamic_cap_result = state.dynamic_cap_result

    # =================================================
    # PLAYER HEADER
    # =================================================

    st.markdown(
        f"# {recommendation.player_name}"
    )


    if nomination_info:

        st.caption(
            f"{recommendation.position} • "
            f"Nomination: "
            f"{nomination_info.action}"
        )


    left, center_left, center_right, right = st.columns(4)


    with left:

        st.metric(
            "Expected Market",
            (
                f"${recommendation.expected_market_value:.0f}"
            ),
        )


        st.metric(
            "Deterministic Ceiling",
            (
                f"${player_level_ceiling}"
            ),
        )


    with center_left:
        st.metric("Target Value", "${0}".format(thresholds.target_value))
        st.metric("Soft Cap", "${0}".format(thresholds.soft_cap))

    with center_right:
        st.markdown("## HARD CAP")
        st.markdown("# 💰 ${0}".format(thresholds.hard_cap))
        st.markdown("### {0}".format(recommendation.strategy))


    with right:

        st.metric(
            "Context Ceiling",
            (
                f"${context_adjusted_ceiling}"
            ),
            delta=(
                f"{context_adjustment.adjustment_dollars:+d}"
                if context_adjustment.applied
                else None
            ),
        )


        st.metric(
            "Roster Ceiling",
            (
                f"${roster_ceiling}"
            ),
        )


    st.caption(
        f"Legal maximum bid: "
        f"${recommendation.legal_max_bid}"
    )

    with st.expander("Dynamic Cap Factors"):
        st.caption(
            "Dynamic adjustment: {0:+.1%} (${1} → ${2}).".format(
                dynamic_cap_result.total_adjustment_pct,
                dynamic_cap_result.base_cap,
                dynamic_cap_result.adjusted_cap,
            )
        )
        st.dataframe(
            [
                {
                    "Factor": component.factor,
                    "Adjustment": component.adjustment_pct,
                    "Why": component.explanation,
                }
                for component in dynamic_cap_result.components
            ],
            width="stretch",
            hide_index=True,
        )


    # =================================================
    # CONTEXT PRICE EFFECT
    # =================================================

    if context_adjustment.applied:

        context_message = (
            f"Context changed the player ceiling "
            f"from ${player_level_ceiling} "
            f"to ${context_adjusted_ceiling} "
            f"({context_adjustment.adjustment_pct:+.1%})."
        )


        if (
            context_adjustment
            .adjustment_dollars
            >
            0
        ):

            st.success(
                context_message
            )

        else:

            st.warning(
                context_message
            )


        with st.expander(
            "Why Context Changed the Price"
        ):

            ca1, ca2, ca3, ca4 = (
                st.columns(4)
            )


            ca1.metric(
                "Current Signal",
                (
                    f"{context_adjustment.current_signal:+.2f}"
                ),
            )


            ca2.metric(
                "Future Signal",
                (
                    f"{context_adjustment.future_signal:+.2f}"
                ),
            )


            ca3.metric(
                "60/40 Blend",
                (
                    f"{context_adjustment.blended_signal:+.2f}"
                ),
            )


            ca4.metric(
                "Confidence",
                (
                    f"{context_adjustment.context_confidence:.0%}"
                ),
            )


            st.caption(
                f"Confidence strength used for pricing: "
                f"{context_adjustment.confidence_strength:.0%}"
            )


            for reason in (
                context_adjustment.reasons
            ):

                st.write(
                    f"• {reason}"
                )

            if context_adjustment.signal_details:
                st.dataframe(
                    [
                        {
                            "Signal": signal.signal,
                            "Evidence": signal.evidence_class.value,
                            "Direction": signal.direction,
                            "Magnitude": signal.magnitude,
                            "Explanation": signal.explanation,
                            "Source": signal.source_name,
                            "Document": signal.source_document_id,
                            "Metadata": signal.source_metadata,
                        }
                        for signal in context_adjustment.signal_details
                    ],
                    width="stretch",
                    hide_index=True,
                )


    else:

        st.caption(
            "Player context did not materially change "
            "the deterministic ceiling."
        )


    # =================================================
    # ROSTER EFFECT
    # =================================================

    if (
        roster_ceiling_available
        and
        roster_ceiling
        <
        context_adjusted_ceiling
    ):

        st.warning(
            f"Roster construction lowers the ceiling "
            f"from ${context_adjusted_ceiling} "
            f"to ${roster_ceiling}."
        )


    # =================================================
    # CEILING PIPELINE
    # =================================================

    with st.expander(
        "💵 Ceiling Calculation"
    ):

        price1, price2, price3, price4 = (
            st.columns(4)
        )


        price1.metric(
            "1. Deterministic",
            f"${player_level_ceiling}",
        )


        price2.metric(
            "2. Context",
            f"${context_adjusted_ceiling}",
        )


        price3.metric(
            "3. Roster",
            f"${roster_ceiling}",
        )


        price4.metric(
            "4. Final",
            f"${final_do_not_exceed}",
        )


    # =================================================
    # LIVE MARKET
    # =================================================

    if selected_market:

        with st.expander(
            "2026 Live Price Adjustment"
        ):

            lp1, lp2, lp3, lp4 = (
                st.columns(4)
            )


            lp1.metric(
                "Before Live Learning",
                (
                    f"${selected_market.pre_live_market_value:.1f}"
                ),
            )


            lp2.metric(
                "Live Multiplier",
                (
                    f"{selected_market.live_multiplier:.3f}x"
                ),
            )


            lp3.metric(
                "Position Signal",
                (
                    f"{selected_market.position_multiplier:.3f}x"
                ),
            )


            lp4.metric(
                "Tier",
                selected_market.price_tier,
            )


    # =================================================
    # CURRENT BID
    # =================================================

    current_bid_key = context.runtime_identity.private_key(
        "current_bid_{0}".format(nominated_key)
    )
    if current_bid_key not in st.session_state:
        st.session_state[current_bid_key] = 1

    def increment_current_bid(amount: int) -> None:
        st.session_state[current_bid_key] = max(
            1, int(st.session_state[current_bid_key]) + amount
        )

    bid_controls = st.columns(4)
    for column, amount in zip(bid_controls, (1, 2, 5, 10)):
        column.button(
            "+${0}".format(amount),
            key=context.runtime_identity.private_key(
                "bid_increment_{0}_{1}".format(nominated_key, amount)
            ),
            on_click=increment_current_bid,
            args=(amount,),
            width="stretch",
        )

    current_bid = (
        st.number_input(
            "Current Bid",
            min_value=1,
            value=1,
            step=1,
            key=current_bid_key,
        )
    )

    bid_decision = evaluate_current_bid(int(current_bid), thresholds)
    message = "{0} — {1} (${2} to hard cap)".format(
        bid_decision.zone.value,
        bid_decision.message,
        bid_decision.dollars_to_hard_cap,
    )
    if bid_decision.zone.value in ("HARD CAP", "PASS"):
        st.error(message)
    elif bid_decision.zone.value == "SOFT CAP":
        st.warning(message)
    else:
        st.success(message)
