from src.live_draft import LiveAuctionSale
from src.purchase_grading import (
    PurchaseGradeInput,
    grade_purchase,
    grade_recorded_purchases,
)
from src.recommendation_snapshot import RecommendationSnapshot


def _snapshot():
    return RecommendationSnapshot(
        "Target", 15, 20, 24, 28, "BID",
        ({"player_name": "Fallback"},),
        {"position_need": {"WR": 0.9}}, {}, {}, {}, ("Need WR",),
    )


def test_strong_fit_disciplined_price_earns_high_grade():
    score, letter, components, reasons = grade_purchase(
        PurchaseGradeInput(18, 20, 24, 28, 1.0, (25,), 90)
    )
    assert score >= 90
    assert letter == "A"
    assert components[0] == 100
    assert len(reasons) == 4


def test_overpay_with_cheaper_alternative_and_poor_outcome_is_penalized():
    score, letter, _, _ = grade_purchase(
        PurchaseGradeInput(35, 20, 24, 28, 0.2, (15,), 20)
    )
    assert score < 60
    assert letter == "F"


def test_recorded_purchase_uses_snapshot_alternative_and_downstream_sales():
    sales = [
        LiveAuctionSale(1, "Target", "WR", "me", 22, 25, 28),
        LiveAuctionSale(2, "Fallback", "WR", "other", 18, 20, 22),
        LiveAuctionSale(3, "Later Value", "RB", "me", 10, 20, 20),
    ]
    grades = grade_recorded_purchases(sales, [_snapshot()])
    assert len(grades) == 1
    assert grades[0].player_name == "Target"
    assert grades[0].roster_fit_score == 90
    assert grades[0].downstream_score > 50
