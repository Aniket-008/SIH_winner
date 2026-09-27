/** Small DOM + state helpers shared by every module. */

export const qs = (sel, root = document) => root.querySelector(sel);
export const qsa = (sel, root = document) => [...root.querySelectorAll(sel)];

export const store = {
  get(key, fallback = null) {
    try {
      const raw = localStorage.getItem(`cm:${key}`);
      return raw === null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(`cm:${key}`, JSON.stringify(value));
    } catch {
      /* private mode / quota — ignore */
    }
  },
  remove(key) {
    try {
      localStorage.removeItem(`cm:${key}`);
    } catch {
      /* ignore */
    }
  },
};

let toastTimer = 0;
export function toast(message, ms = 2600) {
  const host = qs('#toasts');
  if (!host) return;
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = message;
  host.appendChild(el);
  clearTimeout(toastTimer);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transition = 'opacity .3s';
    setTimeout(() => el.remove(), 320);
  }, ms);
}

/** Registry of every dismissible layer, so ESC can close the top-most one. */
const layers = new Map();

export function registerLayer(name, { el, openClass = 'is-open', onOpen, onClose } = {}) {
  layers.set(name, { el, openClass, onOpen, onClose, open: false });
}

export function openLayer(name) {
  const layer = layers.get(name);
  if (!layer) return;
  layer.el.classList.add(layer.openClass);
  layer.el.setAttribute('aria-hidden', 'false');
  layer.open = true;
  layer.onOpen?.();
}

export function closeLayer(name) {
  const layer = layers.get(name);
  if (!layer) return;
  layer.el.classList.remove(layer.openClass);
  layer.el.setAttribute('aria-hidden', 'true');
  layer.open = false;
  layer.onClose?.();
}

export function toggleLayer(name) {
  const layer = layers.get(name);
  if (!layer) return;
  layer.open ? closeLayer(name) : openLayer(name);
}

export function isLayerOpen(name) {
  return Boolean(layers.get(name)?.open);
}

export function closeTopLayer() {
  const openOnes = [...layers.entries()].filter(([, l]) => l.open);
  if (!openOnes.length) return false;
  closeLayer(openOnes[openOnes.length - 1][0]);
  return true;
}

export function closeAllLayers() {
  layers.forEach((_, name) => closeLayer(name));
}

export const pick = (list) => list[Math.floor(Math.random() * list.length)];

export function formatTime(seconds = 0) {
  if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

export function clockLabel(iso) {
  const date = iso ? new Date(iso) : new Date();
  return date
    .toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    .toLowerCase();
}
