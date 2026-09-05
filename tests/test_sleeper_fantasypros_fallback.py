from src.sleeper_fantasypros_fallback import (
    build_fallback_bundle,
    build_projections,
)


def _sleeper_players():
    return {
        "1": {
            "full_name": "Test WR",
            "position": "WR",
            "team": "AAA",
            "active": True,
            "search_rank": 10,
        },
        "2": {
            "full_name": "Test QB",
            "position": "QB",
            "team": "BBB",
            "active": True,
            "search_rank": 20,
        },
    }


def _wr_stats():
    # 10 receptions, 100 rec yards, 1 rec TD -- enough to show full vs. half
    # PPR diverge sharply on the reception term alone.
    return {
        "pts_half_ppr": 20.0,
        "rec": 10.0,
        "rec_yd": 100.0,
        "rec_td": 1.0,
    }


def test_build_projections_rescopes_under_real_scoring_settings():
    stats_by_player = {"1": _wr_stats()}
    full_ppr = {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0}
    half_ppr = {"rec": 0.5, "rec_yd": 0.1, "rec_td": 6.0}

    full_projections = build_projections(_sleeper_players(), stats_by_player, full_ppr)
    half_projections = build_projections(_sleeper_players(), stats_by_player, half_ppr)

    assert full_projections[0].custom_points == 10 * 1.0 + 100 * 0.1 + 1 * 6.0
    assert half_projections[0].custom_points == 10 * 0.5 + 100 * 0.1 + 1 * 6.0
    assert full_projections[0].custom_points > half_projections[0].custom_points
    assert full_projections[0].custom_scoring_exact is True


def test_build_projections_falls_back_to_half_ppr_total_without_scoring_settings():
    stats_by_player = {"1": _wr_stats()}
    projections = build_projections(_sleeper_players(), stats_by_player, None)
    assert projections[0].custom_points == 20.0
    assert projections[0].custom_scoring_exact is False


def test_build_projections_skips_non_vorp_positions():
    players = {"9": {"full_name": "Some Kicker", "position": "K", "team": "AAA"}}
    stats_by_player = {"9": {"pts_half_ppr": 5.0}}
    assert build_projections(players, stats_by_player, {}) == []


def test_build_fallback_bundle_survives_network_failure(monkeypatch):
    import src.sleeper_fantasypros_fallback as module

    def _boom(season, timeout=20):
        raise OSError("network down")

    monkeypatch.setattr(module, "fetch_sleeper_projections", _boom)

    bundle = build_fallback_bundle(2026, _sleeper_players(), scoring_settings={"rec": 1.0})

    assert bundle["_prebuilt_projections"] == []
    assert bundle["intelligence"]
    assert bundle["_source"] == "sleeper_fallback"
