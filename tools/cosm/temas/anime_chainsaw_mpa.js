'use strict';
/* CHAINSAW MAN: MAKIMA, POWER E AKI (Rodada 40, lendário). Só símbolos e objetos desenhados por código (tools/cosm/arte.js: olhos de anéis, chifres, katana...): o dono mandou tirar os personagens. */
const { tema, MP, EA, EP, P, R, B, IMG, apoio, fase } = require('../dsl');
const T = 'chainsaw';
const f1 = B.f1;

// ============================================================================================ MAKIMA
const RUB = '#b5352a', OUR = '#f2c230', PRE = '#16161e';
const coleira = (anim) => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.c{transform-origin:80px 134px;animation:s 3.4s ease-in-out infinite alternate}@keyframes s{from{transform:rotate(-6deg)}to{transform:rotate(6deg)}}</style>` : ''}`
    + `<path d='M54 126A52 52 0 0 0 106 126' fill='none' stroke='#0c0c12' stroke-width='6.5' stroke-linecap='round'/><path d='M55 124A51 51 0 0 0 105 124' fill='none' stroke='#4a4a5c' stroke-width='1.4' stroke-linecap='round' opacity='.8'/>`
    + `<circle cx='80' cy='134' r='5.2' fill='none' stroke='#14141c' stroke-width='4.6'/><circle cx='80' cy='134' r='5.2' fill='none' stroke='#cfd0dc' stroke-width='2.4'/>`
    + `<g class='c'>${[0, 1, 2, 3, 4].map((k) => `<ellipse cx='80' cy='${145 + k * 9}' rx='${k % 2 ? 2.4 : 4}' ry='5.4' fill='none' stroke='#14141c' stroke-width='3.6'/><ellipse cx='80' cy='${145 + k * 9}' rx='${k % 2 ? 2.4 : 4}' ry='5.4' fill='none' stroke='#cfd0dc' stroke-width='1.8'/>`).join('')}</g></svg>`;
