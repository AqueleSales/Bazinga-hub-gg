'use strict';
/* Geradores de imagem do kit: anéis de ícones, formas de anel, ladrilhos de padrão e camadas de cenário (faixas).
   Tudo devolve SVG como texto (viewBox fixo); quem chama embrulha com `uri()` e entrega ao CSS por variável. */
const { f1, f2, claro, escuro, rng } = require('./base');
const { icone, paleta } = require('./icones');

/** Define os ícones usados numa imagem como <symbol> e devolve { defs, usar(nome, pal, x, y, tam, rot) }. Cada (ícone, paleta) vira um símbolo. */
function simbolos() {
    const mapa = new Map();
    let defs = '';
    return {
        usar(nome, pal, cx, cy, tam, rot = 0, extra = '') {
            const chave = nome + JSON.stringify(pal || {});
            if (!mapa.has(chave)) {
                const id = 's' + mapa.size;
                mapa.set(chave, id);
                defs += `<symbol id='${id}' viewBox='0 0 100 100'>${icone(nome, pal)}</symbol>`;
            }
            return `<use href='#${mapa.get(chave)}' x='${f1(cx - tam / 2)}' y='${f1(cy - tam / 2)}' width='${f1(tam)}' height='${f1(tam)}'${rot ? ` transform='rotate(${f1(rot)} ${f1(cx)} ${f1(cy)})'` : ''}${extra}/>`;
        },
        get defs() { return `<defs>${defs}</defs>`; },
    };
}

/** Anel de ícones em volta do centro de um quadro 200x200.
 *  o: { icones:[nomes], pals:[paletas], n, tam, raio, rot0, orient:'fora'|'reto'|'tang', tams:[variações de tamanho] } */
function anelDeIcones(o) {
    const S = simbolos();
    const n = o.n || 12, nomes = o.icones, pals = o.pals || [{}], raio = o.raio || 84, tam = o.tam || 26, rot0 = o.rot0 || 0;
    let usos = '';
    for (let k = 0; k < n; k++) {
        const a = rot0 + (k / n) * 360, ar = (a - 90) * Math.PI / 180;
        const cx = 100 + raio * Math.cos(ar), cy = 100 + raio * Math.sin(ar);
        const t = tam * (o.tams ? o.tams[k % o.tams.length] : 1);
        const rot = o.orient === 'fora' ? a : o.orient === 'tang' ? a + 90 : (o.inclina ? ((k % 2) ? 12 : -12) : 0);
        usos += S.usar(nomes[k % nomes.length], pals[k % pals.length], cx, cy, t, rot);
    }
    return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'>${S.defs}${usos}</svg>`;
}

