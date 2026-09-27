import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

/**
 * A tiny append-and-trim chat store backed by a JSON file.
 * Deliberately dependency free - the room only ever keeps the last N messages,
 * so a flat file is faster (and easier to inspect) than a database here.
 */
export class ChatStore {
  constructor({ dataDir, file = 'messages.json', limit = 200, persist = true }) {
    this.limit = limit;
    this.persist = persist;
    this.file = path.resolve(dataDir, file);
    this.messages = [];
    this.writeQueued = false;

    if (this.persist) {
      this.#load();
    }
  }

  #load() {
    try {
      fs.mkdirSync(path.dirname(this.file), { recursive: true });
      if (fs.existsSync(this.file)) {
        const parsed = JSON.parse(fs.readFileSync(this.file, 'utf8'));
        if (Array.isArray(parsed)) {
          this.messages = parsed.slice(-this.limit);
        }
      }
    } catch (error) {
      console.warn('[chat-store] could not read history:', error.message);
      this.messages = [];
    }
  }

  #scheduleWrite() {
    if (!this.persist || this.writeQueued) return;
    this.writeQueued = true;
    // Debounce: chat bursts should not trigger a write per message.
    setTimeout(() => {
      this.writeQueued = false;
      try {
        fs.mkdirSync(path.dirname(this.file), { recursive: true });
        fs.writeFileSync(this.file, JSON.stringify(this.messages, null, 2));
      } catch (error) {
        console.warn('[chat-store] could not persist history:', error.message);
      }
    }, 400).unref?.();
  }

  add({ name, text, kind = 'user' }) {
    const message = {
      id: randomUUID(),
      name,
      text,
      kind,
      at: new Date().toISOString(),
    };
    this.messages.push(message);
    if (this.messages.length > this.limit) {
      this.messages = this.messages.slice(-this.limit);
    }
    this.#scheduleWrite();
    return message;
  }

  history(limit = this.limit) {
    return this.messages.slice(-limit);
  }

  flush() {
    if (!this.persist) return;
    try {
      fs.mkdirSync(path.dirname(this.file), { recursive: true });
      fs.writeFileSync(this.file, JSON.stringify(this.messages, null, 2));
    } catch (error) {
      console.warn('[chat-store] flush failed:', error.message);
    }
  }
}

export default ChatStore;
