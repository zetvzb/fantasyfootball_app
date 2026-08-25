from src.pass_grading import PassGrade, PassGradeStatus
from src.post_draft_review import (
    DecisionVerdict,
    build_copilot_post_draft_review,
)
from src.purchase_grading import PurchaseGrade


def _purchase(score, price_score=80, fit=80, alternatives=80, downstream=80):
    return PurchaseGrade(
        "Player", 1, score, "B", price_score, fit, alternatives, downstream,
        ("Purchase explanation.",),
    )


def _pass(score=None, status=PassGradeStatus.GRADED):
    return PassGrade(
        "Passed Player", status, score,
        "B" if score is not None else "PENDING", 30, "Fallback", 20,
        80 if score is not None else None,
        80 if score is not None else None,
        80 if score is not None else None,
        ("Pass explanation.",),
    )


def test_post_draft_review_classifies_correct_incorrect_and_pending_decisions():
    review = build_copilot_post_draft_review(
        [_purchase(88), _purchase(55)],
        [_pass(82), _pass(status=PassGradeStatus.PENDING)],
    )

    assert review.correct_count == 2
    assert review.incorrect_count == 1
    assert review.pending_count == 1
    assert review.average_graded_score == 75.0
    assert review.decisions[1].verdict is DecisionVerdict.INCORRECT


def test_post_draft_review_identifies_weak_model_components():
    review = build_copilot_post_draft_review(
        [_purchase(55, price_score=35, fit=90, alternatives=40, downstream=45)],
        [],
    )

    components = {error.component for error in review.calibration_errors}
    assert components == {
        "price discipline",
        "alternatives",
        "downstream outcome",
    }
    assert all(error.explanation for error in review.calibration_errors)
