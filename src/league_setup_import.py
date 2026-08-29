from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Tuple

import pandas as pd


@dataclass(frozen=True)
class DetectedField:
    value: object
    detail: str


@dataclass(frozen=True)
class DetectedTeamBudget:
    amount: int
    # "auction_cash" = already the net dollars available for the next draft.
    # "pre_keeper" = a current/prior total (e.g. "Salary") that keeper costs
    # still need to be subtracted from, mirroring TeamBudget.budget_kind.
    budget_kind: str
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
    team_names: Tuple[str, ...] = ()
    team_budgets: Dict[str, DetectedTeamBudget] = field(default_factory=dict)
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
}

_SETTING_KEY_COLUMNS = {"setting", "field", "key", "parameter", "item"}
_SETTING_VALUE_COLUMNS = {"value"}

_TEAM_COLUMNS = {
    "team", "teams", "team_name", "manager", "manager_name",
    "owner", "owner_name", "franchise", "name",
}
_TEAM_BUDGET_COLUMNS = {"budget", "auction_budget", "cap", "salary_cap"}
_TEAM_CURRENT_COLUMNS = {"me", "is_me", "my_team", "current_team", "you"}
_PLAYER_ROW_COLUMNS = {"type", "player", "player_name"}
_TRUTHY = {"yes", "y", "true", "1", "x"}

# Labels scanned anywhere in a headerless sheet (e.g. a per-manager tab) for
# a "label in one cell, value in the next cell" budget. Tier A is already the
# net dollars available for the next auction; Tier B ("Salary") is a current
# roster-cost total that keeper costs still need to be subtracted from, so it
# maps to TeamBudget.budget_kind="pre_keeper" instead of "auction_cash".
_BUDGET_LABEL_TIER_A = {"draft budget", "budget", "cap", "auction budget"}
_BUDGET_LABEL_TIER_B = {"salary"}


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


def _grid(frame: pd.DataFrame) -> List[List[object]]:
    return frame.values.tolist()


def _header_keys(row: List[object]) -> List[str]:
    return [_column_key(value) for value in row]


def _rows_from_grid(grid: List[List[object]]) -> List[Dict[str, object]]:
    """Treat row 0 as a header and zip it against every following row."""

    header = _header_keys(grid[0])
    rows = []
    for raw_row in grid[1:]:
        row = {}
        for index, key in enumerate(header):
            if not key:
                continue
            row[key] = raw_row[index] if index < len(raw_row) else None
        rows.append(row)
    return rows


def _looks_like_settings_header(columns) -> bool:
    columns = set(columns)
    return bool(columns & _SETTING_KEY_COLUMNS) and bool(columns & _SETTING_VALUE_COLUMNS)


def _looks_like_player_header(columns) -> bool:
    return bool(set(columns) & _PLAYER_ROW_COLUMNS)


def _looks_like_teams_header(columns) -> bool:
    columns = set(columns)
    if _looks_like_player_header(columns):
        return False
    return bool(columns & _TEAM_COLUMNS)


def _parse_settings_rows(
    rows,
    *,
    sheet_name: str,
    detected: Dict[str, DetectedField],
    warnings: List[str],
) -> None:
    key_col = next((c for c in _SETTING_KEY_COLUMNS if c in (rows[0] if rows else {})), None)
    value_col = next((c for c in _SETTING_VALUE_COLUMNS if c in (rows[0] if rows else {})), None)
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
        if field_name is None or field_name in detected:
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


_NON_TEAM_LABELS = (
    _TEAM_COLUMNS | _SETTING_KEY_COLUMNS | _SETTING_VALUE_COLUMNS | _PLAYER_ROW_COLUMNS
)


