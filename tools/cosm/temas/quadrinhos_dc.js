'use strict';
/* HERÓIS E VILÕES DE QUADRINHOS (linha "ampla variedade"): cada um é um mini-tema com cara própria. Nomes genéricos e evocativos; símbolos desenhados por código. */
const { tema, M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P, I, fase } = require('../dsl');
const { cena } = P;
const { icone } = I;
const f1 = (n) => Math.round(n * 10) / 10;
const solido = (c) => ({ m: c, a: c, d: c, l: c, o: c, w: 0 });

// =====================================================================================================  GOTHAM
const YEL = { m: '#f2d02a', a: '#fff0a0', d: '#0a0a10', l: '#ffffff', o: '#000000' };
const ESC = { m: '#14141c', a: '#2a2a3a', d: '#14141c', l: '#f2d02a', o: '#f2d02a', w: 2.5 };
const sinal = `<path d='M262 112L226 6H298Z' fill='rgba(255,246,170,.3)'/><ellipse cx='262' cy='22' rx='22' ry='13' fill='#f2d02a' stroke='#05050a' stroke-width='2'/><g transform='translate(246 11) scale(.32)'><path d='M50 34L56 22 58 34C70 26 86 24 98 34 91 38 89 47 91 58 83 51 77 53 73 61 67 54 59 55 55 64L50 80 45 64C41 55 33 54 27 61 23 53 17 51 9 58 11 47 9 38 2 34 14 24 30 26 42 34L44 22Z' fill='#05050a'/></g>`;
const gotham = tema({
    id: 'gotham', pre: 'got', nome: 'Noite em Gotham', cat: 'quadrinhos', cor: '#f2d02a', cores: ['#f2d02a', '#1c2a40'], icone: 'fa-mask', premium: true,
    lema: 'A cidade dorme. Alguém não.',
    desc: 'Chuva, trovão, uma cidade gótica em silhueta, morcegos cruzando a lua e um sinal amarelo riscando as nuvens.',
    pal: YEL,
    itens: [
        M('Morcegos', 'Morcegos de asas abertas e ovais amarelos girando em volta da foto.', { t: 'icones', icones: ['morcego_oval', 'morcego'], pals: [YEL, ESC], n: 8, tam: 30, giro: 50, glow: '#f2d02a' }, { r: 'epico' }),
        N('Cavaleiro', 'Aço escuro e prata com contorno preto grosso, em letras secas e maiúsculas.', { grad: ['#7a8aa0', '#e8eef6', '#7a8aa0'], mov: 'desliza', dur: 7, contorno: '#05050a', cw: 1.3, fonte: 'impacto', espaco: 1.6, maius: true, peso: 900, sombra: [0, 0, 'transparent'] }, { r: 'epico' }),
        Pl('Grade de Gotham', 'Um preto de asfalto riscado em diagonal, com um brilho amarelo passando e um morcego oval.', { base: ['#0a0a10', '#171722'], pad: { tipo: 'riscado', c1: 'rgba(242,208,42,.2)', c2: 'transparent', tam: 14, lw: 1.3 }, mov: 'x', dur: 12, brilho: 'rgba(242,208,42,.32)', borda: 'rgba(242,208,42,.75)', icone: { nome: 'morcego_oval', pal: YEL, lado: 'dir', tam: 64 } }, { r: 'epico' }),
        F('Gotham', 'Uma cidade gótica em silhueta, a lua enorme e o sinal amarelo nas nuvens, com a chuva caindo.', {
            fundo: ['#05060c', '#12182a', '#2a3550'], fixo: `${cena.sol({ x: 80, y: 38, r: 24, c1: '#e8ecf6', c2: '#aab4c8' })}${sinal}${cena.skyline({ cor: '#06070d', altMin: 30, altMax: 80, larg: [9, 18], seed: 'gt1', antenas: true, janelas: { cor: '#f2d02a', dens: .12 } })}`,
            longe: { svg: `<g opacity='.5'>${cena.nuvens({ cor: '#1a2236', n: 3, y: [6, 44], tam: [20, 32], seed: 'gt2' })}</g>`, anim: 'pan', dur: 60 },
            perto: { svg: `<g stroke='#bcd7ff' stroke-width='.9' opacity='.5'>${[...Array(26)].map((_, k) => `<path d='M${(k * 13 + 4) % 340} ${(k * 37) % 100}l-4 12'/>`).join('')}</g>`, anim: 'pan', dur: 1.2, rev: true },
        }, { r: 'epico' }),
        EA('Sinal de Gotham', 'Um feixe de luz amarela sobe da foto até um sinal de morcego nas nuvens, com morcegos em órbita.', [
            { k: 'raw', html: `<b class="$C"><svg viewBox="0 0 160 160" class="fx"><path d="M62 54L52 -4H108L98 54Z" fill="rgba(255,246,170,.32)"/><ellipse cx="80" cy="-2" rx="26" ry="14" fill="#f2d02a" stroke="#05050a" stroke-width="2.4"/><g transform="translate(62 -13) scale(.36)"><path d="M50 34L56 22 58 34C70 26 86 24 98 34 91 38 89 47 91 58 83 51 77 53 73 61 67 54 59 55 55 64L50 80 45 64C41 55 33 54 27 61 23 53 17 51 9 58 11 47 9 38 2 34 14 24 30 26 42 34L44 22Z" fill="#05050a"/></g></svg></b>`, css: '.ef-av-$ID .fx{position:absolute;inset:0;width:100%;height:100%;overflow:visible;animation:k-$ID-fx 3.4s ease-in-out infinite}@keyframes k-$ID-fx{from{opacity:.55}to{opacity:1}}' },
            { k: 'orbita', icones: ['morcego'], pals: [ESC], n: 4, tam: 22, giro: 18, raio: 72 },
        ], { r: 'epico' }),
        EP('Noite em Gotham', 'Chuva forte, clarões de trovão, névoa e morcegos cruzando o cartão.', [
            { k: 'neblina', cor: '#8a9ab8', alfa: .28, n: 4 },
            { k: 'chuva', n: 44, cor: '#bcd7ff', alfa: .55, ang: 14 },
            { k: 'deriva', icones: ['morcego'], pals: [{ m: '#05050a', a: '#05050a', d: '#05050a', l: '#f2d02a', o: '#05050a', w: 0 }], n: 4, tam: [18, 30], vel: [8, 14], y: [4, 60], bal: 24, alfa: .95 },
            { k: 'flash', cor: '#dfe8ff', dur: 8, ini: 66 },
        ], { r: 'lendario' }),
        FALA('Voz na Noite', 'Quando você fala na call, o card acende em amarelo, como um sinal.', { cores: ['#f2d02a', '#1c2a40'] }),
        RADAR('Sinal no Radar', 'As ondas do radar viram anéis amarelos finos.', { cor: '#f2d02a', estilo: 'liso', glow: '#f2d02a' }),
        CHAT('Bat-Sinal', 'A barra de mensagem acende em amarelo ao digitar e solta morcegos ao enviar.', { cor: '#f2d02a', cor2: '#1c2a40', particula: { icone: 'morcego', pal: ESC } }),
        PIN('Morcego Oval', 'Suas notas no mapa viram o oval amarelo com um morcego.', { icone: 'morcego_oval', pal: YEL, bal: 3 }),
        SOM('Trovão', 'Um trovão distante que rola e um morcego passando, ao entrar na call.', { notas: [{ t: 0, f: 60, f2: 38, d: 1, tipo: 'sawtooth', v: .5 }, { t: .5, f: 2400, f2: 1200, d: .2, tipo: 'sine', v: .2 }], ruidos: [{ t: 0, d: 1.1, f: 420, f2: 90, filtro: 'lowpass', v: .8, q: .7 }] }),
        SERV('Servidor de Gotham', 'O ícone do servidor brilha em amarelo.', { cores: ['#f2d02a', '#1c2a40'] }),
    ],
});

