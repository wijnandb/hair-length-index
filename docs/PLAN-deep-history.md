# Plan: Deep History, Match Navigation & Multi-League Architecture

## Current State

- 5 of 18 Eredivisie teams have a 5-win streak in our data
- 13 teams show "Lost in time" — data only goes back to 2023 (3 seasons)
- Some teams (Go Ahead Eagles, NEC, Sparta) have data from only this season
- Match detail panel shows last 20 matches in a flat table
- Single JSON file ships everything to the frontend

## Problems to Solve

1. **Can't see the streak** — the 5-win streak may be match #40-45 but we only show 20
2. **No visual story** — a table doesn't show the pattern (long drought → sudden streak)
3. **Not enough history** — 3 seasons isn't enough to find every team's streak
4. **Single-league** — architecture is hardcoded to Eredivisie
5. **JSON bloat** — shipping all matches for all teams in one file won't scale

---

## Phase 1: Full Match Timeline with Streak Highlighting

**Goal:** Show ALL matches for a team, with the 5-win streak visually highlighted.

### 1a. Visual: The "Hair Growth Strip"

Replace the match table with a horizontal strip of colored blocks (one per match):

```
[W][W][D][L][W][W][W][W][W][L][D][W][L]...
 green       ←—— STREAK ——→
```

- Each block is a small colored square: green (W), gray (D), red (L)
- The 5-win streak is highlighted with a gold border/background
- Hovering a block shows: date, opponent, score, competition
- Clicking a block opens the detail (like current table row)
- The strip shows ALL matches, most recent on the left
- Auto-scrolls to the streak when opened

**Why this works:** It's a visual heartbeat. You instantly see patterns — long red/gray stretches for struggling teams, green clusters for strong ones. The highlighted streak jumps out.

### 1b. Data: Per-Team Match Files

Split the JSON output:

```
data/
  hair-index.json          # rankings only (no recent_matches)
  teams/
    1.json                 # all matches for team 1
    2.json                 # all matches for team 2
    ...
```

- `hair-index.json` stays small (~5KB for 18 teams)
- Per-team files loaded on demand when user clicks a team
- Each team file contains ALL matches (not just 20)
- Streak start/end indices marked in the file for frontend highlighting

**Schema for per-team file:**
```json
{
  "team_id": 1,
  "team": "PSV",
  "matches": [
    {
      "date": "2026-03-21",
      "opponent": "AZ",
      "home_away": "H",
      "score": "2-1",
      "result": "W",
      "competition": "Eredivisie",
      "decided_in": "REGULAR",
      "source": "football-data.org"
    }
  ],
  "streak": {
    "found": true,
    "start_index": 12,
    "end_index": 17,
    "length": 6
  }
}
```

**Backend change:** `compute_streaks.py` exports per-team files to `data/teams/`. The `export_json` function writes both the index and per-team files. GitHub Actions commits the entire `data/` directory.

**Frontend change:** Click team → fetch `data/teams/{team_id}.json` → render hair growth strip.

### 1c. Match Table as Fallback

Keep the current table view as a toggle below the strip for users who want details. Add pagination or "show all" since we'll have more than 20 matches.

---

## Phase 2: Deeper Historical Data

**Goal:** Find a streak for every team. No more "Lost in time."

### Data Sources (ordered by ease/reliability)

| Source | Coverage | Type | Effort |
|--------|----------|------|--------|
| **football-data.co.uk** | 1990s–present, Eredivisie league | Free CSV download | Low — just parse CSV |
| **API-Football paid** (€19/mo) | 2010–present, all competitions | API | Low — already have client |
| **football-data.org paid** ($12/mo) | More leagues/seasons | API | Low — already have client |
| **RSSSF.org** | 1950s–present, text format | Scrape + parse | Medium — semi-structured text |
| **Transfermarkt** | Detailed match data | Scrape (fragile) | High — blocks bots |
| **Wikipedia season pages** | Per-team per-season | Scrape | Medium — varying HTML |

### Recommended Approach

**Step 1: football-data.co.uk CSV import (free, immediate)**

They provide CSV files for Eredivisie going back to ~2000. Each CSV has:
`Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR, HTHG, HTAG, HTR`

Write `scripts/import_csv.py`:
- Download CSV from football-data.co.uk for seasons 2000-2023
- Parse and import into matches table with `source = "football-data-uk"`
- League matches only (no cups) — but that's enough to find most streaks
- One-time import, ~20 CSV files, instant

