'use strict';
/* CYBERPUNK: EDGERUNNERS (Rodada 40, épico): David, Lucy, Rebecca e Adam Smasher. Só símbolos e objetos por código (arte.js: coluna, Lua, escopeta, olho). A cyberpsicose (shader) mora no tema `edgerunners` (telas.js). */
const { tema, MP, EA, EP, P, R, B, IMG, apoio, fase } = require('../dsl');
const T = 'edgerunners';
const f1 = B.f1;
const AMA = '#f3e600', CIA = '#00e5ff', ROS = '#ff2a8a', VRM = '#ff2020';

// ============================================================================================ DAVID
const david = tema({
    id: 'edg_david', pre: 'dav', nome: 'David Martinez', cat: 'anime', cor: AMA, cores: [AMA, CIA], icone: 'fa-bolt', premium: true,
    lema: 'Eu vou mais longe que todo mundo.',
    desc: 'David e o Sandevistan: a coluna de implante brilhando, ecos de velocidade em volta da foto, riscos de movimento e a jaqueta amarela de Night City.',
    pal: { m: AMA, a: CIA, d: '#0a0a14', l: '#fff', o: '#0a0a14' },
    itens: [
        MP('Sandevistan', 'A coluna do implante Sandevistan ao lado da foto, com o brilho azul correndo.', { imagem: { url: R.url(T, 'sandevistan'), ratio: R.proporcao(T, 'sandevistan'), x: 96, y: 50, w: 20, rot: 0, anim: 'pulsa', dur: .9 } }, { r: 'epico' }),
        EA('Ecos de Velocidade', 'O Sandevistan acelera tudo: ecos ciano e rosa da sua foto se espalham pro lado.', [
            { k: 'raw', html: '<b class="$C"><i class="ec e1"></i><i class="ec e2"></i><i class="ec e3"></i><i class="ec e4"></i></b>',
              css: '.ef-av-$ID .ec{position:absolute;left:50%;top:50%;width:62%;aspect-ratio:1;margin:-31% 0 0 -31%;border-radius:50%;border:3px solid #00e5ff;opacity:0;mix-blend-mode:screen;animation:k-$ID-ec 2.4s steps(6,end) infinite}.ef-av-$ID .e2{border-color:#ff2a8a;animation-delay:-.6s}.ef-av-$ID .e3{border-color:#00e5ff;animation-delay:-1.2s}.ef-av-$ID .e4{border-color:#ff2a8a;animation-delay:-1.8s}@keyframes k-$ID-ec{0%{opacity:.9;transform:translateX(0)}100%{opacity:0;transform:translateX(34%)}}' },
        ], { r: 'epico', id: 'dav_ecos_de_velocidade' }),
        EP('Sandevistan Ativado', 'Riscos de velocidade cruzam o cartão e o aviso SANDEVISTAN pisca.', [
            { k: 'raw', html: [14, 28, 44, 60, 76, 90].map((y, k) => `<i class="sl" style="top:${y}%;--d:${k * .5}s;--w:${24 + (k % 3) * 14}cqw"></i>`).join('') + '<b class="hud">SANDEVISTAN</b>',
              css: '.ef-pf-$ID .sl{position:absolute;left:0;width:var(--w);height:.9cqw;background:linear-gradient(90deg,transparent,#00e5ff 60%,#fff);opacity:0;animation:k-$ID-sl 2.8s cubic-bezier(.3,.6,.4,1) calc(var(--d) + ' + fase(2.8, .2) + ') infinite}@keyframes k-$ID-sl{0%{opacity:0;transform:translateX(-40cqw)}8%{opacity:1}40%{opacity:1;transform:translateX(130cqw)}100%{opacity:0;transform:translateX(130cqw)}}'
                + ".ef-pf-$ID .hud{position:absolute;left:0;right:0;top:6%;text-align:center;font:700 7cqw/1 'Courier New',monospace;color:#f3e600;text-shadow:2px 0 #ff2a8a,-2px 0 #00e5ff;opacity:0;animation:k-$ID-hd 5s steps(1,end) " + fase(5, .3) + ' infinite}@keyframes k-$ID-hd{0%,20%{opacity:0}22%,34%{opacity:1}36%,40%{opacity:.3}42%,60%{opacity:1}62%,100%{opacity:0}}' },
            { k: 'borda', cor: AMA, alfa: .5, blur: 36, esp: 4, dur: 1.2 },
        ], { r: 'epico', id: 'dav_sandevistan_ativado' }),
        ...apoio({
            tema: T, r: 'epico',
            nome: { nomeItem: 'Edgerunner', desc: 'Amarelo e ciano de neon com contorno preto e um brilho de glitch.', grad: [AMA, CIA, AMA], mov: 'glitch', g1: ROS, g2: CIA, dur: 3, contorno: '#0a0a14', cw: 1, fonte: 'mono', espaco: 1 },
            placa: { nomeItem: 'Jaqueta Amarela', desc: 'Amarelo com listras pretas e a coluna do Sandevistan do lado.', base: [AMA, '#c8b800'], pad: { tipo: 'listras', c1: 'rgba(10,10,20,.5)', c2: 'transparent', tam: 10 }, mov: 'x', dur: 8, borda: '#0a0a14', texto: '#0a0a14', img: { nome: 'sandevistan', lado: 'dir', tam: 90, y: 50 } },
            faixa: { nomeItem: 'Night City', desc: 'A cidade em neon amarelo e ciano.', fundo: ['#0a0a14', '#1a1030', '#3a1060'],
                fixo: P.cena.skyline({ cor: '#06060e', altMin: 22, altMax: 78, larg: [8, 18], seed: 'dav1', janelas: { cor: '#f3e600', dens: .45 } }),
                perto: { svg: P.cena.icones({ nomes: ['raio'], pals: [{ m: '#00e5ff', o: '#00e5ff', w: 1 }], n: 5, tam: [10, 18], seed: 'dav2', y: [6, 60] }), anim: 'pisca', dur: 1.2 },
                 },
            fala: { nomeItem: 'Acelerado', desc: 'Quando você fala na call, o card pisca em amarelo e ciano.', cores: [AMA, CIA], passos: true, dur: .25 },
            radar: { nomeItem: 'Pulso de Rua', desc: 'As ondas do radar viram anéis duplos de ciano.', cor: CIA, estilo: 'duplo', glow: AMA },
            chat: { nomeItem: 'Dados', desc: 'A barra de mensagem acende em amarelo ao digitar e solta faíscas de neon ao enviar.', cor: AMA, cor2: CIA, particula: { forma: 'losango' } },
            som: { nomeItem: 'Implante Ligando', desc: 'Um zumbido de implante que sobe de tom e estala, ao entrar na call.', arquivo: 'david.mp3', notas: [{ t: 0, f: 120, f2: 900, d: .5, tipo: 'sawtooth', v: .3 }, { t: .5, f: 1800, f2: 1200, d: .2, tipo: 'square', v: .2 }], ruidos: [{ t: 0, d: .5, f: 2000, f2: 6000, filtro: 'bandpass', v: .3, q: 1.4 }] },
            pin: { nomeItem: 'Coluna', desc: 'Suas notas no mapa viram a coluna do Sandevistan.', img: 'sandevistan', bal: 0 },
            serv: { nomeItem: 'Servidor Edgerunner', desc: 'O ícone do servidor pisca em amarelo e ciano.', cores: [AMA, CIA], passos: true, dur: .4 },
        }),
    ],
});

