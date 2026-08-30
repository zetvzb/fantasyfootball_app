from src.auction_pool import AuctionPlayer
from src.draft_recovery import recover_draft_state
from src.draft_setup import TeamDraftSetup
from src.draft_store import DraftStore
from src.league_profile import ManagerIdentity
from src.live_draft import LiveAuctionSale


def _player(player_id, name, position="WR"):
    return AuctionPlayer(player_id, name, position, None, None, True)


def test_restart_reconciles_store_and_rebuilds_current_draft_state(tmp_path):
    path = tmp_path / "draft.db"
    store = DraftStore(str(path), "league", "draft", 2026)
    store.add_sale(LiveAuctionSale(1, "First", "WR", "wrong", 10))
    teams = {
        "manager": TeamDraftSetup(
            manager_id="manager",
            pre_keeper_budget=100,
            roster_size=3,
            entering_auction_cash=100,
        )
    }
    pool = [_player("p1", "First"), _player("p2", "Second")]
    managers = {
        "manager": ManagerIdentity("manager", sleeper_roster_id=1)
    }
    picks = [
        {"pick_no": 1, "player_id": "p1", "roster_id": 1,
         "metadata": {"amount": 20}},
        {"pick_no": 2, "player_id": "p2", "roster_id": 1,
         "metadata": {"amount": 15}},
    ]

    recovered = recover_draft_state(
        draft_store=store,
        draft_picks=picks,
        starting_team_setups=teams,
        starting_pool_players=pool,
        sleeper_players={},
        managers=managers,
    )

    assert [(sale.player_name, sale.price) for sale in recovered.sales] == [
        ("First", 20), ("Second", 15)
    ]
    assert recovered.live_team_setups["manager"].live_cash == 65
    assert recovered.live_team_setups["manager"].open_roster_spots == 1
    assert recovered.available_players == ()
    assert len(recovered.changes) == 2

    restarted = DraftStore(str(path), "league", "draft", 2026)
    repeated = recover_draft_state(
        draft_store=restarted,
        draft_picks=picks,
        starting_team_setups=teams,
        starting_pool_players=pool,
        sleeper_players={},
        managers=managers,
    )
    assert repeated.changes == ()
    assert restarted.sale_count() == 2


def test_keeper_players_are_purged_from_the_sales_ledger(tmp_path):
    path = tmp_path / "draft.db"
    store = DraftStore(str(path), "league", "draft", 2026)
    # A keeper that slipped in as an auction sale, plus a real sale.
    store.add_sale(LiveAuctionSale(1, "Kept Guy", "RB", "manager", 86, source="sleeper"))
    store.add_sale(LiveAuctionSale(2, "Bought Guy", "WR", "manager", 12))
    teams = {
        "manager": TeamDraftSetup(
            manager_id="manager",
            pre_keeper_budget=100,
            roster_size=3,
            entering_auction_cash=100,
        )
    }
    pool = [_player("p2", "Bought Guy")]
    managers = {"manager": ManagerIdentity("manager", sleeper_roster_id=1)}

    recovered = recover_draft_state(
        draft_store=store,
        draft_picks=[],
        starting_team_setups=teams,
        starting_pool_players=pool,
        sleeper_players={},
        managers=managers,
        keeper_player_names=["Kept Guy"],
    )

    assert [s.player_name for s in recovered.sales] == ["Bought Guy"]
    assert [s.sale_number for s in recovered.sales] == [1]
    assert any("keeper" in w.lower() for w in recovered.warnings)
    assert store.sale_count() == 1  # the purge was persisted
