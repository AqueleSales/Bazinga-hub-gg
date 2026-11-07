'use strict';
/* JOJO: VENTO ÁUREO (Rodada 40, lendário). Um tema por personagem, só com SÍMBOLOS e OBJETOS da obra desenhados por código (joaninha, zíper, bala, cápsula, coração...; o dono mandou tirar os personagens e os Stands). Os ids dos temas começam com `jj_` pra não bater com os genéricos já existentes (Vento Dourado etc.). */
const { tema, MP, EA, EP, P, R, B, IMG, ORBITA, apoio, fase } = require('../dsl');
const f1 = B.f1;
const T = 'jojo';
const url = (n) => R.url(T, n);

// ============================================================================================ peças em SVG (quadro 160, foto = círculo de raio 50 em 80,80)
const zipper = (anim) => {
    let dentes = '';
    for (let k = 0; k < 24; k++) { const a = (-12 + k * 5) * Math.PI / 180, r = 54, x = 80 + r * Math.cos(a), y = 80 + r * Math.sin(a), lado = k % 2 ? 2.1 : -2.1; dentes += `<rect x='${f1(x - 2.4)}' y='${f1(y - 1.5 + lado * .2)}' width='4.8' height='3.6' rx='.8' transform='rotate(${f1(-12 + k * 5 + 90)} ${f1(x)} ${f1(y)}) translate(${lado} 0)' fill='#e8b94a' stroke='#6b4a10' stroke-width='.7'/>`; }
    return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.sl{transform-origin:80px 80px;animation:z 5s ease-in-out infinite}@keyframes z{0%,6%{transform:rotate(-12deg)}46%,54%{transform:rotate(103deg)}94%,100%{transform:rotate(-12deg)}}</style>` : ''}`
        + `<path d='M${f1(80 + 54 * Math.cos(-12 * Math.PI / 180))} ${f1(80 + 54 * Math.sin(-12 * Math.PI / 180))}A54 54 0 0 1 ${f1(80 + 54 * Math.cos(108 * Math.PI / 180))} ${f1(80 + 54 * Math.sin(108 * Math.PI / 180))}' fill='none' stroke='#e8ecf4' stroke-width='8' stroke-linecap='round'/>`
        + `<path d='M${f1(80 + 54 * Math.cos(-12 * Math.PI / 180))} ${f1(80 + 54 * Math.sin(-12 * Math.PI / 180))}A54 54 0 0 1 ${f1(80 + 54 * Math.cos(108 * Math.PI / 180))} ${f1(80 + 54 * Math.sin(108 * Math.PI / 180))}' fill='none' stroke='#9aa6c0' stroke-width='1' stroke-linecap='round' transform='translate(0 0)' opacity='.8'/>${dentes}`
        + `<g class='sl'><g transform='translate(134 80)'><path d='M-6 -7L6 -5L6 5L-6 7Z' fill='#f3d27a' stroke='#6b4a10' stroke-width='1.4' stroke-linejoin='round'/><path d='M6 0L16 0' stroke='#6b4a10' stroke-width='5' stroke-linecap='round'/><ellipse cx='20' cy='0' rx='6' ry='8.5' fill='#f3d27a' stroke='#6b4a10' stroke-width='1.6'/><ellipse cx='21' cy='0' rx='2.6' ry='4.6' fill='#14203a'/></g></g></svg>`;
};
const tambor = (anim) => {
    let furos = '';
    for (let k = 0; k < 6; k++) { const a = k * 60 * Math.PI / 180; furos += `<circle cx='${f1(30 * Math.cos(a))}' cy='${f1(30 * Math.sin(a))}' r='9' fill='#0c0c12' stroke='#5a6070' stroke-width='2.2'/>`; }
    return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.t{transform-origin:122px 122px;animation:g 7s linear infinite}@keyframes g{0%,10%{transform:rotate(0)}22%,35%{transform:rotate(60deg)}47%,60%{transform:rotate(120deg)}72%,85%{transform:rotate(180deg)}100%{transform:rotate(240deg)}}</style>` : ''}`
        + `<defs><radialGradient id='a' cx='.4' cy='.35'><stop offset='0' stop-color='#f0f3f8'/><stop offset='.6' stop-color='#9aa4b8'/><stop offset='1' stop-color='#566074'/></radialGradient></defs>`
        + `<g transform='translate(122 122) scale(.62)'><g class='t' style='transform-origin:0 0'><circle r='46' fill='url(#a)' stroke='#14141c' stroke-width='3.4'/>${furos}<circle r='8' fill='#2a2f3c' stroke='#14141c' stroke-width='2'/></g></g></svg>`;
};
const capsula = (anim) => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.g1,.g2,.g3{opacity:0;animation:v 3s ease-out infinite}.g2{animation-delay:-1s}.g3{animation-delay:-2s}.c{transform-origin:128px 118px;animation:b 3s ease-in-out infinite alternate}@keyframes v{0%{transform:translate(0,0) scale(.5);opacity:0}20%{opacity:.8}100%{transform:translate(8px,-34px) scale(1.7);opacity:0}}@keyframes b{from{transform:rotate(-30deg)}to{transform:rotate(-20deg)}}</style>` : ''}`
    + `<g fill='#a455e8' opacity='.7'><circle class='g1' cx='132' cy='104' r='7'/><circle class='g2' cx='126' cy='108' r='6'/><circle class='g3' cx='136' cy='110' r='5'/></g>`
    + `<g class='c' transform='rotate(-25 128 118)'><rect x='108' y='108' width='40' height='20' rx='10' fill='#e03a5a' stroke='#3a0a18' stroke-width='2.4'/><path d='M128 108H138A10 10 0 0 1 138 128H128Z' fill='#8e4ad8' stroke='#3a0a18' stroke-width='2.4' stroke-linejoin='round'/><path d='M112 112H126' stroke='#ff9aa8' stroke-width='2.2' stroke-linecap='round'/></g></svg>`;
