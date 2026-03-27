"""Central fan culture database.

Rivalries, insider hashtags, club birthdays, and match-specific tags.
Used by all social content generators and the bsky CLI.
"""

from datetime import date

# ============================================================
# RIVALRIES
# ============================================================

RIVALRIES = [
    # Eredivisie
    {"teams": ("Ajax", "Feyenoord"), "name": "De Klassieker", "hashtags": ["#klassieker", "#ajafey"]},
    {"teams": ("Ajax", "PSV Eindhoven"), "name": "De Topper", "hashtags": ["#topper"]},
    {"teams": ("PSV Eindhoven", "Feyenoord"), "name": "PSV-Feyenoord", "hashtags": []},
    {"teams": ("Feyenoord", "Sparta Rotterdam"), "name": "Rotterdamse Derby", "hashtags": ["#rotterdamsederby"]},
    {"teams": ("Feyenoord", "Excelsior"), "name": "Rotterdamse Derby", "hashtags": ["#rotterdamsederby"]},
    {"teams": ("N.E.C.", "Vitesse"), "name": "Gelderse Derby", "hashtags": ["#geldsederby"]},
    {"teams": ("FC Twente", "Heracles Almelo"), "name": "Twentse Derby", "hashtags": ["#twentsederby"]},
    {"teams": ("Go Ahead Eagles", "PEC Zwolle"), "name": "IJsselderby", "hashtags": ["#ijsselderby"]},
    {"teams": ("Willem II", "NAC Breda"), "name": "Brabantse Derby", "hashtags": ["#brabantsederby"]},
    {"teams": ("FC Groningen", "Heerenveen"), "name": "Derby van het Noorden", "hashtags": ["#derbyvanhetnoorden"]},
    # Premier League
    {"teams": ("Liverpool FC", "Manchester United"), "name": "Northwest Derby", "hashtags": ["#nwderby", "#livmun"]},
    {"teams": ("Arsenal FC", "Tottenham Hotspur"), "name": "North London Derby", "hashtags": ["#nld", "#northlondonderby"]},
    {"teams": ("Liverpool FC", "Everton FC"), "name": "Merseyside Derby", "hashtags": ["#merseysidederby"]},
    {"teams": ("Manchester United", "Manchester City"), "name": "Manchester Derby", "hashtags": ["#manchesterderby"]},
    {"teams": ("Chelsea FC", "Tottenham Hotspur"), "name": "London Derby", "hashtags": []},
    {"teams": ("Newcastle United", "Sunderland AFC"), "name": "Tyne-Wear Derby", "hashtags": ["#tynewearderby"]},
    # Bundesliga
    {"teams": ("Borussia Dortmund", "Bayern Munich"), "name": "Der Klassiker", "hashtags": ["#derklassiker"]},
    {"teams": ("Borussia Dortmund", "1. FC Köln"), "name": "Rhein-Ruhr Derby", "hashtags": []},
    {"teams": ("1. FC Köln", "Bor. Mönchengladbach"), "name": "Rheinderby", "hashtags": ["#rheinderby"]},
    {"teams": ("Hamburger SV", "Werder Bremen"), "name": "Nordderby", "hashtags": ["#nordderby"]},
    # La Liga
    {"teams": ("FC Barcelona", "Real Madrid"), "name": "El Clásico", "hashtags": ["#elclasico"]},
    {"teams": ("Atlético Madrid", "Real Madrid"), "name": "Derbi Madrileño", "hashtags": ["#derbimadrileno"]},
    {"teams": ("Athletic Club", "Real Sociedad"), "name": "Derbi Vasco", "hashtags": ["#derbivasco"]},
    {"teams": ("FC Barcelona", "RCD Espanyol"), "name": "Derbi Barceloní", "hashtags": ["#derbibarceloni"]},
    {"teams": ("Sevilla FC", "Real Betis"), "name": "Derbi Sevillano", "hashtags": ["#derbisevillano"]},
    # Serie A
    {"teams": ("Inter", "AC Milan"), "name": "Derby della Madonnina", "hashtags": ["#derbymilano"]},
    {"teams": ("AS Roma", "Lazio Roma"), "name": "Derby della Capitale", "hashtags": ["#derbycapitale"]},
    {"teams": ("Juventus", "Inter"), "name": "Derby d'Italia", "hashtags": ["#derbyditalia"]},
    {"teams": ("Juventus", "Torino FC"), "name": "Derby della Mole", "hashtags": ["#derbymole"]},
    {"teams": ("Genoa CFC", "Sampdoria"), "name": "Derby della Lanterna", "hashtags": []},
    # Ligue 1
    {"teams": ("Paris Saint-Germain", "Olympique Marseille"), "name": "Le Classique", "hashtags": ["#leclassique"]},
    {"teams": ("Olympique Lyonnais", "AS Monaco"), "name": "Choc des Olympiques", "hashtags": []},
    {"teams": ("Olympique Lyonnais", "Stade Rennais"), "name": "Derby", "hashtags": []},
]

# ============================================================
# CLUB HASHTAGS (insider tags fans actually use)
# ============================================================

