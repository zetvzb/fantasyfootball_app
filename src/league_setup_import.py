from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

import pandas as pd


@dataclass(frozen=True)
class DetectedField:
    value: object
    detail: str


@dataclass(frozen=True)
class LeagueSetupWorkbookImport:
    league_name: Optional[DetectedField] = None
    season: Optional[DetectedField] = None
    scoring_format: Optional[DetectedField] = None
    roster_size: Optional[DetectedField] = None
    auction_budget: Optional[DetectedField] = None
    minimum_bid: Optional[DetectedField] = None
    max_keepers: Optional[DetectedField] = None
    keeper_escalation: Optional[DetectedField] = None
    max_devy: Optional[DetectedField] = None
    team_names: Tuple[str, ...] = ()
    team_budgets: Dict[str, int] = field(default_factory=dict)
    current_team_guess: Optional[str] = None
    leftover_rows: Tuple[Dict[str, object], ...] = ()
    warnings: Tuple[str, ...] = ()


SCALAR_FIELDS = (
    "league_name",
    "season",
    "scoring_format",
    "roster_size",
    "auction_budget",
    "minimum_bid",
    "max_keepers",
    "keeper_escalation",
    "max_devy",
)

FIELD_LABELS = {
    "league_name": "League name",
    "season": "Season",
    "scoring_format": "Reception scoring",
    "roster_size": "Roster size",
    "auction_budget": "Default budget",
    "minimum_bid": "Minimum bid",
    "max_keepers": "Maximum keepers",
    "keeper_escalation": "Keeper value increase",
    "max_devy": "Maximum devy players",
}

_SETTING_ALIASES = {
    "league_name": {"league_name", "league", "name", "league_title"},
    "season": {"season", "year", "draft_year"},
    "scoring_format": {
        "scoring",
        "scoring_format",
        "reception_scoring",
        "ppr",
        "reception_points",
    },
    "roster_size": {"roster_size", "roster", "team_size", "roster_spots"},
    "auction_budget": {
        "budget",
        "auction_budget",
        "default_budget",
        "general_budget",
        "salary_cap",
        "cap",
    },
    "minimum_bid": {"minimum_bid", "min_bid", "minimum_auction_bid"},
    "max_keepers": {"max_keepers", "keepers", "keeper_limit", "keeper_max"},
    "keeper_escalation": {
        "keeper_escalation",
        "keeper_increase",
        "escalation",
        "annual_increase",
        "keeper_value_increase",
    },
    "max_devy": {"max_devy", "devy", "devy_limit", "max_devy_players", "taxi_limit"},
}

_SETTING_KEY_COLUMNS = {"setting", "field", "key", "parameter", "item"}
_SETTING_VALUE_COLUMNS = {"value"}

_TEAM_COLUMNS = {"team", "teams", "manager", "owner", "franchise"}
_TEAM_BUDGET_COLUMNS = {"budget", "auction_budget", "cap", "salary_cap", "cash"}
_TEAM_CURRENT_COLUMNS = {"me", "is_me", "my_team", "current_team", "you"}
_PLAYER_ROW_COLUMNS = {"type", "player", "player_name"}
_TRUTHY = {"yes", "y", "true", "1", "x"}


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


def _scoring_from_text(text: str) -> Optional[str]:
    normalized = text.strip().lower().replace(" ", "_")
    if normalized in {"ppr", "1", "1.0", "full_ppr"}:
        return "ppr"
    if normalized in {"half_ppr", "0.5", "half", "0.5_ppr"}:
        return "half_ppr"
    return None


