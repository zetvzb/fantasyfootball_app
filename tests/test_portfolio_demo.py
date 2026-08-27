from src.explanation_service import (
    DecisionExplanationInput,
    DecisionExplanationService,
)
from src.league_registry import LeagueRegistry
from src.league_setup_data import LeagueSetupStore
from src.portfolio_demo import (
    DEMO_LEAGUE_KEY,
    DEMO_MANAGER_ID,
    build_demo_scenario,
    install_portfolio_demo,
)


class _ExplanationResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "KEEP because the deterministic score is 94.5.",
                        }
                    ],
                }
            ]
        }


class _ExplanationSession:
    def __init__(self):
        self.request = None

    def post(self, url, json, headers, timeout):
        self.request = (url, json, headers, timeout)
        return _ExplanationResponse()


def _explanation_input():
    return DecisionExplanationInput(
        subject="Brock Bowers",
        decision="KEEP",
        numeric_facts={"strategy_score": 94.5, "keeper_cost": 21.0},
        reason_codes=("positive_surplus", "future_upside"),
        deterministic_explanation="KEEP from the deterministic engine.",
    )


def test_demo_scenario_is_deterministic_and_legally_reserve_aware():
    first = build_demo_scenario()
    second = build_demo_scenario()
    assert first == second
    assert first.profile.league_key == DEMO_LEAGUE_KEY
    assert len(first.profile.managers) == 8
    assert len(set(budget.amount for budget in first.setup.budgets.values())) > 1
    assert len(first.setup.keepers_for(DEMO_MANAGER_ID)) == 7
    assert first.keeper_optimization.recommended_scenario is not None
    assert [value.keeper_count for value in first.keeper_optimization.scenarios] == [
        4,
        5,
        6,
    ]
    for scenario in first.keeper_optimization.scenarios:
        assert scenario.remaining_cash >= scenario.minimum_reserve
    assert first.target_value <= first.soft_cap <= first.hard_cap
    assert first.hard_cap <= first.live_cap.adjusted_cap


def test_demo_install_round_trips_profile_and_setup(tmp_path):
    registry = LeagueRegistry(tmp_path / "leagues")
    setup_store = LeagueSetupStore(tmp_path / "league_setup")
    profile = install_portfolio_demo(registry, setup_store)
    reinstalled = install_portfolio_demo(registry, setup_store)
    assert reinstalled == profile
    loaded_profile = registry.load(DEMO_LEAGUE_KEY)
    assert loaded_profile.league_key == profile.league_key
    assert loaded_profile.league_name == profile.league_name
    assert loaded_profile.metadata == profile.metadata
    assert set(loaded_profile.managers) == set(profile.managers)
    setup = setup_store.load(DEMO_LEAGUE_KEY)
    assert len(setup.budgets) == 8
    assert setup.metadata["portfolio_demo"] is True
    assert {value.player_name for value in setup.keepers}


def test_explanation_service_falls_back_without_api_key():
    result = DecisionExplanationService(api_key="").explain(
        _explanation_input(), use_ai=True
    )
    assert result.source == "deterministic"
    assert result.text == "KEEP from the deterministic engine."
    assert "OPENAI_API_KEY" in result.warning


def test_explanation_service_cannot_change_numeric_engine_output():
    session = _ExplanationSession()
    result = DecisionExplanationService(
        api_key="secret", model="gpt-5.4", session=session
    ).explain(_explanation_input(), use_ai=True)
    assert result.source == "openai"
    assert result.model == "gpt-5.4"
    assert "94.5" in result.text
    url, request, headers, timeout = session.request
    assert url == "https://api.openai.com/v1/responses"
    assert request["store"] is False
    assert '"strategy_score": 94.5' in request["input"]
    assert "Do not change" in request["instructions"]
    assert headers["Authorization"] == "Bearer secret"
    assert timeout == 20
