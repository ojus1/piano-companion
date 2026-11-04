// Randomized technique drills: scales, arpeggios, broken chords and chord work, each at a random BPM.
// Pure and seedable (pass your own rng), unit-tested in technique.test.ts.
//
// Each drill family maps to a technique/theory node of the research curriculum's concept graph
// (curriculum.json), so a graded run becomes a review of that concept's spaced-repetition card.

export type Hands = "RH" | "LH" | "HT";
export type Rng = () => number;

export interface Step {
  notes: number[]; // MIDI pitches that sound together
  label: string; // what to show: a note name ("F♯4") or a chord symbol ("E♭m")
}

export interface Drill {
  family: FamilyId;
  concept: string;
  title: string;
  detail: string; // "8ths · 2 octaves"
  key: string;
  hands: Hands;
  bpm: number;
  stepsPerBeat: number;
  beatsPerBar: number;
  steps: Step[];
  /** Chord flashcards accept any octave/inversion: match pitch classes only. */
  match: "pitch" | "pitch_class";
}

// ---------- spelling ----------

const LETTERS = ["C", "D", "E", "F", "G", "A", "B"];
const NATURAL = [0, 2, 4, 5, 7, 9, 11];
const ACC: Record<number, string> = { [-2]: "𝄫", [-1]: "♭", 0: "", 1: "♯", 2: "𝄪" };

interface Tonic {
  letter: number; // index into LETTERS
  acc: number; // -1, 0, 1
}

export function parseTonic(s: string): Tonic {
  const letter = LETTERS.indexOf(s[0]);
  const acc = s.slice(1) === "#" || s.slice(1) === "♯" ? 1 : s.slice(1) === "b" || s.slice(1) === "♭" ? -1 : 0;
  return { letter, acc };
}

const pcOf = (t: Tonic) => (((NATURAL[t.letter] + t.acc) % 12) + 12) % 12;
const tonicName = (t: Tonic) => LETTERS[t.letter] + ACC[t.acc];

/** Name a pitch as the given letter (index into LETTERS, any integer), e.g. (61, 0) -> "C♯4". */
export function spellAs(midi: number, letter: number): string {
  const l = ((letter % 7) + 7) % 7;
  const acc = ((((midi % 12) - NATURAL[l]) % 12) + 18) % 12 - 6;
  const natural = midi - acc;
  return `${LETTERS[l]}${ACC[acc] ?? "?"}${Math.floor(natural / 12) - 1}`;
}

// ---------- scales and chords ----------

const SCALES = {
  major: [0, 2, 4, 5, 7, 9, 11],
  natural_minor: [0, 2, 3, 5, 7, 8, 10],
  harmonic_minor: [0, 2, 3, 5, 7, 8, 11],
  melodic_minor: [0, 2, 3, 5, 7, 9, 11],
} as const;
type ScaleName = keyof typeof SCALES;

const CHORDS = {
  maj: { iv: [0, 4, 7], sym: "" },
  min: { iv: [0, 3, 7], sym: "m" },
  dim: { iv: [0, 3, 6], sym: "°" },
  aug: { iv: [0, 4, 8], sym: "+" },
  maj7: { iv: [0, 4, 7, 11], sym: "maj7" },
  dom7: { iv: [0, 4, 7, 10], sym: "7" },
  min7: { iv: [0, 3, 7, 10], sym: "m7" },
  hdim7: { iv: [0, 3, 6, 10], sym: "ø7" },
  dim7: { iv: [0, 3, 6, 9], sym: "°7" },
} as const;
type ChordName = keyof typeof CHORDS;

/** One note of a scale by degree index (0 = tonic, may be negative or > 6), spelled in the key. */
function degree(t: Tonic, base: number, scale: readonly number[], d: number) {
  const oct = Math.floor(d / 7);
  const i = ((d % 7) + 7) % 7;
  const midi = base + oct * 12 + scale[i];
  return { midi, name: spellAs(midi, t.letter + d) };
}

/** Chord tone k (0 = root, 1 = third, ...; k >= tones wraps up an octave), spelled by stacked thirds. */
function chordTone(t: Tonic, base: number, chord: ChordName, k: number) {
  const iv = CHORDS[chord].iv;
  const oct = Math.floor(k / iv.length);
  const i = k % iv.length;
  const midi = base + oct * 12 + iv[i];
  return { midi, name: spellAs(midi, t.letter + 2 * i) };
}

