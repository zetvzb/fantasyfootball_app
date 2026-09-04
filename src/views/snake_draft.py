from __future__ import annotations

import glob

import pandas as pd
import streamlit as st

from src.app_runtime import AppRuntimeContext
from src.auction_pool import normalize_player_name
from src.context_store import ContextStore
from src.draft_strategist import DraftStrategistService
from src.snake_draft import (
    build_draft_board,
    build_roster_need,
    build_team_value_leaderboard,
    bye_week_stack_warnings,
    load_adp_distribution,
    load_bye_weeks,
    next_pick_no_for_slot,
    optimize_snake_roster_plan,
    survival_probability,
)


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

    my_manager_id = context.ACTIVE_MY_MANAGER_ID

    # =========================================================
    # TEAM VALUE LEADERBOARD
    # =========================================================

    st.subheader("🏆 Team Value Leaderboard")
    st.caption(
        "Every manager's drafted picks summed by this league's own VORP/"
        "scoring settings -- not generic ADP, so it reflects real value in "
        "your exact format. A live, in-progress read, not a season forecast."
    )

    leaderboard = build_team_value_leaderboard(
        roster_by_manager=state.roster_by_manager,
        player_values=context.player_values,
    )

    if leaderboard:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Team": manager_name_by_id.get(entry.manager_id, entry.manager_id)
                        + (" (You)" if entry.manager_id == my_manager_id else ""),
                        "Picks Made": entry.picks_made,
                        "Total VORP": round(entry.total_vorp, 1),
                        "Total Projected Pts": round(entry.total_projected_points, 1),
                    }
                    for entry in leaderboard
                ]
            ),
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("No picks have been made yet.")

    st.divider()

    # =========================================================
    # WHO TO DRAFT NEXT
    # =========================================================

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

    # Players marked unavailable in League Setup Data are off the board for a
    # reason the pick feed can't show -- treat them like an already-made pick
    # so they never surface in the board, strategist, or roster plan.
    unavailable_player_names = list(context.unavailable_player_names or ())

    board = build_draft_board(
        player_values=context.player_values,
        drafted_player_names=drafted_player_names + unavailable_player_names,
        roster_need=roster_need,
    )

    st.subheader("📋 Who To Draft Next")
    st.caption(
        "Ranked by VORP against replacement level, weighted toward your open "
        "starter/FLEX needs and toward positions running out of startable "
        "depth. Already-drafted players are removed."
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
    n3.metric(
        "Flexible Starter Gaps",
        ", ".join(
            "{0} x{1}".format(slot, gap)
            for slot, gap in roster_need.flex_gaps.items()
        )
        or "None",
    )

    rankings_paths = sorted(
        glob.glob(
            "data/ml_pipeline/fantasypros_{0}_*_draft_rankings.csv".format(
                context.ACTIVE_LEAGUE_PROFILE.season
            )
        )
    )
    rankings_path = rankings_paths[0] if rankings_paths else None
    bye_weeks = load_bye_weeks(rankings_path) if rankings_path else {}
    adp_distribution = load_adp_distribution(rankings_path) if rankings_path else {}
    my_drafted_names = [pick.player_name for pick in my_picks if pick.player_name]
    bye_warnings = (
        bye_week_stack_warnings(
            candidates=board,
            my_drafted_player_names=my_drafted_names,
            bye_weeks=bye_weeks,
        )
        if bye_weeks
        else {}
    )

    next_turn_pick_no = None
    if adp_distribution and state.viewer_slot and state.current_pick_no:
        next_turn_pick_no = next_pick_no_for_slot(
            state.current_pick_no, state.viewer_slot, state.team_count
        )

    def _survival_pct(player_name: str):
        if next_turn_pick_no is None:
            return None
        dist = adp_distribution.get(normalize_player_name(player_name))
        if dist is None:
            return None
        avg_rank, stddev = dist
        return round(
            100
            * survival_probability(
                average_rank=avg_rank, rank_stddev=stddev, target_pick_no=next_turn_pick_no
            ),
            0,
        )

    try:
        context_store = ContextStore()
    except Exception:
        context_store = None

    def _recent_flag(player_name: str) -> str:
        if context_store is None:
            return ""
        try:
            flag = context_store.get_recent_flag(player_name)
        except Exception:
            return ""
        return flag or ""

    if next_turn_pick_no and next_turn_pick_no != state.current_pick_no:
        st.caption(
            "Your next pick is #{0}. \"Survives to Turn\" estimates the chance "
            "each player is still there then (independent-per-player estimate "
            "from ADP variance -- treat as reach/wait triage, not a guarantee)."
            .format(next_turn_pick_no)
        )

    if board:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Player": entry.player_name,
                        "Pos": entry.position,
                        "VORP": round(entry.vorp, 1),
                        "Need Bonus": round(entry.need_bonus, 1),
                        "Scarcity Bonus": round(entry.scarcity_bonus, 1),
                        "Rank Score": round(entry.utility, 1),
                        "Projected Pts": round(entry.projected_points, 1),
                        "Bye Week": bye_weeks.get(
                            normalize_player_name(entry.player_name), None
                        ),
                        "Survives to Turn (%)": _survival_pct(entry.player_name),
                        "Recent News/Injury (21d)": _recent_flag(entry.player_name),
                    }
                    for entry in board[:50]
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        for entry in board[:10]:
            if entry.player_name in bye_warnings:
                st.warning("{0}: {1}".format(entry.player_name, bye_warnings[entry.player_name]))
    else:
        st.info("No available players found.")

    st.subheader("🤖 Draft Strategist")
    st.caption(
        "A read-only agent compares the top five deterministic candidates and "
        "your roster needs. It cannot change rankings or submit a pick."
    )
    strategist_key = context.runtime_identity.private_key(
        "draft_strategist::{0}".format(state.current_pick_no)
    )
    if st.button(
        "Ask Draft Strategist",
        disabled=not board or state.is_complete,
        key=context.runtime_identity.private_key("ask_draft_strategist"),
    ):
        with st.spinner("Comparing the top five candidates..."):
            st.session_state[strategist_key] = DraftStrategistService().recommend(
                candidates=board[:5],
                roster_need=roster_need,
                current_pick_no=state.current_pick_no,
            )
    strategist = st.session_state.get(strategist_key)
    if strategist is not None:
        st.success(
            "Draft {0} ({1}) — {2} confidence".format(
                strategist.player_name,
                strategist.position,
                strategist.confidence.upper(),
            )
        )
        st.write(strategist.explanation)
        if strategist.alternatives:
            st.caption("Fallbacks: {0}".format(" → ".join(strategist.alternatives)))
        if strategist.warning:
            st.warning(strategist.warning)
        elif strategist.source == "openai":
            st.caption(
                "AI advisory via {0}; deterministic board and roster math unchanged."
                .format(strategist.model)
            )

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
