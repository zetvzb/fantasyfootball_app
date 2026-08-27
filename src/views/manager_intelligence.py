from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.pass_grading import grade_recorded_passes
from src.post_draft_review import build_copilot_post_draft_review
from src.purchase_grading import grade_recorded_purchases


def _team_name(manager_id: str, active_managers) -> str:
    identity = active_managers.get(manager_id)
    if identity is None:
        return manager_id
    return identity.sleeper_team_name or identity.sleeper_username or manager_id


def _render_post_draft_review(context: AppRuntimeContext) -> None:
    live_sales = context.live_sales
    snapshots = context.private_state_access.load_recommendation_history(
        context.draft_store
    )
    purchase_grades = grade_recorded_purchases(live_sales, snapshots)
    pass_grades = grade_recorded_passes(live_sales, snapshots)
    post_draft_review = build_copilot_post_draft_review(purchase_grades, pass_grades)

    st.markdown("### Copilot Post-Draft Review")
    st.caption(
        "How the copilot's own recommendations held up against what actually "
        "happened -- correct/incorrect verdicts, not opponent grading."
    )

    if not post_draft_review.decisions:
        st.info("No graded recommendations yet -- this fills in as sales are recorded.")
        return

    review_columns = st.columns(4)
    review_columns[0].metric("Correct", post_draft_review.correct_count)
    review_columns[1].metric("Incorrect", post_draft_review.incorrect_count)
    review_columns[2].metric("Pending", post_draft_review.pending_count)
    review_columns[3].metric(
        "Average Grade", "{0:.1f}".format(post_draft_review.average_graded_score)
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Player": decision.player_name,
                    "Decision": decision.decision_type,
                    "Verdict": decision.verdict.value,
                    "Score": decision.score,
                    "Explanation": decision.explanation,
                }
                for decision in post_draft_review.decisions
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    if post_draft_review.calibration_errors:
        st.warning(
            "Model review: {0}".format(
                " ".join(error.explanation for error in post_draft_review.calibration_errors)
            )
        )

    if purchase_grades:
        with st.expander("💵 Purchase Grade Details"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Player": grade.player_name,
                            "Grade": grade.letter_grade,
                            "Score": grade.total_score,
                            "Price": grade.price_discipline_score,
                            "Fit": grade.roster_fit_score,
                            "Alternatives": grade.alternative_score,
                            "Downstream": grade.downstream_score,
                            "Why": " ".join(grade.reasons),
                        }
                        for grade in purchase_grades
                    ]
                ),
                width="stretch",
                hide_index=True,
            )

    if pass_grades:
        with st.expander("🚫 Pass Grade Details"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Player": grade.player_name,
                            "Status": grade.status.value,
                            "Grade": grade.letter_grade,
                            "Score": grade.total_score,
                            "Target Sale $": grade.target_sale_price,
                            "Later Alternative": grade.acquired_alternative,
                            "Alternative $": grade.alternative_sale_price,
                            "Discipline": grade.discipline_score,
                            "Availability": grade.availability_score,
                            "Alternative Cost": grade.alternative_cost_score,
                            "Why": " ".join(grade.reasons),
                        }
                        for grade in pass_grades
                    ]
                ),
                width="stretch",
                hide_index=True,
            )


def _render_manager_tendencies(context: AppRuntimeContext) -> None:
    tendency_model = context.manager_tendency_model
    active_managers = context.ACTIVE_MANAGERS

    st.markdown("### Manager Tendencies")
    st.caption(
        "Time-decayed historical behavior per manager -- not a prediction of "
        "exact bids. Use it to anticipate who chases stars, who sits on cash, "
        "and who tends to overpay early."
    )

    if tendency_model is None:
        st.info("No tendency model is available for this league yet.")
        return

    for warning in tendency_model.warnings:
        st.warning(warning)

    if not tendency_model.profiles:
        st.info(
            "No historical auction data is available yet to derive tendencies."
        )
        return

    leaderboard = pd.DataFrame(
        [
            {
                "Team": _team_name(profile.manager_id, active_managers),
                "Confidence": profile.confidence,
                "Aggression": profile.historical_aggression,
                "Star Spend Share": profile.stars_spend_share,
                "Depth Spend Share": profile.depth_spend_share,
            }
            for profile in tendency_model.profiles
        ]
    ).sort_values(by="Aggression", ascending=False)
    st.dataframe(leaderboard, width="stretch", hide_index=True)

    profiles_by_manager = {
        profile.manager_id: profile for profile in tendency_model.profiles
    }
    selected_manager_id = st.selectbox(
        "Drill into a team",
        options=list(profiles_by_manager.keys()),
        format_func=lambda manager_id: _team_name(manager_id, active_managers),
        key="manager_intelligence::tendency_drilldown",
    )
    profile = profiles_by_manager[selected_manager_id]

    card_columns = st.columns(3)
    card_columns[0].metric("Confidence", "{0:.2f}".format(profile.confidence))
    card_columns[1].metric("Aggression", "{0:.2f}".format(profile.historical_aggression))
    card_columns[2].metric("Star Spend Share", "{0:.2f}".format(profile.stars_spend_share))

    detail_columns = st.columns(2)
    with detail_columns[0]:
        st.caption("Position premiums (spend relative to market)")
        if profile.position_premiums:
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Position": position, "Premium": premium}
                        for position, premium in sorted(
                            profile.position_premiums
                        )
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("No position premium data yet.")
    with detail_columns[1]:
        st.caption("Auction-stage timing share")
        if profile.auction_timing_share:
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Stage": stage, "Share": share}
                        for stage, share in sorted(profile.auction_timing_share)
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("No auction-timing data yet.")


def _render_historical_market(context: AppRuntimeContext) -> None:
    historical_market_model = context.historical_market_model
    active_managers = context.ACTIVE_MANAGERS

    st.markdown("### Historical Market")
    st.caption(
        "League-wide price history and per-manager aggressiveness/star-chase "
        "indexes derived from recorded sales across seasons."
    )

    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Mapped Sales", len(historical_market_model.mapped_sales))
    h2.metric("Eligible Seasons", len(historical_market_model.eligible_years))
    h3.metric("Unmapped Sales", historical_market_model.unmapped_sales_count)
    h4.metric(
        "Historical Avg Buy",
        "${0:.1f}".format(historical_market_model.league_average_purchase),
    )

    rows = [
        {
            "Team": _team_name(manager_id, active_managers),
            "Buys": profile.sales_count,
            "Avg Buy": profile.average_price,
            "Max Buy": profile.max_price,
            "Aggressiveness": profile.aggressiveness_index,
            "Star Chase": profile.star_chase_index,
        }
        for manager_id, profile in historical_market_model.manager_profiles.items()
    ]
    if rows:
        st.dataframe(
            pd.DataFrame(rows).sort_values(by="Aggressiveness", ascending=False),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No historical sales are mapped for this league yet.")


def render_manager_intelligence_view(context: AppRuntimeContext) -> None:
    st.header("🧠 Manager Intelligence")
    st.caption(
        "Opponent behavior and copilot self-grading in one place: how the "
        "copilot's own calls graded out, what each manager tends to do at "
        "the table, and the historical market they've built."
    )

    _render_post_draft_review(context)
    st.divider()
    _render_manager_tendencies(context)
    st.divider()
    _render_historical_market(context)
