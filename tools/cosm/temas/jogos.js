'use strict';
/* JOGOS (arte original que só evoca; nada de sprite, logo ou áudio de terceiros). Ver docs/PLANO_TEMAS.md, grupo A. */
const { tema, M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P, I, fase } = require('../dsl');
const { cena } = P;
const { pontos } = I;

// =====================================================================================================
// VALHALLA (luta de plataforma viking): runas, armas, ponte de arco-íris, dano em %, estrela de K.O.
// =====================================================================================================
const OURO = { m: '#ffb84a', a: '#ffd98a', d: '#2b2f3a', l: '#fff3d6', o: '#3a2208', w: 0 };
const PEDRA = { m: '#7a7f90', o: '#7a7f90', w: -13 };
const ACO = { m: '#aeb8cc', a: '#e8eefc', d: '#4a5568', l: '#fff', o: '#262c38' };
const BRASA = { m: '#f08a24', a: '#ffc06a', d: '#5a2a08', l: '#fff3d6', o: '#4a1f04' };

const plat = (x, y, w) => `<path d='M${x + 6} ${y + 7}L${x + w - 6} ${y + 7}L${f(x + w * .74)} ${f(y + 7 + w * .26)}L${f(x + w * .5)} ${f(y + 7 + w * .4)}L${f(x + w * .28)} ${f(y + 7 + w * .24)}Z' fill='#3a3d48' stroke='#22242c' stroke-width='1.4' stroke-linejoin='round'/><rect x='${x}' y='${y}' width='${w}' height='8' rx='3' fill='#868ca0' stroke='#22242c' stroke-width='1.6'/><rect x='${x + 3}' y='${y + 1.2}' width='${w - 6}' height='2.4' rx='1.2' fill='#c4c9dc' opacity='.7'/>`;
const f = (n) => Math.round(n * 10) / 10;
const arenaFixa = `<defs><linearGradient id='bi' x1='0' x2='1'><stop offset='0' stop-color='#ff6b6b'/><stop offset='.33' stop-color='#ffd166'/><stop offset='.66' stop-color='#7be0a4'/><stop offset='1' stop-color='#6ec6ff'/></linearGradient></defs>`
    + `<path d='M-20 118C50 10 290 10 360 118' fill='none' stroke='url(#bi)' stroke-width='11' opacity='.4'/>`
    + cena.estrelas({ cor: '#fff', n: 26, y: [0, 56], r: [.5, 1.3], seed: 'v1' })
    + plat(14, 70, 84) + plat(138, 48, 66) + plat(246, 76, 80)
    + `<g fill='#f08a24'><path d='M60 70c-4-9 1-13 2-17 3 4 7 8 4 17z'/><path d='M180 48c-3-8 1-11 2-15 2 4 6 7 3 15z'/></g>`;

const RUNAS_ANEL = ['runa_fehu', 'runa_algiz', 'runa_tiwaz', 'runa_ansuz', 'runa_sowilo', 'runa_gebo', 'runa_berkano', 'runa_uruz'];

