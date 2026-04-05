"""Daily update: fetch new matches from football-data.org into Neon.

Runs in CI. Per-league: each league has its own workflow.
Source: football-data.org (free tier) for DED, PL, BL1, SA, PD, FL1, CL.
Historical data from worldfootball.net (local Playwright scraper only).

Usage:
    python -m scripts.daily_update --league DED
    python -m scripts.daily_update                # all leagues
"""

import argparse
import logging
import time
from datetime import datetime, timezone

import requests

from scripts.config import (
    FOOTBALL_DATA_API_KEY,
    FOOTBALL_DATA_BASE_URL,
    FOOTBALL_DATA_RATE_LIMIT_SECONDS,
)
from scripts.db import (
    auto_discover_mapping,
    get_all_teams,
    get_connection,
    init_db,
    resolve_team_from_source,
    update_data_source,
    upsert_match,
    upsert_team,
)
from scripts.team_registry import resolve_team_name

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

    home_name = ht.get("name", f"Team {ht['id']}")
    away_name = at.get("name", f"Team {at['id']}")

    # Resolve teams via mapping table (source='fd', source_id=FD team ID)
    home_id = resolve_team_from_source(conn, 'fd', ht["id"], home_name, resolve_team_name)
    away_id = resolve_team_from_source(conn, 'fd', at["id"], away_name, resolve_team_name)

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
    conn.commit()
    log.info(f"  {league}: {len(matches)} matches, {new} new")
    return new


def fetch_fd_team(client: FootballDataClient, conn, fd_id: int, date_from: str, date_to: str) -> int:
    """Fetch all matches for a team (captures CL/EL cup matches)."""
    data = client._get(f"/teams/{fd_id}/matches", {
        "status": "FINISHED",
        "dateFrom": date_from,
        "dateTo": date_to,
    })
    matches = data.get("matches", [])
    new = 0
    for m in matches:
        if _fd_import_match(conn, m) is not None:
            new += 1
    return new


# ═══════════════════════════════════════════════════════════════════
# Main daily update — per-league (football-data.org only)
# ═══════════════════════════════════════════════════════════════════

# Map our internal league codes to football-data.org codes
INTERNAL_TO_FD = {
    "DED": "DED", "PL": "PL", "BL": "BL1", "SA": "SA",
    "LL": "PD", "L1": "FL1",
}


def run_league_update(league: str):
    """Fetch new matches for a single league from football-data.org."""
    fd_code = INTERNAL_TO_FD.get(league)
    if not fd_code:
        log.warning(f"League {league} not supported by football-data.org — skipping")
        return 0

    if not FOOTBALL_DATA_API_KEY:
        log.warning("FOOTBALL_DATA_API_KEY not set — skipping")
        return 0

    conn = get_connection()
    init_db(conn)

    total_new = 0
    season = CURRENT_SEASON_YEAR
    fd_client = FootballDataClient()

    # League matches
    try:
        new = fetch_fd_league(fd_client, conn, fd_code, season)
        total_new += new
        update_data_source(conn, "football-data.org", fd_code, _fd_season_label(season),
                           last_fetched=datetime.now(timezone.utc).isoformat(),
                           status="COMPLETE")
    except Exception as e:
        log.error(f"Error fetching {fd_code}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass

    # Per-team (cup/European matches)
    date_from = f"{season}-07-01"
    date_to = f"{season + 1}-06-30"
    teams = get_all_teams(conn, league=league)
    for t in teams:
        fd_id = t["football_data_id"]
        if not fd_id:
            continue
        try:
            new = fetch_fd_team(fd_client, conn, fd_id, date_from, date_to)
            total_new += new
        except Exception as e:
            log.warning(f"Error fetching {t['name']} (fd={fd_id}): {e}")
            try:
                conn.rollback()
            except Exception:
                pass

    # Also fetch CL matches (covers European matches for this league's teams)
    try:
        cl_new = fetch_fd_league(fd_client, conn, "CL", season)
        total_new += cl_new
    except Exception as e:
        log.warning(f"Error fetching CL: {e}")
        try:
            conn.rollback()
        except Exception:
            pass

    conn.commit()
    log.info(f"[{league}] Update complete. {total_new} new matches.")
    conn.close()
    return total_new


def run_all_leagues():
    """Fetch all leagues sequentially."""
    total = 0
    for league in ["DED", "PL", "BL", "SA", "LL", "L1"]:
        total += run_league_update(league)
    log.info(f"All leagues done. {total} total new matches.")
    return total


def main():
    parser = argparse.ArgumentParser(description="Daily match data update")
    parser.add_argument("--league", type=str, help="Single league code (DED, PL, BL, SA, LL, L1)")
    args = parser.parse_args()

    if args.league:
        run_league_update(args.league)
    else:
        run_all_leagues()


if __name__ == "__main__":
    main()
