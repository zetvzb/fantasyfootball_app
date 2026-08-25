from src.draft_store import DraftStore
from src.live_draft import LiveAuctionSale
from src.optional_feed import (
    OptionalFeedStatus,
    commit_optional_feed,
    load_optional_feed,
)


def test_failed_optional_feed_returns_isolated_fallback_without_commit():
    fallback = {"players": ["cached"]}
    writes = []
    result = load_optional_feed(
        "rankings",
        lambda: (_ for _ in ()).throw(RuntimeError("offline")),
        fallback,
    )

    result.data["players"].append("local change")
    assert result.status is OptionalFeedStatus.FALLBACK
    assert result.error == "offline"
    assert fallback == {"players": ["cached"]}
    assert not commit_optional_feed(result, writes.append)
    assert writes == []


def test_invalid_optional_response_does_not_corrupt_auction_ledger(tmp_path):
    store = DraftStore(str(tmp_path / "draft.db"), "league", "draft", 2026)
    store.add_sale(LiveAuctionSale(1, "Player", "WR", "manager", 20))
    before = store.load_sales()

    result = load_optional_feed(
        "news",
        lambda: {"unexpected": True},
        [],
        validator=lambda value: isinstance(value, list),
    )
    commit_optional_feed(result, lambda _: store.reset_sales())

    assert result.status is OptionalFeedStatus.FALLBACK
    assert store.load_sales() == before


def test_successful_optional_feed_can_be_committed():
    writes = []
    result = load_optional_feed("depth", lambda: ["fresh"], [])
    assert commit_optional_feed(result, writes.append)
    assert writes == [["fresh"]]
