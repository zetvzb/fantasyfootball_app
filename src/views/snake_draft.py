from __future__ import annotations

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.snake_draft import build_draft_board, build_roster_need, optimize_snake_roster_plan


def render_snake_draft_view(context: AppRuntimeContext) -> None:
    st.header("🐍 Snake Draft")

    if context.snake_draft_error and context.snake_draft_state is None:
        st.error(context.snake_draft_error)
        return

    state = context.snake_draft_state
    if state is None:
        st.warning("Snake draft state is unavailable.")
        return

    if context.snake_draft_error:
        st.warning(
            "Live pick sync failed, showing the last known state: {0}".format(
                context.snake_draft_error
            )
        )

    manager_name_by_id = {
        manager_id: (identity.sleeper_team_name or identity.sleeper_username or manager_id)
        for manager_id, identity in context.ACTIVE_MANAGERS.items()
    }

    # =========================================================
    # ON THE CLOCK
    # =========================================================

    if state.is_complete:
        st.success("Draft complete.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Current Pick", "#{0}".format(state.current_pick_no))
        c2.metric("Round", state.current_round)
        on_clock_name = manager_name_by_id.get(
            state.current_manager_id, state.current_manager_id or "Unknown"
        )
        c3.metric(
            "On the Clock",
            "You!" if state.on_the_clock_is_me else on_clock_name,
        )

        if state.next_picks:
            st.caption(
                "Next up: "
                + " → ".join(
                    "#{0} {1}".format(
                        pick.pick_no,
                        manager_name_by_id.get(pick.manager_id, pick.manager_id or "?"),
                    )
                    for pick in state.next_picks[:6]
                )
            )

    st.divider()

    # =========================================================
    # WHO TO DRAFT NEXT
    # =========================================================

    my_manager_id = context.ACTIVE_MY_MANAGER_ID
    my_picks = state.roster_by_manager.get(my_manager_id, ())
    my_drafted_positions = [pick.position for pick in my_picks if pick.position]
    starting_lineup = context.ACTIVE_LEAGUE_PROFILE.roster.starting_lineup
    roster_size = context.ACTIVE_LEAGUE_PROFILE.roster.roster_size

    roster_need = build_roster_need(
        drafted_positions=my_drafted_positions,
        starting_lineup=starting_lineup,
        roster_size=roster_size,
    )

    drafted_player_names = [
        pick.player_name for pick in state.made_picks if pick.player_name
    ]

    board = build_draft_board(
        player_values=context.player_values,
        drafted_player_names=drafted_player_names,
        roster_need=roster_need,
    )

    st.subheader("📋 Who To Draft Next")
    st.caption(
        "Ranked by VORP against replacement level, weighted toward your "
        "open starter and FLEX needs. Already-drafted players are removed."
    )

    n1, n2, n3 = st.columns(3)
    n1.metric("Your Open Spots", roster_need.open_spots)
    n2.metric(
        "Open Starter Needs",
        ", ".join(
            "{0} x{1}".format(position, gap)
            for position, gap in roster_need.starter_gaps.items()
            if gap > 0
        )
        or "None",
    )
    n3.metric("FLEX Gap", roster_need.flex_gap)

    if board:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Player": entry.player_name,
                        "Pos": entry.position,
                        "VORP": round(entry.vorp, 1),
                        "Need Bonus": round(entry.need_bonus, 1),
                        "Rank Score": round(entry.utility, 1),
                        "Projected Pts": round(entry.projected_points, 1),
                    }
                    for entry in board[:50]
                ]
            ),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No available players found.")

    st.divider()

    # =========================================================
    # REMAINING ROSTER PLAN
    # =========================================================

    st.subheader("🧩 Projected Remaining Roster")
    st.caption(
        "A slot-by-slot projection of your best-available roster if the "
        "draft board falls the way it currently ranks -- there's no cash "
        "tradeoff in a snake draft, so this simply maximizes total value "
        "across your remaining picks."
    )

    plan = optimize_snake_roster_plan(roster_need=roster_need, draft_board=board)

    if plan.feasible and plan.entries:
        p1, p2 = st.columns(2)
        p1.metric("Remaining Picks", len(plan.entries))
        p2.metric("Plan Value", round(plan.total_utility, 1))

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Slot": entry.slot,
                        "Player": entry.player_name,
                        "Pos": entry.position,
                        "VORP": round(entry.vorp, 1),
                        "Fallback": entry.is_filler,
                    }
                    for entry in plan.entries
                ]
            ),
            width="stretch",
            hide_index=True,
        )
    elif plan.feasible:
        st.info("Your roster is already full.")
    else:
        for warning in plan.warnings:
            st.warning(warning)

    st.divider()

    # =========================================================
    # RECENT PICKS
    # =========================================================

    st.subheader("📜 Recent Picks")
    recent = list(state.made_picks[-15:])
    recent.reverse()
    if recent:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Pick": pick.pick_no,
                        "Round": pick.round,
                        "Team": manager_name_by_id.get(pick.manager_id, pick.manager_id or "?"),
                        "Player": pick.player_name,
                        "Pos": pick.position,
                    }
                    for pick in recent
                ]
            ),
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("No picks have been made yet.")
