"""Generate match sequence data for Hair Growth Reel video.

Reads a team's match history and produces a JSON sequence optimized
for the Remotion HairGrowthReel composition.

Usage:
    python -m scripts.generate_reel_data --team "Sparta Rotterdam"
    python -m scripts.generate_reel_data --team-id 4
"""

import argparse
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from scripts.config import DATA_DIR
from scripts.team_registry import TEAMS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TIER_THRESHOLDS = [
    (45, 1, "Vers geknipt"),       # ~6 weeks, realistic post-streak glow
    (120, 2, "Groeit terug"),      # ~4 months
    (270, 3, "Wordt slordig"),     # ~9 months
    (500, 4, "Lang & wild"),       # ~1.5 years
    (1000, 5, "Holbewoner"),       # ~2.7 years
    (99999, 6, "Sasquatch"),       # 2.7+ years
]


def get_tier(days: int) -> tuple[int, str]:
    for threshold, tier, label in TIER_THRESHOLDS:
        if days <= threshold:
            return tier, label
    return 6, "Sasquatch"


def generate_reel_data(team_id: int, max_matches: int = 40) -> dict:
    """Generate reel data from a team's match history."""
    team_file = DATA_DIR / "teams" / f"{team_id}.json"
    if not team_file.exists():
        raise FileNotFoundError(f"Team file not found: {team_file}")

    with open(team_file) as f:
        team_data = json.load(f)

    team_name = team_data["team"]
    matches = team_data["matches"]  # newest first
    streak = team_data.get("streak", {})

    # We want to show the journey from the last haircut (or as far back as we go)
    # to the current state. Reverse to chronological order.
    all_matches = list(reversed(matches))

    # Find the last haircut (5 consecutive wins ending point)
    # The streak data tells us where the last 5-in-a-row was
    last_haircut_idx = None
    if streak.get("found"):
        # streak indices are in the original (newest-first) array
        # In our chronological array, the end of streak = len - 1 - start_index
        start_in_chrono = len(matches) - 1 - streak["start_index"]
        last_haircut_idx = start_in_chrono

    # Build the sequence: start from some point before the haircut
    # or from the end if we want to show the current drought
    # Strategy: show the last `max_matches` matches for the reel
    if len(all_matches) > max_matches:
        all_matches = all_matches[-max_matches:]

    # Calculate running days_since for each match
    # We need to track consecutive wins and days between matches
    sequence = []
    consecutive_wins = 0
    days_since_streak = 0  # days since last 5-in-a-row completion

    for i, m in enumerate(all_matches):
        # Calculate days between this and previous match
        if i > 0:
            prev_date = datetime.strptime(all_matches[i - 1]["date"], "%Y-%m-%d")
            curr_date = datetime.strptime(m["date"], "%Y-%m-%d")
            days_between = (curr_date - prev_date).days
            days_since_streak += days_between
        elif i == 0 and len(all_matches) < len(matches):
            # First match in our window — estimate days_since from full data
            # Use the global data for the starting point
            pass

        # Track consecutive wins
        if m["result"] == "W":
            consecutive_wins += 1
        else:
            consecutive_wins = 0

        # Haircut! Reset when 5 wins reached
        haircut = consecutive_wins >= 5
        if haircut:
            consecutive_wins = 0
            days_since_streak = 0

        tier_num, tier_label = get_tier(days_since_streak)

        sequence.append({
            "date": m["date"],
            "opponent": m["opponent"],
            "score": m["score"],
            "result": m["result"],
            "homeAway": m.get("home_away", "H"),
            "competition": m.get("competition", ""),
            "decidedIn": m.get("decided_in", "REGULAR"),
            "daysSince": days_since_streak,
            "consecutiveWins": min(consecutive_wins, 5),
            "tier": tier_num,
            "tierLabel": tier_label,
            "haircut": haircut,
        })

    # Get the current days_since from the global index
    global_file = DATA_DIR / "hair-index-global.json"
    current_days = days_since_streak
    league_name = ""
    if global_file.exists():
        with open(global_file) as f:
            global_data = json.load(f)
        for t in global_data.get("teams", []):
            if t["team"] == team_name:
                current_days = t.get("days_since", days_since_streak)
                league_name = t.get("league_name", "")
                break

    # Find team's league for hashtags
    league_code = ""
    for name, (wf_id, slug, lc) in TEAMS.items():
        if name == team_name:
            league_code = lc
            break

    return {
        "team": team_name,
        "teamId": team_id,
        "league": league_code,
        "leagueName": league_name,
        "currentDays": current_days,
        "currentTier": get_tier(current_days)[0],
        "currentTierLabel": get_tier(current_days)[1],
        "totalMatches": len(sequence),
        "sequence": sequence,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate reel data")
    parser.add_argument("--team", type=str, help="Team name")
    parser.add_argument("--team-id", type=int, help="Team ID")
    parser.add_argument("--matches", type=int, default=30, help="Max matches to show")
    parser.add_argument("--output", type=str, help="Output file path")
    args = parser.parse_args()

    if args.team_id:
        team_id = args.team_id
    elif args.team:
        # Find team ID from the actual data files
        import glob
        team_id = None
        for f in glob.glob(str(DATA_DIR / "teams" / "*.json")):
            with open(f) as fh:
                d = json.load(fh)
            if args.team.lower() in d["team"].lower():
                team_id = d["team_id"]
                log.info(f"Found team: {d['team']} (ID: {team_id})")
                break
        if team_id is None:
            log.error(f"Team not found: {args.team}")
            return
    else:
        log.error("Specify --team or --team-id")
        return

    data = generate_reel_data(team_id, max_matches=args.matches)

    output = args.output or f"video/src/reel-{data['team'].lower().replace(' ', '-')}.json"
    Path(output).write_text(json.dumps(data, indent=2, ensure_ascii=False))
    log.info(f"Generated reel data: {output}")
    log.info(f"  Team: {data['team']} ({data['leagueName']})")
    log.info(f"  Current: {data['currentDays']} days, tier {data['currentTier']} ({data['currentTierLabel']})")
    log.info(f"  Matches: {data['totalMatches']}")

    # Show tier transitions
    prev_tier = 0
    for m in data["sequence"]:
        if m["tier"] != prev_tier:
            log.info(f"  Tier {prev_tier}→{m['tier']} at day {m['daysSince']} ({m['date']})")
            prev_tier = m["tier"]
        if m["haircut"]:
            log.info(f"  ✂️ HAIRCUT at {m['date']}!")


if __name__ == "__main__":
    main()
