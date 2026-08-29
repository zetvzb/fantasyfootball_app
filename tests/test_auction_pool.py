from src.auction_pool import (
    NFL_TEAM_NAMES,
    build_sleeper_name_index,
    find_sleeper_id,
    normalize_player_name,
)


def _all_defense_players():
    return {
        abbr: {
            "position": "DEF",
            "team": abbr,
            "full_name": None,
            "first_name": None,
            "last_name": None,
        }
        for abbr in NFL_TEAM_NAMES
    }


def test_bare_city_name_resolves_to_its_defense():
    index = build_sleeper_name_index(_all_defense_players())
    assert find_sleeper_id("Houston", index) == "HOU"
    assert find_sleeper_id("houston", index) == "HOU"


def test_team_nickname_resolves_even_for_a_shared_city():
    index = build_sleeper_name_index(_all_defense_players())
    assert find_sleeper_id("Rams", index) == "LAR"
    assert find_sleeper_id("Chargers", index) == "LAC"
    assert find_sleeper_id("Giants", index) == "NYG"
    assert find_sleeper_id("Jets", index) == "NYJ"


def test_shared_city_alone_is_not_guessed():
    index = build_sleeper_name_index(_all_defense_players())
    assert find_sleeper_id("Los Angeles", index) is None
    assert find_sleeper_id("New York", index) is None


def test_relocated_franchise_old_city_still_resolves():
    index = build_sleeper_name_index(_all_defense_players())
    assert find_sleeper_id("St. Louis", index) == "LAR"
    assert find_sleeper_id("San Diego", index) == "LAC"
    assert find_sleeper_id("Oakland", index) == "LV"


def test_generational_suffix_mismatch_normalizes_to_same_key():
    # Sleeper: "Kenneth Walker", FantasyPros: "Kenneth Walker III" -- these
    # must key identically or every direct-dict valuation lookup misses.
    assert normalize_player_name("Kenneth Walker") == normalize_player_name(
        "Kenneth Walker III"
    )


def test_various_generational_suffixes_are_stripped():
    assert normalize_player_name("Michael Pittman Jr.") == normalize_player_name(
        "Michael Pittman"
    )
    assert normalize_player_name("Marvin Harrison Jr") == normalize_player_name(
        "Marvin Harrison"
    )
    assert normalize_player_name("Odell Beckham Sr") == normalize_player_name(
        "Odell Beckham"
    )
    assert normalize_player_name("Some Player II") == normalize_player_name(
        "Some Player"
    )
    assert normalize_player_name("Some Player IV") == normalize_player_name(
        "Some Player"
    )


def test_apostrophes_and_periods_are_still_stripped():
    assert normalize_player_name("Ja'Marr Chase") == "jamarr chase"
    assert normalize_player_name("D'Andre Swift") == "dandre swift"
    assert normalize_player_name("A.J. Brown") == "aj brown"


def test_suffix_only_stripped_at_the_end_not_mid_name():
    # "Ivy" etc. must not be mangled by a loose "ii" match.
    assert normalize_player_name("Ivy League") == "ivy league"


def test_none_and_empty_input():
    assert normalize_player_name(None) == ""
    assert normalize_player_name("") == ""
