"""Central team registry with canonical names and aliases.

The single source of truth for team identity. All importers use this
to resolve opponent names to canonical team IDs.
"""

from scripts.db import find_team_by_name, upsert_team

# Canonical teams from worldfootball.net competition standings pages.
# Format: canonical_name → (wf_id, slug, current_league)
TEAMS = {
    # Eredivisie 2025-26
    "Ajax": ("te64", "afc-ajax", "DED"),
    "AZ Alkmaar": ("te181", "az-alkmaar", "DED"),
    "Excelsior": ("te577", "sbv-excelsior", "DED"),
    "FC Groningen": ("te631", "fc-groningen", "DED"),
    "FC Twente": ("te1965", "fc-twente", "DED"),
    "FC Utrecht": ("te711", "fc-utrecht", "DED"),
    "FC Volendam": ("te719", "fc-volendam", "DED"),
    "Feyenoord": ("te736", "feyenoord", "DED"),
    "Fortuna Sittard": ("te828", "fortuna-sittard", "DED"),
    "Go Ahead Eagles": ("te899", "go-ahead-eagles", "DED"),
    "Heerenveen": ("te1644", "sc-heerenveen", "DED"),
    "Heracles Almelo": ("te971", "heracles-almelo", "DED"),
    "N.E.C.": ("te1347", "nec", "DED"),
    "NAC Breda": ("te1331", "nac-breda", "DED"),
    "PEC Zwolle": ("te729", "pec-zwolle", "DED"),
    "PSV Eindhoven": ("te1502", "psv-eindhoven", "DED"),
    "Sparta Rotterdam": ("te1762", "sparta-rotterdam", "DED"),
    "Telstar": ("te1831", "telstar", "DED"),
    # Eerste Divisie 2025-26
    "ADO Den Haag": ("te60", "ado-den-haag", "JE"),
    "Almere City FC": ("te681", "almere-city-fc", "JE"),
    "De Graafschap": ("te453", "de-graafschap", "JE"),
    "FC Den Bosch": ("te615", "fc-den-bosch", "JE"),
    "FC Dordrecht": ("te617", "fc-dordrecht", "JE"),
    "FC Eindhoven": ("te620", "fc-eindhoven", "JE"),
    "FC Emmen": ("te621", "fc-emmen", "JE"),
    "Helmond Sport": ("te969", "helmond-sport", "JE"),
    "MVV": ("te1327", "mvv", "JE"),
    "RKC Waalwijk": ("te1568", "rkc-waalwijk", "JE"),
    "Roda JC Kerkrade": ("te1574", "roda-jc-kerkrade", "JE"),
    "SC Cambuur": ("te315", "sc-cambuur", "JE"),
    "TOP Oss": ("te1914", "top-oss", "JE"),
    "VVV-Venlo": ("te2122", "vvv-venlo", "JE"),
    "Vitesse": ("te2108", "vitesse", "JE"),
    "Willem II": ("te2146", "willem-ii", "JE"),
    # Premier League 2025-26
    "Arsenal FC": ("te127", "arsenal-fc", "PL"),
    "Aston Villa": ("te151", "aston-villa", "PL"),
    "AFC Bournemouth": ("te65", "afc-bournemouth", "PL"),
    "Brentford FC": ("te274", "brentford-fc", "PL"),
    "Brighton & Hove Albion": ("te276", "brighton--hove-albion", "PL"),
    "Burnley FC": ("te290", "burnley-fc", "PL"),
    "Chelsea FC": ("te373", "chelsea-fc", "PL"),
    "Crystal Palace": ("te429", "crystal-palace", "PL"),
    "Everton FC": ("te573", "everton-fc", "PL"),
    "Fulham FC": ("te847", "fulham-fc", "PL"),
    "Leeds United": ("te1197", "leeds-united", "PL"),
    "Liverpool FC": ("te1226", "liverpool-fc", "PL"),
    "Manchester City": ("te1267", "manchester-city", "PL"),
    "Manchester United": ("te1268", "manchester-united", "PL"),
    "Newcastle United": ("te1355", "newcastle-united", "PL"),
    "Nottingham Forest": ("te1391", "nottingham-forest", "PL"),
    "Sunderland AFC": ("te1844", "sunderland-afc", "PL"),
    "Tottenham Hotspur": ("te1924", "tottenham-hotspur", "PL"),
    "West Ham United": ("te2137", "west-ham-united", "PL"),
    "Wolverhampton Wanderers": ("te2151", "wolverhampton-wanderers", "PL"),
    # Bundesliga 2025-26
    "1. FC Heidenheim 1846": ("te5", "1-fc-heidenheim-1846", "BL"),
    "1. FC Köln": ("te9", "1-fc-koeln", "BL"),
    "1. FC Union Berlin": ("te19", "1-fc-union-berlin", "BL"),
    "1. FSV Mainz 05": ("te21", "1-fsv-mainz-05", "BL"),
    "1899 Hoffenheim": ("te24", "1899-hoffenheim", "BL"),
    "Bayer Leverkusen": ("te205", "bayer-leverkusen", "BL"),
    "Bayern Munich": ("te209", "bayern-munich", "BL"),
    "Bor. Mönchengladbach": ("te253", "bor-moenchengladbach", "BL"),
    "Borussia Dortmund": ("te258", "borussia-dortmund", "BL"),
    "Eintracht Frankfurt": ("te530", "eintracht-frankfurt", "BL"),
    "FC Augsburg": ("te594", "fc-augsburg", "BL"),
    "FC St. Pauli": ("te702", "fc-st-pauli", "BL"),
    "Hamburger SV": ("te943", "hamburger-sv", "BL"),
    "RB Leipzig": ("te29680", "rb-leipzig", "BL"),
    "SC Freiburg": ("te1639", "sc-freiburg", "BL"),
    "VfB Stuttgart": ("te2076", "vfb-stuttgart", "BL"),
    "VfL Wolfsburg": ("te2086", "vfl-wolfsburg", "BL"),
    "Werder Bremen": ("te2134", "werder-bremen", "BL"),
    # La Liga 2025-26
    "Athletic Club": ("te156", "athletic-club", "LL"),
    "Atlético Madrid": ("te162", "atletico-madrid", "LL"),
    "CA Osasuna": ("te306", "ca-osasuna", "LL"),
    "CD Alavés": ("te327", "cd-alaves", "LL"),
    "Celta de Vigo": ("te355", "celta-de-vigo", "LL"),
    "Elche CF": ("te538", "elche-cf", "LL"),
    "FC Barcelona": ("te597", "fc-barcelona", "LL"),
    "Getafe CF": ("te880", "getafe-cf", "LL"),
    "Girona FC": ("te627", "girona-fc", "LL"),
    "Levante UD": ("te1207", "levante-ud", "LL"),
    "RCD Espanyol": ("te560", "rcd-espanyol", "LL"),
    "RCD Mallorca": ("te1541", "rcd-mallorca", "LL"),
    "Rayo Vallecano": ("te1535", "rayo-vallecano", "LL"),
    "Real Betis": ("te1543", "real-betis", "LL"),
    "Real Madrid": ("te1545", "real-madrid", "LL"),
    "Real Oviedo": ("te13858", "real-oviedo", "LL"),
    "Real Sociedad": ("te1550", "real-sociedad", "LL"),
    "Sevilla FC": ("te1681", "sevilla-fc", "LL"),
    "Valencia CF": ("te2041", "valencia-cf", "LL"),
    "Villarreal CF": ("te2102", "villarreal-cf", "LL"),
    # Serie A 2025-26
    "AC Milan": ("te43", "ac-milan", "SA"),
    "ACF Fiorentina": ("te48", "acf-fiorentina", "SA"),
    "AS Roma": ("te138", "as-roma", "SA"),
    "Atalanta": ("te155", "atalanta", "SA"),
    "Bologna FC": ("te249", "bologna-fc", "SA"),
    "Cagliari Calcio": ("te312", "cagliari-calcio", "SA"),
    "Como 1907": ("te17583", "como-1907", "SA"),
    "Genoa CFC": ("te626", "genoa-cfc", "SA"),
    "Hellas Verona": ("te17579", "hellas-verona", "SA"),
    "Inter": ("te1052", "inter", "SA"),
    "Juventus": ("te1094", "juventus", "SA"),
    "Lazio Roma": ("te1187", "lazio-roma", "SA"),
    "Parma Calcio 1913": ("te1458", "parma-calcio-1913", "SA"),
    "Pisa SC": ("te1472", "pisa-sc", "SA"),
    "SSC Napoli": ("te1794", "ssc-napoli", "SA"),
    "Sassuolo Calcio": ("te13744", "sassuolo-calcio", "SA"),
    "Torino FC": ("te1916", "torino-fc", "SA"),
    "US Cremonese": ("te13777", "us-cremonese", "SA"),
    "US Lecce": ("te2020", "us-lecce", "SA"),
    "Udinese Calcio": ("te1983", "udinese-calcio", "SA"),
    # Ligue 1 2025-26
    "AJ Auxerre": ("te75", "aj-auxerre", "L1"),
    "Angers SCO": ("te104", "angers-sco", "L1"),
    "AS Monaco": ("te136", "as-monaco", "L1"),
    "FC Lorient": ("te663", "fc-lorient", "L1"),
    "FC Metz": ("te673", "fc-metz", "L1"),
    "FC Nantes": ("te676", "fc-nantes", "L1"),
    "Havre AC": ("te1190", "havre-ac", "L1"),
    "Lille OSC": ("te1435", "lille-osc", "L1"),
    "OGC Nice": ("te1408", "ogc-nice", "L1"),
    "Olympique Lyonnais": ("te1420", "olympique-lyonnais", "L1"),
    "Olympique Marseille": ("te1421", "olympique-de-marseille", "L1"),
    "Paris FC": ("te1456", "paris-fc", "L1"),
    "Paris Saint-Germain": ("te1457", "paris-saint-germain", "L1"),
    "RC Lens": ("te1539", "rc-lens", "L1"),
    "RC Strasbourg": ("te1540", "rc-strasbourg", "L1"),
    "Stade Brestois 29": ("te1806", "stade-brestois-29", "L1"),
    "Stade Rennais": ("te1811", "stade-rennais", "L1"),
    "Toulouse FC": ("te1925", "toulouse-fc", "L1"),
}

