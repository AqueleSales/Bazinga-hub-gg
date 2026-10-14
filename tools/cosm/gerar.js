'use strict';
/* Gerador dos temas de cosméticos (Rodada 27).
 *   node tools/cosm/gerar.js            escreve app/static/css/cosm_<cat>.css, app/static/js/cosm_<cat>.js e app/cosm_gen.json
 *   node tools/cosm/gerar.js --check    não escreve: sai com 1 se algum arquivo gerado estiver desatualizado (usado pelos testes)
 * Os temas moram em tools/cosm/temas/*.js (cada arquivo exporta uma lista de `tema({...})`). Nada aqui roda no navegador: o app só recebe CSS/JS prontos. */
const fs = require('fs');
const path = require('path');
const B = require('./base');

const RAIZ = path.resolve(__dirname, '..', '..');
const ESTATICO = path.join(RAIZ, 'app', 'static');
const { CATEGORIAS } = require('./dsl');

function carregarTemas() {
    const dir = path.join(__dirname, 'temas');
    const lista = [];
    for (const f of fs.readdirSync(dir).filter((x) => x.endsWith('.js') && !x.startsWith('_')).sort()) {
        const mod = require(path.join(dir, f));
        for (const t of mod) lista.push(t);
    }
    return lista;
}

function gerar() {
    const temas = carregarTemas();
    const saidaCss = {}, saidaJs = {}, catalogo = { temas: [], itens: [] };
    const usados = new Set(), idsTema = new Set();
    for (const cat of CATEGORIAS) saidaCss[cat] = { vars: {}, regras: [] }, saidaJs[cat] = { avatar: {}, perfil: {}, ids: {}, sons: {} };

    for (const t of temas) {
        if (idsTema.has(t.id)) throw new Error('tema repetido: ' + t.id);
        idsTema.add(t.id);
        const css = saidaCss[t.cat], reg = saidaJs[t.cat];
        const jaNoTema = {};
        catalogo.temas.push({ id: t.id, nome: t.nome, categoria: t.cat, cor: t.cor, cores: t.cores, icone: t.icone, lema: t.lema, desc: t.desc,
            premium: !!t.premium, sem_pacote: !!t.sem_pacote, sem_hero: t.sem_hero !== false, existente: !!t.existente });
        t.itens.forEach((it) => {
            const id = it.id || `${t.pre}_${B.slug(it.nome)}`.slice(0, 24).replace(/_+$/, "");
            if (!B.idOk(id)) throw new Error(`tema ${t.id}: item "${it.nome}" gera id inválido "${id}" (passe { id: '...' })`);
            const chave = `${it.tipo}:${id}`;
            if (usados.has(chave)) throw new Error(`id repetido: ${chave} (tema ${t.id})`);
            usados.add(chave);
            const ctx = { tema: t, id, vars: css.vars };
            let r;
            try { r = it.gerar(ctx); } catch (e) { throw new Error(`tema ${t.id}, item ${chave}: ${e.stack || e.message}`); }
            if (it.extra) r.css = (r.css || '') + it.extra.replace(/\$ID/g, id);
            if (r.css) css.regras.push(`/* ${t.id}: ${chave} */` + B.minCss(r.css));
            const rg = r.reg || {};
            if (rg.avatar) reg.avatar[id] = rg.avatar;
            if (rg.perfil) reg.perfil[id] = rg.perfil;
            for (const k of ['fala', 'radar', 'chat', 'som', 'pin', 'servidor']) if (rg[k]) (reg.ids[k] = reg.ids[k] || []).push(rg[k]);
            if (rg.receita) reg.sons[id] = rg.receita;
            catalogo.itens.push({ tipo: it.tipo, id, nome: it.nome, desc: it.desc, tema: t.id, raridade: it.raridade, animado: it.animado !== false });
        });
    }

    const arquivos = {};
    const usadas = [];
    for (const cat of CATEGORIAS) {
        const c = saidaCss[cat], j = saidaJs[cat];
        if (!c.regras.length) continue;
        usadas.push(cat);
        const vars = Object.entries(c.vars).map(([k, v]) => `${k}:${v}`).join(';');
        arquivos[path.join(ESTATICO, 'css', `cosm_${cat}.css`)] = `/* GERADO por tools/cosm/gerar.js (categoria ${cat}). NÃO edite: mude o tema em tools/cosm/temas/ e rode o gerador. */\n:root{${vars}}\n${c.regras.join('\n')}\n`;
        const fn = (m) => `{${Object.entries(m).map(([id, h]) => `'${id}':()=>${JSON.stringify(h)}`).join(',')}}`;
        const ids = `{${Object.entries(j.ids).map(([k, v]) => `${k}:[${v.map((x) => `'${x}'`).join(',')}]`).join(',')}}`;
        const lista = { avatar: Object.keys(j.avatar), perfil: Object.keys(j.perfil), ...j.ids, som_receita: Object.keys(j.sons) };
        arquivos[path.join(ESTATICO, 'js', `cosm_${cat}.js`)] = `/* GERADO por tools/cosm/gerar.js (categoria ${cat}). NÃO edite. */\n/*IDS ${JSON.stringify(lista)} */\n(function(){if(typeof Cosm==='undefined')return;Cosm.registrarTema({avatar:${fn(j.avatar)},perfil:${fn(j.perfil)},ids:${ids},sons:${JSON.stringify(j.sons)}});})();\n`;
    }
    catalogo.arquivos = usadas;
    arquivos[path.join(RAIZ, 'app', 'cosm_gen.json')] = JSON.stringify(catalogo, null, 1) + '\n';
    return { arquivos, catalogo };
}

if (require.main === module) {
    const { arquivos, catalogo } = gerar();
    const checar = process.argv.includes('--check');
    let desatualizado = 0;
    for (const [arq, conteudo] of Object.entries(arquivos)) {
        const atual = fs.existsSync(arq) ? fs.readFileSync(arq, 'utf8') : null;
        if (atual === conteudo) continue;
        if (checar) { console.error('DESATUALIZADO:', path.relative(RAIZ, arq)); desatualizado++; }
        else fs.writeFileSync(arq, conteudo);
    }
    // arquivos cosm_<cat> de categorias que ficaram vazias são apagados
    if (!checar) for (const d of ['css', 'js']) for (const f of fs.readdirSync(path.join(ESTATICO, d))) {
        const m = /^cosm_([a-z]+)\.(css|js)$/.exec(f);
        if (m && CATEGORIAS.includes(m[1]) && !catalogo.arquivos.includes(m[1])) fs.unlinkSync(path.join(ESTATICO, d, f));
    }
    if (checar) process.exit(desatualizado ? 1 : 0);
    const porTipo = {};
    catalogo.itens.forEach((i) => { porTipo[i.tipo] = (porTipo[i.tipo] || 0) + 1; });
    console.log(`ok: ${catalogo.temas.length} temas, ${catalogo.itens.length} itens`, JSON.stringify(porTipo));
}

module.exports = { gerar };
