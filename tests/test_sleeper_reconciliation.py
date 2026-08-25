from types import SimpleNamespace

from src.draft_store import DraftStore
from src.auction_pool import AuctionPlayer
from src.draft_setup import TeamDraftSetup
from src.league_profile import ManagerIdentity
from src.live_draft import LiveAuctionSale
from src.sleeper_reconciliation import reconcile_sleeper_sales
from src.sleeper_sync import sync_next_sleeper_sale


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


def test_repeated_sleeper_poll_is_idempotent(tmp_path):
    store = DraftStore(str(tmp_path / "draft.db"), "league", "draft", 2026)
    team_setups = {
        "manager": TeamDraftSetup(
            manager_id="manager",
            pre_keeper_budget=200,
            roster_size=10,
            entering_auction_cash=200,
        )
    }
    pool = [
        AuctionPlayer("player-1", "Player", "WR", "MIN", "Active", True)
    ]
    managers = {
        "manager": ManagerIdentity(manager_id="manager", sleeper_roster_id=1)
    }
    picks = [
        {
            "pick_no": 1,
            "player_id": "player-1",
            "roster_id": 1,
            "metadata": {"amount": "25"},
        }
    ]

    first = sync_next_sleeper_sale(
        picks, team_setups, pool, {}, managers, [], {}, store
    )
    second = sync_next_sleeper_sale(
        picks, team_setups, pool, {}, managers, store.load_sales(), {}, store
    )

    assert first.status == "imported"
    assert second.status == "no_change"
    assert store.sale_count() == 1
    assert store.load_sales()[0].source == "sleeper"


def test_repeated_poll_after_authoritative_correction_is_idempotent(tmp_path):
    store = DraftStore(str(tmp_path / "draft.db"), "league", "draft", 2026)
    store.add_sale(LiveAuctionSale(1, "Player", "WR", "local", 15))
    team_setups = {
        "official": TeamDraftSetup(
            manager_id="official",
            pre_keeper_budget=200,
            roster_size=10,
            entering_auction_cash=200,
        )
    }
    pool = [AuctionPlayer("p1", "Player", "WR", None, None, True)]
    managers = {
        "official": ManagerIdentity("official", sleeper_roster_id=1)
    }
    picks = [{
        "pick_no": 1,
        "player_id": "p1",
        "roster_id": 1,
        "metadata": {"amount": 25},
    }]

    corrected = sync_next_sleeper_sale(
        picks, team_setups, pool, {}, managers, store.load_sales(), {}, store
    )
    repeated = sync_next_sleeper_sale(
        picks, team_setups, pool, {}, managers, store.load_sales(), {}, store
    )

    assert corrected.status == "reconciled"
    assert repeated.status == "no_change"
    assert store.sale_count() == 1
