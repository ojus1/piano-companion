"""Fill a fresh data dir with made-up practice history, for screenshots and UI work.

    PC_DATA_DIR=/tmp/pc-demo uv run piano-companion-demo     # then run the backend with the same dir

Everything here is invented: about 60 days of sessions with a few missed and frozen days, technique
drills that slowly improve, a handful of queue items, takes and pieces, and a short original study
in MusicXML + MIDI so the score viewer and player have something to show. Never point it at a real
data dir; it refuses one that already has a database.
"""

import argparse
import random
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import mido
from sqlmodel import Session

from ..config import get_settings
from ..db import get_engine
from ..models import Performance, Piece, PracticeItem, PracticeSession, Review, Setting, TechniqueAttempt

# A short original study in C (right hand melody over left hand broken chords), as (midi, beats).
RH = [
    (64, 1),
    (65, 1),
    (67, 2),
    (69, 1),
    (67, 1),
    (65, 1),
    (64, 1),
    (62, 1),
    (64, 1),
    (65, 2),
    (64, 1),
    (62, 1),
    (60, 2),
    (64, 1),
    (65, 1),
    (67, 2),
    (72, 1),
    (71, 1),
    (69, 1),
    (67, 1),
    (65, 1),
    (64, 1),
    (62, 1),
    (71, 1),
    (72, 4),
]
LH_BARS = [
    (48, 52, 55),
    (53, 57, 60),
    (43, 47, 50),
    (48, 52, 55),
    (48, 52, 55),
    (53, 57, 60),
    (43, 47, 50),
    (48, 52, 55),
]
STEP = {0: ("C", 0), 2: ("D", 0), 4: ("E", 0), 5: ("F", 0), 7: ("G", 0), 9: ("A", 0), 11: ("B", 0)}


def _note_xml(midi: int, beats: int, staff: int, chord: bool = False) -> str:
    step, _ = STEP[midi % 12]
    octave = midi // 12 - 1
    kind = {1: "quarter", 2: "half", 4: "whole"}[beats]
    return (
        f"<note>{'<chord/>' if chord else ''}<pitch><step>{step}</step><octave>{octave}</octave></pitch>"
        f"<duration>{beats}</duration><voice>{staff}</voice><type>{kind}</type><staff>{staff}</staff></note>"
    )


def study_musicxml() -> str:
    bars_rh: list[list[tuple[int, int]]] = [[]]
    used = 0
    for n in RH:
        if used == 4:
            bars_rh.append([])
            used = 0
        bars_rh[-1].append(n)
        used += n[1]
    measures = []
    for i, (rh, lh) in enumerate(zip(bars_rh, LH_BARS, strict=True)):
        attrs = (
            "<attributes><divisions>1</divisions><key><fifths>0</fifths></key><time><beats>4</beats>"
            "<beat-type>4</beat-type></time><staves>2</staves><clef number='1'><sign>G</sign><line>2</line></clef>"
            "<clef number='2'><sign>F</sign><line>4</line></clef></attributes>"
            if i == 0
            else ""
        )
        body = "".join(_note_xml(m, b, 1) for m, b in rh)
        body += "<backup><duration>4</duration></backup>"
        root, third, fifth = lh
        body += _note_xml(root, 2, 2) + _note_xml(third, 2, 2, chord=True) + _note_xml(fifth, 2, 2, chord=True)
        body += _note_xml(root, 2, 2) + _note_xml(fifth, 2, 2, chord=True)
        measures.append(f"<measure number='{i + 1}'>{attrs}{body}</measure>")
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<score-partwise version='3.1'><work><work-title>Study in C</work-title></work>"
        "<identification><creator type='composer'>Demo</creator></identification>"
        "<part-list><score-part id='P1'><part-name>Piano</part-name></score-part></part-list>"
        f"<part id='P1'>{''.join(measures)}</part></score-partwise>"
    )


