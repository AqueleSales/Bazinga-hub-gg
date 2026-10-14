'use strict';
/* TERROR 1: Sangue, Fantasmas, Halloween, Olhos na Escuridão, Teias e Aranhas. Tudo desenhado por código. */
const { M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P, I, B, fase } = require('../dsl');
const { cena } = P;
const { icone } = I;
const { G } = require('./_generico');
const pal = (m, o) => ({ m, a: B.claro(m, .4), d: B.escuro(m, .62), l: '#ffffff', o: o || B.escuro(m, .42) });
const suave = (cor) => ({ m: cor, a: cor, d: cor, l: cor, o: cor, w: -2 });
const f1 = (n) => Math.round(n * 10) / 10;
const grande = (nome, p, x, y, t, rot = 0) => `<g transform='translate(${f1(x - t / 2)} ${f1(y - t / 2)}) rotate(${rot} ${f1(t / 2)} ${f1(t / 2)}) scale(${f1(t / 100)})'>${icone(nome, p)}</g>`;

const SANGUE = pal('#b3121f', '#1a0408'), SANGUE_C = pal('#e8344a', '#2a0610');
const GELO = pal('#dfeeff', '#4a6a8a');
const ABOB = pal('#ff8a1f', '#2a1000'), ROXH = pal('#7a3ac8', '#14081e'), VERDH = pal('#7ac83a', '#1a2a08');
const OLHO = pal('#ffe066', '#0a0a0a');