# Alias table: maps any known variant name → canonical name
# Built from all names encountered across sources
ALIASES = {
    # Eredivisie
    "AFC Ajax": "Ajax",
    "Ajax Amsterdam": "Ajax",
    "AZ": "AZ Alkmaar",
    "SBV Excelsior": "Excelsior",
    "Excelsior Rotterdam": "Excelsior",
    "Groningen": "FC Groningen",
    "Twente": "FC Twente",
    "FC Twente '65": "FC Twente",
    "FC Twente Enschede": "FC Twente",
    "Utrecht": "FC Utrecht",
    "Volendam": "FC Volendam",
    "Feyenoord Rotterdam": "Feyenoord",
    "For Sittard": "Fortuna Sittard",
    "Sittard": "Fortuna Sittard",
    "sc Heerenveen": "Heerenveen",
    "SC Heerenveen": "Heerenveen",
    "Heracles": "Heracles Almelo",
    "NEC": "N.E.C.",
    "NEC Nijmegen": "N.E.C.",
    "Nijmegen": "N.E.C.",
    "NAC": "NAC Breda",
    "Zwolle": "PEC Zwolle",
    "PSV": "PSV Eindhoven",
    "Sp. Rotterdam": "Sparta Rotterdam",
    "Telstar 1963": "Telstar",
    "SC Telstar": "Telstar",
    # Eerste Divisie
    "Den Haag": "ADO Den Haag",
    "Almere City": "Almere City FC",
    "De Graafs.": "De Graafschap",
    "Den Bosch": "FC Den Bosch",
    "Dordrecht": "FC Dordrecht",
    "Eindhoven": "FC Eindhoven",
    "Emmen": "FC Emmen",
    "Waalwijk": "RKC Waalwijk",
    "RKC": "RKC Waalwijk",
    "Roda JC": "Roda JC Kerkrade",
    "Roda": "Roda JC Kerkrade",
    "Cambuur": "SC Cambuur",
    "SC Cambuur Leeuwarden": "SC Cambuur",
    "Cambuur Leeuwarden": "SC Cambuur",
    "VVV": "VVV-Venlo",
    "VVV Venlo": "VVV-Venlo",
    "SBV Vitesse": "Vitesse",
    "Willem II Tilburg": "Willem II",
    # football-data.org name variants
    "Le Havre AC": "Havre AC",
    "AC Pisa 1909": "Pisa SC",
    "Sassuolo": "Sassuolo Calcio",
    "HSV": "Hamburger SV",
    "Hamburg": "Hamburger SV",
    "SC Heerenveen": "Heerenveen",
    # Italian name variants (worldfootball.net short names)
    "Sassuolo": "Sassuolo Calcio",
    "Bologna": "Bologna FC",
    "Napoli": "SSC Napoli",
    "Lazio": "Lazio Roma",
    "Udinese": "Udinese Calcio",
    "Fiorentina": "ACF Fiorentina",
    "Roma": "AS Roma",
    "Lecce": "US Lecce",
    "Parma": "Parma Calcio 1913",
    "Cagliari": "Cagliari Calcio",
}


