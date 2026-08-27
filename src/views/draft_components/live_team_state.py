from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext


def render_live_team_state(
    context: AppRuntimeContext,
) -> None:

    ACTIVE_MANAGERS = (
        context.ACTIVE_MANAGERS
    )

    ACTIVE_MY_MANAGER_ID = (
        context.ACTIVE_MY_MANAGER_ID
    )

    live_calibration = (
        context.live_calibration
    )

    live_team_setups = (
        context.live_team_setups
    )

    team_need_profiles = (
        context.team_need_profiles
    )

    st.divider()

    st.subheader(
        "💰 Live Team State"
    )


    team_rows = []


    for (
        manager_id,
        setup,
    ) in live_team_setups.items():

        need = (
            team_need_profiles.get(
                manager_id
            )
        )


        live_manager = (
            live_calibration
            .manager_profiles
            .get(
                manager_id
            )
        )


        team_rows.append(
            {
                "Team": (
                    ACTIVE_MANAGERS[
                        manager_id
                    ].sleeper_team_name
                ),
                "Entering Cash": setup.entering_cash,
                "Keeper $": setup.keeper_commitments,
                "Live Cash": setup.live_cash,
                "Reserve": setup.required_reserve,
                "Discretionary": setup.discretionary_cash,
                "Open Spots": setup.open_roster_spots,
                "Legal Max": setup.max_bid,
                "Budget Source": setup.budget_source,
                "Bought": setup.purchased_count,
                "2026 Aggression": (
                    live_manager.multiplier
                    if live_manager
                    else 1.0
                ),
                "QB Need": (
                    need.need_scores.get(
                        "QB",
                        0.0,
                    ) * 100
                    if need
                    else 0
                ),
                "RB Need": (
                    need.need_scores.get(
                        "RB",
                        0.0,
                    ) * 100
                    if need
                    else 0
                ),
                "WR Need": (
                    need.need_scores.get(
                        "WR",
                        0.0,
                    ) * 100
                    if need
                    else 0
                ),
                "TE Need": (
                    need.need_scores.get(
                        "TE",
                        0.0,
                    ) * 100
                    if need
                    else 0
                ),
                "K Need": (
                    need.need_scores.get(
                        "K",
                        0.0,
                    ) * 100
                    if need
                    else 0
                ),
                "DEF Need": (
                    need.need_scores.get(
                        "DEF",
                        0.0,
                    ) * 100
                    if need
                    else 0
                ),
                "My Team": (
                    "⭐"
                    if manager_id
                    ==
                    ACTIVE_MY_MANAGER_ID
                    else ""
                ),
            }
        )


    if team_rows:

        st.dataframe(
            pd.DataFrame(
                team_rows
            ).sort_values(
                by="Live Cash",
                ascending=False,
            ),
            width="stretch",
            hide_index=True,
        )
