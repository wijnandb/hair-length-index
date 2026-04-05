"""Compute winning streaks and generate the Hair Length Index."""

import argparse
import json
import logging
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

from scripts.config import DATA_DIR, MVP_LEAGUE, STREAK_THRESHOLD, get_hair_tier
from scripts.db import get_all_teams, get_connection, get_team_matches, init_db

# How many recent matches to include in JSON output
RECENT_MATCHES_LIMIT = 20

# Competition names that indicate cup/super cup data (fallback when competition_type is wrong)
_CUP_KEYWORDS = (
    "cup", "beker", "pokal", "copa", "coppa", "coupe", "shield", "supercup",
    "supercoppa", "supercopa", "trophee", "trophée", "trophy",
)


def _is_cup_by_name(comp_name: str | None) -> bool:
    """Check if a competition name indicates a cup match (fallback for bad competition_type)."""
    if not comp_name:
        return False
    lower = comp_name.lower()
    return any(kw in lower for kw in _CUP_KEYWORDS)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def slugify(name: str) -> str:
    """Convert team name to URL-friendly slug."""
    # Normalize unicode (ö→o, é→e, etc.)
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _team_result(match, team_id: int, result_field: str = "result_90min") -> str | None:
    """Get W/D/L for a team from a match row.

    result_field is 'result_90min' (official) or 'result_final' (fan).
    Returns 'W', 'D', or 'L' from the perspective of the given team.
    """
    result = match[result_field]
    if result is None:
        return None

    is_home = match["home_team_id"] == team_id
    if result == "D":
        return "D"
    elif result == "H":
        return "W" if is_home else "L"
    else:  # "A"
        return "L" if is_home else "W"


def find_last_streak(
    matches: list,
    team_id: int,
    threshold: int = STREAK_THRESHOLD,
    result_field: str = "result_90min",
) -> dict:
    """Find the most recent N-win streak in a team's match history.

    Matches should be sorted by date DESCENDING (most recent first).

    Returns a dict describing the streak (or lack thereof).
    """
    if not matches:
        return {
            "found": False,
            "streak_length": 0,
            "streak_end_date": None,
            "streak_start_date": None,
            "matches_since": 0,
            "days_since": None,
            "competitions_in_streak": [],
            "search_depth": None,
            "current_form": [],
        }

    # Build the result sequence: most recent match first
    results = []
    for m in matches:
        r = _team_result(m, team_id, result_field)
        if r is not None:
            results.append({
                "result": r,
                "date": m["date"],
                "competition_id": m["competition_id"],
                "competition_name": m["competition_name"],
            })

    if not results:
        return {
            "found": False,
            "streak_length": 0,
            "streak_end_date": None,
            "streak_start_date": None,
            "matches_since": 0,
            "days_since": None,
            "competitions_in_streak": [],
            "search_depth": results[-1]["date"] if results else None,
            "current_form": [],
        }

    # Current form: last 10 results (most recent first)
    current_form = [r["result"] for r in results[:10]]

    # Scan backward from most recent looking for a streak of >= threshold wins
    # We need to find the most recent completed streak of threshold+ wins.
    #
    # Strategy: walk through results (most recent first). Track consecutive wins.
    # When a non-win breaks the streak, check if we had enough.
    # But we need the MOST RECENT such streak, so we track as we go.

    best_streak = None
    current_streak_wins = 0
    current_streak_start_idx = 0

    for i, entry in enumerate(results):
        if entry["result"] == "W":
            current_streak_wins += 1
        else:
            # Streak broken. Did we have enough?
            if current_streak_wins >= threshold:
                # This streak ended at results[i-1] (the previous match)
                # and started at results[current_streak_start_idx]
                streak_end_idx = current_streak_start_idx  # most recent win (lowest index)
                streak_start_idx = i - 1  # oldest win in streak (highest index)
                best_streak = {
                    "end_idx": streak_end_idx,
                    "start_idx": streak_start_idx,
                    "length": current_streak_wins,
                    "matches_since": current_streak_start_idx,
                }
                break  # most recent streak found, stop
            # Reset
            current_streak_wins = 0
            current_streak_start_idx = i + 1

    # Check if we ended while still in a streak
    if best_streak is None and current_streak_wins >= threshold:
        best_streak = {
            "end_idx": current_streak_start_idx,
            "start_idx": len(results) - 1,
            "length": current_streak_wins,
            "matches_since": current_streak_start_idx,
        }

    if best_streak is None:
        return {
            "found": False,
            "streak_length": 0,
            "streak_end_date": None,
            "streak_start_date": None,
            "matches_since": len(results),
            "days_since": None,
            "competitions_in_streak": [],
            "search_depth": str(results[-1]["date"]),
            "current_form": current_form,
            "streak_start_index": None,
            "streak_end_index": None,
        }

    # Extract streak details
    streak_end_date = results[best_streak["end_idx"]]["date"]
    streak_start_date = results[best_streak["start_idx"]]["date"]

    # Competitions involved in the streak
    streak_competitions = set()
    for idx in range(best_streak["end_idx"], best_streak["start_idx"] + 1):
        streak_competitions.add(results[idx]["competition_name"])

    # Days since streak ended
    today = date.today()
    end_date = date.fromisoformat(str(streak_end_date)) if isinstance(streak_end_date, str) else streak_end_date
    days_since = (today - end_date).days

    # Normalize dates to strings for JSON serialization
    streak_end_date = str(streak_end_date)
    streak_start_date = str(streak_start_date)

    return {
        "found": True,
        "streak_length": best_streak["length"],
        "streak_end_date": streak_end_date,
        "streak_start_date": streak_start_date,
        "matches_since": best_streak["matches_since"],
        "days_since": days_since,
        "competitions_in_streak": sorted(streak_competitions),
        "search_depth": str(results[-1]["date"]),
        "current_form": current_form,
        "streak_start_index": best_streak["end_idx"],    # most recent win (index 0 = newest match)
        "streak_end_index": best_streak["start_idx"],     # oldest win in streak
    }


