from src.position_budgets import optimize_position_budgets


def test_position_bands_prioritize_need_and_preserve_reserve():
    plan = optimize_position_budgets(100, {"RB": 2, "WR": 2, "TE": 1}, {"RB": 1.0, "WR": 0.5, "TE": 0.2})
    bands = {band.position: band for band in plan.bands}
    assert plan.minimum_reserve == 5
    assert bands["RB"].target > bands["WR"].target > bands["TE"].target
    assert all(band.minimum <= band.target <= band.maximum for band in plan.bands)


def test_bands_recompute_after_sale_and_filled_position():
    before = optimize_position_budgets(100, {"RB": 2, "WR": 2}, {"RB": 1.0, "WR": 0.5})
    after = optimize_position_budgets(70, {"RB": 1, "WR": 2}, {"RB": 0.4, "WR": 0.8})
    before_bands = {band.position: band for band in before.bands}
    after_bands = {band.position: band for band in after.bands}
    assert after_bands["RB"].target < before_bands["RB"].target
    assert after_bands["WR"].target > after_bands["RB"].target
    assert after.minimum_reserve == 3
