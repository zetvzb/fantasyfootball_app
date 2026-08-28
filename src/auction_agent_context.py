from __future__ import annotations

from typing import Sequence


def append_agent_context(messages: Sequence[str], message: str, limit: int = 8) -> list:
    cleaned = str(message or "").strip()
    existing = [str(item).strip() for item in messages if str(item).strip()]
    if cleaned:
        existing.append(cleaned[:500])
    return existing[-max(1, int(limit)) :]


def format_agent_context(messages: Sequence[str], max_chars: int = 2000) -> str:
    lines = ["Manager context: {0}".format(str(item).strip()) for item in messages]
    return "\n".join(line for line in lines if line != "Manager context:")[-max_chars:]
