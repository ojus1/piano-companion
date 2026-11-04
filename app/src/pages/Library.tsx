import { useState } from "react";
import { api, type Piece } from "../api";
import { useData } from "../hooks";
import ScoreViewer from "../components/ScoreViewer";

export default function Library() {
  const pieces = useData(api.pieces);
  const [open, setOpen] = useState<Piece | null>(null);
  const [title, setTitle] = useState("");
  const [composer, setComposer] = useState("");

  if (open) return <ScoreViewer piece={open} onClose={() => setOpen(null)} />;

  return (
    <div className="page">
      <h2>Library</h2>
      {pieces.error && <p className="error">{pieces.error}</p>}
      <ul className="queue">
        {pieces.data?.map((p) => (
          <li key={p.id} className="item">
            <div>
              <div className="title">{p.title}</div>
              <div className="muted">{[p.composer, p.arranger].filter(Boolean).join(" · ")}</div>
            </div>
            <div className="row">
              <label className="button">
                Upload score
                <input
                  type="file"
                  hidden
                  accept=".musicxml,.xml,.mxl,.pdf"
                  onChange={async (e) => {
                    const f = e.target.files?.[0];
                    if (f) {
                      await api.uploadScore(p.id, f);
                      pieces.reload();
                    }
                  }}
                />
              </label>
              <button disabled={!p.musicxml_path && !p.pdf_path} onClick={() => setOpen(p)}>
                Open
              </button>
            </div>
          </li>
        ))}
      </ul>
      <form
        className="row"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!title.trim()) return;
          await api.addPiece(title.trim(), composer.trim());
          setTitle("");
          setComposer("");
          pieces.reload();
        }}
      >
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" />
        <input value={composer} onChange={(e) => setComposer(e.target.value)} placeholder="Composer" />
        <button type="submit">Add piece</button>
      </form>
    </div>
  );
}
