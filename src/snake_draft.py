from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from src.auction_pool import normalize_player_name
from src.roster_optimizer import (
    FLEX_SLOT_POSITIONS,
    build_remaining_slots,
    candidate_eligible,
    slot_multiplier,
)

FLEX_POSITIONS = {"RB", "WR", "TE"}
NON_STARTER_SLOTS = set(FLEX_SLOT_POSITIONS) | {"BN", "BENCH", "IR", "TAXI"}


# =========================================================
# PICK ORDER MATH
# =========================================================

def slot_for_pick_no(pick_no: int, team_count: int) -> Tuple[int, int]:
    """Return (round_number, slot) for a 1-indexed overall snake-draft pick."""
    if team_count <= 0:
        raise ValueError("team_count must be positive.")
    if pick_no <= 0:
        raise ValueError("pick_no must be positive.")

    round_number = (pick_no - 1) // team_count + 1
    position_in_round = (pick_no - 1) % team_count + 1

    if round_number % 2 == 1:
        slot = position_in_round
    else:
        slot = team_count - position_in_round + 1

    return round_number, slot


def pick_no_for_slot(round_number: int, slot: int, team_count: int) -> int:
    """Return the 1-indexed overall pick number for a given round/slot."""
    if round_number % 2 == 1:
        return (round_number - 1) * team_count + slot
    return (round_number - 1) * team_count + (team_count - slot + 1)


def next_pick_no_for_slot(current_pick_no: int, slot: int, team_count: int) -> int:
    """First pick_no >= current_pick_no assigned to `slot` in snake order."""
    pick_no = current_pick_no
    while slot_for_pick_no(pick_no, team_count)[1] != slot:
        pick_no += 1
    return pick_no


# =========================================================
# DATA OBJECTS
# =========================================================

@dataclass(frozen=True)
class DraftPick:
    pick_no: int
    round: int
    slot: int
    roster_id: Optional[int] = None
    manager_id: Optional[str] = None
    player_id: Optional[str] = None
    player_name: Optional[str] = None
    position: Optional[str] = None


@dataclass(frozen=True)
class SnakeDraftState:
    team_count: int
    total_rounds: int

    current_pick_no: int
    current_round: int
    current_slot: int
    current_manager_id: Optional[str]
    on_the_clock_is_me: bool

    next_picks: Tuple[DraftPick, ...] = ()
    upcoming_picks_for_viewer: Tuple[DraftPick, ...] = ()
    made_picks: Tuple[DraftPick, ...] = ()
    viewer_slot: Optional[int] = None

    drafted_player_ids: frozenset = field(default_factory=frozenset)
    roster_by_manager: Mapping[str, Tuple[DraftPick, ...]] = field(default_factory=dict)

    is_complete: bool = False


# =========================================================
# STATE ASSEMBLY
# =========================================================

def _sleeper_player_display_name(player_id: str, sleeper_players: Mapping[str, Mapping[str, object]]) -> str:
    player = sleeper_players.get(str(player_id)) or {}
    full_name = player.get("full_name")
    if full_name:
        return str(full_name).strip()
    parts = [player.get("first_name"), player.get("last_name")]
    joined = " ".join(str(part) for part in parts if part)
    return joined.strip() or str(player_id)


