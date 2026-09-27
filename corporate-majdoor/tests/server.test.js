import test from 'node:test';
import assert from 'node:assert/strict';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';

import { createApp, currentShift } from '../server/app.js';
import { ChatStore } from '../server/chat-store.js';
import { cleanMessage, cleanName, maskProfanity, RateLimiter } from '../server/moderation.js';

function listen(app) {
  return new Promise((resolve) => {
    const server = app.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      resolve({ server, base: `http://127.0.0.1:${port}` });
    });
  });
}

test('GET /api/playlist returns the rotation', async () => {
  const { server, base } = await listen(createApp({}));
  const res = await fetch(`${base}/api/playlist`);
  const body = await res.json();
  assert.equal(res.status, 200);
  assert.ok(body.count >= 5, 'playlist should have tracks');
  assert.ok(body.tracks.every((t) => t.id && t.title && t.credits));
  server.close();
});

test('GET /api/playlist?mood filters', async () => {
  const { server, base } = await listen(createApp({}));
  const body = await (await fetch(`${base}/api/playlist?mood=late-night`)).json();
  assert.ok(body.tracks.length > 0);
  assert.ok(body.tracks.every((t) => t.mood === 'late-night'));
  server.close();
});

test('GET /api/health reports uptime and shift', async () => {
  const { server, base } = await listen(createApp({ presence: { count: () => 3 } }));
  const body = await (await fetch(`${base}/api/health`)).json();
  assert.equal(body.ok, true);
  assert.equal(body.listeners, 3);
  assert.ok(body.shift.label);
  server.close();
});

test('unknown API routes 404 as JSON, pages fall back to the app shell', async () => {
  const { server, base } = await listen(createApp({}));
  const api = await fetch(`${base}/api/nope`);
  assert.equal(api.status, 404);
  assert.equal((await api.json()).error, 'Not found');

  const page = await fetch(`${base}/some/deep/link`);
  assert.equal(page.status, 404);
  assert.match(await page.text(), /Corporate Majdoor/);
  server.close();
});

test('static assets are served', async () => {
  const { server, base } = await listen(createApp({}));
  const res = await fetch(`${base}/css/styles.css`);
  assert.equal(res.status, 200);
  assert.match(res.headers.get('content-type'), /css/);
  server.close();
});

test('chat store trims and persists history', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cm-'));
  const store = new ChatStore({ dataDir: dir, limit: 3 });
  for (let i = 0; i < 5; i += 1) store.add({ name: 'Dev', text: `msg ${i}` });
  assert.equal(store.history().length, 3);
  assert.equal(store.history()[0].text, 'msg 2');
  store.flush();

  const reloaded = new ChatStore({ dataDir: dir, limit: 3 });
  assert.equal(reloaded.history().length, 3);
  assert.equal(reloaded.history().at(-1).text, 'msg 4');
  fs.rmSync(dir, { recursive: true, force: true });
});

test('moderation strips markup, masks abuse and rejects empties', () => {
  assert.equal(cleanMessage('<script>alert(1)</script>').value, 'scriptalert(1)/script');
  assert.equal(cleanMessage('   ').ok, false);
  assert.equal(cleanMessage('hiiiiiiiiiiii').value, 'hiiii');
  assert.match(maskProfanity('you chutiya'), /\*{3,}/);
  assert.equal(cleanName('admin').ok, false);
  assert.equal(cleanName('  Devashish  ').value, 'Devashish');
  assert.equal(cleanMessage('ab cd ef gh ij kl', { maxLength: 8 }).value, 'ab cd ef');
});

test('rate limiter allows a burst then throttles', () => {
  const limiter = new RateLimiter({ intervalMs: 1000, burst: 2 });
  const now = Date.now();
  assert.equal(limiter.take('s1', now).allowed, true);
  assert.equal(limiter.take('s1', now).allowed, true);
  const blocked = limiter.take('s1', now);
  assert.equal(blocked.allowed, false);
  assert.ok(blocked.waitMs > 0);
  // after a full interval a token is back
  assert.equal(limiter.take('s1', now + 1100).allowed, true);
});

test('currentShift always returns a labelled slot', () => {
  for (let h = 0; h < 24; h += 1) {
    const shift = currentShift(new Date(Date.UTC(2026, 0, 1, h, 0, 0)));
    assert.ok(shift.key && shift.label, `hour ${h}`);
  }
});
