'use strict';
/* Efeitos do kit: EA (efeito de avatar), EP (efeito de perfil) e os extras (fala, radar, chat, pin, servidor, som).
   Um efeito é uma lista de CAMADAS; cada camada gera um pedaço de HTML e as suas regras de CSS.
   Só transform/opacity se mexem (vão pra GPU). O cartão e a prévia têm tamanhos diferentes, então as distâncias usam unidades de container (cqh/cqw): .ef-pf.kz é `container-type:size`. */
const B = require('./base');
const { f1, f2, rng, uri, claro, escuro, alfa } = B;
const { icone, iconeSvg } = require('./icones');
const P = require('./padroes');
const { palDe, nomeVar, dur } = require('./kit');

const imgIcone = (nome, pal, extra = '') => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'${extra}>${icone(nome, pal)}</svg>`;
const pick = (a, k) => (Array.isArray(a) ? a[k % a.length] : a);

/** registra as imagens de uma lista de ícones e devolve os nomes das variáveis */
function varsIcones(ctx, base, nomes, pals) {
    return nomes.map((nm, k) => {
        const v = nomeVar(ctx.id, `${base}${k}`);
        ctx.vars[v] = uri(imgIcone(nm, { ...palDe(ctx, {}), ...(pick(pals || [{}], k) || {}) }));
        return v;
    });
}

