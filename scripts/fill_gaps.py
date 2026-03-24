"""Fill data gaps using API-Football (api-sports.io).

Fetches cup matches, Europa/Conference League, and other competitions
that football-data.org's free tier doesn't cover.
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
    MAX_SEASONS_BACK,
    MVP_LEAGUE,
)
from scripts.db import (
    find_team_by_api_football_id,
    find_team_by_name,
    get_all_teams,
    get_connection,
    get_teams_missing_cup_data,
    init_db,
    set_api_football_id,
    update_data_source,
    upsert_match,
    upsert_team,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# API-Football free tier: only seasons 2022-2024 available
API_FOOTBALL_FREE_TIER_MIN_SEASON = 2022
API_FOOTBALL_FREE_TIER_MAX_SEASON = 2024


class RateLimitExceeded(Exception):
    """Raised when API-Football daily rate limit is hit."""
    pass


class SeasonUnavailable(Exception):
    """Raised when API-Football plan doesn't cover a season."""
    pass


class APIFootballClient:
    """Client for API-Football v3 (api-sports.io)."""

    def __init__(self, api_key: str = API_FOOTBALL_API_KEY):
        if not api_key:
            raise ValueError(
                "API_FOOTBALL_API_KEY not set. "
                "Export it as an environment variable or pass it directly."
            )
        self.session = requests.Session()
        self.session.headers["x-apisports-key"] = api_key
        self.base_url = API_FOOTBALL_BASE_URL
        self._last_request_time = 0.0
        self._requests_today = 0

    def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < API_FOOTBALL_RATE_LIMIT_SECONDS:
            time.sleep(API_FOOTBALL_RATE_LIMIT_SECONDS - elapsed)

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """Make a GET request with rate limiting."""
        self._rate_limit()
        url = f"{self.base_url}/{endpoint}"
        self._last_request_time = time.time()
        self._requests_today += 1

        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        # Check for API errors
        errors = data.get("errors")
        if errors:
            if isinstance(errors, dict):
                if errors.get("rateLimit"):
                    log.warning("API-Football rate limit reached. Saving progress and stopping.")
                    raise RateLimitExceeded("Daily rate limit exceeded")
                if errors.get("plan"):
                    log.info(f"  Season unavailable on free tier: {errors['plan']}")
                    raise SeasonUnavailable(errors["plan"])
            log.warning(f"API-Football errors: {errors}")

        remaining = resp.headers.get("x-ratelimit-requests-remaining")
        if remaining:
            log.debug(f"API-Football requests remaining today: {remaining}")

        return data

    def search_team(self, name: str) -> list[dict]:
        """Search for a team by name."""
        data = self._get("teams", params={"search": name})
        return data.get("response", [])

    def get_team_by_league(self, league_id: int, season: int) -> list[dict]:
        """Get all teams in a league for a season."""
        data = self._get("teams", params={"league": league_id, "season": season})
        return data.get("response", [])

    def get_fixtures(
        self,
        team_id: int | None = None,
        league_id: int | None = None,
        season: int | None = None,
        status: str = "FT-AET-PEN",
    ) -> list[dict]:
        """Get fixtures (finished matches).

        status: "FT" (full time), "AET" (after extra time), "PEN" (penalties)
        Use "FT-AET-PEN" to get all finished matches.
        """
        params = {"status": status}
        if team_id:
            params["team"] = team_id
        if league_id:
            params["league"] = league_id
        if season:
            params["season"] = season
        data = self._get("fixtures", params=params)
        return data.get("response", [])

    @property
    def requests_used(self) -> int:
        return self._requests_today


# === Team ID Mapping ===

# Known mappings: football-data.org name → API-Football team ID
# These are pre-populated for Eredivisie 2025-26 to avoid wasting API calls.
# If a team isn't here, we fall back to search.
KNOWN_TEAM_MAPPINGS = {
    # Eredivisie
    "PSV": 197,
    "Feyenoord Rotterdam": 198,
    "AFC Ajax": 194,
    "AZ": 201,
    "FC Twente '65": 199,
    "FC Utrecht": 200,
    "Sparta Rotterdam": 203,
    "sc Heerenveen": 202,
    "Heracles Almelo": 206,
    "Go Ahead Eagles": 1909,
    "NEC": 208,
    "Willem II": 210,
    "PEC Zwolle": 209,
    "RKC Waalwijk": 207,
    "FC Groningen": 204,
    "NAC Breda": 211,
    "Almere City FC": 1911,
    "Fortuna Sittard": 205,
}


