from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Sequence, Tuple


class IntelligenceSource(str, Enum):
    SLEEPER = "Sleeper"
    RANKINGS_PROJECTIONS = "Rankings + projections"
    NEWS_INJURIES = "News + injuries"
    DEPTH_USAGE_CONTEXT = "Depth + usage/context"


@dataclass(frozen=True)
class RefreshPlan:
    sources: Tuple[IntelligenceSource, ...]
    cache_keys: Tuple[str, ...]

    @property
    def empty(self) -> bool:
        return not self.sources


CACHE_KEYS = {
    IntelligenceSource.SLEEPER: ("sleeper",),
    IntelligenceSource.RANKINGS_PROJECTIONS: ("fantasypros",),
    IntelligenceSource.NEWS_INJURIES: ("context", "targeted_context"),
    IntelligenceSource.DEPTH_USAGE_CONTEXT: (
        "sleeper", "context", "targeted_context"
    ),
}


def build_refresh_plan(
    source_statuses: Mapping[IntelligenceSource, str],
    selected_sources: Sequence[IntelligenceSource] = (),
) -> RefreshPlan:
    selected = set(selected_sources)
    sources = tuple(
        source for source in IntelligenceSource
        if source in selected
        or str(source_statuses.get(source, "UNAVAILABLE")).upper()
        in {"STALE", "ERROR", "UNAVAILABLE"}
    )
    cache_keys = []
    for source in sources:
        for key in CACHE_KEYS[source]:
            if key not in cache_keys:
                cache_keys.append(key)
    return RefreshPlan(sources=sources, cache_keys=tuple(cache_keys))


def execute_refresh_plan(
    plan: RefreshPlan,
    clearers: Mapping[str, Callable[[], None]],
) -> Tuple[str, ...]:
    cleared = []
    for key in plan.cache_keys:
        clearer = clearers.get(key)
        if clearer is None:
            raise KeyError("Missing cache clearer: {0}".format(key))
        clearer()
        cleared.append(key)
    return tuple(cleared)