def _is_repeated_header_row(row: Dict[str, object]) -> bool:
    """A season-boundary or section break inside a Type/Player sheet
    sometimes repeats the header row itself (e.g. a literal "Type" cell
    under the Type column) instead of leaving a blank spacer. Treating
    that as a real row would import a bogus "Player" player owned by
    "Team", so it's dropped the same way a repeated Teams-sheet header
    already is.
    """

    type_value = _column_key(_text(row.get("type")))
    if type_value and type_value in _NON_TEAM_LABELS:
        return True
    player_value = _column_key(
        _text(row.get("player") or row.get("player_name"))
    )
    return bool(player_value) and player_value in _NON_TEAM_LABELS


def _parse_teams_rows(
    rows,
    *,
    sheet_name: str,
    team_names: List[str],
    team_budgets: Dict[str, DetectedTeamBudget],
    current_team_holder: List[Optional[str]],
) -> bool:
    """Return True if this sheet actually contributed any team names.

    Only the first sheet that contributes team names is treated as
    authoritative (see the caller) -- real workbooks often repeat a
    Name/Team-style header on a second stacked table further down the
    same sheet (a new season's block, a second division, ...), and a
    later sheet may use different nicknames for the same 12 owners. Both
    are handled by claiming exactly one source rather than merging them.
    """

    sample = rows[0] if rows else {}
    team_col = next((c for c in _TEAM_COLUMNS if c in sample), None)
    budget_col = next((c for c in _TEAM_BUDGET_COLUMNS if c in sample), None)
    current_col = next((c for c in _TEAM_CURRENT_COLUMNS if c in sample), None)
    if team_col is None:
        return False

    contributed = False
    for row in rows:
        team_name = _text(row.get(team_col))
        if not team_name:
            continue
        # A repeated/stacked header further down the sheet (e.g. a second
        # season's table) reads back as a data row whose team-name cell is
        # literally "Name"/"Team"/etc. -- not a real team.
        if _column_key(team_name) in _NON_TEAM_LABELS:
            continue
        contributed = True
        if team_name not in team_names:
            team_names.append(team_name)
        if budget_col is not None:
            amount = _number(row.get(budget_col))
            if amount is not None:
                team_budgets[team_name] = DetectedTeamBudget(
                    amount=int(round(amount)),
                    budget_kind="auction_cash",
                    detail="Teams sheet '{0}'".format(sheet_name),
                )
        if current_col is not None and current_team_holder[0] is None:
            flag = _text(row.get(current_col)).strip().lower()
            if flag in _TRUTHY:
                current_team_holder[0] = team_name

    return contributed


def _matching_team_names(sheet_name: str, team_names: List[str]) -> List[str]:
    """Existing team names whose normalized form contains, or is contained
    by, the sheet name (e.g. "Brandon" <-> "Brandon C."). Never a loose
    similarity score -- containment only, so "Mike" doesn't ambiguously
    match both a "Mike C." and a "Mike S." tab without us noticing.
    """

    normalized_sheet = _column_key(sheet_name)
    matches = []
    for existing in team_names:
        normalized_existing = _column_key(existing)
        if not normalized_existing:
            continue
        if normalized_existing in normalized_sheet or normalized_sheet in normalized_existing:
            matches.append(existing)
    return matches


def _scan_sheet_for_budget_label(grid: List[List[object]]) -> Optional[Tuple[float, str, str]]:
    """Return (amount, tier, label) for the first Tier A/B label found."""

    tier_b_hit = None
    for row in grid:
        for column_index, cell in enumerate(row):
            label = _column_key(_text(cell))
            if not label:
                continue
            label_spaced = label.replace("_", " ")
            if column_index + 1 >= len(row):
                continue
            amount = _number(row[column_index + 1])
            if amount is None:
                continue
            if label_spaced in _BUDGET_LABEL_TIER_A:
                return (amount, "auction_cash", label_spaced)
            if label_spaced in _BUDGET_LABEL_TIER_B and tier_b_hit is None:
                tier_b_hit = (amount, "pre_keeper", label_spaced)
    return tier_b_hit


_ROSTER_PLAYER_COLUMNS = {"player", "player_name"}
_ROSTER_POSITION_COLUMNS = {"position", "pos"}
_ROSTER_COST_COLUMNS = {"salary", "cost", "price", "keeper_cost"}


