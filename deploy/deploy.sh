#!/usr/bin/env bash
# Run from your laptop at the repo root:  ./deploy/deploy.sh [host]
# Builds the tablet app locally, syncs code to the Pi, installs deps, restarts the service.
# Recordings and the database live in ~/piano-data on the Pi and are never touched by a deploy.
set -euo pipefail
HOST="${1:-${PI_HOST:-piano-pi}}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Building tablet app"
(cd "$ROOT/app" && npm ci --silent && npm run build --silent)

echo "==> Syncing code to $HOST"
rsync -az --delete \
  --exclude .venv --exclude __pycache__ --exclude .pytest_cache --exclude .ruff_cache \
  --exclude .env --exclude .devdata \
  "$ROOT/backend/" "$HOST:piano-companion/backend/"
rsync -az --delete "$ROOT/app/dist/" "$HOST:piano-companion/app/dist/"

echo "==> Installing deps and restarting"
ssh "$HOST" 'cd ~/piano-companion/backend \
  && ~/.local/bin/uv sync --frozen --no-dev --extra hw -q \
  && sudo systemctl restart piano-companion \
  && sleep 2 && curl -fsS localhost:8000/api/status && echo'