// =====================================================================================================  KRYPTON
const KR = { m: '#d4161e', a: '#ff6a6a', d: '#0a1a4a', l: '#ffffff', o: '#1a0a0a' };
const capa = `<svg viewBox="0 0 160 160" class="cp"><path d="M50 104C38 122 36 142 44 156Q62 148 80 158T116 156C124 142 122 122 110 104Z" fill="#d4161e" stroke="#5a0a10" stroke-width="2.4" stroke-linejoin="round"/><path d="M62 112C58 128 60 142 64 152M80 114V154M98 112C102 128 100 142 96 152" fill="none" stroke="#8a0a14" stroke-width="2.2" stroke-linecap="round" opacity=".6"/></svg>`;
const krypton = tema({
    id: 'krypton', pre: 'kry', nome: 'Filho do Sol', cat: 'quadrinhos', cor: '#d4161e', cores: ['#d4161e', '#1a4a9a'], icone: 'fa-shield-halved', premium: true,
    lema: 'Esperança em forma de escudo.',
    desc: 'O escudo vermelho e amarelo, a capa ao vento, a luz do sol e o brilho vermelho do olhar que queima.',
    pal: KR,
    itens: [
        M('Escudos', 'Escudos vermelhos e amarelos de pontas arredondadas em volta da foto.', { t: 'icones', icones: ['escudo_krypton'], pals: [KR], n: 8, tam: 30, giro: 60, glow: '#ffd23f' }, { r: 'epico' }),
        N('Aço do Amanhã', 'Vermelho e azul com contorno amarelo, em letras de capa de revista.', { grad: ['#d4161e', '#1a4a9a', '#d4161e'], mov: 'desliza', dur: 5.4, contorno: '#ffd23f', cw: 1.1, fonte: 'impacto', espaco: 1, peso: 900 }, { r: 'epico' }),
        Pl('Capa', 'O vermelho de uma capa com dobras que ondulam e um escudo ao lado.', { base: ['#c8101a', '#8a0a12'], pad: { tipo: 'ondas', c1: 'rgba(255,255,255,.16)', c2: 'transparent', tam: 18 }, mov: 'x', dur: 9, brilho: 'rgba(255,255,255,.35)', borda: '#ffd23f', icone: { nome: 'escudo_krypton', pal: KR, lado: 'dir', tam: 66 } }, { r: 'epico' }),
        F('Metrópole', 'Uma cidade clara sob um céu azul, o sol amarelo no alto e nuvens passando.', {
            fundo: ['#4a8ad8', '#9ac8f8', '#fff0b0'], fixo: `${cena.sol({ x: 262, y: 34, r: 22, c1: '#fff7c0', c2: '#ffd23f' })}${cena.skyline({ cor: '#e8f0fa', altMin: 26, altMax: 76, larg: [9, 20], seed: 'kr1', antenas: true, janelas: { cor: '#7aa8e8', dens: .25 } })}`,
            longe: { svg: cena.nuvens({ cor: '#ffffff', n: 3, y: [8, 48], alfa: .95, seed: 'kr2' }), anim: 'pan', dur: 44 },
            perto: { svg: cena.nuvens({ cor: '#ffffff', n: 2, y: [52, 90], alfa: .6, seed: 'kr3', tam: [10, 16] }), anim: 'pan', dur: 22 },
        }, { r: 'epico' }),
        EA('Capa ao Vento', 'Uma capa vermelha ondula atrás da foto, como num voo, com um brilho de sol.', [
            { k: 'aura', cor: '#ffd23f', dur: 3 },
            { k: 'raw', html: `<b class="$C">${capa}</b>`, css: '.ef-av-$ID .cp{position:absolute;inset:0;width:100%;height:100%;overflow:visible;transform-origin:50% 62%;animation:k-$ID-cp 2.2s ease-in-out infinite alternate}@keyframes k-$ID-cp{from{transform:skewX(-5deg) scaleY(.97)}to{transform:skewX(5deg) scaleY(1.04)}}' },
        ], { r: 'epico', id: 'kry_capa_ao_vento' }),
        EP('Olhar de Calor', 'Dois feixes vermelhos cruzam o cartão num clarão, sob raios de sol que sobem.', [
            { k: 'clima', fundo: 'radial-gradient(ellipse at 50% 0%,rgba(255,210,63,.6),transparent 62%)', min: .4, max: 1, dur: 4 },
            { k: 'raw', html: '<i class="h1"></i><i class="h2"></i>', css: `.ef-pf-$ID .h1,.ef-pf-$ID .h2{position:absolute;left:-10%;width:120%;height:8px;opacity:0;background:linear-gradient(90deg,transparent,#ff2a2a 20%,#ffd0a0 50%,#ff2a2a 80%,transparent);filter:drop-shadow(0 0 8px #ff2a2a);transform-origin:0 50%}.ef-pf-$ID .h1{top:30%;transform:rotate(14deg);animation:k-$ID-h 6s ease-out ${fase(6, .42)} infinite}.ef-pf-$ID .h2{top:50%;transform:rotate(-14deg);animation:k-$ID-h 6s ease-out calc(${fase(6, .42)} + .08s) infinite}@keyframes k-$ID-h{0%,32%{opacity:0;clip-path:inset(0 100% 0 0)}38%{opacity:1;clip-path:inset(0 0 0 0)}52%{opacity:1}60%,100%{opacity:0;clip-path:inset(0 0 0 0)}}` },
            { k: 'sobe', icones: ['brilho'], pals: [{ m: '#fff7c0', o: '#ffd23f', w: 2 }], n: 10, tam: [8, 14], vel: [5, 9] },
        ], { r: 'epico' }),
        FALA('Voz de Esperança', 'Quando você fala na call, o card acende em vermelho e azul.', { cores: ['#d4161e', '#1a4a9a'] }),
        RADAR('Onda de Sol', 'As ondas do radar viram anéis amarelos.', { cor: '#ffd23f', estilo: 'liso', glow: '#d4161e' }),
        PIN('Escudo', 'Suas notas no mapa viram um escudo vermelho e amarelo.', { icone: 'escudo_krypton', pal: KR }),
        SOM('Voo', 'Um estrondo de voo supersônico que sobe e se afasta, ao entrar na call.', { notas: [{ t: 0, f: 120, f2: 900, d: .55, tipo: 'sawtooth', v: .3 }], ruidos: [{ t: 0, d: .7, f: 200, f2: 4000, filtro: 'bandpass', v: .7, q: 1 }, { t: .5, d: .15, f: 70, filtro: 'lowpass', v: .9 }] }),
    ],
});

