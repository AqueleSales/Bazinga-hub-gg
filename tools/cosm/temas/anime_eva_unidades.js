'use strict';
/* EVANGELION: AS UNIDADES 00, 01 E 02 (Rodada 40, épico). Cada uma com os 12 slots. Quem compra o PACOTE de uma delas leva a insígnia da NERV (loja.BADGE_POR_PACOTE).
   Só símbolos por código (arte.js): o olho, o chifre, os quatro olhos, o plug, as presilhas (sem as cabeças dos Evas). O shader do Evangelion (lança e alerta) mora no pacote NERV. */
const { tema, MP, EA, EP, P, R, B, IMG, apoio, fase } = require('../dsl');
const T = 'eva';
const f1 = B.f1;

const octs = (cor) => {
    let d = '';
    for (let j = 0; j < 3; j++) { const r = 62 + j * 10; let pts = ''; for (let i = 0; i < 8; i++) { const a = i / 8 * 2 * Math.PI + Math.PI / 8; pts += `${i ? 'L' : 'M'}${f1(80 + r * Math.cos(a))} ${f1(80 + r * Math.sin(a))}`; } d += `<path d='${pts}Z' fill='none' stroke='${cor}' stroke-width='${3.4 - j * .8}' stroke-opacity='${1 - j * .22}' stroke-linejoin='round'/>`; }
    return `<svg viewBox='0 0 160 160' class='oc'>${d}</svg>`;
};
/** o campo AT abrindo e quebrando em volta da foto (atrás dela) */
const campo = (cor, ciclo = 6) => ({ k: 'raw', html: `<b class="$C">${octs(cor)}</b>`,
    css: `.ef-av-$ID .oc{position:absolute;inset:0;width:100%;height:100%;overflow:visible;filter:drop-shadow(0 0 4px ${cor});transform-origin:50% 50%;animation:k-$ID-oc ${ciclo}s ease-out ${fase(ciclo, .2)} infinite}@keyframes k-$ID-oc{0%{opacity:0;transform:scale(.6)}12%{opacity:1;transform:scale(1)}52%{opacity:1;transform:scale(1.02)}62%{opacity:.9;transform:scale(1.08) rotate(3deg)}78%,100%{opacity:0;transform:scale(1.5) rotate(10deg)}}` });
/** hexágono no lugar do quadrado no efeito de chat (a barra de mensagem solta hexágonos ao enviar) */
const hexChat = (itens, c1, c2) => itens.forEach((it) => { if (it.tipo === 'efeito_chat') it.extra = `.ef-envio-$ID i{clip-path:polygon(25% 6%,75% 6%,100% 50%,75% 94%,25% 94%,0 50%)!important;border-radius:0!important;min-width:12px;min-height:12px;background:${c1}!important}.ef-envio-$ID i:nth-child(even){background:${c2}!important}`; });

// ============================================================================================ UNIDADE 00
const A0 = '#2a5ab0', L0 = '#ff8a2a', B0 = '#e8eef8';
const olhoUnico = (anim) => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.o{animation:g 1.8s ease-in-out infinite alternate}@keyframes g{from{opacity:.65}to{opacity:1}}</style>` : ''}`
    + `<path d='M104 30Q134 14 156 34Q150 52 126 56Q108 52 104 30Z' fill='#1a2a4a' stroke='#14141c' stroke-width='2.4' stroke-linejoin='round'/><ellipse class='o' cx='130' cy='36' rx='15' ry='9' fill='#ffe86a' stroke='#14141c' stroke-width='1.6'/><circle cx='130' cy='36' r='4.6' fill='#14141c'/><circle cx='127' cy='33' r='1.6' fill='#fff'/><path d='M110 24L124 14L146 14L154 22' fill='none' stroke='${L0}' stroke-width='3' stroke-linecap='round'/></svg>`;
