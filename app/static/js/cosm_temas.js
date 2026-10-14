/* ==========================================================================
   ARTE DOS TEMAS NOVOS (Rodada 26): efeitos que precisam de HTML/SVG gerado por código.
   Cada tema registra aqui os seus efeitos em `Cosm` (cosmeticos.js) por id; o visual em si (CSS) mora em css/cosm_temas.css.
   Carregado DEPOIS de cosmeticos.js. Só gera markup a partir de ids que o catálogo conhece (nada de texto de usuário aqui).

   CAIXA PADRÃO DO EFEITO DE AVATAR: o `.ef-av` é um quadrado de 160% da foto (inset -30%): num SVG de viewBox 160 a foto é o círculo
   de raio 50 no centro (80, 80). Efeito novo tem que caber ali. Um efeito pode também ter uma 2ª peça, `.ef-av-sobre`, que fica POR CIMA
   da foto (viewBox 100 = a foto inteira, já recortada em círculo): é o que deixa o simbionte "engolir" a foto.
   ========================================================================== */
const CosmTemas = (() => {
    const f1 = (n) => Math.round(n * 10) / 10;

    // ---- Símbolo e olhos do simbionte (decalcados por código: pernas afiladas a partir de curvas, espelhadas; ver docs/ARTE_TEMAS.md) ----
    const SIM_SIMBOLO = 'M50.0 25.9 L51.2 26.0 L52.3 26.2 L53.3 26.6 L54.2 27.2 L55.0 27.8 L55.6 28.6 L56.2 29.4 L56.7 30.4 L57.0 31.4 L57.3 32.5 L57.4 33.6 L57.5 34.8 L57.5 34.8 L57.5 35.8 L57.4 36.7 L57.3 37.5 L57.1 38.2 L57.0 38.9 L56.8 39.6 L56.6 40.1 L56.3 40.7 L56.1 41.2 L55.9 41.6 L55.7 42.1 L55.5 42.5 L55.5 42.5 L54.8 42.8 L54.0 43.0 L53.1 43.2 L52.1 43.3 L51.1 43.4 L50.0 43.4 L48.9 43.4 L47.9 43.3 L46.9 43.2 L46.0 43.0 L45.2 42.8 L44.5 42.5 L44.5 42.5 L44.3 42.1 L44.1 41.6 L43.9 41.2 L43.7 40.7 L43.4 40.1 L43.2 39.6 L43.0 38.9 L42.9 38.2 L42.7 37.5 L42.6 36.7 L42.5 35.8 L42.5 34.8 L42.5 34.8 L42.6 33.6 L42.7 32.5 L43.0 31.4 L43.3 30.4 L43.8 29.4 L44.4 28.6 L45.0 27.8 L45.8 27.2 L46.7 26.6 L47.7 26.2 L48.8 26.0 L50.0 25.9ZM42.9 40.9 L57.1 40.9 L57.6 42.3 L58.0 43.7 L58.4 45.2 L58.8 46.7 L59.1 48.1 L59.4 49.6 L59.7 51.1 L59.9 52.6 L60.1 54.1 L60.2 55.6 L60.3 57.2 L60.3 58.7 L60.3 58.7 L60.3 89.0 L60.3 89.9 L60.2 90.8 L60.1 91.6 L59.9 92.2 L59.7 92.8 L59.4 93.3 L59.1 93.7 L58.7 94.1 L58.3 94.3 L57.8 94.5 L57.3 94.6 L56.7 94.6 L56.7 94.6 L54.6 94.6 L54.6 91.6 L45.4 91.6 L45.4 94.6 L43.3 94.6 L42.7 94.6 L42.2 94.5 L41.7 94.3 L41.3 94.1 L40.9 93.7 L40.6 93.3 L40.3 92.8 L40.1 92.2 L39.9 91.6 L39.8 90.8 L39.7 89.9 L39.7 89.0 L39.7 89.0 L39.7 58.7 L39.7 57.2 L39.8 55.6 L39.9 54.1 L40.1 52.6 L40.3 51.1 L40.6 49.6 L40.9 48.1 L41.2 46.7 L41.6 45.2 L42.0 43.7 L42.4 42.3 L42.9 40.9ZM46.6 27.5 L46.3 27.3 L46.0 27.1 L45.7 26.8 L45.4 26.5 L45.2 26.1 L45.0 25.8 L44.8 25.4 L44.7 25.0 L44.7 24.5 L44.7 24.1 L44.8 23.6 L44.9 23.1 L44.9 23.1 L45.4 23.4 L45.8 23.7 L46.2 23.9 L46.5 24.2 L46.9 24.5 L47.3 24.7 L47.7 25.0 L48.1 25.2 L48.4 25.5 L48.8 25.8 L49.1 26.0 L49.4 26.3 L50.6 26.3 L50.6 26.3 L50.9 26.0 L51.2 25.8 L51.6 25.5 L51.9 25.2 L52.3 25.0 L52.7 24.7 L53.1 24.5 L53.5 24.2 L53.8 23.9 L54.2 23.7 L54.6 23.4 L55.1 23.1 L55.1 23.1 L55.2 23.6 L55.3 24.1 L55.3 24.5 L55.3 25.0 L55.2 25.4 L55.0 25.8 L54.8 26.1 L54.6 26.5 L54.3 26.8 L54.0 27.1 L53.7 27.3 L53.4 27.5 L53.4 27.5 L53.1 27.8 L52.6 28.0 L52.0 28.2 L51.4 28.4 L50.7 28.4 L50.0 28.5 L49.3 28.4 L48.6 28.4 L48.0 28.2 L47.4 28.0 L46.9 27.8 L46.6 27.5ZM45.3 31.3 L24.2 11.7 L3.6 27.8 L0.0 27.6 L0.6 24.0 L24.5 5.4 L48.6 27.8ZM51.4 27.8 L75.5 5.4 L99.4 24.0 L100.0 27.6 L96.4 27.8 L75.8 11.7 L54.7 31.3ZM45.3 37.4 L27.1 19.5 L4.9 39.5 L1.3 39.4 L1.7 35.8 L27.2 12.9 L48.7 33.9ZM51.3 33.9 L72.8 12.9 L98.3 35.8 L98.7 39.4 L95.1 39.5 L72.9 19.5 L54.7 37.4ZM45.2 43.3 L30.4 27.4 L7.5 51.4 L3.9 51.7 L4.0 48.1 L30.4 20.4 L48.7 40.0ZM51.3 40.0 L69.6 20.4 L96.0 48.1 L96.1 51.7 L92.5 51.4 L69.6 27.4 L54.8 43.3ZM45.1 49.3 L34.0 35.8 L11.2 63.4 L7.7 64.0 L7.5 60.4 L34.0 28.2 L48.8 46.2ZM51.2 46.2 L66.0 28.2 L92.5 60.4 L92.3 64.0 L88.8 63.4 L66.0 35.8 L54.9 49.3Z';
    const SIM_OLHO = 'M3 5 C20 -4 48 3 63 31 C46 38 18 29 3 5Z';

    // ---------------------------------------------------------------------
    // TENTÁCULOS: cadeia de segmentos aninhados. Cada segmento gira em volta da própria junta (origem do seu <g>), com atraso crescente
    // pra onda andar do pé até a ponta. Só transform (vai pra GPU). `ang` = direção da raiz (0° = pra cima, horário).
    // ---------------------------------------------------------------------
    function tentaculo({ x, y, ang, segs, curva, amp, atraso }) {
        let dentro = '';
        for (let i = segs.length - 1; i >= 0; i--) {
            const [L, w] = segs[i];
            dentro = `<g class="s" style="--a:${amp}deg;--c:${curva}deg;--d:-${f1(atraso + i * .24)}s"><line class="sb" y2="${-L}" stroke-width="${w}"/>${dentro ? `<g transform="translate(0 ${-L})">${dentro}</g>` : ''}</g>`;
        }
        return `<g transform="translate(${f1(x)} ${f1(y)}) rotate(${ang})"><g class="ext" style="--e:${f1(atraso)}s">${dentro}</g></g>`;
    }
    const SEGS_AV = [[8.5, 5.8], [7.6, 4.8], [6.7, 3.8], [5.8, 2.9], [5, 2]];

    // ---------------------------------------------------------------------
    // SIMBIONTE (efeito de avatar). Duas peças:
    //   atrás da foto (.ef-av):       9 tentáculos que ficam ondulando em volta da borda;
    //   por cima da foto (.ef-av-sobre): a gosma preta cresce da borda pro centro e COME a foto, o símbolo branco aparece, e ela recua
    //                                    de volta pra borda (de onde os tentáculos continuam a viver). Ciclo de 16 s.
    // ---------------------------------------------------------------------
    let _sim = null;
    function htmlSimbionte() {
        if (_sim) return _sim;
        const angs = [8, 47, 92, 133, 172, 213, 258, 301, 338];
        const curvas = [14, -12, 16, -15, 12, -16, 15, -13, 14];
        const tent = angs.map((a, i) => {
            const r = 47, rad = a * Math.PI / 180;
            return tentaculo({ x: 80 + r * Math.sin(rad), y: 80 - r * Math.cos(rad), ang: a, segs: SEGS_AV, curva: curvas[i], amp: 9 + (i % 3) * 2.5, atraso: (i * .53) % 3.2 });
        }).join('');
        const blobs = [0, 36, 72, 108, 144, 180, 216, 252, 288, 324].map((a, i) => {
            const rad = (a + 9) * Math.PI / 180;
            return `<circle class="b" cx="${f1(50 + 47 * Math.sin(rad))}" cy="${f1(50 - 47 * Math.cos(rad))}" r="27" style="--d:${f1(i * .09)}s"/>`;
        }).join('');
        _sim = `<i class="ef-av ef-av-simbionte" aria-hidden="true"><svg class="sim-tent" viewBox="0 0 160 160">${tent}</svg></i>` +
               `<i class="ef-av-sobre ef-sobre-simbionte" aria-hidden="true"><svg class="sim-gosma" viewBox="0 0 100 100"><g filter="url(#sim-goo)">${blobs}<circle class="b c" cx="50" cy="50" r="22" style="--d:.95s"/></g>` +
               `<g transform="translate(18 18) scale(.64)"><g class="sim-sim"><path d="${SIM_SIMBOLO}"/></g></g></svg></i>`;
        return _sim;
    }


    // ---------------------------------------------------------------------
    // SVG como imagem de fundo (anel da moldura, olhos da placa, faixa): gerado aqui e entregue ao CSS por variável (--sim-*).
    // SVG usado como imagem roda as próprias animações (CSS dentro do SVG), mas não enxerga o CSS da página: leva o seu <style>.
    // ---------------------------------------------------------------------
    const svgUri = (svg) => `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
    const SIM_ESTILO = '.sb{stroke:#07070c;stroke-linecap:round}.s{transform-origin:0 0;animation:o 3.4s ease-in-out infinite alternate;animation-delay:var(--d)}@keyframes o{from{transform:rotate(calc(var(--c) - var(--a)))}to{transform:rotate(calc(var(--c) + var(--a)))}}';
    const olhosG = (x, y, k) => `<g transform="translate(${x} ${y}) scale(${k})"><path d="${SIM_OLHO}" transform="translate(2 0)"/><path d="${SIM_OLHO}" transform="translate(134 0) scale(-1 1)"/></g>`;

    // anel de gosma: círculo com a borda de fora ondulada e três bolhas (máscara da moldura; viewBox 100 = a caixa do anel)
    function anelGosmaSvg() {
        let ext = '';
        for (let i = 0; i < 140; i++) {
            const a = i / 140 * Math.PI * 2;
            let r = 41.4 + 1.7 * Math.sin(7 * a + .6) + 1.1 * Math.sin(13 * a + 1.9);
            [.5, 1.6, 2.75, 3.7, 4.55, 5.6].forEach((c, k) => { const d = Math.atan2(Math.sin(a - c), Math.cos(a - c)); r += (k % 2 ? 4.4 : 5.6) * Math.exp(-(d * d) / (2 * .11 * .11)); });
            ext += `${i ? 'L' : 'M'}${f1(50 + r * Math.cos(a))} ${f1(50 + r * Math.sin(a))}`;
        }
        return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path fill-rule="evenodd" d="${ext}ZM14 50A36 36 0 1 0 86 50A36 36 0 1 0 14 50Z"/></svg>`;
    }
    // os dois olhos (placa): abrem, olham e piscam
    function olhosSvg() {
        return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 136 34"><style>.o{transform-box:fill-box;transform-origin:50% 50%;animation:p 7s ease-in-out infinite}@keyframes p{0%{transform:scaleY(.04)}7%,83%{transform:scaleY(1)}87%{transform:scaleY(.04)}91%,100%{transform:scaleY(1)}}</style><g class="o" fill="#fff"><path d="${SIM_OLHO}" transform="translate(2 0)"/><path d="${SIM_OLHO}" transform="translate(134 0) scale(-1 1)"/></g></svg>`;
    }
    // faixa "Invasão" (340 x 112, o tamanho do banner do cartão): tentáculos subindo da borda de baixo e descendo da de cima, a aranha ao fundo e dois olhos
    function faixaInvasaoSvg() {
        const baixo = [[14, 7], [64, -8], [114, 8], [170, -7], [226, 8], [282, -8], [330, 7]];
        const segsB = [[24, 13], [21, 10.6], [18, 8.4], [15, 6.2], [12, 4.4], [9, 2.8]];
        const segsC = [[16, 9.5], [14, 7.4], [12, 5.4], [10, 3.6]];
        let tent = baixo.map(([x, c], i) => tentaculo({ x, y: 120, ang: 0, segs: segsB, curva: c, amp: 6 + (i % 3) * 2, atraso: i * .45 })).join('');
        tent += [[40, 6], [150, -6], [250, 6]].map(([x, c], i) => tentaculo({ x, y: -8, ang: 180, segs: segsC, curva: c, amp: 7, atraso: i * .6 + .3 })).join('');
        return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 340 112" preserveAspectRatio="xMidYMax slice"><defs><radialGradient id="g" cx=".82" cy=".25" r=".75"><stop offset="0" stop-color="#232a52"/><stop offset="1" stop-color="#030306"/></radialGradient>` +
            `<filter id="r" x="-10%" y="-10%" width="120%" height="120%"><feDropShadow dx="0" dy="0" stdDeviation=".9" flood-color="#aab4ff" flood-opacity=".85"/></filter></defs>` +
            `<style>${SIM_ESTILO}.ol{transform-box:fill-box;transform-origin:50% 50%;animation:ab 9s ease-in-out infinite}@keyframes ab{0%,50%{opacity:0;transform:scaleY(.1)}57%,70%{opacity:1;transform:scaleY(1)}76%{opacity:1;transform:scaleY(.1)}80%,100%{opacity:0}}</style>` +
            `<rect width="340" height="112" fill="url(#g)"/><g transform="translate(212 4) scale(.92)" fill="#fff" opacity=".12"><path d="${SIM_SIMBOLO}"/></g>` +
            `<g transform="translate(84 30) scale(.62)"><g class="ol" fill="#fff"><path d="${SIM_OLHO}" transform="translate(2 0)"/><path d="${SIM_OLHO}" transform="translate(134 0) scale(-1 1)"/></g></g>` +
            `<g filter="url(#r)">${tent}</g></svg>`;
    }
    function instalarVars() {
        const r = document.documentElement.style;
        r.setProperty('--sim-anel', svgUri(anelGosmaSvg()));
        r.setProperty('--sim-olhos', svgUri(olhosSvg()));
        r.setProperty('--sim-faixa', svgUri(faixaInvasaoSvg()));
    }

    // ---------------------------------------------------------------------
    // INVASÃO NEGRA (efeito de perfil, cartão 340 x 440): tentáculos entram pelas bordas, tomam o cartão, a aranha branca pisca no meio e eles recuam.
    // ---------------------------------------------------------------------
    let _inv = null;
    function htmlInvasao() {
        if (_inv) return _inv;
        // [x, y, direção] das raízes nas bordas
        const raizes = [[0, 60, 88], [0, 190, 78], [0, 330, 100], [340, 100, 272], [340, 250, 282], [340, 390, 260], [50, 440, 6], [170, 440, 354], [290, 440, 4], [110, 0, 178], [240, 0, 184]];
        const segs = [[26, 15], [24, 13], [22, 11], [20, 9.2], [18, 7.4], [16, 5.6], [14, 3.8]];
        const tent = raizes.map(([x, y, ang], i) => tentaculo({ x, y, ang, segs, curva: i % 2 ? 8 : -8, amp: 6 + (i % 3) * 2, atraso: (i * .37) % 2.2 })).join('');
        _inv = `<div class="ef-pf ef-pf-invasao" aria-hidden="true"><i class="inv-vinheta"></i><svg viewBox="0 0 340 440" preserveAspectRatio="xMidYMid slice"><g transform="translate(120 250) scale(1.0)"><g class="inv-sim"><path d="${SIM_SIMBOLO}"/></g></g><g class="inv-tent">${tent}</g></svg></div>`;
        return _inv;
    }

    // ---------------------------------------------------------------------
    // REGISTRO: id -> função que devolve o HTML. `ids` = os ids dos efeitos que só precisam de classe (fala, radar, chat, som, pin, servidor).
    // ---------------------------------------------------------------------
    const AVATAR = { simbionte: htmlSimbionte };
    const PERFIL = { invasao: htmlInvasao };
    const IDS = { fala: [], radar: [], chat: [], som: [], pin: [], servidor: [] };
    instalarVars();
    Cosm.registrarTema({ avatar: AVATAR, perfil: PERFIL, ids: IDS });
    return { AVATAR, PERFIL, IDS, SIM_SIMBOLO, SIM_OLHO, tentaculo };
})();