const gotasTrish = (anim) => {
    const xs = [38, 62, 90, 116];
    let g = '';
    xs.forEach((x, k) => { g += `<g class='d${k}'><path d='M${x - 4} 128L${x - 4} 132C${x - 4} 142 ${x} 146 ${x} 146C${x} 146 ${x + 4} 142 ${x + 4} 132L${x + 4} 128Z' fill='#ff8ac8' stroke='#9a2a78' stroke-width='1.6' stroke-linejoin='round'/><ellipse cx='${x - 1}' cy='134' rx='1.2' ry='2.4' fill='#ffd0ea'/></g>`; });
    return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>${xs.map((x, k) => `.d${k}{transform-origin:${x}px 128px;animation:p ${3.2 + k * .5}s ease-in-out ${-k * .8}s infinite}`).join('')}@keyframes p{0%,100%{transform:scaleY(.55)}55%{transform:scaleY(1.35)}}</style>` : ''}`
        + `<path d='M28 120A58 58 0 0 0 132 120' fill='none' stroke='#ff8ac8' stroke-width='9' stroke-linecap='round'/><path d='M30 118A56 56 0 0 0 130 118' fill='none' stroke='#ffd0ea' stroke-width='2' stroke-linecap='round' opacity='.7'/>${g}</svg>`;
};
const radarPeca = (anim) => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 160'>${anim ? `<style>.p{transform-origin:128px 40px;animation:r 3s linear infinite}@keyframes r{to{transform:rotate(360deg)}}.o{animation:o 3s ease-out infinite}@keyframes o{0%{opacity:.9;transform:scale(.4)}100%{opacity:0;transform:scale(1.5)}}.o{transform-origin:128px 40px}</style>` : ''}`
    + `<circle cx='128' cy='40' r='20' fill='#0c1a12' stroke='#14141c' stroke-width='3'/><circle cx='128' cy='40' r='20' fill='none' stroke='#4be07a' stroke-width='1.4' opacity='.7'/><circle cx='128' cy='40' r='11' fill='none' stroke='#4be07a' stroke-width='1' opacity='.5'/>`
    + `<g class='p'><path d='M128 40L128 20A20 20 0 0 1 143 27Z' fill='#4be07a' opacity='.55'/><path d='M128 40L128 20' stroke='#9affb8' stroke-width='1.6'/></g><circle class='o' cx='128' cy='40' r='20' fill='none' stroke='#4be07a' stroke-width='1.6'/><circle cx='134' cy='33' r='2' fill='#c8ffd8'/></svg>`;

