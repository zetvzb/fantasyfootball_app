from src.opening_strategies import OpeningStrategy, compare_opening_strategies
from src.scalable_simulator import SimulationPlayer


def _players(rb_value, wr_value):
    return tuple(
        [SimulationPlayer("RB{0}".format(i), "RB", 25 - i, 1, rb_value, 23) for i in range(5)]
        + [SimulationPlayer("WR{0}".format(i), "WR", 25 - i, 1, wr_value, 28) for i in range(5)]
        + [SimulationPlayer("D{0}".format(i), "TE", 4, 1, 5, 27) for i in range(5)]
    )


def test_comparison_returns_all_six_ranked_strategies_reproducibly():
    result = compare_opening_strategies(_players(30, 20), 90, 5, 100, 11)
    assert {row.strategy for row in result} == set(OpeningStrategy)
    assert result == compare_opening_strategies(_players(30, 20), 90, 5, 100, 11)
    assert result[0].average_roster_value >= result[-1].average_roster_value


def test_preferred_opening_changes_with_player_pool_strength():
    rb_pool = compare_opening_strategies(_players(45, 10), 70, 4, 100, 9)
    wr_pool = compare_opening_strategies(_players(10, 45), 70, 4, 100, 9)
    rb_score = next(row.average_roster_value for row in rb_pool if row.strategy == OpeningStrategy.ELITE_RB)
    wr_score = next(row.average_roster_value for row in rb_pool if row.strategy == OpeningStrategy.ELITE_WR)
    assert rb_score > wr_score
    rb_score = next(row.average_roster_value for row in wr_pool if row.strategy == OpeningStrategy.ELITE_RB)
    wr_score = next(row.average_roster_value for row in wr_pool if row.strategy == OpeningStrategy.ELITE_WR)
    assert wr_score > rb_score
