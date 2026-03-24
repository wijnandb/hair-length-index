"""Data validation for the Hair Length Index.

Runs integrity checks on match data to catch common issues:
- Missing seasons or competitions
- Team name fragmentation
- Cross-source duplicates
- Incorrect match counts
- Cup elimination logic violations
- Chronological gaps

Usage:
    python -m scripts.validate_data --league DED
    python -m scripts.validate_data --league DED --fix  # auto-fix what's possible
"""

import argparse
import logging
from collections import defaultdict
from datetime import date, timedelta

from scripts.config import MVP_LEAGUE
from scripts.db import get_all_teams, get_connection, get_team_matches, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Expected matches per full season per competition type
EXPECTED_MATCHES = {
    "LEAGUE": {
        "DED": 34,   # 18 teams × 2 rounds = 34 matches per team
        "JE": 38,    # 20 teams × 2 rounds = 38 matches per team
    },
}

# Maximum gap between matches during a season (days)
MAX_SEASON_GAP_DAYS = 50  # accounts for winter break

# Known team name variations that should be the same team
KNOWN_ALIASES = [
    {"NEC", "N.E.C.", "NEC Nijmegen", "Nijmegen"},
    {"FC Twente", "FC Twente '65", "Twente"},
    {"FC Groningen", "Groningen"},
    {"sc Heerenveen", "Heerenveen", "SC Heerenveen"},
    {"Feyenoord Rotterdam", "Feyenoord"},
    {"AFC Ajax", "Ajax"},
    {"SBV Excelsior", "Excelsior"},
    {"SBV Vitesse", "Vitesse"},
    {"RKC Waalwijk", "Waalwijk"},
    {"Roda JC Kerkrade", "Roda JC", "Roda"},
    {"SC Cambuur Leeuwarden", "Cambuur", "SC Cambuur"},
    {"ADO Den Haag", "Den Haag"},
    {"Telstar 1963", "Telstar", "SC Telstar"},
    {"Sparta Rotterdam", "Sp. Rotterdam"},
    {"Almere City FC", "Almere City"},
    {"Fortuna Sittard", "For Sittard", "Sittard"},
    {"NAC Breda", "NAC"},
    {"VVV-Venlo", "VVV Venlo", "VVV"},
    {"FC Utrecht", "Utrecht"},
    {"FC Volendam", "Volendam"},
    {"FC Emmen", "Emmen"},
    {"De Graafschap", "De Graafs."},
]


class ValidationResult:
    def __init__(self):
        self.errors = []    # Critical: data is wrong
        self.warnings = []  # Important: data may be incomplete
        self.info = []      # FYI: notable but not problematic

    def error(self, msg):
        self.errors.append(msg)
        log.error(f"ERROR: {msg}")

    def warn(self, msg):
        self.warnings.append(msg)
        log.warning(f"WARN: {msg}")

    def note(self, msg):
        self.info.append(msg)
        log.info(f"INFO: {msg}")

    @property
    def ok(self):
        return len(self.errors) == 0

    def summary(self):
        return (f"{len(self.errors)} errors, {len(self.warnings)} warnings, "
                f"{len(self.info)} notes")


def check_team_fragmentation(conn, result: ValidationResult):
    """Check for duplicate team entries representing the same club."""
    teams = conn.execute("SELECT id, name FROM teams ORDER BY name").fetchall()
    team_names = {t["id"]: t["name"] for t in teams}

    for alias_group in KNOWN_ALIASES:
        found = []
        for team_id, name in team_names.items():
            if name in alias_group:
                cnt = conn.execute(
                    "SELECT COUNT(*) FROM matches WHERE home_team_id=? OR away_team_id=?",
                    (team_id, team_id)
                ).fetchone()[0]
                if cnt > 0:
                    found.append((team_id, name, cnt))
        if len(found) > 1:
            names = ", ".join(f"{name} (id={tid}, {cnt} matches)" for tid, name, cnt in found)
            result.error(f"Team fragmentation: {names} — should be merged")


