"""Import match data from worldfootball.net via Playwright.

Scrapes historical match results for a team across all competitions
in a given season range. Uses Playwright to bypass Cloudflare protection.

This is a LOCAL-ONLY backfill tool (not for CI) — requires a browser.

Usage:
    python -m scripts.import_worldfootball --team go-ahead-eagles --start 2010 --end 2020
    python -m scripts.import_worldfootball --team fortuna-sittard --start 2013 --end 2018
    python -m scripts.import_worldfootball --list-teams
"""

import argparse
import logging
import re
import time

from scripts.db import (
    find_team_by_name,
    get_connection,
    init_db,
    update_data_source,
    upsert_match,
    upsert_team,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Known team slugs and IDs for worldfootball.net
# Format: our_name → (wf_id, wf_slug)
# Find more at: https://www.worldfootball.net/teams/{slug}/
KNOWN_TEAMS = {
    # Eredivisie 2025-26 (verified from worldfootball.net competition page)
    "Ajax": ("te64", "afc-ajax"),
    "AZ Alkmaar": ("te181", "az-alkmaar"),
    "Excelsior": ("te577", "sbv-excelsior"),
    "Feyenoord": ("te736", "feyenoord"),
    "Fortuna Sittard": ("te828", "fortuna-sittard"),
    "Go Ahead Eagles": ("te899", "go-ahead-eagles"),
    "FC Groningen": ("te631", "fc-groningen"),
    "Heerenveen": ("te1644", "sc-heerenveen"),
    "Heracles Almelo": ("te971", "heracles-almelo"),
    "NAC Breda": ("te1331", "nac-breda"),
    "N.E.C.": ("te1347", "nec"),
    "PSV Eindhoven": ("te1502", "psv-eindhoven"),
    "Sparta Rotterdam": ("te1762", "sparta-rotterdam"),
    "Telstar": ("te1831", "telstar"),
    "FC Twente": ("te1965", "fc-twente"),
    "FC Utrecht": ("te711", "fc-utrecht"),
    "FC Volendam": ("te719", "fc-volendam"),
    "PEC Zwolle": ("te729", "pec-zwolle"),
    # Eerste Divisie 2025-26
    "ADO Den Haag": ("te60", "ado-den-haag"),
    "Almere City FC": ("te681", "almere-city-fc"),
    "De Graafschap": ("te453", "de-graafschap"),
    "FC Den Bosch": ("te615", "fc-den-bosch"),
    "FC Dordrecht": ("te617", "fc-dordrecht"),
    "FC Eindhoven": ("te620", "fc-eindhoven"),
    "FC Emmen": ("te621", "fc-emmen"),
    "Helmond Sport": ("te969", "helmond-sport"),
    "MVV": ("te1327", "mvv"),
    "RKC Waalwijk": ("te1568", "rkc-waalwijk"),
    "Roda JC Kerkrade": ("te1574", "roda-jc-kerkrade"),
    "SC Cambuur": ("te315", "sc-cambuur"),
    "TOP Oss": ("te1914", "top-oss"),
    "VVV-Venlo": ("te2122", "vvv-venlo"),
    "Vitesse": ("te2108", "vitesse"),
    "Willem II": ("te2146", "willem-ii"),
}

# Competition name mapping from worldfootball.net to our model
COMP_MAP = {
    "eredivisie": ("DED", "Eredivisie", "LEAGUE"),
    "eerste divisie": ("JE", "Eerste Divisie", "LEAGUE"),
    "jupiler league": ("JE", "Eerste Divisie", "LEAGUE"),
    "keuken kampioen divisie": ("JE", "Eerste Divisie", "LEAGUE"),
    "knvb beker": ("KNVB", "KNVB Beker", "DOMESTIC_CUP"),
    "knvb-beker": ("KNVB", "KNVB Beker", "DOMESTIC_CUP"),
    "playoffs eredivisie": ("DED-PO", "Eredivisie Playoffs", "LEAGUE"),
    "europa league": ("EL", "Europa League", "CONTINENTAL"),
    "europa league qual": ("EL", "Europa League Kwalificatie", "CONTINENTAL"),
    "conference league": ("ECL", "Conference League", "CONTINENTAL"),
    "conference league qual": ("ECL", "Conference League Kwalificatie", "CONTINENTAL"),
    "champions league": ("CL", "Champions League", "CONTINENTAL"),
    "champions league qual": ("CL", "Champions League Kwalificatie", "CONTINENTAL"),
    "johan cruijff schaal": ("SC_NL", "Johan Cruijff Schaal", "DOMESTIC_CUP"),
    "tweede divisie": ("TD", "Tweede Divisie", "LEAGUE"),
}


def _map_competition(comp_text: str) -> tuple[str, str, str]:
    """Map worldfootball.net competition name to our (id, name, type)."""
    lower = comp_text.lower().strip()
    # Remove season suffix like "2015/2016"
    lower = re.sub(r"\s*\d{4}/\d{4}.*", "", lower)
    # Remove "relegation", "promotion" suffixes
    lower = re.sub(r"\s*(relegation|promotion)$", "", lower)

    # Check longer keys first (e.g., "playoffs eredivisie" before "eredivisie")
    for key, val in sorted(COMP_MAP.items(), key=lambda x: -len(x[0])):
        if key in lower:
            return val
    return (f"WF_{comp_text[:10]}", comp_text, "LEAGUE")


def _parse_date(date_str: str) -> str | None:
    """Parse DD.MM.YYYY to YYYY-MM-DD."""
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", date_str)
    if not m:
        return None
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"


def _parse_score(score_str: str) -> tuple[int, int] | None:
    """Parse '2:1' or '0:4' to (home_goals, away_goals)."""
    m = re.match(r"(\d+):(\d+)", score_str.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def fetch_season(slug: str, wf_id: str, season_start: int) -> list[dict]:
    """Fetch all matches for a team in a season from worldfootball.net.

    Returns list of parsed match dicts.
    """
    from playwright.sync_api import sync_playwright

    season_str = f"{season_start}-{season_start + 1}"
    url = f"https://www.worldfootball.net/teams/{wf_id}/{slug}/vs{season_str}/all-matches/"
    log.info(f"  Fetching {url}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(8)  # Wait for Cloudflare challenge
        content = page.content()
        browser.close()

    if "Just a moment" in content:
        log.warning(f"  Cloudflare blocked request for {season_str}")
        return []

    return _parse_page(content, season_str)


def _parse_page(html: str, season_label: str) -> list[dict]:
    """Parse match data from the HTML page content."""
    import html as html_mod

    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html_mod.unescape(text)
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    matches = []
    current_comp = None
    i = 0

    while i < len(lines):
        line = lines[i]

        # Detect competition headers (e.g. "Eerste Divisie 2015/2016" or "Friendlies Clubs 2024")
        if i + 1 < len(lines) and lines[i + 1] == "Date":
            if re.match(r".+\d{4}/\d{4}", line) or re.match(r".+\d{4}$", line):
                # Stop parsing at friendly sections — everything after is non-competitive
                if "friendl" in line.lower():
                    break
                current_comp = line
                i += 6  # Skip header row: Date, Round, Round, H/A, Res.
                continue

        # Detect match data: starts with a date DD.MM.YYYY
        date_match = re.match(r"(\d{2}\.\d{2}\.\d{4})", line)
        if date_match and current_comp:
            date_str = _parse_date(date_match.group(1))
            if not date_str:
                i += 1
                continue

            # Read the next lines for match data
            # Pattern: date, round_name, round_code, H/A, opponent, W/D/L, score, HT_score
            # Sometimes there's a "pso" or "aet" marker
            j = i + 1
            round_name = lines[j] if j < len(lines) else ""
            j += 1
            round_code = lines[j] if j < len(lines) else ""
            j += 1
            ha = lines[j] if j < len(lines) else ""
            j += 1
            opponent = lines[j] if j < len(lines) else ""
            j += 1
            result_wdl = lines[j] if j < len(lines) else ""

            # Skip unplayed matches early — before consuming score lines
            # that might actually be the next section header
            if result_wdl not in ("W", "D", "L"):
                i = j + 1
                continue

            j += 1
            score_str = lines[j] if j < len(lines) else ""
            j += 1
            ht_score_str = lines[j] if j < len(lines) else ""
            j += 1

            # After HT score, there may be extra score lines (90min, AET) and a pso/aet marker
            # Consume additional score-like lines and markers
            decided_in = "REGULAR"
            while j < len(lines):
                next_line = lines[j].strip().lower()
                if next_line in ("pso", "pen"):
                    decided_in = "PENALTIES"
                    j += 1
                elif next_line in ("aet", "n.v.", "a.e.t."):
                    decided_in = "EXTRA_TIME"
                    j += 1
                elif re.match(r"\d+:\d+$", next_line):
                    # Extra score line (90min or AET score) — skip it
                    j += 1
                else:
                    break

            # Parse score
            score = _parse_score(score_str)
            if not score or result_wdl not in ("W", "D", "L"):
                i = j
                continue

            home_goals, away_goals = score
            is_home = ha == "H"

            # For result_final: use W/D/L as given (includes AET/pens winner)
            if is_home:
                result_final = {"W": "H", "L": "A", "D": "D"}[result_wdl]
            else:
                result_final = {"W": "A", "L": "H", "D": "D"}[result_wdl]

            # For result_90min: if decided in penalties or AET, 90min was a draw
            if decided_in in ("PENALTIES", "EXTRA_TIME"):
                result_90min = "D"
            else:
                result_90min = result_final

            comp_id, comp_name, comp_type = _map_competition(current_comp)

            match_id = f"wf-{date_str}-{opponent}-{ha}"

            matches.append({
                "source_match_id": match_id,
                "date": date_str,
                "opponent": opponent,
                "home_away": ha,
                "home_goals": home_goals,
                "away_goals": away_goals,
                "result_90min": result_90min,
                "result_final": result_final,
                "decided_in": decided_in,
                "competition_id": comp_id,
                "competition_name": comp_name,
                "competition_type": comp_type,
                "round": round_name,
                "season": season_label,
            })

            i = j
            continue

        i += 1

    return matches


def resolve_team(conn, name: str) -> int:
    """Find or create a team by name."""
    team = find_team_by_name(conn, name)
    if team:
        return team["id"]

    # Try alias mapping from CSV importer
    from scripts.import_csv import CSV_TEAM_ALIASES
    canonical = CSV_TEAM_ALIASES.get(name, name)
    if canonical != name:
        team = find_team_by_name(conn, canonical)
        if team:
            return team["id"]

    team_id = upsert_team(conn, name=name, country="NL")
    return team_id


def import_matches(conn, matches: list[dict], team_name: str, dry_run: bool = False) -> int:
    """Import parsed matches into the database."""
    team_id = resolve_team(conn, team_name)
    new_count = 0

    for m in matches:
        opp_id = resolve_team(conn, m["opponent"])
        is_home = m["home_away"] == "H"

        if is_home:
            home_id, away_id = team_id, opp_id
            home_goals, away_goals = m["home_goals"], m["away_goals"]
        else:
            home_id, away_id = opp_id, team_id
            home_goals, away_goals = m["home_goals"], m["away_goals"]

        if dry_run:
            r = m["result_final"]
            result_for_team = "W" if (r == "H" and is_home) or (r == "A" and not is_home) else ("L" if (r == "A" and is_home) or (r == "H" and not is_home) else "D")
            log.info(f"  [DRY] {m['date']} {result_for_team} {m['home_goals']}:{m['away_goals']} "
                     f"vs {m['opponent']} ({m['home_away']}) [{m['competition_name']}] {m['decided_in']}")
            new_count += 1
            continue

        result = upsert_match(
            conn,
            source="worldfootball.net",
            source_match_id=m["source_match_id"],
            date=m["date"],
            home_team_id=home_id,
            away_team_id=away_id,
            home_goals_90min=home_goals,
            away_goals_90min=away_goals,
            home_goals_final=home_goals,
            away_goals_final=away_goals,
            decided_in=m["decided_in"],
            result_90min=m["result_90min"],
            result_final=m["result_final"],
            competition_id=m["competition_id"],
            competition_name=m["competition_name"],
            competition_type=m["competition_type"],
            round=m["round"],
            season=m["season"],
        )
        if result is not None:
            new_count += 1

    return new_count


def run_import(
    team_key: str,
    start_year: int,
    end_year: int,
    dry_run: bool = False,
) -> None:
    """Main entry point: fetch and import match data for a team."""
    # Look up team info
    team_info = None
    for name, (wf_id, slug) in KNOWN_TEAMS.items():
        if slug == team_key or name.lower() == team_key.lower():
            team_info = (name, wf_id, slug)
            break

    if not team_info:
        log.error(f"Unknown team: {team_key}. Use --list-teams to see available teams.")
        return

    team_name, wf_id, slug = team_info

    conn = get_connection()
    init_db(conn)

    log.info(f"Importing {team_name} from worldfootball.net ({start_year}-{end_year})...")
    total_new = 0

    for year in range(end_year, start_year - 1, -1):
        matches = fetch_season(slug, wf_id, year)
        if not matches:
            log.info(f"  {year}-{year+1}: no matches found")
            continue

        new = import_matches(conn, matches, team_name, dry_run=dry_run)
        total_new += new
        season_label = f"{year}-{str(year+1)[-2:]}"
        log.info(f"  {season_label}: {len(matches)} matches parsed, {new} new imported")

    action = "Would import" if dry_run else "Imported"
    log.info(f"{action} {total_new} total new matches for {team_name}")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Import from worldfootball.net")
    parser.add_argument("--team", help="Team slug (e.g. go-ahead-eagles) or name")
    parser.add_argument("--start", type=int, default=2010, help="Start year (default: 2010)")
    parser.add_argument("--end", type=int, default=2024, help="End year (default: 2024)")
    parser.add_argument("--dry-run", action="store_true", help="Parse without importing")
    parser.add_argument("--list-teams", action="store_true", help="List known teams")
    args = parser.parse_args()

    if args.list_teams:
        print("Known teams:")
        for name, (wf_id, slug) in sorted(KNOWN_TEAMS.items()):
            print(f"  --team {slug:<30} # {name}")
        return

    if not args.team:
        parser.error("--team is required (use --list-teams to see options)")

    run_import(args.team, args.start, args.end, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
