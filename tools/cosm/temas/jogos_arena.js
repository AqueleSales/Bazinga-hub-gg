'use strict';
/* JOGOS DE LUTA, TIRO E BLOCOS: arte original que só evoca (barra de vida e "FIGHT!", cartaz de propaganda e caixa de suprimentos, tijolos com pinos). */
const { tema, M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P, I, fase } = require('../dsl');
const { cena } = P;
const { pontos } = I;
const f1 = (n) => Math.round(n * 10) / 10;

// =====================================================================================================
// NEO ARENA (jogos de luta de fliperama: barra de vida, ROUND 1: FIGHT!, K.O., chama carmesim e púrpura)
// =====================================================================================================
const CARM = { m: '#ff3b1a', a: '#ffd400', d: '#7a0a00', l: '#fff4c0', o: '#5a0800' };
const PURP = { m: '#a43aff', a: '#e0b0ff', d: '#2a0a5a', l: '#ffffff', o: '#240a4a' };
const txtArena = (cls, texto) => `<b class="${cls}">${texto}</b>`;

const neoarena = tema({
    id: 'neoarena', pre: 'neo', nome: 'Neo Arena', cat: 'jogos', cor: '#e4002b', cores: ['#e4002b', '#ffd400'], icone: 'fa-hand-fist', premium: true,
    lema: 'ROUND 1. FIGHT!',
    desc: 'O fliperama de luta: chama carmesim contra chama púrpura, barra de vida que esvazia, "ROUND 1: FIGHT!" e o K.O. no fim.',
    pal: CARM,
    itens: [
        M('Chama Carmesim', 'Um anel de chamas vermelhas e amarelas que sobem em volta da foto.', { t: 'icones', icones: ['chama'], pals: [CARM, { ...CARM, m: '#ff7a1a' }], n: 14, tam: 26, giro: 54, orient: 'fora', glow: '#ff3b1a' }, { r: 'epico', id: 'chama_carmesim' }),
        M('Chama Púrpura', 'O mesmo duelo do outro lado: chamas púrpuras girando ao contrário.', { t: 'icones', icones: ['chama'], pals: [PURP, { ...PURP, m: '#c880ff' }], n: 14, tam: 26, giro: -54, orient: 'fora', glow: '#a43aff' }, { r: 'epico', id: 'chama_purpura' }),
        N('K.O.', 'Letras grossas de vermelho e amarelo com contorno preto, como o letreiro de um fliperama.', { grad: ['#ff2b2b', '#ffd400', '#ff2b2b'], mov: 'desliza', dur: 3, contorno: '#000', cw: 1.4, fonte: 'impacto', espaco: 1, sombra: [1.5, 1.5, '#000'], peso: 900 }, { r: 'epico', id: 'ko' }),
        Pl('Barra de Vida', 'A barra de vida amarela esvazia e deixa o rastro vermelho do dano, e depois enche de novo.', {
            base: ['#16161f', '#0b0b12'], borda: 'rgba(255,212,0,.85)', alterna: true, dur: 3.6, mov: 'nenhum',
            extra: [
                { img: 'linear-gradient(#ffec6a,#ffb400)', size: '100% 22%', size1: '38% 22%', pos: '0 88%', pos1: '0 88%' },
                { img: 'linear-gradient(#ff3b3b,#9a0000)', size: '100% 22%', size1: '64% 22%', pos: '0 88%', pos1: '0 88%' },
            ],
            icone: { nome: 'estrela_ko', pal: { m: '#ffd400', a: '#ff3b1a', d: '#7a0a00', l: '#fff', o: '#5a0800' }, lado: 'dir', tam: 62 },
        }, { r: 'epico', id: 'barra_de_vida' }),
        F('Arena Neo', 'O pôr do sol de uma arena: sol vermelho, prédios em silhueta e o chão em grade piscando.', {
            fundo: ['#25084a', '#b8284a', '#ffae3a'],
            fixo: `${cena.sol({ x: 170, y: 58, r: 30, c1: '#ff3b1a', c2: '#ffd400' })}${cena.skyline({ cor: '#14062a', altMin: 22, altMax: 56, larg: [10, 20], seed: 'sn1', janelas: { cor: '#ffd400', dens: .3 } })}${cena.perspectiva({ cor: '#ff3b1a', y: 82, n: 12 })}`,
            longe: { svg: `<g opacity='.5'>${cena.nuvens({ cor: '#5a1a5a', n: 3, y: [14, 50], tam: [18, 28], seed: 'sn2' })}</g>`, anim: 'pan', dur: 44 },
            perto: { svg: cena.estrelas({ cor: '#fff3b0', n: 22, y: [4, 70], r: [.6, 1.4], seed: 'sn3' }), anim: 'pisca', dur: 2.6 },
        }, { r: 'epico', id: 'arena_neo' }),
        EA('Chamas Rivais', 'Duas chamas, uma carmesim e uma púrpura, giram em direções opostas em volta da foto.', [
            { k: 'aura', cor: '#ff3b1a', dur: 2.2 },
            { k: 'orbita', icones: ['chama'], pals: [CARM], n: 9, tam: 24, giro: 14, orient: 'fora', raio: 70 },
            { k: 'orbita', icones: ['chama'], pals: [PURP], n: 9, tam: 20, giro: -18, orient: 'fora', raio: 62, rot0: 20 },
        ], { r: 'epico', id: 'chamas_rivais' }),
        EP('ROUND 1: FIGHT!', 'O letreiro entra pelo lado, "FIGHT!" bate no cartão com tremor e, no fim, um K.O. explode no meio.', [{
            k: 'raw', html: `<i class="fl"></i><i class="ln"></i>${txtArena('r1', 'ROUND 1')}${txtArena('fg', 'FIGHT!')}${txtArena('ko', 'K.O.')}`,
            css: `.ef-pf-$ID b{position:absolute;left:0;right:0;text-align:center;font:900 19cqw/1 Impact,'Arial Black',sans-serif;color:#ffd400;-webkit-text-stroke:2.4px #5a0000;paint-order:stroke fill;text-shadow:0 4px 0 #a00,0 0 20px rgba(255,60,20,.7);opacity:0}`
                + `.ef-pf-$ID .r1{top:30%;font-size:15cqw;animation:k-$ID-r1 10s ease-out ${fase(10, .14)} infinite}.ef-pf-$ID .fg{top:38%;font-size:23cqw;animation:k-$ID-fg 10s ease-out ${fase(10, .3)} infinite}.ef-pf-$ID .ko{top:34%;font-size:34cqw;color:#fff;-webkit-text-stroke:3px #b00000;animation:k-$ID-ko 10s ease-out ${fase(10, .66)} infinite}`
                + `.ef-pf-$ID .fl{position:absolute;inset:0;background:#ff1a1a;opacity:0;animation:k-$ID-fl 10s linear ${fase(10, .66)} infinite}.ef-pf-$ID .ln{position:absolute;inset:-20%;background:repeating-conic-gradient(from 0deg at 50% 46%,rgba(255,212,0,.6) 0 2deg,transparent 2deg 11deg);-webkit-mask:radial-gradient(circle at 50% 46%,transparent 14%,#000 56%);mask:radial-gradient(circle at 50% 46%,transparent 14%,#000 56%);opacity:0;animation:k-$ID-ln 10s linear ${fase(10, .66)} infinite}`
                + `@keyframes k-$ID-r1{0%,3%{opacity:0;transform:translateX(-120%)}8%{opacity:1;transform:translateX(3%)}11%,15%{opacity:1;transform:translateX(0)}20%,100%{opacity:0;transform:translateX(120%)}}`
                + `@keyframes k-$ID-fg{0%,23%{opacity:0;transform:scale(3.2)}27%{opacity:1;transform:scale(.92)}29%{transform:translateX(-4%) scale(1.02)}31%{transform:translateX(3%) scale(1)}33%,38%{opacity:1;transform:scale(1)}44%,100%{opacity:0;transform:scale(1.15)}}`
                + `@keyframes k-$ID-ko{0%,59%{opacity:0;transform:scale(3) rotate(-8deg)}63%{opacity:1;transform:scale(.9) rotate(-4deg)}66%{transform:scale(1.04) rotate(-4deg)}76%{opacity:1;transform:scale(1) rotate(-4deg)}86%,100%{opacity:0;transform:scale(1.1) rotate(-4deg)}}`
                + `@keyframes k-$ID-fl{0%,59%{opacity:0}61%{opacity:.55}68%,100%{opacity:0}}@keyframes k-$ID-ln{0%,59%{opacity:0;transform:rotate(0)}63%{opacity:1}84%{opacity:.8;transform:rotate(10deg)}92%,100%{opacity:0;transform:rotate(12deg)}}`,
        }], { r: 'lendario', id: 'round_fight' }),
        FALA('Golpe de Voz', 'Quando você fala na call, o card pisca em vermelho, amarelo e púrpura, como um golpe especial.', { cores: ['#ff3b1a', '#ffd400', '#a43aff'], passos: true }),
        RADAR('Onda de Energia', 'As ondas do radar viram anéis vermelhos tracejados, como uma onda de energia.', { cor: '#ff3b1a', estilo: 'tracejado', glow: '#ffd400' }),
        CHAT('Combo', 'A barra de mensagem pisca em vermelho ao digitar e solta faíscas de combo ao enviar.', { cor: '#ff3b1a', cor2: '#ffd400', particula: { forma: 'losango' } }),
        PIN('Bola de Fogo', 'Suas notas no mapa viram uma bola de fogo.', { icone: 'chama', pal: CARM, bal: 1.6 }),
        SOM('Round', 'O sino do round e uma pancada, ao entrar na call.', { notas: [{ t: 0, f: 660, d: .45, tipo: 'triangle', v: .7 }, { t: 0, f: 990, d: .35, tipo: 'sine', v: .3 }, { t: .5, f: 120, f2: 50, d: .3, tipo: 'sine', v: 1 }, { t: .5, f: 330, d: .5, tipo: 'sawtooth', v: .4 }], ruidos: [{ t: .5, d: .15, f: 2400, f2: 500, filtro: 'bandpass', v: .7 }] }),
        SERV('Servidor de Fliperama', 'O ícone do servidor pisca em vermelho e amarelo, em passos.', { cores: ['#e4002b', '#ffd400'], passos: true }),
    ],
});

