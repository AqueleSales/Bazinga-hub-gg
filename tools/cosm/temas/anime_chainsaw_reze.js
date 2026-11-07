'use strict';
/* REZE (Chainsaw Man, Rodada 40): a garota da bomba. Só objetos desenhados por código (pino de granada, granada, gérbera, fogos): o dono mandou tirar os personagens. */
const { tema, MP, EA, EP, P, R, B, IMG, apoio, fase } = require('../dsl');
const f1 = B.f1;
const T = 'chainsaw';
const ORG = '#ff7a2a', OURO = '#ffd04a', ROXO = '#3a1458', ROSA = '#ff4d6a';

/** o colar com o pino de granada pendurado no canto de baixo à esquerda; balança de leve (quadro 160, foto = círculo de raio 50) */
const pinoGranada = (anim) => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.p{transform-origin:44px 114px;animation:b 3.2s ease-in-out infinite}@keyframes b{0%,100%{transform:rotate(7deg)}50%{transform:rotate(-9deg)}}</style>` : ''}`
    + `<defs><linearGradient id='m' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#f4f6fa'/><stop offset='.5' stop-color='#a7b0c0'/><stop offset='1' stop-color='#5e6678'/></linearGradient></defs>`
    + `<path d='M28 96A52 52 0 0 0 64 130' fill='none' stroke='#0c0c12' stroke-width='6.5' stroke-linecap='round'/><path d='M29 94A52 52 0 0 0 62 128' fill='none' stroke='#3b3b4c' stroke-width='1.6' stroke-linecap='round' opacity='.8'/>`
    + `<g class='p'><path d='M44 112L40 124' stroke='#7a8296' stroke-width='2.6' stroke-linecap='round'/><circle cx='38' cy='134' r='10.5' fill='none' stroke='#14141c' stroke-width='5.6'/><circle cx='38' cy='134' r='10.5' fill='none' stroke='url(#m)' stroke-width='3.6'/>`
    + `<path d='M44 128L56 122' stroke='#14141c' stroke-width='4' stroke-linecap='round'/><path d='M44 128L56 122' stroke='url(#m)' stroke-width='2.2' stroke-linecap='round'/></g></svg>`;