# External API IDs: canonical_name → {football_data_id, api_football_id}
# football-data.org IDs from their /competitions/{code}/teams endpoints
# API-Football IDs from api-sports.io (league 88=Eredivisie, 89=Eerste Divisie)
EXTERNAL_IDS = {
    # Eredivisie — football-data.org (DED) + API-Football (league 88)
    "Ajax": {"fd": 678, "af": 194},
    "AZ Alkmaar": {"fd": 682, "af": 201},
    "Excelsior": {"fd": 6806, "af": 212},
    "FC Groningen": {"fd": 677, "af": 204},
    "FC Twente": {"fd": 666, "af": 199},
    "FC Utrecht": {"fd": 676, "af": 200},
    "FC Volendam": {"fd": 1914, "af": 1910},
    "Feyenoord": {"fd": 675, "af": 198},
    "Fortuna Sittard": {"fd": 1920, "af": 205},
    "Go Ahead Eagles": {"fd": 718, "af": 1909},
    "Heerenveen": {"fd": 673, "af": 202},
    "Heracles Almelo": {"fd": 671, "af": 206},
    "N.E.C.": {"fd": 1919, "af": 208},
    "NAC Breda": {"fd": 1913, "af": 211},
    "PEC Zwolle": {"fd": 684, "af": 209},
    "PSV Eindhoven": {"fd": 674, "af": 197},
    "Sparta Rotterdam": {"fd": 668, "af": 203},
    "Telstar": {"fd": None, "af": 1912},
    # Eerste Divisie — API-Football only (league 89), no football-data.org
    "ADO Den Haag": {"fd": None, "af": 196},
    "Almere City FC": {"fd": None, "af": 1911},
    "De Graafschap": {"fd": None, "af": 419},
    "FC Den Bosch": {"fd": None, "af": 1908},
    "FC Dordrecht": {"fd": None, "af": 1907},
    "FC Eindhoven": {"fd": None, "af": 1906},
    "FC Emmen": {"fd": None, "af": 1916},
    "Helmond Sport": {"fd": None, "af": 1905},
    "MVV": {"fd": None, "af": 1904},
    "RKC Waalwijk": {"fd": None, "af": 207},
    "Roda JC Kerkrade": {"fd": None, "af": 417},
    "SC Cambuur": {"fd": None, "af": 1903},
    "TOP Oss": {"fd": None, "af": 1902},
    "VVV-Venlo": {"fd": None, "af": 418},
    "Vitesse": {"fd": None, "af": 195},
    "Willem II": {"fd": None, "af": 210},
    # Premier League — football-data.org (PL)
    "Arsenal FC": {"fd": 57, "af": 42},
    "Aston Villa": {"fd": 58, "af": 66},
    "AFC Bournemouth": {"fd": 1044, "af": 35},
    "Brentford FC": {"fd": 402, "af": 55},
    "Brighton & Hove Albion": {"fd": 397, "af": 51},
    "Burnley FC": {"fd": 328, "af": 44},
    "Chelsea FC": {"fd": 61, "af": 49},
    "Crystal Palace": {"fd": 354, "af": 52},
    "Everton FC": {"fd": 62, "af": 45},
    "Fulham FC": {"fd": 63, "af": 36},
    "Leeds United": {"fd": 341, "af": 63},
    "Liverpool FC": {"fd": 64, "af": 40},
    "Manchester City": {"fd": 65, "af": 50},
    "Manchester United": {"fd": 66, "af": 33},
    "Newcastle United": {"fd": 67, "af": 34},
    "Nottingham Forest": {"fd": 351, "af": 65},
    "Sunderland AFC": {"fd": 71, "af": 71},
    "Tottenham Hotspur": {"fd": 73, "af": 47},
    "West Ham United": {"fd": 563, "af": 48},
    "Wolverhampton Wanderers": {"fd": 76, "af": 39},
    # Bundesliga — football-data.org (BL1)
    "1. FC Heidenheim 1846": {"fd": 710, "af": 167},
    "1. FC Köln": {"fd": 1, "af": 192},
    "1. FC Union Berlin": {"fd": 7, "af": 182},
    "1. FSV Mainz 05": {"fd": 15, "af": 164},
    "1899 Hoffenheim": {"fd": 2, "af": 176},
    "Bayer Leverkusen": {"fd": 3, "af": 168},
    "Bayern Munich": {"fd": 5, "af": 157},
    "Bor. Mönchengladbach": {"fd": 18, "af": 163},
    "Borussia Dortmund": {"fd": 4, "af": 165},
    "Eintracht Frankfurt": {"fd": 19, "af": 169},
    "FC Augsburg": {"fd": 16, "af": 170},
    "FC St. Pauli": {"fd": 20, "af": 186},
    "Hamburger SV": {"fd": 9, "af": 180},
    "RB Leipzig": {"fd": 721, "af": 173},
    "SC Freiburg": {"fd": 17, "af": 160},
    "VfB Stuttgart": {"fd": 10, "af": 172},
    "VfL Wolfsburg": {"fd": 11, "af": 161},
    "Werder Bremen": {"fd": 12, "af": 134},
    # La Liga — football-data.org (PD)
    "Athletic Club": {"fd": 77, "af": 531},
    "Atlético Madrid": {"fd": 78, "af": 530},
    "CA Osasuna": {"fd": 79, "af": 727},
    "CD Alavés": {"fd": 263, "af": 542},
    "Celta de Vigo": {"fd": 558, "af": 538},
    "Elche CF": {"fd": 285, "af": 797},
    "FC Barcelona": {"fd": 81, "af": 529},
    "Getafe CF": {"fd": 82, "af": 546},
    "Girona FC": {"fd": 298, "af": 547},
    "Levante UD": {"fd": 88, "af": 539},
    "RCD Espanyol": {"fd": 80, "af": 540},
    "RCD Mallorca": {"fd": 89, "af": 798},
    "Rayo Vallecano": {"fd": 87, "af": 728},
    "Real Betis": {"fd": 90, "af": 543},
    "Real Madrid": {"fd": 86, "af": 541},
    "Real Oviedo": {"fd": 278, "af": 724},
    "Real Sociedad": {"fd": 92, "af": 548},
    "Sevilla FC": {"fd": 559, "af": 536},
    "Valencia CF": {"fd": 95, "af": 532},
    "Villarreal CF": {"fd": 94, "af": 533},
    # Serie A — football-data.org (SA)
    "AC Milan": {"fd": 98, "af": 489},
    "ACF Fiorentina": {"fd": 99, "af": 502},
    "AS Roma": {"fd": 100, "af": 497},
    "Atalanta": {"fd": 102, "af": 499},
    "Bologna FC": {"fd": 103, "af": 500},
    "Cagliari Calcio": {"fd": 104, "af": 490},
    "Como 1907": {"fd": 5890, "af": 895},
    "Genoa CFC": {"fd": 107, "af": 495},
    "Hellas Verona": {"fd": 450, "af": 504},
    "Inter": {"fd": 108, "af": 505},
    "Juventus": {"fd": 109, "af": 496},
    "Lazio Roma": {"fd": 110, "af": 487},
    "Parma Calcio 1913": {"fd": 112, "af": 511},
    "Pisa SC": {"fd": 5911, "af": 514},
    "SSC Napoli": {"fd": 113, "af": 492},
    "Sassuolo Calcio": {"fd": 471, "af": 488},
    "Torino FC": {"fd": 586, "af": 503},
    "US Cremonese": {"fd": 5765, "af": 512},
    "US Lecce": {"fd": 5879, "af": 867},
    "Udinese Calcio": {"fd": 115, "af": 494},
    # Ligue 1 — football-data.org (FL1)
    "AJ Auxerre": {"fd": 519, "af": 99},
    "Angers SCO": {"fd": 532, "af": 90},
    "AS Monaco": {"fd": 548, "af": 91},
    "FC Lorient": {"fd": 536, "af": 97},
    "FC Metz": {"fd": 545, "af": 112},
    "FC Nantes": {"fd": 543, "af": 83},
    "Havre AC": {"fd": 547, "af": 94},
    "Lille OSC": {"fd": 521, "af": 79},
    "OGC Nice": {"fd": 522, "af": 84},
    "Olympique Lyonnais": {"fd": 523, "af": 80},
    "Olympique Marseille": {"fd": 516, "af": 81},
    "Paris FC": {"fd": 1045, "af": 105},
    "Paris Saint-Germain": {"fd": 524, "af": 85},
    "RC Lens": {"fd": 546, "af": 116},
    "RC Strasbourg": {"fd": 576, "af": 95},
    "Stade Brestois 29": {"fd": 512, "af": 106},
    "Stade Rennais": {"fd": 529, "af": 101},
    "Toulouse FC": {"fd": 511, "af": 96},
}


