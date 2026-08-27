from types import SimpleNamespace

from src.draft_strategist import DraftStrategistService
from src.snake_draft import DraftBoardEntry, RosterNeed


def _candidates():
    return [
        DraftBoardEntry("Alpha", "WR", 40.0, 6.0, 46.0, 250.0),
        DraftBoardEntry("Beta", "RB", 42.0, 0.0, 42.0, 240.0),
        DraftBoardEntry("Gamma", "QB", 35.0, 0.0, 35.0, 300.0),
    ]


def _need():
    return RosterNeed(starter_gaps={"WR": 1}, flex_gap=0, open_spots=4)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _Session:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _Response(self.payloads.pop(0))


def test_unconfigured_strategist_returns_deterministic_leader():
    result = DraftStrategistService(api_key="").recommend(
        candidates=_candidates(), roster_need=_need(), current_pick_no=12
    )

    assert result.player_name == "Alpha"
    assert result.source == "deterministic"
    assert "OPENAI_API_KEY" in result.warning


def test_agent_calls_read_only_tools_then_returns_validated_candidate():
    session = _Session(
        [
            {
                "output": [
                    {
                        "type": "function_call",
                        "name": "inspect_draft_candidates",
                        "call_id": "call-1",
                        "arguments": "{}",
                    },
                    {
                        "type": "function_call",
                        "name": "inspect_roster_needs",
                        "call_id": "call-2",
                        "arguments": "{}",
                    },
                ]
            },
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    '{"player_name":"Beta","confidence":"medium",'
                                    '"explanation":"Best value if prioritizing RB.",'
                                    '"alternatives":["Alpha","Not Available"]}'
                                ),
                            }
                        ],
                    }
                ]
            },
        ]
    )
    result = DraftStrategistService(api_key="key", session=session).recommend(
        candidates=_candidates(), roster_need=_need(), current_pick_no=12
    )

    assert result.player_name == "Beta"
    assert result.alternatives == ("Alpha",)
    assert result.source == "openai"
    assert len(session.calls) == 2
    continuation_input = session.calls[1][1]["json"]["input"]
    outputs = [item for item in continuation_input if item.get("type") == "function_call_output"]
    assert len(outputs) == 2
    assert "starter_gaps" in outputs[1]["output"]


def test_out_of_board_agent_choice_is_rejected_and_falls_back():
    session = _Session(
        [
            {
                "output": [
                    {
                        "type": "function_call",
                        "name": "inspect_draft_candidates",
                        "call_id": "call-1",
                        "arguments": "{}",
                    },
                    {
                        "type": "function_call",
                        "name": "inspect_roster_needs",
                        "call_id": "call-2",
                        "arguments": "{}",
                    },
                ]
            },
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    '{"player_name":"Invented Player","confidence":"high",'
                                    '"explanation":"Trust me.","alternatives":[]}'
                                ),
                            }
                        ],
                    }
                ]
            }
        ]
    )
    result = DraftStrategistService(api_key="key", session=session).recommend(
        candidates=_candidates(), roster_need=_need(), current_pick_no=12
    )

    assert result.player_name == "Alpha"
    assert result.source == "deterministic"
    assert "outside the candidate set" in result.warning


def test_valid_looking_answer_without_tool_inspection_is_rejected():
    session = _Session(
        [
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    '{"player_name":"Beta","confidence":"high",'
                                    '"explanation":"Pick Beta.","alternatives":["Alpha"]}'
                                ),
                            }
                        ],
                    }
                ]
            }
        ]
    )
    result = DraftStrategistService(api_key="key", session=session).recommend(
        candidates=_candidates(), roster_need=_need(), current_pick_no=12
    )

    assert result.player_name == "Alpha"
    assert result.source == "deterministic"
    assert "skipped required tool" in result.warning
