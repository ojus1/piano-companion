import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type TechniqueResult } from "../api";
import Keyboard from "../components/Keyboard";
import { onLiveNote, useData, type LiveNote } from "../hooks";
import { Metronome } from "../metronome";
import {
  FAMILIES,
  TEMPO_LEVELS,
  advance,
  generateDrill,
  startProgress,
  type Drill,
  type FamilyId,
  type KeyPool,
  type Progress,
  type TempoLevel,
} from "../technique";

const RATING = { 1: "Again", 2: "Hard", 3: "Good", 4: "Easy" } as const;
const SETTINGS_KEY = "technique-settings";

interface Settings {
  families: FamilyId[];
  keys: KeyPool;
  tempo: TempoLevel;
  click: boolean;
  volume: number;
}

const DEFAULTS: Settings = {
  families: ["five_finger", "scale_major", "scale_minor", "arpeggio_root", "triad_inversions", "chord_flashcards"],
  keys: "easy",
  tempo: "medium",
  click: true,
  volume: 0.6,
};

function loadSettings(): Settings {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? "{}") };
  } catch {
    return DEFAULTS;
  }
}

type Phase = "idle" | "countin" | "playing" | "grading" | "done";

const metronome = new Metronome();

/** The backend's SQLite timestamps may come back without a timezone; they are UTC. */
const parseUtc = (iso: string) => new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);

