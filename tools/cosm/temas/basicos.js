'use strict';
/* BÁSICOS (completa o tema que já existia): TODAS as cores lisas em moldura, nome, placa e faixa, mais os padrões simples (listras, xadrez, bolinhas,
   zigue-zague, quadriculado, ondas) e degradês. Tudo comum, parado e barato. */
const { tema, M, N, Pl, F, B } = require('../dsl');

// (nome, hex, tipo) em três famílias: vivas, pastel e escuras
const CORES = [
    ['Vermelho', '#e53935'], ['Laranja', '#fb8c00'], ['Amarelo', '#fdd835'], ['Verde', '#43a047'], ['Ciano', '#00acc1'], ['Azul', '#1e88e5'],
    ['Roxo', '#8e24aa'], ['Rosa', '#ec407a'], ['Branco', '#f5f5f5'], ['Preto', '#212121'], ['Cinza', '#9e9e9e'],
    ['Rosa-bebê', '#f8bbd0'], ['Azul-bebê', '#bbdefb'], ['Menta', '#c8e6c9'], ['Lavanda', '#d1c4e9'], ['Pêssego', '#ffccbc'], ['Limão-claro', '#f0f4c3'],
    ['Vinho', '#7b1f2b'], ['Marinho', '#14285a'], ['Floresta', '#1b5e20'], ['Ameixa', '#4a148c'], ['Chocolate', '#4e342e'],
];
const luma = (hex) => { const n = parseInt(hex.slice(1), 16), c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]; };
const texto = (hex) => (luma(hex) > .35 ? '#14141a' : '#ffffff');
/** contorno de legibilidade: o nome claro precisa de contorno escuro (tema claro) e o escuro, de contorno claro (tema escuro) */
const contorno = (hex) => (luma(hex) < .12 ? { contorno: '#ffffff', cw: 1 } : luma(hex) > .8 ? { contorno: '#14141a', cw: .8 } : luma(hex) < .22 ? { contorno: '#e8e8f0', cw: .8 } : {});

const R = { r: 'comum' };
const parado = (it) => { it.animado = false; return it; };
const itens = [];

// ---- uma moldura, um nome, uma placa e uma faixa lisos por cor ----
CORES.forEach(([nome, hex]) => {
    itens.push(M(`Aro ${nome}`, `Um aro ${nome.toLowerCase()} liso em volta da foto.`, { t: 'liso', cor: hex }, R));
    itens.push(N(`Letra ${nome}`, `O nome em ${nome.toLowerCase()} liso.`, { cor: hex, peso: 800, ...contorno(hex) }, R));
    itens.push(Pl(`Fita ${nome}`, `Uma barra ${nome.toLowerCase()} lisa atrás do nome.`, { base: hex, mov: 'nenhum', texto: texto(hex) }, R));
    itens.push(parado(F(`Fundo ${nome}`, `Uma faixa ${nome.toLowerCase()} lisa, sem nada em cima.`, { fundo: [hex] }, R)));
});

