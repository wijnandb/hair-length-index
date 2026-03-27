"""Fetch upcoming fixtures for teams on winning streaks.

Only fetches for teams that are "bijna bij de kapper" (3-4 consecutive wins)
to minimize scraping. Uses worldfootball.net team pages.

Usage:
    python3.11 -m scripts.fetch_fixtures
    python3.11 -m scripts.fetch_fixtures --team "AS Monaco"
"""

import argparse
import json
import logging
import re
import time
from pathlib import Path

from scripts.config import DATA_DIR
from scripts.team_registry import TEAMS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

FIXTURES_FILE = DATA_DIR / "fixtures.json"


def fetch_next_match(slug: str, wf_id: str) -> dict | None:
    """Fetch the next upcoming match for a team from worldfootball.net."""
    from playwright.sync_api import sync_playwright

    numeric_id = wf_id.replace("te", "")
    url = f"https://www.worldfootball.net/teams/{wf_id}/{slug}/vs2025-2026/all-matches/"
    log.info(f"  Fetching fixtures from {url}...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            )
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(8)
            content = page.content()
            browser.close()
    except Exception as e:
        log.warning(f"  Error fetching: {e}")
        return None

    # Parse HTML to text
    import html as html_mod
    text = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html_mod.unescape(text)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Find first -:- (unplayed match)
    for i, l in enumerate(lines):
        if l == "-:-" and i >= 5:
            # Walk back through the match data structure
            # Pattern: date, round, round, H/A, opponent, -:-
            opponent = lines[i - 1] if i >= 1 else None
            ha = lines[i - 2] if i >= 2 else None

            # Find the date (DD.MM.YYYY pattern) in the preceding lines
            match_date = None
            for j in range(i - 3, max(0, i - 8), -1):
                dm = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", lines[j])
                if dm:
                    match_date = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}"
                    break

            if match_date and opponent and ha in ("H", "A"):
                # Find competition: look for the section header above this match
                competition = None
                for j in range(i, max(0, i - 50), -1):
                    if re.search(r"\d{4}/\d{4}", lines[j]) and j + 1 < len(lines) and lines[j + 1] == "Date":
                        competition = lines[j]
                        break

                return {
                    "date": match_date,
                    "opponent": opponent,
                    "home_away": ha,
                    "competition": competition or "",
                }

    return None


def get_bijna_teams() -> list[dict]:
    """Get teams currently on 3-4 consecutive wins with long drought."""
    global_path = DATA_DIR / "hair-index-global.json"
    if not global_path.exists():
        return []

    with open(global_path) as f:
        data = json.load(f)

    bijna = []
    for t in data.get("teams", []):
        form = t.get("current_form", [])
        wins = 0
        for r in form:
            if r == "W":
                wins += 1
            else:
                break
        if wins >= 3 and t.get("days_since", 0) and t["days_since"] > 60:
            bijna.append(t)
    return bijna


def run(team_name: str | None = None):
    """Fetch fixtures for bijna teams (or a specific team)."""
    fixtures = {}

    if team_name:
        # Single team
        team_info = None
        for name, (wf_id, slug, league) in TEAMS.items():
            if team_name.lower() in name.lower():
                team_info = (name, wf_id, slug)
                break
        if not team_info:
            log.error(f"Team not found: {team_name}")
            return
        name, wf_id, slug = team_info
        log.info(f"Fetching fixture for {name}...")
        fixture = fetch_next_match(slug, wf_id)
        if fixture:
            fixtures[name] = fixture
            log.info(f"  Next: {fixture['date']} {'🏠' if fixture['home_away']=='H' else '✈️'} vs {fixture['opponent']}")
        else:
            log.info(f"  No upcoming match found")
    else:
        # All bijna teams
        bijna = get_bijna_teams()
        if not bijna:
            log.info("No teams currently on 3+ win streak")
            return

        log.info(f"Fetching fixtures for {len(bijna)} bijna teams...")
        for t in bijna:
            name = t["team"]
            team_info = None
            for tname, (wf_id, slug, league) in TEAMS.items():
                if tname == name:
                    team_info = (tname, wf_id, slug)
                    break
            if not team_info:
                log.warning(f"  {name}: not in team registry")
                continue

            _, wf_id, slug = team_info
            fixture = fetch_next_match(slug, wf_id)
            if fixture:
                fixtures[name] = fixture
                log.info(f"  {name}: {fixture['date']} {'🏠' if fixture['home_away']=='H' else '✈️'} vs {fixture['opponent']}")
            else:
                log.info(f"  {name}: no upcoming match found")

            time.sleep(2)  # Rate limiting

    # Save fixtures
    FIXTURES_FILE.write_text(json.dumps(fixtures, indent=2, ensure_ascii=False))
    log.info(f"Saved {len(fixtures)} fixtures to {FIXTURES_FILE}")
    return fixtures


def main():
    parser = argparse.ArgumentParser(description="Fetch upcoming fixtures")
    parser.add_argument("--team", type=str, help="Fetch for a specific team")
    args = parser.parse_args()
    run(team_name=args.team)


if __name__ == "__main__":
    main()
