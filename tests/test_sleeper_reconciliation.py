from types import SimpleNamespace

from src.draft_store import DraftStore
from src.live_draft import LiveAuctionSale
from src.sleeper_reconciliation import reconcile_sleeper_sales


def _official(player="Player", manager="official", price=25, pick=1):
    return SimpleNamespace(
        pick_no=pick,
        player_name=player,
        position="WR",
        manager_id=manager,
        price=price,
    )


def test_sleeper_overrides_conflicting_provisional_local_sale():
    local = [LiveAuctionSale(1, "Player", "WR", "manual", 20)]
    result = reconcile_sleeper_sales(local, [_official()])

    assert result.sales[0].manager_id == "official"
    assert result.sales[0].price == 25
    assert result.sales[0].source == "sleeper"
    assert result.changes[0].change_type == "CORRECTED"


def test_reconciled_ledger_persists_authority_across_store_restart(tmp_path):
    path = tmp_path / "draft.db"
    store = DraftStore(str(path), "league", "draft", 2026)
    store.add_sale(LiveAuctionSale(1, "Player", "WR", "manual", 20))
    result = reconcile_sleeper_sales(store.load_sales(), [_official()])
    store.replace_sales(list(result.sales))

    restored = DraftStore(str(path), "league", "draft", 2026).load_sales()
    assert [(sale.manager_id, sale.price, sale.source) for sale in restored] == [
        ("official", 25, "sleeper")
    ]
