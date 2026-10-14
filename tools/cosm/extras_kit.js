'use strict';
/* Extras do kit: efeito de fala (call), do radar (mapa), do chat, pin de nota, efeito de servidor e som de entrada. Todos pequenos: só cor, ritmo e (às vezes) um ícone. */
const B = require('./base');
const { f1, uri, alfa, claro, escuro } = B;
const { icone } = require('./icones');
const { palDe, nomeVar, dur } = require('./kit');

/** efeito de fala: o card da call acende quando a pessoa fala. o: { cores:[c1,c2,(c3)], passos:true (troca seca de cor), dur } */
function FALA(nome, desc, o, ex = {}) {
    return { tipo: 'efeito_fala', nome, desc, raridade: ex.r || 'epico', animado: true, id: ex.id, extra: ex.css, gerar(ctx) {
        const id = ctx.id, cs = o.cores, c1 = cs[0], c2 = cs[1] || cs[0], d = o.dur || .7, ease = o.passos ? 'steps(1,end)' : 'ease-in-out', alt = o.passos ? '' : ' alternate';
        let kf, kfa;
        if (o.passos) {
            const n = cs.length;
            kf = `@keyframes k-${id}-f{${cs.map((c, k) => `${f1(k * 100 / n)}%{box-shadow:0 0 0 4px ${c},0 0 0 8px ${cs[(k + 1) % n]}}`).join('')}}`;
            kfa = `@keyframes k-${id}-fa{${cs.map((c, k) => `${f1(k * 100 / n)}%{box-shadow:0 0 0 3px ${c},0 0 0 6px ${cs[(k + 1) % n]}}`).join('')}}`;
        } else {
            kf = `@keyframes k-${id}-f{from{box-shadow:0 0 0 3px ${c1},0 0 12px 2px ${alfa(c2, .45)}}to{box-shadow:0 0 0 5px ${c2},0 0 26px 6px ${alfa(c1, .75)}}}`;
            kfa = `@keyframes k-${id}-fa{from{box-shadow:0 0 0 2px ${c1},0 0 8px 1px ${alfa(c2, .45)}}to{box-shadow:0 0 0 4px ${c2},0 0 16px 4px ${alfa(c1, .75)}}}`;
        }
        return { css: `.video-card.fala-${id}.is-speaking{box-shadow:0 0 0 3px ${c1},0 0 22px 4px ${alfa(c2, .6)}!important;animation:k-${id}-f ${dur(d)} ${ease} infinite${alt}}.video-card.fala-${id}.is-speaking .video-avatar,.inv-fala.fala-${id} .inv-av-img{box-shadow:0 0 0 3px ${c1},0 0 14px 3px ${alfa(c2, .6)};animation:k-${id}-fa ${dur(d)} ${ease} infinite${alt}}${kf}${kfa}`, reg: { fala: id } };
    } };
}

/** efeito do radar: o estilo das ondas que saem de você no mapa. o: { cor, estilo:'liso'|'tracejado'|'pontilhado'|'duplo', glow, passos } */
function RADAR(nome, desc, o, ex = {}) {
    return { tipo: 'efeito_radar', nome, desc, raridade: ex.r || 'epico', animado: true, id: ex.id, extra: ex.css, gerar(ctx) {
        const id = ctx.id, cor = o.cor, borda = { liso: 'solid', tracejado: 'dashed', pontilhado: 'dotted', duplo: 'double' }[o.estilo || 'liso'];
        const bw = o.estilo === 'duplo' ? 5 : 3;
        return { css: `.raio-onda.radar-${id} i{border:${bw}px ${borda} ${cor};background:${o.fundo || 'none'};box-shadow:0 0 ${o.glow ? 12 : 0}px ${alfa(o.glow || cor, .5)}${o.passos ? ';animation-timing-function:steps(10,end)' : ''}}.inv-radar.radar-${id} i{border:${bw}px ${borda} ${cor}}`, reg: { radar: id } };
    } };
}

