'use strict';
/* Utilidades do gerador de temas (Rodada 27). Tudo aqui roda no Node, em tempo de geração: o navegador só recebe CSS/JS prontos. */

const f1 = (n) => Math.round(n * 10) / 10;
const f2 = (n) => Math.round(n * 100) / 100;

// ---- cores ----
function rgb(hex) {
    let h = String(hex).replace('#', '');
    if (h.length === 3) h = h.split('').map((c) => c + c).join('');
    const n = parseInt(h.slice(0, 6), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
const hex = ([r, g, b]) => '#' + [r, g, b].map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('');
const mix = (a, b, t) => { const A = rgb(a), B = rgb(b); return hex(A.map((v, i) => v + (B[i] - v) * t)); };
const claro = (c, t = .3) => mix(c, '#ffffff', t);
const escuro = (c, t = .3) => mix(c, '#000000', t);
const alfa = (c, a) => { const [r, g, b] = rgb(c); return `rgba(${r},${g},${b},${f2(a)})`; };

// ---- sorteio com semente (a saída precisa ser a mesma a cada geração) ----
function rng(semente) {
    let s = 0;
    for (const ch of String(semente)) s = (s * 31 + ch.charCodeAt(0)) >>> 0;
    s = s || 1;
    return () => { s |= 0; s = (s + 0x6D2B79F5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

// ---- SVG como imagem de fundo (data-URI mínima) ----
/** confere o SVG antes de virar imagem: atributo repetido ou aspa aberta deixa a imagem INTEIRA em branco (o navegador recusa o XML) */
function validarSvg(svg) {
    for (const t of String(svg).match(/<[^<>]+>/g) || []) {
        const sem = t.replace(/\"/g, "'");
        if ((sem.match(/'/g) || []).length % 2) throw new Error('SVG com aspa aberta: ' + t.slice(0, 120));
        const attrs = [...sem.replace(/'[^']*'/g, "''").matchAll(/\s([a-zA-Z:-]+)=/g)].map((m) => m[1]);
        const rep = attrs.filter((a, i) => attrs.indexOf(a) !== i);
        if (rep.length) throw new Error('SVG com atributo repetido (' + rep.join(',') + '): ' + t.slice(0, 120));
    }
    return svg;
}
const uri = (svg) => 'url("data:image/svg+xml,' + String(validarSvg(svg)).replace(/[\r\n\t]+/g, ' ').replace(/\s{2,}/g, ' ').replace(/"/g, "'").replace(/%/g, '%25').replace(/#/g, '%23').replace(/</g, '%3C').replace(/>/g, '%3E') + '")';
const svg = (vb, inner, extra = '') => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='${vb}'${extra ? ' ' + extra : ''}>${inner}</svg>`;

// ---- ids ----
const slug = (s) => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z]+/g, '_').replace(/^_+|_+$/g, '');
const idOk = (s) => /^[a-z_]{1,24}$/.test(s);

// ---- CSS ----
const minCss = (s) => String(s).replace(/\/\*[\s\S]*?\*\//g, '').replace(/\s*\n\s*/g, ' ').replace(/\s{2,}/g, ' ').trim();

module.exports = { f1, f2, rgb, hex, mix, claro, escuro, alfa, rng, uri, svg, slug, idOk, minCss };
