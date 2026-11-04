import { useCallback, useEffect, useRef, useState } from "react";
import { liveSocketUrl } from "./api";
import { applyMidiEvent } from "./midi";

export interface LiveState {
  connected: boolean;
  midiPort: string | null;
  recording: boolean;
  held: ReadonlySet<number>;
  lastSavedSession: number | null;
}

/** WebSocket to the Pi's live MIDI stream, reconnecting with backoff (the Pi may reboot). */
export function useLive(): LiveState {
  const [s, setS] = useState<LiveState>({
    connected: false,
    midiPort: null,
    recording: false,
    held: new Set(),
    lastSavedSession: null,
  });
  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry = 500;
    let timer: number | undefined;
    let closed = false;
    const connect = () => {
      ws = new WebSocket(liveSocketUrl());
      ws.onopen = () => {
        retry = 500;
        setS((p) => ({ ...p, connected: true }));
      };
      ws.onmessage = (m) => {
        const ev = JSON.parse(m.data);
        setS((p) => {
          if (ev.type === "status") return { ...p, midiPort: ev.midi ?? null };
          if (ev.type === "session")
            return ev.state === "started"
              ? { ...p, recording: true }
              : { ...p, recording: false, lastSavedSession: ev.id };
          if (ev.type === "note_on" || ev.type === "note_off") return { ...p, held: applyMidiEvent(p.held, ev) };
          return p;
        });
      };
      ws.onclose = () => {
        setS((p) => ({ ...p, connected: false, held: new Set() }));
        if (!closed) timer = window.setTimeout(connect, (retry = Math.min(retry * 2, 10000)));
      };
    };
    connect();
    return () => {
      closed = true;
      window.clearTimeout(timer);
      ws?.close();
    };
  }, []);
  return s;
}

/** Keep the tablet screen on while the app is open (needs HTTPS, see docs/remote-access.md). */
export function useWakeLock(enabled: boolean) {
  const lock = useRef<WakeLockSentinel | null>(null);
  useEffect(() => {
    if (!enabled || !("wakeLock" in navigator)) return;
    const acquire = () =>
      navigator.wakeLock
        .request("screen")
        .then((l) => (lock.current = l))
        .catch(() => {});
    acquire();
    const onVis = () => document.visibilityState === "visible" && acquire();
    document.addEventListener("visibilitychange", onVis);
    return () => {
      document.removeEventListener("visibilitychange", onVis);
      lock.current?.release();
    };
  }, [enabled]);
}

/** Fetch-on-mount with a manual reload. */
export function useData<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => {
    load()
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(reload, [reload]);
  return { data, error, reload };
}