// =====================================================================================================
// FORTALEZA (jogo de tiro por equipes, estética de pôster dos anos 60: RED contra BLU, caixa de suprimentos, "Crítico!")
// =====================================================================================================
const RD = { m: '#b8383b', a: '#d86a6c', d: '#3a1010', l: '#e8dcc0', o: '#3a1010' };
const BL = { m: '#5b7a8c', a: '#8fb0c4', d: '#14202a', l: '#e8dcc0', o: '#14202a' };
const LAR = { m: '#cf7336', a: '#f2b36a', d: '#4a2208', l: '#fff0d0', o: '#4a2208' };
const cartaz = `<rect width='340' height='112' fill='#e8dcc0'/><path d='M0 0H190L150 112H0Z' fill='#b8383b'/><path d='M190 0H340V112H150Z' fill='#5b7a8c'/>
<g fill='#000' opacity='.12'>${(() => { let s = ''; for (let y = 6; y < 112; y += 9) for (let x = (y / 9) % 2 ? 4 : 0; x < 340; x += 9) s += `<circle cx='${x}' cy='${y}' r='2'/>`; return s; })()}</g>
<path d='M170 0L150 112' stroke='#e8dcc0' stroke-width='5'/><g font-family='Impact,Arial Black,sans-serif' font-size='46' text-anchor='middle' fill='#e8dcc0' stroke='#2a1a10' stroke-width='3' paint-order='stroke'><text x='72' y='72' transform='rotate(-6 72 60)'>RED</text><text x='262' y='72' transform='rotate(6 262 60)'>BLU</text></g>
<path d='${pontos(5, 170, 26, 12, 5, -90)}' fill='#e8dcc0' stroke='#2a1a10' stroke-width='2'/><rect x='0' y='96' width='340' height='16' fill='#2a1a10' opacity='.85'/>`;

