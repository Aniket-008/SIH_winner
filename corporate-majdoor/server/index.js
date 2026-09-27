import http from 'node:http';
import { Server as SocketServer } from 'socket.io';

import config from './config.js';
import { createApp } from './app.js';
import { ChatStore } from './chat-store.js';
import { cleanMessage, cleanName, RateLimiter } from './moderation.js';

const store = new ChatStore({
  dataDir: config.dataDir,
  limit: config.chat.historyLimit,
  persist: config.persistChat,
});

const presence = {
  sockets: new Map(),
  count() {
    return this.sockets.size;
  },
  names() {
    return [...new Set([...this.sockets.values()].map((s) => s.name).filter(Boolean))];
  },
};

const app = createApp({ store, presence });
const server = http.createServer(app);

const io = new SocketServer(server, {
  // The preview/proxy host is unknown at build time, so allow any origin but
  // keep the surface tiny: the socket only ever carries chat text.
  cors: { origin: true, methods: ['GET', 'POST'] },
  maxHttpBufferSize: 1e5,
  pingInterval: 20000,
});

const limiter = new RateLimiter(config.chat.rateLimit);

function broadcastPresence() {
  io.emit('presence', { listeners: presence.count(), names: presence.names().slice(-30) });
}

io.on('connection', (socket) => {
  presence.sockets.set(socket.id, { name: null, joinedAt: Date.now() });

  socket.emit('chat:history', { messages: store.history(80) });
  broadcastPresence();

  socket.on('chat:join', (payload = {}, ack) => {
    const result = cleanName(payload.name, { maxLength: config.chat.maxNameLength });
    if (!result.ok) {
      ack?.({ ok: false, error: result.reason });
      return;
    }
    const entry = presence.sockets.get(socket.id);
    const firstJoin = entry && !entry.name;
    if (entry) entry.name = result.value;

    ack?.({ ok: true, name: result.value });

    if (firstJoin) {
      const message = store.add({
        name: result.value,
        text: `${result.value} ne office join kiya 👋`,
        kind: 'system',
      });
      io.emit('chat:message', message);
    }
    broadcastPresence();
  });

  socket.on('chat:message', (payload = {}, ack) => {
    const entry = presence.sockets.get(socket.id);
    const nameResult = cleanName(payload.name || entry?.name, {
      maxLength: config.chat.maxNameLength,
    });
    if (!nameResult.ok) {
      ack?.({ ok: false, error: nameResult.reason, needsName: true });
      return;
    }

    const textResult = cleanMessage(payload.text, { maxLength: config.chat.maxMessageLength });
    if (!textResult.ok) {
      ack?.({ ok: false, error: textResult.reason });
      return;
    }

    const gate = limiter.take(socket.id);
    if (!gate.allowed) {
      ack?.({
        ok: false,
        error: `Thoda slow bhai - ${Math.ceil(gate.waitMs / 1000)}s baad try karo.`,
      });
      return;
    }

    if (entry) entry.name = nameResult.value;
    const message = store.add({ name: nameResult.value, text: textResult.value });
    io.emit('chat:message', message);
    ack?.({ ok: true, id: message.id });
    broadcastPresence();
  });

  socket.on('chat:typing', () => {
    const entry = presence.sockets.get(socket.id);
    if (!entry?.name) return;
    socket.broadcast.emit('chat:typing', { name: entry.name });
  });

  // Ephemeral fun: someone hitting "Boss Aaya!" warns everyone in the room.
  socket.on('room:alarm', () => {
    const entry = presence.sockets.get(socket.id);
    socket.broadcast.emit('room:alarm', { from: entry?.name || 'Koi Majdoor' });
  });

  socket.on('disconnect', () => {
    presence.sockets.delete(socket.id);
    limiter.forget(socket.id);
    broadcastPresence();
  });
});

server.listen(config.port, config.host, () => {
  console.log(`\n  🏢 Corporate Majdoor radio running on http://${config.host}:${config.port}`);
  console.log(`  💬 live chat: socket.io  •  history: ${store.history().length} messages\n`);
});

function shutdown(signal) {
  console.log(`\n[${signal}] closing shift, saving chat...`);
  store.flush();
  io.close();
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 3000).unref();
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
