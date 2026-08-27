from types import SimpleNamespace

from src.ranking_ensemble import (
    RankingObservation,
    build_ranking_ensemble,
    build_repository_ranking_ensemble,
)


def test_three_sources_are_equal_weighted_and_disagreement_is_informational():
    result = build_ranking_ensemble(
        (
            RankingObservation("Sleeper", "Player A", 1),
            RankingObservation("Import", "Player A", 10),
            RankingObservation("Third", "Player A", 4),
            RankingObservation("Sleeper", "Player B", 6),
            RankingObservation("Import", "Player B", 6),
            RankingObservation("Third", "Player B", 6),
        ),
        ("Sleeper", "Import", "Third"),
    )

    assert result.rankings[0].player_name == "Player A"
    assert result.rankings[0].average_source_rank == 5.0
    assert result.rankings[0].rank_disagreement == 9.0
    assert result.rankings[0].source_count == 3


def test_missing_source_is_tolerated_and_available_sources_are_reweighted():
    result = build_ranking_ensemble(
        (RankingObservation("Sleeper", "Player A", 8),),
        ("Sleeper", "Import", "Third"),
    )

    assert result.rankings[0].average_source_rank == 8
    assert result.active_sources == ("Sleeper",)
    assert "Import" in result.warnings[0]


def test_repository_adapter_combines_sleeper_and_fantasypros():
    result = build_repository_ranking_ensemble(
        sleeper_players={
            "1": {"full_name": "Player A", "search_rank": 3, "position": "WR"}
        },
        third_party_players=(
            SimpleNamespace(player_name="Player A", half_ecr=9, position="WR"),
        ),
    )

    assert result.rankings[0].average_source_rank == 6
    assert result.rankings[0].source_count == 2
    assert result.warnings == ()
