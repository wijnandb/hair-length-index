"""Compute winning streaks and generate the Hair Length Index."""

import argparse
import json
import logging
from datetime import date, datetime
from pathlib import Path

from scripts.config import DATA_DIR, MVP_LEAGUE, STREAK_THRESHOLD, get_hair_tier
from scripts.db import get_all_teams, get_connection, get_team_matches, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


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
            "search_depth": results[-1]["date"],
            "current_form": current_form,
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
    end_date = date.fromisoformat(streak_end_date)
    days_since = (today - end_date).days

    return {
        "found": True,
        "streak_length": best_streak["length"],
        "streak_end_date": streak_end_date,
        "streak_start_date": streak_start_date,
        "matches_since": best_streak["matches_since"],
        "days_since": days_since,
        "competitions_in_streak": sorted(streak_competitions),
        "search_depth": results[-1]["date"],
        "current_form": current_form,
    }


def compute_index(league: str = MVP_LEAGUE, threshold: int = STREAK_THRESHOLD) -> list[dict]:
    """Compute the Hair Length Index for all teams in a league."""
    conn = get_connection()
    init_db(conn)

    teams = get_all_teams(conn, league=league)
    if not teams:
        log.warning(f"No teams found for league {league}. Run fetch_matches.py first.")
        return []

    index = []
    for team in teams:
        matches = get_team_matches(conn, team["id"], order="DESC")

        # Official index: based on 90-min results
        streak_90 = find_last_streak(matches, team["id"], threshold, "result_90min")

        # Fan index: based on final results (including AET/pens wins)
        streak_final = find_last_streak(matches, team["id"], threshold, "result_final")

        # Hair tier
        tier_name, tier_desc = get_hair_tier(streak_90["days_since"])

        # Check for data completeness
        match_count = len(matches)
        has_cup_data = any(m["competition_type"] != "LEAGUE" for m in matches)

        entry = {
            "team": team["name"],
            "team_id": team["id"],
            "short_name": team["short_name"],
            "crest_url": team["crest_url"],
            # Official index (90-min results)
            "streak_found": streak_90["found"],
            "streak_length": streak_90["streak_length"],
            "streak_end_date": streak_90["streak_end_date"],
            "streak_start_date": streak_90["streak_start_date"],
            "days_since": streak_90["days_since"],
            "matches_since": streak_90["matches_since"],
            "competitions_in_streak": streak_90["competitions_in_streak"],
            "current_form": streak_90["current_form"],
            "search_depth": streak_90["search_depth"],
            # Hair tier
            "hair_tier": tier_name,
            "hair_description": tier_desc,
            # Fan index (final results, including AET/pens)
            "fan_streak_found": streak_final["found"],
            "fan_streak_end_date": streak_final["streak_end_date"],
            "fan_days_since": streak_final["days_since"],
            # Footnote for penalty/AET wins
            "penalty_footnote": (
                streak_final["found"]
                and not streak_90["found"]
            ),
            # Data completeness
            "total_matches": match_count,
            "has_cup_data": has_cup_data,
            "data_complete": has_cup_data and match_count > 0,
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
    """Export the index as JSON."""
    if output_path is None:
        output_path = DATA_DIR / "hair-index.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "generated_at": datetime.now().isoformat(),
        "threshold": STREAK_THRESHOLD,
        "teams": index,
    }
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    log.info(f"Exported index to {output_path}")
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
        if entry["penalty_footnote"]:
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
