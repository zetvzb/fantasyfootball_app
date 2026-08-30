from src.sleeper_history import fetch_sleeper_auction_history


class _FakeSleeper:
    def __init__(self, leagues, drafts, picks, rosters=None, users=None):
        self._leagues = leagues
        self._drafts = drafts
        self._picks = picks
        self._rosters = rosters or {}
        self._users = users or {}
        self.calls = []

    def get_league(self, league_id):
        self.calls.append(("league", league_id))
        return self._leagues[league_id]

    def get_league_drafts(self, league_id):
        return self._drafts.get(league_id, [])

    def get_draft_picks(self, draft_id):
        return self._picks.get(draft_id, [])

    def get_league_rosters(self, league_id):
        return self._rosters.get(league_id, [])

    def get_league_users(self, league_id):
        return self._users.get(league_id, [])


SLEEPER_PLAYERS = {
    "1001": {"full_name": "Past Stud WR", "position": "WR"},
    "1002": {"full_name": "Past Stud RB", "position": "RB"},
}


def test_walks_previous_league_and_collects_auction_sales():
    leagues = {
        "cur": {"season": "2026", "previous_league_id": "y2025"},
        "y2025": {"season": "2025", "previous_league_id": "y2024"},
        "y2024": {"season": "2024", "previous_league_id": ""},
    }
    drafts = {
        "y2025": [{"draft_id": "d2025", "type": "auction", "status": "complete", "season": "2025"}],
        "y2024": [{"draft_id": "d2024", "type": "snake", "status": "complete", "season": "2024"}],
    }
    picks = {
        "d2025": [
            {"player_id": "1001", "roster_id": "1", "metadata": {"amount": "45"}},
            {"player_id": "1002", "roster_id": "2", "metadata": {"amount": "$30"}},
            {"player_id": "1002", "roster_id": "3", "is_keeper": True, "metadata": {"amount": "5"}},
            {"player_id": "9999", "roster_id": "2", "metadata": {}},  # no price -> skipped
        ],
    }
    rosters = {"y2025": [{"roster_id": 1, "owner_id": "u1"}, {"roster_id": 2, "owner_id": "u2"}]}
    users = {"y2025": [
        {"user_id": "u1", "display_name": "Alice", "metadata": {"team_name": "Alice's Team"}},
        {"user_id": "u2", "display_name": "Bob", "metadata": {}},
    ]}

    client = _FakeSleeper(leagues, drafts, picks, rosters, users)
    sales, warnings = fetch_sleeper_auction_history(
        client, "cur", current_season=2026, sleeper_players=SLEEPER_PLAYERS
    )

    assert warnings == []
    by_name = {s.player_name: s for s in sales}
    assert set(by_name) == {"Past Stud WR", "Past Stud RB"}
    assert by_name["Past Stud WR"].price == 45
    assert by_name["Past Stud WR"].year == 2025
    assert by_name["Past Stud WR"].manager_raw == "Alice's Team"
    assert by_name["Past Stud RB"].price == 30
    assert by_name["Past Stud RB"].manager_raw == "Bob"
    # the snake draft in 2024 contributes nothing
    assert all(s.year == 2025 for s in sales)


def test_skips_current_season_and_stops_at_chain_end():
    leagues = {
        "cur": {"season": "2026", "previous_league_id": ""},
    }
    drafts = {"cur": [{"draft_id": "dcur", "type": "auction", "status": "drafting", "season": "2026"}]}
    picks = {"dcur": [{"player_id": "1001", "roster_id": "1", "metadata": {"amount": "10"}}]}

    client = _FakeSleeper(leagues, drafts, picks)
    sales, warnings = fetch_sleeper_auction_history(
        client, "cur", current_season=2026, sleeper_players=SLEEPER_PLAYERS
    )
    assert sales == []
