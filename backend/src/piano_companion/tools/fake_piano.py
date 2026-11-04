"""Play a MIDI file (or a generated C-major scale) into a virtual MIDI port, so the backend can be
tested without the piano. Run the backend with PC_MIDI_INPUT="Fake Piano", then:

    uv run fake-piano                 # scale
    uv run fake-piano song.mid        # any MIDI file

Needs python-rtmidi (the `hw` extra) and ALSA (Linux) or CoreMIDI (macOS).
"""

import sys
import time

import mido


def scale(bpm: int = 100):
    beat = 60 / bpm / 2  # eighth notes
    notes = [60, 62, 64, 65, 67, 69, 71, 72, 71, 69, 67, 65, 64, 62, 60]
    for n in notes:
        yield mido.Message("note_on", note=n, velocity=70)
        time.sleep(beat * 0.9)
        yield mido.Message("note_off", note=n, velocity=0)
        time.sleep(beat * 0.1)


def main() -> None:
    with mido.open_output("Fake Piano", virtual=True) as out:
        time.sleep(1.5)  # let the backend discover the port
        if len(sys.argv) > 1:
            for msg in mido.MidiFile(sys.argv[1]).play():
                out.send(msg)
        else:
            for _ in range(2):
                for msg in scale():
                    out.send(msg)
        print("done; the session closes after PC_SESSION_IDLE_SECONDS of silence")
        time.sleep(1)


if __name__ == "__main__":
    main()