// =====================================================================================
// EFEITO DE AVATAR (a caixa .ef-av tem 160% da foto; a foto é o círculo de raio 62,5 num quadro de 200)
// =====================================================================================
const EA_CAMADAS = {
    /** html e css escritos à mão (`$ID` vira o id do item): a saída de emergência pra arte única */
    raw(ctx, o, c) { return { html: (o.html || '').replace(/\$ID/g, ctx.id).replace(/\$C/g, c), css: (o.css || '').replace(/\$ID/g, ctx.id).replace(/\$C/g, c) }; },
    /** anel de ícones que gira em volta da foto */
    orbita(ctx, o, c) {
        const p = palDe(ctx, o), tam = o.tam || 24;
        const svg = P.anelDeIcones({ ...o, pals: o.pals || [p], raio: o.raio || 62.5 + tam / 2 + 3, tam });
        const v = nomeVar(ctx.id, c); ctx.vars[v] = uri(svg);
        return { html: `<b class="${c}"></b>`, css: `.ef-av-${ctx.id} .${c}{background:var(${v}) center/100% 100% no-repeat;animation:kGira ${dur(o.giro || 30)} linear ${o.rev ? 'reverse ' : ''}infinite;${o.pulso ? `animation:kGira ${dur(o.giro || 30)} linear infinite,kPulsa ${dur(o.pulso)} ease-in-out infinite;` : ''}}` };
    },
    /** anel tracejado/liso girando */
    anel(ctx, o, c) {
        const r = o.r || 70, col = o.cor || '#fff';
        const svg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><circle cx='100' cy='100' r='${r}' fill='none' stroke='${col}' stroke-width='${o.esp || 3}'${o.dash ? ` stroke-dasharray='${o.dash}'` : ''} stroke-linecap='round'${o.glow ? ` filter='url(#f)'` : ''}/>${o.glow ? `<defs><filter id='f' x='-20%' y='-20%' width='140%' height='140%'><feGaussianBlur stdDeviation='2'/></filter></defs>` : ''}</svg>`;
        const v = nomeVar(ctx.id, c); ctx.vars[v] = uri(svg);
        return { html: `<b class="${c}"></b>`, css: `.ef-av-${ctx.id} .${c}{background:var(${v}) center/100% 100% no-repeat;animation:kGira ${dur(o.giro || 14)} linear ${o.rev ? 'reverse ' : ''}infinite;}` };
    },
    /** halo que pulsa */
    halo(ctx, o, c) {
        const c1 = o.cor || '#fff', c2 = o.cor2 || c1;
        return { html: `<b class="${c}"></b>`, css: `.ef-av-${ctx.id} .${c}{background:radial-gradient(circle closest-side,transparent 58%,${alfa(c1, .75)} 66%,${alfa(c2, .35)} 76%,transparent 88%);animation:k-${ctx.id}-${c} ${dur(o.dur || 2.6)} ease-in-out infinite alternate;}@keyframes k-${ctx.id}-${c}{from{opacity:.55;transform:scale(.94)}to{opacity:1;transform:scale(1.05)}}` };
    },
    /** brilhinhos que piscam em volta */
    faiscas(ctx, o, c) {
        const R = rng(ctx.id + c), n = o.n || 8, nomes = o.icones || [o.icone || 'brilho'], vs = varsIcones(ctx, c, nomes, o.pals);
        let h = '';
        for (let k = 0; k < n; k++) {
            const a = (k / n) * 2 * Math.PI + R() * .5, r = (o.raio || 38) + R() * 8;
            h += `<i style="left:${f1(50 + r * Math.cos(a))}%;top:${f1(50 + r * Math.sin(a))}%;--s:${f1((o.tam || 8) * (.7 + R() * .6))}%;--d:-${f1(R() * 3)}s;--img:var(${vs[k % vs.length]})"></i>`;
        }
        return { html: `<b class="${c}">${h}</b>`, css: `.ef-av-${ctx.id} .${c} i{position:absolute;width:var(--s);aspect-ratio:1;margin:calc(var(--s)/-2) 0 0 calc(var(--s)/-2);background:var(--img) center/contain no-repeat;opacity:0;animation:kPisca ${dur(o.dur || 2.4)} ease-in-out var(--d) infinite;}` };
    },
    /** ícones que sobem dos lados e somem */
    sobe(ctx, o, c) {
        const R = rng(ctx.id + c), n = o.n || 8, vs = varsIcones(ctx, c, o.icones || [o.icone], o.pals);
        let h = '';
        for (let k = 0; k < n; k++) { const side = k % 2 ? 1 : -1; h += `<i style="left:${f1(50 + side * (30 + R() * 18))}%;--s:${f1((o.tam || 9) * (.7 + R() * .6))}%;--t:${f1(2.6 + R() * 2)}s;--d:-${f1(R() * 5)}s;--b:${f1((R() - .5) * 14)}%;--img:var(${vs[k % vs.length]})"></i>`; }
        return { html: `<b class="${c}">${h}</b>`, css: `.ef-av-${ctx.id} .${c} i{position:absolute;bottom:22%;width:var(--s);aspect-ratio:1;margin-left:calc(var(--s)/-2);background:var(--img) center/contain no-repeat;opacity:0;animation:k-${ctx.id}-${c} var(--t) ease-out var(--d) infinite;}@keyframes k-${ctx.id}-${c}{0%{transform:translate3d(0,0,0) scale(.6);opacity:0}15%{opacity:1}100%{transform:translate3d(var(--b),-${o.alt || 180}%,0) scale(1);opacity:0}}` };
    },
    /** acessório no topo da cabeça (coroa, auréola, chapéu, laço...) */
    topo(ctx, o, c) {
        const v = nomeVar(ctx.id, c); ctx.vars[v] = uri(imgIcone(o.icone, palDe(ctx, o)));
        const tam = o.tam || 30, x = o.x === undefined ? 50 : o.x, y = o.y === undefined ? 12 : o.y, rot = o.rot || 0;
        return { html: `<b class="${c}"></b>`, css: `.ef-av-${ctx.id} .${c}{inset:auto;left:${x}%;top:${y}%;width:${tam}%;aspect-ratio:1;margin:calc(${tam}%/-2) 0 0 calc(${tam}%/-2);background:var(${v}) center/contain no-repeat;transform:rotate(${rot}deg);animation:k-${ctx.id}-${c} ${dur(o.dur || 3)} ease-in-out infinite alternate;}@keyframes k-${ctx.id}-${c}{from{transform:translate3d(0,0,0) rotate(${rot - (o.bal || 3)}deg)}to{transform:translate3d(0,${o.bob || -2.5}%,0) rotate(${rot + (o.bal || 3)}deg)}}` };
    },
    /** orelhas (gato, coelho, urso, lobo, raposa, cavalo, diabo): ficam atrás da foto e saem pelo alto */
    orelhas(ctx, o, c) {
        const tipo = o.tipo || 'gato', cor = o.cor || '#ffb86b', ci = o.cor2 || claro(cor, .45), ct = o.contorno || escuro(cor, .55);
        const ang = o.ang || 30, r0 = 45, esc = o.esc || .82;
        let orelha = (lado) => {
            const a0 = (lado * ang) * Math.PI / 180, cx = 80 + r0 * Math.sin(a0) * 1.0, cy = 80 - r0 * Math.cos(a0);
            const rot = lado * (o.incl === undefined ? 0 : o.incl);
            let forma, interno;
            if (tipo === 'coelho') { forma = `<ellipse cx='0' cy='-30' rx='11' ry='34'/>`; interno = `<ellipse cx='0' cy='-30' rx='5.5' ry='25' fill='${ci}'/>`; }
            else if (tipo === 'urso') { forma = `<circle cx='0' cy='-8' r='15'/>`; interno = `<circle cx='0' cy='-8' r='8' fill='${ci}'/>`; }
            else if (tipo === 'cavalo') { forma = `<path d='M-11 6C-13 -8 -8 -22 2 -34 12 -22 14 -8 11 6Z'/>`; interno = `<path d='M-5 2C-6 -8 -3 -18 2 -26 7 -18 8 -8 5 2Z' fill='${ci}'/>`; }
            else if (tipo === 'diabo') { forma = `<path d='M-10 6C-14 -14 -8 -34 6 -44 10 -26 14 -12 10 6Z'/>`; interno = ''; }
            else { forma = `<path d='M-17 6L-14 -34 14 -6Z'/>`; interno = `<path d='M-11 0L-10 -23 7 -6Z' fill='${ci}'/>`; }   // gato / raposa
            if (tipo === 'lobo' || tipo === 'raposa') { forma = `<path d='M-15 6L-10 -38 15 -4Z'/>`; interno = `<path d='M-9 0L-7 -26 8 -5Z' fill='${ci}'/>`; }
            return `<g transform='translate(${f1(cx)} ${f1(cy)}) rotate(${f1(lado * ang * .55 + rot)}) scale(${esc})'><g class='o${lado > 0 ? 2 : 1}'><g fill='${cor}' stroke='${ct}' stroke-width='3.2' stroke-linejoin='round'>${forma}</g>${interno}</g></g>`;
        };
        const svg = `<svg viewBox='0 0 160 160' overflow='visible'>${orelha(-1)}${orelha(1)}</svg>`;
        return { html: `<b class="${c}">${svg}</b>`, css: `.ef-av-${ctx.id} .${c} svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}.ef-av-${ctx.id} .${c} .o1{animation:k-${ctx.id}-o1 ${dur(o.dur || 3.4)} ease-in-out infinite}.ef-av-${ctx.id} .${c} .o2{animation:k-${ctx.id}-o2 ${dur(o.dur || 3.4)} ease-in-out .5s infinite}` +
            `@keyframes k-${ctx.id}-o1{0%,70%,100%{rotate:0deg}78%{rotate:${-(o.mexe || 9)}deg}86%{rotate:${o.mexe || 9}deg}92%{rotate:-3deg}}@keyframes k-${ctx.id}-o2{0%,70%,100%{rotate:0deg}78%{rotate:${o.mexe || 9}deg}86%{rotate:${-(o.mexe || 9)}deg}92%{rotate:3deg}}` };
    },
    /** asas atrás da foto, batendo */
    asas(ctx, o, c) {
        const cor = o.cor || '#fff', ct = o.contorno || escuro(cor, .45), tipo = o.tipo || 'anjo';
        let asa;
        if (tipo === 'morcego') asa = `<path d='M0 0C-14 -22 -36 -30 -58 -22 -50 -14 -50 -6 -52 4 -44 0 -38 2 -34 10 -28 4 -20 6 -16 14 -10 8 -4 8 0 14Z'/>`;
        else if (tipo === 'borboleta') asa = `<path d='M0 0C-10 -34 -40 -44 -58 -26 -66 -12 -48 0 -30 2 -50 8 -50 30 -34 34 -18 36 -6 20 0 0Z'/>`;
        else if (tipo === 'fada') asa = `<path d='M0 0C-4 -30 -30 -48 -52 -36 -58 -20 -34 -4 0 0ZM0 2C-26 6 -50 22 -40 38 -22 40 -6 24 0 2Z'/>`;
        else asa = `<path d='M0 4C-10 -22 -34 -40 -62 -34 -52 -26 -50 -22 -54 -14 -44 -18 -40 -14 -42 -6 -34 -10 -30 -6 -30 2 -22 -2 -14 2 -10 12 -6 8 -2 8 0 4Z'/>`;
        const lado = (s) => `<g transform='translate(80 86) scale(${s} 1)'><g class='w${s > 0 ? 2 : 1}'><g fill='${cor}' stroke='${ct}' stroke-width='2.6' stroke-linejoin='round' ${o.alfa ? `opacity='${o.alfa}'` : ''}>${asa}</g></g></g>`;
        const svg = `<svg viewBox='0 0 160 160' overflow='visible'><g transform='translate(0 0)'>${lado(1)}${lado(-1)}</g></svg>`;
        return { html: `<b class="${c}">${svg}</b>`, css: `.ef-av-${ctx.id} .${c} svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}.ef-av-${ctx.id} .${c} g.w1,.ef-av-${ctx.id} .${c} g.w2{animation:k-${ctx.id}-w ${dur(o.dur || 1.6)} ease-in-out infinite alternate}@keyframes k-${ctx.id}-w{from{rotate:${-(o.bate || 6)}deg}to{rotate:${o.bate || 6}deg}}.ef-av-${ctx.id} .${c} g.w1{animation-direction:alternate-reverse}` };
    },
    /** nuvem de brilho (glow) que respira atrás da foto */
    aura(ctx, o, c) {
        const c1 = o.cor || '#fff';
        return { html: `<b class="${c}"></b>`, css: `.ef-av-${ctx.id} .${c}{background:radial-gradient(circle closest-side,${alfa(c1, .0)} 52%,${alfa(c1, .55)} 64%,transparent 82%);filter:blur(${o.blur || 2}px);animation:k-${ctx.id}-${c} ${dur(o.dur || 3)} ease-in-out infinite alternate}@keyframes k-${ctx.id}-${c}{from{opacity:.6;transform:scale(.96)}to{opacity:1;transform:scale(1.06)}}` };
    },
};

// ---- peças POR CIMA da foto (.ef-av-sobre: o círculo da foto, quadro 100x100) ----
const EA_SOBRE = {
    raw(ctx, o, c) { return { html: (o.html || '').replace(/\$ID/g, ctx.id).replace(/\$C/g, c), css: (o.css || '').replace(/\$ID/g, ctx.id).replace(/\$C/g, c) }; },
    /** pingos escorrendo da borda de cima (sangue, tinta, gosma, mel) */
    pingos(ctx, o, c) {
        const R = rng(ctx.id + c), n = o.n || 6, cor = o.cor || '#b3121f';
        let d = '', gs = '';
        for (let k = 0; k < n; k++) { const x = 10 + (k + R() * .6) * 80 / n, w = 5 + R() * 4, h = 14 + R() * 26; gs += `<g class='g' style='--d:-${f1(R() * 6)}s;--h:${f1(h)}'><path d='M${f1(x - w)} -2L${f1(x - w)} ${f1(10)}C${f1(x - w)} ${f1(h * .8)} ${f1(x - w / 2)} ${f1(h)} ${f1(x)} ${f1(h + w)}C${f1(x + w / 2)} ${f1(h)} ${f1(x + w)} ${f1(h * .8)} ${f1(x + w)} 10L${f1(x + w)} -2Z'/></g>`; }
        const svg = `<svg viewBox='0 0 100 100'><g fill='${cor}'><path d='M0 0H100V8C90 14 80 6 70 12 60 18 50 8 40 12 30 16 20 8 10 12 6 14 2 12 0 8Z'/>${gs}</g></svg>`;
        return { html: `<b class="${c}">${svg}</b>`, css: `.ef-sobre-${ctx.id} .${c} .g{animation:k-${ctx.id}-${c} ${dur(o.dur || 7)} ease-in-out var(--d) infinite;transform-box:fill-box;transform-origin:50% 0}@keyframes k-${ctx.id}-${c}{0%,100%{transform:scaleY(.35)}55%{transform:scaleY(1.15)}}` };
    },
    /** neve no topo da cabeça */
    neve(ctx, o, c) {
        const cor = o.cor || '#fff';
        const svg = `<svg viewBox='0 0 100 100'><path d='M0 0H100V10C92 20 86 10 78 18 70 26 64 12 56 18 48 24 42 12 34 18 26 24 20 14 12 20 6 24 2 16 0 12Z' fill='${cor}' stroke='${escuro(cor, .18)}' stroke-width='1.2' stroke-linejoin='round'/></svg>`;
        return { html: `<b class="${c}">${svg}</b>`, css: '' };
    },
    /** teia no canto superior direito */
    teia(ctx, o, c) {
        const cor = o.cor || '#e8e8f0';
        const svg = `<svg viewBox='0 0 100 100'>${icone('teia', { m: cor })}</svg>`;
        return { html: `<b class="${c}">${svg}</b>`, css: `.ef-sobre-${ctx.id} .${c}{position:absolute;right:-12%;top:-12%;width:70%;height:70%;opacity:.85;transform:rotate(${o.rot || 18}deg)}` };
    },
    /** rachadura que cruza a foto */
    rachadura(ctx, o, c) {
        const cor = o.cor || '#fff';
        const svg = `<svg viewBox='0 0 100 100'><g fill='none' stroke='${cor}' stroke-width='1.8' stroke-linejoin='round' stroke-linecap='round'><path d='M58 0L52 16 62 26 50 44 60 58 48 74 54 100' stroke='${o.sombra || '#000'}' stroke-width='4' opacity='.45'/><path d='M58 0L52 16 62 26 50 44 60 58 48 74 54 100'/><path d='M62 26L80 30 92 22M50 44L30 50 20 66M60 58L78 66'/></g></svg>`;
        return { html: `<b class="${c}">${svg}</b>`, css: `.ef-sobre-${ctx.id} .${c}{animation:k-${ctx.id}-${c} ${dur(o.dur || 8)} ease-in-out infinite}@keyframes k-${ctx.id}-${c}{0%,35%{opacity:0}42%,70%{opacity:1}80%,100%{opacity:0}}` };
    },
    /** brilho passando na foto */
    brilho(ctx, o, c) {
        const cor = o.cor || '#fff';
        return { html: `<b class="${c}"></b>`, css: `.ef-sobre-${ctx.id} .${c}{position:absolute;inset:-10%;background:linear-gradient(105deg,transparent 40%,${alfa(cor, .55)} 50%,transparent 60%);transform:translate3d(-120%,0,0);animation:k-${ctx.id}-${c} ${dur(o.dur || 4)} ease-in-out infinite}@keyframes k-${ctx.id}-${c}{0%,55%{transform:translate3d(-120%,0,0)}85%,100%{transform:translate3d(120%,0,0)}}` };
    },
    /** vinheta colorida */
    vinheta(ctx, o, c) {
        return { html: `<b class="${c}"></b>`, css: `.ef-sobre-${ctx.id} .${c}{position:absolute;inset:0;background:radial-gradient(circle closest-side,transparent 55%,${alfa(o.cor || '#000', o.alfa || .55)} 100%);${o.pulso ? `animation:k-${ctx.id}-${c} ${dur(o.pulso)} ease-in-out infinite alternate` : ''}}@keyframes k-${ctx.id}-${c}{from{opacity:.5}to{opacity:1}}` };
    },
    /** barras de glitch deslocando */
    glitch(ctx, o, c) {
        const c1 = o.c1 || '#ff2d95', c2 = o.c2 || '#22e4ff';
        return { html: `<b class="${c}"></b>`, css: `.ef-sobre-${ctx.id} .${c}{position:absolute;inset:0;background:linear-gradient(transparent 20%,${alfa(c1, .35)} 20% 26%,transparent 26% 54%,${alfa(c2, .35)} 54% 60%,transparent 60%);mix-blend-mode:screen;opacity:0;animation:k-${ctx.id}-${c} ${dur(o.dur || 4)} steps(1,end) infinite}@keyframes k-${ctx.id}-${c}{0%,88%,100%{opacity:0;transform:translate3d(0,0,0)}90%{opacity:1;transform:translate3d(6%,0,0)}93%{opacity:1;transform:translate3d(-5%,6%,0)}96%{opacity:.7;transform:translate3d(3%,-8%,0)}}` };
    },
    /** linha de varredura (scan) */
    scan(ctx, o, c) {
        const cor = o.cor || '#22e4ff';
        return { html: `<b class="${c}"></b>`, css: `.ef-sobre-${ctx.id} .${c}{position:absolute;left:0;right:0;top:0;height:14%;background:linear-gradient(transparent,${alfa(cor, .5)} 70%,${cor});animation:k-${ctx.id}-${c} ${dur(o.dur || 3)} linear infinite}@keyframes k-${ctx.id}-${c}{from{transform:translate3d(0,-110%,0)}to{transform:translate3d(0,780%,0)}}` };
    },
    /** ícones caindo por cima da foto (pétalas, folhas, neve) */
    cai(ctx, o, c) {
        const R = rng(ctx.id + c), n = o.n || 6, vs = varsIcones(ctx, c, o.icones || [o.icone], o.pals);
        let h = '';
        for (let k = 0; k < n; k++) h += `<i style="left:${f1(R() * 100)}%;--s:${f1(o.tam || 11)}%;--t:${f1(3.4 + R() * 2.6)}s;--d:-${f1(R() * 6)}s;--b:${f1((R() - .5) * 24)}%;--img:var(${vs[k % vs.length]})"></i>`;
        return { html: `<b class="${c}">${h}</b>`, css: `.ef-sobre-${ctx.id} .${c} i{position:absolute;top:-14%;width:var(--s);aspect-ratio:1;background:var(--img) center/contain no-repeat;opacity:0;animation:k-${ctx.id}-${c} var(--t) linear var(--d) infinite}@keyframes k-${ctx.id}-${c}{0%{transform:translate3d(0,0,0) rotate(0);opacity:0}12%{opacity:1}88%{opacity:1}100%{transform:translate3d(var(--b),${o.alt || 760}%,0) rotate(200deg);opacity:0}}` };
    },
};

