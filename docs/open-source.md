# Open-source building blocks

Where a solid open-source project already covers something, the app uses it and keeps only the glue as
its own code. This page lists what is used, why it was picked, and what was turned down.

## In use

| Need | Project (license) | Where | Why this one |
|------|-------------------|-------|--------------|
| MIDI I/O from the P-155 | **mido** + **python-rtmidi** (MIT) | Pi | The standard Python MIDI stack. ALSA hot-plug, virtual ports for tests, MIDI file read/write. |
| Spaced repetition | **py-fsrs** (MIT) | Pi | FSRS-6, the scheduler Anki adopted. The research thread's curriculum supplies its parameters and per-deck retention. |
| Score parsing (MusicXML, MIDI, \*\*kern, MEI) | **partitura** (Apache-2.0) | Pi | One loader for every format in the research library. Built for performance analysis (CP JKU). |
| Score-to-performance alignment | **parangonar** (Apache-2.0) | Pi | `DualDTWNoteMatcher` matches each played note to a score note, which gives note accuracy, tempo, timing and stops for auto-grading. Recommended by the research thread. |
| Rendering LilyPond scores | **GNU LilyPond** (GPL, run as a CLI) | Pi | Most of the Mutopia Burgmüller, Czerny, Schumann and Chopin files in the catalog are LilyPond source only. `piano-companion-render` turns them into a PDF and a reference MIDI. It runs as a separate program, so the app's own license is unaffected. |
| MusicXML display | **OpenSheetMusicDisplay** (BSD-3) | Tablet | Reflows notation to the screen, and has a cursor API for score following later. |
| PDF reading + annotation | **EmbedPDF** (MIT; PDFium wasm, BSD) | Tablet | A complete viewer: thumbnails, search, zoom, and **ink/pen, highlight, text and shape annotations**, which suits the S Pen. "Save markings" bakes them into a copy on the Pi, and the original is kept. PDFium is the PDF engine Chrome uses. Everything is served from the Pi: the CDN wasm, fonts and stamp downloads are switched off. |
| MIDI parsing in the browser | **@tonejs/midi** (MIT) | Tablet | Small and reliable, with notes in seconds. |
| Piano sound in the browser | **smplr** SplendidGrandPiano (MIT) | Tablet | A multi-velocity sampled grand. Samples are cached in the browser after the first load. |
| Playback on the piano itself | (own code, ~40 lines) | Pi | The P-155's USB-MIDI works in both directions, so "Play on piano" sends the file back to the piano and you hear its own sound. |

## Considered, not used (yet)

- **pdf.js annotation editor** (Apache-2.0). This was the previous PDF renderer. Its editor layer needs a lot of UI wiring, and EmbedPDF ships that UI ready-made. pdf.js has been removed.
- **Verovio** (LGPL). A strong engraver for MEI, \*\*kern and MusicXML, with built-in MIDI/timemap for following the score. It's the fallback if OSMD struggles with dense Romantic scores, or to show the \*\*kern files without converting them.
- **html-midi-player / Magenta.js** (Apache-2.0). It has a nice piano roll, but it pulls in Magenta (TensorFlow.js), which is far too heavy for this.
- **music21** (BSD). Great for theory analysis such as roman numerals and key finding. Add it when the theory and composition features need it; partitura covers what auto-grading needs.
- **Basic Pitch** (Spotify, Apache-2.0). Audio-to-MIDI transcription, for practising on an acoustic piano or analysing recordings. It's a later step, and better run on the laptop or in the cloud than on the Pi.
- **Neothesia / PianoBooster** (GPL desktop apps). These are piano-roll learning apps rather than libraries. They are useful as UX references for "wait mode" (pause until the right note is played).
- **MuseScore** (GPL). Use it on the laptop to export the 91 `.mscx` catalog items to MusicXML (`mscore -o out.musicxml in.mscx`). It is too heavy to run headless on the Pi.

## Known limits

- Auto-grading a **passage** works best when the take is just that passage. When a full run-through is graded against a few bars of very repetitive music (e.g. Bach's C major prelude), the aligner can match the wrong repetition, and accuracy reads lower than it really is. The UI lets you override any grade.
- 1 of the 40 LilyPond files scheduled for S1 (Hanon) does not compile even after `convert-ly`. Its PDF needs fetching from the source URL.
