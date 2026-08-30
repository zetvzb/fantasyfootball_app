from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional


class PrivateStateIsolationError(PermissionError):
    pass


@dataclass(frozen=True)
class PrivateStateScope:
    league_key: str
    user_key: str
    manager_id: str

    @classmethod
    def from_runtime_identity(cls, runtime_identity: Any) -> "PrivateStateScope":
        return cls(
            league_key=str(runtime_identity.league.league_key),
            user_key=str(runtime_identity.current.user_key),
            manager_id=str(runtime_identity.current.manager_id),
        )

    def require(
        self,
        *,
        league_key: str,
        user_key: str,
        manager_id: Optional[str] = None,
    ) -> None:
        requested = (str(league_key), str(user_key))
        allowed = (self.league_key, self.user_key)
        if requested != allowed:
            raise PrivateStateIsolationError(
                "Private state belongs to another league or user."
            )
        if manager_id is not None and str(manager_id) != self.manager_id:
            raise PrivateStateIsolationError(
                "Private state belongs to another manager."
            )

    def require_resource(self, resource: Any) -> None:
        self.require(
            league_key=str(getattr(resource, "league_key", "")),
            user_key=str(getattr(resource, "user_key", "")),
            manager_id=(
                str(getattr(resource, "manager_id"))
                if getattr(resource, "manager_id", None) is not None
                else None
            ),
        )


@dataclass(frozen=True)
class PrivateStateAccess:
    """Only exposes private resources for one resolved runtime identity."""

    scope: PrivateStateScope

    @classmethod
    def from_runtime_identity(cls, runtime_identity: Any) -> "PrivateStateAccess":
        return cls(PrivateStateScope.from_runtime_identity(runtime_identity))

    def load_strategy(self, store: Any) -> Optional[Any]:
        result = store.load(self.scope.league_key, self.scope.user_key)
        if result is not None:
            self.scope.require_resource(result)
        return result

    def save_strategy(self, store: Any, profile: Any) -> Any:
        self.scope.require_resource(profile)
        return store.save(profile)

    def load_my_guys(self, store: Any) -> Optional[Any]:
        result = store.load(self.scope.league_key, self.scope.user_key)
        if result is not None:
            self.scope.require_resource(result)
        return result

    def save_my_guys(self, store: Any, preferences: Any) -> Any:
        self.scope.require_resource(preferences)
        return store.save(preferences)

    def load_planning(self, store: Any) -> Optional[Any]:
        result = store.load(
            self.scope.league_key,
            self.scope.user_key,
            self.scope.manager_id,
        )
        if result is not None:
            self.scope.require_resource(result)
        return result

    def save_planning(self, store: Any, preferences: Any) -> Any:
        self.scope.require_resource(preferences)
        return store.save(preferences)

    def load_recommendation_history(self, draft_store: Any) -> List[Any]:
        return draft_store.load_private_recommendation_snapshots(
            self.scope.league_key,
            self.scope.user_key,
            self.scope.manager_id,
        )

    def load_scenario_blend_setting(self, draft_store: Any) -> Optional[Any]:
        return draft_store.load_scenario_blend_setting(
            self.scope.league_key, self.scope.user_key, self.scope.manager_id
        )

    def save_scenario_blend_setting(self, draft_store: Any, setting: Any) -> Any:
        self.scope.require_resource(setting)
        return draft_store.save_scenario_blend_setting(setting)
