from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext


def render_sale_input(
    context: AppRuntimeContext,
) -> str:

    ACTIVE_DRAFT_ID = (
        context.ACTIVE_DRAFT_ID
    )

    ACTIVE_MANAGERS = (
        context.ACTIVE_MANAGERS
    )

    SleeperClient = (
        context.SleeperClient
    )

    draft_store = (
        context.draft_store
    )

    pool_result = (
        context.pool_result
    )

    recommendation_index = (
        context.recommendation_index
    )

    sleeper_players = (
        context.sleeper_players
    )

    sync_next_sleeper_sale = (
        context.sync_next_sleeper_sale
    )

    team_setups = (
        context.team_setups
    )

    private_key = context.runtime_identity.private_key

    # =========================================================
    # SALE INPUT
    # =========================================================

    st.divider()

    st.markdown(
        "## 📡 Sale Input"
    )


    sleeper_backed = context.selected_league.source_mode == "sleeper"
    sale_input_options = (
        ["Sleeper Live Sync", "Manual Sale Entry"]
        if sleeper_backed
        else ["Manual Sale Entry"]
    )
    sale_input_mode = (
        st.radio(
            "How should completed auction sales enter the app?",
            options=sale_input_options,
            horizontal=True,
            key=(
                private_key("sale_input_mode")
            ),
        )
    )


    # =========================================================
    # SLEEPER SYNC
    # =========================================================

    def perform_sleeper_sync():

        client = SleeperClient()


        draft_picks = (
            client.get_draft_picks(
                ACTIVE_DRAFT_ID
            )
        )


        latest_local_sales = (
            draft_store.load_sales()
        )


        return (
            sync_next_sleeper_sale(
                draft_picks=(
                    draft_picks
                ),
                starting_team_setups=(
                    team_setups
                ),
                starting_pool_players=(
                    pool_result.available_players
                ),
                sleeper_players=(
                    sleeper_players
                ),
                managers=(
                    ACTIVE_MANAGERS
                ),
                existing_sales=(
                    latest_local_sales
                ),
                recommendation_index=(
                    recommendation_index
                ),
                draft_store=(
                    draft_store
                ),
            )
        )


    if (
        sale_input_mode
        ==
        "Sleeper Live Sync"
        and sleeper_backed
    ):

        st.info(
            "Sleeper is currently the live sale feed. "
            "Completed sales write into the same SQLite "
            "ledger used by manual entry."
        )


        auto_sync = (
            st.toggle(
                "Auto-sync Sleeper every 30s",
                key=(
                    private_key("auto_sleeper_sync")
                ),
                help=(
                    "Off by default. When off, use the button below to pull "
                    "completed picks whenever you want."
                ),
            )
        )


        if hasattr(
            st,
            "fragment",
        ):

            fragment_interval = (
                "30s"
                if auto_sync
                else None
            )


            if auto_sync:
                st.caption("Pulling completed Sleeper picks every 30 seconds.")

            @st.fragment(
                run_every=(
                    fragment_interval
                )
            )
            def sleeper_live_feed():

                manual_sync = (
                    st.button(
                        "🔄 Sync Sleeper picks now",
                        width="stretch",
                        type="primary" if not auto_sync else "secondary",
                        key=private_key("sync_sleeper_now"),
                    )
                )


                if not (
                    auto_sync
                    or
                    manual_sync
                ):

                    return


                try:

                    result = (
                        perform_sleeper_sync()
                    )


                    if (
                        result.status
                        in {"imported", "reconciled"}
                    ):

                        st.success(
                            result.message
                        )

                        st.rerun()


                    elif (
                        result.status
                        ==
                        "conflict"
                    ):

                        st.error(
                            result.message
                        )


                except Exception as error:

                    st.error(
                        f"Sleeper sync failed: "
                        f"{error}"
                    )


            sleeper_live_feed()


        else:

            if st.button(
                "🔄 Sync Sleeper Now",
                width="stretch",
                key=private_key("sync_sleeper_now_fallback"),
            ):

                try:

                    result = (
                        perform_sleeper_sync()
                    )


                    st.success(
                        result.message
                    )


                    if (
                        result.status
                        in {"imported", "reconciled"}
                    ):

                        st.rerun()


                except Exception as error:

                    st.error(
                        f"Sleeper sync failed: "
                        f"{error}"
                    )



    return sale_input_mode
