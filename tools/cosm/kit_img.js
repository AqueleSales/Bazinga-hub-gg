'use strict';
/* Camadas de IMAGEM animada para efeito de avatar (atrás ou por cima da foto) e de perfil (Rodada 40).
   Cada função devolve { k:'raw', html, css } pronto pra entrar na lista de camadas de EA/EP (o `$ID` e o `$C` são trocados pelo kit).
   Uma imagem tem um CICLO: fica escondida, ENTRA (de um deslocamento), fica à mostra e SAI, e espera (o "cooldown"). Só transform/opacity. */
const R = require('./raster');
const B = require('./base');
const { f1 } = B;

const RAIZ = { av: '.ef-av-$ID', sobre: '.ef-sobre-$ID', pf: '.ef-pf-$ID' };

/** o = { tema, img (nome do PNG), onde:'av'|'sobre'|'pf', x, y, w (largura em % da caixa), rot, flip,
 *        ciclo (s), ini, fim (% do ciclo em que está à mostra), de:{x,y,rot,esc} (de onde entra, em % da caixa / graus), sai:{...} (pra onde sai; padrão = de),
 *        bob (% de flutuação), vibra (px), brilho (cor do drop-shadow), atraso (s), n (classe extra), sobreposicao }
 *  `fase` (0..1): quanto do ciclo já passou na PRÉVIA (a prévia nasce com a imagem à mostra). */
function IMG(o) {
    const raiz = RAIZ[o.onde || 'av'], cls = `$C-${o.n || 'i'}`, r = R.proporcao(o.tema, o.img);
    const x = o.x === undefined ? 50 : o.x, y = o.y === undefined ? 50 : o.y, rot = o.rot || 0, esc = o.esc || 1, flip = o.flip ? -1 : 1;
    const base = `translate(-50%,-50%) rotate(${rot}deg) scale(${f1(flip * esc)},${esc})`;
    const de = o.de || { y: 12 }, sai = o.sai || de;
    const t = (d, k = 1) => `translate(calc(-50% + ${f1((d.x || 0) * k)}%),calc(-50% + ${f1((d.y || 0) * k)}%)) rotate(${f1(rot + (d.rot || 0) * k)}deg) scale(${f1(flip * (d.esc === undefined ? 1 : d.esc) * esc)},${f1((d.esc === undefined ? 1 : d.esc) * esc)})`;
    const ini = o.ini === undefined ? 10 : o.ini, fim = o.fim === undefined ? 60 : o.fim, ciclo = o.ciclo || 10, ent = Math.min(6, (fim - ini) / 4), sa = ent;
    const nome = `k-$ID-${cls.replace('$C-', '')}`;
    let meio = '';
    if (o.bob) { const m1 = f1(ini + ent + (fim - ini - ent - sa) * .35), m2 = f1(ini + ent + (fim - ini - ent - sa) * .7); meio = `${m1}%{transform:translate(-50%,calc(-50% + ${o.bob}%)) rotate(${rot}deg) scale(${f1(flip * esc)},${esc})}${m2}%{transform:translate(-50%,calc(-50% - ${o.bob}%)) rotate(${rot}deg) scale(${f1(flip * esc)},${esc})}`; }
    const kf = `@keyframes ${nome}{0%,${ini}%{opacity:0;transform:${t(de)}}${f1(ini + ent)}%{opacity:1;transform:${base}}${meio}${f1(fim - sa)}%{opacity:1;transform:${base}}${fim}%{opacity:0;transform:${t(sai)}}100%{opacity:0;transform:${t(sai)}}}`;
    const brilho = o.brilho ? `filter:drop-shadow(0 0 ${o.bw || 5}px ${o.brilho});` : '';
    const vib = o.vibra ? `.${cls}::after{content:none}` : '';
    const css = `${raiz} .${cls}{position:absolute;left:${x}%;top:${y}%;width:${o.w}%;aspect-ratio:${f1(r * 100) / 100};background:url('${R.url(o.tema, o.img)}') center/contain no-repeat;opacity:0;transform:${t(de)};${brilho}animation:${nome} ${ciclo}s cubic-bezier(.2,.8,.3,1) calc(${o.atraso || 0}s + var(--ef-prev,0) * ${f1((ini + fim) / 200)} * -${ciclo}s) infinite}${kf}${vib}`;
    return { k: 'raw', html: `<i class="${cls}"></i>`, css };
}

/** vários itens pequenos que ORBITAM em volta da foto (caixa do efeito de avatar, 160%): peças girando. o: { tema, imgs:[nomes], n, raio (% da caixa), w (largura de cada um, %), dur (s), rev } */
function ORBITA(o) {
    const n = o.n || 6, raio = o.raio || 34, itens = o.imgs, cls = `$C-${o.nome || 'o'}`, k0 = (o.nome || 'o');
    let h = '', cssImg = '';
    itens.forEach((nome, j) => { cssImg += `.ef-av-$ID .${cls}-i${j}{background-image:url('${R.url(o.tema, nome)}');aspect-ratio:${f1(R.proporcao(o.tema, nome) * 100) / 100}}`; });
    for (let k = 0; k < n; k++) h += `<i class="${cls} ${cls}-i${k % itens.length}" style="--a:${f1(k / n * 360)}deg"></i>`;
    const css = cssImg + `.ef-av-$ID .${cls}{position:absolute;left:50%;top:50%;width:${o.w || 12}%;background-position:center;background-size:contain;background-repeat:no-repeat;--r:${raio}cqw;transform:rotate(var(--a)) translateY(calc(var(--r) * -1)) rotate(calc(var(--a) * -1));animation:k-$ID-${k0} ${o.dur || 12}s linear ${o.rev ? 'reverse ' : ''}infinite;margin:calc(${o.w || 12}% / -2) 0 0 calc(${o.w || 12}% / -2)}`
        + `@keyframes k-$ID-${k0}{from{transform:rotate(var(--a)) translateY(calc(var(--r) * -1)) rotate(calc(var(--a) * -1))}to{transform:rotate(calc(var(--a) + 360deg)) translateY(calc(var(--r) * -1)) rotate(calc((var(--a) + 360deg) * -1))}}`;
    return { k: 'raw', html: `<b class="${cls}-w">${h}</b>`, css };
}

module.exports = { IMG, ORBITA };
