from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional


class OptionalFeedStatus(str, Enum):
    FRESH = "FRESH"
    FALLBACK = "FALLBACK"


@dataclass(frozen=True)
class OptionalFeedResult:
    source: str
    status: OptionalFeedStatus
    data: Any
    error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.status is OptionalFeedStatus.FRESH


def load_optional_feed(
    source: str,
    fetcher: Callable[[], Any],
    fallback: Any,
    validator: Optional[Callable[[Any], bool]] = None,
) -> OptionalFeedResult:
    """Fetch optional data without exposing mutable fallback state to failure."""

    try:
        data = fetcher()
        if validator is not None and not validator(data):
            raise ValueError("Response failed validation.")
        return OptionalFeedResult(source, OptionalFeedStatus.FRESH, data)
    except Exception as error:
        return OptionalFeedResult(
            source=source,
            status=OptionalFeedStatus.FALLBACK,
            data=copy.deepcopy(fallback),
            error=str(error),
        )


def commit_optional_feed(
    result: OptionalFeedResult,
    writer: Callable[[Any], None],
) -> bool:
    """Persist only a successfully fetched and validated optional response."""

    if not result.available:
        return False
    writer(result.data)
    return True
