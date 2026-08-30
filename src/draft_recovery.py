from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Mapping, Sequence, Tuple

from src.auction_pool import normalize_player_name
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
    keeper_player_names: Iterable[str] = (),
) -> DraftRecoveryResult:
    """Rebuild current draft state from persisted state plus Sleeper truth.

    Keepers are protected roster players, not auction sales -- a Sleeper keeper
    pick (or a stale earlier import of one) must never end up in the live-sales
    ledger, where it would lock League Setup and double-charge the manager's
    budget. Any keeper listed in ``keeper_player_names`` is dropped from both the
    persisted ledger and the incoming Sleeper picks.
    """

    keeper_keys = {
        normalize_player_name(name) for name in keeper_player_names if name
    }

    persisted_sales = list(draft_store.load_sales())
    kept_sales = [
        sale
        for sale in persisted_sales
        if normalize_player_name(sale.player_name) not in keeper_keys
    ]
    removed_keeper_rows = len(persisted_sales) - len(kept_sales)
    kept_sales = [
        replace(sale, sale_number=index + 1)
        for index, sale in enumerate(kept_sales)
    ]

    official_sales, warnings = parse_sleeper_auction_picks(
        draft_picks=list(draft_picks),
        starting_pool_players=starting_pool_players,
        sleeper_players=dict(sleeper_players),
        managers=managers,
    )
    official_sales = [
        sale
        for sale in official_sales
        if normalize_player_name(sale.player_name) not in keeper_keys
    ]
    reconciliation = reconcile_sleeper_sales(kept_sales, official_sales)
    sales = list(reconciliation.sales)

    # Validate the fully derived state before replacing persistent data.
    live_team_setups = build_live_team_setups(
        starting_team_setups=starting_team_setups,
        sales=sales,
    )
    available_players = filter_sold_players(starting_pool_players, sales)
    if reconciliation.changes or removed_keeper_rows:
        draft_store.replace_sales(sales)

    warnings = list(warnings)
    if removed_keeper_rows:
        warnings.append(
            "Removed {0} keeper(s) that had been recorded as auction "
            "sales.".format(removed_keeper_rows)
        )

    return DraftRecoveryResult(
        sales=tuple(sales),
        live_team_setups=live_team_setups,
        available_players=tuple(available_players),
        changes=reconciliation.changes,
        warnings=tuple(warnings),
    )
