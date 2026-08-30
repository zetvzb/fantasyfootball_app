import pytest

from src.draft_store import DraftStore
from src.price_thresholds import LivePriceThresholds
from src.private_state import PrivateStateIsolationError, PrivateStateScope
from src.scenario_blend_preview import ScenarioBlendPreview
from src.scenario_blend_rollout import (
    ScenarioBlendSetting,
    apply_guarded_blend,
)
from src.scenario_model_promotion import (
    PromotionReadiness,
    PromotionStatus,
)


def _readiness(status):
    return PromotionReadiness(status=status, gates=(), recommendation="test")


def _setting(version="model-v1", enabled=True):
    return ScenarioBlendSetting(
        league_key="league", user_key="user", manager_id="manager",
        enabled=enabled, approved_model_version=version,
    )


def test_guarded_blend_requires_ready_status_and_matching_model():
    base = LivePriceThresholds(20, 25, 30, "base")
    preview = ScenarioBlendPreview(23, 28, 33, 0.25)

    applied = apply_guarded_blend(
        base, preview, _setting(), _readiness(PromotionStatus.READY), "model-v1"
    )
    not_ready = apply_guarded_blend(
        base, preview, _setting(), _readiness(PromotionStatus.SHADOW), "model-v1"
    )
    mismatch = apply_guarded_blend(
        base, preview, _setting(), _readiness(PromotionStatus.READY), "model-v2"
    )

    assert applied.applied is True
    assert applied.thresholds.target_value == 23
    assert not_ready.thresholds is base and not_ready.applied is False
    assert mismatch.thresholds is base and mismatch.applied is False


def test_private_rollout_setting_survives_restart_and_is_isolated(tmp_path):
    path = tmp_path / "draft.db"
    scope = PrivateStateScope("league", "user", "manager")
    store = DraftStore(str(path), "league", "draft", 2026)
    store.bind_private_scope(scope)
    saved = store.save_scenario_blend_setting(_setting())
    assert saved.enabled is True

    restarted = DraftStore(str(path), "league", "draft", 2026)
    restarted.bind_private_scope(scope)
    loaded = restarted.load_scenario_blend_setting("league", "user", "manager")
    assert loaded is not None
    assert loaded.approved_model_version == "model-v1"

    with pytest.raises(PrivateStateIsolationError):
        restarted.load_scenario_blend_setting("league", "other-user", "manager")


def test_persisted_weight_is_capped_at_twenty_five_percent(tmp_path):
    store = DraftStore(str(tmp_path / "draft.db"), "league", "draft", 2026)
    saved = store.save_scenario_blend_setting(
        ScenarioBlendSetting("league", "user", "manager", True, 0.9, "model")
    )
    assert saved.ml_weight == 0.25
