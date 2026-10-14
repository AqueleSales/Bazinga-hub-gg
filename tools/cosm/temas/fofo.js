'use strict';
const { tema, M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P } = require('../dsl');
const { cena } = P;

const ROSA = { m: '#ffb3d1', a: '#ff8fb8', d: '#7a3a55', l: '#fff', o: '#d9759c' };
const CREME = { m: '#ffe3b5', a: '#ffbf80', d: '#7a4a2a', l: '#fff', o: '#d9a066' };
const SUAVE = (m) => ({ m, o: m, w: 0, l: '#fff', a: m });    // ícone sem contorno (para ladrilhos)

module.exports = [
    tema({
    id: 'gatinhos', pre: 'gat', nome: 'Gatinhos', cat: 'fofo', cor: '#ff9ec4', cores: ['#ff9ec4', '#ffe08a'], icone: 'fa-cat',
        lema: 'Miau. Mas com carinho.', desc: 'Patinhas, orelhinhas e bigodes: o perfil mais fofo do Armazém.',
        pal: ROSA,
        itens: [
            M('Patinhas', 'Um colar de patinhas rosa e creme que gira devagar em volta da sua foto.', { t: 'icones', icones: ['pata'], pals: [ROSA, CREME], n: 10, tam: 25, giro: 70, orient: 'fora' }),
            N('Miau', 'Rosa e pêssego passeando pelas letras, com uma patinha no fim do nome.', { grad: ['#ff7fae', '#ffb98a', '#ff7fae'], mov: 'desliza', dur: 6, fonte: 'redonda', contorno: '#8a3358', cw: .5, icone: { nome: 'pata', pos: 'depois', pal: ROSA } }),
            Pl('Pegadinhas', 'Patinhas e coraçõezinhos andando devagar sobre um fundo rosa e creme.', { base: ['#ffd9e7', '#fff0d1'], pad: { tipo: 'icones', icones: ['pata', 'coracao'], pals: [SUAVE('#ffb0cc'), SUAVE('#ffc999')], tam: 28, ti: 15 }, mov: 'x', dur: 14, texto: '#6b2a45', icone: { nome: 'gato', pal: ROSA, lado: 'dir', tam: 70 } }),
            F('Casinha de Gato', 'Um céu rosa, nuvens fofas passando e patinhas e peixinhos flutuando.', {
                fundo: ['#ffc2dc', '#ffe3c8'],
                fixo: cena.estrelas({ cor: '#fff', n: 22, y: [0, 60], r: [.6, 1.4], seed: 'g1' }),
                longe: { svg: cena.nuvens({ cor: '#fff', n: 3, y: [14, 40], alfa: .9, seed: 'g2' }), anim: 'pan', dur: 60 },
                perto: { svg: cena.icones({ nomes: ['pata', 'coracao', 'peixe', 'estrelinha'], pals: [ROSA, CREME, { m: '#9ad7ff', o: '#5aa9d6' }, { m: '#fff', o: '#fff', w: 0 }], n: 9, tam: [10, 17], seed: 'g3', y: [52, 100] }), anim: 'pan', dur: 34 },
            }),
            EA('Orelhinhas', 'Duas orelhas de gato aparecem no alto da sua foto e balançam, com coraçõezinhos em volta.', [
                { k: 'orelhas', tipo: 'gato', cor: '#ffb3d1', cor2: '#fff0f6', contorno: '#d9759c' },
                { k: 'faiscas', icone: 'coracao', pals: [ROSA], n: 6, tam: 7, raio: 37 },
            ], { r: 'epico' }),
            EP('Chuva de Patinhas', 'Patinhas, peixinhos e corações caindo pelo cartão inteiro, bem devagar.', [
                { k: 'cai', icones: ['pata', 'coracao', 'peixe', 'pata'], pals: [ROSA, { m: '#ff8fb8', o: '#d9759c' }, { m: '#9ad7ff', o: '#5aa9d6' }, CREME], n: 16, tam: [14, 24], vel: [7, 13] },
            ], { r: 'lendario' }),
            CHAT('Miau no Teclado', 'A barra de mensagem fica rosa ao digitar e solta patinhas ao enviar.', { cor: '#ff8fb8', cor2: '#ffc999', particula: { icone: 'pata', pal: ROSA } }),
            PIN('Patinha', 'Suas notas no mapa viram uma patinha rosa.', { icone: 'pata', pal: ROSA, bal: 2.4 }),
            SOM('Miau', 'Um miadinho sintetizado ao entrar na call.', { notas: [{ t: 0, f: 620, f2: 1250, d: .16, tipo: 'triangle', v: .7 }, { t: .15, f: 1250, f2: 700, d: .34, tipo: 'triangle', v: .7 }], ruidos: [] }),
        ],
    }),
];
