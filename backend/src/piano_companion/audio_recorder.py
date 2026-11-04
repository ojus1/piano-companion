"""Optional line-in capture (piano AUX OUT -> USB audio interface -> Pi), started and stopped with
each MIDI session. Audio is written as FLAC (lossless, ~half the size of WAV).

Imports of sounddevice/soundfile are lazy so the backend runs on machines without PortAudio.
Pre-roll: we keep the last few seconds in a ring buffer so the first note isn't clipped.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections import deque
from pathlib import Path

log = logging.getLogger(__name__)


class AudioRecorder:
    def __init__(self, device: str | None, samplerate: int, channels: int, preroll_s: float = 2.0):
        import sounddevice as sd  # noqa: F401  (fail fast if PortAudio is missing)

        self.device = device
        self.samplerate = samplerate
        self.channels = channels
        self._preroll: deque = deque(maxlen=max(1, int(preroll_s * samplerate / 1024)))
        self._q: queue.Queue | None = None
        self._writer: threading.Thread | None = None
        self._stream = None
        self.current_path: Path | None = None

    def start_stream(self) -> None:
        import sounddevice as sd

        def cb(indata, frames, t, status):
            if status:
                log.debug("audio status %s", status)
            block = indata.copy()
            if self._q is not None:
                self._q.put(block)
            else:
                self._preroll.append(block)

        self._stream = sd.InputStream(
            device=self.device,
            samplerate=self.samplerate,
            channels=self.channels,
            blocksize=1024,
            dtype="int16",
            callback=cb,
        )
        self._stream.start()
        log.info("audio stream open on %s", self.device or "default device")

    def begin(self, path: Path) -> None:
        import soundfile as sf

        path.parent.mkdir(parents=True, exist_ok=True)
        q: queue.Queue = queue.Queue()
        for b in self._preroll:
            q.put(b)
        self._preroll.clear()
        self.current_path = path

        def write():
            with sf.SoundFile(path, "w", self.samplerate, self.channels, format="FLAC") as f:
                while (b := q.get()) is not None:
                    f.write(b)

        self._writer = threading.Thread(target=write, name="audio-writer", daemon=True)
        self._writer.start()
        self._q = q

    def end(self) -> Path | None:
        q, self._q = self._q, None
        if q is None:
            return None
        q.put(None)
        if self._writer:
            self._writer.join(timeout=10)
        path, self.current_path = self.current_path, None
        return path

    def close(self) -> None:
        self.end()
        if self._stream:
            self._stream.close()
