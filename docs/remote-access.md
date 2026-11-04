# Remote access, deploy and testing

**Tailscale** puts your laptop, the Pi and the tablet on one private network that works from anywhere: home
Wi-Fi, office, or phone hotspot. It's free for personal use. Every device gets a stable name (`piano-pi`,
`tab-s6-lite`), so you never chase changing IPs. Tailscale also gives the Pi a real HTTPS certificate, which
the tablet needs for "install app" and keep-screen-on.

## 1. Set up the Pi (once, about 30 min)

1. On your laptop, open **Raspberry Pi Imager**. Pick *Raspberry Pi OS Lite (64-bit)* and flash it to the
   microSD. In the Imager settings, set hostname `piano-pi` and your user and password, enable SSH, and add your
   Wi-Fi.
2. Boot the Pi and wait a minute, then `ssh <you>@piano-pi.local` from the same Wi-Fi.
3. If you bought the SSD kit, move the system onto the SSD so the SD card is only a spare:
   `sudo raspi-config` → *Advanced → Boot Order → NVMe/USB*, then use *SD Card Copier* (or `rpi-clone`) to copy
   the SD card to the SSD, and reboot.
4. Copy the repo over and run the bootstrap:
   ```bash
   rsync -a piano-companion/ <you>@piano-pi.local:piano-companion/
   ssh <you>@piano-pi.local 'bash piano-companion/deploy/bootstrap-pi.sh'
   ```
   This installs system packages, uv, Tailscale (with Tailscale SSH) and the systemd service. When it prints
   a login URL, open it and approve the Pi into your tailnet.
5. In the [Tailscale admin console](https://login.tailscale.com/admin/dns), turn on **MagicDNS** and **HTTPS
   Certificates**. Then on the Pi: `sudo tailscale serve --bg 8000`.
   The app is now at `https://piano-pi.<your-tailnet>.ts.net`.
6. Plug the piano's USB TO HOST into the Pi and turn the piano on. Check with `aconnect -i`, which should list
   something like `Digital Piano`.

## 2. Set up your laptop (once)

- Install Tailscale and log in with the same account. Now `ssh piano-pi` works from anywhere through Tailscale
  SSH, with no keys to manage.
- Install `uv`, Node 22+, `adb` (Android platform-tools) and `scrcpy` (`brew install scrcpy` /
  `sudo apt install scrcpy` / `winget install Genymobile.scrcpy`).

## 3. Set up the tablet (once)

1. Install **Tailscale** from the Play Store and log in with the same account. Turn on "Always-on VPN" for it
   in Android settings so it reconnects by itself.
2. Open Chrome, go to `https://piano-pi.<your-tailnet>.ts.net`, then tap **⋮ → Add to Home screen → Install**.
   It now opens full-screen like a native app and keeps the screen awake while open.
3. **Developer access (for testing from your laptop):**
   - Settings → About tablet → Software information → tap *Build number* 7 times to turn on Developer options.
   - Developer options → turn on **USB debugging** and **Wireless debugging**.
   - Pair once over Wi-Fi: Wireless debugging → *Pair device with pairing code*, then on the laptop
     `adb pair <ip>:<pair-port>` and enter the code, then `adb connect <ip>:<port>`.
   - For a fixed port that also works over Tailscale: with the tablet connected (USB or wireless), run
     `adb tcpip 5555`. After that, `make tablet-connect` (`adb connect tab-s6-lite:5555`) works from anywhere
     until the tablet reboots. After a reboot, repeat `adb tcpip 5555` once over wireless debugging.

## Daily development loop

| What | Command (from the repo root on your laptop) |
|------|------|
| Run all tests | `make test` |
| Backend on laptop, no piano | `make dev-backend` → http://localhost:8000/docs |
| UI with hot reload against the real Pi | `make dev-app`, then open `http://<laptop-name>:5173` on the tablet (over Tailscale) |
| UI with hot reload against the laptop backend | `PI_URL=http://localhost:8000 make dev-app` |
| Deploy to the Pi | `make deploy` (builds the app, rsyncs, `uv sync`, restarts, prints `/api/status`) |
| Tail the Pi's logs | `make logs` |
| Is the piano seen? | `make status` |
| Shell on the Pi | `make ssh` |
| See and control the tablet screen | `make tablet-connect && make tablet-mirror` |
| Debug the tablet's Chrome | Laptop Chrome → `chrome://inspect/#devices` (tablet connected by adb) → *inspect* gives full DevTools for the app running on the tablet |

### Testing without the piano

- The backend's unit tests feed synthetic MIDI into the session segmenter. No hardware is needed.
- On the Pi or a Linux laptop, you can drive the real capture path with a virtual MIDI port:
  ```bash
  PC_MIDI_INPUT="Fake Piano" PC_SESSION_IDLE_SECONDS=5 uv run piano-companion &
  uv run --extra hw fake-piano            # plays a C major scale twice
  uv run --extra hw fake-piano song.mid   # or any MIDI file
  ```
  The tablet's Live tab lights up the keys, and a session appears in Sessions 5 seconds later.

### Backups

All your data lives in `~/piano-data` on the Pi. The simplest backup is to pull it to the laptop
(`rsync -a piano-pi:piano-data/ ~/piano-backup/`). A nightly `rclone` to Google Drive is a good next step.
