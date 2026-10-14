'use strict';
/* BIZARRO (aventura psicodélica de poses dramáticas): letras de efeito sonoro japonês desenhadas por código, linhas de impacto, o relógio que para, o ouro que dá vida.
   Arte original: os glifos são traços simples, nada copiado de ninguém. Cada "arco" é um tema à parte (ampla variedade). */
const { tema, M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P, I, fase } = require('../dsl');
const { cena } = P;
const { icone } = I;
const f1 = (n) => Math.round(n * 10) / 10;
const kana = (nome, pal, x, y, s, rot = 0) => `<g transform="translate(${f1(x)} ${f1(y)}) rotate(${rot}) scale(${f1(s / 100)})">${icone('kana_' + nome, pal)}</g>`;

const BIZ = { m: '#e0409a', a: '#ff8aca', d: '#2a0a3a', l: '#ffffff', o: '#12031c' };
const ROXO = { m: '#8a3cff', a: '#c4a0ff', d: '#1a0a3a', l: '#fff', o: '#0a0420' };
const LARJ = { m: '#ff8a1f', a: '#ffc06a', d: '#4a1a00', l: '#fff4d8', o: '#2a0e00' };

const sunburst = (cor1, cor2, n = 22) => { let s = ''; for (let k = 0; k < n; k++) { const a0 = k * 360 / n, a1 = a0 + 180 / n, p = (a, r) => `${f1(170 + r * Math.cos(a * Math.PI / 180))} ${f1(120 + r * Math.sin(a * Math.PI / 180))}`; s += `<path d='M170 120L${p(a0, 300)}L${p(a1, 300)}Z' fill='${k % 2 ? cor1 : cor2}'/>`; } return s; };

// ---- Pose: linhas de impacto, glifos tremendo e um brilho ----
const posePerfil = {
    k: 'raw', html: `<i class="ln"></i><svg class="g1" viewBox="0 0 100 300">${kana('go', BIZ, 0, 0, 100, -4)}${kana('go', BIZ, 0, 100, 100, 3)}${kana('go', BIZ, 0, 200, 100, -3)}</svg><svg class="g2" viewBox="0 0 100 300">${kana('go', ROXO, 0, 0, 100, 4)}${kana('go', ROXO, 0, 100, 100, -3)}${kana('go', ROXO, 0, 200, 100, 3)}</svg>`,
    css: `.ef-pf-$ID .ln{position:absolute;inset:-25%;background:repeating-conic-gradient(from 0deg at 50% 42%,rgba(255,255,255,.85) 0 1.4deg,transparent 1.4deg 9deg);-webkit-mask:radial-gradient(circle at 50% 42%,transparent 18%,#000 62%);mask:radial-gradient(circle at 50% 42%,transparent 18%,#000 62%);opacity:0;animation:k-$ID-ln 9s linear ${fase(9, .4)} infinite}`
        + `.ef-pf-$ID .g1,.ef-pf-$ID .g2{position:absolute;top:6%;width:24%;height:72%;opacity:0;animation:k-$ID-g 9s linear ${fase(9, .4)} infinite,k-$ID-tr .16s steps(2) infinite}.ef-pf-$ID .g1{left:2%}.ef-pf-$ID .g2{right:2%;animation-delay:${fase(9, .4)},0s}`
        + `@keyframes k-$ID-ln{0%,16%{opacity:0;transform:rotate(0)}20%{opacity:1}60%{opacity:.8;transform:rotate(6deg)}70%,100%{opacity:0;transform:rotate(8deg)}}@keyframes k-$ID-g{0%,18%{opacity:0}22%{opacity:1}62%{opacity:1}70%,100%{opacity:0}}@keyframes k-$ID-tr{0%{translate:0 0}50%{translate:1.2px -1px}100%{translate:-1px 1.4px}}`,
};

