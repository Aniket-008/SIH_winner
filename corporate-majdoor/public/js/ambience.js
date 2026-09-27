/**
 * Web Audio toys — everything here is synthesised in the browser, no files.
 *
 *  AmbienceMixer : cubicle atmosphere (rain on the glass, AC hum, keyboard clicks)
 *  LofiEngine    : generative lo-fi chord loop used when YouTube is unavailable
 */

function ctxFactory() {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  return AudioCtx ? new AudioCtx() : null;
}

function noiseBuffer(ctx, seconds = 2) {
  const buffer = ctx.createBuffer(1, ctx.sampleRate * seconds, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < data.length; i += 1) data[i] = Math.random() * 2 - 1;
  return buffer;
}

export class AmbienceMixer {
  constructor() {
    this.ctx = null;
    this.on = false;
    this.nodes = [];
    this.keyTimer = 0;
    this.level = 0.35;
  }

  #build() {
    const ctx = this.ctx;
    const master = ctx.createGain();
    master.gain.value = this.level;
    master.connect(ctx.destination);
    this.master = master;

    // Rain: filtered white noise with a slow LFO on the cutoff.
    const rain = ctx.createBufferSource();
    rain.buffer = noiseBuffer(ctx, 3);
    rain.loop = true;
    const rainFilter = ctx.createBiquadFilter();
    rainFilter.type = 'bandpass';
    rainFilter.frequency.value = 1100;
    rainFilter.Q.value = 0.6;
    const rainGain = ctx.createGain();
    rainGain.gain.value = 0.55;

    const lfo = ctx.createOscillator();
    lfo.frequency.value = 0.08;
    const lfoGain = ctx.createGain();
    lfoGain.gain.value = 320;
    lfo.connect(lfoGain).connect(rainFilter.frequency);

    rain.connect(rainFilter).connect(rainGain).connect(master);

    // AC / server-room hum
    const hum = ctx.createOscillator();
    hum.type = 'sawtooth';
    hum.frequency.value = 58;
    const humFilter = ctx.createBiquadFilter();
    humFilter.type = 'lowpass';
    humFilter.frequency.value = 160;
    const humGain = ctx.createGain();
    humGain.gain.value = 0.05;
    hum.connect(humFilter).connect(humGain).connect(master);

    rain.start();
    lfo.start();
    hum.start();
    this.nodes = [rain, lfo, hum];

    // Occasional mechanical keyboard clicks from the next cubicle
    const click = () => {
      if (!this.on) return;
      const burst = 2 + Math.floor(Math.random() * 6);
      for (let i = 0; i < burst; i += 1) {
        const t = ctx.currentTime + i * (0.06 + Math.random() * 0.09);
        const src = ctx.createBufferSource();
        src.buffer = noiseBuffer(ctx, 0.04);
        const bp = ctx.createBiquadFilter();
        bp.type = 'bandpass';
        bp.frequency.value = 1800 + Math.random() * 1400;
        const g = ctx.createGain();
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(0.16, t + 0.005);
        g.gain.exponentialRampToValueAtTime(0.0001, t + 0.05);
        src.connect(bp).connect(g).connect(master);
        src.start(t);
        src.stop(t + 0.08);
      }
      this.keyTimer = setTimeout(click, 1200 + Math.random() * 4200);
    };
    this.keyTimer = setTimeout(click, 1500);
  }

  toggle() {
    this.on ? this.stop() : this.start();
    return this.on;
  }

  start() {
    if (this.on) return;
    this.ctx = this.ctx || ctxFactory();
    if (!this.ctx) return;
    this.ctx.resume?.();
    this.on = true;
    this.#build();
  }

  stop() {
    if (!this.on) return;
    this.on = false;
    clearTimeout(this.keyTimer);
    try {
      this.master?.gain.setTargetAtTime(0, this.ctx.currentTime, 0.2);
      setTimeout(() => {
        this.nodes.forEach((node) => {
          try { node.stop(); } catch { /* already stopped */ }
        });
        this.nodes = [];
      }, 400);
    } catch { /* ignore */ }
  }

  setLevel(value) {
    this.level = Math.max(0, Math.min(1, value));
    if (this.master) this.master.gain.value = this.level;
  }
}

/* ────────────────────────────────────────────────────────── */

const PROGRESSIONS = [
  [0, 5, 3, 7],
  [0, 3, 8, 5],
  [2, 7, 0, 5],
  [0, 7, 9, 4],
];
const SCALE = [0, 2, 3, 5, 7, 8, 10]; // natural minor flavour

