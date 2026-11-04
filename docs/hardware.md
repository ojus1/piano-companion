# Hardware shopping list (India)

Prices are rough ranges from memory, not live quotes. Check before buying. Good stores for Pi parts are
[Robu.in](https://robu.in), [Thingbits](https://www.thingbits.in), [Robocraze](https://robocraze.com) and
[Probots](https://probots.co.in), which are authorised Raspberry Pi resellers. Use Amazon.in for cables and audio gear.

## How it connects

```
Yamaha P-155                                  Raspberry Pi 5 (on/inside the piano)
  USB TO HOST (USB-B) ──── USB A-to-B cable ───► USB 2.0 port      MIDI in + out (the main signal)
  AUX OUT L/L+R, R (6.35 mm) ─ 2× TS→RCA ─► Behringer UCA222 ─► USB  audio in   (phase 2, optional)
                                            UCA222 RCA out ──► small powered speaker (app voice/metronome)
Galaxy Tab S6 Lite ◄──── Wi-Fi (home LAN or Tailscale) ────► Pi web server
```

The P-155's **USB TO HOST** port is a class-compliant USB-MIDI device. Plugged into the Pi, it shows up as an
ALSA MIDI port with no driver. It carries every key, velocity and pedal event in both directions, so the Pi can
also *play the piano* (demo a passage on the piano's own sound engine). That means you don't need a speaker
to hear music from the app.

## Buy now (MVP, about ₹6–9k without the Pi)

| # | Item | Why | Approx. | Where |
|---|------|-----|---------|-------|
| 1 | **Raspberry Pi 5, 8 GB** *(skip if you have one)* | 4 GB is enough today. 8 GB leaves room for local audio models later | ₹8–9.5k | Robu, Thingbits, Robocraze |
| 2 | **Official Raspberry Pi 27 W USB-C power supply** | Under-powered Pi 5s throttle USB, which drops MIDI | ₹1–1.3k | same |
| 3 | **Raspberry Pi SSD Kit 256 GB** (M.2 HAT+ with NVMe SSD) | Recordings and DB on SSD, and boot from it. SD cards wear out under constant writes | ₹4–5k | same |
| 4 | **Official Active Cooler** | It sits next to a warm piano with no airflow | ₹500–650 | same |
| 5 | **USB 2.0 A-male to B-male cable, 1.5–3 m** ("printer cable") | Piano USB TO HOST to Pi: *this is the MIDI link* | ₹200–400 | Amazon.in |
| 6 | **microSD 32 GB A1/A2** (SanDisk/Samsung) | Only for flashing and recovery. Day-to-day boot is from the SSD | ₹350–500 | Amazon.in |
| 7 | Case or stand that fits the M.2 HAT+ (e.g. an acrylic Pi 5 case "with M.2 HAT+ standoffs") | The official Pi 5 case does not fit the HAT | ₹400–900 | Robu, Amazon.in |

**Alternative to items 3, 4 and 7:** an **Argon NEO 5 M.2 NVMe case** (₹3–3.5k) plus any 2230–2280 NVMe SSD.
It's an enclosed aluminium case with NVMe and cooling, and it looks tidy on a piano.

**Budget start:** skip the SSD and use a 64 GB SanDisk Extreme microSD (~₹800). MIDI files are tiny
(about 100 KB per hour). Add the SSD when you turn on audio recording.

## Phase 2: audio recording and a speaker (about ₹4–6k)

Buy these once MIDI works. MIDI already captures *what* you played. Audio adds how it *sounded*, which helps
when you listen back and for AI feedback later.

| Item | Why | Approx. |
|------|-----|---------|
| **Behringer UCA222** USB audio interface | Stereo RCA line in and out, class-compliant on Linux, cheap. In from the piano's AUX OUT, out to a speaker | ₹2.5–3.5k |
| **2× 6.35 mm (1/4") mono TS to RCA cable**, or one dual 2×TS to 2×RCA, 1.5 m | P-155 AUX OUT (L/L+R, R) to UCA222 inputs | ₹300–600 |
| Small powered speaker with an RCA or 3.5 mm AUX input (USB-powered desktop speakers are fine) | Voice prompts, metronome and coach feedback. The Pi 5 has no headphone jack | ₹800–1.5k |
| RCA to 3.5 mm cable (if the speaker takes 3.5 mm) | UCA222 out to speaker | ₹150 |

Better-quality alternative: **Behringer UMC204HD** (₹9–11k, two 1/4" line inputs, much lower noise).

## Nice to have

- **Bluetooth page-turner pedal** (Donner, or any pedal that sends arrow/PageDown keys), ₹2–3.5k. The score viewer already turns pages on those keys.
- **2 m USB-C cable plus a 15 W charger** for the tablet on the music rest. Turn on *Settings → Battery → Protect battery* (charge limit 85%) on the S6 Lite, since it will sit plugged in.
- **Surge-protected power strip** for the piano, Pi and speaker.
- **Ethernet cable** if the router is near the piano. It's more reliable than Wi-Fi for the Pi.
- **USB microphone** (later): only if you want voice commands or to practise on an acoustic piano.

## Search links

- Robu: [Pi 5](https://robu.in/?s=raspberry+pi+5) · [27W PSU](https://robu.in/?s=raspberry+pi+27w+power+supply) · [SSD kit](https://robu.in/?s=raspberry+pi+ssd+kit) · [Active cooler](https://robu.in/?s=raspberry+pi+5+active+cooler) · [Argon NEO 5](https://robu.in/?s=argon+neo+5)
- Amazon.in: [USB A-B cable](https://www.amazon.in/s?k=usb+a+to+b+cable+2m) · [Behringer UCA222](https://www.amazon.in/s?k=behringer+uca222) · [1/4 TS to RCA](https://www.amazon.in/s?k=6.35mm+ts+to+rca+cable) · [page turner pedal](https://www.amazon.in/s?k=bluetooth+page+turner+pedal)