def build_snake_draft_state(
    *,
    draft: Mapping[str, object],
    picks: Sequence[Mapping[str, object]],
    league_profile,
    sleeper_players: Mapping[str, Mapping[str, object]],
    viewer_manager_id: Optional[str] = None,
    lookahead: int = 8,
) -> SnakeDraftState:
    draft = draft or {}

    slot_to_roster_id_raw = dict(draft.get("slot_to_roster_id") or {})
    slot_to_roster_id: Dict[int, int] = {}
    for slot, roster_id in slot_to_roster_id_raw.items():
        if roster_id is None:
            continue
        slot_to_roster_id[int(slot)] = int(roster_id)

    team_count = len(slot_to_roster_id) or len(league_profile.managers) or 0

    settings = draft.get("settings") or {}
    total_rounds = int(
        settings.get("rounds")
        or league_profile.roster.roster_size
        or 0
    )

    roster_id_to_manager: Dict[int, str] = {
        identity.sleeper_roster_id: manager_id
        for manager_id, identity in league_profile.managers.items()
        if identity.sleeper_roster_id is not None
    }

    made_picks: List[DraftPick] = []
    drafted_player_ids = set()
    roster_by_manager: Dict[str, List[DraftPick]] = {}

    for raw_pick in picks or ():
        player_id = raw_pick.get("player_id")
        pick_no = raw_pick.get("pick_no")
        if player_id is None or pick_no is None:
            continue

        roster_id = raw_pick.get("roster_id")
        round_number = raw_pick.get("round")
        slot = raw_pick.get("draft_slot")
        if round_number is None or slot is None:
            round_number, slot = slot_for_pick_no(int(pick_no), team_count)

        manager_id = (
            roster_id_to_manager.get(int(roster_id))
            if roster_id is not None
            else None
        )
        sleeper_player = sleeper_players.get(str(player_id)) or {}

        pick = DraftPick(
            pick_no=int(pick_no),
            round=int(round_number),
            slot=int(slot),
            roster_id=int(roster_id) if roster_id is not None else None,
            manager_id=manager_id,
            player_id=str(player_id),
            player_name=_sleeper_player_display_name(player_id, sleeper_players),
            position=sleeper_player.get("position"),
        )
        made_picks.append(pick)
        drafted_player_ids.add(str(player_id))
        if manager_id is not None:
            roster_by_manager.setdefault(manager_id, []).append(pick)

    made_picks.sort(key=lambda pick: pick.pick_no)
    made_pick_nos = {pick.pick_no for pick in made_picks}

    total_picks = team_count * total_rounds if team_count and total_rounds else 0
    is_complete = bool(total_picks) and len(made_pick_nos) >= total_picks

    current_pick_no: Optional[int] = None
    if not is_complete and team_count:
        candidate = 1
        while candidate in made_pick_nos:
            candidate += 1
        if total_picks and candidate > total_picks:
            is_complete = True
        else:
            current_pick_no = candidate

    next_picks: List[DraftPick] = []
    if current_pick_no and team_count:
        pick_no = current_pick_no
        while len(next_picks) < lookahead and (not total_picks or pick_no <= total_picks):
            round_number, slot = slot_for_pick_no(pick_no, team_count)
            roster_id = slot_to_roster_id.get(slot)
            manager_id = (
                roster_id_to_manager.get(roster_id)
                if roster_id is not None
                else None
            )
            next_picks.append(
                DraftPick(
                    pick_no=pick_no,
                    round=round_number,
                    slot=slot,
                    roster_id=roster_id,
                    manager_id=manager_id,
                )
            )
            pick_no += 1

    current_round, current_slot, current_manager_id = 0, 0, None
    if current_pick_no and team_count:
        current_round, current_slot = slot_for_pick_no(current_pick_no, team_count)
        current_roster_id = slot_to_roster_id.get(current_slot)
        current_manager_id = (
            roster_id_to_manager.get(current_roster_id)
            if current_roster_id is not None
            else None
        )

    upcoming_for_viewer = tuple(
        pick for pick in next_picks
        if viewer_manager_id and pick.manager_id == viewer_manager_id
    )

    viewer_slot: Optional[int] = None
    if viewer_manager_id:
        manager_to_roster_id = {
            manager_id: roster_id
            for roster_id, manager_id in roster_id_to_manager.items()
        }
        roster_id_to_slot = {
            roster_id: slot for slot, roster_id in slot_to_roster_id.items()
        }
        viewer_roster_id = manager_to_roster_id.get(viewer_manager_id)
        if viewer_roster_id is not None:
            viewer_slot = roster_id_to_slot.get(viewer_roster_id)

    return SnakeDraftState(
        team_count=team_count,
        total_rounds=total_rounds,
        current_pick_no=current_pick_no or 0,
        current_round=current_round,
        current_slot=current_slot,
        current_manager_id=current_manager_id,
        on_the_clock_is_me=bool(viewer_manager_id) and current_manager_id == viewer_manager_id,
        next_picks=tuple(next_picks),
        upcoming_picks_for_viewer=upcoming_for_viewer,
        made_picks=tuple(made_picks),
        viewer_slot=viewer_slot,
        drafted_player_ids=frozenset(drafted_player_ids),
        roster_by_manager={
            manager_id: tuple(picks_list)
            for manager_id, picks_list in roster_by_manager.items()
        },
        is_complete=is_complete,
    )


# =========================================================
# ROSTER NEED
# =========================================================

@dataclass(frozen=True)
class RosterNeed:
    starter_gaps: Mapping[str, int]
    flex_gap: int
    open_spots: int
    flex_gaps: Mapping[str, int] = field(default_factory=dict)


