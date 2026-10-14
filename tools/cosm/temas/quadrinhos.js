'use strict';
/* QUADRINHOS: aqui mora o estilo de HQ de herói com meio-tom (Ben-Day), onomatopeias, painéis e a barra de Ultimate.
   Os heróis de verdade (aranha, morcego, escudo...) entram em outros temas. Arte original. */
const { tema, M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P, I, fase } = require('../dsl');
const { cena } = P;
const { pontos } = I;
const f1 = (n) => Math.round(n * 10) / 10;

const AM = { m: '#ffd23f', a: '#fff0a0', d: '#1a1a1a', l: '#ffffff', o: '#000000' };
const VM = { m: '#e23636', a: '#ff7a7a', d: '#3a0a0a', l: '#ffffff', o: '#000000' };
const AZ = { m: '#1e5eff', a: '#7a9eff', d: '#0a1a4a', l: '#ffffff', o: '#000000' };

const raiosHQ = (c1, c2, n = 24) => { let s = ''; for (let k = 0; k < n; k++) { const a0 = k * 360 / n, a1 = a0 + 180 / n, p = (a, r) => `${f1(250 + r * Math.cos(a * Math.PI / 180))} ${f1(56 + r * Math.sin(a * Math.PI / 180))}`; s += `<path d='M250 56L${p(a0, 300)}L${p(a1, 300)}Z' fill='${k % 2 ? c1 : c2}'/>`; } return s; };
const pontosBenDay = (cor, alfa = .35) => { let s = ''; for (let y = 5; y < 112; y += 9) for (let x = (y / 9) % 2 ? 4 : 0; x < 340; x += 9) s += `<circle cx='${x}' cy='${y}' r='2.6' fill='${cor}' opacity='${alfa}'/>`; return s; };
const explosao = `<path d='${pontos(14, 90, 56, 52, 30, -90)}' fill='#ffd23f' stroke='#000' stroke-width='3.4' stroke-linejoin='round'/><path d='${pontos(14, 90, 56, 38, 22, -83)}' fill='#fff6c0'/><text x='90' y='66' text-anchor='middle' font-family='Impact,Arial Black,sans-serif' font-size='32' fill='#e23636' stroke='#000' stroke-width='2.2' paint-order='stroke' transform='rotate(-8 90 56)'>POW!</text>`;

