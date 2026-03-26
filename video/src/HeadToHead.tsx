import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  interpolate,
  useVideoConfig,
  Img,
  staticFile,
} from "remotion";

interface MatchFrame {
  team: string;
  date: string;
  opponent: string;
  score: string;
  result: string;
  homeAway: string;
  competition: string;
  ajaxDays: number;
  ajaxWins: number;
  feyDays: number;
  feyWins: number;
  haircut: boolean;
  haircutTeam: string | null;
  daysBetween: number;
}

interface TeamConfig {
  name: string;
  color: string;
  bgColor: string;
}

interface Props {
  matches: MatchFrame[];
  framesPerMatch: number;
  introDuration: number;
  outroDuration: number;
  team1: TeamConfig;
  team2: TeamConfig;
}

// Local logo file mapping: team name → filename in public/logos/
const LOGO_FILES: Record<string, string> = {
  "Ajax": "ajax.png", "AZ Alkmaar": "az-alkmaar.png", "Excelsior": "excelsior.png",
  "Feyenoord": "feyenoord.png", "Fortuna Sittard": "fortuna-sittard.png",
  "Go Ahead Eagles": "go-ahead-eagles.png", "FC Groningen": "fc-groningen.png",
  "Heerenveen": "heerenveen.png", "Heracles Almelo": "heracles-almelo.png",
  "N.E.C.": "nec.png", "NAC Breda": "nac-breda.png", "PEC Zwolle": "pec-zwolle.png",
  "PSV Eindhoven": "psv-eindhoven.png", "Sparta Rotterdam": "sparta-rotterdam.png",
  "Telstar": "telstar.png", "FC Twente": "fc-twente.png", "FC Utrecht": "fc-utrecht.png",
  "FC Volendam": "fc-volendam.png", "Vitesse": "vitesse.png",
  "Almere City FC": "almere-city-fc.png",
};

function getLogo(name: string): string | null {
  // Exact match
  if (LOGO_FILES[name]) return staticFile(`logos/${LOGO_FILES[name]}`);
  // Fuzzy match
  for (const [key, file] of Object.entries(LOGO_FILES)) {
    if (name.includes(key) || key.includes(name)) return staticFile(`logos/${file}`);
  }
  return null; // No logo — will be skipped in rendering
}

function getHairTier(days: number) {
  if (days <= 14) return { top: "shortFlat", facialHair: "", mouth: "smile", eyes: "happy", label: "Vers geknipt" };
  if (days <= 60) return { top: "shortCurly", facialHair: "beardLight", mouth: "default", eyes: "default", label: "Groeit terug" };
  if (days <= 120) return { top: "shaggyMullet", facialHair: "beardMedium", mouth: "serious", eyes: "squint", label: "Wordt slordig" };
  if (days <= 270) return { top: "longButNotTooLong", facialHair: "beardMajestic", mouth: "serious", eyes: "side", label: "Lang & wild" };
  if (days <= 500) return { top: "bigHair", facialHair: "beardMajestic", mouth: "grimace", eyes: "xDizzy", label: "Holbewoner" };
  return { top: "dreads", facialHair: "beardMajestic", mouth: "screamOpen", eyes: "surprised", label: "Sasquatch" };
}

function avatarUrl(tier: ReturnType<typeof getHairTier>, seed: string) {
  const params = new URLSearchParams({
    seed, backgroundColor: "transparent", top: tier.top, mouth: tier.mouth, eyes: tier.eyes,
  });
  if (tier.facialHair) params.set("facialHair", tier.facialHair);
  return `https://api.dicebear.com/9.x/avataaars/svg?${params.toString()}`;
}

