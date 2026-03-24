"""Rebuild the database from scratch using worldfootball.net as single source.

Imports all match data for Eredivisie teams from worldfootball.net,
including league, cup, European, and playoff matches.

Usage:
    python3.11 -m scripts.rebuild_db
    python3.11 -m scripts.rebuild_db --min-seasons 5 --max-seasons 20
"""

import argparse
import logging
import shutil
from datetime import datetime
from pathlib import Path

from scripts.config import DATA_DIR, DB_PATH
from scripts.db import get_connection, init_db
from scripts.import_worldfootball import (
    KNOWN_TEAMS,
    fetch_season,
    import_matches,
    _parse_page,
)
from scripts.compute_streaks import find_last_streak, compute_index, export_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Competitions to EXCLUDE (friendlies, pre-season)
FRIENDLY_KEYWORDS = [
    "friendly", "friendl", "testspiel", "oefenwedstrijd",
    "pre-season", "preseason", "winter cup",
]

# Current Eredivisie 2025-26 teams with verified worldfootball.net IDs
EREDIVISIE_2526 = {
    "Ajax": ("te64", "afc-ajax"),
    "AZ Alkmaar": ("te181", "az-alkmaar"),
    "Excelsior": ("te577", "sbv-excelsior"),
    "Feyenoord": ("te736", "feyenoord"),
    "Fortuna Sittard": ("te828", "fortuna-sittard"),
    "Go Ahead Eagles": ("te899", "go-ahead-eagles"),
    "FC Groningen": ("te631", "fc-groningen"),
    "Heerenveen": ("te1644", "sc-heerenveen"),
    "Heracles Almelo": ("te971", "heracles-almelo"),
    "NAC Breda": ("te1331", "nac-breda"),
    "N.E.C.": ("te1347", "nec"),
    "PSV Eindhoven": ("te1502", "psv-eindhoven"),
    "Sparta Rotterdam": ("te1762", "sparta-rotterdam"),
    "Telstar": ("te1831", "telstar"),
    "FC Twente": ("te1965", "fc-twente"),
    "FC Utrecht": ("te711", "fc-utrecht"),
    "FC Volendam": ("te719", "fc-volendam"),
    "PEC Zwolle": ("te729", "pec-zwolle"),
}

# Eerste Divisie 2025-26 teams (excluding Jong teams)
EERSTE_DIVISIE_2526 = {
    "ADO Den Haag": ("te60", "ado-den-haag"),
    "Almere City FC": ("te681", "almere-city-fc"),
    "De Graafschap": ("te453", "de-graafschap"),
    "FC Den Bosch": ("te615", "fc-den-bosch"),
    "FC Dordrecht": ("te617", "fc-dordrecht"),
    "FC Eindhoven": ("te620", "fc-eindhoven"),
    "FC Emmen": ("te621", "fc-emmen"),
    "Helmond Sport": ("te969", "helmond-sport"),
    "MVV": ("te1327", "mvv"),
    "RKC Waalwijk": ("te1568", "rkc-waalwijk"),
    "Roda JC Kerkrade": ("te1574", "roda-jc-kerkrade"),
    "SC Cambuur": ("te315", "sc-cambuur"),
    "TOP Oss": ("te1914", "top-oss"),
    "VVV-Venlo": ("te2122", "vvv-venlo"),
    "Vitesse": ("te2108", "vitesse"),
    "Willem II": ("te2146", "willem-ii"),
}


def is_friendly(competition_name: str) -> bool:
    """Check if a competition is a friendly/pre-season match."""
    lower = competition_name.lower()
    return any(kw in lower for kw in FRIENDLY_KEYWORDS)