const fortaleza = tema({
    id: 'fortaleza', pre: 'for', nome: 'Fortaleza', cat: 'jogos', cor: '#cf7336', cores: ['#b8383b', '#5b7a8c'], icone: 'fa-box-open', premium: true,
    lema: 'Equipe vermelha ou azul. O cartaz é o mesmo.',
    desc: 'Pôster de propaganda dos anos 60, caixa de suprimentos com estêncil, o ouro polido e o "Crítico!": vermelhos e azuis desbotados em guerra.',
    pal: LAR,
    itens: [
        M('Efeito Inusitado', 'Chamas e faíscas giram em volta da foto, como as partículas de um chapéu raro.', { t: 'icones', icones: ['chama', 'brilho', 'chama'], pals: [LAR, { m: '#fff0d0', o: '#cf7336', w: 2 }, { ...LAR, m: '#e8503a' }], n: 12, tam: 24, giro: 22, orient: 'fora', glow: '#cf7336' }, { r: 'epico', id: 'efeito_inusitado' }),
        M('Austrálio', 'Um anel de ouro polido com reflexos que correm, como um item de ouro de verdade.', { t: 'grad', cores: ['#b8780a', '#fff3b0', '#e6a800', '#fff3b0', '#b8780a'], giro: 7, glow: '#ffd54a' }, { r: 'epico' }),
        N('Estêncil', 'Letras de estêncil, em creme, como as de uma caixa de madeira do exército.', { grad: ['#e8dcc0', '#c9b88e', '#e8dcc0'], mov: 'desliza', dur: 7, contorno: '#2a1a10', cw: 1, fonte: 'impacto', espaco: 1.6, maius: true, peso: 900 }, { r: 'epico' }),
        Pl('Caixa de Suprimentos', 'Tábuas de madeira com a borda escura e uma caixa carimbada ao lado.', { base: ['#8a5a2a', '#6e451f'], pad: { tipo: 'horizontais', c1: 'rgba(40,20,5,.35)', c2: 'transparent', tam: 14 }, mov: 'nenhum', borda: 'rgba(40,20,8,.9)', texto: '#fff0d0', icone: { nome: 'caixa', pal: { m: '#a87238', a: '#c8913f', d: '#3a2208', l: '#e8dcc0', o: '#2a1708' }, lado: 'dir', tam: 66 } }, { r: 'epico' }),
        F('Cartaz Vermelho e Azul', 'Um cartaz de propaganda: a equipe vermelha de um lado, a azul do outro, meio-tom e letras grandes.', { fundo: ['#e8dcc0'], fixo: cartaz, perto: { svg: `<g fill='#e8dcc0' opacity='.9'>${cena.icones({ nomes: ['estrelinha'], pals: [{ m: '#e8dcc0', o: '#e8dcc0', w: 0 }], n: 8, tam: [6, 10], seed: 'tf1', y: [4, 100] })}</g>`, anim: 'pisca', dur: 3 } }, { r: 'epico' }),
        EA('ÜberCarga', 'Uma carga vermelha e uma azul pulsam em volta da foto, uma de cada vez, com faíscas.', [
            { k: 'raw', html: '<b class="$C"></b><b class="$C v"></b>', css: `.ef-av-$ID .$C{background:radial-gradient(circle closest-side,transparent 56%,rgba(184,56,59,.85) 66%,rgba(184,56,59,0) 86%);animation:k-$ID-v 2.4s ease-in-out infinite}.ef-av-$ID .$C.v{background:radial-gradient(circle closest-side,transparent 56%,rgba(91,122,140,.95) 66%,rgba(91,122,140,0) 86%);animation-delay:-1.2s}@keyframes k-$ID-v{0%,100%{opacity:0;transform:scale(.92)}50%{opacity:1;transform:scale(1.06)}}` },
            { k: 'faiscas', icone: 'brilho', pals: [{ m: '#fff0d0', o: '#cf7336', w: 2 }], n: 7, tam: 8, raio: 38 },
        ], { r: 'epico', id: 'ubercarga' }),
        EA('Planetas Orbitando', 'Pequenos planetas e estrelas giram em volta da foto: um efeito de universo, só pra quem gosta de exibir.', [
            { k: 'orbita', icones: ['planeta', 'estrelinha', 'planeta'], pals: [{ m: '#cf7336', a: '#f2b36a', d: '#4a2208', l: '#fff0d0', o: '#4a2208' }, { m: '#fff0d0', o: '#fff0d0', w: 0 }, { m: '#5b7a8c', a: '#8fb0c4', d: '#14202a', l: '#e8dcc0', o: '#14202a' }], n: 8, tam: 22, giro: 26 },
        ], { r: 'epico' }),
        EP('Crítico!', 'Estrelas e o letreiro CRÍTICO! estouram no cartão com um clarão vermelho.', [
            { k: 'cai', icones: ['estrelinha'], pals: [{ m: '#ffe44a', o: '#ffe44a', w: 0 }], n: 12, tam: [8, 16], vel: [3, 6], bal: 40, giro: 200 },
            { k: 'raw', html: `<i class="fl"></i><b class="cr">CRÍTICO!</b>`,
              css: `.ef-pf-$ID .fl{position:absolute;inset:0;background:radial-gradient(circle at 50% 42%,rgba(255,60,40,.7),transparent 70%);opacity:0;animation:k-$ID-fl 7s linear ${fase(7, .38)} infinite}.ef-pf-$ID .cr{position:absolute;left:0;right:0;top:36%;text-align:center;font:900 20cqw/1 Impact,'Arial Black',sans-serif;color:#fff4a0;-webkit-text-stroke:2.6px #b00000;paint-order:stroke fill;text-shadow:0 0 20px rgba(255,200,40,.9);opacity:0;animation:k-$ID-cr 7s ease-out ${fase(7, .38)} infinite}`
                + `@keyframes k-$ID-fl{0%,30%{opacity:0}32%{opacity:1}44%,100%{opacity:0}}@keyframes k-$ID-cr{0%,30%{opacity:0;transform:scale(2.4) rotate(-10deg)}35%{opacity:1;transform:scale(.92) rotate(-5deg)}38%{transform:scale(1.05) rotate(-5deg)}52%{opacity:1;transform:scale(1) rotate(-5deg)}60%,100%{opacity:0;transform:scale(1.1) rotate(-5deg)}}` },
        ], { r: 'lendario', id: 'critico' }),
        FALA('ÜberCarga de Voz', 'Quando você fala na call, o card alterna entre a carga vermelha e a azul.', { cores: ['#b8383b', '#5b7a8c'], passos: true }),
        RADAR('Onda de Equipe', 'As ondas do radar viram anéis duplos cor de ferrugem.', { cor: '#cf7336', estilo: 'duplo' }),
        CHAT('Crítico', 'A barra de mensagem acende em laranja ao digitar e solta estrelas ao enviar.', { cor: '#cf7336', cor2: '#ffe44a', particula: { forma: 'estrela' } }),
        PIN('Caixa', 'Suas notas no mapa viram uma caixa de suprimentos.', { icone: 'caixa', pal: { m: '#a87238', a: '#c8913f', d: '#3a2208', l: '#e8dcc0', o: '#2a1708' } }),
        SOM('Crit', 'Um "ting" agudo de crítico, com um sopro de ar, ao entrar na call.', { notas: [{ t: 0, f: 1760, d: .5, tipo: 'sine', v: .7 }, { t: 0, f: 2637, d: .4, tipo: 'sine', v: .35 }, { t: .02, f: 880, d: .35, tipo: 'triangle', v: .4 }], ruidos: [{ t: 0, d: .25, f: 600, f2: 6000, filtro: 'bandpass', v: .6, q: 1.5 }] }),
        SERV('Servidor de Equipe', 'O ícone do servidor alterna entre o vermelho e o azul.', { cores: ['#b8383b', '#5b7a8c'], passos: true }),
    ],
});

