"""Import KNVB Beker match results from eurojackpotknvbbeker.nl.

Scrapes the official KNVB Beker website for match results and imports them
into the SQLite database. Covers all rounds including qualifying.

This fills the gap for current-season cup data that API-Football's free tier
doesn't provide.
"""

import argparse
import logging
import re
from datetime import datetime

import requests

from scripts.config import MVP_LEAGUE
from scripts.db import (
    find_team_by_name,
    get_connection,
    init_db,
    update_data_source,
    upsert_match,
    upsert_team,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_URL = "https://www.eurojackpotknvbbeker.nl/wedstrijden"

# Map KNVB Beker site team names to football-data.org canonical names.
# Only needed where the names differ between sources.
TEAM_ALIASES = {
    "FC Twente": "FC Twente '65",
    "Excelsior M": "SBV Excelsior",
    "SC Cambuur": "SC Cambuur Leeuwarden",
    "Vitesse": "SBV Vitesse",
    "ADO Den Haag": "ADO Den Haag",
    "FC Volendam": "FC Volendam",
    "Telstar": "Telstar",
    "Roda JC": "Roda JC Kerkrade",
    "VVV-Venlo": "VVV-Venlo",
}

# Map round names from the site to our round labels
ROUND_MAP = {
    "kwalificatieronde 1": "Kwalificatieronde 1",
    "kwalificatieronde 2": "Kwalificatieronde 2",
    "1e ronde": "1e Ronde",
    "2e ronde": "2e Ronde",
    "3e ronde": "3e Ronde",
    "4e ronde": "Kwartfinale",
    "5e ronde": "Halve finale",
    "6e ronde": "Finale",
}

# Dutch month names → month numbers
DUTCH_MONTHS = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "augustus": 8,
    "september": 9, "oktober": 10, "november": 11, "december": 12,
}

# Score pattern: "2-1" or "1-1 (4-3)" for penalties/AET
SCORE_RE = re.compile(r"(\d+)\s*-\s*(\d+)(?:\s*\((\d+)\s*-\s*(\d+)\))?")

# Date pattern: "dinsdag 2 september 2025"
DATE_RE = re.compile(
    r"(?:maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag)\s+"
    r"(\d{1,2})\s+(\w+)\s+(\d{4})"
)


