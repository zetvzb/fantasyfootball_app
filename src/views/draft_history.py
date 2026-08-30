from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.purchase_grading import grade_recorded_purchases
from src.scenario_backtest_report import load_scenario_backtest_report
from src.scenario_blend_analysis import load_blend_sensitivity_report
from src.scenario_model_promotion import PromotionStatus, evaluate_promotion_readiness
from src.scenario_blend_rollout import ScenarioBlendSetting
from src.shadow_price_evaluation import evaluate_shadow_prices


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

    st.divider()
    st.subheader("🧪 Scenario Model Shadow Results")
    st.caption(
        "Evaluation only: compares decision-time ML estimates with completed "
        "sales. These estimates do not change the live recommendation."
    )
    shadow_evaluation = evaluate_shadow_prices(live_sales, snapshots)
    readiness = evaluate_promotion_readiness(shadow_evaluation)
    status_columns = st.columns(2)
    status_columns[0].metric("Promotion Status", readiness.status.value)
    status_columns[1].caption(readiness.recommendation)
    with st.expander("Promotion evidence gates", expanded=False):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Gate": gate.name,
                        "Status": "PASS" if gate.passed else "WAIT / FAIL",
                        "Observed": gate.observed_display,
                        "Requirement": gate.requirement,
                    }
                    for gate in readiness.gates
                ]
            ),
            width="stretch",
            hide_index=True,
        )
    current_setting = context.private_state_access.load_scenario_blend_setting(
        context.draft_store
    )
    setting_enabled = bool(current_setting and current_setting.enabled)
    active_model_version = (
        shadow_evaluation.results[-1].model_version
        if shadow_evaluation.results else ""
    )
    desired_enabled = st.checkbox(
        "Enable guarded 25% blend after READY approval",
        value=setting_enabled,
        disabled=(readiness.status is not PromotionStatus.READY and not setting_enabled),
        key=context.runtime_identity.private_key("scenario_blend_rollout_enabled"),
        help=(
            "Persists for this league, user, and manager. Runtime gates and model "
            "version checks continue on every nomination."
        ),
    )
    if desired_enabled != setting_enabled:
        context.private_state_access.save_scenario_blend_setting(
            context.draft_store,
            ScenarioBlendSetting(
                league_key=context.runtime_identity.league.league_key,
                user_key=context.runtime_identity.current.user_key,
                manager_id=context.runtime_identity.current.manager_id,
                enabled=desired_enabled,
                ml_weight=0.25,
                approved_model_version=(active_model_version if desired_enabled else ""),
            ),
        )
        st.success(
            "Guarded blend rollout enabled."
            if desired_enabled else "Guarded blend rollout disabled."
        )
    if not shadow_evaluation.results:
        st.info(
            "No completed sales have a shadow prediction yet. New nomination "
            "snapshots will appear here after their sales are recorded."
        )
    else:
        metric_columns = st.columns(5)
        metric_columns[0].metric("Matched Sales", len(shadow_evaluation.results))
        metric_columns[1].metric(
            "App Target MAE", "${0:.2f}".format(shadow_evaluation.app_mean_absolute_error)
        )
        metric_columns[2].metric(
            "Shadow Model MAE",
            "${0:.2f}".format(shadow_evaluation.shadow_mean_absolute_error),
            delta="${0:.2f}".format(
                shadow_evaluation.app_mean_absolute_error
                - shadow_evaluation.shadow_mean_absolute_error
            ),
            delta_color="normal",
        )
        metric_columns[3].metric(
            "25% Preview MAE",
            (
                "${0:.2f}".format(shadow_evaluation.blend_preview_mean_absolute_error)
                if shadow_evaluation.blend_preview_mean_absolute_error is not None
                else "Pending"
            ),
        )
        metric_columns[4].metric(
            "Prediction Band Coverage",
            "{0:.0%}".format(shadow_evaluation.interval_coverage),
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "#": item.sale_number,
                        "Player": item.player_name,
                        "Actual": item.actual_price,
                        "App Target": item.app_target_value,
                        "ML Low": item.shadow_low,
                        "ML Expected": item.shadow_predicted_price,
                        "ML High": item.shadow_high,
                        "App Error": item.app_error,
                        "ML Error": item.shadow_error,
                        "25% Preview Target": item.blend_preview_target,
                        "25% Preview Error": item.blend_preview_error,
                        "Band Hit": item.interval_hit,
                        "Model": item.model_version,
                    }
                    for item in shadow_evaluation.results
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    st.divider()
    st.subheader("📊 Historical Scenario Backtest")
    st.caption(
        "Offline chronological evaluation: every season was predicted using only "
        "earlier seasons. This is historical evidence, not a live shadow result."
    )
    backtest = load_scenario_backtest_report()
    if backtest is None:
        st.info("The optional historical backtest report is not available.")
        return
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "League": item.league_key.replace("_", " ").title(),
                    "Season": item.season,
                    "Sales": item.prediction_count,
                    "Rank Baseline MAE": item.baseline_mae,
                    "Scenario MAE": item.scenario_mae,
                    "Improvement": item.improvement_dollars,
                    "Improvement %": item.improvement_pct * 100.0,
                    "Bias": item.scenario_bias,
                    "Band Coverage": item.interval_coverage * 100.0,
                }
                for item in backtest.seasons
            ]
        ),
        column_config={
            "Improvement %": st.column_config.NumberColumn(format="%.1f%%"),
            "Band Coverage": st.column_config.NumberColumn(format="%.1f%%"),
        },
        width="stretch",
        hide_index=True,
    )
    for comparison in backtest.app_comparisons:
        st.success(
            "{0} {1}: on {2} comparable sales, scenario MAE was ${3:.2f} "
            "versus ${4:.2f} for the saved app market value ({5:.1%} lower)."
            .format(
                comparison.league_key.upper(), comparison.season,
                comparison.comparison_count, comparison.scenario_mae,
                comparison.app_mae, comparison.improvement_pct,
            )
        )
    if backtest.unmatched_sales:
        st.caption(
            "{0} historical sales were excluded because no ranking match was available."
            .format(backtest.unmatched_sales)
        )

    st.subheader("⚖️ Historical Blend Sensitivity")
    st.caption(
        "What-if analysis on held-out GDFM sales with saved app market values. "
        "This does not select or activate a live blend."
    )
    blend_report = load_blend_sensitivity_report()
    if blend_report is None:
        st.info("The optional held-out prediction file is not available.")
        return
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "League": point.league_key.upper(),
                    "Season": point.season,
                    "Comparable Sales": point.comparison_count,
                    "ML Weight": point.ml_weight * 100.0,
                    "MAE": point.mean_absolute_error,
                    "Bias": point.mean_error_bias,
                    "Improvement vs App": point.improvement_vs_app_pct * 100.0,
                }
                for point in blend_report.points
            ]
        ),
        column_config={
            "ML Weight": st.column_config.NumberColumn(format="%.0f%%"),
            "Improvement vs App": st.column_config.NumberColumn(format="%.1f%%"),
        },
        width="stretch",
        hide_index=True,
    )
    for candidate in blend_report.best_trial_points:
        st.caption(
            "{0} {1} best historical candidate within the 25% trial ceiling: "
            "{2:.0%} ML. "
            "Prospective promotion gates must still pass before any live trial."
            .format(candidate.league_key.upper(), candidate.season, candidate.ml_weight)
        )