// ============================================================================================ GIORNO
const OURO = '#f2c230', ROSA = '#d63a8a', MAR = '#1a2a6a';
const giorno = tema({
    id: 'jj_giorno', pre: 'jgi', nome: 'Giorno Giovanna', cat: 'anime', cor: OURO, cores: [OURO, ROSA], icone: 'fa-seedling', premium: true,
    lema: 'Eu tenho um sonho.',
    desc: 'O broche da joaninha, joaninhas voando, o ゴゴゴ e brilhos dourados. E o tempo que se apaga quando você fica parado.',
    pal: { m: OURO, a: '#ffe27a', d: '#7a5a10', l: '#fff', o: '#3a2a08' },
    itens: [
        MP('Broche da Joaninha', 'O broche de joaninha rosa do Giorno preso na borda da foto, pulsando.', { imagem: { url: url('joaninha'), ratio: R.proporcao(T, 'joaninha'), x: 12, y: 86, w: 30, rot: -12, anim: 'pulsa', dur: 2.4 } }, { r: 'lendario' }),
        EA('Joaninhas Douradas', 'Joaninhas voam em volta da sua foto e brilhos dourados piscam.', [
            ORBITA({ tema: T, imgs: ['joaninha'], n: 3, raio: 33, w: 12, dur: 7, nome: 'jn' }),
            { k: 'faiscas', icone: 'brilho', pals: [{ m: '#ffe27a', o: '#7a5a10', w: 2 }], n: 8, tam: 7, raio: 38 },
        ], { r: 'lendario', id: 'jgi_joaninhas_douradas' }),
        EP('Vento Dourado', 'Os ゴゴゴ tremem ao lado e folhas douradas caem, com a borda pulsando em dourado.', [
            IMG({ tema: T, img: 'gogogo', onde: 'pf', n: 'gg', x: 14, y: 52, w: 24, ciclo: 9, ini: 6, fim: 66, de: { x: -10, esc: .7 }, sai: { x: -10, esc: .7 }, bob: 1.2 }),
            { k: 'cai', icones: ['folha'], pals: [{ m: '#f2c230', a: '#ffe27a', d: '#7a5a10', l: '#fff', o: '#3a2a08' }], n: 10, tam: [14, 22], vel: [7, 13] },
            { k: 'borda', cor: OURO, alfa: .5, blur: 40, esp: 5, dur: 3 },
        ], { r: 'lendario', id: 'jgi_vento_dourado' }),
        ...apoio({
            tema: T,
            nome: { nomeItem: 'Gioia', desc: 'Dourado e rosa com contorno escuro e a joaninha ao lado do nome.', grad: [OURO, ROSA, OURO], mov: 'desliza', dur: 3.6, contorno: '#2a1a08', cw: 1.1, fonte: 'impacto', img: 'joaninha', imgW: 1.1, imgH: 1.1 },
            placa: { nomeItem: 'Passione', desc: 'Azul-marinho e losangos dourados, com uma joaninha do lado.', base: [MAR, '#2b1a5a'], pad: { tipo: 'losangos', c1: 'rgba(242,194,48,.25)', c2: 'transparent', tam: 12 }, mov: 'x', dur: 9, borda: 'rgba(242,194,48,.8)', img: { nome: 'joaninha', lado: 'dir', tam: 84, y: 50 } },
            faixa: { nomeItem: 'Vento Áureo', desc: 'Um céu de ouro com raios de sol e brilhos.', fundo: ['#f6d86a', '#f2a830'],
                perto: { svg: P.cena.icones({ nomes: ['brilho'], pals: [{ m: '#fff', a: '#ffe27a', d: '#7a5a10', l: '#fff', o: '#7a5a10', w: 2 }], n: 7, tam: [8, 14], seed: 'jgi1', y: [6, 100] }), anim: 'pisca', dur: 2.2 },
                css: `.banner-anim-$ID::after{background:repeating-conic-gradient(from 0deg at 28% 70%,rgba(255,255,255,.35) 0 6deg,transparent 6deg 16deg)!important;opacity:.55}` },
            fala: { nomeItem: 'Ouro', desc: 'Quando você fala na call, o card pisca em dourado e rosa.', cores: [OURO, ROSA], passos: true, dur: .5 },
            radar: { nomeItem: 'Ondas de Vida', desc: 'As ondas do radar viram anéis dourados pontilhados, como sementes.', cor: OURO, estilo: 'pontilhado', glow: ROSA },
            chat: { nomeItem: 'Joaninhas', desc: 'A barra de mensagem acende em dourado ao digitar e solta joaninhas ao enviar.', cor: OURO, cor2: ROSA, particula: { img: url('joaninha'), tam: 16 } },
            som: { nomeItem: 'Broto de Ouro', desc: 'Um brilho dourado que cresce como uma folha nascendo, ao entrar na call.', arquivo: 'jojo_giorno.mp3', notas: [{ t: 0, f: 660, f2: 1320, d: .3, tipo: 'sine', v: .5 }, { t: .12, f: 880, f2: 1760, d: .35, tipo: 'triangle', v: .35 }, { t: .3, f: 1320, d: .5, tipo: 'sine', v: .3 }], ruidos: [{ t: .05, d: .5, f: 3000, f2: 8000, filtro: 'bandpass', v: .2, q: 2 }] },
            pin: { nomeItem: 'Joaninha', desc: 'Suas notas no mapa viram a joaninha do Giorno.', img: 'joaninha' },
            serv: { nomeItem: 'Servidor Áureo', desc: 'O ícone do servidor pisca em dourado e rosa.', cores: [OURO, ROSA], passos: true, dur: .8 },
            pagina: { nomeItem: 'O Tempo se Apaga', desc: 'Fique um tempão sem mexer e os ゴゴゴ começam a brotar do nada. Depois uma barra rosa varre a tela e o tempo é apagado. Mexeu o mouse, tudo volta num piscar.', preset: 'jojo_tempo', espera: 25 },
        }),
    ],
});

