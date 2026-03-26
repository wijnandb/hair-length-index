# Video Content Plan — Head-to-Head Streak Animation

## Concept

Two supporters side by side. Each match result ticks by. Hair grows. W's stack up.
First to 5 in a row → HAIRCUT! The other keeps growing into a sasquatch.

## Visual Layout

```
┌─────────────────────────────────────────────┐
│                                             │
│   [Ajax Supporter]    vs    [Feyenoord]     │
│   👨 Fresh cut              🧔 Caveman      │
│                                             │
│   W W W                                     │
│   97 dagen                  326 dagen       │
│                                             │
│   Volgende: Ajax - PSV      NAC - Feyenoord │
│                                             │
│         hairlengthindex.nl                  │
└─────────────────────────────────────────────┘
```

## Per-Frame Data

Each "frame" = one match for either team (chronological, interleaved):

```json
{
  "frame": 1,
  "team": "Ajax",
  "date": "2025-09-17",
  "opponent": "PSV",
  "opponent_crest": "url",
  "result": "W",
  "score": "2-1",
  "days_since_last_streak": 45,
  "current_consecutive_wins": 3,
  "hair_tier": "Growing back"
}
```

## Animation Sequence per Match

1. **Opponent crest slides in** (0.3s)
2. **Score appears** (0.3s)
3. **Result: W/D/L**
   - W: Green flash, W letter stacks below previous W's
   - D: Gray flash, W stack resets to 0
   - L: Red flash, W stack resets to 0
4. **Counter ticks** (+days since last match)
5. **Hair grows** (subtle morph between tiers when crossing threshold)
6. **If 5th W: HAIRCUT!** — confetti, scissors animation, hair resets, counter resets to 0

## Hair Progression Visuals

Use DiceBear avatars with progressive tiers (already defined in our code):

| Days | Tier | Avatar Config |
|------|------|--------------|
| 0-14 | Fresh cut | shortFlat, no beard, smile |
| 15-60 | Growing back | shortCurly, light beard |
| 61-120 | Getting shaggy | shaggyMullet, medium beard, worried |
| 121-270 | Long & wild | longHair, full beard, frustrated |
| 271-500 | Caveman | bigHair, majestic beard, grimace |
| 500+ | Sasquatch | dreads, majestic beard, screaming |

The avatar changes at tier boundaries — a visual "snap" that's immediately noticeable.

## Best Matchups for Launch

| Matchup | Why it's good |
|---------|--------------|
| **Ajax (98d) vs Feyenoord (326d)** | Biggest rivalry, 3x difference |
| **PSV (67d) vs Ajax (98d)** | Top 3, close race |
| **Sparta (3666d) vs Feyenoord (326d)** | Rotterdam derby, 10x difference! |
| **NEC (46d) vs Fortuna (2910d)** | Extreme contrast |
| **Telstar (3064d) vs Heerenveen (3105d)** | Battle of the sasquatches |

## Technical Implementation

### Option A: Remotion (React video)
- Programmatic, data-driven
- Batch render all matchups
- Output: MP4 for social media
- Can add music, sound effects
- Best for polished content

### Option B: CSS Animation on site
- Live on the site as interactive feature
- Users pick two teams → animation plays
- Screen-recordable for sharing
- Lower production quality but interactive

### Option C: Both
- Remotion for pre-made viral content (launch)
- CSS for interactive site feature (ongoing engagement)

## Recommended: Start with Option A (Remotion)

1. Create one polished video: Ajax vs Feyenoord
2. Post it Friday evening
3. If it gets traction, batch-generate all matchups
4. Add interactive version to site later

## Video Specs

- **Duration:** 30-60 seconds
- **Resolution:** 1080x1080 (Instagram), 1920x1080 (Twitter/YouTube)
- **Frame rate:** 30fps
- **Music:** Upbeat, tension-building → celebration at haircut moment
- **Text:** Dutch, large readable font
- **Branding:** hairlengthindex.nl watermark bottom center