/** EA: camadas [{k, ...}] atrás da foto; `sobre`: camadas [{k, ...}] por cima da foto */
function EA(nome, desc, camadas, ex = {}) {
    return { tipo: 'efeito_avatar', nome, desc, raridade: ex.r || 'epico', animado: true, id: ex.id, extra: ex.css, gerar(ctx) {
        const id = ctx.id;
        let html = '', css = '', sobre = '', sobreCss = '';
        (camadas || []).forEach((o, i) => { const f = EA_CAMADAS[o.k]; if (!f) throw new Error('camada de avatar desconhecida: ' + o.k); const r = f(ctx, o, 'a' + (i + 1)); html += r.html; css += r.css; });
        (ex.sobre || []).forEach((o, i) => { const f = EA_SOBRE[o.k]; if (!f) throw new Error('camada sobre desconhecida: ' + o.k); const r = f(ctx, o, 's' + (i + 1)); sobre += r.html; sobreCss += r.css; });
        const ef = camadas && camadas.length ? `<i class="ef-av ef-av-${id} kz" aria-hidden="true">${html}</i>` : '';
        const so = ex.sobre ? `<i class="ef-av-sobre ef-sobre-${id} kz" aria-hidden="true">${sobre}</i>` : '';
        css += sobreCss;
        css += `.ef-sobre-${id} b{position:absolute;inset:0;display:block}.ef-sobre-${id} svg{position:absolute;inset:0;width:100%;height:100%;display:block}`;
        css += `.message .ef-sobre-${id}{display:none}.message .ef-av-${id} *{animation:none!important}`;
        if (ex.filtro) css += `.ef-av-${id}{filter:${ex.filtro}}.message .ef-av-${id}{filter:none}`;
        return { css, reg: { avatar: ef + so } };
    } };
}

