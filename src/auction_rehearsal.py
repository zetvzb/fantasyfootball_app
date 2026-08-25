from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Optional, Sequence, Tuple

from src.draft_recovery import DraftRecoveryResult, recover_draft_state
from src.historical_replay import (
    HistoricalReplayResult,
    RecommendationBuilder,
    replay_historical_sales,
)
from src.live_draft import build_live_team_setups, filter_sold_players


@dataclass(frozen=True)
class RehearsalPoll:
    """One deterministic Sleeper poll in an end-to-end draft rehearsal."""

    draft_picks: Tuple[dict, ...] = ()
    restart_before_poll: bool = False
    reconnect_error: Optional[str] = None


@dataclass(frozen=True)
class RehearsalStepResult:
    step_number: int
    status: str
    persisted_sale_count: int
    available_player_count: int
    reconciliation_changes: int = 0
    warning_count: int = 0
    detail: str = ""


@dataclass(frozen=True)
class FullAuctionRehearsalResult:
    completed: bool
    sales: Tuple[object, ...]
    live_team_setups: Mapping[str, object]
    available_players: Tuple[object, ...]
    steps: Tuple[RehearsalStepResult, ...]
    restart_count: int
    reconnect_failure_count: int
    replay: Optional[HistoricalReplayResult] = None


DraftStoreFactory = Callable[[], object]


def run_full_auction_rehearsal(
    *,
    polls: Sequence[RehearsalPoll],
    draft_store_factory: DraftStoreFactory,
    starting_team_setups: Mapping[str, object],
    starting_pool_players: Sequence[object],
    sleeper_players: Mapping[str, dict],
    managers: Mapping[str, object],
    recommendation_builder: Optional[RecommendationBuilder] = None,
) -> FullAuctionRehearsalResult:
    """Exercise polling, persistence, recovery, and replay through draft end.

    Every successful poll is a complete authoritative Sleeper snapshot. A
    reconnect failure deliberately leaves the persisted ledger untouched. A
    restart creates a fresh store instance and then reconciles from disk plus
    the next official snapshot.
    """

    if not polls:
        raise ValueError("A full auction rehearsal requires at least one poll.")

    store = draft_store_factory()
    steps = []
    restart_count = 0
    reconnect_failure_count = 0
    latest_recovery = None  # type: Optional[DraftRecoveryResult]

    for step_number, poll in enumerate(polls, start=1):
        if poll.restart_before_poll:
            store = draft_store_factory()
            restart_count += 1

        if poll.reconnect_error:
            reconnect_failure_count += 1
            persisted_sales = list(store.load_sales())
            live_team_setups = build_live_team_setups(
                starting_team_setups,
                persisted_sales,
            )
            available_players = filter_sold_players(
                starting_pool_players,
                persisted_sales,
            )
            steps.append(
                RehearsalStepResult(
                    step_number=step_number,
                    status="RECONNECT_FAILED",
                    persisted_sale_count=len(persisted_sales),
                    available_player_count=len(available_players),
                    detail=str(poll.reconnect_error),
                )
            )
            continue

        latest_recovery = recover_draft_state(
            draft_store=store,
            draft_picks=poll.draft_picks,
            starting_team_setups=starting_team_setups,
            starting_pool_players=starting_pool_players,
            sleeper_players=sleeper_players,
            managers=managers,
        )
        steps.append(
            RehearsalStepResult(
                step_number=step_number,
                status=(
                    "RECONCILED"
                    if latest_recovery.changes
                    else "NO_CHANGE"
                ),
                persisted_sale_count=len(latest_recovery.sales),
                available_player_count=len(latest_recovery.available_players),
                reconciliation_changes=len(latest_recovery.changes),
                warning_count=len(latest_recovery.warnings),
            )
        )

    final_sales = tuple(store.load_sales())
    final_team_setups = build_live_team_setups(
        starting_team_setups,
        list(final_sales),
    )
    final_available = tuple(
        filter_sold_players(starting_pool_players, list(final_sales))
    )
    expected_sale_count = sum(
        int(setup.open_roster_spots)
        for setup in starting_team_setups.values()
    )
    completed = (
        len(final_sales) == expected_sale_count
        and all(
            int(team.open_roster_spots) == 0
            for team in final_team_setups.values()
        )
    )
    replay = (
        replay_historical_sales(final_sales, recommendation_builder)
        if recommendation_builder is not None
        else None
    )
    return FullAuctionRehearsalResult(
        completed=completed,
        sales=final_sales,
        live_team_setups=final_team_setups,
        available_players=final_available,
        steps=tuple(steps),
        restart_count=restart_count,
        reconnect_failure_count=reconnect_failure_count,
        replay=replay,
    )
