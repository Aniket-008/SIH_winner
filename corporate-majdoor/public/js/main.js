/** Bootstraps the whole workspace: theme, player, chat, overlays, shortcuts. */
import {
  qs, qsa, store, toast, pick,
  registerLayer, openLayer, closeLayer, toggleLayer, isLayerOpen, closeTopLayer,
} from './ui.js';
import { RadioPlayer } from './player.js';
import { AmbienceMixer } from './ambience.js';
import { LiveChat } from './chat.js';
import { MeetingNotes } from './notes.js';
import { FakeWork } from './fakework.js';
import { initBoss, openBoss } from './boss.js';
import { initRain, initChaiBanter, flashAlarm } from './effects.js';
import { shareTargets } from './data.js';

const state = {
  player: null,
  ambience: new AmbienceMixer(),
  chat: new LiveChat(),
  notes: new MeetingNotes(),
  fakework: null,
  resumeAfterPanic: false,
};

/* ─────────── layers ─────────── */
function registerLayers() {
  registerLayer('chat', {
    el: qs('#chatDrawer'),
    onOpen: () => {
      state.chat.markRead();
      setTimeout(() => qs('#chatInput').focus(), 200);
    },
  });
  registerLayer('playlist', { el: qs('#playlistPanel'), openClass: 'is-open' });
  registerLayer('boss', { el: qs('#bossModal') });
  registerLayer('support', { el: qs('#supportModal') });
  registerLayer('share', { el: qs('#shareModal') });
  registerLayer('name', { el: qs('#nameModal') });
  registerLayer('notes', {
    el: qs('#notesOverlay'),
    onOpen: () => state.notes.resize(),
  });
  registerLayer('ide', { el: qs('#ideOverlay') });

  // the playlist panel uses [hidden]; mirror it with the class
  const panel = qs('#playlistPanel');
  const observer = new MutationObserver(() => {
    panel.hidden = !panel.classList.contains('is-open');
  });
  observer.observe(panel, { attributes: true, attributeFilter: ['class'] });

  qsa('[data-close]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const name = btn.dataset.close;
      if (name === 'ide') state.fakework.exit();
      else closeLayer(name);
    });
  });

  // click on modal backdrop closes it
  qsa('.modal').forEach((modal) => {
    modal.addEventListener('mousedown', (event) => {
      if (event.target === modal) {
        const id = modal.id.replace('Modal', '');
        closeLayer(id === 'support' ? 'support' : id);
      }
    });
  });
}

/* ─────────── theme ─────────── */
function initTheme() {
  const select = qs('#themeSelect');
  const saved = store.get('theme', 'majdoor');
  document.documentElement.dataset.theme = saved;
  select.value = saved;
  select.addEventListener('change', () => {
    document.documentElement.dataset.theme = select.value;
    store.set('theme', select.value);
    toast(`Theme: ${select.options[select.selectedIndex].text}`);
  });
}

