'use strict';
/* JOJO: LEONE ABBACCHIO (Rodada 40, lendário): a fita que rebobina e o tempo que volta. Só símbolos e objetos por código (arte.js). */
const { tema, MP, EA, EP, P, R, B, IMG, apoio, fase } = require('../dsl');
const T = 'jojo';
const f1 = B.f1;
const PRA = '#d0d4de', AZU = '#6a8ad8', VRD = '#3aa05a';

/** o carretel de fita que gira PRA TRÁS (rebobinando), com a fita saindo até a foto */
const carretel = (anim) => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.r{transform-origin:36px 128px;animation:g 3s linear infinite reverse}.s{animation:p 1s steps(2) infinite}@keyframes g{to{transform:rotate(360deg)}}@keyframes p{from{opacity:.4}to{opacity:1}}</style>` : ''}`
    + `<path d='M46 120Q58 96 78 100' fill='none' stroke='#3a2a22' stroke-width='5' stroke-linecap='round'/><path d='M46 120Q58 96 78 100' fill='none' stroke='#7a5a4a' stroke-width='1.6' stroke-linecap='round'/>`
    + `<g class='r'><circle cx='36' cy='128' r='15' fill='#1a1a24' stroke='#9aa4b8' stroke-width='2.4'/>${[0, 1, 2, 3, 4, 5].map((k) => `<circle cx='${f1(36 + 8 * Math.cos(k * 1.0472))}' cy='${f1(128 + 8 * Math.sin(k * 1.0472))}' r='3' fill='#c8ccd8'/>`).join('')}<circle cx='36' cy='128' r='3.4' fill='#6a8ad8'/></g>`
    + `<g class='s' fill='${AZU}' stroke='#14284e' stroke-width='1'><path d='M64 140L76 134V146Z'/><path d='M80 140L92 134V146Z'/></g></svg>`;

