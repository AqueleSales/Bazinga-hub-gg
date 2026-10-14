'use strict';
/* HERÓIS DE QUADRINHOS (parte 2): reator e HUD, escudo, trovão, fúria verde, vibranium, mandalas, as seis joias, o mercenário, as garras, o caos escarlate e o truque. Arte original. */
const { tema, M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P, I, fase } = require('../dsl');
const { cena } = P;
const { icone, pontos } = I;
const f1 = (n) => Math.round(n * 10) / 10;
const solido = (c) => ({ m: c, a: c, d: c, l: c, o: c, w: 0 });
const burst = (cx, cy, cor1, cor2, n = 24) => { let s = ''; for (let k = 0; k < n; k++) { const a0 = k * 360 / n, a1 = a0 + 180 / n, p = (a, r) => `${f1(cx + r * Math.cos(a * Math.PI / 180))} ${f1(cy + r * Math.sin(a * Math.PI / 180))}`; s += `<path d='M${cx} ${cy}L${p(a0, 300)}L${p(a1, 300)}Z' fill='${k % 2 ? cor1 : cor2}'/>`; } return s; };
const glitchBarras = `<rect y='28' width='340' height='4' fill='#fff' opacity='.6'/><rect x='70' y='62' width='200' height='3' fill='#000' opacity='.7'/><rect x='10' y='88' width='140' height='3' fill='#fff' opacity='.5'/>`;

