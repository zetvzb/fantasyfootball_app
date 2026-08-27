from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import requests

from src.auction_pool import normalize_player_name
from src.snake_draft import DraftBoardEntry, RosterNeed


@dataclass(frozen=True)
class DraftStrategistRecommendation:
    player_name: str
    position: str
    confidence: str
    explanation: str
    alternatives: Tuple[str, ...]
    source: str
    model: Optional[str] = None
    warning: Optional[str] = None


class DraftStrategistService:
    """Bounded, read-only agent over the deterministic snake-draft board."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        session: Optional[object] = None,
        timeout: int = 20,
        max_rounds: int = 3,
    ):
        self.api_key = str(
            api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        ).strip()
        self.model = str(
            model
            if model is not None
            else os.getenv(
                "OPENAI_DRAFT_STRATEGIST_MODEL",
                os.getenv("OPENAI_EXPLANATION_MODEL", "gpt-5.4"),
            )
        ).strip()
        self.session = session or requests.Session()
        self.timeout = int(timeout)
        self.max_rounds = int(max_rounds)

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    @staticmethod
    def _candidate_payload(candidates: Sequence[DraftBoardEntry]) -> list:
        return [asdict(candidate) for candidate in candidates]

    @staticmethod
    def _need_payload(roster_need: RosterNeed) -> dict:
        return {
            "starter_gaps": dict(roster_need.starter_gaps),
            "flex_gap": int(roster_need.flex_gap),
            "open_spots": int(roster_need.open_spots),
        }

    @staticmethod
    def _fallback(
        candidates: Sequence[DraftBoardEntry],
        warning: Optional[str] = None,
    ) -> DraftStrategistRecommendation:
        leader = candidates[0]
        alternatives = tuple(candidate.player_name for candidate in candidates[1:3])
        need_text = (
            " and receives a {0:.1f}-point roster-need bonus".format(leader.need_bonus)
            if leader.need_bonus > 0
            else ""
        )
        return DraftStrategistRecommendation(
            player_name=leader.player_name,
            position=leader.position,
            confidence="high" if len(candidates) > 1 and leader.utility > candidates[1].utility else "medium",
            explanation=(
                "The deterministic board ranks {0} first at {1:.1f} utility "
                "({2:.1f} VORP){3}."
            ).format(
                leader.player_name,
                leader.utility,
                leader.vorp,
                need_text,
            ),
            alternatives=alternatives,
            source="deterministic",
            warning=warning,
        )

    @staticmethod
    def _output_text(payload: Mapping[str, Any]) -> str:
        pieces = []
        for item in payload.get("output") or []:
            if not isinstance(item, Mapping) or item.get("type") != "message":
                continue
            for part in item.get("content") or []:
                if isinstance(part, Mapping) and part.get("type") == "output_text":
                    value = str(part.get("text") or "").strip()
                    if value:
                        pieces.append(value)
        return "\n".join(pieces)

    @staticmethod
    def _tool_calls(payload: Mapping[str, Any]) -> list:
        return [
            item
            for item in payload.get("output") or []
            if isinstance(item, Mapping) and item.get("type") == "function_call"
        ]

    def _request_payload(self, input_items: Sequence[Mapping[str, Any]]) -> dict:
        return {
            "model": self.model,
            "instructions": (
                "You are a read-only fantasy football draft strategist. Before "
                "recommending a player, call both available tools. Use only tool "
                "facts. Never invent news, availability, projections, or odds. "
                "Choose only a supplied candidate. The application, not you, owns "
                "all rankings and roster math. Keep the explanation under 80 words."
            ),
            "input": list(input_items),
            "tools": [
                {
                    "type": "function",
                    "name": "inspect_draft_candidates",
                    "description": "Read the current top deterministic draft candidates.",
                    "strict": True,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                },
                {
                    "type": "function",
                    "name": "inspect_roster_needs",
                    "description": "Read the current manager's open roster needs.",
                    "strict": True,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "draft_strategist_recommendation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "player_name": {"type": "string"},
                            "confidence": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                            },
                            "explanation": {"type": "string"},
                            "alternatives": {
                                "type": "array",
                                "items": {"type": "string"},
                                "maxItems": 3,
                            },
                        },
                        "required": [
                            "player_name",
                            "confidence",
                            "explanation",
                            "alternatives",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "max_output_tokens": 350,
            "store": False,
        }

    def recommend(
        self,
        *,
        candidates: Sequence[DraftBoardEntry],
        roster_need: RosterNeed,
        current_pick_no: int,
    ) -> Optional[DraftStrategistRecommendation]:
        bounded_candidates = tuple(candidates[:5])
        if not bounded_candidates:
            return None
        if not self.configured:
            return self._fallback(
                bounded_candidates,
                "OPENAI_API_KEY is not configured; showing the deterministic recommendation.",
            )

        input_items = [
            {
                "role": "user",
                "content": (
                    "Recommend one player for pick #{0}. Inspect both tools first."
                    .format(int(current_pick_no))
                ),
            }
        ]
        tool_results: Dict[str, str] = {
            "inspect_draft_candidates": json.dumps(
                self._candidate_payload(bounded_candidates), sort_keys=True
            ),
            "inspect_roster_needs": json.dumps(
                self._need_payload(roster_need), sort_keys=True
            ),
        }

        try:
            final_text = ""
            used_tools = set()
            for _ in range(self.max_rounds):
                response = self.session.post(
                    "https://api.openai.com/v1/responses",
                    json=self._request_payload(input_items),
                    headers={
                        "Authorization": "Bearer {0}".format(self.api_key),
                        "Content-Type": "application/json",
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
                calls = self._tool_calls(payload)
                if calls:
                    input_items.extend(payload.get("output") or [])
                    for call in calls:
                        name = str(call.get("name") or "")
                        if name not in tool_results:
                            raise ValueError("Unknown strategist tool: {0}".format(name))
                        used_tools.add(name)
                        input_items.append(
                            {
                                "type": "function_call_output",
                                "call_id": call.get("call_id"),
                                "output": tool_results[name],
                            }
                        )
                    continue
                final_text = self._output_text(payload)
                if final_text:
                    break
            if not final_text:
                raise ValueError("The strategist did not return a final recommendation.")
            missing_tools = set(tool_results) - used_tools
            if missing_tools:
                raise ValueError(
                    "The strategist skipped required tool(s): {0}.".format(
                        ", ".join(sorted(missing_tools))
                    )
                )

            result = json.loads(final_text)
            candidates_by_key = {
                normalize_player_name(candidate.player_name): candidate
                for candidate in bounded_candidates
            }
            selected_key = normalize_player_name(result.get("player_name"))
            selected = candidates_by_key.get(selected_key)
            if selected is None:
                raise ValueError("The strategist selected a player outside the candidate set.")
            alternatives = []
            for name in result.get("alternatives") or []:
                key = normalize_player_name(name)
                candidate = candidates_by_key.get(key)
                if candidate is not None and key != selected_key and candidate.player_name not in alternatives:
                    alternatives.append(candidate.player_name)
            return DraftStrategistRecommendation(
                player_name=selected.player_name,
                position=selected.position,
                confidence=str(result["confidence"]),
                explanation=str(result["explanation"]).strip(),
                alternatives=tuple(alternatives),
                source="openai",
                model=self.model,
            )
        except (requests.RequestException, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            return self._fallback(
                bounded_candidates,
                "AI strategist unavailable: {0}".format(error),
            )
