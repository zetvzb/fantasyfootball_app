from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext


def render_live_economy(
    context: AppRuntimeContext,
) -> None:

    ACTIVE_MANAGERS = (
        context.ACTIVE_MANAGERS
    )

    draft_store = (
        context.draft_store
    )

    live_calibration = (
        context.live_calibration
    )

    live_discretionary = (
        context.live_discretionary
    )

    live_open_spots = (
        context.live_open_spots
    )

    live_sales = (
        context.live_sales
    )

    live_total_cash = (
        context.live_total_cash
    )

    room_spend_index = (
        context.room_spend_index
    )

    # =========================================================
    # LIVE AUCTION HEADER
    # =========================================================

    st.divider()

    st.header(
        "🚨 LIVE AUCTION"
    )


    m1, m2, m3, m4, m5 = (
        st.columns(5)
    )


    m1.metric(
        "Players Sold",
        len(
            live_sales
        ),
    )


    m2.metric(
        "Remaining Cash",
        f"${live_total_cash:,}",
    )


    m3.metric(
        "Open Spots",
        live_open_spots,
    )


    m4.metric(
        "Discretionary $",
        f"${live_discretionary:,}",
    )


    m5.metric(
        "Room vs Model",
        (
            f"{room_spend_index:.2f}x"
            if room_spend_index
            is not None
            else "-"
        ),
    )


    if room_spend_index is not None:

        if room_spend_index >= 1.08:

            st.warning(
                "The room has paid above modeled market. "
                "Those overpayments have removed cash "
                "from the remaining auction."
            )


        elif room_spend_index <= 0.92:

            st.info(
                "Players have sold below modeled market. "
                "Extra cash remains in the room and may "
                "produce later inflation."
            )


    # =========================================================
    # LIVE LEARNING
    # =========================================================

    with st.expander(
        "🧠 2026 Live Learning",
        expanded=(
            len(
                live_sales
            )
            >= 2
        ),
    ):

        overall = (
            live_calibration.overall
        )


        l1, l2, l3 = (
            st.columns(3)
        )


        l1.metric(
            "Learned Sales",
            overall.sample_size,
        )


        l2.metric(
            "Actual / Model",
            (
                f"{overall.raw_ratio:.2f}x"
                if overall.sample_size
                else "-"
            ),
        )


        l3.metric(
            "Shrunk Room Signal",
            (
                f"{overall.multiplier:.3f}x"
                if overall.sample_size
                else "1.000x"
            ),
        )


        st.caption(
            "Early samples are deliberately shrunk. "
            "Position and tier adjustments redistribute "
            "remaining auction dollars rather than "
            "creating new money."
        )


        st.markdown(
            "#### Position Market"
        )


        position_rows = []


        for position in [
            "QB",
            "RB",
            "WR",
            "TE",
            "K",
            "DEF",
        ]:

            signal = (
                live_calibration
                .position_signals
                .get(
                    position
                )
            )


            if signal:

                position_rows.append(
                    {
                        "Position": position,
                        "Sales": signal.sample_size,
                        "Actual $": signal.actual_spend,
                        "Model $": signal.modeled_spend,
                        "Raw vs Model": signal.raw_ratio,
                        "Learned Signal": signal.multiplier,
                    }
                )


        if position_rows:

            st.dataframe(
                pd.DataFrame(
                    position_rows
                ),
                width="stretch",
                hide_index=True,
            )

        else:

            st.caption(
                "No position-level learning yet."
            )


        st.markdown(
            "#### Price Tier Market"
        )


        tier_rows = []


        for tier in [
            "ELITE",
            "PREMIUM",
            "CORE",
            "VALUE",
        ]:

            signal = (
                live_calibration
                .tier_signals
                .get(
                    tier
                )
            )


            if signal:

                tier_rows.append(
                    {
                        "Tier": tier,
                        "Sales": signal.sample_size,
                        "Actual $": signal.actual_spend,
                        "Model $": signal.modeled_spend,
                        "Raw vs Model": signal.raw_ratio,
                        "Learned Signal": signal.multiplier,
                    }
                )


        if tier_rows:

            st.dataframe(
                pd.DataFrame(
                    tier_rows
                ),
                width="stretch",
                hide_index=True,
            )


        st.markdown(
            "#### Manager Behavior"
        )


        manager_learning_rows = []


        for (
            manager_id,
            profile,
        ) in (
            live_calibration
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


            manager_learning_rows.append(
                {
                    "Team": team_name,
                    "Buys": profile.purchases,
                    "Spent": profile.actual_spend,
                    "Model $": profile.modeled_spend,
                    "Raw vs Model": profile.raw_ratio,
                    "Learned Aggression": (
                        profile.multiplier
                    ),
                }
            )


        if manager_learning_rows:

            st.dataframe(
                pd.DataFrame(
                    manager_learning_rows
                ).sort_values(
                    by="Learned Aggression",
                    ascending=False,
                ),
                width="stretch",
                hide_index=True,
            )


    # =========================================================
    # UNDO / RESET
    # =========================================================

    control1, control2, control3 = (
        st.columns(
            [
                1,
                1,
                3,
            ]
        )
    )


    with control1:

        if st.button(
            "↩️ Undo Last Sale",
            disabled=(
                len(
                    live_sales
                )
                == 0
            ),
            width="stretch",
            key=context.runtime_identity.private_key(
                "undo_last_sale"
            ),
        ):

            draft_store.undo_last_sale()

            st.rerun()


    with control2:

        if st.button(
            "🗑️ Reset Live Sales",
            disabled=(
                len(
                    live_sales
                )
                == 0
            ),
            width="stretch",
            key=context.runtime_identity.private_key(
                "reset_live_sales"
            ),
        ):

            draft_store.reset_sales()

            st.rerun()

