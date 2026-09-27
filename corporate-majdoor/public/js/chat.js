/**
 * Live chat room. Talks to the socket.io server mounted by server/index.js.
 * If the socket is unavailable (static hosting / offline), the drawer keeps
 * working in a local-only "notepad" mode so nothing feels broken.
 */
import { qs, store, toast, clockLabel, openLayer, closeLayer, isLayerOpen } from './ui.js';

export class LiveChat extends EventTarget {
  constructor() {
    super();
    this.list = qs('#chatList');
    this.form = qs('#chatForm');
    this.input = qs('#chatInput');
    this.presenceEl = qs('#chatPresence');
    this.typingEl = qs('#chatTyping');
    this.whoami = qs('#chatWhoami');
    this.badge = qs('#chatBadge');

    this.name = store.get('name', '');
    this.socket = null;
    this.online = false;
    this.unread = 0;
    this.pending = null;
    this.typingTimeout = 0;
    this.lastTypingSent = 0;
  }

  emit(type, detail) {
    this.dispatchEvent(new CustomEvent(type, { detail }));
  }

  connect() {
    this.#renderWhoami();
    this.#renderBadge();
    this.#bindForm();
    this.#bindNameModal();

    if (window.__noSocket || typeof window.io !== 'function') {
      this.#offlineMode('Chat server offline — messages stay on this device.');
      return;
    }

    this.socket = window.io({ transports: ['websocket', 'polling'], reconnectionDelayMax: 8000 });

    this.socket.on('connect', () => {
      this.online = true;
      this.#setPresence('connected');
      if (this.name) this.socket.emit('chat:join', { name: this.name });
    });

    this.socket.on('disconnect', () => {
      this.online = false;
      this.#setPresence('reconnecting…');
    });

    this.socket.on('connect_error', () => {
      if (!this.online) this.#offlineMode('Chat server offline — messages stay on this device.');
    });

    this.socket.on('chat:history', ({ messages = [] }) => {
      this.list.innerHTML = '';
      messages.forEach((m) => this.#render(m, false));
      this.#scroll();
    });

    this.socket.on('chat:message', (message) => {
      this.#render(message);
      if (!isLayerOpen('chat') && message.kind !== 'system') {
        this.unread += 1;
        this.#renderBadge();
      }
    });

    this.socket.on('presence', ({ listeners }) => {
      this.emit('presence', { listeners });
      this.#setPresence(`${listeners} majdoor${listeners === 1 ? '' : 's'} in the room`);
    });

    this.socket.on('chat:typing', ({ name }) => {
      this.typingEl.textContent = `${name} is typing…`;
      clearTimeout(this.typingTimeout);
      this.typingTimeout = setTimeout(() => {
        this.typingEl.textContent = '';
      }, 1800);
    });

    this.socket.on('room:alarm', ({ from }) => {
      this.emit('alarm', { from });
    });
  }

  #offlineMode(reason) {
    this.online = false;
    this.#setPresence('offline mode');
    const local = store.get('offlineChat', []);
    this.list.innerHTML = '';
    if (!local.length) {
      this.#render(
        { name: 'System', text: reason, kind: 'system', at: new Date().toISOString() },
        false
      );
    }
    local.forEach((m) => this.#render(m, false));
    this.#scroll();
  }

  #bindForm() {
    this.form.addEventListener('submit', (event) => {
      event.preventDefault();
      const text = this.input.value.trim();
      if (!text) return;
      if (!this.name) {
        this.pending = text;
        qs('#namePreview').textContent = `We'll send "${text.slice(0, 60)}" as soon as you enter it.`;
        openLayer('name');
        setTimeout(() => qs('#nameInput').focus(), 80);
        return;
      }
      this.send(text);
    });

    this.input.addEventListener('input', () => {
      const now = Date.now();
      if (this.online && this.name && now - this.lastTypingSent > 1200) {
        this.lastTypingSent = now;
        this.socket?.emit('chat:typing');
      }
    });
  }

  #bindNameModal() {
    qs('#nameForm').addEventListener('submit', (event) => {
      event.preventDefault();
      const value = qs('#nameInput').value.trim();
      if (!value) return;
      this.setName(value);
      closeLayer('name');
      if (this.pending) {
        this.send(this.pending);
        this.pending = null;
      }
    });

    qs('#changeName').addEventListener('click', () => {
      qs('#nameInput').value = this.name;
      qs('#namePreview').textContent = 'Pick the name the room will see.';
      openLayer('name');
      setTimeout(() => qs('#nameInput').focus(), 80);
    });
  }

  setName(name) {
    this.name = name.slice(0, 24);
    store.set('name', this.name);
    this.#renderWhoami();
    if (this.online) this.socket.emit('chat:join', { name: this.name });
  }

  send(text) {
    const payload = { name: this.name, text };
    if (this.online) {
      this.socket.emit('chat:message', payload, (response = {}) => {
        if (!response.ok) toast(response.error || 'Message nahi gaya, dobara try karo.');
      });
    } else {
      const message = { ...payload, kind: 'user', at: new Date().toISOString(), id: `local-${Date.now()}` };
      const local = store.get('offlineChat', []);
      local.push(message);
      store.set('offlineChat', local.slice(-60));
      this.#render(message);
    }
    this.input.value = '';
  }

  #render(message, animate = true) {
    const el = document.createElement('div');
    const mine = message.name === this.name && message.kind !== 'system';
    el.className = `msg${mine ? ' is-mine' : ''}${message.kind === 'system' ? ' is-system' : ''}`;
    if (!animate) el.style.animation = 'none';

    if (message.kind === 'system') {
      el.innerHTML = '<div class="msg__text"></div>';
      el.querySelector('.msg__text').textContent = message.text;
    } else {
      el.innerHTML = `
        <div class="msg__head">
          <span class="msg__name"></span>
          <span class="msg__time"></span>
        </div>
        <div class="msg__text"></div>`;
      el.querySelector('.msg__name').textContent = message.name;
      el.querySelector('.msg__time').textContent = clockLabel(message.at);
      el.querySelector('.msg__text').textContent = message.text;
    }

    this.list.appendChild(el);
    while (this.list.children.length > 250) this.list.removeChild(this.list.firstChild);
    this.#scroll();
  }

  #scroll() {
    requestAnimationFrame(() => {
      this.list.scrollTop = this.list.scrollHeight;
    });
  }

  #setPresence(text) {
    this.presenceEl.textContent = text;
  }

  #renderWhoami() {
    this.whoami.textContent = this.name || 'Anonymous Majdoor';
  }

  #renderBadge() {
    this.badge.textContent = String(this.unread);
    this.badge.style.display = this.unread ? '' : 'none';
  }

  markRead() {
    this.unread = 0;
    this.#renderBadge();
  }

  raiseAlarm() {
    if (this.online) this.socket.emit('room:alarm');
  }
}

export default LiveChat;
