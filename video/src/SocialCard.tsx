import React from "react";
import { AbsoluteFill, Img } from "remotion";

interface Props {
  teamName: string;
  days: number;
  streakLength: number;
  hairTier: string;
  lastStreakDate: string;
  league: string;
}

const TIER_EMOJI: Record<string, string> = {
  "Fresh cut": "\u{1F487}",
  "Growing back": "\u2702\uFE0F",
  "Getting shaggy": "\u{1F488}",
  "Long & wild": "\u{1F981}",
  "Caveman": "\u{1F9D4}",
  "Sasquatch": "\u{1F9CC}",
  "Lost in time": "\u2753",
};

function getHairTier(days: number) {
  if (days <= 14) return { label: "Vers geknipt", mouth: "smile", eyes: "happy", top: "shortFlat", facialHair: "" };
  if (days <= 60) return { label: "Groeit terug", mouth: "default", eyes: "default", top: "shortCurly", facialHair: "beardLight" };
  if (days <= 120) return { label: "Wordt slordig", mouth: "serious", eyes: "squint", top: "shaggyMullet", facialHair: "beardMedium" };
  if (days <= 270) return { label: "Lang & wild", mouth: "serious", eyes: "side", top: "longButNotTooLong", facialHair: "beardMajestic" };
  if (days <= 500) return { label: "Holbewoner", mouth: "grimace", eyes: "xDizzy", top: "bigHair", facialHair: "beardMajestic" };
  return { label: "Sasquatch", mouth: "screamOpen", eyes: "surprised", top: "dreads", facialHair: "beardMajestic" };
}

function avatarUrl(tier: ReturnType<typeof getHairTier>, seed: string) {
  const params = new URLSearchParams({
    seed, backgroundColor: "transparent", top: tier.top, mouth: tier.mouth, eyes: tier.eyes,
  });
  if (tier.facialHair) params.set("facialHair", tier.facialHair);
  return `https://api.dicebear.com/9.x/avataaars/svg?${params.toString()}`;
}

export const SocialCard: React.FC<Props> = ({
  teamName, days, streakLength, hairTier, lastStreakDate, league,
}) => {
  const tier = getHairTier(days);
  const emoji = TIER_EMOJI[hairTier] || "\u{1F9CC}";
  const avatar = avatarUrl(tier, teamName);

  return (
    <AbsoluteFill style={{
      background: "linear-gradient(135deg, #0a1628 0%, #0d1f15 50%, #0a1628 100%)",
      fontFamily: "'Inter', -apple-system, sans-serif",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: 60,
    }}>
      {/* Avatar */}
      <div style={{
        width: 280, height: 280, borderRadius: "50%", overflow: "hidden",
        border: "4px solid rgba(255,255,255,0.2)", marginBottom: 30,
        backgroundColor: "rgba(255,255,255,0.05)",
      }}>
        <Img src={avatar} style={{ width: "100%", height: "100%" }} />
      </div>

      {/* Team name */}
      <div style={{
        fontSize: 48, fontWeight: 900, color: "white",
        textShadow: "0 2px 12px rgba(0,0,0,0.5)", textAlign: "center",
      }}>
        {teamName}
      </div>

      {/* Days counter — THE big number */}
      <div style={{
        fontSize: 120, fontWeight: 900, color: "#f59e0b",
        lineHeight: 1, marginTop: 20,
        textShadow: "0 4px 20px rgba(245,158,11,0.3)",
      }}>
        {days.toLocaleString("nl-NL")}
      </div>
      <div style={{
        fontSize: 24, color: "#9ca3af", textTransform: "uppercase",
        letterSpacing: 6, marginTop: 8,
      }}>
        dagen zonder 5 op rij
      </div>

      {/* Tier badge */}
      <div style={{
        fontSize: 28, marginTop: 24, color: "rgba(255,255,255,0.6)",
      }}>
        {emoji} {tier.label}
      </div>

      {/* Last streak info */}
      <div style={{
        fontSize: 18, color: "#6b7280", marginTop: 16,
      }}>
        Laatst {streakLength}x op rij: {lastStreakDate}
      </div>

      {/* Branding */}
      <div style={{
        position: "absolute", bottom: 40, fontSize: 20,
        color: "#f59e0b", fontWeight: 700,
      }}>
        wijnandb.github.io/hair-length-index
      </div>

      {/* League badge */}
      <div style={{
        position: "absolute", top: 40, right: 40,
        fontSize: 16, color: "#6b7280", fontWeight: 600,
        backgroundColor: "rgba(255,255,255,0.1)", padding: "6px 16px", borderRadius: 20,
      }}>
        {league} 2025-26
      </div>
    </AbsoluteFill>
  );
};
