from types import SimpleNamespace

import pytest

from src.fantasypros_health import validate_fantasypros_data


def test_fantasypros_health_requires_and_reports_usable_data():
    health = validate_fantasypros_data(
        {"players": [{"id": 1}]},
        {"players": [{"player_id": 1}]},
        {"players": [{"fpid": 1}], "public_api_limited": True},
        [SimpleNamespace(half_ecr=1, dynasty_ecr=2)],
        [SimpleNamespace(custom_points=100)],
    )
    assert health.usable
    assert health.current_ecr_count == 1
    assert "1 projections (1 scored)" in health.summary
    assert health.api_limited
    assert "public API tier limited" in health.summary


def test_fantasypros_health_rejects_silent_empty_payloads():
    with pytest.raises(ValueError, match="no usable"):
        validate_fantasypros_data({}, {}, {}, [], [])