// =====================================================================================================
// TIJOLOS (jogos de blocos: peças com pinos, chão quadriculado, percurso de obstáculos sobre lava, bonequinho de blocos)
// =====================================================================================================
const T4 = [{ m: '#d9362b', a: '#ef6a5e', d: '#5a0f0a', l: '#fff', o: '#5a0f0a' }, { m: '#f5c518', a: '#ffe27a', d: '#6a5000', l: '#fff', o: '#6a5000' }, { m: '#2f6fd6', a: '#6a9ae8', d: '#0a2a6a', l: '#fff', o: '#0a2a6a' }, { m: '#2e9e4f', a: '#6ac98a', d: '#0a4a22', l: '#fff', o: '#0a4a22' }];
const plataB = (x, y, w, c, c2) => `<rect x='${x}' y='${y}' width='${w}' height='9' fill='${c}' stroke='#1a1a1a' stroke-width='1.6'/><rect x='${x}' y='${y}' width='${w}' height='3' fill='${c2}' opacity='.7'/>${[...Array(Math.floor(w / 12))].map((_, k) => `<rect x='${x + 3 + k * 12}' y='${y - 3}' width='7' height='3' rx='1' fill='${c}' stroke='#1a1a1a' stroke-width='1'/>`).join('')}`;
const obby = `<rect width='340' height='112' fill='none'/>${plataB(14, 70, 72, '#f5c518', '#fff3a0')}${plataB(112, 52, 60, '#2e9e4f', '#8be0a8')}${plataB(196, 66, 48, '#d9362b', '#ff9a8e')}${plataB(266, 46, 58, '#2f6fd6', '#9ac0ff')}`
    + `<path d='M0 100C20 94 40 106 60 100S100 94 120 100 160 106 180 100 220 94 240 100 280 106 300 100 330 94 340 100V112H0Z' fill='#e8481a'/><path d='M0 106C20 100 40 110 60 106S100 100 120 106 160 110 180 106 220 100 240 106 280 110 300 106 330 100 340 106V112H0Z' fill='#ffb02a'/>`;

