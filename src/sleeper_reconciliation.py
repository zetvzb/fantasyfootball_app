from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from src.auction_pool import normalize_player_name
from src.live_draft import LiveAuctionSale


@dataclass(frozen=True)
class ReconciliationChange:
    player_name: str
    change_type: str
    detail: str


@dataclass(frozen=True)
class SleeperReconciliationResult:
    sales: Tuple[LiveAuctionSale, ...]
    changes: Tuple[ReconciliationChange, ...]


def reconcile_sleeper_sales(
    local_sales: Sequence[LiveAuctionSale],
    sleeper_sales: Sequence[object],
) -> SleeperReconciliationResult:
    """Overlay completed Sleeper results onto provisional local state."""

    reconciled = list(local_sales)
    index = {
        normalize_player_name(sale.player_name): offset
        for offset, sale in enumerate(reconciled)
    }
    changes = []
    for sleeper_sale in sorted(
        sleeper_sales,
        key=lambda sale: int(getattr(sale, "pick_no", 0)),
    ):
        key = normalize_player_name(sleeper_sale.player_name)
        offset = index.get(key)
        if offset is None:
            sale = LiveAuctionSale(
                sale_number=len(reconciled) + 1,
                player_name=sleeper_sale.player_name,
                position=sleeper_sale.position,
                manager_id=sleeper_sale.manager_id,
                price=int(sleeper_sale.price),
                source="sleeper",
            )
            reconciled.append(sale)
            index[key] = len(reconciled) - 1
            changes.append(
                ReconciliationChange(
                    sale.player_name,
                    "IMPORTED",
                    "Imported completed Sleeper sale.",
                )
            )
            continue

        local = reconciled[offset]
        agrees = (
            local.manager_id == sleeper_sale.manager_id
            and int(local.price) == int(sleeper_sale.price)
            and local.position == sleeper_sale.position
        )
        if agrees and local.source == "sleeper":
            continue
        reconciled[offset] = LiveAuctionSale(
            sale_number=local.sale_number,
            player_name=sleeper_sale.player_name,
            position=sleeper_sale.position,
            manager_id=sleeper_sale.manager_id,
            price=int(sleeper_sale.price),
            modeled_market_value=local.modeled_market_value,
            do_not_exceed=local.do_not_exceed,
            source="sleeper",
        )
        changes.append(
            ReconciliationChange(
                sleeper_sale.player_name,
                "CONFIRMED" if agrees else "CORRECTED",
                (
                    "Sleeper confirmed the provisional local sale."
                    if agrees
                    else "Sleeper replaced conflicting local manager/price state."
                ),
            )
        )

    return SleeperReconciliationResult(tuple(reconciled), tuple(changes))