**Step 2: API-Football backfill (if Step 1 doesn't cover everyone)**

For teams where the CSV league data still doesn't show a 5-win streak:
- These are likely teams that only won 5 in a row when cup wins are included
- Or recently promoted teams whose streak was in the Eerste Divisie
- Use API-Football (free tier, 2022-2024) for cup data
- Or upgrade to paid for deeper history

**Step 3: RSSSF for extreme cases**

For teams that have *never* won 5 league matches in a row (e.g., a promoted lower-league team), RSSSF has Eerste Divisie data going back decades. Semi-automated parser.

### Expected Outcome

With football-data.co.uk CSVs (25 seasons of Eredivisie), we should find streaks for most teams. The ones left will be teams whose entire history is mediocre enough that 5 consecutive wins is genuinely rare — which makes the index even funnier.

---

## Phase 3: Multi-League Architecture

**Goal:** Add Premier League, Bundesliga, La Liga, etc. with minimal per-league code.

### Current State → Target State

**Currently:** League is a parameter (`--league DED`) but many things are hardcoded:
- Season year `2025` is hardcoded in `fetch_matches.py` and `fill_gaps.py`
- KNVB Beker importer is Eredivisie-specific
- Frontend shows one league

**Target:** League as a first-class dimension throughout the stack.

### Data Architecture

```
data/
  leagues/
    DED/                          # Eredivisie
      index.json                  # rankings for this league
      teams/
        1.json                    # match history
        2.json
    PL/                           # Premier League
      index.json
      teams/
        ...
    BL1/                          # Bundesliga
      ...
  global-index.json               # cross-league rankings ("longest hair in Europe")
```

### Backend Changes

1. **`config.py`:** Add per-league config:
   ```python
   LEAGUES = {
     "DED": {
       "name": "Eredivisie",
       "country": "NL",
       "football_data_code": "DED",
       "football_data_uk_code": "N1",
       "cup_scraper": "import_knvb_beker",
       "current_season": 2025,
     },
     "PL": {
       "name": "Premier League",
       "country": "EN",
       "football_data_code": "PL",
       "football_data_uk_code": "E0",
       "cup_scraper": None,  # FA Cup: would need a different scraper
       "current_season": 2025,
     },
   }
   ```

2. **`compute_streaks.py`:** Already takes `--league` parameter. Add `--all-leagues` flag that iterates all configured leagues. Export to `data/leagues/{code}/`.

3. **`fetch_matches.py`:** Already takes `--league`. No change needed — just run it multiple times in the workflow.

4. **GitHub Actions workflow:** Loop over leagues:
   ```yaml
   - name: Fetch match data
     run: |
       for LEAGUE in DED PL BL1; do
         python -m scripts.fetch_matches --mode daily --league $LEAGUE
       done
   ```

5. **Cup scrapers:** Each league needs its own cup data source. Start with Eredivisie (done), add others as needed. These are optional — league-only data already gives good streaks.

### Frontend Changes

1. **League selector:** Dropdown or tabs at the top: Eredivisie | Premier League | Bundesliga | ...
2. **Global ranking:** "Longest hair in Europe" cross-league page
3. **Each league loads its own `index.json`** — no change to rendering logic

### What DOESN'T need to change per league

- Match data model (same `matches` table for all leagues)
- Streak calculation algorithm (same `find_last_streak`)
- Team card rendering (same component)
- Hair tier logic (same thresholds)
- Deploy workflow (same pattern, just more files)

---

## Phase 4: Smart Adaptive Depth

**Goal:** Automatically go deeper for teams that need it.

Instead of fetching the same 3 seasons for every team, be smart:
- If a team has a 5-win streak in the current season → stop (PSV, Ajax)
- If not found in 3 seasons → try 5 seasons (football-data.co.uk CSV)
- If still not found → try 10 seasons
- If STILL not found → try 25 seasons → "congratulations, your team has never won 5 in a row in the 21st century"

This is already roughly how `find_last_streak` works (it searches all available data). The key is just *having* the data imported. Phase 2 handles that.

---

## Implementation Order

| Phase | What | Effort | Impact |
|-------|------|--------|--------|
| **1a** | Hair growth strip visualization | 1 day | High — the visual story |
| **1b** | Per-team JSON files + on-demand loading | Half day | Enables 1a, scales |
| **2 Step 1** | football-data.co.uk CSV import | Half day | Finds streaks for most teams |
| **2 Step 2** | API-Football backfill for remaining | Half day | Fills cup data gaps |
| **1c** | Table view toggle with pagination | Half day | Accessibility |
| **3** | Multi-league config + frontend | 1-2 days | Premier League etc. |
| **4** | Adaptive depth search | Already done in algorithm | Automatic |

**Recommended start:** Phase 1b (per-team files) → Phase 2 Step 1 (CSV import) → Phase 1a (strip viz). This order gives us the data first, then the visualization.

---

## Answering Your Specific Questions

**"How far back can we go?"**
With football-data.co.uk CSVs: back to ~2000 for Eredivisie league matches. With RSSSF: back to the 1950s. With API-Football paid: back to ~2010 for all competitions.

**"Do we have to store results separately per team?"**
No. Keep one `matches` table (as now). But *export* per-team JSON files for the frontend. The database is the source of truth; the JSON files are views.

**"Only the index with days and streak per competition?"**
Two-tier export:
1. `index.json` = rankings + summary (small, loads fast)
2. `teams/{id}.json` = full match history (loaded on demand)

**"Apply to other leagues?"**
Yes — the architecture is league-agnostic. Same data model, same streak algorithm, same frontend components. Just different data sources per league. football-data.org free tier already covers PL, Bundesliga, Serie A, La Liga, Ligue 1.
