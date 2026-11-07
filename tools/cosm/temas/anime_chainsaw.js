'use strict';
/* CHAINSAW MAN (Rodada 40, pedido do dono: arte FIEL à obra, lendário).
   Cada personagem é um tema com os 11 slots + efeito de servidor. Só SÍMBOLOS e OBJETOS da obra, tudo desenhado por código (motosserra, sangue, rabinho...): o dono mandou tirar os personagens. */
const { tema, M, MP, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, PAGINA, P, I, R, B, fase } = require('../dsl');
const { cena } = P;
const f1 = B.f1;
const T = 'chainsaw';

// ----------------------------------------------------------------------------------------------- peças em comum
/** mancha de sangue (quadro 100x100): miolo irregular, jatos assimétricos que terminam em gota e gotas soltas (nada de estrela regular) */
function splat(seed, cor = '#a80018', escuro = '#5c000d') {
    const r = B.rng(seed), n = 13, pts = [];
    for (let k = 0; k < n; k++) { const a = k / n * 2 * Math.PI, rr = 8 + r() * 6 + (k % 3 === 0 ? 3 : 0); pts.push([50 + rr * Math.cos(a), 50 + rr * Math.sin(a) * (.85 + r() * .25)]); }
    let d = '';
    for (let k = 0; k < n; k++) { const p = pts[k], q = pts[(k + 1) % n], mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2; d += k ? `Q${f1(p[0])} ${f1(p[1])} ${f1(mx)} ${f1(my)}` : `M${f1(mx)} ${f1(my)}`; }
    d += 'Z';
    const dir = r() * 2 * Math.PI;                    // o lado pra onde o sangue mais voa
    let jatos = '', gotas = '';
    const nj = 9 + Math.floor(r() * 4);
    for (let k = 0; k < nj; k++) {
        const a = dir + (r() - .5) * (k % 3 ? 4.6 : 1.8);           // a maioria espalhada, alguns apontando pro lado da direção
        const forte = Math.cos(a - dir) * .5 + .5;                     // 0..1: quanto aponta pro lado forte
        const len = 8 + Math.pow(r(), 1.6) * 24 + forte * 20, w = 1.6 + r() * 3.4 + (1 - len / 52) * 2;
        const bx = 50 + 8 * Math.cos(a), by = 50 + 8 * Math.sin(a), tx = 50 + (8 + len) * Math.cos(a), ty = 50 + (8 + len) * Math.sin(a);
        const nx = -Math.sin(a), ny = Math.cos(a), curva = (r() - .5) * 9;
        const mx = (bx + tx) / 2 + nx * curva, my = (by + ty) / 2 + ny * curva;
        jatos += `<path d='M${f1(bx + nx * w)} ${f1(by + ny * w)}Q${f1(mx + nx * w * .35)} ${f1(my + ny * w * .35)} ${f1(tx)} ${f1(ty)}Q${f1(mx - nx * w * .35)} ${f1(my - ny * w * .35)} ${f1(bx - nx * w)} ${f1(by - ny * w)}Z'/>`;
        if (len > 22) { gotas += `<circle cx='${f1(tx + Math.cos(a) * 2.2)}' cy='${f1(ty + Math.sin(a) * 2.2)}' r='${f1(1.5 + r() * 2)}'/>`; if (r() < .6) gotas += `<circle cx='${f1(tx + Math.cos(a) * 8)}' cy='${f1(ty + Math.sin(a) * 8)}' r='${f1(.9 + r() * 1.3)}'/>`; }
    }
    for (let k = 0; k < 10; k++) { const a = dir + (r() - .5) * 5, dd = 18 + r() * 30; gotas += `<circle cx='${f1(50 + dd * Math.cos(a))}' cy='${f1(50 + dd * Math.sin(a))}' r='${f1(.6 + r() * 1.5)}'/>`; }
    return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><g fill='${escuro}' transform='translate(.7 1)'><path d='${d}'/>${jatos}${gotas}</g><g fill='${cor}'><path d='${d}'/>${jatos}${gotas}</g><ellipse cx='47' cy='46' rx='4.2' ry='2.4' fill='#ff6070' opacity='.45' transform='rotate(-25 47 46)'/></svg>`;
}
const SANGUE = { m: '#c4001a', a: '#ff3b4e', d: '#6a0010', l: '#ffb0b8', o: '#2a0008' };
const LARANJA = '#ff7a1a', VERM = '#e5001f', PRETO = '#14080a';

// ----------------------------------------------------------------------------------------------- DENJI / POCHITA
/** o rabinho do Pochita (quadro 160, foto = círculo de raio 50 em 80,80): uma cordinha preta fininha que sai da borda embaixo à direita e termina num triângulo vazado; abana de tempos em tempos */
const rabinho = (anim) => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.t{transform-origin:100px 112px;animation:w 3.6s ease-in-out infinite}.v{opacity:0;animation:v 3.6s steps(1,end) infinite}@keyframes w{0%,44%,100%{transform:rotate(0)}4%{transform:rotate(17deg)}8%{transform:rotate(-15deg)}12%{transform:rotate(16deg)}16%{transform:rotate(-13deg)}20%{transform:rotate(14deg)}24%{transform:rotate(-11deg)}28%{transform:rotate(9deg)}32%{transform:rotate(-7deg)}36%{transform:rotate(4deg)}40%{transform:rotate(-2deg)}}@keyframes v{0%,3%,44%,100%{opacity:0}4%,40%{opacity:1}}</style>` : ''}`
    + `<g class='v' fill='none' stroke='#fff' stroke-width='1.8' stroke-linecap='round'><path d='M155 118Q159 126 157 136'/><path d='M150 112Q159 122 158 140'/></g>`
    + `<g class='t'><path d='M98 112C120 114 130 132 138 148' fill='none' stroke='#e4e6ee' stroke-width='5.6' stroke-linecap='round'/><path d='M98 112C120 114 130 132 138 148' fill='none' stroke='#14141c' stroke-width='3' stroke-linecap='round'/>`
    + `<path d='M137 150L158 150L148 130Z' fill='none' stroke='#e4e6ee' stroke-width='5.6' stroke-linejoin='round'/><path d='M137 150L158 150L148 130Z' fill='none' stroke='#14141c' stroke-width='3' stroke-linejoin='round'/></g></svg>`;

/** a motosserra saindo da foto: cabo atrás, lâmina na frente apontando pra quem olha */
const motoCabo = `<b class="$C"><svg viewBox="0 0 160 160" class="mc">`
    + `<g class="fu"><circle cx="58" cy="26" r="6"/><circle cx="52" cy="22" r="5"/><circle cx="64" cy="20" r="4"/></g>`
    + `<g class="cab"><path d="M34 64C21 46 27 22 50 16C63 13 74 17 80 23" fill="none" stroke="#08080c" stroke-width="13" stroke-linecap="round"/><path d="M34 63C23 47 28 25 49 19C61 16 71 19 77 24" fill="none" stroke="#6b4a94" stroke-width="2.4" stroke-linecap="round" opacity=".85" transform="translate(-1.5 -1.5)"/><rect x="73" y="17" width="14" height="14" rx="3" fill="#1a1a22" stroke="#3a3a48" stroke-width="1.4"/></g>`
    + `</svg></b>`;
const motoLamina = `<b class="$C"><svg viewBox="0 0 100 100" class="ml" overflow="visible"><defs><linearGradient id="st" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f4f8fd"/><stop offset=".45" stop-color="#aebbd0"/><stop offset="1" stop-color="#6b788f"/></linearGradient></defs>`
    + `<g class="lam"><g transform="translate(46 56) rotate(-38)"><path d="M2 -4L84 -15Q95 3 84 19L2 9Z" fill="rgba(0,0,0,.38)" transform="translate(3 6)"/><g class="vib">`
    + `<path d="M0 -6L80 -15Q91 0 80 15L0 6Z" fill="url(#st)" stroke="#16161e" stroke-width="1.3" stroke-linejoin="round"/><path d="M7 -2.4L71 -6.8Q79 0 71 6.8L7 2.4Z" fill="#505b70" stroke="#2a3140" stroke-width=".7"/>`
    + `<path class="ch1" d="M0 -6L80 -15Q91 0 80 15L0 6Z" fill="none" stroke="#12121a" stroke-width="4.6" stroke-dasharray="3.1 2.5" stroke-linejoin="round"/><path class="ch2" d="M0 -6L80 -15Q91 0 80 15L0 6Z" fill="none" stroke="#8795ad" stroke-width="1.3" stroke-dasharray="3.1 2.5" stroke-linejoin="round"/>`
    + `<path d="M-4 -8L2 -6L2 6L-4 8Z" fill="#14141c"/></g>`
    + `<g class="fa"><circle cx="88" cy="-6" r="1.7"/><circle cx="92" cy="6" r="1.4"/><circle cx="84" cy="14" r="1.6"/></g><g class="gt"><circle cx="90" cy="-2" r="1.8"/><circle cx="94" cy="9" r="1.4"/><circle cx="88" cy="16" r="1.2"/></g></g></g></svg></b>`;

