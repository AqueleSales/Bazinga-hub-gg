'use strict';
/* ARANHA: a teia, o sentido de aranha, a cidade ao entardecer; o MULTIVERSO (meio-tom e glitch); a CARNIFICINA (o simbionte vermelho) e os extras do SIMBIONTE.
   Aranha de verdade só como bichinho (nada de logo ou de rosto de personagem). Arte original. */
const { tema, M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P, I, fase } = require('../dsl');
const { cena } = P;
const { icone } = I;
const f1 = (n) => Math.round(n * 10) / 10;

const VER = { m: '#d4161e', a: '#ff6a6a', d: '#1a0a0a', l: '#ffffff', o: '#2a0408' };
const AZU = { m: '#1a3a8c', a: '#5a7ad8', d: '#0a1a4a', l: '#ffffff', o: '#050e2a' };
const PRE = { m: '#12121a', a: '#3a3a4a', d: '#05050a', l: '#ffffff', o: '#e8e8f0' };

// ---- a teia: raios saindo de um centro e fios curvos entre eles ----
function teiaPaths(cx, cy, r0, r1, n, aneis, a0 = 0, a1 = 360) {
    const pt = (a, r) => [cx + r * Math.cos(a * Math.PI / 180), cy + r * Math.sin(a * Math.PI / 180)];
    const passo = (a1 - a0) / n, raios = [], arcos = [];
    for (let k = 0; k <= n; k++) { const a = a0 + k * passo, [x0, y0] = pt(a, r0), [x1, y1] = pt(a, r1); raios.push(`M${f1(x0)} ${f1(y0)}L${f1(x1)} ${f1(y1)}`); }
    for (const r of aneis) for (let k = 0; k < n; k++) { const a = a0 + k * passo, [xa, ya] = pt(a, r), [xm, ym] = pt(a + passo / 2, r * .9), [xb, yb] = pt(a + passo, r); arcos.push(`M${f1(xa)} ${f1(ya)}Q${f1(xm)} ${f1(ym)} ${f1(xb)} ${f1(yb)}`); }
    return { raios, arcos };
}
const anelTeia = (() => { const t = teiaPaths(100, 100, 66, 99, 16, [72, 82, 92, 98]); return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><g fill='none' stroke='#f4f4fa' stroke-width='1.5' stroke-linecap='round' opacity='.95'><path d='${t.raios.join('')}'/><path d='${t.arcos.join('')}' stroke-width='1.2'/></g></svg>`; })();

const teiaGrande = (cx, cy, rot) => { const t = teiaPaths(cx, cy, 6, 430, 8, [40, 78, 120, 168, 222, 284, 352, 430], rot, rot + 90); let h = ''; t.raios.forEach((d, k) => { h += `<path pathLength="1" d="${d}" style="--i:${k * .5}"/>`; }); t.arcos.forEach((d, k) => { h += `<path pathLength="1" d="${d}" style="--i:${4 + Math.floor(k / 8) * 1.1 + (k % 8) * .12}"/>`; }); return `<svg class="tg" viewBox="0 0 340 440" preserveAspectRatio="xMinYMin slice"><g fill="none" stroke="#f4f4fa" stroke-width="1.6" stroke-linecap="round">${h}</g></svg>`; };

const cidade = `${cena.estrelas({ cor: '#fff', n: 18, y: [0, 44], r: [.5, 1.2], seed: 'ar1' })}${cena.sol({ x: 250, y: 66, r: 24, c1: '#ffe9a0', c2: '#ff8a2a' })}${cena.skyline({ cor: '#14102a', altMin: 26, altMax: 74, larg: [10, 22], seed: 'ar2', janelas: { cor: '#ffd070', dens: .3 } })}`
    + `<g fill='none' stroke='#fff' stroke-width='1.3' opacity='.9'><path d='M30 0C60 40 120 60 170 38'/><path d='M170 38C200 26 240 28 262 6' /><path d='M0 22C40 56 80 40 90 4' opacity='.7'/></g><circle cx='170' cy='38' r='2.6' fill='#fff'/>`;

const aranha = tema({
    id: 'teia', pre: 'tei', nome: 'Teia', cat: 'quadrinhos', cor: '#d4161e', cores: ['#d4161e', '#1a3a8c'], icone: 'fa-spider', premium: true,
    lema: 'Grandes poderes, grandes pings.',
    desc: 'A teia que se desenha sozinha, o sentido de aranha vibrando, uma cidade ao entardecer e o vermelho e azul de quem vive pendurado nos prédios.',
    pal: VER,
    itens: [
        M('Teia', 'Uma teia de aranha em volta da foto, fina e brilhante, girando bem devagar.', { t: 'svg', svg: anelTeia, giro: 120, glow: '#ffffff', inset: .26 }, { r: 'epico', id: 'tei_teia' }),
        N('Aranha', 'Vermelho e azul de uniforme, com contorno branco fino e uma teia no fim do nome.', { grad: ['#e0161e', '#2a52c8', '#e0161e'], mov: 'desliza', dur: 5, contorno: '#ffffff', cw: .9, fonte: 'impacto', espaco: .8, peso: 900, icone: { nome: 'teia', pos: 'depois', pal: { m: '#ffffff' } } }, { r: 'epico' }),
        Pl('Máscara', 'O vermelho de uma máscara com teia preta e duas lentes brancas que piscam ao lado.', { base: ['#d4161e', '#a00f16'], pad: { tipo: 'icones', icones: ['teia'], pals: [{ m: '#2a0408', a: '#2a0408', d: '#2a0408', l: '#2a0408', o: '#2a0408', w: 0 }], tam: 34, ti: 26, c2: 'transparent' }, mov: 'x', dur: 26, borda: '#000', icone: { nome: 'lentes', pal: { ...VER, l: '#ffffff', o: '#000' }, lado: 'dir', tam: 52 } }, { r: 'epico' }),
        F('Cidade ao Entardecer', 'Uma cidade em silhueta num pôr do sol alaranjado, com fios de teia atravessando o céu.', {
            fundo: ['#1a2a6a', '#d4561e', '#ffb04a'], fixo: cidade,
            longe: { svg: `<g opacity='.45'>${cena.nuvens({ cor: '#3a1a4a', n: 3, y: [10, 40], tam: [16, 26], seed: 'ar3' })}</g>`, anim: 'pan', dur: 52 },
            perto: { svg: cena.estrelas({ cor: '#ffe9a0', n: 12, y: [8, 70], seed: 'ar4' }), anim: 'pisca', dur: 2.4 },
        }, { r: 'epico' }),
        EA('Sentido de Aranha', 'Riscos tremem em volta da cabeça na sua foto, num aviso, e um brilho vermelho pulsa.', [
            { k: 'aura', cor: '#d4161e', dur: 1.4 },
            { k: 'raw', html: '<b class="$C"><svg viewBox="0 0 160 160" class="sa"><g fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round">' + [-60, -40, -20, 0, 20, 40, 60].map((a) => { const r0 = 56, r1 = 70, ar = (a - 90) * Math.PI / 180; return `<path d="M${f1(80 + r0 * Math.cos(ar))} ${f1(80 + r0 * Math.sin(ar))}L${f1(80 + r1 * Math.cos(ar))} ${f1(80 + r1 * Math.sin(ar))}"/>`; }).join('') + '</g></svg></b>',
              css: '.ef-av-$ID .sa{position:absolute;inset:0;width:100%;height:100%;overflow:visible;filter:drop-shadow(0 0 3px #d4161e);animation:k-$ID-sa .16s steps(2) infinite}@keyframes k-$ID-sa{0%{transform:translate(0,0) scale(1)}50%{transform:translate(.8px,-.8px) scale(1.03)}100%{transform:translate(-.8px,.8px) scale(.99)}}' },
        ], { r: 'epico', id: 'tei_sentido' }),
        EA('Fios de Teia', 'Fios de teia disparam das bordas, grudam na foto e somem, de tempos em tempos.', [
            { k: 'raw', html: '<b class="$C"><svg viewBox="0 0 160 160" class="fw"><g fill="none" stroke="#f4f4fa" stroke-width="1.8" stroke-linecap="round">' + [[0, 20, 50, 56], [160, 14, 112, 54], [4, 146, 48, 108], [156, 150, 114, 106]].map(([x, y, x2, y2], k) => `<path pathLength="1" d="M${x} ${y}L${x2} ${y2}" style="--i:${k * .25}"/>`).join('') + '</g></svg></b>',
              css: `.ef-av-$ID .fw{position:absolute;inset:0;width:100%;height:100%;overflow:visible;filter:drop-shadow(0 0 2px #d4161e)}.ef-av-$ID .fw path{stroke-dasharray:1;stroke-dashoffset:1;animation:k-$ID-fw 5s ease-out calc(var(--i) + ${fase(5, .3)}) infinite}@keyframes k-$ID-fw{0%{stroke-dashoffset:1;opacity:1}12%{stroke-dashoffset:0}60%{stroke-dashoffset:0;opacity:1}78%,100%{stroke-dashoffset:0;opacity:0}}` },
            { k: 'aura', cor: '#1a3a8c', dur: 3 },
        ], { r: 'epico', id: 'tei_fios' }),
        EP('Teia Gigante', 'Uma teia enorme se desenha no canto do cartão, fio por fio, e uma aranha desce por um fio.', [
            { k: 'raw', html: `${teiaGrande(0, 0, 0)}<svg class="tg tg2" viewBox="0 0 340 440" preserveAspectRatio="xMaxYMax slice" style="transform:scale(-1,-1)"><g fill="none" stroke="#f4f4fa" stroke-width="1.6" stroke-linecap="round">${(() => { const t = teiaPaths(0, 0, 6, 330, 6, [50, 100, 160, 230, 330], 0, 90); let h = ''; t.raios.forEach((d, k) => { h += `<path pathLength="1" d="${d}" style="--i:${3 + k * .4}"/>`; }); t.arcos.forEach((d, k) => { h += `<path pathLength="1" d="${d}" style="--i:${6 + Math.floor(k / 6) * .9 + (k % 6) * .1}"/>`; }); return h; })()}</g></svg><i class="fio"></i><svg class="ar" viewBox="0 0 100 100">${icone('aranha', { m: '#14141c', a: '#14141c', d: '#14141c', l: '#d4161e', o: '#f4f4fa', w: 3 })}</svg>`,
              css: `.ef-pf-$ID .tg{position:absolute;inset:0;width:100%;height:100%;overflow:visible;filter:drop-shadow(0 0 2px rgba(255,255,255,.55))}.ef-pf-$ID .tg path{stroke-dasharray:1;stroke-dashoffset:1;animation:k-$ID-tg 12s ease-out calc(var(--i) * .5s + ${fase(12, .5)}) infinite}.ef-pf-$ID .fio{position:absolute;left:78%;top:0;width:1.6px;height:30%;background:#f4f4fa;transform-origin:50% 0;animation:k-$ID-fio 12s ease-in-out ${fase(12, .5)} infinite}.ef-pf-$ID .ar{position:absolute;left:78%;top:0;width:11cqw;height:11cqw;margin-left:-5.5cqw;animation:k-$ID-ar 12s ease-in-out ${fase(12, .5)} infinite}`
                  + `@keyframes k-$ID-tg{0%{stroke-dashoffset:1;opacity:1}8%{stroke-dashoffset:0}72%{stroke-dashoffset:0;opacity:1}88%,100%{stroke-dashoffset:0;opacity:0}}@keyframes k-$ID-fio{0%,30%{transform:scaleY(0);opacity:1}50%,66%{transform:scaleY(1);opacity:1}82%,100%{transform:scaleY(0);opacity:0}}@keyframes k-$ID-ar{0%,30%{transform:translateY(0);opacity:0}34%{opacity:1}50%,66%{transform:translateY(calc(30cqh - 5.5cqw));opacity:1}82%,100%{transform:translateY(0);opacity:0}}` },
        ], { r: 'lendario', id: 'tei_gigante' }),
        FALA('Alerta de Aranha', 'Quando você fala na call, o card pisca em vermelho e azul.', { cores: ['#d4161e', '#1a3a8c'], passos: true }),
        RADAR('Fios de Teia', 'As ondas do radar viram anéis brancos finos, como fios de teia.', { cor: '#f4f4fa', estilo: 'liso', glow: '#d4161e' }),
        CHAT('Thwip', 'A barra de mensagem acende em vermelho ao digitar e solta teias ao enviar.', { cor: '#d4161e', cor2: '#1a3a8c', particula: { icone: 'teia', pal: { m: '#f4f4fa' } } }),
        PIN('Aranhinha', 'Suas notas no mapa viram uma aranhinha pendurada.', { icone: 'aranha', pal: { m: '#14141c', a: '#14141c', d: '#14141c', l: '#d4161e', o: '#f4f4fa', w: 3 }, bal: 2 }),
        SOM('Thwip', 'O estalo seco de um disparo de teia e o sopro do balanço, ao entrar na call.', { notas: [{ t: 0, f: 1400, f2: 300, d: .09, tipo: 'square', v: .5 }, { t: .1, f: 400, f2: 900, d: .4, tipo: 'sine', v: .2 }], ruidos: [{ t: 0, d: .08, f: 5000, filtro: 'highpass', v: .6 }, { t: .08, d: .5, f: 300, f2: 2400, filtro: 'bandpass', v: .35, q: 1.4 }] }),
        SERV('Servidor da Vizinhança', 'O ícone do servidor pisca em vermelho e azul.', { cores: ['#d4161e', '#1a3a8c'], passos: true }),
    ],
});

