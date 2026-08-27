from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.auction_pool import normalize_player_name
from src.file_drop_rag import process_research_files
from src.keeper_trade_candidates import evaluate_keeper_trade
from src.strategy_profile import (
    STRATEGY_PRESET_WEIGHTS,
    StrategyMode,
    StrategyProfile,
)
from src.my_guys import MyGuysPreferences
from src.position_budgets import optimize_position_budgets
from src.pre_draft_action_plan import build_pre_draft_action_plan
from src.planning_preferences import (
    PlanningPreferences,
    SavedBudgetBand,
    SavedPriorityTier,
)
from src.explanation_service import (
    DecisionExplanationInput,
    DecisionExplanationService,
)


def _render_decision_narrative(context: AppRuntimeContext) -> None:
    recommendations = tuple(context.keeper_recommendations)
    if not recommendations:
        return
    private_key = context.runtime_identity.private_key
    by_name = {value.player_name: value for value in recommendations}
    selected_name = st.selectbox(
        "Explain keeper decision",
        options=tuple(by_name),
        key=private_key("keeper_narrative_player"),
    )
    recommendation = by_name[selected_name]
    inputs = DecisionExplanationInput(
        subject=recommendation.player_name,
        decision=recommendation.decision.value.upper(),
        numeric_facts={
            "strategy_score": float(recommendation.strategy_score),
            "current_value": float(recommendation.current_value),
            "future_value": float(recommendation.future_value),
            "keeper_cost": float(recommendation.cost),
            "auction_value": float(recommendation.auction_value),
            "surplus": float(recommendation.surplus),
            "scarcity": float(recommendation.scarcity),
            "roster_fit": float(recommendation.roster_fit),
        },
        reason_codes=tuple(
            code.value for code in recommendation.reason_codes
        ),
        deterministic_explanation=recommendation.explanation,
    )
    service = DecisionExplanationService()
    narrative_key = private_key(
        "keeper_narrative::{0}".format(
            normalize_player_name(recommendation.player_name)
        )
    )
    narrative = st.session_state.get(narrative_key)
    if narrative is None:
        narrative = service.explain(inputs)
    if st.button(
        "Generate optional AI explanation",
        key=private_key("generate_keeper_narrative"),
        help=(
            "Sends only the displayed decision facts and reason codes. "
            "The model cannot change the numeric recommendation."
        ),
    ):
        narrative = service.explain(inputs, use_ai=True)
        st.session_state[narrative_key] = narrative
    st.info(narrative.text.replace("$", "USD "))
    if narrative.warning:
        st.caption(narrative.warning)
    elif narrative.source == "openai":
        st.caption(
            "AI-polished narrative via {0}; deterministic score unchanged."
            .format(narrative.model)
        )
    else:
        st.caption(
            "Deterministic narrative. Set OPENAI_API_KEY for optional polish."
        )


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
        context.private_state_access.save_my_guys(store, updated)
        context.my_guys_preferences = updated


def _render_action_plan(context: AppRuntimeContext) -> None:
    setup = context.team_setups.get(context.ACTIVE_MY_MANAGER_ID)
    if setup is None or context.strategy_profile is None:
        return
    budget = optimize_position_budgets(
        live_cash=int(setup.auction_cash),
        open_spots_by_position={"FLEXIBLE ROSTER": int(setup.open_roster_spots)},
        need_scores={"FLEXIBLE ROSTER": 1.0},
        minimum_bid=int(setup.minimum_auction_bid),
    )
    ranked = sorted(
        context.keeper_recommendations,
        key=lambda item: float(getattr(item, "strategy_score", 0.0)),
        reverse=True,
    )
    plan = build_pre_draft_action_plan(
        recommended_strategy=context.strategy_profile.mode.label,
        budget_plan=budget,
        priority_players={
            "Priority": [item.player_name for item in ranked[:3]],
            "Fallback": [item.player_name for item in ranked[3:6]],
        },
        nomination_plan="Open with a low-interest player who pressures opponent cash.",
        fallback_plan=[item.player_name for item in ranked[3:6]],
    )
    saved_plan = PlanningPreferences(
        league_key=context.runtime_identity.league.league_key,
        user_key=context.runtime_identity.current.user_key,
        manager_id=context.runtime_identity.current.manager_id,
        recommended_strategy=plan.recommended_strategy,
        budget_bands=tuple(
            SavedBudgetBand(
                position=band.position,
                minimum=band.minimum,
                target=band.target,
                maximum=band.maximum,
            )
            for band in plan.budget_plan.bands
        ),
        priority_tiers=tuple(
            SavedPriorityTier(tier.label, tier.player_names)
            for tier in plan.priority_tiers
        ),
        nomination_plan=plan.nomination_plan,
        fallback_plan=plan.fallback_plan,
    )
    if (
        context.planning_preferences_store is not None
        and saved_plan != context.planning_preferences
    ):
        try:
            context.private_state_access.save_planning(
                context.planning_preferences_store,
                saved_plan,
            )
        except (OSError, ValueError) as error:
            st.warning("Pre-draft plan could not be saved: {0}".format(error))
        else:
            context.planning_preferences = saved_plan
    st.markdown("### Pre-Draft Action Plan")
    st.caption(
        "Strategy: {0} • Auction cash: ${1} • Reserve: ${2} • Saved privately".format(
            plan.recommended_strategy,
            plan.budget_plan.live_cash,
            plan.budget_plan.minimum_reserve,
        )
    )
    for tier in plan.priority_tiers:
        st.write("**{0}:** {1}".format(tier.label, ", ".join(tier.player_names)))
    st.write("**Nomination:** {0}".format(plan.nomination_plan))


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
            context.private_state_access.save_strategy(store, selected_profile)
            context.strategy_profile = selected_profile
            st.rerun()
        except OSError as error:
            st.warning(
                "Strategy preference could not be saved: {0}".format(error)
            )


