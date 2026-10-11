/* Português / Inglês.
 *
 * A página está escrita em português. Em inglês, este ficheiro troca o texto
 * que aparece no ecrã, nó a nó: frases fixas pela tabela EXACT, frases com
 * números ou nomes pelas regras de RULES. Um MutationObserver apanha também
 * o que os outros scripts forem escrevendo, por isso eles não precisam de
 * saber em que língua se está.
 *
 * Fica por traduzir o que é conteúdo e não interface: os documentos
 * carregados, as categorias que o Gemini devolve e as mensagens de erro do
 * servidor. A frase do ecrã de boas-vindas e o lema da página inicial são
 * trocados por quem os escreve letra a letra (intro.js e index.html), que
 * ouvem o evento "langchange".
 */
(() => {
'use strict';

const EXACT = {
  // cabeçalho e rodapé
  'Sobre nós': 'About us',
  'A ligar ao servidor…': 'Connecting to the server…',
  'Servidor ligado · falta GEMINI_API_KEY': 'Server on · GEMINI_API_KEY missing',
  'Modo demonstração · servidor desligado': 'Demo mode · server off',
  'Para analisar PDFs próprios: python submission/src/server.py': 'To analyse your own PDFs: python submission/src/server.py',
  'Alternar entre tema claro e escuro': 'Switch between light and dark theme',
  'Mudar para inglês': 'Switch to Portuguese',
  'Repositório no GitHub': 'GitHub repository',
  'Início': 'Home',
  'Fechar': 'Close',
  'NOS Gen-AI Hackathon · projeto open-source': 'NOS Gen-AI Hackathon · open-source project',
  'Dados sensíveis detetados por IA podem conter erros: revê sempre o resultado antes de partilhar.': 'Sensitive data detected by AI may contain mistakes: always review the result before sharing.',
  // ecrã de boas-vindas
  'Boas-vindas': 'Welcome',
  'Desliza para começar': 'Scroll to start',
  'Passa a lupa por cima de um * para veres o que ficou escondido.': 'Move the magnifier over a * to see what was hidden.',
  'Toca num * para veres o que ficou escondido.': 'Tap a * to see what was hidden.',
  // página inicial: o bloco de notas de exemplo
  'Relatório de Admissão': 'Admission Report',
  'Paciente:': 'Patient:',
  'anos': 'years old',
  'Diagnóstico:': 'Diagnosis:',
  'HIV positivo': 'HIV positive',
  'desde 2018': 'since 2018',
  'NIF:': 'Tax no.:',
  'Cartão:': 'Card:',
  'Altura': 'Height',
  '· Peso': '· Weight',
  // página inicial
  'Carrega um PDF e escolhe o que fica escondido.': 'Upload a PDF and choose what stays hidden.',
  'Carregar ficheiros PDF ou um ZIP': 'Upload PDF files or a ZIP',
  'Larga aqui os teus PDF': 'Drop your PDFs here',
  'um, vários ou um ZIP · ou clica para escolher': 'one, several or a ZIP · or click to choose',
  'Experimentar com um exemplo →': 'Try it with an example →',
  'Até 25 MB · o texto é analisado pelo Gemini': 'Up to 25 MB · the text is analysed by Gemini',
  // área de trabalho
  'Novo documento': 'New document',
  'Relatório': 'Report',
  'PDF anonimizado': 'Anonymised PDF',
  'A gerar…': 'Generating…',
  '+ Adicionar': '+ Add',
  'Descarregar tudo (.zip)': 'Download all (.zip)',
  'Exemplo': 'Example',
  'Documento': 'Document',
  'Vista do documento': 'Document view',
  'Anonimizado': 'Anonymised',
  'Clica numa palavra para a esconder ou mostrar.': 'Click a word to hide or show it.',
  'Pré-visualização do resultado. Clica num * para voltar a mostrar.': 'Preview of the result. Click a * to show the word again.',
  'O PDF tal como vai ser exportado. Para alterar, volta ao Original.': 'The PDF exactly as it will be exported. To change it, go back to Original.',
  'O que esconder': 'What to hide',
  'Tudo': 'All',
  'Nada': 'None',
  'Filtrar palavras ou categorias…': 'Filter words or categories…',
  'Filtrar palavras ou categorias': 'Filter words or categories',
  'a aguardar análise…': 'waiting for the analysis…',
  'O modelo não encontrou dados sensíveis neste documento.': 'The model found no sensitive data in this document.',
  'Dados pessoais': 'Personal data',
  'Sem subcategoria': 'No subcategory',
  // estado da análise
  'A ler o PDF': 'Reading the PDF',
  'A analisar com o Gemini': 'Analysing with Gemini',
  'A validar os ids': 'Checking the ids',
  'Na fila: é analisado a seguir aos anteriores.': 'Queued: it is analysed after the ones before it.',
  'Tentar novamente': 'Try again',
  'Nenhum PDF pôde ser lido.': 'No PDF could be read.',
  // relatório
  'palavras no documento': 'words in the document',
  'detetadas pela IA': 'detected by the AI',
  'palavras escondidas': 'hidden words',
  'ids rejeitados': 'rejected ids',
  'Como foi decidido': 'How it was decided',
  'Ids ignorados na validação': 'Ids ignored during validation',
  'Ajustes manuais': 'Manual changes',
  'Palavra': 'Word',
  'Subcategoria': 'Subcategory',
  'Posições': 'Positions',
  'Estado': 'Status',
  'Escondida': 'Hidden',
  'Visível': 'Visible',
  'Dados sensíveis': 'Sensitive data',
  'Adicionada manualmente': 'Added by hand',
  // avisos
  'PDF anonimizado descarregado.': 'Anonymised PDF downloaded.',
  'Texto anonimizado descarregado.': 'Anonymised text downloaded.',
  'Relatório descarregado.': 'Report downloaded.',
  'Ainda não há documentos analisados.': 'No documents have been analysed yet.',
  'Escolhe ficheiros PDF ou um ZIP.': 'Choose PDF files or a ZIP.',
  'Cada ficheiro tem de ter menos de 25 MB.': 'Each file must be under 25 MB.',
  'Servidor não encontrado. Corre python submission/src/server.py para analisar PDFs.': 'Server not found. Run python submission/src/server.py to analyse PDFs.',
  'Sem ligação ao servidor local. Está a correr?': 'No connection to the local server. Is it running?',
  'Requer o servidor local: python submission/src/server.py': 'Needs the local server: python submission/src/server.py',
  // sobre nós
  'Somos cinco alunos do 2.º ano da Licenciatura em Engenharia Informática e de Computadores, e juntámo-nos com uma ideia simples: um documento deve poder circular sem levar atrás a vida de quem lá aparece.':
    'We are five second-year students of the BSc in Computer Science and Engineering, and we got together around a simple idea: a document should be able to travel without dragging along the life of whoever appears in it.',
  'Pelo caminho discutimos com um modelo de linguagem até ele perceber o que é um dado pessoal, ensinámos um PDF a guardar segredos e alguém insistiu que o site precisava de um detetive.':
    'Along the way we argued with a language model until it understood what personal data is, taught a PDF to keep secrets, and someone insisted the site needed a detective.',
  'Como bons anonimizadores, começámos por nós.': 'Like good anonymisers, we started with ourselves.',
  'Passa o rato por uma pasta para a abrir.': 'Hover over a folder to open it.',
  'Confidencial': 'Confidential',
  'GitHub por acrescentar': 'GitHub to be added',
  'Anonimizator': 'Anonymizator',   // o nome do site
};

const n = (count, one, many) => `${count} ${count === '1' ? one : many}`;
const secs = s => (s ? ` in ${s.replace(',', '.')} s` : '');
const DECIDED = 'Every word in the document gets an id. Gemini returns each value with its id, category and subcategory, and the pipeline checks in the original text that the word really is at that id (it fixes the ones that are off by a few positions and drops the rest). The final call is yours: what you choose here is what goes into the exported files.';

// [expressão em português, função que devolve o inglês]
const RULES = [
  [/^(\S+) páginas? · (\S+) palavras? · (\S+) linhas?$/, (m) => `${n(m[1], 'page', 'pages')} · ${n(m[2], 'word', 'words')} · ${n(m[3], 'line', 'lines')}`],
  [/^de (\S+) palavras · (\d+)%$/, (m) => `of ${m[1]} words · ${m[2]}%`],
  [/^Servidor ligado · (.+)$/, (m) => `Server on · ${m[1]}`],
  [/^(?:Análise concluída com (.+?)(?: em ([\d,]+) s)?|Resultado pré-calculado do documento de exemplo \(sem chamar o Gemini\)): (\S+) palavras? a censurar em (\S+) categorias?\.(?: (\S+) ids? deslocados? (?:foi|foram) corrigidos?\.)?$/,
    (m) => `${m[1] ? `Analysis done with ${m[1]}${secs(m[2])}` : 'Precomputed result for the example document (Gemini was not called)'}: ${n(m[3], 'word', 'words')} to censor in ${n(m[4], 'category', 'categories')}.${m[5] ? ` ${n(m[5], 'shifted id was fixed', 'shifted ids were fixed')}.` : ''}`],
  [/^(?:Análise feita com (.+?)(?: em ([\d,]+) s)?\. |Resultado pré-calculado de uma análise anterior \(nenhum pedido foi feito ao Gemini\)\. )Cada palavra do documento recebe um id\./,
    (m) => `${m[1] ? `Analysed with ${m[1]}${secs(m[2])}. ` : 'Precomputed result from an earlier analysis (no request was sent to Gemini). '}${DECIDED}`],
  [/^(\S+) ids? ignorados?: não coincidiam com o texto\. Ver detalhes$/, (m) => `${n(m[1], 'id ignored', 'ids ignored')}: they did not match the text. See details`],
  [/^(\d+) id\(s\) indicado\(s\) pelo modelo foram ignorados por não coincidirem com o texto$/, (m) => `${m[1]} id(s) given by the model were ignored because they did not match the text`],
  [/^“(.+)” \((.+)\) apontava para o id (-?\d+), que não existe no documento\.$/, (m) => `“${m[1]}” (${m[2]}) pointed to id ${m[3]}, which does not exist in the document.`],
  [/^“(.+)” \((.+)\) apontava para o id (-?\d+), mas nesse id está “(.*)”\. Não foi escondido\.$/, (m) => `“${m[1]}” (${m[2]}) pointed to id ${m[3]}, but that id holds “${m[4]}”. It was not hidden.`],
  [/^(#\d+ “.*”) foi adicionada por ti \(falso negativo\)\.$/, (m) => `${m[1]} was added by you (false negative).`],
  [/^(#\d+ “.*”) foi detetada, mas mantida visível \(falso positivo\)\.$/, (m) => `${m[1]} was detected but kept visible (false positive).`],
  [/^(\d+)\/(\d+) escondidas$/, (m) => `${m[1]}/${m[2]} hidden`],
  [/^Parcial (.+)$/, (m) => `Partial ${m[1]}`],
  [/^Esconder tudo em (.+)$/, (m) => `Hide everything in ${m[1]}`],
  [/^Expandir (.+)$/, (m) => `Expand ${m[1]}`],
  [/^Página (\d+)$/, (m) => `Page ${m[1]}`],
  [/^Página (\d+) do documento$/, (m) => `Page ${m[1]} of the document`],
  [/^Processo n\.º (\d+)$/, (m) => `File no. ${m[1]}`],
  [/^(\d+) ficheiros$/, (m) => `${m[1]} files`],
  [/^Ignorados: (.+)$/, (m) => `Skipped: ${m[1]}`],
  [/^Sem resultados para “(.*)”\.$/, (m) => `No results for “${m[1]}”.`],
  [/^ZIP descarregado com (\d+) documentos?\.$/, (m) => `ZIP downloaded with ${n(m[1], 'document', 'documents')}.`],
  [/^ZIP descarregado com (\d+) de (\d+) documentos \(os restantes ainda não estão prontos\)\.$/, (m) => `ZIP downloaded with ${m[1]} of ${m[2]} documents (the others are not ready yet).`],
];

const BACK = Object.fromEntries(Object.entries(EXACT).map(([pt, en]) => [en, pt]));
const ATTRS = ['placeholder', 'aria-label', 'title', 'alt', 'data-ref'];
// Conteúdo, não interface: nunca se traduz.
const SKIP = 'script, style, #paper, .chips, td.word, .t-name, .s-head .grow, .intro-title, .intro-line, .hero h1, .sr-only, .file-name, .file-desc, #fname, .tab .name, .lens, .tip small';

let lang = 'pt';
try { if (localStorage.getItem('lang') === 'en') lang = 'en'; } catch { /* sem storage */ }

function toEnglish(pt) {
  if (pt in EXACT) return EXACT[pt];
  for (const [re, fn] of RULES) {
    const m = re.exec(pt);
    if (m) return fn(m);
  }
  return pt;
}

// O texto na língua atual. src é sempre a versão portuguesa, quando se sabe.
function render(src) {
  const core = src.trim();
  if (!core) return src;
  const out = lang === 'en' ? toEnglish(core) : (BACK[core] || core);
  return out === core ? src : src.replace(core, out);
}

function text(node) {
  if (node.parentElement && node.parentElement.closest(SKIP)) return;
  // Se o texto mudou por fora (outro script escreveu), passa a ser a origem.
  if (node._shown !== node.data) node._src = BACK[node.data.trim()] ? node.data.replace(node.data.trim(), BACK[node.data.trim()]) : node.data;
  const out = render(node._src);
  node._shown = out;
  if (node.data !== out) node.data = out;
}

function attrs(el) {
  if (el.closest(SKIP)) return;
  for (const name of ATTRS) {
    const value = el.getAttribute(name);
    if (value == null) continue;
    const kept = (el._i18n ||= {});
    if (!kept[name] || kept[name].shown !== value) kept[name] = { src: BACK[value] || value };
    const out = render(kept[name].src);
    kept[name].shown = out;
    if (value !== out) el.setAttribute(name, out);
  }
}

function walk(root) {
  if (root.nodeType === Node.TEXT_NODE) return text(root);
  if (root.nodeType !== Node.ELEMENT_NODE) return;
  attrs(root);
  for (const el of root.querySelectorAll('*')) attrs(el);
  const it = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = it.nextNode(); node; node = it.nextNode()) text(node);
}

function apply() {
  document.documentElement.lang = lang === 'en' ? 'en' : 'pt-PT';
  document.title = render(document._title ||= document.title);
  walk(document.body);
  const btn = document.getElementById('lang');
  if (btn) btn.textContent = lang === 'en' ? 'EN' : 'PT';
}

new MutationObserver(records => {
  for (const r of records) {
    if (r.type === 'characterData') text(r.target);
    else if (r.type === 'attributes') attrs(r.target);
    else r.addedNodes.forEach(walk);
  }
}).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });

document.getElementById('lang').addEventListener('click', () => {
  lang = lang === 'en' ? 'pt' : 'en';
  try { localStorage.setItem('lang', lang); } catch { /* sem storage */ }
  apply();
  dispatchEvent(new CustomEvent('langchange', { detail: lang }));
});
apply();

})();