const denji = tema({
    id: 'denji', pre: 'dnj', nome: 'Denji', cat: 'anime', cor: LARANJA, cores: [LARANJA, VERM], icone: 'fa-gears', premium: true,
    lema: 'Eu sou a motosserra.',
    desc: 'O cachorrinho Pochita e o caçador de demônios: o rabinho abanando, a motosserra rasgando a foto, sangue que espirra, voa, escorre e some.',
    pal: { m: VERM, a: LARANJA, d: PRETO, l: '#ffffff', o: PRETO },
    itens: [
        MP('Rabinho do Pochita', 'A cordinha preta do rabinho do Pochita, que termina num triângulo, saindo da borda da foto: abana forte de tempos em tempos e para.', { svg: rabinho }, { r: 'lendario' }),
        EA('Motosserra', 'A motosserra do Denji rasga a sua foto e sai na sua direção, com a corrente correndo e o cabo escondido atrás.', [
            { k: 'raw', html: motoCabo,
              css: `.ef-av-$ID .mc{position:absolute;inset:0;width:100%;height:100%;overflow:visible}`
                + `.ef-av-$ID .fu circle{fill:#8a8a96;opacity:0;animation:k-$ID-fu 1.5s ease-out infinite}.ef-av-$ID .fu circle:nth-child(2){animation-delay:-.5s}.ef-av-$ID .fu circle:nth-child(3){animation-delay:-1s}`
                + `.ef-av-$ID .cab{animation:k-$ID-cab .09s steps(2) infinite}`
                + `@keyframes k-$ID-fu{0%{transform:translate(0,0) scale(.5);opacity:0}15%{opacity:.7}100%{transform:translate(-14px,-22px) scale(1.7);opacity:0}}`
                + `@keyframes k-$ID-cab{from{transform:translate(0,0)}to{transform:translate(.7px,-.5px)}}` },
        ], { r: 'lendario', id: 'dnj_motosserra',
            sobre: [{ k: 'raw', html: motoLamina,
              css: `.ef-sobre-$ID .ml{overflow:visible}.ef-sobre-$ID .lam{transform-origin:46px 56px;animation:k-$ID-lam 10s cubic-bezier(.2,.9,.3,1) ${fase(10, .35)} infinite}`
                + `.ef-sobre-$ID .vib{animation:k-$ID-vib .08s steps(2) infinite}.ef-sobre-$ID .ch1,.ef-sobre-$ID .ch2{animation:k-$ID-ch .4s linear infinite}`
                + `.ef-sobre-$ID .fa circle{fill:#ffe9a0;opacity:0;animation:k-$ID-fa .35s steps(1,end) infinite}.ef-sobre-$ID .fa circle:nth-child(2){animation-delay:-.12s}.ef-sobre-$ID .fa circle:nth-child(3){animation-delay:-.24s}`
                + `.ef-sobre-$ID .gt circle{fill:#c4001a;opacity:0;animation:k-$ID-gt 1.1s ease-out infinite}.ef-sobre-$ID .gt circle:nth-child(2){animation-delay:-.37s}.ef-sobre-$ID .gt circle:nth-child(3){animation-delay:-.74s}`
                + `@keyframes k-$ID-lam{0%{transform:scale(.08);opacity:0}5%{transform:scale(1.12);opacity:1}8%{transform:scale(1)}66%{transform:scale(1);opacity:1}74%{transform:scale(.08);opacity:0}100%{transform:scale(.08);opacity:0}}`
                + `@keyframes k-$ID-vib{from{transform:translate(0,0)}to{transform:translate(.9px,.6px)}}@keyframes k-$ID-ch{to{stroke-dashoffset:-5.6}}`
                + `@keyframes k-$ID-fa{0%{opacity:1;transform:translate(0,0)}50%{opacity:.9;transform:translate(3px,-3px)}100%{opacity:0}}@keyframes k-$ID-gt{0%{opacity:0;transform:translate(0,0)}15%{opacity:1}100%{opacity:0;transform:translate(9px,7px)}}`
                + `@media (prefers-reduced-motion:reduce){.ef-sobre-$ID{display:none}}` }],
            css: `.ef-av-sobre.ef-sobre-$ID.kz{overflow:visible}` }),
        EP('Chuva de Sangue', 'Sangue espirra no cartão, voa em gotas, escorre pra baixo, mancha e vai sumindo, de tempos em tempos.', [
            { k: 'raw', html: [[6, 8, 56, 0], [52, 46, 50, 1.4], [10, 64, 44, 2.7]].map(([x, y, w, d], k) => `<i class="sp s${k}" style="left:${x}%;top:${y}%;width:${w}cqw;--d:${d}s"></i>`).join('')
                + [[22, 28], [40, 44], [66, 60], [82, 74], [30, 84]].map(([x, y], k) => `<i class="dr" style="left:${x}%;top:${y}%;--h:${14 + k * 4}cqh;--d:${k * .6 + .5}s"></i>`).join('')
                + Array.from({ length: 18 }, (_, k) => { const a = k * 2.4, d = 22 + (k % 5) * 9; return `<i class="dp" style="left:${[39, 85, 37][k % 3]}%;top:${[36, 77, 89][k % 3]}%;--x:${f1(d * Math.cos(a) * .9)}cqw;--y:${f1(d * Math.sin(a) * .9)}cqh;--s:${1.4 + (k % 4) * .7}cqw;--d:${[0, 1.4, 2.7][k % 3] + (k % 4) * .06}s"></i>`; }).join(''),
              css: [0, 1, 2].map((k) => `.ef-pf-$ID .s${k}{background-image:${B.uri(splat('dnj' + k))}}`).join('') + `.ef-pf-$ID .sp{position:absolute;aspect-ratio:1;background-position:center;background-size:100% 100%;background-repeat:no-repeat;transform:scale(.1);opacity:0;animation:k-$ID-sp 9s cubic-bezier(.15,.9,.3,1) calc(var(--d) + ${fase(9, .22)}) infinite}`
                + `.ef-pf-$ID .dr{position:absolute;width:1.7cqw;height:var(--h);margin-left:-.85cqw;border-radius:0 0 1cqw 1cqw;background:linear-gradient(#b3001b,#8a0014);transform-origin:50% 0;transform:scaleY(0);opacity:0;animation:k-$ID-dr 9s ease-in calc(var(--d) + ${fase(9, .22)}) infinite}`
                + `.ef-pf-$ID .dp{position:absolute;width:var(--s);aspect-ratio:1;margin:calc(var(--s)/-2) 0 0 calc(var(--s)/-2);border-radius:50%;background:#c4001a;opacity:0;animation:k-$ID-dp 9s cubic-bezier(.2,.6,.4,1) calc(var(--d) + ${fase(9, .22)}) infinite}`
                + `@keyframes k-$ID-sp{0%{transform:scale(.1);opacity:0}3%{transform:scale(1.14);opacity:1}6%{transform:scale(1)}58%{transform:scale(1);opacity:1}76%{transform:scale(1) translateY(2%);opacity:0}100%{opacity:0}}`
                + `@keyframes k-$ID-dr{0%,8%{transform:scaleY(0);opacity:0}10%{opacity:1}44%{transform:scaleY(1);opacity:1}60%{transform:scaleY(1);opacity:1}76%,100%{transform:scaleY(1);opacity:0}}`
                + `@keyframes k-$ID-dp{0%{transform:translate(0,0) scale(.6);opacity:0}2%{opacity:1}12%{transform:translate(var(--x),var(--y)) scale(1);opacity:1}28%{transform:translate(calc(var(--x)*1.1),calc(var(--y) + 46cqh)) scale(.8);opacity:0}100%{opacity:0}}` },
            { k: 'borda', cor: '#c4001a', alfa: .55, blur: 46, esp: 5, dur: 4.5 },
        ], { r: 'lendario', id: 'dnj_chuva_de_sangue' }),
        N('Homem-Motosserra', 'Laranja e vermelho de sangue com contorno preto, e uma motosserrinha ao lado do nome.', { grad: [LARANJA, VERM, LARANJA], mov: 'desliza', dur: 3.2, contorno: PRETO, cw: 1.2, fonte: 'impacto', espaco: .8, peso: 900 }, { r: 'lendario', css: `.ne-$ID::after{content:'';display:inline-block;width:2.2em;height:.95em;margin-left:.3em;vertical-align:-.15em;background:${R.css(T, 'motosserra')} center/contain no-repeat;-webkit-text-stroke:0}` }),
        Pl('Corrente', 'Laranja de sangue com dentes de corrente correndo e uma motosserra do lado.', { base: ['#ff7a1a', '#c4001a'], pad: { tipo: 'zigzag', c1: 'rgba(20,8,10,.38)', c2: 'transparent', tam: 12 }, mov: 'x', dur: 2.4, borda: '#14080a', img: { url: R.url(T, 'motosserra'), lado: 'dir', tam: 64, y: 50, barOculta: true } }, { r: 'lendario' }),
        F('Cidade do Diabo', 'Uma cidade vermelha sob a chuva de cinzas, com a corrente correndo na base.', {
            fundo: ['#1a0508', '#6b0e1c', '#e5381e'],
            fixo: `${cena.sol({ x: 74, y: 70, r: 26, c1: '#ffd9a0', c2: '#ff5a1a' })}${cena.skyline({ cor: '#14080a', altMin: 22, altMax: 66, larg: [9, 20], seed: 'dnj1', janelas: { cor: '#ff9a3a', dens: .22 } })}`,
            longe: { svg: `<g fill='none' stroke='#0c0608' stroke-width='5'>${Array.from({ length: 11 }, (_, k) => `<ellipse cx='${15 + k * 30.9}' cy='101' rx='12' ry='5.6'/>`).join('')}</g><g fill='none' stroke='#9aa6bc' stroke-width='1.2' opacity='.8'>${Array.from({ length: 11 }, (_, k) => `<ellipse cx='${15 + k * 30.9}' cy='101' rx='12' ry='5.6'/>`).join('')}</g>`, anim: 'pan', dur: 6 },
        }, { r: 'lendario' }),
        FALA('Motor Ligado', 'Quando você fala na call, o card treme em laranja e vermelho, como a motosserra no talo.', { cores: [LARANJA, VERM], passos: true, dur: .28 }, { r: 'lendario' }),
        RADAR('Corrente', 'As ondas do radar viram uma corrente de motosserra correndo em laranja.', { cor: LARANJA, estilo: 'tracejado', glow: VERM }, { r: 'lendario' }),
        CHAT('Esguicho', 'A barra de mensagem acende em vermelho ao digitar e esguicha sangue ao enviar.', { cor: VERM, cor2: LARANJA, particula: { icone: 'gota_sangue', pal: SANGUE } }, { r: 'lendario' }),
        SOM('Motosserra Ligando', 'O cordão puxado, o motor engasgando e a motosserra pegando no talo, ao entrar na call.', {
            arquivo: 'denji_motosserra.mp3',
            notas: [{ t: 0, f: 38, f2: 52, d: .35, tipo: 'sawtooth', v: .45 }, { t: .4, f: 44, f2: 60, d: .3, tipo: 'sawtooth', v: .5 }, { t: .8, f: 60, f2: 120, d: .45, tipo: 'sawtooth', v: .6 }, { t: 1.25, f: 120, f2: 205, d: .5, tipo: 'sawtooth', v: .65 }, { t: 1.75, f: 205, f2: 150, d: .5, tipo: 'sawtooth', v: .55 }],
            ruidos: [{ t: 0, d: .3, f: 2400, f2: 600, filtro: 'bandpass', v: .45, q: 1.4 }, { t: .8, d: 1.3, f: 1200, f2: 3600, filtro: 'bandpass', v: .45, q: .9 }],
        }, { r: 'lendario' }),
        PIN('Motosserra', 'Suas notas no mapa viram uma motosserra, balançando.', { img: R.url(T, 'motosserra_pin'), bal: 2 }, { r: 'lendario' }),
        SERV('Servidor Motosserra', 'O ícone do servidor pisca em laranja e vermelho, no ritmo do motor.', { cores: [LARANJA, VERM], passos: true, dur: .5 }, { r: 'lendario' }),
        PAGINA('Motosserra Ligada', 'Clique várias vezes seguidas e a motosserra pega no talo, com o barulho. Aí é só passar o mouse: ela corta a página, o sangue jorra e vai sumindo. Parou de mexer, ela desliga.', { preset: 'serra', cor: VERM, cliques: 6 }, { r: 'lendario' }),
    ],
});

module.exports = [denji];
