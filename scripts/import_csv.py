"""Import historical match data from football-data.co.uk CSV files.

football-data.co.uk provides free CSV downloads for major European leagues
going back to the 1990s. This gives us deep historical data to find streaks
for teams that don't have one in recent seasons.

CSV columns we use: Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR
  FTR = Full Time Result (H/A/D)
"""

import argparse
import csv
import io
import logging
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

# football-data.co.uk league codes and URL patterns
# Format: https://www.football-data.co.uk/mmz4281/{season_code}/{league_code}.csv
LEAGUE_CODES = {
    "DED": "N1",   # Eredivisie
    "PL": "E0",    # Premier League
    "BL1": "D1",   # Bundesliga
    "SA": "I1",    # Serie A
    "PD": "SP1",   # La Liga
    "FL1": "F1",   # Ligue 1
}

# Team name aliases: football-data.co.uk name → our canonical name
# These differ between sources and need mapping
CSV_TEAM_ALIASES = {
    # Eredivisie
    "Ajax": "AFC Ajax",
    "PSV Eindhoven": "PSV",
    "PSV": "PSV",
    "Feyenoord": "Feyenoord Rotterdam",
    "AZ Alkmaar": "AZ",
    "AZ": "AZ",
    "FC Twente": "FC Twente '65",
    "Twente": "FC Twente '65",
    "FC Utrecht": "FC Utrecht",
    "Heerenveen": "sc Heerenveen",
    "SC Heerenveen": "sc Heerenveen",
    "Sparta Rotterdam": "Sparta Rotterdam",
    "Heracles": "Heracles Almelo",
    "Go Ahead Eagles": "Go Ahead Eagles",
    "NEC Nijmegen": "NEC",
    "NEC": "NEC",
    "Willem II": "Willem II",
    "PEC Zwolle": "PEC Zwolle",
    "RKC Waalwijk": "RKC Waalwijk",
    "NAC Breda": "NAC Breda",
    "Fortuna Sittard": "Fortuna Sittard",
    "FC Groningen": "FC Groningen",
    "Excelsior": "SBV Excelsior",
    "FC Volendam": "FC Volendam",
    "Almere City": "Almere City FC",
    "Almere City FC": "Almere City FC",
    "Telstar": "Telstar 1963",
    "Cambuur": "SC Cambuur Leeuwarden",
    "SC Cambuur": "SC Cambuur Leeuwarden",
    "Emmen": "FC Emmen",
    "FC Emmen": "FC Emmen",
    "Waalwijk": "RKC Waalwijk",
    "Den Haag": "ADO Den Haag",
    "ADO Den Haag": "ADO Den Haag",
    "Roda": "Roda JC Kerkrade",
    "Roda JC": "Roda JC Kerkrade",
    "Vitesse": "SBV Vitesse",
    "VVV Venlo": "VVV-Venlo",
    "VVV-Venlo": "VVV-Venlo",
    "De Graafschap": "De Graafschap",
    "Zwolle": "PEC Zwolle",
    "Sittard": "Fortuna Sittard",
    "Nijmegen": "NEC",
    "Dordrecht": "FC Dordrecht",
    "FC Dordrecht": "FC Dordrecht",
}


def season_code(year: int) -> str:
    """Convert a start year to football-data.co.uk season code.

    2025 → '2526', 2003 → '0304'
    """
    return f"{year % 100:02d}{(year + 1) % 100:02d}"


def season_label(year: int) -> str:
    """Convert start year to our label: 2025 → '2025-26'."""
    return f"{year}-{str(year + 1)[-2:]}"


def fetch_csv(league: str, year: int) -> str | None:
    """Download a CSV file from football-data.co.uk.

    Returns CSV text or None if not available.
    """
    code = LEAGUE_CODES.get(league)
    if not code:
        log.error(f"Unknown league code: {league}")
        return None

    sc = season_code(year)
    url = f"https://www.football-data.co.uk/mmz4281/{sc}/{code}.csv"
    log.info(f"  Fetching {url}...")

    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 404:
            log.info(f"  Season {season_label(year)} not available (404)")
            return None
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        log.warning(f"  Failed to fetch {url}: {e}")
        return None