/** Register: RH tonic in octave 4 (C4..B4), LH an octave lower. */
const rhBase = (t: Tonic) => 60 + pcOf(t);
const upDown = (n: number) => [...Array(n + 1).keys(), ...[...Array(n).keys()].reverse()];

function handed(t: Tonic, hands: Hands, at: (base: number) => { midi: number; name: string }): Step {
  const rh = at(rhBase(t));
  const lh = at(rhBase(t) - 12);
  if (hands === "RH") return { notes: [rh.midi], label: rh.name };
  if (hands === "LH") return { notes: [lh.midi], label: lh.name };
  return { notes: [lh.midi, rh.midi], label: rh.name.replace(/-?\d+$/, "") };
}

// ---------- families ----------

export type FamilyId =
  | "five_finger"
  | "scale_major"
  | "scale_minor"
  | "scale_ht"
  | "contrary"
  | "chromatic"
  | "arpeggio_root"
  | "arpeggio_inversion"
  | "arpeggio_7th"
  | "alberti"
  | "triad_inversions"
  | "seventh_inversions"
  | "chord_flashcards";

interface Ctx {
  rng: Rng;
  pick: <T>(xs: readonly T[]) => T;
  major: Tonic;
  minor: Tonic;
}

interface Family {
  id: FamilyId;
  label: string;
  group: "Scales" | "Arpeggios" | "Chords";
  concept: string; // curriculum concept-graph node
  bpm: [number, number]; // quarter-note range at "Medium"
  stepsPerBeat: number;
  make: (c: Ctx) => Omit<Drill, "family" | "concept" | "bpm" | "detail" | "stepsPerBeat" | "beatsPerBar" | "match"> &
    Partial<Pick<Drill, "match" | "stepsPerBeat">> & { extra?: string };
}

const HS: Hands[] = ["RH", "LH"];
const ALL_HANDS: Hands[] = ["RH", "LH", "HT"];

