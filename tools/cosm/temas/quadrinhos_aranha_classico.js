'use strict';
/* HOMEM-ARANHA CLÁSSICO (Rodada 40, lendário): o traje vermelho e azul, a teia, o sentido de aranha, a cidade. Só símbolos e objetos por código
   (teia, emblema da aranha; o dono mandou tirar o boneco). Ids com prefixo `hma` (o tema "Teia" genérico, de prefixo `tei`, continua existindo). */
const { tema, MP, EA, EP, P, R, B, IMG, apoio, fase } = require('../dsl');
const f1 = B.f1;
const T = 'aranha';
const VER = '#d4161e', AZU = '#1a3aa0', BRA = '#f4f4fa';
const cena = P.cena;

/** teia de canto: raios e fios curvos a partir de um ponto (cx, cy) num quadro 160 */
const teiaCanto = (anim) => {
    const cx = 134, cy = 22, raios = [], arcos = [];
    const n = 7, a0 = 95, a1 = 185;
    for (let k = 0; k <= n; k++) { const a = (a0 + (a1 - a0) * k / n) * Math.PI / 180; raios.push(`M${cx} ${cy}L${f1(cx + 64 * Math.cos(a))} ${f1(cy + 64 * Math.sin(a))}`); }
    for (const r of [16, 28, 42, 56, 66]) for (let k = 0; k < n; k++) {
        const a = (a0 + (a1 - a0) * k / n) * Math.PI / 180, b = (a0 + (a1 - a0) * (k + 1) / n) * Math.PI / 180, m = (a + b) / 2;
        arcos.push(`M${f1(cx + r * Math.cos(a))} ${f1(cy + r * Math.sin(a))}Q${f1(cx + r * .88 * Math.cos(m))} ${f1(cy + r * .88 * Math.sin(m))} ${f1(cx + r * Math.cos(b))} ${f1(cy + r * Math.sin(b))}`);
    }
    return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.w{transform-origin:134px 22px;animation:v 4s ease-in-out infinite alternate}@keyframes v{from{transform:rotate(-2.5deg) scale(1)}to{transform:rotate(2.5deg) scale(1.03)}}</style>` : ''}<g class='w' fill='none' stroke-linecap='round'><g stroke='#000' stroke-opacity='.45' stroke-width='3.2'><path d='${raios.join('')}'/><path d='${arcos.join('')}'/></g><g stroke='#f4f4fa' stroke-width='1.5'><path d='${raios.join('')}'/><path d='${arcos.join('')}' stroke-width='1.2'/></g></g></svg>`;
};
const lentes = `<svg viewBox='0 0 100 100'><g fill='none' stroke='#fff' stroke-width='3' stroke-linecap='round'>${[-3, -2, -1, 0, 1, 2, 3].map((i) => { const a = -Math.PI / 2 + i * .26; return `<path d='M${f1(50 + 40 * Math.cos(a))} ${f1(50 + 40 * Math.sin(a))}L${f1(50 + 54 * Math.cos(a))} ${f1(50 + 54 * Math.sin(a))}'/>`; }).join('')}</g></svg>`;