def _render_keeper_trade_target_table(all_targets, *, private_key) -> None:
    filter_col1, filter_col2, filter_col3 = st.columns(3)

    position_options = sorted({target.position for target in all_targets})
    owner_options = sorted({target.owner_name for target in all_targets})

    selected_positions = filter_col1.multiselect(
        "Filter: Position",
        options=position_options,
        key=private_key("keeper_targets::position_filter"),
    )
    selected_owners = filter_col2.multiselect(
        "Filter: Owner",
        options=owner_options,
        key=private_key("keeper_targets::owner_filter"),
    )
    upgrades_only = filter_col3.checkbox(
        "Upgrades only",
        key=private_key("keeper_targets::upgrades_only"),
    )

    filtered_targets = [
        target
        for target in all_targets
        if (not selected_positions or target.position in selected_positions)
        and (not selected_owners or target.owner_name in selected_owners)
        and (not upgrades_only or target.is_upgrade)
    ]

    if not filtered_targets:
        st.info("No targets match the selected filters.")
        return

    page_size = 10
    num_pages = max(1, -(-len(filtered_targets) // page_size))

    page_key = private_key("keeper_targets::page")
    if page_key in st.session_state and st.session_state[page_key] > num_pages:
        st.session_state[page_key] = num_pages

    page = st.selectbox(
        "Page",
        options=list(range(1, num_pages + 1)),
        key=page_key,
    )

    start = (page - 1) * page_size
    page_targets = filtered_targets[start : start + page_size]

    st.caption(
        "Showing {0}-{1} of {2} matching target(s).".format(
            start + 1, start + len(page_targets), len(filtered_targets)
        )
    )

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Rank": target.rank,
                    "Player": target.player_name,
                    "Pos": target.position,
                    "Owner": target.owner_name,
                    "Strategy Score": target.strategy_score,
                    "Cost": target.cost,
                    "Surplus": target.surplus,
                    "Your Player at Pos": (
                        target.my_player_name or "(none)"
                    ),
                    "Your Score": target.my_strategy_score,
                    "Upgrade Over Yours?": (
                        "✅ Yes" if target.is_upgrade else "No"
                    ),
                    "Score Advantage": round(target.score_advantage, 2),
                }
                for target in page_targets
            ]
        ),
        width="stretch",
        hide_index=True,
    )


