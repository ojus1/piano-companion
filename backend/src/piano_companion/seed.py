"""Import the research thread's curriculum and score catalog into the app.

    uv run piano-companion-seed --research /mnt/project-files/research --stages S1

- Every row of library/catalog.json (and vgm_personal/catalog_vgm.json) becomes a Piece. Files the
  app can display or align (MusicXML, MIDI, PDF) are copied into the library; .ly/.mscx/.krn paths
  are kept in Piece.meta until they are rendered (see docs/open-source.md).
- Items of the chosen stages become PracticeItems: technique, repertoire and VGM pieces, improv
  drills, the concept-graph nodes introduced in that stage, and one daily sight-reading item.
  Items whose score isn't downloaded yet (link_only / purchase) are created inactive.
- curriculum.json is copied into the data dir; srs.py reads FSRS parameters from it.

Re-running is safe: pieces are keyed by catalog id and items by source_key.
"""

import argparse
import json
import shutil
from pathlib import Path

from sqlmodel import Session, select

from . import curriculum, srs
from .config import get_settings
from .db import get_engine
from .models import Piece, PracticeItem

COPY_FORMATS = {"musicxml": "musicxml_path", "midi": "midi_path", "pdf": "pdf_path"}
KEEP_FIELDS = (
    "subtitle",
    "opus",
    "number",
    "keys",
    "meters",
    "level_source",
    "edition_source",
    "notes",
    "features",
    "source_repo",
    "game",
    "format",
    "planned_path",
    "source_url_verified",
)


def _copy(src_root: Path, rel: str, cid: str, dest_root: Path) -> str | None:
    src = src_root / rel
    if not src.is_file():
        return None
    dest_rel = f"catalog/{cid}/{src.name}"
    dest = dest_root / dest_rel
    if not dest.exists() or dest.stat().st_size != src.stat().st_size:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return dest_rel


def import_catalog(db: Session, catalog_path: Path, copy_files: bool = True) -> int:
    data = json.loads(catalog_path.read_text())
    lib_root = Path(data.get("library_root") or catalog_path.parent)
    if not lib_root.is_dir():
        lib_root = catalog_path.parent
    dest_root = get_settings().library_dir
    existing = {p.catalog_id: p for p in db.exec(select(Piece).where(Piece.catalog_id.is_not(None)))}
    n = 0
    for row in data["items"]:
        cid = row["id"]
        p = existing.get(cid) or Piece(catalog_id=cid, title=row["title"])
        p.title = row["title"] + (f" ({row['subtitle']})" if row.get("subtitle") else "")
        p.composer = row.get("composer")
        p.arranger = row.get("arranger") or row.get("arranger_or_sequencer")
        p.category = "vgm" if cid.startswith("vgm_") else row.get("category")
        p.level_henle = row.get("level_henle")
        p.level_abrsm = row.get("level_abrsm")
        p.skills = row.get("skills") or []
        p.license = row.get("license")
        p.source_url = row.get("source_url")
        files = row.get("files") or {}
        meta = {k: row[k] for k in KEEP_FIELDS if row.get(k) not in (None, "", [])}
        meta["source_files"] = {k: v for k, v in files.items() if v}
        p.meta = meta
        if copy_files:
            for fmt, attr in COPY_FORMATS.items():
                for rel in files.get(fmt) or []:
                    if dest := _copy(lib_root, rel, cid, dest_root):
                        setattr(p, attr, dest)
                        break
        db.add(p)
        n += 1
    db.commit()
    return n


def _stage_number(stage_id: str) -> int:
    return int(stage_id.lstrip("S"))


def _item(db: Session, key: str, **fields) -> bool:
    if db.exec(select(PracticeItem).where(PracticeItem.source_key == key)).first():
        return False
    db.add(PracticeItem(source_key=key, srs_state=srs.new_state(), **fields))
    return True


def import_stages(db: Session, cur: dict, stages: list[str]) -> int:
    by_cid = {p.catalog_id: p for p in db.exec(select(Piece).where(Piece.catalog_id.is_not(None)))}
    nodes = {n["id"]: n for n in cur.get("concept_graph", {}).get("nodes", [])}
    created = 0
    for stage in cur.get("stages", []):
        sid = stage["id"]
        if sid not in stages:
            continue
        for list_name, kind in (
            ("technique_items", "technique"),
            ("repertoire_items", "repertoire"),
            ("vgm_items", "vgm"),
        ):
            for it in stage.get(list_name, []):
                ref = it.get("ref") or {}
                piece = by_cid.get(ref.get("id"))
                key = f"{sid}:{kind}:{ref.get('id') or it['title']}"
                playable = it.get("status") in ("downloaded", "generated")
                created += _item(
                    db,
                    key,
                    kind=kind,
                    stage=sid,
                    title=it["title"],
                    piece_id=piece.id if piece else None,
                    active=playable,
                    details={
                        k: it[k]
                        for k in (
                            "composer",
                            "role",
                            "status",
                            "source_url",
                            "needs_render",
                            "henle_published",
                            "level_henle",
                            "level_abrsm",
                            "game",
                            "arranger",
                            "notes",
                        )
                        if it.get(k) is not None
                    },
                )
        for d in stage.get("improv_drills", []):
            created += _item(
                db,
                f"{sid}:improv:{d['id']}",
                kind="improv",
                stage=sid,
                title=d["name"],
                details={k: d.get(k) for k in ("concept", "description", "midi_check")},
            )
        for node in nodes.values():
            if node.get("stage_introduced") != _stage_number(sid) or node["domain"] in ("repertoire", "sight_reading"):
                continue
            created += _item(
                db,
                f"concept:{node['id']}",
                kind=node["domain"],
                stage=sid,
                title=node["name"],
                details={
                    "concept_id": node["id"],
                    "prerequisites": node.get("prerequisites", []),
                    "midi_check": node.get("midi_check"),
                },
            )
        sr = stage.get("sight_reading")
        if sr:
            created += _item(
                db,
                f"{sid}:sight_reading",
                kind="sight_reading",
                stage=sid,
                title=f"Sight-reading, {sr.get('level')} ({sr.get('daily_minutes', 10)} min)",
                details={k: v for k, v in sr.items() if k != "library_refs"}
                | {"library_refs": [r["ref"]["id"] for r in sr.get("library_refs", []) if r.get("ref")]},
            )
    db.commit()
    return created


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--research", type=Path, required=True, help="the research folder (has curriculum/ and library/)")
    ap.add_argument("--stages", default="S1", help="comma-separated stage ids to schedule, e.g. S1,S2")
    ap.add_argument("--no-copy", action="store_true", help="don't copy score files into the library")
    args = ap.parse_args(argv)

    s = get_settings()
    s.ensure_dirs()
    cur_path = args.research / "curriculum" / "curriculum.json"
    shutil.copy2(cur_path, curriculum.path())
    curriculum.reload()
    srs.reset()
    cur = curriculum.load()

    with Session(get_engine()) as db:
        n = 0
        for rel in cur.get("catalogs", {}).values():
            p = args.research / rel
            if p.is_file():
                n += import_catalog(db, p, copy_files=not args.no_copy)
        items = import_stages(db, cur, [x.strip() for x in args.stages.split(",") if x.strip()])
    print(f"pieces: {n} imported/updated · practice items created: {items} · data dir: {s.data_dir}")


if __name__ == "__main__":
    main()
