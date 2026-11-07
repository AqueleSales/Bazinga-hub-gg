'use strict';
/* Arte dos temas de personagem (Rodada 40). Duas fontes, nesta ordem:
   1) um ARQUIVO em app/static/img/cosm/<tema>/<nome>.png, se existir (hoje só a Lança de Longinus e os ゴゴゴ, que o dono quis como imagem de verdade: tools/cosm/recorte.py);
   2) o SVG desenhado por código em arte.js (símbolos e objetos; o dono mandou tirar os personagens). Sem o arquivo, a lança e o ゴゴゴ caem no desenho de reserva de arte.js.
   API: R.url / R.css / R.proporcao / R.dim / R.existe. O gerador (gerar.js) troca cada data-URI repetido por `var(--img-<tema>-<nome>)` (R.todas só lista os SVG; arquivo fica como caminho). */
const fs = require('fs');
const path = require('path');
const B = require('./base');
const A = require('./arte');

const PASTA = path.join(__dirname, '..', '..', 'app', 'static', 'img', 'cosm');
const cache = {};

function arquivo(tema, nome) {
    const p = path.join(PASTA, tema, `${nome}.png`);
    if (!fs.existsSync(p)) return null;
    const b = fs.readFileSync(p);
    if (b.length < 24 || b.toString('latin1', 1, 4) !== 'PNG') return null;
    return { url: `/static/img/cosm/${tema}/${nome}.png`, w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function item(tema, nome) {
    const k = `${tema}/${nome}`;
    if (cache[k]) return cache[k];
    const arq = arquivo(tema, nome);
    if (arq) return (cache[k] = { ...arq, arquivo: true });
    const r = A.REG[k];
    if (!r) throw new Error(`arte faltando: ${k} (desenhe em tools/cosm/arte.js)`);
    return (cache[k] = { url: B.uri(r.svg).slice(5, -2).replace(/'/g, '%27').replace(/"/g, '%22'), w: r.w, h: r.h, arquivo: false });
}
const url = (tema, nome) => item(tema, nome).url;
/** o arquivo vai como url("/static/...") e o SVG como data-URI seguro pra aspas simples E duplas */
const css = (tema, nome) => `url("${url(tema, nome)}")`;
const existe = (tema, nome) => !!A.REG[`${tema}/${nome}`] || !!arquivo(tema, nome);
const dim = (tema, nome) => ({ w: item(tema, nome).w, h: item(tema, nome).h });
const proporcao = (tema, nome) => item(tema, nome).w / item(tema, nome).h;
/** as peças SVG registradas que NÃO viraram arquivo (o gerador procura as que o CSS usou) */
const todas = () => Object.values(A.REG).filter((r) => !arquivo(r.tema, r.nome)).map((r) => ({ tema: r.tema, nome: r.nome, url: url(r.tema, r.nome), variavel: `--img-${r.tema}-${r.nome}`.replace(/_/g, '-') }));

module.exports = { url, css, dim, existe, proporcao, todas };