def _render_keeper_trade_calculator(
    context: AppRuntimeContext,
    *,
    keeper_trade_candidate_result,
    keeper_recommendations_by_manager,
    ACTIVE_MANAGERS,
    ACTIVE_MY_MANAGER_ID,
    private_key,
) -> None:
    st.markdown("### 🔁 Keeper Trade Calculator")
    st.caption(
        "Compare trading for an opponent's keeper -- plus any cash you'd "
        "include -- against keeping one of your own. Net value is the "
        "trade's value gain minus the cash you send; score advantage is "
        "the strategy-score gap. Both favoring the trade is a clear yes; "
        "both against it is a clear no; a split is a real judgment call."
    )

    targets = (
        keeper_trade_candidate_result.targets
        if keeper_trade_candidate_result is not None
        else ()
    )
    if not targets:
        st.info("No opponent keeper candidates are scored yet to trade for.")
        return

    target_by_label = {
        "{0} ({1}, {2})".format(
            target.player_name, target.position, target.owner_name
        ): target
        for target in targets
    }
    target_label = st.selectbox(
        "Player you'd trade for",
        options=tuple(target_by_label),
        key=private_key("keeper_trade_calc::target"),
    )
    selected_target = target_by_label[target_label]

    opponent_recommendations = keeper_recommendations_by_manager.get(
        selected_target.owner_manager_id, []
    )
    target_recommendation = next(
        (
            recommendation
            for recommendation in opponent_recommendations
            if normalize_player_name(recommendation.player_name)
            == normalize_player_name(selected_target.player_name)
        ),
        None,
    )
    if target_recommendation is None:
        st.warning(
            "{0}'s full keeper economics aren't available right now."
            .format(selected_target.player_name)
        )
        return

    my_recommendations = keeper_recommendations_by_manager.get(
        ACTIVE_MY_MANAGER_ID, []
    )
    current_keeper_options = ["(none -- fills an empty slot)"] + [
        recommendation.player_name for recommendation in my_recommendations
    ]
    default_index = 0
    if selected_target.my_player_name in current_keeper_options:
        default_index = current_keeper_options.index(
            selected_target.my_player_name
        )
    current_keeper_choice = st.selectbox(
        "Player you'd keep instead",
        options=current_keeper_options,
        index=default_index,
        key=private_key("keeper_trade_calc::current"),
    )
    current_keeper_recommendation = next(
        (
            recommendation
            for recommendation in my_recommendations
            if recommendation.player_name == current_keeper_choice
        ),
        None,
    )

    cash_offered = st.number_input(
        "Cash you'd include in the trade ($)",
        min_value=0,
        value=0,
        step=1,
        key=private_key("keeper_trade_calc::cash"),
    )

    evaluation = evaluate_keeper_trade(
        target=target_recommendation,
        current_keeper=current_keeper_recommendation,
        cash_offered=int(cash_offered),
        owner_name=selected_target.owner_name,
    )

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Value Delta", "${0:.0f}".format(evaluation.value_delta))
    e2.metric("Cash Offered", "${0}".format(evaluation.cash_offered))
    e3.metric("Net Value", "${0:.0f}".format(evaluation.net_value))
    e4.metric("Score Advantage", "{0:+.1f}".format(evaluation.score_advantage))

    if evaluation.verdict == "Good Trade":
        st.success("✅ {0}".format(evaluation.verdict))
    elif evaluation.verdict == "Not Worth It":
        st.error("❌ {0}".format(evaluation.verdict))
    else:
        st.warning("⚖️ {0}".format(evaluation.verdict))


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
    _render_action_plan(context)

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
    st.markdown("### Ranking Ensemble")
    if ensemble is not None:
        for warning in ensemble.warnings:
            st.info(warning)
        st.caption(
            "Sleeper and FantasyPros rankings are equal-weighted per player. "
            "Rank disagreement is shown as information and does not reduce "
            "player value. Drop research above to bring in a third opinion "
            "(e.g. ESPN rankings) as file-drop context."
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

    st.caption(
        "Manager tendencies and post-draft grading now live in the "
        "🧠 Manager Intelligence view."
    )

    keeper_recommendations_by_manager = (
        context.keeper_recommendations_by_manager or {}
    )
    keeper_recommendation_warnings = (
        context.keeper_recommendation_warnings
    )

    st.markdown("### Keeper Recommendations")
    st.caption(
        "Current and future value are normalized 0–100 scores. "
        "Auction value and strategy score are deterministic; no LLM "
        "is used for numeric scoring."
    )

    keeper_view_options = [ACTIVE_MY_MANAGER_ID] + [
        manager_id
        for manager_id in ACTIVE_MANAGERS
        if manager_id != ACTIVE_MY_MANAGER_ID
        and manager_id in keeper_recommendations_by_manager
    ]
    keeper_view_manager_id = st.selectbox(
        "Team",
        options=keeper_view_options,
        format_func=lambda manager_id: (
            "My Team"
            if manager_id == ACTIVE_MY_MANAGER_ID
            else (
                ACTIVE_MANAGERS[manager_id].sleeper_team_name
                or ACTIVE_MANAGERS[manager_id].sleeper_username
                or manager_id
            )
        ),
        key="keeper_recommendations::team",
    )
    keeper_recommendations = keeper_recommendations_by_manager.get(
        keeper_view_manager_id, []
    )

    if keeper_view_manager_id == ACTIVE_MY_MANAGER_ID:
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

        st.markdown("#### Decision Narrative")
        _render_decision_narrative(context)

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
                            str(economics.break_even_year)
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
            "{0} yet.".format(
                "your team"
                if keeper_view_manager_id == ACTIVE_MY_MANAGER_ID
                else "this team"
            )
        )

    keeper_trade_candidate_result = (
        context.keeper_trade_candidate_result
    )
    st.markdown("### Top 100 Opponent Keeper Trade Targets")
    st.caption(
        "Every opponent keeper candidate, ranked by strategy score, "
        "compared against your best candidate at the same position. "
        "'Upgrade' means this player currently scores higher than what "
        "you have there -- a real trade target, not just trade bait."
    )

    if keeper_trade_candidate_result is not None:
        for warning in keeper_trade_candidate_result.warnings:
            st.info(warning)

    all_targets = (
        keeper_trade_candidate_result.targets[:100]
        if keeper_trade_candidate_result is not None
        else ()
    )

    if all_targets:
        _render_keeper_trade_target_table(all_targets, private_key=private_key)
    else:
        st.info(
            "No opponent keeper candidates are scored yet for this league."
        )

    _render_keeper_trade_calculator(
        context,
        keeper_trade_candidate_result=keeper_trade_candidate_result,
        keeper_recommendations_by_manager=keeper_recommendations_by_manager,
        ACTIVE_MANAGERS=ACTIVE_MANAGERS,
        ACTIVE_MY_MANAGER_ID=ACTIVE_MY_MANAGER_ID,
        private_key=private_key,
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
        st.success(recommended_scenario.explanation.replace("$", "USD "))
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

    history_count = len(
        league_setup_data.historical_sales
    )


    r1, r2, r3 = (
        st.columns(3)
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
