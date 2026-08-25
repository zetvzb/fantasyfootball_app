from src.auction_pool import AuctionPlayer
from src.auction_rehearsal import RehearsalPoll, run_full_auction_rehearsal
from src.draft_setup import TeamDraftSetup
from src.draft_store import DraftStore
from src.historical_replay import PreSaleRecommendation
from src.league_profile import ManagerIdentity
from src.live_draft import LiveAuctionSale


def _player(number, position):
    return AuctionPlayer(
        "p{0}".format(number),
        "Player {0}".format(number),
        position,
        None,
        None,
        True,
    )


def _pick(number, roster_id, amount):
    return {
        "pick_no": number,
        "player_id": "p{0}".format(number),
        "roster_id": roster_id,
        "metadata": {"amount": amount},
    }


def test_full_rehearsal_survives_reconnect_restart_and_replays_every_sale(tmp_path):
    database = tmp_path / "full-rehearsal.db"

    def store_factory():
        return DraftStore(str(database), "league", "draft", 2026)

    store_factory().add_sale(
        LiveAuctionSale(1, "Player 1", "WR", "wrong-team", 5)
    )
    teams = {
        "alpha": TeamDraftSetup(
            "alpha", 50, roster_size=2, entering_auction_cash=50,
        ),
        "beta": TeamDraftSetup(
            "beta", 50, roster_size=2, entering_auction_cash=50,
        ),
    }
    managers = {
        "alpha": ManagerIdentity("alpha", sleeper_roster_id=1),
        "beta": ManagerIdentity("beta", sleeper_roster_id=2),
    }
    pool = [
        _player(1, "WR"),
        _player(2, "RB"),
        _player(3, "QB"),
        _player(4, "TE"),
        _player(5, "WR"),
    ]
    all_picks = (
        _pick(1, 1, 20),
        _pick(2, 2, 18),
        _pick(3, 1, 10),
        _pick(4, 2, 12),
    )
    target_by_player = {
        "Player 1": 19,
        "Player 2": 18,
        "Player 3": 11,
        "Player 4": 10,
    }

    def recommendation_builder(state, nomination):
        target = target_by_player[nomination.player_name]
        return PreSaleRecommendation(
            player_name=nomination.player_name,
            target_value=target,
            soft_cap=target + 2,
            hard_cap=target + 5,
            decision="BUY",
        )

    result = run_full_auction_rehearsal(
        polls=(
            RehearsalPoll(draft_picks=all_picks[:1]),
            RehearsalPoll(reconnect_error="temporary timeout"),
            RehearsalPoll(
                draft_picks=all_picks[:2],
                restart_before_poll=True,
            ),
            RehearsalPoll(draft_picks=all_picks[:2]),
            RehearsalPoll(
                draft_picks=all_picks,
                restart_before_poll=True,
            ),
        ),
        draft_store_factory=store_factory,
        starting_team_setups=teams,
        starting_pool_players=pool,
        sleeper_players={},
        managers=managers,
        recommendation_builder=recommendation_builder,
    )

    assert result.completed is True
    assert result.restart_count == 2
    assert result.reconnect_failure_count == 1
    assert [step.status for step in result.steps] == [
        "RECONCILED",
        "RECONNECT_FAILED",
        "RECONCILED",
        "NO_CHANGE",
        "RECONCILED",
    ]
    assert result.steps[1].persisted_sale_count == 1
    assert [(sale.player_name, sale.manager_id, sale.price, sale.source)
            for sale in result.sales] == [
        ("Player 1", "alpha", 20, "sleeper"),
        ("Player 2", "beta", 18, "sleeper"),
        ("Player 3", "alpha", 10, "sleeper"),
        ("Player 4", "beta", 12, "sleeper"),
    ]
    assert result.live_team_setups["alpha"].live_cash == 20
    assert result.live_team_setups["beta"].live_cash == 20
    assert [player.player_name for player in result.available_players] == [
        "Player 5"
    ]
    assert result.replay is not None
    assert len(result.replay.evaluations) == 4
    assert DraftStore(str(database), "league", "draft", 2026).sale_count() == 4


def test_reconnect_failure_without_later_sales_is_incomplete_and_non_mutating(tmp_path):
    database = tmp_path / "failed-reconnect.db"

    def store_factory():
        return DraftStore(str(database), "league", "draft", 2026)

    teams = {
        "alpha": TeamDraftSetup(
            "alpha", 25, roster_size=1, entering_auction_cash=25,
        )
    }
    result = run_full_auction_rehearsal(
        polls=(RehearsalPoll(reconnect_error="Sleeper offline"),),
        draft_store_factory=store_factory,
        starting_team_setups=teams,
        starting_pool_players=[_player(1, "WR")],
        sleeper_players={},
        managers={"alpha": ManagerIdentity("alpha", sleeper_roster_id=1)},
    )

    assert result.completed is False
    assert result.sales == ()
    assert result.steps[0].persisted_sale_count == 0
    assert store_factory().sale_count() == 0
