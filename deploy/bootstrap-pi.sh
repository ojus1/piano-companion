#!/usr/bin/env bash
# One-time setup, run ON the Pi (Raspberry Pi OS Lite 64-bit) as your normal user:
#   bash deploy/bootstrap-pi.sh
set -euo pipefail

echo "==> System packages"
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  git curl rsync build-essential pkg-config \
  libasound2-dev libjack-jackd2-dev \
  libportaudio2 libsndfile1 alsa-utils

echo "==> uv (Python toolchain)"
if ! command -v uv >/dev/null && [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

echo "==> Audio/MIDI device access"
sudo usermod -aG audio "$USER"

echo "==> Tailscale (remote access from anywhere, HTTPS for the tablet)"
if ! command -v tailscale >/dev/null; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
# --ssh lets you `ssh piano-pi` from any device on your tailnet, no keys to copy around.
sudo tailscale up --ssh --hostname piano-pi || true

echo "==> Directories"
mkdir -p "$HOME/piano-data" "$HOME/piano-companion/backend" "$HOME/piano-companion/app/dist"

echo "==> systemd service"
sed -e "s|__USER__|$USER|g" -e "s|__HOME__|$HOME|g" \
  "$(dirname "$0")/piano-companion.service" | sudo tee /etc/systemd/system/piano-companion.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable piano-companion

echo "==> HTTPS on the tailnet: https://piano-pi.<your-tailnet>.ts.net -> localhost:8000"
sudo tailscale serve --bg 8000 || \
  echo "Turn on HTTPS certificates in the Tailscale admin console (DNS page), then run: sudo tailscale serve --bg 8000"

echo "Done. Log out and back in (for the audio group), then run ./deploy/deploy.sh from your laptop."
