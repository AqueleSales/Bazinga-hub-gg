/* ==========================================================================
   COSMÉTICOS: patentes (ícones SVG animados), insígnias e o popover "orb".

   Carregado ANTES do script principal do chat.html (só declara coisas; nada aqui
   depende de variáveis do chat na hora de carregar). O que é desenhado vem do
   servidor: id da patente + subnível, ids de insígnias. Os ids são conferidos aqui
   contra as tabelas abaixo - id desconhecido cai num padrão, nunca vira texto solto
   num atributo. O visual (CSS) está em /static/css/cosmeticos.css.
   ========================================================================== */
const Cosm = (() => {
    const ROMANOS = ['I', 'II', 'III'];
    let _uid = 0;

    // ---------------------------------------------------------------------
    // Paleta de cada patente: m = metal (claro, médio, escuro), g = gema, d = fundo escuro
    // ---------------------------------------------------------------------
    const PAL = {
        iniciado:    { m: ['#f9d1a4', '#d98a4a', '#8a4a1f'], g: ['#fff7b0', '#b6e04a', '#4f9d2f'], d: '#4a2410', luz: '#ffd9a8' },
        aprendiz:    { m: ['#f3f4f6', '#9ca3af', '#4b5563'], g: ['#f3e8ff', '#a78bfa', '#6d28d9'], d: '#252a36', luz: '#e9d5ff' },
        explorador:  { m: ['#fff0b3', '#f5c542', '#9a5b06'], g: ['#ffd6d6', '#f06a6a', '#a61b1b'], d: '#4d2f05', luz: '#fff0b3' },
        desbravador: { m: ['#b9f8ee', '#2dd4bf', '#0b6b64'], g: ['#f0feff', '#67e8f9', '#0e7490'], d: '#082f33', luz: '#c7fff6' },
        veterano:    { m: ['#c7defd', '#5b9cf5', '#1b45c4'], g: ['#f2f8ff', '#8ec1ff', '#2150d8'], d: '#0f2260', luz: '#d6e8ff' },
        heroi:       { m: ['#eef2f7', '#94a3b8', '#3f4c60'], g: ['#e6f7ff', '#38bdf8', '#0369a1'], d: '#1a2434', luz: '#d6f1ff' },
        lenda:       { m: ['#ffe0bd', '#fb923c', '#b13a08'], g: ['#fff3a0', '#fb923c', '#d62828'], d: '#3d1707', luz: '#ffe3c2' },
        campeao:     { m: ['#ffffff', '#b9ecff', '#6a6cf0'], g: ['#ffffff', '#bde6ff', '#7a86f5'], d: '#2a2870', luz: '#ffffff' },
        semideus:    { m: ['#fff6cf', '#fbbf24', '#a8520a'], g: ['#fff4ec', '#fda4af', '#d9154a'], d: '#4f2208', luz: '#fff2b8' },
        tita:        { m: ['#7b8494', '#3b4252', '#12151c'], g: ['#fff08a', '#f97316', '#b21d1d'], d: '#0c0d12', luz: '#ffb27a' },
        olimpiano:   { m: ['#ffffff', '#fde68a', '#e08a0b'], g: ['#ffffff', '#fff1bf', '#f6b021'], d: '#6a3f03', luz: '#fffbe6' },
        panteao:     { m: ['#fff0ff', '#ec7ffa', '#6d28d9'], g: ['#ffffff', '#f5b8ff', '#5b6cf9'], d: '#26104f', luz: '#ffe8ff' },
    };
    const PT_IDS = Object.keys(PAL);

    // Gradientes globais (uma vez só): cada ícone só referencia por id, então não repete <defs>.
    function defsHtml() {
        const grad = (id, cores, x2 = 0, y2 = 1) =>
            `<linearGradient id="${id}" x1="0" y1="0" x2="${x2}" y2="${y2}">` +
            cores.map((c, i) => `<stop offset="${i / (cores.length - 1)}" stop-color="${c}"/>`).join('') + '</linearGradient>';
        let h = '';
        PT_IDS.forEach(id => {
            const p = PAL[id];
            h += grad(`ptg-${id}-m`, p.m) + grad(`ptg-${id}-g`, p.g, 1, 1);
            h += `<radialGradient id="ptg-${id}-h"><stop offset="0" stop-color="${p.luz}" stop-opacity=".75"/><stop offset=".55" stop-color="${p.m[1]}" stop-opacity=".25"/><stop offset="1" stop-color="${p.m[1]}" stop-opacity="0"/></radialGradient>`;
            h += `<linearGradient id="ptg-${id}-r" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${p.luz}" stop-opacity=".0"/><stop offset=".5" stop-color="${p.luz}" stop-opacity=".55"/><stop offset="1" stop-color="${p.luz}" stop-opacity="0"/></linearGradient>`;
        });
        h += `<linearGradient id="ptg-brilho" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".85"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>`;
        // Insígnias
        h += grad('bdg-ouro', ['#fff2b0', '#ffb62e', '#b45309']) + grad('bdg-cobre', ['#ffd9b0', '#f08a30', '#8c3a07']);
        h += grad('bdg-roxo', ['#e9d5ff', '#a45cf5', '#4c1d95']) + grad('bdg-aco', ['#f1f5f9', '#94a3b8', '#334155']);
        h += grad('bdg-verde', ['#d1fae5', '#34d399', '#047857']) + grad('bdg-ciano', ['#cffafe', '#22d3ee', '#0e7490']);
        h += `<linearGradient id="bdg-fusao" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#ff9d2e"/><stop offset=".5" stop-color="#f06ab8"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient>`;
        return `<svg id="cosm-defs" width="0" height="0" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true" focusable="false"><defs>${h}</defs></svg>`;
    }

    function injetarDefs() {
        if (document.getElementById('cosm-defs')) return;
        document.body.insertAdjacentHTML('afterbegin', defsHtml());
    }

    // ---------------------------------------------------------------------
    // Os 12 emblemas (viewBox 64x64; o conteúdo ocupa ~y 2..60, os pontinhos de subnível ficam embaixo).
    // `sil` = formas da silhueta, usadas como recorte do brilho que varre o ícone.
    // ---------------------------------------------------------------------
    const espelho = (s) => `<g transform="translate(64 0) scale(-1 1)">${s}</g>`;
    const ponto = (x, y, r, fill, op = 1) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" opacity="${op}"/>`;
    const poly = (pts, fill, stroke, sw = 1.4, extra = '') => `<path d="M${pts.map(p => p.join(' ')).join(' L')} Z" fill="${fill}" ${stroke ? `stroke="${stroke}" stroke-width="${sw}" stroke-linejoin="round"` : ''} ${extra}/>`;
    const losango = (cx, cy, r) => `M${cx} ${cy - r} L${cx + r} ${cy} L${cx} ${cy + r} L${cx - r} ${cy} Z`;

    const EMBLEMAS = {
        // 1. Orbe de cobre
        iniciado: (c) => ({
            sil: '<circle cx="32" cy="31" r="27"/>',
            svg: `<circle cx="32" cy="31" r="27" fill="${c.M}" stroke="${c.D}" stroke-width="1.6"/>
                  <circle cx="32" cy="31" r="21" fill="${c.D}"/>
                  <circle cx="32" cy="31" r="21" fill="none" stroke="${c.L}" stroke-width="1.2" opacity=".55"/>
                  ${[45, 135, 225, 315].map(a => ponto(32 + 24 * Math.cos(a * Math.PI / 180), 31 + 24 * Math.sin(a * Math.PI / 180), 2.1, c.L, .9)).join('')}
                  <circle cx="32" cy="31" r="15" fill="${c.G}" stroke="${c.L}" stroke-width="1.2"/>
                  <path d="M22.5 27 A11 11 0 0 1 35.5 19.5" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" opacity=".65"/>
                  <circle cx="38" cy="38" r="3.4" fill="#fff" opacity=".18"/>`
        }),
        // 2. Escudo invertido de aço com gema violeta
        aprendiz: (c) => ({
            sil: '<path d="M5 7 L59 7 L32 59 Z"/>',
            svg: `${poly([[5, 7], [59, 7], [32, 59]], c.M, c.D, 1.8)}
                  ${poly([[12, 12], [52, 12], [32, 49]], c.D)}
                  ${poly([[18, 16], [46, 16], [32, 41]], c.G, c.L, 1)}
                  <path d="M18 16 L32 16 L32 41 Z" fill="#fff" opacity=".2"/>
                  <path d="M8 9.5 L56 9.5" stroke="#fff" stroke-width="1.4" opacity=".5" stroke-linecap="round"/>`
        }),
        // 3. Losango dourado com gema rubi
        explorador: (c) => ({
            sil: '<path d="M32 2 L62 31 L32 60 L2 31 Z"/>',
            svg: `${poly([[32, 2], [62, 31], [32, 60], [2, 31]], c.M, c.D, 1.8)}
                  ${poly([[32, 9], [55, 31], [32, 53], [9, 31]], c.D)}
                  ${poly([[32, 15], [49, 31], [32, 47], [15, 31]], c.M, c.D, 1)}
                  ${poly([[32, 21], [43, 31], [32, 41], [21, 31]], c.G, c.L, 1)}
                  <path d="M32 21 L43 31 L32 31 Z" fill="#fff" opacity=".28"/>
                  ${[[32, 5], [59, 31], [32, 57], [5, 31]].map(([x, y]) => ponto(x, y, 1.7, '#fff', .8)).join('')}`
        }),
        // 4. Estrela de quatro pontas
        desbravador: (c) => ({
            sil: '<path d="M32 1 C34 22 42 29 63 31 C42 33 34 40 32 61 C30 40 22 33 1 31 C22 29 30 22 32 1 Z"/>',
            svg: `<path d="M32 1 C34 22 42 29 63 31 C42 33 34 40 32 61 C30 40 22 33 1 31 C22 29 30 22 32 1 Z" fill="${c.M}" stroke="${c.D}" stroke-width="1.6" stroke-linejoin="round"/>
                  <path d="M32 11 C33 23 39 29 52 31 C39 33 33 39 32 51 C31 39 25 33 12 31 C25 29 31 23 32 11 Z" fill="${c.G}"/>
                  <path d="M32 11 C33 23 39 29 52 31 L32 31 Z" fill="#fff" opacity=".25"/>
                  ${[[47, 16], [17, 16], [47, 46], [17, 46]].map(([x, y]) => `<path d="${losango(x, y, 3.2)}" fill="${c.M}" stroke="${c.D}" stroke-width=".8"/>`).join('')}
                  ${ponto(32, 31, 4.4, '#fff', .9)}`
        }),
        // 5. Gema lapidada azul
        veterano: (c) => ({
            sil: '<path d="M16 6 L48 6 L62 22 L32 59 L2 22 Z"/>',
            svg: `${poly([[16, 6], [48, 6], [62, 22], [32, 59], [2, 22]], c.M, c.D, 1.8)}
                  ${poly([[19, 11], [45, 11], [56, 23], [32, 52], [8, 23]], c.G)}
                  <path d="M22 11 L42 11 L46 22 L18 22 Z" fill="#fff" opacity=".4"/>
                  <path d="M8 23 L18 22 L32 52 Z" fill="#000" opacity=".12"/>
                  <path d="M56 23 L46 22 L32 52 Z" fill="#000" opacity=".26"/>
                  <path d="M18 22 L46 22 L32 52 Z" fill="#fff" opacity=".1"/>
                  <path d="M19 11 L18 22 M45 11 L46 22 M8 23 L56 23 M18 22 L32 52 L46 22" fill="none" stroke="#fff" stroke-width=".9" opacity=".5" stroke-linejoin="round"/>`
        }),
        // 6. Hexágono de aço com lâminas
        heroi: (c) => {
            const asa = `${poly([[19, 21], [2, 10], [7, 24]], c.M, c.D, 1.2)}${poly([[19, 30], [1, 26], [8, 35]], c.M, c.D, 1.2)}${poly([[19, 38], [4, 42], [12, 48]], c.M, c.D, 1.2)}`;
            return {
                sil: '<path d="M32 3 L48 12 L48 38 L32 49 L16 38 L16 12 Z"/><path d="M1 10 L19 21 L19 48 L4 42 Z"/><path d="M63 10 L45 21 L45 48 L60 42 Z"/>',
                svg: `${asa}${espelho(asa)}
                  ${poly([[32, 1], [38, 9], [26, 9]], c.M, c.D, 1.2)}
                  ${poly([[32, 59], [38, 47], [26, 47]], c.M, c.D, 1.2)}
                  ${poly([[32, 3], [48, 12], [48, 38], [32, 49], [16, 38], [16, 12]], c.M, c.D, 1.8)}
                  ${poly([[32, 9], [42, 15], [42, 35], [32, 42], [22, 35], [22, 15]], c.D)}
                  ${poly([[32, 15], [38, 19], [38, 31], [32, 35], [26, 31], [26, 19]], c.G, c.L, 1)}
                  <path d="M32 15 L38 19 L38 25 L32 25 Z" fill="#fff" opacity=".3"/>`
            };
        },
        // 7. Chama alada
        lenda: (c) => {
            const asa = `<path d="M28 47 C17 45 7 37 2 19 C11 26 20 28 28 28 Z" fill="${c.M}" stroke="${c.D}" stroke-width="1.3" stroke-linejoin="round"/>
                         <path d="M28 52 C19 54 10 51 4 45 C12 45 21 45 28 41 Z" fill="${c.M}" stroke="${c.D}" stroke-width="1.3" stroke-linejoin="round"/>`;
            return {
                sil: '<path d="M32 5 L45 22 L41 47 L32 56 L23 47 L19 22 Z"/><path d="M28 47 C17 45 7 37 2 19 L28 28 Z"/><path d="M36 47 C47 45 57 37 62 19 L36 28 Z"/>',
                svg: `${asa}${espelho(asa)}
                  ${poly([[32, 5], [45, 22], [41, 47], [32, 57], [23, 47], [19, 22]], c.M, c.D, 1.8)}
                  ${poly([[32, 11], [40, 24], [37, 43], [32, 49], [27, 43], [24, 24]], c.D)}
                  <path d="M32 15 C38 24 40 31 32 43 C24 31 26 24 32 15 Z" fill="${c.G}" stroke="${c.L}" stroke-width=".9"/>
                  <path d="M32 21 C35 26 36 30 32 36 C28 30 29 26 32 21 Z" fill="#fff" opacity=".45"/>
                  <path d="${losango(10, 11, 3)}" fill="${c.L}" opacity=".9"/><path d="${losango(54, 11, 3)}" fill="${c.L}" opacity=".9"/>`
            };
        },
        // 8. Coroa de cristal de gelo
        campeao: (c) => ({
            sil: '<path d="M32 1 L41 20 L37 46 L32 52 L27 46 L23 20 Z"/><path d="M5 14 L24 28 L22 46 L12 44 Z"/><path d="M59 14 L40 28 L42 46 L52 44 Z"/><path d="M8 51 L32 59 L56 51 L48 45 L16 45 Z"/>',
            svg: `${poly([[17, 12], [26, 27], [24, 46], [14, 40], [10, 24]], c.G, c.D, 1.3)}
                  ${poly([[47, 12], [38, 27], [40, 46], [50, 40], [54, 24]], c.G, c.D, 1.3)}
                  ${poly([[5, 27], [12, 35], [10, 45], [3, 38]], c.G, c.D, 1.2)}
                  ${poly([[59, 27], [52, 35], [54, 45], [61, 38]], c.G, c.D, 1.2)}
                  ${poly([[32, 1], [41, 20], [37, 46], [32, 52], [27, 46], [23, 20]], c.G, c.D, 1.6)}
                  <path d="M32 1 L32 52 M23 20 L41 20 M17 12 L17 33 M47 12 L47 33" stroke="#fff" stroke-width=".9" opacity=".55" fill="none"/>
                  <path d="M32 1 L41 20 L32 28 Z" fill="#fff" opacity=".35"/>
                  ${poly([[6, 51], [32, 60], [58, 51], [50, 45], [14, 45]], c.M, c.D, 1.4)}`
        }),
        // 9. Louros e sol
        semideus: (c) => {
            const folhas = [];
            for (let i = 0; i < 7; i++) {
                const a = (100 + i * 20) * Math.PI / 180;
                const x = 32 + 25 * Math.cos(a), y = 31 + 25 * Math.sin(a);
                const rot = (100 + i * 20) + 90 + 12;
                folhas.push(`<ellipse cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" rx="3.1" ry="7.4" transform="rotate(${rot} ${x.toFixed(1)} ${y.toFixed(1)})" fill="${c.M}" stroke="${c.D}" stroke-width="1"/>`);
            }
            const raios = [...Array(8)].map((_, i) => {
                const a = i * 45 * Math.PI / 180;
                return `<path d="M${(32 + 12 * Math.cos(a - .24)).toFixed(1)} ${(31 + 12 * Math.sin(a - .24)).toFixed(1)} L${(32 + 19 * Math.cos(a)).toFixed(1)} ${(31 + 19 * Math.sin(a)).toFixed(1)} L${(32 + 12 * Math.cos(a + .24)).toFixed(1)} ${(31 + 12 * Math.sin(a + .24)).toFixed(1)} Z" fill="${c.M}" stroke="${c.D}" stroke-width=".8" stroke-linejoin="round"/>`;
            }).join('');
            return {
                sil: '<circle cx="32" cy="31" r="29"/>',
                svg: `${folhas.join('')}${espelho(folhas.join(''))}
                      ${raios}
                      <circle cx="32" cy="31" r="12.5" fill="${c.M}" stroke="${c.D}" stroke-width="1.4"/>
                      <circle cx="32" cy="31" r="9.5" fill="${c.G}" stroke="${c.L}" stroke-width=".9"/>
                      <path d="M26 28 A7 7 0 0 1 34 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity=".7"/>`
            };
        },
        // 10. Hexagrama de obsidiana com lava
        tita: (c) => {
            const marcas = [...Array(12)].map((_, i) => {
                const a = i * 30 * Math.PI / 180;
                return `<path d="M${(32 + 17 * Math.cos(a)).toFixed(1)} ${(31 + 17 * Math.sin(a)).toFixed(1)} L${(32 + 20 * Math.cos(a)).toFixed(1)} ${(31 + 20 * Math.sin(a)).toFixed(1)}" stroke="#ff9a3c" stroke-width="1.2" opacity=".8"/>`;
            }).join('');
            return {
                sil: '<path d="M32 1 L58 47 L6 47 Z"/><path d="M32 61 L6 15 L58 15 Z"/>',
                svg: `${poly([[32, 1], [59, 47], [5, 47]], c.M, '#f97316', 1.5)}
                      ${poly([[32, 61], [5, 15], [59, 15]], c.M, '#f97316', 1.5)}
                      <circle cx="32" cy="31" r="17" fill="${c.D}" stroke="#f97316" stroke-width="1.2"/>
                      ${marcas}
                      <circle cx="32" cy="31" r="12" fill="${c.G}" stroke="#ffb27a" stroke-width="1"/>
                      <path d="M26 28 L31 31 L29 37 M35 25 L33 31 L39 33" fill="none" stroke="#7a1010" stroke-width="1.1" stroke-linecap="round" opacity=".75"/>
                      <circle cx="28.5" cy="26.5" r="3" fill="#fff" opacity=".4"/>`
            };
        },
        // 11. Asas radiantes com raio
        olimpiano: (c) => {
            const asa = `<path d="M24 24 L2 9 L8 20 L25 29 Z" fill="${c.M}" stroke="${c.D}" stroke-width="1.1" stroke-linejoin="round"/>
                         <path d="M25 29 L1 22 L8 31 L25 35 Z" fill="${c.M}" stroke="${c.D}" stroke-width="1.1" stroke-linejoin="round"/>
                         <path d="M25 35 L3 35 L10 43 L25 40 Z" fill="${c.M}" stroke="${c.D}" stroke-width="1.1" stroke-linejoin="round"/>
                         <path d="M25 40 L8 47 L17 52 L27 44 Z" fill="${c.M}" stroke="${c.D}" stroke-width="1.1" stroke-linejoin="round"/>`;
            return {
                sil: '<circle cx="32" cy="31" r="17"/><path d="M24 24 L1 9 L1 47 L27 44 Z"/><path d="M40 24 L63 9 L63 47 L37 44 Z"/>',
                svg: `<path d="M19 9 Q32 -3 45 9" fill="none" stroke="${c.M}" stroke-width="2.6" stroke-linecap="round"/>
                      ${asa}${espelho(asa)}
                      <circle cx="32" cy="31" r="17.5" fill="${c.M}" stroke="${c.D}" stroke-width="1.5"/>
                      <circle cx="32" cy="31" r="14" fill="${c.D}"/>
                      <path d="M35 15 L23.5 34 L31 34 L28 49 L41.5 27.5 L33.5 27.5 Z" fill="${c.G}" stroke="${c.L}" stroke-width=".8" stroke-linejoin="round"/>`
            };
        },
        // 12. Templo prismático
        panteao: (c) => ({
            sil: '<path d="M3 27 L32 6 L61 27 Z"/><rect x="8" y="27" width="48" height="25"/><rect x="2" y="52" width="60" height="8"/>',
            svg: `${poly([[3, 27], [32, 6], [61, 27]], c.M, c.D, 1.6)}
                  <path d="M12 26 L32 12 L52 26 Z" fill="${c.D}"/>
                  ${ponto(32, 21, 4.2, c.G)}${ponto(31, 20, 1.6, '#fff', .9)}
                  <rect x="6" y="27" width="52" height="4.5" rx="1" fill="${c.M}" stroke="${c.D}" stroke-width="1.1"/>
                  ${[10, 21, 34, 45].map(x => `<rect x="${x}" y="31.5" width="9" height="19" rx="1" fill="${c.G}" stroke="${c.D}" stroke-width=".9"/><rect x="${x - 1}" y="31.5" width="11" height="2.6" fill="${c.M}" stroke="${c.D}" stroke-width=".7"/>`).join('')}
                  <rect x="4" y="50.5" width="56" height="4.2" rx="1" fill="${c.M}" stroke="${c.D}" stroke-width="1.1"/>
                  <rect x="1" y="54.7" width="62" height="5" rx="1" fill="${c.M}" stroke="${c.D}" stroke-width="1.1"/>`
        }),
    };

    // posição das faíscas (anim >= 3) e dos raios giratórios (anim 4) - cada patente com a sua
    const FAISCAS = [[7, 8], [57, 9], [60, 40], [4, 42], [32, 0]];

    function pontosSubnivel(sub, c) {
        return [-7, 0, 7].map((dx, i) =>
            `<path d="${losango(32 + dx, 62.2, 2.3)}" class="pt-pip ${i < sub ? 'on' : ''}" fill="${i < sub ? c.L : 'rgba(255,255,255,.18)'}" stroke="${c.D}" stroke-width=".5"/>`).join('');
    }

    /** SVG da patente. id = 'iniciado'..'panteao'; sub = 1..3; opts: { anim (0-4), pips } */
    function svgPatente(id, sub, opts = {}) {
        if (!PAL[id]) id = 'iniciado';
        sub = Math.min(Math.max(parseInt(sub, 10) || 1, 1), 3);
        const pal = PAL[id];
        const anim = Math.min(Math.max(opts.anim == null ? 0 : opts.anim, 0), 4);
        const c = { M: `url(#ptg-${id}-m)`, G: `url(#ptg-${id}-g)`, D: pal.d, L: pal.m[0] };
        const { sil, svg } = EMBLEMAS[id](c);
        const uid = ++_uid;
        const pips = opts.pips !== false;

        let atras = '', frente = '';
        if (anim >= 1) atras += `<circle class="pt-halo" cx="32" cy="31" r="33" fill="url(#ptg-${id}-h)"/>`;
        if (anim >= 4) {
            const raios = [...Array(10)].map((_, i) => `<path d="M-2.2 0 L0 -44 L2.2 0 Z" fill="url(#ptg-${id}-r)" transform="rotate(${i * 36})"/>`).join('');
            atras = `<g transform="translate(32 31)"><g class="pt-gira">${raios}</g></g>` + atras;
        }
        if (anim >= 1) frente += `<g clip-path="url(#ptc-${uid})"><rect class="pt-varre" x="-34" y="-8" width="16" height="80" fill="url(#ptg-brilho)"/></g>`;
        if (anim >= 3) {
            const n = anim >= 4 ? 5 : 3;
            frente += FAISCAS.slice(0, n).map(([x, y], i) =>
                `<g transform="translate(${x} ${y})"><path class="pt-fa" style="animation-delay:${(i * 0.9).toFixed(1)}s" d="M0 -3.4 L.9 -.9 L3.4 0 L.9 .9 L0 3.4 L-.9 .9 L-3.4 0 L-.9 -.9 Z" fill="${pal.luz}"/></g>`).join('');
        }

        return `<svg viewBox="0 0 64 64" class="pt-svg pt-id-${id}" role="img" aria-label="Patente ${id}" focusable="false">
            <clipPath id="ptc-${uid}">${sil}</clipPath>
            ${atras}
            <g class="pt-corpo">${svg}</g>
            ${pips ? pontosSubnivel(sub, c) : ''}
            ${frente}
        </svg>`;
    }

    /** Ícone de patente pronto pra colocar na tela. `p` = { id, sub, anim, nome_completo, ... } (vem do servidor).
        Leva data-orb pra abrir o popover. `extra` = texto da linha de baixo do popover. */
    function htmlPatente(p, tamanho = 28, extra = {}) {
        if (!p || !PAL[p.id]) p = { id: 'iniciado', sub: 1, anim: 0, nome_completo: 'Iniciado I' };
        const tam = Math.min(Math.max(parseInt(tamanho, 10) || 28, 12), 160);
        const atrib = `data-orb="patente" data-orb-id="${p.id}" data-orb-sub="${p.sub | 0}" data-orb-anim="${p.anim | 0}"` +
            ` data-orb-nome="${esc(p.nome_completo || '')}" data-orb-nivel="${Number(extra.nivel) || ''}"` +
            ` data-orb-prox="${esc(p.proximo ? `${p.proximo.nome} no nível ${p.proximo.nivel}` : '')}"`;
        return `<span class="pt pt-anim-${p.anim | 0}" style="--pt-tam:${tam}px" ${atrib} tabindex="0">${svgPatente(p.id, p.sub, { anim: p.anim, pips: tam >= 34 })}</span>`;
    }

    // ---------------------------------------------------------------------
    // INSÍGNIAS (exclusivas: ver cosmeticos.py). Mesmo molde: id -> desenho.
    // ---------------------------------------------------------------------
    const BADGES = {
        criador:     { nome: 'Criador', desc: 'Quem criou o Panteão do zero.', cor: '#ffb62e' },
        beta_tester: { nome: 'Beta Tester', desc: 'Testou tudo antes de existir. Cada bug achado é uma medalha.', cor: '#34d399' },
        coder:       { nome: 'Coder', desc: 'Mexeu no código por baixo do capô.', cor: '#22d3ee' },
        so_nos:      { nome: 'Só nós', desc: 'Duas chamas, uma fusão. Só quem começou isso tem.', cor: '#e879f9' },
    };
    // Chama de 7 pontos (contorno em coordenadas 0-1, ponta em cima, "lambida" na esquerda), escalada pra caixa dada.
    const CHAMA = [[.50, 0], [.55, .18, .78, .28, .86, .55], [.94, .80, .78, 1, .50, 1], [.22, 1, .06, .80, .14, .55],
                   [.18, .42, .28, .38, .34, .28], [.36, .38, .42, .40, .45, .36], [.44, .22, .44, .10, .50, 0]];
    const chama = (cx, base, larg, alt, fill, cls = '') => {
        const X = (u) => (cx + (u - .5) * 2 * larg).toFixed(1), Y = (v) => (base - alt + v * alt).toFixed(1);
        let d = `M${X(CHAMA[0][0])} ${Y(CHAMA[0][1])}`;
        CHAMA.slice(1).forEach(([a, b, c, e, f, g]) => { d += ` C${X(a)} ${Y(b)} ${X(c)} ${Y(e)} ${X(f)} ${Y(g)}`; });
        return `<path class="${cls}" d="${d} Z" fill="${fill}"/>`;
    };

    const DESENHO_BADGE = {
        // coroa com chama
        criador: () => `
            <path d="M8 46 L12 20 L24 33 L32 12 L40 33 L52 20 L56 46 Z" fill="url(#bdg-ouro)" stroke="#7a3e05" stroke-width="1.8" stroke-linejoin="round"/>
            <path d="M8 46 L56 46 L54 54 L10 54 Z" fill="url(#bdg-ouro)" stroke="#7a3e05" stroke-width="1.8" stroke-linejoin="round"/>
            ${ponto(12, 20, 3, '#fff3b8')}${ponto(52, 20, 3, '#fff3b8')}${ponto(32, 12, 3.4, '#fff3b8')}
            ${chama(32, 44, 7.5, 17, '#ff6a1a', 'bd-chama')}${chama(32, 44, 4, 10, '#ffe27a', 'bd-chama bd-chama2')}
            <path d="M14 49.5 L50 49.5" stroke="#fff" stroke-width="1.2" opacity=".5"/>`,
        // selo com engrenagem e estrela
        beta_tester: () => {
            const dentes = [...Array(8)].map((_, i) => `<rect x="29" y="6" width="6" height="9" rx="1.4" transform="rotate(${i * 45} 32 32)" fill="url(#bdg-verde)" stroke="#065f46" stroke-width="1.2"/>`).join('');
            return `<g class="bd-gira">${dentes}<circle cx="32" cy="32" r="21" fill="url(#bdg-verde)" stroke="#065f46" stroke-width="1.8"/></g>
                <circle cx="32" cy="32" r="15" fill="#06382b"/>
                <path d="M32 19 L35.4 27.8 L44.8 28.4 L37.6 34.4 L40 43.6 L32 38.6 L24 43.6 L26.4 34.4 L19.2 28.4 L28.6 27.8 Z" fill="#fef9c3" stroke="#fde047" stroke-width="1" stroke-linejoin="round" class="bd-estrela"/>`;
        },
        // </> luminoso
        coder: () => `
            <path d="M32 4 L56 17 L56 47 L32 60 L8 47 L8 17 Z" fill="#0b1f2a" stroke="url(#bdg-ciano)" stroke-width="3" stroke-linejoin="round"/>
            <path d="M32 9 L51 19.5 L51 44.5 L32 55 L13 44.5 L13 19.5 Z" fill="none" stroke="#22d3ee" stroke-width=".9" opacity=".45"/>
            <g class="bd-codigo" fill="none" stroke="#67e8f9" stroke-width="4.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M23 24 L14.5 32 L23 40"/><path d="M41 24 L49.5 32 L41 40"/><path d="M35.5 22 L28.5 42" stroke="#a5f3fc" stroke-width="3.6"/>
            </g>`,
        // duas chamas que se fundem
        so_nos: () => `<g transform="translate(32 33) scale(1.28) translate(-32 -33)">
            <g class="bd-fl-a">${chama(22, 52, 11, 38, '#ff8a1f')}${chama(22, 52, 5.5, 22, '#ffd36b')}</g>
            <g class="bd-fl-b">${chama(42, 52, 11, 38, '#8b5cf6')}${chama(42, 52, 5.5, 22, '#d8b4fe')}</g>
            <g class="bd-fl-f">${chama(32, 54, 16, 46, 'url(#bdg-fusao)')}${chama(32, 54, 7.5, 28, '#fff2d6')}</g>
            <g class="bd-fa" fill="#fff"><circle cx="32" cy="14" r="1.6"/><circle cx="20" cy="22" r="1.1"/><circle cx="45" cy="20" r="1.2"/></g></g>`,
    };

    function svgBadge(id) {
        if (!DESENHO_BADGE[id]) return '';
        return `<svg viewBox="0 0 64 64" class="bd-svg bd-${id}" role="img" aria-label="Insígnia ${esc(BADGES[id].nome)}" focusable="false">${DESENHO_BADGE[id]()}</svg>`;
    }

    function htmlBadge(id, tamanho = 22) {
        if (!BADGES[id]) return '';
        const tam = Math.min(Math.max(parseInt(tamanho, 10) || 22, 12), 160);
        return `<span class="bd bd-wrap-${id}" style="--pt-tam:${tam}px;--bd-cor:${BADGES[id].cor}" data-orb="badge" data-orb-id="${id}" tabindex="0">${svgBadge(id)}</span>`;
    }

    function htmlBadges(ids, tamanho = 22) {
        return (Array.isArray(ids) ? ids : []).filter(i => BADGES[i]).map(i => htmlBadge(i, tamanho)).join('');
    }

    // ---------------------------------------------------------------------
    // POPOVER "ORB": ícone grande em cima, nome embaixo. Um só, delegado no document.
    // ---------------------------------------------------------------------
    let orbEl = null, orbAlvo = null, orbTimer = null;

    function conteudoOrb(el) {
        const tipo = el.dataset.orb, id = el.dataset.orbId;
        if (tipo === 'patente' && PAL[id]) {
            const sub = parseInt(el.dataset.orbSub, 10) || 1, anim = parseInt(el.dataset.orbAnim, 10) || 0;
            const nivel = el.dataset.orbNivel ? `Nível ${esc(el.dataset.orbNivel)}` : '';
            const prox = el.dataset.orbProx ? `Próxima evolução: ${esc(el.dataset.orbProx)}` : (nivel ? 'Patente máxima' : '');
            return `<div class="orb-ico pt pt-anim-${anim}" style="--pt-tam:112px">${svgPatente(id, sub, { anim, pips: true })}</div>
                <div class="orb-rotulo">Patente</div>
                <div class="orb-nome">${esc(el.dataset.orbNome || '')}</div>
                ${nivel ? `<div class="orb-linha">${nivel}</div>` : ''}
                ${prox ? `<div class="orb-linha suave">${prox}</div>` : ''}`;
        }
        if (tipo === 'badge' && BADGES[id]) {
            const b = BADGES[id];
            return `<div class="orb-ico bd bd-wrap-${id} orb-grande" style="--pt-tam:112px;--bd-cor:${b.cor}">${svgBadge(id)}</div>
                <div class="orb-rotulo">Insígnia</div>
                <div class="orb-nome">${esc(b.nome)}</div>
                <div class="orb-linha">${esc(b.desc)}</div>`;
        }
        if (tipo === 'texto') {
            return `<div class="orb-nome pequeno">${esc(el.dataset.orbNome || '')}</div>${el.dataset.orbDesc ? `<div class="orb-linha">${esc(el.dataset.orbDesc)}</div>` : ''}`;
        }
        return '';
    }

    function posicionarOrb() {
        if (!orbEl || !orbAlvo) return;
        const r = orbAlvo.getBoundingClientRect();
        const w = orbEl.offsetWidth, h = orbEl.offsetHeight;
        let left = r.left + r.width / 2 - w / 2;
        let top = r.top - h - 12;
        let abaixo = false;
        if (top < 8) { top = r.bottom + 12; abaixo = true; }
        left = Math.min(Math.max(8, left), window.innerWidth - w - 8);
        orbEl.style.left = left + 'px';
        orbEl.style.top = top + 'px';
        orbEl.classList.toggle('abaixo', abaixo);
        orbEl.style.setProperty('--seta', Math.min(Math.max(14, r.left + r.width / 2 - left), w - 14) + 'px');
    }

    function mostrarOrb(el) {
        const html = conteudoOrb(el);
        if (!html) return;
        if (!orbEl) {
            orbEl = document.createElement('div');
            orbEl.id = 'orb-pop';
            orbEl.setAttribute('role', 'tooltip');
            document.body.appendChild(orbEl);
        }
        clearTimeout(orbTimer);
        orbAlvo = el;
        orbEl.innerHTML = html;
        orbEl.style.visibility = 'hidden';
        orbEl.classList.remove('on');
        orbEl.style.display = 'block';
        posicionarOrb();
        orbEl.style.visibility = 'visible';
        requestAnimationFrame(() => orbEl && orbEl.classList.add('on'));
    }

    function esconderOrb() {
        if (!orbEl) return;
        orbAlvo = null;
        orbEl.classList.remove('on');
        clearTimeout(orbTimer);
        orbTimer = setTimeout(() => { if (orbEl && !orbAlvo) orbEl.style.display = 'none'; }, 160);
    }

    function ligarOrb() {
        document.addEventListener('mouseover', (e) => {
            const el = e.target.closest && e.target.closest('[data-orb]');
            if (el && el !== orbAlvo) mostrarOrb(el);
            else if (!el && orbAlvo) esconderOrb();
        });
        document.addEventListener('focusin', (e) => { const el = e.target.closest && e.target.closest('[data-orb]'); if (el) mostrarOrb(el); });
        document.addEventListener('focusout', esconderOrb);
        // celular: toque abre; toque fora fecha
        document.addEventListener('touchstart', (e) => {
            const el = e.target.closest && e.target.closest('[data-orb]');
            if (el) mostrarOrb(el); else esconderOrb();
        }, { passive: true });
        window.addEventListener('scroll', esconderOrb, true);
        window.addEventListener('resize', esconderOrb);
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') esconderOrb(); });
    }

    // ---------------------------------------------------------------------
    // EFEITOS (avatar / cartão): só ids do catálogo viram classe; o desenho é CSS.
    // ---------------------------------------------------------------------
    const idOk = (v) => /^[a-z_]{1,24}$/.test(String(v || ''));
    const EFEITOS_AVATAR = ['gogeta', 'sasuke'];
    const EFEITOS_PERFIL = ['gogeta', 'sasuke'];

    function htmlEfeitoAvatar(id) {
        if (!EFEITOS_AVATAR.includes(id)) return '';
        if (id === 'sasuke') return '<i class="ef-av ef-av-sasuke" aria-hidden="true"></i>';   // olho brilhante: só CSS (anel que acende em vermelho)
        return `<i class="ef-av ef-av-${id}" aria-hidden="true"><b></b><b></b></i>`;
    }

    // Efeito por cima do cartão. Os de partículas fixas são determinísticos (o cartão redesenha a cada mudança e não pode
    // "pular"); os raios do Sasuke sorteiam uma posição nova a cada ciclo (ver `sortearPosicao`), então aparecem
    // "do nada" em lugares diferentes.
    function htmlEfeitoPerfil(id) {
        if (!EFEITOS_PERFIL.includes(id)) return '';
        if (id === 'sasuke') {
            const caminhos = ['M12 0 L7 22 L15 24 L6 52 L16 54 L4 96', 'M10 0 L14 18 L6 30 L13 46 L5 70',
                              'M14 0 L8 16 L16 30 L9 44 L17 62 L10 84', 'M12 0 L16 20 L8 28 L15 50 L9 62 L13 90'];
            // x%, altura%, largura px, período s, atraso s
            const raios = [[4, 62, 34, 3.7, 0.4], [15, 48, 28, 5.3, 1.9], [29, 70, 38, 4.1, 2.6], [43, 40, 26, 7.3, 0.9], [58, 58, 32, 6.1, 3.3],
                           [70, 66, 36, 4.9, 1.2], [82, 44, 28, 8.3, 4.1], [92, 54, 30, 5.9, 2.2]];
            const bolts = raios.map(([x, h, w, t, d], i) => {
                const c = caminhos[i % caminhos.length];
                return `<svg class="ef-raio" data-aleatorio="efRaioPisca" style="left:${x}%;height:${h}%;width:${w}px;--t:${t}s;--d:${d}s" viewBox="0 0 24 100" preserveAspectRatio="none"><path pathLength="100" d="${c}" fill="none" stroke="#8b5cf6" stroke-width="6" opacity=".45" stroke-linejoin="round" stroke-linecap="round"/><path pathLength="100" d="${c}" fill="none" stroke="#f5f3ff" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
            }).join('');
            return `<div class="ef-pf ef-pf-sasuke" aria-hidden="true"><i class="ef-pf-clarao"></i><canvas class="ef-cv" data-ef="amaterasu"></canvas>${bolts}</div>`;
        }
        const n = 22;
        let ps = '';
        for (let i = 0; i < n; i++) {
            const x = (i * 37 + 11) % 100, atraso = ((i * 53) % 40) / 10, dur = 3.2 + ((i * 29) % 30) / 10, tam = 2 + (i * 7) % 4;
            ps += `<i style="--x:${x}%;--d:-${atraso}s;--t:${dur}s;--s:${tam}px"></i>`;
        }
        // + a Punição de Alma (partículas giram, viram a bolha colorida e estouram) num canvas por cima da poeira
        return `<div class="ef-pf ef-pf-${id}" aria-hidden="true">${ps}<canvas class="ef-cv" data-ef="punicao"></canvas></div>`;
    }

    // Raios do Sasuke: ao fim de cada ciclo (invisíveis), cada um sorteia onde vai cair da próxima vez.
    function sortearPosicao(e) {
        const t = e.target;
        if (!t || !t.dataset || !t.dataset.aleatorio || e.animationName !== t.dataset.aleatorio) return;
        const r = (min, max) => min + Math.random() * (max - min);
        if (t.classList.contains('ef-raio')) {
            t.style.left = r(2, 92).toFixed(1) + '%';
        }
    }

    // ---------------------------------------------------------------------
    // SLOTS DE COMPORTAMENTO: fala (call), radar (mapa), chat (digitar/enviar), som de entrada, pin de nota.
    // Só ids conhecidos viram classe; o desenho é CSS (e Web Audio sintetizado pro som: nada de arquivo).
    // ---------------------------------------------------------------------
    const IDS_EFEITO = {
        fala: ['gogeta', 'sasuke'], radar: ['gogeta', 'sasuke'], chat: ['gogeta', 'sasuke'],
        som: ['gogeta', 'sasuke'], pin: ['gogeta', 'sasuke'], servidor: ['gogeta', 'sasuke', 'fusao'],
    };
    const classeDe = (pref, tipo, id) => (IDS_EFEITO[tipo] || []).includes(id) ? `${pref}-${id}` : '';
    const classeFala = (id) => classeDe('fala', 'fala', id);
    const classeRadar = (id) => classeDe('radar', 'radar', id);
    const classePin = (id) => classeDe('pin', 'pin', id);
    const classeServidor = (id) => classeDe('sv-ef', 'servidor', id);            // ícone do servidor / pino no mapa
    const classeNomeServidor = (id) => classeDe('ne', 'servidor', id);          // nome no cabeçalho (reaproveita os estilos de nome)

    // --- som de entrada na call (sintetizado; ctx = AudioContext ou OfflineAudioContext) ---
    // Sons de entrada que vêm de arquivo (static/audio). Se o arquivo falhar, cai no som sintetizado abaixo.
    const ARQ_SOM = { gogeta: ['/static/audio/teleporte.mp3', .8], sasuke: ['/static/audio/sharingan.mp3', .8] };
    const _cacheSom = {};
    function tocarArquivoSom(id) {
        try {
            const [url, vol] = ARQ_SOM[id];
            const base = _cacheSom[id] || (_cacheSom[id] = Object.assign(new Audio(url), { preload: 'auto' }));
            const a = base.cloneNode(); a.volume = vol;
            a.play().catch(() => {});
            return true;
        } catch (e) { return false; }
    }
    function somEntrada(id, ctx, destino) {
        if (!IDS_EFEITO.som.includes(id) || !ctx) return 0;
        if (ARQ_SOM[id] && !(typeof OfflineAudioContext !== 'undefined' && ctx instanceof OfflineAudioContext) && tocarArquivoSom(id)) return 2;
        const t0 = ctx.currentTime;
        const mestre = ctx.createGain();
        mestre.gain.value = 0.2;
        mestre.connect(destino || ctx.destination);
        const env = (g, ataque, pico, segura, fim, topo = pico) => {
            g.gain.setValueAtTime(0.0001, t0);
            g.gain.exponentialRampToValueAtTime(pico, t0 + ataque);
            g.gain.setValueAtTime(topo, t0 + segura);
            g.gain.exponentialRampToValueAtTime(0.0001, t0 + fim);
        };
        if (id === 'gogeta') {
            // Power Up: dente-de-serra subindo com o filtro abrindo, e um brilho no fim
            const o = ctx.createOscillator(); o.type = 'sawtooth';
            o.frequency.setValueAtTime(110, t0); o.frequency.exponentialRampToValueAtTime(880, t0 + .75);
            const f = ctx.createBiquadFilter(); f.type = 'lowpass'; f.Q.value = 4;
            f.frequency.setValueAtTime(300, t0); f.frequency.exponentialRampToValueAtTime(5200, t0 + .75);
            const g = ctx.createGain(); env(g, .15, .9, .62, 1.05);
            o.connect(f); f.connect(g); g.connect(mestre); o.start(t0); o.stop(t0 + 1.1);
            [1568, 2093, 2637].forEach((fr, i) => {
                const s = ctx.createOscillator(), gs = ctx.createGain(); s.type = 'sine'; s.frequency.value = fr;
                const ini = t0 + .68 + i * .07;
                gs.gain.setValueAtTime(0.0001, ini); gs.gain.exponentialRampToValueAtTime(.35, ini + .02); gs.gain.exponentialRampToValueAtTime(0.0001, ini + .4);
                s.connect(gs); gs.connect(mestre); s.start(ini); s.stop(ini + .45);
            });
            return 1.2;
        }
        // Chidori: rajadas curtas de ruído (o estalo) + um zumbido grave de corrente
        const dur = .95;
        const buf = ctx.createBuffer(1, Math.floor(ctx.sampleRate * dur), ctx.sampleRate);
        const dados = buf.getChannelData(0);
        for (let i = 0; i < dados.length; i++) dados[i] = Math.random() * 2 - 1;
        const ruido = ctx.createBufferSource(); ruido.buffer = buf;
        const bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = 3600; bp.Q.value = 1.1;
        const gr = ctx.createGain();
        gr.gain.setValueAtTime(0.0001, t0);
        for (let i = 0; i < 12; i++) {
            const ini = t0 + i * .068 + (i % 3) * .008;
            gr.gain.setValueAtTime(0.0001, ini);
            gr.gain.exponentialRampToValueAtTime(.95 - i * .045, ini + .006);
            gr.gain.exponentialRampToValueAtTime(0.0001, ini + .04);
        }
        ruido.connect(bp); bp.connect(gr); gr.connect(mestre); ruido.start(t0);
        const z = ctx.createOscillator(); z.type = 'sawtooth'; z.frequency.value = 72;
        const lfo = ctx.createOscillator(), lfoG = ctx.createGain(); lfo.frequency.value = 38; lfoG.gain.value = 40;
        lfo.connect(lfoG); lfoG.connect(z.frequency);
        const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 420;
        const gz = ctx.createGain(); env(gz, .05, .5, .5, .9);
        z.connect(lp); lp.connect(gz); gz.connect(mestre); z.start(t0); z.stop(t0 + 1); lfo.start(t0); lfo.stop(t0 + 1);
        return dur;
    }

    // --- efeito de envio (some sozinho): faíscas douradas subindo / um raio roxo cruzando a barra ---
    function efeitoEnvio(id, alvo) {
        if (!IDS_EFEITO.chat.includes(id) || !alvo || !alvo.getBoundingClientRect) return;
        const r = alvo.getBoundingClientRect();
        if (!r.width) return;
        const box = document.createElement('div');
        box.className = `ef-envio ef-envio-${id}`;
        box.style.cssText = `left:${r.left}px;top:${r.top}px;width:${r.width}px;height:${r.height}px;`;
        if (id === 'sasuke') {
            const pts = []; const n = 14;
            for (let i = 0; i <= n; i++) pts.push(`${(i / n * 100).toFixed(1)},${(i % 2 ? 22 : 78) + ((i * 37) % 13) - 6}`);
            box.innerHTML = `<svg viewBox="0 0 100 100" preserveAspectRatio="none"><polyline points="${pts.join(' ')}" fill="none" stroke="#8b5cf6" stroke-width="5" opacity=".55" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/><polyline points="${pts.join(' ')}" fill="none" stroke="#f5f3ff" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg><i class="ef-envio-clarao"></i>`;
        } else {
            let h = '';
            for (let i = 0; i < 18; i++) {
                const x = Math.random() * 100, dx = (Math.random() - .5) * 60, dy = 40 + Math.random() * 90, t = .5 + Math.random() * .4, s = 2 + Math.random() * 4;
                h += `<i style="left:${x.toFixed(1)}%;--dx:${dx.toFixed(0)}px;--dy:-${dy.toFixed(0)}px;--t:${t.toFixed(2)}s;width:${s.toFixed(1)}px;height:${s.toFixed(1)}px"></i>`;
            }
            box.innerHTML = h;
        }
        document.body.appendChild(box);
        setTimeout(() => box.remove(), 1000);
    }

    // --- efeito do chat: brilho enquanto digita (classe no container) + efeito ao enviar (Enter / botão) ---
    let _chatLigado = false, _chatPegarId = () => null;
    function ligarEfeitoChat(pegarId) {
        _chatPegarId = pegarId;
        if (_chatLigado) return;
        _chatLigado = true;
        document.addEventListener('input', (e) => {
            const t = e.target;
            if (!t.classList || !t.classList.contains('chat-input')) return;
            const cont = t.closest('.chat-input-container');
            if (!cont || !classeDe('chat-ef', 'chat', _chatPegarId())) return;
            cont.classList.add('digitando');
            clearTimeout(cont._digTimer);
            cont._digTimer = setTimeout(() => cont.classList.remove('digitando'), 1400);
        });
        // fase de captura: roda antes do envio limpar o campo
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter' || e.shiftKey || e.isComposing) return;
            const t = e.target;
            if (!t.classList || !t.classList.contains('chat-input') || !String(t.value || '').trim()) return;
            efeitoEnvio(_chatPegarId(), t.closest('.chat-input-container'));
        }, true);
        document.addEventListener('click', (e) => {
            const b = e.target.closest && e.target.closest('.dm-enviar');
            if (!b) return;
            const cont = b.closest('.chat-input-container'), campo = cont && cont.querySelector('.chat-input');
            if (campo && String(campo.value || '').trim()) efeitoEnvio(_chatPegarId(), cont);
        }, true);
    }
    function aplicarEfeitoChat(id) {
        const cls = classeDe('chat-ef', 'chat', id);
        document.querySelectorAll('.chat-input-container').forEach(c => {
            [...c.classList].filter(x => x.startsWith('chat-ef-')).forEach(x => c.classList.remove(x));
            if (cls) c.classList.add(cls);
        });
    }

    // ---------------------------------------------------------------------
    // INVENTÁRIO (aba nas Configurações e atalho na barra lateral)
    // ---------------------------------------------------------------------
    const INV_ABAS = [['tudo', 'Tudo'], ['badge', 'Insígnias'], ['moldura', 'Molduras'], ['placa', 'Placas'], ['nome', 'Nomes'],
                      ['faixa', 'Faixas'], ['efeito', 'Efeitos'], ['pacote', 'Pacotes'], ['patentes', 'Patentes']];
    const TIPOS_EFEITO = ['efeito_avatar', 'efeito_perfil', 'efeito_fala', 'efeito_radar', 'efeito_chat', 'som_call', 'pin_nota', 'efeito_servidor'];
    const ROTULO_TIPO = { badge: 'Insígnia', moldura: 'Moldura', placa: 'Placa', nome: 'Estilo de nome', faixa: 'Faixa', efeito_avatar: 'Efeito de avatar',
        efeito_perfil: 'Efeito de perfil', efeito_fala: 'Efeito de fala', efeito_radar: 'Efeito do radar', efeito_chat: 'Efeito do chat',
        som_call: 'Som de entrada', pin_nota: 'Pin de nota', efeito_servidor: 'Efeito de servidor', pacote: 'Pacote de tema' };
    const ICONE_TIPO = { efeito_fala: 'fa-microphone-lines', efeito_radar: 'fa-satellite-dish', efeito_chat: 'fa-keyboard', som_call: 'fa-volume-high', pin_nota: 'fa-location-dot', pacote: 'fa-box-open' };
    const NOME_TEMA = { gogeta: 'Gogeta', sasuke: 'Sasuke', fusao: 'Fusão' };

    function previaItem(it, ctx) {
        const v = it.valor;
        if (!idOk(v)) return '';
        const av = ctx.avatarHtml, nome = esc(ctx.nome);
        switch (it.tipo) {
            case 'moldura': return `<span class="pf-tile-av moldura-${v}">${av}</span>`;
            case 'placa': return `<span class="pf-placa-linha placa-${v}"><span class="pf-mini-av">${av}</span><span>${nome}</span></span>`;
            case 'nome': return `<span class="inv-nome-prev"><span class="cat-nome ne-${v}">${nome}</span></span>`;
            case 'faixa': return `<span class="inv-faixa banner-anim-${v}"></span>`;
            case 'badge': return htmlBadge(v, 56);
            case 'efeito_avatar': return `<span class="inv-av-ef">${htmlEfeitoAvatar(v)}<span class="inv-av-img">${av}</span></span>`;
            case 'efeito_perfil': return `<span class="inv-perfil-ef"><span class="inv-perfil-fundo"></span>${htmlEfeitoPerfil(v)}</span>`;
            case 'efeito_servidor': return `<span class="inv-servidor sv-ef-${v}"><b>SE</b></span>`;
            case 'efeito_fala': return `<span class="inv-av-ef inv-fala fala-${v}"><span class="inv-av-img">${av}</span></span>`;
            case 'efeito_radar': return `<span class="inv-radar radar-${v}"><i></i><i></i><i></i><b></b></span>`;
            case 'efeito_chat': return `<span class="inv-chat chat-ef-${v} digitando"><span>Digitando…</span></span>`;
            case 'pin_nota': return `<span class="inv-pin"><span class="geo-note-bubble minimized pin-${v}" style="--note-color:#5865F2"><span class="note-emoji">💬</span></span></span>`;
            case 'som_call': return `<button type="button" class="inv-ouvir" data-acao="ouvir" data-som="${v}"><i class="fa-solid fa-play"></i> Ouvir</button>`;
            case 'pacote': {
                const cor = (ctx.temas[v] || {}).cor || '#7289da';
                return `<span class="inv-pacote" style="--tema:${esc(cor)}"><i class="fa-solid fa-box-open"></i></span>`;
            }
            default: return `<span class="inv-icone"><i class="fa-solid ${ICONE_TIPO[it.tipo] || 'fa-star'}"></i></span>`;
        }
    }

    function tileItem(it, ctx) {
        const eq = ctx.equipados[it.tipo] === it.valor;
        const sub = ROTULO_TIPO[it.tipo] + (it.tema ? ' · ' + (NOME_TEMA[it.tema] || '') : '');
        const emUso = it.tipo === 'efeito_servidor' && ctx.servidoresComEfeito ? ctx.servidoresComEfeito(it.valor) : [];
        const acao = it.tipo === 'badge'
            ? '<span class="inv-fixo"><i class="fa-solid fa-circle-check"></i> Sempre visível</span>'
            : it.tipo === 'efeito_servidor'
            ? `${emUso.length ? `<span class="inv-fixo"><i class="fa-solid fa-circle-check"></i> Em uso: ${esc(emUso.join(', '))}</span>` : ''}<button type="button" class="inv-btn" data-acao="servidor">Aplicar a um servidor</button>`
            : (eq ? '<button type="button" class="inv-btn eq" data-acao="remover">Equipado · remover</button>'
                  : '<button type="button" class="inv-btn" data-acao="equipar">Equipar</button>');
        return `<div class="inv-item ${eq ? 'eq' : ''} rar-${esc(it.raridade || 'comum')}" data-item="${esc(it.id)}" data-tipo="${esc(it.tipo)}">
            ${it.exclusivo ? '<span class="inv-selo" title="Exclusivo do laboratório"><i class="fa-solid fa-gem"></i></span>' : ''}
            <div class="inv-prev">${previaItem(it, ctx)}</div>
            <div class="inv-nome">${esc(it.nome)}</div>
            <div class="inv-sub">${esc(sub)}</div>
            ${it.desc ? `<div class="inv-desc">${esc(it.desc)}</div>` : ''}
            ${acao}
        </div>`;
    }

    function htmlPatentesInv(estado) {
        const nivel = estado.nivel;
        return `<div class="inv-pat-grade">${estado.patentes.map(p => {
            const atual = nivel >= p.de && (p.ate == null || nivel <= p.ate);
            const alcancada = nivel >= p.de;
            const faixa = p.ate == null ? `Nível ${p.de}+` : `Níveis ${p.de} a ${p.ate}`;
            return `<div class="inv-pat ${atual ? 'atual' : ''} ${alcancada ? '' : 'trancada'}">
                <div class="inv-pat-icos">${[0, 1, 2].map(k => {
                    const ok = nivel >= p.limites[k];
                    const pat = { id: p.id, sub: k + 1, anim: p.anim, nome_completo: `${p.nome} ${ROMANOS[k]}`, proximo: null };
                    return `<span class="inv-pat-sub ${ok ? '' : 'bloq'}" title="${esc(pat.nome_completo)} · nível ${p.limites[k]}">${htmlPatente(pat, 46, { nivel: p.limites[k] })}</span>`;
                }).join('')}</div>
                <div class="inv-pat-nome">${esc(p.nome)}${atual ? ' <small>você está aqui</small>' : ''}</div>
                <div class="inv-pat-faixa">${faixa}</div>
            </div>`;
        }).join('')}</div>`;
    }

    /** Desenha o inventário em `el`. ctx: { livres:[{tipo,valor,nome}], nome, avatarHtml, aba, temas, aoEquipar(id), aoRemover(tipo), aoAba(aba) } */
    function renderInventario(el, estado, ctx) {
        if (!el || !estado) return;
        ctx.temas = ctx.temas || {};
        ctx.equipados = estado.equipados || {};
        el._invCtx = ctx;          // o clique (ligado uma vez só) sempre lê o contexto mais recente
        const aba = ctx.aba || 'tudo';

        const exclusivos = (estado.catalogo || []).map(d => ({ ...d, exclusivo: true }));
        const livres = (ctx.livres || []).map(d => ({ id: `${d.tipo}:${d.valor}`, tipo: d.tipo, valor: d.valor, nome: d.nome, raridade: 'comum', exclusivo: false }));
        const dentro = (it) => aba === 'tudo' || it.tipo === aba || (aba === 'efeito' && TIPOS_EFEITO.includes(it.tipo));

        let corpo;
        if (aba === 'patentes') {
            corpo = `<p class="inv-dica">Seu nível é a experiência total acumulada, de 1 a 1000+. A patente muda a cada faixa e o ícone ganha mais animação quanto maior ela for. Passe o mouse num ícone pra ver o nome.</p><button type="button" class="inv-btn" data-acao="montanha" style="margin:0 0 14px"><i class="fa-solid fa-mountain-sun"></i> Ver a montanha das patentes</button>${htmlPatentesInv(estado)}`;
        } else {
            const ex = exclusivos.filter(dentro), li = livres.filter(dentro);
            const sec = (titulo, lista, dica) => lista.length
                ? `<div class="inv-sec"><div class="inv-sec-tit">${titulo} <small>${lista.length}</small></div>${dica ? `<p class="inv-dica">${dica}</p>` : ''}<div class="inv-grade">${lista.map(i => tileItem(i, ctx)).join('')}</div></div>` : '';
            corpo = sec('Exclusivos', ex, aba === 'tudo' ? 'Só você (e quem recebeu junto) tem estes. O servidor confere a posse antes de deixar equipar.' : '')
                + sec('Livres', li);
            if (!ex.length && !li.length) corpo = '<div class="inv-vazio"><i class="fa-regular fa-face-meh"></i><br>Nada por aqui ainda.</div>';
        }

        el.innerHTML = `<div class="inv-topo">
            <div class="inv-abas" role="tablist">${INV_ABAS.map(([id, rot]) => `<button type="button" role="tab" class="inv-aba ${id === aba ? 'on' : ''}" data-aba="${id}">${rot}</button>`).join('')}</div>
            <div class="inv-resumo"><b>${exclusivos.length}</b> exclusivo${exclusivos.length === 1 ? '' : 's'} · ${livres.length} livres</div>
        </div>${corpo}`;

        if (!el._invLigado) {
            el._invLigado = true;
            el.addEventListener('click', (e) => {
                const c = el._invCtx;
                const aba2 = e.target.closest('.inv-aba');
                if (aba2) { c.aoAba && c.aoAba(aba2.dataset.aba); return; }
                if (e.target.closest('[data-acao="montanha"]')) { c.aoMontanha && c.aoMontanha(); return; }
                const srvBtn = e.target.closest('[data-acao="servidor"]');
                if (srvBtn) { c.aoServidor && c.aoServidor(srvBtn.closest('.inv-item').dataset.item.split(':')[1]); return; }
                const ouvir = e.target.closest('[data-acao="ouvir"]');
                if (ouvir) { c.aoOuvir && c.aoOuvir(ouvir.dataset.som); return; }
                const it = e.target.closest('.inv-item');
                if (!it || it.dataset.tipo === 'badge' || it.dataset.tipo === 'efeito_servidor') return;
                if (it.classList.contains('eq')) { c.aoRemover && c.aoRemover(it.dataset.tipo); return; }
                c.aoEquipar && c.aoEquipar(it.dataset.item);
            });
        }
    }

    // ---------------------------------------------------------------------
    // MONTANHA DAS PATENTES: tela cheia, rola pra cima. As patentes estão "cravadas" na montanha no nível que pedem; cada uma
    // CAI e faz um estrondo (mais forte, mas contido, quanto mais alta). Nuvens e aves passam; lá em cima nasce o sol.
    // ---------------------------------------------------------------------
    const MT_BASE = 560, MT_PASSO = 400, MT_TOPO = 900;      // px: chão até a 1ª patente, entre patentes, folga no topo

    /** Estrondo sintetizado (grave + ruído). forca 0-1. */
    function somImpacto(ctx, forca) {
        if (!ctx) return;
        const f = Math.min(Math.max(forca, 0.1), 1), t0 = ctx.currentTime;
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.type = 'sine'; o.frequency.setValueAtTime(95, t0); o.frequency.exponentialRampToValueAtTime(34, t0 + .38);
        g.gain.setValueAtTime(0.0001, t0); g.gain.exponentialRampToValueAtTime(.16 + .34 * f, t0 + .02); g.gain.exponentialRampToValueAtTime(0.0001, t0 + .5);
        o.connect(g); g.connect(ctx.destination); o.start(t0); o.stop(t0 + .55);
        const buf = ctx.createBuffer(1, Math.floor(ctx.sampleRate * .3), ctx.sampleRate), d = buf.getChannelData(0);
        for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / d.length);
        const r = ctx.createBufferSource(); r.buffer = buf;
        const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 260 + 500 * f;
        const gr = ctx.createGain(); gr.gain.value = .12 + .3 * f;
        r.connect(lp); lp.connect(gr); gr.connect(ctx.destination); r.start(t0);
    }

    let _mtFechar = null;

    /** op: { patentes (tabela do servidor), nivel, patente (atual), impacto(forca) } */
    function abrirMontanha(op) {
        if (_mtFechar) _mtFechar();
        const pats = op.patentes || [];
        if (!pats.length) return;
        const N = pats.length, H = MT_BASE + (N - 1) * MT_PASSO + MT_TOPO;
        const reduz = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
        const nivel = Math.max(parseInt(op.nivel, 10) || 1, 1);

        // x (em %) de cada estação: zigue-zague que vai fechando conforme a montanha estreita
        const xDe = (i) => 50 + (i % 2 ? 1 : -1) * (21 - (i / Math.max(N - 1, 1)) * 9);
        const yDe = (i) => MT_BASE + i * MT_PASSO;                          // distância do chão

        // onde a pessoa está (entre a estação da patente dela e a próxima)
        let pi = 0;
        pats.forEach((p, i) => { if (nivel >= p.de) pi = i; });
        const p0 = pats[pi];
        const frac = p0.ate == null ? Math.min((nivel - p0.de) / 300, 1) : Math.min((nivel - p0.de) / (p0.ate - p0.de + 1), 1);
        const yEu = yDe(pi) + (pi < N - 1 ? frac * MT_PASSO : frac * 260);

        // ---- silhueta arredondada da montanha (sem pontas) ----
        const yTopo = H - (yDe(N - 1) + 300), alt = H - yTopo;
        // paredão largo que vai afinando devagar e fecha numa cúpula arredondada no topo (nada de ponta)
        const meia = (t) => {
            const base = 400 - 70 * Math.min(t / .82, 1) + 22 * Math.sin(t * 41) + 12 * Math.sin(t * 13);
            if (t <= .82) return base;
            const u = (t - .82) / .18;
            return Math.max(base * Math.sqrt(Math.max(1 - u * u, 0)), 0);
        };
        const esq = [], dir = [];
        for (let k = 0; k <= 48; k++) {
            const t = k / 48, y = H - t * alt, m = meia(t);
            esq.push([500 - m + 10 * Math.sin(t * 9), y]); dir.push([500 + m + 10 * Math.cos(t * 7), y]);
        }
        let d = `M${esq[0][0].toFixed(1)} ${H}`;
        esq.forEach(([x, y]) => { d += ` L${x.toFixed(1)} ${y.toFixed(1)}`; });
        for (let k = dir.length - 1; k >= 0; k--) d += ` L${dir[k][0].toFixed(1)} ${dir[k][1].toFixed(1)}`;
        d += ` L${dir[0][0].toFixed(1)} ${H} Z`;
        const colina = (cx, larg, h, cor) => `<path d="M${cx - larg} ${H} C${cx - larg * .6} ${H - h} ${cx + larg * .6} ${H - h} ${cx + larg} ${H} Z" fill="${cor}"/>`;
        const montanhaLonge = (cx, larg, h, cor) => `<path d="M${cx - larg} ${H} C${cx - larg * .55} ${H - h * 1.05} ${cx - larg * .2} ${H - h} ${cx} ${H - h} C${cx + larg * .2} ${H - h} ${cx + larg * .55} ${H - h * 1.05} ${cx + larg} ${H} Z" fill="${cor}"/>`;

        // trilha: pontos das estações; a parte já percorrida é dourada e termina na pessoa
        const pt = (i) => [xDe(i) * 10, H - yDe(i) - 70];
        const todos = pats.map((_, i) => pt(i));
        const eu = [(pi % 2 ? 1 : -1) * 0 + 500, H - yEu];
        const feitos = [[500, H - 90], ...todos.slice(0, pi + 1), eu];
        const linha = (pts) => 'M' + pts.map(([x, y]) => `${x.toFixed(0)} ${y.toFixed(0)}`).join(' L');

        const estrelas = [...Array(46)].map((_, i) => `<i class="mt-estrela" style="left:${(i * 53 + 7) % 100}%;bottom:${(i * 97) % 1900 + 20}px;--t:${2 + (i % 5)}s;--d:-${i % 7}s"></i>`).join('');
        const nuvens = [...Array(9)].map((_, i) => {
            const b = 300 + i * ((H - 800) / 9) + ((i * 131) % 160), w = 190 + (i * 47) % 150, t = 70 + (i * 23) % 70;
            return `<div class="mt-nuvem ${i % 3 === 0 ? 'frente' : ''}" style="bottom:${b.toFixed(0)}px;width:${w}px;height:${(w * .36).toFixed(0)}px;--t:${t}s;--d:-${(i * 17) % t}s"></div>`;
        }).join('');
        const aves = [...Array(7)].map((_, i) => {
            const b = 500 + i * ((H - 900) / 7) + ((i * 89) % 200), t = 16 + (i * 5) % 14;
            return `<svg class="mt-ave" viewBox="0 0 28 12" style="bottom:${b.toFixed(0)}px;--t:${t}s;--d:-${(i * 7) % t}s;--e:${i % 2 ? 1 : -1}"><path d="M1 8 Q7 0 14 7 Q21 0 27 8" fill="none" stroke="#1d1a2b" stroke-width="1.8" stroke-linecap="round"/></svg>`;
        }).join('');

        const est = pats.map((p, i) => {
            const alcancada = nivel >= p.de;
            const subs = [0, 1, 2].map(k => {
                const pat = { id: p.id, sub: k + 1, anim: p.anim, nome_completo: `${p.nome} ${ROMANOS[k]}`, proximo: null };
                return `<div class="mt-col ${nivel >= p.limites[k] ? '' : 'longe'}" style="--d:${k * 140}ms">
                    <div class="mt-queda">${htmlPatente(pat, 62, { nivel: p.limites[k] })}</div>
                    <div class="mt-placa"><b>${ROMANOS[k]}</b> Nv. ${p.limites[k]}</div></div>`;
            }).join('');
            return `<div class="mt-est ${alcancada ? '' : 'longe-est'}" data-i="${i}" style="left:${xDe(i).toFixed(1)}%;bottom:${yDe(i)}px;--f:${(1.2 + (i / Math.max(N - 1, 1)) * 5).toFixed(1)}">
                <div class="mt-nome" style="--cor:${esc(p.cor || '#fff')}">${esc(p.nome)}<small>${p.ate == null ? `Nível ${p.de}+` : `Níveis ${p.de} a ${p.ate}`}</small></div>
                <div class="mt-icos">${subs}</div><div class="mt-pedra"></div></div>`;
        }).join('');

        const ov = document.createElement('div');
        ov.id = 'montanha'; ov.className = 'mt'; ov.setAttribute('role', 'dialog'); ov.setAttribute('aria-label', 'Montanha das patentes');
        ov.innerHTML = `
            <div class="mt-topo">
                <div class="mt-tit"><b>Montanha das Patentes</b><small>Você está no nível ${nivel} · ${esc((op.patente && op.patente.nome_completo) || p0.nome)}</small></div>
                <button type="button" class="mt-pos"><i class="fa-solid fa-location-crosshairs"></i> Minha posição</button>
                <div class="mt-fechar"><button type="button" class="mt-x" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button><span>ESC</span></div>
            </div>
            <div class="mt-cena"><div class="mt-mundo" style="height:${H}px">
                <div class="mt-ceu"></div>
                <div class="mt-estrelas">${estrelas}</div>
                <div class="mt-sol" style="top:${Math.max(yTopo - 520, 40)}px"><div class="mt-sol-raios"></div><div class="mt-sol-disco"></div></div>
                <svg class="mt-svg mt-par" style="--k:.2" viewBox="0 0 1000 ${H}" preserveAspectRatio="none">${montanhaLonge(110, 260, 380, '#2a2f55')}${montanhaLonge(900, 300, 440, '#2b2c58')}</svg>
                <svg class="mt-svg mt-par" style="--k:.1" viewBox="0 0 1000 ${H}" preserveAspectRatio="none">${montanhaLonge(40, 230, 250, '#3a3260')}${montanhaLonge(960, 260, 300, '#3c3363')}</svg>
                <svg class="mt-svg" viewBox="0 0 1000 ${H}" preserveAspectRatio="none">
                    <defs>
                        <linearGradient id="mt-g-pedra" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#2f2626"/><stop offset=".3" stop-color="#574c55"/><stop offset=".65" stop-color="#9a93a8"/><stop offset="1" stop-color="#e3dff0"/></linearGradient>
                        <linearGradient id="mt-g-neve" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>
                        <clipPath id="mt-clip"><path d="${d}"/></clipPath>
                    </defs>
                    <path d="${d}" fill="url(#mt-g-pedra)"/>
                    <g clip-path="url(#mt-clip)"><rect x="0" y="${yTopo}" width="1000" height="${(alt * .22).toFixed(0)}" fill="url(#mt-g-neve)" opacity=".95"/>
                        <path d="M0 ${H} H1000 V${H - 220} Q700 ${H - 330} 500 ${H - 250} T0 ${H - 300} Z" fill="#000" opacity=".28"/></g>
                    <g clip-path="url(#mt-clip)" fill="none" stroke="#fff" stroke-opacity=".07" stroke-width="3">${[...Array(Math.floor(alt / 150))].map((_, k) => `<path d="M0 ${(H - 60 - k * 150).toFixed(0)} Q${300 + (k * 97) % 400} ${(H - 100 - k * 150).toFixed(0)} 1000 ${(H - 40 - k * 150).toFixed(0)}"/>`).join('')}</g>
                    <path d="${linha(todos.concat([[500, yTopo + 60]]))}" fill="none" stroke="#fff" stroke-opacity=".16" stroke-width="3" stroke-dasharray="3 14" stroke-linecap="round"/>
                    <path d="${linha(feitos)}" fill="none" stroke="#ffd76a" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" class="mt-feito"/>
                    ${colina(150, 330, 190, '#1d1722')}${colina(560, 460, 150, '#171219')}${colina(930, 300, 210, '#1b151f')}
                </svg>
                <div class="mt-nuvens">${nuvens}</div>
                ${est}
                <div class="mt-eu" style="bottom:${yEu.toFixed(0)}px"><div class="mt-eu-anel"></div><i class="fa-solid fa-flag"></i><span>Você · Nv. ${nivel}</span></div>
                <div class="mt-aves">${aves}</div>
            </div></div>
            <div class="mt-luz"></div>`;
        document.body.appendChild(ov);
        document.body.classList.add('mt-aberta');

        const cena = ov.querySelector('.mt-cena'), mundo = ov.querySelector('.mt-mundo');
        let mexeu = false, tremeTimer = null;
        const max = () => cena.scrollHeight - cena.clientHeight;
        cena.scrollTop = max();                                   // começa no pé da montanha
        const irPara = (suave) => cena.scrollTo({ top: Math.max(0, Math.min(max(), H - yEu - cena.clientHeight / 2)), behavior: suave ? 'smooth' : 'auto' });

        const aoRolar = () => {
            const m = max() || 1, p = 1 - cena.scrollTop / m;
            ov.style.setProperty('--luz', Math.min(Math.max((p - .5) / .5, 0), 1).toFixed(3));
            mundo.style.setProperty('--sy', cena.scrollTop.toFixed(0));
        };
        cena.addEventListener('scroll', aoRolar, { passive: true });
        ['wheel', 'touchstart', 'pointerdown'].forEach(ev => cena.addEventListener(ev, () => { mexeu = true; }, { passive: true }));
        aoRolar();

        // cada patente cai quando entra na tela; a montanha treme e o estrondo cresce com a altura (sem exagero)
        const obs = new IntersectionObserver((itens) => {
            itens.forEach(it => {
                if (!it.isIntersecting) return;
                const el = it.target; obs.unobserve(el);
                el.classList.add('on');
                if (reduz) return;
                const i = Number(el.dataset.i), f = Number(el.style.getPropertyValue('--f')) || 1;
                setTimeout(() => {
                    mundo.style.setProperty('--f', f);
                    mundo.classList.remove('treme'); void mundo.offsetWidth; mundo.classList.add('treme');
                    clearTimeout(tremeTimer); tremeTimer = setTimeout(() => mundo.classList.remove('treme'), 520);
                    if (op.impacto) op.impacto(.25 + .6 * (i / Math.max(N - 1, 1)));
                }, 520);
            });
        }, { root: cena, threshold: .35 });
        ov.querySelectorAll('.mt-est').forEach(e => obs.observe(e));
        if (reduz) ov.querySelectorAll('.mt-est').forEach(e => e.classList.add('on'));

        const t1 = setTimeout(() => { if (!mexeu) irPara(true); }, 1100);
        const fechar = () => {
            clearTimeout(t1); clearTimeout(tremeTimer); obs.disconnect();
            document.removeEventListener('keydown', aoTecla, true);
            document.body.classList.remove('mt-aberta');
            ov.remove(); _mtFechar = null;
        };
        const aoTecla = (e) => { if (e.key === 'Escape') { e.stopImmediatePropagation(); e.preventDefault(); fechar(); } };
        document.addEventListener('keydown', aoTecla, true);
        ov.querySelector('.mt-x').addEventListener('click', fechar);
        ov.querySelector('.mt-pos').addEventListener('click', () => irPara(true));
        _mtFechar = fechar;
    }

    // ---------------------------------------------------------------------
    // MOTOR DE EFEITOS EM CANVAS (Amaterasu do Sasuke e "Punição de Alma" do Gogeta).
    // CSS não dá conta de fogo/vórtice de verdade: aqui um laço só (30 fps) desenha todo <canvas class="ef-cv" data-ef="...">
    // que estiver visível. O laço dorme quando não há canvas (ou a aba está escondida) e acorda sozinho quando um aparece.
    // ---------------------------------------------------------------------
    const ss = (a, b, x) => { x = Math.min(1, Math.max(0, (x - a) / (b - a))); return x * x * (3 - 2 * x); };
    const rnd = (a, b) => a + Math.random() * (b - a);
    const TAU = Math.PI * 2;

    // brilho de 4 pontas (o "cintilar" dos gifs)
    function estrela(ctx, x, y, r, alfa, rot) {
        if (alfa <= 0.01 || r <= 0.3) return;
        ctx.save(); ctx.translate(x, y); ctx.rotate(rot || 0); ctx.globalAlpha = Math.min(1, alfa);
        ctx.shadowColor = 'rgba(255,255,255,.95)'; ctx.shadowBlur = r * 1.4; ctx.fillStyle = '#fff';
        const c = r * .13;
        ctx.beginPath(); ctx.moveTo(0, -r); ctx.lineTo(c, -c); ctx.lineTo(r, 0); ctx.lineTo(c, c); ctx.lineTo(0, r); ctx.lineTo(-c, c); ctx.lineTo(-r, 0); ctx.lineTo(-c, -c); ctx.closePath(); ctx.fill();
        ctx.restore();
    }

    // ---- Amaterasu: chama negra discreta, língua a língua, que sobe de leve na base do cartão e some ----
    // Cada língua é uma gota esticada (ponta fina em cima), preta, com um halo lilás só na borda (como no anime), que
    // nasce na base, cresce, balança e recolhe. O "nível" do ciclo controla quantas nascem e até onde sobem.
    const AMATERASU = {
        ciclo: 14,
        novo() { return { linguas: [], fagulhas: [], resto: 0, restoF: 0 }; },
        desenhar(ctx, e, t, dt, w, h, esc) {
            const f = ((t + 3.4) % this.ciclo) / this.ciclo;
            const nivel = ss(.10, .34, f) * (1 - ss(.56, .86, f));
            if (nivel > 0.01) {
                e.resto += dt * nivel * 44;
                const altMax = Math.min(h * .15, 100 * esc) * (.4 + .6 * nivel);          // discreto: no máximo ~15% do cartão
                while (e.resto >= 1) {
                    e.resto -= 1;
                    const alt = rnd(.35, 1) * altMax;
                    e.linguas.push({ x: rnd(-.02, 1.02) * w, alt, larg: Math.max(11 * esc, alt * rnd(.42, .7)),
                                     vida: rnd(1.1, 2.2), idade: 0, fase: rnd(0, TAU), inclina: rnd(-.7, .7), freq: rnd(3, 6.5) });
                }
                e.restoF += dt * nivel * 9;
                while (e.restoF >= 1) {
                    e.restoF -= 1;
                    e.fagulhas.push({ x: rnd(0, 1) * w, y: h - rnd(4, h * .12), vy: rnd(24, 60) * esc, vx: rnd(-10, 10) * esc, r: rnd(1.1, 2.6) * esc, vida: rnd(1, 1.9), idade: 0 });
                }
            }
            ctx.clearRect(0, 0, w, h);
            if (!e.linguas.length && !e.fagulhas.length) return;

            // base escura que "ancora" o fogo na borda de baixo
            if (nivel > 0.02) {
                const gb = ctx.createLinearGradient(0, h, 0, h - h * .06 * nivel - 4);
                gb.addColorStop(0, 'rgba(3,1,6,' + (.92 * Math.min(1, nivel * 1.6)) + ')'); gb.addColorStop(1, 'rgba(3,1,6,0)');
                ctx.fillStyle = gb; ctx.fillRect(0, h - h * .06 * nivel - 4, w, h * .06 * nivel + 4);
            }

            // língua de fogo: corpo largo embaixo, lado de dentro côncavo e a ponta curvada pro lado (nada de espeto reto)
            const gota = (x, base, larg, alt, bal) => {
                const topo = x + bal;
                ctx.beginPath();
                ctx.moveTo(x - larg * .55, base);
                ctx.bezierCurveTo(x - larg * .62, base - alt * .3, x - larg * .1 + bal * .25, base - alt * .5, x + bal * .55, base - alt * .78);
                ctx.quadraticCurveTo(x + bal * .95, base - alt * .93, topo, base - alt);
                ctx.bezierCurveTo(x + bal * .9 + larg * .12, base - alt * .72, x + larg * .72, base - alt * .48, x + larg * .55, base);
                ctx.closePath();
            };
            // 1ª passada: halo lilás (traço largo e suave); 2ª: corpo preto por cima, o que deixa só a borda clara
            for (let passada = 0; passada < 2; passada++) {
                for (const l of e.linguas) {
                    const p = l.idade / l.vida;
                    const crescer = Math.pow(Math.sin(Math.PI * Math.min(1, p)), .8);
                    const tremer = 1 + .16 * Math.sin(t * l.freq * 1.7 + l.fase);            // a chama "respira"
                    const alt = l.alt * crescer * tremer, bal = (Math.sin(t * l.freq + l.fase) * .6 + l.inclina) * l.larg * crescer;
                    if (alt < 1.5) continue;
                    gota(l.x, h + 3, l.larg * (1 - p * .25), alt, bal);
                    if (passada === 0) { ctx.lineWidth = 4 * esc; ctx.strokeStyle = 'rgba(196,181,253,.2)'; ctx.stroke(); }
                    else { ctx.shadowColor = 'rgba(210,196,255,.95)'; ctx.shadowBlur = 6 * esc; ctx.fillStyle = 'rgba(3,1,6,.95)'; ctx.fill(); ctx.shadowBlur = 0; }
                }
            }
            // fagulhas pretas subindo (as lascas soltas do desenho)
            ctx.fillStyle = 'rgba(3,1,6,.9)'; ctx.shadowColor = 'rgba(205,190,255,.8)'; ctx.shadowBlur = 5 * esc;
            for (const g of e.fagulhas) {
                const p = g.idade / g.vida; ctx.globalAlpha = 1 - ss(.55, 1, p);
                ctx.beginPath(); ctx.ellipse(g.x, g.y, g.r * .7, g.r * 1.5, 0, 0, TAU); ctx.fill();
            }
            ctx.globalAlpha = 1; ctx.shadowBlur = 0;

            for (const l of e.linguas) l.idade += dt;
            for (const g of e.fagulhas) { g.idade += dt; g.y -= g.vy * dt; g.x += g.vx * dt + Math.sin(g.idade * 4 + g.x) * .25; }
            e.linguas = e.linguas.filter(l => l.idade < l.vida);
            e.fagulhas = e.fagulhas.filter(g => g.idade < g.vida && g.y > -10);
        }
    };

    // ---- Punição de Alma (Soul Punisher): partículas brancas giram pra dentro, viram a bolha colorida e ela estoura ----
    function bolhaArcoIris(ctx, x, y, R, giro, alfa) {
        ctx.save(); ctx.globalAlpha = alfa;
        const halo = ctx.createRadialGradient(x, y, R * .7, x, y, R * 1.9);
        halo.addColorStop(0, 'rgba(255,90,190,.5)'); halo.addColorStop(.5, 'rgba(255,140,60,.16)'); halo.addColorStop(1, 'rgba(255,90,190,0)');
        ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(x, y, R * 1.9, 0, TAU); ctx.fill();
        ctx.save(); ctx.beginPath(); ctx.arc(x, y, R, 0, TAU); ctx.clip();
        const base = ctx.createRadialGradient(x - R * .08, y - R * .04, R * .04, x, y, R);
        base.addColorStop(0, '#2f6bff'); base.addColorStop(.3, '#4cc2ff'); base.addColorStop(.55, '#b84dff'); base.addColorStop(.76, '#ff4fa3');
        base.addColorStop(.92, '#ff7a33'); base.addColorStop(1, '#ffd447');
        ctx.fillStyle = base; ctx.fillRect(x - R, y - R, R * 2, R * 2);
        // braços do redemoinho
        ctx.globalCompositeOperation = 'lighter'; ctx.lineCap = 'round';
        const cores = ['rgba(255,255,255,.26)', 'rgba(110,225,255,.5)', 'rgba(255,100,200,.55)'];
        for (let k = 0; k < 3; k++) {
            ctx.strokeStyle = cores[k]; ctx.lineWidth = R * (.2 - k * .03);
            ctx.beginPath();
            for (let i = 0; i <= 28; i++) {
                const u = i / 28, r = R * (.92 - u * .78), a = giro * (1.2 + k * .35) + k * 2.1 + u * 4.6;
                const px = x + Math.cos(a) * r, py = y + Math.sin(a) * r;
                if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
            }
            ctx.stroke();
        }
        // meia-lua verde-amarela no fundo do redemoinho
        ctx.strokeStyle = 'rgba(225,255,110,.92)'; ctx.lineWidth = R * .17;
        ctx.beginPath(); ctx.arc(x + R * .14, y + R * .3, R * .27, giro * .5 + 2.3, giro * .5 + 5.2); ctx.stroke();
        ctx.globalCompositeOperation = 'source-over';
        ctx.restore();
        // brilho de bolha de sabão: reflexo no canto e aro fino
        const br = ctx.createRadialGradient(x - R * .42, y - R * .46, 0, x - R * .42, y - R * .46, R * .5);
        br.addColorStop(0, 'rgba(255,255,255,.8)'); br.addColorStop(1, 'rgba(255,255,255,0)');
        ctx.fillStyle = br; ctx.beginPath(); ctx.arc(x, y, R, 0, TAU); ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.lineWidth = Math.max(1, R * .05);
        ctx.beginPath(); ctx.arc(x, y, R - ctx.lineWidth / 2, 0, TAU); ctx.stroke();
        ctx.restore();
    }

    const PUNICAO = {
        ciclo: 17,
        novo() { return { fios: [], cacos: [], resto: 0, estourou: false, brilhos: Array.from({ length: 9 }, () => ({ a: rnd(0, TAU), d: rnd(1.25, 2.3), p: rnd(0, TAU), v: rnd(2, 4), r: rnd(.14, .3) })) }; },
        desenhar(ctx, e, t, dt, w, h, esc) {
            ctx.clearRect(0, 0, w, h);
            const s = (t + 4) % this.ciclo;
            const cx = w * .5, cy = h * .5, R = Math.max(11, Math.min(46, w * .125));
            const juntar = ss(5.6, 9.8, s) * (1 - ss(12.8, 12.9, s));       // 0..1: tamanho da esfera
            if (s < 5) { e.estourou = false; e.fios.length = 0; }

            // 1) partículas brancas entrando em espiral
            if (s >= 5 && s < 9.6) {
                e.resto += dt * 30;
                while (e.resto >= 1) {
                    e.resto -= 1;
                    const a = rnd(0, TAU), d = rnd(.3, .62) * Math.min(w * 1.15, h * .9);
                    e.fios.push({ a, d, d0: d, idade: 0, vida: rnd(1.5, 2.3) });
                }
            }
            ctx.lineCap = 'round';
            for (const p of e.fios) {
                p.idade += dt;
                const u = Math.min(1, p.idade / p.vida);
                const r = p.d0 * Math.pow(1 - u, 1.6);
                p.a += (2.2 + 9 * u * u) * dt;                                     // gira cada vez mais rápido
                const x = cx + Math.cos(p.a) * r, y = cy + Math.sin(p.a) * r * .85;
                // rastro curvo: guarda os últimos pontos e desenha com a cauda sumindo (é o que faz o redemoinho aparecer)
                (p.hist || (p.hist = [])).push([x, y]);
                if (p.hist.length > 14) p.hist.shift();
                ctx.shadowColor = 'rgba(255,255,255,.9)'; ctx.shadowBlur = 4 * esc;
                for (let k = 1; k < p.hist.length; k++) {
                    const q = k / p.hist.length;
                    ctx.strokeStyle = 'rgba(255,255,255,' + (.85 * q * (1 - u * .35)) + ')'; ctx.lineWidth = Math.max(.7, 1.7 * esc * q * (1 - u * .5));
                    ctx.beginPath(); ctx.moveTo(p.hist[k - 1][0], p.hist[k - 1][1]); ctx.lineTo(p.hist[k][0], p.hist[k][1]); ctx.stroke();
                }
                if (p.hist.length > 1) { ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(x, y, Math.max(.9, 1.5 * esc), 0, TAU); ctx.fill(); }
                if (r < 4) p.morto = true;
                if (u >= 1) p.morto = true;
            }
            ctx.shadowBlur = 0;
            e.fios = e.fios.filter(p => !p.morto);

            // 2) núcleo que cresce e vira a esfera colorida (com leve ondular de bolha)
            if (juntar > 0.01 && !e.estourou) {
                const ond = 1 + Math.sin(t * 3.1) * .035 + Math.sin(t * 5.3) * .02;
                const raio = R * juntar * ond;
                const nucleo = 1 - ss(.15, .7, juntar);                              // luz branca de energia no começo
                if (nucleo > 0.01) {
                    const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * (.6 + juntar));
                    g.addColorStop(0, 'rgba(255,255,255,' + nucleo + ')'); g.addColorStop(.5, 'rgba(255,230,140,' + nucleo * .5 + ')'); g.addColorStop(1, 'rgba(255,200,80,0)');
                    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, R * (.6 + juntar), 0, TAU); ctx.fill();
                }
                if (raio > 2) bolhaArcoIris(ctx, cx, cy, raio, t * 1.6, Math.min(1, juntar * 1.6));
                // cintilar em volta, só com a esfera formada
                if (juntar > .55) for (const b of e.brilhos) {
                    const k = .5 + .5 * Math.sin(t * b.v + b.p);
                    estrela(ctx, cx + Math.cos(b.a + t * .15) * R * b.d, cy + Math.sin(b.a + t * .15) * R * b.d, R * b.r * (.6 + k) * 1.6, k * ss(.55, .9, juntar), Math.PI / 4 * 0);
                }
            }

            // 3) estouro: aro de película de bolha, flash e cacos coloridos
            if (s >= 12.8 && !e.estourou) {
                e.estourou = true; e.estouroEm = t;
                const cores = ['#ff5aa5', '#ffd447', '#4cc2ff', '#b84dff', '#ff7a33', '#ffffff', '#6dffb0'];
                for (let i = 0; i < 34; i++) {
                    const a = rnd(0, TAU), v = rnd(70, 230) * esc;
                    e.cacos.push({ x: cx, y: cy, vx: Math.cos(a) * v, vy: Math.sin(a) * v, r: rnd(1.2, 3.4) * esc, cor: cores[i % cores.length], vida: rnd(.6, 1.15), idade: 0, tipo: i % 4 === 0 ? 'estrela' : 'ponto' });
                }
            }
            if (e.estourou && e.estouroEm != null) {
                const u = (t - e.estouroEm);
                if (u < .7) {
                    const k = u / .7;
                    ctx.save(); ctx.globalAlpha = (1 - k) * .9;
                    const gr = ctx.createLinearGradient(cx - R, cy - R, cx + R, cy + R);
                    gr.addColorStop(0, '#ff5aa5'); gr.addColorStop(.33, '#ffd447'); gr.addColorStop(.66, '#4cc2ff'); gr.addColorStop(1, '#b84dff');
                    ctx.strokeStyle = gr; ctx.lineWidth = Math.max(.8, R * .14 * (1 - k)); ctx.shadowColor = 'rgba(255,255,255,.8)'; ctx.shadowBlur = 8 * esc;
                    ctx.beginPath(); ctx.arc(cx, cy, R * (1 + k * 1.1), 0, TAU); ctx.stroke(); ctx.restore();
                }
                if (u < .28) {
                    const fl = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 2);
                    fl.addColorStop(0, 'rgba(255,255,255,' + (.95 * (1 - u / .28)) + ')'); fl.addColorStop(1, 'rgba(255,255,255,0)');
                    ctx.fillStyle = fl; ctx.beginPath(); ctx.arc(cx, cy, R * 2, 0, TAU); ctx.fill();
                    estrela(ctx, cx, cy, R * 1.6 * (1 - u / .28 * .5), 1 - u / .28, 0);
                }
                for (const c of e.cacos) {
                    c.idade += dt; c.x += c.vx * dt; c.y += c.vy * dt; c.vx *= .965; c.vy = c.vy * .965 + 40 * dt;
                    const a = 1 - c.idade / c.vida; if (a <= 0) continue;
                    if (c.tipo === 'estrela') estrela(ctx, c.x, c.y, c.r * 3, a, c.idade * 3);
                    else { ctx.globalAlpha = a; ctx.fillStyle = c.cor; ctx.shadowColor = c.cor; ctx.shadowBlur = 6 * esc; ctx.beginPath(); ctx.arc(c.x, c.y, c.r, 0, TAU); ctx.fill(); ctx.globalAlpha = 1; ctx.shadowBlur = 0; }
                }
                e.cacos = e.cacos.filter(c => c.idade < c.vida);
            }
        }
    };

    const MOTORES = { amaterasu: AMATERASU, punicao: PUNICAO };
    const _estadoCv = new WeakMap();
    const _reduzMov = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let _cvRodando = false, _cvUltimo = 0;

    // Desenha um quadro de todos os canvases visíveis. Devolve false quando não há nenhum (o laço dorme).
    function passoCanvas(agora) {
        const lista = document.querySelectorAll('canvas.ef-cv');
        if (!lista.length) return false;
        lista.forEach((cv) => {
            const motor = MOTORES[cv.dataset.ef];
            if (!motor || !cv.isConnected) return;
            const r = cv.getBoundingClientRect();
            if (r.width < 24 || r.height < 24) return;                    // escondido
            const dpr = Math.min(2, window.devicePixelRatio || 1);
            const W = Math.round(r.width * dpr), H = Math.round(r.height * dpr);
            if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
            let st = _estadoCv.get(cv);
            if (!st) { st = { e: motor.novo(), t: 0, ult: agora }; _estadoCv.set(cv, st); }
            const dt = Math.min(.1, Math.max(0, (agora - st.ult) / 1000)); st.ult = agora; st.t += dt;
            const ctx = cv.getContext('2d');
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            try { motor.desenhar(ctx, st.e, st.t, dt, r.width, r.height, Math.max(.5, r.width / 348)); }
            catch (err) { console.warn('[efeito ' + cv.dataset.ef + ']', err); _estadoCv.delete(cv); }   // recomeça do zero no próximo quadro
        });
        return true;
    }
    function lacoCanvas(ts) {
        if (document.hidden) { _cvRodando = false; return; }
        if (ts - _cvUltimo >= 30) {
            _cvUltimo = ts;
            if (!passoCanvas(ts)) { _cvRodando = false; return; }
        }
        requestAnimationFrame(lacoCanvas);
    }
    function acordarCanvas() {
        if (_cvRodando || _reduzMov() || document.hidden) return;
        _cvRodando = true; requestAnimationFrame(lacoCanvas);
    }
    function ligarCanvas() {
        new MutationObserver(() => { if (!_cvRodando && document.querySelector('canvas.ef-cv')) acordarCanvas(); })
            .observe(document.body, { childList: true, subtree: true });
        document.addEventListener('visibilitychange', () => { if (!document.hidden) acordarCanvas(); });
        acordarCanvas();
    }

    function iniciar() {
        injetarDefs();
        ligarCanvas();
        ligarOrb();
        document.addEventListener('animationiteration', sortearPosicao);
    }

    // `esc` é do chat.html (escape de HTML). Fora dele (página de teste), cai numa versão mínima.
    function esc(v) {
        if (typeof window.esc === 'function') return window.esc(v);
        return String(v == null ? '' : v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    return { PAL, PT_IDS, BADGES, svgPatente, htmlPatente, svgBadge, htmlBadge, htmlBadges, htmlEfeitoAvatar, htmlEfeitoPerfil,
        renderInventario, abrirMontanha, somImpacto, classeFala, classeRadar, classePin, classeServidor, classeNomeServidor, somEntrada, efeitoEnvio, ligarEfeitoChat, aplicarEfeitoChat,
        mostrarOrb, esconderOrb, iniciar, injetarDefs, ROMANOS, _passo: passoCanvas };
})();