/** Anel "de forma": borda de fora modulada (ondas, nuvem, dentes...) com um furo redondo no meio. Quadro 200x200, furo de raio `ri`. */
function anelDeForma(o) {
    const forma = o.forma || 'ondas', ri = o.ri || 69, R = o.R || ri + 11, n = o.n || 12, A = o.amp || 7;
    let d = '';
    const passos = 360;
    for (let i = 0; i <= passos; i++) {
        const t = (i / passos) * 2 * Math.PI;
        const u = ((t * n / (2 * Math.PI)) % 1 + 1) % 1;       // posição dentro de cada gomo 0..1
        let r = R;
        if (forma === 'ondas') r = R + A * Math.sin(n * t);
        else if (forma === 'nuvem') r = R + A * Math.abs(Math.sin(n * t / 2)) * 1.3 - A * .4;
        else if (forma === 'dentes') r = R - A + 2 * A * (u < .5 ? u * 2 : 2 - u * 2);
        else if (forma === 'serra') r = R - A + 2 * A * u;
        else if (forma === 'petalas') r = R - A + 2 * A * Math.pow(Math.abs(Math.sin(n * t / 2)), .55);
        else if (forma === 'espinhos') r = R - A * .3 + (u > .42 && u < .58 ? A * 1.8 * (1 - Math.abs(u - .5) / .08) : 0);
        else if (forma === 'gotas') r = R + A * Math.pow(Math.max(0, Math.sin(n * t)), 3) * 1.4;
        else if (forma === 'pingos') r = R + (u < .5 ? 0 : A * 1.6 * Math.sin((u - .5) * 2 * Math.PI) * (n % 2 ? 1 : 1)) * (Math.sin(n * t / 2) > 0 ? 1 : .35);
        else if (forma === 'liso') r = R;
        d += `${i ? 'L' : 'M'}${f1(100 + r * Math.cos(t))} ${f1(100 + r * Math.sin(t))}`;
    }
    d += 'Z';
    const furo = `M${100 - ri} 100A${ri} ${ri} 0 1 0 ${100 + ri} 100A${ri} ${ri} 0 1 0 ${100 - ri} 100Z`;
    const cor = o.cor || '#fff', c2 = o.cor2;
    const grad = c2 ? `<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='${cor}'/><stop offset='1' stop-color='${c2}'/></linearGradient></defs>` : '';
    const ln = o.linha ? ` stroke='${o.linha}' stroke-width='${o.lw || 2.4}' stroke-linejoin='round'` : '';
    let extra = '';
    if (o.pontos) for (let k = 0; k < n; k++) { const t = (k / n) * 2 * Math.PI + (forma === 'dentes' ? Math.PI / n : 0); extra += `<circle cx='${f1(100 + (ri + (R - ri) * .52) * Math.cos(t))}' cy='${f1(100 + (ri + (R - ri) * .52) * Math.sin(t))}' r='${o.pr || 2.2}' fill='${o.pontos}'/>`; }
    return `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'>${grad}<path fill-rule='evenodd' d='${d}${furo}' fill='${c2 ? 'url(#g)' : cor}'${ln}/>${extra}</svg>`;
}

