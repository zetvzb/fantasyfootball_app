from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext


def render_league_setup_view(
    context: AppRuntimeContext,
) -> None:

    ACTIVE_LEAGUE_PROFILE = context.ACTIVE_LEAGUE_PROFILE

    ACTIVE_MANAGERS = context.ACTIVE_MANAGERS

    context_store = context.context_store

    depth_chart_documents = context.depth_chart_documents

    depth_chart_error = context.depth_chart_error

    depth_movement_error = context.depth_movement_error

    depth_movement_result = context.depth_movement_result

    draft_store = context.draft_store

    historical_market_model = context.historical_market_model

    league_data = context.league_data

    league_setup_data = context.league_setup_data

    league_setup_store = context.league_setup_store

    manual_setup_data = context.manual_setup_data

    manual_setup_loaded = context.manual_setup_loaded

    persisted_setup = context.persisted_setup

    pool_result = context.pool_result

    render_league_setup_editor = context.render_league_setup_editor

    selected_league = context.selected_league

    setup_locked = context.setup_locked

    setup_source_summary = context.setup_source_summary

    workbook_loaded = context.workbook_loaded

    st.header(
        "🏠 League Setup"
    )

    st.caption(
        (
            "Configure team budgets, finalized keepers, "
            "and optional historical sales for this off-platform league."
            if selected_league.source_mode != "sleeper"
            else "Review source-driven rosters and protected players, then "
            "configure budget or optional historical overrides."
        )
    )


    setup_metric_1, setup_metric_2, setup_metric_3, setup_metric_4 = (
        st.columns(4)
    )


    setup_metric_1.metric(
        "Teams",
        len(
            ACTIVE_MANAGERS
        ),
    )

    setup_metric_2.metric(
        "Scoring",
        selected_league
        .scoring_label
        .replace(
            "_",
            " ",
        )
        .title(),
    )

    setup_metric_3.metric(
        "Roster Size",
        selected_league.roster_size,
    )

    setup_metric_4.metric(
        "General Budget",
        f"${selected_league.auction.base_budget}",
    )


    if setup_locked:

        st.info(
            "League setup is locked because live auction "
            "sales already exist. Reset live sales before "
            "changing budgets or protected-player data."
        )

    if (
        not setup_locked
        and selected_league.source_mode != "sleeper"
        and not manual_setup_loaded
    ):
        st.info(
            "👋 New league, nothing entered yet. Open **League Setup Data** "
            "below and drop a spreadsheet -- budgets, keepers, and history "
            "are filled in wherever they can be detected."
        )


    render_league_setup_editor(
        league_profile=(
            ACTIVE_LEAGUE_PROFILE
        ),
        managers=(
            ACTIVE_MANAGERS
        ),
        effective_setup=(
            league_setup_data
        ),
        manual_setup=(
            manual_setup_data
            if manual_setup_loaded
            else None
        ),
        persisted_setup=(
            persisted_setup
        ),
        setup_store=(
            league_setup_store
        ),
        setup_locked=(
            setup_locked
        ),
        workbook_loaded=(
            workbook_loaded
        ),
    )

    with st.expander(
        "⚠️ Data Quality"
    ):

        q1, q2, q3, q4, q5, q6, q7 = (
            st.columns(7)
        )


        q1.metric(
            "Setup Data Notes",
            len(
                league_data.warnings
            ),
        )


        q2.metric(
            "Historical Unmapped",
            historical_market_model
            .unmapped_sales_count,
        )


        q3.metric(
            "Protected Match Issues",
            len(
                pool_result
                .unmatched_keepers
            ),
        )


        q4.metric(
            "Persisted Sales",
            draft_store.sale_count(),
        )


        q5.metric(
            "Context Docs",
            (
                context_store.count()
                if context_store is not None
                else 0
            ),
        )


        q6.metric(
            "Depth Snapshot Docs",
            len(
                depth_chart_documents
            ),
        )


        q7.metric(
            "Depth Changes",
            (
                len(
                    depth_movement_result.documents
                )
                if depth_movement_result
                else 0
            ),
        )


        if league_data.warnings:

            for warning in (
                league_data.warnings
            ):

                st.write(
                    f"• {warning}"
                )


        st.caption(
            "Setup source precedence: "
            "manual > import > workbook > Sleeper > default"
        )


        if setup_source_summary:

            st.write(
                "Normalized setup records: "
                + ", ".join(
                    (
                        f"{source_name}={count}"
                    )

                    for (
                        source_name,
                        count,
                    ) in sorted(
                        setup_source_summary.items()
                    )
                )
            )


        if (
            depth_movement_result
            and
            depth_movement_result.warnings
        ):

            for warning in (
                depth_movement_result.warnings
            ):

                st.write(
                    f"• Depth tracking: {warning}"
                )


        if depth_chart_error:

            st.error(
                f"Depth chart ingestion: "
                f"{depth_chart_error}"
            )


        if depth_movement_error:

            st.error(
                f"Depth movement detection: "
                f"{depth_movement_error}"
            )
