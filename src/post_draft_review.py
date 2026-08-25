from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Tuple

from src.pass_grading import PassGrade, PassGradeStatus
from src.purchase_grading import PurchaseGrade


class DecisionVerdict(str, Enum):
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    PENDING = "PENDING"


@dataclass(frozen=True)
class ReviewedDecision:
    player_name: str
    decision_type: str
    verdict: DecisionVerdict
    score: float
    explanation: str


@dataclass(frozen=True)
class ModelCalibrationError:
    component: str
    average_score: float
    direction: str
    explanation: str


@dataclass(frozen=True)
class CopilotPostDraftReview:
    decisions: Tuple[ReviewedDecision, ...]
    calibration_errors: Tuple[ModelCalibrationError, ...]
    correct_count: int
    incorrect_count: int
    pending_count: int
    average_graded_score: float


def _verdict(score: float) -> DecisionVerdict:
    return (
        DecisionVerdict.CORRECT
        if float(score) >= 70.0
        else DecisionVerdict.INCORRECT
    )


def build_copilot_post_draft_review(
    purchase_grades: Sequence[PurchaseGrade],
    pass_grades: Sequence[PassGrade],
) -> CopilotPostDraftReview:
    """Summarize decision quality and expose weak model components."""

    decisions = []
    graded_scores = []
    component_scores = {
        "price discipline": [],
        "roster fit": [],
        "alternatives": [],
        "downstream outcome": [],
    }

    for grade in purchase_grades:
        score = float(grade.total_score)
        graded_scores.append(score)
        component_scores["price discipline"].append(grade.price_discipline_score)
        component_scores["roster fit"].append(grade.roster_fit_score)
        component_scores["alternatives"].append(grade.alternative_score)
        component_scores["downstream outcome"].append(grade.downstream_score)
        decisions.append(
            ReviewedDecision(
                player_name=grade.player_name,
                decision_type="PURCHASE",
                verdict=_verdict(score),
                score=score,
                explanation=" ".join(grade.reasons),
            )
        )

    for grade in pass_grades:
        if grade.status is PassGradeStatus.PENDING or grade.total_score is None:
            decisions.append(
                ReviewedDecision(
                    player_name=grade.player_name,
                    decision_type="PASS",
                    verdict=DecisionVerdict.PENDING,
                    score=0.0,
                    explanation=" ".join(grade.reasons),
                )
            )
            continue
        score = float(grade.total_score)
        graded_scores.append(score)
        component_scores["price discipline"].append(
            float(grade.discipline_score or 0.0)
        )
        component_scores["alternatives"].extend(
            [
                float(grade.availability_score or 0.0),
                float(grade.alternative_cost_score or 0.0),
            ]
        )
        decisions.append(
            ReviewedDecision(
                player_name=grade.player_name,
                decision_type="PASS",
                verdict=_verdict(score),
                score=score,
                explanation=" ".join(grade.reasons),
            )
        )

    errors = []
    for component, scores in component_scores.items():
        if not scores:
            continue
        average = sum(float(value) for value in scores) / len(scores)
        if average >= 70.0:
            continue
        direction = "TOO_HIGH" if component in {
            "price discipline",
            "alternatives",
        } else "MISALIGNED"
        errors.append(
            ModelCalibrationError(
                component=component,
                average_score=round(average, 1),
                direction=direction,
                explanation=(
                    "{0} averaged {1:.1f}/100 across graded decisions; "
                    "review this model input before next season."
                ).format(component.title(), average),
            )
        )

    return CopilotPostDraftReview(
        decisions=tuple(decisions),
        calibration_errors=tuple(errors),
        correct_count=sum(
            decision.verdict is DecisionVerdict.CORRECT for decision in decisions
        ),
        incorrect_count=sum(
            decision.verdict is DecisionVerdict.INCORRECT for decision in decisions
        ),
        pending_count=sum(
            decision.verdict is DecisionVerdict.PENDING for decision in decisions
        ),
        average_graded_score=round(
            sum(graded_scores) / len(graded_scores), 1
        ) if graded_scores else 0.0,
    )
