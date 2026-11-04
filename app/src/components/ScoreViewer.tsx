import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { api, type Piece } from "../api";
import MidiPlayer from "./MidiPlayer";

// EmbedPDF + PDFium wasm is the heaviest dependency; load it only when a PDF is opened.
const PdfScore = lazy(() => import("./PdfScore"));

/**
 * One piece: MusicXML via OpenSheetMusicDisplay (BSD-3, reflows to the screen, cursor for score
 * following later), PDF via EmbedPDF (annotatable), and the reference MIDI in the player.
 */
export default function ScoreViewer({ piece: initial, onClose }: { piece: Piece; onClose: () => void }) {
  const [piece, setPiece] = useState(initial);
  const hasXml = !!piece.musicxml_path;
  const hasPdf = !!piece.pdf_path;
  const [view, setView] = useState<"xml" | "pdf">(hasXml ? "xml" : "pdf");

  return (
    <div className="viewer">
      <div className="viewer-bar">
        <button onClick={onClose}>← Library</button>
        <div>
          <strong>{piece.title}</strong>
          <div className="muted">
            {[piece.composer, piece.level_henle && `Henle ${piece.level_henle}`, piece.license].filter(Boolean).join(" · ")}
          </div>
        </div>
        {hasXml && hasPdf && (
          <div className="row">
            <button className={view === "xml" ? "tab active" : "tab"} onClick={() => setView("xml")}>Notation</button>
            <button className={view === "pdf" ? "tab active" : "tab"} onClick={() => setView("pdf")}>PDF</button>
          </div>
        )}
      </div>
      {piece.midi_path && (
        <div className="viewer-player">
          <MidiPlayer url={api.libraryUrl(piece.midi_path)} playOnPiano={{ piece_id: piece.id }} />
        </div>
      )}
      {view === "xml" && hasXml && <MusicXml path={piece.musicxml_path!} />}
      {view === "pdf" && hasPdf && (
        <Suspense fallback={<p className="page muted">Loading PDF viewer…</p>}>
          <PdfScore piece={piece} onSaved={setPiece} />
        </Suspense>
      )}
      {!hasXml && !hasPdf && (
        <p className="page muted">
          No displayable score yet.{" "}
          {piece.source_url && (
            <a href={piece.source_url} target="_blank" rel="noreferrer">
              Get it from the source
            </a>
          )}
        </p>
      )}
    </div>
  );
}

function MusicXml({ path }: { path: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const el = ref.current!;
    el.innerHTML = "";
    let cancelled = false;
    (async () => {
      try {
        const { OpenSheetMusicDisplay } = await import("opensheetmusicdisplay");
        const osmd = new OpenSheetMusicDisplay(el, { autoResize: true, drawTitle: true, backend: "svg" });
        await osmd.load(api.libraryUrl(path));
        if (!cancelled) osmd.render();
      } catch (e) {
        setError(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [path]);

  // Tap right/left half, or a Bluetooth page-turner pedal (arrow/PageDown keys), to scroll a screen.
  const turn = (d: number) => ref.current?.scrollBy({ top: d * ref.current.clientHeight * 0.85, behavior: "smooth" });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (["ArrowRight", "ArrowDown", "PageDown"].includes(e.key)) turn(1);
      if (["ArrowLeft", "ArrowUp", "PageUp"].includes(e.key)) turn(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      {error && <p className="error">{error}</p>}
      <div
        className="score"
        ref={ref}
        onClick={(e) => turn(e.clientX / (e.currentTarget as HTMLElement).clientWidth > 0.5 ? 1 : -1)}
      />
    </>
  );
}
