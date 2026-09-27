/** "Boss Ki Daant" — random manager escalation generator with a speech line. */
import { qs, pick, openLayer, toast } from './ui.js';
import { BOSS_LINES, BOSS_REPLIES } from './data.js';

let last = -1;

function speak(text) {
  try {
    if (!('speechSynthesis' in window)) return;
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = 'hi-IN';
    utter.rate = 1.08;
    utter.pitch = 0.8;
    utter.volume = 0.9;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  } catch { /* speech not available */ }
}

export function nextDaant({ withVoice = false } = {}) {
  let index = Math.floor(Math.random() * BOSS_LINES.length);
  if (index === last) index = (index + 1) % BOSS_LINES.length;
  last = index;

  const line = BOSS_LINES[index];
  qs('#bossFace').textContent = line.face;
  qs('#bossLine').textContent = line.sub ? `${line.text}\n${line.sub}` : line.text;
  qs('#bossReply').textContent = pick(BOSS_REPLIES);

  const box = qs('.modal__box--boss');
  box.style.animation = 'none';
  void box.offsetWidth;
  box.style.animation = '';

  if (withVoice) speak(line.text);
}

export function initBoss() {
  qs('#nextDaant').addEventListener('click', () => nextDaant({ withVoice: true }));
  qs('#bossSorry').addEventListener('click', () => {
    toast(pick([
      'Boss: "Sorry se kaam nahi hota."',
      'Boss: "Theek hai, but EOD tak chahiye."',
      'Boss: "Ye last time hai." (it is never the last time)',
      'Boss ne 👍 react kiya. Matlab abhi bhi gussa hai.',
    ]));
  });
}

export function openBoss() {
  nextDaant();
  openLayer('boss');
}
