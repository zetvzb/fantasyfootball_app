from src.fantasypros_client import _unescape_strings


def test_unescape_strings_fixes_double_encoded_apostrophe():
    payload = {"player_name": "Ja&amp;#39;Marr Chase"}
    assert _unescape_strings(payload) == {"player_name": "Ja'Marr Chase"}


def test_unescape_strings_leaves_plain_strings_unchanged():
    payload = {"player_name": "Justin Jefferson", "rank": 1}
    assert _unescape_strings(payload) == payload


def test_unescape_strings_walks_nested_lists_and_dicts():
    payload = {
        "players": [
            {"player_name": "Amon-Ra St. Brown &amp; Co."},
            {"player_name": "D&#39;Andre Swift"},
        ]
    }
    result = _unescape_strings(payload)
    assert result["players"][0]["player_name"] == "Amon-Ra St. Brown & Co."
    assert result["players"][1]["player_name"] == "D'Andre Swift"


def test_unescape_strings_leaves_non_string_values_untouched():
    assert _unescape_strings(42) == 42
    assert _unescape_strings(None) is None
    assert _unescape_strings(3.5) == 3.5
