"""Central team registry with canonical names and aliases.

The single source of truth for team identity. All importers use this
to resolve opponent names to canonical team IDs.
"""

from scripts.db import find_team_by_name, upsert_team

# Canonical teams from worldfootball.net competition standings pages.
# Format: canonical_name → (wf_id, slug, current_league, api_football_id)
# api_football_id is optional (None if unknown).
TEAMS = {
    # Eredivisie 2025-26
    "Ajax": ("te64", "afc-ajax", "DED", 194),
    "AZ Alkmaar": ("te181", "az-alkmaar", "DED", 201),
    "Excelsior": ("te577", "sbv-excelsior", "DED", 1908),
    "FC Groningen": ("te631", "fc-groningen", "DED", 204),
    "FC Twente": ("te1965", "fc-twente", "DED", 199),
    "FC Utrecht": ("te711", "fc-utrecht", "DED", 200),
    "FC Volendam": ("te719", "fc-volendam", "DED", 1910),
    "Feyenoord": ("te736", "feyenoord", "DED", 198),
    "Fortuna Sittard": ("te828", "fortuna-sittard", "DED", 205),
    "Go Ahead Eagles": ("te899", "go-ahead-eagles", "DED", 1909),
    "Heerenveen": ("te1644", "sc-heerenveen", "DED", 202),
    "Heracles Almelo": ("te971", "heracles-almelo", "DED", 206),
    "N.E.C.": ("te1347", "nec", "DED", 208),
    "NAC Breda": ("te1331", "nac-breda", "DED", 211),
    "PEC Zwolle": ("te729", "pec-zwolle", "DED", 209),
    "PSV Eindhoven": ("te1502", "psv-eindhoven", "DED", 197),
    "Sparta Rotterdam": ("te1762", "sparta-rotterdam", "DED", 203),
    "Telstar": ("te1831", "telstar", "DED", 1915),
    # Eerste Divisie 2025-26
    "ADO Den Haag": ("te60", "ado-den-haag", "JE", 1912),
    "Almere City FC": ("te681", "almere-city-fc", "JE", 1911),
    "De Graafschap": ("te453", "de-graafschap", "JE", 1914),
    "FC Den Bosch": ("te615", "fc-den-bosch", "JE", 1920),
    "FC Dordrecht": ("te617", "fc-dordrecht", "JE", 1921),
    "FC Eindhoven": ("te620", "fc-eindhoven", "JE", 1922),
    "FC Emmen": ("te621", "fc-emmen", "JE", 1916),
    "Helmond Sport": ("te969", "helmond-sport", "JE", 1923),
    "MVV": ("te1327", "mvv", "JE", 1924),
    "RKC Waalwijk": ("te1568", "rkc-waalwijk", "JE", 207),
    "Roda JC Kerkrade": ("te1574", "roda-jc-kerkrade", "JE", 1917),
    "SC Cambuur": ("te315", "sc-cambuur", "JE", 1913),
    "TOP Oss": ("te1914", "top-oss", "JE", 1925),
    "VVV-Venlo": ("te2122", "vvv-venlo", "JE", 1918),
    "Vitesse": ("te2108", "vitesse", "JE", 1919),
    "Willem II": ("te2146", "willem-ii", "JE", 210),
    # Premier League 2025-26
    "Arsenal FC": ("te127", "arsenal-fc", "PL", None),
    "Aston Villa": ("te151", "aston-villa", "PL", None),
    "AFC Bournemouth": ("te65", "afc-bournemouth", "PL", None),
    "Brentford FC": ("te274", "brentford-fc", "PL", None),
    "Brighton & Hove Albion": ("te276", "brighton--hove-albion", "PL", None),
    "Burnley FC": ("te290", "burnley-fc", "PL", None),
    "Chelsea FC": ("te373", "chelsea-fc", "PL", None),
    "Crystal Palace": ("te429", "crystal-palace", "PL", None),
    "Everton FC": ("te573", "everton-fc", "PL", None),
    "Fulham FC": ("te847", "fulham-fc", "PL", None),
    "Leeds United": ("te1197", "leeds-united", "PL", None),
    "Liverpool FC": ("te1226", "liverpool-fc", "PL", None),
    "Manchester City": ("te1267", "manchester-city", "PL", None),
    "Manchester United": ("te1268", "manchester-united", "PL", None),
    "Newcastle United": ("te1355", "newcastle-united", "PL", None),
    "Nottingham Forest": ("te1391", "nottingham-forest", "PL", None),
    "Sunderland AFC": ("te1844", "sunderland-afc", "PL", None),
    "Tottenham Hotspur": ("te1924", "tottenham-hotspur", "PL", None),
    "West Ham United": ("te2137", "west-ham-united", "PL", None),
    "Wolverhampton Wanderers": ("te2151", "wolverhampton-wanderers", "PL", None),
    # Bundesliga 2025-26
    "1. FC Heidenheim 1846": ("te5", "1-fc-heidenheim-1846", "BL", None),
    "1. FC Köln": ("te9", "1-fc-koeln", "BL", None),
    "1. FC Union Berlin": ("te19", "1-fc-union-berlin", "BL", None),
    "1. FSV Mainz 05": ("te21", "1-fsv-mainz-05", "BL", None),
    "1899 Hoffenheim": ("te24", "1899-hoffenheim", "BL", None),
    "Bayer Leverkusen": ("te205", "bayer-leverkusen", "BL", None),
    "Bayern Munich": ("te209", "bayern-munich", "BL", None),
    "Bor. Mönchengladbach": ("te253", "bor-moenchengladbach", "BL", None),
    "Borussia Dortmund": ("te258", "borussia-dortmund", "BL", None),
    "Eintracht Frankfurt": ("te530", "eintracht-frankfurt", "BL", None),
    "FC Augsburg": ("te594", "fc-augsburg", "BL", None),
    "FC St. Pauli": ("te702", "fc-st-pauli", "BL", None),
    "Hamburger SV": ("te943", "hamburger-sv", "BL", None),
    "RB Leipzig": ("te29680", "rb-leipzig", "BL", None),
    "SC Freiburg": ("te1639", "sc-freiburg", "BL", None),
    "VfB Stuttgart": ("te2076", "vfb-stuttgart", "BL", None),
    "VfL Wolfsburg": ("te2086", "vfl-wolfsburg", "BL", None),
    "Werder Bremen": ("te2134", "werder-bremen", "BL", None),
    # La Liga 2025-26
    "Athletic Club": ("te156", "athletic-club", "LL", None),
    "Atlético Madrid": ("te162", "atletico-madrid", "LL", None),
    "CA Osasuna": ("te306", "ca-osasuna", "LL", None),
    "CD Alavés": ("te327", "cd-alaves", "LL", None),
    "Celta de Vigo": ("te355", "celta-de-vigo", "LL", None),
    "Elche CF": ("te538", "elche-cf", "LL", None),
    "FC Barcelona": ("te597", "fc-barcelona", "LL", None),
    "Getafe CF": ("te880", "getafe-cf", "LL", None),
    "Girona FC": ("te627", "girona-fc", "LL", None),
    "Levante UD": ("te1207", "levante-ud", "LL", None),
    "RCD Espanyol": ("te560", "rcd-espanyol", "LL", None),
    "RCD Mallorca": ("te1541", "rcd-mallorca", "LL", None),
    "Rayo Vallecano": ("te1535", "rayo-vallecano", "LL", None),
    "Real Betis": ("te1543", "real-betis", "LL", None),
    "Real Madrid": ("te1545", "real-madrid", "LL", None),
    "Real Oviedo": ("te13858", "real-oviedo", "LL", None),
    "Real Sociedad": ("te1550", "real-sociedad", "LL", None),
    "Sevilla FC": ("te1681", "sevilla-fc", "LL", None),
    "Valencia CF": ("te2041", "valencia-cf", "LL", None),
    "Villarreal CF": ("te2102", "villarreal-cf", "LL", None),
    # Serie A 2025-26
    "AC Milan": ("te43", "ac-milan", "SA", None),
    "ACF Fiorentina": ("te48", "acf-fiorentina", "SA", None),
    "AS Roma": ("te138", "as-roma", "SA", None),
    "Atalanta": ("te155", "atalanta", "SA", None),
    "Bologna FC": ("te249", "bologna-fc", "SA", None),
    "Cagliari Calcio": ("te312", "cagliari-calcio", "SA", None),
    "Como 1907": ("te17583", "como-1907", "SA", None),
    "Genoa CFC": ("te626", "genoa-cfc", "SA", None),
    "Hellas Verona": ("te17579", "hellas-verona", "SA", None),
    "Inter": ("te1052", "inter", "SA", None),
    "Juventus": ("te1094", "juventus", "SA", None),
    "Lazio Roma": ("te1187", "lazio-roma", "SA", None),
    "Parma Calcio 1913": ("te1458", "parma-calcio-1913", "SA", None),
    "Pisa SC": ("te1472", "pisa-sc", "SA", None),
    "SSC Napoli": ("te1794", "ssc-napoli", "SA", None),
    "Sassuolo Calcio": ("te13744", "sassuolo-calcio", "SA", None),
    "Torino FC": ("te1916", "torino-fc", "SA", None),
    "US Cremonese": ("te13777", "us-cremonese", "SA", None),
    "US Lecce": ("te2020", "us-lecce", "SA", None),
    "Udinese Calcio": ("te1983", "udinese-calcio", "SA", None),
    # Ligue 1 2025-26
    "AJ Auxerre": ("te75", "aj-auxerre", "L1", None),
    "Angers SCO": ("te104", "angers-sco", "L1", None),
    "AS Monaco": ("te136", "as-monaco", "L1", None),
    "FC Lorient": ("te663", "fc-lorient", "L1", None),
    "FC Metz": ("te673", "fc-metz", "L1", None),
    "FC Nantes": ("te676", "fc-nantes", "L1", None),
    "Havre AC": ("te1190", "havre-ac", "L1", None),
    "Lille OSC": ("te1435", "lille-osc", "L1", None),
    "OGC Nice": ("te1408", "ogc-nice", "L1", None),
    "Olympique Lyonnais": ("te1420", "olympique-lyonnais", "L1", None),
    "Olympique Marseille": ("te1421", "olympique-de-marseille", "L1", None),
    "Paris FC": ("te1456", "paris-fc", "L1", None),
    "Paris Saint-Germain": ("te1457", "paris-saint-germain", "L1", None),
    "RC Lens": ("te1539", "rc-lens", "L1", None),
    "RC Strasbourg": ("te1540", "rc-strasbourg", "L1", None),
    "Stade Brestois 29": ("te1806", "stade-brestois-29", "L1", None),
    "Stade Rennais": ("te1811", "stade-rennais", "L1", None),
    "Toulouse FC": ("te1925", "toulouse-fc", "L1", None),
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
    """Create all canonical teams in the database with all known IDs."""
    for name, (wf_id, slug, league, af_id) in TEAMS.items():
        kwargs = dict(
            worldfootball_id=wf_id,
            name=name,
            current_league=league,
        )
        if af_id is not None:
            kwargs["api_football_id"] = af_id
        upsert_team(conn, **kwargs)
    conn.commit()


def resolve_team_name(name: str) -> str:
    """Resolve any team name variant to its canonical form."""
    if name in TEAMS:
        return name
    return ALIASES.get(name, name)


def resolve_team_id(conn, name: str) -> int:
    """Resolve a team name to its database ID, creating if needed.

    Lookup order: worldfootball_id → canonical name → original name → create.
    """
    canonical = resolve_team_name(name)

    # If team is in the registry, look up by worldfootball_id first
    if canonical in TEAMS:
        wf_id, slug, league, af_id = TEAMS[canonical]
        row = conn.execute(
            "SELECT id FROM teams WHERE worldfootball_id = ?", (wf_id,)
        ).fetchone()
        if row:
            return row["id"]

    # Fall back to name lookup
    team = find_team_by_name(conn, canonical)
    if team:
        return team["id"]
    if canonical != name:
        team = find_team_by_name(conn, name)
        if team:
            return team["id"]

    # Create — include all known IDs
    kwargs = {"name": canonical}
    if canonical in TEAMS:
        wf_id, slug, league, af_id = TEAMS[canonical]
        kwargs["worldfootball_id"] = wf_id
        kwargs["current_league"] = league
        if af_id is not None:
            kwargs["api_football_id"] = af_id
    return upsert_team(conn, **kwargs)
