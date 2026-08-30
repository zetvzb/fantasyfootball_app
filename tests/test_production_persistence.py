from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from src.draft_store import DraftStore
from src.live_draft import LiveAuctionSale
from src.production_persistence import (
    BackgroundCheckpointer,
    DurableStateArchive,
    ProductionPersistenceConflict,
    ProductionPersistenceError,
)
from src.recommendation_snapshot import RecommendationSnapshot


class _Response:
    def __init__(self, status_code, content=b"", etag=None):
        self.status_code = status_code
        self.content = content
        self.headers = {} if etag is None else {"ETag": etag}


class _StateObjectSession:
    def __init__(self):
        self.content = None
        self.version = 0

    def get(self, url, headers, timeout):
        del url, headers, timeout
        if self.content is None:
            return _Response(404)
        return _Response(200, self.content, '"{0}"'.format(self.version))

    def put(self, url, data, headers, timeout):
        del url, timeout
        expected = headers.get("If-Match")
        current = None if not self.version else '"{0}"'.format(self.version)
        if expected is not None and expected != current:
            return _Response(412)
        self.content = bytes(data)
        self.version += 1
        return _Response(200, etag='"{0}"'.format(self.version))


def _snapshot():
    return RecommendationSnapshot(
        player_name="Durable Player",
        current_bid=10,
        target_value=15,
        soft_cap=18,
        hard_cap=20,
        decision="BID",
        alternatives=(),
        roster_state={},
        budget_state={},
        inflation_state={},
        context_state={},
        reasons=("durability test",),
        league_key="league",
        user_key="user",
        manager_id="manager",
    )


def test_durable_archive_restores_setup_draft_and_recommendations(tmp_path):
    session = _StateObjectSession()
    first_root = tmp_path / "first"
    setup_path = first_root / "league_setup" / "league.json"
    setup_path.parent.mkdir(parents=True)
    setup_path.write_text('{"source":"manual"}', encoding="utf-8")
    first = DurableStateArchive(
        data_root=first_root,
        state_url="https://state.example/object",
        state_token="secret",
        session=session,
    )
    store = DraftStore(
        str(first_root / "draft_state.db"),
        "league",
        "draft",
        2026,
        checkpoint_callback=first.checkpoint,
    )
    store.add_sale(LiveAuctionSale(1, "Player One", "WR", "manager", 22))
    assert store.add_recommendation_snapshot(_snapshot()) is True
    assert first.checkpoint() is False

    restarted_root = tmp_path / "restarted"
    restarted = DurableStateArchive(
        data_root=restarted_root,
        state_url="https://state.example/object",
        state_token="secret",
        session=session,
    )
    assert restarted.restore() is True
    assert (restarted_root / "league_setup" / "league.json").is_file()
    restarted_store = DraftStore(
        str(restarted_root / "draft_state.db"), "league", "draft", 2026
    )
    assert [sale.player_name for sale in restarted_store.load_sales()] == [
        "Player One"
    ]
    assert [value.player_name for value in restarted_store.load_recommendation_snapshots()] == [
        "Durable Player"
    ]


def test_checkpoint_excludes_a_restore_temp_file_left_by_a_concurrent_restore(tmp_path):
    # restore() writes X.json.restore then atomically replaces X.json --
    # a checkpoint's directory scan must not pick up that momentary temp
    # file the way it already skips .tmp/-wal/-shm/-journal.
    prefs_dir = tmp_path / "planning_preferences"
    prefs_dir.mkdir()
    (prefs_dir / "user.json").write_text("{}")
    (prefs_dir / "user.json.restore").write_text("mid-write")

    session = _StateObjectSession()
    archive = DurableStateArchive(
        data_root=tmp_path,
        state_url="https://state.example/state",
        session=session,
    )
    assert archive.checkpoint()

    with ZipFile(BytesIO(session.content)) as zf:
        names = zf.namelist()
    assert "planning_preferences/user.json" in names
    assert "planning_preferences/user.json.restore" not in names


