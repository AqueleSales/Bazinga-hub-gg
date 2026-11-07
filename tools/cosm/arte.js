'use strict';
/* BIBLIOTECA DE ARTE POR CÓDIGO (Rodada 40). Só SÍMBOLOS e OBJETOS que lembram cada obra (motosserra, granada, zíper, joaninha, tambor, cápsula, fita, olhos, chifres, katana...).
   O dono mandou TIRAR os personagens ("ficou muito meme") e deixar só as referências deles: bonecos, bustos, Stands e rostos NÃO entram aqui.
   Registro: def(tema, nome, largura, altura, svgInterno, defs). raster.js expõe isto (R.url / R.css / R.proporcao) e dá PRIORIDADE a um arquivo
   app/static/img/cosm/<tema>/<nome>.png quando ele existe (a Lança de Longinus e os ゴゴゴ são imagens de verdade).
   Regras: só aspas simples nos atributos; formas simples e bem contornadas (a peça aparece pequena: avatar, placa, pin). */
const B = require('./base');
const { f1 } = B;

const REG = {};
function def(tema, nome, w, h, inner, defs = '') {
    REG[`${tema}/${nome}`] = { tema, nome, w, h, svg: `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 ${w} ${h}'>${defs ? `<defs>${defs}</defs>` : ''}${inner}</svg>` };
}
const grad = (id, c1, c2, x2 = 0, y2 = 1, meio) => `<linearGradient id='${id}' x1='0' y1='0' x2='${x2}' y2='${y2}'><stop offset='0' stop-color='${c1}'/>${meio ? `<stop offset='.5' stop-color='${meio}'/>` : ''}<stop offset='1' stop-color='${c2}'/></linearGradient>`;
const rad = (id, c1, c2, cx = .4, cy = .35) => `<radialGradient id='${id}' cx='${cx}' cy='${cy}' r='.8'><stop offset='0' stop-color='${c1}'/><stop offset='1' stop-color='${c2}'/></radialGradient>`;
const K = '#14141c';

// ================================================================================================ CHAINSAW MAN
def('chainsaw', 'motosserra', 140, 60,
    // a motosserra: corpo preto com a faixa vermelha e o cabo, lâmina de aço com a corrente de dentes
    `<path d='M16 14Q16 2 30 2H50' fill='none' stroke='#0c0c12' stroke-width='6' stroke-linecap='round'/><rect x='2' y='12' width='56' height='42' rx='9' fill='#16161e' stroke='#0a0a10' stroke-width='2.4'/><rect x='10' y='22' width='38' height='8' rx='2' fill='#e5001f'/><circle cx='20' cy='42' r='5' fill='#3a3a48'/><path d='M30 38h22' stroke='#3a3a48' stroke-width='2'/>`
    + `<path d='M52 20H124Q138 30 124 42H52Z' fill='url(#s)' stroke='#1a1a22' stroke-width='2' stroke-linejoin='round'/><path d='M58 26H118Q126 31 118 36H58Z' fill='#505b70'/>`
    + `<path d='M52 20H124Q138 30 124 42H52Z' fill='none' stroke='#101018' stroke-width='4.4' stroke-dasharray='3.2 2.6' stroke-linejoin='round'/><path d='M52 20H124Q138 30 124 42H52Z' fill='none' stroke='#8795ad' stroke-width='1.2' stroke-dasharray='3.2 2.6' stroke-linejoin='round'/>`,
    grad('s', '#f4f8fd', '#6b788f', 0, 1, '#aebbd0'));

// a mesma motosserra, na diagonal dentro de um quadrado (pino do mapa e ícones pequenos)
def('chainsaw', 'motosserra_pin', 100, 100,
    `<g transform='translate(50 50) rotate(-34)'><svg x='-47' y='-20.2' width='94' height='40.3' viewBox='0 0 140 60'>${REG['chainsaw/motosserra'].svg.replace(/^<svg[^>]*>/, '').replace(/<\/svg>$/, '')}</svg></g>`);