def resolve_api_football_id(
    conn, client: APIFootballClient, team_name: str, team_id: int
) -> int | None:
    """Resolve a team's API-Football ID, using cache/DB first, then API search."""
    # Check if already stored in DB
    team = conn.execute("SELECT api_football_id FROM teams WHERE id = ?", (team_id,)).fetchone()
    if team and team["api_football_id"]:
        return team["api_football_id"]

    # Check known mappings
    if team_name in KNOWN_TEAM_MAPPINGS:
        api_id = KNOWN_TEAM_MAPPINGS[team_name]
        set_api_football_id(conn, team_id, api_id)
        log.info(f"  Mapped {team_name} → API-Football ID {api_id} (known)")
        return api_id

    # Fall back to API search
    log.info(f"  Searching API-Football for '{team_name}'...")
    results = client.search_team(team_name)
    if not results:
        # Try short name
        short = conn.execute("SELECT short_name FROM teams WHERE id = ?", (team_id,)).fetchone()
        if short and short["short_name"]:
            results = client.search_team(short["short_name"])

    if results:
        # Pick the best match (prefer Netherlands)
        for r in results:
            team_data = r.get("team", {})
            if team_data.get("country") == "Netherlands":
                api_id = team_data["id"]
                set_api_football_id(conn, team_id, api_id)
                log.info(f"  Mapped {team_name} → API-Football ID {api_id} (search)")
                return api_id
        # If no Dutch team found, take first result
        api_id = results[0]["team"]["id"]
        set_api_football_id(conn, team_id, api_id)
        log.info(f"  Mapped {team_name} → API-Football ID {api_id} (best guess)")
        return api_id

    log.warning(f"  Could not find API-Football ID for {team_name}")
    return None


# === Match Import ===

def _compute_result(home: int, away: int) -> str:
    if home > away:
        return "H"
    elif away > home:
        return "A"
    return "D"


def _map_status_to_decided_in(status_short: str) -> str:
    """Map API-Football status to our decided_in field."""
    if status_short == "PEN":
        return "PENALTIES"
    elif status_short == "AET":
        return "EXTRA_TIME"
    return "REGULAR"


def _map_league_type(league_type: str) -> str:
    """Map API-Football league type to our competition_type."""
    if league_type == "League":
        return "LEAGUE"
    elif league_type == "Cup":
        return "DOMESTIC_CUP"
    return "LEAGUE"


def _season_label(season_year: int) -> str:
    """Convert API-Football season year to our label format."""
    return f"{season_year}-{str(season_year + 1)[-2:]}"