// ---- padrões na placa (parados) ----
const PAD = [
    ['Listras Vermelhas', 'Listras diagonais vermelhas e brancas.', '#e53935', '#ffffff', { tipo: 'listras', tam: 14 }],
    ['Listras Azuis', 'Listras diagonais azuis e brancas.', '#1e88e5', '#ffffff', { tipo: 'listras', tam: 14 }],
    ['Listras Verdes', 'Listras diagonais verdes e brancas.', '#43a047', '#ffffff', { tipo: 'listras', tam: 14 }],
    ['Listras de Aviso', 'Listras diagonais amarelas e pretas, de fita de obra.', '#fdd835', '#212121', { tipo: 'listras', tam: 14 }],
    ['Xadrez Vermelho', 'Xadrez vermelho e branco de toalha de mesa.', '#e53935', '#ffffff', { tipo: 'xadrez', tam: 10 }],
    ['Xadrez Azul', 'Xadrez azul e branco.', '#1e88e5', '#ffffff', { tipo: 'xadrez', tam: 10 }],
    ['Xadrez Preto', 'Xadrez preto e branco.', '#212121', '#f5f5f5', { tipo: 'xadrez', tam: 10 }],
    ['Xadrez Verde', 'Xadrez verde e branco.', '#43a047', '#ffffff', { tipo: 'xadrez', tam: 10 }],
    ['Bolinhas Rosa', 'Bolinhas rosa sobre o branco.', '#ec407a', '#fff0f5', { tipo: 'bolinhas', tam: 9, r: .32 }],
    ['Bolinhas Azuis', 'Bolinhas azuis sobre o branco.', '#1e88e5', '#f0f6ff', { tipo: 'bolinhas', tam: 9, r: .32 }],
    ['Bolinhas Amarelas', 'Bolinhas amarelas sobre o branco.', '#fdd835', '#fffdf0', { tipo: 'bolinhas', tam: 9, r: .32 }],
    ['Bolinhas Pretas', 'Bolinhas pretas sobre o branco.', '#212121', '#f5f5f5', { tipo: 'bolinhas', tam: 9, r: .32 }],
    ['Zigue-zague Laranja', 'Zigue-zague laranja sobre o creme.', '#fb8c00', '#fff6e8', { tipo: 'zigzag', tam: 10 }],
    ['Zigue-zague Azul', 'Zigue-zague azul sobre o branco.', '#1e88e5', '#f0f6ff', { tipo: 'zigzag', tam: 10 }],
    ['Zigue-zague Roxo', 'Zigue-zague roxo sobre o lavanda.', '#8e24aa', '#f6eefa', { tipo: 'zigzag', tam: 10 }],
    ['Zigue-zague Preto', 'Zigue-zague preto sobre o branco.', '#212121', '#f5f5f5', { tipo: 'zigzag', tam: 10 }],
    ['Quadriculado Cinza', 'Quadriculado cinza de caderno.', '#9e9e9e', '#ffffff', { tipo: 'grade', tam: 12, lw: 1 }],
    ['Quadriculado Azul', 'Quadriculado azul de caderno.', '#1e88e5', '#ffffff', { tipo: 'grade', tam: 12, lw: 1 }],
    ['Quadriculado Verde', 'Quadriculado verde de caderno.', '#43a047', '#ffffff', { tipo: 'grade', tam: 12, lw: 1 }],
    ['Quadriculado Rosa', 'Quadriculado rosa de caderno.', '#ec407a', '#ffffff', { tipo: 'grade', tam: 12, lw: 1 }],
    ['Ondas Azuis', 'Ondinhas azuis sobre o azul-bebê.', '#1e88e5', '#e3f2fd', { tipo: 'ondas', tam: 12 }],
    ['Ondas Rosa', 'Ondinhas rosa sobre o rosa-bebê.', '#ec407a', '#fce4ec', { tipo: 'ondas', tam: 12 }],
];
PAD.forEach(([nome, desc, c1, c2, pad]) => {
    itens.push(Pl(nome, desc, { base: c2, pad: { ...pad, c1, c2: 'transparent' }, mov: 'nenhum', texto: texto(c2), borda: c1 }, R));
});

// ---- degradês na faixa (parados) ----
const DEG = [
    ['Degradê Fogo', 'Do vermelho ao laranja.', ['#e53935', '#fb8c00']], ['Degradê Sol', 'Do laranja ao amarelo.', ['#fb8c00', '#fdd835']], ['Degradê Limão', 'Do amarelo ao verde.', ['#fdd835', '#43a047']],
    ['Degradê Esmeralda', 'Do verde ao ciano.', ['#43a047', '#00acc1']], ['Degradê Oceano', 'Do ciano ao azul.', ['#00acc1', '#1e88e5']], ['Degradê Uva', 'Do azul ao roxo.', ['#1e88e5', '#8e24aa']],
    ['Degradê Flor', 'Do roxo ao rosa.', ['#8e24aa', '#ec407a']], ['Degradê Algodão-doce', 'Do rosa-bebê ao azul-bebê.', ['#f8bbd0', '#bbdefb']], ['Degradê Céu', 'Do azul-bebê ao branco.', ['#bbdefb', '#f5f5f5']],
    ['Degradê Menta', 'Do menta ao azul-bebê.', ['#c8e6c9', '#bbdefb']], ['Degradê Pêssego', 'Do pêssego ao rosa-bebê.', ['#ffccbc', '#f8bbd0']], ['Degradê Aurora', 'Do verde ao roxo.', ['#43a047', '#8e24aa']],
    ['Degradê Noite', 'Do azul-marinho ao preto.', ['#14285a', '#212121']], ['Degradê Brasa', 'Do vinho ao preto.', ['#7b1f2b', '#212121']], ['Degradê Cinza', 'Do cinza ao preto.', ['#9e9e9e', '#212121']],
    ['Degradê Chocolate', 'Do chocolate ao laranja.', ['#4e342e', '#fb8c00']],
];
DEG.forEach(([nome, desc, cores]) => itens.push(parado(F(nome, `Um degradê parado: ${desc.charAt(0).toLowerCase()}${desc.slice(1)}`, { fundo: cores, angulo: 100 }, R))));

