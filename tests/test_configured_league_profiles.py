from pathlib import Path

from src.college_domain import apply_college_rules
from src.league_registry import LeagueRegistry
from src.league_setup_data import CollegeRight, LeagueSetupData


def test_configured_bishop_profile_accepts_six_active_college_rights():
    repository_root = Path(__file__).resolve().parents[1]
    profile = LeagueRegistry(repository_root / "data" / "leagues").load(
        "1316602556939522048"
    )
    setup = LeagueSetupData(
        league_key=profile.league_key,
        college_players=[
            CollegeRight(
                manager_id="nobz24",
                player_name="College Player {0}".format(index),
                status="in_college",
                eligibility_status="unknown",
                promotion_status="taxi",
            )
            for index in range(6)
        ],
    )

    assert profile.college.enabled
    assert profile.college.max_college_players == 6
    assert apply_college_rules(league_profile=profile, setup_data=setup) is setup