def import_team(
    conn,
    team_name: str,
    wf_id: str,
    slug: str,
    min_seasons: int = 5,
    max_seasons: int = 25,
    streak_threshold: int = 5,
) -> dict:
    """Import a team's match history, going deeper until streak is found.

    Returns summary dict.
    """
    log.info(f"\n{'='*60}")
    log.info(f"Importing {team_name} ({wf_id}/{slug})...")

    current_year = 2025
    total_new = 0
    streak_found = False

    for offset in range(max_seasons):
        year = current_year - offset

        matches = fetch_season(slug, wf_id, year)
        if not matches:
            if offset >= min_seasons:
                log.info(f"  No data for {year}-{year+1}, stopping")
                break
            continue

        # Filter out friendlies
        competitive = [m for m in matches if not is_friendly(m.get("competition_name", ""))]
        friendly_count = len(matches) - len(competitive)
        if friendly_count > 0:
            log.info(f"  Filtered out {friendly_count} friendly matches")

        new = import_matches(conn, competitive, team_name)
        total_new += new
        season_label = f"{year}-{str(year+1)[-2:]}"
        log.info(f"  {season_label}: {len(competitive)} competitive matches, {new} new")

        # Check if we've found a streak yet (after min_seasons)
        if offset >= min_seasons - 1 and not streak_found:
            from scripts.db import get_team_matches
            team_row = conn.execute(
                "SELECT id FROM teams WHERE name = ?", (team_name,)
            ).fetchone()
            if team_row:
                all_matches = get_team_matches(conn, team_row["id"], order="DESC")
                result = find_last_streak(all_matches, team_row["id"], streak_threshold, "result_final")
                if result["found"]:
                    streak_found = True
                    log.info(f"  *** Streak found! {result['streak_length']}x ending {result['streak_end_date']} ***")
                    # Import 2 more seasons for context, then stop
                    if offset + 2 < max_seasons:
                        for extra in range(1, 3):
                            extra_year = year - extra
                            extra_matches = fetch_season(slug, wf_id, extra_year)
                            if extra_matches:
                                extra_comp = [m for m in extra_matches if not is_friendly(m.get("competition_name", ""))]
                                extra_new = import_matches(conn, extra_comp, team_name)
                                total_new += extra_new
                                log.info(f"  {extra_year}-{str(extra_year+1)[-2:]}: {len(extra_comp)} matches (context)")
                    break

    return {
        "team": team_name,
        "matches_imported": total_new,
        "streak_found": streak_found,
        "seasons_searched": offset + 1,
    }


def rebuild(min_seasons: int = 5, max_seasons: int = 25):
    """Rebuild the entire database from worldfootball.net."""

    # Backup existing DB
    if DB_PATH.exists():
        backup = DB_PATH.with_suffix(".db.bak")
        shutil.copy2(DB_PATH, backup)
        log.info(f"Backed up existing DB to {backup}")
        DB_PATH.unlink()
        log.info("Removed old database")

    # Create fresh DB
    conn = get_connection()
    init_db(conn)
    log.info("Created fresh database")

    # Import Eredivisie teams
    results = []
    log.info(f"\n--- EREDIVISIE ({len(EREDIVISIE_2526)} teams) ---")
    for team_name, (wf_id, slug) in EREDIVISIE_2526.items():
        result = import_team(conn, team_name, wf_id, slug,
                            min_seasons=min_seasons, max_seasons=max_seasons)
        results.append(result)
        team_row = conn.execute("SELECT id FROM teams WHERE name = ?", (team_name,)).fetchone()
        if team_row:
            conn.execute("UPDATE teams SET current_league = 'DED' WHERE id = ?", (team_row["id"],))
            conn.commit()

    # Import Eerste Divisie teams
    log.info(f"\n--- EERSTE DIVISIE ({len(EERSTE_DIVISIE_2526)} teams) ---")
    for team_name, (wf_id, slug) in EERSTE_DIVISIE_2526.items():
        result = import_team(conn, team_name, wf_id, slug,
                            min_seasons=min_seasons, max_seasons=max_seasons)
        results.append(result)
        team_row = conn.execute("SELECT id FROM teams WHERE name = ?", (team_name,)).fetchone()
        if team_row:
            conn.execute("UPDATE teams SET current_league = 'JE' WHERE id = ?", (team_row["id"],))
            conn.commit()

    conn.close()

    # Summary
    log.info(f"\n{'='*60}")
    log.info("REBUILD COMPLETE")
    log.info(f"{'='*60}")
    total = sum(r["matches_imported"] for r in results)
    found = sum(1 for r in results if r["streak_found"])
    log.info(f"Total: {total} matches imported for {len(results)} teams")
    log.info(f"Streaks found: {found}/{len(results)}")
    for r in results:
        status = "OK" if r["streak_found"] else "NOT FOUND"
        log.info(f"  {r['team']:<25} {r['matches_imported']:>4} matches, "
                 f"{r['seasons_searched']:>2} seasons — {status}")

    # Compute streaks and export for both leagues
    for league, label in [("DED", "Eredivisie"), ("JE", "Eerste Divisie")]:
        log.info(f"\nComputing {label} streaks...")
        index = compute_index(league=league)
        if index:
            output_path = DATA_DIR / f"hair-index-{league.lower()}.json" if league != "DED" else None
            export_json(index, output_path)
            log.info(f"Exported {label} index + per-team files")

    # Run validation
    log.info("\nRunning validation...")
    from scripts.validate_data import run_validation
    result = run_validation(league="DED")
    log.info(f"Validation: {result.summary()}")


def main():
    parser = argparse.ArgumentParser(description="Rebuild DB from worldfootball.net")
    parser.add_argument("--min-seasons", type=int, default=5,
                        help="Minimum seasons to import per team (default: 5)")
    parser.add_argument("--max-seasons", type=int, default=25,
                        help="Maximum seasons to search for streak (default: 25)")
    args = parser.parse_args()

    rebuild(min_seasons=args.min_seasons, max_seasons=args.max_seasons)


if __name__ == "__main__":
    main()