const u00 = tema({
    id: 'eva_zero', pre: 'evz', nome: 'Evangelion Unidade-00', cat: 'anime', cor: A0, cores: [A0, L0], icone: 'fa-shield-halved', premium: true,
    lema: 'Eu não sei o que dizer. Mas vou pilotar.',
    desc: 'O protótipo azul e laranja: o olho único, o campo AT em octógonos, o canhão de pósitrons. Quem compra este pacote leva a insígnia da NERV.',
    pal: { m: A0, a: L0, d: '#0a1430', l: '#fff', o: '#0a1430' },
    itens: [
        MP('Olho Único', 'O olho amarelo do protótipo no canto da foto, brilhando.', { svg: olhoUnico }, { r: 'epico' }),
        EA('Olho do Protótipo', 'O olho amarelo do protótipo se acende sobre a sua foto enquanto o campo AT em octógonos laranja abre em volta.', [
            campo(L0),
        ], { r: 'epico', id: 'evz_olho_do_prototipo',
            sobre: [IMG({ tema: T, img: 'eva_olho', onde: 'sobre', n: 'e0', x: 50, y: 30, w: 70, ciclo: 9, ini: 30, fim: 70, de: { esc: .6 }, sai: { esc: 1.2 } })],
            css: '.ef-av-sobre.ef-sobre-$ID.kz{overflow:visible}' }),
        EP('Canhão de Pósitrons', 'Um feixe branco e laranja varre o cartão na diagonal e hexágonos azuis acendem.', [
            { k: 'raw', html: '<i class="fx"></i><i class="hx"></i>',
              css: '.ef-pf-$ID .fx{position:absolute;left:-30%;top:46%;width:160%;height:7%;background:linear-gradient(90deg,transparent,#fff 40%,#ffd08a 70%,transparent);box-shadow:0 0 16px 4px #ff8a2a;transform:rotate(-28deg) scaleX(0);transform-origin:0 50%;opacity:0;animation:k-$ID-fx 7s ease-out ' + fase(7, .3) + ' infinite}@keyframes k-$ID-fx{0%,20%{opacity:0;transform:rotate(-28deg) scaleX(0)}26%{opacity:1;transform:rotate(-28deg) scaleX(1)}44%,100%{opacity:0;transform:rotate(-28deg) scaleX(1)}}'
                + `.ef-pf-$ID .hx{position:absolute;inset:0;background:${B.uri(P.ladrilho({ tipo: 'favo', c1: 'rgba(42,90,176,.5)', c2: 'transparent', tam: 14, lw: 1.2 }).svg)} 0 0/24px 42px repeat;opacity:.18;animation:k-$ID-hx 2.4s ease-in-out infinite alternate}@keyframes k-$ID-hx{from{opacity:.1}to{opacity:.36}}` },
            { k: 'borda', cor: A0, alfa: .5, blur: 36, esp: 4, dur: 2.8 },
        ], { r: 'epico', id: 'evz_canhao_de_positrons' }),
        ...apoio({
            tema: T, r: 'epico',
            nome: { nomeItem: 'Primeira Criança', desc: 'Azul e laranja com contorno escuro, no peso de um título de abertura.', grad: [A0, B0, L0], mov: 'desliza', dur: 4.4, contorno: '#0a1430', cw: 1.1, fonte: 'classica', espaco: 1 },
            placa: { nomeItem: 'Cabine de Pilotagem', desc: 'Azul de plugsuit com hexágonos e o olho da Unidade-00 do lado.', base: [A0, '#0a1a4a'], pad: { tipo: 'favo', c1: 'rgba(232,238,248,.3)', c2: 'transparent', tam: 8, lw: 1 }, mov: 'x', dur: 11, borda: L0, img: { nome: 'eva_olho', lado: 'dir', tam: 78, y: 50 } },
            faixa: { nomeItem: 'Hangar', desc: 'Um hangar azul com hexágonos piscando.', fundo: ['#060e24', '#12285a', '#2a5ab0'],
                perto: { svg: P.cena.icones({ nomes: ['hexagono'], pals: [{ m: '#ff8a2a', o: '#ff8a2a', w: 1 }], n: 8, tam: [10, 20], seed: 'evz1', y: [6, 90] }), anim: 'pisca', dur: 1.8 },
                 },
            fala: { nomeItem: 'Sincronia', desc: 'Quando você fala na call, o card pisca em azul e laranja, como a taxa de sincronização.', cores: [A0, L0], passos: true, dur: .5 },
            radar: { nomeItem: 'Campo AT Azul', desc: 'As ondas do radar viram anéis duplos azuis.', cor: '#5a8ae0', estilo: 'duplo', glow: L0 },
            chat: { nomeItem: 'Hexágonos Azuis', desc: 'Ao digitar a barra acende em azul, e ao enviar hexágonos se abrem sobre ela.', cor: '#5a8ae0', cor2: L0, particula: { forma: 'quadrado' } },
            som: { nomeItem: 'Ativação', desc: 'Uma partida baixa e firme de máquina, ao entrar na call.', arquivo: 'eva00.mp3', notas: [{ t: 0, f: 70, f2: 140, d: .7, tipo: 'sawtooth', v: .4 }, { t: .6, f: 440, d: .25, tipo: 'sine', v: .25 }], ruidos: [{ t: 0, d: .7, f: 400, f2: 1600, filtro: 'bandpass', v: .3, q: .8 }] },
            pin: { nomeItem: 'Olho Único', desc: 'Suas notas no mapa viram o olho da Unidade-00.', img: 'eva_olho' },
            serv: { nomeItem: 'Servidor Protótipo', desc: 'O ícone do servidor pisca em azul e laranja.', cores: [A0, L0], passos: true, dur: .7 },
        }),
    ],
});
hexChat(u00.itens, '#5a8ae0', L0);

