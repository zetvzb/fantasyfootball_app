from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Tuple

from src.league_setup_data import (
    CollegeRight,
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
    college_players: Tuple[CollegeRight, ...] = ()
    historical_sales: Tuple[HistoricalSale, ...] = ()
    warnings: Tuple[str, ...] = ()


def _column_key(value: object) -> str:
    return "_".join(str(value).strip().lower().replace("/", " ").split())


def _text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


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
) -> SetupResourceImport:
    """Normalize a keeper/devy/history spreadsheet into typed setup records."""

    aliases = {str(key).lower(): value for key, value in manager_aliases.items()}
    keepers = []
    college = []
    history = []
    warnings = []
    for row_number, raw_row in enumerate(rows, start=2):
        row = {_column_key(key): value for key, value in raw_row.items()}
        player_name = _text(_first(row, "player", "player_name", "name"))
        if not player_name:
            warnings.append("Row {0}: player name is required.".format(row_number))
            continue
        record_type = _text(
            _first(row, "type", "record_type", "resource_type")
        ).lower() or "keeper"
        manager_id = _manager_id(
            _first(row, "team", "manager", "owner"),
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
            college.append(
                CollegeRight(
                    manager_id=manager_id,
                    player_name=player_name,
                    school_or_team=_text(
                        _first(row, "school", "school_or_nfl_team")
                    ) or None,
                    position=position,
                    status=_text(row.get("status")).lower() or "unknown",
                    eligibility_status=(
                        _text(row.get("eligibility")).lower() or "unknown"
                    ),
                    promotion_status=(
                        _text(row.get("promotion_state")).lower() or "taxi"
                    ),
                    original_manager_id=manager_id,
                    future_values=(value,) if value is not None else (),
                    source=IMPORT_SOURCE,
                )
            )
            continue

        keeper_cost = _number(
            _first(row, "keeper_cost", "cost", "salary")
        )
        prior_cost = _number(_first(row, "prior_year_cost", "prior_cost"))
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
                source=IMPORT_SOURCE,
            )
        )

    return SetupResourceImport(
        keeper_candidates=tuple(keepers),
        college_players=tuple(college),
        historical_sales=tuple(history),
        warnings=tuple(warnings),
    )