// ---------------------------------------------------------------------------------------- MULTIVERSO (meio-tom e glitch)
const MG = { m: '#ff2d95', a: '#ff8ac8', d: '#14061e', l: '#ffffff', o: '#000000' };
const CI = { m: '#22e4ff', a: '#8af0ff', d: '#06242e', l: '#ffffff', o: '#000000' };
const benDay = (cor, alfa = .35) => { let s = ''; for (let y = 5; y < 112; y += 8) for (let x = (y / 8) % 2 ? 4 : 0; x < 340; x += 8) s += `<circle cx='${x}' cy='${y}' r='2.3' fill='${cor}' opacity='${alfa}'/>`; return s; };
const anelAberracao = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><g fill='none' stroke-width='5' stroke-dasharray='58 14'><circle cx='98' cy='100' r='76' stroke='#ff2d95'/><circle cx='102' cy='100' r='76' stroke='#22e4ff'/></g><circle cx='100' cy='100' r='84' fill='none' stroke='#fff' stroke-width='2' stroke-dasharray='2 8' stroke-linecap='round'/></svg>`;
const multiverso = tema({
    id: 'aranhaverso', pre: 'mvs', nome: 'Multiverso', cat: 'quadrinhos', cor: '#ff2d95', cores: ['#ff2d95', '#22e4ff'], icone: 'fa-layer-group',
    lema: 'Em qualquer dimensão, você é o único.',
    desc: 'Meio-tom de gibi, cores que se descolam como num cartaz mal impresso, glitch de dimensão e grafite: o multiverso do desenho.',
    pal: MG,
    itens: [
        M('Aberração', 'Um anel rosa e outro ciano levemente deslocados, como uma impressão que escapou do registro.', { t: 'svg', svg: anelAberracao, giro: 60, inset: .26 }, { r: 'raro' }),
        N('Multiverso', 'Branco com contorno preto que de vez em quando racha em rosa e ciano, como um glitch.', { cor: '#ffffff', mov: 'glitch', g1: '#ff2d95', g2: '#22e4ff', dur: 3.2, contorno: '#000', cw: 1.2, fonte: 'quadrinho', peso: 900, sombra: [1.4, 1.4, '#000'] }, { r: 'raro' }),
        Pl('Grafite', 'Pontinhos de gibi sobre o roxo-escuro, um brilho ciano e uma aranhinha ao lado.', { base: ['#1a0a30', '#2a1050'], pad: { tipo: 'bolinhas', c1: 'rgba(255,45,149,.55)', c2: 'transparent', tam: 8, r: .34 }, mov: 'x', dur: 6, brilho: 'rgba(34,228,255,.4)', borda: 'rgba(34,228,255,.8)', icone: { nome: 'aranha', pal: { m: '#22e4ff', a: '#22e4ff', d: '#06242e', l: '#ff2d95', o: '#000', w: 3 }, lado: 'dir', tam: 62 } }, { r: 'raro' }),
        F('Dimensões', 'Planos rosa e ciano se cortando na diagonal, com pontos de impressão e barras de glitch.', {
            fundo: ['#14061e'], fixo: `<path d='M0 0H210L130 112H0Z' fill='#ff2d95'/><path d='M210 0H340V112H130Z' fill='#22e4ff'/>${benDay('#000', .28)}<path d='M210 0L130 112' stroke='#fff' stroke-width='3'/>`,
            longe: { svg: `<rect x='0' y='30' width='340' height='4' fill='#fff' opacity='.7'/><rect x='80' y='64' width='180' height='3' fill='#14061e' opacity='.8'/><rect x='20' y='90' width='120' height='3' fill='#fff' opacity='.6'/>`, anim: 'pan', dur: 3 },
            perto: { svg: cena.icones({ nomes: ['brilho'], pals: [{ m: '#fff', o: '#000', w: 3 }], n: 5, tam: [10, 16], seed: 'mv1', y: [8, 100] }), anim: 'pisca', dur: 1.6 },
        }, { r: 'raro' }),
        EA('Salto Dimensional', 'Barras de glitch rosa e ciano cortam a sua foto e o brilho de uma outra dimensão aparece em volta.', [
            { k: 'aura', cor: '#ff2d95', dur: 2.2 },
            { k: 'anel', cor: '#22e4ff', r: 68, esp: 2.2, dash: '4 6', giro: 12 },
        ], { r: 'raro', sobre: [{ k: 'glitch', c1: '#ff2d95', c2: '#22e4ff', dur: 3 }] }),
        EP('Colisão de Dimensões', 'Duas faixas, uma rosa e outra ciana, atravessam o cartão e se encontram num clarão.', [
            { k: 'raw', html: '<i class="b1"></i><i class="b2"></i><i class="gl"></i>',
              css: `.ef-pf-$ID .b1,.ef-pf-$ID .b2{position:absolute;top:-10%;width:60%;height:120%;opacity:0;mix-blend-mode:screen}.ef-pf-$ID .b1{left:-60%;background:linear-gradient(100deg,transparent,#ff2d95 40%,#ff8ac8);transform:skewX(-14deg);animation:k-$ID-a 7s ease-in-out ${fase(7, .3)} infinite}.ef-pf-$ID .b2{right:-60%;background:linear-gradient(260deg,transparent,#22e4ff 40%,#8af0ff);transform:skewX(-14deg);animation:k-$ID-b 7s ease-in-out ${fase(7, .3)} infinite}.ef-pf-$ID .gl{position:absolute;inset:0;background:repeating-linear-gradient(0deg,rgba(255,255,255,.12) 0 2px,transparent 2px 6px);opacity:0;animation:k-$ID-g 7s steps(1,end) ${fase(7, .3)} infinite}`
                  + `@keyframes k-$ID-a{0%,10%{opacity:0;left:-60%}30%{opacity:.85;left:10%}44%{opacity:.85;left:20%}60%,100%{opacity:0;left:60%}}@keyframes k-$ID-b{0%,10%{opacity:0;right:-60%}30%{opacity:.85;right:10%}44%{opacity:.85;right:20%}60%,100%{opacity:0;right:60%}}@keyframes k-$ID-g{0%,34%{opacity:0}36%{opacity:1;transform:translateX(3px)}40%{opacity:.6;transform:translateX(-4px)}44%,100%{opacity:0}}` },
            { k: 'pisca', icone: 'brilho', pals: [{ m: '#fff', o: '#ff2d95', w: 2 }], n: 8, tam: [8, 13] },
        ], { r: 'epico' }),
    ],
});

