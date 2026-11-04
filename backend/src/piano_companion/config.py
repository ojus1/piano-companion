"""Runtime settings. Override any field with an env var prefixed PC_, e.g. PC_DATA_DIR=/srv/piano."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PC_", env_file=".env", extra="ignore")

    data_dir: Path = Path.home() / "piano-data"
    host: str = "0.0.0.0"
    port: int = 8000

    # MIDI: substring of the ALSA port name to open. The P-155 shows up as "Digital Piano".
    # "auto" picks the first input that is not an ALSA "Midi Through" port.
    midi_input: str = "auto"
    # "none" disables MIDI capture entirely (e.g. on a laptop with no piano).
    midi_enabled: bool = True
    # A practice session ends after this many seconds with no notes.
    session_idle_seconds: float = 90.0
    # Sessions shorter than this (in notes) are discarded as noise (a cat on the keys).
    session_min_notes: int = 8
    # Disk cap for ~/piano-data/recordings. Oldest files are deleted past this; 0 disables.
    recordings_max_mb: int = 500

    # A performance take that nobody stops is saved after this many seconds of silence.
    take_idle_seconds: float = 300.0

    # Audio line-in capture alongside MIDI. Off by default: MIDI is the primary signal.
    audio_enabled: bool = False
    audio_device: str | None = None  # sounddevice name substring, e.g. "USB Audio CODEC"
    audio_samplerate: int = 48000
    audio_channels: int = 2

    # Built tablet app (app/dist) served at "/". Empty disables static serving.
    static_dir: Path | None = None

    @property
    def db_path(self) -> Path:
        return self.data_dir / "piano.db"

    @property
    def recordings_dir(self) -> Path:
        return self.data_dir / "recordings"

    @property
    def library_dir(self) -> Path:
        return self.data_dir / "library"

    @property
    def performances_dir(self) -> Path:
        # Kept outside recordings_dir on purpose: the recordings size cap must never touch these.
        return self.data_dir / "performances"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.recordings_dir, self.library_dir, self.performances_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
