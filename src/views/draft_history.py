from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext


def render_draft_history_view(
    context: AppRuntimeContext,
) -> None:

    ACTIVE_MANAGERS = context.ACTIVE_MANAGERS

    historical_market_model = context.historical_market_model

    live_sales = context.live_sales

    selected_league = context.selected_league

    st.header(
        "📚 Draft History"
    )

    st.caption(
        "Review recorded sales, historical market behavior, manager tendencies, and auction pricing context."
    )

    # =========================================================
    # LEDGER
    # =========================================================

    st.subheader(
        "📜 Persistent Auction Ledger"
    )


    ledger_rows = []


    for sale in live_sales:

        team_name = (
            ACTIVE_MANAGERS[
                sale.manager_id
            ].sleeper_team_name

            if sale.manager_id
            in ACTIVE_MANAGERS

            else sale.manager_id
        )


        delta = None


        if (
            sale.modeled_market_value
            is not None
        ):

            delta = (
                sale.price
                -
                sale.modeled_market_value
            )


        ratio = None


        if (
            sale.modeled_market_value
            is not None
            and
            sale.modeled_market_value
            >
            0
        ):

            ratio = (
                sale.price
                /
                sale.modeled_market_value
            )


        ledger_rows.append(
            {
                "#": sale.sale_number,
                "Player": sale.player_name,
                "Pos": sale.position,
                "Winner": team_name,
                "Price": sale.price,
                "Market at Sale": (
                    sale.modeled_market_value
                ),
                "vs Market": delta,
                "Actual / Model": ratio,
                "My Ceiling": (
                    sale.do_not_exceed
                ),
            }
        )


    if ledger_rows:

        st.dataframe(
            pd.DataFrame(
                ledger_rows
            ),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "No auction sales recorded yet."
        )

    with st.expander(
        f"📚 Historical {selected_league.league_name} Market"
    ):

        h1, h2, h3, h4 = (
            st.columns(4)
        )


        h1.metric(
            "Mapped Sales",
            len(
                historical_market_model
                .mapped_sales
            ),
        )


        h2.metric(
            "Eligible Seasons",
            len(
                historical_market_model
                .eligible_years
            ),
        )


        h3.metric(
            "Unmapped Sales",
            historical_market_model
            .unmapped_sales_count,
        )


        h4.metric(
            "Historical Avg Buy",
            (
                f"${historical_market_model.league_average_purchase:.1f}"
            ),
        )


        historical_manager_rows = []


        for (
            manager_id,
            profile,
        ) in (
            historical_market_model
            .manager_profiles
            .items()
        ):

            team_name = (
                ACTIVE_MANAGERS[
                    manager_id
                ].sleeper_team_name

                if manager_id
                in ACTIVE_MANAGERS

                else manager_id
            )


            historical_manager_rows.append(
                {
                    "Team": team_name,
                    "Buys": profile.sales_count,
                    "Avg Buy": profile.average_price,
                    "Max Buy": profile.max_price,
                    "Aggressiveness": (
                        profile.aggressiveness_index
                    ),
                    "Star Chase": (
                        profile.star_chase_index
                    ),
                }
            )


        if historical_manager_rows:

            st.dataframe(
                pd.DataFrame(
                    historical_manager_rows
                ).sort_values(
                    by="Aggressiveness",
                    ascending=False,
                ),
                use_container_width=True,
                hide_index=True,
            )
