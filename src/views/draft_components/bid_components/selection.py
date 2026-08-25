from __future__ import annotations

from typing import Optional

import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.dynamic_cap import DynamicCapInput, adjust_dynamic_cap
from src.pass_alternatives import find_pass_alternatives

from .state import BidPlayerState


def build_bid_player_state(
    context: AppRuntimeContext,
) -> Optional[BidPlayerState]:

    recommendations = (
        context.recommendations
    )

    normalize_player_name = (
        context.normalize_player_name
    )

    recommendation_index = (
        context.recommendation_index
    )

    nomination_index = (
        context.nomination_index
    )

    threat_index = (
        context.threat_index
    )

    fantasypros_index = (
        context.fantasypros_index
    )

    projection_index = (
        context.projection_index
    )

    player_value_index = (
        context.player_value_index
    )

    market_value_index = (
        context.market_value_index
    )

    get_targeted_player_context = (
        context.get_targeted_player_context
    )

    fantasypros_data = (
        context.fantasypros_data
    )

    context_store = (
        context.context_store
    )

    calculate_context_valuation_adjustment = (
        context.calculate_context_valuation_adjustment
    )

    calculate_roster_aware_ceiling = (
        context.calculate_roster_aware_ceiling
    )

    my_live_setup = (
        context.my_live_setup
    )

    my_need_profile = (
        context.my_need_profile
    )

    optimization_candidates = (
        context.optimization_candidates
    )

    nominated_player_state_key = (
        context.runtime_identity.private_key(
            "nominated_player"
        )
    )


    recommendation_names = sorted(
        [
            recommendation.player_name

            for recommendation
            in recommendations
        ]
    )


    if (
        nominated_player_state_key
        in st.session_state
        and
        st.session_state[
            nominated_player_state_key
        ]
        not in recommendation_names
    ):

        del st.session_state[
            nominated_player_state_key
        ]


    if not recommendation_names:

        st.warning(
            "No auction recommendations are available."
        )

        return None


    nominated_player = (
        st.selectbox(
            "Nominated Player",
            options=(
                recommendation_names
            ),
            key=(
                nominated_player_state_key
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


    if recommendation is None:

        st.warning(
            "No recommendation is available for the "
            "selected player."
        )

        return None


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


    player_level_ceiling = int(
        recommendation.do_not_exceed
    )


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

    stage = len(context.live_sales) / max(
        1.0,
        float(len(context.live_sales) + context.live_open_spots),
    )
    cash_flexibility = (
        float(my_live_setup.discretionary_cash)
        / max(1.0, float(my_live_setup.live_cash))
        if my_live_setup is not None
        else 0.5
    )
    dynasty_rank = getattr(fp, "dynasty_ecr", None)
    future_value_score = (
        max(0.0, (201.0 - float(dynasty_rank)) / 200.0)
        if dynasty_rank is not None
        else 0.5
    )
    strategy_profile = context.strategy_profile
    dynamic_cap_result = adjust_dynamic_cap(
        DynamicCapInput(
            base_cap=context_adjusted_ceiling,
            legal_max_bid=int(recommendation.legal_max_bid),
            need_score=float(recommendation.my_need_score),
            scarcity_score=float(recommendation.scarcity_score),
            has_comparable_alternative=bool(recommendation.alternative_player),
            cash_flexibility=cash_flexibility,
            auction_stage=stage,
            room_inflation_index=float(
                getattr(context.inflation_v2, "room_inflation_index", 1.0)
            ),
            current_weight=float(getattr(strategy_profile, "current_weight", 0.6)),
            future_weight=float(getattr(strategy_profile, "future_weight", 0.4)),
            future_value_score=future_value_score,
            context_adjustment_pct=float(context_adjustment.adjustment_pct),
        )
    )
    context_adjusted_ceiling = dynamic_cap_result.adjusted_cap


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


    final_do_not_exceed = min(
        context_adjusted_ceiling,
        roster_ceiling,
        int(
            recommendation.legal_max_bid
        ),
    )

    pass_alternatives = find_pass_alternatives(
        player_name=recommendation.player_name,
        position=recommendation.position,
        player_vorp=float(getattr(vorp_value, "vorp", 0.0) or 0.0),
        candidates=optimization_candidates,
        auction_stage=stage,
        threat_score=float(getattr(threat_summary, "top_threat_score", 0.0) or 0.0),
        remaining_cash=float(getattr(my_live_setup, "live_cash", 0.0) or 0.0),
    )


    return BidPlayerState(
        nominated_player=(
            nominated_player
        ),
        nominated_key=(
            nominated_key
        ),
        recommendation=(
            recommendation
        ),
        nomination_info=(
            nomination_info
        ),
        threat_summary=(
            threat_summary
        ),
        fp=(
            fp
        ),
        projection=(
            projection
        ),
        vorp_value=(
            vorp_value
        ),
        selected_market=(
            selected_market
        ),
        player_context_summary=(
            player_context_summary
        ),
        player_context_documents=(
            player_context_documents
        ),
        context_lookup_name=(
            context_lookup_name
        ),
        targeted_news_count=(
            targeted_news_count
        ),
        targeted_injury_count=(
            targeted_injury_count
        ),
        targeted_context_error=(
            targeted_context_error
        ),
        player_level_ceiling=(
            player_level_ceiling
        ),
        context_adjustment=(
            context_adjustment
        ),
        context_adjusted_ceiling=(
            context_adjusted_ceiling
        ),
        roster_ceiling=(
            roster_ceiling
        ),
        roster_ceiling_available=(
            roster_ceiling_available
        ),
        final_do_not_exceed=(
            final_do_not_exceed
        ),
        dynamic_cap_result=dynamic_cap_result,
        pass_alternatives=pass_alternatives,
    )