def _find_roster_header(
    grid: List[List[object]],
) -> Optional[Tuple[int, int, Optional[int], int]]:
    """Scan the first 20 rows for a Player/Position/Salary-style header.

    Real per-manager tabs tuck this below a title row and a spacer (not
    at row 0 like every other recognized sheet shape), so this mirrors
    the same first-N-rows header search already used for the legacy
    Bishop workbook loader's historical-sale sheets
    (``src/league_data.py::_find_column_layout``), generalized to a
    plain pandas grid instead of an openpyxl worksheet.
    """

    for row_index in range(min(len(grid), 20)):
        row = grid[row_index]
        header_by_column = {
            column: _column_key(row[column])
            for column in range(min(len(row), 6))
        }
        player_col = next(
            (c for c, text in header_by_column.items() if text in _ROSTER_PLAYER_COLUMNS),
            None,
        )
        cost_col = next(
            (c for c, text in header_by_column.items() if text in _ROSTER_COST_COLUMNS),
            None,
        )
        if player_col is None or cost_col is None:
            continue
        position_col = next(
            (c for c, text in header_by_column.items() if text in _ROSTER_POSITION_COLUMNS),
            None,
        )
        return row_index, player_col, position_col, cost_col
    return None


def _scan_sheet_for_roster_rows(
    grid: List[List[object]],
) -> Optional[List[Dict[str, object]]]:
    """Return keeper-candidate rows from a per-manager roster tab, or
    None if this sheet doesn't have a recognizable Player/.../Salary
    table. Every rostered player is returned (not just ones flagged
    "(k)" in the source sheet) -- the app's own keeper editor is where
    a manager actually picks which of these to protect."""

    header = _find_roster_header(grid)
    if header is None:
        return None
    header_row_index, player_col, position_col, cost_col = header

    rows: List[Dict[str, object]] = []
    for raw_row in grid[header_row_index + 1 :]:
        player = _text(raw_row[player_col]) if player_col < len(raw_row) else ""
        if not player or _column_key(player) in _NON_TEAM_LABELS:
            continue
        position = (
            _text(raw_row[position_col])
            if position_col is not None and position_col < len(raw_row)
            else ""
        )
        cost = raw_row[cost_col] if cost_col < len(raw_row) else None
        rows.append(
            {"type": "keeper", "player": player, "position": position, "cost": cost}
        )
    return rows or None


_SALE_TEAM_MIN_ROWS = 5
_SALE_TEAM_MATCH_RATIO = 0.7


def _scan_sheet_for_sale_rows(
    grid: List[List[object]],
    team_names: List[str],
) -> Optional[List[Dict[str, object]]]:
    """Detect a headerless Player/Manager/Price draft-history sheet.

    Some workbooks record draft history as a bare 3-column grid with no
    header row at all (e.g. a "'25 Draft" tab). That shape can't be
    found by looking for header text, so instead this checks whether
    columns 0-2 actually behave like (player, known team name, price)
    for most of the sheet -- gated on already knowing the league's team
    names so an unrelated sheet can't be mistaken for one.
    """

    if not team_names:
        return None
    known_teams = {_column_key(name) for name in team_names if _column_key(name)}
    if not known_teams:
        return None

    candidate_rows: List[Dict[str, object]] = []
    matched = 0
    considered = 0
    for row in grid:
        if len(row) < 3:
            continue
        player = _text(row[0])
        team = _text(row[1])
        price = _number(row[2])
        if not player or not team:
            continue
        considered += 1
        if _column_key(team) in known_teams and price is not None:
            matched += 1
            candidate_rows.append(
                {"type": "history", "player": player, "team": team, "price": price}
            )

    if considered < _SALE_TEAM_MIN_ROWS:
        return None
    if matched < _SALE_TEAM_MIN_ROWS:
        return None
    if matched / considered < _SALE_TEAM_MATCH_RATIO:
        return None
    return candidate_rows


