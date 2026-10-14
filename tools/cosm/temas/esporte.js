'use strict';
/* ESPORTES: futebol (a bola, o gol e a rede, os cartões, o placar, o apito). Arte original. */
const { tema, M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P, I, fase } = require('../dsl');
const { cena } = P;
const f1 = (n) => Math.round(n * 10) / 10;

const BOLA = { m: '#ffffff', a: '#e8e8e8', d: '#1a1a22', l: '#ffffff', o: '#1a1a22' };
const OURO = { m: '#ffcf3a', a: '#fff0a0', d: '#7a5a00', l: '#ffffff', o: '#8a6a10' };

const rede = (() => { let s = ''; for (let k = -12; k < 16; k++) s += `<path d='M${k * 22} 0L${k * 22 + 160} 200M${k * 22 + 160} 0L${k * 22} 200' stroke='#fff' stroke-width='1.4' opacity='.8'/>`; return `<svg viewBox="0 0 340 200" preserveAspectRatio="none">${s}</svg>`; })();
const campo = (() => { let s = ''; for (let k = 0; k < 10; k++) s += `<rect x='${k * 34}' width='34' height='112' fill='${k % 2 ? '#2e9e4f' : '#3aab5c'}'/>`; return `${s}<g fill='none' stroke='#fff' stroke-width='2.2' opacity='.9'><circle cx='170' cy='56' r='26'/><path d='M170 0V112'/><circle cx='170' cy='56' r='2.4' fill='#fff'/><rect x='-4' y='24' width='42' height='64'/><rect x='302' y='24' width='42' height='64'/></g>`; })();

