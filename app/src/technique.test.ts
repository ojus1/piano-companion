import { describe, expect, it } from "vitest";
import { FAMILIES, advance, generateDrill, spellAs, startProgress, type FamilyId } from "./technique";

// Small deterministic PRNG (mulberry32) so tests are reproducible.
function rng(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const only = (f: FamilyId, seed = 1, keys: "easy" | "all" = "all") =>
  generateDrill({ families: [f], keys, tempo: "medium" }, rng(seed));

describe("spelling", () => {
  it("names pitches by letter", () => {
    expect(spellAs(61, 0)).toBe("C♯4");
    expect(spellAs(61, 1)).toBe("D♭4");
    expect(spellAs(60, 6)).toBe("B♯3");
    expect(spellAs(65, 2)).toBe("E♯4");
  });
});

describe("drills", () => {
  it("every family generates a sane drill in every key pool", () => {
    for (const f of FAMILIES)
      for (let s = 1; s < 40; s++) {
        const d = only(f.id, s, s % 2 ? "all" : "easy");
        expect(d.family).toBe(f.id);
        expect(d.steps.length).toBeGreaterThan(4);
        expect(d.bpm).toBeGreaterThanOrEqual(30);
        for (const st of d.steps) {
          expect(st.notes.length).toBeGreaterThan(0);
          for (const n of st.notes) expect(n >= 21 && n <= 108).toBe(true);
          expect(st.label).not.toContain("?");
        }
      }
  });

  it("major scales are spelled with one of each letter and go up and back", () => {
    for (let s = 1; s < 60; s++) {
      const d = only("scale_major", s);
      const n = d.steps.map((x) => x.notes[0]);
      const steps = n.slice(1).map((x, i) => x - n[i]);
      const half = (n.length - 1) / 2;
      expect(steps.slice(0, 7)).toEqual([2, 2, 1, 2, 2, 2, 1]);
      expect(n[0]).toBe(n[n.length - 1]);
      expect(n[half] - n[0]).toBe(half === 7 ? 12 : 24);
      const letters = d.steps.slice(0, 7).map((x) => x.label[0]);
      expect(new Set(letters).size).toBe(7);
    }
  });

  it("melodic minor goes up raised and comes down natural", () => {
    let found = false;
    for (let s = 1; s < 80 && !found; s++) {
      const d = only("scale_minor", s);
      if (!d.title.includes("melodic") || d.detail.includes("2 octaves")) continue;
      found = true;
      const n = d.steps.map((x) => x.notes[0] - d.steps[0].notes[0]);
      expect(n).toEqual([0, 2, 3, 5, 7, 9, 11, 12, 10, 8, 7, 5, 3, 2, 0]);
    }
    expect(found).toBe(true);
  });

  it("A major scale spells F♯ C♯ G♯", () => {
    for (let s = 1; s < 200; s++) {
      const d = only("scale_major", s);
      if (!d.title.startsWith("A major") || d.hands !== "RH") continue;
      expect(d.steps.slice(0, 8).map((x) => x.label)).toEqual(["A4", "B4", "C♯5", "D5", "E5", "F♯5", "G♯5", "A5"]);
      return;
    }
    throw new Error("no A major drill generated");
  });

  it("triad inversions climb through root, first and second inversion", () => {
    const d = only("triad_inversions", 3);
    const [root, first, second, top] = d.steps.map((x) => x.notes);
    expect(first[0]).toBe(root[1]);
    expect(second[0]).toBe(root[2]);
    expect(top[0]).toBe(root[0] + 12);
  });

  it("bpm scales with the tempo level", () => {
    const slow = generateDrill({ families: ["scale_major"], keys: "easy", tempo: "slow" }, rng(5));
    const fast = generateDrill({ families: ["scale_major"], keys: "easy", tempo: "fast" }, rng(5));
    expect(fast.bpm).toBeGreaterThan(slow.bpm);
  });

  it("avoids repeating the previous family", () => {
    for (let s = 1; s < 20; s++) {
      const d = generateDrill({ families: ["scale_major", "chromatic"], keys: "easy", tempo: "medium", previous: "chromatic" }, rng(s));
      expect(d.family).toBe("scale_major");
    }
  });
});

describe("live progress", () => {
  it("advances on right notes, skips a missed one, counts wrong ones", () => {
    const d = only("scale_major", 2);
    const n = d.steps.map((x) => x.notes[0]);
    let p = startProgress();
    p = advance(d, p, n[0]);
    p = advance(d, p, n[2]); // skipped step 1
    expect(p.index).toBe(3);
    p = advance(d, p, 20);
    expect(p).toMatchObject({ index: 3, wrong: 1 });
  });

  it("chords need every tone; chord symbols accept any octave", () => {
    const d = only("chord_flashcards", 4);
    let p = startProgress();
    const [a, b, c] = d.steps[0].notes;
    p = advance(d, p, a + 12);
    p = advance(d, p, b - 12);
    expect(p.index).toBe(0);
    p = advance(d, p, c);
    if (d.steps[0].notes.length === 3) expect(p.index).toBe(1);
  });
});