const aranha = tema({
    id: 'aranha_classico', pre: 'hma', nome: 'Homem-Aranha', cat: 'quadrinhos', cor: VER, cores: [VER, AZU], icone: 'fa-spider', premium: true,
    lema: 'Com grandes poderes vêm grandes responsabilidades.',
    desc: 'O traje vermelho e azul, o sentido de aranha, a teia que sai nos dois botões do mouse e a cidade ao entardecer.',
    pal: { m: VER, a: '#ff6a6a', d: '#1a0a0a', l: '#fff', o: '#14141c' },
    itens: [
        MP('Teia de Canto', 'Uma teia grudada no canto da foto, balançando de leve.', { svg: teiaCanto }, { r: 'lendario' }),
        EA('Sentido de Aranha', 'O sentido de aranha vibra em volta da cabeça e uma teia gruda no canto da foto.', [
            { k: 'aura', cor: '#d4161e', dur: 1.3 },
            { k: 'raw', html: `<b class="$C"><svg viewBox="0 0 100 100" class="sa">${lentes}</svg></b>`,
              css: '.ef-av-$ID .sa{position:absolute;inset:0;width:100%;height:100%;overflow:visible;filter:drop-shadow(0 0 3px #d4161e);animation:k-$ID-sa .16s steps(2) infinite}@keyframes k-$ID-sa{0%{transform:translate(0,0) scale(1)}50%{transform:translate(.8px,-.8px) scale(1.03)}100%{transform:translate(-.8px,.8px) scale(.99)}}' },
        ], { r: 'lendario', id: 'hma_sentido_de_aranha', sobre: [{ k: 'teia', cor: BRA, rot: 18 }] }),
        EP('Cidade em Teias', 'Teias se desenham nos cantos do cartão e fios de teia caem, com a borda pulsando em vermelho.', [
            { k: 'raw', html: '<i class="tc t1"></i><i class="tc t2"></i>',
              css: `.ef-pf-$ID .tc{position:absolute;width:62%;aspect-ratio:1;background:url('${R.url(T, 'teias')}') center/contain no-repeat;opacity:0;animation:k-$ID-tc 9s ease-out ${fase(9, .3)} infinite}.ef-pf-$ID .t1{left:-6%;top:-4%;transform:rotate(0)}.ef-pf-$ID .t2{right:-8%;bottom:-6%;transform:rotate(180deg);animation-delay:-4s}`
                + '@keyframes k-$ID-tc{0%{opacity:0}12%{opacity:.7}70%{opacity:.7}90%,100%{opacity:0}}' },
            { k: 'cai', icones: ['teia'], pals: [{ m: '#f4f4fa' }], n: 7, tam: [14, 24], vel: [8, 14], alfa: .8 },
            { k: 'borda', cor: VER, alfa: .45, blur: 36, esp: 4, dur: 2.2 },
        ], { r: 'lendario', id: 'hma_cidade_em_teias' }),
        ...apoio({
            tema: T,
            nome: { nomeItem: 'Amigão da Vizinhança', desc: 'Vermelho e azul de uniforme com contorno branco e uma teia no fim do nome.', grad: [VER, AZU, VER], mov: 'desliza', dur: 4.4, contorno: '#ffffff', cw: .9, fonte: 'impacto', icone: { nome: 'teia', pos: 'depois', pal: { m: '#ffffff' } } },
            placa: { nomeItem: 'Malha', desc: 'A malha vermelha do traje com teias pretas e o emblema da aranha do lado.', base: [VER, '#a00f16'], pad: { tipo: 'icones', icones: ['teia'], pals: [{ m: '#2a0408', a: '#2a0408', d: '#2a0408', l: '#2a0408', o: '#2a0408', w: 0 }], tam: 30, ti: 22, c2: 'transparent' }, mov: 'x', dur: 24, borda: '#000', img: { nome: 'aranha_emblema', lado: 'dir', tam: 92, y: 50 } },
            faixa: { nomeItem: 'Nova York ao Entardecer', desc: 'A cidade em silhueta num pôr do sol laranja.', fundo: ['#1a2a6a', '#d4561e', '#ffb04a'],
                fixo: `${cena.sol({ x: 250, y: 66, r: 24, c1: '#ffe9a0', c2: '#ff8a2a' })}${cena.skyline({ cor: '#14102a', altMin: 26, altMax: 74, larg: [10, 22], seed: 'hma1', janelas: { cor: '#ffd070', dens: .3 } })}`,
                 },
            fala: { nomeItem: 'Sentido de Aranha', desc: 'Quando você fala na call, o card pisca em vermelho e azul.', cores: [VER, AZU], passos: true, dur: .4 },
            radar: { nomeItem: 'Fios de Teia', desc: 'As ondas do radar viram anéis brancos finos, como fios de teia.', cor: BRA, estilo: 'liso', glow: VER },
            chat: { nomeItem: 'Thwip', desc: 'A barra de mensagem acende em vermelho ao digitar e solta teias ao enviar.', cor: VER, cor2: AZU, particula: { icone: 'teia', pal: { m: '#f4f4fa' } } },
            som: { nomeItem: 'Thwip!', desc: 'O estalo seco do lançador de teia e o sopro do balanço, ao entrar na call.', arquivo: 'aranha_thwip.mp3', notas: [{ t: 0, f: 1400, f2: 300, d: .09, tipo: 'square', v: .5 }, { t: .1, f: 400, f2: 900, d: .4, tipo: 'sine', v: .2 }], ruidos: [{ t: 0, d: .08, f: 5000, filtro: 'highpass', v: .6 }, { t: .08, d: .5, f: 300, f2: 2400, filtro: 'bandpass', v: .35, q: 1.4 }] },
            pin: { nomeItem: 'Aranha', desc: 'Suas notas no mapa viram o emblema da aranha.', img: 'aranha_emblema' },
            serv: { nomeItem: 'Servidor da Vizinhança', desc: 'O ícone do servidor pisca em vermelho e azul.', cores: [VER, AZU], passos: true, dur: .7 },
            pagina: { nomeItem: 'Sentido e Teia', desc: 'Fique parado um tempo e a tela vibra com o sentido de aranha. Segure o botão esquerdo e o direito do mouse juntos e você solta teia onde estiver mirando.', preset: 'aranha', espera: 18 },
        }),
    ],
});

module.exports = [aranha];
