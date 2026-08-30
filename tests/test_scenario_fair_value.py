import pytest

from src.scenario_fair_value import (
    DEFAULT_ML_WEIGHT,
    blend_fair_value,
    scenario_ml_weight,
    scenario_pricing_enabled,
)


def test_blend_is_weighted_average():
    assert blend_fair_value(30.0, 10.0, ml_weight=0.75) == pytest.approx(25.0)


def test_missing_ml_price_falls_back_to_rankings():
    assert blend_fair_value(None, 12.5, ml_weight=0.9) == 12.5


def test_weight_is_clamped():
    assert blend_fair_value(30.0, 10.0, ml_weight=5.0) == pytest.approx(30.0)
    assert blend_fair_value(30.0, 10.0, ml_weight=-1.0) == pytest.approx(10.0)


def test_env_toggles(monkeypatch):
    monkeypatch.delenv("SCENARIO_ML_PRICING", raising=False)
    assert scenario_pricing_enabled() is True
    monkeypatch.setenv("SCENARIO_ML_PRICING", "0")
    assert scenario_pricing_enabled() is False

    monkeypatch.delenv("SCENARIO_ML_WEIGHT", raising=False)
    assert scenario_ml_weight() == DEFAULT_ML_WEIGHT
    monkeypatch.setenv("SCENARIO_ML_WEIGHT", "0.4")
    assert scenario_ml_weight() == pytest.approx(0.4)
    monkeypatch.setenv("SCENARIO_ML_WEIGHT", "nonsense")
    assert scenario_ml_weight() == DEFAULT_ML_WEIGHT
