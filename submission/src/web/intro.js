/* Ecrã de boas-vindas (estilos em intro.css).
 *
 *  1. O candeeiro cai do topo; a corda estica e ele balança até parar.
 *  2. A luz acende e o texto de #intro é escrito à máquina.
 *  3. As palavras dentro de <mark> transformam-se em "*", um por palavra,
 *     como o programa faz aos documentos.
 *  4. O cursor passa a ser uma lupa; o vidro mostra a palavra original do
 *     "*" que estiver por baixo.
 *
 * Um clique ou uma tecla saltam a animação. O texto edita-se em index.html.
 */
(() => {
'use strict';

const intro = document.getElementById('intro');
if (!intro) return;

const stage = intro.querySelector('.intro-stage');
const lamp = intro.querySelector('.lamp');
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const canHover = matchMedia('(hover: hover) and (pointer: fine)').matches;

function span(className, text = '') {
  const s = document.createElement('span');
  s.className = className;
  s.textContent = text;
  return s;
}

/* =====================================================================
   Tempo: esperas que se podem saltar
   ===================================================================== */
let skipped = false;
let endLamp = null;
const waiting = new Set();

function sleep(ms) {
  if (skipped) return Promise.resolve();
  return new Promise(resolve => {
    const done = () => { clearTimeout(id); waiting.delete(done); resolve(); };
    const id = setTimeout(done, ms);
    waiting.add(done);
  });
}

// Leva tudo para o estado final de imediato.
function skip() {
  if (skipped) return;
  skipped = true;
  intro.classList.add('instant');
  if (endLamp) endLamp();
  for (const done of [...waiting]) done();
}

/* =====================================================================
   Candeeiro
   ===================================================================== */
const DROP = 0.38;     // segundos em queda livre, até a corda esticar
const STOP = 1.9;      // segundos até o candeeiro parar
const SWING = 20;      // amplitude inicial do balanço, em graus
const PERIOD = 0.72;   // segundos por balanço
const BOUNCE = 3.2;    // ressaltos da corda por segundo

const smooth = x => { const c = Math.min(Math.max(x, 0), 1); return c * c * (3 - 2 * c); };

// Onde está o candeeiro t segundos depois de ser largado.
// k: comprimento da corda (1 = em repouso). a: ângulo, em graus.
function lampAt(t) {
  let k;
  if (t < DROP) {
    k = (t / DROP) ** 2;
  } else {
    // A corda estica com a velocidade a que o candeeiro vinha (2 / DROP)
    // e ressalta até assentar.
    const u = t - DROP;
    const w = 2 * Math.PI * BOUNCE;
    k = 1 + (2 / DROP / w) * Math.exp(-5.5 * u) * Math.sin(w * u);
  }
  // O balanço perde força e é levado a zero nos últimos 0,7 s, para o
  // candeeiro parar mesmo em STOP.
  const strength = Math.exp(-1.25 * t) * (1 - smooth((t - STOP + 0.7) / 0.7));
  return { k, a: SWING * strength * Math.cos(2 * Math.PI * t / PERIOD) };
}

function dropLamp() {
  return new Promise(resolve => {
    let start = null;
    let raf = 0;

    endLamp = () => {
      endLamp = null;
      cancelAnimationFrame(raf);
      lamp.style.removeProperty('--k');
      lamp.style.removeProperty('--a');
      intro.classList.add('down');
      resolve();
    };
    if (skipped) return endLamp();

    const frame = now => {
      if (start === null) start = now;
      const t = (now - start) / 1000;
      if (t >= STOP) return endLamp();
      const { k, a } = lampAt(t);
      lamp.style.setProperty('--k', k.toFixed(4));
      lamp.style.setProperty('--a', `${a.toFixed(3)}deg`);
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
  });
}

/* =====================================================================
   Texto escrito à máquina
   ===================================================================== */
const caret = span('caret');
const rand = (min, max) => min + Math.random() * (max - min);

// Parte o texto de um elemento em letras, agrupadas por palavra. As palavras
// dentro de <mark> ficam em .cz, para serem censuradas.
function prepare(el, wobble) {
  const words = [[]];
  let marks = 0;
  (function walk(node, mark) {
    for (const child of node.childNodes) {
      if (child.nodeType === Node.ELEMENT_NODE) {
        walk(child, child.tagName === 'MARK' ? ++marks : mark);
      } else if (child.nodeType === Node.TEXT_NODE) {
        for (const c of child.textContent) {
          const last = words[words.length - 1];
          if (c.trim()) last.push({ c, mark });
          else if (last.length) words.push([]);
        }
      }
    }
  })(el, 0);

  const chars = [];              // letras, pela ordem em que são escritas
  const hidden = [];             // palavras a censurar
  const wordEnds = new Set();    // última letra de cada palavra
  const label = [];              // o texto final, para leitores de ecrã

  el.textContent = '';
  for (const word of words) {
    if (!word.length) continue;
    if (el.childNodes.length) el.append(' ');
    const wd = span('wd');
    let cz = null;
    let mark = 0;
    let text = '';
    for (const letter of word) {
      if (letter.mark !== mark) {
        mark = letter.mark;
        cz = null;
        if (mark) {
          cz = span('cz');
          cz.dataset.word = '';
          hidden.push(cz);
          wd.append(cz);
          text += '*';
        }
      }
      const ch = span('ch', letter.c);
      // As letras de uma máquina de escrever nunca caem todas direitas.
      if (wobble) ch.style.transform = `translateY(${rand(-0.014, 0.014).toFixed(3)}em) rotate(${rand(-0.9, 0.9).toFixed(2)}deg)`;
      if (cz) cz.dataset.word += letter.c; else text += letter.c;
      (cz || wd).append(ch);
      chars.push(ch);
    }
    wordEnds.add(chars[chars.length - 1]);
    label.push(text);
    el.append(wd);
  }
  el.setAttribute('aria-hidden', 'true');
  return { chars, hidden, wordEnds, label: label.join(' ') };
}

// O nome do site ainda pode mudar: se uma palavra do título for mais larga
// do que o ecrã, a letra encolhe até caber, em vez de partir a meio.
function fitTitle(el) {
  el.style.fontSize = '';
  const widths = [...el.querySelectorAll('.wd')].map(
    wd => [...wd.querySelectorAll('.ch, .cz-star')].reduce((sum, ch) => sum + ch.offsetWidth, 0));
  const widest = Math.max(0, ...widths);
  const style = getComputedStyle(el);
  const room = el.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
  if (widest > room) el.style.fontSize = `${Math.floor(parseFloat(style.fontSize) * room / widest)}px`;
}

async function type({ chars, wordEnds }, speed) {
  for (const ch of chars) {
    ch.classList.add('on');
    ch.after(caret);
    let ms = speed * rand(0.55, 1.45);
    if (/[.,;:!?]/.test(ch.textContent)) ms += speed * 4;   // respirar na pontuação
    else if (wordEnds.has(ch)) ms += speed * 1.2;          // a tecla do espaço
    await sleep(ms);
  }
}

async function censor(cz) {
  // A máquina bate um "*" por cima de cada letra...
  for (const ch of cz.children) {
    ch.textContent = '*';
    ch.classList.add('star');
    await sleep(32);
  }
  await sleep(160);

  // ...e a palavra encolhe para um só "*", como no documento anonimizado.
  const from = cz.getBoundingClientRect().width;
  const star = span('cz-star', '*');
  cz.replaceChildren(star);
  cz.classList.add('done');
  if (!skipped) {
    const to = star.getBoundingClientRect().width;
    cz.style.width = `${from}px`;
    cz.getBoundingClientRect();   // fixar a largura inicial antes de a animar
    cz.style.width = `${to}px`;
    await sleep(320);
  }
  cz.style.width = '';
}

/* =====================================================================
   Lupa
   ===================================================================== */
const SVG = 'http://www.w3.org/2000/svg';
const SCROLL_AWAY = 24;   // píxeis de scroll a partir dos quais a lupa desaparece
const MIN_WORD_PX = 13;   // tamanho mínimo da palavra revelada no vidro

function svgEl(tag, attrs) {
  const n = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
}

function buildLens() {
  const lens = document.createElement('div');
  lens.className = 'lens';
  lens.setAttribute('aria-hidden', 'true');

  const glass = document.createElement('div');
  glass.className = 'lens-glass';
  const word = span('lens-word');
  glass.append(word);

  const svg = svgEl('svg', { viewBox: '-100 -100 200 284' });
  svg.append(lupaRays());   // lupa.js
  lens.append(glass, svg);
  document.body.append(lens);
  return { lens, glass, word };
}

function setupLens(hidden) {
  const { lens, glass, word } = buildLens();
  const pointer = { x: 0, y: 0, known: false };
  let target = null;   // a palavra censurada que está debaixo do vidro

  function sync() {
    // A lupa só existe depois de o texto estar escrito e censurado, com o
    // rato em cima do ecrã de boas-vindas e antes de se fazer scroll; fora
    // disso, o cursor é o normal.
    const under = pointer.known && scrollY <= SCROLL_AWAY
      ? document.elementFromPoint(pointer.x, pointer.y) : null;
    const on = !!under && intro.contains(under) && intro.classList.contains('ready');
    lens.classList.toggle('on', on);
    intro.classList.toggle('has-lens', on);
    if (!on) return;

    const r = lens.offsetWidth / 2;
    lens.style.transform = `translate3d(${pointer.x - r}px, ${pointer.y - r}px, 0)`;

    // O "*" mais perto do centro do vidro, se houver algum lá dentro.
    let best = null;
    let reach = glass.offsetWidth * 0.36;
    let bx = 0;
    let by = 0;
    for (const cz of hidden) {
      if (!cz.classList.contains('done')) continue;
      const box = cz.getBoundingClientRect();
      const cx = box.left + box.width / 2;
      const cy = box.top + box.height / 2;
      const dist = Math.hypot(cx - pointer.x, cy - pointer.y);
      if (dist < reach) { best = cz; reach = dist; bx = cx; by = cy; }
    }

    lens.classList.toggle('decode', !!best);
    if (!best) { target = null; return; }
    if (best !== target) {
      target = best;
      word.textContent = best.dataset.word;
      const size = getComputedStyle(best).fontSize;
      word.style.fontSize = size;
      // Palavras mais largas do que o vidro encolhem até caberem, mas nunca
      // abaixo de um tamanho legível: as muito compridas leem-se a deslizar
      // a lupa por cima delas.
      const fit = glass.offsetWidth * 0.84 / word.offsetWidth;
      word.style.setProperty('--s', Math.min(1, Math.max(fit, MIN_WORD_PX / parseFloat(size))).toFixed(3));
    }
    // A palavra fica presa ao sítio do "*": é o vidro que lhe passa por cima.
    word.style.setProperty('--dx', `${(bx - pointer.x).toFixed(1)}px`);
    word.style.setProperty('--dy', `${(by - pointer.y).toFixed(1)}px`);
  }

  addEventListener('pointermove', e => {
    if (e.pointerType === 'touch') return;
    pointer.x = e.clientX;
    pointer.y = e.clientY;
    pointer.known = true;
    sync();
  }, { passive: true });
  addEventListener('scroll', sync, { passive: true });
  addEventListener('resize', sync);
  document.documentElement.addEventListener('pointerleave', () => { pointer.known = false; sync(); });
  // Ao sair da página inicial (data-phase), o ecrã de boas-vindas desaparece.
  new MutationObserver(sync).observe(document.body, { attributes: true, attributeFilter: ['data-phase'] });
  return sync;
}

// Sem rato não há lupa: um toque mostra ou volta a esconder a palavra.
function setupTouch() {
  intro.addEventListener('click', e => {
    const cz = e.target.closest('.cz.done');
    if (!cz) return;
    const open = cz.classList.toggle('peek');
    cz.firstChild.textContent = open ? cz.dataset.word : '*';
  });
}

/* =====================================================================
   Saída: o scroll desfaz a cena
   ===================================================================== */
// O palco fica preso ao ecrã durante --exit de scroll. Nesse percurso (p de 0
// a 1) o texto é apagado como com backspace, a luz apaga-se, o candeeiro sobe
// e a sala funde-se com a página. Voltar a subir refaz tudo.
function setupExit(blocks) {
  let last = -1;

  function apply() {
    if (!intro.classList.contains('ready')) return;
    // O percurso da saída (--exit); o resto do scroll do palco é a página
    // inicial a subir por cima dele.
    const room = intro.offsetHeight - stage.offsetHeight - innerHeight;
    const p = room > 0 ? Math.min(Math.max(scrollY / room, 0), 1) : 0;
    if (scrollY === last) return;
    last = scrollY;

    intro.classList.toggle('leaving', p > 0);
    intro.style.setProperty('--out', p.toFixed(4));
    intro.style.setProperty('--dim', smooth((p - 0.35) / 0.5).toFixed(4));
    intro.style.setProperty('--fade', smooth((p - 0.7) / 0.3).toFixed(4));
    // O candeeiro só sobe quando a luz já se apagou, enquanto a página
    // inicial entra: leva meio ecrã de scroll.
    const rise = Math.min(Math.max((scrollY - room * 0.85) / (innerHeight * 0.5), 0), 1);
    if (p > 0) lamp.style.setProperty('--k', (1 - rise * rise).toFixed(4));
    else lamp.style.removeProperty('--k');

    // Apagar do fim para o princípio: primeiro a frase, depois o título.
    const glyphs = blocks.flatMap(el => [...el.querySelectorAll('.ch, .cz-star')]);
    const keep = Math.round(glyphs.length * (1 - Math.min(p / 0.6, 1)));
    glyphs.forEach((g, i) => g.classList.toggle('gone', i >= keep));
    if (p === 0 || !glyphs.length) caret.remove();
    else if (keep > 0) glyphs[keep - 1].after(caret);
    else glyphs[0].before(caret);
  }

  addEventListener('scroll', () => {
    if (scrollY > 0) skip();   // quem faz scroll a meio não espera pela animação
    apply();
  }, { passive: true });
  addEventListener('resize', apply);
  return apply;
}

/* =====================================================================
   Sequência
   ===================================================================== */
async function play(title, line, hidden, onReady) {
  const onKey = e => { if (!e.metaKey && !e.ctrlKey && !e.altKey) skip(); };
  intro.addEventListener('pointerdown', skip);
  addEventListener('keydown', onKey);
  if (reduceMotion) skip();

  await sleep(300);              // um instante de sala às escuras
  await dropLamp();

  intro.classList.add('lit');
  if (!skipped) intro.classList.add('flicker');
  await sleep(420);              // a luz tremeluz antes de firmar

  await type(title, 64);
  await sleep(240);
  await type(line, 23);
  await sleep(480);
  caret.remove();

  const jobs = [];
  for (const cz of hidden) {     // as palavras são censuradas em cascata
    jobs.push(censor(cz));
    await sleep(190);
  }
  await Promise.all(jobs);

  intro.classList.add('ready');
  intro.classList.remove('flicker');
  intro.removeEventListener('pointerdown', skip);
  removeEventListener('keydown', onKey);
  for (const fn of onReady) fn();   // a saída por scroll e a lupa passam a valer
  // Depois de saltar, voltar a permitir as animações que ficam a correr.
  if (skipped) setTimeout(() => intro.classList.remove('instant'), 80);
}

// Se alguma coisa falhar, mostrar o ecrã já aceso e com o texto todo, em vez
// de deixar uma sala às escuras.
function showLit(error) {
  console.error(error);
  for (const ch of intro.querySelectorAll('.ch')) ch.classList.add('on');
  intro.classList.add('instant', 'down', 'lit', 'ready');
}

try {
  const titleEl = intro.querySelector('.intro-title');
  const lineEl = intro.querySelector('.intro-line');
  // O título e a frase existem nas duas línguas: a portuguesa no HTML, a
  // inglesa em data-en. i18n.js já definiu a língua quando isto corre.
  const both = el => ({ el, pt: el.innerHTML, en: el.dataset.en || el.innerHTML });
  const texts = [both(titleEl), both(lineEl)];
  const english = () => document.documentElement.lang === 'en';
  const localise = () => { for (const t of texts) t.el.innerHTML = english() ? t.en : t.pt; };
  if (english()) localise();
  const title = prepare(titleEl, true);
  const line = prepare(lineEl, false);
  const hidden = [...title.hidden, ...line.hidden];
  fitTitle(titleEl);
  addEventListener('resize', () => fitTitle(titleEl));

  intro.querySelector('.intro-copy').prepend(span('sr-only', `${title.label}. ${line.label}`));
  intro.querySelector('.intro-hint').textContent = canHover
    ? 'Passa a lupa por cima de um * para veres o que ficou escondido.'
    : 'Toca num * para veres o que ficou escondido.';
  intro.querySelector('.intro-cue').addEventListener('click', () => {
    scrollTo({ top: intro.offsetHeight - innerHeight, behavior: reduceMotion ? 'auto' : 'smooth' });
  });

  const onReady = [setupExit([titleEl, lineEl])];
  if (canHover) onReady.push(setupLens(hidden)); else setupTouch();
  const done = play(title, line, hidden, onReady).catch(showLit);

  // Ao trocar de língua, o texto é reescrito já no estado final (escrito e
  // censurado), sem repetir a animação.
  addEventListener('langchange', async () => {
    skip();
    await done;
    localise();
    const fresh = [prepare(titleEl, true), prepare(lineEl, false)];
    for (const part of fresh) part.chars.forEach(ch => ch.classList.add('on'));
    hidden.splice(0, Infinity, ...fresh.flatMap(part => part.hidden));
    fitTitle(titleEl);
    await Promise.all(hidden.map(censor));
    dispatchEvent(new Event('scroll'));   // repor o que a saída por scroll já tinha apagado
  });
} catch (error) {
  showLit(error);
}

})();
