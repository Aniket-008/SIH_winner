/**
 * Radio player.
 *
 * Primary engine  : YouTube IFrame Player API (official uploads, credited).
 * Fallback engine : a generative Web Audio "lo-fi desk" loop, used when YouTube
 *                   is blocked (corporate VPN / firewall) or fails to load.
 */
import { formatTime, toast } from './ui.js';

const YT_API = 'https://www.youtube.com/iframe_api';

export class RadioPlayer extends EventTarget {
  constructor({ tracks = [], volume = 65 } = {}) {
    super();
    this.tracks = tracks;
    this.index = 0;
    this.volume = volume;
    this.muted = false;
    this.shuffle = false;
    this.playing = false;
    this.ready = false;
    this.mode = 'youtube';
    this.yt = null;
    this.fallback = null;
    this.ticker = 0;
  }

  get track() {
    return this.tracks[this.index] || null;
  }

  emit(type, detail = {}) {
    this.dispatchEvent(new CustomEvent(type, { detail }));
  }

  async init() {
    if (!this.tracks.length) return;
    try {
      await this.#loadYouTubeApi();
      this.#createYouTubePlayer();
    } catch {
      this.#degrade('YouTube blocked — switching to offline lo-fi engine 🎛️');
    }
    // Safety net: if the iframe never becomes ready, degrade gracefully.
    setTimeout(() => {
      if (!this.ready && this.mode === 'youtube') {
        this.#degrade('YouTube took too long — offline lo-fi engine on 🎛️');
      }
    }, 9000);
  }

  #loadYouTubeApi() {
    if (window.YT?.Player) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[src="${YT_API}"]`);
      const prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => {
        prev?.();
        resolve();
      };
      if (existing) return;
      const script = document.createElement('script');
      script.src = YT_API;
      script.async = true;
      script.onerror = () => reject(new Error('yt api blocked'));
      document.head.appendChild(script);
    });
  }

  #createYouTubePlayer() {
    this.yt = new window.YT.Player('ytPlayer', {
      height: '200',
      width: '320',
      videoId: this.track.id,
      playerVars: {
        autoplay: 0,
        controls: 0,
        disablekb: 1,
        modestbranding: 1,
        rel: 0,
        playsinline: 1,
        origin: window.location.origin,
      },
      events: {
        onReady: () => {
          this.ready = true;
          this.setVolume(this.volume);
          this.emit('ready', { mode: 'youtube' });
          this.emit('track', { track: this.track, index: this.index });
          this.#startTicker();
        },
        onStateChange: (event) => {
          const YTState = window.YT.PlayerState;
          if (event.data === YTState.ENDED) this.next();
          this.playing = event.data === YTState.PLAYING;
          this.emit('state', { playing: this.playing });
        },
        onError: () => {
          // Unavailable/region-locked video: skip ahead instead of dying.
          toast('Ye track available nahi hai, agla laga rahe hain ⏭');
          this.next();
        },
      },
    });
  }

  async #degrade(message) {
    if (this.mode === 'fallback') return;
    this.mode = 'fallback';
    this.ready = true;
    const { LofiEngine } = await import('./ambience.js');
    this.fallback = new LofiEngine();
    this.fallback.setVolume(this.muted ? 0 : this.volume / 100);
    toast(message);
    this.emit('ready', { mode: 'fallback' });
    this.emit('track', { track: this.track, index: this.index });
    this.#startTicker();
  }

  #startTicker() {
    clearInterval(this.ticker);
    this.ticker = setInterval(() => {
      const { current, duration } = this.progress();
      this.emit('progress', {
        current,
        duration,
        ratio: duration ? current / duration : 0,
        currentLabel: formatTime(current),
        durationLabel: formatTime(duration),
      });
    }, 500);
  }

  progress() {
    if (this.mode === 'youtube' && this.yt?.getDuration) {
      return { current: this.yt.getCurrentTime() || 0, duration: this.yt.getDuration() || 0 };
    }
    if (this.fallback) return this.fallback.progress();
    return { current: 0, duration: 0 };
  }

  play() {
    if (this.mode === 'youtube') this.yt?.playVideo?.();
    else this.fallback?.start();
    this.playing = true;
    this.emit('state', { playing: true });
  }

  pause() {
    if (this.mode === 'youtube') this.yt?.pauseVideo?.();
    else this.fallback?.stop();
    this.playing = false;
    this.emit('state', { playing: false });
  }

  toggle() {
    this.playing ? this.pause() : this.play();
  }

  load(index, autoplay = true) {
    if (!this.tracks.length) return;
    this.index = ((index % this.tracks.length) + this.tracks.length) % this.tracks.length;
    if (this.mode === 'youtube' && this.yt?.loadVideoById) {
      autoplay ? this.yt.loadVideoById(this.track.id) : this.yt.cueVideoById(this.track.id);
    } else if (this.fallback) {
      this.fallback.reseed(this.index);
      if (autoplay) this.fallback.start();
    }
    if (autoplay) this.playing = true;
    this.emit('track', { track: this.track, index: this.index });
    this.emit('state', { playing: this.playing });
  }

  next() {
    let nextIndex = this.index + 1;
    if (this.shuffle && this.tracks.length > 1) {
      do {
        nextIndex = Math.floor(Math.random() * this.tracks.length);
      } while (nextIndex === this.index);
    }
    this.load(nextIndex, true);
  }

  prev() {
    const { current } = this.progress();
    if (current > 5) return this.seekRatio(0);
    this.load(this.index - 1, true);
  }

  seekRatio(ratio) {
    const { duration } = this.progress();
    const target = Math.max(0, Math.min(1, ratio)) * (duration || 0);
    if (this.mode === 'youtube') this.yt?.seekTo?.(target, true);
    else this.fallback?.seek(target);
  }

  setVolume(value) {
    this.volume = Math.max(0, Math.min(100, value));
    this.muted = this.volume === 0;
    if (this.mode === 'youtube') this.yt?.setVolume?.(this.volume);
    else this.fallback?.setVolume(this.volume / 100);
    this.emit('volume', { volume: this.volume, muted: this.muted });
  }

  toggleMute() {
    if (this.muted) {
      this.muted = false;
      this.setVolume(this.lastVolume || 65);
    } else {
      this.lastVolume = this.volume || 65;
      this.muted = true;
      if (this.mode === 'youtube') this.yt?.setVolume?.(0);
      else this.fallback?.setVolume(0);
      this.emit('volume', { volume: 0, muted: true });
    }
  }

  toggleShuffle() {
    this.shuffle = !this.shuffle;
    this.emit('shuffle', { shuffle: this.shuffle });
    return this.shuffle;
  }
}

export default RadioPlayer;
