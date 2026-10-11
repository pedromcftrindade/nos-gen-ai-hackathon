/* A lupa do logótipo, desenhada em SVG.
 *
 * Usada pelo cursor do ecrã de boas-vindas (intro.js) e pelo detetive
 * (detective.js). As medidas, incluindo a rotação de -0,3 graus, foram
 * tiradas da imagem original.
 */

// Devolve um <g> com a lupa centrada em (0, 0), em unidades em que o raio
// exterior do anel é 100: 36 raios de 10 em 10 graus e o cabo, que prolonga
// o raio dos 160 graus e chega até (65, 178). O vidro é o círculo interior,
// de raio 58.
function lupaRays() {
  const NS = 'http://www.w3.org/2000/svg';
  // Trapézio que aponta para cima, do raio r0 (largura w0) ao raio r1
  // (largura w1), rodado deg graus.
  const ray = (r0, w0, r1, w1, deg) => {
    const p = document.createElementNS(NS, 'polygon');
    p.setAttribute('points', `${-w0 / 2},${-r0} ${w0 / 2},${-r0} ${w1 / 2},${-r1} ${-w1 / 2},${-r1}`);
    p.setAttribute('transform', `rotate(${deg})`);
    return p;
  };
  const g = document.createElementNS(NS, 'g');
  g.setAttribute('transform', 'rotate(-0.3)');
  for (let i = 0; i < 36; i++) g.append(ray(58.2, 5.84, 100, 8.31, i * 10));
  g.append(ray(109.9, 8.14, 189.45, 29.53, 160));
  return g;
}