def('chainsaw', 'granada', 60, 90,
    // uma granada de mão: corpo verde-escuro quadriculado, tampa, alavanca e a argola do pino
    `<path d='M30 4Q42 4 42 14V20H18V14Q18 4 30 4Z' fill='#9aa4b8' stroke='${K}' stroke-width='2.2' stroke-linejoin='round'/><path d='M40 12Q54 8 56 20L54 34' fill='none' stroke='${K}' stroke-width='5' stroke-linecap='round'/><path d='M40 12Q54 8 56 20L54 34' fill='none' stroke='#cfd4de' stroke-width='2.4' stroke-linecap='round'/>`
    + `<circle cx='12' cy='14' r='7' fill='none' stroke='${K}' stroke-width='4.4'/><circle cx='12' cy='14' r='7' fill='none' stroke='#cfd4de' stroke-width='2.2'/>`
    + `<ellipse cx='30' cy='54' rx='24' ry='32' fill='url(#g)' stroke='${K}' stroke-width='2.6'/>${[0, 1, 2, 3].map((k) => `<path d='M${10 + k * 0} ${34 + k * 12}Q30 ${40 + k * 12} 50 ${34 + k * 12}' fill='none' stroke='#14200e' stroke-width='1.6'/>`).join('')}${[18, 30, 42].map((x) => `<path d='M${x} 24Q${x + (x - 30) * .3} 54 ${x} 84' fill='none' stroke='#14200e' stroke-width='1.6'/>`).join('')}`,
    rad('g', '#7a8a52', '#2a361a', .35, .3));

