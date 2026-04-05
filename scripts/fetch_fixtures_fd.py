"""Fetch upcoming fixtures from football-data.org.

Fetches scheduled and timed (confirmed time) matches for supported leagues
and saves to data/fixtures-{code}.json.

Uses the same rate-limiting and client pattern as fetch_standings.py.

Usage:
    python -m scripts.fetch_fixtures_fd
    python -m scripts.fetch_fixtures_fd --league DED
"""

import argparse
import json
import logging
import time
from datetime import datetime, timezone

import requests

from scripts.config import (
    DATA_DIR,
    FOOTBALL_DATA_API_KEY,
    FOOTBALL_DATA_BASE_URL,
    FOOTBALL_DATA_RATE_LIMIT_SECONDS,
)
from scripts.team_registry import resolve_team_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# football-data.org codes → our internal codes
FD_TO_INTERNAL = {
    "DED": "DED",
    "PL": "PL",
    "BL1": "BL",
    "SA": "SA",
    "PD": "LL",
    "FL1": "L1",
}

INTERNAL_TO_FD = {v: k for k, v in FD_TO_INTERNAL.items()}

# All leagues to fetch
FIXTURE_LEAGUES = ["DED", "PL", "BL1", "SA", "PD", "FL1"]


class FixturesClient:
    """Minimal client for football-data.org matches endpoint."""

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


def _resolve_team(fd_id: int, fd_name: str, conn=None) -> tuple[str, int | None]:
    """Resolve team name and internal ID.

    If a DB connection is available, uses resolve_team_from_source for full
    resolution (mapping table + alias lookup). Otherwise falls back to the
    team registry's name resolution (no internal ID).

    Returns (canonical_name, internal_id_or_None).
    """
    if conn is not None:
        try:
            from scripts.db import resolve_team_from_source
            team_id = resolve_team_from_source(conn, 'fd', fd_id, fd_name, resolve_team_name)
            # Get the canonical name from the DB
            row = conn.execute("SELECT name FROM teams WHERE id = ?", (team_id,)).fetchone()
            name = row["name"] if row else resolve_team_name(fd_name)
            return name, team_id
        except Exception:
            pass

    # Fallback: name resolution only, no internal ID
    return resolve_team_name(fd_name), None


def _parse_match_time(utc_date: str) -> str:
    """Extract HH:MM from an ISO datetime string."""
    try:
        dt = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except (ValueError, AttributeError):
        return ""


def fetch_fixtures(client: FixturesClient, fd_league: str, conn=None) -> dict | None:
    """Fetch upcoming fixtures for a single league.

    Fetches both SCHEDULED (date known, time TBD) and TIMED (confirmed time)
    matches from football-data.org.

    Returns our output JSON schema or None on failure.
    """
    internal_code = FD_TO_INTERNAL.get(fd_league, fd_league)
    log.info(f"Fetching fixtures for {fd_league} (internal: {internal_code})...")

    matches = []

    for status in ("SCHEDULED", "TIMED"):
        data = client._get(f"/competitions/{fd_league}/matches", {"status": status})
        api_matches = data.get("matches", [])
        log.info(f"  {status}: {len(api_matches)} matches")
        matches.extend(api_matches)

    if not matches:
        log.info(f"No upcoming fixtures for {fd_league}")
        return {
            "league": internal_code,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "matches": [],
        }

    # Deduplicate by match ID (a match might appear in both SCHEDULED and TIMED
    # if its status changed between calls — unlikely but defensive)
    seen_ids = set()
    unique_matches = []
    for m in matches:
        mid = m.get("id")
        if mid not in seen_ids:
            seen_ids.add(mid)
            unique_matches.append(m)

    # Sort by date, then matchday
    unique_matches.sort(key=lambda m: (m.get("utcDate", ""), m.get("matchday", 0)))

    output_matches = []
    for m in unique_matches:
        ht = m.get("homeTeam", {})
        at = m.get("awayTeam", {})
        comp = m.get("competition", {})

        home_fd_name = ht.get("name", f"Team {ht.get('id', '?')}")
        away_fd_name = at.get("name", f"Team {at.get('id', '?')}")

        home_name, home_id = _resolve_team(ht.get("id"), home_fd_name, conn)
        away_name, away_id = _resolve_team(at.get("id"), away_fd_name, conn)

        output_matches.append({
            "date": m.get("utcDate", "")[:10],
            "time": _parse_match_time(m.get("utcDate", "")),
            "home_team": home_name,
            "home_team_id": home_id,
            "away_team": away_name,
            "away_team_id": away_id,
            "competition": comp.get("name", "Unknown"),
            "matchday": m.get("matchday"),
        })

    return {
        "league": internal_code,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matches": output_matches,
    }


def run(leagues: list[str] | None = None):
    """Fetch and save fixtures for specified leagues (football-data.org codes)."""
    if not FOOTBALL_DATA_API_KEY:
        log.warning("FOOTBALL_DATA_API_KEY not set — skipping fixtures fetch")
        return

    if leagues is None:
        leagues = FIXTURE_LEAGUES

    # Try to get a DB connection for team resolution, but proceed without it
    conn = None
    try:
        from scripts.db import get_connection, init_db
        conn = get_connection()
        init_db(conn)
        log.info("DB connection available — using full team resolution")
    except Exception as e:
        log.info(f"No DB connection ({e}) — using name-only resolution")

    client = FixturesClient()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for fd_league in leagues:
        try:
            result = fetch_fixtures(client, fd_league, conn)
            if result:
                internal_code = FD_TO_INTERNAL.get(fd_league, fd_league)
                output_path = DATA_DIR / f"fixtures-{internal_code}.json"
                output_path.write_text(
                    json.dumps(result, indent=2, ensure_ascii=False)
                )
                log.info(f"  Saved {output_path} ({len(result['matches'])} matches)")
        except Exception as e:
            log.error(f"Error fetching fixtures for {fd_league}: {e}")

    if conn:
        try:
            conn.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Fetch upcoming fixtures")
    parser.add_argument(
        "--league",
        help="Single league to fetch (internal code: DED, PL, BL, SA, LL, L1)",
    )
    args = parser.parse_args()

    if args.league:
        fd_code = INTERNAL_TO_FD.get(args.league, args.league)
        run([fd_code])
    else:
        run()


if __name__ == "__main__":
    main()
