/** Window rain on the background glass + floating chai banter. */
import { qs, pick } from './ui.js';
import { CHAI_QUOTES } from './data.js';

export function initRain() {
  const canvas = qs('#rainCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let drops = [];
  let raf = 0;

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const count = Math.min(160, Math.round(window.innerWidth / 9));
    drops = Array.from({ length: count }, () => spawn());
  }

  function spawn() {
    return {
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      len: 8 + Math.random() * 18,
      speed: 3 + Math.random() * 6,
      drift: -0.6 + Math.random() * 0.4,
      alpha: 0.08 + Math.random() * 0.22,
    };
  }

  function frame() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.lineWidth = 1.1;
    drops.forEach((drop) => {
      ctx.strokeStyle = `rgba(190, 215, 255, ${drop.alpha})`;
      ctx.beginPath();
      ctx.moveTo(drop.x, drop.y);
      ctx.lineTo(drop.x + drop.drift * 3, drop.y + drop.len);
      ctx.stroke();
      drop.y += drop.speed;
      drop.x += drop.drift;
      if (drop.y > canvas.height) Object.assign(drop, spawn(), { y: -20 });
    });
    raf = requestAnimationFrame(frame);
  }

  resize();
  window.addEventListener('resize', resize);
  if (!reduced) frame();

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) cancelAnimationFrame(raf);
    else if (!reduced) frame();
  });
}

/** Rotating chai/office one-liners near the steam. */
export function initChaiBanter() {
  const host = document.createElement('div');
  host.style.cssText =
    'position:fixed;left:6%;bottom:22%;max-width:260px;z-index:-1;color:rgba(255,255,255,.45);' +
    'font-size:13px;font-style:italic;transition:opacity .6s;pointer-events:none;';
  document.body.appendChild(host);

  const rotate = () => {
    host.style.opacity = '0';
    setTimeout(() => {
      host.textContent = `💬 "${pick(CHAI_QUOTES)}"`;
      host.style.opacity = '1';
    }, 600);
  };
  rotate();
  setInterval(rotate, 11000);
}

/** Red alert flash used when someone in the room yells "Boss aaya!". */
export function flashAlarm() {
  const el = qs('#alarmFlash');
  if (!el) return;
  el.classList.remove('is-on');
  void el.offsetWidth;
  el.classList.add('is-on');
  setTimeout(() => el.classList.remove('is-on'), 1600);
}
