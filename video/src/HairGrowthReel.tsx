import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  interpolate,
  useVideoConfig,
  Img,
  staticFile,
  spring,
} from "remotion";

// === Types ===

interface MatchFrame {
  date: string;
  opponent: string;
  score: string;
  result: string;
  homeAway: string;
  competition: string;
  decidedIn: string;
  daysSince: number;
  consecutiveWins: number;
  tier: number;
  tierLabel: string;
  haircut: boolean;
}

interface ReelData {
  team: string;
  teamId: number;
  league: string;
  leagueName: string;
  currentDays: number;
  currentTier: number;
  currentTierLabel: string;
  totalMatches: number;
  sequence: MatchFrame[];
}

interface Props {
  data: ReelData;
  framesPerMatch: number;
  hookDuration: number; // frames for opening hook
  punchlineDuration: number; // frames for closing punchline
}

// === Constants ===

const TIER_IMAGES: Record<number, string> = {
  1: staticFile("supporters/hli-tier1.png"),
  2: staticFile("supporters/hli-tier2.png"),
  3: staticFile("supporters/hli-tier3.png"),
  4: staticFile("supporters/hli-tier4.png"),
  5: staticFile("supporters/hli-tier5.png"),
  6: staticFile("supporters/hli-tier6.png"),
};

const TIER_LABELS: Record<number, string> = {
  1: "Vers geknipt",
  2: "Groeit terug",
  3: "Wordt slordig",
  4: "Lang & wild",
  5: "Holbewoner",
  6: "Sasquatch",
};

// Punchlines — the absurdity of tracking something this mundane
const PUNCHLINES_NL = [
  "Gewoon 5 keer winnen.\nHoe moeilijk kan het zijn?",
  "5 op rij.\nNiemand die het lukt.",
  "Het klinkt zo makkelijk.\n5 keer winnen.\nEn toch.",
  "Elke week denk je:\ndeze keer.\nElke week: nee.",
];

const PUNCHLINES_EN = [
  "5 wins in a row.\nThat's all.\nHow hard can it be?",
  "Just win five.\nNobody's asking for a title.",
  "Five. Consecutive. Wins.\nApparently impossible.",
  "Every week you think:\nthis is the one.\nEvery week: no.",
];

// Logo mapping (same as HeadToHead)
const LOGO_FILES: Record<string, string> = {
  "Ajax": "ajax.png", "AZ Alkmaar": "az-alkmaar.png",
  "Feyenoord": "feyenoord.png", "PSV Eindhoven": "psv-eindhoven.png",
  "FC Twente": "fc-twente.png", "FC Utrecht": "fc-utrecht.png",
  "Sparta Rotterdam": "sparta-rotterdam.png", "Vitesse": "vitesse.png",
  "Go Ahead Eagles": "go-ahead-eagles.png", "Heerenveen": "heerenveen.png",
  "Heracles Almelo": "heracles-almelo.png", "N.E.C.": "nec.png",
  "NAC Breda": "nac-breda.png", "PEC Zwolle": "pec-zwolle.png",
  "FC Groningen": "fc-groningen.png", "Fortuna Sittard": "fortuna-sittard.png",
  "Manchester United": "manchester-united.png", "Liverpool FC": "liverpool-fc.png",
  "Arsenal FC": "arsenal-fc.png", "Chelsea FC": "chelsea-fc.png",
  "Manchester City": "manchester-city.png", "Tottenham Hotspur": "tottenham-hotspur.png",
  "Bayern Munich": "bayern-munich.png", "Borussia Dortmund": "borussia-dortmund.png",
  "Real Madrid": "real-madrid.png", "FC Barcelona": "fc-barcelona.png",
  "Juventus": "juventus.png", "Inter": "inter.png", "AC Milan": "ac-milan.png",
  "Paris Saint-Germain": "paris-saint-germain.png",
};

function getLogo(name: string): string | null {
  if (LOGO_FILES[name]) return staticFile(`logos/${LOGO_FILES[name]}`);
  for (const [key, file] of Object.entries(LOGO_FILES)) {
    if (name.includes(key) || key.includes(name)) return staticFile(`logos/${file}`);
  }
  return null;
}

function formatDaysNL(days: number): string {
  return days.toLocaleString("nl-NL");
}

// === Components ===

