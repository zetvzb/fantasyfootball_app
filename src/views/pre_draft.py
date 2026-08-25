from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.file_drop_rag import process_research_files
from src.strategy_profile import (
    STRATEGY_PRESET_WEIGHTS,
    StrategyMode,
    StrategyProfile,
)
from src.my_guys import MyGuysPreferences


def _render_my_guys(context: AppRuntimeContext) -> None:
    preferences = context.my_guys_preferences
    store = context.my_guys_store
    if preferences is None or store is None:
        return
    key = context.runtime_identity.private_key
    names = sorted(rec.player_name for rec in context.recommendations)
    selected = st.multiselect(
        "My Guys",
        options=names,
        default=[name for name in preferences.player_names if name in names],
        key=key("my_guys_players"),
    )
    premium = st.number_input(
        "My Guys max-bid premium",
        min_value=0,
        max_value=25,
        value=int(preferences.premium),
        key=key("my_guys_premium"),
        help="Optional dollars added to the live cap, never above the legal max. Default is $0.",
    )
    updated = MyGuysPreferences(
        league_key=preferences.league_key,
        user_key=preferences.user_key,
        player_names=tuple(selected),
        premium=int(premium),
    )
    if updated != preferences:
        store.save(updated)
        context.my_guys_preferences = updated


def _render_strategy_profile_selector(
    context: AppRuntimeContext,
) -> None:
    profile = context.strategy_profile
    store = context.strategy_profile_store
    if profile is None or store is None:
        return

    private_key = context.runtime_identity.private_key
    mode_state_key = private_key("strategy_mode")
    current_weight_state_key = private_key("strategy_current_weight")

    if mode_state_key not in st.session_state:
        st.session_state[mode_state_key] = profile.mode
    if current_weight_state_key not in st.session_state:
        st.session_state[current_weight_state_key] = int(
            round(profile.current_weight * 100)
        )

    def apply_mode_preset() -> None:
        selected_mode = StrategyMode(st.session_state[mode_state_key])
        current_weight = STRATEGY_PRESET_WEIGHTS[selected_mode][0]
        st.session_state[current_weight_state_key] = int(
            round(current_weight * 100)
        )

    st.markdown("### Strategy Profile")
    mode_column, weight_column = st.columns(2)

    mode_column.selectbox(
        "Team direction",
        options=list(StrategyMode),
        format_func=lambda mode: mode.label,
        key=mode_state_key,
        on_change=apply_mode_preset,
    )

    weight_column.slider(
        "Current-season emphasis",
        min_value=0,
        max_value=100,
        step=5,
        format="%d%%",
        key=current_weight_state_key,
    )

    selected_mode = StrategyMode(st.session_state[mode_state_key])
    current_weight = (
        float(st.session_state[current_weight_state_key]) / 100.0
    )
    selected_profile = StrategyProfile(
        league_key=profile.league_key,
        user_key=profile.user_key,
        mode=selected_mode,
        current_weight=current_weight,
        future_weight=1.0 - current_weight,
    )

    st.caption(
        "Current season: {0:.0%} • Future value: {1:.0%} • "
        "private to this league and user".format(
            selected_profile.current_weight,
            selected_profile.future_weight,
        )
    )

    if selected_profile != profile:
        try:
            store.save(selected_profile)
            context.strategy_profile = selected_profile
            st.rerun()
        except OSError as error:
            st.warning(
                "Strategy preference could not be saved: {0}".format(error)
            )


