"""Daily update: fetch new matches from football-data.org + API-Football into Neon.

Runs in CI. Two data sources:
- football-data.org (free tier): DED, PL, BL1, SA, PD, FL1, CL
- API-Football (api-sports.io): JE, KNVB Beker, EL, ECL, per-team cups

Usage:
    python -m scripts.daily_update
    python -m scripts.daily_update --dry-run
"""

import argparse
import logging
import time
from datetime import datetime, timezone

import requests

from scripts.config import (
    API_FOOTBALL_API_KEY,
    API_FOOTBALL_BASE_URL,
    API_FOOTBALL_LEAGUES,
    API_FOOTBALL_RATE_LIMIT_SECONDS,
    COMPETITIONS,
    FOOTBALL_DATA_API_KEY,
    FOOTBALL_DATA_BASE_URL,
    FOOTBALL_DATA_RATE_LIMIT_SECONDS,
)
from scripts.db import (
    find_team_by_api_football_id,
    find_team_by_name,
    get_all_teams,
    get_connection,
    init_db,
    set_api_football_id,
    update_data_source,
    upsert_match,
    upsert_team,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Current season
CURRENT_SEASON_YEAR = 2025  # 2025-26 season


# ═══════════════════════════════════════════════════════════════════
# football-data.org client (for DED, PL, BL1, SA, PD, FL1, CL)
# ═══════════════════════════════════════════════════════════════════

class FootballDataClient:
    def __init__(self, api_key: str = FOOTBALL_DATA_API_KEY):
        if not api_key:
            raise ValueError("FOOTBALL_DATA_API_KEY not set")
        self.session = requests.Session()
        self.session.headers["X-Auth-Token"] = api_key
        self.base_url = FOOTBALL_DATA_BASE_URL
        self._last = 0.0

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        elapsed = time.time() - self._last
        if elapsed < FOOTBALL_DATA_RATE_LIMIT_SECONDS:
            time.sleep(FOOTBALL_DATA_RATE_LIMIT_SECONDS - elapsed)
        self._last = time.time()
        url = f"{self.base_url}{endpoint}"
        for attempt in range(3):
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                wait = 6.0 * (2 ** attempt)
                log.warning(f"Rate limited (429). Retrying in {wait:.0f}s...")
                time.sleep(wait)
            else:
                resp.raise_for_status()
        raise RuntimeError(f"Failed after 3 retries: {url}")


def _fd_compute_result(home: int, away: int) -> str:
    if home > away:
        return "H"
    elif away > home:
        return "A"
    return "D"


def _fd_season_label(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _fd_import_match(conn, m: dict) -> int | None:
    """Import a football-data.org match."""
    score = m.get("score", {})
    ht = m["homeTeam"]
    at = m["awayTeam"]
    comp = m.get("competition", {})

    home_id = upsert_team(
        conn,
        football_data_id=ht["id"],
        name=ht.get("name", f"Team {ht['id']}"),
        short_name=ht.get("shortName") or ht.get("tla"),
        crest_url=ht.get("crest"),
    )
    away_id = upsert_team(
        conn,
        football_data_id=at["id"],
        name=at.get("name", f"Team {at['id']}"),
        short_name=at.get("shortName") or at.get("tla"),
        crest_url=at.get("crest"),
    )

    full_time = score.get("fullTime", {})
    regular_time = score.get("regularTime")
    penalties = score.get("penalties")

    duration = score.get("duration", "REGULAR")
    if duration == "PENALTY_SHOOTOUT":
        decided_in = "PENALTIES"
    elif duration == "EXTRA_TIME":
        decided_in = "EXTRA_TIME"
    else:
        decided_in = "REGULAR"

    home_final = full_time.get("home")
    away_final = full_time.get("away")

    if regular_time and regular_time.get("home") is not None:
        home_90 = regular_time["home"]
        away_90 = regular_time["away"]
    else:
        home_90 = home_final
        away_90 = away_final

    home_pens = penalties.get("home") if penalties else None
    away_pens = penalties.get("away") if penalties else None

    result_90min = _fd_compute_result(home_90, away_90) if home_90 is not None else None
    if decided_in == "PENALTIES" and home_pens is not None:
        result_final = _fd_compute_result(home_pens, away_pens)
    elif home_final is not None:
        result_final = _fd_compute_result(home_final, away_final)
    else:
        result_final = None

    comp_type_raw = comp.get("type", "")
    if comp_type_raw == "LEAGUE":
        comp_type = "LEAGUE"
    elif comp_type_raw == "CUP":
        code = comp.get("code", "")
        comp_type = "CONTINENTAL" if code in ("CL", "EL", "CLI", "EC") else "DOMESTIC_CUP"
    else:
        comp_type = "LEAGUE"

    season_data = m.get("season", {})
    start_date = season_data.get("startDate", "")
    season_year = int(start_date[:4]) if start_date else None
    season_label = _fd_season_label(season_year) if season_year else "unknown"

    return upsert_match(
        conn,
        source="football-data.org",
        source_match_id=str(m["id"]),
        date=m["utcDate"][:10],
        home_team_id=home_id,
        away_team_id=away_id,
        home_goals_90min=home_90,
        away_goals_90min=away_90,
        home_goals_final=home_final,
        away_goals_final=away_final,
        home_goals_penalties=home_pens,
        away_goals_penalties=away_pens,
        decided_in=decided_in,
        result_90min=result_90min,
        result_final=result_final,
        competition_id=comp.get("code", "UNK"),
        competition_name=comp.get("name", "Unknown"),
        competition_type=comp_type,
        round=m.get("matchday") and f"Matchday {m['matchday']}",
        season=season_label,
    )


def fetch_fd_league(client: FootballDataClient, conn, league: str, season: int) -> int:
    """Fetch all finished matches for a football-data.org league."""
    log.info(f"[FD] Fetching {league} season={season}...")
    data = client._get(f"/competitions/{league}/matches", {"status": "FINISHED", "season": season})
    matches = data.get("matches", [])
    new = 0
    for m in matches:
        if _fd_import_match(conn, m) is not None:
            new += 1
    log.info(f"  {league}: {len(matches)} matches, {new} new")
    return new


def fetch_fd_team(client: FootballDataClient, conn, fd_id: int, date_from: str, date_to: str) -> tuple[int, set[int]]:
    """Fetch all matches for a team (captures CL/EL).
    Returns (new_match_count, set_of_opponent_football_data_ids)."""
    data = client._get(f"/teams/{fd_id}/matches", {
        "status": "FINISHED",
        "dateFrom": date_from,
        "dateTo": date_to,
    })
    matches = data.get("matches", [])
    new = 0
    opponent_fd_ids: set[int] = set()
    for m in matches:
        # Track opponents
        home_fd = m.get("homeTeam", {}).get("id")
        away_fd = m.get("awayTeam", {}).get("id")
        if home_fd == fd_id:
            opponent_fd_ids.add(away_fd)
        else:
            opponent_fd_ids.add(home_fd)
        if _fd_import_match(conn, m) is not None:
            new += 1
    return new, opponent_fd_ids


# ═══════════════════════════════════════════════════════════════════
# API-Football client (for JE, KNVB, EL, ECL)
# ═══════════════════════════════════════════════════════════════════

class APIFootballClient:
    def __init__(self, api_key: str = API_FOOTBALL_API_KEY):
        if not api_key:
            raise ValueError("API_FOOTBALL_API_KEY not set")
        self.session = requests.Session()
        self.session.headers["x-apisports-key"] = api_key
        self.base_url = API_FOOTBALL_BASE_URL
        self._last = 0.0
        self.requests_used = 0

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        elapsed = time.time() - self._last
        if elapsed < API_FOOTBALL_RATE_LIMIT_SECONDS:
            time.sleep(API_FOOTBALL_RATE_LIMIT_SECONDS - elapsed)
        self._last = time.time()
        self.requests_used += 1
        url = f"{self.base_url}/{endpoint}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        errors = data.get("errors")
        if errors:
            if isinstance(errors, dict) and errors.get("rateLimit"):
                raise RuntimeError("API-Football daily rate limit exceeded")
        remaining = resp.headers.get("x-ratelimit-requests-remaining")
        if remaining:
            log.debug(f"API-Football remaining: {remaining}")
        return data

    def get_fixtures(self, league_id: int, season: int) -> list[dict]:
        data = self._get("fixtures", {"league": league_id, "season": season, "status": "FT-AET-PEN"})
        return data.get("response", [])

    def get_team_fixtures(self, team_id: int, season: int) -> list[dict]:
        data = self._get("fixtures", {"team": team_id, "season": season, "status": "FT-AET-PEN"})
        return data.get("response", [])


def _af_league_id_to_code(league_id: int) -> str:
    mapping = {
        88: "DED", 89: "JE", 90: "KNVB", 91: "SC_NL",
        2: "CL", 3: "EL", 848: "ECL",
        39: "PL", 78: "BL1", 135: "SA", 140: "PD", 61: "FL1",
        45: "FA", 81: "DFB", 143: "CDR", 137: "CI", 66: "CDF",
    }
    return mapping.get(league_id, f"AF_{league_id}")


def _af_import_fixture(conn, fixture: dict) -> int | None:
    """Import a single API-Football fixture."""
    fi = fixture.get("fixture", {})
    league = fixture.get("league", {})
    teams = fixture.get("teams", {})
    goals = fixture.get("goals", {})
    score = fixture.get("score", {})

    status = fi.get("status", {}).get("short", "")
    if status not in ("FT", "AET", "PEN"):
        return None

    # Resolve teams
    home_api_id = teams.get("home", {}).get("id")
    away_api_id = teams.get("away", {}).get("id")
    home_name = teams.get("home", {}).get("name", "Unknown")
    away_name = teams.get("away", {}).get("name", "Unknown")

    home_id = _resolve_af_team(conn, home_api_id, home_name, league.get("country"))
    away_id = _resolve_af_team(conn, away_api_id, away_name, league.get("country"))

    # Scores
    home_goals_final = goals.get("home")
    away_goals_final = goals.get("away")
    fulltime = score.get("fulltime", {})
    home_90 = fulltime.get("home")
    away_90 = fulltime.get("away")
    penalty = score.get("penalty", {})
    home_pens = penalty.get("home") if penalty else None
    away_pens = penalty.get("away") if penalty else None

    if status == "PEN":
        decided_in = "PENALTIES"
    elif status == "AET":
        decided_in = "EXTRA_TIME"
    else:
        decided_in = "REGULAR"

    result_90min = _fd_compute_result(home_90, away_90) if home_90 is not None else None
    if decided_in == "PENALTIES" and home_pens is not None:
        result_final = _fd_compute_result(home_pens, away_pens)
    elif home_goals_final is not None:
        result_final = _fd_compute_result(home_goals_final, away_goals_final)
    else:
        result_final = None

    # Competition type
    league_id = league.get("id")
    if league_id in (2, 3, 848):
        comp_type = "CONTINENTAL"
    elif league.get("type") == "Cup":
        comp_type = "DOMESTIC_CUP"
    else:
        comp_type = "LEAGUE"

    season_year = league.get("season")
    season_label = f"{season_year}-{str(season_year + 1)[-2:]}" if season_year else "unknown"

    return upsert_match(
        conn,
        source="api-football",
        source_match_id=str(fi.get("id", "")),
        date=fi.get("date", "")[:10],
        home_team_id=home_id,
        away_team_id=away_id,
        home_goals_90min=home_90,
        away_goals_90min=away_90,
        home_goals_final=home_goals_final,
        away_goals_final=away_goals_final,
        home_goals_penalties=home_pens,
        away_goals_penalties=away_pens,
        decided_in=decided_in,
        result_90min=result_90min,
        result_final=result_final,
        competition_id=_af_league_id_to_code(league_id),
        competition_name=league.get("name", "Unknown"),
        competition_type=comp_type,
        round=league.get("round"),
        season=season_label,
    )


def _resolve_af_team(conn, api_id: int, name: str, country: str | None) -> int:
    """Resolve an API-Football team to internal ID."""
    team = find_team_by_api_football_id(conn, api_id)
    if team:
        return team["id"]
    # Try name match
    team = find_team_by_name(conn, name)
    if team:
        set_api_football_id(conn, team["id"], api_id)
        return team["id"]
    # Create new team
    return upsert_team(conn, name=name, api_football_id=api_id, country=country)


def fetch_af_league(client: APIFootballClient, conn, league_code: str, season: int) -> int:
    """Fetch all fixtures for an API-Football league."""
    league_info = API_FOOTBALL_LEAGUES.get(league_code)
    if not league_info:
        log.warning(f"Unknown API-Football league: {league_code}")
        return 0
    api_id = league_info["api_id"]
    log.info(f"[AF] Fetching {league_code} (api_id={api_id}) season={season}...")
    fixtures = client.get_fixtures(api_id, season)
    new = 0
    for f in fixtures:
        if _af_import_fixture(conn, f) is not None:
            new += 1
    log.info(f"  {league_code}: {len(fixtures)} fixtures, {new} new")
    return new


def fetch_af_team(client: APIFootballClient, conn, af_id: int, season: int) -> tuple[int, set[int]]:
    """Fetch all fixtures for a team via API-Football (cups, European).
    Returns (new_match_count, set_of_opponent_api_football_ids)."""
    fixtures = client.get_team_fixtures(af_id, season)
    new = 0
    opponent_af_ids: set[int] = set()
    for f in fixtures:
        # Track opponents
        teams = f.get("teams", {})
        home_af = teams.get("home", {}).get("id")
        away_af = teams.get("away", {}).get("id")
        if home_af == af_id:
            opponent_af_ids.add(away_af)
        else:
            opponent_af_ids.add(home_af)
        if _af_import_fixture(conn, f) is not None:
            new += 1
    return new, opponent_af_ids


# ═══════════════════════════════════════════════════════════════════
# Main daily update
# ═══════════════════════════════════════════════════════════════════

def run_daily_update(dry_run: bool = False):
    conn = get_connection()
    init_db(conn)

    total_new = 0
    season = CURRENT_SEASON_YEAR

    # --- Phase 1: football-data.org leagues ---
    fd_leagues = ["DED", "PL", "BL1", "SA", "PD", "FL1", "CL"]
    fd_client = None

    if FOOTBALL_DATA_API_KEY:
        fd_client = FootballDataClient()
        for league in fd_leagues:
            try:
                new = fetch_fd_league(fd_client, conn, league, season)
                total_new += new
                update_data_source(conn, "football-data.org", league, _fd_season_label(season),
                                   last_fetched=datetime.now(timezone.utc).isoformat(),
                                   status="COMPLETE")
            except Exception as e:
                log.error(f"Error fetching {league} from FD: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass

        # Per-team fetch for cup/European matches across all FD leagues.
        # Skip teams already seen as opponents (they share matches).
        seen_fd_ids: set[int] = set()
        fd_skipped = 0
        date_from = f"{season}-07-01"
        date_to = f"{season + 1}-06-30"
        for league in ["DED", "PL", "BL1", "SA", "PD", "FL1"]:
            teams = get_all_teams(conn, league=league)
            for t in teams:
                fd_id = t["football_data_id"]
                if not fd_id:
                    continue
                if fd_id in seen_fd_ids:
                    fd_skipped += 1
                    continue
                try:
                    new, opp_ids = fetch_fd_team(fd_client, conn, fd_id, date_from, date_to)
                    total_new += new
                    seen_fd_ids.update(opp_ids)
                except Exception as e:
                    log.warning(f"Error fetching team {t['name']} (fd={fd_id}): {e}")
                    try:
                        conn.rollback()
                    except Exception:
                        pass
        log.info(f"[FD] Per-team: skipped {fd_skipped} teams (already seen as opponents)")
    else:
        log.warning("FOOTBALL_DATA_API_KEY not set — skipping football-data.org leagues")

    # --- Phase 2: API-Football leagues ---
    af_leagues = ["JE", "KNVB", "EL", "ECL"]
    af_client = None

    if API_FOOTBALL_API_KEY:
        af_client = APIFootballClient()
        for league in af_leagues:
            try:
                new = fetch_af_league(af_client, conn, league, season)
                total_new += new
            except Exception as e:
                log.error(f"Error fetching {league} from AF: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass

        # Per-team fetch for cup matches (JE + DED).
        # Skip teams already seen as opponents.
        seen_af_ids: set[int] = set()
        af_skipped = 0
        for league in ["JE", "DED"]:
            teams = get_all_teams(conn, league=league)
            for t in teams:
                af_id = t["api_football_id"]
                if not af_id:
                    continue
                if af_id in seen_af_ids:
                    af_skipped += 1
                    continue
                try:
                    new, opp_ids = fetch_af_team(af_client, conn, af_id, season)
                    total_new += new
                    seen_af_ids.update(opp_ids)
                except Exception as e:
                    log.warning(f"Error fetching {league} team {t['name']} (af={af_id}): {e}")
                    try:
                        conn.rollback()
                    except Exception:
                        pass
        log.info(f"[AF] Per-team: skipped {af_skipped} teams (already seen as opponents)")

        log.info(f"API-Football requests used: {af_client.requests_used}")
    else:
        log.warning("API_FOOTBALL_API_KEY not set — skipping API-Football leagues")

    log.info(f"Daily update complete. {total_new} new matches inserted.")
    conn.close()
    return total_new


def main():
    parser = argparse.ArgumentParser(description="Daily match data update")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()
    run_daily_update(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
