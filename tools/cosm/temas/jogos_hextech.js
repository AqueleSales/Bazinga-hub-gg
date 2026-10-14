'use strict';
/* HEXTECH (evoca um jogo de arena de fantasia: cristais, hexágonos, runas, pings, "subiu de nível", PENTAKILL) e as REGIÕES do seu mundo, cada uma com cara própria. Arte original. */
const { tema, M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P, I, fase } = require('../dsl');
const { cena } = P;
const { ICONES } = I;

const OURO = { m: '#c8aa6e', a: '#f0e6d2', d: '#091428', l: '#ffffff', o: '#4a3a18' };
const TEAL = { m: '#0ac8b9', a: '#7ef2ea', d: '#052a38', l: '#e6fffd', o: '#04606a' };
const fx = (n) => Math.round(n * 10) / 10;

// ---- Pentakill: cinco raios caem em sequência, clarão, e a palavra aparece ----
const raio = (x, i) => `<svg class="pk-b" style="left:${x}%;--i:${i}" viewBox="0 0 24 100" preserveAspectRatio="none"><path d="M12 0L6 22L16 24L5 52L15 54L8 100" fill="none" stroke="#7ef2ea" stroke-width="7" opacity=".5" stroke-linejoin="round" stroke-linecap="round"/><path d="M12 0L6 22L16 24L5 52L15 54L8 100" fill="none" stroke="#fff" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
const PENTAKILL = {
    k: 'raw', html: `<i class="pk-cl"></i>${[10, 30, 50, 70, 90].map((x, i) => raio(x, i)).join('')}<b class="pk-t">PENTAKILL</b>`,
    css: `.ef-pf-$ID .pk-b{position:absolute;top:0;width:16%;height:76%;margin-left:-8%;opacity:0;animation:k-$ID-b 10s linear calc(var(--i) * .26s + ${fase(10, .5)}) infinite;filter:drop-shadow(0 0 5px #0ac8b9)}`
        + `.ef-pf-$ID .pk-cl{position:absolute;inset:0;background:radial-gradient(circle at 50% 40%,rgba(10,200,185,.65),rgba(200,170,110,.25) 60%,transparent);opacity:0;animation:k-$ID-c 10s linear ${fase(10, .5)} infinite}`
        + `.ef-pf-$ID .pk-t{position:absolute;left:0;right:0;top:44%;text-align:center;font:900 15.5cqw/1 Impact,'Arial Black',sans-serif;letter-spacing:.02em;color:#ffe7a8;-webkit-text-stroke:2.4px #5a1010;paint-order:stroke fill;text-shadow:0 0 18px rgba(255,170,60,.85);opacity:0;animation:k-$ID-t 10s ease-out ${fase(10, .55)} infinite}`
        + `@keyframes k-$ID-b{0%,32%{opacity:0}33%{opacity:1}36%{opacity:.25}38%{opacity:1}46%,100%{opacity:0}}@keyframes k-$ID-c{0%,32%{opacity:0}34%{opacity:1}52%,100%{opacity:0}}`
        + `@keyframes k-$ID-t{0%,40%{opacity:0;transform:scale(1.9)}46%{opacity:1;transform:scale(1)}50%{transform:scale(1.06)}54%{transform:scale(1)}88%{opacity:1}96%,100%{opacity:0;transform:scale(1)}}`,
};

const hextech = tema({
    id: 'hextech', pre: 'hex', nome: 'Hextech', cat: 'jogos', cor: '#c8aa6e', cores: ['#c8aa6e', '#0ac8b9'], icone: 'fa-gem', premium: true,
    lema: 'Subiu de nível. De novo.',
    desc: 'Hexágonos e cristais dourados e turquesa, o mapa da arena, um "ping" e o PENTAKILL: a magia técnica de um mundo de fantasia.',
    pal: OURO,
    itens: [
        M('Anel Hextech', 'Hexágonos e cristais, ouro e turquesa, girando em volta da sua foto.', { t: 'icones', icones: ['hexagono', 'cristal_hex', 'hexagono', 'cristal_hex'], pals: [OURO, TEAL, TEAL, OURO], n: 12, tam: 24, giro: 56, glow: '#0ac8b9' }, { r: 'epico' }),
        N('Invocador', 'Letras serifadas douradas com um brilho turquesa que pulsa.', { grad: ['#a8884a', '#f4e8c8', '#a8884a'], mov: 'pulsa', brilho: '#0ac8b9', bw: 2.6, contorno: '#1a1408', cw: .6, fonte: 'classica', espaco: .6, peso: 900, dur: 3.4 }, { r: 'epico' }),
        Pl('Mapa da Fenda', 'Um favo de hexágonos sobre o azul-marinho, com um brilho dourado passando e um cristal ao lado.', { base: ['#091428', '#0e2240'], pad: { tipo: 'favo', c1: 'rgba(10,200,185,.34)', tam: 13, lw: 1 }, mov: 'x', dur: 18, brilho: 'rgba(200,170,110,.4)', borda: 'rgba(200,170,110,.6)', icone: { nome: 'cristal_hex', pal: TEAL, lado: 'dir', tam: 70 } }, { r: 'epico' }),
        F('Cristal Hextech', 'Cristais turquesa e dourados crescendo no escuro, um favo ao fundo e faíscas piscando.', {
            fundo: ['#050d1e', '#0b2038', '#0a4a52'],
            fixo: `${cena.cristais({ cor: '#0aa89c', cor2: '#06505a', n: 8, alt: [24, 64], seed: 'h1' })}${cena.cristais({ cor: '#c8aa6e', cor2: '#6a5428', n: 5, alt: [14, 38], seed: 'h2', larg: [6, 11] })}`,
            longe: { svg: cena.icones({ nomes: ['hexagono'], pals: [{ m: '#0ac8b9', o: '#0ac8b9', w: -6 }], n: 7, tam: [10, 22], seed: 'h3', y: [6, 70], alfa: .5 }), anim: 'pan', dur: 52 },
            perto: { svg: cena.estrelas({ cor: '#c8f8f4', n: 24, y: [4, 108], r: [.7, 1.7], seed: 'h4' }), anim: 'pisca', dur: 2.4 },
        }, { r: 'epico' }),
        EA('Nível!', 'Um anel de luz turquesa e ouro pulsa em volta da foto, com raios e faíscas: aquele "subiu de nível".', [
            { k: 'aura', cor: '#0ac8b9', dur: 2.2 },
            { k: 'raw', html: '<b class="$C"></b>', css: '.ef-av-$ID .$C{background:repeating-conic-gradient(from 0deg,rgba(200,170,110,.85) 0 3deg,transparent 3deg 15deg);-webkit-mask:radial-gradient(closest-side,transparent 64%,#000 66%,#000 88%,transparent 98%);mask:radial-gradient(closest-side,transparent 64%,#000 66%,#000 88%,transparent 98%);animation:kGira 16s linear infinite}' },
            { k: 'anel', cor: '#c8aa6e', r: 66, esp: 2.4, dash: '8 6', giro: 22 },
            { k: 'faiscas', icone: 'brilho', pals: [{ m: '#ffffff', o: '#7ef2ea', w: 2 }], n: 6, tam: 9, raio: 39 },
        ], { r: 'epico' }),
        EP('Pentakill', 'Cinco raios caem em sequência, o cartão acende em turquesa e dourado e a palavra PENTAKILL aparece.', [PENTAKILL], { r: 'lendario' }),
        EP('Magia Arcana', 'Hexágonos e cristais flutuam pelo cartão em turquesa e ouro, com a borda brilhando.', [
            { k: 'borda', cor: '#0ac8b9', alfa: .4, dur: 3.6 },
            { k: 'sobe', icones: ['hexagono', 'cristal_hex', 'hexagono'], pals: [TEAL, OURO, { m: '#7ef2ea', o: '#7ef2ea', w: -6 }], n: 14, tam: [10, 22], vel: [7, 13], alfa: .9 },
            { k: 'pisca', icone: 'brilho', pals: [{ m: '#fff', o: '#0ac8b9', w: 2 }], n: 10, tam: [8, 14] },
        ], { r: 'epico' }),
        FALA('Ping de Voz', 'Quando você fala na call, o card acende em turquesa e ouro.', { cores: ['#0ac8b9', '#c8aa6e'] }),
        RADAR('Ondas Hextech', 'As ondas do radar viram anéis duplos turquesa, como o círculo de uma habilidade.', { cor: '#0ac8b9', estilo: 'duplo', glow: '#0ac8b9' }),
        CHAT('Ping', 'A barra de mensagem acende em turquesa ao digitar e solta "pings" dourados ao enviar.', { cor: '#0ac8b9', cor2: '#c8aa6e', particula: { icone: 'ping_exclamacao', pal: OURO } }),
        PIN('Cristal Hextech', 'Suas notas no mapa viram um cristal turquesa.', { icone: 'cristal_hex', pal: TEAL, bal: 3 }),
        SOM('Subiu de Nível', 'Um arpejo que sobe e um brilho de cristal, ao entrar na call.', { notas: [{ t: 0, f: 392, d: .22, tipo: 'triangle', v: .6 }, { t: .1, f: 523.25, d: .22, tipo: 'triangle', v: .6 }, { t: .2, f: 659.25, d: .22, tipo: 'triangle', v: .6 }, { t: .3, f: 783.99, d: .25, tipo: 'triangle', v: .6 }, { t: .42, f: 1046.5, d: .7, tipo: 'triangle', v: .7 }, { t: .42, f: 1318.5, d: .6, tipo: 'sine', v: .3 }, { t: .55, f: 2093, d: .6, tipo: 'sine', v: .22 }, { t: .62, f: 2637, d: .5, tipo: 'sine', v: .16 }], ruidos: [] }),
        SERV('Servidor Hextech', 'O ícone do servidor brilha em turquesa e ouro.', { cores: ['#0ac8b9', '#c8aa6e'] }),
    ],
});

// =====================================================================================================
// REGIÕES (cada uma é um tema pequeno de 6 itens, com cara própria)
// =====================================================================================================
const ZV = { m: '#7cff3a', a: '#bfff8a', d: '#16300c', l: '#eaffd6', o: '#2b5a14' };
const zaun = tema({
    id: 'zaun', pre: 'zau', nome: 'Subterrâneo Tóxico', cat: 'jogos', cor: '#7cff3a', cores: ['#7cff3a', '#9b3cff'], icone: 'fa-flask',
    lema: 'Tudo é ciência. Até o que não devia.',
    desc: 'Verde tóxico e roxo: engrenagens, canos, bolhas de uma poção e uma cidade que vive debaixo da outra.',
    pal: ZV,
    itens: [
        M('Engrenagens e Bolhas', 'Engrenagens enferrujadas e bolhas de poção girando em volta da foto.', { t: 'icones', icones: ['engrenagem', 'bolha', 'bolha'], pals: [{ m: '#8a9a7a', a: '#bcd0a8', d: '#2a3a24', l: '#eaffd6', o: '#1c2a18' }, ZV, ZV], n: 10, tam: 26, giro: 48, glow: '#7cff3a' }, { r: 'raro' }),
        N('Quimitec', 'Verde de poção com um tremor de sinal instável, em letras de laboratório.', { grad: ['#4ac91a', '#c8ff7a', '#4ac91a'], mov: 'glitch', g1: '#9b3cff', g2: '#d8ff6a', dur: 3.6, fonte: 'maquina', contorno: '#0c2008', cw: .8, espaco: .6, peso: 900 }, { r: 'raro' }),
        Pl('Tubulações', 'Faixas de aviso em verde e preto, com uma bolha de poção ao lado.', { base: ['#0f1c0c', '#1b3414'], pad: { tipo: 'listras', c1: 'rgba(124,255,58,.2)', c2: 'transparent', tam: 14 }, mov: 'x', dur: 10, brilho: 'rgba(124,255,58,.3)', borda: 'rgba(124,255,58,.5)', icone: { nome: 'bolha', pal: ZV, lado: 'dir', tam: 64 } }, { r: 'raro' }),
        F('Cidade de Baixo', 'Canos e silhuetas de uma cidade subterrânea, janelas verdes acesas e bolhas subindo.', {
            fundo: ['#07110a', '#10281a', '#1b4a22'],
            fixo: `${cena.canos({ cor: '#223a2a', cor2: '#3a6a3a', n: 6, seed: 'z1' })}${cena.skyline({ cor: '#0a150c', janelas: { cor: '#7cff3a', dens: .35 }, altMin: 24, altMax: 70, seed: 'z2', antenas: true })}`,
            longe: { svg: `<g opacity='.35'>${cena.nuvens({ cor: '#7cff3a', n: 3, y: [56, 96], tam: [18, 28], seed: 'z3' })}</g>`, anim: 'pan', dur: 40 },
            perto: { svg: cena.icones({ nomes: ['bolha'], pals: [ZV], n: 10, tam: [8, 16], seed: 'z4', y: [10, 106], alfa: .8 }), anim: 'pan', dur: 28 },
        }, { r: 'raro' }),
        EA('Poção Borbulhando', 'Bolhas verdes sobem em volta da sua foto, com um halo de poção.', [
            { k: 'halo', cor: '#7cff3a', cor2: '#9b3cff', dur: 2.8 },
            { k: 'sobe', icones: ['bolha'], pals: [ZV], n: 9, tam: 10, alt: 170 },
        ], { r: 'raro' }),
        EP('Fumaça Tóxica', 'Uma névoa verde corre pelo cartão e bolhas de poção sobem devagar.', [
            { k: 'neblina', cor: '#7cff3a', alfa: .34, n: 5 },
            { k: 'sobe', icones: ['bolha'], pals: [ZV], n: 14, tam: [8, 20], vel: [8, 15], alfa: .85 },
            { k: 'borda', cor: '#7cff3a', alfa: .3, dur: 4 },
        ], { r: 'epico' }),
    ],
});

const FN = { m: '#40e0a0', a: '#a8ffe0', d: '#0a1a1a', l: '#e6fff5', o: '#0c4a3a' };
const ilhas = tema({
    id: 'ilhas_das_sombras', pre: 'ilh', nome: 'Ilhas das Sombras', cat: 'jogos', cor: '#40e0a0', cores: ['#40e0a0', '#103a3a'], icone: 'fa-skull-crossbones',
    lema: 'A névoa guarda o que a maré levou.',
    desc: 'Verde-fantasma na neblina: correntes, almas penadas e ilhas que só aparecem quando a maré sobe.',
    pal: FN,
    itens: [
        M('Almas Penadas', 'Fantasmas e elos de corrente em verde-fantasma, em volta da foto.', { t: 'icones', icones: ['fantasma', 'elo'], pals: [{ ...FN, m: '#bffff0' }, FN], n: 10, tam: 26, giro: 60, glow: '#40e0a0' }, { r: 'raro' }),
        N('Alma Perdida', 'Verde pálido de lamparina de névoa, com um brilho que respira.', { grad: ['#7ff0c8', '#e6fff5', '#7ff0c8'], mov: 'pulsa', brilho: '#40e0a0', bw: 3, contorno: '#06241c', cw: .6, fonte: 'redonda', espaco: .4, dur: 3.2 }, { r: 'raro' }),
        Pl('Correntes', 'Elos de corrente enferrujada sobre o fundo escuro, com um brilho espectral.', { base: ['#061a1a', '#0c2e2c'], pad: { tipo: 'icones', icones: ['elo'], pals: [{ m: '#2a6a5a', a: '#2a6a5a', o: '#2a6a5a', w: -12 }], tam: 28, ti: 20, c2: 'transparent', rot: 20 }, mov: 'x', dur: 16, brilho: 'rgba(64,224,160,.32)', borda: 'rgba(64,224,160,.45)', icone: { nome: 'fantasma', pal: { ...FN, m: '#bffff0' }, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Ilhas na Névoa', 'Ilhas negras na neblina verde, lanternas de almas piscando e a maré subindo.', {
            fundo: ['#041012', '#0a2a28', '#16524a'],
            fixo: `${cena.montanhas({ cor: '#06161a', n: 4, altMin: 22, altMax: 44, seed: 'i1' })}${cena.terreno({ cor: '#062024', y: 92, amp: 5, n: 3 })}`,
            longe: { svg: `<g opacity='.4'>${cena.nuvens({ cor: '#7ff0c8', n: 3, y: [30, 80], tam: [20, 32], seed: 'i2' })}</g>`, anim: 'pan', dur: 46 },
            perto: { svg: cena.icones({ nomes: ['lanterna'], pals: [FN], n: 6, tam: [9, 15], seed: 'i3', y: [20, 90], alfa: .9 }), anim: 'pisca', dur: 3.4 },
        }, { r: 'raro' }),
        EA('Espectros', 'Almas pálidas orbitam a foto, e uma aura verde-fantasma respira por trás.', [
            { k: 'aura', cor: '#40e0a0', dur: 3.4 },
            { k: 'orbita', icones: ['fantasma'], pals: [{ ...FN, m: '#bffff0' }], n: 5, tam: 22, giro: 26 },
        ], { r: 'raro' }),
        EP('Maré de Almas', 'Almas sobem pelo cartão entre faixas de névoa verde.', [
            { k: 'neblina', cor: '#40e0a0', alfa: .3, n: 5 },
            { k: 'sobe', icones: ['fantasma'], pals: [{ ...FN, m: '#bffff0' }], n: 10, tam: [14, 26], vel: [10, 18], alfa: .75, giro: 30 },
            { k: 'borda', cor: '#40e0a0', alfa: .3, dur: 5 },
        ], { r: 'epico' }),
    ],
});

const NX = { m: '#d12b2b', a: '#ff6a5a', d: '#1a0a0a', l: '#ffd9d0', o: '#3a0808' };
const noxus = tema({
    id: 'noxus', pre: 'nox', nome: 'Império de Ferro', cat: 'jogos', cor: '#d12b2b', cores: ['#d12b2b', '#2a2326'], icone: 'fa-khanda',
    lema: 'A força não pede licença.',
    desc: 'Vermelho e ferro negro: machados, estandartes, uma cidade de pontas afiadas e brasas num céu de guerra.',
    pal: NX,
    itens: [
        M('Lâminas', 'Machados e espadas vermelhos em ferro, em volta da sua foto.', { t: 'icones', icones: ['machado', 'espada'], pals: [{ ...NX, m: '#c4c8d4', a: '#e8ecf6', d: '#7a1a1a' }, NX], n: 8, tam: 28, giro: 44, glow: '#d12b2b' }, { r: 'raro' }),
        N('Dominação', 'Vermelho-sangue sobre ferro, com um contorno grosso e brilho de brasa.', { grad: ['#a81818', '#ff6a5a', '#a81818'], mov: 'pulsa', brilho: '#d12b2b', bw: 2.4, contorno: '#1a0606', cw: 1, fonte: 'impacto', espaco: .8, peso: 900, dur: 2.6 }, { r: 'raro' }),
        Pl('Placa de Ferro', 'Ferro riscado com uma borda vermelha e um machado ao lado.', { base: ['#2a2326', '#1a1416'], pad: { tipo: 'riscado', c1: 'rgba(209,43,43,.2)', c2: 'transparent', tam: 12, lw: 1.4 }, mov: 'x', dur: 14, brilho: 'rgba(209,43,43,.35)', borda: 'rgba(209,43,43,.7)', icone: { nome: 'machado', pal: { m: '#c4c8d4', a: '#e8ecf6', d: '#7a1a1a', l: '#fff', o: '#1a1416' }, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Cidade de Ferro', 'Silhueta de ferro e estandartes vermelhos num céu de guerra, com brasas subindo.', {
            fundo: ['#1a0808', '#5a1414', '#c4421a'],
            fixo: `${cena.skyline({ cor: '#120a0c', altMin: 28, altMax: 76, larg: [10, 22], seed: 'n1', antenas: true })}${cena.bandeiras({ cor: '#d12b2b', cor2: '#2a2326', n: 5, seed: 'n2' })}`,
            longe: { svg: `<g opacity='.45'>${cena.nuvens({ cor: '#3a1010', n: 3, y: [20, 60], tam: [22, 34], seed: 'n3' })}</g>`, anim: 'pan', dur: 50 },
            perto: { svg: cena.estrelas({ cor: '#ffb04a', n: 28, y: [20, 108], r: [.8, 2], seed: 'n4' }), anim: 'pisca', dur: 2.2 },
        }, { r: 'raro' }),
        EA('Sangue e Aço', 'Uma aura vermelha pulsa em volta da foto e, de vez em quando, escorre sangue pelo alto dela.', [
            { k: 'aura', cor: '#d12b2b', dur: 2.4 },
            { k: 'faiscas', icone: 'espinho', pals: [{ m: '#ff6a5a', o: '#3a0808', w: 3 }], n: 6, tam: 8, raio: 39 },
        ], { r: 'raro', sobre: [{ k: 'pingos', cor: '#a81818', n: 5, dur: 8 }] }),
        EP('Tempestade Vermelha', 'Brasas caem pelo cartão sob um céu de névoa vermelha e clarões de guerra.', [
            { k: 'neblina', cor: '#d12b2b', alfa: .3, n: 4 },
            { k: 'cai', icones: ['chama'], pals: [{ m: '#ff7a2a', a: '#ffd070', d: '#7a1a0a', l: '#fff', o: '#7a1a0a', w: 3 }], n: 14, tam: [8, 16], vel: [4, 8], bal: 40, giro: 40, alfa: .9 },
            { k: 'flash', cor: '#ff5a3a', dur: 11, ini: 55 },
        ], { r: 'epico' }),
    ],
});

const DM = { m: '#e8c46a', a: '#fff2c0', d: '#1a3a7a', l: '#ffffff', o: '#6a4a10' };
const demacia = tema({
    id: 'demacia', pre: 'dem', nome: 'Reino de Luz', cat: 'jogos', cor: '#e8c46a', cores: ['#e8c46a', '#2f6fd6'], icone: 'fa-shield-halved',
    lema: 'Pela luz, pela honra.',
    desc: 'Azul real e ouro: asas de luz, estandartes, uma muralha brilhante e penas caindo do céu.',
    pal: DM,
    itens: [
        M('Asas de Luz', 'Asas douradas em volta da foto, girando devagar como um halo.', { t: 'icones', icones: ['asa'], pals: [DM], n: 8, tam: 30, giro: 70, orient: 'fora', glow: '#ffe9a0' }, { r: 'raro' }),
        N('Honra', 'Ouro polido com contorno azul-real e um brilho de luz do dia.', { grad: ['#c8941a', '#fff2c0', '#c8941a'], mov: 'desliza', dur: 5, contorno: '#14306a', cw: .9, fonte: 'classica', peso: 900, espaco: .5 }, { r: 'raro' }),
        Pl('Estandarte', 'O azul de um estandarte real, com losangos de ouro e um escudo ao lado.', { base: ['#1d3f8f', '#2f6fd6'], pad: { tipo: 'losangos', c1: 'rgba(232,196,106,.32)', c2: 'transparent', tam: 18 }, mov: 'x', dur: 16, brilho: 'rgba(255,242,192,.4)', borda: 'rgba(232,196,106,.8)', icone: { nome: 'escudo', pal: DM, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Muralha Brilhante', 'Uma cidade branca e dourada sob o céu azul, com nuvens passando e estandartes ao vento.', {
            fundo: ['#7fb2f5', '#bfdcff', '#fff2c0'],
            fixo: `${cena.skyline({ cor: '#f4efe0', altMin: 24, altMax: 64, larg: [12, 26], seed: 'd1', antenas: true })}${cena.bandeiras({ cor: '#2f6fd6', cor2: '#e8c46a', n: 5, seed: 'd2' })}`,
            longe: { svg: cena.nuvens({ cor: '#ffffff', n: 3, y: [14, 56], alfa: .9, seed: 'd3' }), anim: 'pan', dur: 56 },
            perto: { svg: cena.icones({ nomes: ['pena', 'estrelinha'], pals: [{ m: '#fff', a: '#fff', d: '#d8c890', l: '#fff', o: '#d8c890', w: 2 }, { m: '#ffe9a0', o: '#ffe9a0', w: 0 }], n: 8, tam: [8, 14], seed: 'd4', y: [6, 100] }), anim: 'pan', dur: 30 },
        }, { r: 'raro' }),
        EA('Asas', 'Um par de asas douradas se abre atrás da foto e bate devagar, com uma luz suave.', [
            { k: 'aura', cor: '#ffe9a0', dur: 3 },
            { k: 'asas', tipo: 'anjo', cor: '#fff6d8', contorno: '#c8941a', bate: 7, dur: 2 },
        ], { r: 'raro' }),
        EP('Luz Sagrada', 'Um clarão dourado respira sobre o cartão enquanto penas e faíscas caem do céu.', [
            { k: 'clima', fundo: 'radial-gradient(ellipse at 50% 0%,rgba(255,242,192,.7),transparent 62%)', min: .35, max: 1, dur: 5 },
            { k: 'cai', icones: ['pena'], pals: [{ m: '#fff', a: '#fff', d: '#d8c890', l: '#fff', o: '#d8c890', w: 2 }], n: 10, tam: [12, 22], vel: [8, 14], bal: 60, alfa: .9 },
            { k: 'pisca', icone: 'brilho', pals: [{ m: '#ffe9a0', o: '#c8941a', w: 2 }], n: 10, tam: [8, 14] },
        ], { r: 'epico' }),
    ],
});

const IN = { m: '#ff9ec4', a: '#ffd0e4', d: '#6a2a4a', l: '#ffffff', o: '#c45a8a' };
const ionia = tema({
    id: 'ionia', pre: 'ion', nome: 'Ilha Espiritual', cat: 'jogos', cor: '#ff9ec4', cores: ['#ff9ec4', '#7ad9c9'], icone: 'fa-leaf',
    lema: 'O vento leva o que não é preciso.',
    desc: 'Cerejeiras em flor, neblina de montanha e espíritos: rosa e verde-água numa ilha de equilíbrio.',
    pal: IN,
    itens: [
        M('Cerejeira', 'Flores de cerejeira em volta da foto, girando como numa brisa.', { t: 'icones', icones: ['sakura'], pals: [IN, { ...IN, m: '#ffc0d8' }], n: 12, tam: 25, giro: 64 }, { r: 'raro' }),
        N('Equilíbrio', 'Rosa e verde-água passeando pelas letras, em fonte redonda.', { grad: ['#ff86b4', '#7ad9c9', '#ff86b4'], mov: 'desliza', dur: 6, fonte: 'redonda', contorno: '#5a2a44', cw: .5, peso: 800 }, { r: 'raro' }),
        Pl('Pétalas ao Vento', 'Pétalas de cerejeira andando devagar sobre um degradê rosa e verde-água.', { base: ['#ffd0e4', '#cdf3ea'], pad: { tipo: 'icones', icones: ['sakura'], pals: [{ m: '#ff9ec4', o: '#ff9ec4', a: '#ff9ec4', w: -4 }], tam: 28, ti: 16, c2: 'transparent', rot: 20 }, mov: 'x', dur: 15, texto: '#5a2a44', icone: { nome: 'lanterna', pal: IN, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Ilha de Neblina', 'Montanhas na neblina rosa e verde-água, cerejeiras em flor e pétalas ao vento.', {
            fundo: ['#9fe3d8', '#e9f6f0', '#ffd0e4'],
            fixo: `${cena.montanhas({ cor: '#7ac4b8', cor2: '#5aa8a0', n: 4, altMin: 30, altMax: 64, seed: 'o1' })}${cena.terreno({ cor: '#5ea99a', y: 88, amp: 6, n: 2 })}${cena.icones({ nomes: ['sakura'], pals: [IN], n: 5, tam: [22, 34], seed: 'o2', y: [70, 90], rot: 4 })}`,
            longe: { svg: `<g opacity='.6'>${cena.nuvens({ cor: '#ffffff', n: 3, y: [20, 70], tam: [20, 30], seed: 'o3' })}</g>`, anim: 'pan', dur: 60 },
            perto: { svg: cena.icones({ nomes: ['sakura'], pals: [IN, { ...IN, m: '#ffc0d8' }], n: 9, tam: [8, 14], seed: 'o4', y: [4, 104] }), anim: 'pan', dur: 26 },
        }, { r: 'raro' }),
        EA('Pétalas Soltas', 'Pétalas sobem em volta da foto e algumas caem por cima dela.', [
            { k: 'aura', cor: '#ff9ec4', dur: 3.6, blur: 3 },
            { k: 'sobe', icones: ['sakura'], pals: [IN], n: 7, tam: 10, alt: 160 },
        ], { r: 'raro', sobre: [{ k: 'cai', icones: ['sakura'], pals: [IN], n: 5, tam: 12 }] }),
        EP('Vento Espiritual', 'Uma ventania de pétalas atravessa o cartão com brilhos de espíritos e névoa rosada.', [
            { k: 'neblina', cor: '#ffc0d8', alfa: .35, n: 4 },
            { k: 'cai', icones: ['sakura'], pals: [IN, { ...IN, m: '#ffc0d8' }], n: 18, tam: [10, 20], vel: [6, 11], bal: 110, giro: 400, alfa: .95 },
            { k: 'pisca', icone: 'brilho', pals: [{ m: '#fff', o: '#7ad9c9', w: 2 }], n: 8, tam: [8, 13] },
        ], { r: 'epico' }),
    ],
});

const FR = { m: '#bfe4ff', a: '#e8f6ff', d: '#1a3a5a', l: '#ffffff', o: '#3a6a9a' };
const freljord = tema({
    id: 'freljord', pre: 'fre', nome: 'Terras do Gelo', cat: 'jogos', cor: '#8ad4ff', cores: ['#8ad4ff', '#1b3a5a'], icone: 'fa-snowflake',
    lema: 'O frio ensina quem fica.',
    desc: 'Gelo, geada e aurora: cristais azul-claros, nevasca e picos brancos sob um céu que dança.',
    pal: FR,
    itens: [
        M('Cristais de Gelo', 'Cristais e flocos de gelo em volta da foto, girando devagar.', { t: 'icones', icones: ['cristal_gelo', 'floco'], pals: [FR], n: 12, tam: 25, giro: 66, glow: '#8ad4ff' }, { r: 'raro' }),
        N('Geada', 'Branco-gelo com um contorno azul e um brilho de frio que respira.', { grad: ['#9fd8ff', '#ffffff', '#9fd8ff'], mov: 'pulsa', brilho: '#8ad4ff', bw: 2.6, contorno: '#1b3a5a', cw: .8, fonte: 'redonda', peso: 800, dur: 3.2 }, { r: 'raro' }),
        Pl('Gelo Rachado', 'Gelo azul-claro com rachaduras brancas e um brilho que atravessa.', { base: ['#cfeeff', '#8ac8f0'], pad: { tipo: 'riscado', c1: 'rgba(255,255,255,.5)', c2: 'transparent', tam: 14, lw: 1.2 }, mov: 'x', dur: 18, brilho: 'rgba(255,255,255,.6)', texto: '#12304f', icone: { nome: 'floco', pal: FR, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Tundra Boreal', 'Aurora verde e azul sobre picos nevados e pinheiros, com neve caindo.', {
            fundo: ['#07152e', '#0f4a66', '#3ad6b8'],
            fixo: `${cena.estrelas({ cor: '#fff', n: 30, y: [0, 60], r: [.5, 1.3], seed: 'f1' })}${cena.montanhas({ cor: '#dce9f5', cor2: '#9bb8d4', neve: '#fff', n: 4, altMin: 34, altMax: 66, seed: 'f2' })}${cena.pinheiros({ cor: '#0a2a2a', n: 12, altMin: 16, altMax: 36, seed: 'f3' })}`,
            longe: { svg: cena.nuvens({ cor: '#7ae8d0', n: 2, y: [10, 36], alfa: .28, tam: [28, 40], seed: 'f4' }), anim: 'pan', dur: 70 },
            perto: { svg: cena.icones({ nomes: ['floco'], pals: [FR], n: 12, tam: [6, 11], seed: 'f5', y: [4, 106], alfa: .9 }), anim: 'pan', dur: 24 },
        }, { r: 'raro' }),
        EA('Geada', 'Neve no alto da foto, flocos em órbita e um brilho azul-gelo em volta.', [
            { k: 'aura', cor: '#8ad4ff', dur: 3.2 },
            { k: 'orbita', icones: ['floco', 'cristal_gelo'], pals: [FR], n: 6, tam: 22, giro: 30 },
        ], { r: 'raro', sobre: [{ k: 'neve', cor: '#ffffff' }] }),
        EP('Nevasca', 'Uma nevasca de flocos e névoa branca cobre o cartão.', [
            { k: 'neblina', cor: '#e8f6ff', alfa: .4, n: 5 },
            { k: 'cai', icones: ['floco'], pals: [FR], n: 22, tam: [8, 20], vel: [5, 10], bal: 80, giro: 260, alfa: .95 },
            { k: 'borda', cor: '#8ad4ff', alfa: .35, dur: 4.4 },
        ], { r: 'epico' }),
    ],
});

const SH = { m: '#e8b84a', a: '#ffe08a', d: '#5a3a10', l: '#fff4d0', o: '#7a4a10' };
const shurima = tema({
    id: 'shurima', pre: 'shu', nome: 'Império do Sol', cat: 'jogos', cor: '#e8b84a', cores: ['#e8b84a', '#c8742a'], icone: 'fa-sun',
    lema: 'O sol lembra o que a areia esqueceu.',
    desc: 'Ouro e areia: discos solares, dunas sem fim, pirâmides e uma tempestade que apaga as pegadas.',
    pal: SH,
    itens: [
        M('Disco Solar', 'Pequenos sóis dourados em volta da foto, girando como um relógio antigo.', { t: 'icones', icones: ['sol_disco'], pals: [SH], n: 8, tam: 30, giro: 80, glow: '#ffe08a' }, { r: 'raro' }),
        N('Imperador de Areia', 'Ouro e areia, com um brilho que corre e um contorno de bronze.', { grad: ['#b8801a', '#ffe9a0', '#b8801a'], mov: 'desliza', dur: 5.5, contorno: '#4a2a08', cw: .9, fonte: 'classica', peso: 900, espaco: .5 }, { r: 'raro' }),
        Pl('Hieróglifos', 'Areia dourada gravada com sóis, olhos e pirâmides, em marrom.', { base: ['#e6c07a', '#d29a4a'], pad: { tipo: 'icones', icones: ['sol_disco', 'olho', 'piramide'], pals: [{ m: '#8a5a1a', a: '#8a5a1a', d: '#8a5a1a', l: '#e6c07a', o: '#8a5a1a', w: -3 }], tam: 30, ti: 17, c2: 'transparent', denso: false }, mov: 'x', dur: 20, texto: '#4a2a08', icone: { nome: 'sol_disco', pal: SH, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Dunas do Deserto', 'Um sol enorme sobre as dunas e as pirâmides, com a areia correndo no vento.', {
            fundo: ['#f2a84a', '#f7d58a', '#fff1c4'],
            fixo: `${cena.sol({ x: 250, y: 46, r: 30, c1: '#fff7d0', c2: '#ffd070' })}${cena.piramides({ cor: '#c8842a', n: 3, y: 84, seed: 'u1', tam: [24, 40] })}${cena.terreno({ cor: '#d99a3e', y: 88, amp: 7, n: 2, fase: 1 })}`,
            longe: { svg: cena.terreno({ cor: '#c47a2a', y: 96, amp: 6, n: 3, fase: 2 }), anim: 'pan', dur: 60 },
            perto: { svg: cena.estrelas({ cor: '#fff3c8', n: 30, y: [20, 100], r: [.5, 1.2], seed: 'u2' }), anim: 'pan', dur: 14 },
        }, { r: 'raro' }),
        EA('Sol de Areia', 'Um disco de luz dourado atrás da foto e grãos de areia girando em volta.', [
            { k: 'aura', cor: '#ffd070', dur: 3.2 },
            { k: 'orbita', icones: ['grao'], pals: [{ m: '#f2c466', o: '#f2c466', w: 0 }], n: 14, tam: 8, giro: 20, raio: 74 },
            { k: 'anel', cor: '#e8b84a', r: 68, esp: 2.4, dash: '3 7', giro: 30, rev: true },
        ], { r: 'raro' }),
        EP('Tempestade de Areia', 'Uma nuvem de areia atravessa o cartão, com poeira dourada e um clarão de sol.', [
            { k: 'clima', fundo: 'linear-gradient(120deg,rgba(232,184,74,.5),rgba(200,116,42,.25) 60%,transparent)', min: .3, max: 1, dur: 4 },
            { k: 'neblina', cor: '#f2c466', alfa: .5, n: 6, vel: 8 },
            { k: 'deriva', icones: ['grao'], pals: [{ m: '#f2c466', o: '#f2c466', w: 0 }], n: 26, tam: [3, 7], vel: [3, 6], y: [0, 100], bal: 18, alfa: .85 },
        ], { r: 'epico' }),
    ],
});

module.exports = [hextech, zaun, ilhas, noxus, demacia, ionia, freljord, shurima];