def study_midi(path: Path, bpm: int = 88, rng: random.Random | None = None) -> int:
    """Write the study as a MIDI file (with a little human timing if rng is given). Returns note count."""
    tpb = 480
    events: list[tuple[int, mido.Message]] = []
    t = 0
    for m, b in RH:
        jitter = rng.randint(-25, 25) if rng else 0
        v = rng.randint(58, 84) if rng else 72
        events.append((max(0, t + jitter), mido.Message("note_on", note=m, velocity=v)))
        events.append((t + b * tpb - 20, mido.Message("note_off", note=m, velocity=0)))
        t += b * tpb
    for i, (root, third, fifth) in enumerate(LH_BARS):
        start = i * 4 * tpb
        for k, notes in enumerate([(root, third, fifth), (root, fifth)]):
            for n in notes:
                events.append((start + k * 2 * tpb, mido.Message("note_on", note=n, velocity=52)))
                events.append((start + (k + 1) * 2 * tpb - 30, mido.Message("note_off", note=n, velocity=0)))
    events.sort(key=lambda e: (e[0], e[1].type == "note_on"))
    mf = mido.MidiFile(ticks_per_beat=tpb)
    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm)))
    last = 0
    for at, msg in events:
        tr.append(msg.copy(time=at - last))
        last = at
    mf.tracks.append(tr)
    path.parent.mkdir(parents=True, exist_ok=True)
    mf.save(path)
    return sum(1 for _, m in events if m.type == "note_on")


PIECES = [
    ("Study in C", "Demo", "repertoire", 1, ["legato", "broken chords"]),
    ("Arabesque, Op. 100 No. 2", "Friedrich Burgmüller", "etudes", 2, ["staccato", "scales"]),
    ("Prelude in E minor, Op. 28 No. 4", "Frédéric Chopin", "repertoire", 3, ["voicing", "pedal"]),
    ("Träumerei, Op. 15 No. 7", "Robert Schumann", "repertoire", 4, ["voicing", "rubato"]),
    ("Gymnopédie No. 1", "Erik Satie", "repertoire", 2, ["pedal", "voicing"]),
    ("Étude, Op. 47 No. 1", "Stephen Heller", "etudes", 3, ["melody over accompaniment"]),
]

QUEUE = [
    ('Burgmüller Op. 100 No. 2 "Arabesque", mm. 1–12', "repertoire", "S2", 1),
    ("A minor harmonic scale, HT, 2 oct", "technique", "S2", None),
    ("Sight-reading: 8 bars, C major, quarter notes", "sight_reading", "S2", None),
    ("ii–V–I voicings in F", "theory", "S2", None),
    ("Study in C, whole piece at 80 BPM", "repertoire", "S2", 0),
]

DRILLS = [
    (
        "scale_major",
        "t_scales_major_hs",
        ["C major scale, RH, 2 octaves", "G major scale, LH, 2 octaves", "F major scale, HS"],
    ),
    (
        "scale_minor",
        "t_scales_minor_hs",
        ["A harmonic minor scale, RH", "E natural minor scale, LH", "D harmonic minor, HS"],
    ),
    ("arpeggio_root", "t_arpeggios_root", ["C major arpeggio, RH, 2 octaves", "A minor arpeggio, LH, 2 octaves"]),
    ("triad_inversions", "t_triad_inversions", ["F major triad inversions, RH", "D minor triad inversions, LH"]),
    (
        "chord_flashcards",
        "t_chord_flashcards",
        ["Chord flashcards: major and minor triads", "Chord flashcards: sevenths"],
    ),
]


