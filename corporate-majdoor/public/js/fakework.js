/**
 * "Boss Aaya!" panic mode — a convincing full-screen IDE that types a
 * critical hotfix by itself while a build log scrolls underneath.
 */
import { qs, openLayer, closeLayer, pick } from './ui.js';
import { FAKE_CODE, TERMINAL_LINES, JIRA_TICKETS, FAKE_FILES } from './data.js';

const KEYWORDS = /\b(package|import|public|private|final|volatile|synchronized|class|implements|void|boolean|for|if|return|new|this)\b/g;
const TYPES = /\b(PaymentGatewayService|HighPriorityService|ClientSyncOrchestrator|ChaiBreakScheduler|ExecutionContext|Transaction|AppraisalDenialStrategy|String)\b/g;

function highlight(source) {
  return source
    .replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]))
    .replace(/(\/\*[\s\S]*?\*\/|\/\/.*)/g, '<span class="cm">$1</span>')
    .replace(/"([^"\\]|\\.)*"/g, '<span class="str">$&</span>')
    .replace(KEYWORDS, '<span class="kw">$&</span>')
    .replace(TYPES, '<span class="typ">$&</span>')
    .replace(/\b([a-zA-Z_][\w]*)\(/g, '<span class="fn">$1</span>(');
}

export class FakeWork {
  constructor({ onEnter, onExit } = {}) {
    this.el = qs('#ideOverlay');
    this.codeEl = qs('#ideCode');
    this.terminalEl = qs('#ideTerminal');
    this.jiraEl = qs('#ideJira');
    this.fileEl = qs('#ideFile');
    this.coverageEl = qs('#ideCoverage');
    this.onEnter = onEnter;
    this.onExit = onExit;
    this.timers = [];
  }

  init() {
    this.jiraEl.innerHTML = JIRA_TICKETS.map((t) => `<li>${t}</li>`).join('');
  }

  #clearTimers() {
    this.timers.forEach(clearTimeout);
    this.timers.splice(0);
  }

  #schedule(fn, ms) {
    const id = setTimeout(fn, ms);
    this.timers.push(id);
    return id;
  }

  enter() {
    openLayer('ide');
    this.onEnter?.();
    this.fileEl.textContent = pick(FAKE_FILES);
    this.coverageEl.textContent = (95 + Math.random() * 4.5).toFixed(1);
    this.#typeCode();
    this.#runTerminal();
  }

  exit() {
    this.#clearTimers();
    closeLayer('ide');
    this.onExit?.();
  }

  #typeCode() {
    this.codeEl.textContent = '';
    let index = 0;
    const type = () => {
      // burst a few characters per frame so it looks like frantic typing
      const burst = 2 + Math.floor(Math.random() * 5);
      index = Math.min(FAKE_CODE.length, index + burst);
      this.codeEl.textContent = FAKE_CODE.slice(0, index);
      this.codeEl.parentElement.scrollTop = this.codeEl.parentElement.scrollHeight;
      if (index < FAKE_CODE.length) {
        this.#schedule(type, 18 + Math.random() * 45);
      } else {
        this.codeEl.innerHTML = highlight(FAKE_CODE);
        this.#schedule(() => this.#typeCode(), 9000);
      }
    };
    type();
  }

  #runTerminal() {
    this.terminalEl.innerHTML = '';
    let i = 0;
    const step = () => {
      const line = TERMINAL_LINES[i % TERMINAL_LINES.length];
      const row = document.createElement('div');
      row.className = line.cls;
      row.textContent = line.text;
      this.terminalEl.appendChild(row);
      this.terminalEl.scrollTop = this.terminalEl.scrollHeight;
      while (this.terminalEl.children.length > 40) {
        this.terminalEl.removeChild(this.terminalEl.firstChild);
      }
      i += 1;
      this.#schedule(step, 700 + Math.random() * 1200);
    };
    step();
  }
}

export default FakeWork;
