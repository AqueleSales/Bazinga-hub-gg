'use strict';
// Ferramenta de olho: gera uma folha HTML compacta com os ícones. Uso: node tools/cosm/folha_icones.js <saída.html> [inicio] [fim]
const fs = require('fs');
const { ICONES, iconeSvg } = require('./icones');
const nomes = Object.keys(ICONES).slice(Number(process.argv[3] || 0), Number(process.argv[4] || 999));
let h = '<!doctype html><meta charset=utf-8><body style="background:#2a2d36;color:#ccc;font:9px sans-serif;margin:4px"><div style="display:flex;flex-wrap:wrap;gap:4px">';
for (const nome of nomes) h += `<div style="width:90px;text-align:center;background:#353945;padding:2px;border-radius:5px"><span style="display:block;width:76px;height:76px;margin:0 auto">${iconeSvg(nome, { m: '#ffb86b' }, "width='76' height='76'")}</span>${nome}</div>`;
fs.writeFileSync(process.argv[2], h + '</div>');