// ============================================================================================ BUCCIARATI
const PRATA = '#e8ecf4', AZ = '#5b8bd6';
const bruno = tema({
    id: 'jj_bruno', pre: 'jbr', nome: 'Bruno Bucciarati', cat: 'anime', cor: AZ, cores: [PRATA, AZ], icone: 'fa-link', premium: true,
    lema: 'Arrivederci.',
    desc: 'O zíper que corre pela borda da foto, a abertura de zíper com dentes dourados e o terno branco de bolinhas pretas.',
    pal: { m: AZ, a: PRATA, d: '#14203a', l: '#fff', o: '#14203a' },
    itens: [
        MP('Zíper', 'Um zíper dourado que corre pela borda da foto, abrindo e fechando.', { svg: zipper }, { r: 'lendario' }),
        EA('Abertura', 'Um zíper se abre na sua foto e um anel de dentes dourados gira em volta.', [
            { k: 'anel', cor: '#e8b94a', r: 62, esp: 1.6, dash: '3 5', giro: 8 },
        ], { r: 'lendario', id: 'jbr_abertura',
            sobre: [{ k: 'raw', html: '<b class="$C"><i class="fenda"></i><i class="dt"></i><i class="pu"></i></b>',
              css: `.ef-sobre-$ID .fenda{position:absolute;left:-15%;top:42%;width:130%;height:16%;background:linear-gradient(#050a1c,#0b1a46,#050a1c);transform:rotate(-32deg) scaleY(0);transform-origin:50% 50%;opacity:0;animation:k-$ID-f 9s ease-in-out ${fase(9, .45)} infinite}`
                + `.ef-sobre-$ID .dt{position:absolute;left:-15%;top:41.2%;width:130%;height:17.6%;background:repeating-linear-gradient(90deg,#e8b94a 0 3px,transparent 3px 6px) top/100% 3px no-repeat,repeating-linear-gradient(90deg,#e8b94a 0 3px,transparent 3px 6px) bottom/100% 3px no-repeat;transform:rotate(-32deg) scaleY(0);opacity:0;animation:k-$ID-f 9s ease-in-out ${fase(9, .45)} infinite}`
                + `.ef-sobre-$ID .pu{position:absolute;left:84%;top:2%;width:13%;aspect-ratio:1;border-radius:50%;background:radial-gradient(circle,#14203a 30%,#f3d27a 32%);box-shadow:0 0 0 2px #6b4a10;opacity:0;animation:k-$ID-p 9s ease-in-out ${fase(9, .45)} infinite}`
                + '@keyframes k-$ID-f{0%,14%{transform:rotate(-32deg) scaleY(0);opacity:0}20%{opacity:1}30%,70%{transform:rotate(-32deg) scaleY(1);opacity:1}82%,100%{transform:rotate(-32deg) scaleY(0);opacity:0}}'
                + '@keyframes k-$ID-p{0%,14%{opacity:0;transform:translate(-90%,90%)}20%{opacity:1;transform:translate(-90%,90%)}30%,70%{opacity:1;transform:translate(0,0)}82%,100%{opacity:0;transform:translate(-90%,90%)}}' }],
            css: '.ef-av-sobre.ef-sobre-$ID.kz{overflow:hidden}' }),
        EP('Zíper Aberto', 'Um zíper se abre no cartão entre brilhos de prata.', [
            IMG({ tema: T, img: 'ziper_aberto', onde: 'pf', n: 'bz', x: 72, y: 82, w: 56, ciclo: 11, ini: 12, fim: 74, de: { x: 14, y: 20, esc: .5, rot: 12 }, sai: { x: 14, y: 20, esc: .5, rot: 12 }, bob: 1.2 }),
            { k: 'pisca', icone: 'brilho', pals: [{ m: '#ffffff', a: PRATA, d: '#9db7e8', l: '#fff', o: '#14203a', w: 2 }], n: 12, tam: [8, 14] },
            { k: 'borda', cor: AZ, alfa: .45, blur: 38, esp: 4, dur: 3.4 },
        ], { r: 'lendario', id: 'jbr_ziper_aberto' }),
        ...apoio({
            tema: T,
            nome: { nomeItem: 'Capo', desc: 'Branco e azul-prata com contorno escuro, como o terno do Bruno.', grad: ['#ffffff', '#9db7e8', '#ffffff'], mov: 'desliza', dur: 4.5, contorno: '#14203a', cw: 1.1, fonte: 'classica', espaco: 1 },
            placa: { nomeItem: 'Terno de Bolinhas', desc: 'Branco-prata com as bolinhas pretas do terno e um zíper do lado.', base: ['#eef1f8', '#9db0d8'], pad: { tipo: 'bolinhas', c1: 'rgba(20,20,34,.85)', c2: 'transparent', tam: 8, r: .2 }, mov: 'x', dur: 12, borda: '#14203a', texto: '#14203a', img: { nome: 'ziper', lado: 'dir', tam: 92, y: 50 } },
            faixa: { nomeItem: 'A Abertura', desc: 'Uma noite azul com um zíper dourado cruzando a faixa.', fundo: ['#0a1030', '#1d2f6a'],
                fixo: `<g stroke='#e8b94a' stroke-width='4' stroke-dasharray='4 4' opacity='.9'><path d='M0 58L340 50'/></g><path d='M0 54L340 46' stroke='#14203a' stroke-width='8' opacity='.7'/><circle cx='250' cy='51' r='9' fill='#f3d27a' stroke='#6b4a10' stroke-width='2'/><circle cx='250' cy='51' r='4' fill='#14203a'/>`,
                perto: { svg: P.cena.estrelas({ cor: '#ffffff', n: 16, y: [4, 100], r: [.5, 1.3], seed: 'jbr1' }), anim: 'pisca', dur: 2.6 },
                 },
            fala: { nomeItem: 'Zip', desc: 'Quando você fala na call, o card pisca em azul e prata.', cores: [AZ, PRATA], passos: true, dur: .4 },
            radar: { nomeItem: 'Costura', desc: 'As ondas do radar viram anéis tracejados prateados, como uma costura de zíper.', cor: PRATA, estilo: 'tracejado', glow: AZ },
            chat: { nomeItem: 'Fechadura', desc: 'A barra de mensagem acende em azul ao digitar e solta brilhos prateados ao enviar.', cor: AZ, cor2: PRATA, particula: { icone: 'brilho', pal: { m: '#ffffff', a: PRATA, d: '#9db7e8', l: '#fff', o: '#14203a', w: 2 } } },
            som: { nomeItem: 'Ziiip', desc: 'O som de um zíper grande abrindo e um estalo seco, ao entrar na call.', arquivo: 'jojo_bruno.mp3', notas: [{ t: .55, f: 300, f2: 180, d: .1, tipo: 'square', v: .35 }], ruidos: Array.from({ length: 14 }, (_, k) => ({ t: k * .035, d: .03, f: 2200 + k * 220, filtro: 'highpass', v: .35, q: .8 })).concat([{ t: .52, d: .06, f: 900, filtro: 'bandpass', v: .4, q: 1.2 }]) },
            pin: { nomeItem: 'Zíper Aberto', desc: 'Suas notas no mapa viram um zíper se abrindo.', img: 'ziper_aberto' },
            serv: { nomeItem: 'Servidor Capo', desc: 'O ícone do servidor pisca em azul e prata.', cores: [AZ, PRATA], passos: true, dur: .9 },
        }),
    ],
});

