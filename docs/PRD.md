# PRD: European Hair Length Index

## The Concept

Inspired by the Manchester United fan who refuses to cut his hair until United win 5 matches in a row, the **Hair Length Index** tracks how long it’s been since each club in a league last achieved a 5-game winning streak — across *all* competitions (league, cup, and European).

The longer since the last streak, the longer the “hair.” Teams that have *never* achieved a 5-win streak in the tracked period are “full caveman.”

-----

## 1. Problem Statement

We tried to manually compile Eredivisie 2025-26 match results from web sources (Wikipedia, RSSSF, FBref, worldfootball.net, Transfermarkt) and ran into:

- **No single source** has all matches (league + cup + European) in a clean, parseable format
- **Wikipedia season pages per team** are the richest source (they have W/D/L per round AND cup/European results), but:
  - They require a separate fetch per team (18 fetches for one league)
  - The HTML structure varies between pages
  - Data is often truncated in fetches
- **RSSSF** only publishes after season completion
- **FBref/Transfermarkt/worldfootball.net** block or rate-limit scraping
- **Manual reconstruction** led to estimated/incorrect results for most teams

We need a reliable, automated data pipeline.

-----

## 2. Data Requirements

### 2.1 Core Data Model

```
Match {
  id: INTEGER PRIMARY KEY       # internal auto-increment
  source: TEXT                   # "football-data.org", "api-football", "rsssf", "manual"
  source_match_id: TEXT          # original ID from source (for dedup across sources)
  date: DATE                    # match date (UTC)
  home_team_id: INT             # FK → teams.id
  away_team_id: INT             # FK → teams.id
  home_goals_90min: INT         # score after 90 minutes
  away_goals_90min: INT
  home_goals_final: INT         # score at end of match (after AET if applicable, before pens)
  away_goals_final: INT
  home_goals_penalties: INT NULL # penalty shootout score (NULL if no shootout)
  away_goals_penalties: INT NULL
  decided_in: TEXT              # "REGULAR" | "EXTRA_TIME" | "PENALTIES"
  result_90min: TEXT            # "H" | "A" | "D" — who won after 90 minutes
  result_final: TEXT            # "H" | "A" | "D" — who progresses / wins the match
  competition_id: TEXT          # e.g. "DED", "KNVB", "CL", "EL"
  competition_name: TEXT        # human-readable, e.g. "Eredivisie"
  competition_type: TEXT        # "LEAGUE" | "DOMESTIC_CUP" | "CONTINENTAL" | "SUPER_CUP"
  round: TEXT NULL              # e.g. "Matchday 14", "Quarter-final"
  season: TEXT                  # e.g. "2025-26"
  UNIQUE(source, source_match_id)  # prevent duplicate imports
}

Team {
  id: INTEGER PRIMARY KEY       # internal ID
  name: TEXT                    # canonical display name, e.g. "PSV Eindhoven"
  short_name: TEXT              # e.g. "PSV"
  country: TEXT                 # e.g. "NL", "EN", "DE"
  football_data_id: INT NULL    # football-data.org team ID
  api_football_id: INT NULL     # api-football.com team ID
  crest_url: TEXT NULL
  current_league: TEXT          # e.g. "DED", "PL"
}

DataSource {
  id: INTEGER PRIMARY KEY
  source: TEXT                  # "football-data.org", "api-football", etc.
  competition_id: TEXT          # e.g. "DED"
  season: TEXT                  # e.g. "2025-26"
  last_fetched: DATETIME        # when we last pulled data for this combo
  match_count: INT              # how many matches stored
  status: TEXT                  # "COMPLETE" | "PARTIAL" | "PENDING"
}
```

**Result fields explained:**
- `result_90min`: The regulation result. D means draw after 90 min, even if someone later won in AET or pens. **This is the official hair index result** — a draw after 90 min breaks a winning streak.
- `result_final`: Who actually won/progressed. Useful for display ("won on penalties") and for the lenient/fan interpretation. A team with 5 consecutive `result_final = W` where one was on penalties gets a footnote: *"5 op een rij — maar eentje was na strafschoppen"*.
- Both fields make it trivial to compute either interpretation without re-parsing scores.

### 2.2 What We Need Per Team

A chronologically ordered list of all **competitive** match results (excluding friendlies), with:

- Date (for ordering)
- Result (W/D/L)
- Competition type (for filtering/display)

### 2.3 Scope & Search Strategy

The index looks **backward in time** per club until it finds the last 5-win streak. This means:

- **Variable depth per team**: PSV’s last streak is weeks old; NAC Breda’s might be years ago
- **No season boundary**: We look across seasons — a streak bridging May-August counts
- **All professional competitions**: Eredivisie, Eerste Divisie (for recently promoted/relegated teams), KNVB Cup, European competitions
- **Promoted teams**: Telstar returned to the Eredivisie after 47 years — their last streak might be in the KKD or even further back
- **The search stops** once we find the most recent 5-win streak per team; we don’t need every match in history, just enough to find it

