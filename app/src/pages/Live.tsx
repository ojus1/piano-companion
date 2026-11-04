import { isBlackKey, noteName } from "../midi";

// 88 keys: A0 (21) .. C8 (108)
const KEYS = Array.from({ length: 88 }, (_, i) => i + 21);
const WHITE = KEYS.filter((k) => !isBlackKey(k));

export default function Live({ held }: { held: ReadonlySet<number> }) {
  const w = 100 / WHITE.length;
  return (
    <div className="page">
      <h2>Live</h2>
      <p className="held">{[...held].sort((a, b) => a - b).map(noteName).join("  ") || "Play something…"}</p>
      <div className="keyboard">
        {WHITE.map((k, i) => (
          <div key={k} className={`white ${held.has(k) ? "down" : ""}`} style={{ left: `${i * w}%`, width: `${w}%` }} />
        ))}
        {KEYS.filter(isBlackKey).map((k) => {
          const i = WHITE.filter((x) => x < k).length;
          return (
            <div key={k} className={`black ${held.has(k) ? "down" : ""}`} style={{ left: `${i * w - w * 0.3}%`, width: `${w * 0.6}%` }} />
          );
        })}
      </div>
    </div>
  );
}
