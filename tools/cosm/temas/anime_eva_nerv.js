'use strict';
/* EVANGELION: PACOTE NERV (Rodada 40, épico). A logo da NERV (desenhada por código), a Lança de Longinus (imagem de verdade), o campo AT em octógonos, hexágonos e o alerta de Anjo.
   Quem compra o PACOTE NERV (ou o pacote de uma das unidades 00, 01, 02) leva a insígnia da NERV (ver app/loja.py, BADGE_POR_PACOTE). */
const { tema, MP, EA, EP, P, R, B, IMG, apoio, fase } = require('../dsl');
const f1 = B.f1;
const T = 'eva';
const VER = '#e5201a', LAR = '#ff8a2a', NEG = '#0a0a0e';

/** octógonos concêntricos (quadro 160, foto = círculo raio 50): o campo AT em volta da foto */
const octs = (cor, qtd = 3) => {
    let d = '';
    for (let j = 0; j < qtd; j++) { const r = 62 + j * 10; let pts = ''; for (let i = 0; i < 8; i++) { const a = i / 8 * 2 * Math.PI + Math.PI / 8; pts += `${i ? 'L' : 'M'}${f1(80 + r * Math.cos(a))} ${f1(80 + r * Math.sin(a))}`; } d += `<path d='${pts}Z' fill='none' stroke='${cor}' stroke-width='${3.4 - j * .8}' stroke-opacity='${1 - j * .22}' stroke-linejoin='round'/>`; }
    return `<svg viewBox='0 0 160 160' class='oc'>${d}</svg>`;
};
const hexaIcone = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><path d='M50 6L88 28V72L50 94L12 72V28Z' fill='none' stroke='#ff8a2a' stroke-width='9' stroke-linejoin='round'/></svg>`;

const nerv = tema({
    id: 'eva_nerv', pre: 'nrv', nome: 'NERV', cat: 'anime', cor: VER, cores: [VER, LAR], icone: 'fa-triangle-exclamation', premium: true,
    lema: 'Deus está no céu, e tudo está bem no mundo.',
    desc: 'O pacote NERV: a folha da logo, o campo AT que quebra, a Lança de Longinus, hexágonos na barra de mensagem e o alerta de Anjo. Quem leva este pacote (ou o de uma unidade) ganha a insígnia da NERV.',
    pal: { m: VER, a: LAR, d: NEG, l: '#fff', o: NEG },
    itens: [
        MP('Emblema NERV', 'A folha vermelha da NERV presa à borda da foto, pulsando como um alarme.', { imagem: { url: R.url(T, 'nerv'), ratio: R.proporcao(T, 'nerv'), x: 88, y: 88, w: 40, rot: 0, anim: 'pulsa', dur: 1.8 } }, { r: 'epico' }),
        EA('Campo AT', 'O campo AT em octógonos laranja abre em volta da foto e a Lança de Longinus atravessa tudo, quebrando o campo.', [
            { k: 'raw', html: `<b class="$C">${octs(LAR)}</b>`,
              css: `.ef-av-$ID .oc{position:absolute;inset:0;width:100%;height:100%;overflow:visible;filter:drop-shadow(0 0 4px #ff8a2a);transform-origin:50% 50%;animation:k-$ID-oc 6s ease-out ${fase(6, .2)} infinite}@keyframes k-$ID-oc{0%{opacity:0;transform:scale(.6)}12%{opacity:1;transform:scale(1)}52%{opacity:1;transform:scale(1.02)}62%{opacity:.9;transform:scale(1.08) rotate(3deg)}78%,100%{opacity:0;transform:scale(1.5) rotate(10deg)}}` },
        ], { r: 'epico', id: 'nrv_campo_at',
            sobre: [IMG({ tema: T, img: 'lanca', onde: 'sobre', n: 'ln', x: 50, y: 50, w: 190, ciclo: 6, ini: 30, fim: 70, de: { x: 90, y: -90, esc: 1 }, sai: { x: -30, y: 30, esc: 1 }, rot: 135, brilho: '#ff8a2a', bw: 3 })],
            css: '.ef-av-sobre.ef-sobre-$ID.kz{overflow:visible}' }),
        EP('Alerta de Anjo', 'Hexágonos pulsam em vermelho, faixas de alerta correm no alto e embaixo e a palavra EMERGENCY pisca, como no centro de comando.', [
            { k: 'raw', html: '<i class="hz"></i><i class="fa fa1"></i><i class="fa fa2"></i><b class="em">EMERGENCY</b><i class="lg"></i>',
              css: `.ef-pf-$ID .hz{position:absolute;inset:0;background:${B.uri(P.ladrilho({ tipo: 'favo', c1: 'rgba(255,40,30,.5)', c2: 'transparent', tam: 14, lw: 1.2 }).svg)} 0 0/24px 42px repeat;opacity:.2;animation:k-$ID-hz 2.4s ease-in-out infinite alternate}`
                + `.ef-pf-$ID .fa{position:absolute;left:0;right:0;height:6cqh;background:repeating-linear-gradient(-45deg,#e5201a 0 14px,#0a0a0e 14px 28px);background-size:40px 100%;opacity:0;animation:k-$ID-fa 8s ease-in-out ${fase(8, .3)} infinite}.ef-pf-$ID .fa1{top:0}.ef-pf-$ID .fa2{bottom:0}`
                + `.ef-pf-$ID .em{position:absolute;left:0;right:0;top:44%;text-align:center;font:900 13cqw/1 'Times New Roman',serif;letter-spacing:.04em;color:#fff;text-shadow:0 0 14px #e5201a,2px 2px 0 #7a0a08;opacity:0;animation:k-$ID-em 8s steps(1,end) ${fase(8, .3)} infinite}`
                + `.ef-pf-$ID .lg{position:absolute;right:6%;bottom:8%;width:26cqw;aspect-ratio:${f1(R.proporcao(T, 'nerv') * 100) / 100};background:url('${R.url(T, 'nerv')}') center/contain no-repeat;opacity:.6}`
                + '@keyframes k-$ID-hz{from{opacity:.12}to{opacity:.42}}@keyframes k-$ID-fa{0%,15%{opacity:0;background-position:0 0}22%,70%{opacity:1;background-position:40px 0}80%,100%{opacity:0;background-position:80px 0}}@keyframes k-$ID-em{0%,24%{opacity:0}26%,32%{opacity:1}34%,40%{opacity:0}42%,50%{opacity:1}52%,100%{opacity:0}}' },
            { k: 'borda', cor: VER, alfa: .6, blur: 40, esp: 5, dur: 1.2 },
        ], { r: 'epico', id: 'nrv_alerta_de_anjo' }),
        ...apoio({
            tema: T, r: 'epico',
            nome: { nomeItem: 'Piloto da NERV', desc: 'Vermelho de alerta com contorno preto, no peso de um título de abertura.', grad: [VER, LAR, VER], mov: 'pisca', dur: 1.6, piscaMin: .6, contorno: NEG, cw: 1.2, fonte: 'classica', espaco: 1.2 },
            placa: { nomeItem: 'Centro de Comando', desc: 'Preto com hexágonos vermelhos e a folha da NERV do lado.', base: [NEG, '#2a0606'], pad: { tipo: 'favo', c1: 'rgba(229,32,26,.55)', c2: 'transparent', tam: 8, lw: 1 }, mov: 'x', dur: 10, borda: VER, img: { nome: 'nerv', lado: 'dir', tam: 120, y: 50 } },
            faixa: { nomeItem: 'Sala de Controle', desc: 'Hexágonos em vermelho sobre o preto, faixas de alerta correndo na base e a logo da NERV.', fundo: [NEG, '#2a0606', '#5a0a0a'],
                longe: { svg: `<rect x='0' y='96' width='340' height='16' fill='#0a0a0e'/>${Array.from({ length: 24 }, (_, k) => `<path d='M${k * 28} 96L${k * 28 + 14} 96L${k * 28 + 28} 112L${k * 28 + 14} 112Z' fill='#e5201a'/>`).join('')}`, anim: 'pan', dur: 6 },
                perto: { svg: P.cena.icones({ nomes: ['hexagono'], pals: [{ m: '#ff8a2a', o: '#ff8a2a', w: 1 }], n: 8, tam: [10, 22], seed: 'nrv1', y: [6, 90] }), anim: 'pisca', dur: 1.8 },
                css: `.banner-anim-$ID::before{content:'';position:absolute;right:5%;top:8%;height:76%;aspect-ratio:${f1(R.proporcao(T, 'nerv') * 100) / 100};background:${R.css(T, 'nerv')} center/contain no-repeat;pointer-events:none;opacity:.9}` },
            fala: { nomeItem: 'Sincronização', desc: 'Quando você fala na call, o card pisca em vermelho e laranja, como a taxa de sincronização subindo.', cores: [VER, LAR], passos: true, dur: .5 },
            radar: { nomeItem: 'Campo AT', desc: 'As ondas do radar viram anéis duplos de laranja, como um campo AT.', cor: LAR, estilo: 'duplo', glow: VER },
            chat: { nomeItem: 'Hexágonos', desc: 'Ao digitar a barra de mensagem acende em laranja, e ao enviar hexágonos se abrem sobre ela.', cor: LAR, cor2: VER, particula: { forma: 'quadrado' } },
            som: { nomeItem: 'Alerta Vermelho', desc: 'A sirene de emergência soando duas vezes, ao entrar na call.', arquivo: 'eva_alerta.mp3', notas: [{ t: 0, f: 880, d: .22, tipo: 'square', v: .4 }, { t: .25, f: 660, d: .22, tipo: 'square', v: .4 }, { t: .55, f: 880, d: .22, tipo: 'square', v: .4 }, { t: .8, f: 660, d: .22, tipo: 'square', v: .4 }], ruidos: [] },
            pin: { nomeItem: 'Lança de Longinus', desc: 'Suas notas no mapa viram a Lança de Longinus, em diagonal.', img: 'lanca_pin', bal: 0 },
            serv: { nomeItem: 'Servidor da NERV', desc: 'O ícone do servidor pisca em vermelho e laranja como um alarme.', cores: [VER, LAR], passos: true, dur: .6 },
            pagina: { nomeItem: 'Lança e Alerta', desc: 'Segure o botão esquerdo e o direito juntos e você lança a Lança de Longinus onde mirou, quebrando o campo AT. Fique parado muito tempo e soa o alerta de Anjo, com a contagem do tempo de energia.', preset: 'eva', espera: 30, limite: 60 },
        }),
    ],
});
// o efeito de chat da NERV usa hexágonos (e não quadrados): o recorte do kit é trocado depois
nerv.itens.forEach((it) => { if (it.tipo === 'efeito_chat') it.extra = '.ef-envio-$ID i{clip-path:polygon(25% 6%,75% 6%,100% 50%,75% 94%,25% 94%,0 50%)!important;border-radius:0!important;min-width:12px;min-height:12px;background:#ff8a2a!important}.ef-envio-$ID i:nth-child(even){background:#e5201a!important}'; });

module.exports = [nerv];
