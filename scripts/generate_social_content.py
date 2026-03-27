"""Generate social media content queue by comparing current vs previous data.

Detects events: streak completions (haircuts), building streaks,
close calls, and significant ranking changes.

Usage:
    python -m scripts.generate_social_content
    python -m scripts.generate_social_content --previous data/hair-index-global.prev.json
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from scripts.config import DATA_DIR
from scripts.fan_data import get_birthday_teams, get_milestone, get_rivalry, CLUB_HASHTAGS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

GLOBAL_INDEX = DATA_DIR / "hair-index-global.json"
QUEUE_FILE = DATA_DIR / "social-queue.json"

# Language per league
LEAGUE_LANG = {
    "DED": "nl", "JE": "nl",
    "PL": "en", "BL": "en", "LL": "en", "SA": "en", "L1": "en",
}


def load_index(path: Path) -> dict:
    if not path.exists():
        return {"teams": []}
    with open(path) as f:
        return json.load(f)


def get_consecutive_wins(form: list[str]) -> int:
    """Count consecutive W's from the start of the form array."""
    count = 0
    for r in form:
        if r == "W":
            count += 1
        else:
            break
    return count


def detect_events(current: dict, previous: dict) -> list[dict]:
    """Compare current vs previous data, detect social-worthy events."""
    events = []

    # Index previous data by team name for quick lookup
    prev_map = {}
    for t in previous.get("teams", []):
        prev_map[t["team"]] = t

    for team in current.get("teams", []):
        name = team["team"]
        prev = prev_map.get(name, {})
        league = team.get("league", "DED")
        lang = LEAGUE_LANG.get(league, "en")

        days = team.get("days_since")
        prev_days = prev.get("days_since")
        form = team.get("current_form", [])
        wins = get_consecutive_wins(form)
        prev_wins = get_consecutive_wins(prev.get("current_form", []))

        # 1. BARBER ALERT: days_since reset (was >0, now 0 or much lower)
        if prev_days and prev_days > 30 and days is not None and days < 14:
            events.append({
                "type": "barber_alert",
                "priority": 1,
                "team": name,
                "league": league,
                "league_name": team.get("league_name", league),
                "language": lang,
                "days_waited": prev_days,
                "streak_length": team.get("streak_length", 5),
                "hair_tier": team.get("hair_tier", "Fresh cut"),
                "days_since": days,
                "platforms": ["bluesky", "instagram", "twitter", "reddit"],
                "render_card": True,
            })

        # 2. BIJNA BIJ DE KAPPER: on 3-4 consecutive wins with long drought
        elif wins >= 3 and days and days > 60:
            # Get streak match details from per-team file
            streak_matches = []
            team_id = team.get("team_id")
            if team_id:
                team_file = DATA_DIR / "teams" / f"{team_id}.json"
                if team_file.exists():
                    with open(team_file) as tf:
                        team_data = json.load(tf)
                    for m in team_data.get("matches", [])[:wins]:
                        if m.get("result") == "W":
                            streak_matches.append({
                                "date": m["date"],
                                "opponent": m["opponent"],
                                "score": m["score"],
                                "competition": m.get("competition", ""),
                                "home_away": m.get("home_away", ""),
                            })

            events.append({
                "type": "bijna_bij_de_kapper",
                "priority": 2,
                "team": name,
                "team_id": team.get("team_id"),
                "league": league,
                "league_name": team.get("league_name", league),
                "language": lang,
                "consecutive_wins": wins,
                "remaining": 5 - wins,
                "days_since": days,
                "hair_tier": team.get("hair_tier", ""),
                "streak_matches": streak_matches,
                "platforms": ["bluesky", "twitter", "reddit"],
                "render_card": False,
            })

        # 3. CLOSE CALL: was on 3-4 wins, now streak broken
        elif prev_wins >= 3 and wins == 0 and days and days > 60:
            events.append({
                "type": "close_call",
                "priority": 3,
                "team": name,
                "league": league,
                "league_name": team.get("league_name", league),
                "language": lang,
                "was_on": prev_wins,
                "days_since": days,
                "last_result": form[0] if form else "?",
                "platforms": ["bluesky", "twitter"],
                "render_card": False,
            })

        # 4. MILESTONE: days_since hits a round number (100, 365, 1000, etc.)
        milestone = get_milestone(days) if days else None
        if milestone:
            events.append({
                "type": "milestone",
                "priority": 4,
                "team": name,
                "league": league,
                "league_name": team.get("league_name", league),
                "language": lang,
                "days_since": days,
                "milestone": milestone,
                "hair_tier": team.get("hair_tier", ""),
                "platforms": ["bluesky", "twitter"],
                "render_card": False,
            })

        # 5. COUNTDOWN: team on 4 wins (1 away from haircut!)
        if wins == 4 and days and days > 60:
            events.append({
                "type": "countdown",
                "priority": 2,
                "team": name,
                "league": league,
                "league_name": team.get("league_name", league),
                "language": lang,
                "days_since": days,
                "hair_tier": team.get("hair_tier", ""),
                "platforms": ["bluesky", "twitter", "instagram", "reddit"],
                "render_card": True,
            })

    # 6. BIRTHDAY: club founding anniversary
    birthday_teams = get_birthday_teams()
    team_map = {t["team"]: t for t in current.get("teams", [])}
    for bteam in birthday_teams:
        if bteam in team_map:
            t = team_map[bteam]
            league = t.get("league", "DED")
            events.append({
                "type": "birthday",
                "priority": 4,
                "team": bteam,
                "league": league,
                "league_name": t.get("league_name", league),
                "language": LEAGUE_LANG.get(league, "en"),
                "days_since": t.get("days_since"),
                "hair_tier": t.get("hair_tier", ""),
                "platforms": ["bluesky", "twitter"],
                "render_card": False,
            })

    # 7. DERBY ALERT: two rivalry teams both with long drought
    fixtures_path = DATA_DIR / "fixtures.json"
    if fixtures_path.exists():
        with open(fixtures_path) as ff:
            fixtures = json.load(ff)
        for fix_team, fix in fixtures.items():
            rivalry = get_rivalry(fix_team, fix.get("opponent", ""))
            if rivalry:
                t = team_map.get(fix_team)
                if t and t.get("days_since", 0) and t["days_since"] > 60:
                    league = t.get("league", "DED")
                    events.append({
                        "type": "derby_alert",
                        "priority": 3,
                        "team": fix_team,
                        "opponent": fix.get("opponent", ""),
                        "rivalry_name": rivalry["name"],
                        "rivalry_hashtags": rivalry.get("hashtags", []),
                        "date": fix.get("date", ""),
                        "home_away": fix.get("home_away", ""),
                        "league": league,
                        "league_name": t.get("league_name", league),
                        "language": LEAGUE_LANG.get(league, "en"),
                        "days_since": t["days_since"],
                        "platforms": ["bluesky", "twitter"],
                        "render_card": False,
                    })

    # Sort by priority
    events.sort(key=lambda e: e["priority"])
    return events


