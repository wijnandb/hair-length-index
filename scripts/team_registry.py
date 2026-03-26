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
}


def init_teams(conn):
    """Create all canonical teams in the database."""
    for name, (wf_id, slug, league) in TEAMS.items():
        team = find_team_by_name(conn, name)
        if not team:
            upsert_team(conn, name=name, country="NL", current_league=league)
        else:
            conn.execute("UPDATE teams SET current_league = ? WHERE id = ?",
                        (league, team["id"]))
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
