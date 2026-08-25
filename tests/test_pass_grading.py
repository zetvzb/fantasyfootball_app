from src.live_draft import LiveAuctionSale
from src.pass_grading import PassGradeStatus, grade_recorded_passes
from src.recommendation_snapshot import RecommendationSnapshot


def _pass_snapshot(sale_count=0):
    return RecommendationSnapshot(
        "Target", 25, 20, 25, 30, "PASS",
        ({"player_name": "Fallback"},),
        {"sale_count": sale_count}, {}, {}, {}, ("Alternative available",),
    )


def test_disciplined_pass_with_later_cheap_alternative_grades_highly():
    sales = [
        LiveAuctionSale(1, "Target", "WR", "other", 36),
        LiveAuctionSale(2, "Fallback", "WR", "me", 18),
    ]
    grade = grade_recorded_passes(sales, [_pass_snapshot()])[0]
    assert grade.status == PassGradeStatus.GRADED
    assert grade.letter_grade == "A"
    assert grade.acquired_alternative == "Fallback"


def test_pass_on_affordable_target_with_expensive_fallback_is_penalized():
    sales = [
        LiveAuctionSale(1, "Target", "WR", "other", 18),
        LiveAuctionSale(2, "Fallback", "WR", "me", 35),
    ]
    grade = grade_recorded_passes(sales, [_pass_snapshot()])[0]
    assert grade.status == PassGradeStatus.GRADED
    assert grade.total_score < 70
    assert grade.letter_grade in {"D", "F"}


def test_pass_remains_pending_until_later_outcomes_exist():
    grade = grade_recorded_passes([], [_pass_snapshot()])[0]
    assert grade.status == PassGradeStatus.PENDING
    assert grade.total_score is None
    assert grade.letter_grade == "PENDING"


def test_only_sales_after_snapshot_are_considered():
    sales = [
        LiveAuctionSale(1, "Fallback", "WR", "other", 10),
        LiveAuctionSale(2, "Target", "WR", "other", 35),
    ]
    grade = grade_recorded_passes(sales, [_pass_snapshot(sale_count=1)])[0]
    assert grade.status == PassGradeStatus.PENDING
    completed = grade_recorded_passes(
        sales, [_pass_snapshot(sale_count=1)], auction_complete=True
    )[0]
    assert completed.status == PassGradeStatus.GRADED
    assert completed.availability_score == 20
