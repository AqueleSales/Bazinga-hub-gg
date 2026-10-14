'use strict';
/* O KIT: cada função cria um item de cosmético a partir de uma especificação curta.
   Um item é { tipo, nome, desc, raridade, animado, id?, gerar(ctx) }. `gerar` devolve o CSS (e, quando precisa, o registro de HTML/som).
   ctx = { tema, id, vars } - `vars` são variáveis CSS globais (:root) onde moram as imagens SVG. */
const B = require('./base');
const { f1, f2, claro, escuro, alfa, mix, uri } = B;
const { icone } = require('./icones');
const P = require('./padroes');

// ---------------------------------------------------------------------------
// auxiliares
// ---------------------------------------------------------------------------
const FONTES = {
    serifa: "Georgia,'Times New Roman',serif", mono: "ui-monospace,'Courier New',monospace", cursiva: "'Segoe Script','Brush Script MT','Comic Sans MS',cursive",
    impacto: "Impact,'Arial Black',sans-serif", redonda: "'Trebuchet MS','Varela Round',system-ui,sans-serif", gotica: "'Old English Text MT','Palatino Linotype',Georgia,serif",
    quadrinho: "'Comic Sans MS','Chalkboard SE','Trebuchet MS',cursive", classica: "'Palatino Linotype',Palatino,'Book Antiqua',serif", largos: "'Arial Black','Segoe UI Black',sans-serif",
    fina: "'Segoe UI Light','Helvetica Neue',Arial,sans-serif", maquina: "'Courier New',Courier,monospace",
};
const palDe = (ctx, o) => ({ ...(ctx.tema.pal || {}), ...((o && o.pal) || {}) });
const nomeVar = (id, suf) => `--k-${id.replace(/_/g, '-')}${suf ? '-' + suf : ''}`;
const dur = (s) => `${f1(s)}s`;
/** regras de moldura nos 4 contextos de avatar */
const CTX_AV = ['', '.pf-tile-av', '.message .chat-avatar', '.video-avatar'];
const molduraSel = (id, pseudo = 'before') => CTX_AV.map((c) => `${c}.moldura-${id}::${pseudo}`).join(',');

// ---------------------------------------------------------------------------
// MOLDURA
// ---------------------------------------------------------------------------
/** o.t: 'icones' | 'forma' | 'grad' | 'liso' | 'svg' */
function M(nome, desc, o, ex = {}) {
    return { tipo: 'moldura', nome, desc, raridade: ex.r || 'raro', animado: o.giro !== 0 && o.t !== 'liso', id: ex.id, extra: ex.css, gerar(ctx) {
        const id = ctx.id, p = palDe(ctx, o), giro = o.giro === undefined ? 40 : o.giro;
        if (o.t === 'grad' || o.t === 'liso') {
            let fundo, anim = '';
            if (o.t === 'liso') fundo = o.cor;
            else if (o.tracejado) fundo = `repeating-conic-gradient(from var(--bp-angulo),${o.cores[0]} 0 ${o.tracejado[0]}deg,${o.cores[1] || 'transparent'} ${o.tracejado[0]}deg ${o.tracejado[0] + o.tracejado[1]}deg)`;
            else fundo = `conic-gradient(from var(--bp-angulo),${[...o.cores, o.cores[0]].join(',')})`;
            const anima = o.t === 'grad' && giro !== 0;
            return { css: `.moldura-${id}::before{background:${fundo};${anima ? `animation:bpGira ${dur(giro || 6)} linear infinite;` : 'animation:none;'}${o.glow ? `filter:drop-shadow(0 0 5px ${o.glow});` : ''}}${o.glow ? `.message .chat-avatar.moldura-${id}::before{filter:none}` : ''}` };
        }
        const inset = o.inset || (o.t === 'forma' ? .2 : .26);
        let svg;
        if (o.t === 'icones') svg = P.anelDeIcones({ ...o, pals: o.pals || [p], raio: o.raio || (100 / (1 + 2 * inset) + (o.tam || 26) / 2 - 2) });
        else if (o.t === 'forma') { const ri = 100 / (1 + 2 * inset) - 1; svg = P.anelDeForma({ ...o, ri, R: ri + (o.esp || 11) }); }
        else svg = o.svg;
        const v = nomeVar(id);
        ctx.vars[v] = uri(svg);
        const base = `inset:${f1(-inset * 100)}%;-webkit-mask:none;mask:none;background:var(${v}) center/100% 100% no-repeat;`;
        const anim = giro === 0 ? 'animation:none;' : `animation:kGira ${dur(giro)} linear ${giro < 0 ? 'reverse ' : ''}infinite;`;
        const pulso = o.pulso ? `animation:kGira ${dur(giro || 40)} linear infinite,kPulsa ${dur(o.pulso)} ease-in-out infinite;` : '';
        const glow = o.glow ? `filter:drop-shadow(0 0 3px ${o.glow});` : '';
        return { css: `.moldura-${id}::before{${base}${pulso || anim}${glow}}` +
            `.pf-tile-av.moldura-${id}::before,.message .chat-avatar.moldura-${id}::before,.video-avatar.moldura-${id}::before{${base}}` +
            `.message .chat-avatar.moldura-${id}::before{animation:none;filter:none}` };
    } };
}

