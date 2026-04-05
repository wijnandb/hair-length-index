"""Export fan culture data from Python to JSON for the frontend.

Reads RIVALRIES, CLUB_HASHTAGS, and CLUB_BIRTHDAYS from fan_data.py
and writes data/fan-data.json with bidirectional rivalries, hashtags,
and birthday info including founding years where known.
"""

import json
import os
from collections import defaultdict

from scripts.fan_data import CLUB_BIRTHDAYS, CLUB_HASHTAGS, RIVALRIES

# Founding years for clubs (not stored in fan_data.py which only has month/day)
FOUNDING_YEARS = {
    # Eredivisie
    "Ajax": 1900,
    "Sparta Rotterdam": 1888,
    "Vitesse": 1892,
    "N.E.C.": 1900,
    "Excelsior": 1902,
    "Heracles Almelo": 1903,
    "Feyenoord": 1908,
    "PSV Eindhoven": 1913,
    "NAC Breda": 1912,
    "Heerenveen": 1920,
    "FC Volendam": 1920,
    "Telstar": 1963,
    "AZ Alkmaar": 1967,
    "Fortuna Sittard": 1968,
    "FC Groningen": 1971,
    "FC Twente": 1965,
    "FC Utrecht": 1970,
    "Go Ahead Eagles": 1902,
    "PEC Zwolle": 1910,
    "Willem II": 1896,
    "RKC Waalwijk": 1940,
    "ADO Den Haag": 1905,
    "Almere City FC": 2001,
    # Premier League
    "Liverpool FC": 1892,
    "Arsenal FC": 1886,
    "Tottenham Hotspur": 1882,
    "Chelsea FC": 1905,
    "Manchester City": 1880,
    "Manchester United": 1878,
    "Newcastle United": 1892,
    "Everton FC": 1878,
    "West Ham United": 1895,
    "Aston Villa": 1874,
    "Brighton & Hove Albion": 1901,
    "Nottingham Forest": 1865,
    "Crystal Palace": 1905,
    "Fulham FC": 1879,
    "Brentford FC": 1889,
    "Wolverhampton Wanderers": 1877,
    "AFC Bournemouth": 1899,
    "Leeds United": 1919,
    "Burnley FC": 1882,
    "Sunderland AFC": 1879,
    # Bundesliga
    "Bayern Munich": 1900,
    "Borussia Dortmund": 1909,
    "Bayer Leverkusen": 1904,
    "RB Leipzig": 2009,
    "Eintracht Frankfurt": 1899,
    "VfB Stuttgart": 1893,
    "SC Freiburg": 1904,
    "VfL Wolfsburg": 1945,
    "1. FC Union Berlin": 1966,
    "Werder Bremen": 1899,
    "1. FC Köln": 1948,
    "Bor. Mönchengladbach": 1900,
    "Hamburger SV": 1887,
    # La Liga
    "Real Madrid": 1902,
    "FC Barcelona": 1899,
    "Atlético Madrid": 1903,
    "Athletic Club": 1898,
    "Real Sociedad": 1909,
    "Sevilla FC": 1890,
    "Villarreal CF": 1923,
    "Real Betis": 1907,
    "RCD Espanyol": 1900,
    # Serie A
    "Juventus": 1897,
    "Inter": 1908,
    "AC Milan": 1899,
    "SSC Napoli": 1926,
    "AS Roma": 1927,
    "Lazio Roma": 1900,
    "Atalanta": 1907,
    "ACF Fiorentina": 1926,
    "Torino FC": 1906,
    "Genoa CFC": 1893,
    "Sampdoria": 1946,
    # Ligue 1
    "Paris Saint-Germain": 1970,
    "Olympique Marseille": 1899,
    "Olympique Lyonnais": 1950,
    "AS Monaco": 1924,
    "Lille OSC": 1944,
    "Stade Rennais": 1901,
}


def export_fan_data():
    """Export fan data to JSON."""
    # Build bidirectional rivalries
    rivalries = defaultdict(list)
    for r in RIVALRIES:
        team_a, team_b = r["teams"]
        entry_for_a = {
            "opponent": team_b,
            "name": r["name"],
            "hashtags": r["hashtags"],
        }
        entry_for_b = {
            "opponent": team_a,
            "name": r["name"],
            "hashtags": r["hashtags"],
        }
        rivalries[team_a].append(entry_for_a)
        rivalries[team_b].append(entry_for_b)

    # Build hashtags (straight copy)
    hashtags = dict(CLUB_HASHTAGS)

    # Build birthdays with founding years
    birthdays = {}
    for (month, day), team in CLUB_BIRTHDAYS.items():
        entry = {"month": month, "day": day}
        if team in FOUNDING_YEARS:
            entry["year"] = FOUNDING_YEARS[team]
        birthdays[team] = entry

    data = {
        "rivalries": dict(rivalries),
        "hashtags": hashtags,
        "birthdays": birthdays,
    }

    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "fan-data.json")
    output_path = os.path.normpath(output_path)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    team_count = len(set(list(rivalries.keys()) + list(hashtags.keys()) + list(birthdays.keys())))
    print(f"Exported fan data: {len(rivalries)} teams with rivalries, "
          f"{len(hashtags)} with hashtags, {len(birthdays)} with birthdays "
          f"({team_count} unique teams) → {output_path}")


if __name__ == "__main__":
    export_fan_data()