def _sheet_year_guess(sheet_name: str, current_season: int) -> int:
    """Best-effort season year from a sheet name like "'25 Draft" or
    "2024 Draft" -- falls back to the current season when nothing in the
    name looks like a year."""

    match = re.search(r"(20\d{2}|\d{2})", sheet_name)
    if not match:
        return current_season
    digits = match.group(1)
    if len(digits) == 4:
        return int(digits)
    year = 2000 + int(digits)
    return year


def parse_league_setup_workbook(
    sheets: Mapping[str, pd.DataFrame],
    *,
    current_season: int,
) -> LeagueSetupWorkbookImport:
    """Best-effort auto-fill of manual league setup from a spreadsheet.

    ``sheets`` values must be raw grids (``pd.read_excel``/``read_csv`` with
    ``header=None``) since real workbooks mix header-less per-manager tabs
    with proper tabular sheets, and this function decides per sheet which
    shape it is rather than assuming pandas' default header inference.

    Three shapes are recognized per sheet:
    - a two-column Setting/Value table for league-level scalars
    - a Team-name table (optionally with Budget/Current-team columns)
    - a Type/Player table, whose rows are returned untouched as
      ``leftover_rows`` for ``parse_setup_resource_rows`` to run once real
      manager ids exist (see src/setup_resource_import.py)

    Any other sheet is scanned for a "label in one cell, value in the next"
    budget (matching the label-adjacent-value convention already used by the
    legacy Bishop workbook loader in src/league_data.py, generalized here so
    it isn't coupled to a hard-coded manager list). A hit there treats the
    sheet as one more team, reconciled against already-known team names by
    substring containment only -- never fuzzy similarity, since wrongly
    merging two different owners' data is worse than missing a budget.

    Nothing is guessed: a field not found stays unset for manual entry.
    """

    detected: Dict[str, DetectedField] = {}
    warnings: List[str] = []
    team_names: List[str] = []
    team_budgets: Dict[str, DetectedTeamBudget] = {}
    current_team_holder: List[Optional[str]] = [None]
    leftover_rows: List[Dict[str, object]] = []
    deferred_scans: List[Tuple[str, List[List[object]]]] = []
    had_teams_sheet = False

    for sheet_name, frame in sheets.items():
        if frame is None or frame.empty:
            continue
        grid = _grid(frame)
        if not grid or not grid[0]:
            continue
        header_columns = _header_keys(grid[0])

        if _looks_like_settings_header(header_columns):
            _parse_settings_rows(
                _rows_from_grid(grid),
                sheet_name=str(sheet_name),
                detected=detected,
                warnings=warnings,
            )
            continue

        if _looks_like_teams_header(header_columns):
            # Only the first sheet that actually yields team names is
            # authoritative -- a workbook may have several sheets shaped
            # like a teams table (e.g. a standings sheet) using slightly
            # different nicknames for the same owners, and merging across
            # them is exactly the kind of guess we don't make.
            if not had_teams_sheet:
                had_teams_sheet = _parse_teams_rows(
                    _rows_from_grid(grid),
                    sheet_name=str(sheet_name),
                    team_names=team_names,
                    team_budgets=team_budgets,
                    current_team_holder=current_team_holder,
                )
            continue

        if _looks_like_player_header(header_columns):
            leftover_rows.extend(
                row
                for row in _rows_from_grid(grid)
                if not _is_repeated_header_row(row)
            )
            continue

        # Not a recognized tabular shape -- defer the free-form label scan
        # until after every sheet has been classified, so team-name
        # reconciliation has the full picture from any Teams sheet.
        deferred_scans.append((str(sheet_name), grid))

    # A per-tab budget belongs to at most one already-known team. Collect
    # every sheet's candidate team key(s) first, so a collision is visible
    # whether it comes from one sheet matching multiple teams (a very
    # generic sheet name) or multiple sheets independently matching the
    # same team (sibling tabs like "Mike C." and "Mike S." both containing
    # "Mike") -- either way that's a genuine ambiguity, and we drop it and
    # say so rather than guessing which owner it belongs to.
    hits_by_team: Dict[str, List[Tuple[str, float, str, str]]] = {}
    roster_hits_by_team: Dict[str, List[Tuple[str, List[Dict[str, object]]]]] = {}
    for sheet_name, grid in deferred_scans:
        candidates = _matching_team_names(sheet_name, team_names)
        if not candidates:
            if had_teams_sheet:
                # An authoritative Teams sheet exists and this sheet name
                # didn't match anything in it -- likely an unrelated sheet
                # (e.g. "Trades") that happened to contain a matching
                # label, not a team. Still surface a headerless sale table
                # below, since that's tagged per-row rather than per-sheet.
                candidates = []
            else:
                candidates = [sheet_name]

        hit = _scan_sheet_for_budget_label(grid)
        if hit is not None:
            amount, budget_kind, label = hit
            for team_key in candidates:
                hits_by_team.setdefault(team_key, []).append(
                    (sheet_name, amount, budget_kind, label)
                )

        roster_rows = _scan_sheet_for_roster_rows(grid)
        if roster_rows:
            for team_key in candidates:
                roster_hits_by_team.setdefault(team_key, []).append(
                    (sheet_name, roster_rows)
                )

        sale_rows = _scan_sheet_for_sale_rows(grid, team_names)
        if sale_rows:
            year = _sheet_year_guess(sheet_name, current_season)
            for row in sale_rows:
                leftover_rows.append({**row, "year": year})

    for team_key, hits in hits_by_team.items():
        distinct_sheets = sorted({sheet_name for sheet_name, _, _, _ in hits})
        if len(distinct_sheets) > 1:
            warnings.append(
                "Sheets {0} could all match team '{1}' -- enter its budget "
                "manually.".format(
                    ", ".join("'{0}'".format(name) for name in distinct_sheets), team_key
                )
            )
            continue
        sheet_name, amount, budget_kind, label = hits[0]
        if team_key not in team_names:
            team_names.append(team_key)
        team_budgets[team_key] = DetectedTeamBudget(
            amount=int(round(amount)),
            budget_kind=budget_kind,
            detail="Sheet '{0}', label '{1}'".format(sheet_name, label),
        )

    for team_key, hits in roster_hits_by_team.items():
        distinct_sheets = sorted({sheet_name for sheet_name, _ in hits})
        if len(distinct_sheets) > 1:
            warnings.append(
                "Sheets {0} could all match team '{1}' -- its roster wasn't "
                "imported, add keepers manually.".format(
                    ", ".join("'{0}'".format(name) for name in distinct_sheets), team_key
                )
            )
            continue
        sheet_name, roster_rows = hits[0]
        if team_key not in team_names:
            team_names.append(team_key)
        seen_players = set()
        for row in roster_rows:
            player_key = _column_key(row["player"])
            if player_key in seen_players:
                warnings.append(
                    "Sheet '{0}': duplicate player '{1}' on the roster -- "
                    "only the first was imported.".format(
                        sheet_name, row["player"]
                    )
                )
                continue
            seen_players.add(player_key)
            leftover_rows.append({**row, "team": team_key})

    return LeagueSetupWorkbookImport(
        league_name=detected.get("league_name"),
        season=detected.get("season"),
        scoring_format=detected.get("scoring_format"),
        roster_size=detected.get("roster_size"),
        auction_budget=detected.get("auction_budget"),
        minimum_bid=detected.get("minimum_bid"),
        max_keepers=detected.get("max_keepers"),
        keeper_escalation=detected.get("keeper_escalation"),
        team_names=tuple(team_names),
        team_budgets=team_budgets,
        current_team_guess=current_team_holder[0],
        leftover_rows=tuple(leftover_rows),
        warnings=tuple(warnings),
    )