/** Ladrilho de padrão (para placa e faixa): devolve { svg, w, h } com w x h em px do ladrilho. */
function ladrilho(o) {
    const k = o.tipo, c1 = o.c1 || '#fff', c2 = o.c2 || 'transparent', t = o.tam || 16, a = o.alfa === undefined ? 1 : o.alfa;
    let w = t, h = t, inner = '';
    if (k === 'listras') {          // listras diagonais
        inner = `<path d='M-${t} ${t}L${t} -${t}L${t * 2} 0L0 ${t * 2}ZM0 ${t}' fill='${c1}'/><path d='M-2 ${t + 2}L${t + 2} -2' stroke='${c1}' stroke-width='${t / 2}'/>`;
        inner = `<rect width='${t}' height='${t}' fill='${c2}'/><path d='M${-t / 4} ${t * 1.25}L${t * 1.25} ${-t / 4}' stroke='${c1}' stroke-width='${t / 2}'/><path d='M${t * .75} ${t * 1.25}L${t * 2.25} ${-t / 4}M${-t * 1.25} ${t * 1.25}L${t / 4} ${-t / 4}' stroke='${c1}' stroke-width='${t / 2}'/>`;
    } else if (k === 'xadrez') { w = h = t * 2; inner = `<rect width='${w}' height='${h}' fill='${c2}'/><rect width='${t}' height='${t}' fill='${c1}'/><rect x='${t}' y='${t}' width='${t}' height='${t}' fill='${c1}'/>`; }
    else if (k === 'bolinhas') { w = h = t * 2; inner = `<rect width='${w}' height='${h}' fill='${c2}'/><circle cx='${t / 2}' cy='${t / 2}' r='${t * (o.r || .28)}' fill='${c1}'/><circle cx='${t * 1.5}' cy='${t * 1.5}' r='${t * (o.r || .28)}' fill='${c1}'/>`; }
    else if (k === 'zigzag') { w = t * 2; h = t; inner = `<rect width='${w}' height='${h}' fill='${c2}'/><path d='M0 ${h * .75}L${t} ${h * .25}L${w} ${h * .75}' fill='none' stroke='${c1}' stroke-width='${t * .22}' stroke-linejoin='round'/>`; }
    else if (k === 'ondas') { w = t * 2; h = t; inner = `<rect width='${w}' height='${h}' fill='${c2}'/><path d='M0 ${h / 2}Q${t / 2} 0 ${t} ${h / 2}T${w} ${h / 2}' fill='none' stroke='${c1}' stroke-width='${t * .18}'/>`; }
    else if (k === 'grade') { inner = `<rect width='${t}' height='${t}' fill='${c2}'/><path d='M0 0H${t}M0 0V${t}' stroke='${c1}' stroke-width='${o.lw || 1}'/>`; }
    else if (k === 'losangos') { inner = `<rect width='${t}' height='${t}' fill='${c2}'/><path d='M${t / 2} 0L${t} ${t / 2}L${t / 2} ${t}L0 ${t / 2}Z' fill='${c1}'/>`; }
    else if (k === 'riscos') { inner = `<rect width='${t}' height='${t}' fill='${c2}'/><path d='M0 ${t}L${t} 0' stroke='${c1}' stroke-width='${o.lw || 1.4}'/>`; }
    else if (k === 'riscado') { w = h = t * 2; inner = `<rect width='${w}' height='${h}' fill='${c2}'/><path d='M0 ${h}L${w} 0M-${t} ${t}L${t} -${t}M${t} ${h + t}L${w + t} ${t}' stroke='${c1}' stroke-width='${o.lw || 1.2}'/>`; }
    else if (k === 'horizontais') { inner = `<rect width='${t}' height='${t}' fill='${c2}'/><rect y='${t * .6}' width='${t}' height='${t * .4}' fill='${c1}'/>`; }
    else if (k === 'verticais') { inner = `<rect width='${t}' height='${t}' fill='${c2}'/><rect width='${t * .5}' height='${t}' fill='${c1}'/>`; }
    else if (k === 'favo') {         // favo de mel / hexágonos (lados de comprimento t)
        const R = t, W = Math.sqrt(3) * R, H = 3 * R;
        const hex = (cx, cy) => { let d = ''; for (let i = 0; i < 6; i++) { const a = (-90 + i * 60) * Math.PI / 180; d += `${i ? 'L' : 'M'}${f1(cx + R * Math.cos(a))} ${f1(cy + R * Math.sin(a))}`; } return `<path d='${d}Z'/>`; };
        w = f2(W); h = H;
        inner = `<rect width='${w}' height='${h}' fill='${c2}'/><g fill='none' stroke='${c1}' stroke-width='${o.lw || 1}'>${hex(0, 0)}${hex(W, 0)}${hex(W / 2, 1.5 * R)}${hex(0, H)}${hex(W, H)}</g>`;
    }
    else if (k === 'icones') {        // ícones espalhados em xadrez
        const S = simbolos();
        const nomes = o.icones, pals = o.pals || [{}], ti = o.ti || t * .6;
        w = h = t * 2;
        let us = '';
        us += S.usar(nomes[0], pals[0], t * .5, t * .5, ti, o.rot || 0);
        us += S.usar(nomes[nomes.length > 1 ? 1 : 0], pals[pals.length > 1 ? 1 : 0], t * 1.5, t * 1.5, ti, -(o.rot || 0));
        if (o.denso) { us += S.usar(nomes[nomes.length > 2 ? 2 : 0], pals[0], t * 1.5, t * .5, ti * .7); us += S.usar(nomes[nomes.length > 3 ? 3 : 0], pals[0], t * .5, t * 1.5, ti * .7); }
        inner = `<rect width='${w}' height='${h}' fill='${c2}'/>${S.defs}${us}`;
    }
    return { svg: `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 ${w} ${h}' width='${w}' height='${h}'${a < 1 ? ` opacity='${a}'` : ''}>${inner}</svg>`, w, h };
}

