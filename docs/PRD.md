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
  match_id: int                # football-data.org match ID (for deduplication)
  date: Date
  home_team: string
  away_team: string
  home_team_id: int            # football-data.org team ID (for reliable matching)
  away_team_id: int
  home_goals: int
  away_goals: int
  result_strict: enum [HOME_WIN, AWAY_WIN, DRAW]   # based on score after 90 min (AET/pens = DRAW)
  result_lenient: enum [HOME_WIN, AWAY_WIN, DRAW]  # AET/penalty win counts as WIN
  decided_in: enum [REGULAR, EXTRA_TIME, PENALTIES] # how the match was decided
  competition: enum [LEAGUE, DOMESTIC_CUP, CHAMPIONS_LEAGUE, EUROPA_LEAGUE, CONFERENCE_LEAGUE, SUPER_CUP, FRIENDLY]
  round: string (optional — e.g. "Matchday 14", "Round of 16")
  season: string (e.g. "2025-26")
}
```

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

## 3. Data Source: football-data.org API (v4)

### 3.1 Why This Works

The **`/v4/teams/{id}/matches`** endpoint is ideal: it returns all matches for a team across ALL competitions (league, cup, European) in one call, filterable by date range. This maps directly to our backward-search algorithm.

**API key**: Available (free tier)
**Rate limit**: 10 requests/minute
**Base URL**: `https://api.football-data.org/v4`
**Auth**: Header `X-Auth-Token: {API_KEY}`

### 3.2 Key Endpoints

|Endpoint                                                     |Purpose                                      |Example                                |
|-------------------------------------------------------------|---------------------------------------------|---------------------------------------|
|`GET /competitions/DED/teams`                                |Get all Eredivisie team IDs                  |Returns 18 teams with IDs              |
|`GET /teams/{id}/matches?dateFrom=X&dateTo=Y&status=FINISHED`|All finished matches for a team in date range|Returns league + cup + European matches|
|`GET /competitions/DED/matches?season=2025`                  |All Eredivisie matches for a season          |Backup: league-only data               |
|`GET /competitions/DED/standings`                            |Current league table                         |For validation                         |

### 3.3 Competition Codes

|Code  |Competition                                         |
|------|----------------------------------------------------|
|`DED` |Eredivisie                                          |
|`PL`  |Premier League                                      |
|`BL1` |Bundesliga                                          |
|`SA`  |Serie A                                             |
|`PD`  |La Liga                                             |
|`FL1` |Ligue 1                                             |
|`CL`  |Champions League                                    |
|`EL`  |Europa League (check if available on free tier)     |
|`ECL` |Conference League (check if available on free tier) |
|`KNVB`|KNVB Cup (may not be available — needs verification)|

### 3.4 Free Tier Limitations to Verify

- **Which competitions are included?** The free tier may not include domestic cups or lower European competitions (Conference League). Need to test.
- **Historical depth**: Can we query `?season=2023` for matches 2-3 years back?
- **Eerste Divisie**: Probably NOT available — this affects promoted teams like Telstar whose last 5-streak might be in the KKD. For those, we note “not found in available data.”

### 3.5 API Request Budget (per run)

```
Step 1: Get all team IDs
  GET /competitions/DED/teams                          = 1 request

Step 2: For each team, fetch current season matches
  GET /teams/{id}/matches?dateFrom={season_start}&dateTo={today}&status=FINISHED
  18 teams × 1 request                                = 18 requests

Step 3: For teams without a 5-streak, fetch previous season
  GET /teams/{id}/matches?dateFrom={prev_start}&dateTo={prev_end}&status=FINISHED
  ~8 teams × 1 request                                = 8 requests

Step 4: If still not found, go back another season
  ~3 teams × 1 request                                = 3 requests

Step 5: Validate against standings
  GET /competitions/DED/standings                      = 1 request

Total: ~31 requests
At 10 req/min, this takes ~3 minutes with 6s sleep between requests.
```

### 3.6 Caching & Resilience

- **Cache raw API responses** in `data/raw/` keyed by team ID and date range. Only re-fetch if the cached data is older than 24h.
- **Completed seasons are immutable** — once 2024-25 is fully fetched, never re-fetch it. Only the current (in-progress) season needs daily updates.
- **Rate limit handling**: If the API returns HTTP 429, back off exponentially (6s → 12s → 24s). Log and alert on repeated failures.
- **API downtime fallback**: If the API is unreachable, serve the last successfully computed `hair-index.json`. The frontend should display a "last updated" timestamp so users know the data age.
- **Data validation**: After each fetch, verify that the number of matches is plausible (e.g., a team mid-season should have 15-40 matches, not 0 or 500). Flag anomalies rather than silently using bad data.

### 3.7 Match Response Structure (what we extract)

```json
{
  "utcDate": "2025-10-26T17:45:00Z",
  "status": "FINISHED",
  "competition": { "code": "DED", "name": "Eredivisie" },
  "homeTeam": { "id": 674, "name": "PSV" },
  "awayTeam": { "id": 675, "name": "Feyenoord" },
  "score": {
    "fullTime": { "home": 3, "away": 2 },
    "halfTime": { "home": 1, "away": 0 }
  }
}
```

