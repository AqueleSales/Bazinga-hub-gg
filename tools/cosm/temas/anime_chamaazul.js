'use strict';
/* CHAMA AZUL: energia amaldiçoada em chama azul-branca (o dono falou só "chama azul do JJK": se ele tinha uma técnica específica em mente, é só trocar o nome e o texto).
   Diferente do Gojo (azul, roxo e olhos): aqui é só FOGO azul. Arte original. */
const { tema, M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P, I, fase } = require('../dsl');
const { cena } = P;
const f1 = (n) => Math.round(n * 10) / 10;

const AZ = { m: '#3a8aff', a: '#e6f8ff', d: '#0a2a5a', l: '#ffffff', o: '#0a3a8a' };
const AZ2 = { m: '#8ae0ff', a: '#ffffff', d: '#0a4a7a', l: '#ffffff', o: '#1a6ac8' };
const fogueira = [...Array(9)].map((_, k) => ({ icone: 'chama', x: 6 + k * 11.5, y: 98 - (k % 2) * 2, tam: 62 + (k % 3) * 16, rot: 0, pal: k % 2 ? AZ2 : AZ }));

const chamaAzul = tema({
    id: 'chama_azul', pre: 'chz', nome: 'Chama Azul', cat: 'anime', cor: '#3a8aff', cores: ['#3a8aff', '#e6f8ff'], icone: 'fa-fire-flame-curved', premium: true,
    lema: 'Energia que queima sem esquentar.',
    desc: 'Fogo azul-branco de energia amaldiçoada: chamas subindo da foto, um céu escuro com uma lua fria e as bordas do cartão escurecendo enquanto a luz azul cresce.',
    pal: AZ,
    itens: [
        M('Chama Azul', 'Chamas azuis e brancas sobem em volta da foto, com um brilho frio.', { t: 'icones', icones: ['chama'], pals: [AZ, AZ2], n: 14, tam: 28, giro: 58, orient: 'fora', glow: '#3a8aff' }, { r: 'epico' }),
        N('Fogo Azul', 'Azul-elétrico que ferve até o branco, com contorno azul-marinho e um brilho que respira.', { grad: ['#1a5ae0', '#e6f8ff', '#1a5ae0'], mov: 'pulsa', brilho: '#3a8aff', bw: 3.4, contorno: '#06143a', cw: 1.1, fonte: 'impacto', espaco: .8, peso: 900, dur: 2.2 }, { r: 'epico' }),
        Pl('Aura Amaldiçoada', 'Um fundo quase preto com pequenas chamas azuis subindo e um brilho frio passando.', { base: ['#030a1c', '#0a1a3a'], pad: { tipo: 'icones', icones: ['chama'], pals: [{ m: '#1a4aa0', a: '#1a4aa0', d: '#1a4aa0', l: '#1a4aa0', o: '#1a4aa0', w: 0 }], tam: 26, ti: 14, c2: 'transparent' }, mov: 'x', dur: 18, brilho: 'rgba(138,224,255,.4)', borda: 'rgba(58,138,255,.8)', icone: { nome: 'chama', pal: AZ, lado: 'dir', tam: 66 } }, { r: 'epico' }),
        F('Céu Maldito', 'Uma lua fria sobre uma noite escura e uma fogueira de chamas azuis crescendo no chão.', {
            fundo: ['#02061a', '#0a1a4a', '#1a3a8a'], fixo: `${cena.estrelas({ cor: '#e6f8ff', n: 26, y: [0, 70], r: [.5, 1.4], seed: 'cz1' })}${cena.sol({ x: 90, y: 34, r: 22, c1: '#f4faff', c2: '#a8c8f4' })}`,
            longe: { svg: `<g opacity='.35'>${cena.nuvens({ cor: '#3a6ac8', n: 3, y: [10, 60], tam: [20, 30], seed: 'cz2' })}</g>`, anim: 'pan', dur: 56 },
            perto: { svg: cena.icones({ nomes: ['chama'], pals: [AZ, AZ2], n: 10, tam: [30, 56], seed: 'cz3', y: [90, 112], rot: 4, fileira: 104 }), anim: 'respira', dur: 2.2, min: .6 },
        }, { r: 'epico' }),
        EA('Energia Amaldiçoada', 'Chamas azuis sobem dos lados da foto, com uma aura fria pulsando e um anel de brasa.', [
            { k: 'aura', cor: '#3a8aff', dur: 1.8 },
            { k: 'anel', cor: '#8ae0ff', r: 66, esp: 2, dash: '6 6', giro: 16 },
            { k: 'sobe', icones: ['chama'], pals: [AZ, AZ2], n: 10, tam: 14, alt: 180 },
        ], { r: 'epico' }),
        EP('Fogo Azul', 'Uma fogueira de chamas azuis cresce de baixo enquanto as bordas do cartão escurecem, e faíscas sobem.', [
            { k: 'clima', fundo: 'radial-gradient(ellipse at 50% 110%,rgba(58,138,255,.75),transparent 62%)', min: .4, max: 1, dur: 2.4 },
            { k: 'cantos', itens: fogueira, dur: 1.2, bal: 5 },
            { k: 'sobe', icones: ['brilho'], pals: [{ m: '#e6f8ff', o: '#3a8aff', w: 2 }], n: 12, tam: [6, 12], vel: [3, 7] },
            { k: 'borda', cor: '#010510', alfa: .85, blur: 70, esp: 22, dur: 4 },
        ], { r: 'lendario' }),
        FALA('Energia na Voz', 'Quando você fala na call, o card acende em azul e branco, como uma chama.', { cores: ['#3a8aff', '#e6f8ff'] }),
        RADAR('Ondas de Brasa', 'As ondas do radar viram anéis azuis tracejados.', { cor: '#3a8aff', estilo: 'tracejado', glow: '#8ae0ff' }),
        CHAT('Faísca Fria', 'A barra de mensagem acende em azul ao digitar e solta chamas azuis ao enviar.', { cor: '#3a8aff', cor2: '#e6f8ff', particula: { icone: 'chama', pal: AZ } }),
        PIN('Chama Azul', 'Suas notas no mapa viram uma chama azul.', { icone: 'chama', pal: AZ, bal: 1.6 }),
        SOM('Energia', 'Um rugido de fogo que cresce e se acende num brilho agudo, ao entrar na call.', { notas: [{ t: 0, f: 90, f2: 240, d: .7, tipo: 'sawtooth', v: .3 }, { t: .55, f: 1175, d: .6, tipo: 'sine', v: .3 }], ruidos: [{ t: 0, d: .8, f: 300, f2: 2400, filtro: 'bandpass', v: .6, q: .7 }] }),
        SERV('Servidor de Chama Azul', 'O ícone do servidor brilha em azul e branco.', { cores: ['#3a8aff', '#e6f8ff'] }),
    ],
});

module.exports = [chamaAzul];
