"""Configuration for the Hair Length Index pipeline."""

import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "hair-index.db"

# football-data.org API
FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"
FOOTBALL_DATA_API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")

# Rate limiting: 10 req/min on free tier → 6s between requests
FOOTBALL_DATA_RATE_LIMIT_SECONDS = 6.0

# API-Football (api-sports.io / RapidAPI)
API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
API_FOOTBALL_API_KEY = os.environ.get("API_FOOTBALL_API_KEY", "")

# Rate limiting: free tier = 100 req/day, no per-minute documented limit
# Be conservative: 1 req/sec
API_FOOTBALL_RATE_LIMIT_SECONDS = 1.0

# API-Football league IDs for competitions not on football-data.org free tier
API_FOOTBALL_LEAGUES = {
    "KNVB": {"api_id": 90, "name": "KNVB Beker", "type": "DOMESTIC_CUP", "country": "NL"},
    "EL": {"api_id": 3, "name": "Europa League", "type": "CONTINENTAL", "country": "EU"},
    "ECL": {"api_id": 848, "name": "Conference League", "type": "CONTINENTAL", "country": "EU"},
    "JE": {"api_id": 89, "name": "Eerste Divisie", "type": "LEAGUE", "country": "NL"},
    "SC_NL": {"api_id": 91, "name": "Johan Cruijff Schaal", "type": "SUPER_CUP", "country": "NL"},
}

# Competition codes (football-data.org free tier)
COMPETITIONS = {
    "DED": {"name": "Eredivisie", "type": "LEAGUE", "country": "NL"},
    "PL": {"name": "Premier League", "type": "LEAGUE", "country": "EN"},
    "BL1": {"name": "Bundesliga", "type": "LEAGUE", "country": "DE"},
    "SA": {"name": "Serie A", "type": "LEAGUE", "country": "IT"},
    "PD": {"name": "La Liga", "type": "LEAGUE", "country": "ES"},
    "FL1": {"name": "Ligue 1", "type": "LEAGUE", "country": "FR"},
    "ELC": {"name": "Championship", "type": "LEAGUE", "country": "EN"},
    "CL": {"name": "Champions League", "type": "CONTINENTAL", "country": "EU"},
    "EC": {"name": "European Championship", "type": "CONTINENTAL", "country": "EU"},
}

# MVP: Eredivisie only
MVP_LEAGUE = "DED"

# How many seasons back to search for streaks
MAX_SEASONS_BACK = 3

# Streak threshold
STREAK_THRESHOLD = 5

# Hair length tiers (days since last streak)
HAIR_TIERS = [
    (14, "Fresh cut", "Clean buzzcut, fresh fade"),
    (60, "Growing back", "Short neat hair, hint of stubble"),
    (120, "Getting shaggy", "Messy medium-length hair, visible beard"),
    (270, "Long & wild", "Long unkempt hair past shoulders, full beard"),
    (500, "Caveman", "Very long tangled hair, huge bushy beard"),
    (float("inf"), "Sasquatch", "Hair and beard merge, barely human"),
]


def get_hair_tier(days_since: int | None) -> tuple[str, str]:
    """Return (tier_name, description) for a given number of days."""
    if days_since is None:
        return ("Lost in time", "Need deeper historical data")
    for threshold, name, desc in HAIR_TIERS:
        if days_since <= threshold:
            return (name, desc)
    return ("Sasquatch", "Hair and beard merge, barely human")
