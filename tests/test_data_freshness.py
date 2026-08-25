from datetime import datetime, timedelta, timezone

import pytest

from src.data_freshness import FreshnessStatus, assess_data_freshness


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def test_freshness_reports_age_and_threshold_boundary():
    fresh = assess_data_freshness(
        "Sleeper", NOW - timedelta(seconds=300), 300, now=NOW
    )
    stale = assess_data_freshness(
        "Sleeper", NOW - timedelta(seconds=301), 300, now=NOW
    )
    assert fresh.status == FreshnessStatus.FRESH
    assert fresh.age_label == "5m"
    assert fresh.threshold_label == "5m"
    assert stale.status == FreshnessStatus.STALE


def test_error_and_unavailable_are_explicit():
    failed = assess_data_freshness("FantasyPros", None, 900, error="timeout")
    missing = assess_data_freshness("News", None, 900, available=False)
    assert failed.status == FreshnessStatus.ERROR
    assert failed.detail == "timeout"
    assert missing.status == FreshnessStatus.UNAVAILABLE
    assert missing.age_label == "unknown"


def test_iso_timestamp_and_invalid_threshold_handling():
    result = assess_data_freshness(
        "Rankings", "2026-08-25T11:00:00Z", 3600, now=NOW
    )
    assert result.status == FreshnessStatus.FRESH
    assert result.threshold_label == "1h"
    with pytest.raises(ValueError, match="positive"):
        assess_data_freshness("Bad", NOW, 0, now=NOW)