def fetch_page() -> str:
    """Fetch the wedstrijden page."""
    resp = requests.get(BASE_URL, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_dutch_date(text: str) -> str | None:
    """Parse 'dinsdag 2 september 2025' → '2025-09-02'."""
    m = DATE_RE.search(text)
    if not m:
        return None
    day, month_name, year = m.group(1), m.group(2).lower(), m.group(3)
    month = DUTCH_MONTHS.get(month_name)
    if not month:
        return None
    return f"{year}-{month:02d}-{int(day):02d}"


def parse_score(score_text: str) -> dict | None:
    """Parse score text like '2-1', '1-1 (4-3)'.

    Returns dict with home/away goals for 90min and penalties.
    """
    m = SCORE_RE.search(score_text)
    if not m:
        return None
    home_90 = int(m.group(1))
    away_90 = int(m.group(2))
    home_pens = int(m.group(3)) if m.group(3) else None
    away_pens = int(m.group(4)) if m.group(4) else None
    return {
        "home_90": home_90,
        "away_90": away_90,
        "home_pens": home_pens,
        "away_pens": away_pens,
    }


def determine_decided_in(home_name: str, away_name: str) -> str:
    """Determine how match was decided based on asterisks.

    * = verlenging (extra time), ** = strafschoppen (penalties).
    Returns decided_in and cleaned team names.
    """
    decided_in = "REGULAR"
    # Check for ** (penalties) first, then * (AET)
    if home_name.endswith("**") or away_name.endswith("**"):
        decided_in = "PENALTIES"
    elif home_name.endswith("*") or away_name.endswith("*"):
        decided_in = "EXTRA_TIME"
    # Strip asterisks from names
    home_clean = home_name.rstrip("*").strip()
    away_clean = away_name.rstrip("*").strip()
    return decided_in, home_clean, away_clean


def compute_result(home: int, away: int) -> str:
    if home > away:
        return "H"
    elif away > home:
        return "A"
    return "D"


def _strip_html(html: str) -> list[str]:
    """Strip HTML to clean text lines."""
    import html as html_module

    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html_module.unescape(text)
    return [line.strip() for line in text.split("\n") if line.strip()]


def parse_matches(html: str) -> list[dict]:
    """Parse match data from the HTML page.

    The site renders matches as three consecutive lines:
        Home Team
        2-1
        Away Team*

    Asterisks on team names indicate: * = AET, ** = penalties.
    Scores with parentheses like '1-1 (4-3)' show penalty results.
    """
    lines = _strip_html(html)

    matches = []
    current_round = None
    current_date = None

    i = 0
    while i < len(lines):
        line_lower = lines[i].lower()

        # Detect round headers
        for key, label in ROUND_MAP.items():
            if key in line_lower and ("mannen" in line_lower or "beker" in line_lower):
                current_round = label
                break

        # Detect dates
        date_parsed = parse_dutch_date(lines[i])
        if date_parsed:
            current_date = date_parsed
            i += 1
            continue

        # Check if this line is a score (the middle of a triplet)
        score_match = SCORE_RE.fullmatch(lines[i].strip())
        if score_match and current_date and i >= 1 and i + 1 < len(lines):
            home_raw = lines[i - 1].strip()
            score_text = lines[i].strip()
            away_raw = lines[i + 1].strip()

            # Validate: home/away shouldn't look like dates or headers
            if (not DATE_RE.search(home_raw)
                    and not DATE_RE.search(away_raw)
                    and not any(k in home_raw.lower() for k in ROUND_MAP)
                    and home_raw and away_raw):

                score = parse_score(score_text)
                if score:
                    decided_in, home_name, away_name = determine_decided_in(
                        home_raw, away_raw
                    )

                    home_90 = score["home_90"]
                    away_90 = score["away_90"]

                    if decided_in == "PENALTIES":
                        home_final = score["home_90"]
                        away_final = score["away_90"]
                        home_pens = score["home_pens"]
                        away_pens = score["away_pens"]
                        result_90min = "D"
                        result_final = compute_result(home_pens, away_pens)
                    elif decided_in == "EXTRA_TIME":
                        home_final = score["home_90"]
                        away_final = score["away_90"]
                        home_pens = None
                        away_pens = None
                        result_90min = "D"
                        result_final = compute_result(home_final, away_final)
                    else:
                        home_final = home_90
                        away_final = away_90
                        home_pens = None
                        away_pens = None
                        result_90min = compute_result(home_90, away_90)
                        result_final = result_90min

                    match_id = f"{current_date}-{home_name}-{away_name}"

                    matches.append({
                        "source_match_id": match_id,
                        "date": current_date,
                        "home_name": home_name,
                        "away_name": away_name,
                        "home_goals_90min": home_90,
                        "away_goals_90min": away_90,
                        "home_goals_final": home_final,
                        "away_goals_final": away_final,
                        "home_goals_penalties": home_pens,
                        "away_goals_penalties": away_pens,
                        "decided_in": decided_in,
                        "result_90min": result_90min,
                        "result_final": result_final,
                        "round": current_round,
                    })

                    i += 2  # skip away team line
                    continue

        i += 1

    return matches


def resolve_team(conn, name: str) -> int:
    """Find or create a team by name. Returns internal team ID."""
    # Try exact name first
    team = find_team_by_name(conn, name)
    if team:
        return team["id"]

    # Try alias mapping (KNVB Beker name → football-data.org name)
    canonical = TEAM_ALIASES.get(name)
    if canonical and canonical != name:
        team = find_team_by_name(conn, canonical)
        if team:
            return team["id"]

    # Strip trailing " 1" (first team marker on amateur clubs)
    if name.endswith(" 1"):
        team = find_team_by_name(conn, name[:-2])
        if team:
            return team["id"]

    # Create the team (likely a non-Eredivisie club)
    team_id = upsert_team(conn, name=name, country="NL")
    log.debug(f"  Created new team: {name} (id={team_id})")
    return team_id


def import_matches(
    conn, matches: list[dict], season: str = "2025-26", dry_run: bool = False
) -> int:
    """Import parsed matches into the database."""
    new_count = 0
    for m in matches:
        home_id = resolve_team(conn, m["home_name"])
        away_id = resolve_team(conn, m["away_name"])

        if dry_run:
            log.info(
                f"  [DRY RUN] {m['date']} {m['home_name']} {m['home_goals_90min']}-"
                f"{m['away_goals_90min']} {m['away_name']} ({m['decided_in']}) "
                f"round={m['round']}"
            )
            new_count += 1
            continue

        result = upsert_match(
            conn,
            source="knvb-beker-nl",
            source_match_id=m["source_match_id"],
            date=m["date"],
            home_team_id=home_id,
            away_team_id=away_id,
            home_goals_90min=m["home_goals_90min"],
            away_goals_90min=m["away_goals_90min"],
            home_goals_final=m["home_goals_final"],
            away_goals_final=m["away_goals_final"],
            home_goals_penalties=m["home_goals_penalties"],
            away_goals_penalties=m["away_goals_penalties"],
            decided_in=m["decided_in"],
            result_90min=m["result_90min"],
            result_final=m["result_final"],
            competition_id="KNVB",
            competition_name="KNVB Beker",
            competition_type="DOMESTIC_CUP",
            round=m["round"],
            season=season,
        )
        if result is not None:
            new_count += 1

    return new_count


def run_import(season: str = "2025-26", dry_run: bool = False) -> None:
    """Main entry point: fetch, parse, and import KNVB Beker results."""
    log.info(f"Fetching KNVB Beker results from {BASE_URL}...")
    html = fetch_page()

    log.info("Parsing matches...")
    matches = parse_matches(html)
    log.info(f"Found {len(matches)} matches across all rounds")

    if not matches:
        log.warning("No matches found. Page structure may have changed.")
        return

    # Count by round
    rounds = {}
    for m in matches:
        r = m["round"] or "Unknown"
        rounds[r] = rounds.get(r, 0) + 1
    for r, count in sorted(rounds.items()):
        log.info(f"  {r}: {count} matches")

    conn = get_connection()
    init_db(conn)

    new_count = import_matches(conn, matches, season=season, dry_run=dry_run)

    if not dry_run:
        update_data_source(
            conn,
            source="knvb-beker-nl",
            competition_id="KNVB",
            season=season,
            last_fetched=datetime.now().isoformat(),
            match_count=len(matches),
            status="COMPLETE",
        )

    action = "Would import" if dry_run else "Imported"
    log.info(f"{action} {new_count} new matches from KNVB Beker ({season})")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Import KNVB Beker results")
    parser.add_argument("--season", default="2025-26", help="Season label")
    parser.add_argument(
        "--dry-run", action="store_true", help="Parse and display without importing"
    )
    args = parser.parse_args()

    run_import(season=args.season, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