// =====================================================================================================  STARK (reator e HUD)
const CYA = { m: '#7ae8ff', a: '#d4f8ff', d: '#04242e', l: '#ffffff', o: '#0a5a6a' };
const reatorAnel = (() => { let s = `<circle cx='100' cy='100' r='96' fill='none' stroke='#7ae8ff' stroke-width='2.4' opacity='.7'/><circle cx='100' cy='100' r='70' fill='none' stroke='#d4f8ff' stroke-width='1.6' opacity='.8'/>`; for (let k = 0; k < 10; k++) { const a0 = k * 36 + 5, a1 = k * 36 + 31, p = (a, r) => `${f1(100 + r * Math.cos(a * Math.PI / 180))} ${f1(100 + r * Math.sin(a * Math.PI / 180))}`; s += `<path d='M${p(a0, 76)}L${p(a0 + 3, 92)}L${p(a1 - 3, 92)}L${p(a1, 76)}Z' fill='#7ae8ff' stroke='#04242e' stroke-width='2' stroke-linejoin='round'/>`; } return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'>${s}</svg>`; })();
const hudSvg = (() => { let s = ''; for (let r = 30; r < 90; r += 20) s += `<circle cx='170' cy='56' r='${r}' fill='none' stroke='#7ae8ff' stroke-width='1.2' opacity='${.7 - r / 220}' stroke-dasharray='${r % 3 ? '3 4' : '1 0'}'/>`; for (let k = 0; k < 24; k++) { const a = k * 15 * Math.PI / 180; s += `<path d='M${f1(170 + 78 * Math.cos(a))} ${f1(56 + 78 * Math.sin(a))}L${f1(170 + 84 * Math.cos(a))} ${f1(56 + 84 * Math.sin(a))}' stroke='#7ae8ff' stroke-width='1.4'/>`; } return `${s}<path d='M20 20H60M20 20V50M320 92H280M320 92V62' stroke='#d4f8ff' stroke-width='1.6' fill='none'/><circle cx='170' cy='56' r='9' fill='#d4f8ff'/>`; })();
const stark = tema({
    id: 'stark', pre: 'sta', nome: 'Oficina de Armadura', cat: 'quadrinhos', cor: '#c8202a', cores: ['#c8202a', '#e8b82a'], icone: 'fa-robot', premium: true,
    lema: 'Sou eu. E a armadura.',
    desc: 'Vermelho e ouro de armadura, o reator azul que pulsa no peito, a tela de combate com círculos girando e um repulsor pronto pra disparar.',
    pal: CYA,
    itens: [
        M('Reator', 'O reator azul: dez segmentos brilhantes em volta da foto, pulsando como um coração de energia.', { t: 'svg', svg: reatorAnel, giro: 0, pulso: 2.8, glow: '#7ae8ff', inset: .26 }, { r: 'epico' }),
        N('Armadura', 'Vermelho e ouro metálicos que correm pelas letras, com contorno escuro.', { grad: ['#a81018', '#ffb02a', '#a81018'], mov: 'desliza', dur: 4.4, contorno: '#2a0a0a', cw: 1.1, fonte: 'impacto', espaco: 1, peso: 900 }, { r: 'epico' }),
        Pl('Painel de Combate', 'Uma grade azul de tela de bordo com um brilho de varredura e um reator ao lado.', { base: ['#04141c', '#082a38'], pad: { tipo: 'grade', c1: 'rgba(122,232,255,.3)', c2: 'transparent', tam: 14, lw: 1 }, mov: 'x', dur: 9, brilho: 'rgba(122,232,255,.4)', borda: 'rgba(232,184,42,.8)', icone: { nome: 'reator', pal: CYA, lado: 'dir', tam: 66 } }, { r: 'epico' }),
        F('Oficina', 'Uma oficina escura com a tela de combate: círculos, escalas e o brilho do reator.', {
            fundo: ['#02080e', '#06202c', '#0a3a4a'], fixo: hudSvg,
            longe: { svg: `<path d='M0 56H340' stroke='#7ae8ff' stroke-width='1' opacity='.5'/><rect x='0' y='54' width='60' height='4' fill='#d4f8ff' opacity='.8'/>`, anim: 'pan', dur: 5 },
            perto: { svg: cena.estrelas({ cor: '#d4f8ff', n: 14, seed: 'st1', y: [4, 108] }), anim: 'pisca', dur: 2.2 },
        }, { r: 'epico' }),
        EA('Repulsor', 'Ondas de energia azul saem da foto, uma atrás da outra, com um núcleo que brilha.', [
            { k: 'raw', html: '<b class="$C"></b><b class="$C b"></b><b class="$C c"></b>', css: `.ef-av-$ID .$C{border-radius:50%;border:2px solid rgba(122,232,255,.95);box-shadow:0 0 10px rgba(122,232,255,.8),inset 0 0 10px rgba(122,232,255,.6);inset:21%;opacity:0;animation:k-$ID-o 2.6s ease-out ${fase(2.6, .3)} infinite}.ef-av-$ID .$C.b{animation-delay:calc(${fase(2.6, .3)} + .87s)}.ef-av-$ID .$C.c{animation-delay:calc(${fase(2.6, .3)} + 1.74s)}@keyframes k-$ID-o{0%{opacity:.95;transform:scale(.75)}100%{opacity:0;transform:scale(1.6)}}` },
            { k: 'aura', cor: '#7ae8ff', dur: 1.6 },
        ], { r: 'epico' }),
        EP('Tela de Combate', 'Círculos de mira giram sobre o cartão, uma linha de varredura passa e o canto ganha mostradores.', [
            { k: 'raw', html: `<svg class="hd" viewBox="-100 -100 200 200"><g fill="none" stroke="#7ae8ff" stroke-width="1.6"><circle r="90" stroke-dasharray="6 5" class="c1"/><circle r="68" stroke-dasharray="26 8" class="c2" stroke="#d4f8ff"/><circle r="46" stroke-dasharray="3 5" class="c1"/><path d="M-100 0H-24M24 0H100M0 -100V-24M0 24V100"/><circle r="6" fill="#d4f8ff"/></g></svg><i class="sc"></i>`,
              css: `.ef-pf-$ID .hd{position:absolute;left:50%;top:44%;width:92cqw;height:92cqw;margin:-46cqw 0 0 -46cqw;opacity:.75;filter:drop-shadow(0 0 4px #7ae8ff)}.ef-pf-$ID .c1{transform-origin:0 0;animation:kGira 24s linear infinite}.ef-pf-$ID .c2{transform-origin:0 0;animation:kGira 16s linear infinite reverse}.ef-pf-$ID .sc{position:absolute;left:0;right:0;top:0;height:14%;background:linear-gradient(transparent,rgba(122,232,255,.4) 80%,rgba(212,248,255,.8));animation:k-$ID-sc 5s linear infinite}@keyframes k-$ID-sc{from{transform:translate3d(0,-110%,0)}to{transform:translate3d(0,720%,0)}}` },
            { k: 'borda', cor: '#7ae8ff', alfa: .4, dur: 3 },
        ], { r: 'lendario' }),
        FALA('Voz do Reator', 'Quando você fala na call, o card acende em ciano e ouro.', { cores: ['#7ae8ff', '#e8b82a'] }),
        RADAR('Disparo', 'As ondas do radar viram anéis duplos azuis.', { cor: '#7ae8ff', estilo: 'duplo', glow: '#7ae8ff' }),
        PIN('Reator', 'Suas notas no mapa viram um reator azul.', { icone: 'reator', pal: CYA, bal: 2.6 }),
        SOM('Repulsor', 'Um zumbido de carga que sobe e o disparo de uma onda de energia, ao entrar na call.', { notas: [{ t: 0, f: 200, f2: 1400, d: .5, tipo: 'sawtooth', v: .3 }, { t: .5, f: 100, f2: 40, d: .35, tipo: 'sine', v: 1 }, { t: .5, f: 600, f2: 200, d: .4, tipo: 'square', v: .25 }], ruidos: [{ t: .5, d: .35, f: 3000, f2: 500, filtro: 'bandpass', v: .7 }] }),
    ],
});

// =====================================================================================================  ESCUDO
const AZ = '#1a3a9a', VM = '#d4161e';
const bandeira = `${[...Array(9)].map((_, k) => `<rect y='${k * 12.4}' width='340' height='12.4' fill='${k % 2 ? '#f6f6fa' : '#d4161e'}'/>`).join('')}<rect width='150' height='62' fill='#1a3a9a'/>${[...Array(18)].map((_, k) => `<path d='${pontos(5, 14 + (k % 6) * 24, 12 + Math.floor(k / 6) * 20, 5, 2.2, -90)}' fill='#fff'/>`).join('')}`;
const escudo = tema({
    id: 'escudo', pre: 'esc', nome: 'Escudo da Liberdade', cat: 'quadrinhos', cor: '#d4161e', cores: ['#d4161e', '#1a3a9a'], icone: 'fa-star',
    lema: 'Sempre à frente da linha.',
    desc: 'Anéis vermelho, branco e azul, uma estrela no meio, listras e estrelas ao vento: um escudo que volta sempre.',
    pal: { m: VM, a: '#fff', d: AZ, l: '#fff', o: '#0a1a4a' },
    itens: [
        M('Escudos', 'Escudos de anéis vermelho, branco e azul com uma estrela, girando em volta da foto.', { t: 'icones', icones: ['escudo_estrela'], pals: [{ o: '#0a1a4a' }], n: 6, tam: 34, giro: 48 }, { r: 'raro' }),
        N('Sentinela', 'Vermelho, branco e azul em cores secas, com contorno escuro.', { grad: ['#d4161e', '#ffffff', '#1a3a9a'], passos: true, mov: 'desliza', dur: 3.6, contorno: '#0a1a4a', cw: 1.1, fonte: 'impacto', espaco: 1, peso: 900 }, { r: 'raro' }),
        Pl('Listras', 'Listras vermelhas e brancas e um escudo de anéis ao lado.', { base: '#f6f6fa', pad: { tipo: 'horizontais', c1: '#d4161e', c2: 'transparent', tam: 18 }, mov: 'nenhum', borda: '#1a3a9a', texto: '#0a1a4a', icone: { nome: 'escudo_estrela', pal: { o: '#0a1a4a' }, lado: 'dir', tam: 70 } }, { r: 'raro' }),
        F('Bandeira ao Vento', 'Listras e estrelas ao vento, com o brilho do sol passando como numa bandeira que ondula.', {
            fundo: ['#d4161e'], fixo: bandeira,
            longe: { svg: `<path d='M-40 0L-10 0L50 112L20 112Z' fill='#fff' opacity='.28'/><path d='M120 0L170 0L230 112L180 112Z' fill='#fff' opacity='.2'/>`, anim: 'pan', dur: 7 },
        }, { r: 'raro' }),
        EA('Escudo Lançado', 'Um escudo gira rápido em volta da foto, com uma luz azul.', [
            { k: 'aura', cor: '#1a5aff', dur: 2 },
            { k: 'orbita', icones: ['escudo_estrela'], pals: [{ o: '#0a1a4a' }], n: 1, tam: 36, giro: 2.8, raio: 74 },
        ], { r: 'raro' }),
        EP('Estrelas e Listras', 'Estrelas brancas caem pelo cartão sobre um clarão vermelho e azul.', [
            { k: 'clima', fundo: 'linear-gradient(135deg,rgba(212,22,30,.5),transparent 50%,rgba(26,58,154,.5))', min: .3, max: 1, dur: 3 },
            { k: 'cai', icones: ['estrelinha'], pals: [solido('#ffffff')], n: 18, tam: [8, 18], vel: [4, 8], bal: 50, giro: 240 },
            { k: 'flash', cor: '#ffffff', dur: 7, ini: 64 },
        ], { r: 'epico' }),
        PIN('Escudo', 'Suas notas no mapa viram um escudo de anéis e estrela.', { icone: 'escudo_estrela', pal: { o: '#0a1a4a' } }),
        SOM('Escudo no Ar', 'Um zunido de metal girando e o estalo de um quique, ao entrar na call.', { notas: [{ t: 0, f: 900, f2: 1500, d: .4, tipo: 'triangle', v: .3 }, { t: .4, f: 1100, d: .5, tipo: 'sine', v: .6 }, { t: .4, f: 1650, d: .4, tipo: 'sine', v: .3 }], ruidos: [{ t: .4, d: .1, f: 4000, filtro: 'highpass', v: .6 }] }),
    ],
});

// =====================================================================================================  TROVÃO
const TR = { m: '#9ad8ff', a: '#ffffff', d: '#0a2a5a', l: '#ffffff', o: '#0a3a7a' };
const asgard = `<defs><linearGradient id='ar' x1='0' x2='1'><stop offset='0' stop-color='#ff6b6b'/><stop offset='.33' stop-color='#ffd166'/><stop offset='.66' stop-color='#7be0a4'/><stop offset='1' stop-color='#6ec6ff'/></linearGradient></defs><path d='M-10 112C70 30 270 30 350 112' fill='none' stroke='url(#ar)' stroke-width='7' opacity='.8'/>${cena.skyline({ cor: '#e8b82a', altMin: 20, altMax: 60, larg: [8, 14], seed: 'tr1', antenas: true })}<rect y='96' width='340' height='16' fill='#2a3a6a'/>`;
const trovao = tema({
    id: 'trovao', pre: 'tro', nome: 'Deus do Trovão', cat: 'quadrinhos', cor: '#9ad8ff', cores: ['#9ad8ff', '#e8b82a'], icone: 'fa-hammer',
    lema: 'Digno, ou não digno?',
    desc: 'Raios azul-brancos, um martelo de metal escuro, uma ponte de arco-íris e uma cidade dourada sob uma tempestade que não acaba.',
    pal: TR,
    itens: [
        M('Raios', 'Raios azul-claros girando em volta da foto, com um brilho elétrico.', { t: 'icones', icones: ['raio'], pals: [TR, { ...TR, m: '#ffffff', o: '#5aa8e8' }], n: 10, tam: 28, giro: 15, glow: '#9ad8ff' }, { r: 'raro' }),
        N('Trovão', 'Azul-claro e branco que estoura, com contorno azul-marinho.', { grad: ['#5aa8e8', '#ffffff', '#5aa8e8'], mov: 'pulsa', brilho: '#9ad8ff', bw: 3.2, contorno: '#0a2a5a', cw: 1.1, fonte: 'impacto', espaco: 1, peso: 900, dur: 1.8 }, { r: 'raro' }),
        Pl('Metal de Martelo', 'Aço escuro riscado, um brilho azul passando e um martelo ao lado.', { base: ['#3a4452', '#262e3a'], pad: { tipo: 'riscado', c1: 'rgba(154,216,255,.22)', c2: 'transparent', tam: 12, lw: 1.3 }, mov: 'x', dur: 9, brilho: 'rgba(154,216,255,.42)', borda: 'rgba(154,216,255,.8)', icone: { nome: 'martelo', pal: { m: '#aeb8cc', a: '#e8eefc', d: '#4a5568', l: '#fff', o: '#10161e' }, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Ponte de Arco-Íris', 'Uma cidade dourada sob a tempestade, a ponte de arco-íris e raios piscando nas nuvens.', {
            fundo: ['#0a1228', '#1c2a5a', '#3a4a8a'], fixo: asgard,
            longe: { svg: `<g opacity='.6'>${cena.nuvens({ cor: '#10183a', n: 3, y: [4, 40], tam: [22, 34], seed: 'tr2' })}</g>`, anim: 'pan', dur: 46 },
            perto: { svg: cena.icones({ nomes: ['raio'], pals: [TR], n: 4, tam: [14, 22], seed: 'tr3', y: [6, 60] }), anim: 'pisca', dur: 2.6 },
        }, { r: 'raro' }),
        EA('Relâmpago', 'Raios giram em volta da foto e uma luz azul-branca estoura de tempos em tempos.', [
            { k: 'aura', cor: '#9ad8ff', dur: 1.4 },
            { k: 'orbita', icones: ['raio'], pals: [TR], n: 7, tam: 24, giro: 10 },
        ], { r: 'raro', sobre: [{ k: 'brilho', cor: '#ffffff', dur: 2.6 }] }),
        EP('Tempestade Divina', 'Chuva forte, raios que riscam o cartão de cima a baixo e clarões azul-brancos.', [
            { k: 'neblina', cor: '#4a5a8a', alfa: .4, n: 4 },
            { k: 'chuva', n: 40, cor: '#9ad8ff', alfa: .6, ang: 10 },
            { k: 'raw', html: [14, 46, 80].map((x, i) => `<svg class="rl" style="left:${x}%;--i:${i}" viewBox="0 0 24 100" preserveAspectRatio="none"><path d="M12 0L6 22L16 24L5 52L15 54L8 100" fill="none" stroke="#9ad8ff" stroke-width="7" opacity=".5" stroke-linejoin="round"/><path d="M12 0L6 22L16 24L5 52L15 54L8 100" fill="none" stroke="#fff" stroke-width="2.4" stroke-linejoin="round"/></svg>`).join(''),
              css: `.ef-pf-$ID .rl{position:absolute;top:0;width:16%;height:80%;margin-left:-8%;opacity:0;animation:k-$ID-rl 7s linear calc(var(--i) * 1.9s + ${fase(7, .4)}) infinite;filter:drop-shadow(0 0 6px #9ad8ff)}@keyframes k-$ID-rl{0%,36%{opacity:0}37%{opacity:1}40%{opacity:.2}42%{opacity:1}50%,100%{opacity:0}}` },
            { k: 'flash', cor: '#dff2ff', dur: 7, ini: 36 },
        ], { r: 'lendario' }),
        PIN('Martelo', 'Suas notas no mapa viram um martelo de aço.', { icone: 'martelo', pal: { m: '#aeb8cc', a: '#e8eefc', d: '#4a5568', l: '#fff', o: '#10161e' } }),
        SOM('Trovão Divino', 'Um estalo de raio e um trovão que rola, ao entrar na call.', { notas: [{ t: .05, f: 70, f2: 36, d: 1.1, tipo: 'sawtooth', v: .5 }], ruidos: [{ t: 0, d: .15, f: 5000, f2: 1500, filtro: 'bandpass', v: .9, q: 1.4 }, { t: .05, d: 1, f: 500, f2: 80, filtro: 'lowpass', v: .8, q: .7 }] }),
    ],
});

// =====================================================================================================  GAMA (fúria verde)
const GM = { m: '#4ac84a', a: '#9aff6a', d: '#0a2a0a', l: '#e8ffd8', o: '#0a3a0a' };
const rachaduras = `<g fill='none' stroke='#9aff6a' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M170 112L160 90 176 74 164 52 180 34' stroke-width='2.6'/><path d='M176 74L204 66 228 78M164 52L136 48 114 60M160 90L128 96 104 88'/></g><g fill='none' stroke='#2a7a2a' stroke-width='5' opacity='.5'><path d='M170 112L160 90 176 74 164 52 180 34'/></g>`;
const gama = tema({
    id: 'gama', pre: 'gam', nome: 'Fúria Verde', cat: 'quadrinhos', cor: '#4ac84a', cores: ['#4ac84a', '#8a3cc8'], icone: 'fa-hand-fist',
    lema: 'Não me deixe irritado.',
    desc: 'Verde-gama e roxo: pedra que racha, ondas de choque e uma cratera onde algo grande acabou de bater.',
    pal: GM,
    itens: [
        M('Pedra Rachada', 'Uma moldura de rocha verde de bordas serrilhadas, girando devagar em volta da foto.', { t: 'forma', forma: 'serra', n: 12, amp: 8, esp: 13, cor: '#4ac84a', cor2: '#2a7a2a', linha: '#0a2a0a', lw: 2.6, giro: 80 }, { r: 'raro' }),
        N('Fúria', 'Verde-gama com um contorno roxo grosso, em letras de impacto.', { grad: ['#2a9a2a', '#9aff6a', '#2a9a2a'], mov: 'desliza', dur: 3.6, contorno: '#3a1a6a', cw: 1.6, fonte: 'impacto', espaco: 1, peso: 900, sombra: [1.5, 1.5, '#1a0a3a'] }, { r: 'raro' }),
        Pl('Rocha', 'Pedra cinza-esverdeada rachada e um brilho verde que vaza pelas fendas.', { base: ['#4a5a4a', '#2a3a2a'], pad: { tipo: 'riscado', c1: 'rgba(154,255,106,.3)', c2: 'transparent', tam: 14, lw: 1.5 }, mov: 'x', dur: 12, brilho: 'rgba(154,255,106,.3)', borda: 'rgba(154,255,106,.7)', icone: { nome: 'estrela_ko', pal: { m: '#9aff6a', a: '#4ac84a', d: '#0a2a0a', l: '#fff', o: '#0a2a0a' }, lado: 'dir', tam: 62 } }, { r: 'raro' }),
        F('Cratera', 'Um deserto de pedra com uma cratera cheia de fendas brilhando em verde.', {
            fundo: ['#2a3a2a', '#5a6a4a', '#9aa86a'], fixo: `${cena.montanhas({ cor: '#2a3226', n: 5, altMin: 20, altMax: 46, seed: 'gm1' })}${cena.terreno({ cor: '#1a2216', y: 90, amp: 5, n: 3 })}${rachaduras}`,
            longe: { svg: `<g opacity='.4'>${cena.nuvens({ cor: '#9aa86a', n: 3, y: [10, 60], tam: [20, 30], seed: 'gm2' })}</g>`, anim: 'pan', dur: 40 },
            perto: { svg: cena.icones({ nomes: ['grao'], pals: [solido('#9aff6a')], n: 12, tam: [2, 5], seed: 'gm3', y: [10, 106] }), anim: 'pisca', dur: 2.2 },
        }, { r: 'raro' }),
        EA('Onda de Choque', 'Anéis verdes de choque se espalham a partir da foto e uma rachadura corta a imagem.', [
            { k: 'raw', html: '<b class="$C"></b><b class="$C b"></b>', css: `.ef-av-$ID .$C{border-radius:50%;border:3px solid rgba(154,255,106,.95);box-shadow:0 0 12px rgba(74,200,74,.9);inset:20%;opacity:0;animation:k-$ID-o 2.4s ease-out ${fase(2.4, .3)} infinite}.ef-av-$ID .$C.b{border-color:rgba(138,60,200,.9);box-shadow:0 0 12px rgba(138,60,200,.8);animation-delay:calc(${fase(2.4, .3)} + 1.2s)}@keyframes k-$ID-o{0%{opacity:1;transform:scale(.8)}100%{opacity:0;transform:scale(1.7)}}` },
            { k: 'aura', cor: '#4ac84a', dur: 2 },
        ], { r: 'raro', sobre: [{ k: 'rachadura', cor: '#9aff6a', dur: 6 }] }),
        EP('Rachaduras', 'Fendas verdes se abrem pelo cartão, uma onda de choque passa e pedaços de pedra caem.', [
            { k: 'raw', html: `<svg class="rc" viewBox="0 0 340 440" preserveAspectRatio="none"><g fill="none" stroke="#9aff6a" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">${['M170 440L150 380 190 330 150 270 200 210 170 150 210 90 190 0', 'M190 330L260 310 300 250', 'M150 270L90 250 40 200', 'M200 210L270 190 320 130', 'M170 150L110 120 60 60'].map((d, k) => `<path pathLength="1" d="${d}" style="--i:${k * .25}"/>`).join('')}</g></svg><i class="rg"></i>`,
              css: `.ef-pf-$ID .rc{position:absolute;inset:0;width:100%;height:100%;filter:drop-shadow(0 0 5px #4ac84a)}.ef-pf-$ID .rc path{stroke-dasharray:1;stroke-dashoffset:1;animation:k-$ID-rc 8s ease-out calc(var(--i) * 1s + ${fase(8, .5)}) infinite}.ef-pf-$ID .rg{position:absolute;left:50%;top:50%;width:60cqw;height:60cqw;margin:-30cqw 0 0 -30cqw;border-radius:50%;border:4px solid #9aff6a;box-shadow:0 0 22px #4ac84a;opacity:0;animation:k-$ID-rg 8s ease-out ${fase(8, .4)} infinite}@keyframes k-$ID-rc{0%{stroke-dashoffset:1;opacity:1}10%{stroke-dashoffset:0}70%{stroke-dashoffset:0;opacity:1}86%,100%{stroke-dashoffset:0;opacity:0}}@keyframes k-$ID-rg{0%,4%{opacity:0;transform:scale(.1)}8%{opacity:1}34%,100%{opacity:0;transform:scale(2.2)}}` },
            { k: 'cai', icones: ['grao'], pals: [solido('#6a7a5a'), solido('#9aff6a')], n: 16, tam: [4, 10], vel: [3, 7], bal: 30, giro: 200 },
        ], { r: 'epico' }),
        SOM('Esmagar', 'Uma pancada grave que racha e o estrondo de pedra caindo, ao entrar na call.', { notas: [{ t: 0, f: 110, f2: 36, d: .5, tipo: 'sine', v: 1 }], ruidos: [{ t: 0, d: .12, f: 3000, f2: 800, filtro: 'bandpass', v: .8 }, { t: .1, d: .7, f: 600, f2: 120, filtro: 'lowpass', v: .6, q: .8 }] }),
    ],
});

// =====================================================================================================  WAKANDA
const WK = { m: '#8a3cd8', a: '#c4a0ff', d: '#0a0a10', l: '#ffffff', o: '#1a0a2a' };
const wakanda = tema({
    id: 'wakanda', pre: 'wak', nome: 'Reino de Vibranium', cat: 'quadrinhos', cor: '#8a3cd8', cores: ['#8a3cd8', '#c8ccd8'], icone: 'fa-paw',
    lema: 'O futuro nunca deixou de ser antigo.',
    desc: 'Roxo-vibranium e prata sobre o preto: formas geométricas, garras de metal e uma cidade luminosa escondida na noite.',
    pal: WK,
    itens: [
        M('Vibranium', 'Um anel de pontas geométricas roxas e prata que brilha em volta da foto.', { t: 'forma', forma: 'dentes', n: 14, amp: 8, esp: 12, cor: '#8a3cd8', cor2: '#4a1a8a', linha: '#c4a0ff', lw: 1.6, giro: 70, glow: '#8a3cd8' }, { r: 'raro' }),
        N('Realeza', 'Prata e roxo-vibranium, com um contorno preto e brilho suave.', { grad: ['#8a3cd8', '#e8eaf4', '#8a3cd8'], mov: 'pulsa', brilho: '#8a3cd8', bw: 2.6, contorno: '#0a0a10', cw: 1.1, fonte: 'classica', espaco: .8, peso: 900, dur: 3 }, { r: 'raro' }),
        Pl('Garras', 'Riscos de garra em prata sobre o preto e roxo, com uma garra ao lado.', { base: ['#0a0a10', '#1a1030'], pad: { tipo: 'riscado', c1: 'rgba(200,204,216,.28)', c2: 'transparent', tam: 14, lw: 1.3 }, mov: 'x', dur: 12, brilho: 'rgba(138,60,216,.4)', borda: 'rgba(138,60,216,.8)', icone: { nome: 'garra', pal: { m: '#c8ccd8', a: '#e8eaf4', d: '#4a4a5a', l: '#fff', o: '#0a0a10' }, lado: 'dir', tam: 64 } }, { r: 'raro' }),
        F('Cidade Escondida', 'Torres luminosas e arredondadas num horizonte roxo, com veios de vibranium brilhando.', {
            fundo: ['#07040f', '#1a0e36', '#3a1a6a'], fixo: `${cena.cristais({ cor: '#150a2a', cor2: '#2a1050', n: 10, alt: [26, 70], seed: 'wk1', larg: [10, 18] })}${cena.skyline({ cor: '#0a0614', altMin: 14, altMax: 34, larg: [8, 14], seed: 'wk2', janelas: { cor: '#c4a0ff', dens: .3 } })}<path d='M0 100C60 90 120 104 180 94S300 90 340 98' fill='none' stroke='#8a3cd8' stroke-width='2' opacity='.8'/>`,
            longe: { svg: cena.estrelas({ cor: '#c4a0ff', n: 22, y: [0, 60], seed: 'wk3' }), anim: 'pisca', dur: 2.6 },
            perto: { svg: cena.icones({ nomes: ['hexagono'], pals: [{ m: '#8a3cd8', o: '#8a3cd8', w: -6 }], n: 6, tam: [8, 14], seed: 'wk4', y: [6, 80], alfa: .6 }), anim: 'pan', dur: 30 },
        }, { r: 'raro' }),
        EA('Garras', 'Três garras de metal cortam a sua foto num clarão, de tempos em tempos, sob uma aura roxa.', [
            { k: 'aura', cor: '#8a3cd8', dur: 2.6 },
            { k: 'faiscas', icone: 'hexagono', pals: [{ m: '#c4a0ff', o: '#c4a0ff', w: -6 }], n: 6, tam: 8, raio: 39 },
        ], { r: 'raro', sobre: [{ k: 'raw', html: `<svg viewBox="0 0 100 100" class="gr"><g fill="none" stroke="#e8eaf4" stroke-width="3.4" stroke-linecap="round"><path pathLength="1" d="M20 6L66 98" style="--i:0"/><path pathLength="1" d="M38 2L84 94" style="--i:.08"/><path pathLength="1" d="M56 -2L102 90" style="--i:.16"/></g></svg>`, css: `.ef-sobre-$ID .gr{filter:drop-shadow(0 0 3px #8a3cd8)}.ef-sobre-$ID .gr path{stroke-dasharray:1;stroke-dashoffset:1;animation:k-$ID-gr 5s ease-out calc(var(--i) * 1s + ${fase(5, .3)}) infinite}@keyframes k-$ID-gr{0%,20%{stroke-dashoffset:1;opacity:1}28%{stroke-dashoffset:0}50%{stroke-dashoffset:0;opacity:1}64%,100%{stroke-dashoffset:0;opacity:0}}` }] }),
        EP('Veios de Vibranium', 'Pulsos de energia roxa percorrem o cartão, hexágonos sobem e a borda brilha.', [
            { k: 'clima', fundo: 'radial-gradient(ellipse at 50% 100%,rgba(138,60,216,.6),transparent 65%)', min: .3, max: 1, dur: 3 },
            { k: 'sobe', icones: ['hexagono'], pals: [{ m: '#8a3cd8', o: '#8a3cd8', w: -6 }, { m: '#c4a0ff', o: '#c4a0ff', w: -6 }], n: 14, tam: [10, 22], vel: [6, 11], alfa: .85 },
            { k: 'pisca', icone: 'brilho', pals: [{ m: '#fff', o: '#8a3cd8', w: 2 }], n: 8, tam: [7, 12] },
            { k: 'borda', cor: '#8a3cd8', alfa: .5, dur: 2.6 },
        ], { r: 'epico' }),
        SOM('Vibranium', 'Um zumbido de metal que sobe e um tinido prateado, ao entrar na call.', { notas: [{ t: 0, f: 160, f2: 480, d: .45, tipo: 'triangle', v: .4 }, { t: .4, f: 1318, d: .8, tipo: 'sine', v: .4 }, { t: .4, f: 2637, d: .6, tipo: 'sine', v: .2 }], ruidos: [] }),
    ],
});

// =====================================================================================================  MÍSTICA (mandalas de faíscas)
const MS = { m: '#ff9a2a', a: '#ffd070', d: '#3a1608', l: '#fff4d8', o: '#7a3a08' };
const mandala = (cx, cy, r, cor = '#ff9a2a') => { let s = `<g fill='none' stroke='${cor}' stroke-linecap='round'><circle cx='${cx}' cy='${cy}' r='${r}' stroke-width='2.4'/><circle cx='${cx}' cy='${cy}' r='${r * .86}' stroke-width='1.2' stroke-dasharray='3 4'/><circle cx='${cx}' cy='${cy}' r='${r * .62}' stroke-width='2'/>`; for (let k = 0; k < 8; k++) { const a = k * 45 * Math.PI / 180, b = a + Math.PI / 8; s += `<path d='M${f1(cx + r * .62 * Math.cos(a))} ${f1(cy + r * .62 * Math.sin(a))}L${f1(cx + r * .86 * Math.cos(b))} ${f1(cy + r * .86 * Math.sin(b))}L${f1(cx + r * .62 * Math.cos(a + Math.PI / 4))} ${f1(cy + r * .62 * Math.sin(a + Math.PI / 4))}' stroke-width='1.6'/><circle cx='${f1(cx + r * Math.cos(a))}' cy='${f1(cy + r * Math.sin(a))}' r='${r * .06}' fill='${cor}' stroke='none'/>`; } s += `<path d='${pontos(8, cx, cy, r * .5, r * .26, -90).replace(/Z$/, 'Z')}' stroke-width='1.6'/></g>`; return s; };
const mandalaAnel = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'>${mandala(100, 100, 96)}</svg>`;
const mistica = tema({
    id: 'mistica', pre: 'mis', nome: 'Artes Místicas', cat: 'quadrinhos', cor: '#ff9a2a', cores: ['#ff9a2a', '#7a3a08'], icone: 'fa-wand-sparkles',
    lema: 'Existem mais realidades do que você imagina.',
    desc: 'Mandalas de faíscas laranja girando, portais que se abrem e o brilho dourado de um feitiço de proteção.',
    pal: MS,
    itens: [
        M('Mandala', 'Uma mandala de linhas laranja e faíscas, girando em volta da foto.', { t: 'svg', svg: mandalaAnel, giro: 36, glow: '#ff9a2a', inset: .3 }, { r: 'epico' }),
        N('Mestre das Artes', 'Laranja e dourado de faísca, com contorno marrom e um brilho que corre.', { grad: ['#e8780a', '#ffd070', '#e8780a'], mov: 'desliza', dur: 4, contorno: '#3a1608', cw: 1, fonte: 'classica', espaco: .6, peso: 900 }, { r: 'epico' }),
        Pl('Grimório', 'Couro escuro e mandalas douradas gravadas, com um brilho de faísca passando.', { base: ['#3a1608', '#5a2a10'], pad: { tipo: 'icones', icones: ['estrela_pontas'], pals: [solido('#c87a2a')], tam: 30, ti: 18, c2: 'transparent' }, mov: 'x', dur: 22, brilho: 'rgba(255,154,42,.4)', borda: 'rgba(255,154,42,.7)', icone: { nome: 'estrela_pontas', pal: MS, lado: 'dir', tam: 62 } }, { r: 'epico' }),
        F('Santuário', 'Mandalas gigantes girando num céu escuro, com faíscas laranja subindo.', {
            fundo: ['#120804', '#2a1208', '#4a2410'], fixo: `<g opacity='.8'>${mandala(80, 56, 52)}${mandala(260, 56, 42, '#ffd070')}</g>`,
            longe: { svg: cena.estrelas({ cor: '#ffb04a', n: 20, seed: 'ms1' }), anim: 'pisca', dur: 2.4 },
            perto: { svg: cena.icones({ nomes: ['brilho'], pals: [{ m: '#ffd070', o: '#ff9a2a', w: 2 }], n: 8, tam: [7, 12], seed: 'ms2', y: [6, 104] }), anim: 'pan', dur: 20 },
        }, { r: 'epico' }),
        EA('Portal', 'Um círculo de faíscas laranja gira em volta da foto, como a borda de um portal que acabou de se abrir.', [
            { k: 'aura', cor: '#ff9a2a', dur: 2.4 },
            { k: 'anel', cor: '#ff9a2a', r: 68, esp: 3.6, dash: '2 8', giro: 8 },
            { k: 'anel', cor: '#ffd070', r: 72, esp: 2.2, dash: '10 6', giro: 14, rev: true },
            { k: 'faiscas', icone: 'brilho', pals: [{ m: '#ffd070', o: '#ff9a2a', w: 2 }], n: 8, tam: 8, raio: 40 },
        ], { r: 'epico' }),
        EP('Mandalas', 'Uma mandala enorme gira atrás do cartão e faíscas laranja saem do portal e sobem.', [
            { k: 'raw', html: `<svg class="md" viewBox="0 0 200 200">${mandala(100, 100, 96)}</svg><svg class="md m2" viewBox="0 0 200 200">${mandala(100, 100, 96, '#ffd070')}</svg>`,
              css: `.ef-pf-$ID .md{position:absolute;left:50%;top:44%;width:112cqw;height:112cqw;margin:-56cqw 0 0 -56cqw;opacity:.7;filter:drop-shadow(0 0 5px #ff9a2a);animation:kGira 40s linear infinite}.ef-pf-$ID .md.m2{width:76cqw;height:76cqw;margin:-38cqw 0 0 -38cqw;animation-direction:reverse;animation-duration:26s}` },
            { k: 'sobe', icones: ['brilho'], pals: [{ m: '#ffd070', o: '#ff9a2a', w: 2 }], n: 14, tam: [7, 14], vel: [4, 9], alfa: .95 },
            { k: 'borda', cor: '#ff9a2a', alfa: .4, dur: 3.4 },
        ], { r: 'lendario' }),
        FALA('Voz Mística', 'Quando você fala na call, o card acende em laranja e dourado.', { cores: ['#ff9a2a', '#ffd070'] }),
        PIN('Mandala', 'Suas notas no mapa viram uma estrela mística dourada.', { icone: 'estrela_pontas', pal: MS, bal: 3 }),
        SOM('Feitiço', 'Um brilho de faíscas que sobe em escala e se abre num acorde, ao entrar na call.', { notas: [{ t: 0, f: 523, d: .5, tipo: 'sine', v: .4 }, { t: .1, f: 784, d: .5, tipo: 'sine', v: .4 }, { t: .2, f: 1046, d: .5, tipo: 'sine', v: .35 }, { t: .3, f: 1568, d: .7, tipo: 'sine', v: .3 }], ruidos: [{ t: 0, d: .5, f: 1500, f2: 7000, filtro: 'bandpass', v: .3, q: 1.4 }] }),
    ],
});

// =====================================================================================================  JOIAS
const JO = [{ m: '#8a3cd8', a: '#c4a0ff', d: '#2a0a4a', l: '#fff', o: '#2a0a4a' }, { m: '#2a7aff', a: '#8ab4ff', d: '#0a1a5a', l: '#fff', o: '#0a1a5a' }, { m: '#e23636', a: '#ff9a9a', d: '#4a0a0a', l: '#fff', o: '#4a0a0a' }, { m: '#ff9a2a', a: '#ffd070', d: '#4a2208', l: '#fff', o: '#4a2208' }, { m: '#2ee86a', a: '#9affbd', d: '#04401c', l: '#fff', o: '#04401c' }, { m: '#ffd23f', a: '#fff0a0', d: '#6a5000', l: '#fff', o: '#6a5000' }];
const seisPontos = JO.map((p, k) => ({ img: `radial-gradient(circle,${p.m} 0 3.6px,${p.a} 3.8px 4.6px,transparent 5px)`, size: '12px 12px', pos: `${50 + k * 9.4}% 50%`, repeat: 'no-repeat' }));
const joias = tema({
    id: 'joias', pre: 'joi', nome: 'As Seis Joias', cat: 'quadrinhos', cor: '#8a3cd8', cores: ['#8a3cd8', '#e8b82a'], icone: 'fa-gem',
    lema: 'Metade do que existe pode desaparecer.',
    desc: 'Seis gemas, roxa, azul, vermelha, laranja, verde e amarela, orbitando; a manopla de ouro; e o estalo que transforma tudo em poeira.',
    pal: JO[0],
    itens: [
        M('Seis Joias', 'As seis joias, uma de cada cor, giram em volta da foto com um brilho próprio.', { t: 'icones', icones: ['gema'], pals: JO, n: 6, tam: 34, giro: 34, glow: '#c4a0ff' }, { r: 'epico' }),
        N('Equilíbrio', 'Ouro e roxo-escuro com contorno preto, como o metal de uma manopla.', { grad: ['#b8801a', '#ffe08a', '#8a3cd8'], mov: 'desliza', dur: 5.4, contorno: '#14041e', cw: 1.1, fonte: 'classica', espaco: .6, peso: 900 }, { r: 'epico' }),
        Pl('Manopla', 'Ouro polido com as seis joias em fila, brilhando, e um brilho passando.', { base: ['#e8b82a', '#b8801a'], extra: seisPontos, brilho: 'rgba(255,255,255,.5)', mov: 'x', dur: 8, borda: '#5a3a00', texto: '#2a1400' }, { r: 'epico' }),
        F('Espaço Profundo', 'O espaço roxo com estrelas, uma névoa cósmica e as seis joias brilhando numa fileira.', {
            fundo: ['#080414', '#1a0a3a', '#3a1a6a'], fixo: `${cena.estrelas({ cor: '#fff', n: 40, seed: 'jo1', r: [.5, 1.6] })}${JO.map((p, k) => `<circle cx='${40 + k * 52}' cy='84' r='7' fill='${p.m}' stroke='${p.a}' stroke-width='1.6'/><circle cx='${40 + k * 52}' cy='84' r='13' fill='${p.m}' opacity='.25'/>`).join('')}`,
            longe: { svg: `<g opacity='.35'>${cena.nuvens({ cor: '#8a3cd8', n: 3, y: [10, 70], tam: [24, 36], seed: 'jo2' })}</g>`, anim: 'pan', dur: 60 },
            perto: { svg: cena.estrelas({ cor: '#ffe08a', n: 12, seed: 'jo3' }), anim: 'pisca', dur: 2 },
        }, { r: 'epico' }),
        EA('Estalo', 'Uma sombra de poeira passa por cima da foto, como se ela se desfizesse, enquanto as joias giram em volta.', [
            { k: 'aura', cor: '#8a3cd8', dur: 2.6 },
            { k: 'orbita', icones: ['gema'], pals: JO, n: 6, tam: 22, giro: 18 },
        ], { r: 'epico', sobre: [{ k: 'raw', html: '<b class="ds"></b>', css: `.ef-sobre-$ID .ds{position:absolute;inset:-12%;background:linear-gradient(115deg,transparent 38%,rgba(10,6,16,.9) 50%,rgba(10,6,16,.9));transform:translateX(-125%);animation:k-$ID-ds 7s ease-in-out ${fase(7, .3)} infinite}@keyframes k-$ID-ds{0%,16%{transform:translateX(-125%)}40%,56%{transform:translateX(0)}80%,100%{transform:translateX(125%)}}` }] }),
        EP('Estalo de Dedos', 'Poeira cinza voa pelo cartão numa rajada, com um clarão dourado e as joias brilhando no escuro.', [
            { k: 'clima', fundo: 'radial-gradient(ellipse at 50% 40%,rgba(138,60,216,.5),transparent 65%)', min: .3, max: 1, dur: 4 },
            { k: 'deriva', icones: ['grao'], pals: [solido('#6a6a74'), solido('#a8a8b4')], n: 30, tam: [3, 8], vel: [3, 7], y: [0, 100], bal: -60, alfa: .85 },
            { k: 'flash', cor: '#ffe08a', dur: 7, ini: 30 },
            { k: 'pisca', icone: 'gema', pals: JO, n: 6, tam: [10, 16] },
        ], { r: 'lendario' }),
        PIN('Joia', 'Suas notas no mapa viram uma joia roxa.', { icone: 'gema', pal: JO[0], bal: 2.8 }),
        SOM('Estalo', 'Um estalo seco de dedos, um silêncio e um brilho que se apaga, ao entrar na call.', { notas: [{ t: .5, f: 880, f2: 220, d: .7, tipo: 'sine', v: .4 }], ruidos: [{ t: 0, d: .05, f: 5000, filtro: 'highpass', v: 1 }, { t: .02, d: .12, f: 1500, f2: 600, filtro: 'bandpass', v: .6, q: 2 }] }),
    ],
});

// =====================================================================================================  MERCENÁRIO
const MC = { m: '#c8101a', a: '#ff5a5a', d: '#14141c', l: '#ffffff', o: '#14141c' };
const tiros = (() => { let s = ''; for (let k = 0; k < 9; k++) { const x = 20 + (k * 71) % 300, y = 14 + (k * 43) % 86; s += `<circle cx='${x}' cy='${y}' r='4' fill='#14141c'/><path d='M${x} ${y - 9}V${y + 9}M${x - 9} ${y}H${x + 9}M${x - 6} ${y - 6}L${x + 6} ${y + 6}M${x + 6} ${y - 6}L${x - 6} ${y + 6}' stroke='#14141c' stroke-width='1.2' opacity='.6'/>`; } return s; })();
const mercenario = tema({
    id: 'mercenario', pre: 'mer', nome: 'Mercenário Falastrão', cat: 'quadrinhos', cor: '#c8101a', cores: ['#c8101a', '#14141c'], icone: 'fa-masks-theater',
    lema: 'Desculpa, esqueci de desligar o narrador.',
    desc: 'Vermelho e preto: katanas cruzadas, furos de bala, balões de fala que ninguém pediu e uma quarta parede que já era.',
    pal: MC,
    itens: [
        M('Katanas', 'Lâminas vermelhas e pretas, uma depois da outra, em volta da foto.', { t: 'icones', icones: ['espada'], pals: [{ ...MC, m: '#c4c8d4', a: '#e8ecf6', l: '#fff', d: '#c8101a' }, { ...MC, m: '#c4c8d4', a: '#e8ecf6', d: '#14141c' }], n: 8, tam: 30, giro: 46, orient: 'fora', glow: '#c8101a' }, { r: 'raro' }),
        N('Falastrão', 'Vermelho e preto em cores secas, com contorno branco, em letras de gibi.', { grad: ['#c8101a', '#14141c'], passos: true, mov: 'desliza', dur: 3, contorno: '#ffffff', cw: 1.2, fonte: 'quadrinho', peso: 900 }, { r: 'raro' }),
        Pl('Mira Vermelha', 'Riscos pretos sobre o vermelho e um balão de fala que ninguém pediu ao lado.', { base: ['#c8101a', '#8a0a12'], pad: { tipo: 'xadrez', c1: 'rgba(20,20,28,.35)', c2: 'transparent', tam: 10 }, mov: 'x', dur: 10, borda: '#14141c', icone: { nome: 'balao_fala', pal: { ...MC, l: '#fff', m: '#14141c' }, lado: 'dir', tam: 64 } }, { r: 'raro' }),
        F('Tiroteio', 'Furos de bala sobre o vermelho, faíscas e balões de fala atravessando a tela.', {
            fundo: ['#8a0a12', '#c8101a', '#e83040'], fixo: tiros,
            longe: { svg: cena.icones({ nomes: ['balao_fala'], pals: [{ ...MC, m: '#14141c' }], n: 5, tam: [16, 24], seed: 'mc1', y: [8, 90], rot: 8 }), anim: 'pan', dur: 22 },
            perto: { svg: cena.estrelas({ cor: '#ffe08a', n: 14, seed: 'mc2', r: [.8, 2] }), anim: 'pisca', dur: 1.4 },
        }, { r: 'raro' }),
        EA('Balões de Fala', 'Balões de fala sobem em volta da foto, com um brilho vermelho pulsando.', [
            { k: 'aura', cor: '#c8101a', dur: 1.8 },
            { k: 'sobe', icones: ['balao_fala'], pals: [{ ...MC, m: '#14141c' }], n: 7, tam: 12, alt: 170 },
        ], { r: 'raro' }),
        EP('Quarta Parede', 'Balões de fala caem pelo cartão e clarões de tiro piscam em vermelho.', [
            { k: 'clima', fundo: 'radial-gradient(ellipse at 50% 100%,rgba(200,16,26,.55),transparent 65%)', min: .3, max: 1, dur: 2.6 },
            { k: 'cai', icones: ['balao_fala'], pals: [{ ...MC, m: '#14141c' }], n: 12, tam: [18, 30], vel: [6, 11], bal: 60, giro: 60 },
            { k: 'flash', cor: '#ff5a5a', dur: 4, ini: 50 },
        ], { r: 'epico' }),
        PIN('Balão Falante', 'Suas notas no mapa viram um balão de fala.', { icone: 'balao_fala', pal: { ...MC, m: '#c8101a' }, bal: 2.4 }),
        SOM('Quebra', 'Um tiro seco e um "ping" cômico, ao entrar na call.', { notas: [{ t: .15, f: 1760, d: .4, tipo: 'sine', v: .35 }, { t: .15, f: 2637, d: .3, tipo: 'sine', v: .2 }], ruidos: [{ t: 0, d: .09, f: 2200, f2: 400, filtro: 'bandpass', v: 1, q: .8 }, { t: 0, d: .2, f: 150, f2: 60, filtro: 'lowpass', v: .8 }] }),
    ],
});

// =====================================================================================================  GARRAS
const GR = { m: '#c4cad6', a: '#eef2fa', d: '#3a4252', l: '#ffffff', o: '#10141c' };
const garras = tema({
    id: 'garras', pre: 'gar', nome: 'Garras de Aço', cat: 'quadrinhos', cor: '#ffd23f', cores: ['#ffd23f', '#1a3a8a'], icone: 'fa-khanda',
    lema: 'O melhor no que faço.',
    desc: 'Amarelo e azul de uniforme, três garras de aço que cortam, uma floresta à noite e o brilho de metal nas faíscas.',
    pal: GR,
    itens: [
        M('Arranhões', 'Garras de aço em volta da foto, saindo pra fora como um rugido.', { t: 'icones', icones: ['garra'], pals: [GR], n: 8, tam: 30, giro: 50, orient: 'fora', glow: '#eef2fa' }, { r: 'raro' }),
        N('Fera', 'Amarelo de uniforme com contorno azul-escuro, em letras de impacto.', { grad: ['#e8b010', '#fff0a0', '#e8b010'], mov: 'desliza', dur: 4, contorno: '#10246a', cw: 1.4, fonte: 'impacto', espaco: 1, peso: 900 }, { r: 'raro' }),
        Pl('Aço Escovado', 'Metal escovado com riscos finos e um reflexo que passa, e três garras ao lado.', { base: ['#8a96a6', '#6a7686'], pad: { tipo: 'horizontais', c1: 'rgba(255,255,255,.18)', c2: 'transparent', tam: 6 }, mov: 'x', dur: 8, brilho: 'rgba(255,255,255,.6)', borda: '#1a3a8a', texto: '#0a1424', icone: { nome: 'garra', pal: GR, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Floresta à Noite', 'Pinheiros negros sob a lua cheia, com arranhões de garra riscando o céu.', {
            fundo: ['#060a14', '#10244a', '#1c3a6a'], fixo: `${cena.sol({ x: 250, y: 34, r: 20, c1: '#f4f8ff', c2: '#c4d4f0' })}${cena.pinheiros({ cor: '#05080f', n: 16, altMin: 28, altMax: 66, seed: 'ga1' })}<g stroke='#eef2fa' stroke-width='2.6' stroke-linecap='round' fill='none' opacity='.85'><path d='M66 8L98 76'/><path d='M80 4L112 72'/><path d='M94 0L126 68'/></g>`,
            longe: { svg: cena.estrelas({ cor: '#fff', n: 22, y: [0, 60], seed: 'ga2' }), anim: 'pisca', dur: 2.6 },
            perto: { svg: `<g opacity='.5'>${cena.nuvens({ cor: '#10244a', n: 2, y: [20, 70], tam: [20, 30], seed: 'ga3' })}</g>`, anim: 'pan', dur: 40 },
        }, { r: 'raro' }),
        EA('Garras', 'Três garras de aço cortam a sua foto num clarão e deixam faíscas em volta.', [
            { k: 'aura', cor: '#ffd23f', dur: 2.2 },
            { k: 'faiscas', icone: 'brilho', pals: [{ m: '#fff', o: '#c4cad6', w: 2 }], n: 6, tam: 8, raio: 39 },
        ], { r: 'raro', sobre: [{ k: 'raw', html: `<svg viewBox="0 0 100 100" class="gr"><g fill="none" stroke="#eef2fa" stroke-width="3.6" stroke-linecap="round"><path pathLength="1" d="M18 -2L64 98" style="--i:0"/><path pathLength="1" d="M36 -4L82 96" style="--i:.07"/><path pathLength="1" d="M54 -6L100 94" style="--i:.14"/></g></svg>`, css: `.ef-sobre-$ID .gr{filter:drop-shadow(0 0 3px #ffd23f)}.ef-sobre-$ID .gr path{stroke-dasharray:1;stroke-dashoffset:1;animation:k-$ID-gr 5s ease-out calc(var(--i) * 1s + ${fase(5, .3)}) infinite}@keyframes k-$ID-gr{0%,20%{stroke-dashoffset:1;opacity:1}27%{stroke-dashoffset:0}48%{stroke-dashoffset:0;opacity:1}60%,100%{stroke-dashoffset:0;opacity:0}}` }] }),
        EP('Três Arranhões', 'Três cortes de garra rasgam o cartão na diagonal, com faíscas de metal.', [
            { k: 'raw', html: `<svg class="rz" viewBox="0 0 340 440" preserveAspectRatio="none"><g fill="none" stroke="#eef2fa" stroke-width="7" stroke-linecap="round"><path pathLength="1" d="M70 20L230 420" style="--i:0"/><path pathLength="1" d="M140 0L300 400" style="--i:.15"/><path pathLength="1" d="M10 50L170 440" style="--i:.3"/></g></svg>`,
              css: `.ef-pf-$ID .rz{position:absolute;inset:0;width:100%;height:100%;filter:drop-shadow(0 0 6px #ffd23f)}.ef-pf-$ID .rz path{stroke-dasharray:1;stroke-dashoffset:1;animation:k-$ID-rz 7s ease-out calc(var(--i) * 1s + ${fase(7, .4)}) infinite}@keyframes k-$ID-rz{0%,24%{stroke-dashoffset:1;opacity:1}30%{stroke-dashoffset:0}60%{stroke-dashoffset:0;opacity:1}76%,100%{stroke-dashoffset:0;opacity:0}}` },
            { k: 'flash', cor: '#fff0a0', dur: 7, ini: 24 },
            { k: 'sobe', icones: ['brilho'], pals: [{ m: '#fff', o: '#c4cad6', w: 2 }], n: 8, tam: [6, 11], vel: [3, 6] },
        ], { r: 'epico' }),
        SOM('Garras', 'Um "snikt" de metal deslizando e um rosnado grave, ao entrar na call.', { notas: [{ t: .02, f: 3000, f2: 5400, d: .25, tipo: 'sawtooth', v: .15 }, { t: .2, f: 85, f2: 55, d: .5, tipo: 'sawtooth', v: .45 }], ruidos: [{ t: 0, d: .22, f: 2500, f2: 7000, filtro: 'bandpass', v: .8, q: 2 }] }),
    ],
});

// =====================================================================================================  FEITIÇO (caos escarlate)
const FE = { m: '#e23636', a: '#ff8a8a', d: '#2a0408', l: '#ffd0d0', o: '#4a0a10' };
const feitico = tema({
    id: 'feitico', pre: 'fei', nome: 'Magia do Caos', cat: 'quadrinhos', cor: '#e23636', cores: ['#e23636', '#2a0408'], icone: 'fa-hat-wizard',
    lema: 'A realidade é o que eu decidir.',
    desc: 'Fiapos de magia escarlate que se retorcem, nuvens vermelhas e o brilho de uma energia que não obedece a regra nenhuma.',
    pal: FE,
    itens: [
        M('Fiapos', 'Ondas escarlate se retorcendo em volta da foto, girando devagar.', { t: 'forma', forma: 'ondas', n: 10, amp: 7, esp: 11, cor: '#e23636', cor2: '#8a0a1a', linha: '#2a0408', lw: 1.6, giro: 54, glow: '#e23636' }, { r: 'raro' }),
        N('Caos', 'Vermelho de magia com um brilho rosado que pisca e contorno escuro.', { grad: ['#a81018', '#ff6a7a', '#a81018'], mov: 'pulsa', brilho: '#e23636', bw: 3, contorno: '#2a0408', cw: 1, fonte: 'cursiva', peso: 800, dur: 2 }, { r: 'raro' }),
        Pl('Magia Escarlate', 'Fios de magia vermelha ondulando sobre o preto, com um brilho que passa.', { base: ['#14040a', '#2a0a14'], pad: { tipo: 'ondas', c1: 'rgba(226,54,54,.4)', c2: 'transparent', tam: 14 }, mov: 'x', dur: 7, brilho: 'rgba(255,138,138,.4)', borda: 'rgba(226,54,54,.75)', icone: { nome: 'brilho', pal: { m: '#ff8a8a', o: '#e23636', w: 3 }, lado: 'dir', tam: 62 } }, { r: 'raro' }),
        F('Nuvem Escarlate', 'Uma névoa vermelha que se mexe sobre o preto, com faíscas de magia piscando.', {
            fundo: ['#0a0204', '#3a0a14', '#7a1424'], fixo: `<g opacity='.55'>${cena.nuvens({ cor: '#e23636', n: 4, y: [24, 90], tam: [20, 34], seed: 'fe1' })}</g>`,
            longe: { svg: `<g opacity='.5'>${cena.nuvens({ cor: '#ff6a7a', n: 3, y: [10, 70], tam: [16, 26], seed: 'fe2' })}</g>`, anim: 'pan', dur: 30 },
            perto: { svg: cena.icones({ nomes: ['brilho'], pals: [{ m: '#ffd0d0', o: '#e23636', w: 2 }], n: 9, tam: [7, 12], seed: 'fe3', y: [6, 104] }), anim: 'pisca', dur: 1.8 },
        }, { r: 'raro' }),
        EA('Fiapos de Magia', 'Faíscas escarlate giram em volta da foto e uma aura vermelha ondula.', [
            { k: 'aura', cor: '#e23636', dur: 1.6 },
            { k: 'orbita', icones: ['brilho'], pals: [{ m: '#ff8a8a', o: '#e23636', w: 2.5 }], n: 8, tam: 20, giro: 14 },
            { k: 'anel', cor: '#ff6a7a', r: 66, esp: 1.8, dash: '2 5', giro: 10, rev: true },
        ], { r: 'raro' }),
        EP('Caos Escarlate', 'Névoa vermelha, faíscas de magia e clarões que estalam pelo cartão.', [
            { k: 'neblina', cor: '#e23636', alfa: .42, n: 5 },
            { k: 'pisca', icone: 'brilho', pals: [{ m: '#ffd0d0', o: '#e23636', w: 2 }], n: 14, tam: [7, 14] },
            { k: 'sobe', icones: ['brilho'], pals: [{ m: '#ff8a8a', o: '#e23636', w: 2.5 }], n: 10, tam: [8, 16], vel: [5, 9] },
            { k: 'flash', cor: '#ff4a5a', dur: 5, ini: 60 },
        ], { r: 'epico' }),
        SOM('Caos', 'Um chiado de energia que gira e um estalo que deforma, ao entrar na call.', { notas: [{ t: 0, f: 300, f2: 180, d: .5, tipo: 'sawtooth', v: .3 }, { t: .3, f: 900, f2: 300, d: .4, tipo: 'sine', v: .3 }], ruidos: [{ t: 0, d: .6, f: 1200, f2: 4000, filtro: 'bandpass', v: .45, q: 1.2 }] }),
    ],
});

// =====================================================================================================  TRUQUE
const LK = { m: '#2ee86a', a: '#9affbd', d: '#04200e', l: '#e8fff0', o: '#04401c' };
const OLK = { m: '#e8b82a', a: '#fff0a0', d: '#5a3a00', l: '#fff', o: '#8a5a00' };
const truque = tema({
    id: 'truque', pre: 'tru', nome: 'Deus das Trapaças', cat: 'quadrinhos', cor: '#2ee86a', cores: ['#2ee86a', '#e8b82a'], icone: 'fa-hat-wizard',
    lema: 'Nada é o que parece.',
    desc: 'Verde e ouro: chifres dourados, ilusões que falham com um chiado de glitch e uma cidade que pode não estar ali.',
    pal: LK,
    itens: [
        M('Chifres', 'Chifres dourados em volta da foto, apontando pra fora.', { t: 'icones', icones: ['chifre'], pals: [OLK], n: 8, tam: 32, giro: 56, orient: 'fora', glow: '#e8b82a' }, { r: 'raro' }),
        N('Truque', 'Verde e dourado que de repente racha em rosa e ciano, como uma ilusão que falha.', { grad: ['#16b84a', '#e8b82a', '#16b84a'], mov: 'glitch', g1: '#ff2d95', g2: '#22e4ff', dur: 3.4, contorno: '#04200e', cw: 1.1, fonte: 'classica', peso: 900, espaco: .6 }, { r: 'raro' }),
        Pl('Ilusão', 'Verde com riscos que dançam, como uma imagem que não se firma, e um chifre ao lado.', { base: ['#04200e', '#0a4a22'], pad: { tipo: 'horizontais', c1: 'rgba(46,232,106,.3)', c2: 'transparent', tam: 8 }, mov: 'y', dur: 3, brilho: 'rgba(232,184,42,.4)', borda: 'rgba(232,184,42,.8)', icone: { nome: 'chifre', pal: OLK, lado: 'dir', tam: 62 } }, { r: 'raro' }),
        F('Cidade que Falha', 'Uma cidade dourada sob uma aurora verde que treme como uma ilusão que falha.', {
            fundo: ['#03140a', '#0a4a22', '#2ee86a'], fixo: `${cena.skyline({ cor: '#e8b82a', altMin: 22, altMax: 64, larg: [8, 14], seed: 'tk1', antenas: true })}<rect y='96' width='340' height='16' fill='#0a2a14'/>`,
            longe: { svg: `<rect y='24' width='340' height='3' fill='#fff' opacity='.55'/><rect x='80' y='58' width='160' height='3' fill='#04200e' opacity='.7'/><rect x='10' y='84' width='120' height='3' fill='#2ee86a' opacity='.7'/>`, anim: 'pan', dur: 2.6 },
            perto: { svg: cena.estrelas({ cor: '#e8fff0', n: 16, y: [4, 80], seed: 'tk2' }), anim: 'pisca', dur: 2 },
        }, { r: 'raro' }),
        EA('Ilusão', 'A sua foto racha em barras de glitch verdes e douradas, e uma luz verde pulsa por trás.', [
            { k: 'aura', cor: '#2ee86a', dur: 2 },
            { k: 'faiscas', icone: 'chifre', pals: [OLK], n: 4, tam: 8, raio: 39 },
        ], { r: 'raro', sobre: [{ k: 'glitch', c1: '#2ee86a', c2: '#e8b82a', dur: 2.6 }] }),
        EP('Truque', 'Barras de glitch cruzam o cartão, faíscas douradas flutuam e a imagem treme como uma ilusão.', [
            { k: 'clima', fundo: 'linear-gradient(120deg,rgba(46,232,106,.4),transparent 50%,rgba(232,184,42,.35))', min: .3, max: 1, dur: 3 },
            { k: 'raw', html: '<i class="g1"></i><i class="g2"></i>', css: `.ef-pf-$ID .g1,.ef-pf-$ID .g2{position:absolute;left:0;right:0;height:5%;background:rgba(46,232,106,.5);mix-blend-mode:screen;opacity:0;animation:k-$ID-g 5s steps(1,end) infinite}.ef-pf-$ID .g1{top:24%}.ef-pf-$ID .g2{top:62%;background:rgba(232,184,42,.5);animation-delay:-2.1s}@keyframes k-$ID-g{0%,56%{opacity:0;transform:translateX(0)}58%{opacity:1;transform:translateX(6%)}62%{opacity:.8;transform:translateX(-8%)}66%{opacity:1;transform:translateX(4%)}70%,100%{opacity:0}}` },
            { k: 'deriva', icones: ['brilho'], pals: [{ m: '#e8b82a', o: '#2ee86a', w: 2 }], n: 8, tam: [8, 14], vel: [7, 13], y: [4, 96], bal: 24 },
            { k: 'flash', cor: '#9affbd', dur: 5, ini: 56 },
        ], { r: 'epico' }),
        SOM('Truque', 'Um acorde dourado e um chiado de glitch que desfaz tudo, ao entrar na call.', { notas: [{ t: 0, f: 659, d: .3, tipo: 'triangle', v: .45 }, { t: 0, f: 988, d: .3, tipo: 'triangle', v: .3 }, { t: .3, f: 220, f2: 90, d: .25, tipo: 'sawtooth', v: .3 }], ruidos: [{ t: .28, d: .22, f: 4000, f2: 900, filtro: 'bandpass', v: .7, q: 2 }] }),
    ],
});

module.exports = [stark, escudo, trovao, gama, wakanda, mistica, joias, mercenario, garras, feitico, truque];
