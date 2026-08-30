from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.keeper_domain import KeeperDomainRules
from src.keeper_upside import build_keeper_stash_board


def render_keeper_stash_board(context: AppRuntimeContext) -> None:
    """Cheap remaining players with the best projected next-year keeper surplus."""

    league_profile = context.ACTIVE_LEAGUE_PROFILE
    if league_profile is None or not getattr(
        getattr(league_profile, "keepers", None), "enabled", False
    ):
        return

    try:
        rules = KeeperDomainRules.from_league_profile(league_profile)
    except (ValueError, AttributeError):
        return

    manager_count = max(1, len(context.ACTIVE_MANAGERS or {}))
    average_team_budget = (
        float(context.starting_total_auction_cash or 0) / manager_count
    )

    board = build_keeper_stash_board(
        available_players=context.available_players or [],
        market_value_index=context.market_value_index or {},
        fantasypros_index=context.fantasypros_index or {},
        annual_escalation=rules.annual_escalation,
        average_team_budget=average_team_budget,
    )

    open_spots = int(context.live_open_spots or 0)
    total_spots = open_spots + len(context.live_sales or [])
    late = total_spots > 0 and open_spots <= max(4, total_spots * 0.25)

    with st.expander(
        "🌱 Keeper Stashes ({0})".format(len(board)),
        expanded=bool(board) and late,
    ):
        st.caption(
            "Cheap players left on the board whose dynasty value clears next "
            "year's keeper cost (this year's price + ${0} escalation) by the "
            "widest margin. Best used once the money is gone and you're "
            "filling $1-3 bench spots.".format(rules.annual_escalation)
        )

        if not board:
            st.info(
                "No clear keeper-stash values right now -- either the cheap "
                "players left don't have strong dynasty ranks, or dynasty "
                "rankings aren't loaded."
            )
            return

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Player": c.player_name,
                        "Pos": c.position,
                        "Buy ~$": c.acquisition_cost,
                        "Keep next yr $": c.next_year_keeper_cost,
                        "Proj value $": c.projected_next_year_value,
                        "Surplus $": c.keeper_surplus,
                        "Value / cost": c.surplus_multiple,
                        "Dyn ECR": c.dynasty_ecr,
                        "Redraft ECR": c.half_ecr,
                        "Why": " • ".join(c.reasons),
                    }
                    for c in board
                ]
            ),
            width="stretch",
            hide_index=True,
        )