CLUB_HASHTAGS = {
    # Eredivisie
    "Ajax": ["#wijzijnajax", "#ajax"],
    "Feyenoord": ["#hetlegioen", "#feyenoord"],
    "PSV Eindhoven": ["#psv", "#psveindhoven"],
    "AZ Alkmaar": ["#azalkmaar", "#az"],
    "FC Twente": ["#fctwente", "#twente"],
    "FC Utrecht": ["#fcutrecht"],
    "Heerenveen": ["#senteravee", "#heerenveen"],
    "Go Ahead Eagles": ["#kowet", "#goaheadeagles"],
    "N.E.C.": ["#eniesee", "#nec"],
    "Heracles Almelo": ["#heracles"],
    "Sparta Rotterdam": ["#spartarotterdam", "#sparta"],
    "NAC Breda": ["#nacbreda", "#nac"],
    "PEC Zwolle": ["#peczwolle"],
    "FC Groningen": ["#fcgroningen"],
    "Fortuna Sittard": ["#fortunasittard"],
    "FC Volendam": ["#fcvolendam"],
    "Telstar": ["#telstar"],
    "Excelsior": ["#excelsior"],
    # Eerste Divisie
    "Vitesse": ["#vitesse"],
    "Willem II": ["#willemii"],
    "RKC Waalwijk": ["#rkc"],
    "Almere City FC": ["#almerecity"],
    "ADO Den Haag": ["#adodenhaag", "#ado"],
    # Premier League
    "Arsenal FC": ["#gunners", "#afc", "#arsenal"],
    "Liverpool FC": ["#lfc", "#ynwa", "#liverpool"],
    "Manchester United": ["#mufc", "#redevils"],
    "Manchester City": ["#mancity", "#cityzens"],
    "Chelsea FC": ["#cfc", "#chelsea"],
    "Tottenham Hotspur": ["#thfc", "#spurs", "#coys"],
    "Newcastle United": ["#nufc", "#magpies"],
    "West Ham United": ["#whufc", "#irons"],
    "Everton FC": ["#efc", "#toffees"],
    "Aston Villa": ["#avfc", "#utv"],
    "Brighton & Hove Albion": ["#bhafc", "#seagulls"],
    "Nottingham Forest": ["#nffc", "#forest"],
    "Crystal Palace": ["#cpfc", "#eagles"],
    "Fulham FC": ["#ffc", "#fulham"],
    "Brentford FC": ["#brentford", "#bees"],
    "Wolverhampton Wanderers": ["#wwfc", "#wolves"],
    "AFC Bournemouth": ["#afcb", "#bournemouth"],
    "Leeds United": ["#lufc", "#leeds", "#mot"],
    "Burnley FC": ["#burnley", "#clarets"],
    "Sunderland AFC": ["#safc", "#sunderland"],
    # Bundesliga
    "Bayern Munich": ["#fcbayern", "#miasanmia"],
    "Borussia Dortmund": ["#bvb", "#echteliebe"],
    "Bayer Leverkusen": ["#b04", "#werkself"],
    "RB Leipzig": ["#rbleipzig", "#dierotenbullen"],
    "Eintracht Frankfurt": ["#sge", "#eintracht"],
    "VfB Stuttgart": ["#vfb", "#stuttgart"],
    "SC Freiburg": ["#scf", "#freiburg"],
    "VfL Wolfsburg": ["#vfl", "#wolfsburg"],
    "1. FC Union Berlin": ["#fcunion", "#eisern"],
    "Werder Bremen": ["#werder", "#svw"],
    "1. FC Köln": ["#effzeh", "#koeln"],
    "Bor. Mönchengladbach": ["#bmg", "#fohlenelf"],
    # La Liga
    "Real Madrid": ["#halamadrid", "#realmadrid"],
    "FC Barcelona": ["#fcblive", "#barca", "#visca"],
    "Atlético Madrid": ["#atletico", "#aupaatleti"],
    "Athletic Club": ["#athleticclub", "#aurreraathletic"],
    "Real Sociedad": ["#realsociedad", "#aurrera"],
    "Sevilla FC": ["#sevillafc", "#vamosmisevilla"],
    "Villarreal CF": ["#villarreal", "#submarino"],
    "Real Betis": ["#realbetis", "#vivobetis"],
    # Serie A
    "Juventus": ["#juventus", "#finoallafine"],
    "Inter": ["#inter", "#forzainter", "#amala"],
    "AC Milan": ["#acmilan", "#sempremilan"],
    "SSC Napoli": ["#napoli", "#forzanapolisempre"],
    "AS Roma": ["#asroma", "#forzaroma"],
    "Lazio Roma": ["#lazio", "#forzalazio"],
    "Atalanta": ["#atalanta", "#goanta"],
    "ACF Fiorentina": ["#fiorentina", "#forzaviola"],
    # Ligue 1
    "Paris Saint-Germain": ["#psg", "#icicestparis"],
    "Olympique Marseille": ["#om", "#teamom"],
    "Olympique Lyonnais": ["#ol", "#teamol"],
    "AS Monaco": ["#asmonaco", "#daghe"],
    "Lille OSC": ["#losc", "#lille"],
    "Stade Rennais": ["#srfc", "#rennes"],
}