// ============================================================================================ MISTA
const LAR = '#f0772a', AZM = '#2d63c8', AMA = '#f3d35a';
const mista = tema({
    id: 'jj_mista', pre: 'jmi', nome: 'Guido Mista', cat: 'anime', cor: LAR, cores: [AZM, LAR], icone: 'fa-gun', premium: true,
    lema: 'Nunca o número quatro.',
    desc: 'O tambor do revólver girando, balas douradas orbitando a foto, rajadas de tiros e o tigre laranja.',
    pal: { m: LAR, a: AMA, d: '#14203a', l: '#fff', o: '#14203a' },
    itens: [
        MP('Tambor', 'O tambor de um revólver girando aos pulos, um furo de cada vez.', { svg: tambor }, { r: 'lendario' }),
        EA('Balas', 'Balas douradas voam em volta da foto, soltando clarões de tiro.', [
            ORBITA({ tema: T, imgs: ['bala'], n: 4, raio: 35, w: 12, dur: 6, nome: 'sx' }),
            { k: 'faiscas', icone: 'brilho', pals: [{ m: AMA, a: '#fff', d: LAR, l: '#fff', o: '#14203a', w: 2 }], n: 8, tam: 8, raio: 38, dur: .9 },
        ], { r: 'lendario', id: 'jmi_balas' }),
        EP('Rajada', 'Balas cruzam o cartão deixando rastro e clarões de tiro estouram.', [
            { k: 'raw', html: [14, 34, 52, 70].map((y, k) => `<i class="bl" style="top:${y}%;--d:${k * 1.3}s"></i>`).join(''),
              css: `.ef-pf-$ID .bl{position:absolute;left:0;width:16cqw;height:1.6cqw;border-radius:1cqw;background:linear-gradient(90deg,transparent,rgba(243,211,90,.9) 60%,#fff);opacity:0;transform:translateX(-30cqw) rotate(-6deg);animation:k-$ID-bl 5.2s cubic-bezier(.3,.6,.4,1) calc(var(--d) + ${fase(5.2, .3)}) infinite}@keyframes k-$ID-bl{0%{opacity:0;transform:translateX(-30cqw) rotate(-6deg)}4%{opacity:1}22%{opacity:1;transform:translateX(120cqw) rotate(-6deg)}30%,100%{opacity:0;transform:translateX(130cqw) rotate(-6deg)}}` },
            { k: 'pisca', icone: 'brilho', pals: [{ m: AMA, a: '#fff', d: LAR, l: '#fff', o: '#14203a', w: 2 }], n: 8, tam: [10, 16] },
            { k: 'borda', cor: LAR, alfa: .45, blur: 36, esp: 4, dur: 1.6 },
        ], { r: 'lendario', id: 'jmi_rajada' }),
        ...apoio({
            tema: T,
            nome: { nomeItem: 'Pistoleiro', desc: 'Laranja de tigre e azul com contorno escuro.', grad: [LAR, AMA, AZM, LAR], mov: 'desliza', dur: 3.4, contorno: '#14203a', cw: 1.1, fonte: 'impacto', img: 'bala', imgW: .6, imgH: 1.2 },
            placa: { nomeItem: 'Blusa de Losangos', desc: 'Azul com losangos brancos, como a blusa do Mista, e uma bala no canto.', base: [AZM, '#1b3a8a'], pad: { tipo: 'losangos', c1: 'rgba(255,255,255,.35)', c2: 'transparent', tam: 11 }, mov: 'x', dur: 10, borda: LAR, img: { nome: 'bala', lado: 'dir', tam: 84, y: 50 } },
            faixa: { nomeItem: 'Calça de Tigre', desc: 'Listras de tigre laranja e preto.', fundo: [LAR, '#c8541a'],
                fixo: `<g fill='#14080a'>${Array.from({ length: 10 }, (_, k) => `<path d='M${k * 36 - 10} 0L${k * 36 + 8} 0L${k * 36 + 22} 112L${k * 36 + 6} 112Z' opacity='.85'/>`).join('')}</g>`,
                 },
            fala: { nomeItem: 'Tiroteio', desc: 'Quando você fala na call, o card pisca em azul e laranja, como um tiroteio.', cores: [AZM, LAR], passos: true, dur: .25 },
            radar: { nomeItem: 'Eco do Tiro', desc: 'As ondas do radar viram anéis duplos laranja.', cor: LAR, estilo: 'duplo', glow: AMA },
            chat: { nomeItem: 'Cartuchos', desc: 'A barra de mensagem acende em laranja ao digitar e solta clarões ao enviar.', cor: LAR, cor2: AMA, particula: { forma: 'estrela' } },
            som: { nomeItem: 'Bang Bang Bang', desc: 'Três tiros secos em sequência e um clique de recarga, ao entrar na call.', arquivo: 'jojo_mista.mp3', notas: [{ t: 0, f: 180, f2: 50, d: .12, tipo: 'sawtooth', v: .5 }, { t: .16, f: 180, f2: 50, d: .12, tipo: 'sawtooth', v: .5 }, { t: .32, f: 180, f2: 50, d: .12, tipo: 'sawtooth', v: .5 }], ruidos: [{ t: 0, d: .1, f: 4000, f2: 500, filtro: 'lowpass', v: .6 }, { t: .16, d: .1, f: 4000, f2: 500, filtro: 'lowpass', v: .6 }, { t: .32, d: .1, f: 4000, f2: 500, filtro: 'lowpass', v: .6 }, { t: .6, d: .04, f: 3000, filtro: 'highpass', v: .3 }] },
            pin: { nomeItem: 'Bala', desc: 'Suas notas no mapa viram uma bala dourada.', img: 'bala' },
            serv: { nomeItem: 'Servidor Pistoleiro', desc: 'O ícone do servidor pisca em azul e laranja.', cores: [AZM, LAR], passos: true, dur: .5 },
        }),
    ],
});

