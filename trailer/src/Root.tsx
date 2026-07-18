import "./index.css";
import { Composition } from "remotion";
import { StreamDeckTrailer } from "./Trailer";
import { trailerConfig } from "./trailerData";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id={trailerConfig.id}
        component={StreamDeckTrailer}
        durationInFrames={trailerConfig.durationInFrames}
        fps={trailerConfig.fps}
        width={trailerConfig.width}
        height={trailerConfig.height}
      />
    </>
  );
};