// ============================================================================================ LUCY
const lucy = tema({
    id: 'edg_lucy', pre: 'luc', nome: 'Lucy', cat: 'anime', cor: CIA, cores: [CIA, ROS], icone: 'fa-moon', premium: true,
    lema: 'Eu quero ver a Lua.',
    desc: 'Lucy, a netrunner: a Lua crescente, o visor de dados em hexágonos, a chuva de código e o cabelo em preto e ciano.',
    pal: { m: CIA, a: ROS, d: '#0a0a14', l: '#fff', o: '#0a0a14' },
    itens: [
        MP('Lua Crescente', 'A Lua que a Lucy quer ver, pendurada no alto da foto e flutuando.', { imagem: { url: R.url(T, 'lua'), ratio: 1, x: 90, y: 8, w: 40, rot: 0, anim: 'flutua', dur: 4, bal: 5 } }, { r: 'epico' }),
        EA('Netrunner', 'Hexágonos de dados giram em volta da foto e o visor pisca em ciano e rosa.', [
            { k: 'orbita', icones: ['hexagono'], pals: [{ m: '#00e5ff', o: '#00e5ff', w: 1 }], n: 6, tam: 18, giro: 14 },
            { k: 'faiscas', icone: 'brilho', pals: [{ m: '#ff2a8a', o: '#ff2a8a', w: 1 }], n: 6, tam: 7, raio: 40 },
        ], { r: 'epico', id: 'luc_netrunner', sobre: [{ k: 'scan', cor: '#00e5ff', dur: 3.4 }] }),
        EP('Chuva de Dados', 'Uma Lua gigante sobe e hexágonos de dados caem como chuva.', [
            { k: 'raw', html: '<i class="mo"></i>',
              css: '.ef-pf-$ID .mo{position:absolute;left:50%;top:14%;width:52cqw;aspect-ratio:1;margin-left:-26cqw;border-radius:50%;background:radial-gradient(circle at 36% 34%,#fff,#cfe8f4 56%,#7ab8d0);box-shadow:0 0 36px 8px rgba(0,229,255,.4);opacity:0;transform:translateY(40cqh);animation:k-$ID-mo 10s ease-out ' + fase(10, .4) + ' infinite}@keyframes k-$ID-mo{0%{opacity:0;transform:translateY(40cqh)}22%{opacity:.8}50%,80%{opacity:.8;transform:translateY(0)}100%{opacity:0;transform:translateY(-10cqh)}}' },
            { k: 'cai', icones: ['hexagono'], pals: [{ m: '#00e5ff', o: '#00e5ff', w: 1 }], n: 14, tam: [10, 18], vel: [5, 10], alfa: .8 },
            { k: 'borda', cor: CIA, alfa: .45, blur: 36, esp: 4, dur: 3 },
        ], { r: 'epico', id: 'luc_chuva_de_dados' }),
        ...apoio({
            tema: T, r: 'epico',
            nome: { nomeItem: 'Netrunner', desc: 'Ciano e rosa de neon com contorno preto.', grad: [CIA, '#ffffff', ROS], mov: 'desliza', dur: 4.4, contorno: '#0a0a14', cw: 1, fonte: 'mono', espaco: 1.4 },
            placa: { nomeItem: 'Interface', desc: 'Preto com hexágonos ciano e a Lua do lado.', base: ['#0a0a14', '#101830'], pad: { tipo: 'favo', c1: 'rgba(0,229,255,.35)', c2: 'transparent', tam: 8, lw: 1 }, mov: 'x', dur: 11, borda: CIA, img: { nome: 'lua', lado: 'dir', tam: 86, y: 50 } },
            faixa: { nomeItem: 'A Lua', desc: 'Uma noite escura com a Lua crescente e dados de ciano caindo.', fundo: ['#05050e', '#0a1430', '#1a2a5a'],
                fixo: P.cena.estrelas({ cor: '#fff', n: 20, y: [0, 70], r: [.5, 1.2], seed: 'luc1' }) + P.cena.skyline({ cor: '#05050c', altMin: 14, altMax: 44, larg: [8, 16], seed: 'luc2' }),
                css: `.banner-anim-$ID::before{content:'';position:absolute;right:6%;top:6%;height:78%;aspect-ratio:1;background:${R.css(T, 'lua')} center/contain no-repeat;pointer-events:none;animation:k-$ID-m 6s ease-in-out infinite alternate}@keyframes k-$ID-m{from{transform:translateY(3%)}to{transform:translateY(-3%)}}` },
            fala: { nomeItem: 'Conexão', desc: 'Quando você fala na call, o card pisca em ciano e rosa.', cores: [CIA, ROS], passos: true, dur: .4 },
            radar: { nomeItem: 'Ping', desc: 'As ondas do radar viram anéis ciano pontilhados.', cor: CIA, estilo: 'pontilhado', glow: ROS },
            chat: { nomeItem: 'Pacote de Dados', desc: 'A barra de mensagem acende em ciano ao digitar e solta pacotes de dados ao enviar.', cor: CIA, cor2: ROS, particula: { icone: 'hexagono', pal: { m: '#00e5ff', o: '#00e5ff', w: 1 } } },
            som: { nomeItem: 'Login na Rede', desc: 'Um acorde etéreo e brilhante de conexão, ao entrar na call.', arquivo: 'lucy.mp3', notas: [{ t: 0, f: 523, d: .8, tipo: 'sine', v: .3 }, { t: .1, f: 784, d: .8, tipo: 'sine', v: .25 }, { t: .2, f: 1047, d: .8, tipo: 'sine', v: .2 }, { t: .6, f: 2093, f2: 1568, d: .3, tipo: 'triangle', v: .12 }], ruidos: [{ t: 0, d: .4, f: 6000, filtro: 'highpass', v: .15 }] },
            pin: { nomeItem: 'Lua', desc: 'Suas notas no mapa viram a Lua crescente.', img: 'lua', bal: 1 },
            serv: { nomeItem: 'Servidor da Lua', desc: 'O ícone do servidor pisca em ciano e rosa.', cores: [CIA, ROS], passos: true, dur: .7 },
        }),
    ],
});

