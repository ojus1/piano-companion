import { useMemo, useRef, useState } from "react";
import { PDFViewer, type PDFViewerRef } from "@embedpdf/react-pdf-viewer";
import wasmUrl from "@embedpdf/pdfium/pdfium.wasm?url";
import { api, type Piece } from "../api";

/**
 * PDF scores with EmbedPDF (MIT, PDFium compiled to WebAssembly): thumbnails, zoom, search, and
 * annotations (pen/ink for the S Pen, highlight, text, shapes). "Save markings" bakes the annotations
 * into a copy of the PDF on the Pi; the original stays untouched. Everything loads from the Pi,
 * no CDN: the wasm is bundled and external fonts are disabled.
 */
// EmbedPDF's own dark theme is navy; match the app's matte neutrals instead.
const PDF_THEME = {
  background: { app: "#121211", surface: "#1a1a19", surfaceAlt: "#1a1a19", elevated: "#232322", input: "#232322" },
  foreground: { primary: "#ecebe7", secondary: "#a7a59f", muted: "#8b8984", onAccent: "#0f1410" },
  border: { default: "#2a2a28", subtle: "#2a2a28", strong: "#3a3a37" },
  accent: { primary: "#9fbfa6", primaryHover: "#b2cdb8", primaryActive: "#8aab92", primaryLight: "#24302a", primaryForeground: "#0f1410" },
  interactive: { hover: "#232322", active: "#2a2a28", selected: "#24302a", focus: "#9fbfa6", focusRing: "#24302a" },
  scrollbar: { track: "#121211", thumb: "#3a3a37", thumbHover: "#4a4a46" },
  tooltip: { background: "#232322", foreground: "#ecebe7" },
};

export default function PdfScore({ piece, onSaved }: { piece: Piece; onSaved: (p: Piece) => void }) {
  const viewer = useRef<PDFViewerRef>(null);
  const [status, setStatus] = useState<string | null>(null);
  const src = api.libraryUrl((piece.pdf_annotated_path ?? piece.pdf_path)!);
  // The viewer re-initialises (and drops the open document) whenever `config` changes identity,
  // so it must be memoised: a status update re-render would otherwise lose the document mid-save.
  const config = useMemo(
    () => ({
      src,
      wasmUrl: new URL(wasmUrl, location.href).href, // absolute: the engine runs in a worker
      fontFallback: null,
      fonts: { ui: null, signature: null },
      stamp: { manifests: [] }, // default stamps come from a CDN; keep everything on the Pi
      theme: { preference: "dark" as const, dark: PDF_THEME },
      disabledCategories: ["redaction", "print"],
      // Author name stamped on annotations; set VITE_ANNOTATION_AUTHOR in app/.env.local (not committed).
      annotations: { annotationAuthor: import.meta.env.VITE_ANNOTATION_AUTHOR || "Me" },
    }),
    [src],
  );

  const save = async () => {
    setStatus("Saving…");
    try {
      const registry = await viewer.current?.registry;
      const exporter = registry?.getPlugin("export") as unknown as {
        provides(): { saveAsCopy(): { toPromise(): Promise<ArrayBuffer> } };
      } | null;
      if (!exporter) throw new Error("viewer not ready");
      const buf = await exporter.provides().saveAsCopy().toPromise();
      const r = await fetch(`/api/pieces/${piece.id}/annotated-pdf`, {
        method: "PUT",
        headers: { "Content-Type": "application/pdf" },
        body: buf,
      });
      if (!r.ok) throw new Error(`save failed: ${r.status}`);
      onSaved(await r.json());
      setStatus("Saved");
    } catch (e) {
      setStatus(String(e));
    }
  };

  return (
    <div className="pdf-wrap">
      <div className="row pdf-actions">
        <button onClick={save}>Save markings</button>
        {piece.pdf_annotated_path && <span className="muted">showing your marked-up copy</span>}
        {status && <span className="muted">{status}</span>}
      </div>
      <div className="pdf-viewer">
        <PDFViewer ref={viewer} config={config} />
      </div>
    </div>
  );
}
