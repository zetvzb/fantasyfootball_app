import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from src.league_setup_data import (
    LeagueSetupData,
    MANUAL_SOURCE,
    TeamBudget,
)
from src.auction_pool import build_auction_pool
from src.draft_setup import build_team_draft_setup_from_setup_data
from src.workbook_enrichment import enrich_setup_from_optional_workbook


def _profile():
    return SimpleNamespace(
        league_key="league",
        auction=SimpleNamespace(base_budget=200, minimum_bid=1),
        roster=SimpleNamespace(roster_size=5),
        keepers=SimpleNamespace(max_keepers=6),
    )


def _baseline():
    return LeagueSetupData(
        league_key="league",
        budgets={
            "team": TeamBudget(
                manager_id="team",
                amount=200,
            )
        },
    )


def _workbook_data(managers=None, warnings=None):
    return SimpleNamespace(
        managers=managers or {},
        historical_sales=[],
        warnings=warnings or [],
    )


def test_minimal_mode_starts_without_workbook_or_workbook_parser():
    result = enrich_setup_from_optional_workbook(
        baseline=_baseline(),
        league_profile=_profile(),
        workbook_path=None,
    )

    assert result.loaded is False
    assert result.error is None
    assert result.setup_data.budgets["team"].amount == 200
    assert any("No league workbook" in warning for warning in result.setup_data.warnings)

    team_setup = build_team_draft_setup_from_setup_data(
        manager_id="team",
        league_setup_data=result.setup_data,
        selected_keeper_names=[],
        league_profile=_profile(),
    )
    pool = build_auction_pool(
        sleeper_players={
            "p1": {
                "full_name": "Available Player",
                "position": "WR",
                "active": True,
                "team": "CHI",
            }
        },
        league_data=result.setup_data,
        team_setups={"team": team_setup},
    )
    assert team_setup.entering_cash == 200
    assert [player.player_name for player in pool.available_players] == [
        "Available Player"
    ]

    process = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import src.league_setup_data; "
                "import src.draft_setup; import src.workbook_enrichment; "
                "assert 'src.league_data' not in sys.modules"
            ),
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr


def test_partial_workbook_mode_keeps_baseline_for_missing_sections():
    result = enrich_setup_from_optional_workbook(
        baseline=_baseline(),
        league_profile=_profile(),
        workbook_path=Path("partial.xlsx"),
        loader=lambda unused_path: _workbook_data(
            warnings=["Historical sheet unavailable"]
        ),
    )

    assert result.loaded is True
    assert result.setup_data.budgets["team"].amount == 200
    assert result.setup_data.historical_sales == []
    assert "Historical sheet unavailable" in result.setup_data.warnings


def test_full_workbook_enriches_baseline_but_manual_data_stays_authoritative():
    workbook_manager = SimpleNamespace(
        pre_keeper_budget=400,
        keeper_options=[],
    )
    result = enrich_setup_from_optional_workbook(
        baseline=_baseline(),
        league_profile=_profile(),
        workbook_path=Path("full.xlsx"),
        loader=lambda unused_path: _workbook_data(
            managers={"team": workbook_manager}
        ),
    )
    manual = LeagueSetupData(
        league_key="league",
        budgets={
            "team": TeamBudget(
                manager_id="team",
                amount=425,
                source=MANUAL_SOURCE,
            )
        },
    )
    effective = result.setup_data.merged_with(manual)

    assert result.loaded is True
    assert result.setup_data.budgets["team"].amount == 400
    assert effective.budgets["team"].amount == 425
    assert effective.budgets["team"].source.source == "manual"


def test_broken_workbook_falls_back_to_baseline():
    def fail(unused_path):
        raise ValueError("malformed workbook")

    result = enrich_setup_from_optional_workbook(
        baseline=_baseline(),
        league_profile=_profile(),
        workbook_path=Path("broken.xlsx"),
        loader=fail,
    )

    assert result.loaded is False
    assert result.error == "malformed workbook"
    assert result.setup_data.budgets["team"].amount == 200