def _load_team_names(conn) -> dict[int, str]:
    """Load all team names into a cache to avoid N+1 queries."""
    rows = conn.execute("SELECT id, name, short_name FROM teams").fetchall()
    return {r["id"]: (r["short_name"] or r["name"]) for r in rows}


def _build_recent_matches(matches: list, team_id: int, team_names: dict, limit: int = RECENT_MATCHES_LIMIT) -> list[dict]:
    """Build a list of recent match details for JSON export."""
    recent = []
    for m in matches[:limit]:
        is_home = m["home_team_id"] == team_id
        opp_id = m["away_team_id"] if is_home else m["home_team_id"]
        opp_name = team_names.get(opp_id, "?")

        result = _team_result(m, team_id, "result_final")
        if is_home:
            score = f"{m['home_goals_90min']}-{m['away_goals_90min']}"
        else:
            score = f"{m['away_goals_90min']}-{m['home_goals_90min']}"

        entry = {
            "date": str(m["date"]),
            "opponent": opp_name,
            "home_away": "H" if is_home else "A",
            "score": score,
            "result": result,
            "competition": m["competition_name"] or m["competition_id"],
            "decided_in": m["decided_in"],
            "source": m["source"],
        }
        recent.append(entry)
    return recent


def compute_index(league: str = MVP_LEAGUE, threshold: int = STREAK_THRESHOLD) -> list[dict]:
    """Compute the Hair Length Index for all teams in a league."""
    conn = get_connection()
    init_db(conn)

    teams = get_all_teams(conn, league=league)
    if not teams:
        log.warning(f"No teams found for league {league}. Run fetch_matches.py first.")
        return []

    # Guard: detect duplicate team names before computing anything
    seen_names: dict[str, int] = {}
    for team in teams:
        name = team["name"]
        if name in seen_names:
            raise ValueError(
                f"Duplicate team name '{name}' in league {league} "
                f"(ids {seen_names[name]} and {team['id']}). "
                f"Merge duplicates in the teams table before recomputing."
            )
        seen_names[name] = team["id"]

    # Cache all team names to avoid N+1 queries (critical for Postgres performance)
    team_names = _load_team_names(conn)

    index = []
    for team in teams:
        matches = get_team_matches(conn, team["id"], order="DESC")

        # Primary index: based on final results (winning is winning, including AET/pens)
        streak_final = find_last_streak(matches, team["id"], threshold, "result_final")

        # Strict index: based on 90-min results only
        streak_90 = find_last_streak(matches, team["id"], threshold, "result_90min")

        # Hair tier based on primary (final result)
        tier_name, tier_desc = get_hair_tier(streak_final["days_since"])

        # Recent match details for frontend
        recent_matches = _build_recent_matches(matches, team["id"], team_names)

        # Check for data completeness
        match_count = len(matches)
        has_cup_data = any(
            m["competition_type"] not in ("LEAGUE", None)
            or _is_cup_by_name(m["competition_name"])
            for m in matches
        )

        entry = {
            "team": team["name"],
            "team_id": team["id"],
            "football_data_id": team.get("football_data_id"),
            "slug": slugify(team["name"]),
            "short_name": team["short_name"],
            "crest_url": team["crest_url"],
            # Primary index (final results — winning is winning)
            "streak_found": streak_final["found"],
            "streak_length": streak_final["streak_length"],
            "streak_end_date": streak_final["streak_end_date"],
            "streak_start_date": streak_final["streak_start_date"],
            "days_since": streak_final["days_since"],
            "matches_since": streak_final["matches_since"],
            "competitions_in_streak": streak_final["competitions_in_streak"],
            "current_form": streak_final["current_form"],
            "search_depth": streak_final["search_depth"],
            # Hair tier
            "hair_tier": tier_name,
            "hair_description": tier_desc,
            # Strict index (90-min results only)
            "strict_streak_found": streak_90["found"],
            "strict_streak_end_date": streak_90["streak_end_date"],
            "strict_days_since": streak_90["days_since"],
            # Footnote when streak includes AET/pens wins
            "includes_aet_pens": (
                streak_final["found"]
                and (not streak_90["found"] or streak_final["days_since"] < streak_90["days_since"])
            ),
            # Data completeness
            "total_matches": match_count,
            "has_cup_data": has_cup_data,
            "data_complete": has_cup_data and match_count > 0,
        }
        # Store per-team match data separately (not in index)
        entry["_team_detail"] = {
            "team_id": team["id"],
            "team": team["name"],
            "short_name": team["short_name"],
            "matches": _build_recent_matches(matches, team["id"], team_names, limit=len(matches)),
            "streak": {
                "found": streak_final["found"],
                "start_index": streak_final.get("streak_start_index"),
                "end_index": streak_final.get("streak_end_index"),
                "length": streak_90["streak_length"],
            },
        }
        index.append(entry)

    # Sort: longest hair first (highest days_since), "not found" at the very top
    index.sort(key=lambda x: (
        0 if not x["streak_found"] else 1,  # not found = top
        -(x["days_since"] or 0),  # then by days descending
    ))

    conn.close()
    return index


