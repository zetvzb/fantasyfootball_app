from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext

from .state import BidPlayerState


def render_signals_intelligence(
    context: AppRuntimeContext,
    state: BidPlayerState,
) -> None:

    fp = (
        state.fp
    )

    projection = (
        state.projection
    )

    recommendation = (
        state.recommendation
    )

    vorp_value = (
        state.vorp_value
    )

    # =================================================
    # PLAYER SIGNALS
    # =================================================

    st.markdown(
        "### Player Signals"
    )


    signal1, signal2, signal3, signal4 = (
        st.columns(4)
    )


    signal1.metric(
        "Your Need",
        f"{recommendation.my_need_score:.0%}",
    )


    signal2.metric(
        "Scarcity",
        f"{recommendation.scarcity_score:.0%}",
    )


    signal3.metric(
        "Bidder Threat",
        f"{recommendation.threat_score:.0f}/100",
    )


    signal4.metric(
        "VORP",
        (
            f"{vorp_value.vorp:.1f}"
            if vorp_value
            else "-"
        ),
    )


    if recommendation.reasons:

        st.write(
            " • ".join(
                recommendation.reasons
            )
        )


    # =================================================
    # NEXT OPTION
    # =================================================

    st.markdown(
        "### Next Option"
    )


    if (
        recommendation
        .alternative_player
    ):

        alt1, alt2, alt3 = (
            st.columns(3)
        )


        alt1.metric(
            f"Next {recommendation.position}",
            recommendation.alternative_player,
        )


        alt2.metric(
            "Expected Market",
            (
                f"${recommendation.alternative_market_value:.0f}"
                if (
                    recommendation
                    .alternative_market_value
                    is not None
                )
                else "-"
            ),
        )


        alt3.metric(
            "VORP",
            (
                f"{recommendation.alternative_vorp:.1f}"
                if (
                    recommendation
                    .alternative_vorp
                    is not None
                )
                else "-"
            ),
        )


    # =================================================
    # FANTASYPROS INTELLIGENCE
    # =================================================

    with st.container(border=True):

        st.markdown("### FantasyPros Intelligence")

        intel1, intel2, intel3, intel4 = (
            st.columns(4)
        )


        intel1.metric(
            "Projected Points",
            (
                f"{projection.custom_points:.1f}"
                if (
                    projection
                    and
                    projection.custom_points
                    is not None
                )
                else "-"
            ),
        )


        intel2.metric(
            "2026 ECR",
            (
                f"{fp.half_ecr:.0f}"
                if (
                    fp
                    and
                    fp.half_ecr
                    is not None
                )
                else "-"
            ),
        )


        intel3.metric(
            "Dynasty ECR",
            (
                f"{fp.dynasty_ecr:.0f}"
                if (
                    fp
                    and
                    fp.dynasty_ecr
                    is not None
                )
                else "-"
            ),
        )


        intel4.metric(
            "ADP",
            (
                f"{fp.adp:.1f}"
                if (
                    fp
                    and
                    fp.adp
                    is not None
                )
                else "-"
            ),
        )

