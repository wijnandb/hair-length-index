"""Template-based social media post text generator.

Generates engaging, taunting-but-friendly text for each content type.
Multiple templates per type for variety. Dutch for NL leagues, English for rest.

Usage:
    from scripts.generate_post_text import generate_text
    text = generate_text(queue_item)
"""

import random

URL = "wijnandb.github.io/hair-length-index/"

# === BARBER ALERT ===
BARBER_ALERT_NL = [
    "KNIPBEURT! ✂️ {team} heeft eindelijk 5 op rij gewonnen!\n\n{days_waited} dagen wachten is voorbij. {streak_length} wedstrijden achter elkaar winnen.\n\nDe schaar is erin gezet.\n\n{url}\n\n#HairLengthIndex #{league_tag}",
    "De kapper is blij: {team} komt langs! 💇\n\nNa {days_waited} dagen zonder 5 op rij is het eindelijk zover.\n\nWie is de volgende?\n{url}\n\n#HairLengthIndex #{league_tag}",
    "🎉 {team}! Na {days_waited} dagen eindelijk weer 5 op rij.\n\nDat was even wachten.\n\n{url}\n\n#HairLengthIndex #{league_tag}",
]

BARBER_ALERT_EN = [
    "HAIRCUT! ✂️ {team} finally won 5 in a row!\n\n{days_waited} days of waiting. The barber is happy.\n\n{url}\n\n#HairLengthIndex #{league_tag}",
    "🎉 {team} got a haircut!\n\nAfter {days_waited} days, they finally won {streak_length} in a row.\n\nWho's next?\n{url}\n\n#HairLengthIndex #{league_tag}",
]

# === BIJNA BIJ DE KAPPER ===
BIJNA_NL = [
    "👀 {team} is al {wins} wedstrijden op rij aan het winnen...\n\nNog {remaining} te gaan voor een kappersbezoek!\nAl {days_since} dagen lang haar.\n\n{url}\n\n#HairLengthIndex #BijnaBijDeKapper",
    "Durven jullie het al te dromen, {team}-fans?\n\n{wins} op rij. Nog {remaining} te gaan. Al {days_since} dagen...\n\n{url}\n\n#HairLengthIndex",
]

BIJNA_EN = [
    "👀 {team} are on a {wins}-match winning streak...\n\n{remaining} more to go for a haircut!\n{days_since} days of long hair.\n\n{url}\n\n#HairLengthIndex",
    "Can you feel it, {team} fans?\n\n{wins} in a row. {remaining} more to go. {days_since} days waiting...\n\n{url}\n\n#HairLengthIndex",
]

# === CLOSE CALL ===
CLOSE_CALL_NL = [
    "Zo dichtbij... 😩 {team} was {was_on} wedstrijden op rij aan het winnen.\n\nMaar het werd een {result}. Terug naar af.\nDe teller staat op {days_since} dagen.\n\n{url}\n\n#HairLengthIndex",
    "{team}: {was_on} op rij... en toen een {result}.\n\nHet haar groeit weer.\n\n{url}",
]

CLOSE_CALL_EN = [
    "So close... 😩 {team} were on a {was_on}-match winning streak.\n\nThen came a {result}. Back to square one.\n{days_since} days and counting.\n\n{url}\n\n#HairLengthIndex",
]

# === WEEKLY SUMMARY ===
WEEKLY_NL = [
    "Hair Length Index — weekoverzicht 📊\n\n🧔 Langste haar: {longest_team} ({longest_days} dagen, {longest_league})\n💇 Kortste haar: {freshest_team} ({freshest_days} dagen, {freshest_league})\n{almost_text}\n\n{total_teams} clubs, 7 competities.\n{url}\n\n#HairLengthIndex",
]

WEEKLY_EN = [
    "Hair Length Index — weekly update 📊\n\n🧔 Longest hair: {longest_team} ({longest_days} days, {longest_league})\n💇 Freshest cut: {freshest_team} ({freshest_days} days, {freshest_league})\n{almost_text}\n\n{total_teams} clubs across 7 leagues.\n{url}\n\n#HairLengthIndex",
]

# === MILESTONE ===
MILESTONE_NL = [
    "📅 {team}: vandaag precies {milestone} dagen zonder 5 op rij.\n\nDat is {human_days}.\n\n{url}\n\n#HairLengthIndex #{league_tag}",
    "{milestone} dagen! 🧔 {team} wacht al {human_days} op 5 overwinningen op rij.\n\n{url}\n\n#HairLengthIndex",
]

MILESTONE_EN = [
    "📅 {team}: exactly {milestone} days without 5 in a row.\n\nThat's {human_days}.\n\n{url}\n\n#HairLengthIndex #{league_tag}",
    "{milestone} days! 🧔 {team} has been waiting {human_days} for 5 wins in a row.\n\n{url}\n\n#HairLengthIndex",
]

