"""Fetch current-season home kit images from footyheadlines.com.

For each team, searches footyheadlines.com, finds the home kit article,
and downloads the first product photo.

Usage:
    python3.11 -m scripts.fetch_jerseys
    python3.11 -m scripts.fetch_jerseys --team Ajax
    python3.11 -m scripts.fetch_jerseys --league DED
"""

import argparse
import json
import logging
import re
import time
from pathlib import Path

import requests

from scripts.config import PROJECT_ROOT
from scripts.team_registry import TEAMS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

JERSEYS_DIR = PROJECT_ROOT / "frontend" / "jerseys"
JERSEY_MAP_FILE = PROJECT_ROOT / "frontend" / "jersey-map.json"

SEASON = "25-26"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
}

# Map our canonical names to footyheadlines search terms.
# Most teams: just use the common name (drop "FC", country suffixes, etc.)
# Override only where the default slugify wouldn't work.
FH_OVERRIDES = {
    # Dutch — footyheadlines labels
    "AZ Alkmaar": "AZ",
    "N.E.C.": "NEC",
    "PSV Eindhoven": "PSV",
    "NAC Breda": "NAC",
    "FC Volendam": "Volendam",
    "Fortuna Sittard": "Fortuna Sittard",
    "Heracles Almelo": "Heracles",
    # English
    "Arsenal FC": "Arsenal",
    "AFC Bournemouth": "Bournemouth",
    "Brighton & Hove Albion": "Brighton",
    "Brentford FC": "Brentford",
    "Burnley FC": "Burnley",
    "Chelsea FC": "Chelsea",
    "Crystal Palace": "Crystal Palace",
    "Everton FC": "Everton",
    "Fulham FC": "Fulham",
    "Leeds United": "Leeds United",
    "Liverpool FC": "Liverpool",
    "Manchester City": "Manchester City",
    "Manchester United": "Manchester United",
    "Newcastle United": "Newcastle",
    "Nottingham Forest": "Nottingham Forest",
    "Sunderland AFC": "Sunderland",
    "Tottenham Hotspur": "Tottenham",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
    # German — footyheadlines uses German names
    "1. FC Heidenheim 1846": "Heidenheim",
    "1. FC Köln": "1. FC Köln",
    "1. FC Union Berlin": "Union Berlin",
    "1. FSV Mainz 05": "Mainz",
    "1899 Hoffenheim": "Hoffenheim",
    "Bayer Leverkusen": "Bayer Leverkusen",
    "Bayern Munich": "Bayern München",
    "Bor. Mönchengladbach": "Gladbach",
    "Borussia Dortmund": "Borussia Dortmund",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "FC Augsburg": "Augsburg",
    "FC St. Pauli": "St. Pauli",
    "Hamburger SV": "Hamburg",
    "RB Leipzig": "RB Leipzig",
    "SC Freiburg": "Freiburg",
    "VfB Stuttgart": "Stuttgart",
    "VfL Wolfsburg": "Wolfsburg",
    "Werder Bremen": "Werder Bremen",
    # Spanish
    "Athletic Club": "Athletic Bilbao",
    "Atlético Madrid": "Atlético Madrid",
    "CA Osasuna": "Osasuna",
    "CD Alavés": "Alavés",
    "Celta de Vigo": "Celta",
    "Elche CF": "Elche",
    "FC Barcelona": "FC Barcelona",
    "Getafe CF": "Getafe",
    "Girona FC": "Girona",
    "Levante UD": "Levante",
    "RCD Espanyol": "Espanyol",
    "RCD Mallorca": "Mallorca",
    "Rayo Vallecano": "Rayo Vallecano",
    "Real Betis": "Real Betis",
    "Real Madrid": "Real Madrid",
    "Real Oviedo": "Real Oviedo",
    "Real Sociedad": "Real Sociedad",
    "Sevilla FC": "Sevilla",
    "Valencia CF": "Valencia",
    "Villarreal CF": "Villarreal",
    # Italian
    "AC Milan": "AC Milan",
    "ACF Fiorentina": "Fiorentina",
    "AS Roma": "AS Roma",
    "Atalanta": "Atalanta",
    "Bologna FC": "Bologna",
    "Cagliari Calcio": "Cagliari",
    "Como 1907": "Como",
    "Genoa CFC": "Genoa",
    "Hellas Verona": "Verona",
    "Inter": "Inter Milan",
    "Juventus": "Juventus",
    "Lazio Roma": "Lazio",
    "Parma Calcio 1913": "Parma",
    "Pisa SC": "Pisa",
    "SSC Napoli": "Napoli",
    "Sassuolo Calcio": "Sassuolo",
    "Torino FC": "Torino",
    "US Cremonese": "Cremonese",
    "US Lecce": "Lecce",
    "Udinese Calcio": "Udinese",
    # French
    "AJ Auxerre": "Auxerre",
    "Angers SCO": "Angers",
    "AS Monaco": "AS Monaco",
    "FC Lorient": "Lorient",
    "FC Metz": "Metz",
    "FC Nantes": "Nantes",
    "Havre AC": "Le Havre",
    "Lille OSC": "Lille",
    "OGC Nice": "Nice",
    "Olympique Lyonnais": "Lyon",
    "Olympique Marseille": "Marseille",
    "Paris FC": "Paris FC",
    "Paris Saint-Germain": "PSG",
    "RC Lens": "Lens",
    "RC Strasbourg": "Strasbourg",
    "Stade Brestois 29": "Brest",
    "Stade Rennais": "Rennes",
    "Toulouse FC": "Toulouse",
}


def get_fh_search_term(team_name: str) -> str:
    """Get the footyheadlines search term for a team."""
    return FH_OVERRIDES.get(team_name, team_name)


