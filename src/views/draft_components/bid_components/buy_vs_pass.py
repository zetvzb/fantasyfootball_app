from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext

from .state import BidPlayerState


def render_buy_vs_pass(
    context: AppRuntimeContext,
    state: BidPlayerState,
) -> None:

    context_adjusted_ceiling = (
        state.context_adjusted_ceiling
    )

    nominated_key = (
        state.nominated_key
    )

    recommendation = (
        state.recommendation
    )

    compare_buy_vs_pass = (
        context.compare_buy_vs_pass
    )

    my_live_setup = (
        context.my_live_setup
    )

    my_need_profile = (
        context.my_need_profile
    )

    normalize_player_name = (
        context.normalize_player_name
    )

    optimization_candidates = (
        context.optimization_candidates
    )

    # =================================================
    # BUY VS PASS
    # =================================================

    st.markdown(
        "## 🔮 What If I Win Him?"
    )

    if state.pass_alternatives:
        st.markdown("### Comparable Pass Alternatives")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Player": alternative.player_name,
                        "Pos": alternative.position,
                        "Expected Range": "${0}-${1}".format(
                            alternative.expected_price_low,
                            alternative.expected_price_high,
                        ),
                        "VORP": alternative.vorp,
                        "Comparable": alternative.comparability,
                        "Availability": "{0} ({1:.0%})".format(
                            alternative.availability_label,
                            alternative.availability_probability,
                        ),
                        "Why": alternative.rationale,
                    }
                    for alternative in state.pass_alternatives
                ]
            ),
            width="stretch",
            hide_index=True,
        )


    scenario_max_price = max(
        1,
        int(
            recommendation.legal_max_bid
        ),
    )


    scenario_default_price = min(
        scenario_max_price,
        max(
            1,
            int(
                round(
                    recommendation
                    .expected_market_value
                )
            ),
        ),
    )


    hypothetical_price = (
        st.number_input(
            "Hypothetical Winning Price",
            min_value=1,
            max_value=(
                scenario_max_price
            ),
            value=(
                scenario_default_price
            ),
            step=1,
            key=(
                context.runtime_identity.private_key(
                    f"scenario_price_{nominated_key}"
                )
            ),
        )
    )


    scenario = None


    if (
        my_live_setup
        and
        my_need_profile
        and
        optimization_candidates
    ):

        scenario = (
            compare_buy_vs_pass(
                player_name=(
                    recommendation.player_name
                ),
                proposed_price=(
                    int(
                        hypothetical_price
                    )
                ),
                my_team_setup=(
                    my_live_setup
                ),
                my_need_profile=(
                    my_need_profile
                ),
                candidates=(
                    optimization_candidates
                ),
                existing_do_not_exceed=(
                    context_adjusted_ceiling
                ),
            )
        )


    if scenario:

        sc1, sc2, sc3, sc4 = (
            st.columns(4)
        )


        sc1.metric(
            "Winning Price",
            f"${hypothetical_price}",
        )


        sc2.metric(
            "Roster Ceiling",
            f"${scenario.recommended_ceiling}",
        )


        sc3.metric(
            "Buy vs Pass Utility",
            f"{scenario.utility_delta:+.1f}",
        )


        sc4.metric(
            "Cash After Buy",
            (
                f"${scenario.buy_plan.cash_after_plan}"
                if scenario.buy_plan.feasible
                else "-"
            ),
        )


        if not scenario.buy_plan.feasible:

            st.error(
                "❌ Buying at this price prevents "
                "a legal complete roster."
            )


        elif (
            hypothetical_price
            >
            scenario.recommended_ceiling
        ):

            st.error(
                f"❌ PASS AT ${hypothetical_price}"
            )


        elif (
            scenario.utility_delta
            >= 0.25
        ):

            st.success(
                f"✅ BUY AT ${hypothetical_price}"
            )


        elif (
            scenario.utility_delta
            >= -0.25
        ):

            st.info(
                "⚖️ CLOSE CALL"
            )


        else:

            st.warning(
                f"⚠️ PASS IS BETTER AT "
                f"${hypothetical_price}"
            )


        buy_column, pass_column = (
            st.columns(2)
        )


        with buy_column:

            st.markdown(
                "### ✅ BUY PLAN"
            )


            if scenario.buy_plan.feasible:

                buy_rows = [
                    {
                        "Slot": entry.slot,
                        "Player": entry.player_name,
                        "Pos": entry.position,
                        "Plan $": entry.planned_cost,
                        "Market $": entry.expected_market_value,
                        "VORP": entry.vorp,
                    }

                    for entry
                    in scenario.buy_plan.entries
                ]


                st.dataframe(
                    pd.DataFrame(
                        buy_rows
                    ),
                    width="stretch",
                    hide_index=True,
                )


        with pass_column:

            st.markdown(
                "### ⏭️ PASS PLAN"
            )


            if scenario.pass_plan.feasible:

                pass_rows = [
                    {
                        "Slot": entry.slot,
                        "Player": entry.player_name,
                        "Pos": entry.position,
                        "Plan $": entry.planned_cost,
                        "Market $": entry.expected_market_value,
                        "VORP": entry.vorp,
                    }

                    for entry
                    in scenario.pass_plan.entries
                ]


                st.dataframe(
                    pd.DataFrame(
                        pass_rows
                    ),
                    width="stretch",
                    hide_index=True,
                )


        if (
            scenario.buy_plan.feasible
            and
            scenario.pass_plan.feasible
        ):

            buy_names = {
                normalize_player_name(
                    entry.player_name
                )

                for entry
                in scenario.buy_plan.entries

                if not entry.is_filler
            }


            pass_only_entries = [
                entry

                for entry
                in scenario.pass_plan.entries

                if (
                    not entry.is_filler
                    and
                    normalize_player_name(
                        entry.player_name
                    )
                    not in buy_names
                )
            ]


            if pass_only_entries:

                st.markdown(
                    "### 💸 What Buying Him Costs You"
                )


                lost_players = sorted(
                    pass_only_entries,
                    key=lambda entry: (
                        entry.utility
                    ),
                    reverse=True,
                )


                for entry in (
                    lost_players[
                        :5
                    ]
                ):

                    st.write(
                        f"• **{entry.player_name}** "
                        f"({entry.position}) — "
                        f"planned at "
                        f"${entry.planned_cost}"
                    )
