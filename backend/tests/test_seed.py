import json

from sqlmodel import Session, select


def _research(tmp_path):
    root = tmp_path / "research"
    (root / "curriculum").mkdir(parents=True)
    (root / "library" / "rep").mkdir(parents=True)
    (root / "library" / "rep" / "a.musicxml").write_text("<score-partwise/>")
    catalog = {
        "library_root": str(root / "library"),
        "items": [
            {
                "id": "a",
                "title": "Melodie",
                "composer": "Schumann",
                "category": "repertoire",
                "level_henle": 1,
                "skills": ["voicing_melody"],
                "files": {"musicxml": ["rep/a.musicxml"], "ly": []},
            },
            {
                "id": "b",
                "title": "Arabesque",
                "composer": "Burgmüller",
                "category": "etudes",
                "files": {"ly": ["etudes/b.ly"]},
            },
        ],
    }
    (root / "library" / "catalog.json").write_text(json.dumps(catalog))
    cur = {
        "catalogs": {"catalog.json": "library/catalog.json"},
        "stages": [
            {
                "id": "S1",
                "technique_items": [
                    {
                        "ref": {"catalog": "catalog.json", "id": "b"},
                        "title": "Arabesque",
                        "status": "downloaded",
                        "role": "staccato",
                    }
                ],
                "repertoire_items": [
                    {"ref": {"catalog": "catalog.json", "id": "a"}, "title": "Melodie", "status": "downloaded"}
                ],
                "vgm_items": [
                    {
                        "ref": {"catalog": "catalog_vgm.json", "id": "v"},
                        "title": "Song of Healing",
                        "status": "link_only",
                    }
                ],
                "improv_drills": [{"id": "I1.1", "name": "Chord tones", "concept": "im_chord_tones"}],
                "sight_reading": {"level": "Initial", "daily_minutes": 12, "library_refs": []},
            }
        ],
        "concept_graph": {
            "nodes": [
                {
                    "id": "t_five",
                    "name": "Five-finger patterns",
                    "domain": "technique",
                    "prerequisites": [],
                    "stage_introduced": 1,
                },
                {
                    "id": "th_late",
                    "name": "Later concept",
                    "domain": "theory",
                    "prerequisites": [],
                    "stage_introduced": 2,
                },
            ]
        },
        "scheduler_defaults": {"fsrs": {"desired_retention": {"technique": 0.85}, "maximum_interval_days": 180}},
    }
    (root / "curriculum" / "curriculum.json").write_text(json.dumps(cur))
    return root


def test_seed_is_idempotent(client, tmp_path):
    from piano_companion import seed
    from piano_companion.db import get_engine
    from piano_companion.models import Piece, PracticeItem

    root = _research(tmp_path)
    seed.main(["--research", str(root)])
    seed.main(["--research", str(root)])
    with Session(get_engine()) as db:
        pieces = db.exec(select(Piece)).all()
        items = db.exec(select(PracticeItem)).all()
    assert len(pieces) == 2
    a = next(p for p in pieces if p.catalog_id == "a")
    assert a.musicxml_path == "catalog/a/a.musicxml" and a.level_henle == 1
    assert client.get(f"/api/library/{a.musicxml_path}").text == "<score-partwise/>"
    kinds = sorted((i.kind, i.active) for i in items)
    assert kinds == [
        ("improv", True),
        ("repertoire", True),
        ("sight_reading", True),
        ("technique", True),
        ("technique", True),
        ("vgm", False),
    ]
    queue = client.get("/api/practice/queue?limit=20").json()
    assert {q["piece"]["title"] for q in queue if q["piece"]} == {"Melodie", "Arabesque"}
    assert client.get("/api/pieces?q=schu").json()[0]["title"] == "Melodie"