// ============================================================================================ UNIDADE 01
const P1 = '#6a3ab0', V1 = '#5ae05a';
const plug = (anim) => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.b{animation:u 2.4s ease-in infinite}.b2{animation-delay:-.8s}.b3{animation-delay:-1.6s}@keyframes u{0%{transform:translateY(0);opacity:0}15%{opacity:.9}100%{transform:translateY(-28px);opacity:0}}</style>` : ''}`
    + `<rect x='124' y='56' width='22' height='62' rx='11' fill='#cfe9d8' fill-opacity='.35' stroke='#14141c' stroke-width='2.6'/><path d='M126 82H144V108Q144 116 135 116Q126 116 126 108Z' fill='${V1}' fill-opacity='.85'/><rect x='121' y='50' width='28' height='8' rx='3' fill='#6a3ab0' stroke='#14141c' stroke-width='2'/><rect x='121' y='116' width='28' height='7' rx='3' fill='#6a3ab0' stroke='#14141c' stroke-width='2'/>`
    + `<g fill='#c8ffd8'><circle class='b' cx='132' cy='108' r='2.6'/><circle class='b b2' cx='138' cy='104' r='2'/><circle class='b b3' cx='134' cy='100' r='1.6'/></g></svg>`;
const u01 = tema({
    id: 'eva_um', pre: 'evu', nome: 'Evangelion Unidade-01', cat: 'anime', cor: P1, cores: [P1, V1], icone: 'fa-bolt', premium: true,
    lema: 'Eu não vou fugir.',
    desc: 'O Eva roxo e verde: o plug de entrada cheio de LCL, o modo berserk, o campo AT em pedaços. Quem compra este pacote leva a insígnia da NERV.',
    pal: { m: P1, a: V1, d: '#14062a', l: '#fff', o: '#14062a' },
    itens: [
        MP('Plug de Entrada', 'O plug de entrada cheio de LCL verde, com bolhas subindo, preso ao lado da foto.', { svg: plug }, { r: 'epico' }),
        EA('Berserk', 'O verde pulsa em fúria em volta da sua foto e o campo AT estala.', [
            { k: 'aura', cor: '#5ae05a', dur: 1.2 },
            campo('#ff8a2a'),
        ], { r: 'epico', id: 'evu_berserk', sobre: [{ k: 'glitch', c1: '#5ae05a', c2: '#a06af0', dur: 3.4 }] }),
        EP('Sincronização 400%', 'Anéis verdes pulsam no cartão e hexágonos acendem.', [
            { k: 'raw', html: '<i class="an a1"></i><i class="an a2"></i><i class="an a3"></i>',
              css: '.ef-pf-$ID .an{position:absolute;left:50%;top:48%;width:34cqw;aspect-ratio:1;margin:-17cqw 0 0 -17cqw;border-radius:50%;border:3px solid #5ae05a;box-shadow:0 0 12px #5ae05a;opacity:0;animation:k-$ID-an 5s ease-out calc(var(--d) + ' + fase(5, .3) + ') infinite}.ef-pf-$ID .a1{--d:0s}.ef-pf-$ID .a2{--d:-1.7s}.ef-pf-$ID .a3{--d:-3.4s}@keyframes k-$ID-an{0%{opacity:.9;transform:scale(.3)}100%{opacity:0;transform:scale(3.6)}}' },
            { k: 'pisca', icone: 'hexagono', pals: [{ m: '#5ae05a', o: '#5ae05a', w: 1 }], n: 10, tam: [10, 18] },
            { k: 'borda', cor: V1, alfa: .55, blur: 38, esp: 5, dur: 1.6 },
        ], { r: 'epico', id: 'evu_sincronizacao' }),
        ...apoio({
            tema: T, r: 'epico',
            nome: { nomeItem: 'Terceira Criança', desc: 'Roxo e verde com contorno escuro, no peso de um título de abertura.', grad: [P1, V1, P1], mov: 'desliza', dur: 3.6, contorno: '#14062a', cw: 1.1, fonte: 'classica', espaco: 1 },
            placa: { nomeItem: 'Sala de Controle', desc: 'Roxo de plugsuit com hexágonos verdes e o chifre da Unidade-01 do lado.', base: [P1, '#2a1060'], pad: { tipo: 'favo', c1: 'rgba(90,224,90,.3)', c2: 'transparent', tam: 8, lw: 1 }, mov: 'x', dur: 10, borda: V1, img: { nome: 'eva_chifre', lado: 'dir', tam: 96, y: 50 } },
            faixa: { nomeItem: 'Gaiola', desc: 'A gaiola de lançamento roxa com luz verde.', fundo: ['#0a0418', '#2a1060', '#6a3ab0'],
                perto: { svg: P.cena.icones({ nomes: ['raio'], pals: [{ m: '#5ae05a', o: '#5ae05a', w: 1 }], n: 6, tam: [10, 18], seed: 'evu1', y: [6, 90] }), anim: 'pisca', dur: 1.4 },
                 },
            fala: { nomeItem: 'Berserk', desc: 'Quando você fala na call, o card pisca em verde e roxo, em fúria.', cores: [V1, P1], passos: true, dur: .3 },
            radar: { nomeItem: 'Campo AT Verde', desc: 'As ondas do radar viram anéis duplos verdes.', cor: V1, estilo: 'duplo', glow: P1 },
            chat: { nomeItem: 'Hexágonos Verdes', desc: 'Ao digitar a barra acende em verde, e ao enviar hexágonos se abrem sobre ela.', cor: V1, cor2: P1, particula: { forma: 'quadrado' } },
            som: { nomeItem: 'Rugido', desc: 'Um rugido grave e rasgado de fera, ao entrar na call.', arquivo: 'eva01.mp3', notas: [{ t: 0, f: 90, f2: 55, d: .9, tipo: 'sawtooth', v: .55 }, { t: .05, f: 180, f2: 110, d: .8, tipo: 'sawtooth', v: .3 }], ruidos: [{ t: .05, d: .9, f: 900, f2: 3000, filtro: 'bandpass', v: .45, q: .7 }] },
            pin: { nomeItem: 'Chifre', desc: 'Suas notas no mapa viram o chifre da Unidade-01.', img: 'eva_chifre' },
            serv: { nomeItem: 'Servidor Berserk', desc: 'O ícone do servidor pisca em verde e roxo.', cores: [V1, P1], passos: true, dur: .5 },
        }),
    ],
});
hexChat(u01.itens, V1, P1);