export const FAMILIES: Family[] = [
  {
    id: "five_finger",
    label: "Five-finger patterns",
    group: "Scales",
    concept: "t_five_finger",
    bpm: [60, 96],
    stepsPerBeat: 2,
    make: ({ pick, major, minor }) => {
      const minorMode = pick([false, true]);
      const t = minorMode ? minor : major;
      const scale = minorMode ? SCALES.natural_minor : SCALES.major;
      const hands = pick(ALL_HANDS);
      const pattern = [0, 1, 2, 3, 4, 3, 2, 1, 0, 1, 2, 3, 4, 3, 2, 1, 0];
      return {
        key: `${tonicName(t)} ${minorMode ? "minor" : "major"}`,
        title: `${tonicName(t)} ${minorMode ? "minor" : "major"} five-finger pattern`,
        hands,
        steps: pattern.map((d) => handed(t, hands, (b) => degree(t, b, scale, d))),
      };
    },
  },
  {
    id: "scale_major",
    label: "Major scales",
    group: "Scales",
    concept: "t_scales_major_hs",
    bpm: [54, 92],
    stepsPerBeat: 2,
    make: ({ pick, major }) => {
      const hands = pick(HS);
      const oct = pick([1, 2, 2]);
      return {
        key: `${tonicName(major)} major`,
        title: `${tonicName(major)} major scale`,
        hands,
        extra: `${oct} octave${oct > 1 ? "s" : ""}`,
        steps: upDown(7 * oct).map((d) => handed(major, hands, (b) => degree(major, b, SCALES.major, d))),
      };
    },
  },
  {
    id: "scale_minor",
    label: "Minor scales",
    group: "Scales",
    concept: "t_scales_minor_hs",
    bpm: [50, 88],
    stepsPerBeat: 2,
    make: ({ pick, minor }) => {
      const hands = pick(HS);
      const kind = pick(["harmonic", "melodic"] as const);
      const oct = pick([1, 2, 2]);
      const n = 7 * oct;
      // Melodic minor: raised 6 and 7 going up, natural minor coming down.
      const steps = upDown(n).map((d, i) => {
        const scale: readonly number[] =
          kind === "harmonic" ? SCALES.harmonic_minor : i <= n ? SCALES.melodic_minor : SCALES.natural_minor;
        return handed(minor, hands, (b) => degree(minor, b, scale, d));
      });
      return {
        key: `${tonicName(minor)} minor`,
        title: `${tonicName(minor)} ${kind} minor scale`,
        hands,
        extra: `${oct} octave${oct > 1 ? "s" : ""}`,
        steps,
      };
    },
  },
  {
    id: "scale_ht",
    label: "Scales hands together",
    group: "Scales",
    concept: "t_scales_ht",
    bpm: [48, 80],
    stepsPerBeat: 2,
    make: ({ pick, major, minor }) => {
      const minorMode = pick([false, true]);
      const t = minorMode ? minor : major;
      const scale = minorMode ? SCALES.harmonic_minor : SCALES.major;
      return {
        key: `${tonicName(t)} ${minorMode ? "minor" : "major"}`,
        title: `${tonicName(t)} ${minorMode ? "harmonic minor" : "major"} scale`,
        hands: "HT",
        extra: "2 octaves, an octave apart",
        steps: upDown(14).map((d) => handed(t, "HT", (b) => degree(t, b, scale, d))),
      };
    },
  },
  {
    id: "contrary",
    label: "Contrary motion",
    group: "Scales",
    concept: "t_chromatic_contrary",
    bpm: [48, 80],
    stepsPerBeat: 2,
    make: ({ major }) => {
      const b = rhBase(major);
      const steps = upDown(7).map((d) => {
        const rh = degree(major, b, SCALES.major, d);
        const lh = degree(major, b - 12, SCALES.major, -d);
        return { notes: [lh.midi, rh.midi], label: rh.name.replace(/-?\d+$/, "") };
      });
      return {
        key: `${tonicName(major)} major`,
        title: `${tonicName(major)} major scale in contrary motion`,
        hands: "HT",
        extra: "1 octave, RH up while LH goes down",
        steps,
      };
    },
  },
  {
    id: "chromatic",
    label: "Chromatic scales",
    group: "Scales",
    concept: "t_chromatic_contrary",
    bpm: [50, 84],
    stepsPerBeat: 2,
    make: ({ pick, major }) => {
      const hands = pick(HS);
      const sharps = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"];
      const flats = ["C", "D♭", "D", "E♭", "E", "F", "G♭", "G", "A♭", "A", "B♭", "B"];
      const base = rhBase(major) - (hands === "LH" ? 12 : 0);
      const steps = upDown(12).map((d, i) => {
        const m = base + d;
        return { notes: [m], label: `${(i <= 12 ? sharps : flats)[m % 12]}${Math.floor(m / 12) - 1}` };
      });
      return { key: tonicName(major), title: `Chromatic scale from ${tonicName(major)}`, hands, extra: "1 octave", steps };
    },
  },
  {
    id: "arpeggio_root",
    label: "Arpeggios",
    group: "Arpeggios",
    concept: "t_arpeggio_root",
    bpm: [40, 72],
    stepsPerBeat: 3,
    make: ({ pick, major, minor }) => {
      const minorMode = pick([false, true]);
      const t = minorMode ? minor : major;
      const chord: ChordName = minorMode ? "min" : "maj";
      const hands = pick(HS);
      return {
        key: `${tonicName(t)}${CHORDS[chord].sym}`,
        title: `${tonicName(t)} ${minorMode ? "minor" : "major"} arpeggio`,
        hands,
        extra: "2 octaves, root position",
        steps: upDown(6).map((k) => handed(t, hands, (b) => chordTone(t, b, chord, k))),
      };
    },
  },
  {
    id: "arpeggio_inversion",
    label: "Arpeggio inversions",
    group: "Arpeggios",
    concept: "t_arpeggio_inversions",
    bpm: [40, 66],
    stepsPerBeat: 3,
    make: ({ pick, major, minor }) => {
      const minorMode = pick([false, true]);
      const t = minorMode ? minor : major;
      const chord: ChordName = minorMode ? "min" : "maj";
      const hands = pick(HS);
      const inv = pick([1, 2]);
      return {
        key: `${tonicName(t)}${CHORDS[chord].sym}`,
        title: `${tonicName(t)} ${minorMode ? "minor" : "major"} arpeggio, ${inv === 1 ? "1st" : "2nd"} inversion`,
        hands,
        extra: `2 octaves, starting on the ${inv === 1 ? "third" : "fifth"}`,
        steps: upDown(6).map((k) => handed(t, hands, (b) => chordTone(t, b, chord, k + inv))),
      };
    },
  },
  {
    id: "arpeggio_7th",
    label: "Dominant & diminished 7th arpeggios",
    group: "Arpeggios",
    concept: "t_arpeggio_dom7_dim7",
    bpm: [54, 88],
    stepsPerBeat: 2,
    make: ({ pick, major }) => {
      const chord = pick(["dom7", "dim7"] as const);
      const hands = pick(HS);
      return {
        key: `${tonicName(major)}${CHORDS[chord].sym}`,
        title: `${tonicName(major)}${CHORDS[chord].sym} arpeggio (${chord === "dom7" ? "dominant" : "diminished"} seventh)`,
        hands,
        extra: "2 octaves",
        steps: upDown(8).map((k) => handed(major, hands, (b) => chordTone(major, b, chord, k))),
      };
    },
  },
  {
    id: "alberti",
    label: "Alberti bass (I–IV–V7–I)",
    group: "Chords",
    concept: "t_broken_chords_alberti",
    bpm: [60, 100],
    stepsPerBeat: 2,
    make: ({ major }) => {
      const b = rhBase(major) - 12; // LH, tonic in octave 3
      // Close LH voicings with smooth voice leading: I (1 3 5), IV64 (1 4 6), V7 (7, 4 5), I.
      const chords = [
        [0, 2, 4],
        [0, 3, 5],
        [-1, 3, 4],
        [0, 2, 4],
      ];
      const steps: Step[] = [];
      for (const [lo, mid, hi] of chords) {
        for (const d of [lo, hi, mid, hi, lo, hi, mid, hi]) {
          const n = degree(major, b, SCALES.major, d);
          steps.push({ notes: [n.midi], label: n.name });
        }
      }
      const last = degree(major, b, SCALES.major, 0);
      steps.push({ notes: [last.midi], label: last.name });
      return {
        key: `${tonicName(major)} major`,
        title: `Alberti bass in ${tonicName(major)} major`,
        hands: "LH",
        extra: "I – IV – V7 – I, one bar each",
        steps,
      };
    },
  },
  {
    id: "triad_inversions",
    label: "Triad inversions",
    group: "Chords",
    concept: "th_triads",
    bpm: [60, 100],
    stepsPerBeat: 0.5,
    make: ({ pick, major }) => {
      const chord = pick(["maj", "maj", "min", "min", "dim", "aug"] as const);
      const hands = pick(HS);
      const shift = hands === "LH" ? -12 : 0;
      const block = (inv: number): Step => {
        const tones = [0, 1, 2].map((k) => chordTone(major, rhBase(major) + shift, chord, k + inv));
        return { notes: tones.map((x) => x.midi), label: tones.map((x) => x.name.replace(/-?\d+$/, "")).join(" ") };
      };
      return {
        key: `${tonicName(major)}${CHORDS[chord].sym}`,
        title: `${tonicName(major)}${CHORDS[chord].sym} triad through its inversions`,
        hands,
        extra: "block chords: root, 1st, 2nd, root and back, two beats each",
        steps: [0, 1, 2, 3, 2, 1, 0].map(block),
      };
    },
  },
  {
    id: "seventh_inversions",
    label: "Seventh-chord inversions",
    group: "Chords",
    concept: "th_sevenths",
    bpm: [56, 92],
    stepsPerBeat: 0.5,
    make: ({ pick, major }) => {
      const chord = pick(["maj7", "dom7", "min7", "hdim7", "dim7"] as const);
      const block = (inv: number): Step => {
        const tones = [0, 1, 2, 3].map((k) => chordTone(major, rhBase(major) - 12, chord, k + inv));
        return { notes: tones.map((x) => x.midi), label: tones.map((x) => x.name.replace(/-?\d+$/, "")).join(" ") };
      };
      return {
        key: `${tonicName(major)}${CHORDS[chord].sym}`,
        title: `${tonicName(major)}${CHORDS[chord].sym} through its inversions`,
        hands: "RH",
        extra: "block chords: root, 1st, 2nd, 3rd, root and back, two beats each",
        steps: [0, 1, 2, 3, 4, 3, 2, 1, 0].map(block),
      };
    },
  },
  {
    id: "chord_flashcards",
    label: "Chord symbols",
    group: "Chords",
    concept: "th_triads",
    bpm: [50, 84],
    stepsPerBeat: 0.25,
    make: ({ pick }) => {
      const pool: ChordName[] = ["maj", "maj", "min", "min", "dim", "aug", "dom7", "maj7", "min7"];
      const steps: Step[] = [];
      for (let i = 0; i < 8; i++) {
        const root = parseTonic(pick(ALL_MAJOR));
        const chord = pick(pool);
        const tones = CHORDS[chord].iv.map((_, k) => chordTone(root, rhBase(root) - 12, chord, k));
        steps.push({ notes: tones.map((x) => x.midi), label: `${tonicName(root)}${CHORDS[chord].sym}` });
      }
      return {
        key: "random",
        title: "Chord symbols: read and play",
        hands: "RH",
        extra: "any inversion or octave, one bar each",
        steps,
        match: "pitch_class",
      };
    },
  },
];

