from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

from src.position_budgets import PositionBudgetPlan


@dataclass(frozen=True)
class PriorityTier:
    label: str
    player_names: Tuple[str, ...]


@dataclass(frozen=True)
class PreDraftActionPlan:
    recommended_strategy: str
    budget_plan: PositionBudgetPlan
    priority_tiers: Tuple[PriorityTier, ...]
    nomination_plan: str
    fallback_plan: Tuple[str, ...]


def build_pre_draft_action_plan(
    recommended_strategy: str,
    budget_plan: PositionBudgetPlan,
    priority_players: Mapping[str, Sequence[str]],
    nomination_plan: str,
    fallback_plan: Sequence[str],
) -> PreDraftActionPlan:
    if not recommended_strategy.strip():
        raise ValueError("A recommended strategy is required.")
    tiers = tuple(
        PriorityTier(label=str(label), player_names=tuple(names))
        for label, names in priority_players.items()
        if names
    )
    return PreDraftActionPlan(
        recommended_strategy=recommended_strategy,
        budget_plan=budget_plan,
        priority_tiers=tiers,
        nomination_plan=nomination_plan,
        fallback_plan=tuple(fallback_plan),
    )