From this we derive: date, opponent, home/away, result (W/D/L), competition, and score.

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
- **Extra time & penalty shootout results**: These are treated as special cases rather than plain W or D. Strictly speaking, a match decided in extra time or on penalties is not a regulation win. However, fans absolutely experience these as wins. We compute streaks **both ways** (strict: AET/penalties = Draw; lenient: AET = Win, penalties = Win) and compare. If a team's 5-streak only exists under the lenient interpretation, we highlight that — e.g. *"Feyenoord heeft 5 op een rij* gewonnen, maar alleen als je verlenging meetelt*"*. This makes for a great talking point and lets fans argue about it, which is exactly what we want.
  - **Implementation**: Store a `result_strict` (90 min only; AET/pens = Draw) and `result_lenient` (AET win = Win, penalty win = Win) per match. Compute two streak values. Display the strict one by default with a toggle or footnote for the lenient version.
  - **API mapping**: Use `score.fullTime` for the strict result. If `score.fullTime` is a draw but the match has a `score.penalties` field, the lenient result is a Win for the advancing team.
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

### 5.4 V2: Timeline & Animation

- **Hair growth timeline**: Slider showing how each team’s hair evolved over the season. Every match day, hair grows or resets.
- **“Barber alert”**: Push notification / social post when a team completes a 5-streak: “🎉 Ajax is eindelijk naar de kapper geweest!”
- **Comparison mode**: Pick 2-3 teams, overlay their streak timelines
- **League selector**: Switch between Eredivisie, PL, La Liga, etc.

### 5.5 V3: Pan-European Hair Salon

- “Longest hair in Europe” — overall ranking across all leagues
- Side-by-side league comparison (which league has the shaggiest fans?)
- Historical deep dive: “When was the last time [team] won 5 in a row?”

-----

## 6. Technical Architecture

### 6.1 Stack (MVP)

```
Data Layer:
├── Python script: fetch_matches.py
│   ├── Calls football API
│   ├── Stores raw match data as JSON
│   └── Runs daily via cron/GitHub Actions
├── Python script: compute_streaks.py
│   ├── Reads match JSON
│   ├── Computes streaks per team
│   └── Outputs hair_index.json
│
Frontend:
├── Single React component or static HTML
├── Reads hair_index.json
├── Renders the index table + visuals
└── Hosted on Cloudflare Pages / GitHub Pages / Vercel
```

### 6.2 Data Storage

MVP: Flat JSON files in a git repo, updated daily
V2: SQLite or Supabase for historical queries
V3: Proper database with multi-season data

### 6.3 File Structure

```
hair-length-index/
├── data/
│   ├── raw/
│   │   ├── eredivisie-2025-26.json      # raw match results
│   │   ├── premier-league-2025-26.json
│   │   └── ...
│   ├── processed/
│   │   ├── streaks-eredivisie.json       # computed streak data
│   │   └── hair-index.json              # final index for frontend
│   └── teams.json                        # team metadata (name, crest URL, league)
├── scripts/
│   ├── fetch_matches.py                  # API data fetcher
│   ├── compute_streaks.py                # streak calculator
│   ├── validate_data.py                  # cross-check with known standings
│   └── config.py                         # API keys, league IDs
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

### Phase 1: Data Pipeline (Day 1-2)

1. **Explore the API** (30 min):
   - Hit `/competitions/DED/teams` to get all 18 Eredivisie team IDs
   - Hit `/teams/{psv_id}/matches` to see the exact response format
   - Test: does the free tier include KNVB Cup and European matches?
   - Test: how far back can we query? (`?season=2023`)
2. **Write `fetch_matches.py`** — smart backward search:

   ```
   for each team:
     season = current
     streak_found = False
     while not streak_found and season >= 2022:
       fetch /teams/{id}/matches?season={season}&status=FINISHED
       scan for 5-win streaks (most recent match backward)
       if found: record it, break
       else: carry partial streak, go to previous season
   ```

   Rate limit: sleep 6s between requests (10 req/min limit).
   Store raw JSON per team in `data/raw/`.
3. **Write `compute_streaks.py`**:
   - Read raw match data per team
   - Build chronological match list across all competitions
   - Find last 5-win streak (scanning backward from most recent match)
   - Calculate days since (hair length)
   - Output `data/processed/hair-index.json`
4. **Write `validate_data.py`**:
   - Fetch `/competitions/DED/standings`
   - Compare our computed league W/D/L/Pts with official standings
   - Report discrepancies
5. **First full run**: Execute pipeline, verify results against our known PSV and Feyenoord data from Wikipedia

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
1. **Penalty shootouts**: Official result is a draw — confirm this interpretation. Some argue “advancing” = a win for fans, but the match result is a draw.
1. **How deep do we go?** If a team has NEVER won 5 in a row in their professional history… do we show that? (Could be powerful for lower-league teams)
1. **Friendly matches**: Excluded for sure, but what about pre-season tournaments with prize money?
1. **Update frequency**: Real-time during match days, or daily batch? (Daily is fine for the hair metaphor — hair doesn’t grow by the minute)
1. **Relegated teams appearing in index**: If we show Eredivisie, do we include teams that got relegated mid-history? Or only current members?
1. **The “barber visit” moment**: Should we send notifications / post on social when a team completes a 5-streak? “🎉 Ajax finally got a haircut!”

-----

## 10. MVP Definition of Done

The MVP is shippable when all of the following are true:

- [ ] `fetch_matches.py` retrieves match data for all 18 Eredivisie teams from the API
- [ ] `compute_streaks.py` correctly identifies the last 5-win streak (or “not found”) for each team
- [ ] `validate_data.py` confirms 0 discrepancies with official league standings
- [ ] `hair-index.json` is generated with all required fields per team
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