def('chainsaw', 'reze_flor', 80, 80,
    // uma gérbera vermelha (a flor da Reze)
    `${Array.from({ length: 16 }, (_, k) => `<ellipse cx='40' cy='17' rx='4.6' ry='15' fill='${k % 2 ? '#ff3b3b' : '#e0202a'}' stroke='#7a0a14' stroke-width='.8' transform='rotate(${k * 22.5} 40 40)'/>`).join('')}<circle cx='40' cy='40' r='9' fill='#3a1a10'/><circle cx='40' cy='40' r='5' fill='#ffd04a'/>`);

const aneis = (cx, cy, r, c1, c2) => `${[1, .78, .56, .34].map((k, i) => `<circle cx='${cx}' cy='${cy}' r='${f1(r * k)}' fill='${i % 2 ? c2 : c1}' stroke='#3a1a08' stroke-width='.8'/>`).join('')}<circle cx='${cx}' cy='${cy}' r='${f1(r * .12)}' fill='#1a0a08'/>`;
def('chainsaw', 'makima_olhos', 100, 60, `<g>${aneis(28, 30, 22, '#f2c230', '#c8802a')}${aneis(72, 30, 22, '#f2c230', '#c8802a')}</g>`);

def('chainsaw', 'power_chifres', 100, 60,
    `<path d='M20 56Q4 40 14 8Q20 30 34 44Z' fill='#d8262a' stroke='#5a0a0a' stroke-width='2' stroke-linejoin='round'/><path d='M80 56Q96 40 86 8Q80 30 66 44Z' fill='#d8262a' stroke='#5a0a0a' stroke-width='2' stroke-linejoin='round'/>`);

const katana = `<path d='M4 12L112 8L118 12L112 14Z' fill='#e8eef6' stroke='#2a303c' stroke-width='1.4' stroke-linejoin='round'/><path d='M8 12L112 11' stroke='#8fa0b8' stroke-width='.8'/><ellipse cx='122' cy='11' rx='4' ry='7' fill='#c8a038' stroke='#4a360a' stroke-width='1.4'/><rect x='126' y='8' width='32' height='7' rx='2' fill='#16161e'/>${[0, 1, 2, 3, 4].map((k) => `<path d='M${130 + k * 6} 8L${133 + k * 6} 15' stroke='#c8a038' stroke-width='1.2'/>`).join('')}`;
def('chainsaw', 'aki_katana', 160, 24, katana);
def('chainsaw', 'aki_katana_pin', 100, 100, `<g transform='translate(50 50) rotate(-38) scale(.58) translate(-80 -12)'>${katana}</g>`);

// ================================================================================================ JOJO
def('jojo', 'joaninha', 100, 100,
    // o broche: disco rosa com dentes de engrenagem dos lados, as duas meias-luas da cabeça, o naipe escuro no meio e a bolinha
    `<circle cx='50' cy='52' r='42' fill='#ff1a8c'/>${[[7, 40], [7, 64], [93, 40], [93, 64], [14, 22], [86, 22]].map(([x, y]) => `<circle cx='${x}' cy='${y}' r='8' fill='#1b1b22'/>`).join('')}`
    + `<path d='M20 16Q36 4 46 12Q34 14 20 16ZM80 16Q64 4 54 12Q66 14 80 16Z' fill='#ff1a8c'/><circle cx='50' cy='12' r='6' fill='#ff1a8c'/>`
    + `<path d='M50 36C38 40 32 50 34 60C36 68 46 70 50 76C54 70 64 68 66 60C68 50 62 40 50 36Z' fill='#1b1b22'/><path d='M49 74H51V96H49Z' fill='#1b1b22'/><circle cx='50' cy='13' r='3' fill='#1b1b22'/>`);

(() => {
    // ゴ desenhado com traços (reserva: o shader e os temas usam a IMAGEM de verdade quando o arquivo existe)
    const glifo = (x, y, s) => `<g transform='translate(${x} ${y}) scale(${s}) skewX(-12)'><path d='M8 12H40V44H8' fill='none' stroke='#14061e' stroke-width='14' stroke-linejoin='miter'/><path d='M44 2L52 12M36 2L44 12' stroke='#14061e' stroke-width='11' stroke-linecap='butt'/>`
        + `<path d='M8 12H40V44H8' fill='none' stroke='url(#g)' stroke-width='8' stroke-linejoin='miter'/><path d='M44 3L51 11M36 3L43 11' stroke='url(#g)' stroke-width='5.4' stroke-linecap='butt'/></g>`;
    def('jojo', 'gogogo', 100, 150, [[8, 4, 1], [34, 30, .84], [10, 66, .64], [40, 88, .52], [18, 118, .38]].map(([x, y, s]) => glifo(x, y, s)).join(''), grad('g', '#c43aa0', '#5a2a9a', 0, 1));
})();

def('jojo', 'ziper', 40, 120,
    // um zíper vertical: duas fileiras de dentes dourados, a fita de pano e o puxador no alto
    `<rect x='6' y='14' width='28' height='104' rx='3' fill='#e8ecf4' stroke='#9aa6c0' stroke-width='1.2'/>${Array.from({ length: 16 }, (_, k) => `<rect x='${k % 2 ? 20 : 12}' y='${22 + k * 6}' width='8' height='4.4' rx='1' fill='#e8b94a' stroke='#6b4a10' stroke-width='.8'/>`).join('')}`
    + `<path d='M12 4H28L26 16H14Z' fill='#f3d27a' stroke='#6b4a10' stroke-width='1.6' stroke-linejoin='round'/><rect x='17' y='0' width='6' height='5' rx='2' fill='#6b4a10'/>`);
def('jojo', 'ziper_aberto', 100, 60,
    // a abertura de um zíper: dentes dourados dos dois lados, o escuro de dentro e o puxador
    `<path d='M6 38Q8 6 56 8Q94 10 96 30Q60 18 38 44Q22 56 6 38Z' fill='#0a1030'/><path d='M6 38Q8 6 56 8Q94 10 96 30' fill='none' stroke='#e8b94a' stroke-width='3.4' stroke-dasharray='4 3'/><path d='M96 30Q60 18 38 44Q22 56 6 38' fill='none' stroke='#e8b94a' stroke-width='3.4' stroke-dasharray='4 3'/>`
    + `<path d='M96 30L90 42L100 40Z' fill='#e8b94a' stroke='#6b4a10' stroke-width='1.4'/><circle cx='93' cy='47' r='5' fill='#e8b94a' stroke='#6b4a10' stroke-width='1.6'/><circle cx='93' cy='47' r='2' fill='#14203a'/>${[[34, 14], [50, 10], [66, 14], [44, 22], [60, 20], [76, 22]].map(([x, y]) => `<circle cx='${x}' cy='${y}' r='1' fill='#fff' opacity='.8'/>`).join('')}`);
def('jojo', 'bala', 30, 70,
    // uma bala dourada de revólver (cobre na ponta)
    `<path d='M15 2Q26 14 26 28V62H4V28Q4 14 15 2Z' fill='url(#b)' stroke='#6b4a10' stroke-width='2' stroke-linejoin='round'/><path d='M15 2Q26 14 26 28H4Q4 14 15 2Z' fill='#c8742a' stroke='#6b4a10' stroke-width='2' stroke-linejoin='round'/><path d='M4 36H26M4 56H26' stroke='#6b4a10' stroke-width='1.6'/><path d='M9 32V58' stroke='#fff2b0' stroke-width='2' stroke-linecap='round' opacity='.7'/>`,
    grad('b', '#f2d870', '#c8a028', 1, 0));
def('jojo', 'capsula_obj', 100, 50,
    // a cápsula do vírus (metade vermelha, metade roxa) com reflexo
    `<rect x='4' y='8' width='92' height='34' rx='17' fill='#e03a5a' stroke='#3a0a18' stroke-width='3'/><path d='M50 8H79A17 17 0 0 1 79 42H50Z' fill='#8e4ad8' stroke='#3a0a18' stroke-width='3' stroke-linejoin='round'/><path d='M16 16H44' stroke='#ff9aa8' stroke-width='3' stroke-linecap='round'/><path d='M56 16H76' stroke='#c8a0f8' stroke-width='3' stroke-linecap='round'/>`);
def('jojo', 'coracao_rosa', 100, 90,
    // um coração rosa-choque com brilho
    `<path d='M50 84C20 62 4 46 4 28C4 14 14 6 26 6C36 6 44 12 50 22C56 12 64 6 74 6C86 6 96 14 96 28C96 46 80 62 50 84Z' fill='#ff8ac8' stroke='#9a2a78' stroke-width='3.2' stroke-linejoin='round'/><path d='M18 24Q20 14 30 14' fill='none' stroke='#ffe0f2' stroke-width='4' stroke-linecap='round'/>`);
def('jojo', 'fita', 100, 100,
    // o carretel de uma fita cassete: aro, seis furos e o miolo
    `<circle cx='50' cy='50' r='44' fill='#1a1a24' stroke='#9aa4b8' stroke-width='4'/><circle cx='50' cy='50' r='30' fill='none' stroke='#5a6480' stroke-width='2.4'/>${[0, 1, 2, 3, 4, 5].map((k) => `<circle cx='${f1(50 + 20 * Math.cos(k * 1.0472))}' cy='${f1(50 + 20 * Math.sin(k * 1.0472))}' r='6' fill='#c8ccd8'/>`).join('')}<circle cx='50' cy='50' r='7' fill='#6a8ad8'/><path d='M6 50Q10 20 40 8' fill='none' stroke='#7a5a4a' stroke-width='3' stroke-linecap='round'/>`);
def('jojo', 'stand_aerosmith', 120, 60,
    // o avião do Aerosmith visto de lado: fuselagem vermelha com faixa branca, asa, cauda, hélice e as metralhadoras
    `<path d='M14 30L2 22L4 38Z' fill='#c8302a' stroke='#4a0a0a' stroke-width='1.6'/><path d='M14 30L8 12L26 26Z' fill='#f4f4f4' stroke='#4a0a0a' stroke-width='1.6'/>`
    + `<ellipse cx='60' cy='32' rx='46' ry='11' fill='#c8302a' stroke='#4a0a0a' stroke-width='2'/><path d='M30 28H92V34H30Z' fill='#f4f4f4' opacity='.92'/><path d='M44 24Q58 12 76 24Z' fill='#9ad4f4' stroke='#4a0a0a' stroke-width='1.6'/>`
    + `<path d='M44 34L62 52L78 52L66 34Z' fill='#f4f4f4' stroke='#4a0a0a' stroke-width='1.6' stroke-linejoin='round'/><path d='M44 28L62 8L80 8L68 28Z' fill='#c8302a' stroke='#4a0a0a' stroke-width='1.6' stroke-linejoin='round'/>`
    + `<path d='M70 16V4M70 48V58' stroke='#4a0a0a' stroke-width='2.4'/><circle cx='106' cy='32' r='5.4' fill='#f2c230' stroke='#4a0a0a' stroke-width='1.6'/><ellipse cx='110' cy='32' rx='3' ry='18' fill='#9aa4b8' opacity='.55'/><path d='M96 38L112 40M96 26L112 24' stroke='#4a0a0a' stroke-width='2' stroke-linecap='round'/>`
    + `<circle cx='34' cy='44' r='3.6' fill='#14080a'/>`);

// ================================================================================================ HOMEM-ARANHA
def('aranha', 'aranha_emblema', 100, 100,
    // o emblema da aranha preta (corpo comprido, cabeça pequena e oito pernas finas e longas), com um contorno claro pra aparecer em fundo escuro
    `<g fill='none' stroke='#f4f4fa' stroke-width='6.4' stroke-linecap='round' stroke-linejoin='round'>${legs()}</g><g fill='none' stroke='#0c0c12' stroke-width='3.6' stroke-linecap='round' stroke-linejoin='round'>${legs()}</g>`
    + `<ellipse cx='50' cy='58' rx='9' ry='17' fill='#0c0c12' stroke='#f4f4fa' stroke-width='1.6'/><ellipse cx='50' cy='38' rx='6' ry='7' fill='#0c0c12' stroke='#f4f4fa' stroke-width='1.6'/>`);
function legs() {
    return '<path d=\'M44 36Q28 26 14 30L6 18\'/><path d=\'M44 42Q26 38 10 50L4 46\'/><path d=\'M44 54Q24 54 12 70L6 88\'/><path d=\'M46 68Q32 74 28 94\'/>'
        + '<path d=\'M56 36Q72 26 86 30L94 18\'/><path d=\'M56 42Q74 38 90 50L96 46\'/><path d=\'M56 54Q76 54 88 70L94 88\'/><path d=\'M54 68Q68 74 72 94\'/>';
}
def('aranha', 'teias', 100, 100,
    `<g fill='none' stroke='#f4f4fa' stroke-width='1.8' stroke-linecap='round'>${Array.from({ length: 12 }, (_, k) => { const a = k / 12 * 6.2832; return `<path d='M50 50L${f1(50 + 48 * Math.cos(a))} ${f1(50 + 48 * Math.sin(a))}'/>`; }).join('')}${[12, 22, 33, 44].map((r) => Array.from({ length: 12 }, (_, k) => { const a = k / 12 * 6.2832, b = (k + 1) / 12 * 6.2832, m = (a + b) / 2; return `<path d='M${f1(50 + r * Math.cos(a))} ${f1(50 + r * Math.sin(a))}Q${f1(50 + r * .86 * Math.cos(m))} ${f1(50 + r * .86 * Math.sin(m))} ${f1(50 + r * Math.cos(b))} ${f1(50 + r * Math.sin(b))}'/>`; }).join('')).join('')}</g>`);

// ================================================================================================ EVANGELION
def('eva', 'nerv', 100, 118,
    // a folha da NERV (lóbulos à direita, corte em diagonal) e as letras NE / RV em serifa, no mesmo vermelho
    `<path d='M22 12L42 36Q50 18 70 12Q96 8 98 30Q88 38 96 48Q100 66 90 76Q84 82 88 94L90 108L46 66Q30 40 22 12Z' fill='#ff1010'/>`
    + `<text x='4' y='72' font-family='Times New Roman,Georgia,serif' font-size='40' font-weight='700' fill='#ff1010'>NE</text><text x='46' y='108' font-family='Times New Roman,Georgia,serif' font-size='40' font-weight='700' fill='#ff1010'>RV</text>`);
const lancaCorpo = `<path d='M2 8L136 6.6L136 9.4Z' fill='#6a1818' stroke='#2a0808' stroke-width='.8'/><path d='M136 8C142 2 150 14 156 8C162 2 168 14 174 8' fill='none' stroke='#b02020' stroke-width='2.4'/><path d='M136 8C142 14 150 2 156 8C162 14 168 2 174 8' fill='none' stroke='#7a1212' stroke-width='2.4'/><path d='M174 8L184 3L198 1L190 6L178 8ZM174 8L184 13L198 15L190 10L178 8Z' fill='#b02020' stroke='#2a0808' stroke-width='1' stroke-linejoin='round'/>`;
def('eva', 'lanca', 200, 16, lancaCorpo);                                      // reserva: o tema usa a IMAGEM (app/static/img/cosm/eva/lanca.png)
def('eva', 'lanca_pin', 100, 100, `<g transform='translate(50 50) rotate(-40) scale(.5) translate(-100 -8)'>${lancaCorpo}</g>`);
def('eva', 'eva_olho', 100, 60,
    // o olho único do Eva-00: visor escuro com o olho amarelo e a pupila
    `<path d='M4 26Q8 4 50 2Q92 4 96 26Q92 52 50 58Q8 52 4 26Z' fill='#1a2a4a' stroke='${K}' stroke-width='3'/><ellipse cx='50' cy='30' rx='30' ry='20' fill='#ffe86a' stroke='${K}' stroke-width='2.4'/><circle cx='50' cy='30' r='11' fill='${K}'/><circle cx='45' cy='25' r='4' fill='#fff'/><path d='M12 14Q50 -2 88 14' fill='none' stroke='#ff8a2a' stroke-width='3.4' stroke-linecap='round'/>`);
def('eva', 'eva_chifre', 60, 100,
    // o chifre do Eva-01: comprido, afilado, branco com a base laranja
    `<path d='M10 98Q8 50 30 2Q52 50 50 98Z' fill='#f4f4f8' stroke='${K}' stroke-width='3' stroke-linejoin='round'/><path d='M10 98Q10 80 12 70L48 70Q50 82 50 98Z' fill='#ff8a2a' stroke='${K}' stroke-width='3' stroke-linejoin='round'/><path d='M24 20Q16 50 18 66' fill='none' stroke='#cfd4de' stroke-width='3' stroke-linecap='round'/>`);
def('eva', 'eva_olhos4', 100, 60,
    // os quatro olhos amarelos inclinados do Eva-02 sobre o capacete vermelho
    `<rect x='2' y='4' width='96' height='52' rx='14' fill='#c42a1a' stroke='${K}' stroke-width='3'/><path d='M10 14L40 24L36 32L12 26ZM90 14L60 24L64 32L88 26ZM14 36L40 42L38 48L16 44ZM86 36L60 42L62 48L84 44Z' fill='#ffe86a' stroke='${K}' stroke-width='1.8' stroke-linejoin='round'/>`);

// ================================================================================================ CYBERPUNK EDGERUNNERS
def('edgerunners', 'sandevistan', 60, 100,
    // a coluna do implante Sandevistan: vértebras de metal com um brilho azul que corre
    `${Array.from({ length: 8 }, (_, k) => `<path d='M14 ${6 + k * 11.5}H46L42 ${14 + k * 11.5}H18Z' fill='#9aa4b8' stroke='${K}' stroke-width='1.6' stroke-linejoin='round'/><path d='M22 ${9 + k * 11.5}H38' stroke='#00e5ff' stroke-width='2' stroke-linecap='round'/>`).join('')}<path d='M30 4V98' stroke='#00e5ff' stroke-width='2.4' opacity='.55'/>`);
def('edgerunners', 'lua', 100, 100,
    `<path d='M62 8A42 42 0 1 0 90 66A34 34 0 1 1 62 8Z' fill='url(#l)' stroke='#8ad8e8' stroke-width='2'/><circle cx='28' cy='40' r='5' fill='#c8dce8' opacity='.7'/><circle cx='40' cy='64' r='3.4' fill='#c8dce8' opacity='.7'/><circle cx='24' cy='62' r='2.4' fill='#c8dce8' opacity='.7'/>`,
    grad('l', '#f4fbff', '#8ab8d0', 1, 1));
def('edgerunners', 'escopeta', 200, 44,
    // a escopeta da Rebecca vista de lado: coronha vazada (alça fechada), apoio de bochecha preto, corpo turquesa com duas faixas rosa na diagonal, furinhos de ventilação e a boca preta
    `<clipPath id='cb'><path d='M2 25L48 25L60 14L88 12L112 9L186 9L186 33L112 33L88 33L88 31L66 31L62 29L52 30L52 38Q52 42 48 42L8 42Q2 42 2 36Z'/></clipPath>`
    + `<path d='M2 25L48 25L60 14L88 12L112 9L186 9L186 33L112 33L88 33L88 31L66 31L62 29L52 30L52 38Q52 42 48 42L8 42Q2 42 2 36ZM10 31L44 31L44 36Q44 37 43 37L11 37Q10 37 10 36Z' fill='#3cc9aa' fill-rule='evenodd'/>`
    + `<g clip-path='url(#cb)'><path d='M68 44L82 44L100 4L86 4Z' fill='#e0407f'/><path d='M130 44L146 44L162 4L146 4Z' fill='#e0407f'/></g>`
    + `<rect x='112' y='32' width='76' height='7' rx='3.5' fill='#2fa88c' stroke='#14262a' stroke-width='1.4'/><rect x='186' y='8' width='9' height='15' rx='3' fill='#23262c' stroke='#14262a' stroke-width='1.2'/>`
    + `<path d='M20 25L40 25L48 17L34 15Z' fill='#2c3238' stroke='#14262a' stroke-width='1.2' stroke-linejoin='round'/><rect x='54' y='13' width='30' height='5' fill='#4a4f58' stroke='#14262a' stroke-width='1'/>`
    + `<g fill='#23262c'>${[0, 1, 2, 3, 4, 5, 6].map((k) => `<rect x='${116 + k * 9.5}' y='15' width='5.4' height='2' rx='1'/>`).join('')}${[0, 1, 2].map((k) => `<circle cx='${92 + k * 5}' cy='24' r='1.3'/>`).join('')}</g>`
    + `<path d='M62 31V37H74V31' fill='none' stroke='#14262a' stroke-width='2' stroke-linejoin='round'/>`
    + `<path d='M2 25L48 25L60 14L88 12L112 9L186 9L186 33L112 33L88 33L88 31L66 31L62 29L52 30L52 38Q52 42 48 42L8 42Q2 42 2 36ZM10 31L44 31L44 36Q44 37 43 37L11 37Q10 37 10 36Z' fill='none' stroke='#14262a' stroke-width='1.8' stroke-linejoin='round'/>`);
// a mesma escopeta, na diagonal dentro de um quadrado (pino do mapa)
def('edgerunners', 'escopeta_pin', 100, 100,
    `<g transform='translate(50 50) rotate(-30)'><svg x='-47' y='-10.4' width='94' height='20.8' viewBox='0 0 200 44'>${REG['edgerunners/escopeta'].svg.replace(/^<svg[^>]*>/, '').replace(/<\/svg>$/, '')}</svg></g>`);
def('edgerunners', 'smasher_olho', 100, 100,
    // o olho cibernético do Adam Smasher: placas de metal, mira em cruz e a pupila vermelha acesa
    `<circle cx='50' cy='50' r='46' fill='#2a2e38' stroke='${K}' stroke-width='3'/><circle cx='50' cy='50' r='36' fill='#14161e' stroke='#6a7080' stroke-width='2'/><path d='M50 4V16M50 84V96M4 50H16M84 50H96' stroke='#9aa4b8' stroke-width='3' stroke-linecap='round'/><circle cx='50' cy='50' r='22' fill='url(#r)' stroke='#7a0a0a' stroke-width='2'/><circle cx='50' cy='50' r='9' fill='#ffd0d0'/><circle cx='45' cy='45' r='3' fill='#fff'/>`,
    rad('r', '#ff6a6a', '#b01010', .5, .5));

module.exports = { REG, def, grad, rad };
