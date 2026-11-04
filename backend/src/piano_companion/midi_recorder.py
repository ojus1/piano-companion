"""Always-on MIDI capture that splits playing into practice sessions.

The piano's USB TO HOST port shows up as an ALSA MIDI device on the Pi. We keep it open, start a
session on the first note, and close the session after `session_idle_seconds` of silence. Each
session is written as a standard MIDI file and a PracticeSession row; live events are fanned out to
WebSocket listeners (the tablet) through `subscribe()`.

The segmenter is separated from the port handling so tests and `fake-piano` can drive it directly.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import mido

from .analysis import NoteEvent, session_metrics

log = logging.getLogger(__name__)

TICKS_PER_BEAT = 480
TEMPO = 500000  # 120 bpm: 1 beat = 0.5 s, so ticks map to seconds exactly


@dataclass
class _Active:
    started_wall: datetime
    started_mono: float
    messages: list[tuple[float, mido.Message]] = field(default_factory=list)
    notes: list[NoteEvent] = field(default_factory=list)
    open_notes: dict[int, NoteEvent] = field(default_factory=dict)
    pedal_downs: int = 0
    last_event: float = 0.0


@dataclass
class FinishedSession:
    started_at: datetime
    ended_at: datetime
    midi_path: Path
    note_count: int
    metrics: dict


class SessionSegmenter:
    """Feed it timestamped MIDI messages; it emits FinishedSession objects."""

    def __init__(
        self,
        out_dir: Path,
        idle_seconds: float,
        min_notes: int,
        on_finished: Callable[[FinishedSession], None],
        on_started: Callable[[datetime], None] | None = None,
    ):
        self.out_dir = out_dir
        self.idle_seconds = idle_seconds
        self.min_notes = min_notes
        self.on_finished = on_finished
        self.on_started = on_started
        self._active: _Active | None = None
        self._lock = threading.Lock()
        self.paused = False  # set while the app itself plays MIDI to the piano

    @property
    def active(self) -> bool:
        return self._active is not None

    def feed(self, msg: mido.Message, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        if msg.type in ("clock", "active_sensing", "sysex") or self.paused:
            return  # the P-155 sends active sensing constantly
        with self._lock:
            self._maybe_timeout_locked(now)
            is_note_on = msg.type == "note_on" and msg.velocity > 0
            if self._active is None:
                if not is_note_on:
                    return
                self._active = _Active(started_wall=datetime.now(UTC), started_mono=now, last_event=now)
                if self.on_started:
                    self.on_started(self._active.started_wall)
            a = self._active
            t = now - a.started_mono
            a.messages.append((t, msg))
            a.last_event = now
            if is_note_on:
                ev = NoteEvent(t=t, note=msg.note, velocity=msg.velocity)
                a.notes.append(ev)
                a.open_notes[msg.note] = ev
            elif msg.type in ("note_off", "note_on"):
                ev = a.open_notes.pop(msg.note, None)
                if ev:
                    ev.duration = t - ev.t
            elif msg.type == "control_change" and msg.control == 64 and msg.value >= 64:
                a.pedal_downs += 1

    def tick(self, now: float | None = None) -> None:
        """Call periodically so a session closes even when no more MIDI arrives."""
        with self._lock:
            self._maybe_timeout_locked(time.monotonic() if now is None else now)

    def flush(self) -> None:
        with self._lock:
            self._close_locked(time.monotonic())

    def end_active(self) -> None:
        """Close the running session at its last note (used when a performance take begins)."""
        with self._lock:
            if self._active:
                self._close_locked(self._active.last_event)

    def _maybe_timeout_locked(self, now: float) -> None:
        if self._active and now - self._active.last_event > self.idle_seconds:
            self._close_locked(self._active.last_event)

    def _close_locked(self, end_mono: float) -> None:
        a, self._active = self._active, None
        if a is None:
            return
        if len(a.notes) < self.min_notes:
            log.info("discarding %d-note blip", len(a.notes))
            return
        ended = a.started_wall.timestamp() + (end_mono - a.started_mono)
        ended_at = datetime.fromtimestamp(ended, UTC)
        path = self._write_midi(a)
        fs = FinishedSession(
            started_at=a.started_wall,
            ended_at=ended_at,
            midi_path=path,
            note_count=len(a.notes),
            metrics=session_metrics(a.notes, a.pedal_downs),
        )
        try:
            self.on_finished(fs)
        except Exception:  # never let a DB hiccup kill the capture thread
            log.exception("on_finished failed for %s", path)

    def _write_midi(self, a: _Active) -> Path:
        day = a.started_wall.astimezone().strftime("%Y-%m-%d")
        d = self.out_dir / day
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{a.started_wall.astimezone().strftime('%H%M%S')}.mid"
        write_midi(path, a.messages)
        return path


def write_midi(path: Path, messages: list[tuple[float, mido.Message]]) -> None:
    """Write (seconds, message) pairs as a single-track type-0 MIDI file at 120 bpm."""
    mid = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=TEMPO, time=0))
    last = 0
    for t, msg in messages:
        tick = int(round(mido.second2tick(max(0.0, t), TICKS_PER_BEAT, TEMPO)))
        track.append(msg.copy(time=max(0, tick - last)))
        last = max(last, tick)
    mid.save(path)


@dataclass
class FinishedTake:
    title: str
    kind: str
    piece_id: int | None
    started_at: datetime
    midi_path: Path
    note_count: int
    duration_s: float
    metrics: dict
    auto_stopped: bool = False


@dataclass
class _Take:
    title: str
    kind: str
    piece_id: int | None
    started_wall: datetime
    started_mono: float
    messages: list[tuple[float, mido.Message]] = field(default_factory=list)
    notes: list[NoteEvent] = field(default_factory=list)
    open_notes: dict[int, NoteEvent] = field(default_factory=dict)
    pedal_downs: int = 0
    last_event: float = 0.0


class TakeRecorder:
    """A deliberate performance or cover take, started and stopped from the tablet.

    While a take is armed, MIDI goes here instead of the practice-session segmenter. The saved file
    starts at the first note (leading silence and any pedal pressed before it are pulled to t=0)
    and ends at the last event, so playback starts immediately. A take nobody stops is saved after
    `idle_seconds` of silence.
    """

    def __init__(
        self,
        out_dir: Path,
        idle_seconds: float = 300.0,
        on_auto_stop: Callable[[FinishedTake | None], None] | None = None,
    ):
        self.out_dir = out_dir
        self.idle_seconds = idle_seconds
        self.on_auto_stop = on_auto_stop
        self._take: _Take | None = None
        self._lock = threading.Lock()

    @property
    def active(self) -> bool:
        return self._take is not None

    def info(self) -> dict | None:
        t = self._take
        if t is None:
            return None
        return {
            "title": t.title,
            "kind": t.kind,
            "piece_id": t.piece_id,
            "started_at": t.started_wall.isoformat(),
            "note_count": len(t.notes),
        }

    def start(
        self, title: str, kind: str = "performance", piece_id: int | None = None, now: float | None = None
    ) -> bool:
        with self._lock:
            if self._take is not None:
                return False
            now = time.monotonic() if now is None else now
            self._take = _Take(title, kind, piece_id, datetime.now(UTC), now, last_event=now)
            return True

    def feed(self, msg: mido.Message, now: float | None = None) -> None:
        if msg.type in ("clock", "active_sensing", "sysex"):
            return
        now = time.monotonic() if now is None else now
        with self._lock:
            k = self._take
            if k is None:
                return
            t = now - k.started_mono
            k.messages.append((t, msg))
            k.last_event = now
            if msg.type == "note_on" and msg.velocity > 0:
                ev = NoteEvent(t=t, note=msg.note, velocity=msg.velocity)
                k.notes.append(ev)
                k.open_notes[msg.note] = ev
            elif msg.type in ("note_off", "note_on"):
                ev = k.open_notes.pop(msg.note, None)
                if ev:
                    ev.duration = t - ev.t
            elif msg.type == "control_change" and msg.control == 64 and msg.value >= 64:
                k.pedal_downs += 1

    def tick(self, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            k = self._take
            if k is None or now - k.last_event <= self.idle_seconds:
                return
            done = self._close_locked(auto=True)
        if self.on_auto_stop:
            try:
                self.on_auto_stop(done)
            except Exception:
                log.exception("on_auto_stop failed")

    def stop(self) -> FinishedTake | None:
        """Save the take. Returns None (and writes nothing) if no note was played."""
        with self._lock:
            return self._close_locked()

    def cancel(self) -> bool:
        with self._lock:
            had, self._take = self._take is not None, None
            return had

    def _close_locked(self, auto: bool = False) -> FinishedTake | None:
        k, self._take = self._take, None
        if k is None or not k.notes:
            return None
        t0 = k.notes[0].t
        for ev in k.notes:
            ev.t -= t0
        msgs = [(max(0.0, t - t0), m) for t, m in k.messages]
        duration = max(t for t, _ in msgs)
        local = k.started_wall.astimezone()
        d = self.out_dir / local.strftime("%Y-%m-%d")
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{local.strftime('%H%M%S')}.mid"
        n = 1
        while path.exists():
            n += 1
            path = d / f"{local.strftime('%H%M%S')}-{n}.mid"
        write_midi(path, msgs)
        return FinishedTake(
            title=k.title,
            kind=k.kind,
            piece_id=k.piece_id,
            started_at=k.started_wall,
            midi_path=path,
            note_count=len(k.notes),
            duration_s=round(duration, 2),
            metrics=session_metrics(k.notes, k.pedal_downs),
            auto_stopped=auto,
        )


def find_output_port(pattern: str) -> str | None:
    try:
        return _pick(mido.get_output_names(), pattern)
    except Exception:  # no ALSA sequencer
        return None


def find_input_port(pattern: str) -> str | None:
    return _pick(mido.get_input_names(), pattern)


def _pick(names: list[str], pattern: str) -> str | None:
    if pattern != "auto":
        return next((n for n in names if pattern.lower() in n.lower()), None)
    return next((n for n in names if "through" not in n.lower()), None)


class MidiCapture:
    """Owns the hardware port: opens it, reconnects when the piano is switched off and on again."""

    def __init__(
        self,
        segmenter: SessionSegmenter,
        pattern: str,
        loop: asyncio.AbstractEventLoop,
        take: TakeRecorder | None = None,
    ):
        self.segmenter = segmenter
        self.take = take
        self.pattern = pattern
        self.loop = loop
        self.port_name: str | None = None
        self._listeners: set[asyncio.Queue] = set()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="midi-capture", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3)
        self.segmenter.flush()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._listeners.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._listeners.discard(q)

    def broadcast(self, event: dict) -> None:
        def _put():
            for q in list(self._listeners):
                if not q.full():
                    q.put_nowait(event)

        self.loop.call_soon_threadsafe(_put)

    def route(self, msg: mido.Message, now: float | None = None) -> None:
        """A recording take gets the notes; otherwise they go to automatic practice capture."""
        if self.take is not None and self.take.active:
            self.take.feed(msg, now)
        else:
            self.segmenter.feed(msg, now)

    def _tick(self) -> None:
        self.segmenter.tick()
        if self.take is not None:
            self.take.tick()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                name = find_input_port(self.pattern)
            except Exception as e:  # no ALSA sequencer (e.g. container) or backend missing
                if not getattr(self, "_warned", False):
                    log.warning("cannot list MIDI ports (%s); will keep retrying", e)
                    self._warned = True
                name = None
            if not name:
                self.port_name = None
                self._tick()
                self._stop.wait(2.0)  # piano off: poll for it
                continue
            try:
                with mido.open_input(name) as port:
                    self.port_name = name
                    log.info("MIDI input open: %s", name)
                    self.broadcast({"type": "status", "midi": name})
                    while not self._stop.is_set():
                        for msg in port.iter_pending():
                            self.route(msg)
                            if msg.type in ("note_on", "note_off", "control_change"):
                                self.broadcast({"type": "midi", **msg.dict()})
                        self._tick()
                        if name not in mido.get_input_names():
                            raise OSError("port disappeared")
                        self._stop.wait(0.002)
            except Exception as e:  # unplugged / powered off
                log.warning("MIDI port lost (%s); retrying", e)
                self.port_name = None
                self.broadcast({"type": "status", "midi": None})
                self._stop.wait(1.0)
