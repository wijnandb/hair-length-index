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
  hookDuration: number;
  punchlineDuration: number;
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

const MONTHS_NL = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
const MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

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

// Logo mapping
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

function parseDate(dateStr: string): { month: number; year: number } {
  const [y, m] = dateStr.split("-").map(Number);
  return { month: m - 1, year: y };
}

// === Components ===

// Rolling calendar — shows month + year, always same position
const RollingCalendar: React.FC<{
  date: string;
  nextDate: string | null;
  progress: number;
  isNL: boolean;
}> = ({ date, nextDate, progress, isNL }) => {
  const cur = parseDate(date);
  const nxt = nextDate ? parseDate(nextDate) : cur;
  const months = isNL ? MONTHS_NL : MONTHS_EN;

  const sameMonth = cur.month === nxt.month && cur.year === nxt.year;
  const slideY = sameMonth ? 0 : interpolate(progress, [0.7, 1], [0, -30], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const nextSlideY = sameMonth ? 30 : interpolate(progress, [0.7, 1], [30, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const curOpacity = sameMonth ? 1 : interpolate(progress, [0.7, 1], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const nextOpacity = sameMonth ? 0 : interpolate(progress, [0.7, 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <div style={{
      height: 28,
      overflow: "hidden",
      position: "relative",
      minWidth: 120,
      textAlign: "center",
    }}>
      <div style={{
        fontSize: 18,
        fontWeight: 600,
        color: "#6b7280",
        transform: `translateY(${slideY}px)`,
        opacity: curOpacity,
        position: "absolute",
        width: "100%",
      }}>
        {months[cur.month]} {cur.year}
      </div>
      {!sameMonth && (
        <div style={{
          fontSize: 18,
          fontWeight: 600,
          color: "#6b7280",
          transform: `translateY(${nextSlideY}px)`,
          opacity: nextOpacity,
          position: "absolute",
          width: "100%",
        }}>
          {months[nxt.month]} {nxt.year}
        </div>
      )}
    </div>
  );
};

// Match result flash — compact, centered
const MatchFlash: React.FC<{
  match: MatchFrame;
  progress: number;
}> = ({ match, progress }) => {
  const opacity = interpolate(progress, [0, 0.08, 0.65, 0.85], [0, 1, 1, 0]);
  const scale = interpolate(progress, [0, 0.08, 0.12], [0.85, 1.05, 1], { extrapolateRight: "clamp" });
  const bgColor = match.result === "W" ? "#166534" : match.result === "L" ? "#991b1b" : "#374151";
  const oppLogo = getLogo(match.opponent);
  const extra = match.decidedIn === "PENALTIES" ? " (pen)" :
                match.decidedIn === "EXTRA_TIME" ? " (n.v.)" : "";

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      backgroundColor: bgColor,
      borderRadius: 14,
      padding: "8px 16px",
      opacity,
      transform: `scale(${scale})`,
      boxShadow: `0 4px 16px ${match.result === "W" ? "rgba(34,197,94,0.25)" : match.result === "L" ? "rgba(239,68,68,0.25)" : "rgba(0,0,0,0.2)"}`,
      maxWidth: 420,
      margin: "0 auto",
    }}>
      {oppLogo ? (
        <Img src={oppLogo} style={{ width: 24, height: 24, borderRadius: 3 }} />
      ) : (
        <div style={{ width: 24, height: 24, borderRadius: 12, backgroundColor: "#555" }} />
      )}
      <span style={{ color: "rgba(255,255,255,0.7)", fontSize: 14, fontWeight: 500, maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {match.opponent}
      </span>
      <span style={{ color: "white", fontSize: 18, fontWeight: 900 }}>
        {match.score}{extra}
      </span>
      <span style={{
        color: "white",
        fontSize: 20,
        fontWeight: 900,
        backgroundColor: "rgba(255,255,255,0.15)",
        borderRadius: 6,
        padding: "1px 8px",
      }}>
        {match.result}
      </span>
    </div>
  );
};

// Win streak progress boxes (0-5)
const WinProgress: React.FC<{
  wins: number;
  haircut: boolean;
}> = ({ wins, haircut }) => {
  return (
    <div style={{
      display: "flex",
      gap: 6,
      justifyContent: "center",
      alignItems: "center",
    }}>
      {[0, 1, 2, 3, 4].map((i) => {
        const filled = i < wins;
        return (
          <div key={i} style={{
            width: 38,
            height: 38,
            borderRadius: 8,
            backgroundColor: filled ? "#166534" : "rgba(255,255,255,0.04)",
            border: filled ? "2px solid #22c55e" : "2px solid rgba(255,255,255,0.08)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: filled ? "0 2px 8px rgba(34,197,94,0.25)" : "none",
          }}>
            <span style={{
              fontSize: 18,
              fontWeight: 900,
              color: filled ? "#22c55e" : "rgba(255,255,255,0.1)",
            }}>
              W
            </span>
          </div>
        );
      })}
      {haircut && (
        <div style={{ fontSize: 32, marginLeft: 6 }}>✂️</div>
      )}
    </div>
  );
};

// Supporter image with crossfade + pulse on tier transition
const SupporterImage: React.FC<{
  currentTier: number;
  prevTier: number;
  transitionProgress: number; // 0 = fully prev, 1 = fully current
  tierLabel: string;
  haircut: boolean;
  haircutProgress: number;
}> = ({ currentTier, prevTier, transitionProgress, tierLabel, haircut, haircutProgress }) => {
  const isTierChange = currentTier !== prevTier;

  // Pulse on tier change: scale up then back
  const pulseScale = isTierChange
    ? interpolate(transitionProgress, [0, 0.3, 0.6, 1], [1, 1.08, 1.04, 1])
    : 1;

  // Glow intensity on tier change
  const glowIntensity = isTierChange
    ? interpolate(transitionProgress, [0, 0.3, 1], [0, 0.6, 0])
    : 0;

  return (
    <div style={{
      width: 440,
      height: 440,
      borderRadius: 24,
      overflow: "hidden",
      position: "relative",
      transform: `scale(${pulseScale})`,
      boxShadow: isTierChange
        ? `0 0 ${40 + glowIntensity * 40}px rgba(245,158,11,${0.2 + glowIntensity * 0.4}), 0 8px 32px rgba(0,0,0,0.4)`
        : "0 8px 32px rgba(0,0,0,0.4)",
      border: isTierChange
        ? `3px solid rgba(245,158,11,${0.3 + glowIntensity * 0.7})`
        : "3px solid rgba(255,255,255,0.08)",
    }}>
      {/* Previous tier (fading out) */}
      {isTierChange && (
        <Img
          src={TIER_IMAGES[prevTier] || TIER_IMAGES[1]}
          style={{
            width: "100%",
            height: "100%",
            position: "absolute",
            inset: 0,
            opacity: 1 - transitionProgress,
          }}
        />
      )}
      {/* Current tier (fading in or full) */}
      <Img
        src={TIER_IMAGES[currentTier] || TIER_IMAGES[1]}
        style={{
          width: "100%",
          height: "100%",
          position: "absolute",
          inset: 0,
          opacity: isTierChange ? transitionProgress : 1,
        }}
      />
      {/* Tier label overlay */}
      <div style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        right: 0,
        background: "linear-gradient(transparent, rgba(0,0,0,0.8))",
        padding: "24px 16px 14px",
        textAlign: "center",
        zIndex: 2,
      }}>
        <span style={{
          fontSize: 15,
          fontWeight: 700,
          color: isTierChange ? "#f59e0b" : "rgba(255,255,255,0.7)",
          textTransform: "uppercase",
          letterSpacing: 3,
        }}>
          {tierLabel}
        </span>
      </div>
      {/* Haircut overlay */}
      {haircut && haircutProgress < 0.7 && (
        <div style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "rgba(34,197,94,0.35)",
          fontSize: 110,
          zIndex: 3,
        }}>
          ✂️
        </div>
      )}
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
  const prevMatch = currentIdx > 0 ? data.sequence[currentIdx - 1] : currentMatch;
  const nextMatch = currentIdx < data.sequence.length - 1 ? data.sequence[currentIdx + 1] : null;
  const isNL = data.league === "DED" || data.league === "JE";
  const punchlines = isNL ? PUNCHLINES_NL : PUNCHLINES_EN;
  const punchline = punchlines[data.teamId % punchlines.length];

  const displayDays = isMain && currentMatch ? currentMatch.daysSince : data.currentDays;
  const displayTier = isMain && currentMatch ? currentMatch.tier : data.currentTier;
  const prevTier = prevMatch ? prevMatch.tier : displayTier;
  const displayWins = isMain && currentMatch ? currentMatch.consecutiveWins : 0;
  const teamLogo = getLogo(data.team);

  // Tier transition progress: crossfade over the first part of a match frame
  const tierTransitionProgress = displayTier !== prevTier
    ? interpolate(matchProgress, [0, 0.5], [0, 1], { extrapolateRight: "clamp" })
    : 1;

  // Hook animations
  const hookOpacity = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" });
  const hookNumberScale = spring({ frame: Math.max(0, frame - 8), fps, config: { damping: 10, stiffness: 60 } });
  const hookShake = isHook && frame > 25
    ? Math.sin(frame * 0.7) * interpolate(frame, [25, hookDuration], [0, 2.5], { extrapolateRight: "clamp" })
    : 0;

  // Punchline
  const punchlineFrame = frame - (durationInFrames - punchlineDuration);
  const punchlineOpacity = interpolate(punchlineFrame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  const punchlineLines = punchline.split("\n");

  // Day counter interpolation between matches
  const nextDays = nextMatch ? nextMatch.daysSince : displayDays;
  const smoothDays = Math.round(interpolate(matchProgress, [0, 1], [displayDays, nextDays]));

  return (
    <AbsoluteFill style={{
      background: "linear-gradient(180deg, #0a0a0a 0%, #111827 40%, #0a0a0a 100%)",
      fontFamily: "'Inter', -apple-system, sans-serif",
    }}>

      {/* ====== HOOK ====== */}
      {isHook && (
        <AbsoluteFill style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          opacity: hookOpacity,
        }}>
          <div style={{
            width: 380,
            height: 380,
            borderRadius: 24,
            overflow: "hidden",
            border: "3px solid rgba(255,255,255,0.1)",
            transform: `rotate(${hookShake}deg)`,
            boxShadow: "0 8px 40px rgba(0,0,0,0.5)",
          }}>
            <Img src={TIER_IMAGES[data.currentTier] || TIER_IMAGES[6]} style={{ width: "100%", height: "100%" }} />
          </div>

          <div style={{
            display: "flex", alignItems: "center", gap: 12, marginTop: 20,
          }}>
            {teamLogo && <Img src={teamLogo} style={{ width: 36, height: 36 }} />}
            <span style={{ fontSize: 28, fontWeight: 800, color: "white" }}>{data.team}</span>
          </div>

          <div style={{
            fontSize: 130,
            fontWeight: 900,
            color: "#f59e0b",
            lineHeight: 1,
            marginTop: 12,
            transform: `scale(${hookNumberScale})`,
            textShadow: "0 6px 30px rgba(245,158,11,0.4)",
          }}>
            {formatDaysNL(data.currentDays)}
          </div>
          <div style={{
            fontSize: 20,
            color: "#6b7280",
            textTransform: "uppercase",
            letterSpacing: 6,
          }}>
            dagen zonder 5 op rij
          </div>
        </AbsoluteFill>
      )}

      {/* ====== MAIN: Centered layout ====== */}
      {isMain && currentMatch && (
        <AbsoluteFill style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "flex-start",
          padding: "50px 30px 60px",
        }}>
          {/* Team bar — compact top */}
          <div style={{
            display: "flex", alignItems: "center", gap: 10, marginBottom: 12,
          }}>
            {teamLogo && <Img src={teamLogo} style={{ width: 28, height: 28 }} />}
            <span style={{ fontSize: 18, fontWeight: 700, color: "rgba(255,255,255,0.6)" }}>{data.team}</span>
          </div>

          {/* Supporter image with crossfade + pulse */}
          <SupporterImage
            currentTier={displayTier}
            prevTier={prevTier}
            transitionProgress={tierTransitionProgress}
            tierLabel={currentMatch.tierLabel}
            haircut={currentMatch.haircut}
            haircutProgress={matchProgress}
          />

          {/* === Everything below photo, centered === */}
          <div style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 10,
            marginTop: 16,
          }}>
            {/* Match result flash */}
            <div style={{ minHeight: 44, width: "100%" }}>
              <MatchFlash match={currentMatch} progress={matchProgress} />
            </div>

            {/* Day counter — big gold number */}
            <div style={{ textAlign: "center" }}>
              <div style={{
                fontSize: 80,
                fontWeight: 900,
                color: "#f59e0b",
                lineHeight: 1,
                textShadow: "0 4px 20px rgba(245,158,11,0.35)",
                fontVariantNumeric: "tabular-nums",
                letterSpacing: -2,
              }}>
                {formatDaysNL(smoothDays)}
              </div>
              <div style={{
                fontSize: 14,
                color: "#6b7280",
                textTransform: "uppercase",
                letterSpacing: 5,
                marginTop: 2,
              }}>
                dagen
              </div>
            </div>

            {/* Rolling calendar */}
            <RollingCalendar
              date={currentMatch.date}
              nextDate={nextMatch?.date || null}
              progress={matchProgress}
              isNL={isNL}
            />

            {/* Win streak progress */}
            <WinProgress wins={displayWins} haircut={currentMatch.haircut} />
          </div>
        </AbsoluteFill>
      )}

      {/* ====== PUNCHLINE ====== */}
      {isPunchline && (
        <AbsoluteFill style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "rgba(0,0,0,0.92)",
          opacity: punchlineOpacity,
          padding: 50,
        }}>
          <div style={{ textAlign: "center", maxWidth: 800 }}>
            {punchlineLines.map((line, i) => {
              const lineDelay = i * 18;
              const lineOpacity = interpolate(
                punchlineFrame, [lineDelay, lineDelay + 12], [0, 1],
                { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
              );
              const lineY = interpolate(
                punchlineFrame, [lineDelay, lineDelay + 12], [16, 0],
                { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
              );
              const isLast = i === punchlineLines.length - 1;
              return (
                <div key={i} style={{
                  fontSize: isLast ? 42 : 34,
                  fontWeight: isLast ? 900 : 600,
                  color: isLast ? "#f59e0b" : "white",
                  opacity: lineOpacity,
                  transform: `translateY(${lineY}px)`,
                  marginBottom: 10,
                  lineHeight: 1.3,
                }}>
                  {line}
                </div>
              );
            })}
          </div>

          <div style={{
            display: "flex", alignItems: "center", gap: 10, marginTop: 36,
            opacity: interpolate(punchlineFrame, [50, 70], [0, 1], { extrapolateRight: "clamp" }),
          }}>
            {teamLogo && <Img src={teamLogo} style={{ width: 24, height: 24 }} />}
            <span style={{ fontSize: 16, color: "#6b7280" }}>
              {data.team} — {formatDaysNL(data.currentDays)} dagen
            </span>
          </div>

          <div style={{
            position: "absolute", bottom: 50,
            fontSize: 16, color: "#f59e0b", fontWeight: 700,
            opacity: interpolate(punchlineFrame, [70, 90], [0, 1], { extrapolateRight: "clamp" }),
          }}>
            Hair Length Index
          </div>
        </AbsoluteFill>
      )}

      {/* Watermark */}
      {isMain && (
        <div style={{
          position: "absolute", bottom: 16, left: 0, right: 0,
          textAlign: "center", fontSize: 10, color: "rgba(255,255,255,0.1)",
        }}>
          hairlengthindex
        </div>
      )}
    </AbsoluteFill>
  );
};
