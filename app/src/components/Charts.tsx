// Small dependency-free SVG charts for the Progress screen. Each is single-series (the title names it),
// thin marks, a recessive grid and a hover readout instead of a number on every mark.
import { useState } from "react";
import type { DayStatus } from "../api";

const fmtDay = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });

/** Daily goal ring: fills as today's minutes approach the goal. */
export function Ring({ value, goal, size = 120, label }: { value: number; goal: number; size?: number; label: string }) {
  const r = size / 2 - 8;
  const c = 2 * Math.PI * r;
  const f = Math.min(1, goal > 0 ? value / goal : 0);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--line)" strokeWidth={10} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={f >= 1 ? "var(--ok)" : "var(--accent)"}
        strokeWidth={10}
        strokeLinecap="round"
        strokeDasharray={`${c * f} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="47%" textAnchor="middle" className="ring-big">
        {Math.round(value)}
      </text>
      <text x="50%" y="66%" textAnchor="middle" className="ring-small">
        of {goal} min
      </text>
    </svg>
  );
}

interface BarDatum {
  label: string;
  value: number;
  tip: string;
}

/** Vertical bars with an optional dashed goal line (minutes per day, per week). */
export function Bars({
  data,
  goal,
  unit,
  height = 160,
  width = 640,
}: {
  data: BarDatum[];
  goal?: number;
  unit: string;
  height?: number;
  width?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const W = width;
  const pad = { l: 34, r: 8, t: 10, b: 22 };
  const max = Math.max(1, goal ?? 0, ...data.map((d) => d.value)) * 1.1;
  const bw = (W - pad.l - pad.r) / Math.max(1, data.length);
  const y = (v: number) => pad.t + (height - pad.t - pad.b) * (1 - v / max);
  const ticks = niceTicks(max);
  const every = Math.ceil(data.length / 8);
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${height}`} className="chart-svg" onMouseLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} className="grid" />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" className="axis">
              {t}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const x = pad.l + i * bw;
          const h = height - pad.b - y(d.value);
          return (
            <g key={i} onMouseEnter={() => setHover(i)} onPointerDown={() => setHover(i)}>
              <rect x={x} y={pad.t} width={bw} height={height - pad.t - pad.b} fill="transparent" />
              {d.value > 0 && (
                <rect
                  x={x + 1}
                  y={y(d.value)}
                  width={Math.max(2, bw - 2)}
                  height={Math.max(1, h)}
                  rx={Math.min(4, bw / 3)}
                  className={hover === i ? "bar hot" : goal && d.value >= goal ? "bar met" : "bar"}
                />
              )}
              {i % every === 0 && (
                <text x={x + bw / 2} y={height - 6} textAnchor="middle" className="axis">
                  {d.label}
                </text>
              )}
            </g>
          );
        })}
        {goal ? <line x1={pad.l} x2={W - pad.r} y1={y(goal)} y2={y(goal)} className="goal-line" /> : null}
      </svg>
      <div className="chart-tip">{hover !== null ? data[hover].tip : goal ? `Dashed line: goal (${goal} ${unit})` : " "}</div>
    </div>
  );
}

interface LinePoint {
  date: string;
  value: number | null;
}