/** Generative lo-fi loop: warm chords + soft kick, all synthesised. */
export class LofiEngine {
  constructor() {
    this.ctx = null;
    this.playing = false;
    this.volume = 0.6;
    this.seed = 0;
    this.startedAt = 0;
    this.offset = 0;
    this.duration = 214; // pretend track length so the seek bar feels real
    this.timer = 0;
  }

  #ensure() {
    if (!this.ctx) {
      this.ctx = ctxFactory();
      if (!this.ctx) return false;
      this.master = this.ctx.createGain();
      this.master.gain.value = this.volume;
      const lp = this.ctx.createBiquadFilter();
      lp.type = 'lowpass';
      lp.frequency.value = 2400; // that muffled tape warmth
      this.master.connect(lp).connect(this.ctx.destination);

      // vinyl hiss bed
      const hiss = this.ctx.createBufferSource();
      hiss.buffer = noiseBuffer(this.ctx, 4);
      hiss.loop = true;
      const hissGain = this.ctx.createGain();
      hissGain.gain.value = 0.015;
      hiss.connect(hissGain).connect(this.master);
      hiss.start();
      this.hiss = hiss;
    }
    this.ctx.resume?.();
    return true;
  }

  #note(semitone, time, duration, gain = 0.09, type = 'sine') {
    const osc = this.ctx.createOscillator();
    osc.type = type;
    osc.frequency.value = 220 * Math.pow(2, semitone / 12);
    const env = this.ctx.createGain();
    env.gain.setValueAtTime(0.0001, time);
    env.gain.exponentialRampToValueAtTime(gain, time + 0.08);
    env.gain.exponentialRampToValueAtTime(0.0001, time + duration);
    osc.connect(env).connect(this.master);
    osc.start(time);
    osc.stop(time + duration + 0.05);
  }

  #kick(time) {
    const osc = this.ctx.createOscillator();
    osc.frequency.setValueAtTime(120, time);
    osc.frequency.exponentialRampToValueAtTime(45, time + 0.14);
    const env = this.ctx.createGain();
    env.gain.setValueAtTime(0.28, time);
    env.gain.exponentialRampToValueAtTime(0.0001, time + 0.24);
    osc.connect(env).connect(this.master);
    osc.start(time);
    osc.stop(time + 0.3);
  }

  #scheduleBar() {
    if (!this.playing) return;
    const ctx = this.ctx;
    const bar = 2.4; // seconds per bar (~100 bpm, 4/4 halved)
    const t0 = ctx.currentTime + 0.05;
    const progression = PROGRESSIONS[this.seed % PROGRESSIONS.length];
    const root = progression[this.bar % progression.length];

    // chord (root, third, fifth from the minor scale)
    [0, 2, 4].forEach((step, i) => {
      const semitone = root + SCALE[step % SCALE.length] + (i === 2 ? 12 : 0);
      this.#note(semitone - 12, t0, bar * 0.95, 0.055, 'triangle');
    });

    // melody sprinkle
    for (let i = 0; i < 4; i += 1) {
      if (Math.random() < 0.55) {
        const step = SCALE[Math.floor(Math.random() * SCALE.length)];
        this.#note(root + step + 12, t0 + i * (bar / 4), 0.45, 0.045, 'sine');
      }
    }

    this.#kick(t0);
    this.#kick(t0 + bar / 2 + 0.08);

    this.bar += 1;
    this.timer = setTimeout(() => this.#scheduleBar(), bar * 1000);
  }

  start() {
    if (this.playing || !this.#ensure()) return;
    this.playing = true;
    this.bar = 0;
    this.startedAt = performance.now() / 1000 - this.offset;
    this.master.gain.setTargetAtTime(this.volume, this.ctx.currentTime, 0.3);
    this.#scheduleBar();
  }

  stop() {
    if (!this.playing) return;
    this.playing = false;
    clearTimeout(this.timer);
    this.offset = this.progress().current;
    this.master?.gain.setTargetAtTime(0.0001, this.ctx.currentTime, 0.2);
  }

  reseed(index = 0) {
    this.seed = index;
    this.offset = 0;
    this.startedAt = performance.now() / 1000;
  }

  seek(seconds) {
    this.offset = Math.max(0, Math.min(this.duration, seconds));
    this.startedAt = performance.now() / 1000 - this.offset;
  }

  progress() {
    const current = this.playing
      ? Math.min(this.duration, performance.now() / 1000 - this.startedAt)
      : this.offset;
    return { current, duration: this.duration };
  }

  setVolume(value) {
    this.volume = Math.max(0, Math.min(1, value));
    if (this.master && this.playing) this.master.gain.value = this.volume;
  }
}
