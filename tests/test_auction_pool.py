from src.auction_pool import normalize_player_name


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
