// Web Audio metronome with a look-ahead scheduler (clicks are scheduled on the audio clock, so they stay
// steady even when the UI thread is busy). Beat 1 of each bar is accented.

export type BeatListener = (beat: number, bar: number) => void;

export class Metronome {
  private ctx: AudioContext | null = null;
  private gain: GainNode | null = null;
  private timer: number | undefined;
  private nextTime = 0;
  private beat = 0;
  private uiTimers: number[] = [];
  bpm = 80;
  beatsPerBar = 4;
  volume = 0.6;
  onBeat: BeatListener | null = null;

  get running() {
    return this.timer !== undefined;
  }

  /** Must be called from a user gesture the first time (browser autoplay rules). */
  start(bpm = this.bpm, beatsPerBar = this.beatsPerBar) {
    this.stop();
    this.bpm = bpm;
    this.beatsPerBar = beatsPerBar;
    this.ctx ??= new AudioContext();
    void this.ctx.resume();
    this.gain ??= this.ctx.createGain();
    this.gain.connect(this.ctx.destination);
    this.gain.gain.value = this.volume;
    this.beat = 0;
    this.nextTime = this.ctx.currentTime + 0.1;
    this.timer = window.setInterval(() => this.schedule(), 25);
    this.schedule();
  }

  stop() {
    window.clearInterval(this.timer);
    this.timer = undefined;
    this.uiTimers.forEach((t) => window.clearTimeout(t));
    this.uiTimers = [];
  }

  setVolume(v: number) {
    this.volume = v;
    if (this.gain) this.gain.gain.value = v;
  }

  private schedule() {
    const ctx = this.ctx!;
    while (this.nextTime < ctx.currentTime + 0.12) {
      const beat = this.beat;
      this.click(this.nextTime, beat % this.beatsPerBar === 0);
      const delay = Math.max(0, (this.nextTime - ctx.currentTime) * 1000);
      this.uiTimers.push(window.setTimeout(() => this.onBeat?.(beat % this.beatsPerBar, Math.floor(beat / this.beatsPerBar)), delay));
      if (this.uiTimers.length > 16) this.uiTimers.shift();
      this.nextTime += 60 / this.bpm;
      this.beat++;
    }
  }

  private click(at: number, accent: boolean) {
    const ctx = this.ctx!;
    const osc = ctx.createOscillator();
    const env = ctx.createGain();
    osc.frequency.value = accent ? 1760 : 1175;
    env.gain.setValueAtTime(0.0001, at);
    env.gain.exponentialRampToValueAtTime(accent ? 1 : 0.6, at + 0.002);
    env.gain.exponentialRampToValueAtTime(0.0001, at + 0.05);
    osc.connect(env).connect(this.gain!);
    osc.start(at);
    osc.stop(at + 0.06);
  }
}
