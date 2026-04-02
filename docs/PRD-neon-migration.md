# PRD: Hair Length Index — Neon Postgres Migration

## Problem

The SQLite database is local-only and not committed to git. Every CI run rebuilds from scratch using multiple data sources (football-data.org, football-data.co.uk CSV, KNVB Beker scraper, API-Football). These sources use different team names, creating duplicate team entries and corrupted index data.

**Root cause**: no persistent database means no stable team identity across runs.

## Solution

Migrate to Neon Postgres as the single persistent database. CI reads/writes to Neon directly, then generates static JSON and commits it to the repo. GitHub Pages continues to serve the frontend with static JSON — no API needed.

**Key insight**: data changes once per day. There's no reason to query a database on every page load. The database solves the *write* problem (persistent team identity). The *read* path stays static.

## Current State

| Metric | Value |
|--------|-------|
| Teams | ~1,100 (across 7 leagues) |
| Matches | ~31,500 |
| DB size | 11 MB |
| Leagues | DED, JE, PL, BL, SA, LL, L1 |
| Update frequency | Daily at 06:00 UTC |

## Architecture

```
Before:
  CI → rebuild SQLite from 4 data sources → duplicates → broken JSON → deploy

After:
  Local: Playwright → worldfootball.net → Neon (only when new matches to add)
  CI:    Read Neon → compute streaks → generate JSON → commit → deploy
```

- **One data source**: worldfootball.net only (via Playwright, run locally)
- **One database**: Neon Postgres (persistent, shared between local and CI)
- **One output**: static JSON on GitHub Pages (no API needed)
- **Zero data fetching in CI** — CI only reads and computes

## Database Schema (Neon Postgres)

Migrate the existing SQLite schema with these improvements:

### `teams` table

```sql
CREATE TABLE teams (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    short_name    TEXT,
    country       TEXT,
    wf_slug       TEXT UNIQUE,          -- worldfootball.net slug = canonical team ID
    crest_url     TEXT,
    current_league TEXT,
    UNIQUE(name, current_league)        -- prevent duplicate names per league
);
```

**Key change**: `wf_slug` is the canonical team identifier (from `team_registry.py`). One source, one ID, no ambiguity. The `football_data_id` and `api_football_id` columns are dropped — those sources are no longer used.

### `matches` table

```sql
CREATE TABLE matches (
    id                    SERIAL PRIMARY KEY,
    source                TEXT NOT NULL,
    source_match_id       TEXT NOT NULL,
    date                  DATE NOT NULL,
    home_team_id          INTEGER NOT NULL REFERENCES teams(id),
    away_team_id          INTEGER NOT NULL REFERENCES teams(id),
    home_goals_90min      SMALLINT,
    away_goals_90min      SMALLINT,
    home_goals_final      SMALLINT,
    away_goals_final      SMALLINT,
    home_goals_penalties  SMALLINT,
    away_goals_penalties  SMALLINT,
    decided_in            TEXT CHECK(decided_in IN ('REGULAR', 'EXTRA_TIME', 'PENALTIES')),
    result_90min          TEXT CHECK(result_90min IN ('H', 'A', 'D')),
    result_final          TEXT CHECK(result_final IN ('H', 'A', 'D')),
    competition_id        TEXT NOT NULL,
    competition_name      TEXT,
    competition_type      TEXT CHECK(competition_type IN ('LEAGUE', 'DOMESTIC_CUP', 'CONTINENTAL', 'SUPER_CUP')),
    round                 TEXT,
    season                TEXT NOT NULL,
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, home_team_id, away_team_id)
);

CREATE INDEX idx_matches_team_date ON matches(home_team_id, date);
CREATE INDEX idx_matches_away_date ON matches(away_team_id, date);
CREATE INDEX idx_matches_competition ON matches(competition_id, season);
```

### `data_sources` table

