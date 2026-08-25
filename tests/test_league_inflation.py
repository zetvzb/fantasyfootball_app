from types import SimpleNamespace

from src.league_inflation import (
    InflationObservation,
    build_league_inflation_model,
    calculate_live_room_inflation,
)


def test_historical_inflation_segments_season_position_tier_and_stage():
    model = build_league_inflation_model(
        (
            InflationObservation(2024, "WR", "elite", "early", 50, 60),
            InflationObservation(2025, "WR", "elite", "early", 50, 70),
            InflationObservation(2025, "RB", "depth", "late", 10, 8),
        )
    )

    assert model.overall_inflation_index == 1.255
    wr = next(
        segment
        for segment in model.segments
        if segment.position == "WR" and segment.season == 2025
    )
    assert wr.sample_size == 1
    assert wr.inflation_index == 1.4
    assert {item.season for item in model.observations} == {2024, 2025}


def test_live_room_inflation_tracks_expected_vs_actual_and_unmapped_sales():
    result = calculate_live_room_inflation(
        live_sales=(
            SimpleNamespace(player_name="Star", position="WR", price=60),
            SimpleNamespace(player_name="Depth", position="RB", price=8),
            SimpleNamespace(player_name="Unknown", position="TE", price=2),
        ),
        expected_values={
            "star": SimpleNamespace(expected_market_value=50),
            "depth": SimpleNamespace(expected_market_value=10),
        },
    )

    assert result.expected_spend == 60
    assert result.actual_spend == 68
    assert result.room_inflation_index == 1.133
    assert result.unmapped_sales == ("Unknown",)
    assert {segment.position for segment in result.by_position} == {"RB", "WR"}