def resolve_team(conn, name: str) -> int:
    """Find or create a team by name with alias resolution."""
    canonical = CSV_TEAM_ALIASES.get(name, name)

    team = find_team_by_name(conn, canonical)
    if team:
        return team["id"]

    # Try original name
    if canonical != name:
        team = find_team_by_name(conn, name)
        if team:
            return team["id"]

    # Create new team
    team_id = upsert_team(conn, name=canonical, country="NL")
    return team_id


def parse_date(date_str: str) -> str | None:
    """Parse CSV date formats to YYYY-MM-DD.

    football-data.co.uk uses DD/MM/YYYY or DD/MM/YY.
    """
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def import_csv_data(conn, csv_text: str, league: str, year: int) -> int:
    """Parse and import a single CSV season."""
    sl = season_label(year)
    reader = csv.DictReader(io.StringIO(csv_text))

    new_count = 0
    for row in reader:
        date = parse_date(row.get("Date", ""))
        home_name = row.get("HomeTeam", "").strip()
        away_name = row.get("AwayTeam", "").strip()
        fthg = row.get("FTHG", "")
        ftag = row.get("FTAG", "")
        ftr = row.get("FTR", "")

        if not all([date, home_name, away_name, fthg, ftag, ftr]):
            continue

        try:
            home_goals = int(fthg)
            away_goals = int(ftag)
        except (ValueError, TypeError):
            continue

        home_id = resolve_team(conn, home_name)
        away_id = resolve_team(conn, away_name)

        # Map FTR to our result format
        result_map = {"H": "H", "A": "A", "D": "D"}
        result = result_map.get(ftr)
        if not result:
            continue

        match_id = f"csv-{date}-{home_name}-{away_name}"

        r = upsert_match(
            conn,
            source="football-data-uk",
            source_match_id=match_id,
            date=date,
            home_team_id=home_id,
            away_team_id=away_id,
            home_goals_90min=home_goals,
            away_goals_90min=away_goals,
            home_goals_final=home_goals,
            away_goals_final=away_goals,
            decided_in="REGULAR",
            result_90min=result,
            result_final=result,
            competition_id=league,
            competition_name=LEAGUE_CODES.get(league, league),
            competition_type="LEAGUE",
            season=sl,
        )
        if r is not None:
            new_count += 1

    return new_count


def run_import(league: str = MVP_LEAGUE, start_year: int = 2003, end_year: int = 2024) -> None:
    """Import historical CSV data for a league."""
    conn = get_connection()
    init_db(conn)

    log.info(f"Importing {league} CSV data from {start_year} to {end_year}...")
    total_new = 0

    for year in range(end_year, start_year - 1, -1):
        csv_text = fetch_csv(league, year)
        if csv_text is None:
            continue

        new = import_csv_data(conn, csv_text, league, year)
        total_new += new
        sl = season_label(year)
        log.info(f"  {sl}: {new} new matches imported")

        if new > 0:
            update_data_source(
                conn,
                source="football-data-uk",
                competition_id=league,
                season=sl,
                last_fetched=datetime.now().isoformat(),
                match_count=new,
                status="COMPLETE",
            )

    log.info(f"Done. {total_new} total new matches imported for {league}.")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Import historical CSV data")
    parser.add_argument("--league", default=MVP_LEAGUE, help="League code (default: DED)")
    parser.add_argument("--start", type=int, default=2003, help="Start year (default: 2003)")
    parser.add_argument("--end", type=int, default=2024, help="End year (default: 2024)")
    args = parser.parse_args()

    run_import(league=args.league, start_year=args.start, end_year=args.end)


if __name__ == "__main__":
    main()