const makima = tema({
    id: 'makima', pre: 'mak', nome: 'Makima', cat: 'anime', cor: OUR, cores: [RUB, OUR], icone: 'fa-bullseye', premium: true,
    lema: 'Eu sou a sua dona.',
    desc: 'A Diabo do Controle: a coleira com a corrente, olhos de anéis que te prendem, círculos dourados que se abrem e um contrato assinado em vermelho.',
    pal: { m: OUR, a: '#ffe27a', d: '#3a1008', l: '#fff', o: '#3a1008' },
    itens: [
        MP('Coleira e Corrente', 'Uma coleira preta com a corrente balançando, presa embaixo da foto.', { svg: coleira }, { r: 'lendario' }),
        EA('Olhos de Controle', 'Círculos dourados se abrem em volta da sua foto e os olhos de anéis surgem sobre você.', [
            { k: 'raw', html: '<b class="$C"><i class="rg r1"></i><i class="rg r2"></i><i class="rg r3"></i></b>',
              css: '.ef-av-$ID .rg{position:absolute;left:50%;top:50%;width:62%;aspect-ratio:1;margin:-31% 0 0 -31%;border-radius:50%;border:2.6px solid #f2c230;box-shadow:0 0 6px #c8802a;opacity:0;animation:k-$ID-rg 4.2s ease-out infinite}.ef-av-$ID .r2{animation-delay:-1.4s}.ef-av-$ID .r3{animation-delay:-2.8s}@keyframes k-$ID-rg{0%{opacity:.9;transform:scale(.7)}100%{opacity:0;transform:scale(1.7)}}' },
        ], { r: 'lendario', id: 'mak_olhos_de_controle',
            sobre: [IMG({ tema: T, img: 'makima_olhos', onde: 'sobre', n: 'ol', x: 50, y: 34, w: 86, ciclo: 9, ini: 34, fim: 64, de: { esc: .6 }, sai: { esc: 1.2 } })], css: '.ef-av-sobre.ef-sobre-$ID.kz{overflow:visible}' }),
        EP('Contrato', 'Círculos dourados se abrem sem parar no cartão como um olhar que prende, e a borda pulsa em vinho.', [
            { k: 'raw', html: '<i class="cg c1"></i><i class="cg c2"></i><i class="cg c3"></i><i class="cg c4"></i>',
              css: '.ef-pf-$ID .cg{position:absolute;left:50%;top:44%;width:30cqw;aspect-ratio:1;margin:-15cqw 0 0 -15cqw;border-radius:50%;border:3px solid #f2c230;box-shadow:0 0 10px #c8802a,inset 0 0 8px #c8802a;opacity:0;animation:k-$ID-cg 6s ease-out calc(var(--d) + ' + fase(6, .3) + ') infinite}.ef-pf-$ID .c1{--d:0s}.ef-pf-$ID .c2{--d:-1.5s}.ef-pf-$ID .c3{--d:-3s}.ef-pf-$ID .c4{--d:-4.5s}@keyframes k-$ID-cg{0%{opacity:.8;transform:scale(.3)}100%{opacity:0;transform:scale(4.2)}}' },
            { k: 'borda', cor: RUB, alfa: .5, blur: 38, esp: 5, dur: 3.2 },
        ], { r: 'lendario', id: 'mak_contrato' }),
        ...apoio({
            tema: T,
            nome: { nomeItem: 'Diabo do Controle', desc: 'Vermelho-cabelo e dourado de anéis, com contorno escuro.', grad: [RUB, OUR, RUB], mov: 'desliza', dur: 4.2, contorno: '#2a0a06', cw: 1.1, fonte: 'classica', espaco: 1 },
            placa: { nomeItem: 'Escritório', desc: 'Preto e vinho com riscas de contrato e os olhos de anéis do lado.', base: [PRE, '#3a1010'], pad: { tipo: 'horizontais', c1: 'rgba(181,53,42,.3)', c2: 'transparent', tam: 9 }, mov: 'y', dur: 14, borda: OUR, img: { nome: 'makima_olhos', lado: 'dir', tam: 76, y: 50 } },
            faixa: { nomeItem: 'Olhar de Cima', desc: 'Um fundo vinho com os olhos de anéis dourados olhando de lado.', fundo: ['#1a0606', '#5a1a1a', '#8a2a1a'],
                perto: { svg: P.cena.nuvens({ cor: '#f2c230', n: 3, y: [10, 80], tam: [10, 16], seed: 'mak1' }), anim: 'pisca', dur: 3 },
                css: `.banner-anim-$ID::before{content:'';position:absolute;right:4%;top:8%;height:74%;aspect-ratio:${f1(R.proporcao(T, 'makima_olhos') * 100) / 100};background:${R.css(T, 'makima_olhos')} center/contain no-repeat;pointer-events:none;animation:k-$ID-o 4s ease-in-out infinite alternate}@keyframes k-$ID-o{from{opacity:.55;transform:scale(.96)}to{opacity:1;transform:scale(1.04)}}` },
            fala: { nomeItem: 'Ordem', desc: 'Quando você fala na call, o card pisca em dourado e vinho, como uma ordem.', cores: [OUR, RUB], passos: true, dur: .6 },
            radar: { nomeItem: 'Círculos', desc: 'As ondas do radar viram anéis dourados duplos que se abrem.', cor: OUR, estilo: 'duplo', glow: RUB },
            chat: { nomeItem: 'Assinatura', desc: 'A barra de mensagem acende em dourado ao digitar e solta anéis ao enviar.', cor: OUR, cor2: RUB, particula: { forma: 'circulo' } },
            som: { nomeItem: 'Voz Calma', desc: 'Um acorde grave e calmo com um tilintar de corrente, ao entrar na call.', arquivo: 'makima.mp3', notas: [{ t: 0, f: 130, d: 1.3, tipo: 'sine', v: .4 }, { t: 0, f: 195, d: 1.3, tipo: 'sine', v: .25 }, { t: .5, f: 1760, f2: 1320, d: .3, tipo: 'triangle', v: .12 }], ruidos: [{ t: .45, d: .25, f: 5000, filtro: 'highpass', v: .25 }] },
            pin: { nomeItem: 'Olhos de Anéis', desc: 'Suas notas no mapa viram os olhos de anéis da Makima.', img: 'makima_olhos', bal: 0 },
            serv: { nomeItem: 'Servidor do Controle', desc: 'O ícone do servidor pisca em dourado e vinho.', cores: [OUR, RUB], passos: true, dur: 1 },
        }),
    ],
});

