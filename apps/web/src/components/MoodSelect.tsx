import type { MoodSelection } from "../types";
import PlutchikWheel from "./PlutchikWheel";
import ShinyText from "./ShinyText";

interface Props {
  onPick: (sel: MoodSelection) => void;
}

export default function MoodSelect({ onPick }: Props) {
  return (
    <div className="screen select">
      <div className="landing">
        <header className="landing-head">
          <p className="wordmark">anima</p>
          <h1>
            <ShinyText
              text="How are you feeling?"
              speed={4}
              delay={0.6}
              color="#b9bdc4"
              shineColor="#ffffff"
              spread={100}
              direction="left"
              yoyo={false}
              pauseOnHover={false}
            />
          </h1>
          <p className="lead dim">
            Choose a feeling — and how strongly. The gallery will meet you there.
          </p>
        </header>

        <div className="wheel-wrap">
          <PlutchikWheel onSelect={onPick} />
        </div>

        <p className="landing-note dim">
          A quiet, mood-led walk through world art. Not a substitute for professional care —
          if you’re in crisis, please reach out to a local helpline.
        </p>
      </div>
    </div>
  );
}
