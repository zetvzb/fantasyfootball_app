from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext

from .state import BidPlayerState


def render_player_context(
    context: AppRuntimeContext,
    state: BidPlayerState,
) -> None:

    context_adjusted_ceiling = (
        state.context_adjusted_ceiling
    )

    context_adjustment = (
        state.context_adjustment
    )

    context_lookup_name = (
        state.context_lookup_name
    )

    fp = (
        state.fp
    )

    player_context_documents = (
        state.player_context_documents
    )

    player_context_summary = (
        state.player_context_summary
    )

    player_level_ceiling = (
        state.player_level_ceiling
    )

    recommendation = (
        state.recommendation
    )

    targeted_context_error = (
        state.targeted_context_error
    )

    targeted_injury_count = (
        state.targeted_injury_count
    )

    targeted_news_count = (
        state.targeted_news_count
    )

    # =================================================
    # PLAYER CONTEXT
    # =================================================

    st.markdown(
        "## 🧠 Player Context"
    )


    with st.container(border=True):

        st.markdown("### Context Retrieval Status")

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
                width="stretch",
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

        with st.container(border=True):

            st.markdown("### Recent Context Evidence")

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