// ---------- keys and tempo ----------

const EASY_MAJOR = ["C", "G", "D", "A", "E", "F"];
const ALL_MAJOR = ["C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"];
const EASY_MINOR = ["A", "E", "D", "B", "G"];
const ALL_MINOR = ["A", "E", "B", "F#", "C#", "G#", "D", "G", "C", "F", "Bb", "Eb"];

export type KeyPool = "easy" | "all";
export const TEMPO_LEVELS = { slow: 0.75, medium: 1, fast: 1.25 } as const;
export type TempoLevel = keyof typeof TEMPO_LEVELS;

export interface Options {
  families: FamilyId[];
  keys: KeyPool;
  tempo: TempoLevel;
  /** Concepts whose spaced-repetition card is due: their families come up three times as often. */
  due?: ReadonlySet<string>;
  /** Avoid repeating the previous drill's family when there is a choice. */
  previous?: FamilyId;
}

function weighted<T>(rng: Rng, xs: T[], w: (x: T) => number): T {
  const total = xs.reduce((s, x) => s + w(x), 0);
  let r = rng() * total;
  for (const x of xs) if ((r -= w(x)) < 0) return x;
  return xs[xs.length - 1];
}

const STEP_NAME: Record<number, string> = { 0.25: "whole notes", 0.5: "half notes", 1: "quarters", 2: "8ths", 3: "triplets", 4: "16ths" };