def export_json(index: list[dict], output_path: Path | None = None) -> Path:
    """Export the index and per-team match files as JSON."""
    if output_path is None:
        output_path = DATA_DIR / "hair-index.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Export per-team match files
    teams_dir = output_path.parent / "teams"
    teams_dir.mkdir(parents=True, exist_ok=True)
    for entry in index:
        detail = entry.get("_team_detail")
        if detail:
            team_path = teams_dir / f"{detail['team_id']}.json"
            team_path.write_text(json.dumps(detail, indent=2, ensure_ascii=False))

    # Final safety checks before writing
    names = [e["team"] for e in index]
    dupes = [n for n in set(names) if names.count(n) > 1]
    if dupes:
        raise ValueError(f"Refusing to export: duplicate team names {dupes}")
    null_streaks = [e["team"] for e in index if e["days_since"] is None]
    if null_streaks:
        log.warning(f"Teams with no streak found (will show as 'Lost in time'): {null_streaks}")

    # Strip internal _team_detail from index before writing
    clean_index = []
    for entry in index:
        clean = {k: v for k, v in entry.items() if not k.startswith("_")}
        clean_index.append(clean)

    output = {
        "generated_at": datetime.now().isoformat(),
        "threshold": STREAK_THRESHOLD,
        "teams": clean_index,
    }
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    log.info(f"Exported index to {output_path} + {len(index)} team files to {teams_dir}/")
    return output_path


def print_index(index: list[dict]) -> None:
    """Print the index as a CLI table."""
    print()
    print(f"{'#':>3}  {'Team':<25} {'Days':>6} {'Tier':<16} {'Streak':>6} {'Last Streak':<12} {'Form':<12} {'Note'}")
    print("-" * 105)

    for i, entry in enumerate(index, 1):
        days = entry["days_since"]
        days_str = str(days) if days is not None else "???"
        tier = entry["hair_tier"]
        streak_len = entry["streak_length"] or "-"
        end_date = entry["streak_end_date"] or "not found"
        form = "".join(entry["current_form"][:5])

        notes = []
        if not entry["data_complete"]:
            notes.append("incomplete")
        if entry.get("includes_aet_pens"):
            notes.append("*pens")
        note = ", ".join(notes)

        print(f"{i:>3}  {entry['team']:<25} {days_str:>6} {tier:<16} {streak_len:>6} {end_date:<12} {form:<12} {note}")

    print()
    print(f"  * 'pens' = team has a 5-streak only when counting penalty/AET wins as wins")
    print(f"  * 'incomplete' = missing cup/European data")
    print()


def main():
    parser = argparse.ArgumentParser(description="Compute Hair Length Index")
    parser.add_argument("--league", default=MVP_LEAGUE, help="Competition code")
    parser.add_argument("--threshold", type=int, default=STREAK_THRESHOLD, help="Win streak threshold")
    parser.add_argument("--json", action="store_true", help="Export to JSON file")
    parser.add_argument("--output", type=str, help="Output JSON path")
    args = parser.parse_args()

    index = compute_index(league=args.league, threshold=args.threshold)

    if not index:
        print("No data. Run fetch_matches.py first.")
        return

    print_index(index)

    if args.json:
        output_path = Path(args.output) if args.output else None
        export_json(index, output_path)


if __name__ == "__main__":
    main()
