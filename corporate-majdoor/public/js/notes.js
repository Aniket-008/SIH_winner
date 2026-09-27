/**
 * Meeting Notes overlay: a full-screen desk you can scribble on, with
 * draggable + editable sticky notes. Ink and stickies persist per device.
 */
import { qs, store, toast, closeLayer } from './ui.js';
import { DEFAULT_STICKIES, STICKY_COLORS } from './data.js';

export class MeetingNotes {
  constructor() {
    this.overlay = qs('#notesOverlay');
    this.canvas = qs('#doodleCanvas');
    this.ctx = this.canvas.getContext('2d');
    this.layer = qs('#stickyLayer');
    this.color = store.get('inkColor', '#ffd166');
    this.drawing = false;
    this.stickies = store.get('stickies', null) || structuredClone(DEFAULT_STICKIES);
    this.saveTimer = 0;
  }

  init() {
    this.#buildSwatches();
    this.#bindCanvas();
    this.#bindToolbar();
    this.renderStickies();
    window.addEventListener('resize', () => this.resize(true));
  }

  /** Called every time the overlay opens (canvas has no size while hidden). */
  resize(preserve = false) {
    const snapshot = preserve ? this.canvas.toDataURL() : null;
    const ratio = window.devicePixelRatio || 1;
    this.canvas.width = Math.floor(window.innerWidth * ratio);
    this.canvas.height = Math.floor(window.innerHeight * ratio);
    this.ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    this.ctx.lineCap = 'round';
    this.ctx.lineJoin = 'round';
    this.ctx.lineWidth = 3.2;

    const source = snapshot || store.get('ink', null);
    if (source) {
      const img = new Image();
      img.onload = () => this.ctx.drawImage(img, 0, 0, window.innerWidth, window.innerHeight);
      img.src = source;
    }
  }

  #bindCanvas() {
    const pos = (event) => ({ x: event.clientX, y: event.clientY });

    this.canvas.addEventListener('pointerdown', (event) => {
      this.drawing = true;
      this.canvas.setPointerCapture(event.pointerId);
      const { x, y } = pos(event);
      this.ctx.strokeStyle = this.color;
      this.ctx.shadowColor = this.color;
      this.ctx.shadowBlur = 6;
      this.ctx.beginPath();
      this.ctx.moveTo(x, y);
    });

    this.canvas.addEventListener('pointermove', (event) => {
      if (!this.drawing) return;
      const { x, y } = pos(event);
      this.ctx.lineTo(x, y);
      this.ctx.stroke();
    });

    const end = () => {
      if (!this.drawing) return;
      this.drawing = false;
      this.#saveInk();
    };
    this.canvas.addEventListener('pointerup', end);
    this.canvas.addEventListener('pointerleave', end);
    this.canvas.addEventListener('pointercancel', end);
  }

  #saveInk() {
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => {
      try {
        store.set('ink', this.canvas.toDataURL('image/png'));
      } catch { /* quota */ }
    }, 500);
  }

  #buildSwatches() {
    const host = qs('#swatches');
    host.innerHTML = '';
    ['#ffd166', '#4cc9f0', '#ff5d73', '#caffbf', '#ffffff'].forEach((color) => {
      const dot = document.createElement('button');
      dot.type = 'button';
      dot.className = `swatch${color === this.color ? ' is-active' : ''}`;
      dot.style.background = color;
      dot.title = `Ink: ${color}`;
      dot.addEventListener('click', () => {
        this.color = color;
        store.set('inkColor', color);
        host.querySelectorAll('.swatch').forEach((s) => s.classList.remove('is-active'));
        dot.classList.add('is-active');
      });
      host.appendChild(dot);
    });
  }

  #bindToolbar() {
    qs('#eraseDoodle').addEventListener('click', () => {
      this.ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      store.remove('ink');
      toast('Whiteboard saaf. Manager khush. 🧽');
    });

    qs('#resetNotes').addEventListener('click', () => {
      this.stickies = structuredClone(DEFAULT_STICKIES);
      store.remove('stickies');
      store.remove('ink');
      this.ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      this.renderStickies();
      toast('Notes reset ho gaye ♻️');
    });

    qs('#addSticky').addEventListener('click', () => {
      const color = STICKY_COLORS[this.stickies.length % STICKY_COLORS.length];
      this.stickies.push({
        id: `s-${Date.now()}`,
        title: 'New note 📌',
        color,
        x: 60 + Math.random() * Math.max(80, window.innerWidth - 400),
        y: 60 + Math.random() * Math.max(80, window.innerHeight - 340),
        text: 'Type here…',
      });
      this.#persist();
      this.renderStickies();
    });
  }

  #persist() {
    store.set('stickies', this.stickies);
  }

  renderStickies() {
    this.layer.innerHTML = '';
    this.stickies.forEach((note) => this.layer.appendChild(this.#buildSticky(note)));
  }

  #buildSticky(note) {
    const el = document.createElement('div');
    el.className = 'sticky';
    el.style.background = note.color;
    el.style.left = `${note.x}px`;
    el.style.top = `${note.y}px`;

    const title = document.createElement('div');
    title.className = 'sticky__title';
    title.textContent = note.title;

    const del = document.createElement('button');
    del.className = 'sticky__del';
    del.type = 'button';
    del.textContent = '✕';
    del.title = 'Remove note';
    del.addEventListener('click', (event) => {
      event.stopPropagation();
      this.stickies = this.stickies.filter((n) => n.id !== note.id);
      this.#persist();
      this.renderStickies();
    });

    const body = document.createElement('div');
    body.className = 'sticky__body';
    body.textContent = note.text;

    el.append(title, del, body);

    // double-click / double-tap to edit
    el.addEventListener('dblclick', () => {
      body.contentEditable = 'true';
      el.setAttribute('contenteditable', 'true');
      body.focus();
      document.getSelection()?.selectAllChildren(body);
    });
    body.addEventListener('blur', () => {
      body.contentEditable = 'false';
      el.removeAttribute('contenteditable');
      note.text = body.textContent.trim();
      this.#persist();
    });

    // drag
    let offsetX = 0;
    let offsetY = 0;
    el.addEventListener('pointerdown', (event) => {
      if (body.contentEditable === 'true' || event.target === del) return;
      el.classList.add('is-dragging');
      el.setPointerCapture(event.pointerId);
      offsetX = event.clientX - el.offsetLeft;
      offsetY = event.clientY - el.offsetTop;
    });
    el.addEventListener('pointermove', (event) => {
      if (!el.classList.contains('is-dragging')) return;
      note.x = Math.max(0, Math.min(window.innerWidth - 120, event.clientX - offsetX));
      note.y = Math.max(0, Math.min(window.innerHeight - 120, event.clientY - offsetY));
      el.style.left = `${note.x}px`;
      el.style.top = `${note.y}px`;
    });
    const stop = () => {
      if (!el.classList.contains('is-dragging')) return;
      el.classList.remove('is-dragging');
      this.#persist();
    };
    el.addEventListener('pointerup', stop);
    el.addEventListener('pointercancel', stop);

    return el;
  }

  close() {
    closeLayer('notes');
  }
}

export default MeetingNotes;