// ---------------------------------------------------------------------------------------- CARNIFICINA (o simbionte vermelho)
const CV = { m: '#b00018', a: '#ff4a5a', d: '#1a0003', l: '#ffd0d4', o: '#1a0003' };
const veias = (() => { let s = ''; const R = I.paleta ? null : null; for (let k = 0; k < 9; k++) { const x = 18 + k * 38 + (k % 2) * 6, h = 40 + (k * 17) % 34; s += `<path d='M${x} 120C${x - 12} ${120 - h * .4} ${x + 14} ${120 - h * .7} ${x - 4} ${120 - h}' fill='none' stroke='#b00018' stroke-width='${4 + (k % 3)}' stroke-linecap='round'/><path d='M${x} 120C${x - 12} ${120 - h * .4} ${x + 14} ${120 - h * .7} ${x - 4} ${120 - h}' fill='none' stroke='#ff4a5a' stroke-width='1.4' stroke-linecap='round' opacity='.7'/>`; } return s; })();
const carnificina = tema({
    id: 'carnificina', pre: 'crn', nome: 'Carnificina', cat: 'quadrinhos', cor: '#b00018', cores: ['#b00018', '#1a0003'], icone: 'fa-droplet',
    lema: 'Vermelho. Vivo. Faminto.',
    desc: 'O simbionte vermelho: veias que pulsam, sangue escorrendo e uma névoa escarlate que respira.',
    pal: CV,
    itens: [
        M('Veias', 'Um anel de espinhos vermelho-sangue com contorno preto, girando devagar em volta da foto.', { t: 'forma', forma: 'espinhos', n: 16, amp: 7, esp: 12, cor: '#b00018', cor2: '#ff4a5a', linha: '#1a0003', lw: 2.6, giro: 70 }, { r: 'epico' }),
        N('Carnificina', 'Vermelho escuro com contorno preto, pingando um brilho de sangue.', { grad: ['#8a0012', '#ff4a5a', '#8a0012'], mov: 'gotejar', brilho: '#ff2030', dur: 2.8, contorno: '#1a0003', cw: 1.1, fonte: 'impacto', espaco: .8, peso: 900 }, { r: 'epico' }),
        Pl('Fios Vermelhos', 'Ondas vermelhas se retorcendo sobre o preto, com uma gota ao lado.', { base: ['#1a0003', '#3a0008'], pad: { tipo: 'ondas', c1: 'rgba(255,48,64,.4)', c2: 'transparent', tam: 14 }, mov: 'x', dur: 8, brilho: 'rgba(255,74,90,.4)', borda: 'rgba(255,48,64,.7)', icone: { nome: 'gota_sangue', pal: CV, lado: 'dir', tam: 62 } }, { r: 'epico' }),
        F('Veias Vivas', 'Um fundo preto e vermelho com veias que sobem do chão e gotas piscando.', {
            fundo: ['#0a0002', '#3a0008', '#7a0014'], fixo: veias,
            longe: { svg: `<g opacity='.35'>${cena.nuvens({ cor: '#ff2030', n: 3, y: [20, 80], tam: [18, 28], seed: 'cr1' })}</g>`, anim: 'pan', dur: 40 },
            perto: { svg: cena.icones({ nomes: ['gota_sangue'], pals: [CV], n: 7, tam: [8, 13], seed: 'cr2', y: [8, 96] }), anim: 'pisca', dur: 2.8 },
        }, { r: 'epico' }),
        EA('Fúria', 'Uma aura escarlate pulsa em volta da foto e o sangue escorre pelo alto dela.', [
            { k: 'aura', cor: '#ff2030', dur: 1.8 },
            { k: 'faiscas', icone: 'espinho', pals: [{ m: '#ff4a5a', o: '#1a0003', w: 3 }], n: 7, tam: 8, raio: 39 },
        ], { r: 'epico', sobre: [{ k: 'pingos', cor: '#b00018', n: 6, dur: 6 }] }),
        EP('Sangue Vivo', 'Uma névoa escarlate respira, gotas sobem e a borda do cartão pulsa como um coração.', [
            { k: 'clima', fundo: 'radial-gradient(ellipse at 50% 100%,rgba(176,0,24,.7),transparent 65%)', min: .3, max: 1, dur: 2.6 },
            { k: 'neblina', cor: '#b00018', alfa: .4, n: 4 },
            { k: 'sobe', icones: ['gota_sangue'], pals: [CV], n: 12, tam: [10, 20], vel: [6, 11], alfa: .9 },
            { k: 'borda', cor: '#ff2030', alfa: .5, dur: 1.5 },
        ], { r: 'lendario' }),
        PIN('Gota', 'Suas notas no mapa viram uma gota de sangue.', { icone: 'gota_sangue', pal: CV, bal: 2 }),
    ],
});

