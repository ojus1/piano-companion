"""Render LilyPond (.ly) scores from the catalog to PDF + MIDI with GNU LilyPond (GPL, run as a CLI).

Most Mutopia items in the research catalog are LilyPond source only. This turns them into a PDF the
tablet can show/annotate and, when the source has a \\midi block, a reference MIDI for the player.

    sudo apt install lilypond          # on the Pi (bootstrap-pi.sh does this)
    uv run piano-companion-render --research ~/research          # scheduled pieces
    uv run piano-companion-render --research ~/research --all    # the whole catalog

MuseScore (.mscx) files are better exported on a laptop: `mscore -o score.musicxml file.mscx`, then
upload through the Library.
"""

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from sqlmodel import Session, col, select

from .config import get_settings
from .db import get_engine
from .models import Piece, PracticeItem


def render_ly(src: Path, out_dir: Path, timeout: int = 300) -> tuple[Path | None, Path | None]:
    try:
        return _render(src, out_dir, timeout)
    except RuntimeError:
        # Older Mutopia sources use pre-2.24 syntax: upgrade a copy with convert-ly and retry.
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / src.parent.name
            shutil.copytree(src.parent, copy)
            for ly in copy.glob("*.ly*"):
                subprocess.run(["convert-ly", "-e", ly.name], cwd=copy, capture_output=True, timeout=timeout)
            return _render(copy / src.name, out_dir, timeout)


def _render(src: Path, out_dir: Path, timeout: int) -> tuple[Path | None, Path | None]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        stem = Path(tmp) / src.stem
        r = subprocess.run(
            ["lilypond", "-dno-point-and-click", "--pdf", "-o", str(stem), src.name],
            cwd=src.parent,  # Mutopia sources \include sibling files
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        pdf = stem.with_suffix(".pdf")
        midis = sorted(Path(tmp).glob(f"{src.stem}*.mid*"))
        if r.returncode != 0 and not pdf.exists():
            raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "lilypond failed")
        out_pdf = out_dir / "score.pdf" if pdf.exists() else None
        if out_pdf:
            shutil.copy2(pdf, out_pdf)
        out_mid = None
        if midis:
            out_mid = out_dir / "score.mid"
            shutil.copy2(midis[0], out_mid)
        return out_pdf, out_mid


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--research", type=Path, required=True, help="folder holding library/ (catalog source files)")
    ap.add_argument("--all", action="store_true", help="render every catalog piece, not just scheduled ones")
    args = ap.parse_args(argv)
    if not shutil.which("lilypond"):
        raise SystemExit("lilypond not found: sudo apt install lilypond")

    s = get_settings()
    lib_root = args.research / "library"
    with Session(get_engine()) as db:
        stmt = select(Piece).where(col(Piece.pdf_path).is_(None), col(Piece.catalog_id).is_not(None))
        if not args.all:
            ids = select(PracticeItem.piece_id).where(PracticeItem.active, col(PracticeItem.piece_id).is_not(None))
            stmt = stmt.where(col(Piece.id).in_(ids))
        todo = [p for p in db.exec(stmt) if (p.meta or {}).get("source_files", {}).get("ly")]
        print(f"{len(todo)} pieces to render")
        ok = 0
        for p in todo:
            src = lib_root / p.meta["source_files"]["ly"][0]
            try:
                pdf, mid = render_ly(src, s.library_dir / "catalog" / p.catalog_id)
            except Exception as e:  # keep going; report at the end
                print(f"  ✗ {p.title}: {e}")
                continue
            rel = lambda f: str(f.relative_to(s.library_dir)) if f else None  # noqa: E731
            p.pdf_path = rel(pdf)
            p.midi_path = p.midi_path or rel(mid)
            p.meta = {**p.meta, "rendered_with": "lilypond"}
            db.add(p)
            db.commit()
            ok += 1
            print(f"  ✓ {p.title}" + ("" if mid else " (no MIDI block)"))
    print(json.dumps({"rendered": ok, "failed": len(todo) - ok}))


if __name__ == "__main__":
    main()