/* ─────────── player ─────────── */
async function initPlayer() {
  let tracks = [];
  try {
    const response = await fetch('/api/playlist');
    tracks = (await response.json()).tracks || [];
  } catch {
    const module = await import('./fallback-playlist.js');
    tracks = module.default;
  }

  const player = new RadioPlayer({ tracks, volume: store.get('volume', 65) });
  state.player = player;
  qs('#statTracks').textContent = String(tracks.length);

  const playBtn = qs('#playBtn');
  const vinyl = qs('#vinyl');

  player.addEventListener('track', ({ detail }) => {
    const { track } = detail;
    if (!track) return;
    qs('#trackTitle').textContent = `${track.title} — ${track.movie}`;
    qs('#trackArtist').textContent = track.artist;
    qs('#trackCredits').textContent = track.credits;
    document.title = `${track.title} • Corporate Majdoor`;
    renderPlaylist(tracks, detail.index);
  });

  player.addEventListener('state', ({ detail }) => {
    playBtn.textContent = detail.playing ? '❚❚' : '▶';
    vinyl.classList.toggle('is-spinning', detail.playing);
  });

  player.addEventListener('progress', ({ detail }) => {
    const pct = Math.max(0, Math.min(100, detail.ratio * 100));
    qs('#seekFill').style.width = `${pct}%`;
    qs('#seekKnob').style.left = `${pct}%`;
    qs('#seek').setAttribute('aria-valuenow', String(Math.round(pct)));
    qs('#timeNow').textContent = detail.currentLabel;
    qs('#timeTotal').textContent = detail.durationLabel;
  });

  player.addEventListener('volume', ({ detail }) => {
    qs('#muteBtn').textContent = detail.muted || detail.volume === 0 ? '🔇' : '🔊';
    if (!detail.muted) store.set('volume', detail.volume);
  });

  playBtn.addEventListener('click', () => player.toggle());
  qs('#nextBtn').addEventListener('click', () => player.next());
  qs('#prevBtn').addEventListener('click', () => player.prev());
  qs('#muteBtn').addEventListener('click', () => player.toggleMute());
  qs('#shuffleBtn').addEventListener('click', (event) => {
    const on = player.toggleShuffle();
    event.currentTarget.classList.toggle('is-on', on);
    toast(on ? 'Shuffle on 🔀' : 'Shuffle off ➡️');
  });

  const volume = qs('#volume');
  volume.value = store.get('volume', 65);
  volume.addEventListener('input', () => player.setVolume(Number(volume.value)));

  // seek bar (click + drag)
  const seek = qs('#seek');
  const seekTo = (event) => {
    const rect = seek.getBoundingClientRect();
    player.seekRatio((event.clientX - rect.left) / rect.width);
  };
  let seeking = false;
  seek.addEventListener('pointerdown', (event) => {
    seeking = true;
    seek.setPointerCapture(event.pointerId);
    seekTo(event);
  });
  seek.addEventListener('pointermove', (event) => seeking && seekTo(event));
  seek.addEventListener('pointerup', () => { seeking = false; });
  seek.addEventListener('keydown', (event) => {
    const { current, duration } = player.progress();
    if (event.key === 'ArrowRight') player.seekRatio((current + 10) / (duration || 1));
    if (event.key === 'ArrowLeft') player.seekRatio((current - 10) / (duration || 1));
  });

  qs('#ambienceBtn').addEventListener('click', (event) => {
    const on = state.ambience.toggle();
    event.currentTarget.classList.toggle('is-on', on);
    toast(on ? 'Cubicle ambience on 🌧⌨️' : 'Ambience off');
  });

  qs('#playlistBtn').addEventListener('click', () => toggleLayer('playlist'));

  await player.init();
}

function renderPlaylist(tracks, activeIndex) {
  const host = qs('#playlistItems');
  host.innerHTML = '';
  tracks.forEach((track, index) => {
    const li = document.createElement('li');
    li.className = index === activeIndex ? 'is-active' : '';
    li.innerHTML = `<span class="num">${String(index + 1).padStart(2, '0')}</span>
      <span><b></b><small></small></span>`;
    li.querySelector('b').textContent = track.title;
    li.querySelector('small').textContent = `${track.movie} • ${track.artist}`;
    li.addEventListener('click', () => {
      state.player.load(index, true);
      state.player.play();
    });
    host.appendChild(li);
  });
}

/* ─────────── action bar ─────────── */
function initActions() {
  qs('#actionBar').addEventListener('click', (event) => {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    if (action === 'chat') toggleLayer('chat');
    if (action === 'boss') openBoss();
    if (action === 'notes') openLayer('notes');
    if (action === 'share') openLayer('share');
    if (action === 'fakework') panic();
  });

  qs('#supportBtn').addEventListener('click', () => openLayer('support'));
  qs('#footerSupport').addEventListener('click', (e) => { e.preventDefault(); openLayer('support'); });
  qs('#footerShare').addEventListener('click', (e) => { e.preventDefault(); openLayer('share'); });

  qs('#copyUpi').addEventListener('click', async () => {
    await navigator.clipboard?.writeText(qs('#upiId').textContent.trim());
    toast('UPI ID copied ❤️');
  });
}

function panic() {
  if (state.player?.playing) {
    state.resumeAfterPanic = true;
    state.player.pause();
  }
  state.chat.raiseAlarm();
  state.fakework.enter();
}

