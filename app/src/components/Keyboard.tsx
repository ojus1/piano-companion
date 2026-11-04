import { isBlackKey } from "../midi";

interface Props {
  held: ReadonlySet<number>;
  /** Keys to outline (the notes you should play next). */
  targets?: ReadonlySet<number>;
  lo?: number;
  hi?: number;
  height?: number;
}

/** On-screen keyboard. Defaults to all 88 keys (A0..C8). */
export default function Keyboard({ held, targets, lo = 21, hi = 108, height = 180 }: Props) {
  if (isBlackKey(lo)) lo -= 1;
  if (isBlackKey(hi)) hi += 1;
  const keys = Array.from({ length: hi - lo + 1 }, (_, i) => i + lo);
  const white = keys.filter((k) => !isBlackKey(k));
  const w = 100 / white.length;
  const cls = (k: number) => `${held.has(k) ? "down" : ""} ${targets?.has(k) ? "target" : ""}`;
  return (
    <div className="keyboard" style={{ height }}>
      {white.map((k, i) => (
        <div key={k} className={`white ${cls(k)}`} style={{ left: `${i * w}%`, width: `${w}%` }} />
      ))}
      {keys.filter(isBlackKey).map((k) => {
        const i = white.filter((x) => x < k).length;
        return <div key={k} className={`black ${cls(k)}`} style={{ left: `${i * w - w * 0.3}%`, width: `${w * 0.6}%` }} />;
      })}
    </div>
  );
}