// ---------------------------------------------------------------------------
// NOME
// ---------------------------------------------------------------------------
/** o: { cor | grad:[...], mov:'desliza'|'pulsa'|'pisca'|'glitch'|'nenhum', dur, contorno, cw, fonte, espaco, peso, brilho, sombra:[dx,dy,cor], icone:{nome,pos,tam,pal}, maius } */
function N(nome, desc, o, ex = {}) {
    return { tipo: 'nome', nome, desc, raridade: ex.r || 'raro', animado: !!o.mov && o.mov !== 'nenhum', id: ex.id, extra: ex.css, gerar(ctx) {
        const id = ctx.id, p = palDe(ctx, o), mov = o.mov || 'nenhum', d = o.dur || 4;
        let r = '', extra = '';
        const grad = o.grad ? [...o.grad, o.grad[0]] : null;
        if (grad) {
            // `passos`: cores secas (sem degradê), cada uma ocupando uma fatia igual
            const stops = o.passos ? o.grad.map((c, k) => `${c} ${f1(k * 100 / o.grad.length)}% ${f1((k + 1) * 100 / o.grad.length)}%`).concat([`${o.grad[0]} 100%`]).join(',') : grad.join(',');
            r += `color:transparent!important;-webkit-background-clip:text;background-clip:text;background-image:linear-gradient(90deg,${stops});background-size:${mov === 'desliza' ? '200% auto' : '100% auto'};`;
        } else r += `color:${o.cor}!important;`;
        r += `font-weight:${o.peso || 800};`;
        if (o.fonte) r += `font-family:${FONTES[o.fonte] || o.fonte};`;
        if (o.espaco !== undefined) r += `letter-spacing:${o.espaco}px;`;
        if (o.contorno) r += `-webkit-text-stroke:${o.cw || .6}px ${o.contorno};paint-order:stroke fill;`;
        if (o.maius) r += 'text-transform:uppercase;';
        const fl = [];
        if (o.brilho) fl.push(`drop-shadow(0 0 ${o.bw || 3}px ${o.brilho})`);
        if (o.sombra) fl.push(`drop-shadow(${o.sombra[0]}px ${o.sombra[1]}px 0 ${o.sombra[2]})`);
        if (fl.length) r += `filter:${fl.join(' ')};`;
        if (mov === 'desliza') r += `animation:kNomeDesl ${dur(d)} ${o.passos ? `steps(${o.grad.length},end)` : 'linear'} infinite;`;
        else if (mov === 'pulsa' && o.brilho) { extra += `@keyframes k-${id}-p{from{filter:drop-shadow(0 0 1px ${o.brilho})}to{filter:drop-shadow(0 0 ${(o.bw || 3) * 2.4}px ${o.brilho})}}`; r += `animation:k-${id}-p ${dur(d)} ease-in-out infinite alternate;`; }
        else if (mov === 'pisca') { extra += `@keyframes k-${id}-s{0%,100%{opacity:1}50%{opacity:${o.piscaMin || .45}}}`; r += `animation:k-${id}-s ${dur(d)} ease-in-out infinite;`; }
        else if (mov === 'glitch') { const c1 = o.g1 || '#ff2d95', c2 = o.g2 || '#22e4ff'; extra += `@keyframes k-${id}-g{0%,88%,100%{filter:none}90%{filter:drop-shadow(2px 0 ${c1}) drop-shadow(-2px 0 ${c2})}94%{filter:drop-shadow(-3px 0 ${c1}) drop-shadow(3px 0 ${c2})}}`; r += `animation:k-${id}-g ${dur(d)} steps(1,end) infinite;`; }
        else if (mov === 'gotejar') { extra += `@keyframes k-${id}-j{0%,100%{filter:drop-shadow(0 0 0 ${o.brilho || '#900'})}50%{filter:drop-shadow(0 3px 2px ${o.brilho || '#900'})}}`; r += `animation:k-${id}-j ${dur(d)} ease-in-out infinite;`; }
        let css = `.ne-${id}{${r}}${extra}`;
        if (o.icone) {
            const ic = o.icone, v = nomeVar(id, 'n');
            ctx.vars[v] = uri(`<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>${icone(ic.nome, { ...p, ...(ic.pal || {}) })}</svg>`);
            const pos = ic.pos === 'antes' ? 'before' : 'after';
            css += `.ne-${id}::${pos}{content:'';display:inline-block;width:${ic.tam || .95}em;height:${ic.tam || .95}em;${pos === 'after' ? 'margin-left' : 'margin-right'}:.22em;vertical-align:-.12em;background:var(${v}) center/contain no-repeat;-webkit-text-stroke:0;}`;
        }
        return { css };
    } };
}

