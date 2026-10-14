'use strict';
/* DERBY (corrida de cavalinhas idol): ferraduras, orelhas, fitas, linha de chegada quadriculada, cenouras e o palco do show. Arte original, tudo pastel. */
const { tema, M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P, I, fase } = require('../dsl');
const { cena } = P;
const f1 = (n) => Math.round(n * 10) / 10;

const ROSA = { m: '#ff8fc7', a: '#ffc4e2', d: '#8a2a5a', l: '#ffffff', o: '#c4569a' };
const OURO = { m: '#ffd166', a: '#fff0b0', d: '#8a5a00', l: '#ffffff', o: '#b8861a' };
const CEU = { m: '#7ec8ff', a: '#bfe4ff', d: '#1a4a7a', l: '#ffffff', o: '#3a86c4' };
const MENTA = { m: '#7fe0b4', a: '#c0f4dc', d: '#14603c', l: '#ffffff', o: '#3aa878' };

const bandeirolas = (() => { const cores = ['#ff8fc7', '#7ec8ff', '#ffd166', '#7fe0b4']; let s = `<path d='M-4 8Q85 22 170 8T344 8' fill='none' stroke='#8a8aa8' stroke-width='1.6'/>`; for (let k = 0; k < 14; k++) { const x = 8 + k * 25, y = 8 + Math.sin(k * .85) * 5 + 6; s += `<path d='M${x} ${f1(y - 4)}L${x + 12} ${f1(y - 4)}L${x + 6} ${f1(y + 12)}Z' fill='${cores[k % 4]}'/>`; } return s; })();
const arquibancada = (() => { let s = `<path d='M0 112V62H340V112Z' fill='#b8c8e0'/><path d='M0 62H340' stroke='#8a9ac0' stroke-width='2'/>`; const cores = ['#ff8fc7', '#7ec8ff', '#ffd166', '#7fe0b4', '#fff']; for (let r = 0; r < 3; r++) for (let x = 6 + (r % 2) * 5; x < 340; x += 10) s += `<circle cx='${x}' cy='${72 + r * 10}' r='3' fill='${cores[(x / 10 + r) % 5 | 0]}'/>`; return s; })();
const pista = `<rect y='88' width='340' height='24' fill='#d9a066'/><path d='M0 94H340M0 100H340M0 106H340' stroke='#fff' stroke-width='1.4' opacity='.7'/><rect y='84' width='340' height='4' fill='#7fe0b4'/>`;
const linhaChegada = (() => { let s = '<g>'; for (let y = 0; y < 5; y++) for (let x = 0; x < 3; x++) if ((x + y) % 2 === 0) s += `<rect x='${x * 8}' y='${y * 8}' width='8' height='8' fill='#14161c'/>`; return s + '</g>'; })();

