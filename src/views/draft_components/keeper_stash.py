from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.auction_pool import normalize_player_name
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

    # Restrict the board to the positions this league actually keeps -- from the
    # players managers have finalized as keepers this year (candidates are the
    # whole roster and tell us nothing). If they only protect WR/RB, a cheap QB
    # is not a stash here.
    all_keepers = getattr(context.league_setup_data, "keepers", []) or []
    _pos_by_name = {}
    for keeper in all_keepers:
        pos = str(getattr(keeper, "position", "") or "").upper()
        if pos:
            _pos_by_name[normalize_player_name(keeper.player_name)] = pos
    fp_index = context.fantasypros_index or {}

    def _keeper_position(keeper) -> str:
        key = normalize_player_name(keeper.player_name)
        direct = str(getattr(keeper, "position", "") or "").upper()
        if direct:
            return direct
        if key in _pos_by_name:
            return _pos_by_name[key]
        return str(getattr(fp_index.get(key), "position", "") or "").upper()

    finalized_positions = [
        _keeper_position(keeper)
        for keeper in all_keepers
        if str(getattr(keeper, "status", "")) == "finalized"
    ]
    finalized_positions = [pos for pos in finalized_positions if pos]
    # Keep a position only if it is a real part of this league's keeper mix --
    # a lone QB or TE keeper should not open the board to every cheap young
    # passer. Needs enough signal (>= 6 finalized keepers) to restrict at all.
    eligible_positions = None
    if len(finalized_positions) >= 6:
        counts = Counter(finalized_positions)
        threshold = max(2, 0.12 * len(finalized_positions))
        eligible_positions = sorted(
            pos for pos, count in counts.items() if count >= threshold
        )
        if not eligible_positions:
            eligible_positions = None

    board = build_keeper_stash_board(
        available_players=context.available_players or [],
        market_value_index=context.market_value_index or {},
        fantasypros_index=context.fantasypros_index or {},
        annual_escalation=rules.annual_escalation,
        average_team_budget=average_team_budget,
        eligible_positions=eligible_positions,
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
        if eligible_positions:
            st.caption(
                "Limited to the positions this league actually keeps: {0}.".format(
                    ", ".join(eligible_positions)
                )
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
