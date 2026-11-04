import { describe, expect, it } from "vitest";
import { applyMidiEvent, formatDuration, isBlackKey, noteName } from "./midi";

describe("midi helpers", () => {
  it("names notes", () => {
    expect(noteName(60)).toBe("C4");
    expect(noteName(21)).toBe("A0");
    expect(noteName(108)).toBe("C8");
  });
  it("knows black keys", () => {
    expect(isBlackKey(61)).toBe(true);
    expect(isBlackKey(60)).toBe(false);
  });
  it("tracks held keys, treating velocity-0 note_on as off", () => {
    let held: ReadonlySet<number> = new Set();
    held = applyMidiEvent(held, { type: "note_on", note: 60, velocity: 80 });
    held = applyMidiEvent(held, { type: "note_on", note: 64, velocity: 80 });
    held = applyMidiEvent(held, { type: "note_on", note: 60, velocity: 0 });
    expect([...held]).toEqual([64]);
    held = applyMidiEvent(held, { type: "note_off", note: 64 });
    expect(held.size).toBe(0);
  });
  it("formats durations", () => {
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:02:05Z")).toBe("2 min 5s");
    expect(formatDuration("2026-01-01T00:00:00Z", null)).toBe("in progress");
  });
});