def import_api_football_fixture(conn, fixture: dict) -> int | None:
    """Import a single API-Football fixture into the database."""
    fixture_info = fixture.get("fixture", {})
    league = fixture.get("league", {})
    teams = fixture.get("teams", {})
    goals = fixture.get("goals", {})
    score = fixture.get("score", {})

    # Skip if not finished
    status = fixture_info.get("status", {}).get("short", "")
    if status not in ("FT", "AET", "PEN"):
        return None

    # Resolve teams — need internal IDs
    home_api_id = teams.get("home", {}).get("id")
    away_api_id = teams.get("away", {}).get("id")
    home_name = teams.get("home", {}).get("name", "Unknown")
    away_name = teams.get("away", {}).get("name", "Unknown")

    # Look up or create teams
    home_team = find_team_by_api_football_id(conn, home_api_id)
    if home_team:
        home_id = home_team["id"]
    else:
        # Try name match, otherwise create
        home_team = find_team_by_name(conn, home_name)
        if home_team:
            home_id = home_team["id"]
            if not home_team["api_football_id"]:
                set_api_football_id(conn, home_id, home_api_id)
        else:
            home_id = upsert_team(
                conn, name=home_name, api_football_id=home_api_id,
                country=league.get("country"),
            )

    away_team = find_team_by_api_football_id(conn, away_api_id)
    if away_team:
        away_id = away_team["id"]
    else:
        away_team = find_team_by_name(conn, away_name)
        if away_team:
            away_id = away_team["id"]
            if not away_team["api_football_id"]:
                set_api_football_id(conn, away_id, away_api_id)
        else:
            away_id = upsert_team(
                conn, name=away_name, api_football_id=away_api_id,
                country=league.get("country"),
            )

    # Scores
    # goals.home / goals.away = final score (after AET if applicable, before pens)
    home_goals_final = goals.get("home")
    away_goals_final = goals.get("away")

    # score.fulltime = 90-min score
    fulltime = score.get("fulltime", {})
    home_goals_90 = fulltime.get("home")
    away_goals_90 = fulltime.get("away")

    # score.extratime = goals in extra time only (None if no ET)
    extratime = score.get("extratime", {})
    # score.penalty = penalty shootout score (None if no pens)
    penalty = score.get("penalty", {})

    home_pens = penalty.get("home") if penalty else None
    away_pens = penalty.get("away") if penalty else None

    decided_in = _map_status_to_decided_in(status)

    # Compute results
    result_90min = _compute_result(home_goals_90, away_goals_90) if home_goals_90 is not None else None
    if decided_in == "PENALTIES" and home_pens is not None:
        result_final = _compute_result(home_pens, away_pens)
    elif home_goals_final is not None:
        result_final = _compute_result(home_goals_final, away_goals_final)
    else:
        result_final = None

    # Competition type
    league_type = league.get("type", "League")
    comp_type = _map_league_type(league_type)
    # Override for known continental competitions
    league_id = league.get("id")
    if league_id in (2, 3, 848):  # CL, EL, ECL
        comp_type = "CONTINENTAL"

    # Date
    match_date = fixture_info.get("date", "")[:10]

    # Season
    season_year = league.get("season")
    season_label = _season_label(season_year) if season_year else "unknown"

    # League code mapping (API-Football ID → our competition_id)
    comp_id = _league_id_to_code(league_id, league.get("name", ""))

    return upsert_match(
        conn,
        source="api-football",
        source_match_id=str(fixture_info.get("id", "")),
        date=match_date,
        home_team_id=home_id,
        away_team_id=away_id,
        home_goals_90min=home_goals_90,
        away_goals_90min=away_goals_90,
        home_goals_final=home_goals_final,
        away_goals_final=away_goals_final,
        home_goals_penalties=home_pens,
        away_goals_penalties=away_pens,
        decided_in=decided_in,
        result_90min=result_90min,
        result_final=result_final,
        competition_id=comp_id,
        competition_name=league.get("name", "Unknown"),
        competition_type=comp_type,
        round=league.get("round"),
        season=season_label,
    )


def _league_id_to_code(league_id: int, league_name: str) -> str:
    """Map API-Football league ID to our competition code."""
    mapping = {
        88: "DED",    # Eredivisie
        89: "JE",     # Eerste Divisie
        90: "KNVB",   # KNVB Beker
        91: "SC_NL",  # Johan Cruijff Schaal
        2: "CL",      # Champions League
        3: "EL",      # Europa League
        848: "ECL",   # Conference League
        39: "PL",     # Premier League
        78: "BL1",    # Bundesliga
        135: "SA",    # Serie A
        140: "PD",    # La Liga
        61: "FL1",    # Ligue 1
        45: "FA",     # FA Cup
        81: "DFB",    # DFB-Pokal
        143: "CDR",   # Copa del Rey
        137: "CI",    # Coppa Italia
        66: "CDF",    # Coupe de France
    }
    return mapping.get(league_id, f"AF_{league_id}")


# === Gap Detection & Filling ===

