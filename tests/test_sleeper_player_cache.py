import json
import os
import time

import pytest
import requests

from src.sleeper_client import SleeperClient


def _client_with_cache(tmp_path):
    client = SleeperClient()
    client.cache_dir = tmp_path
    client.player_cache_file = tmp_path / "sleeper_players.json"
    return client


def test_stale_player_universe_is_used_when_sleeper_is_unavailable(tmp_path, monkeypatch):
    client = _client_with_cache(tmp_path)
    cached = {"1": {"full_name": "Cached Player", "position": "WR"}}
    client.player_cache_file.write_text(json.dumps(cached), encoding="utf-8")
    stale_time = time.time() - ((client.PLAYER_CACHE_HOURS + 1) * 3600)
    os.utime(str(client.player_cache_file), (stale_time, stale_time))

    def unavailable(endpoint):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(client, "_get", unavailable)
    assert client.get_players() == cached


def test_player_universe_failure_without_cache_is_explicit(tmp_path, monkeypatch):
    client = _client_with_cache(tmp_path)

    def unavailable(endpoint):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(client, "_get", unavailable)
    with pytest.raises(requests.ConnectionError, match="offline"):
        client.get_players()
