from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Mapping, Optional, Sequence, Tuple

import requests


@dataclass(frozen=True)
class DecisionExplanationInput:
    subject: str
    decision: str
    numeric_facts: Mapping[str, float]
    reason_codes: Tuple[str, ...]
    deterministic_explanation: str


@dataclass(frozen=True)
class DecisionNarrative:
    text: str
    source: str
    model: Optional[str] = None
    warning: Optional[str] = None


class DecisionExplanationService:
    """Optionally polish a completed deterministic decision with an LLM."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        session: Optional[object] = None,
        timeout: int = 20,
    ):
        self.api_key = str(
            api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        ).strip()
        self.model = str(
            model
            if model is not None
            else os.getenv("OPENAI_EXPLANATION_MODEL", "gpt-5.4")
        ).strip()
        self.session = session or requests.Session()
        self.timeout = int(timeout)

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    @staticmethod
    def deterministic(inputs: DecisionExplanationInput) -> DecisionNarrative:
        return DecisionNarrative(
            text=inputs.deterministic_explanation,
            source="deterministic",
        )

    @staticmethod
    def _output_text(payload: Mapping[str, object]) -> str:
        pieces = []
        output = payload.get("output") or []
        if not isinstance(output, Sequence) or isinstance(output, (str, bytes)):
            return ""
        for item in output:
            if not isinstance(item, Mapping) or item.get("type") != "message":
                continue
            content = item.get("content") or []
            if not isinstance(content, Sequence) or isinstance(content, (str, bytes)):
                continue
            for part in content:
                if isinstance(part, Mapping) and part.get("type") == "output_text":
                    text = str(part.get("text") or "").strip()
                    if text:
                        pieces.append(text)
        return "\n".join(pieces)

    def explain(
        self,
        inputs: DecisionExplanationInput,
        *,
        use_ai: bool = False,
    ) -> DecisionNarrative:
        if not use_ai:
            return self.deterministic(inputs)
        if not self.configured:
            fallback = self.deterministic(inputs)
            return DecisionNarrative(
                text=fallback.text,
                source=fallback.source,
                warning=(
                    "OPENAI_API_KEY is not configured; showing the "
                    "deterministic explanation."
                ),
            )

        request_payload = {
            "model": self.model,
            "instructions": (
                "Write a concise fantasy-football decision explanation using "
                "only the supplied computed facts and reason codes. Do not "
                "change, recalculate, or invent any decision, score, price, "
                "player fact, injury, or news. State that the numeric result "
                "comes from the deterministic engine."
            ),
            "input": json.dumps(
                {
                    "subject": inputs.subject,
                    "decision": inputs.decision,
                    "numeric_facts": dict(inputs.numeric_facts),
                    "reason_codes": list(inputs.reason_codes),
                    "deterministic_explanation": inputs.deterministic_explanation,
                },
                sort_keys=True,
            ),
            "max_output_tokens": 250,
            "store": False,
        }
        try:
            response = self.session.post(
                "https://api.openai.com/v1/responses",
                json=request_payload,
                headers={
                    "Authorization": "Bearer {0}".format(self.api_key),
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            text = self._output_text(response.json())
            if not text:
                raise ValueError("The explanation response contained no text.")
        except (requests.RequestException, TypeError, ValueError) as error:
            fallback = self.deterministic(inputs)
            return DecisionNarrative(
                text=fallback.text,
                source=fallback.source,
                warning="AI explanation unavailable: {0}".format(error),
            )
        return DecisionNarrative(text=text, source="openai", model=self.model)
