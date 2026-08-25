from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.price_thresholds import LivePriceThresholds, constrain_thresholds

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

    current_bid = (
        st.number_input(
            "Current Bid",
            min_value=1,
            value=1,
            step=1,
            key=(
                context.runtime_identity.private_key(
                    f"current_bid_{nominated_key}"
                )
            ),
        )
    )


    if (
        current_bid
        <
        final_do_not_exceed
    ):

        st.success(
            f"${final_do_not_exceed - current_bid} "
            f"of bidding room remains."
        )


    elif (
        current_bid
        ==
        final_do_not_exceed
    ):

        st.warning(
            "THIS IS YOUR CEILING. "
            "Do not bid again."
        )


    else:

        st.error(
            f"STOP — ${current_bid} is above "
            f"your ${final_do_not_exceed} ceiling."
        )
