from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence


@dataclass
class BidPlayerState:
    nominated_player: str
    nominated_key: str
    recommendation: Any
    nomination_info: Optional[Any]
    threat_summary: Optional[Any]
    fp: Optional[Any]
    projection: Optional[Any]
    vorp_value: Optional[Any]
    selected_market: Optional[Any]

    player_context_summary: Any
    player_context_documents: Sequence[Any]
    context_lookup_name: str
    targeted_news_count: Optional[int]
    targeted_injury_count: Optional[int]
    targeted_context_error: Optional[str]

    player_level_ceiling: int
    context_adjustment: Any
    context_adjusted_ceiling: int
    roster_ceiling: int
    roster_ceiling_available: bool
    final_do_not_exceed: int
    dynamic_cap_result: Any
    pass_alternatives: Sequence[Any]