const derby = tema({
    id: 'derby', pre: 'der', nome: 'Derby', cat: 'anime', cor: '#ff8fc7', cores: ['#ff8fc7', '#7ec8ff'], icone: 'fa-horse', premium: true,
    lema: 'Largar na frente. Chegar sorrindo.',
    desc: 'Ferraduras de ouro, orelhinhas que balançam, bandeirolas, a linha de chegada quadriculada e confete: a corrida mais fofa do Armazém.',
    pal: ROSA,
    itens: [
        M('Ferradura', 'Ferraduras de ouro com cravos, em volta da foto, como um amuleto de sorte.', { t: 'icones', icones: ['ferradura'], pals: [OURO], n: 8, tam: 30, giro: 70, orient: 'fora', glow: '#ffd166' }, { r: 'epico' }),
        N('Idol', 'Rosa, azul-céu e menta com um contorno branco e brilho, como o letreiro de um show.', { grad: ['#ff8fc7', '#7ec8ff', '#7fe0b4'], mov: 'desliza', dur: 5, contorno: '#ffffff', cw: 1.4, brilho: '#ff8fc7', bw: 2.2, fonte: 'redonda', peso: 900 }, { r: 'epico' }),
        Pl('Raia', 'Uma pista de terra com as linhas brancas das raias andando, e uma ferradura ao lado.', { base: ['#e2b27a', '#cf9558'], pad: { tipo: 'horizontais', c1: 'rgba(255,255,255,.75)', c2: 'transparent', tam: 16 }, mov: 'x', dur: 4, borda: 'rgba(255,255,255,.8)', texto: '#4a2a0a', icone: { nome: 'ferradura', pal: OURO, lado: 'dir', tam: 62 } }, { r: 'epico' }),
        F('Dia de Derby', 'A arquibancada colorida, bandeirolas ao vento, a pista de terra e confete subindo.', {
            fundo: ['#7ec8ff', '#d6f0ff'], fixo: `${arquibancada}${bandeirolas}${pista}`,
            longe: { svg: cena.nuvens({ cor: '#fff', n: 3, y: [14, 40], alfa: .9, seed: 'dr1', tam: [10, 18] }), anim: 'pan', dur: 60 },
            perto: { svg: cena.icones({ nomes: ['confete', 'estrelinha'], pals: [{ m: '#ff8fc7', a: '#7ec8ff', l: '#ffd166' }, { m: '#fff', o: '#fff', w: 0 }], n: 8, tam: [8, 14], seed: 'dr2', y: [8, 100] }), anim: 'pan', dur: 22 },
        }, { r: 'epico' }),
        EA('Orelhinhas', 'Orelhas de cavalinha rosa e douradas no alto da foto, que balançam, com estrelinhas em volta.', [
            { k: 'orelhas', tipo: 'cavalo', cor: '#ff8fc7', cor2: '#fff0f8', contorno: '#c4569a', ang: 30, esc: .95 },
            { k: 'faiscas', icone: 'estrelinha', pals: [{ m: '#ffd166', o: '#ffd166', w: 0 }], n: 7, tam: 7, raio: 38 },
        ], { r: 'epico' }),
        EA('Trilha de Cascos', 'Ferraduras douradas sobem pelos lados da foto, como a trilha de uma disparada.', [
            { k: 'aura', cor: '#ffd166', dur: 2.4 },
            { k: 'sobe', icones: ['ferradura'], pals: [OURO], n: 8, tam: 10, alt: 170 },
        ], { r: 'epico' }),
        EP('Linha de Chegada', 'Uma fita quadriculada cruza o cartão, o confete cai e os holofotes acendem.', [
            { k: 'cai', icones: ['confete'], pals: [{ m: '#ff8fc7', a: '#7ec8ff', l: '#ffd166' }, { m: '#7fe0b4', a: '#ffd166', l: '#ff8fc7' }], n: 16, tam: [10, 18], vel: [4, 8], bal: 50, giro: 360 },
            { k: 'raw', html: `<i class="fita"></i><i class="holo"></i><i class="holo b"></i>`,
              css: `.ef-pf-$ID .fita{position:absolute;left:0;right:0;top:44%;height:7cqw;background:repeating-conic-gradient(#14161c 0 25%,#fff 0 50%) 0 0/14px 14px;box-shadow:0 0 0 2px #14161c;transform:translateX(-110%);animation:k-$ID-f 8s ease-in-out ${fase(8, .42)} infinite}.ef-pf-$ID .holo{position:absolute;top:-6%;left:10%;width:36%;height:80%;background:linear-gradient(180deg,rgba(255,255,255,.55),transparent 82%);clip-path:polygon(40% 0,60% 0,100% 100%,0 100%);opacity:0;animation:k-$ID-h 8s ease-in-out ${fase(8, .42)} infinite}.ef-pf-$ID .holo.b{left:54%;animation-delay:calc(${fase(8, .42)} + .35s)}`
                  + `@keyframes k-$ID-f{0%,30%{transform:translateX(-110%)}46%{transform:translateX(0)}70%{transform:translateX(0);opacity:1}86%,100%{transform:translateX(110%);opacity:1}}@keyframes k-$ID-h{0%,40%{opacity:0}48%,76%{opacity:1}86%,100%{opacity:0}}` },
        ], { r: 'lendario' }),
        FALA('Torcida', 'Quando você fala na call, o card brilha em rosa e azul-céu como um refletor.', { cores: ['#ff8fc7', '#7ec8ff'] }),
        RADAR('Pista Pontilhada', 'As ondas do radar viram anéis pontilhados dourados, como a trilha de cascos.', { cor: '#ffd166', estilo: 'pontilhado' }),
        CHAT('Galope', 'A barra de mensagem acende em rosa ao digitar e solta ferraduras ao enviar.', { cor: '#ff8fc7', cor2: '#ffd166', particula: { icone: 'ferradura', pal: OURO } }),
        PIN('Ferradura', 'Suas notas no mapa viram uma ferradura de ouro.', { icone: 'ferradura', pal: OURO, bal: 2.6 }),
        SOM('Largada', 'O sino da largada e quatro batidas de galope, ao entrar na call.', { notas: [{ t: 0, f: 1046.5, d: .4, tipo: 'triangle', v: .6 }, { t: 0, f: 1568, d: .3, tipo: 'sine', v: .3 }, { t: .45, f: 160, f2: 90, d: .1, tipo: 'sine', v: .9 }, { t: .55, f: 160, f2: 90, d: .1, tipo: 'sine', v: .9 }, { t: .7, f: 160, f2: 90, d: .1, tipo: 'sine', v: .9 }, { t: .8, f: 160, f2: 90, d: .1, tipo: 'sine', v: .9 }], ruidos: [] }),
        SERV('Servidor de Derby', 'O ícone do servidor brilha em rosa e azul-céu.', { cores: ['#ff8fc7', '#7ec8ff'] }),
    ],
});

