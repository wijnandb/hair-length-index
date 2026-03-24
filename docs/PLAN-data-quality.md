# Plan: Definitive Data Quality Rebuild

## The Problem

After multiple import attempts, the database has unreliable data:
- Team name fragmentation (same club under 2+ names)
- Duplicate matches (imported from both teams' perspectives)
- Mistagged friendlies (pre-season games labeled as competitive)
- Incomplete seasons (Cloudflare timeouts, partial imports)
- Mixed data from multiple sources (CSV, API, scrape)

None of the previous approaches produced a clean dataset. We need to start over with a fundamentally better approach.

## First Principles

### What uniquely identifies a match?

**Date + Home Team + Away Team.** Not source. Not source_match_id. Two records with the same date, home team, and away team are the same match — always.

Current schema: `UNIQUE(source, source_match_id)` — wrong. Allows the same real-world match to be stored multiple times.

New schema: `UNIQUE(date, home_team_id, away_team_id)` — correct. One row per real-world match, period.

### Expected match counts per team per season

| Competition | Code | Type | Matches/team | Notes |
|-------------|------|------|-------------|-------|
| Eredivisie | DED | LEAGUE | **34** | 18 teams × 2 = 34. Non-negotiable. |
| Eerste Divisie | JE | LEAGUE | **38** | 20 teams × 2 = 38. Non-negotiable. |
| KNVB Beker | KNVB | DOMESTIC_CUP | 1-7 | Knockout. Last match = loss (except cup winner). Max 1 loss per team per season. |
| Champions League | CL | CONTINENTAL | 0-15 | League phase (8) + knockout (up to 7). Only 1-3 Dutch teams. |
| Europa League | EL | CONTINENTAL | 0-15 | Same structure as CL. |
| Conference League | ECL | CONTINENTAL | 0-15 | Same structure. |
| Playoffs/Nacompetitie | PO | LEAGUE | 0-6 | Eerste Divisie teams only. Promotion/relegation. |
| Johan Cruijff Schaal | SC | DOMESTIC_CUP | 0-1 | Champion + cup winner only. 1 match. |

**Validation rules:**
- Eredivisie: exactly 34 league matches per team per completed season
- Eerste Divisie: exactly 38 league matches per team per completed season
- COVID 2019-20: 25-26 Eredivisie, ~28 Eerste Divisie (season voided)
- A team cannot play on the same day twice
- Minimum 2 calendar days between matches (72-hour rule)
- A team can lose at most once per knockout cup per season
- No friendlies in the database

### What is a friendly?

worldfootball.net sometimes includes pre-season tournament matches. Indicators:
- Two matches on the same day for the same team
- Match against a foreign club outside of European competition
- Summer dates (June-July) with non-Dutch/European competition name
- Competition names containing: "friendly", "testspiel", "oefenwedstrijd", "pre-season"

### Team name canonicalization

One canonical name per club. The name from worldfootball.net's competition standings page is authoritative:

**Eredivisie 2025-26:** Ajax, AZ Alkmaar, Excelsior, FC Groningen, FC Twente, FC Utrecht, FC Volendam, Feyenoord, Fortuna Sittard, Go Ahead Eagles, Heerenveen, Heracles Almelo, N.E.C., NAC Breda, PEC Zwolle, PSV Eindhoven, Sparta Rotterdam, Telstar

**Eerste Divisie 2025-26:** ADO Den Haag, Almere City FC, De Graafschap, FC Den Bosch, FC Dordrecht, FC Eindhoven, FC Emmen, Helmond Sport, MVV, RKC Waalwijk, Roda JC Kerkrade, SC Cambuur, TOP Oss, VVV-Venlo, Vitesse, Willem II

**Not included:** Jong Ajax, Jong PSV, Jong AZ, Jong FC Utrecht (reserve teams, excluded)

When an opponent name doesn't match a canonical name, look up alternatives:
- "Heracles" → "Heracles Almelo"
- "Groningen" → "FC Groningen"
- etc.

Build this alias table ONCE and use it everywhere.

## The Rebuild Strategy

### Step 1: Schema change

Add `UNIQUE(date, home_team_id, away_team_id)` constraint. Use `INSERT OR REPLACE` — if the same match is imported from a different team's page, the existing record is updated, not duplicated.

### Step 2: Canonical team registry

Before importing any matches, create all 34 teams in the `teams` table with:
- Canonical name (from worldfootball.net competition page)
- worldfootball.net team ID and slug
- `current_league` = DED or JE
- All known name aliases

### Step 3: Smart opponent name resolution

When importing Team A's matches and encountering an opponent "Heracles":
1. Check canonical names → no match
2. Check alias table → maps to "Heracles Almelo"
3. Look up "Heracles Almelo" in teams table → found, use that ID

Build the alias table from all names that appear in worldfootball.net data. Run a one-time analysis of all opponent names to build the complete mapping.

### Step 4: Import order

Import all teams sequentially. Thanks to `UNIQUE(date, home_team_id, away_team_id)`:
- Team A's page: match "2025-10-01 AZ vs Ajax" → inserted
- Team B's page: same match "2025-10-01 AZ vs Ajax" → already exists, skipped (or updated)

No duplicates possible. No dedup step needed.

### Step 5: Post-import validation (hard fail)

After all imports, run validation. These are **hard failures** — if any fail, the data is not published:

1. **League match count:** Every team that was in Eredivisie for a completed season must have exactly 34 league matches. Every Eerste Divisie team: 38. No exceptions (except COVID 2019-20).
2. **No same-day doubles:** No team plays twice on the same day.
3. **72-hour rule:** No team has matches on consecutive days.
4. **Cup knockout logic:** Maximum 1 loss per team per knockout cup per season.
5. **No friendlies:** No matches tagged as friendly or pre-season.
6. **Season completeness:** Every team must have data for every season they existed in.

### Step 6: Season format normalization

Use `YYYY-YY` everywhere (e.g., "2025-26"). Normalize at import time, not as a post-processing step.

## What's Different This Time

| Previous approach | This approach |
|------------------|--------------|
| `UNIQUE(source, source_match_id)` | `UNIQUE(date, home_team_id, away_team_id)` |
| Multiple sources, dedup after | Single source, no dedup needed |
| Team names created on-the-fly | Team registry created before imports |
| Alias resolution per-importer | Central alias table, used everywhere |
| Validation as optional check | Validation as hard gate |
| Resume with mixed data | No resume — fresh DB or nothing |

## Implementation Steps

1. Build `scripts/team_registry.py` — canonical team names + aliases
2. Modify `db.py` — change UNIQUE constraint
3. Modify `import_worldfootball.py` — use central team resolution
4. Build `scripts/rebuild_clean.py` — the definitive rebuild script
5. Run rebuild (takes ~90 min for 34 teams)
6. Run validation — must pass ALL checks
7. Commit and deploy only if validation passes
