'use strict';
/* FÁBRICA DE TEMAS GENÉRICOS (fofos, emo, assustadores, do dia a dia, sazonais): um tema inteiro a partir de uma configuração curta.
   Cada slot tem um padrão sensato (anel de ícones, nome em degradê, placa com padrão, faixa de sprites, efeitos que usam os ícones do tema) e pode ser
   refinado campo a campo ou trocado por um item feito à mão (`itens` extras). Arquivos que começam com "_" não são temas: o gerador pula. */
const { tema, M, N, Pl, F, EA, EP, FALA, RADAR, CHAT, PIN, SERV, SOM, P, I, B, fase } = require('../dsl');
const { cena } = P;

const solido = (c) => ({ m: c, a: c, d: c, l: c, o: c, w: 0 });
const f1 = (n) => Math.round(n * 10) / 10;

/** configuração:
 *  id, pre, nome, cat, cor, cores, icone, lema, desc, premium
 *  pal: paleta dos ícones {m,a,d,l,o}; icones: [...]; pals: [...] (alternadas)
 *  fundo: [c1, c2, (c3)] (fundo da faixa e do cartão); texto: cor do texto em placa clara
 *  m: {nome, desc, ...}  anel        n: {nome, desc, grad, fonte, ...}  nome       p: {nome, desc, base, pad, ...}  placa
 *  f: {nome, desc, fixo, longe, perto, fundo}  faixa      ea: {nome, desc, camadas, sobre}  avatar      ep: {nome, desc, camadas}  perfil
 *  extra: [item...]  r: { v: raridade dos visuais, e: dos efeitos, p: do perfil } */
function G(c) {
    const pal = c.pal, pals = c.pals || [pal], ic = c.icones, r = { v: 'raro', e: 'raro', p: 'epico', ...(c.r || {}) };
    const suave = (cor) => ({ m: cor, a: cor, d: cor, l: cor, o: cor, w: -2 });
    const mn = c.m || {}, nn = c.n || {}, pp = c.p || {}, ff = c.f || {}, ee = c.ea || {}, pe = c.ep || {};
    const cores = c.cores;
    const itens = [];

    // ---- moldura ----
    itens.push(M(mn.nome || 'Anel', mn.desc || 'Os enfeites do tema em volta da foto, girando devagar.', { t: 'icones', icones: mn.icones || ic, pals: mn.pals || pals, n: 10, tam: 26, giro: 56, ...mn, nome: undefined, desc: undefined }, { r: r.v, id: mn.id }));
    // ---- nome ----
    const iconeNome = nn.icone === true ? { nome: ic[0], pos: 'depois', pal: pal } : nn.icone;
    itens.push(N(nn.nome || 'Letras', nn.desc || 'Letras do tema, com um brilho que corre.', { grad: nn.grad || [cores[0], cores[1], cores[0]], mov: 'desliza', dur: 5, fonte: 'redonda', peso: 800, contorno: nn.contorno, cw: nn.cw || .6, ...nn, icone: iconeNome, nome: undefined, desc: undefined }, { r: r.v, id: nn.id }));
    // ---- placa ----
    const padPadrao = { tipo: 'icones', icones: ic.slice(0, 2), pals: [suave(pal.m), suave(pal.a || pal.m)], tam: 28, ti: 15, c2: 'transparent' };
    const { nome: _a, desc: _b, id: _c, pad: _d, icone: _e, pal: _f, ...restoPl } = pp;
    itens.push(Pl(pp.nome || 'Placa', pp.desc || 'O padrão do tema andando devagar atrás do seu nome.', {
        base: c.fundo || [cores[0], cores[1]], pad: pp.pad === false ? undefined : (pp.pad || padPadrao), mov: 'x', dur: 14, texto: c.texto,
        icone: pp.icone === false ? undefined : { nome: (typeof pp.icone === 'string' && pp.icone) || ic[0], pal: pp.pal || pal, lado: 'dir', tam: 64 }, ...restoPl,
    }, { r: r.v, id: pp.id }));
    // ---- faixa ----
    const longePadrao = { svg: cena.icones({ nomes: ic, pals, n: 8, tam: [14, 26], seed: c.id + 'f1', y: [8, 96], rot: 14 }), anim: 'pan', dur: 40 };
    const pertoPadrao = { svg: cena.icones({ nomes: ['brilho', 'estrelinha'], pals: [{ m: '#fff', o: '#fff', w: 0 }], n: 9, tam: [6, 11], seed: c.id + 'f2', y: [4, 106] }), anim: 'pisca', dur: 2.4 };
    itens.push(F(ff.nome || 'Cenário', ff.desc || 'O cenário do tema, com os enfeites passando devagar.', {
        fundo: ff.fundo || c.fundo || cores, fixo: ff.fixo, longe: ff.longe === false ? undefined : (ff.longe || longePadrao), perto: ff.perto === false ? undefined : (ff.perto || pertoPadrao),
    }, { r: r.v, id: ff.id }));
    // ---- efeito de avatar ----
    const camAv = ee.camadas || [{ k: 'aura', cor: cores[0], dur: 3 }, { k: 'orbita', icones: ic, pals, n: 6, tam: 22, giro: 26 }, { k: 'sobe', icones: ic, pals, n: 5, tam: 9, alt: 160 }];
    if (ee !== undefined && ee.nome !== false) itens.push(EA(ee.nome || 'Enfeites', ee.desc || 'Os enfeites do tema giram e sobem em volta da foto.', camAv, { r: r.e, id: ee.id, sobre: ee.sobre }));
    // ---- efeito de perfil ----
    const movEp = pe.mov || 'cai';
    const camPf = pe.camadas || [{ k: movEp, icones: ic, pals, n: 16, tam: [12, 24], vel: [6, 12], bal: 50, giro: 160 }, { k: 'pisca', icone: 'brilho', pals: [{ m: '#fff', o: cores[0], w: 2 }], n: 8, tam: [7, 12] }];
    if (pe.nome !== false) itens.push(EP(pe.nome || 'Chuva de Enfeites', pe.desc || 'Os enfeites do tema atravessam o cartão inteiro.', camPf, { r: r.p, id: pe.id }));
    (c.extra || []).forEach((x) => itens.push(x));
    return tema({ id: c.id, pre: c.pre, nome: c.nome, cat: c.cat, cor: c.cor, cores, icone: c.icone, lema: c.lema, desc: c.desc, premium: !!c.premium, pal, itens });
}

module.exports = { G, solido };