// ---------------------------------------------------------------------------
// PLACA
// ---------------------------------------------------------------------------
/** o: { base: cor | [c1,c2], pad: { tipo, c1, c2, tam, ... }, mov:'x'|'y'|'xy'|'-x'|'nenhum', dur, icone:{nome,pal,lado,tam}, brilho:cor, borda } */
function Pl(nome, desc, o, ex = {}) {
    return { tipo: 'placa', nome, desc, raridade: ex.r || 'raro', animado: (o.mov !== undefined ? o.mov !== 'nenhum' : !!o.pad) || !!o.brilho, id: ex.id, extra: ex.css, gerar(ctx) {
        const id = ctx.id, p = palDe(ctx, o), mov = o.mov === undefined ? (o.pad ? 'x' : 'nenhum') : o.mov;
        const camadas = [];     // { img, size, pos0, pos1, repeat }
        const bar = {};         // posições alternativas na barra do usuário
        if (o.icone) {
            const v = nomeVar(id, 'i');
            ctx.vars[v] = uri(`<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>${icone(o.icone.nome, { ...p, ...(o.icone.pal || {}) })}</svg>`);
            const lado = o.icone.lado === 'esq' ? 'left 12px' : 'right 14px';
            camadas.push({ img: `var(${v})`, size: `auto ${o.icone.tam || 62}%`, pos0: `${lado} center`, pos1: `${lado} center`, repeat: 'no-repeat', bar: o.icone.lado === 'esq' ? 'left 54px center' : 'calc(100% - 132px) center' });
        }
        if (o.brilho) camadas.push({ img: `linear-gradient(100deg,transparent 38%,${o.brilho} 50%,transparent 62%)`, size: '260% 100%', pos0: '140% 0', pos1: '-40% 0', repeat: 'no-repeat' });
        if (o.pad) {
            const t = P.ladrilho({ ...o.pad, pals: o.pad.pals || [p] });
            const v = nomeVar(id, 'p');
            ctx.vars[v] = uri(t.svg);
            const dx = /x/.test(mov) ? (mov[0] === '-' ? -t.w : t.w) : 0, dy = /y/.test(mov) ? t.h : 0;
            camadas.push({ img: `var(${v})`, size: `${t.w}px ${t.h}px`, pos0: '0 0', pos1: `${dx}px ${dy}px`, repeat: 'repeat' });
        }
        const base = Array.isArray(o.base) ? `linear-gradient(${o.angulo || 100}deg,${o.base.join(',')})` : (o.base || '#222');
        // camadas extras por cima do fundo (barra de vida que esvazia...): { img, size, size1?, pos, pos1?, repeat }
        const ordem = camadas.splice(0, camadas.length);
        (o.extra || []).forEach((c) => camadas.push({ img: c.img, size: c.size, size1: c.size1, pos0: c.pos || '0 0', pos1: c.pos1 || c.pos || '0 0', repeat: c.repeat || 'no-repeat' }));
        ordem.forEach((c) => camadas.push(c));
        camadas.push({ img: base === o.base ? `linear-gradient(${base},${base})` : base, size: '100% 100%', pos0: '0 0', pos1: '0 0', repeat: 'no-repeat' });
        const anima = camadas.some((c) => c.pos0 !== c.pos1 || (c.size1 && c.size1 !== c.size));
        const montar = (barra) => {
            const g = (k) => camadas.map((c) => (barra && k.startsWith('pos') && c.bar ? c.bar : c[k])).join(',');
            const tam = camadas.map((c) => (barra && c.bar ? 'auto 44%' : c.size)).join(',');
            const nomeKf = `k-${id}-${barra && o.icone ? 'pb' : 'pl'}`;
            const tam1 = camadas.map((c) => (barra && c.bar ? 'auto 44%' : (c.size1 || c.size))).join(',');
            const temTam = camadas.some((c) => c.size1 && c.size1 !== c.size);
            const kf = anima ? `@keyframes ${nomeKf}{from{background-position:${g('pos0')}${temTam ? `;background-size:${tam}` : ''}}to{background-position:${g('pos1')}${temTam ? `;background-size:${tam1}` : ''}}}` : '';
            const decl = `background-color:${Array.isArray(o.base) ? o.base[0] : (o.base || '#222')}!important;background-image:${g('img')}!important;background-size:${tam}!important;background-position:${g('pos0')}!important;background-repeat:${g('repeat')}!important;`
                + (anima ? `animation:${nomeKf} ${dur(o.dur || 8)} linear infinite${o.alterna ? ' alternate' : ''}!important;` : 'animation:none!important;')
                + (o.borda ? `box-shadow:inset 0 0 0 1.5px ${o.borda}!important;` : '');
            return { decl, kf };
        };
        const a1 = montar(false), a2 = montar(true);
        // texto escuro em placa clara: vale pro nome, pro status e pros ícones (menos o nome estilizado, que tem cor própria)
        const txt = o.texto ? `.placa-${id}:not(.xx),.placa-${id} :not([class*="ne-"]){color:${o.texto}!important;text-shadow:none!important}` : '';
        return { css: `.placa-${id}{${a1.decl}}.user-profile-bar.placa-${id}{${a2.decl}}${txt}${a1.kf}${o.icone ? a2.kf : ''}` };
    } };
}

