# Hair Length Index — Project Instructions

## What This Is

Tracks how long since each football club last won 5 matches in a row.
Live at: https://wijnandb.github.io/hair-length-index/

## Data Architecture

### Three Data Sources

Match data comes from three sources, each serving a specific purpose:

1. **worldfootball.net** (Playwright scraper, local only) — historical backfill. Has everything: league, cup, European, playoffs. Cannot run in CI (Cloudflare blocks headless browsers).
2. **football-data.org** (REST API, free tier) — daily CI updates for: DED, PL, BL1, SA, PD, FL1, CL. Key: `FOOTBALL_DATA_API_KEY`. Rate limit: 10 req/min.
3. **API-Football** (api-sports.io) — intended for JE, KNVB Beker, EL, ECL. Key: `API_FOOTBALL_API_KEY`. Rate limit: 100 req/day. **Note: free tier only covers seasons 2022-2024.** Current-season JE data comes from worldfootball.net local rebuilds only.

### Team ID Mapping

Each team can have up to 3 external IDs stored in the `teams` table:
- `wf_id` — worldfootball.net team ID (e.g., `te64` for Ajax)
- `football_data_id` — football-data.org team ID (e.g., `678` for Ajax)
- `api_football_id` — API-Football team ID (e.g., `194` for Ajax)

All mappings are defined in `scripts/team_registry.py` → `EXTERNAL_IDS` dict. The `upsert_team` function in `db.py` resolves teams by external ID (football_data_id → api_football_id → wf_slug → create new).

### Critical Parser Rules for worldfootball.net

1. **Friendly section header uses single year**: `"Friendlies Clubs 2025"` (NOT `YYYY/YYYY`). The parser MUST detect this and STOP parsing. Everything after this header is a friendly.

2. **Unplayed matches (`-:-`) consume extra lines**: When a match result is `-:-` (not yet played), skip it IMMEDIATELY after reading the result field. Do NOT read score/HT lines — they will consume the next section header.

3. **Competition mapping — longest key first**: When matching competition names, sort keys by length descending. Otherwise `"eredivisie"` matches before `"playoffs eredivisie"` and playoffs get counted as league matches.

4. **Season format**: worldfootball.net uses `YYYY/YYYY` in headers. Normalize to `YYYY-YY` (e.g., `"2025-26"`) for storage.

### Database: Neon Postgres (with SQLite fallback)

Production data lives in **Neon Postgres** (`DATABASE_URL` env var, project `bitter-moon-88639626`). If `DATABASE_URL` is not set, scripts fall back to local SQLite (`data/hair-index.db`). CI fetches new matches into Neon via APIs, then computes streaks.

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
| `scripts/db.py` | Database module — Neon Postgres with SQLite fallback |
| `scripts/rebuild_clean.py` | Definitive single-source rebuild from worldfootball.net |
| `scripts/import_worldfootball.py` | Playwright scraper for worldfootball.net team pages |
| `scripts/team_registry.py` | Canonical team names, aliases, external ID mappings |
| `scripts/daily_update.py` | CI daily update: fetch from football-data.org + API-Football |
| `scripts/compute_streaks.py` | Streak calculation + JSON export |
| `scripts/validate_data.py` | 12 validation checks |
| `scripts/generate_social_content.py` | Social media content generation (multiple post types) |
| `scripts/post_bluesky.py` | Bluesky posting |
| `scripts/post_reddit.py` | Reddit posting (league-specific subreddits) |
| `scripts/generate_reel_data.py` | Generate match data for Remotion reels |
| `scripts/fan_data.py` | Supporter image pipeline (jersey swap + hair growth) |
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
- Compositions: `HeadToHead` (landscape), `HairGrowthReel` (9:16 vertical Instagram), `SocialCard`
- Match data generated from team JSON files
- Club logos in `video/public/logos/`
- DiceBear avatars for supporter portraits with hair tier progression

## Workflow (GitHub Actions)

- `update-data.yml`: daily at 06:00 UTC — fetch new matches from APIs → compute streaks for all 7 leagues → deploy to GitHub Pages
- `deploy-pages.yml`: deploy frontend to GitHub Pages
- `social-post.yml`: daily at 10:00 UTC — auto-post to Bluesky + Reddit (supports dry run)
- `ci.yml`: CI checks
- CI fetches from football-data.org (DED/PL/BL1/SA/PD/FL1/CL) and API-Football (JE/KNVB/EL/ECL) into Neon
- Historical data maintained via local rebuilds with worldfootball.net scraper
- Secrets needed: `DATABASE_URL`, `FOOTBALL_DATA_API_KEY`, `API_FOOTBALL_API_KEY`

## Social Media

- **Bluesky**: automated posting via `scripts/post_bluesky.py`
- **Reddit**: league-specific subreddits with markdown tables via `scripts/post_reddit.py`
- Content types: streak updates, "bijna bij de kapper" alerts, weekly summaries
- Secrets: `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`

## Conventions

- Default language: Dutch for user-facing content
- Use Bun over Node.js
- Python 3.11 for scripts with Playwright (`python3.11`)
- System Python 3.12 for non-Playwright scripts (`python` or `python3`)
- Don't commit `data/hair-index.db` (local only)
- DO commit `data/hair-index.json`, `data/hair-index-je.json`, `data/teams/*.json`
- `DATABASE_URL` env var for Neon Postgres connection (local dev + CI)
