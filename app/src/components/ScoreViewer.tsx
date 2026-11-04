import { useEffect, useRef, useState } from "react";
import { api, type Piece } from "../api";

/**
 * MusicXML is rendered with OpenSheetMusicDisplay (reflowable, and later lets us drive a cursor
 * from live MIDI). PDFs are rendered page-by-page with pdf.js. Tap the right/left half to turn
 * pages; Bluetooth page-turner pedals send arrow/PageDown keys, which also work.
 */
export default function ScoreViewer({ piece, onClose }: { piece: Piece; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [pages, setPages] = useState(1);

  useEffect(() => {
    const el = ref.current!;
    el.innerHTML = "";
    let cancelled = false;
    (async () => {
      try {
        if (piece.musicxml_path) {
          const { OpenSheetMusicDisplay } = await import("opensheetmusicdisplay");
          const osmd = new OpenSheetMusicDisplay(el, { autoResize: true, drawTitle: true, backend: "svg" });
          await osmd.load(api.libraryUrl(piece.musicxml_path));
          if (!cancelled) osmd.render();
          setPages(1);
        } else if (piece.pdf_path) {
          const pdfjs = await import("pdfjs-dist");
          pdfjs.GlobalWorkerOptions.workerSrc = (await import("pdfjs-dist/build/pdf.worker.min.mjs?url")).default;
          const doc = await pdfjs.getDocument({ url: api.libraryUrl(piece.pdf_path) }).promise;
          if (cancelled) return;
          setPages(doc.numPages);
          for (let i = 1; i <= doc.numPages; i++) {
            const pg = await doc.getPage(i);
            const scale = (el.clientWidth / pg.getViewport({ scale: 1 }).width) * devicePixelRatio;
            const vp = pg.getViewport({ scale });
            const canvas = document.createElement("canvas");
            canvas.width = vp.width;
            canvas.height = vp.height;
            canvas.className = "pdf-page";
            canvas.dataset.page = String(i - 1);
            el.appendChild(canvas);
            await pg.render({ canvas, viewport: vp }).promise;
          }
        }
      } catch (e) {
        setError(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [piece]);

  const turn = (d: number) => {
    const next = Math.max(0, Math.min(pages - 1, page + d));
    setPage(next);
    const el = ref.current;
    if (!el) return;
    if (pages > 1) el.querySelector<HTMLElement>(`[data-page="${next}"]`)?.scrollIntoView({ behavior: "smooth" });
    else el.scrollBy({ top: d * el.clientHeight * 0.85, behavior: "smooth" });
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (["ArrowRight", "ArrowDown", "PageDown", " "].includes(e.key)) turn(1);
      if (["ArrowLeft", "ArrowUp", "PageUp"].includes(e.key)) turn(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="viewer">
      <div className="viewer-bar">
        <button onClick={onClose}>← Library</button>
        <strong>{piece.title}</strong>
        <span className="muted">{pages > 1 ? `page ${page + 1} / ${pages}` : ""}</span>
      </div>
      {error && <p className="error">{error}</p>}
      <div
        className="score"
        ref={ref}
        onClick={(e) => {
          const x = e.clientX / (e.currentTarget as HTMLElement).clientWidth;
          turn(x > 0.5 ? 1 : -1);
        }}
      />
    </div>
  );
}
