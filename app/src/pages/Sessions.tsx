import { api } from "../api";
import { useData } from "../hooks";
import { formatDuration, noteName } from "../midi";

export default function Sessions({ lastSaved }: { lastSaved: number | null }) {
  const sessions = useData(api.sessions, [lastSaved]);
  return (
    <div className="page">
      <h2>Practice log</h2>
      <p className="muted">Sessions are recorded automatically when you play, and end after a pause.</p>
      {sessions.error && <p className="error">{sessions.error}</p>}
      <ul className="queue">
        {sessions.data?.map((s) => (
          <li key={s.id} className="item column">
            <div className="row spread">
              <div>
                <div className="title">
                  {new Date(s.started_at.endsWith("Z") ? s.started_at : s.started_at + "Z").toLocaleString()}
                </div>
                <div className="muted">
                  {formatDuration(s.started_at, s.ended_at)} · {s.note_count} notes
                  {s.metrics.pitch_low != null &&
                    ` · ${noteName(s.metrics.pitch_low)}–${noteName(s.metrics.pitch_high ?? 0)}`}
                  {s.metrics.ioi_cv != null && ` · pulse variation ${(s.metrics.ioi_cv * 100).toFixed(0)}%`}
                </div>
              </div>
              <div className="row">
                {s.midi_path && (
                  <a className="button" href={api.sessionFileUrl(s.id, "midi")} download>
                    MIDI
                  </a>
                )}
              </div>
            </div>
            {s.audio_path && <audio controls preload="none" src={api.sessionFileUrl(s.id, "audio")} />}
            <input
              defaultValue={s.notes ?? ""}
              placeholder="Notes for this session"
              onBlur={(e) => e.target.value !== (s.notes ?? "") && api.patchSession(s.id, e.target.value)}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}
