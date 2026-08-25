from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


def _safe_part(value: str) -> str:
    safe = "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in str(value)
    ).strip("_")
    return safe or "unknown"


def private_state_key(league_key: str, user_key: str, name: str) -> str:
    """Namespace private UI state by both league and current user."""

    return "private::{0}::{1}::{2}".format(
        _safe_part(league_key),
        _safe_part(user_key),
        _safe_part(name),
    )


@dataclass(frozen=True)
class LeagueRuntimeIdentity:
    league_key: str
    sleeper_league_id: Optional[str]
    draft_id: Optional[str]
    season: int


@dataclass(frozen=True)
class UserManagerIdentity:
    user_key: str
    sleeper_user_id: Optional[str]
    manager_id: str
    resolution_source: str
    auth_provider: Optional[str] = None
    authenticated_subject: Optional[str] = None


@dataclass(frozen=True)
class RuntimeIdentity:
    league: LeagueRuntimeIdentity
    current: UserManagerIdentity

    def private_key(self, name: str) -> str:
        return private_state_key(
            self.league.league_key,
            self.current.user_key,
            name,
        )


def resolve_runtime_identity(
    league_profile: Any,
    managers: Mapping[str, Any],
    sleeper_user_id: Optional[str],
    fallback_manager_id: Optional[str] = None,
    authenticated_identity: Optional[Any] = None,
    authenticated_manager_mappings: Optional[Mapping[str, Mapping[str, str]]] = None,
) -> RuntimeIdentity:
    """Resolve a current user to a manager without changing league identity."""

    if authenticated_identity is not None:
        from src.auth_identity import resolve_authenticated_manager

        manager_id = resolve_authenticated_manager(
            league_profile=league_profile,
            managers=managers,
            identity=authenticated_identity,
            external_mappings=authenticated_manager_mappings,
        )
        return RuntimeIdentity(
            league=LeagueRuntimeIdentity(
                league_key=str(league_profile.league_key),
                sleeper_league_id=(
                    str(league_profile.sleeper_league_id)
                    if league_profile.sleeper_league_id is not None
                    else None
                ),
                draft_id=(
                    str(league_profile.sleeper_draft_id)
                    if league_profile.sleeper_draft_id is not None
                    else None
                ),
                season=int(league_profile.season),
            ),
            current=UserManagerIdentity(
                user_key=authenticated_identity.user_key,
                sleeper_user_id=None,
                manager_id=manager_id,
                resolution_source="authenticated_mapping",
                auth_provider=authenticated_identity.provider,
                authenticated_subject=authenticated_identity.subject,
            ),
        )

    normalized_user_id = (
        str(sleeper_user_id) if sleeper_user_id is not None else None
    )
    manager_id = None
    source = "sleeper_user_id"

    if normalized_user_id is not None:
        for candidate_id, identity in managers.items():
            candidate_user_id = getattr(identity, "sleeper_user_id", None)
            if (
                candidate_user_id is not None
                and str(candidate_user_id) == normalized_user_id
            ):
                manager_id = candidate_id
                break

    if manager_id is None and fallback_manager_id in managers:
        manager_id = fallback_manager_id
        source = "single_user_fallback"

    if manager_id is None:
        raise ValueError(
            "Could not resolve the current user to a manager in league {0}.".format(
                league_profile.league_key
            )
        )

    user_key = normalized_user_id or "manager-{0}".format(manager_id)
    return RuntimeIdentity(
        league=LeagueRuntimeIdentity(
            league_key=str(league_profile.league_key),
            sleeper_league_id=(
                str(league_profile.sleeper_league_id)
                if league_profile.sleeper_league_id is not None
                else None
            ),
            draft_id=(
                str(league_profile.sleeper_draft_id)
                if league_profile.sleeper_draft_id is not None
                else None
            ),
            season=int(league_profile.season),
        ),
        current=UserManagerIdentity(
            user_key=user_key,
            sleeper_user_id=normalized_user_id,
            manager_id=str(manager_id),
            resolution_source=source,
        ),
    )
