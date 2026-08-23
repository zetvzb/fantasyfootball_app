import sys
from collections import Counter
from pathlib import Path


sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

from src.league_data import (
    LeagueDataLoader,
)


loader = LeagueDataLoader(
    "data/league.xlsx"
)

data = loader.load()


print()
print("=" * 70)
print("MANAGERS")
print("=" * 70)

for manager_id, manager in (
    data.managers.items()
):

    print()
    print(
        manager_id.upper()
    )

    print(
        f"Sheet: "
        f"{manager.spreadsheet_tab}"
    )

    print(
        f"Pre-Keeper Budget: "
        f"${manager.pre_keeper_budget}"
    )

    print(
        f"Keeper Options: "
        f"{len(manager.keeper_options)}"
    )

    print(
        f"College Picks: "
        f"{manager.college_picks}"
    )


print()
print("=" * 70)
print("HISTORICAL SALES")
print("=" * 70)

sales_by_year = Counter(
    sale.year
    for sale in data.historical_sales
)

for year, count in sorted(
    sales_by_year.items()
):
    print(
        f"{year}: {count} auction sales"
    )


print()
print("=" * 70)
print("COLLEGE RIGHTS")
print("=" * 70)

college_by_manager = Counter(
    player.manager_id
    for player in data.college_players
)

for manager_id, count in sorted(
    college_by_manager.items()
):
    print(
        f"{manager_id}: "
        f"{count} players"
    )


print()
print("=" * 70)
print("WARNINGS")
print("=" * 70)

if not data.warnings:
    print("None")

else:
    for warning in data.warnings:
        print(
            f"- {warning}"
        )