// ============================================================================================ NARANCIA
const NLAR = '#f08a2a', NVER = '#c8302a', NROX = '#5a3a8a';
const narancia = tema({
    id: 'jj_narancia', pre: 'jna', nome: 'Narancia Ghirga', cat: 'anime', cor: NLAR, cores: [NLAR, NROX], icone: 'fa-plane', premium: true,
    lema: 'Aerosmith, detecte o CO2.',
    desc: 'Narancia e o Aerosmith: um radar de gás carbônico girando, o avião que cruza a foto de tempos em tempos, e o laranja e roxo do colete.',
    pal: { m: NLAR, a: '#ffd04a', d: '#2a1a4a', l: '#fff', o: '#2a1a4a' },
    itens: [
        MP('Radar de CO2', 'Um mini radar verde no canto da foto, varrendo e soltando ondas.', { svg: radarPeca }, { r: 'lendario' }),
        EA('Aerosmith', 'O Aerosmith cruza a sua foto por uns instantes e some, e outra passagem vem depois de uma pausa.', [
            { k: 'anel', cor: '#4be07a', r: 62, esp: 1.6, dash: '2 6', giro: 9 },
        ], { r: 'lendario', id: 'jna_aerosmith',
            sobre: [IMG({ tema: T, img: 'stand_aerosmith', onde: 'sobre', n: 'ae', x: 50, y: 30, w: 92, ciclo: 6.5, ini: 6, fim: 42, de: { x: -75, y: 6, rot: -8 }, sai: { x: 75, y: -8, rot: 6 }, rot: -4, brilho: '#c8302a', bw: 3 })],
            css: '.ef-av-sobre.ef-sobre-$ID.kz{overflow:visible}' }),
        EP('Voo Rasante', 'O avião do Aerosmith cruza o cartão com um rastro, ondas de radar saem do chão e bolhas de CO2 sobem.', [
            IMG({ tema: T, img: 'stand_aerosmith', onde: 'pf', n: 'ae', x: 50, y: 30, w: 52, ciclo: 7, ini: 8, fim: 48, de: { x: -80, y: 8, rot: -10 }, sai: { x: 80, y: -10, rot: 8 }, rot: -5 }),
            { k: 'sobe', icones: ['bolha'], pals: [{ m: '#4be07a', a: '#c8ffd8', d: '#1a8a40', l: '#fff', o: '#0a3a1a' }], n: 12, tam: [10, 18], vel: [6, 11], alfa: .85 },
            { k: 'ondas', cor: '#4be07a', alfa: .35, dur: 6 },
            { k: 'borda', cor: NLAR, alfa: .4, blur: 36, esp: 4, dur: 3 },
        ], { r: 'lendario', id: 'jna_voo_rasante' }),
        ...apoio({
            tema: T,
            nome: { nomeItem: 'Piloto', desc: 'Laranja e roxo com contorno escuro, o colete do Narancia.', grad: [NLAR, '#ffd04a', NROX, NLAR], mov: 'desliza', dur: 3.8, contorno: '#2a1a4a', cw: 1.1, fonte: 'impacto', img: 'stand_aerosmith', imgW: 1.6, imgH: 1 },
            placa: { nomeItem: 'Colete', desc: 'Roxo e laranja com quadrados dourados e o Aerosmith voando do lado.', base: [NROX, '#2a1a4a'], pad: { tipo: 'xadrez', c1: 'rgba(240,138,42,.28)', c2: 'transparent', tam: 8 }, mov: 'x', dur: 10, borda: NLAR, img: { nome: 'stand_aerosmith', lado: 'dir', tam: 76, y: 50 } },
            faixa: { nomeItem: 'Céu de Radar', desc: 'Um céu laranja de fim de tarde com o Aerosmith cruzando.', fundo: ['#ffb04a', '#f0702a', '#5a3a8a'],
                longe: { svg: `<g opacity='.5'>${P.cena.nuvens({ cor: '#ffe2b0', n: 3, y: [10, 50], tam: [16, 26], seed: 'jna1' })}</g>`, anim: 'pan', dur: 36 },
                css: `.banner-anim-$ID::after{content:'';position:absolute;left:0;top:18%;height:56%;aspect-ratio:390/221;background:${R.css(T, 'stand_aerosmith')} center/contain no-repeat;pointer-events:none;animation:k-$ID-v 7s linear infinite}@keyframes k-$ID-v{from{transform:translateX(-120%)}to{transform:translateX(420%)}}` },
            fala: { nomeItem: 'Detectou', desc: 'Quando você fala na call, o card pisca em verde e laranja, como um radar.', cores: ['#4be07a', NLAR], passos: true, dur: .5 },
            radar: { nomeItem: 'Pings de CO2', desc: 'As ondas do radar viram anéis verdes de um detector de gás carbônico.', cor: '#4be07a', estilo: 'liso', glow: NLAR },
            chat: { nomeItem: 'Hélices', desc: 'A barra de mensagem acende em laranja ao digitar e solta bolhas de CO2 ao enviar.', cor: NLAR, cor2: '#4be07a', particula: { icone: 'bolha', pal: { m: '#4be07a', a: '#c8ffd8', d: '#1a8a40', l: '#fff', o: '#0a3a1a' } } },
            som: { nomeItem: 'Motor de Avião', desc: 'Um motorzinho de avião que passa zunindo, ao entrar na call.', arquivo: 'jojo_narancia.mp3', notas: [{ t: 0, f: 140, f2: 260, d: .5, tipo: 'sawtooth', v: .35 }, { t: .5, f: 260, f2: 110, d: .6, tipo: 'sawtooth', v: .3 }], ruidos: [{ t: 0, d: 1.1, f: 800, f2: 2400, filtro: 'bandpass', v: .3, q: .9 }] },
            pin: { nomeItem: 'Aerosmith', desc: 'Suas notas no mapa viram o avião do Aerosmith.', img: 'stand_aerosmith' },
            serv: { nomeItem: 'Servidor Aéreo', desc: 'O ícone do servidor pisca em laranja e roxo.', cores: [NLAR, NROX], passos: true, dur: .8 },
        }),
    ],
});

