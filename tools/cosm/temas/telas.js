'use strict';
/* SHADERS DE TELA (Rodada 40): os efeitos de página inteira que não pertencem a um personagem. Só o computador; ver static/js/shaders.js.
   Cyberpunk Edgerunners: só a cyberpsicose (os temas de cada personagem ficam em anime_edgerunners.js). */
const { tema, PAGINA } = require('../dsl');

const edge = tema({
    id: 'edgerunners', pre: 'edg', nome: 'Cyberpunk: Edgerunners', cat: 'anime', cor: '#ff1744', cores: ['#ff1744', '#00e5ff'], icone: 'fa-microchip', sem_pacote: true,
    lema: 'Eu vou até a Lua.',
    desc: 'Night City e a cyberpsicose: o implante que passa do limite e a tela começa a falhar.',
    pal: { m: '#ff1744', a: '#00e5ff', d: '#0a0a14', l: '#fff', o: '#0a0a14' },
    itens: [
        PAGINA('Cyberpsicose', 'De vez em quando a tela tem um surto: faixas de cor deslocadas, linhas de varredura, blocos de pixel e o aviso CYBERPSYCHOSIS. Sacuda o mouse com força pra provocar um.', { preset: 'cyber', cor: '#ff1744', cor2: '#00e5ff', min: 20, max: 45 }, { r: 'epico' }),
    ],
});

const telas = tema({
    id: 'telas', pre: 'tel', nome: 'Efeitos de Tela', cat: 'basico', cor: '#4be07a', cores: ['#4be07a', '#7ad7ff'], icone: 'fa-wand-magic-sparkles', sem_pacote: true,
    lema: 'A página inteira reage a você.',
    desc: 'Efeitos que tomam a tela toda: código verde, ondinhas, rastro de arco-íris e uma lagoa com sapos. Só no computador.',
    pal: { m: '#4be07a', a: '#7ad7ff', d: '#0a1a10', l: '#fff', o: '#0a1a10' },
    itens: [
        PAGINA('Matrix', 'Fique um tempo sem mexer e a tela escurece enquanto o código verde cai, letra por letra. Mexeu, tudo volta.', { preset: 'matrix', espera: 12, cor: '#4be07a' }, { r: 'epico' }),
        PAGINA('Ondinhas', 'Cada clique solta anéis de água que se abrem e somem.', { preset: 'ondinhas', cor: '#7ad7ff', cor2: '#ffffff' }, { r: 'raro' }),
        PAGINA('Rastro de Arco-íris', 'O mouse deixa um rastro de arco-íris que vai sumindo.', { preset: 'arcoiris' }, { r: 'raro' }),
        PAGINA('Lagoa dos Sapos', 'Fique parado e começa a chover de leve: vitórias-régias aparecem com sapinhos de pixel. Mexeu, a chuva para, mas os sapos ficam um tempo e pulam pra fora da tela. Clique num sapo e ele pula.', { preset: 'sapos', espera: 15 }, { r: 'epico' }),
    ],
});

module.exports = [edge, telas];
