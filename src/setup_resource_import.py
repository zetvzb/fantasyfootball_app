from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional, Tuple

from src.auction_pool import build_sleeper_name_index, find_sleeper_id
from src.league_profile import ManagerIdentity
from src.league_setup_data import (
    HistoricalSale,
    KeeperRecord,
    SourceInfo,
)


IMPORT_SOURCE = SourceInfo(
    source="import",
    confidence=1.0,
    inferred=False,
    detail="Uploaded league resource",
)


@dataclass(frozen=True)
class SetupResourceImport:
    keeper_candidates: Tuple[KeeperRecord, ...] = ()
    historical_sales: Tuple[HistoricalSale, ...] = ()
    warnings: Tuple[str, ...] = ()


def _column_key(value: object) -> str:
    return "_".join(str(value).strip().lower().replace("/", " ").split())


_KEEPER_MARKER = re.compile(r"\s*\((?:k|keeper)\)\s*$", re.IGNORECASE)


def _text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def _strip_keeper_marker(name: str) -> str:
    """Drop a trailing "(k)"/"(K)"/"(keeper)" marker some workbooks use to
    flag a roster row as a kept player, so it doesn't corrupt name matching
    against the Sleeper player universe."""

    return _KEEPER_MARKER.sub("", name).strip()


def build_manager_aliases(
    managers: Mapping[str, ManagerIdentity],
) -> Dict[str, str]:
    """Map every known name/username/alias for each manager to their id.

    Shared by every uploaded-resource importer so a spreadsheet's Team
    column can be matched case-insensitively against a manager's id, team
    name, Sleeper username, or any recorded historical alias.
    """

    aliases: Dict[str, str] = {}
    for manager_id, identity in managers.items():
        aliases[manager_id.lower()] = manager_id
        for value in (
            identity.sleeper_team_name,
            identity.sleeper_username,
        ) + tuple(identity.historical_aliases):
            if value:
                aliases[str(value).strip().lower()] = manager_id
    return aliases


def _number(value: object) -> Optional[float]:
    text = _text(value).replace("$", "").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _first(row: Mapping[str, object], *keys: str) -> object:
    for key in keys:
        value = row.get(key)
        if _text(value):
            return value
    return None


def _manager_id(
    value: object,
    aliases: Mapping[str, str],
    default_manager_id: str,
) -> Optional[str]:
    text = _text(value)
    if not text:
        return default_manager_id or None
    return aliases.get(text.lower())


def parse_setup_resource_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    manager_aliases: Mapping[str, str],
    default_manager_id: str,
    current_season: int,
    sleeper_players: Optional[Mapping[str, dict]] = None,
) -> SetupResourceImport:
    """Normalize a keeper/history spreadsheet into typed setup records.

    When `sleeper_players` is supplied, every player name is matched
    against the real Sleeper player database (the same collision-safe
    matcher used everywhere else) so keeper records carry a real
    `sleeper_player_id` instead of just a name string. A row that can't
    be matched still imports -- a bad match shouldn't block a manual
    keeper -- but is called out as a warning so it doesn't quietly fail
    to exclude that player from the auction pool later.
    """

    aliases = {str(key).lower(): value for key, value in manager_aliases.items()}
    name_index = (
        build_sleeper_name_index(sleeper_players) if sleeper_players else {}
    )
    keepers = []
    history = []
    warnings = []
    for row_number, raw_row in enumerate(rows, start=2):
        row = {_column_key(key): value for key, value in raw_row.items()}
        player_name = _strip_keeper_marker(
            _text(_first(row, "player", "player_name", "name"))
        )
        if not player_name:
            warnings.append("Row {0}: player name is required.".format(row_number))
            continue
        record_type = _text(
            _first(row, "type", "record_type", "resource_type")
        ).lower()
        if not record_type:
            # A row carrying an explicit year AND a sale price is a past
            # auction result, not a keeper -- otherwise a plain draft-history
            # export (no Type column) would silently import every line as a
            # keeper and pull those players out of the auction pool.
            has_year = _number(_first(row, "year", "season")) is not None
            has_price = _number(_first(row, "price", "sale_price")) is not None
            record_type = "history" if (has_year and has_price) else "keeper"
        manager_id = _manager_id(
            _first(row, "team", "team_manager", "team_owner", "manager", "owner"),
            aliases,
            default_manager_id,
        )
        if manager_id is None:
            warnings.append(
                "Row {0}: team/manager could not be matched.".format(row_number)
            )
            continue
        position = _text(_first(row, "position", "pos")).upper() or None
        value = _number(
            _first(row, "value", "player_value", "future_value")
        )

        if record_type in {"history", "historical", "sale", "draft_history"}:
            price = _number(_first(row, "price", "sale_price"))
            year = _number(_first(row, "year", "season"))
            if price is None:
                warnings.append("Row {0}: historical sale price is required.".format(row_number))
                continue
            history.append(
                HistoricalSale(
                    year=int(year or current_season),
                    player_name=player_name,
                    price=int(round(price)),
                    manager_id=manager_id,
                    position=position,
                    source=IMPORT_SOURCE,
                )
            )
            continue

        if record_type in {"devy", "college", "taxi"}:
            warnings.append(
                "Row {0}: devy/college rows are no longer supported and "
                "were skipped.".format(row_number)
            )
            continue

        keeper_cost = _number(
            _first(row, "keeper_cost", "cost", "salary")
        )
        prior_cost = _number(_first(row, "prior_year_cost", "prior_cost"))

        sleeper_id = None
        if sleeper_players:
            sleeper_id = find_sleeper_id(player_name, name_index)
            if sleeper_id is None:
                warnings.append(
                    "Row {0}: '{1}' could not be matched to the Sleeper "
                    "player database -- check the spelling, or it won't "
                    "be excluded from the auction pool.".format(
                        row_number, player_name
                    )
                )

        keepers.append(
            KeeperRecord(
                manager_id=manager_id,
                player_name=player_name,
                position=position,
                cost=int(round(keeper_cost)) if keeper_cost is not None else None,
                cost_basis="explicit",
                prior_year_cost=(
                    int(round(prior_cost)) if prior_cost is not None else None
                ),
                future_values=(value,) if value is not None else (),
                status="candidate",
                sleeper_player_id=sleeper_id,
                source=IMPORT_SOURCE,
            )
        )

    return SetupResourceImport(
        keeper_candidates=tuple(keepers),
        historical_sales=tuple(history),
        warnings=tuple(warnings),
    )