// ============================================================================================ FUGO
const FRAM = '#e03a5a', FROX = '#8e4ad8';
const fugo = tema({
    id: 'jj_fugo', pre: 'jfu', nome: 'Pannacotta Fugo', cat: 'anime', cor: FROX, cores: [FRAM, FROX], icone: 'fa-flask', premium: true,
    lema: 'Purple Haze.',
    desc: 'A cápsula do vírus, o gás roxo que sobe e a nuvem que se espalha em volta da foto.',
    pal: { m: FROX, a: '#d9a8ff', d: '#2a0a4a', l: '#fff', o: '#2a0a4a' },
    itens: [
        MP('Cápsula', 'A cápsula do vírus do Purple Haze presa à borda da foto, soltando gás roxo.', { svg: capsula }, { r: 'lendario' }),
        EA('Gás Roxo', 'O gás roxo se espalha em volta da sua foto e as bordas pulsam em roxo.', [
            { k: 'raw', html: '<b class="$C"><i class="gs g1"></i><i class="gs g2"></i><i class="gs g3"></i><i class="gs g4"></i></b>',
              css: '.ef-av-$ID .gs{position:absolute;width:38%;aspect-ratio:1;border-radius:50%;background:radial-gradient(circle,rgba(170,90,235,.75),rgba(110,40,170,.0) 70%);opacity:0;animation:k-$ID-gs 6s ease-in-out infinite}.ef-av-$ID .g1{left:6%;top:50%}.ef-av-$ID .g2{left:56%;top:44%;animation-delay:-1.5s}.ef-av-$ID .g3{left:28%;top:2%;animation-delay:-3s}.ef-av-$ID .g4{left:50%;top:60%;animation-delay:-4.5s}@keyframes k-$ID-gs{0%{opacity:0;transform:scale(.5) translateY(6%)}30%{opacity:1}100%{opacity:0;transform:scale(1.7) translateY(-18%)}}' },
        ], { r: 'lendario', id: 'jfu_gas_roxo', sobre: [{ k: 'vinheta', cor: '#8e4ad8', alfa: .5, pulso: 2.4 }] }),
        EP('Nuvem de Vírus', 'Gás roxo sobe do chão do cartão em ondas e cápsulas estouram.', [
            { k: 'neblina', cor: '#8e4ad8', alfa: .5, n: 5, vel: 14 },
            { k: 'sobe', icones: ['bolha'], pals: [{ m: '#b06af0', a: '#e6c8ff', d: '#5a2a8a', l: '#fff', o: '#2a0a4a' }], n: 10, tam: [10, 18], vel: [6, 11], alfa: .85 },
            { k: 'borda', cor: FROX, alfa: .5, blur: 40, esp: 5, dur: 2.2 },
        ], { r: 'lendario', id: 'jfu_nuvem_de_virus' }),
        ...apoio({
            tema: T,
            nome: { nomeItem: 'Contaminado', desc: 'Framboesa e roxo-vírus com contorno escuro.', grad: [FRAM, FROX, '#d9a8ff', FRAM], mov: 'desliza', dur: 4, contorno: '#2a0a4a', cw: 1.1, fonte: 'impacto', img: 'capsula_obj', imgW: 1.3, imgH: .7 },
            placa: { nomeItem: 'Terno Furado', desc: 'Framboesa com os buracos do terno do Fugo e uma cápsula do lado.', base: [FRAM, '#8a1a3a'], pad: { tipo: 'bolinhas', c1: 'rgba(30,6,20,.5)', c2: 'transparent', tam: 9, r: .3 }, mov: 'x', dur: 11, borda: FROX, img: { nome: 'capsula_obj', lado: 'dir', tam: 56, y: 50 } },
            faixa: { nomeItem: 'Laboratório', desc: 'Névoa roxa num fundo escuro de laboratório.', fundo: ['#12041e', '#3a1060', '#5a2a8a'],
                longe: { svg: `<g opacity='.5'>${P.cena.nuvens({ cor: '#b06af0', n: 4, y: [20, 90], tam: [18, 30], seed: 'jfu1' })}</g>`, anim: 'pan', dur: 30 },
                 },
            fala: { nomeItem: 'Surto', desc: 'Quando você fala na call, o card pisca em framboesa e roxo, num surto.', cores: [FRAM, FROX], passos: true, dur: .35 },
            radar: { nomeItem: 'Gás', desc: 'As ondas do radar viram anéis de gás roxo.', cor: FROX, estilo: 'duplo', glow: FRAM },
            chat: { nomeItem: 'Esporos', desc: 'A barra de mensagem acende em roxo ao digitar e solta esporos ao enviar.', cor: FROX, cor2: FRAM, particula: { icone: 'bolha', pal: { m: '#b06af0', a: '#e6c8ff', d: '#5a2a8a', l: '#fff', o: '#2a0a4a' } } },
            som: { nomeItem: 'Vírus Liberado', desc: 'Uma cápsula estalando e um chiado de gás saindo, ao entrar na call.', arquivo: 'jojo_fugo.mp3', notas: [{ t: 0, f: 900, f2: 300, d: .08, tipo: 'square', v: .35 }, { t: .1, f: 90, f2: 60, d: .8, tipo: 'sawtooth', v: .3 }], ruidos: [{ t: .08, d: 1, f: 4000, f2: 900, filtro: 'bandpass', v: .45, q: .7 }] },
            pin: { nomeItem: 'Cápsula', desc: 'Suas notas no mapa viram a cápsula do vírus.', img: 'capsula_obj' },
            serv: { nomeItem: 'Servidor Infectado', desc: 'O ícone do servidor pisca em framboesa e roxo.', cores: [FRAM, FROX], passos: true, dur: .7 },
        }),
    ],
});