def _normalized_rows(frame: pd.DataFrame) -> List[Dict[str, object]]:
    return [
        {_column_key(key): value for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _looks_like_settings_sheet(columns: Iterable[str]) -> bool:
    columns = set(columns)
    return bool(columns & _SETTING_KEY_COLUMNS) and bool(columns & _SETTING_VALUE_COLUMNS)


def _looks_like_player_sheet(columns: Iterable[str]) -> bool:
    return bool(set(columns) & _PLAYER_ROW_COLUMNS)


def _looks_like_teams_sheet(columns: Iterable[str]) -> bool:
    columns = set(columns)
    if _looks_like_player_sheet(columns):
        return False
    return bool(columns & _TEAM_COLUMNS)


def _parse_settings_rows(
    rows: Iterable[Dict[str, object]],
    *,
    sheet_name: str,
    detected: Dict[str, DetectedField],
    warnings: List[str],
) -> None:
    key_col = None
    value_col = None
    for row in rows:
        if key_col is None:
            for candidate in _SETTING_KEY_COLUMNS:
                if candidate in row:
                    key_col = candidate
                    break
        if value_col is None:
            for candidate in _SETTING_VALUE_COLUMNS:
                if candidate in row:
                    value_col = candidate
                    break
        break
    if key_col is None or value_col is None:
        return

    for row_number, row in enumerate(rows, start=2):
        label = _column_key(_text(row.get(key_col)))
        raw_value = row.get(value_col)
        if not label or not _text(raw_value):
            continue
        field_name = None
        for candidate_field, aliases in _SETTING_ALIASES.items():
            if label in aliases:
                field_name = candidate_field
                break
        if field_name is None:
            continue
        if field_name in detected:
            continue

        if field_name == "league_name":
            detected[field_name] = DetectedField(
                value=_text(raw_value),
                detail="Settings sheet '{0}', row {1}".format(sheet_name, row_number),
            )
        elif field_name == "scoring_format":
            scoring = _scoring_from_text(_text(raw_value))
            if scoring is None:
                warnings.append(
                    "Settings sheet '{0}', row {1}: could not interpret scoring "
                    "value '{2}'.".format(sheet_name, row_number, _text(raw_value))
                )
                continue
            detected[field_name] = DetectedField(
                value=scoring,
                detail="Settings sheet '{0}', row {1}".format(sheet_name, row_number),
            )
        else:
            number = _number(raw_value)
            if number is None:
                warnings.append(
                    "Settings sheet '{0}', row {1}: '{2}' is not a number for {3}.".format(
                        sheet_name, row_number, _text(raw_value), FIELD_LABELS[field_name]
                    )
                )
                continue
            detected[field_name] = DetectedField(
                value=int(round(number)),
                detail="Settings sheet '{0}', row {1}".format(sheet_name, row_number),
            )


def _parse_teams_rows(
    rows: Iterable[Dict[str, object]],
    *,
    team_names: List[str],
    team_budgets: Dict[str, int],
    current_team_holder: List[Optional[str]],
) -> None:
    team_col = budget_col = current_col = None
    for row in rows:
        for candidate in _TEAM_COLUMNS:
            if team_col is None and candidate in row:
                team_col = candidate
        for candidate in _TEAM_BUDGET_COLUMNS:
            if budget_col is None and candidate in row:
                budget_col = candidate
        for candidate in _TEAM_CURRENT_COLUMNS:
            if current_col is None and candidate in row:
                current_col = candidate
        break
    if team_col is None:
        return

    for row in rows:
        team_name = _text(row.get(team_col))
        if not team_name:
            continue
        if team_name not in team_names:
            team_names.append(team_name)
        if budget_col is not None:
            amount = _number(row.get(budget_col))
            if amount is not None:
                team_budgets[team_name] = int(round(amount))
        if current_col is not None and current_team_holder[0] is None:
            flag = _text(row.get(current_col)).strip().lower()
            if flag in _TRUTHY:
                current_team_holder[0] = team_name


def parse_league_setup_workbook(
    sheets: Mapping[str, pd.DataFrame],
    *,
    current_season: int,
) -> LeagueSetupWorkbookImport:
    """Best-effort auto-fill of manual league setup from a spreadsheet.

    Recognizes two optional table shapes per sheet: a two-column
    Setting/Value table for league-level scalars, and a Team-name table
    (with optional Budget/Current-team columns). Any sheet carrying
    Type/Player columns is left untouched here and returned as
    ``leftover_rows`` so the existing ``parse_setup_resource_rows``
    keeper/devy/history importer can run on it once manager ids exist.
    """

    detected: Dict[str, DetectedField] = {}
    warnings: List[str] = []
    team_names: List[str] = []
    team_budgets: Dict[str, int] = {}
    current_team_holder: List[Optional[str]] = [None]
    leftover_rows: List[Dict[str, object]] = []

    for sheet_name, frame in sheets.items():
        if frame is None or frame.empty:
            continue
        rows = _normalized_rows(frame)
        if not rows:
            continue
        columns = rows[0].keys()

        if _looks_like_settings_sheet(columns):
            _parse_settings_rows(
                rows, sheet_name=str(sheet_name), detected=detected, warnings=warnings
            )
            continue

        if _looks_like_teams_sheet(columns):
            _parse_teams_rows(
                rows,
                team_names=team_names,
                team_budgets=team_budgets,
                current_team_holder=current_team_holder,
            )
            continue

        if _looks_like_player_sheet(columns):
            leftover_rows.extend(rows)

    return LeagueSetupWorkbookImport(
        league_name=detected.get("league_name"),
        season=detected.get("season"),
        scoring_format=detected.get("scoring_format"),
        roster_size=detected.get("roster_size"),
        auction_budget=detected.get("auction_budget"),
        minimum_bid=detected.get("minimum_bid"),
        max_keepers=detected.get("max_keepers"),
        keeper_escalation=detected.get("keeper_escalation"),
        max_devy=detected.get("max_devy"),
        team_names=tuple(team_names),
        team_budgets=team_budgets,
        current_team_guess=current_team_holder[0],
        leftover_rows=tuple(leftover_rows),
        warnings=tuple(warnings),
    )
