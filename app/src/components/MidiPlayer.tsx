import { useEffect, useRef, useState } from "react";
import { Midi } from "@tonejs/midi";
import { CacheStorage, SplendidGrandPiano } from "smplr";

/**
 * MIDI player for recorded takes and reference performances.
 * - Parsing: @tonejs/midi (MIT).
 * - Sound: smplr's SplendidGrandPiano (MIT; sampled grand), samples cached in the browser after first load.
 * - "Play on piano" sends the file to the P-155 through the Pi instead, using the piano's own sound.
 * A small piano roll with a playhead is drawn on a canvas.
 */

interface Props {
  url: string;
  title?: string;
  playOnPiano?: { session_id?: number; piece_id?: number; performance_id?: number };
}

interface N {
  midi: number;
  time: number;
  duration: number;
  velocity: number;
}

let ctx: AudioContext | null = null;
let piano: ReturnType<typeof SplendidGrandPiano> | null = null;
function getPiano() {
  ctx ??= new AudioContext();
  piano ??= SplendidGrandPiano(ctx, { storage: CacheStorage("piano-samples"), decayTime: 0.6 });
  return { ctx, piano };
}

export default function MidiPlayer({ url, title, playOnPiano }: Props) {
  const [notes, setNotes] = useState<N[]>([]);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [pos, setPos] = useState(0);
  const [msg, setMsg] = useState<string | null>(null);
  const start = useRef<{ at: number; from: number } | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(url)
      .then((r) => r.arrayBuffer())
      .then((buf) => {
        if (cancelled) return;
        const midi = new Midi(buf);
        const all = midi.tracks.flatMap((t) => t.notes.map((n) => ({ midi: n.midi, time: n.time, duration: n.duration, velocity: n.velocity })));
        all.sort((a, b) => a.time - b.time);
        setNotes(all);
        setDuration(midi.duration);
      })
      .catch((e) => setMsg(String(e)));
    return () => {
      cancelled = true;
      piano?.stop();
    };
  }, [url]);

  // Piano roll
  useEffect(() => {
    const c = canvas.current;
    if (!c || !notes.length) return;
    const g = c.getContext("2d")!;
    const w = (c.width = c.clientWidth * devicePixelRatio);
    const h = (c.height = c.clientHeight * devicePixelRatio);
    const lo = Math.min(...notes.map((n) => n.midi)) - 2;
    const hi = Math.max(...notes.map((n) => n.midi)) + 2;
    const xs = w / Math.max(duration, 1);
    const ys = h / (hi - lo);
    g.clearRect(0, 0, w, h);
    const css = getComputedStyle(document.documentElement);
    const accent = css.getPropertyValue("--accent").trim() || "#9fbfa6";
    const rest = css.getPropertyValue("--faint").trim() || "#8b8984";
    const head = css.getPropertyValue("--text").trim() || "#ecebe7";
    for (const n of notes) {
      g.globalAlpha = 0.35 + 0.65 * n.velocity;
      g.fillStyle = n.time <= pos ? accent : rest;
      g.fillRect(n.time * xs, h - (n.midi - lo + 1) * ys, Math.max(2, n.duration * xs), Math.max(2, ys - 1));
    }
    g.globalAlpha = 1;
    g.fillStyle = head;
    g.fillRect(pos * xs, 0, 2 * devicePixelRatio, h);
  }, [notes, duration, pos]);

  // Playhead
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    const tick = () => {
      if (start.current && ctx) {
        const p = start.current.from + (ctx.currentTime - start.current.at) * speed;
        setPos(p);
        if (p >= duration) {
          setPlaying(false);
          setPos(0);
          return;
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, duration, speed]);

  const play = async () => {
    const { ctx, piano } = getPiano();
    await ctx.resume();
    setLoading(true);
    await piano.load;
    setLoading(false);
    const at = ctx.currentTime + 0.1;
    start.current = { at, from: pos };
    for (const n of notes) {
      if (n.time < pos) continue;
      piano.start({ note: n.midi, velocity: Math.round(n.velocity * 127), time: at + (n.time - pos) / speed, duration: n.duration / speed });
    }
    setPlaying(true);
  };

  const pause = () => {
    piano?.stop();
    setPlaying(false);
  };

  const onPiano = async () => {
    try {
      const r = await fetch("/api/play", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...playOnPiano, tempo_scale: speed }),
      });
      setMsg(r.ok ? "Playing on the piano" : (await r.json()).detail);
    } catch (e) {
      setMsg(String(e));
    }
  };

  return (
    <div className="player">
      {title && <div className="muted">{title}</div>}
      <canvas
        ref={canvas}
        className="roll"
        onClick={(e) => {
          const x = e.nativeEvent.offsetX / (e.currentTarget as HTMLCanvasElement).clientWidth;
          pause();
          setPos(x * duration);
        }}
      />
      <div className="row">
        <button onClick={playing ? pause : play} disabled={!notes.length || loading}>
          {loading ? "Loading piano…" : playing ? "Pause" : "Play"}
        </button>
        <label className="row muted">
          Speed
          <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} disabled={playing}>
            {[0.5, 0.6, 0.7, 0.8, 0.9, 1, 1.1].map((s) => (
              <option key={s} value={s}>
                {Math.round(s * 100)}%
              </option>
            ))}
          </select>
        </label>
        {playOnPiano && (
          <>
            <button className="ghost" onClick={onPiano}>Play on piano</button>
            <button className="ghost" onClick={() => fetch("/api/play/stop", { method: "POST" })}>Stop piano</button>
          </>
        )}
        <span className="time">
          {fmt(pos)} / {fmt(duration)}
        </span>
      </div>
      {msg && <div className="muted">{msg}</div>}
    </div>
  );
}

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
