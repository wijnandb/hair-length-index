"""Fetch match data from football-data.org API v4 into SQLite."""

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

import requests

from scripts.config import (
    COMPETITIONS,
    FOOTBALL_DATA_API_KEY,
    FOOTBALL_DATA_BASE_URL,
    FOOTBALL_DATA_RATE_LIMIT_SECONDS,
    MAX_SEASONS_BACK,
    MVP_LEAGUE,
)
from scripts.db import get_connection, init_db, update_data_source, upsert_match, upsert_team

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


class FootballDataClient:
    """Client for football-data.org API v4."""

    def __init__(self, api_key: str = FOOTBALL_DATA_API_KEY):
        if not api_key:
            raise ValueError(
                "FOOTBALL_DATA_API_KEY not set. "
                "Export it as an environment variable or pass it directly."
            )
        self.session = requests.Session()
        self.session.headers["X-Auth-Token"] = api_key
        self.base_url = FOOTBALL_DATA_BASE_URL
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < FOOTBALL_DATA_RATE_LIMIT_SECONDS:
            sleep_time = FOOTBALL_DATA_RATE_LIMIT_SECONDS - elapsed
            log.debug(f"Rate limiting: sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """Make a GET request with rate limiting and retry on 429."""
        self._rate_limit()
        url = f"{self.base_url}{endpoint}"
        max_retries = 3
        backoff = 6.0

        for attempt in range(max_retries):
            self._last_request_time = time.time()
            resp = self.session.get(url, params=params)

            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                wait = backoff * (2 ** attempt)
                log.warning(f"Rate limited (429). Retrying in {wait:.0f}s...")
                time.sleep(wait)
            else:
                resp.raise_for_status()

        raise RuntimeError(f"Failed after {max_retries} retries: {url}")

    def get_competition_teams(self, competition: str, season: int | None = None) -> list[dict]:
        """Get all teams for a competition."""
        params = {}
        if season is not None:
            params["season"] = season
        data = self._get(f"/competitions/{competition}/teams", params)
        return data.get("teams", [])

    def get_competition_matches(
        self, competition: str, season: int | None = None, status: str = "FINISHED"
    ) -> list[dict]:
        """Get all matches for a competition/season."""
        params = {"status": status}
        if season is not None:
            params["season"] = season
        data = self._get(f"/competitions/{competition}/matches", params)
        return data.get("matches", [])

    def get_team_matches(
        self,
        team_id: int,
        date_from: str | None = None,
        date_to: str | None = None,
        status: str = "FINISHED",
        competitions: str | None = None,
    ) -> list[dict]:
        """Get all matches for a team in a date range."""
        params = {"status": status}
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        if competitions:
            params["competitions"] = competitions
        data = self._get(f"/teams/{team_id}/matches", params)
        return data.get("matches", [])


def _compute_result(home: int, away: int) -> str:
    """Compute H/A/D from goal counts."""
    if home > away:
        return "H"
    elif away > home:
        return "A"
    return "D"


def _determine_decided_in(match_data: dict) -> str:
    """Determine how the match was decided based on API duration field."""
    duration = match_data.get("score", {}).get("duration", "REGULAR")
    if duration == "PENALTY_SHOOTOUT":
        return "PENALTIES"
    elif duration == "EXTRA_TIME":
        return "EXTRA_TIME"
    return "REGULAR"


def _map_competition_type(competition: dict) -> str:
    """Map API competition type to our model."""
    comp_type = competition.get("type", "")
    if comp_type == "LEAGUE":
        return "LEAGUE"
    elif comp_type == "CUP":
        code = competition.get("code", "")
        if code in ("CL", "EL", "CLI", "EC"):
            return "CONTINENTAL"
        return "DOMESTIC_CUP"
    return "LEAGUE"


def _season_label(start_year: int) -> str:
    """Convert a start year to a season label like '2025-26'."""
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def import_match(conn, match_data: dict, source: str = "football-data.org") -> int | None:
    """Parse an API match response and upsert into the database."""
    score = match_data.get("score", {})
    home_team = match_data["homeTeam"]
    away_team = match_data["awayTeam"]
    competition = match_data.get("competition", {})

    # Ensure teams exist
    home_id = upsert_team(
        conn,
        football_data_id=home_team["id"],
        name=home_team.get("name", f"Team {home_team['id']}"),
        short_name=home_team.get("shortName") or home_team.get("tla"),
        crest_url=home_team.get("crest"),
    )
    away_id = upsert_team(
        conn,
        football_data_id=away_team["id"],
        name=away_team.get("name", f"Team {away_team['id']}"),
        short_name=away_team.get("shortName") or away_team.get("tla"),
        crest_url=away_team.get("crest"),
    )

    # Score parsing
    full_time = score.get("fullTime", {})
    regular_time = score.get("regularTime")
    penalties = score.get("penalties")
    decided_in = _determine_decided_in(match_data)

    home_final = full_time.get("home")
    away_final = full_time.get("away")

    # 90-min score: use regularTime if available (cup matches with AET),
    # otherwise fullTime (league matches, no AET possible)
    if regular_time and regular_time.get("home") is not None:
        home_90 = regular_time["home"]
        away_90 = regular_time["away"]
    else:
        home_90 = home_final
        away_90 = away_final

    # Penalty scores
    home_pens = penalties.get("home") if penalties else None
    away_pens = penalties.get("away") if penalties else None

    # Compute results
    result_90min = _compute_result(home_90, away_90) if home_90 is not None else None
    if decided_in == "PENALTIES" and home_pens is not None:
        result_final = _compute_result(home_pens, away_pens)
    elif home_final is not None:
        result_final = _compute_result(home_final, away_final)
    else:
        result_final = None

    # Season label
    season_data = match_data.get("season", {})
    start_date = season_data.get("startDate", "")
    season_year = int(start_date[:4]) if start_date else None
    season_label = _season_label(season_year) if season_year else "unknown"

    return upsert_match(
        conn,
        source=source,
        source_match_id=str(match_data["id"]),
        date=match_data["utcDate"][:10],  # YYYY-MM-DD
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
        competition_id=competition.get("code", "UNK"),
        competition_name=competition.get("name", "Unknown"),
        competition_type=_map_competition_type(competition),
        round=match_data.get("matchday") and f"Matchday {match_data['matchday']}",
        season=season_label,
    )


def fetch_league_season(
    client: FootballDataClient,
    conn,
    league: str,
    season: int | None = None,
) -> int:
    """Fetch all matches for a league/season. Returns count of new matches."""
    log.info(f"Fetching {league} season={season or 'current'}...")
    matches = client.get_competition_matches(league, season=season)
    new_count = 0
    for m in matches:
        result = import_match(conn, m)
        if result is not None:
            new_count += 1

    season_label = _season_label(season) if season else "current"
    total = len(matches)
    log.info(f"  {league} {season_label}: {total} matches fetched, {new_count} new")

    update_data_source(
        conn,
        source="football-data.org",
        competition_id=league,
        season=season_label,
        last_fetched=datetime.now(timezone.utc).isoformat(),
        match_count=total,
        status="COMPLETE" if total > 0 else "PARTIAL",
    )
    return new_count


def fetch_team_all_competitions(
    client: FootballDataClient,
    conn,
    team_fd_id: int,
    date_from: str,
    date_to: str,
) -> int:
    """Fetch all matches for a team across all available competitions."""
    log.info(f"Fetching all matches for team {team_fd_id} ({date_from} to {date_to})...")
    matches = client.get_team_matches(
        team_fd_id, date_from=date_from, date_to=date_to
    )
    new_count = 0
    for m in matches:
        result = import_match(conn, m)
        if result is not None:
            new_count += 1
    log.info(f"  Team {team_fd_id}: {len(matches)} matches, {new_count} new")
    return new_count


def sync_teams(client: FootballDataClient, conn, league: str) -> list[dict]:
    """Fetch and sync all teams for a league. Returns team data."""
    log.info(f"Syncing teams for {league}...")
    teams = client.get_competition_teams(league)
    for t in teams:
        upsert_team(
            conn,
            football_data_id=t["id"],
            name=t.get("name", f"Team {t['id']}"),
            short_name=t.get("shortName") or t.get("tla"),
            crest_url=t.get("crest"),
            current_league=league,
            country=COMPETITIONS.get(league, {}).get("country"),
        )
    log.info(f"  Synced {len(teams)} teams for {league}")
    return teams


def run_full_fetch(league: str = MVP_LEAGUE, seasons_back: int = MAX_SEASONS_BACK) -> None:
    """Run a complete data fetch for a league: teams + matches for N seasons."""
    client = FootballDataClient()
    conn = get_connection()
    init_db(conn)

    # Step 1: Sync teams
    teams = sync_teams(client, conn, league)

    # Step 2: Fetch league matches per season
    # Current season (2025) + previous seasons
    current_year = 2025  # 2025-26 season
    for offset in range(seasons_back):
        season_year = current_year - offset
        fetch_league_season(client, conn, league, season=season_year)

    # Step 3: Fetch per-team matches (captures CL/EL matches not in league endpoint)
    for t in teams:
        fd_id = t["id"]
        for offset in range(seasons_back):
            season_year = current_year - offset
            date_from = f"{season_year}-07-01"
            date_to = f"{season_year + 1}-06-30"
            fetch_team_all_competitions(client, conn, fd_id, date_from, date_to)

    # Summary
    total = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    team_count = conn.execute(
        "SELECT COUNT(*) FROM teams WHERE current_league = ?", (league,)
    ).fetchone()[0]
    conn.commit()
    log.info(f"Done! {team_count} teams, {total} total matches in database.")
    conn.close()


def run_daily_update(league: str = MVP_LEAGUE) -> None:
    """Fetch only new matches for the current season."""
    client = FootballDataClient()
    conn = get_connection()
    init_db(conn)

    # Sync teams (might have transfers/promotions)
    sync_teams(client, conn, league)

    # Fetch current season league matches
    new = fetch_league_season(client, conn, league, season=2025)

    # Fetch per-team for CL/EL results
    teams = conn.execute(
        "SELECT football_data_id FROM teams WHERE current_league = ?", (league,)
    ).fetchall()
    for t in teams:
        fetch_team_all_competitions(
            client, conn, t["football_data_id"],
            date_from="2025-07-01", date_to="2026-06-30",
        )

    conn.commit()
    log.info(f"Daily update done. {new} new league matches.")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Fetch football match data")
    parser.add_argument(
        "--mode",
        choices=["full", "daily"],
        default="full",
        help="full = initial fetch (3 seasons), daily = current season only",
    )
    parser.add_argument("--league", default=MVP_LEAGUE, help="Competition code (default: DED)")
    parser.add_argument("--seasons", type=int, default=MAX_SEASONS_BACK, help="Seasons to look back")
    args = parser.parse_args()

    if args.mode == "full":
        run_full_fetch(league=args.league, seasons_back=args.seasons)
    else:
        run_daily_update(league=args.league)


if __name__ == "__main__":
    main()
