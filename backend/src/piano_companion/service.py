"""Wires MIDI capture, optional audio capture and the database together."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlmodel import Session

from .config import Settings
from .db import get_engine
from .midi_recorder import FinishedSession, MidiCapture, SessionSegmenter
from .models import PracticeSession

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
        if self.capture:
            self.capture.start()

    def stop(self) -> None:
        if self.capture:
            self.capture.stop()
        else:
            self.segmenter.flush()
        if self.audio:
            self.audio.close()

    def status(self) -> dict:
        return {
            "midi_port": self.capture.port_name if self.capture else None,
            "midi_enabled": self.capture is not None,
            "recording": self.segmenter.active,
            "audio": self.audio is not None,
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
