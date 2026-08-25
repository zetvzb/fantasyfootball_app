from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext

from .state import BidPlayerState


def render_bidder_threats(
    context: AppRuntimeContext,
    state: BidPlayerState,
) -> None:

    threat_summary = (
        state.threat_summary
    )

    ACTIVE_MANAGERS = (
        context.ACTIVE_MANAGERS
    )

    live_calibration = (
        context.live_calibration
    )

    # =================================================
    # BIDDER THREATS
    # =================================================

    with st.expander(
        "Who Might Bid Against Me?"
    ):

        bidder_rows = []


        if threat_summary:

            for threat in (
                threat_summary.threats
            ):

                manager_id = (
                    threat.manager_id
                )


                team_name = (
                    ACTIVE_MANAGERS[
                        manager_id
                    ].sleeper_team_name

                    if manager_id
                    in ACTIVE_MANAGERS

                    else manager_id
                )


                live_manager = (
                    live_calibration
                    .manager_profiles
                    .get(
                        manager_id
                    )
                )


                bidder_rows.append(
                    {
                        "Team": team_name,
                        "Threat": threat.threat_score,
                        "Need": (
                            threat.need_score
                            *
                            100
                        ),
                        "Cash": threat.auction_cash,
                        "Legal Max": threat.max_bid,
                        "Can Afford": (
                            threat.can_afford_market
                        ),
                        "2026 Buys": (
                            live_manager.purchases
                            if live_manager
                            else 0
                        ),
                        "2026 Aggression": (
                            live_manager.multiplier
                            if live_manager
                            else 1.0
                        ),
                        "Why": (
                            "; ".join(
                                threat.reasons
                            )
                        ),
                    }
                )


        if bidder_rows:

            st.dataframe(
                pd.DataFrame(
                    bidder_rows
                ),
                use_container_width=True,
                hide_index=True,
            )


