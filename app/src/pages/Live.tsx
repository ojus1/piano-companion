import { noteName } from "../midi";
import Keyboard from "../components/Keyboard";

export default function Live({ held }: { held: ReadonlySet<number> }) {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Live</h1>
          <p>What the Pi hears from the piano, right now.</p>
        </div>
      </div>
      <p className="held">{[...held].sort((a, b) => a - b).map(noteName).join("  ") || "Play something…"}</p>
      <Keyboard held={held} />
    </div>
  );
}
