from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext


def render_auction_board(
    context: AppRuntimeContext,
) -> None:

    ACTIVE_MANAGERS = (
        context.ACTIVE_MANAGERS
    )

    auction_value_index = (
        context.auction_value_index
    )

    available_players = (
        context.available_players
    )

    fantasypros_index = (
        context.fantasypros_index
    )

    market_value_index = (
        context.market_value_index
    )

    nomination_index = (
        context.nomination_index
    )

    normalize_player_name = (
        context.normalize_player_name
    )

    player_value_index = (
        context.player_value_index
    )

    recommendation_index = (
        context.recommendation_index
    )

    threat_index = (
        context.threat_index
    )

    st.divider()

    st.subheader(
        "📋 Live Auction Board"
    )


    st.caption(
        "Select a player in Live Bid Copilot for targeted "
        "news, injury, static depth-chart, depth-chart "
        "movement, and the authoritative roster-aware "
        "DO NOT EXCEED."
    )


    board_rows = []


    for player in available_players:

        key = (
            normalize_player_name(
                player.player_name
            )
        )


        recommendation = (
            recommendation_index.get(
                key
            )
        )


        nomination = (
            nomination_index.get(
                key
            )
        )


        market = (
            market_value_index.get(
                key
            )
        )


        baseline = (
            auction_value_index.get(
                key
            )
        )


        threat = (
            threat_index.get(
                key
            )
        )


        fp_board = (
            fantasypros_index.get(
                key
            )
        )


        vorp = (
            player_value_index.get(
                key
            )
        )


        top_competitor = "-"


        if (
            threat
            and
            threat.top_manager_id
        ):

            manager_id = (
                threat.top_manager_id
            )


            top_competitor = (
                ACTIVE_MANAGERS[
                    manager_id
                ].sleeper_team_name

                if manager_id
                in ACTIVE_MANAGERS

                else manager_id
            )


        board_rows.append(
            {
                "Player": player.player_name,
                "Pos": player.position,
                "NFL": player.nfl_team or "FA",
                "Player Ceiling": (
                    recommendation.do_not_exceed
                    if recommendation
                    else None
                ),
                "Strategy": (
                    recommendation.strategy
                    if recommendation
                    else "-"
                ),
                "Nominate Score": (
                    nomination.nomination_score
                    if nomination
                    else None
                ),
                "Nomination Action": (
                    nomination.action
                    if nomination
                    else "-"
                ),
                "Market $": (
                    market.expected_market_value
                    if market
                    else None
                ),
                "Live Multiplier": (
                    market.live_multiplier
                    if market
                    else 1.0
                ),
                "Baseline $": (
                    baseline.baseline_value
                    if baseline
                    else None
                ),
                "My Need": (
                    recommendation.my_need_score
                    *
                    100
                    if recommendation
                    else 0
                ),
                "Scarcity": (
                    recommendation.scarcity_score
                    *
                    100
                    if recommendation
                    else 0
                ),
                "Next Option": (
                    recommendation.alternative_player
                    if (
                        recommendation
                        and
                        recommendation.alternative_player
                    )
                    else "-"
                ),
                "Threat": (
                    threat.top_threat_score
                    if threat
                    else 0
                ),
                "Top Competitor": top_competitor,
                "VORP": (
                    vorp.vorp
                    if vorp
                    else None
                ),
                "2026 ECR": (
                    fp_board.half_ecr
                    if fp_board
                    else None
                ),
                "Dynasty ECR": (
                    fp_board.dynasty_ecr
                    if fp_board
                    else None
                ),
            }
        )


    board_df = (
        pd.DataFrame(
            board_rows
        )
    )


    filter1, filter2, filter3 = (
        st.columns(
            [
                2,
                1,
                1,
            ]
        )
    )


    with filter1:

        search = (
            st.text_input(
                "Search Player",
                key=context.runtime_identity.private_key(
                    "auction_board_search"
                ),
            )
        )


    with filter2:

        positions = (
            st.multiselect(
                "Position",
                options=[
                    "QB",
                    "RB",
                    "WR",
                    "TE",
                    "K",
                    "DEF",
                ],
                default=[
                    "QB",
                    "RB",
                    "WR",
                    "TE",
                    "K",
                    "DEF",
                ],
                key=context.runtime_identity.private_key(
                    "auction_board_positions"
                ),
            )
        )


    with filter3:

        sort_by = (
            st.selectbox(
                "Sort",
                options=[
                    "Player Ceiling",
                    "Nominate Score",
                    "Market $",
                    "Live Multiplier",
                    "My Need",
                    "Scarcity",
                    "Threat",
                    "VORP",
                    "2026 ECR",
                    "Dynasty ECR",
                ],
                key=context.runtime_identity.private_key(
                    "auction_board_sort"
                ),
            )
        )


    filtered_board = (
        board_df.copy()
    )


    if (
        not filtered_board.empty
        and
        positions
    ):

        filtered_board = (
            filtered_board[
                filtered_board[
                    "Pos"
                ].isin(
                    positions
                )
            ]
        )


    if (
        not filtered_board.empty
        and
        search
    ):

        filtered_board = (
            filtered_board[
                filtered_board[
                    "Player"
                ]
                .str.contains(
                    search,
                    case=False,
                    na=False,
                )
            ]
        )


    if not filtered_board.empty:

        ascending = (
            sort_by
            in {
                "2026 ECR",
                "Dynasty ECR",
            }
        )


        filtered_board = (
            filtered_board.sort_values(
                by=sort_by,
                ascending=ascending,
                na_position="last",
            )
        )


    st.dataframe(
        filtered_board,
        width="stretch",
        hide_index=True,
    )