// =====================================================================================
// EFEITO DE PERFIL (cartão 340 x 440; .ef-pf.kz é container size)
// =====================================================================================
/** cria `n` partículas (<i>) com variáveis sorteadas */
function particulas(ctx, c, o, fnEstilo) {
    const R = rng(ctx.id + c), n = o.n || 16, nomes = o.icones || [o.icone];
    const vs = nomes[0] ? varsIcones(ctx, c, nomes, o.pals) : [];
    let h = '';
    for (let k = 0; k < n; k++) h += `<i style="${fnEstilo(R, k, vs)}"></i>`;
    return h;
}
const EP_CAMADAS = {
    raw(ctx, o, c) { return { html: (o.html || '').replace(/\$ID/g, ctx.id).replace(/\$C/g, c), css: (o.css || '').replace(/\$ID/g, ctx.id).replace(/\$C/g, c) }; },
    /** ícones que caem (neve, pétalas, folhas, chuva de coisas) */
    cai(ctx, o, c) {
        const tam = o.tam || [14, 26], vel = o.vel || [6, 12];
        const h = particulas(ctx, c, o, (R, k, vs) => `left:${f1(R() * 100)}%;--s:${f1(tam[0] + R() * (tam[1] - tam[0]))}px;--t:${f1(vel[0] + R() * (vel[1] - vel[0]))}s;--d:-${f1(R() * vel[1])}s;--b:${f1((R() - .5) * (o.bal === undefined ? 70 : o.bal))}px;--r:${f1((R() - .5) * (o.giro === undefined ? 300 : o.giro))}deg;--a:${f2(o.alfa || 1)};--img:var(${vs[k % vs.length]})`);
        return { html: `<div class="${c}">${h}</div>`, css: `.ef-pf-${ctx.id} .${c} i{position:absolute;top:0;margin-left:calc(var(--s)/-2);width:var(--s);height:var(--s);background:var(--img) center/contain no-repeat;opacity:0;animation:k-${ctx.id}-${c} var(--t) linear var(--d) infinite}@keyframes k-${ctx.id}-${c}{0%{transform:translate3d(0,calc(var(--s)*-1.5),0) rotate(0);opacity:0}8%{opacity:var(--a)}90%{opacity:var(--a)}100%{transform:translate3d(var(--b),calc(100cqh + var(--s)),0) rotate(var(--r));opacity:0}}` };
    },
    /** ícones que sobem (bolhas, brasas, balões, corações) */
    sobe(ctx, o, c) {
        const tam = o.tam || [14, 26], vel = o.vel || [6, 12];
        const h = particulas(ctx, c, o, (R, k, vs) => `left:${f1(R() * 100)}%;--s:${f1(tam[0] + R() * (tam[1] - tam[0]))}px;--t:${f1(vel[0] + R() * (vel[1] - vel[0]))}s;--d:-${f1(R() * vel[1])}s;--b:${f1((R() - .5) * (o.bal === undefined ? 60 : o.bal))}px;--r:${f1((R() - .5) * (o.giro === undefined ? 40 : o.giro))}deg;--a:${f2(o.alfa || 1)};--img:var(${vs[k % vs.length]})`);
        return { html: `<div class="${c}">${h}</div>`, css: `.ef-pf-${ctx.id} .${c} i{position:absolute;top:0;margin-left:calc(var(--s)/-2);width:var(--s);height:var(--s);background:var(--img) center/contain no-repeat;opacity:0;animation:k-${ctx.id}-${c} var(--t) linear var(--d) infinite}@keyframes k-${ctx.id}-${c}{0%{transform:translate3d(0,calc(100cqh + var(--s)),0) rotate(0);opacity:0}10%{opacity:var(--a)}85%{opacity:var(--a)}100%{transform:translate3d(var(--b),calc(var(--s)*-1.5),0) rotate(var(--r));opacity:0}}` };
    },
    /** ícones que atravessam de um lado a outro (nuvens, peixes, morcegos, barcos) */
    deriva(ctx, o, c) {
        const tam = o.tam || [20, 34], vel = o.vel || [14, 26], y = o.y || [8, 85];
        const h = particulas(ctx, c, o, (R, k, vs) => `top:${f1(y[0] + R() * (y[1] - y[0]))}%;--s:${f1(tam[0] + R() * (tam[1] - tam[0]))}px;--t:${f1(vel[0] + R() * (vel[1] - vel[0]))}s;--d:-${f1(R() * vel[1])}s;--b:${f1((R() - .5) * (o.bal === undefined ? 30 : o.bal))}px;--a:${f2(o.alfa || 1)};--img:var(${vs[k % vs.length]})`);
        const ida = o.volta ? '-100cqw' : '100cqw';
        return { html: `<div class="${c}">${h}</div>`, css: `.ef-pf-${ctx.id} .${c} i{position:absolute;left:0;width:var(--s);height:var(--s);background:var(--img) center/contain no-repeat;${o.volta ? 'transform:scaleX(-1);' : ''}opacity:0;animation:k-${ctx.id}-${c} var(--t) linear var(--d) infinite}@keyframes k-${ctx.id}-${c}{0%{transform:translate3d(${o.volta ? '100cqw' : 'calc(var(--s)*-1.5)'},0,0)${o.volta ? ' scaleX(-1)' : ''};opacity:0}8%{opacity:var(--a)}90%{opacity:var(--a)}100%{transform:translate3d(${o.volta ? 'calc(var(--s)*-1.5)' : '100cqw'},var(--b),0)${o.volta ? ' scaleX(-1)' : ''};opacity:0}}` };
    },
    /** brilhinhos fixos que piscam */
    pisca(ctx, o, c) {
        const tam = o.tam || [8, 16];
        const h = particulas(ctx, c, o, (R, k, vs) => `left:${f1(R() * 100)}%;top:${f1(R() * 100)}%;--s:${f1(tam[0] + R() * (tam[1] - tam[0]))}px;--d:-${f1(R() * 4)}s;--t:${f1(1.8 + R() * 2.4)}s;--img:var(${vs[k % vs.length]})`);
        return { html: `<div class="${c}">${h}</div>`, css: `.ef-pf-${ctx.id} .${c} i{position:absolute;margin:calc(var(--s)/-2) 0 0 calc(var(--s)/-2);width:var(--s);height:var(--s);background:var(--img) center/contain no-repeat;opacity:0;animation:kPisca var(--t) ease-in-out var(--d) infinite}` };
    },
    /** enfeites presos nos cantos/bordas, balançando devagar. o.itens: [{icone, x, y, tam, rot, pal}] (x, y em %) */
    cantos(ctx, o, c) {
        const nomes = o.itens.map((it) => it.icone), vs = varsIcones(ctx, c, nomes, o.itens.map((it) => it.pal || o.pal));
        const h = o.itens.map((it, k) => `<i style="left:${it.x}%;top:${it.y}%;--s:${it.tam}px;--r:${it.rot || 0}deg;--d:-${f1(k * .7)}s;--img:var(${vs[k]})"></i>`).join('');
        return { html: `<div class="${c}">${h}</div>`, css: `.ef-pf-${ctx.id} .${c} i{position:absolute;margin:calc(var(--s)/-2) 0 0 calc(var(--s)/-2);width:var(--s);height:var(--s);background:var(--img) center/contain no-repeat;transform:rotate(var(--r));animation:k-${ctx.id}-${c} ${dur(o.dur || 5)} ease-in-out var(--d) infinite alternate}@keyframes k-${ctx.id}-${c}{from{transform:rotate(calc(var(--r) - ${o.bal || 4}deg))}to{transform:rotate(calc(var(--r) + ${o.bal || 4}deg))}}` };
    },
    /** manchas de névoa à deriva */
    neblina(ctx, o, c) {
        const R = rng(ctx.id + c), n = o.n || 4, cor = o.cor || '#cfd8e6';
        let h = '';
        for (let k = 0; k < n; k++) h += `<i style="top:${f1(10 + R() * 80)}%;--w:${f1(70 + R() * 50)}%;--h:${f1(14 + R() * 18)}%;--t:${f1((o.vel || 18) * (.8 + R() * .6))}s;--d:-${f1(R() * 20)}s"></i>`;
        return { html: `<div class="${c}">${h}</div>`, css: `.ef-pf-${ctx.id} .${c} i{position:absolute;left:0;width:var(--w);height:var(--h);background:radial-gradient(ellipse closest-side,${alfa(cor, o.alfa || .4)},transparent);opacity:.9;animation:k-${ctx.id}-${c} var(--t) ease-in-out var(--d) infinite alternate}@keyframes k-${ctx.id}-${c}{from{transform:translate3d(-30%,0,0)}to{transform:translate3d(calc(100cqw - 60%),0,0)}}` };
    },
    /** clarão que pisca de vez em quando (relâmpago, flash de câmera) */
    flash(ctx, o, c) {
        const cor = o.cor || '#fff';
        return { html: `<i class="${c}"></i>`, css: `.ef-pf-${ctx.id} .${c}{position:absolute;inset:0;background:${o.fundo || `radial-gradient(circle at 50% 30%,${alfa(cor, .85)},${alfa(cor, .25)} 60%,transparent)`};opacity:0;animation:k-${ctx.id}-${c} ${dur(o.dur || 9)} linear infinite}@keyframes k-${ctx.id}-${c}{0%,${o.ini || 60}%{opacity:0}${(o.ini || 60) + 1}%{opacity:.9}${(o.ini || 60) + 3}%{opacity:.05}${(o.ini || 60) + 5}%{opacity:.7}${(o.ini || 60) + 9}%,100%{opacity:0}}` };
    },
    /** riscos de chuva caindo na diagonal */
    chuva(ctx, o, c) {
        const R = rng(ctx.id + c), n = o.n || 26, cor = o.cor || '#bcd7ff';
        let h = '';
        for (let k = 0; k < n; k++) h += `<i style="left:${f1(R() * 110 - 5)}%;--h:${f1(14 + R() * 22)}px;--t:${f1(.7 + R() * .6)}s;--d:-${f1(R() * 1.6)}s"></i>`;
        return { html: `<div class="${c}">${h}</div>`, css: `.ef-pf-${ctx.id} .${c} i{position:absolute;top:0;width:1.4px;height:var(--h);background:linear-gradient(transparent,${alfa(cor, o.alfa || .6)});opacity:0;transform:rotate(${o.ang || 12}deg);animation:k-${ctx.id}-${c} var(--t) linear var(--d) infinite}@keyframes k-${ctx.id}-${c}{0%{transform:translate3d(0,calc(var(--h)*-1),0) rotate(${o.ang || 12}deg);opacity:0}10%{opacity:1}100%{transform:translate3d(${o.dx || -40}px,calc(100cqh + var(--h)),0) rotate(${o.ang || 12}deg);opacity:.9}}` };
    },
    /** vinheta/brilho de borda que pulsa */
    borda(ctx, o, c) {
        const cor = o.cor || '#fff';
        return { html: `<i class="${c}"></i>`, css: `.ef-pf-${ctx.id} .${c}{position:absolute;inset:0;border-radius:inherit;box-shadow:inset 0 0 ${o.blur || 40}px ${o.esp || 6}px ${alfa(cor, o.alfa || .55)};animation:k-${ctx.id}-${c} ${dur(o.dur || 4)} ease-in-out infinite alternate}@keyframes k-${ctx.id}-${c}{from{opacity:.4}to{opacity:1}}` };
    },
    /** gradiente que respira cobrindo o cartão (clima de cor) */
    clima(ctx, o, c) {
        return { html: `<i class="${c}"></i>`, css: `.ef-pf-${ctx.id} .${c}{position:absolute;inset:0;background:${o.fundo};opacity:${o.min === undefined ? .5 : o.min};animation:k-${ctx.id}-${c} ${dur(o.dur || 6)} ease-in-out infinite alternate}@keyframes k-${ctx.id}-${c}{from{opacity:${o.min === undefined ? .5 : o.min}}to{opacity:${o.max === undefined ? 1 : o.max}}}` };
    },
    /** faixa de onda rolando na base */
    ondas(ctx, o, c) {
        const cor = o.cor || '#4aa3ff', h = o.alt || 14;
        const svg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 20' preserveAspectRatio='none'><path d='M0 10Q15 0 30 10T60 10T90 10T120 10V20H0Z' fill='${cor}' fill-opacity='${o.alfa || .55}'/></svg>`;
        const v = nomeVar(ctx.id, c); ctx.vars[v] = uri(svg);
        return { html: `<i class="${c}"></i>`, css: `.ef-pf-${ctx.id} .${c}{position:absolute;left:0;bottom:0;width:200%;height:${h}%;background:var(${v}) 0 100%/25% 100% repeat-x;animation:k-${ctx.id}-${c} ${dur(o.dur || 7)} linear infinite}@keyframes k-${ctx.id}-${c}{to{transform:translate3d(-50%,0,0)}}` };
    },
};