/* ─────────── share ─────────── */
function initShare() {
  const url = window.location.href.split('#')[0];
  const title = 'Corporate Majdoor — 9 to 5 Indian office radio 🎧';
  qs('#shareUrl').value = url;

  const grid = qs('#shareGrid');
  grid.innerHTML = '';
  shareTargets(url, title).forEach((target) => {
    const a = document.createElement('a');
    a.href = target.href;
    a.target = '_blank';
    a.rel = 'noopener';
    a.textContent = target.label;
    grid.appendChild(a);
  });

  qs('#copyLink').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(url);
      toast('Link copied — ab colleague ko bhejo 🔗');
    } catch {
      qs('#shareUrl').select();
      toast('Press Ctrl+C to copy');
    }
  });

  // use the native share sheet on mobile when available
  if (navigator.share) {
    const native = document.createElement('a');
    native.href = '#';
    native.textContent = '📱 More…';
    native.addEventListener('click', (event) => {
      event.preventDefault();
      navigator.share({ title, url }).catch(() => {});
    });
    grid.appendChild(native);
  }
}

/* ─────────── shortcuts ─────────── */
function initShortcuts() {
  document.addEventListener('keydown', (event) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)
      || event.target.isContentEditable;

    if (event.key === 'Escape') {
      if (isLayerOpen('ide')) return state.fakework.exit();
      closeTopLayer();
      return;
    }
    if (typing) return;

    switch (event.key.toLowerCase()) {
      case ' ':
      case 'k':
        event.preventDefault();
        state.player?.toggle();
        break;
      case 'arrowright':
        state.player?.next();
        break;
      case 'arrowleft':
        state.player?.prev();
        break;
      case 'm':
        state.player?.toggleMute();
        break;
      case 'c':
        toggleLayer('chat');
        break;
      case 'b':
        openBoss();
        break;
      case 'n':
        openLayer('notes');
        break;
      case 'f':
        panic();
        break;
      default:
        break;
    }
  });
}

/* ─────────── stats strip ─────────── */
async function refreshStats() {
  try {
    const [health, messages] = await Promise.all([
      fetch('/api/health').then((r) => r.json()),
      fetch('/api/chat/messages?limit=200').then((r) => r.json()),
    ]);
    qs('#statListeners').textContent = health.listeners ?? 0;
    qs('#listenerCount').textContent = health.listeners ?? 0;
    qs('#statMessages').textContent = messages.messages?.length ?? 0;
    qs('#statUptime').textContent = `${Math.max(1, Math.round((health.uptimeSeconds || 0) / 60))}m`;
    qs('#shiftLabel').textContent = health.shift?.label || '9 to 5 ki majdoori';
  } catch {
    qs('#shiftLabel').textContent = 'Offline mode • lo-fi still works';
  }
}

/* ─────────── boot ─────────── */
function boot() {
  registerLayers();
  initTheme();
  initBoss();
  initActions();
  initShare();
  initShortcuts();
  initRain();
  initChaiBanter();

  state.notes.init();
  state.fakework = new FakeWork({
    onExit: () => {
      if (state.resumeAfterPanic) {
        state.player?.play();
        state.resumeAfterPanic = false;
      }
      toast(pick(['Boss chala gaya 😮‍💨', 'Safe! Wapas lo-fi pe 🎧', 'Close call tha yaar 😅']));
    },
  });
  state.fakework.init();

  state.chat.connect();
  state.chat.addEventListener('presence', ({ detail }) => {
    qs('#listenerCount').textContent = detail.listeners;
    qs('#statListeners').textContent = detail.listeners;
  });
  state.chat.addEventListener('alarm', ({ detail }) => {
    flashAlarm();
    toast(`🚨 ${detail.from} bola: Boss aa gaya!`);
  });

  initPlayer();
  refreshStats();
  setInterval(refreshStats, 30000);

  // a random daant every few minutes keeps the office authentic
  setInterval(() => {
    const busy = isLayerOpen('ide') || isLayerOpen('boss') || isLayerOpen('notes');
    if (!busy && document.visibilityState === 'visible' && Math.random() < 0.3) {
      openBoss();
    }
  }, 300000);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
