/* O detetive da página inicial (estilos e poses em detective.css).
 *
 * Vive nos cantos inferiores da página inicial e desliza com ela no scroll.
 * Espreita pela lateral, entra, vai fazendo pequenos gestos com a lupa, sai
 * e reaparece no canto oposto.
 *
 * O estado vai em atributos data-* de .detective e não em classes, para os
 * nomes das poses não colidirem com classes do resto da página (.tip, por
 * exemplo, é a dica flutuante e tem opacity: 0):
 *
 *   data-side   "left" | "right"      de que lateral entra
 *   data-stage  "peek" | "up"         a espreitar ou em cena; ausente = fora
 *   data-pose   um nome de GESTURES   o gesto em curso; ausente = em repouso
 */
(() => {
'use strict';

const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const landing = document.getElementById('landing');
if (!landing) return;

const el = document.createElement('div');
el.className = 'detective';
el.setAttribute('aria-hidden', 'true');
// Desenho fixo (sem texto de fora). Como o ícone do modo incógnito: chapéu e
// óculos sobre um vazio preto, que vai da aba do chapéu ao fundo do pescoço
// e é fechado dos lados pela gola levantada da gabardina. O casaco continua
// para lá do fundo do desenho, para não se ver a bainha quando ele se
// inclina.
el.innerHTML = `<div class="det-flip"><svg viewBox="0 0 200 210">
  <path class="det-coat" d="M22 300v-90C24 172 40 150 74 140h52c34 10 50 32 52 70v90z"/>
  <path class="det-void" d="M66 64h68l3 22-37 76-37-76z"/>
  <path class="det-seam" d="M100 168v132"/>
  <circle class="det-button" cx="111" cy="186" r="3"/>
  <circle class="det-button" cx="111" cy="206" r="3"/>
  <circle class="det-button" cx="111" cy="226" r="3"/>
  <g class="det-head">
    <g class="det-glasses">
      <path class="det-frame" d="M97 93q3-3 6 0M76 92l-9-4M124 92l9-4"/>
      <circle cx="87" cy="95" r="11.5"/>
      <circle cx="113" cy="95" r="11.5"/>
    </g>
    <g class="det-eye-l"><g class="det-blink"><circle class="det-pupil" cx="87" cy="95" r="3.4"/></g></g>
    <g class="det-eye-r"><g class="det-blink"><circle class="det-pupil" cx="113" cy="95" r="3.4"/></g></g>
    <g class="det-hat">
      <path class="det-crown" d="M72 62 78.5 33q1.5-7 8.5-7h26q7 0 8.5 7L128 62z"/>
      <rect class="det-brim" x="40" y="60" width="120" height="11" rx="5.5"/>
    </g>
  </g>
  <path class="det-collar" d="M52 160 61 80l39 82z"/>
  <path class="det-collar" d="M148 160 139 80l-39 82z"/>
  <g class="det-arm">
    <path class="det-sleeve" d="M172 222 154 156"/>
    <circle class="det-glove" cx="152" cy="141" r="9"/>
    <g class="det-lupa" transform="translate(138 96) scale(.24)"></g>
    <circle class="det-glass" cx="138" cy="96" r="13.6"/>
  </g>
</svg></div>`;
el.querySelector('.det-lupa').append(lupaRays());   // lupa.js
landing.append(el);

/* ---------- Quando é que ele pode aparecer ---------- */
// Só na página inicial (na área de trabalho, #landing nem é mostrado).
const active = () => document.body.dataset.phase === 'landing';

// Uma espera que acaba mais cedo se se sair da página inicial (ou voltar).
let wake = null;
let was = active();
function sleep(ms) {
  return new Promise(resolve => {
    const done = () => { clearTimeout(id); if (wake === done) wake = null; resolve(); };
    const id = setTimeout(done, ms);
    wake = done;
  });
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));   // esta não acorda
function check() {
  const now = active();
  if (now !== was) { was = now; if (wake) wake(); }
}
new MutationObserver(check).observe(document.body, { attributes: true, attributeFilter: ['data-phase'] });

/* ---------- O que ele faz ---------- */
const rand = (min, max) => min + Math.random() * (max - min);
// [pose, duração em ms]; as poses repetidas saem mais vezes.
const GESTURES = [
  ['look-a', 1200], ['look-b', 1200], ['scan', 2800], ['scan', 2800],
  ['sweep', 3200], ['tilt', 1500], ['tip', 900],
];

// Um gesto nunca o tira do sítio: só sai do ecrã para trocar de canto.
async function gesture() {
  const [pose, ms] = GESTURES[Math.floor(Math.random() * GESTURES.length)];
  el.dataset.pose = pose;
  await sleep(ms);
  delete el.dataset.pose;
}

async function live() {
  let right = Math.random() < 0.5;
  for (;;) {
    while (!active()) await sleep(60000);
    await sleep(rand(900, 2200));
    if (!active()) continue;

    // Está fora do ecrã: muda de lado sem animação, para não o atravessar.
    el.style.transition = 'none';
    el.dataset.side = right ? 'right' : 'left';
    el.getBoundingClientRect();
    el.style.transition = '';

    if (reduceMotion) {                  // sem movimento: fica só ali, quieto
      el.dataset.stage = 'up';
      while (active()) await sleep(60000);
      delete el.dataset.stage;
      continue;
    }

    el.dataset.stage = 'peek';           // primeiro espreita, depois entra
    await sleep(1200);
    if (active()) {
      el.dataset.stage = 'up';
      for (let n = 6 + Math.floor(rand(0, 5)); n > 0 && active(); n--) {
        await sleep(rand(800, 2000));
        if (active()) await gesture();
      }
    }

    delete el.dataset.pose;
    delete el.dataset.stage;
    await pause(1300);                   // o tempo de sair
    right = !right;                      // da próxima vez, no outro canto
    if (active()) await sleep(rand(3500, 8000));
  }
}

live();

})();
