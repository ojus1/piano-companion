// Pure helpers, unit-tested in midi.test.ts.

const NAMES = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"];

export function noteName(n: number): string {
  return `${NAMES[n % 12]}${Math.floor(n / 12) - 1}`;
}

export function isBlackKey(n: number): boolean {
  return [1, 3, 6, 8, 10].includes(n % 12);
}

/** Track which keys are held, from the backend's live MIDI events. */
export function applyMidiEvent(held: ReadonlySet<number>, ev: { type: string; note?: number; velocity?: number }) {
  if (ev.note === undefined) return held;
  const next = new Set(held);
  if (ev.type === "note_on" && (ev.velocity ?? 0) > 0) next.add(ev.note);
  else if (ev.type === "note_off" || ev.type === "note_on") next.delete(ev.note);
  return next;
}

export function formatDuration(startIso: string, endIso?: string | null): string {
  if (!endIso) return "in progress";
  const s = Math.round((Date.parse(endIso) - Date.parse(startIso)) / 1000);
  const m = Math.floor(s / 60);
  return m > 0 ? `${m} min ${s % 60}s` : `${s}s`;
}
