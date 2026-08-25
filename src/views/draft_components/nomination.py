from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext


def render_nomination_strategy(
    context: AppRuntimeContext,
) -> None:

    ACTIVE_MANAGERS = (
        context.ACTIVE_MANAGERS
    )

    nomination_recommendations = (
        context.nomination_recommendations
    )

    # =========================================================
    # NOMINATION COPILOT
    # =========================================================

    st.divider()

    st.header(
        "🎯 WHO SHOULD I NOMINATE?"
    )

    st.caption(
        "Find players who can drain opponent budgets, "
        "attack positional desperation, or create a "
        "buy window for one of your own targets."
    )


    if nomination_recommendations:

        top_nomination = (
            nomination_recommendations[
                0
            ]
        )


        top1, top2, top3 = (
            st.columns(
                [
                    2,
                    1,
                    1,
                ]
            )
        )


        with top1:

            st.markdown(
                f"## {top_nomination.player_name}"
            )

            st.markdown(
                f"### {top_nomination.action}"
            )

            target = top_nomination.target_manager_id
            if target and target in ACTIVE_MANAGERS:
                target = ACTIVE_MANAGERS[target].sleeper_team_name
            st.caption(
                f"Target: {target or 'the room'} • {top_nomination.reason}"
            )

            if st.button(
                "🎯 USE TOP NOMINATION",
                key=context.runtime_identity.private_key("use_top_nomination"),
            ):
                st.session_state[
                    context.runtime_identity.private_key("nominated_player")
                ] = top_nomination.player_name
                st.rerun()


        with top2:

            st.metric(
                "Nomination Score",
                f"{top_nomination.nomination_score:.0f}/100",
            )


        with top3:

            st.metric(
                "Expected Market",
                f"${top_nomination.expected_market_value:.0f}",
            )


        nomination_rows = []


        for nomination in (
            nomination_recommendations[
                :20
            ]
        ):

            if (
                nomination.top_opponent_id
                and
                nomination.top_opponent_id
                in ACTIVE_MANAGERS
            ):

                opponent_name = (
                    ACTIVE_MANAGERS[
                        nomination
                        .top_opponent_id
                    ].sleeper_team_name
                )

            else:

                opponent_name = (
                    nomination
                    .top_opponent_id
                    or "-"
                )


            nomination_rows.append(
                {
                    "Player": nomination.player_name,
                    "Pos": nomination.position,
                    "Score": nomination.nomination_score,
                    "Action": nomination.action,
                    "Target": (
                        ACTIVE_MANAGERS[nomination.target_manager_id].sleeper_team_name
                        if nomination.target_manager_id in ACTIVE_MANAGERS
                        else nomination.target_manager_id or "Room"
                    ),
                    "Reason": nomination.reason,
                    "Market $": nomination.expected_market_value,
                    "Player Ceiling": nomination.do_not_exceed,
                    "My Interest": (
                        nomination.my_interest_score
                        *
                        100
                    ),
                    "Opponent Need": (
                        nomination.opponent_need_score
                        *
                        100
                    ),
                    "Cash Drain": (
                        nomination.cash_drain_score
                        *
                        100
                    ),
                    "Competition": (
                        nomination.competition_score
                        *
                        100
                    ),
                    "Top Opponent": opponent_name,
                    "Live Heat": nomination.live_market_heat,
                }
            )


        st.dataframe(
            pd.DataFrame(
                nomination_rows
            ),
            width="stretch",
            hide_index=True,
        )


        (
            drain_tab,
            target_tab,
            window_tab,
        ) = (
            st.tabs(
                [
                    "🔥 Drain the Room",
                    "🎯 My Targets",
                    "🪟 Buy Windows",
                ]
            )
        )


        with drain_tab:

            drain_candidates = [
                nomination

                for nomination
                in nomination_recommendations

                if (
                    nomination
                    .my_interest_score
                    <= 0.45
                )
            ]


            if drain_candidates:

                for candidate in (
                    drain_candidates[
                        :8
                    ]
                ):

                    st.markdown(
                        f"**{candidate.player_name} "
                        f"({candidate.position})** — "
                        f"{candidate.action} — "
                        f"{candidate.nomination_score:.0f}/100"
                    )


                    if candidate.reasons:

                        st.caption(
                            " • ".join(
                                candidate.reasons
                            )
                        )

            else:

                st.info(
                    "No strong cash-drain nominations "
                    "are currently available."
                )


        with target_tab:

            my_targets = sorted(
                [
                    nomination

                    for nomination
                    in nomination_recommendations

                    if (
                        nomination
                        .my_interest_score
                        >= 0.65
                    )
                ],
                key=lambda value: (
                    value.my_interest_score
                ),
                reverse=True,
            )


            if my_targets:

                for candidate in (
                    my_targets[
                        :10
                    ]
                ):

                    st.markdown(
                        f"**{candidate.player_name} "
                        f"({candidate.position})**"
                    )

                    st.caption(
                        f"My interest "
                        f"{candidate.my_interest_score:.0%} • "
                        f"Market "
                        f"${candidate.expected_market_value:.0f} • "
                        f"Ceiling "
                        f"${candidate.do_not_exceed}"
                    )

            else:

                st.info(
                    "No high-priority personal targets "
                    "are currently identified."
                )


        with window_tab:

            buy_windows = [
                nomination

                for nomination
                in nomination_recommendations

                if (
                    nomination.action
                    ==
                    "ACQUIRE TARGET"
                )
            ]


            if buy_windows:

                for candidate in buy_windows:

                    st.success(
                        f"{candidate.player_name} — "
                        f"market heat "
                        f"{candidate.live_market_heat:.3f}x — "
                        f"expected "
                        f"${candidate.expected_market_value:.0f}"
                    )

            else:

                st.info(
                    "No clear buy windows right now."
                )