def build_roster_need(
    *,
    drafted_positions: Sequence[str],
    starting_lineup: Sequence[str],
    roster_size: int,
) -> RosterNeed:
    """Compute a manager's still-open starter/flex/bench needs from what
    they've drafted so far in a snake draft."""

    starter_demand = Counter(
        slot for slot in starting_lineup if slot not in NON_STARTER_SLOTS
    )
    flex_demand = Counter(
        slot for slot in starting_lineup if slot in FLEX_SLOT_POSITIONS
    )

    filled = Counter(str(position).upper() for position in drafted_positions if position)

    starter_gaps = {
        position: max(0, required - filled.get(position, 0))
        for position, required in starter_demand.items()
    }

    remaining = {
        position: max(0, filled.get(position, 0) - starter_demand.get(position, 0))
        for position in {"QB", "RB", "WR", "TE"}
    }
    flex_gaps = {}
    for slot, demand in sorted(
        flex_demand.items(),
        key=lambda item: len(FLEX_SLOT_POSITIONS[item[0]]),
    ):
        unfilled = 0
        for _ in range(demand):
            eligible = FLEX_SLOT_POSITIONS[slot]
            available = [
                position for position in eligible if remaining.get(position, 0) > 0
            ]
            if available:
                selected = max(available, key=lambda position: remaining[position])
                remaining[selected] -= 1
            else:
                unfilled += 1
        if unfilled:
            flex_gaps[slot] = unfilled
    flex_gap = sum(flex_gaps.values())

    open_spots = max(0, int(roster_size) - sum(filled.values()))

    return RosterNeed(
        starter_gaps=starter_gaps,
        flex_gap=flex_gap,
        open_spots=open_spots,
        flex_gaps=flex_gaps,
    )


# =========================================================
# WHO TO DRAFT NEXT
# =========================================================

NEED_BONUS_STARTER = 6.0
NEED_BONUS_FLEX = 3.0

# A position is "running out" once fewer than this many still-startable
# (VORP > 0) players remain in the pool. Scarcity ramps in linearly below
# that floor so a thin position outweighs a marginal VORP edge elsewhere --
# validated against a Monte Carlo draft simulation showing that prioritizing
# a position at its scarcity cliff beats pure best-player-available in
# leagues with heavy FLEX demand (2x RB/WR/TE FLEX craters the RB pool
# fastest, but the mechanism is position-agnostic).
SCARCITY_FLOOR = 10
SCARCITY_WEIGHT = 4.0


@dataclass(frozen=True)
class DraftBoardEntry:
    player_name: str
    position: str
    vorp: float
    need_bonus: float
    utility: float
    projected_points: float
    scarcity_bonus: float = 0.0


def build_draft_board(
    *,
    player_values: Sequence[object],
    drafted_player_names: Sequence[str],
    roster_need: Optional[RosterNeed] = None,
    limit: int = 200,
) -> List[DraftBoardEntry]:
    """Rank available players for a snake-draft pick.

    Reuses the same VORP (`PlayerValue`) intelligence the auction cockpit
    already computes -- there is no dollar concept here, just who is the
    best player left, weighted toward the viewer's open roster need and
    toward positions whose startable depth is running out.
    """

    drafted_keys = {normalize_player_name(name) for name in drafted_player_names}
    starter_gaps = roster_need.starter_gaps if roster_need else {}
    flex_gaps = roster_need.flex_gaps if roster_need else {}

    available = [
        value
        for value in player_values
        if normalize_player_name(value.player_name) not in drafted_keys
    ]

    remaining_startable_by_position = Counter(
        value.position for value in available if float(value.vorp) > 0
    )

    entries = []
    for value in available:
        need_bonus = 0.0
        if starter_gaps.get(value.position, 0) > 0:
            need_bonus += NEED_BONUS_STARTER
        elif any(
            gap > 0 and value.position in FLEX_SLOT_POSITIONS.get(slot, set())
            for slot, gap in flex_gaps.items()
        ):
            need_bonus += NEED_BONUS_FLEX

        remaining = remaining_startable_by_position.get(value.position, 0)
        scarcity_bonus = SCARCITY_WEIGHT * max(0, SCARCITY_FLOOR - remaining) / SCARCITY_FLOOR

        entries.append(
            DraftBoardEntry(
                player_name=value.player_name,
                position=value.position,
                vorp=float(value.vorp),
                need_bonus=need_bonus,
                scarcity_bonus=scarcity_bonus,
                utility=float(value.vorp) + need_bonus + scarcity_bonus,
                projected_points=float(value.projected_points),
            )
        )

    entries.sort(key=lambda entry: entry.utility, reverse=True)
    return entries[:limit]