// ============================================================================================ POWER
const LAR = '#ff6a3a', SAN = '#c4141c', LOI = '#f2d8a0';
const power = tema({
    id: 'power', pre: 'pow', nome: 'Power', cat: 'anime', cor: SAN, cores: [SAN, LOI], icone: 'fa-droplet', premium: true,
    lema: 'Eu sou a grande Power!',
    desc: 'A Diabo do Sangue: os chifres, o sangue que escorre e a lua vermelha.',
    pal: { m: SAN, a: LAR, d: '#3a0408', l: '#fff', o: '#3a0408' },
    itens: [
        MP('Chifres', 'Os dois chifres vermelhos da Power no alto da foto, balançando de orgulho.', { imagem: { url: R.url(T, 'power_chifres'), ratio: R.proporcao(T, 'power_chifres'), x: 50, y: -2, w: 88, rot: 0, anim: 'balanca', dur: 2.2, bal: 2.5 } }, { r: 'lendario' }),
        EA('Sangue Vivo', 'O sangue escorre pela sua foto, que pulsa em vermelho.', [
            { k: 'aura', cor: '#c4141c', dur: 1.6 },
        ], { r: 'lendario', id: 'pow_sangue_vivo', sobre: [{ k: 'pingos', cor: '#b3001b', n: 7, dur: 6 }] }),
        EP('Lua de Sangue', 'Uma lua vermelha sobe no cartão e gotas de sangue caem, com a borda pulsando em vermelho.', [
            { k: 'raw', html: '<i class="lu"></i>',
              css: '.ef-pf-$ID .lu{position:absolute;left:50%;top:22%;width:46cqw;aspect-ratio:1;margin-left:-23cqw;border-radius:50%;background:radial-gradient(circle at 38% 36%,#ff8a7a,#c4141c 58%,#6a0a10);box-shadow:0 0 40px 12px rgba(196,20,28,.5);opacity:0;transform:translateY(40cqh);animation:k-$ID-lu 10s ease-out ' + fase(10, .35) + ' infinite}@keyframes k-$ID-lu{0%{opacity:0;transform:translateY(40cqh)}20%{opacity:.85}50%,80%{opacity:.85;transform:translateY(0)}100%{opacity:0;transform:translateY(-8cqh)}}' },
            { k: 'cai', icones: ['gota_sangue'], pals: [{ m: '#c4001a', a: '#ff3b4e', d: '#6a0010', l: '#ffb0b8', o: '#2a0008' }], n: 10, tam: [10, 18], vel: [6, 11] },
            { k: 'borda', cor: SAN, alfa: .55, blur: 40, esp: 5, dur: 2.4 },
        ], { r: 'lendario', id: 'pow_lua_de_sangue' }),
        ...apoio({
            tema: T,
            nome: { nomeItem: 'A Grande Power', desc: 'Vermelho de sangue e loiro com contorno escuro.', grad: [SAN, LAR, LOI, SAN], mov: 'desliza', dur: 3.2, contorno: '#3a0408', cw: 1.1, fonte: 'impacto' },
            placa: { nomeItem: 'Fome de Sangue', desc: 'Vermelho com gotas e os chifres da Power do lado.', base: [SAN, '#7a0a14'], pad: { tipo: 'bolinhas', c1: 'rgba(40,0,4,.35)', c2: 'transparent', tam: 9, r: .3 }, mov: 'x', dur: 9, borda: LOI, img: { nome: 'power_chifres', lado: 'dir', tam: 80, y: 50 } },
            faixa: { nomeItem: 'Noite do Demônio', desc: 'Um céu vermelho com uma lua enorme sobre a cidade.', fundo: ['#1a0408', '#5a0a14', '#c4141c'],
                fixo: P.cena.sol({ x: 80, y: 40, r: 30, c1: '#ffb0a0', c2: '#c4141c' }) + P.cena.skyline({ cor: '#14040a', altMin: 18, altMax: 50, larg: [10, 20], seed: 'pow1' }),
            },
            fala: { nomeItem: 'Grito', desc: 'Quando você fala na call, o card pisca em vermelho e laranja, como um grito.', cores: [SAN, LAR], passos: true, dur: .3 },
            radar: { nomeItem: 'Poça', desc: 'As ondas do radar viram anéis vermelhos grossos de sangue.', cor: SAN, estilo: 'liso', glow: LAR },
            chat: { nomeItem: 'Esguicho de Sangue', desc: 'A barra de mensagem acende em vermelho ao digitar e solta gotas ao enviar.', cor: SAN, cor2: LAR, particula: { icone: 'gota_sangue', pal: { m: '#c4001a', a: '#ff3b4e', d: '#6a0010', l: '#ffb0b8', o: '#2a0008' } } },
            som: { nomeItem: 'Risada da Power', desc: 'Uma risada aguda e debochada de quem se acha demais, ao entrar na call.', arquivo: 'power.mp3', notas: [{ t: 0, f: 700, f2: 1000, d: .12, tipo: 'sawtooth', v: .35 }, { t: .15, f: 760, f2: 1100, d: .12, tipo: 'sawtooth', v: .35 }, { t: .3, f: 820, f2: 1200, d: .12, tipo: 'sawtooth', v: .35 }, { t: .5, f: 900, f2: 500, d: .3, tipo: 'sawtooth', v: .3 }], ruidos: [] },
            pin: { nomeItem: 'Chifres', desc: 'Suas notas no mapa viram os chifres da Power.', img: 'power_chifres' },
            serv: { nomeItem: 'Servidor de Sangue', desc: 'O ícone do servidor pisca em vermelho e laranja.', cores: [SAN, LAR], passos: true, dur: .6 },
        }),
    ],
});

