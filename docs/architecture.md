# Architecture

```
┌──────────────── Raspberry Pi 5 (piano-pi) ─────────────────┐        ┌──── Galaxy Tab S6 Lite ────┐
│  systemd: piano-companion (FastAPI, uvicorn :8000)         │        │  Chrome → installed PWA    │
│   ├─ MidiCapture thread ── ALSA ◄── P-155 USB TO HOST      │  HTTPS │   Today  (due items, grade)│
│   │    └─ SessionSegmenter: auto start on first note,      │◄──────►│   Library (score viewer)   │
│   │       end after 90 s silence → .mid + DB row + metrics │  WS    │   Sessions (log, playback) │
│   ├─ AudioRecorder (optional) ◄── USB interface ◄── AUX OUT│        │   Live  (88-key display)   │
│   ├─ REST /api/* · WebSocket /api/live                     │        └────────────────────────────┘
│   ├─ SQLite (WAL) ~/piano-data/piano.db                    │
│   ├─ ~/piano-data/recordings/YYYY-MM-DD/HHMMSS.{mid,flac}  │   tailscale serve: https://piano-pi.<tailnet>.ts.net
│   └─ ~/piano-data/library/pieces/<id>/score.{musicxml,pdf} │   Tailscale SSH: ssh piano-pi
└────────────────────────────────────────────────────────────┘
```

## Key decisions

**MIDI first, audio optional.** The P-155 is digital, so MIDI is a perfect record: exact notes, timing to
the millisecond, velocity and pedal. All analysis (evenness, dynamics, wrong notes against the score) runs on
MIDI. Audio from AUX OUT is for listening back and for future AI feedback on tone.

**Sessions record themselves.** You never press record. The first note opens a session, and 90 seconds of
silence closes it (`PC_SESSION_IDLE_SECONDS`). Blips under 8 notes are thrown away. This is the "practice
journal" a teacher would want, and it costs you no effort.

**Tablet app is a PWA, not a native APK.** It's built with React, Vite and TypeScript, served by the Pi, and
installed to the home screen from Chrome ("Add to Home screen", which opens full-screen). Deploying means
rebuilding on your laptop and rsyncing. There's no Play Store, no APK signing, and no adb install loop.
Everything a practice app needs works in the browser: WebSocket, screen wake lock, audio playback, file
upload, and Bluetooth page-turner keys. If a native-only need shows up later, the same code wraps into an APK
with Capacitor.

**Scores.** MusicXML is rendered by OpenSheetMusicDisplay, which reflows to the screen and can later drive a
cursor from live MIDI ("follow along"). PDFs open in EmbedPDF, where you can annotate with the S Pen and save the
markings back to the Pi. Reference and recorded MIDI play in the browser with a sampled grand piano, or through the
P-155 itself.

**Spaced repetition: FSRS.** Each practice item (scale, etude passage, sight-reading drill, piece section)
is an FSRS card. You grade each attempt Again, Hard, Good or Easy, and FSRS sets the next due date. FSRS is the
open, research-backed scheduler that Anki now uses. The pedagogy thread will decide *what* goes into the
queue. Later, grading can be automatic from MIDI metrics instead of self-reported.

**Storage: SQLite plus files.** One user and one device, so there's no Postgres to look after. WAL mode
holds up through power cuts. Back up by copying `~/piano-data`.

## Curriculum and auto-grading

The research thread's `curriculum.json` and score catalog are imported with `piano-companion-seed` (see
remote-access.md). FSRS-6 parameters and per-deck retention (technique 0.85, passages 0.9, maintenance 0.8) come
from that file. Sight-reading is scheduled daily rather than by FSRS, because the material is always fresh; the
research plans Elo for it. **Auto-grade** aligns the last recorded take to the item's score with
partitura and parangonar. It computes note accuracy, tempo ratio against the target BPM, timing deviation,
stops/restarts and evenness, then applies the curriculum's Again/Hard/Good/Easy rules (`grading.py`). You can
always override the grade with the buttons. Still to build from the research: the tempo ladder, Elo for
sight-reading, BKT mastery gates on the concept graph, and FIRe implicit credit.

Open-source components and the reasons for each choice are in [open-source.md](open-source.md).

## Where AI fits later

- `PracticeSession.analysis` (a JSON column) holds LLM and DSP results. A worker can pick up sessions with an
  empty `analysis`, align the MIDI to the linked score, compute errors and tempo drift, and ask Claude to
  write feedback and suggest the next practice items.
- Heavy jobs (audio transcription, source separation, arranging) can run off the Pi on your laptop or a cloud
  API. The Pi stays the always-on recorder and scheduler.

## Code map

```
backend/src/piano_companion/
  config.py          settings (env vars PC_*)
  models.py          Piece, PracticeItem, PracticeSession, Review
  midi_recorder.py   SessionSegmenter (pure, tested) + MidiCapture (ALSA port, hot-plug)
  audio_recorder.py  line-in to FLAC with 2 s pre-roll
  analysis.py        quick MIDI metrics (range, dynamics, pulse evenness)
  srs.py             FSRS-6 decks configured from curriculum.json
  curriculum.py      loads curriculum.json from the data dir
  grading.py         curriculum grading rules: metrics -> Again/Hard/Good/Easy
  alignment.py       partitura + parangonar score alignment -> attempt metrics
  seed.py            piano-companion-seed: catalog + stages -> pieces + practice items
  render.py          piano-companion-render: LilyPond -> PDF + MIDI
  service.py         wires capture → files → DB → WebSocket
  api/routes.py      REST + /api/live
  tools/fake_piano.py  plays a scale/MIDI file into a virtual port for testing
app/src/
  api.ts, hooks.ts (live socket, wake lock), midi.ts (+ tests)
  pages/Today, Library, Sessions, Live
  components/ScoreViewer (OSMD) · PdfScore (EmbedPDF + annotations) · MidiPlayer (smplr + piano roll)
deploy/  bootstrap-pi.sh · deploy.sh · piano-companion.service
```
