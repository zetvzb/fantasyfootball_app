import unittest
from types import SimpleNamespace

from src.recommendation import (
    BidRecommendation,
    build_recommendation_index,
    build_value_lookup,
    calculate_bid_recommendations,
    calculate_scarcity,
    clamp,
    numeric,
    recommendation_strategy,
)


def auction_value(name, baseline=20.0, position="WR"):
    return SimpleNamespace(
        player_name=name,
        position=position,
        baseline_value=baseline,
    )


class RecommendationHelpersTests(unittest.TestCase):
    def test_numeric_and_clamp_handle_invalid_and_out_of_range_values(self):
        self.assertEqual(numeric(None, default=3.5), 3.5)
        self.assertEqual(numeric("not a number", default=3.5), 3.5)
        self.assertEqual(numeric("12.5"), 12.5)
        self.assertEqual(clamp(-1.0), 0.0)
        self.assertEqual(clamp(2.0), 1.0)
        self.assertEqual(clamp(0.4), 0.4)

    def test_build_value_lookup_normalizes_player_names(self):
        value = auction_value("Ja'Marr Chase")

        lookup = build_value_lookup([value])

        self.assertIs(lookup["jamarr chase"], value)

    def test_strategy_boundaries_cover_all_labels(self):
        self.assertEqual(recommendation_strategy(100, 108, 0.8), "AGGRESSIVE BUY")
        self.assertEqual(recommendation_strategy(100, 108, 0.79), "PURSUE")
        self.assertEqual(recommendation_strategy(100, 100, 0.5), "BUY AT MARKET")
        self.assertEqual(recommendation_strategy(100, 90, 0.5), "DISCIPLINED")
        self.assertEqual(recommendation_strategy(100, 89, 0.5), "LET SOMEONE ELSE PAY")

    def test_scarcity_returns_zero_for_missing_player(self):
        scarcity, alternative = calculate_scarcity(
            player_name="Missing Player",
            position="WR",
            alternatives_by_position={
                "WR": [{"player_name": "Available Player", "vorp": 30}],
            },
        )

        self.assertEqual(scarcity, 0.0)
        self.assertIsNone(alternative)

    def test_scarcity_marks_last_player_as_maximally_scarce(self):
        scarcity, alternative = calculate_scarcity(
            player_name="Last Player",
            position="WR",
            alternatives_by_position={
                "WR": [{"player_name": "Last Player", "vorp": 30}],
            },
        )

        self.assertEqual(scarcity, 1.0)
        self.assertIsNone(alternative)

    def test_recommendation_index_uses_normalized_names(self):
        recommendation = BidRecommendation(
            player_name="A.J. Brown",
            position="WR",
            expected_market_value=30,
            baseline_value=28,
            do_not_exceed=31,
            legal_max_bid=40,
            my_need_score=0.8,
            scarcity_score=0.5,
            threat_score=20,
            value_edge=1,
            alternative_player=None,
            alternative_market_value=None,
            alternative_vorp=None,
            player_vorp=25,
            strategy="PURSUE",
        )

        index = build_recommendation_index([recommendation])

        self.assertIs(index["aj brown"], recommendation)


class RecommendationEngineTests(unittest.TestCase):
    def test_engine_returns_empty_when_my_team_is_unknown(self):
        result = calculate_bid_recommendations(
            available_players=[],
            auction_values=[],
            market_values=[],
            player_values=[],
            threat_summaries=[],
            team_need_profiles={},
            my_manager_id="unknown",
        )

        self.assertEqual(result, [])

    def test_engine_skips_players_without_auction_values(self):
        player = SimpleNamespace(player_name="Unpriced Player", position="WR")
        team = SimpleNamespace(max_bid=100, need_scores={"WR": 0.5})

        result = calculate_bid_recommendations(
            available_players=[player],
            auction_values=[],
            market_values=[],
            player_values=[],
            threat_summaries=[],
            team_need_profiles={"me": team},
            my_manager_id="me",
        )

        self.assertEqual(result, [])

    def test_engine_caps_ceiling_at_legal_max_and_exposes_next_option(self):
        player = SimpleNamespace(player_name="Ja'Marr Chase", position="WR")
        alternative = SimpleNamespace(player_name="Second Receiver", position="WR")
        team = SimpleNamespace(max_bid=50, need_scores={"WR": 1.0})

        result = calculate_bid_recommendations(
            available_players=[player, alternative],
            auction_values=[
                auction_value("Ja'Marr Chase", baseline=100),
                auction_value("Second Receiver", baseline=10),
            ],
            market_values=[
                SimpleNamespace(player_name="Ja'Marr Chase", expected_market_value=100),
                SimpleNamespace(player_name="Second Receiver", expected_market_value=10),
            ],
            player_values=[
                SimpleNamespace(player_name="Ja'Marr Chase", vorp=100),
                SimpleNamespace(player_name="Second Receiver", vorp=10),
            ],
            threat_summaries=[
                SimpleNamespace(player_name="Ja'Marr Chase", top_threat_score=90),
            ],
            team_need_profiles={"me": team},
            my_manager_id="me",
        )

        recommendation = result[0]

        self.assertEqual(recommendation.player_name, "Ja'Marr Chase")
        self.assertEqual(recommendation.legal_max_bid, 50)
        self.assertEqual(recommendation.do_not_exceed, 50)
        self.assertEqual(recommendation.alternative_player, "Second Receiver")
        self.assertEqual(recommendation.alternative_vorp, 10.0)
        self.assertIn("limited by legal max bid", recommendation.reasons)


if __name__ == "__main__":
    unittest.main()