// The BIG day counter — hero element
const DayCounter: React.FC<{
  days: number;
  frame: number;
  fps: number;
}> = ({ days, frame, fps }) => {
  const scale = spring({ frame, fps, config: { damping: 15, stiffness: 80 } });

  return (
    <div style={{
      textAlign: "center",
      transform: `scale(${interpolate(scale, [0, 1], [0.8, 1])})`,
    }}>
      <div style={{
        fontSize: 96,
        fontWeight: 900,
        color: "#f59e0b",
        lineHeight: 1,
        textShadow: "0 4px 24px rgba(245,158,11,0.4), 0 0 80px rgba(245,158,11,0.15)",
        fontVariantNumeric: "tabular-nums",
        letterSpacing: -2,
      }}>
        {formatDaysNL(days)}
      </div>
      <div style={{
        fontSize: 18,
        color: "#6b7280",
        textTransform: "uppercase",
        letterSpacing: 6,
        marginTop: 4,
      }}>
        dagen
      </div>
    </div>
  );
};

// Win streak progress boxes (0-5)
const WinProgress: React.FC<{
  wins: number;
  frame: number;
  fps: number;
  haircut: boolean;
}> = ({ wins, frame, fps, haircut }) => {
  return (
    <div style={{
      display: "flex",
      gap: 8,
      justifyContent: "center",
      alignItems: "center",
    }}>
      {[0, 1, 2, 3, 4].map((i) => {
        const filled = i < wins;
        const scale = filled
          ? spring({ frame: frame + i * 2, fps, config: { damping: 12, stiffness: 200 } })
          : 1;
        return (
          <div key={i} style={{
            width: 44,
            height: 44,
            borderRadius: 10,
            backgroundColor: filled ? "#166534" : "rgba(255,255,255,0.06)",
            border: filled ? "2px solid #22c55e" : "2px solid rgba(255,255,255,0.1)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transform: `scale(${scale})`,
            boxShadow: filled ? "0 2px 12px rgba(34,197,94,0.3)" : "none",
          }}>
            <span style={{
              fontSize: 22,
              fontWeight: 900,
              color: filled ? "#22c55e" : "rgba(255,255,255,0.15)",
            }}>
              W
            </span>
          </div>
        );
      })}
      {haircut && (
        <div style={{ fontSize: 36, marginLeft: 8 }}>✂️</div>
      )}
    </div>
  );
};

// Match result flash — slides in from right
const MatchFlash: React.FC<{
  match: MatchFrame;
  progress: number; // 0-1 within match duration
  frame: number;
  fps: number;
}> = ({ match, progress, frame, fps }) => {
  const slideIn = interpolate(progress, [0, 0.15], [200, 0], { extrapolateRight: "clamp" });
  const opacity = interpolate(progress, [0, 0.1, 0.75, 1], [0, 1, 1, 0]);
  const bgColor = match.result === "W" ? "#166534" : match.result === "L" ? "#991b1b" : "#374151";
  const oppLogo = getLogo(match.opponent);
  const ha = match.homeAway === "H" ? "🏠" : "✈️";
  const extra = match.decidedIn === "PENALTIES" ? " (pen)" :
                match.decidedIn === "EXTRA_TIME" ? " (n.v.)" : "";

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 10,
      backgroundColor: bgColor,
      borderRadius: 16,
      padding: "10px 20px",
      opacity,
      transform: `translateX(${slideIn}px)`,
      boxShadow: `0 4px 20px ${match.result === "W" ? "rgba(34,197,94,0.3)" : match.result === "L" ? "rgba(239,68,68,0.3)" : "rgba(0,0,0,0.3)"}`,
    }}>
      <span style={{ fontSize: 16 }}>{ha}</span>
      {oppLogo ? (
        <Img src={oppLogo} style={{ width: 28, height: 28, borderRadius: 4 }} />
      ) : (
        <div style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: "#555" }} />
      )}
      <span style={{ color: "white", fontSize: 18, fontWeight: 600, flex: 1 }}>
        {match.opponent}
      </span>
      <span style={{ color: "white", fontSize: 22, fontWeight: 900 }}>
        {match.score}{extra}
      </span>
      <span style={{
        color: "white",
        fontSize: 24,
        fontWeight: 900,
        backgroundColor: "rgba(255,255,255,0.15)",
        borderRadius: 8,
        padding: "2px 10px",
      }}>
        {match.result}
      </span>
    </div>
  );
};

// === Main Composition ===