export default function Technique({ held, pianoConnected }: { held: ReadonlySet<number>; pianoConnected: boolean }) {
  const [settings, setSettings] = useState<Settings>(loadSettings);
  const items = useData(api.items);
  const history = useData(() => api.techniqueAttempts(10));
  const due = useMemo(() => {
    const now = Date.now();
    return new Set(
      (items.data ?? [])
        .filter((i) => i.active !== false && parseUtc(i.due).getTime() <= now)
        .map((i) => String(i.details?.concept_id ?? ""))
        .filter(Boolean),
    );
  }, [items.data]);

  const newDrill = useCallback(
    (previous?: FamilyId) => generateDrill({ families: settings.families, keys: settings.keys, tempo: settings.tempo, due, previous }),
    [settings.families, settings.keys, settings.tempo, due],
  );
  const [drill, setDrill] = useState<Drill>(() => newDrill());
  const [bpm, setBpm] = useState(drill.bpm);
  const [phase, setPhase] = useState<Phase>("idle");
  const [beat, setBeat] = useState<{ beat: number; bar: number } | null>(null);
  const [progress, setProgress] = useState<Progress>(startProgress);
  const [result, setResult] = useState<TechniqueResult | string | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  const notes = useRef<LiveNote[]>([]);
  const acceptFrom = useRef(0); // tablet clock (ms) after which key presses count
  const lastNoteAt = useRef(0);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;

  useEffect(() => {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    } catch {
      /* private mode: settings just won't persist */
    }
  }, [settings]);

  useEffect(() => () => metronome.stop(), []);
  useEffect(() => metronome.setVolume(settings.volume), [settings.volume]);

  const show = (d: Drill) => {
    metronome.stop();
    setDrill(d);
    setBpm(d.bpm);
    setPhase("idle");
    setBeat(null);
    setProgress(startProgress());
    setResult(null);
  };

  const finish = useCallback(async () => {
    if (phaseRef.current !== "playing" && phaseRef.current !== "countin") return;
    metronome.stop();
    setBeat(null);
    if (notes.current.length === 0) {
      setPhase("idle");
      return;
    }
    setPhase("grading");
    try {
      const r = await api.techniqueAttempt({
        family: drill.family,
        title: drill.title,
        concept_id: drill.concept,
        bpm,
        steps_per_beat: drill.stepsPerBeat,
        steps: drill.steps.map((s) => s.notes),
        notes: notes.current.map((n) => ({ note: n.note, t: n.t })),
        match: drill.match,
        drill: { key: drill.key, hands: drill.hands, detail: drill.detail, generated_bpm: drill.bpm },
      });
      setResult(r);
      items.reload();
      history.reload();
    } catch (e) {
      setResult(String(e));
    }
    setPhase("done");
  }, [drill, bpm, items, history]);

  // Key presses from the piano (via the Pi's live feed).
  useEffect(
    () =>
      onLiveNote((n) => {
        const p = phaseRef.current;
        if ((p !== "countin" && p !== "playing") || performance.now() < acceptFrom.current) return;
        if (p === "countin") setPhase("playing"); // started a touch early: fine
        notes.current.push(n);
        lastNoteAt.current = performance.now();
        setProgress((prev) => advance(drill, prev, n.note));
      }),
    [drill],
  );

  // Auto-finish when the last step is played, or after three bars of silence.
  useEffect(() => {
    if (phase === "playing" && progress.index >= drill.steps.length) {
      const t = window.setTimeout(finish, 400);
      return () => window.clearTimeout(t);
    }
  }, [phase, progress.index, drill.steps.length, finish]);
  useEffect(() => {
    if (phase !== "playing") return;
    const barMs = (60000 / bpm) * drill.beatsPerBar;
    const t = window.setInterval(() => {
      if (lastNoteAt.current && performance.now() - lastNoteAt.current > 3 * barMs) void finish();
    }, 250);
    return () => window.clearInterval(t);
  }, [phase, bpm, drill.beatsPerBar, finish]);

  const start = () => {
    notes.current = [];
    lastNoteAt.current = 0;
    setProgress(startProgress());
    setResult(null);
    const beatMs = 60000 / bpm;
    // Count-in: one bar. Notes from the last half beat of it on are accepted.
    acceptFrom.current = performance.now() + 100 + beatMs * (drill.beatsPerBar - 0.5);
    metronome.onBeat = (b, bar) => {
      setBeat({ beat: b, bar });
      if (bar >= 1 && phaseRef.current === "countin") setPhase("playing");
      if (bar >= 1 && !settings.click) metronome.stop();
    };
    metronome.start(bpm, drill.beatsPerBar);
    setPhase("countin");
  };

  const targets = new Set(phase === "done" ? [] : (drill.steps[progress.index]?.notes ?? []));
  const allNotes = drill.steps.flatMap((s) => s.notes);
  const lo = Math.min(...allNotes) - 2;
  const hi = Math.max(...allNotes) + 2;
  const keyLo = drill.match === "pitch_class" ? 36 : Math.max(21, Math.min(lo, hi - 24));
  const keyHi = drill.match === "pitch_class" ? 84 : Math.min(108, Math.max(hi, lo + 24));
  const active = phase === "countin" || phase === "playing";

  const toggleFamily = (id: FamilyId) =>
    setSettings((s) => ({
      ...s,
      families: s.families.includes(id) ? s.families.filter((f) => f !== id) : [...s.families, id],
    }));

  return (
    <div className="page technique">
      <div className="page-head">
        <div>
          <h1>Technique</h1>
          <p>Random scale, arpeggio and chord drills, graded from what you play.</p>
        </div>
        <div className="row">
          <button onClick={() => setShowSettings((v) => !v)}>{showSettings ? "Done" : "Drills & keys"}</button>
          <button className="primary" onClick={() => show(newDrill(drill.family))} disabled={active}>
            New drill
          </button>
        </div>
      </div>

      {showSettings && (
        <section className="panel settings" style={{ marginBottom: 16 }}>
          {(["Scales", "Arpeggios", "Chords"] as const).map((g) => (
            <div key={g} className="row">
              <span className="muted group-label">{g}</span>
              {FAMILIES.filter((f) => f.group === g).map((f) => (
                <button
                  key={f.id}
                  className={`chip ${settings.families.includes(f.id) ? "on" : ""}`}
                  onClick={() => toggleFamily(f.id)}
                >
                  {f.label}
                  {due.has(f.concept) && <span className="due-dot" title="due for review" />}
                </button>
              ))}
            </div>
          ))}
          <div className="row">
            <span className="muted group-label">Keys</span>
            {(["easy", "all"] as const).map((k) => (
              <button key={k} className={`chip ${settings.keys === k ? "on" : ""}`} onClick={() => setSettings((s) => ({ ...s, keys: k }))}>
                {k === "easy" ? "Common keys" : "All 12 keys"}
              </button>
            ))}
          </div>
          <div className="row">
            <span className="muted group-label">Tempo</span>
            {(Object.keys(TEMPO_LEVELS) as TempoLevel[]).map((t) => (
              <button key={t} className={`chip ${settings.tempo === t ? "on" : ""}`} onClick={() => setSettings((s) => ({ ...s, tempo: t }))}>
                {t[0].toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
          <p className="muted">A dot marks a skill whose review is due; due skills come up more often.</p>
        </section>
      )}

      <section className="panel drill">
        <div className="drill-title">{drill.title}</div>
        <div className="muted">
          {drill.hands === "HT" ? "Hands together" : drill.hands === "RH" ? "Right hand" : "Left hand"} · {drill.detail}
        </div>
        <div className="steps">
          {drill.steps.map((s, i) => (
            <span
              key={i}
              className={`step ${i < progress.index ? "done" : i === progress.index && active ? "current" : ""} ${s.notes.length > 1 ? "chord" : ""}`}
            >
              {s.label}
            </span>
          ))}
        </div>
        <Keyboard held={held} targets={targets} lo={keyLo} hi={keyHi} height={150} />
      </section>

      <section className="row spread controls">
        <div className="row">
          {!active ? (
            <button className="primary big-btn" onClick={start} disabled={phase === "grading"}>
              {phase === "done" ? "Again" : "Start"}
            </button>
          ) : (
            <button className="big-btn" onClick={() => void finish()}>
              Stop
            </button>
          )}
          <div className="beats" aria-label="metronome">
            {Array.from({ length: drill.beatsPerBar }, (_, b) => (
              <span key={b} className={`beat ${beat?.beat === b ? (b === 0 ? "on accent" : "on") : ""}`} />
            ))}
          </div>
          <span className="muted">
            {phase === "countin" ? "Count-in…" : phase === "playing" ? `${progress.index}/${drill.steps.length}` : ""}
            {phase === "grading" ? "Grading…" : ""}
            {!pianoConnected && phase === "idle" ? "Piano not connected: switch it on to be graded" : ""}
          </span>
        </div>
        <div className="row">
          <button onClick={() => setBpm((b) => Math.max(30, b - 4))} disabled={active}>
            −
          </button>
          <span className="bpm">{bpm} BPM</span>
          <button onClick={() => setBpm((b) => Math.min(240, b + 4))} disabled={active}>
            +
          </button>
          <button className={`chip ${settings.click ? "on" : ""}`} onClick={() => setSettings((s) => ({ ...s, click: !s.click }))}>
            Click {settings.click ? "on" : "off"}
          </button>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={settings.volume}
            onChange={(e) => setSettings((s) => ({ ...s, volume: Number(e.target.value) }))}
            aria-label="metronome volume"
            className="volume"
          />
        </div>
      </section>

      {typeof result === "string" && <p className="error">{result}</p>}
      {result && typeof result !== "string" && <ResultCard r={result} target={bpm} onNext={() => show(newDrill(drill.family))} />}

      <h2>Recent drills</h2>
      <ul className="queue">
        {(history.data ?? []).map((a) => (
          <li key={a.id} className="item">
            <div className="grow">
              <div className="title">{a.title}</div>
              <div className="muted">
                {parseUtc(a.created_at).toLocaleString()} · {a.bpm} BPM ·{" "}
                {Math.round(a.metrics.accuracy * 100)}% notes
                {a.metrics.achieved_bpm ? ` · played at ${Math.round(a.metrics.achieved_bpm)}` : ""}
              </div>
            </div>
            <span className={`grade r${a.rating}`}>{RATING[a.rating]}</span>
          </li>
        ))}
        {history.data?.length === 0 && <li className="empty">No drills yet.</li>}
      </ul>
    </div>
  );
}

function ResultCard({ r, target, onNext }: { r: TechniqueResult; target: number; onNext: () => void }) {
  const m = r.metrics;
  const evenness = m.ibi_cv == null ? "–" : m.ibi_cv <= 0.05 ? "very even" : m.ibi_cv <= 0.08 ? "even" : "uneven";
  return (
    <section className="item column result">
      <div className="row spread">
        <span className={`grade big-grade r${r.rating}`}>{RATING[r.rating]}</span>
        <button className="primary" onClick={onNext}>
          Next drill
        </button>
      </div>
      <div className="strip">
        <div className="cell">
          <div className="label">Right notes{m.extra ? ` · ${m.extra} extra` : ""}</div>
          <div className="big">
            {m.matched}
            <span className="unit">/ {m.expected}</span>
          </div>
        </div>
        <div className="cell">
          <div className="label">Tempo played (target {target})</div>
          <div className="big">
            {m.achieved_bpm ? Math.round(m.achieved_bpm) : "–"}
            <span className="unit">BPM</span>
          </div>
        </div>
        <div className="cell">
          <div className="label">Timing spread · {evenness}</div>
          <div className="big">{m.ibi_cv == null ? "–" : `${Math.round(m.ibi_cv * 100)}%`}</div>
        </div>
      </div>
      <p className="muted">
        {m.breakdowns ? `${m.breakdowns} stop${m.breakdowns > 1 ? "s" : ""}. ` : ""}
        {r.applied
          ? `Saved as today's review for this skill; next due ${r.next_due ? parseUtc(r.next_due).toLocaleDateString() : "later"}.`
          : "Logged. This skill isn't due for review yet, so its schedule is unchanged."}
      </p>
    </section>
  );
}