def check_match_counts(conn, league: str, result: ValidationResult):
    """Check match counts per team per season."""
    teams = get_all_teams(conn, league=league)
    expected = EXPECTED_MATCHES.get("LEAGUE", {}).get(league, 34)
    current_season = "2025-26"

    for team in teams:
        # Get league matches grouped by season
        rows = conn.execute("""
            SELECT season, COUNT(*) as cnt
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
            AND competition_type = 'LEAGUE'
            GROUP BY season
            ORDER BY season
        """, (team["id"], team["id"])).fetchall()

        for row in rows:
            season = row["season"]
            cnt = row["cnt"]

            # Skip current (incomplete) season
            if season == current_season:
                continue

            # COVID-affected seasons: 2019-20 Eredivisie stopped at matchday 26
            # Some competitions had even fewer matches
            if season in ("2019-20", "2019-2020"):
                if cnt < 20:
                    result.warn(f"{team['name']} {season}: only {cnt} league matches "
                                f"(expected 25-26, COVID-shortened season)")
                continue

            if cnt < expected - 2:
                result.warn(f"{team['name']} {season}: only {cnt} league matches "
                            f"(expected {expected})")
            elif cnt > expected + 2:
                result.error(f"{team['name']} {season}: {cnt} league matches "
                             f"(expected {expected}) — possible duplicates")


def check_chronological_gaps(conn, league: str, result: ValidationResult):
    """Check for unexplained gaps in match chronology."""
    teams = get_all_teams(conn, league=league)

    for team in teams:
        matches = get_team_matches(conn, team["id"], order="ASC")
        if len(matches) < 2:
            result.warn(f"{team['name']}: only {len(matches)} matches total")
            continue

        prev_date = None
        for m in matches:
            curr_date = date.fromisoformat(m["date"])
            if prev_date:
                gap = (curr_date - prev_date).days
                # Flag gaps > 50 days that aren't summer breaks (June-August)
                if gap > MAX_SEASON_GAP_DAYS:
                    # Allow summer break (roughly June to August)
                    if not (prev_date.month in (5, 6) and curr_date.month in (7, 8)):
                        result.note(f"{team['name']}: {gap}-day gap between "
                                    f"{prev_date} and {curr_date}")
            prev_date = curr_date


def check_cup_elimination(conn, league: str, result: ValidationResult):
    """Check cup data integrity:
    1. A team can only LOSE once per cup per season (knockout tournament)
    2. Last cup match should be a loss (unless cup winner)
    """
    teams = get_all_teams(conn, league=league)

    for team in teams:
        cup_matches = conn.execute("""
            SELECT date, home_team_id, away_team_id, result_final, season,
                   competition_name, source, id
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
            AND competition_type = 'DOMESTIC_CUP'
            ORDER BY season, date
        """, (team["id"], team["id"])).fetchall()

        # Group by season + competition
        from itertools import groupby
        key_fn = lambda m: (m["season"], m["competition_name"])
        sorted_matches = sorted(cup_matches, key=key_fn)

        for (season, comp), group in groupby(sorted_matches, key=key_fn):
            matches = list(group)
            if not matches:
                continue

            # Rule 1: Count losses — max 1 per cup per season (knockout)
            losses = []
            for m in matches:
                is_home = m["home_team_id"] == team["id"]
                lost = (is_home and m["result_final"] == "A") or (not is_home and m["result_final"] == "H")
                if lost:
                    losses.append(m["date"])

            if len(losses) > 1:
                result.error(f"{team['name']} {season} {comp}: {len(losses)} cup losses "
                             f"({', '.join(losses)}) — knockout tournament allows max 1 loss. "
                             f"Likely misattributed matches from different seasons.")

            # Rule 2: Last match should be a loss (unless cup winner)
            last_match = matches[-1]
            is_home = last_match["home_team_id"] == team["id"]
            team_won_last = (is_home and last_match["result_final"] == "H") or \
                            (not is_home and last_match["result_final"] == "A")

            if team_won_last and len(matches) < 6:
                result.warn(f"{team['name']} {season} {comp}: won last cup match "
                            f"({last_match['date']}) with only {len(matches)} matches "
                            f"— may be missing later rounds")


def check_cross_source_duplicates(conn, result: ValidationResult):
    """Check for duplicate matches from different sources."""
    dupes = conn.execute("""
        SELECT m1.date, m1.source as src1, m2.source as src2,
               t1.name as home, t2.name as away
        FROM matches m1
        JOIN matches m2 ON m1.date = m2.date
            AND m1.home_team_id = m2.home_team_id
            AND m1.away_team_id = m2.away_team_id
            AND m1.id < m2.id
        JOIN teams t1 ON m1.home_team_id = t1.id
        JOIN teams t2 ON m1.away_team_id = t2.id
        WHERE m1.source != m2.source
        LIMIT 20
    """).fetchall()

    if dupes:
        result.error(f"Found {len(dupes)}+ cross-source duplicate matches")
        for d in dupes[:5]:
            result.error(f"  Duplicate: {d['date']} {d['home']} vs {d['away']} "
                         f"({d['src1']} + {d['src2']})")


