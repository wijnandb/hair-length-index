"""Definitive clean rebuild from worldfootball.net.

Creates a fresh database with UNIQUE(date, home_team_id, away_team_id),
imports all teams using central team registry, validates strictly.

Usage:
    python3.11 -m scripts.rebuild_clean
    python3.11 -m scripts.rebuild_clean --max-seasons 15
"""

import argparse
import logging
import shutil
from pathlib import Path

from scripts.config import DATA_DIR, DB_PATH
from scripts.db import get_connection, init_db, upsert_match
from scripts.team_registry import TEAMS, init_teams, resolve_team_id, resolve_team_name
from scripts.import_worldfootball import fetch_season, _map_competition
from scripts.compute_streaks import find_last_streak, compute_index, export_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

FRIENDLY_KEYWORDS = [
    "friendly", "friendl", "testspiel", "oefenwedstrijd",
    "pre-season", "preseason",
]


def is_friendly(comp_name: str) -> bool:
    return any(kw in comp_name.lower() for kw in FRIENDLY_KEYWORDS)


def season_label_short(year: int) -> str:
    """2025 → '2025-26'"""
    return f"{year}-{str(year + 1)[-2:]}"


def import_team_clean(conn, name: str, wf_id: str, slug: str,
                      min_seasons: int = 5, max_seasons: int = 20) -> dict:
    """Import one team cleanly from worldfootball.net."""
    log.info(f"\n{'='*50}")
    log.info(f"Importing {name}...")

    current_year = 2025
    total_new = 0
    streak_found = False
    seasons_done = 0

    for offset in range(max_seasons):
        year = current_year - offset
        try:
            matches = fetch_season(slug, wf_id, year)
        except Exception as e:
            log.warning(f"  Error fetching {year}: {e}")
            continue

        if not matches:
            if offset >= min_seasons:
                break
            continue

        # Filter friendlies
        competitive = [m for m in matches if not is_friendly(m.get("competition_name", ""))]
        friendly_cnt = len(matches) - len(competitive)

        new = 0
        for m in competitive:
            # Resolve opponent name via central registry
            opp_canonical = resolve_team_name(m["opponent"])
            opp_id = resolve_team_id(conn, opp_canonical)
            team_id = resolve_team_id(conn, name)

            is_home = m["home_away"] == "H"
            if is_home:
                home_id, away_id = team_id, opp_id
            else:
                home_id, away_id = opp_id, team_id

            result = upsert_match(
                conn,
                source="worldfootball.net",
                source_match_id=f"wf-{m['date']}-{home_id}-{away_id}",
                date=m["date"],
                home_team_id=home_id,
                away_team_id=away_id,
                home_goals_90min=m["home_goals"],
                away_goals_90min=m["away_goals"],
                home_goals_final=m["home_goals"],
                away_goals_final=m["away_goals"],
                decided_in=m["decided_in"],
                result_90min=m["result_90min"],
                result_final=m["result_final"],
                competition_id=m["competition_id"],
                competition_name=m["competition_name"],
                competition_type=m["competition_type"],
                round=m.get("round", ""),
                season=season_label_short(year),
            )
            if result is not None:
                new += 1

        total_new += new
        seasons_done += 1
        sl = season_label_short(year)
        extra = f" (filtered {friendly_cnt} friendlies)" if friendly_cnt else ""
        log.info(f"  {sl}: {len(competitive)} competitive, {new} new{extra}")

        # Check for streak after min_seasons
        if offset >= min_seasons - 1 and not streak_found:
            from scripts.db import get_team_matches
            team_row = conn.execute("SELECT id FROM teams WHERE name = ?", (name,)).fetchone()
            if team_row:
                all_m = get_team_matches(conn, team_row["id"], order="DESC")
                result = find_last_streak(all_m, team_row["id"], 5, "result_final")
                if result["found"]:
                    streak_found = True
                    log.info(f"  *** Streak: {result['streak_length']}x ending {result['streak_end_date']} ***")
                    # 2 more seasons for context
                    for extra_offset in range(1, 3):
                        ey = year - extra_offset
                        try:
                            em = fetch_season(slug, wf_id, ey)
                        except Exception:
                            continue
                        if em:
                            ec = [x for x in em if not is_friendly(x.get("competition_name", ""))]
                            for m in ec:
                                opp_id = resolve_team_id(conn, resolve_team_name(m["opponent"]))
                                tid = resolve_team_id(conn, name)
                                h, a = (tid, opp_id) if m["home_away"] == "H" else (opp_id, tid)
                                upsert_match(conn, source="worldfootball.net",
                                    source_match_id=f"wf-{m['date']}-{h}-{a}",
                                    date=m["date"], home_team_id=h, away_team_id=a,
                                    home_goals_90min=m["home_goals"], away_goals_90min=m["away_goals"],
                                    home_goals_final=m["home_goals"], away_goals_final=m["away_goals"],
                                    decided_in=m["decided_in"], result_90min=m["result_90min"],
                                    result_final=m["result_final"], competition_id=m["competition_id"],
                                    competition_name=m["competition_name"], competition_type=m["competition_type"],
                                    round=m.get("round", ""), season=season_label_short(ey))
                            log.info(f"  {season_label_short(ey)}: {len(ec)} matches (context)")
                    break

    return {"team": name, "new": total_new, "streak_found": streak_found, "seasons": seasons_done}


def rebuild(max_seasons: int = 20, min_seasons: int = 5):
    """Full clean rebuild."""
    # Backup and delete
    if DB_PATH.exists():
        backup = DB_PATH.with_suffix(".db.bak")
        shutil.copy2(DB_PATH, backup)
        log.info(f"Backed up to {backup}")
        DB_PATH.unlink()

    conn = get_connection()
    init_db(conn)
    log.info("Fresh database created")

    # Register all teams first
    init_teams(conn)
    team_count = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    log.info(f"Registered {team_count} teams")

    # Import all teams
    results = []
    for name, (wf_id, slug, league) in TEAMS.items():
        r = import_team_clean(conn, name, wf_id, slug,
                              min_seasons=min_seasons, max_seasons=max_seasons)
        results.append(r)
        conn.commit()

    conn.close()

    # Summary
    log.info(f"\n{'='*50}")
    log.info("REBUILD COMPLETE")
    total = sum(r["new"] for r in results)
    found = sum(1 for r in results if r["streak_found"])
    log.info(f"Matches: {total}, Streaks: {found}/{len(results)}")
    for r in results:
        s = "OK" if r["streak_found"] else "NOT FOUND"
        log.info(f"  {r['team']:<25} {r['new']:>4} matches — {s}")

    # Compute + export
    log.info("\nComputing streaks...")
    for league in ("DED", "JE"):
        idx = compute_index(league=league)
        if idx:
            out = None if league == "DED" else DATA_DIR / f"hair-index-{league.lower()}.json"
            export_json(idx, out)

    # Validate
    log.info("\nValidating...")
    from scripts.validate_data import run_validation
    result = run_validation(league="DED")
    log.info(f"Validation: {result.summary()}")
    if not result.ok:
        log.error("VALIDATION FAILED — check errors above")


def main():
    parser = argparse.ArgumentParser(description="Clean rebuild from worldfootball.net")
    parser.add_argument("--max-seasons", type=int, default=20)
    parser.add_argument("--min-seasons", type=int, default=5)
    args = parser.parse_args()
    rebuild(max_seasons=args.max_seasons, min_seasons=args.min_seasons)


if __name__ == "__main__":
    main()
