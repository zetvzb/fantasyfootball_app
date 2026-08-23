import sys
from pathlib import Path


sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)


from src.config import (
    SEASON,
)

from src.fantasypros_client import (
    FantasyProsClient,
)

from src.fantasypros_intelligence import (
    normalize_fantasypros_intelligence,
)


client = FantasyProsClient()


rankings_response = (
    client.get_rankings(
        season=SEASON,
        week=0,
    )
)


players_response = (
    client.get_players_with_ecr()
)


players = (
    normalize_fantasypros_intelligence(
        rankings_response=(
            rankings_response
        ),
        players_response=(
            players_response
        ),
    )
)


print()
print("=" * 70)
print("FANTASYPROS INTELLIGENCE")
print("=" * 70)

print(
    "Players normalized:",
    len(players)
)


print()
print("TOP HALF-PPR PLAYERS")
print("-" * 70)


ranked = [
    player
    for player in players
    if player.half_ecr is not None
]


ranked.sort(
    key=lambda player: (
        player.half_ecr
    )
)


for player in ranked[:20]:

    print(
        player.player_name,
        "|",
        player.position,
        "| Half:",
        player.half_ecr,
        "| Pos:",
        player.half_position_rank,
        "| Dynasty:",
        player.dynasty_ecr,
        "| ADP:",
        player.adp,
        "| Std:",
        player.ecr_std,
    )