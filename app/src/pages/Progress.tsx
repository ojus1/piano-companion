import { useState } from "react";
import { api, type Goals, type Progress as P, type TechniqueTrend } from "../api";
import { useData } from "../hooks";
import { FAMILIES } from "../technique";
import { Bars, Calendar, Line, Ring } from "../components/Charts";

const familyLabel = (id?: string) => FAMILIES.find((f) => f.id === id)?.label ?? id ?? "All drills";
const pct = (v: number) => `${Math.round(v * 100)}%`;
const hrs = (m: number) => (m >= 60 ? `${(m / 60).toFixed(1)} h` : `${Math.round(m)} min`);
const DOW = ["M", "T", "W", "T", "F", "S", "S"];

export default function Progress({ lastSaved }: { lastSaved: number | null }) {
  const p = useData(api.progress, [lastSaved]);
  if (p.error) return <div className="page"><p className="error">Can't reach the Pi: {p.error}</p></div>;
  if (!p.data) return <div className="page"><p className="muted">Loading…</p></div>;
  return <Dashboard p={p.data} reload={p.reload} />;
}

function Dashboard({ p, reload }: { p: P; reload: () => void }) {
  const s = p.streak;
  const cal = p.consistency.calendar;
  const last30 = cal.slice(-30);
  const weekStartIdx = cal.length - (cal.length % 7 || 7);
  const thisWeek = cal.slice(weekStartIdx);

  return (
    <div className="page progress">
      <section className="hero">
        <div className="stat streak-card">
          <div className={`flame ${s.practiced_today ? "lit" : ""}`} aria-hidden>🔥</div>
          <div className="big">{s.current}</div>
          <div>day streak</div>
          <div className="muted">
            {s.at_risk ? "Play today to keep it" : s.practiced_today ? "Today counts ✓" : "Play to start one"} · best {s.longest}
          </div>
          <div className="freezes" title="Streak freezes: a missed day uses one instead of breaking your streak. Hit the weekly goal to earn more.">
            {Array.from({ length: s.max_freezes }, (_, i) => (
              <span key={i} className={i < s.freezes ? "freeze on" : "freeze"}>❄</span>
            ))}
            <span className="muted"> {s.freezes} freeze{s.freezes === 1 ? "" : "s"}</span>
          </div>
        </div>
        <div className="stat">
          <Ring value={p.today_minutes} goal={p.goals.daily_minutes} label="Today's minutes against the daily goal" />
          <div>daily goal</div>
          <div className="muted">+{p.today_xp} XP today</div>
        </div>
        <div className="stat">
          <div className="week-dots">
            {DOW.map((d, i) => {
              const day = thisWeek[i];
              const cls = !day ? "future" : day.status === "practiced" ? "done" : day.status === "frozen" ? "frozen" : day.status === "pending" ? "today" : "miss";
              return (
                <span key={i} className={`wd ${cls}`}>
                  {d}
                </span>
              );
            })}
          </div>
          <div className="big small">
            {s.week_days}/{p.goals.weekly_days}
          </div>
          <div>days this week</div>
          <div className="muted">
            {s.week_streak} week streak · best {s.best_week_streak}
          </div>
        </div>
        <div className="stat">
          <div className="level">Lv {p.xp.level}</div>
          <div className="xpbar">
            <div style={{ width: pct(p.xp.progress) }} />
          </div>
          <div className="muted">
            {p.xp.xp} XP · {p.xp.next_level - p.xp.xp} to level {p.xp.level + 1}
          </div>
          <div className="muted">XP = practice minutes + drill accuracy + goal bonuses</div>
        </div>
      </section>

      <h2>Consistency</h2>
      <div className="panel">
        <div className="chips">
          <Chip v={`${p.consistency.days_last30}/30`} l="days practised (30 d)" />
          <Chip v={`${p.consistency.goal_days_last30}`} l="days goal met (30 d)" />
          <Chip v={`${p.consistency.practice_days}`} l="practice days total" />
          <Chip v={`${s.frozen_days}`} l="freezes used" />
        </div>
        <Calendar days={cal} goal={p.goals.daily_minutes} />
      </div>

      <h2>Time spent</h2>
      <div className="panel">
        <div className="chips">
          <Chip v={hrs(p.time.last7_minutes)} l="last 7 days" />
          <Chip v={hrs(p.time.last30_minutes)} l="last 30 days" />
          <Chip v={hrs(p.time.total_minutes)} l="all time" />
          <Chip v={p.time.avg_session_minutes ? `${Math.round(p.time.avg_session_minutes)} min` : "–"} l="avg session" />
        </div>
        <h3>Minutes per day</h3>
        <Bars
          unit="min"
          goal={p.goals.daily_minutes}
          data={last30.map((d) => ({
            label: new Date(d.date + "T12:00:00").getDate().toString(),
            value: d.minutes,
            tip: `${new Date(d.date + "T12:00:00").toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}: ${Math.round(d.minutes)} min`,
          }))}
        />
        <div className="two">
          <div>
            <h3>Hours per week</h3>
            <Bars
              unit="h"
              width={360}
              height={150}
              data={p.time.weeks.slice(-12).map((w) => ({
                label: new Date(w.week + "T12:00:00").toLocaleDateString(undefined, { month: "numeric", day: "numeric" }),
                value: Math.round((w.minutes / 60) * 10) / 10,
                tip: `Week of ${new Date(w.week + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" })}: ${hrs(w.minutes)} on ${w.days} day${w.days === 1 ? "" : "s"}`,
              }))}
            />
          </div>
          <div>
            <h3>When you practise</h3>
            <Bars
              unit="min"
              width={360}
              height={150}
              data={p.time.by_hour.map((m, h) => ({ label: `${h}`, value: Math.round(m), tip: `${h}:00–${h + 1}:00: ${hrs(m)} total` }))}
            />
          </div>
        </div>
      </div>

      <Technique t={p.technique} />

      <h2>Achievements</h2>
      <div className="badges">
        {p.achievements.map((a) => (
          <div key={a.id} className={a.earned ? "badge earned" : "badge"} title={a.desc}>
            <div className="badge-icon">{a.earned ? "🏆" : "🔒"}</div>
            <div className="title">{a.title}</div>
            <div className="muted">{a.desc}</div>
            {!a.earned && (
              <div className="xpbar thin">
                <div style={{ width: pct(a.progress) }} />
              </div>
            )}
          </div>
        ))}
      </div>

      <GoalsForm goals={p.goals} onSaved={reload} />
    </div>
  );
}