// ---------------------------------------------------------------------------------------- extras do SIMBIONTE (tema feito à mão; aqui só entram itens novos)
const SB = { m: '#07070c', a: '#2a2a3c', d: '#07070c', l: '#ffffff', o: '#f3f5ff', w: 3 };
const simbionteExtras = tema({
    id: 'simbionte', pre: 'sim', nome: 'Simbionte', cat: 'quadrinhos', cor: '#c9cfe6', cores: ['#0a0a10', '#dfe3f5'], icone: 'fa-spider', existente: true,
    lema: 'Nós somos um só.', desc: 'Extras do tema Simbionte.',
    pal: SB,
    itens: [
        FALA('Olhos na Call', 'Quando você fala na call, o card ganha um contorno branco que pulsa sobre o preto.', { cores: ['#f3f5ff', '#2a2a3c'] }, { r: 'epico', id: 'sim_olhos_na_call' }),
        RADAR('Ondas Negras', 'As ondas do radar viram anéis duplos brancos sobre o escuro.', { cor: '#f3f5ff', estilo: 'duplo', glow: '#ffffff' }, { r: 'epico', id: 'sim_ondas_negras' }),
        CHAT('Gosma', 'A barra de mensagem acende em branco ao digitar e solta gotas de gosma preta ao enviar.', { cor: '#f3f5ff', cor2: '#aab4ff', particula: { icone: 'gota', pal: SB } }, { r: 'epico', id: 'sim_gosma' }),
        PIN('Aranhinha Negra', 'Suas notas no mapa viram uma aranhinha preta de contorno branco.', { icone: 'aranha', pal: SB, bal: 2 }, { r: 'epico', id: 'sim_aranhinha' }),
        SOM('Rosnado', 'Um rosnado grave que se arrasta e um chiado, ao entrar na call.', { notas: [{ t: 0, f: 70, f2: 48, d: .7, tipo: 'sawtooth', v: .6 }, { t: .1, f: 140, f2: 90, d: .55, tipo: 'sawtooth', v: .3 }], ruidos: [{ t: .25, d: .6, f: 1800, f2: 6000, filtro: 'bandpass', v: .45, q: .8 }] }, { r: 'epico', id: 'sim_rosnado' }),
        SERV('Servidor Simbionte', 'O ícone do servidor ganha um brilho branco que respira sobre o preto.', { cores: ['#f3f5ff', '#2a2a3c'] }, { r: 'epico', id: 'sim_servidor' }),
    ],
});

module.exports = [aranha, multiverso, carnificina, simbionteExtras];