const tijolos = tema({
    id: 'tijolos', pre: 'tij', nome: 'Tijolos', cat: 'jogos', cor: '#f5c518', cores: ['#d9362b', '#2f6fd6'], icone: 'fa-cubes', premium: true,
    lema: 'Monte. Pule. Tente de novo.',
    desc: 'Peças de tijolo com pinos, chão quadriculado, um percurso de obstáculos sobre a lava e um bonequinho de blocos: vermelho, amarelo, azul e verde.',
    pal: T4[1],
    itens: [
        M('Anel de Tijolos', 'Tijolos vermelhos, amarelos, azuis e verdes de pinos, em volta da foto.', { t: 'icones', icones: ['tijolo', 'tijolo', 'tijolo', 'tijolo'], pals: T4, n: 12, tam: 25, giro: 42, orient: 'fora' }, { r: 'epico' }),
        N('Blocão', 'Letras grossas que trocam de cor em blocos: vermelho, amarelo, azul e verde.', { grad: ['#d9362b', '#f5c518', '#2f6fd6', '#2e9e4f'], passos: true, mov: 'desliza', dur: 2.4, contorno: '#111', cw: 1.1, fonte: 'impacto', espaco: 1, peso: 900 }, { r: 'epico' }),
        Pl('Baseplate', 'A placa cinza com pinos, andando devagar, e um bonequinho de blocos ao lado.', { base: ['#9a9ea8', '#868a96'], pad: { tipo: 'bolinhas', c1: 'rgba(255,255,255,.34)', c2: 'transparent', tam: 14, r: .36 }, mov: 'x', dur: 12, borda: 'rgba(30,30,40,.8)', texto: '#14161c', icone: { nome: 'bonequinho', pal: T4[1], lado: 'dir', tam: 70 } }, { r: 'epico' }),
        F('Obby', 'Plataformas coloridas de pinos sobre um mar de lava, num céu de nuvens quadradas.', {
            fundo: ['#6ab8ec', '#cfeaff'], fixo: obby,
            longe: { svg: cena.nuvens({ cor: '#ffffff', n: 3, y: [8, 40], tam: [12, 20], seed: 'tj1' }), anim: 'pan', dur: 50 },
            perto: { svg: cena.icones({ nomes: ['tijolo'], pals: T4, n: 7, tam: [8, 13], seed: 'tj2', y: [8, 60], rot: 25 }), anim: 'pan', dur: 28 },
        }, { r: 'epico' }),
        EA('Tijolos Empilhando', 'Tijolos coloridos giram em volta da foto e subem pelos lados.', [
            { k: 'orbita', icones: ['tijolo'], pals: T4, n: 8, tam: 22, giro: 30, orient: 'fora' },
            { k: 'sobe', icones: ['tijolo'], pals: T4, n: 6, tam: 8, alt: 150 },
        ], { r: 'epico' }),
        EP('Chuva de Tijolos', 'Tijolos coloridos caem por todo o cartão e vão formando um muro embaixo.', [
            { k: 'cai', icones: ['tijolo'], pals: T4, n: 14, tam: [14, 24], vel: [4, 8], bal: 24, giro: 120 },
            { k: 'cantos', itens: [10, 24, 38, 52, 66, 80, 94].map((x, k) => ({ icone: 'tijolo', x, y: 96, tam: 28, rot: 0, pal: T4[k % 4] })), dur: 30, bal: 0 },
        ], { r: 'lendario' }),
        FALA('Cor da Vez', 'Quando você fala na call, o card troca de cor em blocos: vermelho, amarelo, azul e verde.', { cores: ['#d9362b', '#f5c518', '#2f6fd6', '#2e9e4f'], passos: true }),
        RADAR('Peças no Radar', 'As ondas do radar viram anéis pontilhados, como as fileiras de pinos.', { cor: '#f5c518', estilo: 'pontilhado' }),
        CHAT('Encaixa', 'A barra de mensagem acende em amarelo ao digitar e solta tijolinhos ao enviar.', { cor: '#f5c518', cor2: '#2f6fd6', particula: { icone: 'tijolo', pal: T4[0] } }),
        PIN('Tijolo', 'Suas notas no mapa viram um tijolo de pinos.', { icone: 'tijolo', pal: T4[0] }),
        SOM('Bloco Encaixado', 'Dois estalos de peça se encaixando e um "plim" alegre, ao entrar na call.', { notas: [{ t: 0, f: 520, d: .08, tipo: 'square', v: .5 }, { t: .1, f: 780, d: .08, tipo: 'square', v: .5 }, { t: .22, f: 1046, d: .35, tipo: 'triangle', v: .6 }, { t: .22, f: 1568, d: .3, tipo: 'sine', v: .3 }], ruidos: [{ t: 0, d: .04, f: 3000, filtro: 'highpass', v: .5 }, { t: .1, d: .04, f: 3000, filtro: 'highpass', v: .5 }] }),
        SERV('Servidor de Blocos', 'O ícone do servidor troca de cor em blocos.', { cores: ['#d9362b', '#2f6fd6'], passos: true }),
    ],
});

module.exports = [neoarena, fortaleza, tijolos];