def generate_weekly_summary(current: dict) -> dict | None:
    """Generate a weekly summary item (run on Mondays)."""
    if datetime.now().weekday() != 0:  # Monday = 0
        return None

    teams = current.get("teams", [])
    if not teams:
        return None

    # Find extremes
    with_days = [t for t in teams if t.get("days_since") is not None]
    if not with_days:
        return None

    longest = max(with_days, key=lambda t: t["days_since"])
    freshest = min(with_days, key=lambda t: t["days_since"])

    # Teams close to a haircut
    almost = [t for t in with_days if get_consecutive_wins(t.get("current_form", [])) >= 3]

    return {
        "type": "weekly_summary",
        "priority": 5,
        "language": "en",
        "longest": {"team": longest["team"], "days": longest["days_since"], "league": longest.get("league_name", "")},
        "freshest": {"team": freshest["team"], "days": freshest["days_since"], "league": freshest.get("league_name", "")},
        "almost": [{"team": t["team"], "wins": get_consecutive_wins(t.get("current_form", [])), "league": t.get("league_name", "")} for t in almost[:3]],
        "total_teams": len(teams),
        "platforms": ["bluesky", "instagram", "twitter", "linkedin"],
        "render_card": True,
    }


def run():
    log.info("Generating social content queue...")

    current = load_index(GLOBAL_INDEX)
    # Previous = the same file from before today's computation
    # In practice, use git to get the previous version, or store a copy
    prev_path = DATA_DIR / "hair-index-global.prev.json"
    previous = load_index(prev_path)

    events = detect_events(current, previous)

    # Add weekly summary on Mondays
    weekly = generate_weekly_summary(current)
    if weekly:
        events.append(weekly)

    queue = {
        "generated_at": datetime.now().isoformat(),
        "total_events": len(events),
        "items": events,
    }

    QUEUE_FILE.write_text(json.dumps(queue, indent=2, ensure_ascii=False))
    log.info(f"Generated {len(events)} social content items → {QUEUE_FILE}")

    for e in events:
        log.info(f"  [{e['type']}] {e.get('team', 'summary')} ({e.get('league_name', '')})")

    # Save current as previous for next run
    import shutil
    shutil.copy2(GLOBAL_INDEX, prev_path)

    return queue


def main():
    parser = argparse.ArgumentParser(description="Generate social content queue")
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