const bizarro = tema({
    id: 'bizarro', pre: 'biz', nome: 'Aventura Bizarra', cat: 'anime', cor: '#e0409a', cores: ['#e0409a', '#7a2bbf'], icone: 'fa-explosion', premium: true,
    lema: 'Uma pose. Uma vida inteira.',
    desc: 'Poses dramáticas, letras de efeito sonoro japonês flutuando sobre a sua foto, linhas de impacto e cores que não existem na natureza.',
    pal: BIZ,
    itens: [
        M('Flecha', 'Pontas de flecha misteriosas, em magenta e roxo, em volta da sua foto.', { t: 'icones', icones: ['ponta_flecha'], pals: [BIZ, ROXO], n: 10, tam: 28, giro: 46, orient: 'fora' }, { r: 'epico' }),
        M('Estrela de Nascença', 'Seis estrelas grandes, como a marca de uma linhagem, girando em volta da foto.', { t: 'icones', icones: ['estrela'], pals: [{ m: '#9b5cff', a: '#d0b4ff', d: '#1a0a3a', l: '#fff', o: '#12031c' }, BIZ], n: 6, tam: 34, raio: 84, giro: 60, inclina: true }, { r: 'epico' }),
        N('Bizarro', 'Letras de quadrinho com contorno preto grosso, sombra deslocada e cores que mudam sem aviso.', { grad: ['#e0409a', '#ff8a1f', '#1aa6b7', '#8a3cff'], passos: true, mov: 'desliza', dur: 3.2, contorno: '#12031c', cw: 1.4, fonte: 'quadrinho', sombra: [1.6, 1.6, '#12031c'], peso: 900, espaco: .5 }, { r: 'epico' }),
        Pl('Joestar', 'Roxo e magenta com listras cruzadas e uma estrela de nascença ao lado.', { base: ['#5a1a9a', '#e0409a'], pad: { tipo: 'riscado', c1: 'rgba(18,3,28,.4)', c2: 'transparent', tam: 12, lw: 1.6 }, mov: 'x', dur: 9, brilho: 'rgba(255,255,255,.4)', borda: '#12031c', icone: { nome: 'estrela', pal: { m: '#ffd24a', a: '#fff0a8', d: '#7a4a00', l: '#fff', o: '#12031c' }, lado: 'dir', tam: 66 } }, { r: 'epico' }),
        F('Aventura', 'Um céu psicodélico de listras em rajadas, linhas de impacto e o "ゴ" correndo pela faixa.', {
            fundo: ['#2a0a4a'], fixo: `${sunburst('#7a2bbf', '#e0409a')}<rect width='340' height='112' fill='url(#v)' opacity='.0'/>${cena.estrelas({ cor: '#fff', n: 18, seed: 'bz1', r: [.8, 2] })}`,
            longe: { svg: `${kana('go', { ...BIZ, m: '#ffd24a' }, 20, 30, 56, -6)}${kana('do', { ...BIZ, m: '#ffffff' }, 130, 44, 52, 5)}${kana('go', { ...BIZ, m: '#1aa6b7' }, 238, 26, 58, -4)}`, anim: 'pan', dur: 14 },
            perto: { svg: cena.icones({ nomes: ['brilho'], pals: [{ m: '#fff', o: '#e0409a', w: 2 }], n: 8, tam: [8, 14], seed: 'bz2', y: [6, 106] }), anim: 'pisca', dur: 1.8 },
        }, { r: 'epico' }),
        EA('Menacing', 'Letras de efeito sonoro japonês tremem por cima da sua foto, e uma aura roxa pulsa por trás.', [
            { k: 'aura', cor: '#8a3cff', dur: 1.6 },
            { k: 'faiscas', icone: 'brilho', pals: [{ m: '#fff', o: '#e0409a', w: 2 }], n: 6, tam: 8, raio: 39 },
        ], { r: 'epico', sobre: [{ k: 'raw', html: `<svg viewBox="0 0 100 100" class="gg">${kana('go', BIZ, 4, 52, 40, -6)}${kana('go', BIZ, 33, 38, 44, 4)}${kana('go', BIZ, 62, 50, 40, -3)}</svg>`, css: '.ef-sobre-$ID .gg{animation:k-$ID-tr .14s steps(2) infinite}@keyframes k-$ID-tr{0%{translate:0 0}50%{translate:.8px -.7px}100%{translate:-.7px .9px}}' }] }),
        EA('Batida do Coração', 'Os "ド" batem em volta da foto como um coração disparado, em passos.', [
            { k: 'aura', cor: '#e0409a', dur: .9 },
            { k: 'orbita', icones: ['kana_do'], pals: [BIZ, ROXO], n: 6, tam: 30, raio: 78, giro: 24, inclina: true, pulso: .9 },
        ], { r: 'epico', id: 'batida_coracao' }),
        EP('Pose', 'Linhas de impacto estouram pelo cartão e colunas de "ゴ" tremem de cada lado, em magenta e roxo.', [posePerfil], { r: 'lendario' }),
        FALA('Aura de Stand', 'Quando você fala na call, o card acende em magenta e roxo.', { cores: ['#e0409a', '#8a3cff'] }),
        RADAR('Ondas Bizarras', 'As ondas do radar viram anéis magenta tracejados.', { cor: '#e0409a', estilo: 'tracejado', glow: '#8a3cff' }),
        CHAT('Impacto', 'A barra de mensagem pulsa em magenta ao digitar e solta pontas de flecha ao enviar.', { cor: '#e0409a', cor2: '#8a3cff', particula: { icone: 'ponta_flecha', pal: BIZ } }),
        PIN('Estrela', 'Suas notas no mapa viram uma estrela dourada.', { icone: 'estrela', pal: { m: '#ffd24a', a: '#fff0a8', d: '#7a4a00', l: '#fff', o: '#12031c' }, bal: 2 }),
        SOM('Pose Dramática', 'Três batidas graves, um brilho que sobe e um estalo, ao entrar na call.', { notas: [{ t: 0, f: 90, f2: 50, d: .22, tipo: 'sine', v: 1 }, { t: .2, f: 90, f2: 50, d: .22, tipo: 'sine', v: 1 }, { t: .4, f: 90, f2: 40, d: .35, tipo: 'sine', v: 1 }, { t: .55, f: 440, f2: 1760, d: .5, tipo: 'sawtooth', v: .25 }], ruidos: [{ t: .45, d: .2, f: 3000, f2: 800, filtro: 'bandpass', v: .6 }] }),
        SERV('Servidor Bizarro', 'O ícone do servidor pulsa em magenta e roxo.', { cores: ['#e0409a', '#8a3cff'] }),
    ],
});