def init_teams(conn):
    """Create all canonical teams in the database with external IDs."""
    for name, (wf_id, slug, league) in TEAMS.items():
        ext = EXTERNAL_IDS.get(name, {})
        kwargs = {
            "name": name,
            "wf_slug": slug,
            "wf_id": wf_id,
            "current_league": league,
        }
        if ext.get("fd"):
            kwargs["football_data_id"] = ext["fd"]
        if ext.get("af"):
            kwargs["api_football_id"] = ext["af"]
        # Determine country from league
        league_countries = {
            "DED": "NL", "JE": "NL", "PL": "EN", "BL": "DE",
            "LL": "ES", "SA": "IT", "L1": "FR",
        }
        kwargs["country"] = league_countries.get(league, "NL")

        team = find_team_by_name(conn, name)
        if not team:
            upsert_team(conn, **kwargs)
        else:
            # Update existing team with any new fields
            updates = []
            values = []
            for key in ("current_league", "wf_id", "wf_slug", "football_data_id", "api_football_id"):
                if key in kwargs and kwargs[key] is not None:
                    updates.append(f"{key} = ?")
                    values.append(kwargs[key])
            if updates:
                values.append(team["id"])
                conn.execute(
                    f"UPDATE teams SET {', '.join(updates)} WHERE id = ?", values
                )
    conn.commit()


def resolve_team_name(name: str) -> str:
    """Resolve any team name variant to its canonical form."""
    if name in TEAMS:
        return name
    return ALIASES.get(name, name)


def resolve_team_id(conn, name: str) -> int:
    """Resolve a team name to its database ID, creating if needed."""
    canonical = resolve_team_name(name)
    team = find_team_by_name(conn, canonical)
    if team:
        return team["id"]
    # Try original name
    if canonical != name:
        team = find_team_by_name(conn, name)
        if team:
            return team["id"]
    # Create (probably a foreign opponent in European competition)
    return upsert_team(conn, name=canonical, country="NL")