function EP(nome, desc, camadas, ex = {}) {
    return { tipo: 'efeito_perfil', nome, desc, raridade: ex.r || 'lendario', animado: true, id: ex.id, extra: ex.css, gerar(ctx) {
        const id = ctx.id;
        let html = '', css = '';
        camadas.forEach((o, i) => { const f = EP_CAMADAS[o.k]; if (!f) throw new Error('camada de perfil desconhecida: ' + o.k); const r = f(ctx, o, 'p' + (i + 1)); html += r.html; css += r.css; });
        css += `@media (prefers-reduced-motion:reduce){.ef-pf-${id} i{display:none}}`;
        return { css, reg: { perfil: `<div class="ef-pf ef-pf-${id} kz" aria-hidden="true">${html}</div>` } };
    } };
}

/** atraso de animação que faz a PRÉVIA nascer numa fase representativa do ciclo (efeitos de ciclo longo começam "vazios").
 *  `--ef-prev` é 1 nas prévias (Armazém, inventário, editor) e 0 no uso normal; `ponto` é a fração do ciclo que mostra o efeito no auge. */
const fase = (durSeg, ponto = .5) => `calc(var(--ef-prev,0) * ${ponto} * -${durSeg}s)`;

module.exports = { EA, EP, EA_CAMADAS, EA_SOBRE, EP_CAMADAS, varsIcones, imgIcone, fase };
