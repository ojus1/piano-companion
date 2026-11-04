# Piano Companion

A practice companion that lives on the piano. A Raspberry Pi 5 records every practice session from a Yamaha
P-155 over USB-MIDI, tracks progress, and schedules practice with spaced repetition. A Galaxy Tab S6 Lite on the
music rest shows the day's assignments, sheet music, the practice log and a live keyboard.

- [docs/hardware.md](docs/hardware.md): what to buy (Indian retailers) and how it connects
- [docs/architecture.md](docs/architecture.md): how the system fits together, and why
- [docs/remote-access.md](docs/remote-access.md): Pi, tablet and laptop setup (Tailscale, SSH, adb), deploy and test

## Quick start (laptop, no hardware)

```bash
make test          # backend: ruff + pytest, app: typecheck + vitest
make dev-backend   # API on :8000 with MIDI off
PI_URL=http://localhost:8000 make dev-app   # app on :5173
```

## Layout

```
backend/   Python 3.11+, FastAPI, SQLite, mido, FSRS     (runs on the Pi under systemd)
app/       React + Vite + TypeScript PWA                  (served by the Pi, installed on the tablet)
deploy/    bootstrap-pi.sh (one time), deploy.sh (each release), systemd unit
docs/
```
