import { useState } from "react";
import { api } from "../api";
import { useData } from "../hooks";

const RATINGS = [
  { r: 1, label: "Again", hint: "fell apart" },
  { r: 2, label: "Hard", hint: "got through, struggling" },
  { r: 3, label: "Good", hint: "solid with effort" },
  { r: 4, label: "Easy", hint: "effortless" },
] as const;

export default function Today({ lastSaved }: { lastSaved: number | null }) {
  const queue = useData(api.queue);
  const stats = useData(api.stats, [lastSaved]);
  const [title, setTitle] = useState("");

  const grade = async (id: number, r: 1 | 2 | 3 | 4) => {
    await api.review(id, r);
    queue.reload();
  };

  const today = new Date().toLocaleDateString("en-CA");
  const minutesToday = stats.data?.minutes_by_day[today] ?? 0;

  return (
    <div className="page">
      <section className="cards">
        <div className="stat">
          <div className="big">{stats.data?.streak_days ?? "–"}</div>
          <div>day streak</div>
        </div>
        <div className="stat">
          <div className="big">{Math.round(minutesToday)}</div>
          <div>minutes today</div>
        </div>
        <div className="stat">
          <div className="big">{queue.data?.length ?? "–"}</div>
          <div>items due</div>
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
              <div className="muted">{item.kind.replace("_", " ")}</div>
            </div>
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
