// Thin typed client for the Pi backend. Same origin in production (the Pi serves the app);
// the vite dev server proxies /api to the Pi during development.

export interface Piece {
  id: number;
  catalog_id?: string | null;
  title: string;
  composer?: string | null;
  arranger?: string | null;
  category?: string | null;
  level_henle?: number | null;
  level_abrsm?: number | null;
  skills: string[];
  license?: string | null;
  source_url?: string | null;
  musicxml_path?: string | null;
  pdf_path?: string | null;
  pdf_annotated_path?: string | null;
  midi_path?: string | null;
  tags: string[];
  meta: Record<string, unknown>;
}

export interface PracticeItem {
  id: number;
  kind: string;
  title: string;
  piece_id?: number | null;
  stage?: string | null;
  details: Record<string, unknown>;
  due: string;
  active?: boolean;
  retrievability?: number;
  piece?: Piece | null;
}

export interface AutoGrade {
  rating: 1 | 2 | 3 | 4;
  metrics: Record<string, number | null>;
  session_id: number;
}

export interface PracticeSession {
  id: number;
  started_at: string;
  ended_at?: string | null;
  midi_path?: string | null;
  audio_path?: string | null;
  note_count: number;
  metrics: Record<string, number | null>;
  analysis: Record<string, unknown>;
  notes?: string | null;
}

export interface Stats {
  streak_days: number;
  minutes_by_day: Record<string, number>;
  total_minutes: number;
  sessions: number;
}

export interface Goals {
  daily_minutes: number;
  weekly_days: number;
  streak_min_minutes: number;
}

export interface TechniquePoint {
  date: string;
  attempts: number;
  accuracy: number | null;
  evenness: number | null;
  clean_bpm: number | null;
  rating: number;
}

export interface TechniqueTrend {
  family?: string;
  concept_id?: string | null;
  attempts: number;
  days: number;
  accuracy_now: number | null;
  accuracy_change: number | null;
  best_clean_bpm: number | null;
  last_at: string | null;
  series: TechniquePoint[];
}

export interface Achievement {
  id: string;
  title: string;
  desc: string;
  earned: boolean;
  progress: number;
}

export type DayStatus = "practiced" | "frozen" | "missed" | "pending" | "none";

export interface Progress {
  today: string;
  goals: Goals;
  streak: {
    current: number;
    longest: number;
    freezes: number;
    max_freezes: number;
    practiced_today: boolean;
    at_risk: boolean;
    week_days: number;
    week_streak: number;
    best_week_streak: number;
    frozen_days: number;
  };
  today_minutes: number;
  today_xp: number;
  xp: { level: number; xp: number; level_start: number; next_level: number; progress: number };
  time: {
    total_minutes: number;
    sessions: number;
    avg_session_minutes: number | null;
    last7_minutes: number;
    last30_minutes: number;
    by_hour: number[];
    weeks: { week: string; minutes: number; days: number }[];
  };
  consistency: {
    days_last30: number;
    goal_days_last30: number;
    practice_days: number;
    calendar: { date: string; minutes: number; status: DayStatus; goal: boolean; xp: number }[];
  };
  technique: { overall: TechniqueTrend; families: TechniqueTrend[] };
  achievements: Achievement[];
}

export type TakeKind = "performance" | "cover";

export interface TakeInfo {
  title: string;
  kind: TakeKind;
  piece_id?: number | null;
  started_at: string;
  note_count: number;
}

export interface Performance {
  id: number;
  title: string;
  kind: TakeKind;
  piece_id?: number | null;
  started_at: string;
  duration_s: number;
  midi_path?: string | null;
  note_count: number;
  metrics: Record<string, number | boolean | null>;
  favorite: boolean;
  notes?: string | null;
}

export interface Status {
  midi_port?: string | null;
  midi_enabled: boolean;
  recording?: boolean;
  audio?: boolean;
  take?: TakeInfo | null;
}