const gol = tema({
    id: 'gol', pre: 'gol', nome: 'Dia de Jogo', cat: 'esporte', cor: '#2e9e4f', cores: ['#2e9e4f', '#ffcf3a'], icone: 'fa-futbol', premium: true,
    lema: 'Bola rolando. Torcida de pé.',
    desc: 'O gramado listrado, a bola, o placar, o apito, o cartão amarelo e a rede que balança no gol: uma tarde de futebol.',
    pal: BOLA,
    itens: [
        M('Bola em Jogo', 'Bolas de futebol giram em volta da sua foto, como um treino de embaixadinha.', { t: 'icones', icones: ['bola_futebol'], pals: [BOLA], n: 7, tam: 30, giro: 24 }, { r: 'epico' }),
        N('Camisa 10', 'Listras verdes e brancas de camisa de time, com contorno escuro e letras de numeral.', { grad: ['#1f8a3a', '#ffffff', '#1f8a3a', '#ffffff'], passos: true, mov: 'desliza', dur: 4, contorno: '#0a2a14', cw: 1.3, fonte: 'impacto', espaco: 1.2, peso: 900 }, { r: 'epico' }),
        Pl('Placar', 'Um placar de lâmpadas âmbar sobre o preto, com um troféu ao lado.', { base: ['#0c0f16', '#151a24'], pad: { tipo: 'bolinhas', c1: 'rgba(255,170,40,.34)', c2: 'transparent', tam: 8, r: .3 }, mov: 'x', dur: 6, brilho: 'rgba(255,200,90,.3)', borda: 'rgba(255,170,40,.6)', texto: '#ffcf70', icone: { nome: 'trofeu', pal: OURO, lado: 'dir', tam: 66 } }, { r: 'epico' }),
        F('Gramado', 'O campo visto de cima, com as faixas do corte do gramado e bolas passando.', {
            fundo: ['#2e9e4f'], fixo: campo,
            longe: { svg: `<g opacity='.35'>${cena.nuvens({ cor: '#fff', n: 2, y: [10, 90], tam: [24, 34], seed: 'gl1' })}</g>`, anim: 'pan', dur: 70 },
            perto: { svg: cena.icones({ nomes: ['bola_futebol'], pals: [BOLA], n: 3, tam: [12, 16], seed: 'gl2', y: [24, 90], rot: 40 }), anim: 'pan', dur: 14 },
        }, { r: 'epico' }),
        EA('Chute', 'Uma bola gira rápido em volta da foto, com um brilho de refletor e faíscas.', [
            { k: 'aura', cor: '#ffffff', dur: 2.2 },
            { k: 'orbita', icones: ['bola_futebol'], pals: [BOLA], n: 1, tam: 30, giro: 3.4, raio: 74 },
            { k: 'faiscas', icone: 'estrelinha', pals: [{ m: '#ffcf3a', o: '#ffcf3a', w: 0 }], n: 6, tam: 7, raio: 39 },
        ], { r: 'epico' }),
        EP('GOL!', 'A rede balança, a palavra GOL! aparece e a torcida joga papel picado no cartão inteiro.', [
            { k: 'cai', icones: ['confete'], pals: [{ m: '#2e9e4f', a: '#ffcf3a', l: '#fff' }, { m: '#ffcf3a', a: '#2e9e4f', l: '#fff' }], n: 18, tam: [10, 18], vel: [3.5, 7], bal: 60, giro: 400 },
            { k: 'raw', html: `<i class="rd">${rede}</i><b class="gl">GOL!</b><i class="fl"></i>`,
              css: `.ef-pf-$ID .rd{position:absolute;left:0;right:0;top:0;height:46%;opacity:0;transform-origin:50% 0;animation:k-$ID-rd 8s ease-out ${fase(8, .4)} infinite}.ef-pf-$ID .rd svg{width:100%;height:100%;display:block}.ef-pf-$ID .gl{position:absolute;left:0;right:0;top:36%;text-align:center;font:900 28cqw/1 Impact,'Arial Black',sans-serif;color:#fff;-webkit-text-stroke:3px #1f7a3a;paint-order:stroke fill;text-shadow:0 0 22px rgba(255,255,255,.8);opacity:0;animation:k-$ID-gl 8s ease-out ${fase(8, .4)} infinite}.ef-pf-$ID .fl{position:absolute;inset:0;background:radial-gradient(circle at 50% 30%,rgba(255,255,255,.7),transparent 60%);opacity:0;animation:k-$ID-fl 8s linear ${fase(8, .4)} infinite}`
                  + `@keyframes k-$ID-rd{0%,28%{opacity:0;transform:scaleY(.6)}34%{opacity:1;transform:scaleY(1.35)}40%{transform:scaleY(.95)}46%{transform:scaleY(1.12)}52%,66%{opacity:1;transform:scaleY(1)}76%,100%{opacity:0;transform:scaleY(1)}}@keyframes k-$ID-gl{0%,30%{opacity:0;transform:scale(2.6)}36%{opacity:1;transform:scale(.94)}40%{transform:scale(1.04)}46%,66%{opacity:1;transform:scale(1)}76%,100%{opacity:0;transform:scale(1.1)}}@keyframes k-$ID-fl{0%,29%{opacity:0}31%{opacity:1}40%,100%{opacity:0}}` },
        ], { r: 'lendario' }),
        FALA('Torcida em Pé', 'Quando você fala na call, o card pisca em verde e dourado, como a torcida.', { cores: ['#2e9e4f', '#ffcf3a'] }),
        RADAR('Círculo Central', 'As ondas do radar viram o círculo branco do meio de campo.', { cor: '#ffffff', estilo: 'liso', glow: '#2e9e4f' }),
        CHAT('Cartão', 'A barra de mensagem acende em verde ao digitar e solta cartões amarelos e vermelhos ao enviar.', { cor: '#2e9e4f', cor2: '#ffcf3a', particula: { forma: 'quadrado' } }),
        PIN('Bola', 'Suas notas no mapa viram uma bola de futebol.', { icone: 'bola_futebol', pal: BOLA, bal: 2.4 }),
        SOM('Apito', 'O apito do juiz e o rugido da torcida, ao entrar na call.', { notas: [{ t: 0, f: 2800, d: .5, tipo: 'square', v: .45 }, { t: .12, f: 3100, d: .38, tipo: 'square', v: .35 }], ruidos: [{ t: .5, d: .7, f: 700, f2: 1400, filtro: 'bandpass', v: .45, q: .7 }] }),
        SERV('Servidor Campeão', 'O ícone do servidor brilha em verde e dourado.', { cores: ['#2e9e4f', '#ffcf3a'] }),
    ],
});

module.exports = [gol];
