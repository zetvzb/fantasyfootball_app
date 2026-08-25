from types import SimpleNamespace

import pytest

from src.strategy_profile import (
    STRATEGY_PRESET_WEIGHTS,
    StrategyMode,
    StrategyProfile,
    StrategyProfileStore,
)


def _league_profile(current_weight=0.60, future_weight=0.40):
    return SimpleNamespace(
        league_key="league-a",
        model=SimpleNamespace(
            current_season_weight=current_weight,
            future_value_weight=future_weight,
        ),
    )


def test_strategy_modes_have_explicit_labels_and_directional_presets():
    win_now = StrategyProfile.for_mode(
        "league",
        "user",
        StrategyMode.WIN_NOW,
    )
    hybrid = StrategyProfile.for_mode(
        "league",
        "user",
        StrategyMode.HYBRID,
    )
    win_later = StrategyProfile.for_mode(
        "league",
        "user",
        StrategyMode.WIN_LATER,
    )

    assert [mode.label for mode in StrategyMode] == [
        "Win Now",
        "Hybrid",
        "Win Later",
    ]
    assert win_now.current_weight > hybrid.current_weight
    assert hybrid.current_weight > win_later.current_weight
    assert STRATEGY_PRESET_WEIGHTS[StrategyMode.HYBRID] == (0.50, 0.50)


def test_first_use_preserves_existing_league_model_weights():
    profile = StrategyProfile.from_league_defaults(
        _league_profile(current_weight=0.60, future_weight=0.40),
        user_key="user-1",
    )

    assert profile.mode is StrategyMode.HYBRID
    assert profile.current_weight == pytest.approx(0.60)
    assert profile.future_weight == pytest.approx(0.40)


def test_current_and_future_weights_are_configurable_and_complementary():
    original = StrategyProfile.for_mode(
        "league",
        "user",
        StrategyMode.WIN_NOW,
    )

    customized = original.with_current_weight(0.65)

    assert customized.mode is StrategyMode.WIN_NOW
    assert customized.current_weight == pytest.approx(0.65)
    assert customized.future_weight == pytest.approx(0.35)


def test_invalid_strategy_weights_are_rejected():
    with pytest.raises(ValueError, match="must total 1.0"):
        StrategyProfile(
            league_key="league",
            user_key="user",
            mode=StrategyMode.HYBRID,
            current_weight=0.7,
            future_weight=0.4,
        )


def test_profiles_persist_across_store_instances(tmp_path):
    profile = StrategyProfile(
        league_key="league-a",
        user_key="user-1",
        mode=StrategyMode.WIN_LATER,
        current_weight=0.30,
        future_weight=0.70,
    )
    StrategyProfileStore(tmp_path).save(profile)

    restarted_store = StrategyProfileStore(tmp_path)

    assert restarted_store.load("league-a", "user-1") == profile


def test_profile_storage_is_isolated_by_league_and_user(tmp_path):
    store = StrategyProfileStore(tmp_path)
    first = StrategyProfile.for_mode(
        "league-a",
        "user-1",
        StrategyMode.WIN_NOW,
    )
    other_league = StrategyProfile.for_mode(
        "league-b",
        "user-1",
        StrategyMode.HYBRID,
    )
    other_user = StrategyProfile.for_mode(
        "league-a",
        "user-2",
        StrategyMode.WIN_LATER,
    )

    for profile in (first, other_league, other_user):
        store.save(profile)

    assert store.load("league-a", "user-1") == first
    assert store.load("league-b", "user-1") == other_league
    assert store.load("league-a", "user-2") == other_user
    assert len(list(tmp_path.glob("*.json"))) == 3


def test_loading_does_not_create_storage_for_inactive_or_new_identity(tmp_path):
    store = StrategyProfileStore(tmp_path / "profiles")

    assert store.load("league", "user") is None
    assert not store.root.exists()


def test_pre_draft_selector_exposes_and_saves_custom_profile(monkeypatch):
    from src.views import pre_draft

    class RecordingStore:
        def __init__(self):
            self.saved = []

        def save(self, profile):
            self.saved.append(profile)

    class FakeStreamlit:
        def __init__(self):
            self.session_state = {
                "strategy_mode": StrategyMode.WIN_LATER,
                "strategy_current_weight": 35,
            }
            self.selectbox_options = None

        def markdown(self, unused_text):
            return None

        def columns(self, unused_count):
            return self, self

        def selectbox(self, unused_label, options, **unused_kwargs):
            self.selectbox_options = options

        def slider(self, unused_label, **unused_kwargs):
            return None

        def caption(self, unused_text):
            return None

        def warning(self, unused_text):
            return None

        def rerun(self):
            return None

    fake_streamlit = FakeStreamlit()
    store = RecordingStore()
    context = SimpleNamespace(
        strategy_profile=StrategyProfile.from_league_defaults(
            _league_profile(),
            user_key="user-1",
        ),
        strategy_profile_store=store,
        runtime_identity=SimpleNamespace(
            private_key=lambda name: name,
        ),
        private_state_access=SimpleNamespace(
            save_strategy=lambda target_store, profile: target_store.save(profile),
        ),
    )
    monkeypatch.setattr(pre_draft, "st", fake_streamlit)

    pre_draft._render_strategy_profile_selector(context)

    assert fake_streamlit.selectbox_options == list(StrategyMode)
    assert store.saved[0].mode is StrategyMode.WIN_LATER
    assert store.saved[0].current_weight == pytest.approx(0.35)
    assert store.saved[0].future_weight == pytest.approx(0.65)
    assert context.strategy_profile == store.saved[0]
