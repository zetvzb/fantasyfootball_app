from types import SimpleNamespace

import pytest

from src.runtime_identity import (
    private_state_key,
    resolve_runtime_identity,
)


def _profile(league_key="league-a"):
    return SimpleNamespace(
        league_key=league_key,
        sleeper_league_id="sleeper-{0}".format(league_key),
        sleeper_draft_id="draft-{0}".format(league_key),
        season=2026,
    )


def _manager(user_id):
    return SimpleNamespace(sleeper_user_id=user_id)


def test_league_and_current_user_manager_identity_are_separate():
    identity = resolve_runtime_identity(
        league_profile=_profile("league-a"),
        managers={
            "manager-a": _manager("user-1"),
            "manager-b": _manager("user-2"),
        },
        sleeper_user_id="user-2",
    )

    assert identity.league.league_key == "league-a"
    assert identity.league.sleeper_league_id == "sleeper-league-a"
    assert identity.current.user_key == "user-2"
    assert identity.current.manager_id == "manager-b"
    assert identity.current.resolution_source == "sleeper_user_id"


def test_private_state_is_isolated_by_both_league_and_user():
    first = private_state_key("league-a", "user-1", "active_view")
    other_league = private_state_key("league-b", "user-1", "active_view")
    other_user = private_state_key("league-a", "user-2", "active_view")

    assert len({first, other_league, other_user}) == 3
    assert first == "private::league-a::user-1::active_view"


def test_single_user_fallback_preserves_legacy_manager_behavior():
    identity = resolve_runtime_identity(
        league_profile=_profile(),
        managers={"legacy-manager": _manager(None)},
        sleeper_user_id=None,
        fallback_manager_id="legacy-manager",
    )

    assert identity.current.manager_id == "legacy-manager"
    assert identity.current.user_key == "manager-legacy-manager"
    assert identity.current.resolution_source == "single_user_fallback"


def test_unresolved_user_does_not_silently_select_another_manager():
    with pytest.raises(ValueError, match="Could not resolve"):
        resolve_runtime_identity(
            league_profile=_profile(),
            managers={"manager-a": _manager("user-1")},
            sleeper_user_id="missing-user",
        )
