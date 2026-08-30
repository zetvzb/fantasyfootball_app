from types import SimpleNamespace

from src.scenario_price_inference import (
    ScenarioPriceInferenceService,
    build_live_feature_row,
    save_model_artifact,
)
from src.scenario_price_model import train_quantile_models


def _training_rows():
    rows = []
    for index in range(40):
        rows.append(
            {
                "historical_overall_rank": index + 1,
                "position": "WR" if index % 2 else "RB",
                "league_key": "league-a",
                "auction_stage": index / 40.0,
                "team_cash_before": 300 - index,
                "team_open_spots_before": 12,
                "team_legal_max_before": 250,
                "league_cash_before": 3000 - index * 10,
                "league_open_spots_before": 120 - index,
                "league_discretionary_cash_before": 2500 - index * 10,
                "position_sales_before": index // 2,
                "position_average_price_before": 20,
                "position_spend_before": index * 10,
                "winning_price": max(1, 60 - index),
            }
        )
    return rows


def test_versioned_artifact_round_trip_and_legal_bound(tmp_path):
    rows = _training_rows()
    models = train_quantile_models(rows)
    path = tmp_path / "model.joblib"
    metadata = save_model_artifact(path, models, rows)

    live_row = dict(rows[0], team_legal_max_before=25)
    prediction = ScenarioPriceInferenceService(path).predict(live_row)

    assert prediction is not None
    assert prediction.model_version == metadata["model_version"]
    assert 1 <= prediction.low <= prediction.predicted_price <= prediction.high <= 25
    assert prediction.to_dict()["mode"] == "shadow"


def test_missing_artifact_is_an_optional_noop(tmp_path):
    assert ScenarioPriceInferenceService(tmp_path / "missing.joblib").predict({}) is None


def test_live_feature_adapter_uses_pre_sale_state():
    sales = (
        SimpleNamespace(position="WR", price=20),
        SimpleNamespace(position="RB", price=30),
        SimpleNamespace(position="WR", price=40),
    )
    context = SimpleNamespace(
        live_sales=sales,
        live_open_spots=97,
        live_total_cash=2400,
        live_discretionary=2303,
        my_live_setup=SimpleNamespace(live_cash=250, open_roster_spots=10),
        runtime_identity=SimpleNamespace(
            league=SimpleNamespace(league_key="custom-league")
        ),
    )
    state = SimpleNamespace(
        fp=SimpleNamespace(half_ecr=12.5),
        recommendation=SimpleNamespace(position="WR", legal_max_bid=241),
    )

    row = build_live_feature_row(context, state)

    assert row["league_key"] == "custom-league"
    assert row["historical_overall_rank"] == 12.5
    assert row["position_sales_before"] == 2
    assert row["position_average_price_before"] == 30
    assert row["auction_stage"] == 0.03