// ---------------------------------------------------------------------------------------------
// CAMADAS DE CENÁRIO (faixas): cada uma devolve um fragmento SVG no quadro 340 x 112 (VW x VH). Quem compõe põe dentro de um <svg viewBox='0 0 340 112'>.
// As que se repetem horizontalmente são desenhadas com período 340 (as bordas se encontram), então rolam sem emenda.
// ---------------------------------------------------------------------------------------------
const VW = 340, VH = 112;
const cena = {
    /** linha de terreno ondulada (colinas, dunas, ondas) preenchida até o fundo */
    terreno({ cor, y = 78, amp = 10, n = 2, fase = 0, borda, seed = 'terreno' }) {
        let d = '';
        for (let x = 0; x <= VW; x += 5) d += `${x ? 'L' : 'M'}${x} ${f1(y + amp * Math.sin((x / VW) * n * 2 * Math.PI + fase) + amp * .4 * Math.sin((x / VW) * (n * 2 + 1) * 2 * Math.PI + fase * 2))}`;
        return `<path d='${d}L${VW} ${VH}L0 ${VH}Z' fill='${cor}'${borda ? ` stroke='${borda}' stroke-width='1.5'` : ''}/>`;
    },
    /** prédios em silhueta, com janelas acesas opcionais */
    skyline({ cor, y = 112, seed = 'sky', altMin = 22, altMax = 62, larg = [14, 30], janelas, antenas }) {
        const R = rng(seed);
        let x = 0, s = '', j = '';
        while (x < VW) {
            const w = Math.min(VW - x, larg[0] + R() * (larg[1] - larg[0])), h = altMin + R() * (altMax - altMin);
            s += `<rect x='${f1(x)}' y='${f1(y - h)}' width='${f1(w + .5)}' height='${f1(h)}' fill='${cor}'/>`;
            if (antenas && R() < .3) s += `<rect x='${f1(x + w / 2 - .6)}' y='${f1(y - h - 10)}' width='1.2' height='10' fill='${cor}'/>`;
            if (janelas) for (let yy = y - h + 5; yy < y - 4; yy += 7) for (let xx = x + 3; xx < x + w - 3; xx += 5) if (R() < (janelas.dens || .35)) j += `<rect x='${f1(xx)}' y='${f1(yy)}' width='2.4' height='3.2' fill='${janelas.cor}' opacity='${f2(.55 + R() * .45)}'/>`;
            x += w + (R() < .5 ? 0 : 2);
        }
        return s + j;
    },
    /** pinheiros / árvores triangulares */
    pinheiros({ cor, y = 112, seed = 'pin', n = 14, altMin = 20, altMax = 46 }) {
        const R = rng(seed);
        let s = '';
        for (let k = 0; k < n; k++) { const x = (k + .5) * VW / n + (R() - .5) * 8, h = altMin + R() * (altMax - altMin), w = h * .5; s += `<path d='M${f1(x)} ${f1(y - h)}L${f1(x + w / 2)} ${f1(y - h * .5)}L${f1(x + w * .28)} ${f1(y - h * .5)}L${f1(x + w * .6)} ${f1(y - h * .12)}L${f1(x - w * .6)} ${f1(y - h * .12)}L${f1(x - w * .28)} ${f1(y - h * .5)}L${f1(x - w / 2)} ${f1(y - h * .5)}Z' fill='${cor}'/>`; }
        return s;
    },
    /** nuvens (círculos fundidos) com período 340 */
    nuvens({ cor, n = 3, y = [10, 40], seed = 'nuv', tam = [16, 26], alfa = 1 }) {
        const R = rng(seed);
        let s = '';
        for (let k = 0; k < n; k++) { const cx = (k + R() * .6) * VW / n, cy = y[0] + R() * (y[1] - y[0]), r = tam[0] + R() * (tam[1] - tam[0]); s += `<g fill='${cor}' opacity='${alfa}'><circle cx='${f1(cx)}' cy='${f1(cy)}' r='${f1(r)}'/><circle cx='${f1(cx + r * .9)}' cy='${f1(cy + r * .15)}' r='${f1(r * .75)}'/><circle cx='${f1(cx - r * .9)}' cy='${f1(cy + r * .2)}' r='${f1(r * .7)}'/><rect x='${f1(cx - r * 1.5)}' y='${f1(cy + r * .2)}' width='${f1(r * 3)}' height='${f1(r * .7)}' rx='${f1(r * .35)}'/></g>`; }
        return s;
    },
    /** estrelas (pontinhos de 1 a 3 px) */
    estrelas({ cor = '#fff', n = 40, seed = 'est', y = [0, 100], r = [.5, 1.6], alfa = [.4, 1] }) {
        const R = rng(seed);
        let s = '';
        for (let k = 0; k < n; k++) s += `<circle cx='${f1(R() * VW)}' cy='${f1(y[0] + R() * (y[1] - y[0]))}' r='${f2(r[0] + R() * (r[1] - r[0]))}' fill='${cor}' opacity='${f2(alfa[0] + R() * (alfa[1] - alfa[0]))}'/>`;
        return s;
    },
    /** ícones espalhados (ou em fileira) */
    icones({ nomes, pals = [{}], n = 8, tam = [10, 18], seed = 'ico', y = [8, 100], fileira, rot = 12, alfa = 1 }) {
        const R = rng(seed), S = simbolos();
        let s = '';
        for (let k = 0; k < n; k++) {
            const t = tam[0] + R() * (tam[1] - tam[0]);
            const x = fileira ? (k + .5) * VW / n : R() * VW, yy = fileira ? (fileira === true ? (y[0] + y[1]) / 2 : fileira) + (R() - .5) * 6 : y[0] + R() * (y[1] - y[0]);
            s += S.usar(nomes[k % nomes.length], pals[k % pals.length], x, yy, t, (R() - .5) * 2 * rot, alfa < 1 ? ` opacity='${alfa}'` : '');
        }
        return S.defs + s;
    },
    /** picos de montanha (com neve opcional) */
    montanhas({ cor, y = 112, n = 5, altMin = 30, altMax = 70, neve, seed = 'mon', cor2 }) {
        const R = rng(seed);
        let s = '';
        for (let k = 0; k < n; k++) {
            const cx = (k + .5) * VW / n + (R() - .5) * 20, h = altMin + R() * (altMax - altMin), w = h * 1.25;
            s += `<path d='M${f1(cx - w)} ${y}L${f1(cx)} ${f1(y - h)}L${f1(cx + w)} ${y}Z' fill='${cor}'/>`;
            if (cor2) s += `<path d='M${f1(cx)} ${f1(y - h)}L${f1(cx + w)} ${y}L${f1(cx + w * .15)} ${y}Z' fill='${cor2}' opacity='.5'/>`;
            if (neve) s += `<path d='M${f1(cx)} ${f1(y - h)}L${f1(cx - w * .22)} ${f1(y - h * .72)}L${f1(cx - w * .08)} ${f1(y - h * .78)}L${f1(cx + w * .02)} ${f1(y - h * .68)}L${f1(cx + w * .12)} ${f1(y - h * .78)}L${f1(cx + w * .22)} ${f1(y - h * .72)}Z' fill='${neve}'/>`;
        }
        return s;
    },
    /** pirâmides */
    piramides({ cor, cor2, y = 112, n = 3, seed = 'pir', tam = [30, 56] }) {
        const R = rng(seed);
        let s = '';
        for (let k = 0; k < n; k++) { const cx = (k + .5) * VW / n + (R() - .5) * 24, h = tam[0] + R() * (tam[1] - tam[0]), w = h * 1.1; s += `<path d='M${f1(cx - w)} ${y}L${f1(cx)} ${f1(y - h)}L${f1(cx + w)} ${y}Z' fill='${cor}'/><path d='M${f1(cx)} ${f1(y - h)}L${f1(cx + w)} ${y}L${f1(cx)} ${y}Z' fill='${cor2 || escuro(cor, .25)}'/>`; }
        return s;
    },
    /** cristais/estalagmites pontudos subindo do chão */
    cristais({ cor, cor2, y = 112, n = 9, seed = 'cri', alt = [18, 52], larg = [8, 16] }) {
        const R = rng(seed);
        let s = '';
        for (let k = 0; k < n; k++) { const cx = (k + .5) * VW / n + (R() - .5) * 14, h = alt[0] + R() * (alt[1] - alt[0]), w = larg[0] + R() * (larg[1] - larg[0]); s += `<path d='M${f1(cx - w / 2)} ${y}L${f1(cx - w * .3)} ${f1(y - h * .8)}L${f1(cx)} ${f1(y - h)}L${f1(cx + w * .3)} ${f1(y - h * .8)}L${f1(cx + w / 2)} ${y}Z' fill='${cor}'/><path d='M${f1(cx)} ${f1(y - h)}L${f1(cx + w * .3)} ${f1(y - h * .8)}L${f1(cx + w / 2)} ${y}L${f1(cx)} ${y}Z' fill='${cor2 || escuro(cor, .3)}' opacity='.7'/>`; }
        return s;
    },
    /** canos e tubulações (horizontais e verticais, com juntas) */
    canos({ cor, cor2, seed = 'can', n = 5, esp = [5, 9] }) {
        const R = rng(seed);
        let s = '';
        for (let k = 0; k < n; k++) {
            const x = R() * VW, y = 10 + R() * 90, w = esp[0] + R() * (esp[1] - esp[0]);
            s += R() < .5 ? `<rect x='${f1(x - 30)}' y='${f1(y)}' width='${f1(60 + R() * 90)}' height='${f1(w)}' rx='${f1(w / 2)}' fill='${cor}'/><rect x='${f1(x - 30)}' y='${f1(y + 1)}' width='${f1(40)}' height='1.6' fill='${cor2}' opacity='.8'/>` : `<rect x='${f1(x)}' y='${f1(y - 40)}' width='${f1(w)}' height='${f1(50 + R() * 70)}' rx='${f1(w / 2)}' fill='${cor}'/>`;
            s += `<circle cx='${f1(x)}' cy='${f1(y + w / 2)}' r='${f1(w * .8)}' fill='${cor2}'/>`;
        }
        return s;
    },
    /** estandartes/bandeirolas pendurados em cima */
    bandeiras({ cor, cor2, n = 5, seed = 'ban', alt = [26, 44] }) {
        const R = rng(seed);
        let s = `<path d='M0 4H${VW}' stroke='${cor2 || '#333'}' stroke-width='2'/>`;
        for (let k = 0; k < n; k++) { const x = (k + .5) * VW / n, h = alt[0] + R() * (alt[1] - alt[0]), w = 16; s += `<path d='M${f1(x - w / 2)} 4H${f1(x + w / 2)}V${f1(h)}L${f1(x)} ${f1(h - 8)}L${f1(x - w / 2)} ${f1(h)}Z' fill='${cor}'/>`; }
        return s;
    },
    /** listras de cortina/faixa vertical */
    cortina({ cores, larg = 20 }) { let s = ''; for (let x = 0, k = 0; x < VW; x += larg, k++) s += `<rect x='${x}' width='${larg}' height='${VH}' fill='${cores[k % cores.length]}'/>`; return s; },
    /** grade em perspectiva (synthwave) */
    perspectiva({ cor, y = 70, n = 14 }) {
        let s = `<g stroke='${cor}' stroke-width='1' fill='none' opacity='.85'>`;
        for (let k = -n; k <= n; k++) s += `<path d='M${VW / 2 + k * 6} ${y}L${VW / 2 + k * 40} ${VH}'/>`;
        for (let k = 0; k < 6; k++) { const yy = y + Math.pow(k / 5, 1.7) * (VH - y); s += `<path d='M0 ${f1(yy)}H${VW}'/>`; }
        return s + '</g>';
    },
    /** sol (disco) com listras horizontais opcionais */
    sol({ x = 170, y = 60, r = 28, c1, c2, listras = 0 }) {
        const id = 'sg' + Math.round(x + y);
        let s = `<defs><linearGradient id='${id}' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='${c1}'/><stop offset='1' stop-color='${c2 || c1}'/></linearGradient><clipPath id='c${id}'><circle cx='${x}' cy='${y}' r='${r}'/></clipPath></defs><circle cx='${x}' cy='${y}' r='${r}' fill='url(#${id})'/>`;
        if (listras) { s += `<g clip-path='url(#c${id})' fill='#000' opacity='.0'/>`; }
        return s;
    },
};

module.exports = { simbolos, anelDeIcones, anelDeForma, ladrilho, cena, VW, VH };