const abba = tema({
    id: 'jj_abba', pre: 'jab', nome: 'Leone Abbacchio', cat: 'anime', cor: AZU, cores: [PRA, AZU], icone: 'fa-backward', premium: true,
    lema: 'Eu nunca me arrependo.',
    desc: 'O carretel que rebobina o tempo, anéis de relógio ao contrário, setas voltando e a tela de fita VHS.',
    pal: { m: AZU, a: PRA, d: '#14284e', l: '#fff', o: '#14284e' },
    itens: [
        MP('Fita Rebobinando', 'Um carretel de fita girando ao contrário, com a fita saindo até a foto.', { svg: carretel }, { r: 'lendario' }),
        EA('Rebobinar', 'Anéis de relógio giram ao contrário em volta da foto e setas de rebobinar piscam.', [
            { k: 'anel', cor: '#d0d4de', r: 66, esp: 2, dash: '6 5', giro: 9, rev: true },
            { k: 'raw', html: `<b class="$C"><svg viewBox="0 0 160 160" class="rw"><path d="M64 14L52 22L64 30ZM80 14L68 22L80 30Z" fill="#d0d4de" stroke="#14284e" stroke-width="1.4" stroke-linejoin="round"/></svg></b>`,
              css: '.ef-av-$ID .rw{position:absolute;inset:0;width:100%;height:100%;overflow:visible;animation:k-$ID-rw 1.6s steps(1,end) infinite}@keyframes k-$ID-rw{0%{opacity:.3;transform:translateX(8px)}33%{opacity:1;transform:translateX(0)}66%{opacity:.6;transform:translateX(-6px)}100%{opacity:.2;transform:translateX(-10px)}}' },
        ], { r: 'lendario', id: 'jab_rebobinar' }),
        EP('Replay', 'Linhas de fita VHS correm e setas de rebobinar varrem o cartão de um lado ao outro.', [
            { k: 'raw', html: '<i class="vh"></i><i class="rb rb1"></i><i class="rb rb2"></i>',
              css: '.ef-pf-$ID .vh{position:absolute;inset:0;background:repeating-linear-gradient(0deg,rgba(208,212,222,.16) 0 2px,transparent 2px 7px);opacity:.7;animation:k-$ID-vh 1.4s linear infinite}@keyframes k-$ID-vh{to{background-position:0 28px}}'
                + '.ef-pf-$ID .rb{position:absolute;left:100%;width:24cqw;height:12cqw;background:linear-gradient(90deg,transparent,rgba(106,138,216,.55));clip-path:polygon(100% 0,0 50%,100% 100%);opacity:0;animation:k-$ID-rb 6s ease-in calc(var(--d) + ' + fase(6, .25) + ') infinite}.ef-pf-$ID .rb1{top:30%;--d:0s}.ef-pf-$ID .rb2{top:62%;--d:-3s}@keyframes k-$ID-rb{0%{opacity:0;transform:translateX(0)}8%{opacity:1}60%{opacity:1;transform:translateX(-140cqw)}100%{opacity:0;transform:translateX(-140cqw)}}' },
            { k: 'borda', cor: AZU, alfa: .45, blur: 36, esp: 4, dur: 3 },
        ], { r: 'lendario', id: 'jab_replay' }),
        ...apoio({
            tema: T,
            nome: { nomeItem: 'Sem Arrependimento', desc: 'Prata e azul com contorno escuro, o brilho do cabelo do Abbacchio.', grad: [PRA, AZU, PRA], mov: 'desliza', dur: 4, contorno: '#14284e', cw: 1.1, fonte: 'classica', espaco: 1 },
            placa: { nomeItem: 'Gola de Cordões', desc: 'Preto com a trama verde da gola e um carretel de fita do lado.', base: ['#14141c', '#0a0a10'], pad: { tipo: 'riscos', c1: 'rgba(58,160,90,.4)', c2: 'transparent', tam: 8, lw: 1.2 }, mov: 'x', dur: 12, borda: VRD, img: { nome: 'fita', lado: 'dir', tam: 84, y: 50 } },
            faixa: { nomeItem: 'Fita VHS', desc: 'Ruído de fita VHS em azul.', fundo: ['#0a1430', '#1c2a5a', '#3a4a8a'],
                perto: { svg: `<g opacity='.5'>${Array.from({ length: 12 }, (_, k) => `<rect x='0' y='${k * 9}' width='340' height='1.4' fill='#d0d4de'/>`).join('')}</g>`, anim: 'pisca', dur: .6 },
                 },
            fala: { nomeItem: 'Replay', desc: 'Quando você fala na call, o card pisca em prata e azul, como um replay.', cores: [PRA, AZU], passos: true, dur: .5 },
            radar: { nomeItem: 'Voltando', desc: 'As ondas do radar viram anéis prateados tracejados.', cor: PRA, estilo: 'tracejado', glow: AZU },
            chat: { nomeItem: 'Rebobinar', desc: 'A barra de mensagem acende em azul ao digitar e solta setas de rebobinar ao enviar.', cor: AZU, cor2: PRA, particula: { forma: 'losango' } },
            som: { nomeItem: 'Fita Voltando', desc: 'O chiado agudo de uma fita rebobinando e o clique do fim, ao entrar na call.', arquivo: 'abbacchio.mp3', notas: [{ t: 0, f: 2600, f2: 400, d: .55, tipo: 'sawtooth', v: .18 }, { t: .6, f: 300, f2: 220, d: .08, tipo: 'square', v: .3 }], ruidos: [{ t: 0, d: .55, f: 5000, f2: 800, filtro: 'bandpass', v: .35, q: 1.2 }] },
            pin: { nomeItem: 'Fita', desc: 'Suas notas no mapa viram um carretel de fita.', img: 'fita' },
            serv: { nomeItem: 'Servidor Replay', desc: 'O ícone do servidor pisca em prata e azul.', cores: [PRA, AZU], passos: true, dur: .9 },
        }),
    ],
});

module.exports = [abba];