const pinoSolto = `<svg viewBox='0 0 40 40'><circle cx='15' cy='24' r='8.5' fill='none' stroke='#14141c' stroke-width='5'/><circle cx='15' cy='24' r='8.5' fill='none' stroke='#cfd5e2' stroke-width='3'/><path d='M22 21L34 15' stroke='#14141c' stroke-width='4' stroke-linecap='round'/><path d='M22 21L34 15' stroke='#cfd5e2' stroke-width='2' stroke-linecap='round'/></svg>`;
const fogosBurst = (cor, n = 14) => {
    let d = '';
    for (let k = 0; k < n; k++) { const a = k / n * 2 * Math.PI, r0 = 6, r1 = 30 + (k % 3) * 6; d += `<path d='M${f1(50 + r0 * Math.cos(a))} ${f1(50 + r0 * Math.sin(a))}L${f1(50 + r1 * Math.cos(a))} ${f1(50 + r1 * Math.sin(a))}' stroke='${cor}' stroke-width='2.6' stroke-linecap='round'/><circle cx='${f1(50 + (r1 + 5) * Math.cos(a))}' cy='${f1(50 + (r1 + 5) * Math.sin(a))}' r='2' fill='${cor}'/>`; }
    return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>${d}<circle cx='50' cy='50' r='4' fill='#fff'/></svg>`;
};
const MARG = { m: '#ffffff', a: '#ffe08a', d: '#f5c542', l: '#ffffff', o: '#3a1a28' };

const fumaca = '<b class="$C"><i class="fu f1"></i><i class="fu f2"></i><i class="fu f3"></i><i class="fu f4"></i></b>';
const fumacaCss = `.ef-av-$ID .fu{position:absolute;width:34%;aspect-ratio:1;border-radius:50%;background:radial-gradient(circle,#6a6a74,#2c2c34);opacity:0;animation:k-$ID-fu 12s ease-out calc(var(--d,0s) + ${fase(12, .42)}) infinite}.ef-av-$ID .f1{left:33%;top:33%;--d:0s}.ef-av-$ID .f2{left:10%;top:18%;--d:.15s}.ef-av-$ID .f3{left:56%;top:14%;--d:.3s}.ef-av-$ID .f4{left:50%;top:56%;--d:.1s}`
    + '@keyframes k-$ID-fu{0%,23%{opacity:0;transform:scale(.2)}27%{opacity:.85;transform:scale(1)}48%{opacity:.5;transform:scale(1.5) translateY(-10%)}60%,100%{opacity:0;transform:scale(1.8) translateY(-22%)}}';

const boom = `<b class="$C"><i class="pn">${pinoSolto}</i><i class="fl"></i><i class="an"></i><i class="sp s1"></i><i class="sp s2"></i><i class="sp s3"></i><i class="sp s4"></i><i class="sp s5"></i><i class="sp s6"></i></b>`;
const boomCss = `.ef-sobre-$ID .pn{position:absolute;left:6%;top:-2%;width:30%;height:30%;opacity:0;animation:k-$ID-pn 12s cubic-bezier(.5,0,.9,.6) ${fase(12, .42)} infinite}.ef-sobre-$ID .pn svg{width:100%;height:100%;display:block}`
    + `.ef-sobre-$ID .fl{position:absolute;inset:0;background:radial-gradient(circle,#fff 0,#ffe08a 35%,rgba(255,140,40,.7) 62%,transparent 80%);opacity:0;animation:k-$ID-fl 12s ease-out ${fase(12, .42)} infinite}`
    + `.ef-sobre-$ID .an{position:absolute;left:50%;top:50%;width:100%;aspect-ratio:1;margin:-50% 0 0 -50%;border-radius:50%;border:5px solid #ffb13a;box-shadow:0 0 12px 3px rgba(255,120,30,.8),inset 0 0 12px 2px rgba(255,200,80,.6);opacity:0;animation:k-$ID-an 12s ease-out ${fase(12, .42)} infinite}`
    + `.ef-sobre-$ID .sp{position:absolute;left:50%;top:50%;width:7%;aspect-ratio:1;margin:-3.5% 0 0 -3.5%;border-radius:50%;background:#ffd04a;box-shadow:0 0 6px #ff7a2a;opacity:0;animation:k-$ID-sp 12s ease-out ${fase(12, .42)} infinite}`
    + [['s1', 80, -60], ['s2', 100, 10], ['s3', 70, 80], ['s4', -80, 70], ['s5', -100, -10], ['s6', -60, -70]].map(([c, x, y]) => `.ef-sobre-$ID .${c}{--x:${x}%;--y:${y}%}`).join('')
    + '@keyframes k-$ID-pn{0%{opacity:0;transform:translateY(0) rotate(0)}2%{opacity:1}18%{opacity:1;transform:translateY(150%) rotate(220deg)}22%,100%{opacity:0;transform:translateY(190%) rotate(260deg)}}'
    + '@keyframes k-$ID-fl{0%,22%{opacity:0}24%{opacity:1}30%{opacity:.35}38%,100%{opacity:0}}@keyframes k-$ID-an{0%,23%{opacity:0;transform:scale(.15)}26%{opacity:1}46%,100%{opacity:0;transform:scale(1.9)}}'
    + '@keyframes k-$ID-sp{0%,23%{opacity:0;transform:translate(0,0)}25%{opacity:1}44%,100%{opacity:0;transform:translate(var(--x),var(--y))}}';

const fogos = [[22, 26, 0, ORG], [74, 20, 2.6, OURO], [50, 58, 5.2, ROSA], [20, 78, 7.4, OURO], [80, 74, 3.9, ORG]];

const reze = tema({
    id: 'reze', pre: 'rez', nome: 'Reze', cat: 'anime', cor: ORG, cores: [ORG, ROXO], icone: 'fa-bomb', premium: true,
    lema: 'Boom.',
    desc: 'A garota da bomba: o pino da granada no pescoço, a explosão que vira o demônio, fogos de artifício e uma margarida.',
    pal: { m: ORG, a: OURO, d: '#1a0a12', l: '#ffffff', o: '#1a0a12' },
    itens: [
        MP('Pino da Granada', 'O pino de granada pendurado num colar preto na borda da foto, balançando.', { svg: pinoGranada }, { r: 'lendario' }),
        EA('Detonação', 'O pino cai e a foto explode numa bola de fogo, com fumaça e faíscas, de tempos em tempos.', [
            { k: 'raw', html: fumaca, css: fumacaCss },
        ], { r: 'lendario', id: 'rez_detonacao', sobre: [{ k: 'raw', html: boom, css: boomCss + '@media (prefers-reduced-motion:reduce){.ef-sobre-$ID{display:none}}' }], css: '.ef-av-sobre.ef-sobre-$ID.kz{overflow:visible}' }),
        EP('Festival de Fogos', 'Fogos de artifício estouram no cartão, margaridas caem e a borda pisca em laranja, como na noite do festival.', [
            { k: 'raw', html: fogos.map(([x, y, d], k) => `<i class="fw f${k}" style="left:${x}%;top:${y}%;--d:${d}s"></i>`).join(''),
              css: fogos.map(([x, y, d, c], k) => `.ef-pf-$ID .f${k}{background-image:${B.uri(fogosBurst(c, 14 + k))}}`).join('')
                + `.ef-pf-$ID .fw{position:absolute;width:44cqw;aspect-ratio:1;margin:-22cqw 0 0 -22cqw;background-size:100% 100%;opacity:0;transform:scale(.1);animation:k-$ID-fw 8.5s cubic-bezier(.1,.8,.3,1) calc(var(--d) + ${fase(8.5, .12)}) infinite}`
                + '@keyframes k-$ID-fw{0%{opacity:0;transform:scale(.1)}3%{opacity:1}14%{opacity:1;transform:scale(1)}30%{opacity:0;transform:scale(1.14) translateY(4%)}100%{opacity:0}}' },
            { k: 'cai', icones: ['flor'], pals: [MARG], n: 9, tam: [14, 22], vel: [7, 13], alfa: .95 },
            { k: 'borda', cor: ORG, alfa: .5, blur: 40, esp: 5, dur: 2.4 },
        ], { r: 'lendario', id: 'rez_festival_de_fogos' }),
        ...apoio({
            tema: T,
            nome: { nomeItem: 'Garota da Bomba', desc: 'Branco, laranja e vermelho de explosão, com contorno escuro e uma margarida ao lado do nome.', grad: ['#ffffff', ORG, '#ff3b4e', '#ffffff'], mov: 'pulsa', brilho: ORG, contorno: '#1a0a12', cw: 1, fonte: 'classica', espaco: .6, icone: { nome: 'flor', pos: 'depois', pal: MARG } },
            placa: { nomeItem: 'Noite de Festival', desc: 'Roxo-noite com faíscas laranja e uma gérbera do lado.', base: ['#150a22', '#3a1458'], pad: { tipo: 'bolinhas', c1: 'rgba(255,140,60,.3)', c2: 'transparent', tam: 10, r: .3 }, mov: 'x', dur: 7, borda: 'rgba(255,122,42,.7)', img: { nome: 'reze_flor', lado: 'dir', tam: 120, y: 50 } },
            faixa: { nomeItem: 'Margarida e Fogos', desc: 'A gérbera vermelha da Reze sob fogos de artifício numa noite roxa.', fundo: ['#08040f', '#2a1040', '#7a2a2a'],
                perto: { svg: P.cena.icones({ nomes: ['fogos'], pals: [{ m: ORG, a: OURO, d: '#1a0a12', l: '#fff', o: '#1a0a12' }], n: 5, tam: [14, 22], seed: 'rez1', y: [8, 80] }), anim: 'pisca', dur: 2.2 },
                css: `.banner-anim-$ID::before{content:'';position:absolute;inset:0;background:${R.css(T, 'reze_flor')} 96% 52%/auto 118% no-repeat;-webkit-mask-image:linear-gradient(90deg,transparent 35%,#000 80%);mask-image:linear-gradient(90deg,transparent 35%,#000 80%);pointer-events:none}` },
            fala: { nomeItem: 'Contagem', desc: 'Quando você fala na call, o card pisca em laranja e dourado, como um estouro.', cores: [ORG, OURO], passos: true, dur: .3 },
            radar: { nomeItem: 'Onda de Choque', desc: 'As ondas do radar viram anéis duplos de laranja, como uma onda de explosão.', cor: ORG, estilo: 'duplo', glow: OURO },
            chat: { nomeItem: 'Margarida', desc: 'A barra de mensagem acende em laranja ao digitar e solta margaridas ao enviar.', cor: ORG, cor2: OURO, particula: { icone: 'flor', pal: MARG } },
            som: { nomeItem: 'Explosão', desc: 'O pino saindo e uma explosão grave que ecoa, ao entrar na call.', arquivo: 'reze_explosao.mp3', notas: [{ t: 0, f: 2400, f2: 1800, d: .08, tipo: 'triangle', v: .4 }, { t: .35, f: 150, f2: 28, d: .9, tipo: 'sine', v: .95 }, { t: .35, f: 70, f2: 24, d: 1, tipo: 'sawtooth', v: .5 }], ruidos: [{ t: .35, d: 1, f: 3200, f2: 180, filtro: 'lowpass', v: .85, q: .6 }, { t: .38, d: .5, f: 6000, filtro: 'highpass', v: .3 }] },
            pin: { nomeItem: 'Granada', desc: 'Suas notas no mapa viram uma granada, balançando.', img: 'granada' },
            serv: { nomeItem: 'Servidor Explosivo', desc: 'O ícone do servidor pisca em laranja e dourado como um estouro de fogos.', cores: [ORG, OURO], passos: true, dur: .6 },
        }),
    ],
});

module.exports = [reze];
