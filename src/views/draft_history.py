from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.purchase_grading import grade_recorded_purchases


def render_draft_history_view(
    context: AppRuntimeContext,
) -> None:

    ACTIVE_MANAGERS = context.ACTIVE_MANAGERS

    live_sales = context.live_sales

    snapshots = context.private_state_access.load_recommendation_history(
        context.draft_store
    )
    purchase_grades = grade_recorded_purchases(
        live_sales,
        snapshots,
    )
    grade_by_sale = {grade.sale_number: grade for grade in purchase_grades}

    st.header(
        "📚 Draft History"
    )

    st.caption(
        "Review recorded sales and auction pricing context. Post-draft "
        "grading, manager tendencies, and historical market behavior now "
        "live in the 🧠 Manager Intelligence view."
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
                "Purchase Grade": (
                    grade_by_sale[sale.sale_number].letter_grade
                    if sale.sale_number in grade_by_sale
                    else "-"
                ),
                "Grade Score": (
                    grade_by_sale[sale.sale_number].total_score
                    if sale.sale_number in grade_by_sale
                    else None
                ),
            }
        )


    if ledger_rows:

        st.dataframe(
            pd.DataFrame(
                ledger_rows
            ),
            width="stretch",
            hide_index=True,
        )

    else:

        st.info(
            "No auction sales recorded yet."
        )
