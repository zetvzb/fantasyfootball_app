from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext


def render_bid_copilot(
    context: AppRuntimeContext,
    sale_input_mode: str,
) -> None:

    ACTIVE_MANAGERS = (
        context.ACTIVE_MANAGERS
    )

    add_live_sale = (
        context.add_live_sale
    )

    calculate_context_valuation_adjustment = (
        context.calculate_context_valuation_adjustment
    )

    calculate_roster_aware_ceiling = (
        context.calculate_roster_aware_ceiling
    )

    compare_buy_vs_pass = (
        context.compare_buy_vs_pass
    )

    context_store = (
        context.context_store
    )

    draft_store = (
        context.draft_store
    )

    fantasypros_data = (
        context.fantasypros_data
    )

    fantasypros_index = (
        context.fantasypros_index
    )

    get_targeted_player_context = (
        context.get_targeted_player_context
    )

    live_calibration = (
        context.live_calibration
    )

    live_sales = (
        context.live_sales
    )

    live_team_setups = (
        context.live_team_setups
    )

    market_value_index = (
        context.market_value_index
    )

    my_live_setup = (
        context.my_live_setup
    )

    my_need_profile = (
        context.my_need_profile
    )

    nomination_index = (
        context.nomination_index
    )

    normalize_player_name = (
        context.normalize_player_name
    )

    optimization_candidates = (
        context.optimization_candidates
    )

    player_value_index = (
        context.player_value_index
    )

    projection_index = (
        context.projection_index
    )

    recommendation_index = (
        context.recommendation_index
    )

    recommendations = (
        context.recommendations
    )

    team_setups = (
        context.team_setups
    )

    threat_index = (
        context.threat_index
    )

    # =========================================================
    # LIVE BID COPILOT
    # =========================================================

    st.divider()

    st.header(
        "💰 Live Bid Copilot"
    )


    recommendation_names = sorted(
        [
            recommendation.player_name

            for recommendation
            in recommendations
        ]
    )


    if (
        "nominated_player"
        in st.session_state
        and
        st.session_state[
            "nominated_player"
        ]
        not in recommendation_names
    ):

        del st.session_state[
            "nominated_player"
        ]


    if recommendation_names:

        nominated_player = (
            st.selectbox(
                "Nominated Player",
                options=(
                    recommendation_names
                ),
                key=(
                    "nominated_player"
                ),
            )
        )


        nominated_key = (
            normalize_player_name(
                nominated_player
            )
        )


        recommendation = (
            recommendation_index.get(
                nominated_key
            )
        )


        nomination_info = (
            nomination_index.get(
                nominated_key
            )
        )


        threat_summary = (
            threat_index.get(
                nominated_key
            )
        )


        fp = (
            fantasypros_index.get(
                nominated_key
            )
        )


        projection = (
            projection_index.get(
                nominated_key
            )
        )


        vorp_value = (
            player_value_index.get(
                nominated_key
            )
        )


        selected_market = (
            market_value_index.get(
                nominated_key
            )
        )


        (
            player_context_summary,
            player_context_documents,
            context_lookup_name,
            targeted_news_count,
            targeted_injury_count,
            targeted_context_error,
        ) = (
            get_targeted_player_context(
                fp=(
                    fp
                ),
                auction_player_name=(
                    nominated_player
                ),
                fantasypros_data=(
                    fantasypros_data
                ),
                context_store=(
                    context_store
                ),
            )
        )


        if recommendation:

            # =================================================
            # DETERMINISTIC CEILING
            # =================================================

            player_level_ceiling = int(
                recommendation.do_not_exceed
            )


            # =================================================
            # CONTEXT CEILING
            # =================================================

            context_adjustment = (
                calculate_context_valuation_adjustment(
                    player_name=(
                        recommendation.player_name
                    ),
                    base_ceiling=(
                        player_level_ceiling
                    ),
                    context_summary=(
                        player_context_summary
                    ),
                    legal_max=(
                        recommendation
                        .legal_max_bid
                    ),
                )
            )


            context_adjusted_ceiling = (
                context_adjustment
                .adjusted_ceiling
            )


            # =================================================
            # ROSTER-AWARE CEILING
            # =================================================

            roster_ceiling = (
                context_adjusted_ceiling
            )


            roster_ceiling_available = False


            if (
                my_live_setup
                and
                my_need_profile
                and
                optimization_candidates
            ):

                (
                    calculated_roster_ceiling,
                    _,
                ) = (
                    calculate_roster_aware_ceiling(
                        player_name=(
                            recommendation.player_name
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


                if (
                    calculated_roster_ceiling
                    >
                    0
                ):

                    roster_ceiling = int(
                        calculated_roster_ceiling
                    )

                    roster_ceiling_available = True


            # =================================================
            # FINAL CEILING
            # =================================================

            final_do_not_exceed = min(
                context_adjusted_ceiling,
                roster_ceiling,
                int(
                    recommendation.legal_max_bid
                ),
            )


            # =================================================
            # PLAYER HEADER
            # =================================================

            st.markdown(
                f"# {recommendation.player_name}"
            )


            if nomination_info:

                st.caption(
                    f"{recommendation.position} • "
                    f"Nomination: "
                    f"{nomination_info.action}"
                )


            left, center, right = (
                st.columns(
                    [
                        1.3,
                        2,
                        1.3,
                    ]
                )
            )


            with left:

                st.metric(
                    "Expected Market",
                    (
                        f"${recommendation.expected_market_value:.0f}"
                    ),
                )


                st.metric(
                    "Deterministic Ceiling",
                    (
                        f"${player_level_ceiling}"
                    ),
                )


            with center:

                st.markdown(
                    "## DO NOT EXCEED"
                )


                st.markdown(
                    f"# 💰 ${final_do_not_exceed}"
                )


                st.markdown(
                    f"### {recommendation.strategy}"
                )


            with right:

                st.metric(
                    "Context Ceiling",
                    (
                        f"${context_adjusted_ceiling}"
                    ),
                    delta=(
                        f"{context_adjustment.adjustment_dollars:+d}"
                        if context_adjustment.applied
                        else None
                    ),
                )


                st.metric(
                    "Roster Ceiling",
                    (
                        f"${roster_ceiling}"
                    ),
                )


            st.caption(
                f"Legal maximum bid: "
                f"${recommendation.legal_max_bid}"
            )


            # =================================================
            # CONTEXT PRICE EFFECT
            # =================================================

            if context_adjustment.applied:

                context_message = (
                    f"Context changed the player ceiling "
                    f"from ${player_level_ceiling} "
                    f"to ${context_adjusted_ceiling} "
                    f"({context_adjustment.adjustment_pct:+.1%})."
                )


                if (
                    context_adjustment
                    .adjustment_dollars
                    >
                    0
                ):

                    st.success(
                        context_message
                    )

                else:

                    st.warning(
                        context_message
                    )


                with st.expander(
                    "Why Context Changed the Price"
                ):

                    ca1, ca2, ca3, ca4 = (
                        st.columns(4)
                    )


                    ca1.metric(
                        "Current Signal",
                        (
                            f"{context_adjustment.current_signal:+.2f}"
                        ),
                    )


                    ca2.metric(
                        "Future Signal",
                        (
                            f"{context_adjustment.future_signal:+.2f}"
                        ),
                    )


                    ca3.metric(
                        "60/40 Blend",
                        (
                            f"{context_adjustment.blended_signal:+.2f}"
                        ),
                    )


                    ca4.metric(
                        "Confidence",
                        (
                            f"{context_adjustment.context_confidence:.0%}"
                        ),
                    )


                    st.caption(
                        f"Confidence strength used for pricing: "
                        f"{context_adjustment.confidence_strength:.0%}"
                    )


                    for reason in (
                        context_adjustment.reasons
                    ):

                        st.write(
                            f"• {reason}"
                        )


            else:

                st.caption(
                    "Player context did not materially change "
                    "the deterministic ceiling."
                )


            # =================================================
            # ROSTER EFFECT
            # =================================================

            if (
                roster_ceiling_available
                and
                roster_ceiling
                <
                context_adjusted_ceiling
            ):

                st.warning(
                    f"Roster construction lowers the ceiling "
                    f"from ${context_adjusted_ceiling} "
                    f"to ${roster_ceiling}."
                )


            # =================================================
            # CEILING PIPELINE
            # =================================================

            with st.expander(
                "💵 Ceiling Calculation"
            ):

                price1, price2, price3, price4 = (
                    st.columns(4)
                )


                price1.metric(
                    "1. Deterministic",
                    f"${player_level_ceiling}",
                )


                price2.metric(
                    "2. Context",
                    f"${context_adjusted_ceiling}",
                )


                price3.metric(
                    "3. Roster",
                    f"${roster_ceiling}",
                )


                price4.metric(
                    "4. Final",
                    f"${final_do_not_exceed}",
                )


            # =================================================
            # LIVE MARKET
            # =================================================

            if selected_market:

                with st.expander(
                    "2026 Live Price Adjustment"
                ):

                    lp1, lp2, lp3, lp4 = (
                        st.columns(4)
                    )


                    lp1.metric(
                        "Before Live Learning",
                        (
                            f"${selected_market.pre_live_market_value:.1f}"
                        ),
                    )


                    lp2.metric(
                        "Live Multiplier",
                        (
                            f"{selected_market.live_multiplier:.3f}x"
                        ),
                    )


                    lp3.metric(
                        "Position Signal",
                        (
                            f"{selected_market.position_multiplier:.3f}x"
                        ),
                    )


                    lp4.metric(
                        "Tier",
                        selected_market.price_tier,
                    )


            # =================================================
            # CURRENT BID
            # =================================================

            current_bid = (
                st.number_input(
                    "Current Bid",
                    min_value=1,
                    value=1,
                    step=1,
                    key=(
                        f"current_bid_"
                        f"{nominated_key}"
                    ),
                )
            )


            if (
                current_bid
                <
                final_do_not_exceed
            ):

                st.success(
                    f"${final_do_not_exceed - current_bid} "
                    f"of bidding room remains."
                )


            elif (
                current_bid
                ==
                final_do_not_exceed
            ):

                st.warning(
                    "THIS IS YOUR CEILING. "
                    "Do not bid again."
                )


            else:

                st.error(
                    f"STOP — ${current_bid} is above "
                    f"your ${final_do_not_exceed} ceiling."
                )


            # =================================================
            # BUY VS PASS
            # =================================================

            st.markdown(
                "## 🔮 What If I Win Him?"
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
                        f"scenario_price_"
                        f"{nominated_key}"
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
                            use_container_width=True,
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
                            use_container_width=True,
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


            # =================================================
            # PLAYER CONTEXT
            # =================================================

            st.markdown(
                "## 🧠 Player Context"
            )


            with st.expander(
                "Context Retrieval Status"
            ):

                c1, c2, c3, c4, c5 = (
                    st.columns(5)
                )


                c1.metric(
                    "FantasyPros ID",
                    (
                        str(
                            fp.fantasypros_id
                        )
                        if (
                            fp
                            and
                            fp.fantasypros_id
                        )
                        else "-"
                    ),
                )


                c2.metric(
                    "Targeted News",
                    (
                        targeted_news_count
                        if targeted_news_count
                        is not None
                        else "-"
                    ),
                )


                c3.metric(
                    "Targeted Injuries",
                    (
                        targeted_injury_count
                        if targeted_injury_count
                        is not None
                        else "-"
                    ),
                )


                c4.metric(
                    "Stored Docs",
                    player_context_summary.document_count,
                )


                c5.metric(
                    "Active Events",
                    player_context_summary.event_count,
                )


                st.caption(
                    f"Auction name: "
                    f"{recommendation.player_name}"
                )


                st.caption(
                    f"Context lookup name: "
                    f"{context_lookup_name}"
                )


                if targeted_context_error:

                    st.error(
                        targeted_context_error
                    )


            if (
                player_context_summary
                and
                player_context_summary.document_count
                >
                0
            ):

                ctx1, ctx2, ctx3, ctx4 = (
                    st.columns(4)
                )


                ctx1.metric(
                    "Role",
                    f"{player_context_summary.role_score:+.2f}",
                )


                ctx2.metric(
                    "Usage",
                    f"{player_context_summary.usage_score:+.2f}",
                )


                ctx3.metric(
                    "Health",
                    f"{player_context_summary.health_score:+.2f}",
                )


                ctx4.metric(
                    "Dynasty",
                    f"{player_context_summary.dynasty_score:+.2f}",
                )


                ctx5, ctx6, ctx7 = (
                    st.columns(3)
                )


                ctx5.metric(
                    "Overall Context",
                    (
                        f"{player_context_summary.overall_context_score:+.2f}"
                    ),
                )


                ctx6.metric(
                    "Confidence",
                    (
                        f"{player_context_summary.confidence:.0%}"
                    ),
                )


                ctx7.metric(
                    "Active Events",
                    player_context_summary.event_count,
                )


                # =============================================
                # VALUATION EFFECT
                # =============================================

                st.markdown(
                    "### Auction Valuation Impact"
                )


                vi1, vi2, vi3, vi4 = (
                    st.columns(4)
                )


                vi1.metric(
                    "Before Context",
                    f"${player_level_ceiling}",
                )


                vi2.metric(
                    "Context Adjustment",
                    (
                        f"{context_adjustment.adjustment_pct:+.1%}"
                    ),
                )


                vi3.metric(
                    "Dollar Change",
                    (
                        f"{context_adjustment.adjustment_dollars:+d}"
                    ),
                )


                vi4.metric(
                    "After Context",
                    f"${context_adjusted_ceiling}",
                )


                st.caption(
                    "Context is bounded: positive information "
                    "can add at most 6%, while negative context "
                    "can remove at most 8% before roster "
                    "optimization applies."
                )


                # =============================================
                # SUMMARY
                # =============================================

                if player_context_summary.reasons:

                    st.markdown(
                        "### Context Summary"
                    )


                    for reason in (
                        player_context_summary.reasons
                    ):

                        st.write(
                            f"• {reason}"
                        )


                # =============================================
                # STATIC DEPTH CHART
                # =============================================

                depth_documents = [
                    document

                    for document
                    in player_context_documents

                    if (
                        document.source_type
                        ==
                        "depth_chart"
                    )
                ]


                if depth_documents:

                    latest_depth = (
                        depth_documents[
                            0
                        ]
                    )


                    depth_meta = (
                        latest_depth.metadata
                    )


                    st.markdown(
                        "### 🪜 Current Depth Chart"
                    )


                    dc1, dc2, dc3, dc4 = (
                        st.columns(4)
                    )


                    dc1.metric(
                        "Role",
                        (
                            depth_meta.get(
                                "role_label"
                            )
                            or "-"
                        ),
                    )


                    dc2.metric(
                        "Depth Order",
                        (
                            depth_meta.get(
                                "depth_chart_order"
                            )
                            or "-"
                        ),
                    )


                    dc3.metric(
                        "Team",
                        (
                            depth_meta.get(
                                "team"
                            )
                            or "-"
                        ),
                    )


                    dc4.metric(
                        "Committee",
                        (
                            "YES"
                            if depth_meta.get(
                                "committee_risk"
                            )
                            else "NO"
                        ),
                    )


                    nearby = (
                        depth_meta.get(
                            "nearby_players",
                            [],
                        )
                    )


                    if nearby:

                        st.caption(
                            "Nearby competition: "
                            +
                            ", ".join(
                                nearby[
                                    :5
                                ]
                            )
                        )


                # =============================================
                # DEPTH MOVEMENT HISTORY
                # =============================================

                movement_documents = [
                    document

                    for document
                    in player_context_documents

                    if (
                        document.source_type
                        ==
                        "depth_chart_movement"
                    )
                ]


                if movement_documents:

                    st.markdown(
                        "### 📈 Recent Depth-Chart Movement"
                    )


                    for document in (
                        movement_documents[
                            :6
                        ]
                    ):

                        movement_type = (
                            document.metadata.get(
                                "movement_type",
                                "CHANGE",
                            )
                        )


                        event_date = "-"


                        if document.published_at:

                            event_date = (
                                document
                                .published_at
                                .strftime(
                                    "%Y-%m-%d %H:%M"
                                )
                            )


                        if movement_type in {
                            "PROMOTED",
                            "COMPETITION_REMOVED",
                            "STARTER_REMOVED",
                        }:

                            st.success(
                                f"**{movement_type}** — "
                                f"{document.title}"
                            )


                        elif movement_type in {
                            "DEMOTED",
                            "COMPETITION_ADDED",
                        }:

                            st.warning(
                                f"**{movement_type}** — "
                                f"{document.title}"
                            )


                        else:

                            st.info(
                                f"**{movement_type}** — "
                                f"{document.title}"
                            )


                        st.caption(
                            f"{event_date} • "
                            f"Role "
                            f"{document.role_signal:+.2f} • "
                            f"Usage "
                            f"{document.usage_signal:+.2f}"
                        )


                # =============================================
                # CURRENT FOOTBALL STATE
                # =============================================

                st.markdown(
                    "### Current Football State"
                )


                event_rows = []


                for event in (
                    player_context_summary
                    .active_events[
                        :18
                    ]
                ):

                    event_date = "-"


                    if event.occurred_at:

                        event_date = (
                            event
                            .occurred_at
                            .strftime(
                                "%Y-%m-%d"
                            )
                        )


                    event_rows.append(
                        {
                            "State": event.event_type,
                            "Dimension": event.dimension,
                            "Impact": event.impact,
                            "Confidence": (
                                event.confidence
                                *
                                100
                            ),
                            "Date": event_date,
                            "Evidence": event.evidence,
                            "Source": event.title,
                        }
                    )


                if event_rows:

                    st.dataframe(
                        pd.DataFrame(
                            event_rows
                        ),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Impact": (
                                st.column_config
                                .NumberColumn(
                                    format="%.2f",
                                )
                            ),
                            "Confidence": (
                                st.column_config
                                .ProgressColumn(
                                    min_value=0,
                                    max_value=100,
                                    format="%.0f%%",
                                )
                            ),
                        },
                    )


                # =============================================
                # RAW EVIDENCE
                # =============================================

                with st.expander(
                    "Recent Context Evidence",
                    expanded=False,
                ):

                    for document in (
                        player_context_documents[
                            :12
                        ]
                    ):

                        date_text = "-"


                        if document.published_at:

                            date_text = (
                                document
                                .published_at
                                .strftime(
                                    "%Y-%m-%d %H:%M"
                                )
                            )


                        st.markdown(
                            f"**{document.title}**"
                        )


                        st.caption(
                            f"{document.source_name} • "
                            f"{document.source_type} • "
                            f"{date_text}"
                        )


                        if document.content:

                            content = (
                                document.content
                            )


                            if len(
                                content
                            ) > 700:

                                content = (
                                    content[
                                        :700
                                    ]
                                    +
                                    "..."
                                )


                            st.write(
                                content
                            )


                        if document.url:

                            st.markdown(
                                f"[Open source]({document.url})"
                            )


                        st.divider()


            else:

                st.info(
                    "No meaningful stored context is "
                    "currently available for this player."
                )


            # =================================================
            # PLAYER SIGNALS
            # =================================================

            st.markdown(
                "### Player Signals"
            )


            signal1, signal2, signal3, signal4 = (
                st.columns(4)
            )


            signal1.metric(
                "Your Need",
                f"{recommendation.my_need_score:.0%}",
            )


            signal2.metric(
                "Scarcity",
                f"{recommendation.scarcity_score:.0%}",
            )


            signal3.metric(
                "Bidder Threat",
                f"{recommendation.threat_score:.0f}/100",
            )


            signal4.metric(
                "VORP",
                (
                    f"{vorp_value.vorp:.1f}"
                    if vorp_value
                    else "-"
                ),
            )


            if recommendation.reasons:

                st.write(
                    " • ".join(
                        recommendation.reasons
                    )
                )


            # =================================================
            # NEXT OPTION
            # =================================================

            st.markdown(
                "### Next Option"
            )


            if (
                recommendation
                .alternative_player
            ):

                alt1, alt2, alt3 = (
                    st.columns(3)
                )


                alt1.metric(
                    f"Next {recommendation.position}",
                    recommendation.alternative_player,
                )


                alt2.metric(
                    "Expected Market",
                    (
                        f"${recommendation.alternative_market_value:.0f}"
                        if (
                            recommendation
                            .alternative_market_value
                            is not None
                        )
                        else "-"
                    ),
                )


                alt3.metric(
                    "VORP",
                    (
                        f"{recommendation.alternative_vorp:.1f}"
                        if (
                            recommendation
                            .alternative_vorp
                            is not None
                        )
                        else "-"
                    ),
                )


            # =================================================
            # FANTASYPROS INTELLIGENCE
            # =================================================

            with st.expander(
                "FantasyPros Intelligence"
            ):

                intel1, intel2, intel3, intel4 = (
                    st.columns(4)
                )


                intel1.metric(
                    "Projected Points",
                    (
                        f"{projection.custom_points:.1f}"
                        if (
                            projection
                            and
                            projection.custom_points
                            is not None
                        )
                        else "-"
                    ),
                )


                intel2.metric(
                    "2026 ECR",
                    (
                        f"{fp.half_ecr:.0f}"
                        if (
                            fp
                            and
                            fp.half_ecr
                            is not None
                        )
                        else "-"
                    ),
                )


                intel3.metric(
                    "Dynasty ECR",
                    (
                        f"{fp.dynasty_ecr:.0f}"
                        if (
                            fp
                            and
                            fp.dynasty_ecr
                            is not None
                        )
                        else "-"
                    ),
                )


                intel4.metric(
                    "ADP",
                    (
                        f"{fp.adp:.1f}"
                        if (
                            fp
                            and
                            fp.adp
                            is not None
                        )
                        else "-"
                    ),
                )


            # =================================================
            # BIDDER THREATS
            # =================================================

            with st.expander(
                "Who Might Bid Against Me?"
            ):

                bidder_rows = []


                if threat_summary:

                    for threat in (
                        threat_summary.threats
                    ):

                        manager_id = (
                            threat.manager_id
                        )


                        team_name = (
                            ACTIVE_MANAGERS[
                                manager_id
                            ].sleeper_team_name

                            if manager_id
                            in ACTIVE_MANAGERS

                            else manager_id
                        )


                        live_manager = (
                            live_calibration
                            .manager_profiles
                            .get(
                                manager_id
                            )
                        )


                        bidder_rows.append(
                            {
                                "Team": team_name,
                                "Threat": threat.threat_score,
                                "Need": (
                                    threat.need_score
                                    *
                                    100
                                ),
                                "Cash": threat.auction_cash,
                                "Legal Max": threat.max_bid,
                                "Can Afford": (
                                    threat.can_afford_market
                                ),
                                "2026 Buys": (
                                    live_manager.purchases
                                    if live_manager
                                    else 0
                                ),
                                "2026 Aggression": (
                                    live_manager.multiplier
                                    if live_manager
                                    else 1.0
                                ),
                                "Why": (
                                    "; ".join(
                                        threat.reasons
                                    )
                                ),
                            }
                        )


                if bidder_rows:

                    st.dataframe(
                        pd.DataFrame(
                            bidder_rows
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )


            # =================================================
            # MANUAL SALE
            # =================================================

            if (
                sale_input_mode
                ==
                "Manual Sale Entry"
            ):

                st.markdown(
                    "## 🧾 Record Completed Sale"
                )


                with st.form(
                    key=(
                        f"record_sale_"
                        f"{nominated_key}"
                    )
                ):

                    winner_id = (
                        st.selectbox(
                            "Winning Team",
                            options=list(
                                live_team_setups.keys()
                            ),
                            format_func=(
                                lambda manager_id: (
                                    ACTIVE_MANAGERS[
                                        manager_id
                                    ].sleeper_team_name
                                )
                            ),
                        )
                    )


                    winner_state = (
                        live_team_setups[
                            winner_id
                        ]
                    )


                    st.caption(
                        f"Cash: "
                        f"${winner_state.auction_cash} • "
                        f"Open spots: "
                        f"{winner_state.open_roster_spots} • "
                        f"Legal max: "
                        f"${winner_state.max_bid}"
                    )


                    sale_price = (
                        st.number_input(
                            "Sale Price",
                            min_value=1,
                            value=1,
                            step=1,
                        )
                    )


                    submit_sale = (
                        st.form_submit_button(
                            "✅ RECORD SALE",
                            use_container_width=True,
                        )
                    )


                    if submit_sale:

                        try:

                            updated_sales = (
                                add_live_sale(
                                    starting_team_setups=(
                                        team_setups
                                    ),
                                    existing_sales=(
                                        live_sales
                                    ),
                                    player_name=(
                                        recommendation
                                        .player_name
                                    ),
                                    position=(
                                        recommendation
                                        .position
                                    ),
                                    manager_id=(
                                        winner_id
                                    ),
                                    price=(
                                        int(
                                            sale_price
                                        )
                                    ),
                                    modeled_market_value=(
                                        recommendation
                                        .expected_market_value
                                    ),
                                    do_not_exceed=(
                                        final_do_not_exceed
                                    ),
                                )
                            )


                            draft_store.add_sale(
                                updated_sales[
                                    -1
                                ]
                            )


                            st.rerun()


                        except ValueError as error:

                            st.error(
                                str(
                                    error
                                )
                            )


    else:

        st.warning(
            "No auction recommendations are available."
        )
