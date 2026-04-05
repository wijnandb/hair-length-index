"""Fetch current league standings from football-data.org.

Fetches standings for all supported leagues and saves to data/standings-{code}.json.
Uses the same rate-limiting pattern as daily_update.py.

Usage:
    python -m scripts.fetch_standings
    python -m scripts.fetch_standings --league DED
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# football-data.org codes → our internal codes
# football-data.org uses: DED, PL, BL1, SA, PD, FL1
# Our internal codes:      DED, PL, BL,  SA, LL, L1
FD_TO_INTERNAL = {
    "DED": "DED",
    "PL": "PL",
    "BL1": "BL",
    "SA": "SA",
    "PD": "LL",
    "FL1": "L1",
}

INTERNAL_TO_FD = {v: k for k, v in FD_TO_INTERNAL.items()}

# All leagues to fetch (football-data.org codes)
STANDINGS_LEAGUES = ["DED", "PL", "BL1", "SA", "PD", "FL1"]


class StandingsClient:
    """Minimal client for football-data.org standings endpoint."""

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


def _season_label(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def fetch_standings(client: StandingsClient, fd_league: str) -> dict | None:
    """Fetch standings for a single league from football-data.org.

    Returns our output JSON schema or None on failure.
    """
    internal_code = FD_TO_INTERNAL.get(fd_league, fd_league)
    log.info(f"Fetching standings for {fd_league} (internal: {internal_code})...")

    data = client._get(f"/competitions/{fd_league}/standings")

    standings = data.get("standings", [])
    if not standings:
        log.warning(f"No standings data for {fd_league}")
        return None

    # Use TOTAL standings (not HOME/AWAY)
    total = None
    for s in standings:
        if s.get("type") == "TOTAL":
            total = s
            break
    if not total:
        total = standings[0]

    season_data = data.get("season", {})
    start_year = None
    if season_data.get("startDate"):
        start_year = int(season_data["startDate"][:4])

    table = []
    for row in total.get("table", []):
        team_data = row.get("team", {})
        table.append({
            "position": row.get("position"),
            "team": team_data.get("name", "Unknown"),
            "team_id": team_data.get("id"),  # football_data_id
            "played": row.get("playedGames", 0),
            "won": row.get("won", 0),
            "drawn": row.get("draw", 0),
            "lost": row.get("lost", 0),
            "goals_for": row.get("goalsFor", 0),
            "goals_against": row.get("goalsAgainst", 0),
            "goal_difference": row.get("goalDifference", 0),
            "points": row.get("points", 0),
        })

    return {
        "league": internal_code,
        "season": _season_label(start_year) if start_year else "unknown",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "table": table,
    }


def run(leagues: list[str] | None = None):
    """Fetch and save standings for specified leagues (football-data.org codes)."""
    if not FOOTBALL_DATA_API_KEY:
        log.warning("FOOTBALL_DATA_API_KEY not set — skipping standings fetch")
        return

    if leagues is None:
        leagues = STANDINGS_LEAGUES

    client = StandingsClient()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for fd_league in leagues:
        try:
            result = fetch_standings(client, fd_league)
            if result:
                internal_code = FD_TO_INTERNAL.get(fd_league, fd_league)
                output_path = DATA_DIR / f"standings-{internal_code}.json"
                output_path.write_text(
                    json.dumps(result, indent=2, ensure_ascii=False)
                )
                log.info(f"  Saved {output_path}")
        except Exception as e:
            log.error(f"Error fetching standings for {fd_league}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Fetch league standings")
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
