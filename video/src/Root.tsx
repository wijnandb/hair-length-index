import { Composition } from "remotion";
import { HeadToHead } from "./HeadToHead";
import { SocialCard } from "./SocialCard";
import { HairGrowthReel } from "./HairGrowthReel";
import matchData from "./match-data.json";
import spartaReel from "./reel-sparta-rotterdam.json";

export const RemotionRoot: React.FC = () => {
  const framesPerMatch = 45; // 1.5 seconds per match at 30fps
  const introDuration = 90; // 3 seconds intro
  const outroDuration = 120; // 4 seconds outro
  const totalFrames = introDuration + matchData.length * framesPerMatch + outroDuration;

  // Reel timing
  const reelFramesPerMatch = 24; // 0.8s per match — fast paced
  const hookDuration = 75; // 2.5s hook
  const punchlineDuration = 120; // 4s punchline
  const reelTotalFrames = hookDuration + spartaReel.sequence.length * reelFramesPerMatch + punchlineDuration;

  return (
    <>
      <Composition
        id="HeadToHead"
        component={HeadToHead}
        durationInFrames={totalFrames}
        fps={30}
        width={1080}
        height={1080}
        defaultProps={{
          matches: matchData,
          framesPerMatch,
          introDuration,
          outroDuration,
          team1: { name: "Ajax", color: "#D2122E", bgColor: "#1A0005" },
          team2: { name: "Feyenoord", color: "#005F3B", bgColor: "#001A0F" },
        }}
      />
      <Composition
        id="SocialCard"
        component={SocialCard}
        durationInFrames={1}
        fps={30}
        width={1080}
        height={1080}
        defaultProps={{
          teamName: "Sparta Rotterdam",
          days: 3667,
          streakLength: 8,
          hairTier: "Sasquatch",
          lastStreakDate: "11 maart 2016",
          league: "Eredivisie",
        }}
      />
      <Composition
        id="HairGrowthReel"
        component={HairGrowthReel}
        durationInFrames={reelTotalFrames}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          data: spartaReel as any,
          framesPerMatch: reelFramesPerMatch,
          hookDuration,
          punchlineDuration,
        }}
      />
    </>
  );
};
