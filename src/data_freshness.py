from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Union


class FreshnessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class DataSourceFreshness:
    source: str
    status: FreshnessStatus
    last_refresh: Optional[datetime]
    age_seconds: Optional[int]
    stale_after_seconds: int
    detail: str = ""

    @property
    def age_label(self) -> str:
        if self.age_seconds is None:
            return "unknown"
        if self.age_seconds < 60:
            return "{0}s".format(self.age_seconds)
        if self.age_seconds < 3600:
            return "{0}m".format(self.age_seconds // 60)
        return "{0}h {1}m".format(
            self.age_seconds // 3600,
            (self.age_seconds % 3600) // 60,
        )

    @property
    def threshold_label(self) -> str:
        if self.stale_after_seconds % 3600 == 0:
            return "{0}h".format(self.stale_after_seconds // 3600)
        if self.stale_after_seconds % 60 == 0:
            return "{0}m".format(self.stale_after_seconds // 60)
        return "{0}s".format(self.stale_after_seconds)


def _parse_timestamp(value: Union[str, datetime, None]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def assess_data_freshness(
    source: str,
    last_refresh: Union[str, datetime, None],
    stale_after_seconds: int,
    now: Optional[datetime] = None,
    error: Optional[str] = None,
    available: bool = True,
) -> DataSourceFreshness:
    if stale_after_seconds <= 0:
        raise ValueError("Stale threshold must be positive.")
    parsed = _parse_timestamp(last_refresh)
    if error:
        return DataSourceFreshness(
            source, FreshnessStatus.ERROR, parsed, None,
            stale_after_seconds, str(error),
        )
    if not available or parsed is None:
        return DataSourceFreshness(
            source, FreshnessStatus.UNAVAILABLE, parsed, None,
            stale_after_seconds, "No successful refresh recorded.",
        )
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age = max(0, int((current.astimezone(timezone.utc) - parsed).total_seconds()))
    status = (
        FreshnessStatus.STALE
        if age > stale_after_seconds
        else FreshnessStatus.FRESH
    )
    return DataSourceFreshness(
        source, status, parsed, age, stale_after_seconds,
        "Older than the configured threshold." if status == FreshnessStatus.STALE else "",
    )