// ============================================================================================ AKI
const NAV = '#1c2a4a', VER = '#c4141c', FUM = '#cfd4de';
const cigarro = (anim) => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.f{stroke-dasharray:60;animation:v 3.2s ease-out infinite}.f2{animation-delay:-1.6s}.e{animation:b 1.2s ease-in-out infinite alternate}@keyframes v{0%{stroke-dashoffset:60;opacity:.8}100%{stroke-dashoffset:0;opacity:0}}@keyframes b{from{opacity:.6}to{opacity:1}}</style>` : ''}`
    + `<g transform='rotate(-30 28 126)'><rect x='26' y='122' width='40' height='6' rx='2.4' fill='#f4f4f8' stroke='#14141c' stroke-width='1.6'/><rect x='26' y='122' width='11' height='6' rx='2' fill='#e08a3a' stroke='#14141c' stroke-width='1.6'/><circle class='e' cx='68' cy='125' r='3.6' fill='#ff6a2a'/></g>`
    + `<path class='f' d='M64 106Q58 94 66 84Q74 74 66 62' fill='none' stroke='${FUM}' stroke-width='2.2' stroke-linecap='round'/><path class='f f2' d='M70 108Q78 96 70 86Q62 76 72 66' fill='none' stroke='${FUM}' stroke-width='1.8' stroke-linecap='round'/></svg>`;