export const HairGrowthReel: React.FC<Props> = ({
  data,
  framesPerMatch,
  hookDuration,
  punchlineDuration,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const isHook = frame < hookDuration;
  const isPunchline = frame >= durationInFrames - punchlineDuration;
  const isMain = !isHook && !isPunchline;

  const mainFrame = frame - hookDuration;
  const rawIdx = mainFrame / framesPerMatch;
  const currentIdx = Math.floor(Math.max(0, Math.min(rawIdx, data.sequence.length - 1)));
  const matchProgress = rawIdx - Math.floor(rawIdx);

  const currentMatch = data.sequence[currentIdx];
  const isNL = data.league === "DED" || data.league === "JE";
  const punchlines = isNL ? PUNCHLINES_NL : PUNCHLINES_EN;
  const punchline = punchlines[data.teamId % punchlines.length];

  // Current state for interpolation
  const displayDays = isMain && currentMatch
    ? currentMatch.daysSince
    : data.currentDays;

  const displayTier = isMain && currentMatch
    ? currentMatch.tier
    : data.currentTier;

  const displayWins = isMain && currentMatch
    ? currentMatch.consecutiveWins
    : 0;

  const teamLogo = getLogo(data.team);

  // Tier transition: crossfade between tier images
  const prevTier = currentIdx > 0 ? data.sequence[Math.max(0, currentIdx - 1)].tier : displayTier;
  const tierChanged = isMain && currentMatch && prevTier !== displayTier;

  // Hook animation
  const hookTitleOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  const hookNumberScale = spring({ frame: Math.max(0, frame - 10), fps, config: { damping: 10, stiffness: 60 } });
  const hookShake = isHook && frame > 30
    ? Math.sin(frame * 0.8) * interpolate(frame, [30, hookDuration], [0, 3], { extrapolateRight: "clamp" })
    : 0;

  // Punchline animation
  const punchlineFrame = frame - (durationInFrames - punchlineDuration);
  const punchlineOpacity = interpolate(punchlineFrame, [0, 20], [0, 1], { extrapolateRight: "clamp" });
  const punchlineLines = punchline.split("\n");

  return (
    <AbsoluteFill style={{
      background: "linear-gradient(180deg, #0a0a0a 0%, #111827 40%, #0a0a0a 100%)",
      fontFamily: "'Inter', -apple-system, sans-serif",
    }}>

      {/* ====== HOOK: Start with the extreme (current state) ====== */}
      {isHook && (
        <AbsoluteFill style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          opacity: hookTitleOpacity,
        }}>
          {/* Supporter at worst state */}
          <div style={{
            width: 400,
            height: 400,
            borderRadius: 24,
            overflow: "hidden",
            border: "3px solid rgba(255,255,255,0.1)",
            transform: `rotate(${hookShake}deg)`,
            boxShadow: "0 8px 40px rgba(0,0,0,0.5)",
          }}>
            <Img src={TIER_IMAGES[data.currentTier] || TIER_IMAGES[6]} style={{ width: "100%", height: "100%" }} />
          </div>

          {/* Team name + logo */}
          <div style={{
            display: "flex", alignItems: "center", gap: 14,
            marginTop: 24,
          }}>
            {teamLogo && <Img src={teamLogo} style={{ width: 40, height: 40 }} />}
            <span style={{ fontSize: 32, fontWeight: 800, color: "white" }}>{data.team}</span>
          </div>

          {/* THE number */}
          <div style={{
            fontSize: 140,
            fontWeight: 900,
            color: "#f59e0b",
            lineHeight: 1,
            marginTop: 16,
            transform: `scale(${hookNumberScale})`,
            textShadow: "0 6px 30px rgba(245,158,11,0.4)",
          }}>
            {formatDaysNL(data.currentDays)}
          </div>
          <div style={{
            fontSize: 22,
            color: "#6b7280",
            textTransform: "uppercase",
            letterSpacing: 8,
          }}>
            dagen zonder 5 op rij
          </div>
        </AbsoluteFill>
      )}

      {/* ====== MAIN: Match sequence with hair growth ====== */}
      {isMain && currentMatch && (
        <AbsoluteFill style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          padding: "60px 40px 80px",
        }}>
          {/* Top bar: team + league + date */}
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
            marginBottom: 16,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              {teamLogo && <Img src={teamLogo} style={{ width: 32, height: 32 }} />}
              <span style={{ fontSize: 20, fontWeight: 700, color: "white" }}>{data.team}</span>
            </div>
            <div style={{
              fontSize: 16,
              color: "#6b7280",
              backgroundColor: "rgba(255,255,255,0.06)",
              padding: "4px 14px",
              borderRadius: 12,
            }}>
              {currentMatch.date}
            </div>
          </div>

          {/* Supporter image — THE visual center */}
          <div style={{
            width: 420,
            height: 420,
            borderRadius: 24,
            overflow: "hidden",
            border: tierChanged
              ? "3px solid #f59e0b"
              : "3px solid rgba(255,255,255,0.08)",
            boxShadow: tierChanged
              ? "0 0 40px rgba(245,158,11,0.3)"
              : "0 8px 32px rgba(0,0,0,0.4)",
            position: "relative",
            transition: "border-color 0.3s",
          }}>
            <Img
              src={TIER_IMAGES[displayTier] || TIER_IMAGES[1]}
              style={{ width: "100%", height: "100%" }}
            />
            {/* Tier label overlay */}
            <div style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              background: "linear-gradient(transparent, rgba(0,0,0,0.8))",
              padding: "20px 16px 12px",
              textAlign: "center",
            }}>
              <span style={{
                fontSize: 16,
                fontWeight: 700,
                color: "rgba(255,255,255,0.8)",
                textTransform: "uppercase",
                letterSpacing: 3,
              }}>
                {currentMatch.tierLabel}
              </span>
            </div>
            {/* Haircut overlay */}
            {currentMatch.haircut && matchProgress < 0.6 && (
              <div style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "rgba(34,197,94,0.3)",
                fontSize: 100,
              }}>
                ✂️
              </div>
            )}
          </div>

          {/* Match result flash */}
          <div style={{ marginTop: 20, width: "100%", minHeight: 56 }}>
            <MatchFlash
              match={currentMatch}
              progress={matchProgress}
              frame={mainFrame}
              fps={fps}
            />
          </div>

          {/* Day counter */}
          <div style={{ marginTop: 16 }}>
            <DayCounter days={displayDays} frame={mainFrame} fps={fps} />
          </div>

          {/* Win streak progress */}
          <div style={{ marginTop: 16 }}>
            <WinProgress
              wins={displayWins}
              frame={mainFrame}
              fps={fps}
              haircut={currentMatch.haircut}
            />
          </div>

          {/* Competition badge */}
          <div style={{
            marginTop: 12,
            fontSize: 13,
            color: "#4b5563",
            fontWeight: 600,
          }}>
            {currentMatch.competition}
          </div>
        </AbsoluteFill>
      )}

      {/* ====== PUNCHLINE: The absurdist payoff ====== */}
      {isPunchline && (
        <AbsoluteFill style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "rgba(0,0,0,0.9)",
          opacity: punchlineOpacity,
          padding: 60,
        }}>
          {/* The punchline text — line by line */}
          <div style={{ textAlign: "center", maxWidth: 800 }}>
            {punchlineLines.map((line, i) => {
              const lineDelay = i * 20;
              const lineOpacity = interpolate(
                punchlineFrame,
                [lineDelay, lineDelay + 15],
                [0, 1],
                { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
              );
              const lineY = interpolate(
                punchlineFrame,
                [lineDelay, lineDelay + 15],
                [20, 0],
                { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
              );
              const isLast = i === punchlineLines.length - 1;
              return (
                <div
                  key={i}
                  style={{
                    fontSize: isLast ? 44 : 36,
                    fontWeight: isLast ? 900 : 600,
                    color: isLast ? "#f59e0b" : "white",
                    opacity: lineOpacity,
                    transform: `translateY(${lineY}px)`,
                    marginBottom: 12,
                    lineHeight: 1.3,
                  }}
                >
                  {line}
                </div>
              );
            })}
          </div>

          {/* Team + days small reminder */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginTop: 40,
            opacity: interpolate(punchlineFrame, [60, 80], [0, 1], { extrapolateRight: "clamp" }),
          }}>
            {teamLogo && <Img src={teamLogo} style={{ width: 28, height: 28 }} />}
            <span style={{ fontSize: 18, color: "#6b7280" }}>
              {data.team} — {formatDaysNL(data.currentDays)} dagen
            </span>
          </div>

          {/* Branding */}
          <div style={{
            position: "absolute",
            bottom: 60,
            fontSize: 18,
            color: "#f59e0b",
            fontWeight: 700,
            opacity: interpolate(punchlineFrame, [80, 100], [0, 1], { extrapolateRight: "clamp" }),
          }}>
            Hair Length Index
          </div>
        </AbsoluteFill>
      )}

      {/* Subtle branding watermark during main */}
      {isMain && (
        <div style={{
          position: "absolute",
          bottom: 20,
          left: 0,
          right: 0,
          textAlign: "center",
          fontSize: 11,
          color: "rgba(255,255,255,0.12)",
        }}>
          hairlengthindex
        </div>
      )}
    </AbsoluteFill>
  );
};
