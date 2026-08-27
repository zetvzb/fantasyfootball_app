from src.league_profile import LeagueProfile, RosterRules
from src.league_registry import LeagueRegistry, delete_league_data
from src.league_setup_data import LeagueSetupData, LeagueSetupStore


def _profile(league_key="test_league"):
    return LeagueProfile(
        league_key=league_key,
        league_name="Test League",
        season=2026,
        source_mode="manual",
        roster=RosterRules(roster_size=5),
    )


def test_delete_league_data_removes_profile_setup_and_draft_state(tmp_path):
    registry = LeagueRegistry(tmp_path / "leagues")
    setup_store = LeagueSetupStore(tmp_path / "league_setup")
    draft_state_directory = tmp_path / "draft_states"
    draft_state_directory.mkdir()

    profile = _profile()
    registry.save(profile)
    setup_store.save(LeagueSetupData(league_key=profile.league_key))

    (draft_state_directory / "test_league_sleeper_123.db").write_text("x")
    (draft_state_directory / "test_league_manual_2026.db").write_text("x")
    (draft_state_directory / "other_league_manual_2026.db").write_text("x")

    removed = delete_league_data(
        league_key=profile.league_key,
        league_registry=registry,
        setup_store=setup_store,
        draft_state_directory=draft_state_directory,
    )

    assert not registry.exists(profile.league_key)
    assert not setup_store.exists(profile.league_key)
    assert not (draft_state_directory / "test_league_sleeper_123.db").exists()
    assert not (draft_state_directory / "test_league_manual_2026.db").exists()
    assert (draft_state_directory / "other_league_manual_2026.db").exists()
    assert "league profile" in removed
    assert "league setup data" in removed
    assert any("draft state database" in item for item in removed)


def test_delete_league_data_is_safe_to_call_when_nothing_exists(tmp_path):
    registry = LeagueRegistry(tmp_path / "leagues")
    setup_store = LeagueSetupStore(tmp_path / "league_setup")
    draft_state_directory = tmp_path / "draft_states"

    removed = delete_league_data(
        league_key="never_existed",
        league_registry=registry,
        setup_store=setup_store,
        draft_state_directory=draft_state_directory,
    )

    assert removed == []


def test_delete_league_data_never_touches_another_leagues_draft_state(tmp_path):
    registry = LeagueRegistry(tmp_path / "leagues")
    setup_store = LeagueSetupStore(tmp_path / "league_setup")
    draft_state_directory = tmp_path / "draft_states"
    draft_state_directory.mkdir()

    registry.save(_profile("league_a"))
    registry.save(_profile("league_b"))
    (draft_state_directory / "league_a_manual_2026.db").write_text("x")
    (draft_state_directory / "league_b_manual_2026.db").write_text("x")

    delete_league_data(
        league_key="league_a",
        league_registry=registry,
        setup_store=setup_store,
        draft_state_directory=draft_state_directory,
    )

    assert not registry.exists("league_a")
    assert registry.exists("league_b")
    assert (draft_state_directory / "league_b_manual_2026.db").exists()
