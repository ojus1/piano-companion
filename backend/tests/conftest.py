import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PC_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PC_MIDI_ENABLED", "false")
    from piano_companion import config, db

    config.get_settings.cache_clear()
    db.reset_engine()
    from piano_companion.main import create_app

    with TestClient(create_app()) as c:
        yield c
    config.get_settings.cache_clear()
    db.reset_engine()