def find_gaps(conn, league: str, seasons: list[str]) -> dict:
    """Identify what data is missing.

    Returns a dict of {competition_id: [seasons_missing]}.
    """
    gaps = {}

    for season in seasons:
        # Check which cup competitions we're missing for teams in this league
        teams = get_all_teams(conn, league=league)
        if not teams:
            continue

        # Check for KNVB Beker data
        cup_matches = conn.execute(
            """
            SELECT COUNT(*) FROM matches
            WHERE competition_type = 'DOMESTIC_CUP' AND season = ?
            AND (home_team_id IN (SELECT id FROM teams WHERE current_league = ?)
                 OR away_team_id IN (SELECT id FROM teams WHERE current_league = ?))
            """,
            (season, league, league),
        ).fetchone()[0]

        if cup_matches == 0:
            gaps.setdefault("KNVB", []).append(season)

        # Check for Europa League / Conference League
        for comp_code, comp_info in [("EL", API_FOOTBALL_LEAGUES.get("EL")),
                                      ("ECL", API_FOOTBALL_LEAGUES.get("ECL"))]:
            if comp_info is None:
                continue
            european_matches = conn.execute(
                """
                SELECT COUNT(*) FROM matches
                WHERE competition_id = ? AND season = ?
                """,
                (comp_code, season),
            ).fetchone()[0]
            # Only flag as gap if we have 0 matches — some teams might not play in Europe
            # We'll check per-team later
            if european_matches == 0:
                # Check data_sources to see if we already tried
                ds = conn.execute(
                    "SELECT status FROM data_sources WHERE source = 'api-football' AND competition_id = ? AND season = ?",
                    (comp_code, season),
                ).fetchone()
                if not ds or ds["status"] == "PENDING":
                    gaps.setdefault(comp_code, []).append(season)

    return gaps


def fill_team_cups(
    client: APIFootballClient,
    conn,
    team_id: int,
    team_name: str,
    api_football_id: int,
    season_year: int,
) -> int:
    """Fetch all cup matches for a team in a season from API-Football."""
    season_label = _season_label(season_year)
    log.info(f"  Fetching cups for {team_name} ({season_label})...")

    try:
        fixtures = client.get_fixtures(team_id=api_football_id, season=season_year)
    except SeasonUnavailable:
        log.info(f"    {team_name}: season {season_label} not available on free tier, skipping")
        return 0

    new_count = 0
    for f in fixtures:
        league = f.get("league", {})
        league_id = league.get("id")
        # Skip Eredivisie — we already have that from football-data.org
        if league_id == 88:
            continue
        result = import_api_football_fixture(conn, f)
        if result is not None:
            new_count += 1

    log.info(f"    {team_name}: {new_count} new non-league matches imported")
    return new_count


