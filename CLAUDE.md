# Hair Length Index — Project Instructions

## What This Is

Tracks how long since each football club last won 5 matches in a row.
Live at: https://wijnandb.github.io/hair-length-index/

## Data Architecture

### Single Source: worldfootball.net

**USE ONLY worldfootball.net for match data.** Previous attempts with multiple sources (football-data.co.uk CSV, football-data.org API, API-Football, KNVB Beker scraper) caused:
- Team name fragmentation (same club as 2+ entries)
- Cross-source duplicate matches
- Misattributed seasons
- Inconsistent competition names

worldfootball.net has everything: league, cup, European, playoffs — all from one team page.

### Critical Parser Rules for worldfootball.net

1. **Friendly section header uses single year**: `"Friendlies Clubs 2025"` (NOT `YYYY/YYYY`). The parser MUST detect this and STOP parsing. Everything after this header is a friendly.

2. **Unplayed matches (`-:-`) consume extra lines**: When a match result is `-:-` (not yet played), skip it IMMEDIATELY after reading the result field. Do NOT read score/HT lines — they will consume the next section header.

3. **Competition mapping — longest key first**: When matching competition names, sort keys by length descending. Otherwise `"eredivisie"` matches before `"playoffs eredivisie"` and playoffs get counted as league matches.

4. **Season format**: worldfootball.net uses `YYYY/YYYY` in headers. Normalize to `YYYY-YY` (e.g., `"2025-26"`) for storage.

### Database Schema

**The uniqueness constraint is `UNIQUE(date, home_team_id, away_team_id)`.** NOT `UNIQUE(source, source_match_id)`. One row per real-world match, regardless of how many sources report it.

### Team Name Resolution

Use the central team registry (`scripts/team_registry.py`). NEVER create team names on-the-fly without checking aliases. Known problem names:
- "N.E.C." vs "NEC" vs "NEC Nijmegen" vs "Nijmegen" — all same club
- "FC Twente" vs "FC Twente '65" vs "Twente"
- "sc Heerenveen" vs "Heerenveen" vs "SC Heerenveen"
- "Feyenoord" vs "Feyenoord Rotterdam"
- "De Graafschap" vs "De Graafs."
- "Sp. Rotterdam" vs "Sparta Rotterdam"

### worldfootball.net Team IDs

Team IDs on worldfootball.net are NOT predictable. They must be looked up from competition pages. The competition pages are at:
- Eredivisie: `https://www.worldfootball.net/competition/co37/`
- Eerste Divisie: `https://www.worldfootball.net/competition/co50/`
- Premier League: `https://www.worldfootball.net/competition/co1/`
- Bundesliga: `https://www.worldfootball.net/competition/co3/`
- Serie A: `https://www.worldfootball.net/competition/co4/`
- La Liga: `https://www.worldfootball.net/competition/co5/`
- Ligue 1: `https://www.worldfootball.net/competition/co7/`

### Cloudflare Protection

worldfootball.net uses Cloudflare. Playwright (headless Chrome) is required with:
- `time.sleep(8)` after page load for Cloudflare challenge
- User-agent header: `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36`
- Rate limiting: ~10 seconds between requests
- Cloudflare may block after many requests — add error handling and retry

## Data Validation Rules

Run `python -m scripts.validate_data --league DED` after any data change.

### Hard rules (errors):
- Eredivisie: exactly 34 league matches per team per completed season
- Eerste Divisie: exactly 38 league matches per team per completed season
- KNVB Beker: max 7 matches per team per season
- European competitions (CL/EL/ECL): max 21 matches per team per season
- Playoffs: max 6 matches per team per season
- Max 1 loss per team per knockout cup per season
- No team plays twice on the same day
- No duplicate matches (same date + same teams)

### Expected total matches per team per season:
- Eredivisie team (no Europe): 35-45
- Eredivisie team (with Europe): 45-60
- Eerste Divisie team: 39-50
- COVID 2019-20: 25-28 league matches (season stopped at matchday 26)

### Common false positives:
- Teams that switch divisions (e.g., relegated from DED to JE) will have 38 "league" matches in their JE season, not 34
- The validator now checks per-competition_id (DED=34, JE=38) instead of assuming all teams play 34

## Streak Calculation

- Uses `result_final` (winning is winning, including AET/penalties)
- All competitions count (league + cup + European)
- Friendlies are EXCLUDED
- A draw in a cup match still counts as a non-win (breaks the streak)

## Key Files

| File | Purpose |
|------|---------|
| `scripts/rebuild_clean.py` | Definitive single-source rebuild from worldfootball.net |
| `scripts/import_worldfootball.py` | Playwright scraper for worldfootball.net team pages |
| `scripts/team_registry.py` | Canonical team names + aliases |
| `scripts/compute_streaks.py` | Streak calculation + JSON export |
| `scripts/validate_data.py` | 12 validation checks |
| `frontend/app.js` | Site frontend (league tabs, team cards, growth strip) |
| `video/` | Remotion video project for social media |

## Frontend

- League selector: Eredivisie / Eerste Divisie tabs
- Click any team card to see match detail (hair growth strip + table)
- Share button per team (Web Share API + clipboard fallback)
- YouTube search links per match
- "Bijna bij de kapper!" section (auto-shows when teams on 3+ win streak with >120 days drought)

## Video (Remotion)

- Project at `video/`
- Render: `cd video && npx remotion render HeadToHead ~/Downloads/output.mp4`
- Match data generated from team JSON files
- Club logos in `video/public/logos/`
- DiceBear avatars for supporter portraits with hair tier progression

## Workflow (GitHub Actions)

- `update-data.yml`: daily data update + deploy
- `deploy-pages.yml`: deploy frontend to GitHub Pages
- Both generate Eredivisie AND Eerste Divisie indexes
- The workflow uses football-data.org API for current-season updates (not worldfootball.net — can't run Playwright in CI)
- Historical data from worldfootball.net is maintained via local rebuilds

## Conventions

- Default language: Dutch for user-facing content
- Use Bun over Node.js
- Python 3.11 for scripts with Playwright (`python3.11`)
- System Python 3.12 for non-Playwright scripts (`python` or `python3`)
- Don't commit `data/hair-index.db` (local only)
- DO commit `data/hair-index.json`, `data/hair-index-je.json`, `data/teams/*.json`
