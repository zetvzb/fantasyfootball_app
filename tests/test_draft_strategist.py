from types import SimpleNamespace

from src.draft_strategist import (
    AuctionStrategistService,
    DraftStrategistService,
    NominationStrategistService,
)
from src.live_cockpit import build_live_cockpit_summary
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


def _auction_inputs(current_bid=18, hard_cap=25):
    alternatives = [
        SimpleNamespace(
            player_name="Fallback",
            expected_price_low=10,
            expected_price_high=15,
            availability_probability=0.7,
        )
    ]
    summary = build_live_cockpit_summary(
        "Nominated Player",
        current_bid,
        18,
        22,
        hard_cap,
        "PURSUE",
        ["fills roster need"],
        alternatives,
        "MEDIUM",
        40,
    )
    state = SimpleNamespace(
        recommendation=SimpleNamespace(
            position="WR",
            legal_max_bid=30,
            expected_market_value=20.0,
            strategy="PURSUE",
            reasons=["fills roster need"],
        ),
        pass_alternatives=alternatives,
    )
    team_setup = SimpleNamespace(
        live_cash=100,
        open_roster_spots=5,
        discretionary_cash=96,
    )
    return summary, state, team_setup


def _auction_tool_call_payload():
    return {
        "output": [
            {
                "type": "function_call",
                "name": "inspect_price_decision",
                "call_id": "price-call",
                "arguments": "{}",
            },
            {
                "type": "function_call",
                "name": "inspect_roster_and_alternatives",
                "call_id": "roster-call",
                "arguments": "{}",
            },
        ]
    }


def test_auction_agent_works_for_manual_source_and_validates_fallbacks():
    session = _Session(
        [
            _auction_tool_call_payload(),
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    '{"decision":"BID","max_bid":24,'
                                    '"confidence":"high","explanation":"Bid within cap.",'
                                    '"alternatives":["Fallback","Invented"]}'
                                ),
                            }
                        ],
                    }
                ]
            },
        ]
    )
    summary, state, team_setup = _auction_inputs()
    result = AuctionStrategistService(api_key="key", session=session).recommend_auction(
        summary=summary,
        bid_state=state,
        team_setup=team_setup,
        source_mode="manual",
        user_context="The room is chasing wide receivers.",
    )

    assert result.decision == "BID"
    assert result.max_bid == 24
    assert result.alternatives == ("Fallback",)
    assert result.source == "openai"
    second_input = session.calls[1][1]["json"]["input"]
    roster_output = next(
        item["output"]
        for item in second_input
        if item.get("call_id") == "roster-call"
        and item.get("type") == "function_call_output"
    )
    assert '"source_mode": "manual"' in roster_output
    assert "The room is chasing wide receivers." in roster_output


def test_nomination_agent_uses_context_and_validates_choice():
    candidates = [
        SimpleNamespace(
            player_name="Alpha",
            position="WR",
            nomination_score=90.0,
            action="Drain Cash",
            reason="The room needs receivers.",
            expected_market_value=30.0,
            do_not_exceed=22,
        ),
        SimpleNamespace(
            player_name="Beta",
            position="RB",
            nomination_score=85.0,
            action="Acquire Target",
            reason="A useful buy window.",
            expected_market_value=18.0,
            do_not_exceed=21,
        ),
    ]
    session = _Session(
        [
            {
                "output": [
                    {
                        "type": "function_call",
                        "name": "inspect_nomination_options",
                        "call_id": "nomination-call",
                        "arguments": "{}",
                    }
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
                                    '{"player_name":"Beta","confidence":"high",'
                                    '"explanation":"Use the room context."}'
                                ),
                            }
                        ],
                    }
                ]
            },
        ]
    )

    result = NominationStrategistService(
        api_key="key", session=session
    ).recommend_nomination(
        candidates=candidates,
        user_context="Nobody wants to spend on running backs yet.",
    )

    assert result.player_name == "Beta"
    assert result.source == "openai"
    second_input = session.calls[1][1]["json"]["input"]
    tool_output = next(
        item["output"]
        for item in second_input
        if item.get("type") == "function_call_output"
    )
    assert "Nobody wants to spend on running backs yet." in tool_output


def test_auction_agent_cannot_exceed_deterministic_hard_cap():
    session = _Session(
        [
            _auction_tool_call_payload(),
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    '{"decision":"BID","max_bid":99,'
                                    '"confidence":"high","explanation":"Overpay.",'
                                    '"alternatives":[]}'
                                ),
                            }
                        ],
                    }
                ]
            },
        ]
    )
    summary, state, team_setup = _auction_inputs()
    result = AuctionStrategistService(api_key="key", session=session).recommend_auction(
        summary=summary,
        bid_state=state,
        team_setup=team_setup,
        source_mode="sleeper",
    )

    assert result.source == "deterministic"
    assert result.max_bid == 25
    assert "exceeded the deterministic hard cap" in result.warning


def test_auction_agent_must_pass_when_current_bid_is_above_cap():
    session = _Session(
        [
            _auction_tool_call_payload(),
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    '{"decision":"BID","max_bid":25,'
                                    '"confidence":"high","explanation":"Keep bidding.",'
                                    '"alternatives":[]}'
                                ),
                            }
                        ],
                    }
                ]
            },
        ]
    )
    summary, state, team_setup = _auction_inputs(current_bid=26, hard_cap=25)
    result = AuctionStrategistService(api_key="key", session=session).recommend_auction(
        summary=summary,
        bid_state=state,
        team_setup=team_setup,
        source_mode="manual",
    )

    assert result.decision == "PASS"
    assert result.source == "deterministic"
    assert "above the hard cap" in result.warning


def test_auction_agent_cannot_bid_above_its_own_maximum():
    session = _Session(
        [
            _auction_tool_call_payload(),
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    '{"decision":"BID","max_bid":17,'
                                    '"confidence":"medium","explanation":"Bid.",'
                                    '"alternatives":[]}'
                                ),
                            }
                        ],
                    }
                ]
            },
        ]
    )
    summary, state, team_setup = _auction_inputs(current_bid=18)
    result = AuctionStrategistService(api_key="key", session=session).recommend_auction(
        summary=summary,
        bid_state=state,
        team_setup=team_setup,
        source_mode="sleeper",
    )

    assert result.source == "deterministic"
    assert "above its own maximum" in result.warning