**Practical implication**: For top clubs (PSV, Feyenoord, Ajax), the last 5-streak is almost certainly within the current season. For lower-table clubs, we may need to go back 1-3 seasons. For extreme cases, we might need deeper historical data.

**MVP:** Eredivisie 2025-26, all 18 teams, look back up to 3 seasons (2022-23 onward)
**V2:** Top European leagues (Premier League, La Liga, Bundesliga, Serie A, Ligue 1)
**V3:** Unlimited historical depth — find the streak no matter how far back it is

-----

## 3. Data Sources — Multi-Source Strategy

The goal is **complete match data for all competitions** a team plays in. No single free API covers everything, so we use multiple sources with a priority system. All data flows into the same SQLite database.

### 3.1 Source Priority

| Priority | Source | What it gives us | Cost | Rate Limit |
|----------|--------|-----------------|------|------------|
| 1 | **football-data.org** (v4) | Top leagues, CL, EL. The `/teams/{id}/matches` endpoint returns all competitions per team in one call. | Free tier available | 10 req/min |
| 2 | **API-Football** (via RapidAPI) | 1,200+ leagues incl. KNVB Beker, Eerste Divisie, Conference League, domestic cups for all countries. All competitions on all plans. | Free: 100 req/day. Pro $19/mo: 7,500 req/day | Varies by plan |
| 3 | **RSSSF.org** | Historical lower-league data (pre-2020 Eerste Divisie, old cup results). Published after season ends. Plain text, semi-structured. | Free (scrape/manual) | N/A |
| 4 | **Manual import** | For edge cases: Wikipedia season pages, official KNVB results. Last resort. | Free | N/A |

**Rule**: When a match exists in multiple sources, prefer the source with the most detail (penalty scores, AET info). The `UNIQUE(source, source_match_id)` constraint prevents duplicates within a source; cross-source dedup uses `(date, home_team_id, away_team_id)`.

### 3.2 Source 1: football-data.org (v4) — Primary

**API key**: Available (free tier)
**Base URL**: `https://api.football-data.org/v4`
**Auth**: Header `X-Auth-Token: {API_KEY}`

**Key Endpoints:**

|Endpoint                                                     |Purpose                                      |
|-------------------------------------------------------------|---------------------------------------------|
|`GET /competitions/DED/teams`                                |Get all Eredivisie team IDs                  |
|`GET /teams/{id}/matches?dateFrom=X&dateTo=Y&status=FINISHED`|All finished matches for a team in date range|
|`GET /competitions/DED/matches?season=2025`                  |All Eredivisie matches for a season          |
|`GET /competitions/DED/standings`                            |Current league table (for validation)        |

**Competition codes (free tier confirmed):**

|Code  |Competition       |Available |
|------|------------------|----------|
|`DED` |Eredivisie        |Yes       |
|`PL`  |Premier League    |Yes       |
|`BL1` |Bundesliga        |Yes       |
|`SA`  |Serie A           |Yes       |
|`PD`  |La Liga           |Yes       |
|`FL1` |Ligue 1           |Yes       |
|`ELC` |Championship      |Yes       |
|`CL`  |Champions League  |Yes       |
|`EC`  |European Champ.   |Yes       |

**Free tier gaps (CONFIRMED):**
- Domestic cups (KNVB Beker, FA Cup, DFB-Pokal, Copa del Rey) — **NOT on free tier** (requires paid: Standard €49/mo)
- Europa League, Conference League — **NOT on free tier** (requires paid)
- Eerste Divisie (KKD) — **NOT available** (even on paid tiers)
- Lower leagues — **NOT available**
- Paid tiers: Standard (25 competitions, €49/mo), Advanced (50, €99/mo), Pro (144, €249/mo)