# === COUNTDOWN (4 op rij!) ===
COUNTDOWN_NL = [
    "🔥 {team} heeft 4 op rij! Nog EEN wedstrijd winnen voor een kappersbezoek!\n\nAl {days_since} dagen lang haar. Dit is het moment.\n\n{url}\n\n#HairLengthIndex #BijnaBijDeKapper",
    "NOG EENTJE! {team} staat op 4 overwinningen op rij. 🔥\n\nDe kapper staat klaar. {days_since} dagen wachten.\n\n{url}\n\n#HairLengthIndex",
]

COUNTDOWN_EN = [
    "🔥 {team} have won 4 in a row! ONE more win for a haircut!\n\n{days_since} days of long hair. This is the moment.\n\n{url}\n\n#HairLengthIndex",
    "ONE MORE! {team} are on 4 wins in a row. 🔥\n\nThe barber is ready. {days_since} days waiting.\n\n{url}\n\n#HairLengthIndex",
]

# === BIRTHDAY ===
BIRTHDAY_NL = [
    "🎂 Gefeliciteerd {team}!\n\nEn hun haar? Al {days_since} dagen geen 5 op rij.\n\nVerjaardagscadeau: een kappersbezoek?\n\n{url}\n\n#HairLengthIndex #{league_tag}",
]

BIRTHDAY_EN = [
    "🎂 Happy birthday {team}!\n\nAnd their hair? {days_since} days without 5 in a row.\n\nBirthday wish: a trip to the barber?\n\n{url}\n\n#HairLengthIndex #{league_tag}",
]

# === DERBY ALERT ===
DERBY_NL = [
    "⚔️ {rivalry_name}! {team} vs {opponent}\n\n{team} wacht al {days_since} dagen op 5 op rij.\n\nKan de derby het begin zijn van een streak?\n\n{url}\n\n#HairLengthIndex {extra_tags}",
]

DERBY_EN = [
    "⚔️ {rivalry_name}! {team} vs {opponent}\n\n{team} has waited {days_since} days for 5 in a row.\n\nCan the derby spark a streak?\n\n{url}\n\n#HairLengthIndex {extra_tags}",
]

RESULT_MAP = {"L": "verlies", "D": "gelijkspel", "W": "winst"}
RESULT_MAP_EN = {"L": "loss", "D": "draw", "W": "win"}


def _league_tag(league_name: str) -> str:
    return league_name.replace(" ", "").replace(".", "")


def generate_text(item: dict) -> str:
    """Generate post text from a social queue item."""
    lang = item.get("language", "en")
    item_type = item["type"]
    item["url"] = URL
    item["league_tag"] = _league_tag(item.get("league_name", ""))

    if item_type == "barber_alert":
        templates = BARBER_ALERT_NL if lang == "nl" else BARBER_ALERT_EN
        return random.choice(templates).format(**item)

    elif item_type == "bijna_bij_de_kapper":
        item["wins"] = item["consecutive_wins"]
        templates = BIJNA_NL if lang == "nl" else BIJNA_EN
        return random.choice(templates).format(**item)

    elif item_type == "close_call":
        result_code = item.get("last_result", "L")
        item["result"] = RESULT_MAP.get(result_code, result_code) if lang == "nl" else RESULT_MAP_EN.get(result_code, result_code)
        templates = CLOSE_CALL_NL if lang == "nl" else CLOSE_CALL_EN
        return random.choice(templates).format(**item)

    elif item_type == "weekly_summary":
        longest = item["longest"]
        freshest = item["freshest"]
        almost = item.get("almost", [])
        almost_text = ""
        if almost:
            almost_lines = [f"👀 {a['team']} ({a['wins']}x, {a['league']})" for a in almost]
            label = "Bijna bij de kapper:" if lang == "nl" else "Almost there:"
            almost_text = f"\n{label}\n" + "\n".join(almost_lines)

        data = {
            "longest_team": longest["team"],
            "longest_days": f"{longest['days']:,}".replace(",", "."),
            "longest_league": longest["league"],
            "freshest_team": freshest["team"],
            "freshest_days": freshest["days"],
            "freshest_league": freshest["league"],
            "almost_text": almost_text,
            "total_teams": item.get("total_teams", 130),
            "url": URL,
        }
        templates = WEEKLY_NL if lang == "nl" else WEEKLY_EN
        return random.choice(templates).format(**data)

    elif item_type == "milestone":
        from scripts.fan_data import days_to_human
        item["human_days"] = days_to_human(item.get("milestone", 0))
        templates = MILESTONE_NL if lang == "nl" else MILESTONE_EN
        return random.choice(templates).format(**item)

    elif item_type == "countdown":
        templates = COUNTDOWN_NL if lang == "nl" else COUNTDOWN_EN
        return random.choice(templates).format(**item)

    elif item_type == "birthday":
        templates = BIRTHDAY_NL if lang == "nl" else BIRTHDAY_EN
        return random.choice(templates).format(**item)

    elif item_type == "derby_alert":
        extra = " ".join(item.get("rivalry_hashtags", []))
        item["extra_tags"] = extra
        templates = DERBY_NL if lang == "nl" else DERBY_EN
        return random.choice(templates).format(**item)

    return f"Hair Length Index update: {item.get('team', 'check it out')} — {URL}"