// ---------------------------------------------------------------------------------------- PARAR O TEMPO
const TP = { m: '#c8e63a', a: '#eef7a0', d: '#0e3a2a', l: '#ffffff', o: '#06201a' };
const romanos = (() => { const R = ['XII', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI']; let t = ''; R.forEach((r, k) => { const a = (k * 30 - 90) * Math.PI / 180; t += `<text x='${f1(100 + 82 * Math.cos(a))}' y='${f1(100 + 82 * Math.sin(a))}' text-anchor='middle' dominant-baseline='central' font-family='Georgia,Times New Roman,serif' font-size='${r.length > 2 ? 15 : 18}' font-weight='700' fill='#e6f05a' stroke='#06201a' stroke-width='3.4' paint-order='stroke'>${r}</text>`; }); return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'>${t}</svg>`; })();
const relogioGrande = (() => { let m = ''; for (let k = 0; k < 12; k++) m += `<path d='M0 -60V-50' stroke='#06201a' stroke-width='${k % 3 ? 2 : 3.6}' transform='rotate(${k * 30})'/>`; return `<g transform='translate(250 56)'><circle r='50' fill='#e6f05a' stroke='#06201a' stroke-width='4'/><circle r='42' fill='#f6ffd0' stroke='#06201a' stroke-width='2'/>${m}<path d='M0 0V-34M0 0V-26' stroke='#06201a' stroke-width='4.4' stroke-linecap='round'/><circle r='5' fill='#06201a'/></g>`; })();

const tempo = tema({
    id: 'tempo_parado', pre: 'tmp', nome: 'O Mundo Para', cat: 'anime', cor: '#c8e63a', cores: ['#c8e63a', '#0e3a2a'], icone: 'fa-clock',
    lema: 'O relógio parou. Só você se mexe.',
    desc: 'Algarismos romanos, um relógio parado em doze horas e o clarão que inverte as cores do mundo por um instante.',
    pal: TP,
    itens: [
        M('Algarismos Romanos', 'Os números romanos de um relógio, em verde-limão, em volta da foto.', { t: 'svg', svg: romanos, giro: 120, inset: .26 }, { r: 'raro' }),
        N('Doze Horas', 'Verde-limão com contorno preto grosso e um relógio no fim do nome.', { grad: ['#9ac41a', '#f2ffa0', '#9ac41a'], mov: 'desliza', dur: 4.4, contorno: '#06201a', cw: 1.3, fonte: 'impacto', espaco: .8, peso: 900, icone: { nome: 'relogio', pos: 'depois', pal: TP } }, { r: 'raro' }),
        Pl('Horas Paradas', 'Relógios e engrenagens sobre o verde-escuro, com um brilho limão passando.', { base: ['#0e3a2a', '#0a2a20'], pad: { tipo: 'icones', icones: ['relogio', 'engrenagem'], pals: [{ m: '#2a6a3a', a: '#2a6a3a', d: '#2a6a3a', l: '#0e3a2a', o: '#2a6a3a', w: 0 }], tam: 30, ti: 18, c2: 'transparent' }, mov: 'x', dur: 24, brilho: 'rgba(200,230,58,.34)', borda: 'rgba(200,230,58,.55)', icone: { nome: 'relogio', pal: TP, lado: 'dir', tam: 68 } }, { r: 'raro' }),
        F('Relógio Parado', 'Um relógio enorme parado em doze horas, raios de luz limão e as engrenagens do tempo.', {
            fundo: ['#0e3a2a', '#1c6a3a', '#9ac41a'], fixo: `${sunburst('#2a8a3a', '#1c6a3a', 24).replace(/<path /g, "<path opacity='.5' ")}${relogioGrande}`,
            longe: { svg: cena.icones({ nomes: ['engrenagem'], pals: [{ m: '#0e3a2a', a: '#0e3a2a', d: '#1c6a3a', l: '#0e3a2a', o: '#0e3a2a', w: 0 }], n: 6, tam: [14, 28], seed: 'tp1', y: [10, 100], alfa: .55 }), anim: 'pan', dur: 80 },
            perto: { svg: cena.estrelas({ cor: '#f2ffa0', n: 18, seed: 'tp2' }), anim: 'pisca', dur: 2 },
        }, { r: 'raro' }),
        EA('Tempo Parado', 'De tempos em tempos um clarão inverte as cores da sua foto e um relógio para nas doze horas.', [
            { k: 'anel', cor: '#c8e63a', r: 68, esp: 2.6, dash: '10 6', giro: 40 },
            { k: 'faiscas', icone: 'relogio', pals: [TP], n: 5, tam: 9, raio: 40 },
        ], { r: 'raro', sobre: [{ k: 'raw', html: `<b class="inv"></b><svg viewBox="0 0 100 100" class="rl">${icone('relogio', { ...TP, m: '#ffffff' }).replace(/stroke-width='4'/g, "stroke-width='4'")}</svg>`,
            css: `.ef-sobre-$ID{mix-blend-mode:difference}.ef-sobre-$ID .inv{position:absolute;inset:0;background:#fff;opacity:0;animation:k-$ID-inv 6s linear ${fase(6, .25)} infinite}.ef-sobre-$ID .rl{width:54%;height:54%;left:23%;top:23%;opacity:0;transform:scale(.4);animation:k-$ID-rl 6s ease-out ${fase(6, .25)} infinite}`
                + `@keyframes k-$ID-inv{0%,16%{opacity:0}17%,30%{opacity:1}31%,100%{opacity:0}}@keyframes k-$ID-rl{0%,16%{opacity:0;transform:scale(.4)}20%{opacity:1;transform:scale(1.05)}24%,30%{opacity:1;transform:scale(1)}34%,100%{opacity:0;transform:scale(1.1)}}` }] }),
        EP('O Mundo Para', 'O cartão inteiro tem as cores invertidas por um instante, enquanto os algarismos de um relógio giram.', [
            { k: 'raw', html: `<i class="fl"></i><svg class="rm" viewBox="0 0 200 200">${romanos.replace(/<svg[^>]*>|<\/svg>/g, '')}</svg>`,
              css: `.ef-pf-$ID{mix-blend-mode:difference}.ef-pf-$ID .fl{position:absolute;inset:0;background:#fff;opacity:0;animation:k-$ID-fl 8s linear ${fase(8, .3)} infinite}.ef-pf-$ID .rm{position:absolute;left:50%;top:44%;width:92cqw;height:92cqw;margin:-46cqw 0 0 -46cqw;opacity:0;animation:k-$ID-rm 8s ease-out ${fase(8, .3)} infinite}`
                  + `@keyframes k-$ID-fl{0%,22%{opacity:0}23%,40%{opacity:1}41%,100%{opacity:0}}@keyframes k-$ID-rm{0%,22%{opacity:0;transform:scale(1.4) rotate(-30deg)}30%{opacity:.9;transform:scale(1) rotate(0)}40%{opacity:.9}46%,100%{opacity:0;transform:scale(.96)}}` },
        ], { r: 'epico' }),
    ],
});

// ---------------------------------------------------------------------------------------- VENTO DOURADO
const OU = { m: '#f2c230', a: '#fff0a0', d: '#3a5a1a', l: '#ffffff', o: '#6a4a08' };
const VD = { m: '#5ab83a', a: '#a8e88a', d: '#14400c', l: '#ecffe0', o: '#14400c' };
const ventoD = tema({
    id: 'vento_dourado', pre: 'vdo', nome: 'Vento Dourado', cat: 'anime', cor: '#f2c230', cores: ['#f2c230', '#5ab83a'], icone: 'fa-seedling',
    lema: 'Do ouro, a vida.',
    desc: 'Joaninhas e borboletas douradas, flores brotando onde tudo era pedra e um sol que transforma o que toca.',
    pal: OU,
    itens: [
        M('Joaninhas Douradas', 'Joaninhas, borboletas e folhas de ouro girando em volta da foto.', { t: 'icones', icones: ['joaninha', 'borboleta', 'folha'], pals: [{ ...OU, m: '#f2c230', d: '#3a2a08' }, OU, VD], n: 12, tam: 25, giro: 52, glow: '#ffe066' }, { r: 'raro' }),
        N('Ouro e Vida', 'Do dourado ao verde, como uma folha que nasce do ouro.', { grad: ['#d09a10', '#fff0a0', '#58b83a'], mov: 'desliza', dur: 6, contorno: '#3a2a08', cw: .8, fonte: 'redonda', peso: 900 }, { r: 'raro' }),
        Pl('Jardim de Ouro', 'Folhas e flores douradas brotando devagar sobre o verde.', { base: ['#2f6a2a', '#5aa83a'], pad: { tipo: 'icones', icones: ['folha', 'flor'], pals: [{ m: '#f2d860', a: '#f2d860', d: '#f2d860', l: '#fff0a0', o: '#f2d860', w: -2 }], tam: 30, ti: 17, c2: 'transparent', rot: 20 }, mov: 'x', dur: 18, brilho: 'rgba(255,240,160,.4)', icone: { nome: 'joaninha', pal: OU, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Sol de Ouro', 'Um sol dourado sobre colinas floridas e borboletas douradas voando.', {
            fundo: ['#ffe9a0', '#fff6d0'], fixo: `${cena.sol({ x: 80, y: 40, r: 26, c1: '#fff7c0', c2: '#ffc830' })}${cena.terreno({ cor: '#7ac85a', y: 76, amp: 8, n: 2 })}${cena.terreno({ cor: '#4aa83a', y: 92, amp: 6, n: 3, fase: 2 })}${cena.icones({ nomes: ['flor'], pals: [OU, { ...OU, m: '#ff9ec4' }], n: 12, tam: [8, 14], seed: 'vd1', y: [84, 106], rot: 6 })}`,
            longe: { svg: cena.nuvens({ cor: '#fff', n: 3, y: [10, 36], alfa: .9, seed: 'vd2' }), anim: 'pan', dur: 60 },
            perto: { svg: cena.icones({ nomes: ['borboleta'], pals: [OU], n: 5, tam: [12, 18], seed: 'vd3', y: [14, 80] }), anim: 'pan', dur: 26 },
        }, { r: 'raro' }),
        EA('Vida Brotando', 'Flores e folhas brotam e sobem pelos lados da foto, com um brilho dourado.', [
            { k: 'aura', cor: '#ffe066', dur: 3 },
            { k: 'sobe', icones: ['flor', 'folha', 'borboleta'], pals: [{ ...OU, m: '#ff9ec4' }, VD, OU], n: 9, tam: 11, alt: 170 },
        ], { r: 'raro' }),
        EP('Borboletas de Ouro', 'Borboletas douradas atravessam o cartão, folhas caem e a luz do sol respira.', [
            { k: 'clima', fundo: 'radial-gradient(ellipse at 20% 0%,rgba(255,224,102,.55),transparent 62%)', min: .4, max: 1, dur: 5 },
            { k: 'deriva', icones: ['borboleta'], pals: [OU], n: 7, tam: [16, 28], vel: [10, 18], bal: 40 },
            { k: 'cai', icones: ['folha'], pals: [VD], n: 8, tam: [10, 18], vel: [8, 13], bal: 60, alfa: .9 },
        ], { r: 'epico' }),
    ],
});

// ---------------------------------------------------------------------------------------- AREIA
const AR = { m: '#e0b878', a: '#f6dcaa', d: '#6a4a22', l: '#fff6e0', o: '#8a6030' };
const areia = tema({
    id: 'areia_bizarra', pre: 'are', nome: 'Tempestade de Areia', cat: 'anime', cor: '#e0b878', cores: ['#e0b878', '#8a6030'], icone: 'fa-wind',
    lema: 'A areia vai aonde você nem sabe.',
    desc: 'Tons de areia e ferrugem, patinhas na duna, grãos girando e uma tempestade que se forma do nada.',
    pal: AR,
    itens: [
        M('Patinhas na Areia', 'Patinhas e grãos de areia girando em volta da foto.', { t: 'icones', icones: ['pata', 'grao', 'grao'], pals: [AR, { m: '#f2cf8a', o: '#f2cf8a', w: 0 }, { m: '#caa060', o: '#caa060', w: 0 }], n: 14, tam: 22, giro: 56 }, { r: 'raro' }),
        N('Areia', 'Areia dourada com um contorno marrom, como uma duna ao entardecer.', { grad: ['#c89a50', '#fff0c0', '#c89a50'], mov: 'desliza', dur: 6.4, contorno: '#5a3a14', cw: 1, fonte: 'classica', peso: 900 }, { r: 'raro' }),
        Pl('Dunas', 'Ondas de areia que andam devagar, com uma patinha ao lado.', { base: ['#e6c488', '#caa060'], pad: { tipo: 'ondas', c1: 'rgba(138,96,48,.35)', c2: 'transparent', tam: 16 }, mov: 'x', dur: 14, texto: '#4a2a0a', icone: { nome: 'pata', pal: AR, lado: 'dir', tam: 62 } }, { r: 'raro' }),
        F('Tempestade', 'Dunas ao fundo e a areia voando no vento, num céu cor de ferrugem.', {
            fundo: ['#c8843a', '#e8b068', '#f6dcaa'], fixo: `${cena.terreno({ cor: '#b87a38', y: 82, amp: 8, n: 2 })}${cena.terreno({ cor: '#a06a2a', y: 96, amp: 6, n: 3, fase: 2 })}`,
            longe: { svg: `<g opacity='.45'>${cena.nuvens({ cor: '#fff0c0', n: 4, y: [18, 80], tam: [18, 30], seed: 'ar1' })}</g>`, anim: 'pan', dur: 18 },
            perto: { svg: cena.icones({ nomes: ['grao'], pals: [{ m: '#fff0c0', o: '#fff0c0', w: 0 }], n: 30, tam: [2, 5], seed: 'ar2', y: [4, 108], rot: 0 }), anim: 'pan', dur: 6 },
        }, { r: 'raro' }),
        EA('Grãos em Órbita', 'Uma nuvem de areia gira em volta da foto, com uma aura cor de duna.', [
            { k: 'aura', cor: '#e0b878', dur: 3.2 },
            { k: 'orbita', icones: ['grao'], pals: [{ m: '#f2cf8a', o: '#f2cf8a', w: 0 }], n: 22, tam: 7, giro: 12, raio: 76, tams: [1, .7, 1.3, .9] },
        ], { r: 'raro' }),
        EP('Redemoinho', 'A areia atravessa o cartão em rajadas, com névoa cor de duna e poeira dourada.', [
            { k: 'neblina', cor: '#e0b878', alfa: .5, n: 6, vel: 7 },
            { k: 'deriva', icones: ['grao'], pals: [{ m: '#f6dcaa', o: '#f6dcaa', w: 0 }], n: 30, tam: [3, 7], vel: [2.5, 5], y: [0, 100], bal: 30, alfa: .85 },
        ], { r: 'epico' }),
    ],
});

// ---------------------------------------------------------------------------------------- PLATINA (ORA ORA)
const PL = { m: '#9a8aff', a: '#cfc6ff', d: '#1a1060', l: '#ffffff', o: '#0a0640' };
const platina = tema({
    id: 'estrela_platina', pre: 'pla', nome: 'Rajada de Estrelas', cat: 'anime', cor: '#9a8aff', cores: ['#9a8aff', '#2a1a8a'], icone: 'fa-star',
    lema: 'Orá! Orá! Orá! Orá!',
    desc: 'Roxo e azul-platina: estrelas, raios e uma rajada de golpes tão rápida que só se vê o rastro.',
    pal: PL,
    itens: [
        M('Estrelas de Platina', 'Estrelas e raios de platina em volta da foto.', { t: 'icones', icones: ['estrela', 'raio'], pals: [PL, { ...PL, m: '#ffe066', a: '#fff0a8', d: '#7a4a00' }], n: 10, tam: 26, giro: 38 }, { r: 'raro' }),
        N('Platina', 'Prateado com azul-platina, contorno roxo e um brilho veloz.', { grad: ['#8a8aff', '#ffffff', '#8a8aff'], mov: 'desliza', dur: 2.2, contorno: '#0a0640', cw: 1.2, fonte: 'impacto', espaco: 1, peso: 900 }, { r: 'raro' }),
        Pl('Rajada', 'Riscos de velocidade sobre o roxo e uma estrela dourada ao lado.', { base: ['#2a1a8a', '#5a3ad8'], pad: { tipo: 'riscado', c1: 'rgba(255,255,255,.28)', c2: 'transparent', tam: 10, lw: 1.4 }, mov: 'x', dur: 3.2, brilho: 'rgba(255,255,255,.5)', borda: '#0a0640', icone: { nome: 'estrela', pal: { m: '#ffe066', a: '#fff0a8', d: '#7a4a00', l: '#fff', o: '#0a0640' }, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Noite de Estrelas', 'Um céu roxo cheio de estrelas, rastros de velocidade e as letras "オラ" passando.', {
            fundo: ['#12083a', '#2a1a8a', '#5a3ad8'], fixo: `${cena.estrelas({ cor: '#fff', n: 40, seed: 'pl1', r: [.6, 2] })}`,
            longe: { svg: `${kana('o', { ...PL, m: '#ffe066' }, 14, 30, 50, -6)}${kana('ra', { ...PL, m: '#fff' }, 70, 40, 50, 4)}${kana('o', { ...PL, m: '#ffe066' }, 130, 26, 50, -4)}${kana('ra', { ...PL, m: '#fff' }, 190, 38, 50, 5)}${kana('o', { ...PL, m: '#ffe066' }, 250, 30, 50, -5)}${kana('ra', { ...PL, m: '#fff' }, 304, 40, 44, 4)}`, anim: 'pan', dur: 6 },
            perto: { svg: cena.estrelas({ cor: '#fff', n: 14, seed: 'pl2', r: [1, 2.4] }), anim: 'pisca', dur: 1.6 },
        }, { r: 'raro' }),
        EA('Soco de Estrelas', 'Letras de golpe piscam depressa por cima da foto, com uma aura roxa e estrelas.', [
            { k: 'aura', cor: '#9a8aff', dur: 1.2 },
            { k: 'faiscas', icone: 'estrela', pals: [{ m: '#ffe066', a: '#fff0a8', d: '#7a4a00', l: '#fff', o: '#0a0640', w: 2 }], n: 7, tam: 9, raio: 39 },
        ], { r: 'raro', sobre: [{ k: 'raw', html: `<svg viewBox="0 0 100 100" class="gg">${kana('o', { ...PL, m: '#ffffff' }, 6, 30, 44, -6)}${kana('ra', { ...PL, m: '#ffe066' }, 48, 44, 46, 5)}</svg>`, css: '.ef-sobre-$ID .gg{opacity:0;animation:k-$ID-gg 1.4s steps(1,end) infinite}@keyframes k-$ID-gg{0%,40%{opacity:0}42%,52%{opacity:1;translate:1px -1px}54%{opacity:1;translate:-1px 1px}56%,100%{opacity:0}}' }] }),
        EP('Orá Orá Orá', 'Uma rajada de "オ" e "ラ" enche o cartão, com linhas de velocidade e um clarão.', [
            { k: 'raw', html: `<i class="ln"></i><svg class="g1" viewBox="0 0 300 100">${[0, 1, 2, 3].map((k) => kana(k % 2 ? 'ra' : 'o', { ...PL, m: k % 2 ? '#ffe066' : '#ffffff' }, k * 74, 4, 70, k % 2 ? 6 : -6)).join('')}</svg><svg class="g2" viewBox="0 0 300 100">${[0, 1, 2, 3].map((k) => kana(k % 2 ? 'o' : 'ra', { ...PL, m: k % 2 ? '#ffffff' : '#ffe066' }, k * 74, 4, 70, k % 2 ? -6 : 6)).join('')}</svg>`,
              css: `.ef-pf-$ID .ln{position:absolute;inset:-25%;background:repeating-conic-gradient(from 90deg at 50% 50%,rgba(255,255,255,.8) 0 1deg,transparent 1deg 7deg);-webkit-mask:radial-gradient(circle,transparent 16%,#000 60%);mask:radial-gradient(circle,transparent 16%,#000 60%);opacity:0;animation:k-$ID-ln 8s linear ${fase(8, .4)} infinite}.ef-pf-$ID .g1,.ef-pf-$ID .g2{position:absolute;left:2%;width:96%;opacity:0;animation:k-$ID-g 8s linear ${fase(8, .4)} infinite,k-$ID-tr .1s steps(2) infinite}.ef-pf-$ID .g1{top:12%}.ef-pf-$ID .g2{top:60%;animation-delay:${fase(8, .4)},0s}`
                  + `@keyframes k-$ID-ln{0%,24%{opacity:0}28%{opacity:1}56%{opacity:.8}64%,100%{opacity:0}}@keyframes k-$ID-g{0%,26%{opacity:0}30%{opacity:1}58%{opacity:1}66%,100%{opacity:0}}@keyframes k-$ID-tr{0%{translate:0 0}50%{translate:2px -1px}100%{translate:-2px 1.6px}}` },
        ], { r: 'epico' }),
    ],
});

// ---------------------------------------------------------------------------------------- HAMON
const HA = { m: '#ffd24a', a: '#fff0a8', d: '#7a4a00', l: '#ffffff', o: '#8a5a00' };
const hamon = tema({
    id: 'hamon', pre: 'ham', nome: 'Ondulação', cat: 'anime', cor: '#ffd24a', cores: ['#ffd24a', '#ff8a1f'], icone: 'fa-sun',
    lema: 'Respire. A luz percorre o corpo.',
    desc: 'Anéis de energia dourada que se espalham como ondas, e o brilho de um sol que nasce dentro de você.',
    pal: HA,
    itens: [
        M('Anéis de Ondulação', 'Um anel de ouro tracejado que gira e brilha em volta da foto.', { t: 'grad', cores: ['#ffd24a', '#ff8a1f'], tracejado: [8, 8], giro: 6, glow: '#ffd24a' }, { r: 'raro' }),
        N('Respiração', 'Ouro com um brilho que pulsa como uma respiração profunda.', { grad: ['#e8a010', '#fff0a8', '#e8a010'], mov: 'pulsa', brilho: '#ffd24a', bw: 3.2, contorno: '#5a3400', cw: .8, fonte: 'redonda', peso: 900, dur: 2.4 }, { r: 'raro' }),
        Pl('Ondas de Energia', 'Ondas douradas passando sobre o laranja, com um brilho solar.', { base: ['#e8780a', '#ffb02a'], pad: { tipo: 'ondas', c1: 'rgba(255,240,168,.45)', c2: 'transparent', tam: 14 }, mov: 'x', dur: 9, brilho: 'rgba(255,255,255,.5)', borda: '#7a4a00', icone: { nome: 'sol', pal: HA, lado: 'dir', tam: 66 }, texto: '#4a2a00' }, { r: 'raro' }),
        F('Sol Nascente', 'Um sol que nasce com anéis de energia se espalhando e raios dourados.', {
            fundo: ['#ff8a1f', '#ffc04a', '#fff0a8'], fixo: `${sunburst('#ffb02a', '#ffd24a', 28).replace(/<path /g, "<path opacity='.55' ")}${[24, 44, 64, 86].map((r, k) => `<circle cx='170' cy='120' r='${r}' fill='none' stroke='#fff6c8' stroke-width='${3 - k * .5}' opacity='${.9 - k * .15}'/>`).join('')}`,
            perto: { svg: cena.estrelas({ cor: '#fff', n: 22, seed: 'ha1', r: [.8, 2] }), anim: 'pisca', dur: 2.2 },
        }, { r: 'raro' }),
        EA('Ondulação', 'Anéis de luz dourada se espalham a partir da foto, um atrás do outro.', [
            { k: 'raw', html: '<b class="$C"></b><b class="$C b"></b><b class="$C c"></b>', css: `.ef-av-$ID .$C{border-radius:50%;border:2px solid rgba(255,224,102,.95);box-shadow:0 0 8px rgba(255,200,40,.8);inset:22%;opacity:0;animation:k-$ID-o 3.6s ease-out ${fase(3.6, .3)} infinite}.ef-av-$ID .$C.b{animation-delay:calc(${fase(3.6, .3)} + 1.2s)}.ef-av-$ID .$C.c{animation-delay:calc(${fase(3.6, .3)} + 2.4s)}@keyframes k-$ID-o{0%{opacity:.95;transform:scale(.7)}100%{opacity:0;transform:scale(1.55)}}` },
            { k: 'aura', cor: '#ffd24a', dur: 2.4 },
        ], { r: 'raro' }),
        EP('Energia do Sol', 'Ondas douradas sobem de baixo, faíscas sobem pelo cartão e a borda brilha.', [
            { k: 'clima', fundo: 'radial-gradient(ellipse at 50% 120%,rgba(255,176,42,.75),transparent 62%)', min: .4, max: 1, dur: 3.6 },
            { k: 'ondas', cor: '#ffd24a', alt: 16, dur: 6 },
            { k: 'sobe', icones: ['brilho'], pals: [{ m: '#fff6c8', o: '#ffb02a', w: 2 }], n: 12, tam: [8, 16], vel: [4, 8], alfa: .95 },
            { k: 'borda', cor: '#ffd24a', alfa: .45, dur: 2.8 },
        ], { r: 'epico' }),
    ],
});

// ---------------------------------------------------------------------------------------- DIAMANTE
const DI = { m: '#ff9ed0', a: '#ffd0ea', d: '#8a2a5a', l: '#ffffff', o: '#b04a82' };
const diamante = tema({
    id: 'diamante_bizarro', pre: 'dia', nome: 'Diamante Inquebrável', cat: 'anime', cor: '#ff9ed0', cores: ['#ff9ed0', '#7a5aff'], icone: 'fa-gem',
    lema: 'Quebrar, só pra voltar inteiro.',
    desc: 'Cristais rosados que se estilhaçam e voltam ao lugar: um tema de cidade tranquila ao entardecer, onde nada se perde de vez.',
    pal: DI,
    itens: [
        M('Cristais Rosados', 'Diamantes e cacos de cristal rosados em volta da foto.', { t: 'icones', icones: ['diamante', 'cristal_gelo'], pals: [DI, { ...DI, m: '#c4b0ff', o: '#6a52c8' }], n: 10, tam: 26, giro: 48, glow: '#ff9ed0' }, { r: 'raro' }),
        N('Inquebrável', 'Branco e rosa-cristal, com um contorno rosa-escuro e um brilho que corre.', { grad: ['#ff86c0', '#ffffff', '#ff86c0'], mov: 'desliza', dur: 3.6, contorno: '#8a2a5a', cw: 1, fonte: 'redonda', peso: 900 }, { r: 'raro' }),
        Pl('Cacos', 'Losangos de cristal que brilham sobre um rosa suave.', { base: ['#ffd0ea', '#ffe8f4'], pad: { tipo: 'losangos', c1: 'rgba(255,126,190,.3)', c2: 'transparent', tam: 16 }, mov: 'x', dur: 16, brilho: 'rgba(255,255,255,.7)', texto: '#6a1a44', icone: { nome: 'diamante', pal: DI, lado: 'dir', tam: 66 } }, { r: 'raro' }),
        F('Cidade ao Entardecer', 'Uma cidade tranquila num céu rosa e roxo, com cacos de cristal brilhando.', {
            fundo: ['#6a52c8', '#e87ac0', '#ffd0a8'], fixo: `${cena.skyline({ cor: '#3a2a6a', altMin: 20, altMax: 56, larg: [10, 22], seed: 'dm1', janelas: { cor: '#fff0a8', dens: .3 } })}`,
            longe: { svg: cena.nuvens({ cor: '#ffd0ea', n: 3, y: [14, 46], alfa: .7, seed: 'dm2' }), anim: 'pan', dur: 56 },
            perto: { svg: cena.icones({ nomes: ['diamante'], pals: [DI], n: 8, tam: [7, 13], seed: 'dm3', y: [6, 100] }), anim: 'pisca', dur: 2.6 },
        }, { r: 'raro' }),
        EA('Cacos Voltando', 'Cacos de cristal se afastam e voltam ao lugar em volta da foto, sem parar.', [
            { k: 'aura', cor: '#ff9ed0', dur: 2.8 },
            { k: 'orbita', icones: ['diamante', 'cristal_gelo'], pals: [DI], n: 8, tam: 22, giro: 28, pulso: 2.6 },
        ], { r: 'raro' }),
        EP('Reconstrução', 'Cacos de cristal sobem e pousam no cartão enquanto a luz rosada pulsa.', [
            { k: 'clima', fundo: 'radial-gradient(ellipse at 50% 100%,rgba(255,158,208,.55),transparent 62%)', min: .3, max: 1, dur: 4 },
            { k: 'sobe', icones: ['diamante', 'cristal_gelo'], pals: [DI, { ...DI, m: '#c4b0ff', o: '#6a52c8' }], n: 14, tam: [10, 20], vel: [7, 12], giro: 120, alfa: .95 },
            { k: 'pisca', icone: 'brilho', pals: [{ m: '#fff', o: '#ff9ed0', w: 2 }], n: 8, tam: [8, 13] },
        ], { r: 'epico' }),
    ],
});

module.exports = [bizarro, tempo, ventoD, areia, platina, hamon, diamante];