```sql
CREATE TABLE data_sources (
    id              SERIAL PRIMARY KEY,
    source          TEXT NOT NULL,
    competition_id  TEXT NOT NULL,
    season          TEXT NOT NULL,
    last_fetched    TIMESTAMPTZ,
    match_count     INTEGER DEFAULT 0,
    status          TEXT CHECK(status IN ('COMPLETE', 'PARTIAL', 'PENDING')) DEFAULT 'PENDING',
    UNIQUE(source, competition_id, season)
);
```

## Data Flow

### Adding new match data (local, manual)

```bash
# Run Playwright scraper → writes to Neon
python3.11 -m scripts.import_worldfootball --league DED
```

Run this after matchdays or whenever you want fresh data. Playwright + worldfootball.net requires a real browser, so it runs locally (not in CI).

### CI Workflow (daily, automated)

```
checkout → install deps → compute streaks from Neon → generate JSON → commit → deploy
```

CI does **zero data fetching**. It only:
1. Connects to Neon via `DATABASE_URL`
2. Runs `compute_streaks` (reads matches, calculates streaks)
3. Generates `hair-index.json` + `hair-index-je.json` + team files
4. Commits and deploys if changed

### Scripts removed from CI
- `fetch_matches.py` (football-data.org) — dropped entirely
- `import_csv.py` (football-data.co.uk) — dropped entirely
- `import_knvb_beker.py` (web scraper) — dropped entirely
- `fill_gaps.py` (API-Football) — dropped entirely

All historical data is already in Neon from the migration. New data comes from worldfootball.net only.

### Environment Variables

| Where | Secret | Purpose |
|-------|--------|---------|
| GitHub Actions | `DATABASE_URL` | Neon Postgres connection string |
| Local `.env` | `DATABASE_URL` | Same connection string for local scraping |

`FOOTBALL_DATA_API_KEY` and `API_FOOTBALL_API_KEY` can be removed from GitHub secrets — no longer used.

## Migration Plan

### Phase 1: Neon Setup

**You create the Neon project.** I need:
- **Connection string** (`DATABASE_URL`) — format: `postgresql://user:pass@host/dbname?sslmode=require`
- **Project region** — recommend `aws-eu-central-1` (Frankfurt, close to data sources)

I'll create the tables via the connection string.

### Phase 2: Data Migration

Dump existing SQLite data and load into Neon:
- Export teams + matches from SQLite
- Enrich teams with `wf_slug` from `team_registry.py`
- Insert into Neon
- Validate row counts match

### Phase 3: Script Updates

Update `scripts/config.py` and `scripts/db.py`:
- Replace SQLite connection with `psycopg2` / `asyncpg`
- Keep the same function signatures (`get_connection`, `upsert_team`, etc.)
- Add `DATABASE_URL` env var support
- Keep SQLite as fallback for local dev (if `DATABASE_URL` not set)

### Phase 4: CI Workflow

- Update `update-data.yml`: remove ALL data fetch steps
- Keep only: `compute_streaks` (reads Neon) → generate JSON → commit → deploy
- Add `DATABASE_URL` as GitHub secret

### Phase 5: Validate

- Trigger CI manually, verify JSON output matches current
- Confirm no duplicate teams
- Frontend unchanged — zero risk

## What I Need From You

1. **Create a Neon project** (free tier is fine — we're at 11MB, limit is 512MB)
   - Suggested name: `hair-length-index`
   - Region: `aws-eu-central-1` (Frankfurt)
2. **Share the connection string** — I'll set up tables and migrate data
3. **Add `DATABASE_URL` as a GitHub Actions secret** on the repo

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Neon free tier limits (512MB storage) | Current data is 11MB; even 10x growth = 110MB |
| Neon cold starts slow down CI | CI runs once/day; a few seconds extra is fine |
| Migration data loss | Validate row counts SQLite vs Neon before switching CI |

## Out of Scope

- Cloudflare Worker / API layer (data changes daily; static JSON is the right pattern)
- Real-time match updates (daily batch is sufficient)
- Frontend changes (zero changes needed)