// ============================================================================================ UNIDADE 02
const R2 = '#d82a1a', L2 = '#ff8a2a', Y2 = '#ffe86a';
const presilhas = (anim) => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.p{animation:g 1.2s ease-in-out infinite alternate}@keyframes g{from{opacity:.6}to{opacity:1}}</style>` : ''}`
    + `<g><path d='M30 44L44 34L50 48L36 58Z' fill='${L2}' stroke='#14141c' stroke-width='2.2' stroke-linejoin='round'/><circle class='p' cx='40' cy='46' r='3.6' fill='${Y2}'/></g><g><path d='M48 26L62 18L67 31L53 40Z' fill='${L2}' stroke='#14141c' stroke-width='2.2' stroke-linejoin='round'/><circle class='p' cx='58' cy='29' r='3.6' fill='${Y2}'/></g></svg>`;
const u02 = tema({
    id: 'eva_dois', pre: 'evd', nome: 'Evangelion Unidade-02', cat: 'anime', cor: R2, cores: [R2, L2], icone: 'fa-fire', premium: true,
    lema: 'Eu sou a melhor piloto.',
    desc: 'O Eva vermelho: as presilhas de interface laranjas, os quatro olhos acendendo, chamas e o campo AT quebrando. Quem compra este pacote leva a insígnia da NERV.',
    pal: { m: R2, a: L2, d: '#2a0604', l: '#fff', o: '#2a0604' },
    itens: [
        MP('Presilhas de Interface', 'As duas presilhas laranja da interface de piloto, piscando no alto da foto.', { svg: presilhas }, { r: 'epico' }),
        EA('Quatro Olhos', 'Os quatro olhos acendem sobre a sua foto e o vermelho pulsa em fogo.', [
            { k: 'aura', cor: '#ff5a2a', dur: 1.3 },
            { k: 'faiscas', icone: 'brilho', pals: [{ m: '#ffe86a', o: '#d82a1a', w: 2 }], n: 8, tam: 8, raio: 38 },
        ], { r: 'epico', id: 'evd_quatro_olhos',
            sobre: [IMG({ tema: T, img: 'eva_olhos4', onde: 'sobre', n: 'e2', x: 50, y: 30, w: 70, ciclo: 9, ini: 30, fim: 70, de: { esc: .6 }, sai: { esc: 1.2 } })],
            css: '.ef-av-sobre.ef-sobre-$ID.kz{overflow:visible}' }),
        EP('Fúria Vermelha', 'Chamas sobem pelo cartão e o vermelho respira, com a borda em fogo.', [
            { k: 'clima', fundo: 'radial-gradient(ellipse at 50% 100%,rgba(216,42,26,.7),transparent 65%)', min: .3, max: 1, dur: 2.4 },
            { k: 'sobe', icones: ['chama'], pals: [{ m: '#ff5a2a', a: '#ffe86a', d: '#a01a10', l: '#fff', o: '#2a0604' }], n: 12, tam: [14, 26], vel: [5, 10], alfa: .9 },
            { k: 'borda', cor: R2, alfa: .55, blur: 40, esp: 5, dur: 1.5 },
        ], { r: 'epico', id: 'evd_furia_vermelha' }),
        ...apoio({
            tema: T, r: 'epico',
            nome: { nomeItem: 'Segunda Criança', desc: 'Vermelho e laranja com contorno escuro, no peso de um título de abertura.', grad: [R2, L2, Y2, R2], mov: 'desliza', dur: 3.2, contorno: '#2a0604', cw: 1.1, fonte: 'classica', espaco: 1 },
            placa: { nomeItem: 'Plugsuit Vermelho', desc: 'Vermelho de plugsuit com hexágonos e os quatro olhos da Unidade-02 do lado.', base: [R2, '#7a0a06'], pad: { tipo: 'favo', c1: 'rgba(255,232,106,.3)', c2: 'transparent', tam: 8, lw: 1 }, mov: 'x', dur: 10, borda: Y2, img: { nome: 'eva_olhos4', lado: 'dir', tam: 78, y: 50 } },
            faixa: { nomeItem: 'Céu em Chamas', desc: 'Um céu de fogo com chamas piscando.', fundo: ['#1a0604', '#7a0a06', '#d82a1a'],
                perto: { svg: P.cena.icones({ nomes: ['chama'], pals: [{ m: '#ff8a2a', a: '#ffe86a', d: '#a01a10', l: '#fff', o: '#2a0604', w: 1 }], n: 7, tam: [12, 22], seed: 'evd1', y: [30, 100] }), anim: 'pisca', dur: 1.2 },
                 },
            fala: { nomeItem: 'Eu Sou Melhor', desc: 'Quando você fala na call, o card pisca em vermelho e laranja, orgulhoso.', cores: [R2, L2], passos: true, dur: .35 },
            radar: { nomeItem: 'Campo AT Vermelho', desc: 'As ondas do radar viram anéis duplos vermelhos.', cor: R2, estilo: 'duplo', glow: L2 },
            chat: { nomeItem: 'Hexágonos Vermelhos', desc: 'Ao digitar a barra acende em vermelho, e ao enviar hexágonos se abrem sobre ela.', cor: R2, cor2: L2, particula: { forma: 'quadrado' } },
            som: { nomeItem: 'Grito de Guerra', desc: 'Um grito de batalha agudo e orgulhoso, ao entrar na call.', arquivo: 'eva02.mp3', notas: [{ t: 0, f: 600, f2: 1100, d: .25, tipo: 'sawtooth', v: .35 }, { t: .28, f: 1100, f2: 700, d: .35, tipo: 'sawtooth', v: .3 }, { t: 0, f: 100, f2: 70, d: .6, tipo: 'sawtooth', v: .3 }], ruidos: [{ t: .05, d: .5, f: 1500, f2: 4000, filtro: 'bandpass', v: .3, q: 1 }] },
            pin: { nomeItem: 'Quatro Olhos', desc: 'Suas notas no mapa viram os quatro olhos da Unidade-02.', img: 'eva_olhos4' },
            serv: { nomeItem: 'Servidor Vermelho', desc: 'O ícone do servidor pisca em vermelho e laranja.', cores: [R2, L2], passos: true, dur: .5 },
        }),
    ],
});
hexChat(u02.itens, R2, L2);

module.exports = [u00, u01, u02];
