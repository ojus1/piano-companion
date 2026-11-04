"""Wires MIDI capture, optional audio capture and the database together."""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from pathlib import Path

import mido
from sqlmodel import Session

from .config import Settings
from .db import get_engine
from .midi_recorder import FinishedSession, MidiCapture, SessionSegmenter, find_output_port
from .models import PracticeSession
from .retention import enforce_recordings_cap

log = logging.getLogger(__name__)


class Recorder:
    def __init__(self, settings: Settings, loop: asyncio.AbstractEventLoop):
        self.settings = settings
        self.audio = None
        if settings.audio_enabled:
            try:
                from .audio_recorder import AudioRecorder

                self.audio = AudioRecorder(settings.audio_device, settings.audio_samplerate, settings.audio_channels)
                self.audio.start_stream()
            except Exception:
                log.exception("audio capture disabled")
                self.audio = None
        self.segmenter = SessionSegmenter(
            out_dir=settings.recordings_dir,
            idle_seconds=settings.session_idle_seconds,
            min_notes=settings.session_min_notes,
            on_finished=self._save,
            on_started=self._started,
        )
        self.capture: MidiCapture | None = None
        if settings.midi_enabled:
            self.capture = MidiCapture(self.segmenter, settings.midi_input, loop)

    def start(self) -> None:
        self.enforce_cap()
        if self.capture:
            self.capture.start()

    def stop(self) -> None:
        if self.capture:
            self.capture.stop()
        else:
            self.segmenter.flush()
        if self.audio:
            self.audio.close()

    def enforce_cap(self) -> None:
        try:
            enforce_recordings_cap(self.settings.recordings_dir, self.settings.recordings_max_mb * 1_000_000)
        except Exception:
            log.exception("recordings cap check failed")

    # ---- playback on the piano's own sound engine (USB-MIDI is bidirectional) ----
    _play_thread: threading.Thread | None = None
    _play_stop = threading.Event()

    def play(self, path: Path, tempo_scale: float = 1.0) -> bool:
        name = find_output_port(self.settings.midi_input)
        if not name:
            return False
        self.stop_playback()
        stop = self._play_stop = threading.Event()

        def run():
            # Don't record our own playback as a practice session.
            self.segmenter.paused = True
            try:
                with mido.open_output(name) as out:
                    for msg in mido.MidiFile(path).play():
                        if stop.is_set():
                            break
                        if not msg.is_meta:
                            out.send(msg)
                    out.reset()  # all notes off
            except Exception:
                log.exception("playback failed")
            finally:
                self.segmenter.paused = False

        if tempo_scale != 1.0:
            mid = mido.MidiFile(path)
            for tr in mid.tracks:
                for m in tr:
                    m.time = int(m.time / tempo_scale)
            tmp = self.settings.data_dir / "playback.mid"
            mid.save(tmp)
            path = tmp
        self._play_thread = threading.Thread(target=run, name="midi-playback", daemon=True)
        self._play_thread.start()
        return True

    def stop_playback(self) -> None:
        self._play_stop.set()
        if self._play_thread:
            self._play_thread.join(timeout=2)
            self._play_thread = None

    def status(self) -> dict:
        return {
            "midi_port": self.capture.port_name if self.capture else None,
            "midi_enabled": self.capture is not None,
            "recording": self.segmenter.active,
            "audio": self.audio is not None,
            "playing": bool(self._play_thread and self._play_thread.is_alive()),
        }

    def _started(self, when: datetime) -> None:
        if self.capture:
            self.capture.broadcast({"type": "session", "state": "started", "at": when.isoformat()})
        if self.audio:
            local = when.astimezone()
            self.audio.begin(
                self.settings.recordings_dir / local.strftime("%Y-%m-%d") / f"{local.strftime('%H%M%S')}.flac"
            )

    def _save(self, fs: FinishedSession) -> None:
        audio_path = self.audio.end() if self.audio else None

        def rel(p):
            return str(p.relative_to(self.settings.recordings_dir)) if p else None

        with Session(get_engine()) as db:
            row = PracticeSession(
                started_at=fs.started_at,
                ended_at=fs.ended_at,
                midi_path=rel(fs.midi_path),
                audio_path=rel(audio_path),
                note_count=fs.note_count,
                metrics=fs.metrics,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            log.info("saved session %s (%d notes)", row.id, row.note_count)
            if self.capture:
                self.capture.broadcast({"type": "session", "state": "saved", "id": row.id})
        self.enforce_cap()