def render_pre_draft_view(
    context: AppRuntimeContext,
) -> None:

    ACTIVE_LEAGUE_PROFILE = context.ACTIVE_LEAGUE_PROFILE

    ACTIVE_MANAGERS = context.ACTIVE_MANAGERS

    ACTIVE_MY_MANAGER_ID = context.ACTIVE_MY_MANAGER_ID

    fantasypros_index = context.fantasypros_index

    historical_market_model = context.historical_market_model

    league_setup_data = context.league_setup_data

    live_sales = context.live_sales

    persisted_setup = context.persisted_setup

    player_values = context.player_values

    pool_result = context.pool_result

    projection_index = context.projection_index

    run_draft_simulation = context.run_draft_simulation

    setup_rows = context.setup_rows

    sleeper_players = context.sleeper_players

    starting_total_auction_cash = context.starting_total_auction_cash

    team_setups = context.team_setups

    private_key = context.runtime_identity.private_key
    simulation_result_state_key = private_key(
        "draft_simulation_result"
    )

    st.header(
        "🧭 Pre-Draft"
    )

    st.caption(
        "Confirm the auction starting state before going live: "
        "team cash, protected players, roster openings, and "
        "legal maximum bids."
    )

    readiness = context.pre_draft_readiness
    st.markdown("### Draft Readiness")
    if readiness is None:
        st.warning("Draft readiness could not be evaluated.")
    else:
        if readiness.ready_for_draft:
            st.success(
                "READY FOR DRAFT"
                if not readiness.warning_reasons
                else "READY FOR DRAFT — review warnings"
            )
        else:
            st.error("NOT READY FOR DRAFT")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Area": check.label,
                        "Status": check.status.value,
                        "Summary": check.summary,
                        "Detail": check.detail,
                    }
                    for check in readiness.checks
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    _render_strategy_profile_selector(context)
    _render_my_guys(context)

    st.markdown("### Research File Drop")
    uploaded_research = st.file_uploader(
        "Upload PDF, text, CSV, rankings, or research",
        type=["pdf", "txt", "md", "csv", "tsv", "json"],
        accept_multiple_files=True,
        key=private_key("research_uploads"),
    )
    if uploaded_research and st.button(
        "Process Research",
        key=private_key("process_research"),
    ):
        rag_result = process_research_files(
            uploaded_research,
            player_names=tuple(
                str(player.get("full_name"))
                for player in sleeper_players.values()
                if player.get("full_name")
            ),
        )
        if context.context_store is not None:
            context.context_store.add_documents(rag_result.documents)
        for warning in rag_result.warnings:
            st.warning(warning)
        st.success(
            "Processed {0} chunk(s), linked {1} player signal(s).".format(
                len(rag_result.chunks), len(rag_result.documents)
            )
        )

    ensemble = context.ranking_ensemble
    st.markdown("### Three-Source Ranking Ensemble")
    if ensemble is not None:
        for warning in ensemble.warnings:
            st.info(warning)
        st.caption(
            "Available sources are equal-weighted per player. Rank disagreement "
            "is shown as information and does not reduce player value."
        )
        if ensemble.rankings:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Rank": player.ensemble_rank,
                            "Player": player.player_name,
                            "Pos": player.position,
                            "Average Source Rank": player.average_source_rank,
                            "Sources": player.source_count,
                            "Disagreement": player.rank_disagreement,
                            "Source Ranks": ", ".join(
                                "{0}: {1:g}".format(source, rank)
                                for source, rank in player.source_ranks
                            ),
                        }
                        for player in ensemble.rankings[:50]
                    ]
                ),
                width="stretch",
                hide_index=True,
            )

    tendency_model = context.manager_tendency_model
    st.markdown("### Manager Tendencies")
    st.caption(
        "Time-decayed historical tendencies describe behavior; they do not predict exact bids."
    )
    if tendency_model is not None:
        for warning in tendency_model.warnings:
            st.warning(warning)
        if tendency_model.profiles:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Manager": profile.manager_id,
                            "Confidence": profile.confidence,
                            "Aggression": profile.historical_aggression,
                            "Star Spend Share": profile.stars_spend_share,
                            "Depth Spend Share": profile.depth_spend_share,
                            "Keeper Rate": profile.keeper_rate,
                            "Avg Unused Cash": profile.average_unused_cash,
                            "Position Premiums": dict(profile.position_premiums),
                            "Timing": dict(profile.auction_timing_share),
                        }
                        for profile in tendency_model.profiles
                    ]
                ),
                width="stretch",
                hide_index=True,
            )

    college_promotion_result = (
        context.college_promotion_recommendation_result
    )
    st.markdown("### Promote Now vs Leave on Taxi")
    st.caption(
        "Deterministic recommendations use league eligibility, NFL role, "
        "draft capital, production, future value, age, depth chart, roster "
        "need, promotion economics, taxi cost, and college capacity."
    )
    if college_promotion_result is not None:
        for warning in college_promotion_result.warnings:
            st.info(warning)
    if (
        college_promotion_result is not None
        and college_promotion_result.recommendations
    ):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Decision": recommendation.decision.value,
                        "Player": recommendation.player_name,
                        "Pos": recommendation.position,
                        "Score": recommendation.score,
                        "NFL Role": recommendation.nfl_role_opportunity,
                        "Draft Capital": recommendation.draft_capital,
                        "Current Production": (
                            recommendation.current_projected_production
                        ),
                        "Future Value": recommendation.future_value,
                        "Age": recommendation.age,
                        "Depth Chart": recommendation.depth_chart_status,
                        "Roster Need": recommendation.roster_need,
                        "Taxi Cost": recommendation.taxi_opportunity_cost,
                        "Capacity Pressure": (
                            recommendation.college_capacity_pressure
                        ),
                        "Keeper Surplus": (
                            recommendation.keeper_economics.cumulative_surplus
                            if recommendation.keeper_economics is not None
                            else None
                        ),
                        "Reason Codes": ", ".join(
                            code.value for code in recommendation.reason_codes
                        ),
                        "Explanation": recommendation.explanation,
                    }
                    for recommendation in (
                        college_promotion_result.recommendations
                    )
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    keeper_recommendations = context.keeper_recommendations
    keeper_recommendation_warnings = (
        context.keeper_recommendation_warnings
    )

    st.markdown("### Keeper Recommendations")
    st.caption(
        "Current and future value are normalized 0–100 scores. "
        "Auction value and strategy score are deterministic; no LLM "
        "is used for numeric scoring."
    )

    for warning in keeper_recommendation_warnings:
        st.warning(warning)

    if keeper_recommendations:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Decision": recommendation.decision.value.upper(),
                        "Player": recommendation.player_name,
                        "Pos": recommendation.position,
                        "Current": recommendation.current_value,
                        "Future": recommendation.future_value,
                        "Age Adj.": recommendation.age_adjustment,
                        "Cost": recommendation.cost,
                        "Auction Value": recommendation.auction_value,
                        "Surplus": recommendation.surplus,
                        "Scarcity": recommendation.scarcity,
                        "Roster Fit": recommendation.roster_fit,
                        "Strategy Score": recommendation.strategy_score,
                        "Reason Codes": ", ".join(
                            code.value
                            for code in recommendation.reason_codes
                        ),
                        "Explanation": recommendation.explanation,
                    }
                    for recommendation in keeper_recommendations
                ]
            ),
            width="stretch",
            hide_index=True,
        )

        economics_rows = []
        for recommendation in keeper_recommendations:
            economics = recommendation.economics
            if economics is None:
                continue
            for yearly_projection in economics.years:
                economics_rows.append(
                    {
                        "Player": recommendation.player_name,
                        "Year": yearly_projection.year,
                        "Projected Cost": yearly_projection.projected_cost,
                        "Projected Value": (
                            yearly_projection.projected_player_value
                        ),
                        "Yearly Surplus": yearly_projection.yearly_surplus,
                        "Cumulative Surplus": (
                            yearly_projection.cumulative_surplus
                        ),
                        "Strategy Weight": yearly_projection.strategy_weight,
                        "Strategy-Adjusted Surplus": (
                            yearly_projection.strategy_adjusted_surplus
                        ),
                        "Break-Even Year": (
                            economics.break_even_year
                            if economics.break_even_year is not None
                            else "Beyond horizon"
                        ),
                        "Keeper Runway": economics.keeper_runway_years,
                    }
                )

        if economics_rows:
            st.markdown("#### 2–3 Year Keeper Economics")
            st.caption(
                "Runway counts consecutive positive-surplus seasons. "
                "Strategy-adjusted surplus weights year 1 by the current "
                "strategy weight and divides the future weight across "
                "later seasons."
            )
            st.dataframe(
                pd.DataFrame(economics_rows),
                width="stretch",
                hide_index=True,
            )
    else:
        st.info(
            "No keeper candidates with valid costs are available for "
            "your team yet."
        )

    keeper_trade_candidate_result = (
        context.keeper_trade_candidate_result
    )
    st.markdown("### Top 10 Opponent Keeper Trade Targets")
    st.caption(
        "Candidates are ranked with your active strategy profile and "
        "must fall outside their current owner's strategy-score top six. "
        "This identifies keeper-slot pressure, not trade availability."
    )

    if keeper_trade_candidate_result is not None:
        for warning in keeper_trade_candidate_result.warnings:
            st.warning(warning)

    if (
        keeper_trade_candidate_result is not None
        and keeper_trade_candidate_result.candidates
    ):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Rank": candidate.rank,
                        "Player": candidate.player_name,
                        "Pos": candidate.position,
                        "Current Owner": candidate.owner_name,
                        "Owner Keeper Rank": candidate.owner_keeper_rank,
                        "Strategy Score": candidate.strategy_score,
                        "Cost": candidate.cost,
                        "Auction Value": candidate.auction_value,
                        "Surplus": candidate.surplus,
                        "Current Value": candidate.current_value,
                        "Future Value": candidate.future_value,
                        "Why Trade Candidate": candidate.rationale,
                    }
                    for candidate in keeper_trade_candidate_result.candidates
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "Evaluated {0} scored keeper candidates across {1} opponent "
            "team(s).".format(
                keeper_trade_candidate_result.recommendations_evaluated,
                keeper_trade_candidate_result.opponents_evaluated,
            )
        )
    else:
        st.info(
            "No eligible trade targets are available. Each opponent needs "
            "at least seven valid, priced keeper candidates before a player "
            "can fall outside that team's projected top six."
        )

    keeper_optimization_result = context.keeper_optimization_result
    st.markdown("### Best 4 / 5 / 6 Keeper Comparison")
    st.caption(
        "Opportunity cost is the positive surplus left among excluded "
        "keeper candidates. Cash and reserve use the team's actual setup."
    )

    if keeper_optimization_result is not None:
        for warning in keeper_optimization_result.warnings:
            st.warning(warning)

    if (
        keeper_optimization_result is not None
        and keeper_optimization_result.scenarios
    ):
        recommended_scenario = (
            keeper_optimization_result.recommended_scenario
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Recommended": (
                            "YES"
                            if scenario == recommended_scenario
                            else ""
                        ),
                        "Keeper Count": scenario.keeper_count,
                        "Keepers": ", ".join(scenario.keeper_names),
                        "Keeper Spend": scenario.keeper_spend,
                        "Auction Cash": scenario.remaining_cash,
                        "Open Spots": scenario.remaining_roster_spots,
                        "Reserve": scenario.minimum_reserve,
                        "Discretionary": scenario.discretionary_cash,
                        "Current Value": scenario.current_value,
                        "Future Value": scenario.future_value,
                        "Surplus": scenario.surplus,
                        "Opportunity Cost": scenario.opportunity_cost,
                        "Roster Fit": scenario.roster_fit,
                        "Objective": scenario.objective_score,
                    }
                    for scenario in keeper_optimization_result.scenarios
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        st.success(recommended_scenario.explanation)
        st.caption(
            "Evaluated {0} candidate combinations exhaustively and "
            "discarded any that violated cash or reserve rules."
            .format(keeper_optimization_result.combinations_evaluated)
        )
    else:
        st.info(
            "At least four valid keeper candidates are required before "
            "the 4/5/6 comparison is available."
        )

    if setup_rows:

        st.markdown(
            "### Auction Start State"
        )

        st.dataframe(
            pd.DataFrame(
                setup_rows
            ),
            width="stretch",
            hide_index=True,
        )


    setup_count = len(
        team_setups
    )

    explicit_keeper_count = len(
        [
            keeper

            for keeper
            in league_setup_data.keepers

            if keeper.status
            == "finalized"
        ]
    )

    college_count = len(
        league_setup_data.college_players
    )

    history_count = len(
        league_setup_data.historical_sales
    )


    r1, r2, r3, r4 = (
        st.columns(4)
    )


    r1.metric(
        "Teams Ready",
        f"{setup_count}/{len(ACTIVE_MANAGERS)}",
    )

    r2.metric(
        "Finalized Keepers",
        explicit_keeper_count,
    )

    r3.metric(
        "College / Devy Rights",
        college_count,
    )

    r4.metric(
        "Historical Sales",
        history_count,
    )


    if (
        ACTIVE_LEAGUE_PROFILE.keepers.enabled
        and
        explicit_keeper_count == 0
        and
        not any(
            (
                persisted_setup
                .get(
                    manager_id,
                    {},
                )
                .get(
                    "keepers",
                    [],
                )
            )

            for manager_id
            in ACTIVE_MANAGERS
        )
    ):

        st.info(
            "No finalized keepers are currently entered. "
            "That is valid if this league has no keepers or if "
            "keeper decisions are not available yet."
        )


    if history_count == 0:

        st.caption(
            "No historical auction data is loaded. "
            "The recommendation engine will continue without "
            "historical-market adjustments."
        )

    st.divider()

    st.header(
        "🧪 Draft Simulation / Test Mode"
    )


    sim1, sim2, sim3, sim4 = (
        st.columns(4)
    )


    with sim1:

        simulation_sale_count = (
            st.number_input(
                "Fake Sales",
                min_value=1,
                max_value=50,
                value=5,
                step=1,
                key=(
                    private_key("simulation_sale_count")
                ),
            )
        )


    with sim2:

        simulation_seed = (
            st.number_input(
                "Simulation Seed",
                min_value=1,
                max_value=999999,
                value=42,
                step=1,
                key=(
                    private_key("simulation_seed")
                ),
            )
        )


    with sim3:

        simulation_checkpoint = (
            st.number_input(
                "Full Checkpoint Every",
                min_value=1,
                max_value=10,
                value=5,
                step=1,
                key=(
                    private_key("simulation_checkpoint")
                ),
            )
        )


    with sim4:

        simulation_from_current = (
            st.checkbox(
                "Start from current ledger",
                value=False,
                key=private_key("simulation_from_current"),
            )
        )


    st.info(
        "Simulation sales are in-memory only. "
        "draft_state.db is not modified."
    )


    run_simulation = (
        st.button(
            "🧪 RUN DRAFT SIMULATION",
            type="primary",
            width="stretch",
            key=private_key("run_draft_simulation"),
        )
    )


    if run_simulation:

        initial_simulation_sales = (
            live_sales
            if simulation_from_current
            else []
        )


        simulation_progress = (
            st.progress(
                0.0
            )
        )


        simulation_status = (
            st.empty()
        )


        simulation_detail = (
            st.empty()
        )


        def update_simulation_progress(
            completed,
            total,
            message,
        ):

            progress_value = (
                completed
                /
                total
                if total
                else 0.0
            )


            simulation_progress.progress(
                min(
                    1.0,
                    max(
                        0.0,
                        progress_value,
                    ),
                )
            )


            simulation_status.markdown(
                f"**Simulation progress: "
                f"{completed} / {total} sales**"
            )


            simulation_detail.caption(
                message
            )


        try:

            simulation_result = (
                run_draft_simulation(
                    number_of_sales=(
                        int(
                            simulation_sale_count
                        )
                    ),
                    seed=(
                        int(
                            simulation_seed
                        )
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
                    player_values=(
                        player_values
                    ),
                    projection_index=(
                        projection_index
                    ),
                    fantasypros_index=(
                        fantasypros_index
                    ),
                    historical_market_model=(
                        historical_market_model
                    ),
                    starting_total_auction_cash=(
                        starting_total_auction_cash
                    ),
                    my_manager_id=(
                        ACTIVE_MY_MANAGER_ID
                    ),
                    initial_sales=(
                        initial_simulation_sales
                    ),
                    checkpoint_every=(
                        int(
                            simulation_checkpoint
                        )
                    ),
                    progress_callback=(
                        update_simulation_progress
                    ),
                )
            )


            simulation_progress.progress(
                1.0
            )


            simulation_status.success(
                f"Simulation complete — "
                f"{simulation_result.completed_sales} "
                f"sales processed."
            )


            st.session_state[
                simulation_result_state_key
            ] = simulation_result


        except Exception as error:

            simulation_status.error(
                "Simulation stopped."
            )


            st.error(
                f"Simulation failed: {error}"
            )


    simulation_result = (
        st.session_state.get(
            simulation_result_state_key
        )
    )


    if simulation_result:

        st.markdown(
            "## Test Results"
        )


        t1, t2, t3, t4, t5 = (
            st.columns(5)
        )


        t1.metric(
            "Requested",
            simulation_result.requested_sales,
        )


        t2.metric(
            "Completed",
            simulation_result.completed_sales,
        )


        t3.metric(
            "Violations",
            len(
                simulation_result.violations
            ),
        )


        t4.metric(
            "Room vs Model",
            (
                f"{simulation_result.final_room_spend_index:.2f}x"
                if (
                    simulation_result
                    .final_room_spend_index
                    is not None
                )
                else "-"
            ),
        )


        t5.metric(
            "Optimizer",
            (
                "FEASIBLE"
                if simulation_result
                .final_optimizer_feasible
                else "FAILED"
            ),
        )


        if not simulation_result.violations:

            st.success(
                "✅ TEST PASSED"
            )

        else:

            st.error(
                f"❌ "
                f"{len(simulation_result.violations)} "
                f"violation(s) detected."
            )


        if simulation_result.stopped_reason:

            st.warning(
                simulation_result.stopped_reason
            )


        simulation_rows = []


        for step in (
            simulation_result.steps
        ):

            manager_name = (
                ACTIVE_MANAGERS[
                    step.manager_id
                ].sleeper_team_name

                if step.manager_id
                in ACTIVE_MANAGERS

                else step.manager_id
            )


            simulation_rows.append(
                {
                    "#": step.sale_number,
                    "Player": step.player_name,
                    "Pos": step.position,
                    "Winner": manager_name,
                    "Price": step.price,
                    "Model $": step.expected_market_value,
                    "Player Ceiling": step.player_ceiling,
                    "Roster Ceiling": (
                        step.roster_aware_ceiling
                    ),
                    "Winner Max Before": (
                        step.winner_pre_sale_max_bid
                    ),
                    "Remaining Cash": (
                        step.remaining_cash
                    ),
                    "Open Spots": (
                        step.remaining_open_spots
                    ),
                    "Room vs Model": (
                        step.room_spend_index
                    ),
                    "Live Signal": (
                        step.live_room_multiplier
                    ),
                    "Optimizer": (
                        "OK"
                        if step.optimizer_feasible
                        else "FAILED"
                    ),
                    "Next Nomination": (
                        step.top_nomination
                        or "-"
                    ),
                    "Violations": (
                        "; ".join(
                            step.violations
                        )
                    ),
                }
            )


        if simulation_rows:

            st.dataframe(
                pd.DataFrame(
                    simulation_rows
                ),
                width="stretch",
                hide_index=True,
            )


        st.markdown(
            "### Final Simulated Team State"
        )


        final_team_rows = []


        for (
            manager_id,
            setup,
        ) in (
            simulation_result
            .final_team_setups
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


            final_team_rows.append(
                {
                    "Team": team_name,
                    "Cash": setup.auction_cash,
                    "Open Spots": setup.open_roster_spots,
                    "Legal Max": setup.max_bid,
                    "Auction Buys": setup.purchased_count,
                    "My Team": (
                        "⭐"
                        if manager_id
                        ==
                        ACTIVE_MY_MANAGER_ID
                        else ""
                    ),
                }
            )


        if final_team_rows:

            st.dataframe(
                pd.DataFrame(
                    final_team_rows
                ).sort_values(
                    by="Cash",
                    ascending=False,
                ),
                width="stretch",
                hide_index=True,
            )


        st.markdown(
            "### Learned Position Market"
        )


        position_signal_rows = []


        for position in [
            "QB",
            "RB",
            "WR",
            "TE",
            "K",
            "DEF",
        ]:

            multiplier = (
                simulation_result
                .final_position_signals
                .get(
                    position
                )
            )


            if multiplier is not None:

                position_signal_rows.append(
                    {
                        "Position": position,
                        "Learned Multiplier": multiplier,
                    }
                )


        if position_signal_rows:

            st.dataframe(
                pd.DataFrame(
                    position_signal_rows
                ),
                width="stretch",
                hide_index=True,
            )


        st.markdown(
            "### Learned Manager Behavior"
        )


        manager_signal_rows = []


        for (
            manager_id,
            multiplier,
        ) in (
            simulation_result
            .final_manager_signals
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


            manager_signal_rows.append(
                {
                    "Team": team_name,
                    "2026 Aggression": multiplier,
                }
            )


        if manager_signal_rows:

            st.dataframe(
                pd.DataFrame(
                    manager_signal_rows
                ).sort_values(
                    by="2026 Aggression",
                    ascending=False,
                ),
                width="stretch",
                hide_index=True,
            )


        if simulation_result.violations:

            with st.expander(
                "❌ Simulation Violations",
                expanded=True,
            ):

                for violation in (
                    simulation_result
                    .violations
                ):

                    st.error(
                        violation
                    )


        if st.button(
            "Clear Simulation Results",
            key=private_key("clear_simulation_results"),
        ):

            del st.session_state[
                simulation_result_state_key
            ]

            st.rerun()
