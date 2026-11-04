import { noteName } from "../midi";
import Keyboard from "../components/Keyboard";

export default function Live({ held }: { held: ReadonlySet<number> }) {
  return (
    <div className="page">
      <h2>Live</h2>
      <p className="held">{[...held].sort((a, b) => a - b).map(noteName).join("  ") || "Play something…"}</p>
      <Keyboard held={held} />
    </div>
  );
}
