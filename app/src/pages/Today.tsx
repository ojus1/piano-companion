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

  const today = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
  const minutesPct = p ? Math.min(1, p.today_minutes / Math.max(1, p.goals.daily_minutes)) : 0;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Today</h1>
          <p>{today}</p>
        </div>
      </div>

      {fresh.length > 0 && (
        <div className="notice" onClick={dismiss} role="status">
          <span>
            Achievement unlocked: <strong>{fresh.map((a) => a.title).join(", ")}</strong>
          </span>
          <span className="muted">Dismiss</span>
        </div>
      )}

      <section className="strip">
        <div className="cell">
          <div className="label">Streak</div>
          <div className="big">
            {p?.streak.current ?? "–"}
            <span className="unit">days</span>
          </div>
          {p && (
            <div className="sub">
              {p.streak.at_risk ? "Play today to keep it" : p.streak.practiced_today ? "Today counts" : "Play to start one"} ·{" "}
              {p.streak.freezes} freeze{p.streak.freezes === 1 ? "" : "s"} left
            </div>
          )}
        </div>
        <div className="cell">
          <div className="label">Practised today</div>
          <div className="big">
            {Math.round(p?.today_minutes ?? 0)}
            <span className="unit">/ {p?.goals.daily_minutes ?? "–"} min</span>
          </div>
          <div className="meter" aria-hidden>
            <div style={{ width: `${minutesPct * 100}%` }} />
          </div>
          {p && <div className="sub">{goalLeft > 0 ? `${Math.ceil(goalLeft)} min to your daily goal` : "Daily goal met"}</div>}
        </div>
        <div className="cell">
          <div className="label">Due for review</div>
          <div className="big">
            {queue.data?.length ?? "–"}
            <span className="unit">item{queue.data?.length === 1 ? "" : "s"}</span>
          </div>
          {p && (
            <div className="sub">
              Level {p.xp.level} · {p.streak.week_days} of {p.goals.weekly_days} days this week
            </div>
          )}
        </div>
      </section>

      <h2>Practice queue</h2>
      {queue.error && <p className="error">Can't reach the Pi: {queue.error}</p>}
      {queue.data?.length === 0 && <p className="muted">Nothing due. Free play, or add an item below.</p>}
      <ul className="queue">
        {queue.data?.map((item) => (
          <li key={item.id} className="item">
            <div className="grow">
              <div className="title">{item.title}</div>
              <div className="muted">
                {[item.stage, item.kind.replace("_", " "), item.details.role as string | undefined].filter(Boolean).join(" · ")}
              </div>
              {typeof graded[item.id] === "string" && <div className="error">{graded[item.id] as string}</div>}
            </div>
            <div className="actions">
              {item.piece && (
                <>
                  <button className="ghost" onClick={() => setOpen(item.piece!)}>
                    Score
                  </button>
                  {(item.piece.musicxml_path || item.piece.midi_path) && (
                    <button className="ghost" title="Grade your last recorded take against the score" onClick={() => autograde(item.id)}>
                      Auto-grade
                    </button>
                  )}
                </>
              )}
              <div className="ratings" role="group" aria-label="How did it go?">
                {RATINGS.map(({ r, label, hint }) => (
                  <button key={r} className={`rate r${r}`} title={hint} onClick={() => grade(item.id, r)}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </li>
        ))}
      </ul>

      <form
        className="row"
        style={{ marginTop: 16 }}
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