**Extra time / penalty scoring (CONFIRMED):**
football-data.org v4 uses **incremental** scoring (not cumulative) — see [docs](https://docs.football-data.org/general/v4/overtime.html):
- `score.regularTime` = goals in 90 minutes only
- `score.extraTime` = goals scored *only* during extra time (not cumulative with 90 min)
- `score.penalties` = penalty shootout goals only
- `score.fullTime` = 90 min + extra time goals (cumulative)
- These fields appear when match `duration` is `EXTRA_TIME` or `PENALTY_SHOOTOUT`

**Match response includes:**
```json
{
  “utcDate”: “2025-10-26T17:45:00Z”,
  “status”: “FINISHED”,
  “competition”: { “code”: “DED”, “name”: “Eredivisie” },
  “homeTeam”: { “id”: 674, “name”: “PSV” },
  “awayTeam”: { “id”: 675, “name”: “Feyenoord” },
  “score”: {
    “fullTime”: { “home”: 3, “away”: 2 },
    “halfTime”: { “home”: 1, “away”: 0 },
    “regularTime”: { “home”: 2, “away”: 2 },
    “penalties”: { “home”: 4, “away”: 3 }
  }
}
```

**Mapping to our model (CONFIRMED — scores are incremental):**
- `home_goals_90min` / `away_goals_90min` = `score.regularTime` (always present for cup matches with AET). For league matches: `score.fullTime` (no AET possible)
- `home_goals_final` / `away_goals_final` = `score.fullTime` (= 90 min + extra time, cumulative)
- `home_goals_penalties` / `away_goals_penalties` = `score.penalties` (NULL if no shootout)
- `decided_in` = based on match `duration` field: `REGULAR` / `EXTRA_TIME` / `PENALTY_SHOOTOUT`
- `result_90min` = compare `regularTime` home vs away. This is what we need for the official index.
- `result_final` = if penalties: winner of penalty shootout. else: compare `fullTime` scores.

### 3.3 Source 2: API-Football (via RapidAPI) — Cups & Lower Leagues

**Why**: Covers what football-data.org misses — domestic cups, Conference League, Eerste Divisie, and lower divisions across Europe.

**Coverage verified**: 1,200+ leagues including:
- KNVB Beker (Dutch Cup)
- Eerste Divisie / Keuken Kampioen Divisie
- FA Cup, EFL Cup (England)
- DFB-Pokal (Germany)
- Copa del Rey (Spain)
- Coppa Italia
- Coupe de France
- Conference League
- Europa League

**Key endpoints:**
- `GET /fixtures?team={id}&season={year}` — all matches for a team
- `GET /fixtures?league={id}&season={year}` — all matches in a competition
- Response includes `score.fulltime`, `score.extratime`, `score.penalty`

**Usage strategy:**
- **Don't duplicate**: Only fetch from API-Football what football-data.org doesn't have
- **fill_gaps.py** queries `data_sources` table for competitions with status = PENDING, then fetches only those from API-Football
- **Team ID mapping**: Store both `football_data_id` and `api_football_id` in the teams table. Build mapping once, reuse forever.
- **Free tier (100 req/day)**: All competitions available, but limited to recent seasons only. Enough for Eredivisie MVP gap-filling (~36 cup requests for 18 teams). For all European leagues: Pro plan ($19/mo, 7,500 req/day) or Mega ($39/mo, 150K req/day).
- **Score format**: `fulltime` = 90 min score, `extratime` and `penalty` are separate fields (NULL when not applicable). Maps cleanly to our model.

### 3.4 Source 3: RSSSF.org — Historical Lower Leagues

**What it is**: The Rec.Sport.Soccer Statistics Foundation. Volunteer-maintained archive of football results going back decades. Covers lower leagues that no API has.

**Format**: Plain text, semi-structured. Example:
```
Round 1  [Aug 10]
Telstar           1-0  Jong Ajax
Cambuur           2-1  De Graafschap
```

**Good for**: Finding the last 5-win streak for promoted teams whose streak might be in the Eerste Divisie 3+ years ago, before API-Football's historical coverage.

**How we use it:**
- `import_rsssf.py` — semi-automated parser for RSSSF season pages
- Only used for backfilling historical data that APIs don't cover
- Results imported with `source = “rsssf”` so we know the provenance
- **Not needed for MVP** — only kicks in when a team's streak can't be found via APIs

### 3.5 Bonus Source: football-data.co.uk — Bulk Historical CSV

Free CSV downloads for major European leagues (including Eredivisie) going back to the 1990s. English leagues down to Conference level. Updated weekly. No API — just download CSVs. Includes betting odds data.

**Good for**: Quickly bootstrapping historical league-only data for many seasons. Doesn't include cups or lower Dutch leagues, but useful as a validation source and for seeding the database with older league results.

### 3.5 Fetch Strategy: First Run vs Daily Updates

**First run (one-time, longer):**
```
1. Fetch all Eredivisie team IDs from football-data.org
2. For each team: fetch ALL matches for current season + 2 previous seasons
   - football-data.org: league + European (what's available on free tier)
   - API-Football: domestic cup + any competitions missing from source 1
3. For teams with no 5-streak found: go deeper (season by season) via API-Football
4. For extreme cases (promoted from KKD): try RSSSF for historical lower league data
5. Populate data_sources table with status for every (source, competition, season) combo
```

**Daily updates (fast):**
```
1. For current season only:
   - Fetch new matches from football-data.org (since last_fetched)
   - If cup matches are in progress: fetch from API-Football too
2. Re-compute streaks
3. Export hair_index.json
4. ~20 API calls, ~2 minutes
```

**Async gap-filling (runs separately, not blocking):**
```
- fill_gaps.py checks data_sources for status = PARTIAL or PENDING
- Fetches missing competition data from API-Football
- Can be triggered manually or via weekly cron
- Example: “We have Feyenoord's Eredivisie matches but not their KNVB Beker results for 2024-25”
```

### 3.6 API Request Budget

```
First run (Eredivisie, 18 teams, 3 seasons):
  football-data.org:
    GET /competitions/DED/teams                     = 1 request
    18 teams × 3 seasons × /teams/{id}/matches      = 54 requests (6 min at 10/min)
    GET /competitions/DED/standings                  = 1 request
  API-Football (gap-filling cups):
    18 teams × ~2 cup seasons × /fixtures            = ~36 requests
  Total: ~92 requests, ~10 minutes

Daily update:
  football-data.org: 18 teams × 1 request           = 18 requests (2 min)
  API-Football: only if cup matches played           = ~2-5 requests
  Total: ~23 requests, ~2 minutes
```

### 3.7 Resilience

- **Completed seasons are immutable** — once fully fetched, never re-fetch. Only current (in-progress) season needs updates.
- **Rate limit handling**: If HTTP 429, back off exponentially (6s → 12s → 24s).
- **API downtime fallback**: Serve last computed `hair-index.json`. Display “last updated” timestamp.
- **Data validation**: After each fetch, verify match counts are plausible. Flag anomalies.
- **Graceful degradation**: If a source is down, compute streaks with available data. Mark teams with incomplete data. The index still works — it just might have a footnote “cup results pending.”

-----

## 4. Streak Calculation Logic

### 4.1 Algorithm

```python
def find_last_5_streak(team_id: str, api_client) -> dict:
    """
    Search backward through a team’s match history until we find
    the most recent 5-win streak.

    Strategy:
    1. Fetch current season matches, sort chronologically
    2. Scan from most recent match backward, counting consecutive wins
    3. If streak >= 5 found, record it and stop
    4. If no 5-streak in current season, fetch previous season
    5. IMPORTANT: carry partial streak across season boundary
       (e.g. if the current season starts W W W, check if the
       previous season ended with wins to extend the streak)
    6. Keep going back until found or data runs out

    Returns: {
        "team": str,
        "team_id": int,
        "found": bool,
        "streak_end_date": Date | None,     # date of the LAST win in the streak
        "streak_start_date": Date | None,   # date of the 1st win in the streak
        "streak_length": int,               # might be > 5
        "days_since": int,                  # calendar days from streak_end_date to today
        "matches_since": int,               # competitive matches played since streak ended
        "competitions_in_streak": List[str], # e.g. ["Eredivisie", "KNVB Cup"]
        "search_depth": str,                # earliest season searched, e.g. "2023-24"
        "current_form": List[str],          # last 10 results, e.g. ["W","L","W","D",...]
    }
    """
```

The key insight: we search **backward from today**, and we stop as soon as we find a 5-win streak. For PSV that’s a few weeks of data. For Telstar it might be years.

**Important clarification on "backward search":** We fetch season data chronologically (the API returns matches in date order), but we process seasons from most recent to oldest. Within each season, we scan from the latest match backward to find streaks. This is more efficient than a true reverse scan because the API doesn’t support reverse ordering.

### 4.2 Hair Length Metric

The metric is **calendar days since the date of the 5th consecutive win** (i.e. the date the streak was “completed”). This makes it comparable across leagues and competitions with different schedules.

```
hair_length = (today - streak_end_date).days

Tiers (canonical — used for both display and portrait generation):
- 0-14 days:     💇 "Fresh cut" — just completed a 5-streak
- 15-60 days:    ✂️ "Growing back"
- 61-120 days:   💈 "Getting shaggy"
- 121-270 days:  🦁 "Long & wild"
- 271-500 days:  🧔 "Caveman"
- 500+ days:     🧌 "Sasquatch"
- Not found:     ❓ "Lost in time" (need deeper historical data)
```

**Note**: The further back we look, the funnier the metric gets. A team whose last 5-win streak was in 2019 produces “their fans haven’t had a haircut in 6 years.”

### 4.3 Edge Cases

- **Cross-season streaks**: A streak bridging two seasons counts (e.g. 3 wins at end of 24/25 + 2 wins at start of 25/26 = 5)
- **Summer break gap**: The wins must be consecutive competitive matches — a 2-month gap between seasons is fine as long as no competitive match broke the streak
- **Mid-week matches**: A team playing Wed + Sat builds/breaks streaks faster
- **European teams** get more chances to build streaks but also more chances to break them
- **Extra time & penalty shootout results**: Treated as special cases. We store two results per match:
  - `result_90min`: The regulation result. AET or penalty matches are a **D** after 90 min. **This is the official index.**
  - `result_final`: Who progresses. AET win = **W** for the winner. Penalty win = **W** for the winner.
  - The official hair index uses `result_90min`. But if a team's 5-streak only exists when using `result_final`, we highlight that with a footnote — e.g. *"5 op een rij — maar eentje was na strafschoppen"*. Great for debate.
  - **Note**: Extra time wins only occur in cup/knockout matches, never in league. So this only matters when cup results are part of the streak.
- **Walkovers/forfeits**: Count as W or L per official result
- **Promoted teams**: Search continues into lower division data (Eerste Divisie etc.)
- **Relegated teams**: Their Eredivisie streak history still counts — search stops at the last 5-streak regardless of division
- **Search depth limit**: If no 5-streak found within available data, mark as “not found” with the earliest date searched. This is an honest “we don’t know” rather than a false “never”

-----

## 5. Frontend / Visualization

### 5.1 The Page: Hair Length Index Ranking

A single-page app showing all teams ranked by “hair length” (days since last 5-win streak), longest first.

**Per team row:**

- AI-generated supporter portrait (see 5.2)
- Team crest + name
- Days since last 5-streak (the headline number)
- Date of last 5-streak (“12 januari 2026”)
- Competition the streak was in (“Eredivisie + KNVB Cup”)
- Current form (last 5-10 matches as W/D/L colored dots)
- A one-liner quote, e.g. *“PSV-fans zijn net bij de kapper geweest”* or *“Telstar-supporters herkennen hun eigen familie niet meer”*

**Sorting:** Longest hair first (highest number of days). The “just got a haircut” teams are at the bottom.

### 5.2 AI-Generated Supporter Portraits

The hero visual: per team, an AI-generated image of a supporter in club shirt, with hair/beard length matching their score.

**Style:** Consistent editorial illustration / slightly cartoonish. NOT photorealistic — keep it humorous, warm, and shareable. Think Pixar-adjacent or editorial caricature.

**Template prompt structure:**

```
A [hair_description] football supporter wearing a [team] shirt 
([color_description]), portrait style, [emotion], 
editorial illustration style, warm lighting, 
white/simple background, slightly exaggerated features
```

**Hair length tiers (5-6 visual levels):**

|Tier            |Days Since|Hair Description                                        |Emotion                     |
|----------------|----------|--------------------------------------------------------|----------------------------|
|💇 Fresh Cut     |0-14      |Clean buzzcut, fresh fade, smooth shaven                |Smiling, relieved, confident|
|✂️ Growing Back  |15-60     |Short neat hair, hint of stubble                        |Content, relaxed            |
|💈 Getting Shaggy|61-120    |Messy medium-length hair, visible beard                 |Slightly worried, hopeful   |
|🦁 Long & Wild   |121-270   |Long unkempt hair past shoulders, full beard            |Frustrated, desperate       |
|🧔 Caveman       |271-500   |Very long tangled hair, huge bushy beard, wild eyes     |Haunted, exhausted          |
|🧌 Sasquatch     |500+      |Hair and beard merge, barely human, leaves/twigs in hair|Feral, lost all hope        |

**Per team, vary:**

- Club shirt colors and design (primary + secondary colors, sponsor)
- Supporter “type” (vary age, build — keep it inclusive)
- Small team-specific touches (e.g. Ajax supporter with three X’s somewhere, PSV with Philips Stadion vibe)

**Generation approach:**

- Pre-generate all 18 images at current hair length
- Store in `/assets/portraits/`
- Re-generate only when a team’s tier changes (= they complete a 5-streak or cross a tier boundary)
- **Tool**: Use an image generation API (DALL-E, Midjourney, Flux) with consistent style prompt + seed for reproducibility

**Image count:** 18 teams × 1 image = 18 images for Eredivisie MVP. When expanding to 6 leagues: ~120 images total.

### 5.3 Social Sharing

Each team’s card should be individually shareable as a social image:

- Portrait + team name + days count + one-liner
- Formatted for Twitter/X (1200×675) and Instagram Stories (1080×1920)
- Auto-generated via a template overlay on the AI portrait

Example share text:

> 🧔 Telstar-supporters hebben al 847 dagen geen kapper gezien.
> De laatste keer dat Telstar 5x op een rij won was op 14 november 2023.
> #HairLengthIndex #Eredivisie

### 5.4 Teams to Watch ("Bijna bij de Kapper")

A highlighted section on the page showing teams that are **close to getting a haircut** — long drought but currently on a hot streak.

**Selection criteria:**
- Team has a high `days_since` (long drought, e.g. > 120 days / "Getting shaggy" tier or worse)
- Current form shows a winning streak of **3 or 4** consecutive wins (from `current_form`)
- i.e., they need just 1-2 more wins to complete a 5-streak and "visit the barber"

**Why this is compelling:**
- Creates narrative tension: "Telstar hasn't won 5 in a row in 847 days, but they're on a 4-match streak right now…"
- Gives visitors a reason to come back and check after the next match day
- Natural social sharing hook: "Will [team] finally get a haircut this weekend?"

**Data needed:** Already available — `current_form` (last 10 results) and `days_since` are in `hair-index.json`. The frontend just needs to filter:
```python
teams_to_watch = [
    t for t in index
    if t["days_since"] and t["days_since"] > 120  # shaggy or worse
    and len(t["current_form"]) >= 3
    and all(r == "W" for r in t["current_form"][:3])  # last 3+ are wins
]
```

**Display:** A card/banner above or below the main table:
- "🔥 **Bijna bij de kapper!**" header
- Team crest + name + current streak length + "nog X te gaan"
- Link to the team's next fixture if available

### 5.5 Match Highlights (YouTube Integration)

Link YouTube match highlight videos ("samenvattingen") to individual results in a team's form display or match history.

**Feasibility: HIGH** — Eredivisie highlights are widely available on YouTube:
- **ESPN NL / Eredivisie official** channels publish "samenvatting" videos within hours of each match
- Video titles follow a predictable pattern: `{Home} - {Away} | Samenvatting | Eredivisie 2025-26`
- International highlights channels cover big matches (CL, EL)

**Search strategy:**
```
Query: "{home_team} {away_team} samenvatting {season}"
Filter: regionCode=NL, recency=pastMonth, maxResults=3
Match: pick the result with highest view count or from a known channel
```

**Known highlight channels (Eredivisie):**
- ESPN NL (official Eredivisie broadcaster)
- NOS Sport (public broadcaster, shorter clips)
- For CL/EL: UEFA official, CBS Sports Golazo

**Implementation approach:**
1. **`scripts/fetch_highlights.py`** — new script, runs after `compute_streaks.py`
   - For each match in the last 7 days: search YouTube API for highlights
   - Store `youtube_video_id` in a new `match_highlights` table (or column on `matches`)
   - Cache aggressively — a match's highlight URL never changes
2. **YouTube Data API quota:** Search costs 100 units/call, daily limit = 10,000 units
   - 18 teams × ~2 matches/week = ~36 searches/week = ~5/day → well within budget
   - Only search for matches in the last 7 days (highlights are uploaded within 24h)
   - Cache forever once found — never re-search a match
3. **Frontend:** Each W/D/L dot in the form display becomes clickable → opens YouTube highlight
4. **Fallback:** If no highlight found, the dot is not clickable. No broken links.

**Data model addition:**
```sql
ALTER TABLE matches ADD COLUMN highlight_url TEXT;  -- YouTube video URL
ALTER TABLE matches ADD COLUMN highlight_fetched DATETIME;  -- when we last searched
```

**Privacy/legal:** We're only linking to publicly available YouTube videos, not embedding or downloading. Standard practice, same as any sports news site.

**Phase:** V2 feature — not needed for MVP, but high engagement potential. Fans love clicking through to watch the goals that built (or broke) a streak.

### 5.6 V2: Timeline & Animation (was 5.4)

- **Hair growth timeline**: Slider showing how each team’s hair evolved over the season. Every match day, hair grows or resets.
- **“Barber alert”**: Push notification / social post when a team completes a 5-streak: “🎉 Ajax is eindelijk naar de kapper geweest!”
- **Comparison mode**: Pick 2-3 teams, overlay their streak timelines
- **League selector**: Switch between Eredivisie, PL, La Liga, etc.

### 5.7 V3: Pan-European Hair Salon (was 5.5)

- “Longest hair in Europe” — overall ranking across all leagues
- Side-by-side league comparison (which league has the shaggiest fans?)
- Historical deep dive: “When was the last time [team] won 5 in a row?”

-----

## 6. Technical Architecture

### 6.1 Stack (MVP)

```
Data Layer:
├── SQLite database: data/hair-index.db
│   ├── matches table (all results, all sources, all competitions)
│   ├── teams table (metadata, cross-source IDs)
│   └── data_sources table (tracks what we've fetched and when)
├── Python scripts:
│   ├── fetch_matches.py    — pulls from APIs, upserts into SQLite
│   ├── compute_streaks.py  — queries SQLite, outputs hair_index.json
│   ├── fill_gaps.py        — async backfill for cups/lower leagues
│   └── validate_data.py    — cross-check with known standings
├── Runs daily via cron/GitHub Actions
│
Frontend:
├── Single React component or static HTML
├── Reads hair_index.json (exported from SQLite)
├── Renders the index table + visuals
└── Hosted on Cloudflare Pages / GitHub Pages / Vercel
```

### 6.2 Data Storage: SQLite from Day 1

**Why SQLite, not flat JSON:**
- **Deduplication**: `UNIQUE(source, source_match_id)` prevents double-counting when importing from multiple sources
- **Incremental updates**: Upsert new matches without re-fetching everything. Only query "what's new since last fetch?"
- **Cross-source merging**: A match might come from football-data.org (league) and api-football (with penalty detail). SQLite makes it easy to merge/prefer sources
- **Gap detection**: `SELECT * FROM data_sources WHERE status = 'PENDING'` instantly shows what's missing
- **Query flexibility**: "Show me all Feyenoord results across all competitions sorted by date" is one SQL query, not parsing 15 JSON files
- **Portable**: Single file, committed to git, works everywhere, no server needed

**The database file `data/hair-index.db` is committed to git.** It's small (a few MB even with all European leagues) and gives anyone who clones the repo immediate access to all data.

**Daily update flow:**
```
1. fetch_matches.py:
   - For each (source, competition, season) in data_sources where status != COMPLETE:
     - Fetch new matches since last_fetched
     - UPSERT into matches table
     - Update data_sources.last_fetched
   - Current season: always re-fetch (new matches played)
   - Past seasons: skip if status = COMPLETE

2. fill_gaps.py (runs separately, not blocking):
   - Check which teams still need cup/European/lower league data
   - Fetch from secondary sources (api-football, manual import)
   - Mark gaps as filled in data_sources

3. compute_streaks.py:
   - For each team: SELECT all matches ORDER BY date DESC
   - Scan for 5-win streaks using result_90min (official) and result_final (fan)
   - Flag teams with incomplete data (missing competitions)
   - Output hair_index.json for frontend
```

### 6.3 File Structure

```
hair-length-index/
├── data/
│   ├── hair-index.db                     # SQLite — the single source of truth
│   └── hair-index.json                   # exported for frontend (generated, not edited)
├── scripts/
│   ├── fetch_matches.py                  # API data fetcher → SQLite
│   ├── fill_gaps.py                      # async backfill for cups/lower leagues
│   ├── compute_streaks.py                # streak calculator (reads SQLite, writes JSON)
│   ├── validate_data.py                  # cross-check with known standings
│   ├── import_rsssf.py                   # manual/semi-auto import from RSSSF
│   └── config.py                         # API keys, league IDs, source priorities
├── frontend/
│   ├── index.html / App.jsx
│   ├── components/
│   │   ├── HairIndex.jsx                 # main table
│   │   ├── TeamRow.jsx                   # single team display
│   │   ├── StreakTimeline.jsx            # visual timeline
│   │   └── HairVisual.jsx               # the fun hair illustration
│   └── styles/
├── .github/
│   └── workflows/
│       └── update-data.yml               # daily data refresh
└── README.md
```

-----

## 7. Implementation Plan

### Phase 1: Database & Primary Data (Day 1-2)

1. **Set up SQLite schema** (30 min):
   - Create `data/hair-index.db` with matches, teams, data_sources tables
   - Write `scripts/db.py` — shared database module with upsert helpers
2. **Explore & verify APIs** (1h):
   - football-data.org: test free tier coverage (does it include KNVB Cup? EL? Conference League?)
   - API-Football: test free tier, confirm KNVB Beker and Eerste Divisie are available
   - Document what each source actually returns for a cup match with penalties
3. **Write `fetch_matches.py`** — primary data pipeline:
   ```
   for each team in teams table:
     for each season (current → 3 seasons back):
       fetch /teams/{id}/matches from football-data.org
       upsert into matches table
       update data_sources table (last_fetched, match_count, status)
   ```
   Rate limit: sleep 6s between requests (10 req/min limit).
4. **Write `compute_streaks.py`**:
   - Query SQLite: all matches per team, ordered by date DESC
   - Compute streaks using `result_90min` (official) and `result_final` (fan)
   - Flag teams where data is incomplete (missing competitions)
   - Output `data/hair-index.json`
5. **Write `validate_data.py`**:
   - Fetch `/competitions/DED/standings`
   - Compare computed league W/D/L/Pts with official standings
   - Report discrepancies
6. **First full run**: Execute pipeline, verify against known PSV and Feyenoord data

### Phase 1b: Gap Filling (Day 2-3, non-blocking)

1. **Write `fill_gaps.py`**:
   - Query data_sources for competitions with status = PENDING
   - Fetch missing cup/European data from API-Football
   - Upsert into same matches table
2. **Write `import_rsssf.py`** (if needed):
   - Parser for RSSSF plain-text season pages
   - Only used for historical lower-league data where APIs have no coverage
3. **Team ID mapping**: Build and maintain cross-source ID map (football-data.org ↔ API-Football)

### Phase 2: Frontend MVP (Day 3-4)

1. Build React app with the Hair Length Index table
1. Team crests from a public source (e.g., football-data.org)
1. Simple hair/beard visual (CSS-based or SVG)
1. Deploy to Cloudflare Pages

### Phase 3: Automation (Day 5)

1. GitHub Actions workflow: daily fetch + compute + commit
1. Frontend auto-deploys on data change

### Phase 4: Polish & Expand (Week 2+)

1. Add Premier League, La Liga, etc.
1. Historical data (previous seasons)
1. Social sharing cards
1. Animated hair growth timeline
1. “Barber Shop” — shows which teams just “got a haircut” (just completed a 5-streak)

-----

## 8. Verified Data (What We Know So Far)

From our research session, we have **verified** W/D/L sequences for two teams:

### PSV Eindhoven (Eredivisie only, rounds 1-23)

```
W W W L W D W W W W W W W W W W W W D W W W L
Max streak: 13 (rounds 7-19)
```

Source: Wikipedia 2025-26 PSV Eindhoven season page

### Feyenoord (Eredivisie only, rounds 1-25)

```
W W W W W D W W W L W L L W W L D D L W L W W W L
Max streak: 5 (rounds 1-5)
```

Source: Wikipedia 2025-26 Feyenoord season page

### Key Insight

These are Eredivisie-only. For the full Hair Length Index (all competitions), we need to interleave cup and European results chronologically. Both PSV and Feyenoord played CL/EL matches between league rounds, which could affect their streaks significantly.

-----

## 9. Open Questions

1. **Streak threshold**: 5 is the Man United reference — do we also show alternative thresholds (3, 7, 10) as toggles?
1. ~~**Penalty shootouts**~~: RESOLVED — `result_90min` (D after 90 min) is the official index. `result_final` (who progresses) stored alongside for the fan/lenient view. Footnote when it matters.
1. **How deep do we go?** If a team has NEVER won 5 in a row in their professional history… do we show that? (Could be powerful for lower-league teams)
1. **Friendly matches**: Excluded for sure, but what about pre-season tournaments with prize money?
1. **Update frequency**: Real-time during match days, or daily batch? (Daily is fine for the hair metaphor — hair doesn’t grow by the minute)
1. **Relegated teams appearing in index**: If we show Eredivisie, do we include teams that got relegated mid-history? Or only current members?
1. **The “barber visit” moment**: Should we send notifications / post on social when a team completes a 5-streak? “🎉 Ajax finally got a haircut!”
1. **API-Football free tier**: 100 req/day — enough for Eredivisie MVP gap-filling. Pro plan ($19/mo) needed when scaling to all European leagues.
1. ~~**football-data.org `regularTime` field**~~: RESOLVED — Confirmed via [docs](https://docs.football-data.org/general/v4/overtime.html). The API uses incremental scoring: `regularTime` = 90 min, `extraTime` = AET only, `penalties` = shootout only, `fullTime` = 90 min + AET cumulative. Both sources (football-data.org and API-Football) give us what we need for `result_90min` and `result_final`.

-----

## 10. MVP Definition of Done

The MVP is shippable when all of the following are true:

- [ ] SQLite database with matches, teams, data_sources tables
- [ ] `fetch_matches.py` populates matches for all 18 Eredivisie teams (league data from football-data.org)
- [ ] `fill_gaps.py` adds cup/European matches from API-Football (or marks as pending)
- [ ] `compute_streaks.py` correctly identifies the last 5-win streak (or “not found”) for each team, using both `result_90min` and `result_final`
- [ ] `validate_data.py` confirms 0 discrepancies with official league standings
- [ ] `hair-index.json` is generated with all required fields per team
- [ ] Teams with incomplete data are flagged (not silently wrong)
- [ ] Frontend renders the Hair Length Index table, sorted longest-first
- [ ] Each team row shows: crest, name, days since streak, date of streak, current form
- [ ] GitHub Actions workflow runs daily and commits updated data
- [ ] Deployed and publicly accessible

-----

## 11. Success Metrics

- **Accuracy**: 0 discrepancies between our computed league W/D/L/Pts and official standings (automated validation on every run)
- **Coverage**: All competitive matches (league + cup + European where available) for all 18 Eredivisie teams
- **Freshness**: Data updated within 24h of last match day
- **Reliability**: Pipeline runs successfully >95% of days (accounting for API downtime)
- **Engagement**: Social sharing, Reddit/Twitter/Mastodon pickup — track via share button clicks and referral traffic
- **Virality potential**: “Ajax fans haven’t had a haircut since [date]” is inherently shareable