def run_fill_gaps(league: str = MVP_LEAGUE, seasons_back: int = MAX_SEASONS_BACK) -> None:
    """Main entry point: detect and fill data gaps."""
    client = APIFootballClient()
    conn = get_connection()
    init_db(conn)

    current_year = 2025
    seasons = [_season_label(current_year - i) for i in range(seasons_back)]

    # Step 1: Detect gaps
    gaps = find_gaps(conn, league, seasons)
    if not gaps:
        log.info("No gaps detected! All data appears complete.")
    else:
        log.info(f"Gaps detected: {gaps}")

    # Step 2: For each team, resolve API-Football ID and fetch cup matches
    teams = get_all_teams(conn, league=league)
    if not teams:
        log.warning(f"No teams found for {league}. Run fetch_matches.py first.")
        return

    # Filter to seasons available on free tier
    available_seasons = [
        current_year - offset
        for offset in range(seasons_back)
        if API_FOOTBALL_FREE_TIER_MIN_SEASON <= (current_year - offset) <= API_FOOTBALL_FREE_TIER_MAX_SEASON
    ]
    if not available_seasons:
        log.warning("No seasons available on API-Football free tier for the requested range.")
    else:
        skipped = seasons_back - len(available_seasons)
        if skipped > 0:
            log.info(f"Skipping {skipped} season(s) outside free tier range "
                     f"({API_FOOTBALL_FREE_TIER_MIN_SEASON}-{API_FOOTBALL_FREE_TIER_MAX_SEASON})")

    # Prioritize teams without a found streak — they need ED/cup data most
    from scripts.compute_streaks import find_last_streak
    from scripts.db import get_team_matches as _get_team_matches
    def _has_streak(team_row):
        matches = _get_team_matches(conn, team_row["id"], order="DESC")
        result = find_last_streak(matches, team_row["id"], 5, "result_final")
        return result["found"]

    teams_no_streak = [t for t in teams if not _has_streak(t)]
    teams_with_streak = [t for t in teams if t not in teams_no_streak]
    ordered_teams = teams_no_streak + teams_with_streak
    if teams_no_streak:
        log.info(f"Prioritizing {len(teams_no_streak)} teams without a 5-win streak")

    total_new = 0
    teams_processed = 0
    rate_limited = False
    for team in ordered_teams:
        api_id = resolve_api_football_id(conn, client, team["name"], team["id"])
        if api_id is None:
            log.warning(f"  Skipping {team['name']} — no API-Football ID")
            continue

        try:
            for season_year in available_seasons:
                new = fill_team_cups(client, conn, team["id"], team["name"], api_id, season_year)
                total_new += new
        except RateLimitExceeded:
            log.warning(f"Rate limit hit while processing {team['name']}. "
                        f"Progress saved: {teams_processed} teams done, {total_new} matches imported.")
            rate_limited = True
            break

        teams_processed += 1

        # Check API budget proactively
        if client.requests_used >= 90:
            log.warning(f"Approaching API limit ({client.requests_used} requests used). "
                        f"Stopping after {teams_processed} teams, {total_new} matches imported.")
            break

    # Step 3: Update data_sources
    for season_year_offset in range(seasons_back):
        s_year = current_year - season_year_offset
        s_label = _season_label(s_year)
        for comp_code in ("KNVB", "EL", "ECL"):
            count = conn.execute(
                "SELECT COUNT(*) FROM matches WHERE competition_id = ? AND season = ? AND source = 'api-football'",
                (comp_code, s_label),
            ).fetchone()[0]
            if count > 0:
                update_data_source(
                    conn,
                    source="api-football",
                    competition_id=comp_code,
                    season=s_label,
                    last_fetched=datetime.now(timezone.utc).isoformat(),
                    match_count=count,
                    status="COMPLETE",
                )

    log.info(f"Gap filling done. {total_new} new matches imported. "
             f"{client.requests_used} API requests used.")
    conn.close()


def run_map_teams(league: str = MVP_LEAGUE) -> None:
    """Map all teams in a league to API-Football IDs (without fetching matches)."""
    client = APIFootballClient()
    conn = get_connection()
    init_db(conn)

    teams = get_all_teams(conn, league=league)
    if not teams:
        log.warning(f"No teams found for {league}. Run fetch_matches.py first.")
        return

    mapped = 0
    for team in teams:
        api_id = resolve_api_football_id(conn, client, team["name"], team["id"])
        if api_id:
            mapped += 1

    log.info(f"Mapped {mapped}/{len(teams)} teams to API-Football IDs. "
             f"{client.requests_used} API requests used.")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Fill data gaps via API-Football")
    parser.add_argument(
        "--mode",
        choices=["fill", "map-teams", "detect"],
        default="fill",
        help="fill = fetch missing data, map-teams = only resolve team IDs, detect = show gaps",
    )
    parser.add_argument("--league", default=MVP_LEAGUE, help="Competition code")
    parser.add_argument("--seasons", type=int, default=MAX_SEASONS_BACK, help="Seasons back")
    args = parser.parse_args()

    if args.mode == "fill":
        run_fill_gaps(league=args.league, seasons_back=args.seasons)
    elif args.mode == "map-teams":
        run_map_teams(league=args.league)
    elif args.mode == "detect":
        conn = get_connection()
        init_db(conn)
        current_year = 2025
        seasons = [_season_label(current_year - i) for i in range(args.seasons)]
        gaps = find_gaps(conn, args.league, seasons)
        if gaps:
            print("Data gaps detected:")
            for comp, seasons_list in gaps.items():
                print(f"  {comp}: {', '.join(seasons_list)}")
        else:
            print("No gaps detected.")
        conn.close()


if __name__ == "__main__":
    main()