const valhalla = tema({
    id: 'valhalla', pre: 'val', nome: 'Valhalla', cat: 'jogos', cor: '#f08a24', cores: ['#f08a24', '#3a6ea5'], icone: 'fa-hammer', premium: true,
    lema: 'Só se vence na arena. Só se fica pelo nome.',
    desc: 'Runas que giram, armas voando, o dano que sobe em % e a estrela de K.O. que estoura: a arena flutuante dos vikings.',
    pal: BRASA,
    itens: [
        M('Círculo de Runas', 'Um círculo de runas douradas que gira devagar em volta da foto, com um brilho de brasa.', { t: 'icones', icones: RUNAS_ANEL, pals: [OURO], n: 12, tam: 22, giro: 80, glow: '#f08a24' }, { r: 'epico' }),
        N('Valhalla', 'Letras de pedra talhada, com a borda em brasa que pulsa.', { grad: ['#efe8d6', '#b9b3a2', '#efe8d6'], mov: 'pulsa', brilho: '#f08a24', bw: 2.4, contorno: '#2a1808', cw: .8, fonte: 'classica', espaco: .4, peso: 900, dur: 3 }, { r: 'epico' }),
        Pl('Laje de Runas', 'Uma laje de pedra gravada com runas e um brilho de brasa que passa.', { base: ['#4b4e5a', '#393c47'], pad: { tipo: 'icones', icones: ['runa_fehu', 'runa_algiz', 'runa_tiwaz', 'runa_ansuz'], pals: [PEDRA], tam: 30, ti: 17, c2: 'transparent' }, mov: 'x', dur: 22, brilho: 'rgba(240,138,36,.42)', borda: 'rgba(240,138,36,.55)', icone: { nome: 'martelo', pal: ACO, lado: 'dir', tam: 66 } }, { r: 'epico' }),
        F('Arena Flutuante', 'Plataformas de pedra no ar, a ponte de arco-íris ao fundo e brasas piscando.', {
            fundo: ['#141b38', '#2d3f78', '#e0803a'], fixo: arenaFixa,
            longe: { svg: cena.nuvens({ cor: '#27315a', n: 3, y: [76, 104], alfa: .75, tam: [14, 22], seed: 'v2' }), anim: 'pan', dur: 64 },
            perto: { svg: cena.estrelas({ cor: '#ffb04a', n: 26, y: [10, 108], r: [.8, 1.8], seed: 'v3' }), anim: 'pisca', dur: 2.6 },
        }, { r: 'epico' }),
        EA('Dano %', 'O dano sobe por cima da sua foto, de 0% até mais de 150%, e vai do branco ao amarelo e ao vermelho.', [
            { k: 'raw', html: '<b class="$C"><i class="dn"></i></b>',
              css: `.ef-av-$ID .$C{overflow:visible}.ef-av-$ID .$C .dn{position:absolute;left:50%;top:-6%;width:60cqw;margin-left:-30cqw;text-align:center;font:900 15cqw/1 Impact,'Arial Black',sans-serif;color:#fff;-webkit-text-stroke:1.4px #1a0a00;paint-order:stroke fill;letter-spacing:.5px;counter-reset:dn var(--k-dn);opacity:0;animation:k-$ID-dn 8s linear ${fase(8, .5)} infinite}.ef-av-$ID .$C .dn::after{content:counter(dn) '%'}`
              + `@keyframes k-$ID-dn{0%{--k-dn:0;color:#fff;opacity:0;transform:translateY(30%) scale(.6)}6%{opacity:1;transform:translateY(0) scale(1)}40%{--k-dn:90;color:#ffe94a}70%{--k-dn:158;color:#ff8a1a}84%{--k-dn:199;color:#ff2b2b;transform:scale(1.18)}90%{opacity:1;transform:scale(1)}100%{--k-dn:199;color:#ff2b2b;opacity:0;transform:translateY(-14%) scale(1)}}` },
            { k: 'faiscas', icone: 'estrelinha', pals: [{ m: '#ffd24a', o: '#ffd24a', w: 0 }], n: 6, tam: 6, raio: 40 },
        ], { r: 'epico' }),
        EA('Armas Orbitando', 'Martelo, machado, espada, lança, arco e escudo giram em volta da sua foto.', [
            { k: 'orbita', icones: ['martelo', 'machado', 'espada', 'lanca', 'arco', 'escudo_redondo'], pals: [ACO], n: 6, tam: 25, giro: 20 },
        ], { r: 'epico' }),
        EP('Zona de K.O.', 'A cada tanto o cartão leva um K.O.: clarão, a estrela estoura com os raios e a palavra aparece.', [
            { k: 'raw', html: `<i class="ko-cl"></i><svg class="ko-r" viewBox="-100 -100 200 200">${(() => { let s = ''; for (let k = 0; k < 28; k++) { const a = k * 360 / 28 * Math.PI / 180, r2 = 78 + (k % 2) * 22; s += `<path d="M${f(20 * Math.cos(a))} ${f(20 * Math.sin(a))}L${f(r2 * Math.cos(a))} ${f(r2 * Math.sin(a))}" stroke="${k % 2 ? '#ffd24a' : '#fff'}" stroke-width="${k % 2 ? 2.4 : 4.4}" stroke-linecap="round"/>`; } return s; })()}</svg>`
              + `<svg class="ko-e" viewBox="0 0 100 100"><path d="${pontos(12, 50, 50, 48, 28, -90)}" fill="#ffd24a" stroke="#7a3a00" stroke-width="3" stroke-linejoin="round"/><path d="${pontos(12, 50, 50, 34, 20, -75)}" fill="#fff3b0"/></svg><b class="ko-t">K.O.</b>`,
              css: `.ef-pf-$ID .ko-cl{position:absolute;inset:0;background:#fff;opacity:0;animation:k-$ID-cl 9s linear ${fase(9, .72)} infinite}.ef-pf-$ID .ko-r,.ef-pf-$ID .ko-e{position:absolute;left:50%;top:46%;margin:-58cqw 0 0 -58cqw;width:116cqw;height:116cqw;opacity:0}.ef-pf-$ID .ko-e{margin:-30cqw 0 0 -30cqw;width:60cqw;height:60cqw;filter:drop-shadow(0 0 6px rgba(255,160,40,.8))}`
              + `.ef-pf-$ID .ko-r{animation:k-$ID-r 9s ease-out ${fase(9, .78)} infinite}.ef-pf-$ID .ko-e{animation:k-$ID-e 9s ease-out ${fase(9, .78)} infinite}.ef-pf-$ID .ko-t{position:absolute;left:0;right:0;top:46%;margin-top:-12cqw;text-align:center;font:900 24cqw/1 Impact,'Arial Black',sans-serif;color:#fff;-webkit-text-stroke:2px #5a2a00;paint-order:stroke fill;opacity:0;animation:k-$ID-t 9s ease-out ${fase(9, .78)} infinite}`
              + `@keyframes k-$ID-cl{0%,72%{opacity:0}73%{opacity:.9}76%,100%{opacity:0}}@keyframes k-$ID-r{0%,72%{opacity:0;transform:scale(.2) rotate(0)}75%{opacity:1;transform:scale(.8) rotate(6deg)}90%{opacity:.85;transform:scale(1.25) rotate(14deg)}100%{opacity:0;transform:scale(1.5) rotate(16deg)}}`
              + `@keyframes k-$ID-e{0%,72%{opacity:0;transform:scale(0) rotate(-40deg)}76%{opacity:1;transform:scale(1.28) rotate(8deg)}80%{transform:scale(1) rotate(0)}92%{opacity:1;transform:scale(1.05)}100%{opacity:0;transform:scale(1.2)}}@keyframes k-$ID-t{0%,74%{opacity:0;transform:scale(2.2)}78%{opacity:1;transform:scale(1)}92%{opacity:1}100%{opacity:0;transform:scale(1.1)}}` },
        ], { r: 'lendario' }),
        FALA('Grito de Guerra', 'Quando você fala na call, o card acende em brasa e azul-aço.', { cores: ['#f08a24', '#3a6ea5'] }),
        RADAR('Ondas de Runa', 'As ondas do radar viram anéis dourados tracejados, como um círculo de runas.', { cor: '#ffb84a', estilo: 'tracejado', glow: '#f08a24' }),
        CHAT('Golpe', 'A barra de mensagem acende em brasa ao digitar e solta faíscas de impacto ao enviar.', { cor: '#f08a24', cor2: '#fff3d6', particula: { forma: 'losango' } }),
        PIN('Runa', 'Suas notas no mapa viram uma pedra com uma runa gravada.', { icone: 'pedra_runa', pal: { m: '#868ca0', l: '#c4c9dc', d: '#f08a24', o: '#22242c' } }),
        SOM('Impacto', 'Uma pancada grave e o tinido de metal de um golpe certeiro, ao entrar na call.', { notas: [{ t: 0, f: 130, f2: 42, d: .3, tipo: 'sine', v: 1 }, { t: .02, f: 880, d: .7, tipo: 'sine', v: .35 }, { t: .02, f: 1330, d: .55, tipo: 'sine', v: .25 }, { t: .02, f: 2210, d: .35, tipo: 'sine', v: .15 }], ruidos: [{ t: 0, d: .12, f: 1800, f2: 400, filtro: 'bandpass', v: .8, q: .8 }] }),
        SERV('Servidor de Brasa', 'O ícone do servidor brilha em brasa e azul-aço.', { cores: ['#f08a24', '#3a6ea5'] }),
    ],
});

module.exports = [valhalla];