def check_cross_source_score_consistency(conn, result: ValidationResult):
    """Check that when two sources have the same match, scores agree."""
    # Find matches that exist in multiple sources (using dedup index)
    conflicts = conn.execute("""
        SELECT m1.date, m1.source as src1, m2.source as src2,
               m1.home_goals_90min as h1, m1.away_goals_90min as a1,
               m2.home_goals_90min as h2, m2.away_goals_90min as a2,
               t1.name as home, t2.name as away
        FROM matches m1
        JOIN matches m2 ON m1.date = m2.date
            AND m1.home_team_id = m2.home_team_id
            AND m1.away_team_id = m2.away_team_id
            AND m1.id < m2.id
        JOIN teams t1 ON m1.home_team_id = t1.id
        JOIN teams t2 ON m1.away_team_id = t2.id
        WHERE m1.source != m2.source
        AND (m1.home_goals_90min != m2.home_goals_90min
             OR m1.away_goals_90min != m2.away_goals_90min)
        LIMIT 20
    """).fetchall()

    if conflicts:
        result.error(f"Found {len(conflicts)} score conflicts between sources")
        for c in conflicts[:5]:
            result.error(f"  {c['date']} {c['home']} vs {c['away']}: "
                         f"{c['src1']} says {c['h1']}-{c['a1']}, "
                         f"{c['src2']} says {c['h2']}-{c['a2']}")


def check_partial_seasons(conn, league: str, result: ValidationResult):
    """Detect seasons where we only have a few stray matches (from opponent imports)."""
    teams = get_all_teams(conn, league=league)

    for team in teams:
        rows = conn.execute("""
            SELECT season, source, COUNT(*) as cnt
            FROM matches
            WHERE (home_team_id = ? OR away_team_id = ?)
            GROUP BY season, source
            ORDER BY season
        """, (team["id"], team["id"])).fetchall()

        for row in rows:
            # Flag seasons with very few matches from worldfootball.net
            # (likely stray matches from opponent imports, not full team data)
            if row["source"] == "worldfootball.net" and 1 <= row["cnt"] <= 5:
                result.note(f"{team['name']} {row['season']}: only {row['cnt']} matches "
                            f"from {row['source']} — likely from opponent import, not team data")


def check_season_format_consistency(conn, result: ValidationResult):
    """Check for inconsistent season label formats (e.g. '2021-22' vs '2021-2022')."""
    formats = conn.execute("""
        SELECT DISTINCT season, LENGTH(season) as len
        FROM matches
        ORDER BY season
    """).fetchall()

    short = [f["season"] for f in formats if len(f["season"]) == 7]  # "2021-22"
    long = [f["season"] for f in formats if len(f["season"]) == 9]   # "2021-2022"

    if short and long:
        result.warn(f"Inconsistent season formats: {len(short)} short (e.g. {short[0]}), "
                    f"{len(long)} long (e.g. {long[0]}). Should normalize to one format.")


def run_validation(league: str = MVP_LEAGUE) -> ValidationResult:
    """Run all validation checks."""
    conn = get_connection()
    init_db(conn)

    result = ValidationResult()

    log.info(f"Validating data for {league}...")
    log.info("=" * 60)

    log.info("1. Checking team fragmentation...")
    check_team_fragmentation(conn, result)

    log.info("2. Checking cross-source duplicates...")
    check_cross_source_duplicates(conn, result)

    log.info("3. Checking score consistency between sources...")
    check_cross_source_score_consistency(conn, result)

    log.info("4. Checking match counts per season...")
    check_match_counts(conn, league, result)

    log.info("5. Checking cup elimination logic...")
    check_cup_elimination(conn, league, result)

    log.info("6. Checking for partial/stray seasons...")
    check_partial_seasons(conn, league, result)

    log.info("7. Checking season format consistency...")
    check_season_format_consistency(conn, result)

    log.info("8. Checking chronological gaps...")
    check_chronological_gaps(conn, league, result)

    log.info("=" * 60)
    log.info(f"Validation complete: {result.summary()}")
    if not result.ok:
        log.error("DATA ISSUES DETECTED — fix before trusting streak calculations")

    conn.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="Validate match data integrity")
    parser.add_argument("--league", default=MVP_LEAGUE, help="League to validate")
    args = parser.parse_args()

    result = run_validation(league=args.league)
    exit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
