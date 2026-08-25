from src.manager_tendencies import (
    ManagerTendencyObservation,
    build_manager_tendency_model,
    build_manager_tendencies_from_mappings,
)


def test_manager_profile_covers_premiums_style_timing_keepers_cash_and_aggression():
    model = build_manager_tendency_model(
        (
            ManagerTendencyObservation("m1", 2026, "WR", "star", "early", 60, 50, True, 5),
            ManagerTendencyObservation("m1", 2026, "RB", "depth", "late", 8, 10, False, 5),
        ),
        as_of_season=2026,
    )
    profile = model.profiles[0]

    assert dict(profile.position_premiums) == {"RB": 0.8, "WR": 1.2}
    assert profile.historical_aggression == 1.133
    assert profile.stars_spend_share > profile.depth_spend_share
    assert dict(profile.auction_timing_share) == {"early": 0.5, "late": 0.5}
    assert profile.keeper_rate == 0.5
    assert profile.average_unused_cash == 5


def test_recent_behavior_outweighs_old_behavior_with_time_decay():
    model = build_manager_tendency_model(
        (
            ManagerTendencyObservation("m1", 2022, "WR", "star", "early", 100, 50),
            ManagerTendencyObservation("m1", 2026, "WR", "star", "early", 40, 50),
        ),
        as_of_season=2026,
        half_life_years=1,
    )

    assert model.profiles[0].historical_aggression < 1.0


def test_mapping_adapter_skips_bad_rows_with_warning():
    model = build_manager_tendencies_from_mappings(
        (
            {"manager_id": "m1", "season": 2026, "actual_price": 20, "expected_price": 10},
            {"manager_id": "bad"},
        ),
        as_of_season=2026,
    )

    assert len(model.profiles) == 1
    assert len(model.warnings) == 1