// ---------------------------------------------------------------------------
// FAIXA (banner do perfil, 340 x 112 de referência)
// ---------------------------------------------------------------------------
const svgCena = (frag) => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 ${P.VW} ${P.VH}' preserveAspectRatio='xMidYMax slice'>${frag}</svg>`;
/** o: { fundo:[c1,c2,c3?], angulo, fixo:frag, longe:{ svg, anim:'pan'|'pisca'|'flutua'|'respira'|'nenhuma', dur, rev }, perto:{...} } */
function F(nome, desc, o, ex = {}) {
    return { tipo: 'faixa', nome, desc, raridade: ex.r || 'raro', animado: true, id: ex.id, extra: ex.css, gerar(ctx) {
        const id = ctx.id;
        const fundo = o.fundo ? (o.fundo.length === 1 ? o.fundo[0] : `linear-gradient(${o.angulo === undefined ? 180 : o.angulo}deg,${o.fundo.join(',')})`) : '#222';
        let imgs = '', css = '', kf = '';
        if (o.fixo) { const v = nomeVar(id, 'f'); ctx.vars[v] = uri(svgCena(o.fixo)); imgs = `var(${v}) center bottom/cover no-repeat,`; }
        css += `:where(.banner-anim-${id}){position:relative}.banner-anim-${id}{overflow:hidden;background:${imgs}${fundo};animation:none;}`;
        ['longe', 'perto'].forEach((nm, i) => {
            const l = o[nm];
            if (!l) return;
            const v = nomeVar(id, nm[0]), pseudo = i ? 'after' : 'before', a = l.anim || 'pan', d = l.dur || (i ? 24 : 48);
            ctx.vars[v] = uri(svgCena(l.svg));
            const comum = `content:'';position:absolute;pointer-events:none;`;
            if (a === 'pan') {
                css += `.banner-anim-${id}::${pseudo}{${comum}top:0;bottom:0;left:0;width:200%;background:var(${v}) 0 100%/50% 100% repeat-x;animation:k-${id}-${nm[0]} ${dur(d)} linear infinite${l.rev ? ' reverse' : ''};}`;
                kf += `@keyframes k-${id}-${nm[0]}{to{transform:translate3d(-50%,0,0)}}`;
            } else {
                css += `.banner-anim-${id}::${pseudo}{${comum}inset:0;background:var(${v}) center bottom/cover no-repeat;`;
                if (a === 'pisca') { css += `animation:k-${id}-${nm[0]} ${dur(d)} ease-in-out infinite;}`; kf += `@keyframes k-${id}-${nm[0]}{0%,100%{opacity:${l.min === undefined ? .3 : l.min}}50%{opacity:1}}`; }
                else if (a === 'flutua') { css += `animation:k-${id}-${nm[0]} ${dur(d)} ease-in-out infinite alternate;}`; kf += `@keyframes k-${id}-${nm[0]}{from{transform:translate3d(0,${l.dy || 4}px,0)}to{transform:translate3d(0,${-(l.dy || 4)}px,0)}}`; }
                else if (a === 'respira') { css += `animation:k-${id}-${nm[0]} ${dur(d)} ease-in-out infinite alternate;}`; kf += `@keyframes k-${id}-${nm[0]}{from{opacity:${l.min === undefined ? .55 : l.min};transform:scale(1)}to{opacity:1;transform:scale(1.04)}}`; }
                else css += '}';
            }
        });
        return { css: css + kf };
    } };
}

module.exports = { M, N, Pl, F, FONTES, palDe, nomeVar, dur, svgCena, CTX_AV, molduraSel, P };