/** efeito do chat: brilho na barra ao digitar + partículas ao enviar. o: { cor, cor2, particula:{icone,pal}|{forma:'circulo'|'losango'|'quadrado'|'estrela'}, dur } */
function CHAT(nome, desc, o, ex = {}) {
    return { tipo: 'efeito_chat', nome, desc, raridade: ex.r || 'epico', animado: true, id: ex.id, extra: ex.css, gerar(ctx) {
        const id = ctx.id, c1 = o.cor, c2 = o.cor2 || o.cor, p = palDe(ctx, o);
        let css = `.chat-input-container.chat-ef-${id}.digitando,.inv-chat.chat-ef-${id}{border-color:${c1}!important;box-shadow:0 0 0 2px ${alfa(c1, .9)},0 0 16px ${alfa(c2, .55)}!important;animation:k-${id}-c ${dur(o.dur || 1.2)} ease-in-out infinite alternate}@keyframes k-${id}-c{from{box-shadow:0 0 0 2px ${alfa(c1, .9)},0 0 8px ${alfa(c2, .3)}}to{box-shadow:0 0 0 3px ${c2},0 0 20px ${alfa(c1, .7)}}}`;
        let part = `.ef-envio-${id} i{position:absolute;bottom:4px;opacity:0;min-width:9px;min-height:9px;animation:envioSobe var(--t) ease-out forwards;`;
        const pa = o.particula || { forma: 'circulo' };
        if (pa.icone) {
            const v = nomeVar(id, 'e');
            ctx.vars[v] = uri(`<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>${icone(pa.icone, { ...p, ...(pa.pal || {}) })}</svg>`);
            part += `background:var(${v}) center/contain no-repeat;}`;
        } else {
            const forma = { circulo: 'border-radius:50%', losango: 'clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%)', quadrado: 'border-radius:1px', estrela: 'clip-path:polygon(50% 0,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)' }[pa.forma || 'circulo'];
            part += `background:${c1};${forma};}.ef-envio-${id} i:nth-child(even){background:${c2};}`;
        }
        css += part;
        return { css, reg: { chat: id } };
    } };
}

/** pin de nota no mapa: o balão ganha a forma de um ícone. o: { icone, pal } */
function PIN(nome, desc, o, ex = {}) {
    return { tipo: 'pin_nota', nome, desc, raridade: ex.r || 'epico', animado: !!o.bal, id: ex.id, extra: ex.css, gerar(ctx) {
        const id = ctx.id, p = palDe(ctx, o), v = nomeVar(id, 'pin');
        ctx.vars[v] = uri(`<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>${icone(o.icone, { ...p, ...(o.pal || {}) })}</svg>`);
        return { css: `.geo-note-bubble.pin-${id}.minimized{background:var(${v}) center/115% no-repeat!important;border:0!important;border-radius:0!important;box-shadow:none!important;filter:drop-shadow(0 2px 2px rgba(0,0,0,.45));opacity:1!important;${o.bal ? `animation:k-${id}-pin ${dur(o.bal)} ease-in-out infinite alternate;` : ''}}.geo-note-bubble.pin-${id}.minimized>.note-emoji{position:relative;z-index:1;font-size:11px!important}.geo-note-bubble.pin-${id}:not(.minimized){box-shadow:0 0 0 2px ${alfa(p.m, .8)},0 8px 24px rgba(0,0,0,.6)}${o.bal ? `@keyframes k-${id}-pin{from{transform:translateY(0) rotate(-4deg)}to{transform:translateY(-2px) rotate(4deg)}}` : ''}`, reg: { pin: id } };
    } };
}

/** efeito de servidor: aura no ícone do servidor (barra, cabeçalho, mapa). o: { cores:[c1,c2], passos } */
function SERV(nome, desc, o, ex = {}) {
    return { tipo: 'efeito_servidor', nome, desc, raridade: ex.r || 'epico', animado: true, id: ex.id, extra: ex.css, gerar(ctx) {
        const id = ctx.id, [c1, c2] = [o.cores[0], o.cores[1] || o.cores[0]];
        return { css: `.sv-ef-${id}{box-shadow:0 0 0 3px ${c1},0 0 14px 2px ${alfa(c2, .55)}!important;animation:k-${id}-s ${dur(o.dur || 2.4)} ${o.passos ? 'steps(1,end)' : 'ease-in-out'} infinite${o.passos ? '' : ' alternate'}}@keyframes k-${id}-s{${o.passos ? `50%{box-shadow:0 0 0 3px ${c2},0 0 14px 2px ${alfa(c1, .55)}}` : `from{box-shadow:0 0 0 2px ${c1},0 0 6px 1px ${alfa(c2, .4)}}to{box-shadow:0 0 0 4px ${c2},0 0 18px 4px ${alfa(c1, .75)}}`}}.pino-foto.sv-ef-${id}{border-color:${c1}}`, reg: { servidor: id } };
    } };
}

/** som de entrada na call (sintetizado no navegador). o: { notas:[{t,f,f2?,d,tipo?,v?}], ruidos:[{t,d,f,f2?,filtro?,v?,q?}] } */
function SOM(nome, desc, o, ex = {}) {
    return { tipo: 'som_call', nome, desc, raridade: ex.r || 'epico', animado: false, id: ex.id, extra: ex.css, gerar(ctx) {
        const fim = Math.max(0, ...(o.notas || []).map((n) => n.t + n.d), ...(o.ruidos || []).map((n) => n.t + n.d));
        return { css: '', reg: { som: ctx.id, receita: { notas: o.notas || [], ruidos: o.ruidos || [], total: f1(fim + .05) } } };
    } };
}

module.exports = { FALA, RADAR, CHAT, PIN, SERV, SOM };