// ---- padrões na faixa (parados): o ladrilho vira um SVG de página inteira ----
const faixaPadrao = (tipo, c1, c2) => {
    const pat = {
        listras: `<pattern id='p' width='20' height='20' patternUnits='userSpaceOnUse' patternTransform='rotate(45)'><rect width='10' height='20' fill='${c1}'/></pattern>`,
        xadrez: `<pattern id='p' width='28' height='28' patternUnits='userSpaceOnUse'><rect width='14' height='14' fill='${c1}'/><rect x='14' y='14' width='14' height='14' fill='${c1}'/></pattern>`,
        zigzag: `<pattern id='p' width='28' height='16' patternUnits='userSpaceOnUse'><path d='M0 12L14 4 28 12' fill='none' stroke='${c1}' stroke-width='3' stroke-linejoin='round'/></pattern>`,
        bolinhas: `<pattern id='p' width='24' height='24' patternUnits='userSpaceOnUse'><circle cx='6' cy='6' r='4' fill='${c1}'/><circle cx='18' cy='18' r='4' fill='${c1}'/></pattern>`,
        grade: `<pattern id='p' width='14' height='14' patternUnits='userSpaceOnUse'><path d='M0 0H14M0 0V14' stroke='${c1}' stroke-width='1.2'/></pattern>`,
    }[tipo];
    return `<defs>${pat}</defs><rect width='340' height='112' fill='${c2}'/><rect width='340' height='112' fill='url(#p)'/>`;
};
[
    ['Faixa Listrada Vermelha', 'Listras diagonais vermelhas e brancas, paradas.', 'listras', '#e53935', '#ffffff'], ['Faixa Listrada Azul', 'Listras diagonais azuis e brancas, paradas.', 'listras', '#1e88e5', '#ffffff'],
    ['Faixa Listrada Preta', 'Listras diagonais pretas e amarelas, paradas.', 'listras', '#212121', '#fdd835'],
    ['Faixa Xadrez Vermelha', 'Xadrez vermelho e branco, parado.', 'xadrez', '#e53935', '#ffffff'], ['Faixa Xadrez Preta', 'Xadrez preto e branco, parado.', 'xadrez', '#212121', '#f5f5f5'],
    ['Faixa Xadrez Verde', 'Xadrez verde e branco, parado.', 'xadrez', '#43a047', '#ffffff'],
    ['Faixa Zigue-zague Azul', 'Zigue-zague azul sobre o branco, parado.', 'zigzag', '#1e88e5', '#f0f6ff'], ['Faixa Zigue-zague Laranja', 'Zigue-zague laranja sobre o creme, parado.', 'zigzag', '#fb8c00', '#fff6e8'],
    ['Faixa Bolinhas Rosa', 'Bolinhas rosa sobre o branco, paradas.', 'bolinhas', '#ec407a', '#fff0f5'], ['Faixa Bolinhas Azuis', 'Bolinhas azuis sobre o branco, paradas.', 'bolinhas', '#1e88e5', '#f0f6ff'],
    ['Faixa Quadriculada Cinza', 'Quadriculado cinza de caderno, parado.', 'grade', '#9e9e9e', '#ffffff'], ['Faixa Quadriculada Azul', 'Quadriculado azul de caderno, parado.', 'grade', '#1e88e5', '#ffffff'],
].forEach(([nome, desc, tipo, c1, c2]) => itens.push(parado(F(nome, desc, { fundo: [c2], fixo: faixaPadrao(tipo, c1, c2) }, R))));

module.exports = [tema({
    id: 'basicos', pre: 'bas', nome: 'Básicos', cat: 'basico', cor: '#9aa3b2', cores: ['#9aa3b2', '#5b6475'], icone: 'fa-circle', existente: true,
    lema: 'A cor que você quiser, sem enfeite.', desc: 'Todas as cores lisas, em versão viva, pastel e escura, mais listras, xadrez, bolinhas, zigue-zague, quadriculado e degradês: simples, parado e barato.',
    itens,
})];