def build(data_dir: Path, days: int, seed: int) -> None:
    rng = random.Random(seed)
    s = get_settings()
    lib = s.library_dir / "demo"
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "study-in-c.musicxml").write_text(study_musicxml())
    study_midi(lib / "study-in-c.mid")

    now = datetime.now(UTC)
    today = now.date()
    with Session(get_engine()) as db:
        db.add(Setting(key="goals", value={"daily_minutes": 20, "weekly_days": 5, "streak_min_minutes": 5}))
        pieces = []
        for title, composer, cat, lvl, skills in PIECES:
            p = Piece(
                title=title, composer=composer, category=cat, level_henle=lvl, skills=skills, license="Public domain"
            )
            if title == "Study in C":
                p.musicxml_path, p.midi_path, p.license = "demo/study-in-c.musicxml", "demo/study-in-c.mid", "Demo"
            db.add(p)
            pieces.append(p)
        db.flush()

        items = []
        for title, kind, stage, piece_idx in QUEUE:
            it = PracticeItem(
                title=title,
                kind=kind,
                stage=stage,
                piece_id=pieces[piece_idx].id if piece_idx is not None else None,
                due=now - timedelta(hours=2),
            )
            db.add(it)
            items.append(it)
        db.flush()

        # Sessions: practice most days, skip a few (some of which a freeze covers), short today.
        rec = s.recordings_dir
        for back in range(days, -1, -1):
            d = today - timedelta(days=back)
            if back > 45 and rng.random() < 0.6:
                continue
            if back not in (0,) and rng.random() < 0.05:
                continue
            n_sessions = 1 if back == 0 else rng.choice([1, 1, 2])
            for k in range(n_sessions):
                hour = rng.choice([7, 8, 19, 20, 21, 22]) if k == 0 else rng.choice([12, 13, 17])
                start = datetime(d.year, d.month, d.day, hour, rng.randint(0, 50), tzinfo=UTC)
                mins = 14 if back == 0 else max(4, rng.gauss(22, 9))
                sess = PracticeSession(started_at=start, ended_at=start + timedelta(minutes=mins), source="midi")
                if back < 4:
                    rel = f"{d.isoformat()}/session-{k}.mid"
                    sess.note_count = study_midi(rec / rel, bpm=rng.randint(76, 92), rng=rng) * 6
                    sess.midi_path = rel
                    sess.metrics = {"pitch_low": 43, "pitch_high": 72, "ioi_cv": round(rng.uniform(0.08, 0.2), 3)}
                else:
                    sess.note_count = int(mins * rng.uniform(60, 110))
                db.add(sess)

        # Technique: accuracy and clean tempo creep up over the weeks.
        for back in range(42, -1, -1):
            if rng.random() < 0.35:
                continue
            for _ in range(rng.randint(1, 3)):
                family, concept, titles = rng.choice(DRILLS)
                growth = (42 - back) / 42
                acc = min(1.0, max(0.4, rng.gauss(0.72 + 0.22 * growth, 0.06)))
                bpm = round(60 + 30 * growth + rng.uniform(-6, 6))
                rating = 1 if acc < 0.7 else 2 if acc < 0.85 else 3 if acc < 0.96 else 4
                created = datetime(*(today - timedelta(days=back)).timetuple()[:3], 19, rng.randint(0, 59), tzinfo=UTC)
                db.add(
                    TechniqueAttempt(
                        created_at=created,
                        family=family,
                        concept_id=concept,
                        title=rng.choice(titles),
                        bpm=bpm,
                        rating=rating,
                        metrics={
                            "accuracy": round(acc, 3),
                            "achieved_bpm": round(bpm * rng.uniform(0.94, 1.02), 1),
                            "ibi_cv": round(max(0.03, rng.gauss(0.11 - 0.05 * growth, 0.015)), 3),
                            "matched": 30,
                            "expected": 32,
                        },
                    )
                )
        for back in range(1, 20, 3):
            db.add(
                Review(practice_item_id=items[back % len(items)].id, rating=3, reviewed_at=now - timedelta(days=back))
            )

        # Takes.
        perf_dir = s.performances_dir
        for i, (title, kind, fav, back) in enumerate(
            [
                ("Study in C, first full run", "performance", True, 1),
                ("Gymnopédie No. 1, opening", "performance", False, 6),
                ("Original improvisation in A minor", "cover", False, 12),
            ]
        ):
            rel = f"take-{i}.mid"
            n = study_midi(perf_dir / rel, bpm=84, rng=rng)
            db.add(
                Performance(
                    title=title,
                    kind=kind,
                    favorite=fav,
                    started_at=now - timedelta(days=back, hours=3),
                    duration_s=rng.uniform(60, 200),
                    midi_path=rel,
                    note_count=n,
                    notes="Left hand too loud in bar 5." if i == 0 else None,
                )
            )
        db.commit()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--pdf", type=Path, help="optional PDF score to attach to a demo piece")
    args = ap.parse_args(argv)
    s = get_settings()
    if s.db_path.exists():
        sys.exit(f"{s.db_path} already exists; demo data only goes into an empty PC_DATA_DIR")
    build(s.data_dir, args.days, args.seed)
    if args.pdf:
        dest = s.library_dir / "demo" / args.pdf.name
        shutil.copy(args.pdf, dest)
        with Session(get_engine()) as db:
            p = db.get(Piece, 2)
            if p:
                p.pdf_path = f"demo/{args.pdf.name}"
                db.add(p)
                db.commit()
    print(f"demo data written to {s.data_dir}")


if __name__ == "__main__":
    main()
