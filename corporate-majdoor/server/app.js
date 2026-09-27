import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';

import playlist from './playlist.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.resolve(__dirname, '..', 'public');

/**
 * Builds the express app. Kept separate from the http/socket bootstrap so the
 * test-suite can mount it without opening a port.
 */
export function createApp({ store, presence } = {}) {
  const app = express();

  app.disable('x-powered-by');
  app.use(express.json({ limit: '16kb' }));

  // The live preview runs behind a proxy; trust it for correct client IPs.
  app.set('trust proxy', true);

  app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
    next();
  });

  app.get('/api/health', (req, res) => {
    res.json({
      ok: true,
      service: 'corporate-majdoor',
      uptimeSeconds: Math.round(process.uptime()),
      listeners: presence?.count?.() ?? 0,
      shift: currentShift(),
    });
  });

  app.get('/api/playlist', (req, res) => {
    const mood = req.query.mood;
    const tracks = mood ? playlist.filter((t) => t.mood === mood) : playlist;
    res.json({ count: tracks.length, tracks });
  });

  app.get('/api/chat/messages', (req, res) => {
    const limit = Math.min(Number(req.query.limit) || 80, 200);
    res.json({ messages: store ? store.history(limit) : [] });
  });

  app.get('/api/stats', (req, res) => {
    res.json({
      listeners: presence?.count?.() ?? 0,
      messages: store ? store.history().length : 0,
      shift: currentShift(),
      serverTime: new Date().toISOString(),
    });
  });

  app.use(
    express.static(publicDir, {
      extensions: ['html'],
      setHeaders(res, filePath) {
        if (/\.(jpg|jpeg|png|svg|webp|ico|mp3)$/i.test(filePath)) {
          res.setHeader('Cache-Control', 'public, max-age=86400');
        } else {
          res.setHeader('Cache-Control', 'no-cache');
        }
      },
    })
  );

  app.use((req, res) => {
    if (req.path.startsWith('/api/')) {
      return res.status(404).json({ error: 'Not found' });
    }
    return res.status(404).sendFile(path.join(publicDir, 'index.html'));
  });

  return app;
}

/** Playful IST-based "which part of the shift are we in" helper. */
export function currentShift(date = new Date()) {
  const istHour = Number(
    new Intl.DateTimeFormat('en-GB', {
      hour: 'numeric',
      hour12: false,
      timeZone: 'Asia/Kolkata',
    }).format(date)
  );

  if (istHour >= 9 && istHour < 12) return { key: 'morning', label: 'Morning standup grind ☕' };
  if (istHour >= 12 && istHour < 14) return { key: 'lunch', label: 'Lunch + 20 min nap 🍱' };
  if (istHour >= 14 && istHour < 17) return { key: 'deep-work', label: 'Deep work / debugging 🧠' };
  if (istHour >= 17 && istHour < 19) return { key: 'chai', label: '5 PM tapri chai break 🫖' };
  if (istHour >= 19 && istHour < 24) return { key: 'overtime', label: 'Unpaid overtime mode 🌙' };
  return { key: 'night-deploy', label: 'Production deploy window 🚀' };
}

export default createApp;