// ---------------------------------------------------------------------------------------- LIVE (palco de show)
const LV = { m: '#ff5fb8', a: '#ffa0d8', d: '#3a0a4a', l: '#ffffff', o: '#7a1a6a' };
const holofotes = `<path d='M40 0L10 112H80Z' fill='rgba(255,255,255,.18)'/><path d='M150 0L110 112H200Z' fill='rgba(126,200,255,.22)'/><path d='M270 0L230 112H320Z' fill='rgba(255,209,102,.2)'/>`;
const plateia = (() => { let s = `<path d='M0 112V90C30 82 60 92 90 86S150 80 180 88 250 92 280 84 320 86 340 90V112Z' fill='#1a0a2a'/>`; const cores = ['#ff5fb8', '#7ec8ff', '#ffd166', '#7fe0b4']; for (let k = 0; k < 14; k++) s += `<rect x='${6 + k * 24}' y='${74 + (k % 3) * 4}' width='3.4' height='14' rx='1.7' fill='${cores[k % 4]}' transform='rotate(${(k % 5 - 2) * 8} ${6 + k * 24} 88)'/>`; return s; })();
const live = tema({
    id: 'live_idol', pre: 'liv', nome: 'Show ao Vivo', cat: 'anime', cor: '#ff5fb8', cores: ['#ff5fb8', '#7ec8ff'], icone: 'fa-microphone-lines',
    lema: 'As luzes acendem. É a sua vez.',
    desc: 'O palco de um show: holofotes, bastões de luz balançando na plateia, confete e o brilho de quem canta pra todo mundo.',
    pal: LV,
    itens: [
        M('Bastões de Luz', 'Bastões de luz coloridos em volta da foto, como a plateia de um show.', { t: 'icones', icones: ['bastao_luz'], pals: [LV, { ...LV, m: '#7ec8ff', a: '#bfe4ff', d: '#0a2a4a', o: '#2a6aa8' }, { ...LV, m: '#ffd166', a: '#fff0b0', d: '#5a3a00', o: '#b8861a' }], n: 12, tam: 26, giro: 44, glow: '#ff5fb8' }, { r: 'raro' }),
        N('Estrela do Palco', 'Rosa, azul e dourado em degradê vivo, como um letreiro de show.', { grad: ['#ff5fb8', '#7ec8ff', '#ffd166'], mov: 'desliza', dur: 3.6, contorno: '#2a0a3a', cw: 1.2, brilho: '#ff5fb8', bw: 2, fonte: 'redonda', peso: 900 }, { r: 'raro' }),
        Pl('Palco', 'O palco escuro com holofotes passando e estrelas piscando.', { base: ['#1a0a2a', '#2a1040'], pad: { tipo: 'icones', icones: ['estrelinha'], pals: [{ m: '#ff5fb8', o: '#ff5fb8', w: 0 }, { m: '#7ec8ff', o: '#7ec8ff', w: 0 }], tam: 26, ti: 7, c2: 'transparent' }, mov: 'x', dur: 12, brilho: 'rgba(255,255,255,.4)', borda: 'rgba(255,95,184,.8)', icone: { nome: 'microfone', pal: LV, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Noite de Show', 'Holofotes cortando o escuro, a plateia com bastões de luz e estrelas piscando.', {
            fundo: ['#12062a', '#3a1058', '#7a2a8a'], fixo: `${holofotes}${plateia}`,
            longe: { svg: cena.estrelas({ cor: '#fff', n: 24, y: [0, 70], seed: 'lv1' }), anim: 'pisca', dur: 2.4 },
            perto: { svg: cena.icones({ nomes: ['confete', 'estrelinha'], pals: [{ m: '#ff5fb8', a: '#7ec8ff', l: '#ffd166' }, { m: '#ffd166', o: '#ffd166', w: 0 }], n: 8, tam: [8, 13], seed: 'lv2', y: [6, 80] }), anim: 'pan', dur: 24 },
        }, { r: 'raro' }),
        EA('Holofote', 'Um holofote rosa e estrelas brilham em volta da foto, com um brilho passando por cima dela.', [
            { k: 'aura', cor: '#ff5fb8', dur: 2 },
            { k: 'sobe', icones: ['estrelinha', 'brilho'], pals: [{ m: '#ffd166', o: '#ffd166', w: 0 }, { m: '#fff', o: '#ff5fb8', w: 2 }], n: 8, tam: 9, alt: 160 },
        ], { r: 'raro', sobre: [{ k: 'brilho', cor: '#ffffff', dur: 3.4 }] }),
        EP('Final do Show', 'Confete caindo, clarões de palco e estrelas piscando pelo cartão inteiro.', [
            { k: 'clima', fundo: 'linear-gradient(180deg,rgba(255,95,184,.4),transparent 50%,rgba(126,200,255,.3))', min: .3, max: 1, dur: 3 },
            { k: 'cai', icones: ['confete'], pals: [{ m: '#ff5fb8', a: '#7ec8ff', l: '#ffd166' }, { m: '#ffd166', a: '#ff5fb8', l: '#7ec8ff' }], n: 20, tam: [10, 18], vel: [3.5, 7], bal: 60, giro: 400 },
            { k: 'flash', cor: '#ffffff', dur: 6, ini: 70 },
            { k: 'pisca', icone: 'estrelinha', pals: [{ m: '#fff', o: '#fff', w: 0 }], n: 10, tam: [6, 12] },
        ], { r: 'epico' }),
    ],
});

// ---------------------------------------------------------------------------------------- CENOURAS
const CN = { m: '#ff9a2a', a: '#ffc06a', d: '#7a3a00', l: '#fff4d8', o: '#b8620a' };
const cenouras = tema({
    id: 'cenouras', pre: 'cen', nome: 'Cenourinhas', cat: 'fofo', cor: '#ff9a2a', cores: ['#ff9a2a', '#7fe0b4'], icone: 'fa-carrot',
    lema: 'O melhor lanche depois da corrida.',
    desc: 'Cenouras por todo lado: em volta da foto, caindo pelo cartão e crescendo num campinho verde.',
    pal: CN,
    itens: [
        M('Roda de Cenouras', 'Cenourinhas giram em volta da foto, com as folhinhas pra fora.', { t: 'icones', icones: ['cenoura'], pals: [CN], n: 10, tam: 28, giro: 56, orient: 'fora' }, { r: 'raro' }),
        N('Crocante', 'Laranja cenoura com um toque de verde-folha e contorno marrom.', { grad: ['#e8780a', '#ffc06a', '#6ac84a'], mov: 'desliza', dur: 5.4, contorno: '#7a3a00', cw: .9, fonte: 'redonda', peso: 900, icone: { nome: 'cenoura', pos: 'depois', pal: CN } }, { r: 'raro' }),
        Pl('Canteiro', 'Cenourinhas num canteiro de terra macia, andando devagar.', { base: ['#a8744a', '#8a5a34'], pad: { tipo: 'icones', icones: ['cenoura'], pals: [{ m: '#ff9a2a', o: '#ff9a2a', a: '#ff9a2a', w: -3 }, { m: '#ffc06a', o: '#ffc06a', a: '#ffc06a', w: -3 }], tam: 28, ti: 16, c2: 'transparent', rot: 25 }, mov: 'x', dur: 16, borda: 'rgba(60,30,10,.6)', icone: { nome: 'cenoura', pal: CN, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Campinho', 'Um campinho verde com cenouras espiando da terra e nuvens fofas passando.', {
            fundo: ['#bfe4ff', '#e6f6ff'], fixo: `${cena.terreno({ cor: '#7fd070', y: 72, amp: 7, n: 2 })}${cena.terreno({ cor: '#5ab854', y: 90, amp: 5, n: 3, fase: 1 })}${cena.icones({ nomes: ['cenoura'], pals: [CN], n: 9, tam: [14, 20], seed: 'cn1', y: [86, 104], rot: 10 })}`,
            longe: { svg: cena.nuvens({ cor: '#fff', n: 3, y: [10, 38], alfa: .95, seed: 'cn2' }), anim: 'pan', dur: 58 },
        }, { r: 'raro' }),
        EA('Cenouras ao Redor', 'Cenourinhas sobem dos lados da foto e uma aura laranja pulsa.', [
            { k: 'aura', cor: '#ff9a2a', dur: 3 },
            { k: 'sobe', icones: ['cenoura'], pals: [CN], n: 8, tam: 11, alt: 170 },
        ], { r: 'raro' }),
        EP('Chuva de Cenouras', 'Cenourinhas caem pelo cartão inteiro, girando devagar.', [
            { k: 'cai', icones: ['cenoura'], pals: [CN, { ...CN, m: '#ffb04a' }], n: 18, tam: [14, 26], vel: [6, 12], bal: 70, giro: 360 },
            { k: 'pisca', icone: 'estrelinha', pals: [{ m: '#fff', o: '#fff', w: 0 }], n: 8, tam: [6, 11] },
        ], { r: 'epico' }),
    ],
});

module.exports = [derby, live, cenouras];