# ============================================================
# CLUB BIRTHDAYS (founding dates)
# ============================================================

CLUB_BIRTHDAYS = {
    # Eredivisie (month, day) → team name
    (3, 18): "Ajax",          # 18 March 1900
    (4, 1): "Sparta Rotterdam",  # 1 April 1888
    (5, 14): "Vitesse",       # 14 May 1892
    (11, 15): "N.E.C.",       # 15 November 1900
    (7, 23): "Excelsior",     # 23 July 1902
    (5, 3): "Heracles Almelo", # 3 May 1903
    (9, 19): "NAC Breda",     # 19 September 1912
    (7, 20): "Heerenveen",    # 20 July 1920
    (6, 1): "FC Volendam",    # 1 June 1920
    (7, 17): "Telstar",       # 17 July 1963
    (5, 10): "AZ Alkmaar",    # 10 May 1967
    (7, 1): "Fortuna Sittard", # 1 July 1968
    (6, 16): "FC Groningen",  # 16 June 1971
    # Premier League
    (10, 26): "Liverpool FC",  # 1892
    (12, 21): "Arsenal FC",    # 1886
    (3, 5): "Tottenham Hotspur", # 1882
    (3, 10): "Chelsea FC",    # 1905
    (4, 16): "Manchester City", # 1880
    (1, 9): "Manchester United", # 1878 (Newton Heath)
    (12, 9): "Newcastle United", # 1892
    (3, 29): "Everton FC",    # 1878
    # Bundesliga
    (2, 27): "Bayern Munich",  # 1900
    (12, 19): "Borussia Dortmund", # 1909
    (7, 1): "Bayer Leverkusen", # 1904 (shared with Fortuna)
    # La Liga
    (3, 6): "Real Madrid",    # 1902
    (11, 29): "FC Barcelona", # 1899
    (4, 26): "Atlético Madrid", # 1903
    # Serie A
    (3, 9): "Inter",          # 1908
    (12, 16): "AC Milan",     # 1899
    (11, 1): "Juventus",      # 1897
    (8, 1): "SSC Napoli",     # 1926
    (6, 7): "AS Roma",        # 1927
    (1, 9): "Lazio Roma",     # 1900 (shared with Man Utd)
    # Ligue 1
    (8, 12): "Paris Saint-Germain", # 1970
    (8, 31): "Olympique Marseille", # 1899
}

# ============================================================
# LEAGUE HASHTAGS
# ============================================================

LEAGUE_HASHTAGS = {
    "DED": ["#eredivisie", "#voetbal"],
    "JE": ["#eerstdivisie", "#voetbal"],
    "PL": ["#premierleague", "#epl"],
    "BL": ["#bundesliga"],
    "LL": ["#laliga"],
    "SA": ["#seriea", "#serieA"],
    "L1": ["#ligue1"],
}

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_hashtags(team: str, opponent: str | None = None, league: str | None = None) -> str:
    """Get relevant hashtags for a post about a team."""
    tags = ["#HairLengthIndex"]

    # Club-specific tags
    if team in CLUB_HASHTAGS:
        tags.extend(CLUB_HASHTAGS[team][:2])  # max 2 insider tags

    # League tags
    if league and league in LEAGUE_HASHTAGS:
        tags.extend(LEAGUE_HASHTAGS[league][:1])

    # Match/rivalry tags
    if opponent:
        rivalry = get_rivalry(team, opponent)
        if rivalry:
            tags.extend(rivalry.get("hashtags", []))

    return " ".join(tags)


def get_rivalry(team1: str, team2: str) -> dict | None:
    """Check if two teams have a known rivalry. Returns rivalry dict or None."""
    for r in RIVALRIES:
        t = r["teams"]
        if (team1 in t[0] or t[0] in team1) and (team2 in t[1] or t[1] in team2):
            return r
        if (team2 in t[0] or t[0] in team2) and (team1 in t[1] or t[1] in team1):
            return r
    return None


def get_birthday_teams(today: date | None = None) -> list[str]:
    """Get teams with a birthday today."""
    if today is None:
        today = date.today()
    key = (today.month, today.day)
    teams = []
    for (m, d), team in CLUB_BIRTHDAYS.items():
        if m == key[0] and d == key[1]:
            teams.append(team)
    return teams


def get_milestone(days: int) -> int | None:
    """Check if days_since hits a milestone. Returns the milestone or None."""
    MILESTONES = [100, 200, 365, 500, 730, 1000, 1500, 2000, 2500, 3000, 3650, 4000, 5000, 5475]
    # Also check round years
    for m in MILESTONES:
        if days == m:
            return m
    return None


def days_to_human(days: int) -> str:
    """Convert days to human-readable string."""
    years = days // 365
    months = (days % 365) // 30
    if years >= 1:
        if months > 0:
            return f"{years} jaar en {months} maanden" if years < 5 else f"{years} jaar"
        return f"{years} jaar"
    if months > 0:
        return f"{months} maanden"
    return f"{days} dagen"