// ============================================================================================ REBECCA
const { REG } = require('../arte');
const gunInner = REG['edgerunners/escopeta'].svg.replace(/^<svg[^>]*>/, '').replace(/<\/svg>$/, '');
/** a escopeta dela embaixo da foto (quadro 160, foto = círculo de raio 50 em 80,80), balançando de leve */
const escopeta = (anim) => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.g{transform-origin:80px 142px;animation:b 2.8s ease-in-out infinite alternate}@keyframes b{from{transform:rotate(-4deg)}to{transform:rotate(4deg)}}</style>` : ''}`
    + `<g class='g'><g transform='translate(80 142) rotate(-4)'><svg x='-60' y='-13.2' width='120' height='26.4' viewBox='0 0 200 44'>${gunInner}</svg></g></g></svg>`;
const rebecca = tema({
    id: 'edg_rebecca', pre: 'reb', nome: 'Rebecca', cat: 'anime', cor: ROS, cores: [ROS, CIA], icone: 'fa-gun', premium: true,
    lema: 'Atira primeiro, ri depois.',
    desc: 'A escopeta dela: o corpo turquesa de faixas rosa, clarões de tiro em rosa e ciano e rastros de bala.',
    pal: { m: ROS, a: CIA, d: '#0a0a14', l: '#fff', o: '#0a0a14' },
    itens: [
        MP('Escopeta', 'A escopeta turquesa de faixas rosa pendurada embaixo da foto, balançando.', { svg: escopeta }, { r: 'epico' }),
        EA('Tiroteio', 'Clarões de tiro rosa e ciano estouram em volta da foto, um depois do outro.', [
            { k: 'faiscas', icone: 'estrela', pals: [{ m: '#ff2a8a', a: '#fff', o: '#ff2a8a', w: 1 }, { m: '#00e5ff', a: '#fff', o: '#00e5ff', w: 1 }], n: 10, tam: 10, raio: 39, dur: .9 },
            { k: 'aura', cor: '#ff2a8a', dur: 1 },
        ], { r: 'epico', id: 'reb_tiroteio' }),
        EP('Bala Perdida', 'Balas rosa e ciano cruzam o cartão deixando rastro e estrelas de tiro estouram.', [
            { k: 'raw', html: [16, 32, 50, 68, 84].map((y, k) => `<i class="bl" style="top:${y}%;--d:${k * .8}s;--c:${k % 2 ? '#00e5ff' : '#ff2a8a'}"></i>`).join(''),
              css: '.ef-pf-$ID .bl{position:absolute;left:0;width:22cqw;height:1.4cqw;border-radius:1cqw;background:linear-gradient(90deg,transparent,var(--c) 70%,#fff);opacity:0;transform:translateX(-30cqw) rotate(-5deg);animation:k-$ID-bl 3.6s cubic-bezier(.3,.6,.4,1) calc(var(--d) + ' + fase(3.6, .25) + ') infinite}@keyframes k-$ID-bl{0%{opacity:0;transform:translateX(-30cqw) rotate(-5deg)}6%{opacity:1}34%{opacity:1;transform:translateX(130cqw) rotate(-5deg)}100%{opacity:0;transform:translateX(130cqw) rotate(-5deg)}}' },
            { k: 'pisca', icone: 'estrela', pals: [{ m: '#ff2a8a', a: '#fff', o: '#ff2a8a', w: 1 }], n: 9, tam: [10, 18] },
            { k: 'borda', cor: ROS, alfa: .5, blur: 36, esp: 4, dur: 1.2 },
        ], { r: 'epico', id: 'reb_bala_perdida' }),
        ...apoio({
            tema: T, r: 'epico',
            nome: { nomeItem: 'Pequena e Perigosa', desc: 'Rosa e ciano de neon com contorno preto.', grad: [ROS, CIA, ROS], mov: 'pulsa', brilho: ROS, contorno: '#0a0a14', cw: 1, fonte: 'impacto', espaco: 1 },
            placa: { nomeItem: 'Jaqueta de Neon', desc: 'Rosa-choque com bolinhas e a escopeta turquesa do lado.', base: [ROS, '#a0105a'], pad: { tipo: 'bolinhas', c1: 'rgba(0,229,255,.35)', c2: 'transparent', tam: 9, r: .28 }, mov: 'x', dur: 8, borda: CIA, img: { nome: 'escopeta', lado: 'dir', tam: 36, y: 50 } },
            faixa: { nomeItem: 'Beco do Neon', desc: 'Um beco em rosa e ciano.', fundo: ['#0a0a14', '#2a0a3a', '#6a1060'],
                fixo: P.cena.skyline({ cor: '#06060e', altMin: 20, altMax: 70, larg: [8, 18], seed: 'reb1', janelas: { cor: '#ff2a8a', dens: .4 } }),
                 },
            fala: { nomeItem: 'Gritaria', desc: 'Quando você fala na call, o card pisca em rosa e ciano, aos gritos.', cores: [ROS, CIA], passos: true, dur: .25 },
            radar: { nomeItem: 'Tiro no Radar', desc: 'As ondas do radar viram anéis rosa grossos.', cor: ROS, estilo: 'liso', glow: CIA },
            chat: { nomeItem: 'Cartuchos de Neon', desc: 'A barra de mensagem acende em rosa ao digitar e solta estrelas ao enviar.', cor: ROS, cor2: CIA, particula: { forma: 'estrela' } },
            som: { nomeItem: 'Dois Tiros', desc: 'Dois tiros secos de pistola e uma risada curta, ao entrar na call.', arquivo: 'rebecca.mp3', notas: [{ t: 0, f: 200, f2: 55, d: .1, tipo: 'sawtooth', v: .5 }, { t: .14, f: 200, f2: 55, d: .1, tipo: 'sawtooth', v: .5 }, { t: .4, f: 900, f2: 1300, d: .1, tipo: 'sawtooth', v: .25 }, { t: .52, f: 960, f2: 1400, d: .1, tipo: 'sawtooth', v: .25 }], ruidos: [{ t: 0, d: .08, f: 4000, f2: 600, filtro: 'lowpass', v: .6 }, { t: .14, d: .08, f: 4000, f2: 600, filtro: 'lowpass', v: .6 }] },
            pin: { nomeItem: 'Escopeta', desc: 'Suas notas no mapa viram a escopeta da Rebecca.', img: 'escopeta_pin', bal: 1 },
            serv: { nomeItem: 'Servidor Barulhento', desc: 'O ícone do servidor pisca em rosa e ciano.', cores: [ROS, CIA], passos: true, dur: .4 },
        }),
    ],
});

