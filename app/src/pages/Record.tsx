import { useEffect, useState } from "react";
import { api, type Performance, type TakeInfo, type TakeKind } from "../api";
import { useData } from "../hooks";
import { noteName } from "../midi";
import MidiPlayer from "../components/MidiPlayer";

/**
 * Deliberate takes: performances of a piece and covers. Unlike practice sessions (recorded
 * automatically), a take starts and stops here, gets a title, and is kept until you delete it.
 * The take lives on the Pi, so closing the app or locking the tablet doesn't stop it.
 */

interface Props {
  held: ReadonlySet<number>;
  takeEvent: number;
  pianoConnected: boolean;
}

type Filter = "all" | TakeKind | "favorites";

export default function Record({ held, takeEvent, pianoConnected }: Props) {
  const [take, setTake] = useState<TakeInfo | null>(null);
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<TakeKind>("performance");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const [filter, setFilter] = useState<Filter>("all");
  const takes = useData(api.performances, [takeEvent]);

  // Pick up a take already running (started before the app was opened, or on another screen).
  useEffect(() => {
    api
      .status()
      .then((s) => setTake(s.take ?? null))
      .catch(() => {});
  }, [takeEvent]);

  // While recording: tick the clock and refresh the note count.
  useEffect(() => {
    if (!take) return;
    const id = window.setInterval(() => {
      setNow(Date.now());
      api
        .status()
        .then((s) => setTake(s.take ?? null))
        .catch(() => {});
    }, 1000);
    return () => window.clearInterval(id);
  }, [take?.started_at]); // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    setBusy(true);
    setMsg(null);
    try {
      setTake(await api.startTake(title, kind));
      setNow(Date.now());
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      const { performance: p } = await api.stopTake();
      setTake(null);
      setTitle("");
      setMsg(
        p
          ? `Saved “${p.title}”: ${p.note_count} notes, ${fmt(p.duration_s)}.`
          : "Nothing was played, so nothing was saved.",
      );
      takes.reload();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  };

  const discard = async () => {
    setBusy(true);
    try {
      await api.cancelTake();
      setTake(null);
      setMsg("Take discarded.");
    } finally {
      setBusy(false);
    }
  };

  const elapsed = take ? Math.max(0, (now - Date.parse(take.started_at)) / 1000) : 0;
  const shown = (takes.data ?? []).filter((p) =>
    filter === "all" ? true : filter === "favorites" ? p.favorite : p.kind === filter,
  );

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Record</h1>
          <p>Performances and covers you want to keep. Practice is recorded on its own; takes are never trimmed.</p>
        </div>
      </div>

      <div className={`take-panel ${take ? "live" : ""}`}>
        {take ? (
          <>
            <div className="row spread">
              <div>
                <div className="rec">Recording</div>
                <div className="title">{take.title}</div>
                <div className="muted">{take.kind === "cover" ? "Cover" : "Performance"}</div>
              </div>
              <div className="take-clock">{fmt(elapsed)}</div>
            </div>
            <div className="muted">
              {take.note_count === 0
                ? "Waiting for the first note. The recording starts when you play."
                : `${take.note_count} notes`}
              {held.size > 0 && ` · ${[...held].sort((a, b) => a - b).map(noteName).join(" ")}`}
            </div>
            <div className="row">
              <button className="record-btn stop" onClick={stop} disabled={busy}>
                Stop and save
              </button>
              <button onClick={discard} disabled={busy}>
                Discard
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="row">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Title, e.g. “Merry-Go-Round of Life (Animenz)”"
                onKeyDown={(e) => e.key === "Enter" && !busy && start()}
              />
            </div>
            <div className="row">
              <div className="segmented">
                {(["performance", "cover"] as const).map((k) => (
                  <button key={k} className={k === kind ? "active" : ""} onClick={() => setKind(k)}>
                    {k === "cover" ? "Cover" : "Performance"}
                  </button>
                ))}
              </div>
              <button className="record-btn" onClick={start} disabled={busy}>
                Record
              </button>
            </div>
            {!pianoConnected && <div className="error">The piano isn’t connected, so nothing will be captured.</div>}
          </>
        )}
        {msg && <div className="muted">{msg}</div>}
      </div>

      <div className="row spread" style={{ margin: "40px 0 12px" }}>
        <h2 style={{ margin: 0 }}>Saved takes</h2>
        <div className="segmented">
          {(
            [
              ["all", "All"],
              ["performance", "Performances"],
              ["cover", "Covers"],
              ["favorites", "Favourites"],
            ] as const
          ).map(([f, label]) => (
            <button key={f} className={f === filter ? "active" : ""} onClick={() => setFilter(f)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      {takes.error && <p className="error">{takes.error}</p>}
      {takes.data && shown.length === 0 && <p className="muted">{filter === "all" ? "No takes yet." : "Nothing here yet."}</p>}
      <ul className="queue">
        {shown.map((p) => (
          <TakeRow key={p.id} p={p} onChange={takes.reload} />
        ))}
      </ul>
    </div>
  );
}

function TakeRow({ p, onChange }: { p: Performance; onChange: () => void }) {
  const [confirm, setConfirm] = useState(false);
  const patch = (body: Parameters<typeof api.patchPerformance>[1]) => api.patchPerformance(p.id, body).then(onChange);

  useEffect(() => {
    if (!confirm) return;
    const t = window.setTimeout(() => setConfirm(false), 4000);
    return () => window.clearTimeout(t);
  }, [confirm]);

  return (
    <li className="item column">
      <div className="row spread">
        <div className="row grow">
          <button
            className={`star ${p.favorite ? "on" : ""}`}
            title={p.favorite ? "Unfavorite" : "Favorite"}
            aria-label={p.favorite ? "Unfavorite" : "Favorite"}
            onClick={() => patch({ favorite: !p.favorite })}
          >
            <svg viewBox="0 0 24 24" fill={p.favorite ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" aria-hidden>
              <path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" />
            </svg>
          </button>
          <input
            className="title-input"
            defaultValue={p.title}
            onBlur={(e) => {
              const v = e.target.value.trim();
              if (v && v !== p.title) patch({ title: v });
              else e.target.value = p.title;
            }}
          />
        </div>
        <div className="row">
          <select value={p.kind} onChange={(e) => patch({ kind: e.target.value as TakeKind })}>
            <option value="performance">Performance</option>
            <option value="cover">Cover</option>
          </select>
          <a className="button ghost" href={api.performanceMidiUrl(p.id)} download>
            MIDI
          </a>
          <button
            className={confirm ? "danger" : "ghost"}
            onClick={() => (confirm ? api.deletePerformance(p.id).then(onChange) : setConfirm(true))}
          >
            {confirm ? "Tap again to delete" : "Delete"}
          </button>
        </div>
      </div>
      <div className="muted">
        {new Date(p.started_at.endsWith("Z") || p.started_at.includes("+") ? p.started_at : p.started_at + "Z").toLocaleString()}
        {` · ${fmt(p.duration_s)} · ${p.note_count} notes`}
        {p.metrics.auto_stopped && " · stopped automatically after a long silence"}
      </div>
      {p.midi_path && <MidiPlayer url={api.performanceMidiUrl(p.id)} playOnPiano={{ performance_id: p.id }} />}
      <input
        defaultValue={p.notes ?? ""}
        placeholder="Notes on this take"
        onBlur={(e) => e.target.value !== (p.notes ?? "") && patch({ notes: e.target.value })}
      />
    </li>
  );
}

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
