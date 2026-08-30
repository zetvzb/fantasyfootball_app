from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.recommendation_snapshot import build_recommendation_snapshot

from .state import BidPlayerState


def render_manual_sale(
    context: AppRuntimeContext,
    state: BidPlayerState,
    sale_input_mode: str,
) -> None:

    final_do_not_exceed = (
        state.final_do_not_exceed
    )

    nominated_key = (
        state.nominated_key
    )

    recommendation = (
        state.recommendation
    )

    ACTIVE_MANAGERS = (
        context.ACTIVE_MANAGERS
    )

    add_live_sale = (
        context.add_live_sale
    )

    draft_store = (
        context.draft_store
    )

    live_sales = (
        context.live_sales
    )

    live_team_setups = (
        context.live_team_setups
    )

    team_setups = (
        context.team_setups
    )

    # =================================================
    # MANUAL SALE
    # =================================================

    if (
        sale_input_mode
        ==
        "Manual Sale Entry"
    ):

        st.markdown(
            "## 🧾 Record Completed Sale"
        )


        with st.form(
            key=(
                context.runtime_identity.private_key(
                    f"record_sale_{nominated_key}"
                )
            )
        ):

            winner_id = (
                st.selectbox(
                    "Winning Team",
                    options=list(
                        live_team_setups.keys()
                    ),
                    format_func=(
                        lambda manager_id: (
                            ACTIVE_MANAGERS[
                                manager_id
                            ].sleeper_team_name
                        )
                    ),
                )
            )


            winner_state = (
                live_team_setups[
                    winner_id
                ]
            )


            st.caption(
                f"Cash: "
                f"${winner_state.auction_cash} • "
                f"Open spots: "
                f"{winner_state.open_roster_spots} • "
                f"Legal max: "
                f"${winner_state.max_bid}"
            )


            sale_price = (
                st.number_input(
                    "Sale Price",
                    min_value=1,
                    value=1,
                    step=1,
                )
            )


            submit_sale = (
                st.form_submit_button(
                    "✅ RECORD SALE",
                    width="stretch",
                )
            )


            if submit_sale:

                try:

                    updated_sales = (
                        add_live_sale(
                            starting_team_setups=(
                                team_setups
                            ),
                            existing_sales=(
                                live_sales
                            ),
                            player_name=(
                                recommendation
                                .player_name
                            ),
                            position=(
                                recommendation
                                .position
                            ),
                            manager_id=(
                                winner_id
                            ),
                            price=(
                                int(
                                    sale_price
                                )
                            ),
                            modeled_market_value=(
                                recommendation
                                .expected_market_value
                            ),
                            do_not_exceed=(
                                final_do_not_exceed
                            ),
                        )
                    )


                    draft_store.add_sale(
                        updated_sales[
                            -1
                        ]
                    )


                    try:
                        draft_store.add_recommendation_snapshot(
                            build_recommendation_snapshot(
                                context=context,
                                state=state,
                                current_bid=int(sale_price),
                                target_value=(
                                    recommendation.target_value
                                    or recommendation.do_not_exceed
                                ),
                                soft_cap=(
                                    recommendation.soft_cap
                                    or recommendation.do_not_exceed
                                ),
                                hard_cap=(
                                    recommendation.hard_cap
                                    or recommendation.do_not_exceed
                                ),
                                decision="SOLD",
                            )
                        )
                    except (OSError, ValueError):
                        # A missing decision-time snapshot only degrades
                        # post-draft grading for this one player; never
                        # block recording the sale over it.
                        pass


                    st.rerun()


                except ValueError as error:

                    st.error(
                        str(
                            error
                        )
                    )