// ============================================================================================ ADAM SMASHER
const olhoCibernetico = (anim) => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.o{animation:g 1.1s ease-in-out infinite alternate}.s{transform-origin:132px 36px;animation:r 4s linear infinite}@keyframes g{from{opacity:.55}to{opacity:1}}@keyframes r{to{transform:rotate(360deg)}}</style>` : ''}`
    + `<circle cx='132' cy='36' r='18' fill='#1a1c24' stroke='#14141c' stroke-width='2.6'/><circle cx='132' cy='36' r='14' fill='none' stroke='#6a7080' stroke-width='1.6'/><g class='s'><path d='M132 20V26M132 46V52M116 36H122M142 36H148' stroke='#9aa4b8' stroke-width='2'/></g><circle class='o' cx='132' cy='36' r='8.6' fill='${VRM}'/><circle cx='132' cy='36' r='3.4' fill='#ffd0d0'/><circle cx='129' cy='33' r='1.4' fill='#fff'/></svg>`;
const smasher = tema({
    id: 'edg_smasher', pre: 'sma', nome: 'Adam Smasher', cat: 'anime', cor: VRM, cores: [VRM, '#6a7080'], icone: 'fa-robot', premium: true,
    lema: 'Eu sou a lenda de Night City.',
    desc: 'Adam Smasher, o ciborgue que sobrou do homem: o olho vermelho, varredura de laser e faíscas de metal.',
    pal: { m: VRM, a: '#ff7a7a', d: '#0a0a14', l: '#fff', o: '#0a0a14' },
    itens: [
        MP('Olho Cibernético', 'O olho vermelho de um ciborgue no canto da foto, mirando e pulsando.', { svg: olhoCibernetico }, { r: 'epico' }),
        EA('Mira Travada', 'Um laser vermelho varre a sua foto de cima a baixo enquanto a mira trava.', [
            { k: 'aura', cor: '#ff2020', dur: 1.3 },
        ], { r: 'epico', id: 'sma_mira_travada', sobre: [{ k: 'scan', cor: '#ff2020', dur: 2.4 }, { k: 'vinheta', cor: '#ff2020', alfa: .45, pulso: 1.6 }] }),
        EP('Varredura', 'Linhas de varredura vermelhas descem pelo cartão e faíscas de metal saltam.', [
            { k: 'raw', html: '<i class="vr"></i><i class="va"></i>',
              css: '.ef-pf-$ID .vr{position:absolute;left:0;right:0;top:0;height:10%;background:linear-gradient(transparent,rgba(255,32,32,.55) 70%,#ff2020);animation:k-$ID-vr 3.4s linear infinite}.ef-pf-$ID .va{position:absolute;inset:0;background:repeating-linear-gradient(0deg,rgba(255,32,32,.12) 0 2px,transparent 2px 6px)}@keyframes k-$ID-vr{from{transform:translateY(-110%)}to{transform:translateY(1000%)}}' },
            { k: 'sobe', icones: ['brilho'], pals: [{ m: '#ff7a3a', a: '#ffd06a', d: '#a01a10', l: '#fff', o: '#2a0604', w: 1 }], n: 12, tam: [8, 14], vel: [3, 7], alfa: .9 },
            { k: 'borda', cor: VRM, alfa: .55, blur: 38, esp: 5, dur: 1.4 },
        ], { r: 'epico', id: 'sma_varredura' }),
        ...apoio({
            tema: T, r: 'epico',
            nome: { nomeItem: 'Lenda de Aço', desc: 'Aço e vermelho de olho cibernético com contorno preto.', grad: ['#9aa4b8', VRM, '#9aa4b8'], mov: 'pisca', dur: 1.4, piscaMin: .65, contorno: '#0a0a14', cw: 1.1, fonte: 'impacto', espaco: 1 },
            placa: { nomeItem: 'Blindagem', desc: 'Aço escuro com rebites vermelhos e o olho cibernético do lado.', base: ['#2a2e38', '#14161e'], pad: { tipo: 'grade', c1: 'rgba(255,32,32,.35)', c2: 'transparent', tam: 10 }, mov: 'x', dur: 12, borda: VRM, img: { nome: 'smasher_olho', lado: 'dir', tam: 90, y: 50 } },
            faixa: { nomeItem: 'Cidade Queimada', desc: 'Uma cidade em chamas vermelhas.', fundo: ['#0a0a14', '#2a0a0a', '#7a1410'],
                fixo: P.cena.skyline({ cor: '#06060c', altMin: 24, altMax: 76, larg: [8, 18], seed: 'sma1', janelas: { cor: '#ff2020', dens: .3 } }),
                 },
            fala: { nomeItem: 'Voz de Ferro', desc: 'Quando você fala na call, o card pisca em vermelho e aço.', cores: [VRM, '#6a7080'], passos: true, dur: .4 },
            radar: { nomeItem: 'Mira', desc: 'As ondas do radar viram anéis vermelhos tracejados, como uma mira.', cor: VRM, estilo: 'tracejado', glow: '#6a7080' },
            chat: { nomeItem: 'Faíscas de Metal', desc: 'A barra de mensagem acende em vermelho ao digitar e solta faíscas ao enviar.', cor: VRM, cor2: '#ffd06a', particula: { forma: 'losango' } },
            som: { nomeItem: 'Passos de Ferro', desc: 'Um passo pesado de metal e um zumbido grave de servo, ao entrar na call.', arquivo: 'smasher.mp3', notas: [{ t: 0, f: 60, f2: 35, d: .4, tipo: 'sawtooth', v: .6 }, { t: .55, f: 55, f2: 30, d: .4, tipo: 'sawtooth', v: .6 }, { t: .1, f: 160, f2: 150, d: .8, tipo: 'square', v: .12 }], ruidos: [{ t: 0, d: .2, f: 700, filtro: 'lowpass', v: .5 }, { t: .55, d: .2, f: 700, filtro: 'lowpass', v: .5 }] },
            pin: { nomeItem: 'Olho Vermelho', desc: 'Suas notas no mapa viram o olho cibernético do Adam Smasher.', img: 'smasher_olho' },
            serv: { nomeItem: 'Servidor de Aço', desc: 'O ícone do servidor pisca em vermelho e aço.', cores: [VRM, '#6a7080'], passos: true, dur: .6 },
        }),
    ],
});

module.exports = [david, lucy, rebecca, smasher];
