import importlib
import sys

import pytest

from src.app_runtime import (
    DRAFT_HISTORY_VIEW,
    DRAFT_MODE_VIEW,
    LEAGUE_SETUP_VIEW,
    PRE_DRAFT_VIEW,
    build_view_runtime,
    requirements_for_view,
)


def test_view_requirements_do_not_initialize_inactive_integrations():
    setup = requirements_for_view(LEAGUE_SETUP_VIEW)
    pre_draft = requirements_for_view(PRE_DRAFT_VIEW)
    draft = requirements_for_view(DRAFT_MODE_VIEW)
    history = requirements_for_view(DRAFT_HISTORY_VIEW)

    assert setup.setup is True
    assert setup.pre_draft_intelligence is False
    assert setup.live_draft is False
    assert pre_draft.pre_draft_intelligence is True
    assert pre_draft.live_draft is False
    assert draft.live_draft is True
    assert history.history is True
    assert history.setup is False
    assert history.pre_draft_intelligence is False
    assert history.live_draft is False


def test_build_view_runtime_uses_inert_defaults():
    runtime = build_view_runtime(
        ACTIVE_DRAFT_ID="draft-1",
        selected_league=object(),
    )

    assert runtime.ACTIVE_DRAFT_ID == "draft-1"
    assert runtime.context_store is None
    assert runtime.strategy_profile is None
    assert runtime.strategy_profile_store is None
    assert runtime.keeper_recommendations == []
    assert runtime.keeper_trade_candidate_result is None
    assert runtime.college_promotion_recommendation_result is None
    assert runtime.pre_draft_readiness is None
    assert runtime.ranking_ensemble is None
    assert runtime.inflation_v2 is None
    assert runtime.manager_tendency_model is None
    assert runtime.keeper_recommendation_warnings == []
    assert runtime.keeper_optimization_result is None
    assert runtime.SleeperClient is None
    assert runtime.fantasypros_data == {}
    assert runtime.live_team_setups == {}


def test_router_imports_only_selected_view(monkeypatch):
    for module_name in (
        "src.views.league_setup",
        "src.views.pre_draft",
        "src.views.draft_mode",
        "src.views.draft_history",
    ):
        sys.modules.pop(module_name, None)

    router = importlib.reload(importlib.import_module("src.views.router"))
    imported = []
    real_import = router.import_module

    def recording_import(module_path):
        imported.append(module_path)
        return real_import(module_path)

    monkeypatch.setattr(router, "import_module", recording_import)

    renderer = router.load_view_renderer(DRAFT_HISTORY_VIEW)

    assert renderer.__name__ == "render_draft_history_view"
    assert imported == ["src.views.draft_history"]
    assert "src.views.draft_mode" not in sys.modules
    assert "src.views.pre_draft" not in sys.modules
    assert "src.views.league_setup" not in sys.modules


def test_unknown_view_requirements_fail_explicitly():
    with pytest.raises(ValueError, match="Unknown app view"):
        requirements_for_view("missing")