const aki = tema({
    id: 'aki', pre: 'aki', nome: 'Aki Hayakawa', cat: 'anime', cor: VER, cores: [NAV, VER], icone: 'fa-fire-flame-simple', premium: true,
    lema: 'Vou matar o Diabo da Arma.',
    desc: 'O caçador de demônios de gravata: o cigarro e a fumaça, a katana que corta e o contrato vermelho.',
    pal: { m: VER, a: '#ff6a5a', d: '#0a0e1a', l: '#fff', o: '#0a0e1a' },
    itens: [
        MP('Cigarro', 'Um cigarro aceso preso embaixo da foto, soltando fumaça.', { svg: cigarro }, { r: 'lendario' }),
        EA('Corte de Katana', 'Uma katana entra pelo lado da foto e um corte vermelho passa por cima dela, de tempos em tempos.', [
            IMG({ tema: T, img: 'aki_katana_pin', onde: 'av', n: 'rp', x: 82, y: 44, w: 52, ciclo: 8, ini: 10, fim: 52, de: { x: 40, esc: .6, rot: 14 }, sai: { x: 30, esc: .7 }, rot: -8, brilho: '#c4141c', bw: 6 }),
            { k: 'aura', cor: '#c4141c', dur: 1.4 },
        ], { r: 'lendario', id: 'aki_corte_de_katana',
            sobre: [{ k: 'raw', html: '<b class="$C"><i class="cr"></i></b>',
              css: '.ef-sobre-$ID .cr{position:absolute;left:-20%;top:46%;width:140%;height:4%;background:linear-gradient(90deg,transparent,#fff 30%,#fff 70%,transparent);box-shadow:0 0 8px 2px #c4141c;transform:rotate(-34deg) scaleX(0);transform-origin:0 50%;opacity:0;animation:k-$ID-cr 8s ease-out ' + fase(8, .6) + ' infinite}@keyframes k-$ID-cr{0%,52%{opacity:0;transform:rotate(-34deg) scaleX(0)}56%{opacity:1;transform:rotate(-34deg) scaleX(1)}68%,100%{opacity:0;transform:rotate(-34deg) scaleX(1)}}' }],
            css: '.ef-av-sobre.ef-sobre-$ID.kz{overflow:visible}' }),
        EP('Pacto de Sangue', 'Fumaça vermelha sobe e cortes de katana cruzam o cartão, com a borda pulsando em vermelho.', [
            { k: 'raw', html: '<i class="ct k1"></i><i class="ct k2"></i><i class="ct k3"></i>',
              css: '.ef-pf-$ID .ct{position:absolute;left:-10%;width:120%;height:1.2cqw;background:linear-gradient(90deg,transparent,#fff,transparent);box-shadow:0 0 10px 2px #c4141c;opacity:0;transform-origin:0 50%;animation:k-$ID-ct 7s ease-out calc(var(--d) + ' + fase(7, .3) + ') infinite}.ef-pf-$ID .k1{top:30%;--d:0s;transform:rotate(-24deg)}.ef-pf-$ID .k2{top:56%;--d:-2.4s;transform:rotate(-30deg)}.ef-pf-$ID .k3{top:76%;--d:-4.8s;transform:rotate(-20deg)}@keyframes k-$ID-ct{0%,8%{opacity:0;clip-path:inset(0 100% 0 0)}12%{opacity:1;clip-path:inset(0 0 0 0)}30%,100%{opacity:0;clip-path:inset(0 0 0 0)}}' },
            { k: 'neblina', cor: '#c4141c', alfa: .4, n: 4 },
            { k: 'borda', cor: VER, alfa: .5, blur: 36, esp: 4, dur: 2.6 },
        ], { r: 'lendario', id: 'aki_pacto_de_sangue' }),
        ...apoio({
            tema: T,
            nome: { nomeItem: 'Caçador de Gravata', desc: 'Azul-marinho e vermelho com contorno claro, e a fumaça de um cigarro.', grad: ['#3a5a9a', VER, '#3a5a9a'], mov: 'desliza', dur: 4.6, contorno: '#e8eef6', cw: .7, fonte: 'classica', espaco: .8 },
            placa: { nomeItem: 'Segurança Pública', desc: 'Terno azul-marinho com listras finas e uma katana do lado.', base: [NAV, '#0a0e1a'], pad: { tipo: 'verticais', c1: 'rgba(196,20,28,.18)', c2: 'transparent', tam: 8 }, mov: 'x', dur: 16, borda: VER, img: { nome: 'aki_katana_pin', lado: 'dir', tam: 96, y: 50 } },
            faixa: { nomeItem: 'Katana na Noite', desc: 'Uma noite azul com a katana atravessando e fumaça subindo.', fundo: ['#0a0e1a', '#1c2a4a', '#3a1a2a'],
                perto: { svg: P.cena.nuvens({ cor: '#cfd4de', n: 4, y: [20, 90], tam: [10, 16], seed: 'aki1' }), anim: 'pan', dur: 40 },
                css: `.banner-anim-$ID::before{content:'';position:absolute;left:0;top:30%;width:90%;aspect-ratio:${f1(R.proporcao(T, 'aki_katana') * 100) / 100};background:${R.css(T, 'aki_katana')} center/contain no-repeat;pointer-events:none;transform:rotate(-12deg);animation:k-$ID-k 5s ease-in-out infinite alternate}@keyframes k-$ID-k{from{transform:rotate(-14deg) translateX(-6%)}to{transform:rotate(-10deg) translateX(6%)}}` },
            fala: { nomeItem: 'Contrato', desc: 'Quando você fala na call, o card pisca em vermelho e azul-marinho.', cores: [VER, NAV], passos: true, dur: .45 },
            radar: { nomeItem: 'Fumaça', desc: 'As ondas do radar viram anéis cinza pontilhados, como fumaça.', cor: FUM, estilo: 'pontilhado', glow: VER },
            chat: { nomeItem: 'Cinzas', desc: 'A barra de mensagem acende em vermelho ao digitar e solta cinzas ao enviar.', cor: VER, cor2: FUM, particula: { forma: 'circulo' } },
            som: { nomeItem: 'Katana e Isqueiro', desc: 'O estalo de um isqueiro e o corte de uma katana, ao entrar na call.', arquivo: 'aki.mp3', notas: [{ t: 0, f: 3000, f2: 2200, d: .05, tipo: 'square', v: .3 }, { t: .5, f: 2400, f2: 900, d: .3, tipo: 'sawtooth', v: .18 }], ruidos: [{ t: .03, d: .15, f: 4500, filtro: 'highpass', v: .3 }, { t: .5, d: .3, f: 1200, f2: 6000, filtro: 'bandpass', v: .4, q: 1.6 }] },
            pin: { nomeItem: 'Katana', desc: 'Suas notas no mapa viram uma katana.', img: 'aki_katana_pin' },
            serv: { nomeItem: 'Servidor do Contrato', desc: 'O ícone do servidor pisca em vermelho e azul-marinho.', cores: [VER, NAV], passos: true, dur: .8 },
        }),
    ],
});

module.exports = [makima, power, aki];
