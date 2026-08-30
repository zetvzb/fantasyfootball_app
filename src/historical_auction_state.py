from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple


@dataclass(frozen=True)
class ReplayIssue:
    severity: str
    code: str
    message: str
    league_key: str
    season: int
    manager_id: str = ""
    sale_order: int = 0


@dataclass(frozen=True)
class ReplayResult:
    features: Tuple[dict, ...]
    issues: Tuple[ReplayIssue, ...]

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


def _integer(value: object) -> int:
    return int(float(value or 0))


def _number(value: object) -> float:
    return float(value or 0.0)


def _draft_key(row: Mapping[str, object]) -> Tuple[str, int]:
    return str(row.get("league_key") or ""), _integer(row.get("season"))


def replay_auction_states(
    sales: Sequence[Mapping[str, object]],
    opening_states: Sequence[Mapping[str, object]],
) -> ReplayResult:
    openings_by_draft: Dict[Tuple[str, int], List[Mapping[str, object]]] = {}
    for opening in opening_states:
        openings_by_draft.setdefault(_draft_key(opening), []).append(opening)

    sales_by_draft: Dict[Tuple[str, int], List[Mapping[str, object]]] = {}
    for sale in sales:
        sales_by_draft.setdefault(_draft_key(sale), []).append(sale)

    features = []
    issues = []
    for key, draft_sales in sorted(sales_by_draft.items()):
        league_key, season = key
        openings = openings_by_draft.get(key, [])
        if not openings:
            issues.append(
                ReplayIssue(
                    "error", "missing_opening_states",
                    "Draft has sales but no opening team states.", league_key, season,
                )
            )
            continue

        teams = {}
        for opening in openings:
            manager_id = str(opening.get("manager_id") or "")
            teams[manager_id] = {
                "cash": _integer(opening.get("opening_cash")),
                "spots": _integer(opening.get("opening_roster_spots")),
                "minimum_bid": max(1, _integer(opening.get("minimum_bid"))),
            }

        expected_sales = sum(team["spots"] for team in teams.values())
        position_sales: Dict[str, int] = {}
        position_spend: Dict[str, float] = {}
        ordered_sales = sorted(
            draft_sales,
            key=lambda row: _integer(row.get("overall_order")),
        )
        for sale_index, sale in enumerate(ordered_sales):
            manager_id = str(sale.get("winning_manager_id") or "")
            order = _integer(sale.get("overall_order"))
            team = teams.get(manager_id)
            if team is None:
                issues.append(
                    ReplayIssue(
                        "error", "missing_team_state",
                        "Sale winner has no opening team state.",
                        league_key, season, manager_id, order,
                    )
                )
                continue

            price = _integer(sale.get("winning_price"))
            position = str(sale.get("position") or "").upper()
            league_cash = sum(value["cash"] for value in teams.values())
            league_spots = sum(value["spots"] for value in teams.values())
            league_reserve = sum(
                value["spots"] * value["minimum_bid"]
                for value in teams.values()
            )
            team_reserve_after_purchase = max(0, team["spots"] - 1) * team["minimum_bid"]
            legal_max_bid = max(0, team["cash"] - team_reserve_after_purchase)
            prior_position_sales = position_sales.get(position, 0)
            prior_position_spend = position_spend.get(position, 0.0)
            features.append(
                {
                    **dict(sale),
                    "sale_index": sale_index + 1,
                    "expected_draft_sales": expected_sales,
                    "auction_stage": (
                        float(sale_index) / expected_sales if expected_sales else 0.0
                    ),
                    "team_cash_before": team["cash"],
                    "team_open_spots_before": team["spots"],
                    "team_legal_max_before": legal_max_bid,
                    "league_cash_before": league_cash,
                    "league_open_spots_before": league_spots,
                    "league_reserve_before": league_reserve,
                    "league_discretionary_cash_before": max(
                        0, league_cash - league_reserve
                    ),
                    "position_sales_before": prior_position_sales,
                    "position_spend_before": round(prior_position_spend, 2),
                    "position_average_price_before": round(
                        prior_position_spend / prior_position_sales, 2
                    ) if prior_position_sales else 0.0,
                }
            )

            if team["spots"] <= 0:
                issues.append(
                    ReplayIssue(
                        "error", "sale_after_roster_full",
                        "Manager bought a player after filling the roster.",
                        league_key, season, manager_id, order,
                    )
                )
            if price > team["cash"]:
                issues.append(
                    ReplayIssue(
                        "error", "sale_exceeds_cash",
                        "Sale price exceeds the manager cash before purchase.",
                        league_key, season, manager_id, order,
                    )
                )
            if price > legal_max_bid:
                issues.append(
                    ReplayIssue(
                        "error", "sale_breaks_minimum_reserve",
                        "Sale price breaks the minimum-bid reserve.",
                        league_key, season, manager_id, order,
                    )
                )

            team["cash"] -= price
            team["spots"] -= 1
            position_sales[position] = prior_position_sales + 1
            position_spend[position] = prior_position_spend + price

        unfilled = sum(max(0, team["spots"]) for team in teams.values())
        if unfilled:
            issues.append(
                ReplayIssue(
                    "warning", "draft_has_unrecorded_slots",
                    "Draft replay ends with {0} unrecorded roster slots.".format(unfilled),
                    league_key, season,
                )
            )

    return ReplayResult(tuple(features), tuple(issues))


def read_csv_rows(path: Path) -> List[dict]:
    with Path(path).open(encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write_feature_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
