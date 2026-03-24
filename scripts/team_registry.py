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
