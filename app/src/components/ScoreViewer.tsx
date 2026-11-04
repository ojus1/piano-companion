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
  const [paper, setPaper] = useState(() => {
    try {
      return localStorage.getItem("score-paper") === "1";
    } catch {
      return false;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem("score-paper", paper ? "1" : "0");
    } catch {
      /* private mode */
    }
  }, [paper]);

  return (
    <div className="viewer">
      <div className="viewer-bar">
        <button className="ghost" onClick={onClose} aria-label="Back">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
            <path d="M10 3L5 8l5 5" />
          </svg>
          Back
        </button>
        <div className="grow">
          <strong>{piece.title}</strong>
          <div className="muted">
            {[piece.composer, piece.level_henle && `Henle ${piece.level_henle}`, piece.license].filter(Boolean).join(" · ")}
          </div>
        </div>
        {hasXml && hasPdf && (
          <div className="segmented">
            <button className={view === "xml" ? "active" : ""} onClick={() => setView("xml")}>Notation</button>
            <button className={view === "pdf" ? "active" : ""} onClick={() => setView("pdf")}>PDF</button>
          </div>
        )}
        {view === "xml" && hasXml && (
          <div className="segmented" aria-label="Notation colours">
            <button className={!paper ? "active" : ""} onClick={() => setPaper(false)}>Dark</button>
            <button className={paper ? "active" : ""} onClick={() => setPaper(true)}>Paper</button>
          </div>
        )}
      </div>
      {piece.midi_path && (
        <div className="viewer-player">
          <MidiPlayer url={api.libraryUrl(piece.midi_path)} playOnPiano={{ piece_id: piece.id }} />
        </div>
      )}
      {view === "xml" && hasXml && <MusicXml path={piece.musicxml_path!} paper={paper} />}
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

// Notation ink on the dark ground; "Paper" switches to black on a soft off-white page.
const INK = "#dcdad4";

function MusicXml({ path, paper }: { path: string; paper: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const el = ref.current!;
    el.innerHTML = "";
    let cancelled = false;
    (async () => {
      try {
        const { OpenSheetMusicDisplay } = await import("opensheetmusicdisplay");
        const osmd = new OpenSheetMusicDisplay(el, {
          autoResize: true,
          drawTitle: true,
          backend: "svg",
          defaultColorMusic: paper ? "#000000" : INK,
          defaultColorTitle: paper ? "#000000" : INK,
        });
        await osmd.load(api.libraryUrl(path));
        if (!cancelled) osmd.render();
      } catch (e) {
        setError(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [path, paper]);

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
        className={paper ? "score paper" : "score"}
        ref={ref}
        onClick={(e) => turn(e.clientX / (e.currentTarget as HTMLElement).clientWidth > 0.5 ? 1 : -1)}
      />
    </>
  );
}
