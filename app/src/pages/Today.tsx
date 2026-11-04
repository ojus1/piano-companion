import { useEffect, useState } from "react";
import { api, type Achievement, type AutoGrade, type Piece } from "../api";
import { useData } from "../hooks";
import ScoreViewer from "../components/ScoreViewer";

const RATINGS = [
  { r: 1, label: "Again", hint: "fell apart" },
  { r: 2, label: "Hard", hint: "got through, struggling" },
  { r: 3, label: "Good", hint: "solid with effort" },
  { r: 4, label: "Easy", hint: "effortless" },
] as const;

export default function Today({ lastSaved }: { lastSaved: number | null }) {
  const queue = useData(api.queue);
  const progress = useData(api.progress, [lastSaved]);
  const [fresh, dismiss] = useNewAchievements(progress.data?.achievements);
  const [title, setTitle] = useState("");
  const [open, setOpen] = useState<Piece | null>(null);
  const [graded, setGraded] = useState<Record<number, AutoGrade | string>>({});

  const grade = async (id: number, r: 1 | 2 | 3 | 4) => {
    await api.review(id, r);
    queue.reload();
  };

  const autograde = async (id: number) => {
    try {
      const g = await api.autograde(id, lastSaved ?? undefined);
      setGraded((p) => ({ ...p, [id]: g }));
      queue.reload();
    } catch (e) {
      setGraded((p) => ({ ...p, [id]: String(e) }));
    }
  };

  if (open) return <ScoreViewer piece={open} onClose={() => setOpen(null)} />;

  const p = progress.data;
  const goalLeft = p ? Math.max(0, p.goals.daily_minutes - p.today_minutes) : 0;

  return (
    <div className="page">
      {fresh.length > 0 && (
        <div className="celebrate" onClick={dismiss}>
          🎉 Achievement unlocked: <strong>{fresh.map((a) => a.title).join(", ")}</strong>
        </div>
      )}
      <section className="cards">
        <div className="stat">
          <div className="big">🔥 {p?.streak.current ?? "–"}</div>
          <div>day streak</div>
          {p && (
            <div className="muted">
              {p.streak.at_risk ? "play today to keep it" : p.streak.practiced_today ? "today counts ✓" : " "} · {"❄".repeat(p.streak.freezes) || "no"} freeze
              {p.streak.freezes === 1 ? "" : "s"}
            </div>
          )}
        </div>
        <div className="stat">
          <div className="big">
            {Math.round(p?.today_minutes ?? 0)}
            <span className="of">/{p?.goals.daily_minutes ?? "–"}</span>
          </div>
          <div>minutes today</div>
          {p && <div className="muted">{goalLeft > 0 ? `${Math.ceil(goalLeft)} min to your goal` : "daily goal met ✓"}</div>}
        </div>
        <div className="stat">
          <div className="big">{queue.data?.length ?? "–"}</div>
          <div>items due</div>
          {p && (
            <div className="muted">
              Lv {p.xp.level} · {p.streak.week_days}/{p.goals.weekly_days} days this week
            </div>
          )}
        </div>
      </section>

      <h2>Today's practice</h2>
      {queue.error && <p className="error">Can't reach the Pi: {queue.error}</p>}
      {queue.data?.length === 0 && <p className="muted">Nothing due. Free play, or add an item below.</p>}
      <ul className="queue">
        {queue.data?.map((item) => (
          <li key={item.id} className="item">
            <div>
              <div className="title">{item.title}</div>
              <div className="muted">
                {[item.stage, item.kind.replace("_", " "), item.details.role as string | undefined].filter(Boolean).join(" · ")}
              </div>
              {typeof graded[item.id] === "string" && <div className="error">{graded[item.id] as string}</div>}
            </div>
            {item.piece && (
              <div className="row">
                <button onClick={() => setOpen(item.piece!)}>Score</button>
                {(item.piece.musicxml_path || item.piece.midi_path) && (
                  <button title="Grade your last recorded take against the score" onClick={() => autograde(item.id)}>
                    Auto-grade last take
                  </button>
                )}
              </div>
            )}
            <div className="ratings">
              {RATINGS.map(({ r, label, hint }) => (
                <button key={r} className={`rate r${r}`} title={hint} onClick={() => grade(item.id, r)}>
                  {label}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>

      <form
        className="row"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!title.trim()) return;
          await api.addItem(title.trim(), "exercise");
          setTitle("");
          queue.reload();
        }}
      >
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Add a practice item, e.g. A minor arpeggio HT" />
        <button type="submit">Add</button>
      </form>
    </div>
  );
}

/** Achievements earned since this tablet last looked, so each one is celebrated once. */
function useNewAchievements(list: Achievement[] | undefined): [Achievement[], () => void] {
  const [fresh, setFresh] = useState<Achievement[]>([]);
  useEffect(() => {
    if (!list) return;
    let seen: string[] | null = null;
    try {
      seen = JSON.parse(localStorage.getItem("pc-achievements-seen") ?? "null");
    } catch {
      seen = null;
    }
    const earned = list.filter((a) => a.earned).map((a) => a.id);
    // First run: remember what's already earned without a burst of old celebrations.
    if (seen) setFresh(list.filter((a) => a.earned && !seen!.includes(a.id)));
    try {
      localStorage.setItem("pc-achievements-seen", JSON.stringify(earned));
    } catch {
      /* private mode: celebrate nothing rather than everything */
    }
  }, [list]);
  return [fresh, () => setFresh([])];
}
