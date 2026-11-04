import shutil

import pytest

from piano_companion.render import render_ly

pytestmark = pytest.mark.skipif(not shutil.which("lilypond"), reason="needs lilypond")


def test_render_pdf_and_midi(tmp_path):
    src = tmp_path / "src" / "tiny.ly"
    src.parent.mkdir()
    src.write_text('\\version "2.24.0"\n\\score { \\relative c\' { c4 d e f g1 } \\layout {} \\midi {} }\n')
    pdf, mid = render_ly(src, tmp_path / "out")
    assert pdf.read_bytes()[:4] == b"%PDF"
    assert mid.read_bytes()[:4] == b"MThd"
