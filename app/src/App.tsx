import { useState } from "react";
import { useLive, useWakeLock } from "./hooks";
import Today from "./pages/Today";
import Library from "./pages/Library";
import Sessions from "./pages/Sessions";
import Live from "./pages/Live";
import Record from "./pages/Record";
import Technique from "./pages/Technique";
import Progress from "./pages/Progress";

const TABS = ["Today", "Technique", "Progress", "Library", "Record", "Sessions", "Live"] as const;
type Tab = (typeof TABS)[number];

export default function App() {
  const [tab, setTab] = useState<Tab>("Today");
  const live = useLive();
  useWakeLock(true);

  return (
    <div className="app">
      <header className="topbar">
        <nav>
          {TABS.map((t) => (
            <button key={t} className={t === tab ? "tab active" : "tab"} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </nav>
        <div className="status" title={live.midiPort ?? "piano not connected"}>
          <span className={`dot ${live.connected ? (live.midiPort ? "ok" : "warn") : "off"}`} />
          {!live.connected ? "Pi offline" : live.midiPort ? "Piano connected" : "Piano off"}
          {live.recording && <span className="rec">● REC</span>}
        </div>
      </header>
      <main>
        {tab === "Today" && <Today lastSaved={live.lastSavedSession} />}
        {tab === "Technique" && <Technique held={live.held} pianoConnected={live.connected && !!live.midiPort} />}
        {tab === "Progress" && <Progress lastSaved={live.lastSavedSession} />}
        {tab === "Library" && <Library />}
        {tab === "Record" && <Record held={live.held} takeEvent={live.takeEvent} pianoConnected={!!live.midiPort} />}
        {tab === "Sessions" && <Sessions lastSaved={live.lastSavedSession} />}
        {tab === "Live" && <Live held={live.held} />}
      </main>
    </div>
  );
}