// ============================================================================================ TRISH
const TROS = '#ff8ac8', TMAG = '#e03a9a', TLAV = '#b79af0';
const trish = tema({
    id: 'jj_trish', pre: 'jtr', nome: 'Trish Una', cat: 'anime', cor: TROS, cores: [TROS, TLAV], icone: 'fa-heart', premium: true,
    lema: 'Spice Girl, amoleça.',
    desc: 'Gotas cor-de-rosa amolecendo a borda da foto, corações de borracha e tudo que vira rosa mole.',
    pal: { m: TROS, a: '#ffd0ea', d: '#7a1a5a', l: '#fff', o: '#7a1a5a' },
    itens: [
        MP('Amolecendo', 'Gotas cor-de-rosa se derretendo na borda de baixo da foto, esticando e encolhendo.', { svg: gotasTrish }, { r: 'lendario' }),
        EA('Rosa Mole', 'O rosa vai escorrendo pela sua foto, amolecendo tudo, enquanto uma aura rosa pulsa.', [
            { k: 'aura', cor: '#ff8ac8', dur: 3 },
        ], { r: 'lendario', id: 'jtr_rosa_mole', sobre: [{ k: 'pingos', cor: '#ff8ac8', n: 6, dur: 6 }] }),
        EP('Mundo de Borracha', 'Corações de borracha sobem pelo cartão e gotas rosa escorrem.', [
            { k: 'sobe', icones: ['coracao'], pals: [{ m: '#ff8ac8', a: '#ffd0ea', d: '#7a1a5a', l: '#fff', o: '#7a1a5a' }], n: 12, tam: [12, 22], vel: [6, 11], alfa: .9 },
            { k: 'cai', icones: ['gota'], pals: [{ m: '#ff8ac8', a: '#ffd0ea', d: '#7a1a5a', l: '#fff', o: '#7a1a5a' }], n: 8, tam: [10, 18], vel: [6, 11] },
            { k: 'borda', cor: TROS, alfa: .5, blur: 38, esp: 5, dur: 2.6 },
        ], { r: 'lendario', id: 'jtr_mundo_de_borracha' }),
        ...apoio({
            tema: T,
            nome: { nomeItem: 'Filha do Chefe', desc: 'Rosa e lavanda com contorno escuro.', grad: [TROS, '#ffd0ea', TLAV, TROS], mov: 'desliza', dur: 4, contorno: '#7a1a5a', cw: 1.1, fonte: 'redonda', espaco: .6, img: 'coracao_rosa', imgW: 1.1, imgH: 1 },
            placa: { nomeItem: 'Corações Moles', desc: 'Rosa-choque com coraçõezinhos e um coração maior do lado.', base: [TMAG, '#a02a78'], pad: { tipo: 'icones', icones: ['coracao'], pals: [{ m: '#ffd0ea', a: '#fff', d: '#7a1a5a', l: '#fff', o: '#7a1a5a', w: 0 }], tam: 22, ti: 14, c2: 'transparent' }, mov: 'x', dur: 14, borda: '#ffd0ea', img: { nome: 'coracao_rosa', lado: 'dir', tam: 78, y: 50 } },
            faixa: { nomeItem: 'Quarto Rosa', desc: 'Um céu rosa e lavanda com coraçõezinhos piscando.', fundo: ['#ffc2e2', '#e89ad8', '#b79af0'],
                perto: { svg: P.cena.icones({ nomes: ['coracao'], pals: [{ m: '#fff', a: '#ffd0ea', d: '#e03a9a', l: '#fff', o: '#7a1a5a', w: 2 }], n: 7, tam: [10, 16], seed: 'jtr1', y: [6, 100] }), anim: 'pisca', dur: 2.4 },
                 },
            fala: { nomeItem: 'Elástico', desc: 'Quando você fala na call, o card pisca em rosa e lavanda.', cores: [TROS, TLAV], passos: true, dur: .5 },
            radar: { nomeItem: 'Ondas Moles', desc: 'As ondas do radar viram anéis rosa que parecem de borracha.', cor: TROS, estilo: 'liso', glow: TLAV },
            chat: { nomeItem: 'Coraçõezinhos', desc: 'A barra de mensagem acende em rosa ao digitar e solta coraçõezinhos ao enviar.', cor: TROS, cor2: TLAV, particula: { icone: 'coracao', pal: { m: '#ff8ac8', a: '#ffd0ea', d: '#7a1a5a', l: '#fff', o: '#7a1a5a' } } },
            som: { nomeItem: 'Boing', desc: 'Um boing de borracha esticando e voltando, ao entrar na call.', arquivo: 'jojo_trish.mp3', notas: [{ t: 0, f: 200, f2: 700, d: .18, tipo: 'sine', v: .5 }, { t: .18, f: 700, f2: 120, d: .35, tipo: 'sine', v: .5 }, { t: .55, f: 300, f2: 520, d: .2, tipo: 'triangle', v: .3 }], ruidos: [] },
            pin: { nomeItem: 'Coração Mole', desc: 'Suas notas no mapa viram um coração cor-de-rosa.', img: 'coracao_rosa' },
            serv: { nomeItem: 'Servidor de Borracha', desc: 'O ícone do servidor pisca em rosa e lavanda.', cores: [TROS, TLAV], passos: true, dur: .8 },
        }),
    ],
});

module.exports = [giorno, bruno, mista, narancia, fugo, trish];