/** A line over days, with dots and a crosshair readout. Gaps (null) are skipped, not drawn as zero. */
export function Line({
  points,
  format,
  min,
  max,
  height = 140,
  width = 640,
}: {
  points: LinePoint[];
  format: (v: number) => string;
  min?: number;
  max?: number;
  height?: number;
  width?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const W = width;
  const pad = { l: 40, r: 12, t: 10, b: 22 };
  const vals = points.map((p) => p.value).filter((v): v is number => v !== null);
  if (vals.length === 0) return <p className="muted">No data yet.</p>;
  const lo = min ?? Math.min(...vals) * 0.9;
  const hi = max ?? Math.max(...vals) * 1.05;
  const span = hi - lo || 1;
  const x = (i: number) => pad.l + (points.length === 1 ? (W - pad.l - pad.r) / 2 : (i * (W - pad.l - pad.r)) / (points.length - 1));
  const y = (v: number) => pad.t + (height - pad.t - pad.b) * (1 - (v - lo) / span);
  const path = points
    .map((p, i) => (p.value === null ? null : `${x(i)},${y(p.value)}`))
    .filter(Boolean)
    .join(" L");
  const ticks = [lo, lo + span / 2, hi];
  const every = Math.ceil(points.length / 6);
  return (
    <div className="chart">
      <svg
        viewBox={`0 0 ${W} ${height}`}
        className="chart-svg"
        onMouseLeave={() => setHover(null)}
        onPointerMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          let best = 0;
          points.forEach((_, i) => {
            if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i;
          });
          setHover(best);
        }}
      >
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} className="grid" />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" className="axis">
              {format(t)}
            </text>
          </g>
        ))}
        {points.map((p, i) =>
          i % every === 0 ? (
            <text key={p.date} x={x(i)} y={height - 6} textAnchor="middle" className="axis">
              {fmtDay(p.date)}
            </text>
          ) : null,
        )}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={height - pad.b} className="crosshair" />}
        <path d={`M${path}`} className="line" />
        {points.map((p, i) =>
          p.value === null ? null : <circle key={i} cx={x(i)} cy={y(p.value)} r={hover === i ? 6 : points.length > 30 ? 2.5 : 4} className="dot-mark" />,
        )}
      </svg>
      <div className="chart-tip">
        {hover !== null
          ? `${fmtDay(points[hover].date)}: ${points[hover].value === null ? "no attempts" : format(points[hover].value!)}`
          : " "}
      </div>
    </div>
  );
}

interface CalDay {
  date: string;
  minutes: number;
  status: DayStatus;
  goal: boolean;
}

/** GitHub-style consistency calendar: one column per week, Monday on top. Frozen days show as ice. */
export function Calendar({ days: all, goal }: { days: CalDay[]; goal: number }) {
  const [hover, setHover] = useState<CalDay | null>(null);
  // Skip leading empty weeks before the first practice, but always show at least 12 weeks.
  const firstActive = all.findIndex((d) => d.minutes > 0);
  const skipWeeks = Math.max(0, Math.min(Math.floor((firstActive < 0 ? all.length : firstActive) / 7), Math.floor(all.length / 7) - 12));
  const days = all.slice(skipWeeks * 7);
  const cell = 16;
  const gap = 3;
  const weeks = Math.ceil(days.length / 7);
  const level = (m: number) => (m <= 0 ? 0 : m < goal / 2 ? 1 : m < goal ? 2 : m < goal * 2 ? 3 : 4);
  const W = weeks * (cell + gap) + 48;
  const H = 7 * (cell + gap) + 18;
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg calendar" style={{ maxWidth: W * 2 }} onMouseLeave={() => setHover(null)}>
        {["M", "", "W", "", "F", "", "S"].map((l, i) => (
          <text key={i} x={0} y={18 + i * (cell + gap) + cell - 4} className="axis">
            {l}
          </text>
        ))}
        {days.map((d, i) => {
          const w = Math.floor(i / 7);
          const dow = i % 7;
          const first = new Date(d.date + "T12:00:00").getDate() <= 7 && dow === 0;
          return (
            <g key={d.date}>
              {first && (
                <text x={24 + w * (cell + gap)} y={10} className="axis">
                  {new Date(d.date + "T12:00:00").toLocaleDateString(undefined, { month: "short" })}
                </text>
              )}
              <rect
                x={24 + w * (cell + gap)}
                y={18 + dow * (cell + gap)}
                width={cell}
                height={cell}
                rx={3}
                className={`cal ${d.status === "frozen" ? "frozen" : `l${level(d.minutes)}`} ${d.status === "pending" ? "today" : ""}`}
                onMouseEnter={() => setHover(d)}
                onPointerDown={() => setHover(d)}
              />
            </g>
          );
        })}
      </svg>
      <div className="chart-tip">
        {hover
          ? `${fmtDay(hover.date)}: ${Math.round(hover.minutes)} min${hover.status === "frozen" ? " · streak freeze used" : ""}${hover.goal ? " · goal met" : ""}`
          : "Darker = more minutes. Blue = a streak freeze saved the day."}
      </div>
    </div>
  );
}

function niceTicks(max: number): number[] {
  const step = [1, 2, 5, 10, 15, 20, 30, 60, 120, 300, 600].find((s) => max / s <= 4) ?? Math.ceil(max / 4);
  const out = [];
  for (let t = 0; t <= max; t += step) out.push(t);
  return out;
}