# =========================================================
# REMAINING ROSTER PLAN
# =========================================================

@dataclass(frozen=True)
class SnakeRosterPlanEntry:
    slot: str
    player_name: str
    position: str
    vorp: float
    utility: float
    is_filler: bool = False


@dataclass(frozen=True)
class SnakeRosterPlan:
    feasible: bool
    total_utility: float
    entries: Tuple[SnakeRosterPlanEntry, ...] = ()
    warnings: Tuple[str, ...] = ()


@dataclass
class _SlotCandidate:
    player_name: str
    position: str
    utility: float


def optimize_snake_roster_plan(
    *,
    roster_need: RosterNeed,
    draft_board: Sequence[DraftBoardEntry],
    beam_width: int = 60,
) -> SnakeRosterPlan:
    """Project a full remaining-roster plan from here to the last pick.

    Unlike the auction cockpit's cash-constrained beam search, a snake
    draft has no price tradeoff -- every remaining pick is "free," so this
    is a slot-assignment beam search over `draft_board` utility alone.
    """

    slots = build_remaining_slots(
        open_spots=roster_need.open_spots,
        starter_gaps=dict(roster_need.starter_gaps),
        flex_gap=roster_need.flex_gap,
        flex_gaps=dict(roster_need.flex_gaps),
    )
    if not slots:
        return SnakeRosterPlan(feasible=True, total_utility=0.0)

    pool = [
        _SlotCandidate(entry.player_name, entry.position, entry.utility)
        for entry in draft_board
    ]

    beam: List[Tuple[float, Tuple[str, ...], Tuple[SnakeRosterPlanEntry, ...]]] = [
        (0.0, (), ())
    ]

    for slot in slots:
        eligible = [candidate for candidate in pool if candidate_eligible(candidate, slot)]
        eligible.sort(
            key=lambda candidate: candidate.utility * slot_multiplier(slot, candidate.position),
            reverse=True,
        )
        eligible = eligible[: max(beam_width, 1)]

        next_beam: List[Tuple[float, Tuple[str, ...], Tuple[SnakeRosterPlanEntry, ...]]] = []
        for utility_so_far, selected_keys, entries in beam:
            selected = set(selected_keys)
            branched = False
            for candidate in eligible:
                key = normalize_player_name(candidate.player_name)
                if key in selected:
                    continue
                branched = True
                score = candidate.utility * slot_multiplier(slot, candidate.position)
                entry = SnakeRosterPlanEntry(
                    slot=slot,
                    player_name=candidate.player_name,
                    position=candidate.position,
                    vorp=candidate.utility,
                    utility=score,
                )
                next_beam.append(
                    (utility_so_far + score, selected_keys + (key,), entries + (entry,))
                )
            if not branched:
                filler = SnakeRosterPlanEntry(
                    slot=slot,
                    player_name="(best available at pick time)",
                    position=slot,
                    vorp=0.0,
                    utility=0.0,
                    is_filler=True,
                )
                next_beam.append((utility_so_far, selected_keys, entries + (filler,)))

        next_beam.sort(key=lambda state: state[0], reverse=True)
        beam = next_beam[:beam_width]

    if not beam:
        return SnakeRosterPlan(
            feasible=False,
            total_utility=0.0,
            warnings=("No eligible players found for the remaining roster.",),
        )

    best_utility, _, best_entries = beam[0]
    return SnakeRosterPlan(feasible=True, total_utility=best_utility, entries=best_entries)


# =========================================================
# BYE WEEK AWARENESS
# =========================================================
#
# Bye-week collisions are a display/warning overlay only -- deliberately
# kept out of `build_draft_board`'s utility score. A team's true bye-week
# risk depends on bench depth still to be drafted (unknown mid-draft), so
# baking a hard penalty into VORP could talk a viewer out of the best
# player on the board over a risk that later picks may resolve anyway.
# Surfacing it as a warning keeps the decision with the human.

