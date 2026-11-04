import pytest

from piano_companion.tools import demo_data


def test_demo_data_fills_every_screen(client, tmp_path):
    (tmp_path / "piano.db").unlink(missing_ok=True)  # the client fixture already made one
    demo_data.build(tmp_path, days=60, seed=7)
    p = client.get("/api/progress").json()
    assert p["streak"]["current"] > 7 and p["technique"]["overall"]["attempts"] > 10
    assert len(client.get("/api/practice/queue").json()) == len(demo_data.QUEUE)
    takes = client.get("/api/performances").json()
    assert takes and all(t["midi_path"] for t in takes)
    study = next(x for x in client.get("/api/pieces?q=Study").json() if x["title"] == "Study in C")
    assert client.get(f"/api/library/{study['musicxml_path']}").text.startswith("<?xml")


def test_demo_data_refuses_an_existing_db(client):
    with pytest.raises(SystemExit):
        demo_data.main([])