// =====================================================================================================  TEMISCIRA
const OR = { m: '#e8b82a', a: '#fff0a0', d: '#5a3a00', l: '#ffffff', o: '#8a5a00' };
const AM2 = { m: '#c8202a', a: '#ff6a70', d: '#3a0a10', l: '#ffffff', o: '#5a0a10' };
const temiscira = tema({
    id: 'temiscira', pre: 'tem', nome: 'Ilha das Amazonas', cat: 'quadrinhos', cor: '#e8b82a', cores: ['#e8b82a', '#c8202a'], icone: 'fa-star',
    lema: 'A verdade é dourada.',
    desc: 'Um laço dourado, a estrela vermelha, braceletes que faíscam e uma ilha de colunas brancas sobre o mar.',
    pal: OR,
    itens: [
        M('Laço Dourado', 'Elos de ouro em volta da foto, como um laço que gira devagar.', { t: 'icones', icones: ['elo'], pals: [{ ...OR, m: '#e8b82a', a: '#fff0a0', o: '#8a5a00' }], n: 14, tam: 26, giro: 62, glow: '#ffe066' }, { r: 'raro' }),
        N('Amazona', 'Ouro polido com contorno vinho, em letras clássicas.', { grad: ['#b8801a', '#fff0a0', '#b8801a'], mov: 'desliza', dur: 5, contorno: '#5a0a10', cw: 1, fonte: 'classica', peso: 900, espaco: .5 }, { r: 'raro' }),
        Pl('Braceletes', 'Ouro com estrelas vermelhas que brilham e uma estrela maior ao lado.', { base: ['#e8b82a', '#b8801a'], pad: { tipo: 'icones', icones: ['estrelinha'], pals: [solido('#c8202a'), solido('#fff0a0')], tam: 24, ti: 10, c2: 'transparent' }, mov: 'x', dur: 12, brilho: 'rgba(255,255,255,.5)', borda: '#5a3a00', texto: '#3a1a00', icone: { nome: 'estrela', pal: AM2, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Ilha Paraíso', 'Colunas brancas num templo à beira-mar, o céu rosa e dourado do entardecer e o mar azul.', {
            fundo: ['#ff9ec4', '#ffd0a0', '#fff0c0'], fixo: `${cena.sol({ x: 250, y: 46, r: 22, c1: '#fff7c0', c2: '#ffb04a' })}${cena.terreno({ cor: '#2a7ac0', y: 82, amp: 3, n: 4 })}<g fill='#f6f0e6' stroke='#c8b89a' stroke-width='1'>${[0, 1, 2, 3, 4].map((k) => `<rect x='${40 + k * 22}' y='38' width='9' height='44'/><rect x='${37 + k * 22}' y='34' width='15' height='5'/><rect x='${37 + k * 22}' y='80' width='15' height='4'/>`).join('')}<path d='M32 34L100 14 168 34Z'/></g>`,
            longe: { svg: cena.nuvens({ cor: '#fff', n: 3, y: [8, 36], alfa: .85, seed: 'tm1' }), anim: 'pan', dur: 56 },
            perto: { svg: cena.icones({ nomes: ['brilho'], pals: [{ m: '#fff', o: '#ffb04a', w: 2 }], n: 8, tam: [6, 10], seed: 'tm2', y: [84, 108] }), anim: 'pisca', dur: 2 },
        }, { r: 'raro' }),
        EA('Estrela Dourada', 'Estrelas de ouro giram em volta da foto, com um anel vermelho e uma luz dourada.', [
            { k: 'aura', cor: '#ffd23f', dur: 2.6 },
            { k: 'anel', cor: '#c8202a', r: 68, esp: 2.6, dash: '6 6', giro: 20 },
            { k: 'orbita', icones: ['estrela'], pals: [OR], n: 5, tam: 24, giro: 24 },
        ], { r: 'raro' }),
        EP('Laço da Verdade', 'Anéis dourados se desenham do centro pra fora no cartão, com faíscas de ouro subindo.', [
            { k: 'raw', html: `<svg class="lc" viewBox="0 0 340 440">${[34, 70, 110, 154, 202].map((r, k) => `<circle pathLength="1" cx="170" cy="190" r="${r}" fill="none" stroke="#e8b82a" stroke-width="${5 - k * .6}" stroke-linecap="round" style="--i:${k * .6}"/>`).join('')}</svg>`,
              css: `.ef-pf-$ID .lc{position:absolute;inset:0;width:100%;height:100%;overflow:visible;filter:drop-shadow(0 0 6px rgba(255,224,102,.9))}.ef-pf-$ID .lc circle{stroke-dasharray:1;stroke-dashoffset:1;transform-origin:170px 190px;animation:k-$ID-lc 8s ease-out calc(var(--i) * 1s + ${fase(8, .5)}) infinite}@keyframes k-$ID-lc{0%{stroke-dashoffset:1;opacity:1;transform:rotate(-90deg)}14%{stroke-dashoffset:0}70%{stroke-dashoffset:0;opacity:1}86%,100%{stroke-dashoffset:0;opacity:0}}` },
            { k: 'sobe', icones: ['brilho', 'estrelinha'], pals: [{ m: '#fff0a0', o: '#e8b82a', w: 2 }, solido('#ffe066')], n: 12, tam: [8, 14], vel: [5, 9] },
        ], { r: 'epico' }),
        PIN('Estrela', 'Suas notas no mapa viram uma estrela vermelha com contorno dourado.', { icone: 'estrela', pal: AM2 }),
        SOM('Brilho Dourado', 'Um tilintar de metal dourado e um acorde luminoso, ao entrar na call.', { notas: [{ t: 0, f: 1318.5, d: .6, tipo: 'sine', v: .5 }, { t: .06, f: 1760, d: .55, tipo: 'sine', v: .4 }, { t: .12, f: 2217, d: .5, tipo: 'sine', v: .3 }, { t: .18, f: 2637, d: .45, tipo: 'sine', v: .25 }], ruidos: [{ t: 0, d: .1, f: 6000, filtro: 'highpass', v: .35 }] }),
    ],
});

// =====================================================================================================  VELOCISTA
const VE = { m: '#ffd23f', a: '#fff0a0', d: '#7a1010', l: '#ffffff', o: '#7a1010' };
const velocista = tema({
    id: 'velocista', pre: 'vel', nome: 'Força da Velocidade', cat: 'quadrinhos', cor: '#ffd23f', cores: ['#e22a2a', '#ffd23f'], icone: 'fa-bolt-lightning',
    lema: 'Antes de você piscar.',
    desc: 'Raios amarelos em rastro vermelho, imagens residuais pra trás e faíscas de velocidade: tudo rápido demais.',
    pal: VE,
    itens: [
        M('Raios', 'Raios amarelos e vermelhos girando rápido em volta da foto.', { t: 'icones', icones: ['raio'], pals: [VE, { ...VE, m: '#ff4a3a', a: '#ff9a8a', o: '#4a0a0a' }], n: 12, tam: 26, giro: 9, glow: '#ffd23f' }, { r: 'raro' }),
        N('Rápido', 'Amarelo e vermelho que correm pelas letras, com sombra deslocada.', { grad: ['#ffd23f', '#ff4a3a', '#ffd23f'], mov: 'desliza', dur: 1.1, contorno: '#4a0a0a', cw: 1.1, fonte: 'impacto', espaco: 1, sombra: [1.5, 1.5, '#4a0a0a'], peso: 900 }, { r: 'raro' }),
        Pl('Rastro', 'Riscos de velocidade amarelos sobre o vermelho, correndo, e um raio ao lado.', { base: ['#e22a2a', '#9a1010'], pad: { tipo: 'riscado', c1: 'rgba(255,210,63,.45)', c2: 'transparent', tam: 10, lw: 1.6 }, mov: '-x', dur: 1.1, borda: '#ffd23f', icone: { nome: 'raio', pal: VE, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Rastro de Raios', 'Riscos de velocidade e raios amarelos correndo sobre o vermelho, sem parar.', {
            fundo: ['#7a1010', '#e22a2a', '#ff7a2a'], fixo: `<g stroke='#ffd23f' stroke-width='1.6' opacity='.5'>${[...Array(14)].map((_, k) => `<path d='M0 ${8 + k * 8}H${60 + (k * 37) % 220}'/>`).join('')}</g>`,
            longe: { svg: `<g stroke='#ffe9a0' stroke-width='2' opacity='.7'>${[...Array(10)].map((_, k) => `<path d='M${(k * 41) % 300} ${6 + k * 11}h${50 + (k * 23) % 60}'/>`).join('')}</g>`, anim: 'pan', dur: 1.6, rev: true },
            perto: { svg: cena.icones({ nomes: ['raio'], pals: [VE], n: 7, tam: [10, 16], seed: 've1', y: [6, 100], rot: 10 }), anim: 'pan', dur: 3, rev: true },
        }, { r: 'raro' }),
        EA('Imagens Residuais', 'Discos amarelos e vermelhos ficam pra trás da sua foto, como imagens que não alcançaram você.', [
            { k: 'raw', html: '<b class="$C"></b><b class="$C b"></b><b class="$C c"></b>', css: '.ef-av-$ID .$C{inset:18.8%;border-radius:50%;background:radial-gradient(circle,rgba(255,210,63,.55),rgba(255,210,63,0) 72%);animation:k-$ID-r 1.4s ease-out infinite}.ef-av-$ID .$C.b{background:radial-gradient(circle,rgba(226,42,42,.55),rgba(226,42,42,0) 72%);animation-delay:-.47s}.ef-av-$ID .$C.c{background:radial-gradient(circle,rgba(255,255,255,.4),rgba(255,255,255,0) 72%);animation-delay:-.93s}@keyframes k-$ID-r{0%{opacity:.9;transform:translateX(0) scale(1)}100%{opacity:0;transform:translateX(-34%) scale(.9)}}' },
            { k: 'faiscas', icone: 'raio', pals: [VE], n: 6, tam: 10, raio: 40 },
        ], { r: 'raro' }),
        EP('Faíscas de Velocidade', 'Raios atravessam o cartão de um lado a outro, em clarões amarelos.', [
            { k: 'clima', fundo: 'linear-gradient(100deg,rgba(226,42,42,.5),transparent 60%,rgba(255,210,63,.4))', min: .3, max: 1, dur: 1.6 },
            { k: 'deriva', icones: ['raio'], pals: [VE], n: 14, tam: [14, 26], vel: [1.2, 2.6], y: [0, 100], bal: 10 },
            { k: 'flash', cor: '#fff0a0', dur: 3.5, ini: 70 },
        ], { r: 'epico' }),
        SOM('Zum', 'Um zumbido que sobe numa fração de segundo e um estalo de raio, ao entrar na call.', { notas: [{ t: 0, f: 150, f2: 1800, d: .3, tipo: 'sawtooth', v: .35 }], ruidos: [{ t: .26, d: .12, f: 5000, f2: 1000, filtro: 'bandpass', v: .8, q: 1.6 }] }),
    ],
});

// =====================================================================================================  VONTADE
const VD = { m: '#2ee86a', a: '#9affbd', d: '#04200e', l: '#e8fff0', o: '#04401c' };
const vontade = tema({
    id: 'vontade', pre: 'von', nome: 'Força de Vontade', cat: 'quadrinhos', cor: '#2ee86a', cores: ['#2ee86a', '#04200e'], icone: 'fa-ring',
    lema: 'No dia mais claro, na noite mais escura.',
    desc: 'Verde-esmeralda: o símbolo, o anel que cria o que você imaginar, construtos de luz e uma energia que não acaba.',
    pal: VD,
    itens: [
        M('Anel da Vontade', 'O símbolo verde, repetido em volta da foto, girando com um brilho esmeralda.', { t: 'icones', icones: ['simbolo_vontade'], pals: [VD], n: 8, tam: 30, giro: 52, glow: '#2ee86a' }, { r: 'raro' }),
        N('Vontade', 'Verde esmeralda que respira, com contorno escuro e letras redondas.', { grad: ['#16b84a', '#c8ffd8', '#16b84a'], mov: 'pulsa', brilho: '#2ee86a', bw: 3, contorno: '#04200e', cw: 1, fonte: 'redonda', peso: 900, dur: 2.6 }, { r: 'raro' }),
        Pl('Circuito de Luz', 'Linhas de energia verde sobre o escuro, com um brilho correndo e o símbolo ao lado.', { base: ['#04200e', '#08381a'], pad: { tipo: 'grade', c1: 'rgba(46,232,106,.3)', c2: 'transparent', tam: 14, lw: 1 }, mov: 'x', dur: 10, brilho: 'rgba(46,232,106,.4)', borda: 'rgba(46,232,106,.75)', icone: { nome: 'simbolo_vontade', pal: VD, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Setor Espacial', 'O espaço profundo com estrelas, um planeta e feixes de energia verde cruzando.', {
            fundo: ['#02080a', '#062a18', '#0a5a2a'], fixo: `${cena.estrelas({ cor: '#fff', n: 36, seed: 'vn1', r: [.5, 1.5] })}<circle cx='270' cy='70' r='26' fill='#0a3a22' stroke='#2ee86a' stroke-width='1.6'/><path d='M-10 90L360 20' stroke='#2ee86a' stroke-width='4' opacity='.4'/><path d='M-10 96L360 26' stroke='#9affbd' stroke-width='1.4' opacity='.8'/>`,
            longe: { svg: cena.icones({ nomes: ['hexagono'], pals: [{ m: '#2ee86a', o: '#2ee86a', w: -6 }], n: 6, tam: [10, 20], seed: 'vn2', y: [6, 100], alfa: .5 }), anim: 'pan', dur: 40 },
            perto: { svg: cena.estrelas({ cor: '#9affbd', n: 14, seed: 'vn3' }), anim: 'pisca', dur: 2 },
        }, { r: 'raro' }),
        EA('Construto', 'Hexágonos de luz verde giram em volta da foto, num escudo de energia.', [
            { k: 'aura', cor: '#2ee86a', dur: 2.2 },
            { k: 'orbita', icones: ['hexagono'], pals: [VD], n: 8, tam: 22, giro: 20 },
            { k: 'anel', cor: '#9affbd', r: 66, esp: 2, dash: '5 6', giro: 14, rev: true },
        ], { r: 'raro' }),
        EP('Energia Esmeralda', 'Cristais e hexágonos de luz verde sobem pelo cartão numa energia que não para.', [
            { k: 'clima', fundo: 'radial-gradient(ellipse at 50% 100%,rgba(46,232,106,.55),transparent 65%)', min: .3, max: 1, dur: 3.4 },
            { k: 'sobe', icones: ['hexagono', 'cristal_hex'], pals: [VD, { ...VD, m: '#9affbd' }], n: 14, tam: [10, 22], vel: [6, 11], alfa: .9 },
            { k: 'borda', cor: '#2ee86a', alfa: .45, dur: 3 },
        ], { r: 'epico' }),
        PIN('Símbolo', 'Suas notas no mapa viram o símbolo verde.', { icone: 'simbolo_vontade', pal: VD, bal: 2.6 }),
        SOM('Juramento', 'Um brilho verde que sobe em escala e se espalha, ao entrar na call.', { notas: [{ t: 0, f: 392, d: .5, tipo: 'sine', v: .5 }, { t: .12, f: 587.3, d: .5, tipo: 'sine', v: .45 }, { t: .24, f: 784, d: .6, tipo: 'sine', v: .4 }, { t: .36, f: 1174.7, d: .7, tipo: 'triangle', v: .35 }], ruidos: [{ t: .3, d: .5, f: 1000, f2: 5000, filtro: 'bandpass', v: .25 }] }),
    ],
});

// =====================================================================================================  ATLÂNTIDA
const AT = { m: '#1fb8b8', a: '#8aeaea', d: '#04303a', l: '#e8ffff', o: '#0a6a70' };
const OUROAT = { m: '#e8a82a', a: '#ffe08a', d: '#5a3a00', l: '#fff', o: '#8a5a00' };
const raiosMar = `<defs><linearGradient id='rm' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#bfffff' stop-opacity='.55'/><stop offset='1' stop-color='#bfffff' stop-opacity='0'/></linearGradient></defs>${[40, 120, 200, 280].map((x, k) => `<path d='M${x} 0L${x + 30} 0L${x + 70 + k * 6} 112L${x + 10} 112Z' fill='url(#rm)'/>`).join('')}`;
const atlantida = tema({
    id: 'atlantida', pre: 'atl', nome: 'Reino Submerso', cat: 'quadrinhos', cor: '#1fb8b8', cores: ['#1fb8b8', '#e8a82a'], icone: 'fa-water',
    lema: 'O mar é grande. E tem dono.',
    desc: 'O fundo do mar: ondas verde-água, um tridente dourado, raios de luz atravessando a água e bolhas subindo.',
    pal: AT,
    itens: [
        M('Maré', 'Uma coroa de ondas verde-água em volta da foto, girando devagar.', { t: 'forma', forma: 'ondas', n: 14, amp: 6, esp: 12, cor: '#1fb8b8', cor2: '#0a6a90', linha: '#04303a', lw: 2.2, pontos: '#e8ffff', giro: 90 }, { r: 'raro' }),
        N('Rei dos Mares', 'Verde-água e dourado, com contorno azul-escuro, como uma coroa debaixo d\'água.', { grad: ['#1fb8b8', '#ffe08a', '#1fb8b8'], mov: 'desliza', dur: 6, contorno: '#04303a', cw: 1, fonte: 'classica', peso: 900 }, { r: 'raro' }),
        Pl('Águas', 'Ondas brancas sobre o azul-profundo e um tridente dourado ao lado.', { base: ['#0a4a6a', '#0e6a8a'], pad: { tipo: 'ondas', c1: 'rgba(255,255,255,.22)', c2: 'transparent', tam: 16 }, mov: 'x', dur: 8, brilho: 'rgba(191,255,255,.35)', borda: 'rgba(232,168,42,.8)', icone: { nome: 'tridente', pal: OUROAT, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Fundo do Mar', 'Raios de luz atravessando a água, corais em silhueta e peixes e bolhas passando.', {
            fundo: ['#0a5a8a', '#083a5a', '#041a30'], fixo: `${raiosMar}${cena.cristais({ cor: '#e8603a', cor2: '#a8381a', n: 9, alt: [14, 40], seed: 'at1', larg: [8, 14] })}${cena.terreno({ cor: '#0a2a3a', y: 100, amp: 3, n: 3 })}`,
            longe: { svg: cena.icones({ nomes: ['peixe'], pals: [{ m: '#e8a82a', a: '#ffe08a', d: '#5a3a00', l: '#fff', o: '#8a5a00' }, { m: '#e87a1a', o: '#8a3a00' }], n: 4, tam: [10, 16], seed: 'at2', y: [14, 80], alfa: .9 }), anim: 'pan', dur: 24 },
            perto: { svg: cena.icones({ nomes: ['bolha'], pals: [{ m: '#bfffff', o: '#7adcdc' }], n: 9, tam: [5, 10], seed: 'at3', y: [4, 108], alfa: .7 }), anim: 'pan', dur: 10, rev: true },
        }, { r: 'raro' }),
        EA('Bolhas do Fundo', 'Bolhas sobem em volta da foto, com uma luz verde-água e conchas em órbita.', [
            { k: 'aura', cor: '#1fb8b8', dur: 3 },
            { k: 'sobe', icones: ['bolha'], pals: [{ m: '#bfffff', o: '#7adcdc' }], n: 8, tam: 10, alt: 170 },
            { k: 'orbita', icones: ['concha'], pals: [{ m: '#ffd0e4', a: '#ffe8f2', d: '#a8486a', l: '#fff', o: '#a8486a' }], n: 3, tam: 22, giro: 30 },
        ], { r: 'raro' }),
        EP('Maré Alta', 'A água sobe no cartão em ondas, com bolhas e névoa verde-água.', [
            { k: 'neblina', cor: '#1fb8b8', alfa: .3, n: 4 },
            { k: 'ondas', cor: '#1fb8b8', alt: 22, dur: 8, alfa: .5 },
            { k: 'sobe', icones: ['bolha'], pals: [{ m: '#bfffff', o: '#7adcdc' }], n: 16, tam: [8, 20], vel: [6, 12], alfa: .85 },
        ], { r: 'epico' }),
        PIN('Tridente', 'Suas notas no mapa viram um tridente dourado.', { icone: 'tridente', pal: OUROAT }),
        SOM('Maré', 'Uma onda que quebra e o eco de um sino submerso, ao entrar na call.', { notas: [{ t: .3, f: 392, d: 1, tipo: 'sine', v: .4 }, { t: .3, f: 589, d: .9, tipo: 'sine', v: .2 }], ruidos: [{ t: 0, d: .9, f: 300, f2: 1600, filtro: 'bandpass', v: .5, q: .6 }] }),
    ],
});

// =====================================================================================================  CAOS (vilão de cartas)
const CA = { m: '#6a2a9a', a: '#a46ad8', d: '#14041e', l: '#ffffff', o: '#14041e' };
const CAV = { m: '#4ae04a', a: '#9aff9a', d: '#0a3a0a', l: '#ffffff', o: '#0a3a0a' };
const caos = tema({
    id: 'caos', pre: 'cao', nome: 'Palhaço do Caos', cat: 'quadrinhos', cor: '#6a2a9a', cores: ['#6a2a9a', '#4ae04a'], icone: 'fa-masks-theater',
    lema: 'Por que tão sério?',
    desc: 'Roxo e verde-ácido: cartas voando, confete, gargalhada e uma casa de apostas onde nada é o que parece.',
    pal: CA,
    itens: [
        M('Cartas', 'Cartas de baralho roxas e verdes inclinadas em volta da foto.', { t: 'icones', icones: ['carta'], pals: [{ ...CA, m: '#6a2a9a' }, { ...CA, m: '#2ab82a', o: '#0a3a0a' }], n: 8, tam: 30, giro: 44, inclina: true }, { r: 'raro' }),
        N('Risada', 'Verde-ácido com um tremor de glitch roxo, em letras de gibi.', { grad: ['#2ab82a', '#c8ff9a', '#2ab82a'], mov: 'glitch', g1: '#6a2a9a', g2: '#ff2a8a', dur: 3.2, contorno: '#14041e', cw: 1.2, fonte: 'quadrinho', peso: 900, sombra: [1.4, 1.4, '#14041e'] }, { r: 'raro' }),
        Pl('Baralho', 'Losangos verdes sobre o roxo de uma mesa de cartas, e uma carta ao lado.', { base: ['#3a1060', '#6a2a9a'], pad: { tipo: 'losangos', c1: 'rgba(74,224,74,.32)', c2: 'transparent', tam: 18 }, mov: 'x', dur: 12, brilho: 'rgba(200,255,154,.3)', borda: '#4ae04a', icone: { nome: 'carta', pal: { ...CA, m: '#2ab82a', o: '#0a3a0a' }, lado: 'dir', tam: 64 } }, { r: 'raro' }),
        F('Cassino do Caos', 'Um salão roxo e verde de cartas e confete passando, com holofotes cortando a fumaça.', {
            fundo: ['#14041e', '#3a1060', '#2a7a2a'], fixo: `<path d='M60 0L20 112H100Z' fill='rgba(200,255,154,.16)'/><path d='M250 0L210 112H290Z' fill='rgba(164,106,216,.22)'/>`,
            longe: { svg: cena.icones({ nomes: ['carta'], pals: [{ ...CA, m: '#6a2a9a' }, { ...CA, m: '#2ab82a', o: '#0a3a0a' }], n: 6, tam: [14, 22], seed: 'ca1', y: [10, 100], rot: 30 }), anim: 'pan', dur: 34 },
            perto: { svg: cena.icones({ nomes: ['confete'], pals: [{ m: '#4ae04a', a: '#a46ad8', l: '#fff' }], n: 8, tam: [8, 13], seed: 'ca2', y: [6, 100] }), anim: 'pan', dur: 14 },
        }, { r: 'raro' }),
        EA('Cartas Voando', 'Cartas giram em volta da foto e confete sobe dos lados.', [
            { k: 'aura', cor: '#4ae04a', dur: 2.4 },
            { k: 'orbita', icones: ['carta'], pals: [{ ...CA, m: '#6a2a9a' }, { ...CA, m: '#2ab82a', o: '#0a3a0a' }], n: 6, tam: 24, giro: 22, inclina: true },
            { k: 'sobe', icones: ['confete'], pals: [{ m: '#4ae04a', a: '#a46ad8', l: '#fff' }], n: 6, tam: 9, alt: 160 },
        ], { r: 'raro' }),
        EP('Gargalhada', 'Um "HA HA HA" pulsa sobre o cartão, com confete e cartas caindo e clarões verdes.', [
            { k: 'cai', icones: ['confete', 'carta'], pals: [{ m: '#4ae04a', a: '#a46ad8', l: '#fff' }, { ...CA, m: '#6a2a9a' }], n: 16, tam: [10, 20], vel: [4, 8], bal: 60, giro: 300 },
            { k: 'raw', html: '<b class="ha">HA HA HA</b>', css: `.ef-pf-$ID .ha{position:absolute;left:0;right:0;top:38%;text-align:center;font:900 17cqw/1 Impact,'Arial Black',sans-serif;color:#4ae04a;-webkit-text-stroke:2.4px #14041e;paint-order:stroke fill;text-shadow:0 0 18px rgba(74,224,74,.75);opacity:0;animation:k-$ID-ha 6s ease-out ${fase(6, .4)} infinite}@keyframes k-$ID-ha{0%,28%{opacity:0;transform:scale(.5) rotate(-6deg)}34%{opacity:1;transform:scale(1.1) rotate(-4deg)}38%{transform:scale(.96) rotate(-4deg)}42%{transform:scale(1.06) rotate(-4deg)}46%,62%{opacity:1;transform:scale(1) rotate(-4deg)}72%,100%{opacity:0;transform:scale(1.1) rotate(-4deg)}}` },
            { k: 'flash', cor: '#9aff9a', dur: 6, ini: 30 },
        ], { r: 'lendario' }),
        PIN('Carta', 'Suas notas no mapa viram uma carta de baralho.', { icone: 'carta', pal: { ...CA, m: '#6a2a9a' }, bal: 2.6 }),
        SOM('Risada', 'Uma gargalhada sintetizada, aguda e descendo aos solavancos, ao entrar na call.', { notas: [{ t: 0, f: 620, f2: 440, d: .12, tipo: 'sawtooth', v: .5 }, { t: .15, f: 660, f2: 460, d: .12, tipo: 'sawtooth', v: .5 }, { t: .3, f: 600, f2: 420, d: .12, tipo: 'sawtooth', v: .5 }, { t: .45, f: 560, f2: 380, d: .12, tipo: 'sawtooth', v: .45 }, { t: .6, f: 520, f2: 340, d: .22, tipo: 'sawtooth', v: .4 }], ruidos: [] }),
    ],
});

// =====================================================================================================  ARLEQUINA
const AR = { m: '#e2203a', a: '#ff7a8a', d: '#14040a', l: '#ffffff', o: '#14040a' };
const arlequina = tema({
    id: 'arlequina', pre: 'arl', nome: 'Circo de Losangos', cat: 'quadrinhos', cor: '#e2203a', cores: ['#e2203a', '#2a6aff'], icone: 'fa-diamond',
    lema: 'Travessura é um jeito de amar.',
    desc: 'Losangos vermelhos e pretos, balões voando, piruetas e a alegria do caos: um circo de cores berrantes.',
    pal: AR,
    itens: [
        M('Losangos', 'Diamantes vermelhos e pretos, com um toque de azul, girando em volta da foto.', { t: 'icones', icones: ['diamante'], pals: [AR, { ...AR, m: '#14040a', a: '#3a1a22', d: '#e2203a', o: '#e2203a', w: 3 }, { ...AR, m: '#2a6aff', a: '#7aa0ff', o: '#0a1a4a' }], n: 10, tam: 24, giro: 50 }, { r: 'raro' }),
        N('Travessura', 'Vermelho e preto em cores secas, como uma fantasia de losangos.', { grad: ['#e2203a', '#14040a', '#2a6aff', '#14040a'], passos: true, mov: 'desliza', dur: 3.4, contorno: '#ffffff', cw: .9, fonte: 'quadrinho', peso: 900 }, { r: 'raro' }),
        Pl('Xadrez de Circo', 'Losangos vermelhos e pretos andando, com um balão ao lado.', { base: ['#14040a', '#2a0a12'], pad: { tipo: 'losangos', c1: '#e2203a', c2: 'transparent', tam: 16 }, mov: 'x', dur: 10, borda: '#ffffff', icone: { nome: 'balao', pal: { ...AR, m: '#2a6aff', o: '#0a1a4a' }, lado: 'dir', tam: 64 } }, { r: 'raro' }),
        F('Tenda do Circo', 'Uma tenda de listras vermelhas e brancas, balões flutuando e confete caindo.', {
            fundo: ['#2a0a12'], fixo: `${cena.cortina({ cores: ['#e2203a', '#ffffff'], larg: 24 })}<path d='M0 70H340V112H0Z' fill='#14040a'/><path d='M0 70Q85 52 170 70T340 70' fill='#14040a'/>`,
            longe: { svg: cena.icones({ nomes: ['balao'], pals: [{ ...AR, m: '#2a6aff', o: '#0a1a4a' }, AR, { ...AR, m: '#ffd23f', o: '#8a5a00' }], n: 6, tam: [14, 22], seed: 'al1', y: [10, 70], rot: 10 }), anim: 'pan', dur: 36 },
            perto: { svg: cena.icones({ nomes: ['confete'], pals: [{ m: '#e2203a', a: '#2a6aff', l: '#ffd23f' }], n: 8, tam: [8, 13], seed: 'al2', y: [6, 100] }), anim: 'pan', dur: 12 },
        }, { r: 'raro' }),
        EA('Pirueta', 'Balões e estrelas giram em volta da foto, com uma luz vermelha pulsando.', [
            { k: 'aura', cor: '#e2203a', dur: 2.4 },
            { k: 'orbita', icones: ['balao', 'estrela'], pals: [{ ...AR, m: '#2a6aff', o: '#0a1a4a' }, { m: '#ffd23f', a: '#fff0a0', d: '#8a5a00', l: '#fff', o: '#8a5a00' }], n: 6, tam: 24, giro: 20, inclina: true },
        ], { r: 'raro' }),
        EP('Palhaçada', 'Balões sobem, confete cai e o cartão pisca em vermelho e azul, como um número de circo.', [
            { k: 'clima', fundo: 'linear-gradient(120deg,rgba(226,32,58,.45),transparent 50%,rgba(42,106,255,.4))', min: .3, max: 1, dur: 2.4 },
            { k: 'sobe', icones: ['balao'], pals: [{ ...AR, m: '#2a6aff', o: '#0a1a4a' }, AR, { ...AR, m: '#ffd23f', o: '#8a5a00' }], n: 9, tam: [16, 28], vel: [7, 12], bal: 50, alfa: .95 },
            { k: 'cai', icones: ['confete'], pals: [{ m: '#e2203a', a: '#2a6aff', l: '#ffd23f' }], n: 14, tam: [8, 14], vel: [4, 7], bal: 50, giro: 360 },
        ], { r: 'epico' }),
    ],
});

// =====================================================================================================  CIBORGUE
const CB = { m: '#9aa8b8', a: '#d4dce8', d: '#10161e', l: '#ffffff', o: '#10161e' };
const CIB = { m: '#4ae0ff', a: '#c4f4ff', d: '#04242e', l: '#ffffff', o: '#0a5a6a' };
const placaMae = (() => { let s = ''; for (let k = 0; k < 16; k++) { const x = (k * 53) % 330, y = 10 + (k * 29) % 90, w = 40 + (k * 17) % 90; s += `<path d='M${x} ${y}h${w}l8 8h20' fill='none' stroke='#4ae0ff' stroke-width='1.4' opacity='.5'/><circle cx='${x + w + 28}' cy='${y + 8}' r='2.4' fill='#4ae0ff' opacity='.8'/>`; } return s; })();
const ciborgue = tema({
    id: 'ciborgue', pre: 'cib', nome: 'Metade Máquina', cat: 'quadrinhos', cor: '#4ae0ff', cores: ['#4ae0ff', '#ff3030'], icone: 'fa-microchip',
    lema: 'Sistema online.',
    desc: 'Aço, circuitos azuis e um olho vermelho de máquina: engrenagens, varreduras e dados correndo por tudo.',
    pal: CB,
    itens: [
        M('Circuito', 'Hexágonos de circuito e engrenagens de aço girando em volta da foto.', { t: 'icones', icones: ['hexagono', 'engrenagem'], pals: [CIB, CB], n: 12, tam: 24, giro: 40, glow: '#4ae0ff' }, { r: 'raro' }),
        N('Sistema', 'Texto de terminal em azul-ciano que vez ou outra falha.', { grad: ['#2ab8d8', '#e6fbff', '#2ab8d8'], mov: 'glitch', g1: '#ff3030', g2: '#4ae0ff', dur: 3, fonte: 'maquina', contorno: '#04242e', cw: .7, espaco: .8, peso: 800 }, { r: 'raro' }),
        Pl('Placa-Mãe', 'Trilhas e pontos de solda azuis sobre o aço escuro, com uma engrenagem ao lado.', { base: ['#10161e', '#1c2632'], pad: { tipo: 'grade', c1: 'rgba(74,224,255,.28)', c2: 'transparent', tam: 12, lw: 1 }, mov: 'x', dur: 8, brilho: 'rgba(74,224,255,.35)', borda: 'rgba(154,168,184,.7)', icone: { nome: 'engrenagem', pal: CB, lado: 'dir', tam: 64 } }, { r: 'raro' }),
        F('Torre de Circuitos', 'Uma placa de circuitos azuis num fundo de aço, com dados correndo.', {
            fundo: ['#0a0e14', '#141c28', '#1e2c3a'], fixo: placaMae,
            longe: { svg: `<g stroke='#4ae0ff' stroke-width='1.6' opacity='.7'>${[...Array(8)].map((_, k) => `<path d='M${(k * 47) % 300} ${12 + k * 12}h${30 + (k * 19) % 50}'/>`).join('')}</g>`, anim: 'pan', dur: 6 },
            perto: { svg: cena.icones({ nomes: ['hexagono'], pals: [{ m: '#ff3030', o: '#ff3030', w: -6 }], n: 4, tam: [6, 10], seed: 'cb1', y: [10, 100] }), anim: 'pisca', dur: 1.6 },
        }, { r: 'raro' }),
        EA('Inicialização', 'Um anel de circuito gira em volta da foto enquanto uma linha de varredura passa por cima dela.', [
            { k: 'aura', cor: '#4ae0ff', dur: 2 },
            { k: 'anel', cor: '#4ae0ff', r: 68, esp: 2.4, dash: '3 5', giro: 12 },
            { k: 'faiscas', icone: 'hexagono_cheio', pals: [{ m: '#ff3030', a: '#ff9090', d: '#400000', l: '#fff', o: '#400000' }], n: 4, tam: 7, raio: 40 },
        ], { r: 'raro', sobre: [{ k: 'scan', cor: '#4ae0ff', dur: 3 }] }),
        EP('Download', 'Uma varredura cruza o cartão e hexágonos de dados sobem, com um brilho de alerta vermelho.', [
            { k: 'raw', html: '<i class="sc"></i>', css: `.ef-pf-$ID .sc{position:absolute;left:0;right:0;top:0;height:18%;background:linear-gradient(transparent,rgba(74,224,255,.45) 80%,rgba(230,251,255,.9));animation:k-$ID-sc 4s linear ${fase(4, .5)} infinite;filter:drop-shadow(0 0 8px #4ae0ff)}@keyframes k-$ID-sc{from{transform:translate3d(0,-110%,0)}to{transform:translate3d(0,560%,0)}}` },
            { k: 'sobe', icones: ['hexagono'], pals: [CIB], n: 12, tam: [8, 18], vel: [4, 8], alfa: .85 },
            { k: 'borda', cor: '#4ae0ff', alfa: .4, dur: 2.4 },
        ], { r: 'epico' }),
    ],
});

module.exports = [gotham, krypton, temiscira, velocista, vontade, atlantida, caos, arlequina, ciborgue];
