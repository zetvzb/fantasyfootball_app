from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

from src.live_draft import (
    LiveAuctionSale,
    build_live_team_setups,
    filter_sold_players,
)
from src.sleeper_reconciliation import (
    ReconciliationChange,
    reconcile_sleeper_sales,
)
from src.sleeper_sync import parse_sleeper_auction_picks


@dataclass(frozen=True)
class DraftRecoveryResult:
    sales: Tuple[LiveAuctionSale, ...]
    live_team_setups: Mapping[str, object]
    available_players: Tuple[object, ...]
    changes: Tuple[ReconciliationChange, ...]
    warnings: Tuple[str, ...]


def recover_draft_state(
    *,
    draft_store: object,
    draft_picks: Sequence[dict],
    starting_team_setups: Mapping[str, object],
    starting_pool_players: Sequence[object],
    sleeper_players: Mapping[str, dict],
    managers: Mapping[str, object],
) -> DraftRecoveryResult:
    """Rebuild current draft state from persisted state plus Sleeper truth."""

    persisted_sales = draft_store.load_sales()
    official_sales, warnings = parse_sleeper_auction_picks(
        draft_picks=list(draft_picks),
        starting_pool_players=starting_pool_players,
        sleeper_players=dict(sleeper_players),
        managers=managers,
    )
    reconciliation = reconcile_sleeper_sales(persisted_sales, official_sales)
    sales = list(reconciliation.sales)

    # Validate the fully derived state before replacing persistent data.
    live_team_setups = build_live_team_setups(
        starting_team_setups=starting_team_setups,
        sales=sales,
    )
    available_players = filter_sold_players(starting_pool_players, sales)
    if reconciliation.changes:
        draft_store.replace_sales(sales)

    return DraftRecoveryResult(
        sales=tuple(sales),
        live_team_setups=live_team_setups,
        available_players=tuple(available_players),
        changes=reconciliation.changes,
        warnings=tuple(warnings),
    )
