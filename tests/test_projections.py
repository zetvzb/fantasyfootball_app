import pytest

from src.projections import STANDARD_SCORING_DEFAULTS, score_offensive_projection


def _elite_wr_stats():
    return {
        "rec_rec": 98.91,
        "rec_yds": 1310.88,
        "rec_tds": 7.12,
        "rush_att": 1.34,
        "rush_yds": 5.54,
        "rush_tds": 0.03,
    }


def test_sparse_scoring_settings_fall_back_to_standard_defaults():
    # A manual/off-platform league's scoring settings have historically
    # only ever recorded reception points (see build_manual_league_profile)
    # -- everything else must still score using standard conventions
    # rather than silently contributing zero.
    points, breakdown, warnings = score_offensive_projection(
        stats=_elite_wr_stats(),
        scoring_settings={"rec": 0.5},
    )

    assert points > 200
    assert "rec_yd" in breakdown
    assert "rec_td" in breakdown
    assert warnings == []


def test_explicit_zero_setting_is_respected_not_overridden():
    # A league that explicitly turns a category off must stay off --
    # only a category the league never mentions gets a default filled in.
    points, breakdown, _ = score_offensive_projection(
        stats=_elite_wr_stats(),
        scoring_settings={"rec": 0.5, "rec_td": 0},
    )

    assert breakdown.get("rec_td", 0) == 0
    points_with_td, _, _ = score_offensive_projection(
        stats=_elite_wr_stats(),
        scoring_settings={"rec": 0.5},
    )
    assert points < points_with_td


def test_fully_specified_scoring_settings_are_unaffected():
    full_settings = dict(STANDARD_SCORING_DEFAULTS)
    full_settings["rec"] = 1.0
    points, breakdown, _ = score_offensive_projection(
        stats=_elite_wr_stats(),
        scoring_settings=full_settings,
    )
    assert points > 200
    assert breakdown["rec"] == pytest.approx(98.91)