function Technique({ t }: { t: P["technique"] }) {
  const [sel, setSel] = useState<string>("");
  const trend: TechniqueTrend = (sel && t.families.find((f) => f.family === sel)) || t.overall;
  return (
    <>
      <h2>Technique</h2>
      <div className="panel">
        {t.overall.attempts === 0 ? (
          <p className="muted">Play some drills on the Technique tab and your accuracy, clean tempo and evenness will chart here.</p>
        ) : (
          <>
            <div className="row">
              <select value={sel} onChange={(e) => setSel(e.target.value)}>
                <option value="">All drills</option>
                {t.families.map((f) => (
                  <option key={f.family} value={f.family}>
                    {familyLabel(f.family)} ({f.attempts})
                  </option>
                ))}
              </select>
            </div>
            <div className="chips">
              <Chip v={`${trend.attempts}`} l="attempts" />
              <Chip v={trend.accuracy_now !== null ? pct(trend.accuracy_now) : "–"} l="accuracy now" />
              <Chip
                v={trend.accuracy_change !== null ? `${trend.accuracy_change >= 0 ? "+" : ""}${Math.round(trend.accuracy_change * 100)} pts` : "–"}
                l="since you started"
                good={trend.accuracy_change !== null ? trend.accuracy_change >= 0 : undefined}
              />
              <Chip v={trend.best_clean_bpm ? `${Math.round(trend.best_clean_bpm)}` : "–"} l="best clean BPM (≥90% notes)" />
            </div>
            <h3>Accuracy</h3>
            <Line points={trend.series.map((s) => ({ date: s.date, value: s.accuracy }))} format={pct} max={1} />
            <div className="two">
              <div>
                <h3>Clean tempo (BPM)</h3>
                <Line width={360} height={150} points={trend.series.map((s) => ({ date: s.date, value: s.clean_bpm }))} format={(v) => `${Math.round(v)}`} />
              </div>
              <div>
                <h3>Evenness</h3>
                <Line width={360} height={150} points={trend.series.map((s) => ({ date: s.date, value: s.evenness }))} format={pct} max={1} />
              </div>
            </div>
            {!sel && t.families.length > 1 && (
              <table className="fam-table">
                <thead>
                  <tr>
                    <th>Drill</th>
                    <th>Attempts</th>
                    <th>Accuracy</th>
                    <th>Change</th>
                    <th>Best clean BPM</th>
                  </tr>
                </thead>
                <tbody>
                  {t.families.map((f) => (
                    <tr key={f.family} onClick={() => setSel(f.family!)}>
                      <td>{familyLabel(f.family)}</td>
                      <td>{f.attempts}</td>
                      <td>{f.accuracy_now !== null ? pct(f.accuracy_now) : "–"}</td>
                      <td>{f.accuracy_change !== null ? `${f.accuracy_change >= 0 ? "+" : ""}${Math.round(f.accuracy_change * 100)}` : "–"}</td>
                      <td>{f.best_clean_bpm ? Math.round(f.best_clean_bpm) : "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>
    </>
  );
}

function Chip({ v, l, good }: { v: string; l: string; good?: boolean }) {
  return (
    <div className="chip">
      <div className={`chip-v ${good === true ? "up" : good === false ? "down" : ""}`}>{v}</div>
      <div className="muted">{l}</div>
    </div>
  );
}

function GoalsForm({ goals, onSaved }: { goals: Goals; onSaved: () => void }) {
  const [g, setG] = useState(goals);
  const [msg, setMsg] = useState("");
  const dirty = g.daily_minutes !== goals.daily_minutes || g.weekly_days !== goals.weekly_days || g.streak_min_minutes !== goals.streak_min_minutes;
  return (
    <>
      <h2>Goals</h2>
      <form
        className="panel goals"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await api.setGoals(g);
            setMsg("Saved");
            onSaved();
          } catch (err) {
            setMsg(String(err));
          }
        }}
      >
        <label>
          Daily goal (minutes)
          <input type="number" min={1} max={600} value={g.daily_minutes} onChange={(e) => setG({ ...g, daily_minutes: +e.target.value })} />
        </label>
        <label>
          Weekly goal (days of 7)
          <input type="number" min={1} max={7} value={g.weekly_days} onChange={(e) => setG({ ...g, weekly_days: +e.target.value })} />
        </label>
        <label>
          A day counts for the streak after (minutes)
          <input type="number" min={1} max={120} value={g.streak_min_minutes} onChange={(e) => setG({ ...g, streak_min_minutes: +e.target.value })} />
        </label>
        <div className="row">
          <button type="submit" disabled={!dirty}>
            Save goals
          </button>
          <span className="muted">{msg}</span>
        </div>
      </form>
    </>
  );
}
