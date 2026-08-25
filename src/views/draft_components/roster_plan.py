from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.ideal_roster_blueprint import build_ideal_roster_blueprint


def render_roster_plan(
    context: AppRuntimeContext,
) -> None:

    optimal_roster_plan = (
        context.optimal_roster_plan
    )

    # =========================================================
    # OPTIMAL REMAINING ROSTER
    # =========================================================

    st.divider()

    st.header(
        "🧩 Optimal Remaining Roster"
    )

    st.caption(
        "Whole-roster planning based on your remaining "
        "cash, starter gaps, FLEX needs, expected prices, "
        "and $1 endgame requirements."
    )


    if (
        optimal_roster_plan
        and
        optimal_roster_plan.feasible
    ):
        blueprint = build_ideal_roster_blueprint(
            optimal_roster_plan,
            context.optimization_candidates,
        )

        r1, r2, r3, r4, r5 = (
            st.columns(5)
        )


        r1.metric(
            "Your Cash",
            f"${optimal_roster_plan.starting_cash}",
        )


        r2.metric(
            "Open Spots",
            optimal_roster_plan.starting_open_spots,
        )


        r3.metric(
            "Planned Spend",
            f"${optimal_roster_plan.planned_spend}",
        )


        r4.metric(
            "Cash Left",
            f"${optimal_roster_plan.cash_after_plan}",
        )


        r5.metric(
            "Plan Utility",
            f"{optimal_roster_plan.total_utility:.1f}",
        )


        roster_rows = []


        for entry in (
            optimal_roster_plan.entries
        ):

            roster_rows.append(
                {
                    "Slot": entry.slot,
                    "Player": entry.player_name,
                    "Pos": entry.position,
                    "Plan $": entry.planned_cost,
                    "Market $": entry.expected_market_value,
                    "Player Ceiling": entry.do_not_exceed,
                    "Baseline": entry.baseline_value,
                    "VORP": entry.vorp,
                    "Fallback": entry.is_filler,
                    "Alternatives": ", ".join(
                        next(
                            (
                                slot.alternatives
                                for slot in blueprint.slots
                                if slot.slot == entry.slot
                                and slot.preferred_player == entry.player_name
                            ),
                            (),
                        )
                    ),
                }
            )


        st.dataframe(
            pd.DataFrame(
                roster_rows
            ),
            width="stretch",
            hide_index=True,
        )


    else:

        st.warning(
            "No feasible complete roster plan was found."
        )