def load_bye_weeks(csv_path: str) -> Dict[str, int]:
    """Best-effort player_name -> bye_week lookup from a FantasyPros rankings
    export. Returns {} if the file is missing or malformed -- bye-week
    awareness is a nice-to-have overlay, never a reason to break the board.
    """
    import csv
    import os

    lookup: Dict[str, int] = {}
    if not csv_path or not os.path.exists(csv_path):
        return lookup
    try:
        with open(csv_path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                name = row.get("player_name")
                bye = row.get("bye_week")
                if not name or not bye:
                    continue
                try:
                    lookup[normalize_player_name(name)] = int(bye)
                except ValueError:
                    continue
    except OSError:
        return {}
    return lookup


def bye_week_stack_warnings(
    *,
    candidates: Sequence[DraftBoardEntry],
    my_drafted_player_names: Sequence[str],
    bye_weeks: Mapping[str, int],
    stack_threshold: int = 2,
) -> Dict[str, str]:
    """Flag candidates that would give the viewer `stack_threshold`-or-more
    already-rostered players sharing a bye week. Keyed by player_name;
    empty when bye data is unavailable or nothing collides.
    """
    my_byes = Counter(
        bye_weeks[normalize_player_name(name)]
        for name in my_drafted_player_names
        if normalize_player_name(name) in bye_weeks
    )

    warnings: Dict[str, str] = {}
    for entry in candidates:
        bye = bye_weeks.get(normalize_player_name(entry.player_name))
        if bye is None:
            continue
        already_on_bye = my_byes.get(bye, 0)
        if already_on_bye >= stack_threshold:
            warnings[entry.player_name] = (
                "Bye week {0} collision: you'd have {1} rostered players "
                "out that week.".format(bye, already_on_bye + 1)
            )
    return warnings


# =========================================================
# RUNOUT RISK (survival probability)
# =========================================================
#
# Closed-form stand-in for a full Monte Carlo draft simulation: treats a
# player's true draft slot as Normal(average_rank, rank_stddev) -- both
# already published per-player by FantasyPros ECR -- and asks how much of
# that distribution falls beyond a target pick number. This is an
# independent-per-player approximation (it ignores that picks are without
# replacement), so treat it as "should I reach now" triage, not a precise
# guarantee -- a full simulation (see the Monte Carlo draft-strategy
# analysis) is the more rigorous version of the same idea.

def load_adp_distribution(csv_path: str) -> Dict[str, Tuple[float, float]]:
    """Best-effort player_name -> (average_rank, rank_stddev) lookup from a
    FantasyPros rankings export. Returns {} if the file is missing or
    malformed -- runout-risk is a nice-to-have overlay, never a reason to
    break the board.
    """
    import csv
    import os

    lookup: Dict[str, Tuple[float, float]] = {}
    if not csv_path or not os.path.exists(csv_path):
        return lookup
    try:
        with open(csv_path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                name = row.get("player_name")
                avg = row.get("average_rank")
                std = row.get("rank_stddev")
                if not name or not avg:
                    continue
                try:
                    lookup[normalize_player_name(name)] = (
                        float(avg),
                        float(std) if std else 1.0,
                    )
                except ValueError:
                    continue
    except OSError:
        return {}
    return lookup


def survival_probability(
    *,
    average_rank: float,
    rank_stddev: float,
    target_pick_no: int,
) -> float:
    """Estimated probability a player is still undrafted at target_pick_no."""
    import math

    stddev = max(float(rank_stddev), 0.5)
    z = (float(target_pick_no) - float(average_rank)) / stddev
    normal_cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2)))
    return max(0.0, min(1.0, 1.0 - normal_cdf))


# =========================================================
# LIVE TEAM VALUE LEADERBOARD
# =========================================================

@dataclass(frozen=True)
class TeamValueEntry:
    manager_id: str
    picks_made: int
    total_vorp: float
    total_projected_points: float


def build_team_value_leaderboard(
    *,
    roster_by_manager: Mapping[str, Sequence[object]],
    player_values: Sequence[object],
) -> List[TeamValueEntry]:
    """Rank every manager by the VORP/points they've actually drafted so far.

    Reuses the same league-scoring-aware VORP the draft board ranks by, so
    this reflects real value in *your* league's format, not generic ADP --
    unlike a raw ECR-based comparison, it already accounts for this
    league's roster construction and scoring settings.
    """

    value_by_name = {
        normalize_player_name(value.player_name): value for value in player_values
    }

    entries = []
    for manager_id, picks in roster_by_manager.items():
        total_vorp = 0.0
        total_points = 0.0
        for pick in picks:
            player_name = getattr(pick, "player_name", None)
            if not player_name:
                continue
            value = value_by_name.get(normalize_player_name(player_name))
            if value is None:
                continue
            total_vorp += float(value.vorp)
            total_points += float(value.projected_points)
        entries.append(
            TeamValueEntry(
                manager_id=manager_id,
                picks_made=len(picks),
                total_vorp=total_vorp,
                total_projected_points=total_points,
            )
        )

    entries.sort(key=lambda entry: entry.total_vorp, reverse=True)
    return entries