def find_kit_article_url(team_name: str, session: requests.Session) -> str | None:
    """Search footyheadlines label page for the home kit article URL."""
    search_term = get_fh_search_term(team_name)
    label_url = f"https://www.footyheadlines.com/search/label/{search_term}"
    log.info(f"  Searching: {label_url}")

    try:
        resp = session.get(label_url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"  Label page returned {resp.status_code}")
            return None

        # Find article URLs matching "{season} home kit" (URLs can be relative or absolute)
        pattern = rf'href="(/?\d{{4}}/\d{{2}}/[^"]*{SEASON}[^"]*home[^"]*kit[^"]*\.html)"'
        matches = re.findall(pattern, resp.text, re.IGNORECASE)
        if matches:
            url = matches[0] if matches[0].startswith("http") else f"https://www.footyheadlines.com{matches[0]}"
            log.info(f"  Found article: {url}")
            return url

        # Broader: any home kit article
        pattern2 = rf'href="(/?\d{{4}}/\d{{2}}/[^"]*home[^"]*kit[^"]*\.html)"'
        matches2 = re.findall(pattern2, resp.text, re.IGNORECASE)
        for m in matches2:
            if SEASON in m:
                url = m if m.startswith("http") else f"https://www.footyheadlines.com{m}"
                log.info(f"  Found article (broad): {url}")
                return url
        if matches2:
            url = matches2[0] if matches2[0].startswith("http") else f"https://www.footyheadlines.com{matches2[0]}"
            log.info(f"  Found article (fallback): {url}")
            return url

        log.warning(f"  No home kit article found for {team_name}")
        return None

    except Exception as e:
        log.warning(f"  Error searching for {team_name}: {e}")
        return None


def download_kit_image(article_url: str, team_slug: str, session: requests.Session) -> Path | None:
    """Download the first product photo from a kit article."""
    try:
        resp = session.get(article_url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            log.warning(f"  Article returned {resp.status_code}")
            return None

        # Find blogger CDN images (the actual kit photos)
        img_pattern = r'(https://blogger\.googleusercontent\.com/img/b/[^"\']+\.(?:jpg|png|webp))'
        images = re.findall(img_pattern, resp.text)

        if not images:
            # Try alternative pattern
            img_pattern2 = r'(https://[^"\']*googleusercontent\.com[^"\']+)'
            images = re.findall(img_pattern2, resp.text)

        if not images:
            log.warning(f"  No images found in article")
            return None

        # Use the first or second image (first is often the header/hero shot)
        # Skip very small thumbnails by picking image index 1-2
        img_url = images[min(1, len(images) - 1)]

        # Replace size parameter for higher quality (s1600 → s800 for reasonable size)
        img_url = re.sub(r'/s\d+/', '/s800/', img_url)

        log.info(f"  Downloading image...")
        img_resp = session.get(img_url, headers=HEADERS, timeout=30)
        if img_resp.status_code != 200:
            log.warning(f"  Image download failed: {img_resp.status_code}")
            return None

        JERSEYS_DIR.mkdir(parents=True, exist_ok=True)
        ext = "jpg"
        if "png" in img_url.lower():
            ext = "png"
        filepath = JERSEYS_DIR / f"{team_slug}.{ext}"
        filepath.write_bytes(img_resp.content)
        log.info(f"  Saved: {filepath} ({len(img_resp.content) // 1024}KB)")
        return filepath

    except Exception as e:
        log.warning(f"  Error downloading image: {e}")
        return None


def fetch_team_jersey(team_name: str, team_slug: str, session: requests.Session) -> str | None:
    """Fetch jersey for one team. Returns relative path or None."""
    log.info(f"Fetching jersey for {team_name}...")

    article_url = find_kit_article_url(team_name, session)
    if not article_url:
        return None

    time.sleep(2)  # Rate limit between article search and fetch

    filepath = download_kit_image(article_url, team_slug, session)
    if filepath:
        return f"jerseys/{filepath.name}"
    return None


def run(team_filter: str = None, league_filter: str = None):
    """Fetch jerseys for all teams (or filtered)."""
    session = requests.Session()
    jersey_map = {}

    # Load existing map
    if JERSEY_MAP_FILE.exists():
        jersey_map = json.loads(JERSEY_MAP_FILE.read_text())

    teams_to_fetch = []
    for name, (wf_id, slug, league) in TEAMS.items():
        if league == "JE":
            continue  # Skip Eerste Divisie
        if team_filter and team_filter.lower() not in name.lower():
            continue
        if league_filter and league != league_filter:
            continue
        teams_to_fetch.append((name, slug))

    log.info(f"Fetching jerseys for {len(teams_to_fetch)} teams...")

    for name, slug in teams_to_fetch:
        # Skip if already have it
        if name in jersey_map and (JERSEYS_DIR / jersey_map[name].split("/")[-1]).exists():
            log.info(f"  {name}: already have jersey, skipping")
            continue

        result = fetch_team_jersey(name, slug, session)
        if result:
            jersey_map[name] = result

        time.sleep(8)  # Rate limit between teams

    # Save map
    JERSEY_MAP_FILE.write_text(json.dumps(jersey_map, indent=2, ensure_ascii=False))
    log.info(f"Saved jersey map: {len(jersey_map)} teams → {JERSEY_MAP_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Fetch club jersey images")
    parser.add_argument("--team", type=str, help="Fetch for a specific team")
    parser.add_argument("--league", type=str, help="Fetch for a specific league")
    args = parser.parse_args()
    run(team_filter=args.team, league_filter=args.league)


if __name__ == "__main__":
    main()