// Match result display — shows opponent logo + result, W stays, D/L fades
const MatchResult: React.FC<{
  result: string;
  opponent: string;
  score: string;
  progress: number; // 0-1 within this match's time
}> = ({ result, opponent, score, progress }) => {
  const logo = getLogo(opponent);
  const isWin = result === "W";
  // D/L appear then fade. W stays.
  const opacity = isWin ? 1 : interpolate(progress, [0, 0.3, 0.7, 1], [0, 1, 1, 0]);
  const bgColor = result === "W" ? "#166534" : result === "L" ? "#991b1b" : "#374151";

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 6,
      opacity, padding: "4px 10px", borderRadius: 8,
      backgroundColor: bgColor, transition: "opacity 0.3s",
      minWidth: 120,
    }}>
      {getLogo(opponent) ? <Img src={getLogo(opponent)!} style={{ width: 20, height: 20 }} /> : <div style={{ width: 18, height: 18, borderRadius: 9, backgroundColor: "#555", flexShrink: 0 }} />}
      <span style={{ color: "white", fontSize: 13, fontWeight: 700 }}>{score}</span>
      <span style={{ color: "white", fontSize: 16, fontWeight: 900 }}>{result}</span>
    </div>
  );
};

// Win stack with opponent logos
const WinStack: React.FC<{
  wins: number;
  recentMatches: MatchFrame[];
}> = ({ wins, recentMatches }) => {
  // Get the last N wins from recent matches
  const winMatches = recentMatches.filter(m => m.result === "W").slice(-wins);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3, minHeight: 140 }}>
      {winMatches.map((m, i) => {
        const oppLogo = getLogo(m.opponent);
        return (
          <div key={i} style={{
            display: "flex", alignItems: "center", gap: 4,
            backgroundColor: "#166534", borderRadius: 6,
            padding: "3px 8px",
            boxShadow: "0 2px 6px rgba(34,197,94,0.3)",
          }}>
            <span style={{ color: "white", fontWeight: 900, fontSize: 14 }}>W</span>
            {oppLogo && <Img src={oppLogo} style={{ width: 16, height: 16, borderRadius: 2 }} />}
            <span style={{ color: "#bbf7d0", fontSize: 11 }}>{m.score}</span>
          </div>
        );
      })}
      {wins >= 5 && (
        <div style={{
          fontSize: 28, marginTop: 4,
          animation: "none", // Remotion doesn't use CSS animations
        }}>
          ✂️🎉
        </div>
      )}
    </div>
  );
};

// Running day counter with smooth interpolation
const DayCounter: React.FC<{
  currentDays: number;
  nextDays: number;
  matchProgress: number; // 0-1 progress between matches
}> = ({ currentDays, nextDays, matchProgress }) => {
  const displayDays = Math.round(
    interpolate(matchProgress, [0, 1], [currentDays, nextDays])
  );

  return (
    <div style={{ textAlign: "center" }}>
      <div style={{
        fontSize: 52, fontWeight: 900, color: "white",
        textShadow: "0 2px 12px rgba(0,0,0,0.5)",
        fontVariantNumeric: "tabular-nums",
      }}>
        {displayDays.toLocaleString("nl-NL")}
      </div>
      <div style={{ fontSize: 12, color: "#6b7280", textTransform: "uppercase", letterSpacing: 2 }}>
        dagen
      </div>
    </div>
  );
};