// ---- um anel de sangue com gotas escorrendo (a parte de baixo escorre mais) ----
const anelSangue = (() => {
    const ang = [200, 218, 236, 304, 322, 340, 20, 38, 56, 124, 142, 160];
    const comp = [30, 12, 22, 16, 30, 12, 34, 14, 26, 22, 12, 30];
    let gotas = '';
    ang.forEach((a, k) => {
        const r = 82, x = 100 + r * Math.cos(a * Math.PI / 180), y = 100 + r * Math.sin(a * Math.PI / 180), w = 3.6 + (k % 3), L = comp[k] * (y > 100 ? 1 : .5);
        if (y < 100) return;
        gotas += `<path d='M${f1(x - w)} ${f1(y)}L${f1(x - w)} ${f1(y + L)}A${w} ${w} 0 0 0 ${f1(x + w)} ${f1(y + L)}L${f1(x + w)} ${f1(y)}Z' class='g' style='--i:${k}'/>`;
    });
    const anel = `M100 14A86 86 0 1 1 99.9 14ZM100 32A68 68 0 1 0 100.1 32Z`;
    return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><g fill='#b3121f' stroke='#2a0408' stroke-width='2.2' stroke-linejoin='round'><path fill-rule='evenodd' d='${anel}'/>${gotas}</g><path d='M52 46C70 28 100 22 130 30' fill='none' stroke='#ff8a96' stroke-width='3.4' stroke-linecap='round' opacity='.6'/></svg>`;
})();
const gotejando = (cor) => { let h = ''; [10, 36, 70, 96, 128, 150, 186, 214, 244, 270, 300, 326].forEach((x, k) => { const L = 14 + ((k * 37) % 30), w = 3 + (k % 3); h += `<path d='M${x - w} 0V${L}A${w} ${w} 0 0 0 ${x + w} ${L}V0Z'/>`; }); return `<g fill='${cor}' stroke='#2a0408' stroke-width='1.2'><rect width='340' height='7'/>${h}</g>`; };

// ---- olhos que abrem no escuro ----
const PARES = [[12, 13], [74, 7], [30, 41], [86, 33], [14, 67], [62, 60], [88, 82], [38, 90]];
const olhosRaw = (cor) => ({ k: 'raw',
    html: PARES.map(([x, y], k) => `<i class="oc" style="left:${x}%;top:${y}%;--s:${[16, 22, 14, 18, 20, 12, 16, 14][k]}px;--d:${f1(k * 1.1)}s;--t:${f1(7 + (k % 4))}s"><b></b><b></b></i>`).join(''),
    css: `.ef-pf-$ID .oc{position:absolute;display:flex;gap:calc(var(--s)*.5);margin:calc(var(--s)*-.5) 0 0 calc(var(--s)*-1)}.ef-pf-$ID .oc b{display:block;width:var(--s);height:calc(var(--s)*.55);border-radius:50%;background:radial-gradient(ellipse at 50% 50%,#fff 0 14%,${cor} 34%,transparent 72%);box-shadow:0 0 calc(var(--s)*.7) ${cor};opacity:0;animation:k-$ID-o var(--t) ease-in-out calc(var(--d) - var(--ef-prev,0)*3s) infinite}@keyframes k-$ID-o{0%,8%{opacity:0;transform:scaleY(.1)}16%,52%{opacity:1;transform:scaleY(1)}55%{transform:scaleY(.08)}58%,68%{transform:scaleY(1)}80%,100%{opacity:0;transform:scaleY(.1)}}` });

// ---- aranhas descendo por um fio ----
const ARANHA = pal('#14101c', '#e8e8f0');
const aranhaFio = (x, y0, y1) => ({ k: 'raw', html: `<svg viewBox="0 0 100 100"><g class="ar"><path d="M${x} -90V${y0}" stroke="#e8e8f0" stroke-width=".9"/><g transform="translate(${x} ${y0 + 3}) scale(.13) translate(-50 -50)">${icone('aranha', ARANHA)}</g></g></svg>`,
    css: `.ef-sobre-$ID .ar{animation:k-$ID-ar 6s ease-in-out infinite alternate}@keyframes k-$ID-ar{from{transform:translateY(0)}to{transform:translateY(${y1 - y0}px)}}` });

module.exports = [
    // ============================================================ SANGUE
    G({ id: 'sangue', pre: 'sng', nome: 'Sangue', cat: 'sombrio', cor: '#b3121f', cores: ['#b3121f', '#14080a'], icone: 'fa-droplet',
        lema: 'Vermelho que escorre e não seca.', desc: 'Gotas pesadas, poças e muito vermelho escorrendo: moldura, nome e cartão pingando num tema só para quem gosta do pior.',
        pal: SANGUE_C, icones: ['gota_sangue'], pals: [SANGUE_C, SANGUE, pal('#7a0a14', '#14030a')], fundo: ['#2a0508', '#14030a'], texto: null,
        m: { t: 'svg', nome: 'Escorrendo', desc: 'Um anel de sangue grosso com gotas que escorrem pela borda de baixo da foto, pulsando como se estivesse vivo.', svg: anelSangue, giro: 0, pulso: 3.6, glow: '#b3121f', inset: .26, icones: undefined, tam: undefined, n: undefined },
        n: { nome: 'Pingando', desc: 'Do vermelho-vivo ao vinho escuro, com a tinta escorrendo pelas letras, e uma gota no fim.', grad: ['#ff3a4a', '#b3121f', '#6a0a14', '#b3121f'], contorno: '#14030a', cw: 1.1, fonte: 'classica', peso: 900, mov: 'gotejar', icone: { nome: 'gota_sangue', pos: 'depois', pal: SANGUE_C } },
        p: { nome: 'Poça', desc: 'Vermelho escuro com gotas pesadas espalhadas, e uma poça ao lado.', pad: { tipo: 'icones', icones: ['gota_sangue'], pals: [suave('#8a0a14')], tam: 26, ti: 12, c2: 'transparent' }, borda: '#5a0610', icone: 'gota_sangue' },
        f: { nome: 'Parede Suja', desc: 'Uma parede escura com sangue escorrendo do alto e uma poça crescendo embaixo.', fundo: ['#3a0a10', '#14030a'], fixo: `${gotejando('#b3121f')}<path d='M0 112V100C40 94 80 104 130 98S230 94 270 100 320 98 340 102V112Z' fill='#8a0a14'/>`, longe: { svg: `<g transform='translate(0 8)' opacity='.8'>${gotejando('#e8344a')}</g>`, anim: 'respira', dur: 5 }, perto: false },
        ea: { nome: 'Escorrendo', desc: 'Gotas de sangue escorrem pela borda de cima da foto e uma aura vermelha bate como um coração.', camadas: [{ k: 'aura', cor: '#b3121f', dur: 1.6 }, { k: 'sobe', icones: ['gota_sangue'], pals: [SANGUE_C], n: 4, tam: 9, alt: 150 }], sobre: [{ k: 'pingos', cor: '#b3121f', n: 6, dur: 6 }] },
        ep: { nome: 'Chuva Vermelha', desc: 'Gotas de sangue caem pelo cartão, o vermelho respira e uma poça vai subindo e baixando embaixo.', camadas: [{ k: 'clima', fundo: 'linear-gradient(180deg,rgba(179,18,31,.45),rgba(20,3,10,.3))', min: .45, max: .9, dur: 6 }, { k: 'cai', icones: ['gota_sangue'], pals: [SANGUE_C, SANGUE], n: 18, tam: [9, 18], vel: [3, 7], bal: 8, giro: 6 }, { k: 'ondas', cor: '#8a0a14', alfa: .85, alt: 12, dur: 8 }, { k: 'borda', cor: '#b3121f', alfa: .5, dur: 2.4 }] },
        extra: [PIN('Gota', 'Suas notas no mapa viram uma gota de sangue.', { icone: 'gota_sangue', pal: SANGUE_C, bal: 3 }), SERV('Pulso', 'Um anel vermelho que bate como um coração no ícone do servidor.', { cores: ['#b3121f', '#e8344a'], dur: 1.2 }),
            SOM('Pingo', 'Três pingos pesados e um estalo úmido, ao entrar na call.', { notas: [{ t: 0, f: 900, f2: 180, d: .09, tipo: 'sine', v: .7 }, { t: .3, f: 760, f2: 150, d: .09, tipo: 'sine', v: .6 }, { t: .55, f: 640, f2: 120, d: .12, tipo: 'sine', v: .5 }], ruidos: [{ t: .55, d: .15, f: 400, filtro: 'lowpass', v: .3 }] })] }),

    // ============================================================ FANTASMAS
    G({ id: 'fantasma', pre: 'fan', nome: 'Fantasmas', cat: 'sombrio', cor: '#dfeeff', cores: ['#dfeeff', '#4a6a8a'], icone: 'fa-ghost',
        lema: 'Uuuh... quem é que está aí?', desc: 'Lençóis flutuando, olhos vazados, névoa azul e uma lua pálida: uma casa que nunca está vazia.',
        pal: GELO, icones: ['fantasma', 'lua', 'estrelinha'], pals: [GELO, pal('#bcd8f0', '#2a4a6a'), pal('#ffffff', '#4a6a8a')], fundo: ['#14202c', '#2a4058'], texto: null,
        m: { nome: 'Assombração', desc: 'Fantasminhas e estrelinhas flutuando em volta da foto.', icones: ['fantasma', 'estrelinha'], tam: 27 },
        n: { nome: 'Lençol', desc: 'Branco-azulado fantasmagórico, que some e aparece, e um fantasma no fim.', grad: ['#9ac0e0', '#ffffff', '#9ac0e0'], contorno: '#1a2a3a', cw: .9, mov: 'pulsa', icone: true },
        p: { nome: 'Casa Vazia', desc: 'Fantasminhas esmaecidos sobre o azul noturno, e um fantasma ao lado.', pad: { tipo: 'icones', icones: ['fantasma'], pals: [suave('#bcd8f0')], tam: 28, ti: 14, c2: 'transparent' }, icone: 'fantasma' },
        f: { nome: 'Noite Assombrada', desc: 'Uma lua pálida, névoa azul e fantasmas passando devagar pelo céu.', fundo: ['#0a1420', '#2a4058'], fixo: `${cena.estrelas({ cor: '#dfeeff', n: 18, y: [0, 60], seed: 'fn1', r: [.5, 1.2] })}<circle cx='270' cy='36' r='22' fill='#dfeeff'/><circle cx='262' cy='30' r='4' fill='#bcd8f0'/>${cena.terreno({ cor: '#06101a', y: 92, amp: 4, n: 3 })}`, longe: { svg: cena.icones({ nomes: ['fantasma'], pals: [pal('#dfeeff', '#4a6a8a')], n: 3, tam: [16, 26], seed: 'fn2', y: [10, 70], alfa: .8 }), anim: 'pan', dur: 34 }, perto: { svg: `<g opacity='.35'>${cena.nuvens({ cor: '#bcd8f0', n: 3, y: [60, 100], tam: [24, 36], seed: 'fn3' })}</g>`, anim: 'pan', dur: 22 } },
        ea: { nome: 'Aparição', desc: 'Um fantasminha circula a foto, que fica pálida e translúcida como uma assombração.', camadas: [{ k: 'aura', cor: '#bcd8f0', dur: 3.4 }, { k: 'orbita', icones: ['fantasma'], pals: [GELO], n: 3, tam: 26, giro: 22 }, { k: 'sobe', icones: ['estrelinha'], pals: [pal('#ffffff', '#4a6a8a')], n: 5, tam: 8, alt: 150 }], sobre: [{ k: 'vinheta', cor: '#dfeeff', alfa: .5, pulso: 4 }] },
        ep: { nome: 'Assombração', desc: 'Fantasmas atravessam o cartão numa névoa azul, e um relâmpago acende tudo de vez em quando.', camadas: [{ k: 'clima', fundo: 'linear-gradient(180deg,rgba(80,120,160,.4),rgba(10,20,32,.3))', min: .5, max: .9, dur: 8 }, { k: 'neblina', cor: '#bcd8f0', alfa: .4, n: 5, vel: 24 }, { k: 'deriva', icones: ['fantasma'], pals: [GELO], n: 4, tam: [24, 40], vel: [12, 20], y: [10, 75], bal: 36, alfa: .75 }, { k: 'flash', cor: '#dfeeff', dur: 13, ini: 70 }] },
        extra: [SOM('Uuuh', 'Um lamento agudo que desce, ao entrar na call.', { notas: [{ t: 0, f: 700, f2: 280, d: .9, tipo: 'sine', v: .35 }, { t: .05, f: 705, f2: 285, d: .9, tipo: 'triangle', v: .2 }], ruidos: [{ t: 0, d: .8, f: 900, filtro: 'bandpass', v: .1 }] }), PIN('Lençol', 'Suas notas no mapa viram um fantasminha.', { icone: 'fantasma', pal: GELO, bal: 3 })] }),

    // ============================================================ HALLOWEEN
    G({ id: 'halloween', pre: 'hal', nome: 'Noite de Halloween', cat: 'sombrio', cor: '#ff8a1f', cores: ['#ff8a1f', '#7a3ac8'], icone: 'fa-hat-wizard',
        lema: 'Doce ou travessura?', desc: 'Abóboras de olhos acesos, chapéu de bruxa, morcegos e uma lua enorme: laranja, roxo e preto na noite das bruxas.',
        pal: ABOB, icones: ['abobora', 'jackolantern', 'morcego', 'fantasma', 'caldeirao'], pals: [ABOB, pal('#a8e03a', '#1a2a08'), pal('#2a1a3a', '#ff8a1f'), pal('#ffffff', '#4a3a6a')], fundo: ['#1a0a2a', '#4a1a6a'], texto: null,
        m: { nome: 'Abóboras e Morcegos', desc: 'Abóboras, morcegos, fantasmas e caldeirões em volta da foto.', icones: ['jackolantern', 'morcego', 'fantasma', 'abobora'], tam: 28 },
        n: { nome: 'Travessura', desc: 'Laranja-abóbora e roxo, com contorno preto, e uma abóbora de olhos acesos no fim.', grad: ['#ff8a1f', '#ffd166', '#ff8a1f', '#a05aff'], contorno: '#14081e', cw: 1.3, fonte: 'classica', peso: 900, mov: 'desliza', icone: { nome: 'jackolantern', pos: 'depois', pal: ABOB } },
        p: { nome: 'Teia e Abóbora', desc: 'Roxo-escuro com abóboras e morcegos, e um chapéu de bruxa ao lado.', base: ['#2a1048', '#14081e'], pad: { tipo: 'icones', icones: ['abobora', 'morcego'], pals: [suave('#ff8a1f'), suave('#6a3a9a')], tam: 28, ti: 14, c2: 'transparent' }, icone: 'chapeu_bruxa' },
        f: { nome: 'Lua das Bruxas', desc: 'Uma lua laranja enorme atrás de uma árvore seca, com abóboras no chão e morcegos voando.', fundo: ['#1a0a2a', '#7a2a6a', '#ff8a1f'], fixo: `<circle cx='250' cy='52' r='40' fill='#ffb04a'/><circle cx='238' cy='42' r='6' fill='#e8903a'/><circle cx='262' cy='62' r='9' fill='#e8903a'/>${grande('arvore_morta', pal('#0a0410', '#0a0410'), 60, 56, 90)}${cena.terreno({ cor: '#0a0410', y: 96, amp: 3, n: 4 })}${grande('jackolantern', ABOB, 150, 94, 24)}${grande('abobora', ABOB, 296, 96, 20)}`, longe: { svg: cena.icones({ nomes: ['morcego'], pals: [pal('#0a0410', '#6a3a9a')], n: 4, tam: [14, 22], seed: 'ha1', y: [4, 60] }), anim: 'pan', dur: 26 } },
        ea: { nome: 'Chapéu de Bruxa', desc: 'Um chapéu de bruxa no alto da foto, com morcegos girando em volta e uma aura laranja.', camadas: [{ k: 'aura', cor: '#ff8a1f', dur: 2.6 }, { k: 'orbita', icones: ['morcego', 'abobora'], pals: [pal('#14081e', '#ff8a1f'), ABOB], n: 5, tam: 22, giro: 26 }, { k: 'topo', icone: 'chapeu_bruxa', pal: pal('#4a2a7a', '#14081e'), tam: 52, y: 6, rot: -14, dur: 4 }] },
        ep: { nome: 'Doces e Travessuras', desc: 'Abóboras, morcegos e fantasmas atravessam o cartão sob uma lua laranja, com névoa roxa passando.', camadas: [{ k: 'clima', fundo: 'linear-gradient(180deg,rgba(122,58,200,.45),rgba(255,138,31,.25))', min: .5, max: .95, dur: 6 }, { k: 'neblina', cor: '#7a3ac8', alfa: .4, n: 4, vel: 24 }, { k: 'cai', icones: ['abobora', 'jackolantern', 'fantasma'], pals: [ABOB, ABOB, pal('#ffffff', '#4a3a6a')], n: 12, tam: [14, 26], vel: [7, 13], bal: 60, giro: 200 }, { k: 'deriva', icones: ['morcego'], pals: [pal('#0a0410', '#ff8a1f')], n: 4, tam: [18, 30], vel: [9, 16], y: [6, 60], bal: 30 }, { k: 'borda', cor: '#ff8a1f', alfa: .35, dur: 3 }] },
        extra: [PIN('Abóbora', 'Suas notas no mapa viram uma abóbora de olhos acesos.', { icone: 'jackolantern', pal: ABOB, bal: 2.4 }), SERV('Lanterna', 'Um anel laranja que pisca no ícone do servidor.', { cores: ['#ff8a1f', '#7a3ac8'], dur: 1.8 }),
            SOM('Gargalhada', 'Uma risada de bruxa aguda e um trovão, ao entrar na call.', { notas: [{ t: 0, f: 600, f2: 900, d: .1, tipo: 'sawtooth', v: .25 }, { t: .12, f: 640, f2: 940, d: .1, tipo: 'sawtooth', v: .25 }, { t: .24, f: 680, f2: 980, d: .1, tipo: 'sawtooth', v: .25 }, { t: .36, f: 720, f2: 1020, d: .16, tipo: 'sawtooth', v: .25 }], ruidos: [{ t: .5, d: .5, f: 400, f2: 80, filtro: 'lowpass', v: .5 }] })] }),

    // ============================================================ OLHOS NA ESCURIDÃO
    G({ id: 'olhos', pre: 'olh', nome: 'Olhos na Escuridão', cat: 'sombrio', cor: '#ffe066', cores: ['#ffe066', '#0a0a0a'], icone: 'fa-eye',
        lema: 'Não olhe para o escuro. Ele olha de volta.', desc: 'Pares de olhos amarelos que abrem no escuro, piscam devagar e somem. Preto total e brilho amarelo.',
        pal: OLHO, icones: ['olho_fenda', 'olho'], pals: [OLHO, pal('#ff3a3a', '#0a0a0a'), pal('#7aff6a', '#0a0a0a')], fundo: ['#050508', '#14141c'], texto: null,
        m: { nome: 'Vigias', desc: 'Olhos de fenda amarelos em volta da foto, olhando.', icones: ['olho_fenda'], pals: [OLHO, pal('#ff3a3a', '#0a0a0a')], n: 8, tam: 26 },
        n: { nome: 'Brilho no Escuro', desc: 'Amarelo-olho que pisca no preto, com um olho de fenda no fim.', grad: ['#ffe066', '#ffffff', '#ffe066'], contorno: '#050508', cw: 1, mov: 'pisca', icone: { nome: 'olho_fenda', pos: 'depois', pal: OLHO } },
        p: { nome: 'Escuridão', desc: 'Preto fundo com olhinhos amarelos espiando, e um olho grande ao lado.', base: ['#050508', '#14141c'], pad: { tipo: 'icones', icones: ['olho_fenda'], pals: [suave('#7a6a1a')], tam: 24, ti: 12, c2: 'transparent' }, icone: 'olho_fenda' },
        f: { nome: 'Breu', desc: 'Um breu cheio de olhos amarelos abrindo e fechando, sem ver mais nada.', fundo: ['#050508', '#0a0a12'], longe: { svg: cena.icones({ nomes: ['olho_fenda'], pals: [pal('#ffe066', '#050508'), pal('#ff3a3a', '#050508')], n: 8, tam: [10, 18], seed: 'ol1', y: [8, 96] }), anim: 'pisca', dur: 3 }, perto: { svg: cena.icones({ nomes: ['olho_fenda'], pals: [pal('#ffe066', '#050508')], n: 5, tam: [14, 22], seed: 'ol2', y: [10, 96] }), anim: 'pisca', dur: 4.4 } },
        ea: { nome: 'Olhando', desc: 'Olhos de fenda abrem em volta da foto, que fica no escuro.', camadas: [{ k: 'orbita', icones: ['olho_fenda'], pals: [OLHO, pal('#ff3a3a', '#0a0a0a')], n: 6, tam: 22, giro: 40 }, { k: 'aura', cor: '#ffe066', dur: 3 }], sobre: [{ k: 'vinheta', cor: '#000000', alfa: .8, pulso: 3.4 }] },
        ep: { nome: 'Olhos', desc: 'O cartão escurece e vários pares de olhos amarelos abrem, piscam e somem, em lugares diferentes.', camadas: [{ k: 'clima', fundo: 'radial-gradient(circle at 50% 38%,transparent 25%,rgba(0,0,0,.88) 95%)', min: .75, max: 1, dur: 5 }, olhosRaw('#ffe066')] },
        extra: [SOM('Rosnado', 'Um rosnado grave e um brilho agudo, ao entrar na call.', { notas: [{ t: 0, f: 70, f2: 55, d: .8, tipo: 'sawtooth', v: .35 }, { t: .5, f: 2000, f2: 2400, d: .2, tipo: 'sine', v: .12 }], ruidos: [{ t: 0, d: .8, f: 300, filtro: 'lowpass', v: .4 }] }), PIN('Olho', 'Suas notas no mapa viram um olho de fenda.', { icone: 'olho_fenda', pal: OLHO, bal: 3 })] }),

    // ============================================================ TEIAS E ARANHAS
    G({ id: 'teias', pre: 'tia', nome: 'Teias e Aranhas', cat: 'sombrio', cor: '#e8e8f0', cores: ['#e8e8f0', '#2a2a3a'], icone: 'fa-spider',
        lema: 'Fios finos, paciência infinita.', desc: 'Teias nos cantos, aranhas descendo por um fio e orvalho pendurado: cinza-prata sobre o escuro do sótão.',
        pal: pal('#e8e8f0', '#2a2a3a'), icones: ['teia', 'aranha'], pals: [pal('#e8e8f0', '#2a2a3a'), pal('#14101c', '#e8e8f0'), pal('#b0b0c0', '#2a2a3a')], fundo: ['#1a1a24', '#34344a'], texto: null,
        m: { nome: 'Teia de Orvalho', desc: 'Teias e aranhas penduradas em volta da foto.', icones: ['teia', 'aranha'], tam: 27 },
        n: { nome: 'Fio de Seda', desc: 'Prata fina como seda, com um brilho que corre e uma aranha no fim.', grad: ['#9a9ab0', '#ffffff', '#9a9ab0'], contorno: '#14101c', cw: 1, icone: { nome: 'aranha', pos: 'depois', pal: pal('#14101c', '#e8e8f0') } },
        p: { nome: 'Sótão', desc: 'Teias de aranha sobre o cinza escuro, com uma aranha ao lado.', pad: { tipo: 'icones', icones: ['teia'], pals: [suave('#6a6a80')], tam: 30, ti: 16, c2: 'transparent' }, icone: 'aranha' },
        f: { nome: 'Canto do Sótão', desc: 'Um canto escuro com uma teia grande, aranhas penduradas e poeira no ar.', fundo: ['#14141c', '#34344a'], fixo: `${grande('teia', pal('#e8e8f0'), 40, 40, 110)}${grande('teia', pal('#e8e8f0'), 310, 36, 80, 90)}<g stroke='#e8e8f0' stroke-width='.9'><path d='M120 0V40M230 0V62'/></g>${grande('aranha', ARANHA, 120, 46, 14)}${grande('aranha', ARANHA, 230, 68, 18)}`, longe: false, perto: { svg: cena.icones({ nomes: ['grao'], pals: [{ m: '#cfd0e0', o: '#cfd0e0', w: 0, a: '#cfd0e0', d: '#cfd0e0', l: '#cfd0e0' }], n: 14, tam: [2, 4], seed: 'ti1', y: [4, 108] }), anim: 'pisca', dur: 3 } },
        ea: { nome: 'Aranha Pendurada', desc: 'Uma teia no canto da foto e uma aranha que desce por um fio e sobe de novo.', camadas: [{ k: 'aura', cor: '#b0b0c0', dur: 3.4 }, { k: 'orbita', icones: ['aranha'], pals: [ARANHA], n: 3, tam: 18, giro: 40 }], sobre: [{ k: 'teia', cor: '#e8e8f0', rot: 20 }, aranhaFio(28, 10, 34)] },
        ep: { nome: 'Sótão Empoeirado', desc: 'Teias grandes nos cantos do cartão, aranhas descendo e subindo pelos fios e poeira flutuando.', camadas: [{ k: 'cantos', itens: [{ icone: 'teia', x: 6, y: 6, tam: 150, rot: 0, pal: pal('#e8e8f0') }, { icone: 'teia', x: 94, y: 94, tam: 150, rot: 180, pal: pal('#e8e8f0') }], bal: 2 }, { k: 'raw', html: [[24, 0, 5.2], [58, 1.4, 6.6], [84, .6, 5.8]].map(([x, d, t]) => `<i class="fio" style="left:${x}%;--d:${d}s;--t:${t}s"><u></u><svg viewBox="0 0 100 100"><g transform="translate(50 50) scale(.9) translate(-50 -50)">${icone('aranha', ARANHA)}</g></svg></i>`).join(''),
                css: `.ef-pf-$ID .fio{position:absolute;top:0;width:26px;height:240px;margin-left:-13px;transform:translateY(-170px);animation:k-$ID-f var(--t) ease-in-out calc(var(--d) - var(--ef-prev,0)*2.4s) infinite alternate}.ef-pf-$ID .fio u{position:absolute;left:50%;top:0;width:1.2px;height:190px;background:rgba(232,232,240,.85)}.ef-pf-$ID .fio svg{position:absolute;left:0;top:186px;width:26px;height:26px}@keyframes k-$ID-f{to{transform:translateY(-60px)}}` }, { k: 'pisca', icone: 'brilho', pals: [{ m: '#e8e8f0', o: '#e8e8f0', w: 0, a: '#e8e8f0', d: '#e8e8f0', l: '#e8e8f0' }], n: 10, tam: [4, 8] }] },
        extra: [PIN('Aranha', 'Suas notas no mapa viram uma aranha.', { icone: 'aranha', pal: ARANHA, bal: 3 }), SOM('Fio', 'Um fio esticando e vibrando, ao entrar na call.', { notas: [{ t: 0, f: 2200, f2: 3000, d: .3, tipo: 'sine', v: .15 }, { t: .3, f: 1500, f2: 1480, d: .6, tipo: 'triangle', v: .12 }], ruidos: [] })] }),
];