export function generateDrill(opts: Options, rng: Rng = Math.random): Drill {
  const pick = <T,>(xs: readonly T[]) => xs[Math.floor(rng() * xs.length)];
  let pool = FAMILIES.filter((f) => opts.families.includes(f.id));
  if (pool.length === 0) pool = FAMILIES;
  if (pool.length > 1 && opts.previous) pool = pool.filter((f) => f.id !== opts.previous);
  const fam = weighted(rng, pool, (f) => (opts.due?.has(f.concept) ? 3 : 1));
  const major = parseTonic(pick(opts.keys === "all" ? ALL_MAJOR : EASY_MAJOR));
  const minor = parseTonic(pick(opts.keys === "all" ? ALL_MINOR : EASY_MINOR));
  const made = fam.make({ rng, pick, major, minor });
  const scale = TEMPO_LEVELS[opts.tempo];
  const [lo, hi] = fam.bpm;
  const bpm = Math.round((lo + rng() * (hi - lo)) * scale / 2) * 2;
  const stepsPerBeat = made.stepsPerBeat ?? fam.stepsPerBeat;
  const detail = [STEP_NAME[stepsPerBeat] ?? "", made.extra ?? ""].filter(Boolean).join(" · ");
  return {
    family: fam.id,
    concept: fam.concept,
    title: made.title,
    detail,
    key: made.key,
    hands: made.hands,
    bpm,
    stepsPerBeat,
    beatsPerBar: 4,
    steps: made.steps,
    match: made.match ?? "pitch",
  };
}

// ---------- live progress through a drill (display only; the Pi does the grading) ----------

export interface Progress {
  index: number; // current step
  hit: number[]; // pitches of the current step already played
  wrong: number; // count of notes that fit neither the current nor the next step
}

export const startProgress = (): Progress => ({ index: 0, hit: [], wrong: 0 });

export function advance(drill: Drill, p: Progress, note: number): Progress {
  const key = (n: number) => (drill.match === "pitch_class" ? n % 12 : n);
  const wants = (i: number) => drill.steps[i]?.notes.map(key) ?? [];
  const k = key(note);
  const tryStep = (i: number, hit: number[]): Progress | null => {
    if (!wants(i).includes(k)) return null;
    const nextHit = hit.includes(k) ? hit : [...hit, k];
    const done = wants(i).every((x) => nextHit.includes(x));
    return done ? { index: i + 1, hit: [], wrong: p.wrong } : { index: i, hit: nextHit, wrong: p.wrong };
  };
  if (p.index >= drill.steps.length) return p;
  return tryStep(p.index, p.hit) ?? tryStep(p.index + 1, []) ?? { ...p, wrong: p.wrong + 1 };
}