const TeamColumn: React.FC<{
  team: TeamConfig;
  days: number;
  nextDays: number;
  wins: number;
  matchProgress: number;
  currentMatch: MatchFrame | null;
  recentMatches: MatchFrame[];
  isActive: boolean;
  haircut: boolean;
}> = ({ team, days, nextDays, wins, matchProgress, currentMatch, recentMatches, isActive, haircut }) => {
  const tier = getHairTier(days);
  const avatar = avatarUrl(tier, team.name);
  const logo = getLogo(team.name);

  return (
    <div style={{
      flex: 1, display: "flex", flexDirection: "column",
      alignItems: "center", padding: "24px 10px",
    }}>
      {/* Team header with logo */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        {logo && <Img src={logo} style={{ width: 36, height: 36 }} />}
        <div style={{
          fontSize: 30, fontWeight: 900, color: team.color,
          letterSpacing: -1, textShadow: "0 2px 8px rgba(0,0,0,0.3)",
        }}>
          {team.name}
        </div>
      </div>

      {/* Avatar with hair tier */}
      <div style={{
        width: 160, height: 160, borderRadius: "50%", overflow: "hidden",
        border: `3px solid ${team.color}`, backgroundColor: "rgba(255,255,255,0.08)",
        position: "relative",
      }}>
        <Img src={avatar} style={{ width: "100%", height: "100%" }} />
        {haircut && (
          <div style={{
            position: "absolute", inset: 0, display: "flex",
            alignItems: "center", justifyContent: "center",
            fontSize: 64, background: "rgba(0,0,0,0.4)",
          }}>
            ✂️
          </div>
        )}
      </div>
      <div style={{ fontSize: 13, color: "#9ca3af", fontWeight: 600, marginTop: 4, marginBottom: 8 }}>
        {tier.label}
      </div>

      {/* Current match result */}
      <div style={{ minHeight: 32, marginBottom: 4 }}>
        {isActive && currentMatch && (
          <MatchResult
            result={currentMatch.result}
            opponent={currentMatch.opponent}
            score={currentMatch.score}
            progress={matchProgress}
          />
        )}
      </div>

      {/* Win stack with logos */}
      <WinStack wins={wins} recentMatches={recentMatches} />

      {/* Running day counter */}
      <DayCounter currentDays={days} nextDays={nextDays} matchProgress={matchProgress} />
    </div>
  );
};

export const HeadToHead: React.FC<Props> = ({
  matches, framesPerMatch, introDuration, outroDuration, team1, team2,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const matchFrame = frame - introDuration;
  const rawIdx = matchFrame / framesPerMatch;
  const currentMatchIdx = Math.floor(rawIdx);
  const matchProgress = rawIdx - currentMatchIdx; // 0-1 within current match
  const isIntro = frame < introDuration;
  const isOutro = frame >= durationInFrames - outroDuration;

  const idx = Math.min(Math.max(currentMatchIdx, 0), matches.length - 1);
  const nextIdx = Math.min(idx + 1, matches.length - 1);
  const cur = matches[idx];
  const nxt = matches[nextIdx];

  // Get recent matches for win stack
  const ajaxRecent = matches.slice(0, idx + 1).filter(m => m.team === "Ajax");
  const feyRecent = matches.slice(0, idx + 1).filter(m => m.team === "Feyenoord");

  const titleOpacity = isIntro
    ? interpolate(frame, [0, 30], [0, 1], { extrapolateRight: "clamp" })
    : isOutro ? 1
    : interpolate(frame, [introDuration - 20, introDuration], [1, 0], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{
      background: "linear-gradient(180deg, #0a1628 0%, #0d1f15 50%, #0a1628 100%)",
      fontFamily: "'Inter', -apple-system, sans-serif",
    }}>
      {/* Center divider */}
      <div style={{
        position: "absolute", top: 80, bottom: 80, left: "50%",
        width: 2, background: "rgba(255,255,255,0.08)",
      }} />
      <div style={{
        position: "absolute", top: "50%", left: "50%",
        transform: "translate(-50%, -50%)",
        fontSize: 28, fontWeight: 900, color: "rgba(255,255,255,0.1)", letterSpacing: 6,
      }}>
        VS
      </div>

      {/* Match date indicator */}
      {!isIntro && !isOutro && cur && (
        <div style={{
          position: "absolute", top: 16, left: "50%", transform: "translateX(-50%)",
          fontSize: 14, color: "#6b7280", fontWeight: 600,
          backgroundColor: "rgba(0,0,0,0.4)", padding: "4px 16px", borderRadius: 20,
        }}>
          {cur.date}
        </div>
      )}

      {/* Two team columns */}
      {!isIntro && (
        <div style={{ display: "flex", width: "100%", height: "100%", padding: "44px 16px 40px" }}>
          <TeamColumn
            team={team1}
            days={cur?.ajaxDays ?? 99}
            nextDays={nxt?.ajaxDays ?? cur?.ajaxDays ?? 99}
            wins={cur?.ajaxWins ?? 0}
            matchProgress={matchProgress}
            currentMatch={cur?.team === "Ajax" ? cur : null}
            recentMatches={ajaxRecent}
            isActive={matchFrame >= 0 && cur?.team === "Ajax"}
            haircut={cur?.haircutTeam === "Ajax" && matchProgress < 0.5}
          />
          <TeamColumn
            team={team2}
            days={cur?.feyDays ?? 327}
            nextDays={nxt?.feyDays ?? cur?.feyDays ?? 327}
            wins={cur?.feyWins ?? 0}
            matchProgress={matchProgress}
            currentMatch={cur?.team === "Feyenoord" ? cur : null}
            recentMatches={feyRecent}
            isActive={matchFrame >= 0 && cur?.team === "Feyenoord"}
            haircut={cur?.haircutTeam === "Feyenoord" && matchProgress < 0.5}
          />
        </div>
      )}

      {/* Intro */}
      {isIntro && (
        <AbsoluteFill style={{
          display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", background: "rgba(0,0,0,0.8)", opacity: titleOpacity,
        }}>
          <div style={{ fontSize: 44, fontWeight: 900, color: "white" }}>
            Hair Length Index
          </div>
          <div style={{ fontSize: 24, color: "#9ca3af", marginTop: 8 }}>
            Wie gaat het eerst naar de kapper?
          </div>
          <div style={{ display: "flex", gap: 30, marginTop: 36, alignItems: "center" }}>
            {getLogo(team1.name) && <Img src={getLogo(team1.name)!} style={{ width: 60, height: 60 }} />}
            <div style={{ fontSize: 32, fontWeight: 800, color: team1.color }}>{team1.name}</div>
            <div style={{ fontSize: 20, color: "#6b7280" }}>vs</div>
            <div style={{ fontSize: 32, fontWeight: 800, color: team2.color }}>{team2.name}</div>
            {getLogo(team2.name) && <Img src={getLogo(team2.name)!} style={{ width: 60, height: 60 }} />}
          </div>
        </AbsoluteFill>
      )}

      {/* Outro */}
      {isOutro && (
        <AbsoluteFill style={{
          display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", background: "rgba(0,0,0,0.8)",
          opacity: interpolate(frame, [durationInFrames - outroDuration, durationInFrames - outroDuration + 30], [0, 1], { extrapolateRight: "clamp" }),
        }}>
          <div style={{ fontSize: 24, color: "#9ca3af", marginBottom: 20 }}>Eindstand</div>
          <div style={{ display: "flex", gap: 40, alignItems: "center" }}>
            <div style={{ textAlign: "center" }}>
              {getLogo(team1.name) && <Img src={getLogo(team1.name)!} style={{ width: 48, height: 48, marginBottom: 8 }} />}
              <div style={{ fontSize: 56, fontWeight: 900, color: team1.color }}>
                {matches[matches.length - 1]?.ajaxDays}
              </div>
              <div style={{ fontSize: 18, color: "white" }}>{team1.name}</div>
            </div>
            <div style={{ fontSize: 18, color: "#6b7280" }}>dagen</div>
            <div style={{ textAlign: "center" }}>
              {getLogo(team2.name) && <Img src={getLogo(team2.name)!} style={{ width: 48, height: 48, marginBottom: 8 }} />}
              <div style={{ fontSize: 56, fontWeight: 900, color: team2.color }}>
                {matches[matches.length - 1]?.feyDays}
              </div>
              <div style={{ fontSize: 18, color: "white" }}>{team2.name}</div>
            </div>
          </div>
          <div style={{ fontSize: 22, color: "#f59e0b", marginTop: 36, fontWeight: 700 }}>
            hairlengthindex.nl
          </div>
          <div style={{ fontSize: 14, color: "#6b7280", marginTop: 8 }}>
            Check jouw club!
          </div>
        </AbsoluteFill>
      )}

      {/* Branding */}
      <div style={{
        position: "absolute", bottom: 8, left: 0, right: 0,
        textAlign: "center", fontSize: 11, color: "rgba(255,255,255,0.15)",
      }}>
        hairlengthindex.nl
      </div>
    </AbsoluteFill>
  );
};