const hq = tema({
    id: 'hq', pre: 'hq', nome: 'Gibi de Herói', cat: 'quadrinhos', cor: '#e23636', cores: ['#e23636', '#1e5eff'], icone: 'fa-bolt', premium: true,
    lema: 'POW! BAM! KRAK!',
    desc: 'Meio-tom de gibi, onomatopeias, painéis entrando em sequência e uma barra de Ultimate que enche e explode: o herói de quadrinhos.',
    pal: AM,
    itens: [
        M('Explosão de HQ', 'A moldura é um balão de explosão de gibi: amarelo, com contorno preto grosso.', { t: 'forma', forma: 'dentes', n: 20, amp: 8, esp: 13, cor: '#ffd23f', cor2: '#ff8a1f', linha: '#000', lw: 3, giro: 90 }, { r: 'epico' }),
        N('Impacto', 'Amarelo de gibi com contorno preto e uma sombra vermelha deslocada.', { cor: '#ffd23f', contorno: '#000', cw: 1.4, fonte: 'quadrinho', sombra: [2, 2, '#e23636'], peso: 900, espaco: .6 }, { r: 'epico' }),
        Pl('Meio-tom', 'Pontinhos de impressão de gibi sobre o amarelo, e um balão de fala ao lado.', { base: ['#ffd23f', '#ffb02a'], pad: { tipo: 'bolinhas', c1: 'rgba(226,54,54,.5)', c2: 'transparent', tam: 8, r: .34 }, mov: 'x', dur: 5, borda: '#000', texto: '#14100a', icone: { nome: 'balao_fala', pal: { ...AM, m: '#e23636', l: '#ffffff' }, lado: 'dir', tam: 64 } }, { r: 'epico' }),
        F('Capa de HQ', 'A capa de um gibi: raios vermelhos e amarelos, pontos de impressão e um "POW!" estourando.', {
            fundo: ['#ffd23f'], fixo: `${raiosHQ('#e23636', '#ffd23f')}${pontosBenDay('#000', .16)}<g transform='translate(110 0)'>${explosao}</g>`,
            perto: { svg: cena.icones({ nomes: ['estrela_ko'], pals: [{ m: '#fff', a: '#ffd23f', d: '#e23636', l: '#fff', o: '#000' }], n: 4, tam: [10, 16], seed: 'hq1', y: [10, 100] }), anim: 'pisca', dur: 2 },
        }, { r: 'epico' }),
        EA('Ultimate', 'Um anel em volta da foto enche até o fim e explode em raios, como uma barra de habilidade final.', [
            { k: 'raw', html: `<b class="$C"><svg viewBox="0 0 160 160"><circle cx="80" cy="80" r="63" fill="none" stroke="rgba(0,0,0,.55)" stroke-width="8"/><circle class="bar" cx="80" cy="80" r="63" fill="none" stroke="#ffd23f" stroke-width="6" pathLength="100" stroke-dasharray="100" stroke-dashoffset="100" stroke-linecap="butt" transform="rotate(-90 80 80)"/></svg></b><b class="$C bst"></b>`,
              css: `.ef-av-$ID .$C svg{position:absolute;inset:0;width:100%;height:100%}.ef-av-$ID .bar{animation:k-$ID-bar 6s ease-in-out ${fase(6, .66)} infinite;filter:drop-shadow(0 0 4px #ffd23f)}.ef-av-$ID .bst{background:repeating-conic-gradient(from 0deg,rgba(255,210,63,.95) 0 3deg,transparent 3deg 15deg);-webkit-mask:radial-gradient(closest-side,transparent 62%,#000 66%,transparent 96%);mask:radial-gradient(closest-side,transparent 62%,#000 66%,transparent 96%);opacity:0;animation:k-$ID-bst 6s ease-out ${fase(6, .66)} infinite}`
                  + `@keyframes k-$ID-bar{0%{stroke-dashoffset:100;stroke:#ffd23f}62%{stroke-dashoffset:0;stroke:#ff8a1f}80%,100%{stroke-dashoffset:0;stroke:#e23636}}@keyframes k-$ID-bst{0%,62%{opacity:0;transform:scale(.8)}68%{opacity:1;transform:scale(1)}86%,100%{opacity:0;transform:scale(1.35)}}` },
        ], { r: 'epico' }),
        EP('Painéis', 'Três painéis de gibi entram em sequência no cartão, cada um com a sua onomatopeia.', [
            { k: 'raw', html: `<b class="pn p1"><i>POW!</i></b><b class="pn p2"><i>BAM!</i></b><b class="pn p3"><i>KRAK!</i></b>`,
              css: `.ef-pf-$ID .pn{position:absolute;display:flex;align-items:center;justify-content:center;border:3px solid #000;box-shadow:4px 4px 0 #000;opacity:0;overflow:hidden}.ef-pf-$ID .pn i{font:900 12cqw/1 Impact,'Arial Black',sans-serif;font-style:normal;color:#fff;-webkit-text-stroke:2px #000;paint-order:stroke fill;transform:rotate(-6deg)}`
                  + `.ef-pf-$ID .p1{left:4%;top:6%;width:62%;height:24%;background:radial-gradient(circle,#ffd23f 30%,#ff8a1f 100%);transform:rotate(-2deg);animation:k-$ID-a 10s ease-out ${fase(10, .4)} infinite}.ef-pf-$ID .p2{left:34%;top:36%;width:62%;height:24%;background:radial-gradient(circle,#ff6a6a 30%,#e23636 100%);transform:rotate(1.5deg);animation:k-$ID-b 10s ease-out ${fase(10, .4)} infinite}.ef-pf-$ID .p3{left:6%;top:66%;width:60%;height:26%;background:radial-gradient(circle,#7a9eff 30%,#1e5eff 100%);transform:rotate(-1deg);animation:k-$ID-c 10s ease-out ${fase(10, .4)} infinite}`
                  + `@keyframes k-$ID-a{0%,4%{opacity:0;transform:translateX(-120%) rotate(-2deg)}9%{opacity:1;transform:translateX(0) rotate(-2deg)}70%{opacity:1}78%,100%{opacity:0;transform:translateX(-30%) rotate(-2deg)}}@keyframes k-$ID-b{0%,14%{opacity:0;transform:translateX(120%) rotate(1.5deg)}19%{opacity:1;transform:translateX(0) rotate(1.5deg)}70%{opacity:1}78%,100%{opacity:0;transform:translateX(30%) rotate(1.5deg)}}@keyframes k-$ID-c{0%,24%{opacity:0;transform:translateY(120%) rotate(-1deg)}29%{opacity:1;transform:translateY(0) rotate(-1deg)}70%{opacity:1}78%,100%{opacity:0;transform:translateY(30%) rotate(-1deg)}}` },
        ], { r: 'lendario' }),
        FALA('Grito de Herói', 'Quando você fala na call, o card pisca em vermelho, amarelo e azul, como um painel de ação.', { cores: ['#e23636', '#ffd23f', '#1e5eff'], passos: true }),
        RADAR('Pontos de Impressão', 'As ondas do radar viram anéis pontilhados amarelos, como o meio-tom de um gibi.', { cor: '#ffd23f', estilo: 'pontilhado', glow: '#e23636' }),
        CHAT('BAM', 'A barra de mensagem acende em amarelo ao digitar e solta estrelas de impacto ao enviar.', { cor: '#ffd23f', cor2: '#e23636', particula: { icone: 'estrela_ko', pal: { m: '#ffd23f', a: '#e23636', d: '#7a0a0a', l: '#fff', o: '#000' } } }),
        PIN('Balão de Fala', 'Suas notas no mapa viram um balão de fala de gibi.', { icone: 'balao_fala', pal: { m: '#e23636', l: '#ffffff', o: '#000000' }, bal: 2.4 }),
        SOM('Ultimate', 'Um som que sobe e enche e uma pancada de impacto, ao entrar na call.', { notas: [{ t: 0, f: 200, f2: 1100, d: .5, tipo: 'sawtooth', v: .3 }, { t: .5, f: 110, f2: 45, d: .4, tipo: 'sine', v: 1 }, { t: .5, f: 330, d: .45, tipo: 'square', v: .35 }], ruidos: [{ t: .5, d: .3, f: 2500, f2: 400, filtro: 'bandpass', v: .8 }] }),
        SERV('Servidor de Gibi', 'O ícone do servidor pisca em vermelho e amarelo.', { cores: ['#e23636', '#ffd23f'], passos: true }),
    ],
});

module.exports = [hq];
