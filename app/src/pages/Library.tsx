import { useEffect, useState } from "react";
import { api, type Piece } from "../api";
import ScoreViewer from "../components/ScoreViewer";

const CATEGORIES = [
  ["", "All"],
  ["repertoire", "Repertoire"],
  ["etudes", "Études"],
  ["technique", "Technique"],
  ["vgm", "Game music"],
] as const;

export default function Library() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [pieces, setPieces] = useState<Piece[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Piece | null>(null);
  const [title, setTitle] = useState("");
  const [composer, setComposer] = useState("");

  const load = () =>
    api
      .pieces(q, category, category !== "vgm")
      .then(setPieces)
      .catch((e) => setError(String(e)));
  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, category]);

  if (open) return <ScoreViewer piece={open} onClose={() => setOpen(null)} />;

  return (
    <div className="page">
      <h2>Library</h2>
      <div className="row">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title or composer" />
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {CATEGORIES.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </div>
      {error && <p className="error">{error}</p>}
      <p className="muted">{pieces ? `${pieces.length} pieces${pieces.length === 200 ? " (first 200)" : ""}` : "Loading…"}</p>
      <ul className="queue">
        {pieces?.map((p) => (
          <li key={p.id} className="item">
            <div>
              <div className="title">{p.title}</div>
              <div className="muted">
                {[p.composer, p.level_henle != null && `Henle ${p.level_henle}`, (p.skills ?? []).slice(0, 3).join(", ")]
                  .filter(Boolean)
                  .join(" · ")}
              </div>
            </div>
            <div className="row">
              <span className="muted">
                {[p.musicxml_path && "notation", p.pdf_path && "PDF", p.midi_path && "MIDI"].filter(Boolean).join(" · ")}
              </span>
              <label className="button">
                Upload
                <input
                  type="file"
                  hidden
                  accept=".musicxml,.xml,.mxl,.pdf"
                  onChange={async (e) => {
                    const f = e.target.files?.[0];
                    if (f) {
                      await api.uploadScore(p.id, f);
                      load();
                    }
                  }}
                />
              </label>
              <button onClick={() => setOpen(p)}>Open</button>
            </div>
          </li>
        ))}
      </ul>
      <h2>Add your own piece</h2>
      <form
        className="row"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!title.trim()) return;
          await api.addPiece(title.trim(), composer.trim());
          setTitle("");
          setComposer("");
          setQ(title.trim());
        }}
      >
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" />
        <input value={composer} onChange={(e) => setComposer(e.target.value)} placeholder="Composer / arranger" />
        <button type="submit">Add piece</button>
      </form>
    </div>
  );
}