def test_checkpoint_tolerates_a_file_disappearing_mid_scan(tmp_path):
    # A file present during the directory scan but gone by the time it's
    # actually read (a genuine race with another concurrent writer) must
    # not fail the whole snapshot -- it'll be captured whole next time.
    prefs_dir = tmp_path / "planning_preferences"
    prefs_dir.mkdir()
    stable = prefs_dir / "stable.json"
    stable.write_text('{"ok": true}')
    vanishing = prefs_dir / "vanishing.json"
    vanishing.write_text('{"mid": "write"}')

    session = _StateObjectSession()
    archive = DurableStateArchive(
        data_root=tmp_path,
        state_url="https://state.example/state",
        session=session,
    )

    real_read_bytes = Path.read_bytes

    def flaky_read_bytes(self):
        if self.name == "vanishing.json":
            raise FileNotFoundError(str(self))
        return real_read_bytes(self)

    with patch.object(Path, "read_bytes", flaky_read_bytes):
        assert archive.checkpoint()

    with ZipFile(BytesIO(session.content)) as zf:
        names = zf.namelist()
    assert "planning_preferences/stable.json" in names
    assert "planning_preferences/vanishing.json" not in names


def test_durable_archive_rejects_stale_writer(tmp_path):
    session = _StateObjectSession()
    seed_root = tmp_path / "seed"
    (seed_root / "leagues").mkdir(parents=True)
    (seed_root / "leagues" / "league.json").write_text("one", encoding="utf-8")
    seed = DurableStateArchive(
        data_root=seed_root, state_url="https://state.example/object", session=session
    )
    assert seed.checkpoint() is True

    first = DurableStateArchive(
        data_root=tmp_path / "first", state_url="https://state.example/object", session=session
    )
    second = DurableStateArchive(
        data_root=tmp_path / "second", state_url="https://state.example/object", session=session
    )
    assert first.restore() is True
    assert second.restore() is True
    (first.data_root / "leagues" / "league.json").write_text("first", encoding="utf-8")
    assert first.checkpoint() is True
    (second.data_root / "leagues" / "league.json").write_text("second", encoding="utf-8")
    with pytest.raises(ProductionPersistenceConflict):
        second.checkpoint()


def test_background_checkpointer_coalesces_and_reports_conflict(tmp_path):
    session = _StateObjectSession()
    seed_root = tmp_path / "seed"
    (seed_root / "leagues").mkdir(parents=True)
    (seed_root / "leagues" / "league.json").write_text("one", encoding="utf-8")
    seed = DurableStateArchive(
        data_root=seed_root, state_url="https://state.example/object", session=session
    )
    seed.checkpoint()

    archive = DurableStateArchive(
        data_root=tmp_path / "live",
        state_url="https://state.example/object",
        session=session,
    )
    archive.restore()
    checkpointer = BackgroundCheckpointer(archive, idle_wait=0.05)

    (archive.data_root / "leagues" / "league.json").write_text("two", encoding="utf-8")
    for _ in range(5):
        checkpointer.request()
    checkpointer.flush()
    with ZipFile(BytesIO(session.content)) as zf:
        assert zf.read("leagues/league.json") == b"two"

    # A writer that fell behind surfaces the conflict rather than raising.
    stale = DurableStateArchive(
        data_root=tmp_path / "stale",
        state_url="https://state.example/object",
        session=session,
    )
    stale.restore()
    session.version += 1  # someone else wrote in the meantime
    session.content = session.content
    stale_checkpointer = BackgroundCheckpointer(stale, idle_wait=0.05)
    (stale.data_root / "leagues" / "league.json").write_text("stale", encoding="utf-8")
    stale_checkpointer.request()
    stale_checkpointer.flush()
    assert stale_checkpointer.consume_error() == "conflict"
    assert stale_checkpointer.consume_error() is None


def test_durable_archive_rejects_unsafe_or_unsupported_paths(tmp_path):
    session = _StateObjectSession()
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("../secret", "bad")
    session.content = buffer.getvalue()
    session.version = 1
    durable = DurableStateArchive(
        data_root=tmp_path / "state",
        state_url="https://state.example/object",
        session=session,
    )
    with pytest.raises(ProductionPersistenceError):
        durable.restore()
    assert not (tmp_path / "secret").exists()
