import { Composition } from "remotion";
import { HeadToHead } from "./HeadToHead";
import matchData from "./match-data.json";

export const RemotionRoot: React.FC = () => {
  const framesPerMatch = 45; // 1.5 seconds per match at 30fps
  const introDuration = 90; // 3 seconds intro
  const outroDuration = 120; // 4 seconds outro
  const totalFrames = introDuration + matchData.length * framesPerMatch + outroDuration;

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
    </>
  );
};
