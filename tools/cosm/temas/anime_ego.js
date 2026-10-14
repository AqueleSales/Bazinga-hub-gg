'use strict';
/* EGO (futebol de ego e eliminação): chama azul da "zona", linhas de campo em arame, trajetória do chute e a colisão que faz faíscas. Arte original. */
const { tema, M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P, I, fase } = require('../dsl');
const { cena } = P;

const ZONA = { m: '#2d6bff', a: '#4ae0ff', d: '#06143a', l: '#e6f8ff', o: '#0a2a8a' };
const ZONA2 = { m: '#4ae0ff', a: '#e6fbff', d: '#06324a', l: '#ffffff', o: '#0a5a8a' };

const ego = tema({
    id: 'ego', pre: 'ego', nome: 'Ego', cat: 'anime', cor: '#2d6bff', cores: ['#2d6bff', '#4ae0ff'], icone: 'fa-fire', premium: true,
    lema: 'Só o melhor sobrevive. E é você.',
    desc: 'A chama azul da "zona", uma gaiola de linhas em arame, a trajetória exata do chute e a reação que explode quando dois egos se encontram.',
    pal: ZONA,
    itens: [
        M('Zona', 'Chamas azuis e ciano sobem em volta da foto, como a concentração de quem entrou na zona.', { t: 'icones', icones: ['chama'], pals: [ZONA, ZONA2], n: 14, tam: 27, giro: 46, orient: 'fora', glow: '#2d6bff' }, { r: 'epico' }),
        N('Ego', 'Azul-elétrico com contorno branco e um brilho que pulsa, em letras maiúsculas e secas.', { grad: ['#1a4ae0', '#4ae0ff', '#1a4ae0'], mov: 'pulsa', brilho: '#2d6bff', bw: 3, contorno: '#ffffff', cw: 1.1, fonte: 'impacto', espaco: 1.4, maius: true, peso: 900, dur: 2.2 }, { r: 'epico' }),
        Pl('Metavisão', 'Uma grade de arame ciano sobre o preto, com setas de trajetória e um olho aberto.', { base: ['#02060f', '#061226'], pad: { tipo: 'grade', c1: 'rgba(74,224,255,.35)', c2: 'transparent', tam: 14, lw: 1 }, mov: 'xy', dur: 7, brilho: 'rgba(74,224,255,.4)', borda: 'rgba(74,224,255,.75)', icone: { nome: 'olho_aberto', pal: { ...ZONA2, m: '#4ae0ff', l: '#02060f', d: '#4ae0ff' }, lado: 'dir', tam: 62 } }, { r: 'epico' }),
        F('Gaiola Azul', 'Um campo de linhas em arame ciano sob uma gaiola de barras escuras, com o chão brilhando.', {
            fundo: ['#02060f', '#061a3a', '#0a3a8a'],
            fixo: `${cena.perspectiva({ cor: '#4ae0ff', y: 66, n: 14 })}${cena.cortina({ cores: ['rgba(2,6,15,.0)', 'rgba(2,6,15,.55)'], larg: 14 })}<path d='M0 66H340' stroke='#4ae0ff' stroke-width='1.6' opacity='.9'/>`,
            longe: { svg: `<g opacity='.5'>${cena.icones({ nomes: ['flecha'], pals: [{ m: '#4ae0ff', a: '#4ae0ff', d: '#4ae0ff', l: '#4ae0ff', o: '#4ae0ff', w: -6 }], n: 5, tam: [10, 16], seed: 'eg1', y: [8, 56], rot: 8 })}</g>`, anim: 'pan', dur: 16 },
            perto: { svg: cena.estrelas({ cor: '#9af0ff', n: 18, seed: 'eg2', y: [4, 60] }), anim: 'pisca', dur: 1.8 },
        }, { r: 'epico' }),
        EA('Aura da Zona', 'Uma chama azul sobe em volta da foto, com uma aura elétrica e um anel ciano.', [
            { k: 'aura', cor: '#2d6bff', dur: 1.8 },
            { k: 'anel', cor: '#4ae0ff', r: 66, esp: 2, dash: '14 6', giro: 18 },
            { k: 'sobe', icones: ['chama'], pals: [ZONA, ZONA2], n: 9, tam: 12, alt: 170 },
        ], { r: 'epico' }),
        EP('Reação Química', 'Dois feixes, um azul e um branco, se chocam no meio do cartão numa explosão de faíscas.', [
            { k: 'raw', html: '<i class="b1"></i><i class="b2"></i><i class="fl"></i><i class="rg"></i><i class="rg r2"></i>',
              css: `.ef-pf-$ID .b1,.ef-pf-$ID .b2{position:absolute;top:44%;height:9px;margin-top:-4px;width:50%;border-radius:5px;opacity:0;filter:drop-shadow(0 0 7px #4ae0ff)}.ef-pf-$ID .b1{left:0;background:linear-gradient(90deg,transparent,#2d6bff 40%,#9af0ff);transform-origin:0 50%;animation:k-$ID-b 7s ease-in ${fase(7, .34)} infinite}.ef-pf-$ID .b2{right:0;background:linear-gradient(270deg,transparent,#e6fbff 40%,#ffffff);transform-origin:100% 50%;animation:k-$ID-b 7s ease-in ${fase(7, .34)} infinite}`
                  + `.ef-pf-$ID .fl{position:absolute;inset:0;background:radial-gradient(circle at 50% 44%,#fff,rgba(74,224,255,.6) 24%,transparent 62%);opacity:0;animation:k-$ID-fl 7s linear ${fase(7, .34)} infinite}.ef-pf-$ID .rg{position:absolute;left:50%;top:44%;width:60cqw;height:60cqw;margin:-30cqw 0 0 -30cqw;border-radius:50%;border:3px solid #9af0ff;box-shadow:0 0 18px #2d6bff,inset 0 0 18px #2d6bff;opacity:0;animation:k-$ID-rg 7s ease-out ${fase(7, .34)} infinite}.ef-pf-$ID .rg.r2{border-color:#fff;animation-delay:calc(${fase(7, .34)} + .18s)}`
                  + `@keyframes k-$ID-b{0%,6%{opacity:0;transform:scaleX(0)}8%{opacity:1}22%{opacity:1;transform:scaleX(1)}26%,100%{opacity:0;transform:scaleX(1)}}@keyframes k-$ID-fl{0%,22%{opacity:0}25%{opacity:1}40%,100%{opacity:0}}@keyframes k-$ID-rg{0%,23%{opacity:0;transform:scale(.1)}27%{opacity:1}52%,100%{opacity:0;transform:scale(1.9)}}` },
            { k: 'pisca', icone: 'brilho', pals: [{ m: '#fff', o: '#2d6bff', w: 2 }], n: 8, tam: [7, 13] },
        ], { r: 'lendario' }),
        FALA('Concentração', 'Quando você fala na call, o card acende em azul e ciano, como quem entrou na zona.', { cores: ['#2d6bff', '#4ae0ff'] }),
        RADAR('Linhas em Arame', 'As ondas do radar viram anéis tracejados ciano, como as linhas do campo na metavisão.', { cor: '#4ae0ff', estilo: 'tracejado', glow: '#2d6bff' }),
        CHAT('Chute Direto', 'A barra de mensagem acende em azul ao digitar e solta faíscas azuis e ciano ao enviar.', { cor: '#2d6bff', cor2: '#4ae0ff', particula: { forma: 'losango' } }),
        PIN('Cadeado', 'Suas notas no mapa viram um cadeado azul, como a gaiola.', { icone: 'cadeado', pal: { m: '#2d6bff', a: '#4ae0ff', d: '#06143a', l: '#e6f8ff', o: '#0a2a8a' } }),
        SOM('Zona', 'Um zumbido grave que sobe, um estalo elétrico e um brilho agudo, ao entrar na call.', { notas: [{ t: 0, f: 70, f2: 220, d: .7, tipo: 'sawtooth', v: .35 }, { t: .55, f: 880, f2: 1760, d: .3, tipo: 'sine', v: .4 }, { t: .6, f: 2349, d: .5, tipo: 'sine', v: .2 }], ruidos: [{ t: .5, d: .18, f: 4000, f2: 900, filtro: 'bandpass', v: .7, q: 2 }] }),
        SERV('Servidor da Zona', 'O ícone do servidor brilha em azul e ciano.', { cores: ['#2d6bff', '#4ae0ff'] }),
    ],
});

module.exports = [ego];