export interface TechniqueResult {
  id: number;
  rating: 1 | 2 | 3 | 4;
  metrics: {
    accuracy: number;
    tempo_ratio: number | null;
    achieved_bpm: number | null;
    ibi_cv: number | null;
    timing_dev_ms: number | null;
    breakdowns: number;
    matched: number;
    expected: number;
    extra: number;
  };
  applied: boolean; // became the concept card's FSRS review (only when it was due)
  practice_item_id: number | null;
  next_due: string | null;
}

export interface TechniqueAttemptRow {
  id: number;
  created_at: string;
  family: string;
  concept_id: string | null;
  title: string;
  bpm: number;
  rating: 1 | 2 | 3 | 4;
  metrics: TechniqueResult["metrics"];
  applied: boolean;
}

export interface TechniqueAttemptIn {
  family: string;
  title: string;
  concept_id: string;
  bpm: number;
  steps_per_beat: number;
  steps: number[][];
  notes: { note: number; t: number }[];
  match: "pitch" | "pitch_class";
  drill: Record<string, unknown>;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/api${path}`, init);
  if (!r.ok) throw new Error(`${init?.method ?? "GET"} ${path}: ${r.status}`);
  return r.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  status: () => req<Status>("/status"),
  stats: () => req<Stats>("/stats"),
  progress: () => req<Progress>("/progress"),
  setGoals: (g: Partial<Goals>) => req<Goals>("/goals", json("PUT", g)),
  queue: () => req<PracticeItem[]>("/practice/queue"),
  items: () => req<PracticeItem[]>("/practice/items"),
  addItem: (title: string, kind: string) => req<PracticeItem>("/practice/items", json("POST", { title, kind })),
  review: (id: number, rating: 1 | 2 | 3 | 4) =>
    req<PracticeItem>(`/practice/items/${id}/review`, json("POST", { rating })),
  sessions: () => req<PracticeSession[]>("/sessions"),
  patchSession: (id: number, notes: string) => req<PracticeSession>(`/sessions/${id}`, json("PATCH", { notes })),
  pieces: (q = "", category = "", hasScore = true) =>
    req<Piece[]>(`/pieces?${new URLSearchParams({ q, category, has_score: String(hasScore) })}`),
  autograde: (id: number, session_id?: number) =>
    req<AutoGrade>(`/practice/items/${id}/autograde`, json("POST", { session_id })),
  addPiece: (title: string, composer: string) => req<Piece>("/pieces", json("POST", { title, composer })),
  uploadScore: (id: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return req<Piece>(`/pieces/${id}/files`, { method: "POST", body: fd });
  },
  performances: () => req<Performance[]>("/performances"),
  startTake: (title: string, kind: TakeKind) => req<TakeInfo>("/performances/start", json("POST", { title, kind })),
  stopTake: () => req<{ performance: Performance | null }>("/performances/stop", { method: "POST" }),
  cancelTake: () => req<{ cancelled: boolean }>("/performances/cancel", { method: "POST" }),
  patchPerformance: (id: number, patch: Partial<Pick<Performance, "title" | "kind" | "favorite" | "notes">>) =>
    req<Performance>(`/performances/${id}`, json("PATCH", patch)),
  deletePerformance: async (id: number) => {
    const r = await fetch(`/api/performances/${id}`, { method: "DELETE" });
    if (!r.ok) throw new Error(`DELETE /performances/${id}: ${r.status}`);
  },
  performanceMidiUrl: (id: number) => `/api/performances/${id}/midi`,
  techniqueAttempt: (body: TechniqueAttemptIn) => req<TechniqueResult>("/technique/attempts", json("POST", body)),
  techniqueAttempts: (limit = 20) => req<TechniqueAttemptRow[]>(`/technique/attempts?limit=${limit}`),
  libraryUrl: (rel: string) => `/api/library/${rel}`,
  sessionFileUrl: (id: number, kind: "midi" | "audio") => `/api/sessions/${id}/${kind}`,
};

export function liveSocketUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/api/live`;
}
