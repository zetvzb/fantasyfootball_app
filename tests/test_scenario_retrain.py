import json
from pathlib import Path
from types import SimpleNamespace

from src.scenario_retrain import build_live_training_rows, retrain_with_live_draft

CANONICAL = Path("data/ml_pipeline/canonical")


def _teams():
    return {
        f"Bishop_{name}": SimpleNamespace(
            manager_id=f"Bishop_{name}",
            starting_auction_cash=300,
            auction_cash=300,
            starting_open_roster_spots=13,
            open_roster_spots=13,
            minimum_auction_bid=1,
        )
        for name in ("Zach", "Troy", "Pete", "Fritz")
    }


def _sales():
    rows = [
        ("Bijan Robinson", "RB", "Bishop_Zach", 60),
        ("Ja Marr Chase", "WR", "Bishop_Troy", 65),
        ("Unranked Guy", "WR", "Bishop_Pete", 3),
    ]
    return [
        SimpleNamespace(sale_number=i + 1, player_name=n, position=p, manager_id=m, price=pr)
        for i, (n, p, m, pr) in enumerate(rows)
    ]


def _fp_index():
    return {
        "bijan robinson": SimpleNamespace(half_ecr=2.0, half_position_rank=1.0),
        "ja marr chase": SimpleNamespace(half_ecr=1.0, half_position_rank=1.0),
    }


def test_live_rows_replay_state_and_skip_unranked():
    rows = build_live_training_rows(
        _sales(), _teams(), _fp_index(), league_key="bishop_sycamore_2026", season=2026
    )
    assert len(rows) == 2  # the unranked sale is dropped
    first = rows[0]
    assert first["team_cash_before"] == 300
    assert first["auction_stage"] == 0.0  # first sale
    assert rows[1]["team_cash_before"] == 300  # different manager, still full


def test_retrain_appends_live_rows_and_rewrites_artifact(tmp_path):
    artifact = tmp_path / "model.joblib"
    metadata = tmp_path / "model.metadata.json"
    result = retrain_with_live_draft(
        _sales(),
        _teams(),
        _fp_index(),
        league_key="bishop_sycamore_2026",
        season=2026,
        canonical_dir=CANONICAL,
        artifact_path=artifact,
        metadata_path=metadata,
    )
    assert artifact.is_file()
    assert result.live_rows == 2
    assert result.historical_rows == 574
    payload = json.loads(metadata.read_text())
    assert payload["training_row_count"] == 576
    assert payload["live_partial_draft_rows"] == 2
