/* Gráficos do Estúdio (/admin): SVG puro, sem biblioteca. Objeto global `Graficos`.
   Regras (guia de visualização de dados): UM eixo só; barra fina (<= 24 px) com ponta de cima arredondada (4 px) e base reta; linha de 2 px com
   ponto final de 8 px e anel da cor do fundo; área a 10%; grade de 1 px, discreta; rótulo só no extremo e no fim (nunca um número em cada ponto);
   texto sempre em cor de texto (a cor da série fica só na marca); dica ao passar o mouse OU ao focar com o teclado; e toda série tem a sua
   versão em TABELA (o botão "Ver como tabela"), que é o mesmo dado sem depender de cor nem de mouse.
   Nada vira HTML: os textos entram por textContent (nome de pessoa/servidor é dado de usuário).
   Uso: Graficos.montar(elemento, { tipo: 'colunas'|'linha'|'barrasH', titulo, serie: [{chave, rotulo, valor, ...}], tabela: { cabecalho: [...], linhas: [[...]] }, ... }) */
const Graficos = (() => {
    'use strict';
    const NS = 'http://www.w3.org/2000/svg';
    const fmt = (n) => Number(n || 0).toLocaleString('pt-BR');

    function svg(tag, attrs, pai, texto) {
        const e = document.createElementNS(NS, tag);
        for (const k in (attrs || {})) e.setAttribute(k, attrs[k]);
        if (texto != null) e.textContent = texto;
        if (pai) pai.appendChild(e);
        return e;
    }

    /** Escala "limpa": passo de 1, 2 ou 5 x 10^k, no máximo 5 divisões. */
    function escala(max) {
        if (!(max > 0)) return { topo: 4, passo: 1 };
        for (let e = 0; e < 12; e++) {
            for (const f of [1, 2, 5]) {
                const passo = f * Math.pow(10, e);
                if (Math.ceil(max / passo) <= 5) return { topo: Math.ceil(max / passo) * passo, passo };
            }
        }
        return { topo: max, passo: max };
    }

    // ---------------------------------------------------------------------
    // DICA (uma só, flutuante): valor em destaque, rótulo depois
    // ---------------------------------------------------------------------
    let dica = null;
    function dicaEl() {
        if (!dica) { dica = document.createElement('div'); dica.className = 'es-dica'; dica.setAttribute('role', 'tooltip'); document.body.appendChild(dica); }
        return dica;
    }
    function mostrarDica(linhas, x, y) {
        const d = dicaEl();
        d.replaceChildren();
        linhas.forEach((l) => { const r = document.createElement('div'); r.className = l.c || ''; r.textContent = l.t; d.appendChild(r); });
        d.style.display = 'block';
        const w = d.offsetWidth, h = d.offsetHeight;
        d.style.left = Math.max(8, Math.min(x - w / 2, innerWidth - w - 8)) + 'px';
        d.style.top = Math.max(8, y - h - 12) + 'px';
    }
    function esconderDica() { if (dica) dica.style.display = 'none'; }
    /** Posição na tela de um ponto do SVG (pra a dica aparecer em cima da marca, também quando é o teclado que focou). */
    function naTela(raiz, x, y) { const r = raiz.getBoundingClientRect(); return [r.left + x, r.top + y]; }

    // ---------------------------------------------------------------------
    // GRADE E EIXOS (comum às três formas)
    // ---------------------------------------------------------------------
    function eixoY(raiz, m, W, y, topo, passo) {
        for (let v = 0; v <= topo + 1e-9; v += passo) {
            const yy = y(v);
            svg('line', { x1: m.l, x2: W - m.r, y1: yy, y2: yy, class: 'es-g-grade' }, raiz);
            svg('text', { x: m.l - 8, y: yy + 4, 'text-anchor': 'end', class: 'es-g-eixo' }, raiz, fmt(v));
        }
    }
    function rotulosX(raiz, serie, xc, y, banda) {
        const salto = Math.max(1, Math.ceil(44 / Math.max(banda, 1)));
        serie.forEach((s, i) => {
            if ((serie.length - 1 - i) % salto !== 0) return;      // sempre inclui o último dia
            svg('text', { x: xc(i), y, 'text-anchor': 'middle', class: 'es-g-eixo' }, raiz, s.rotulo);
        });
    }
    function vazio(el, texto) {
        el.replaceChildren();
        const v = document.createElement('div');
        v.className = 'es-g-vazio';
        v.textContent = texto || 'Ainda sem dados nesse período.';
        el.appendChild(v);
    }
    const larguraDe = (el) => Math.max(300, Math.floor(el.clientWidth || 640));

    // ---------------------------------------------------------------------
    // COLUNAS (um valor por dia)
    // ---------------------------------------------------------------------
    function barraPath(x, w, yTopo, yBase, r) {
        const h = yBase - yTopo;
        r = Math.max(0, Math.min(r, h, w / 2));
        return `M${x},${yBase} V${yTopo + r} Q${x},${yTopo} ${x + r},${yTopo} H${x + w - r} Q${x + w},${yTopo} ${x + w},${yTopo + r} V${yBase} Z`;
    }

    function colunas(el, spec) {
        const serie = spec.serie || [];
        if (!serie.length) return vazio(el, spec.vazio);
        const W = larguraDe(el), H = 232, m = { t: 24, r: 10, b: 28, l: 40 };
        const pw = W - m.l - m.r, ph = H - m.t - m.b, n = serie.length;
        const max = Math.max(0, ...serie.map((s) => s.valor));
        const { topo, passo } = escala(max);
        const y = (v) => m.t + ph - (v / topo) * ph;
        const banda = pw / n, larg = Math.max(2, Math.min(24, banda - 2));
        const xc = (i) => m.l + banda * i + banda / 2;
        const raiz = svg('svg', { viewBox: `0 0 ${W} ${H}`, width: W, height: H, class: 'es-g-svg', role: 'img', 'aria-label': spec.titulo || 'Gráfico de colunas' });
        eixoY(raiz, m, W, y, topo, passo);
        rotulosX(raiz, serie, xc, H - 8, banda);
        const iMax = serie.reduce((a, s, i) => (s.valor > serie[a].valor ? i : a), 0), ult = n - 1;
        serie.forEach((s, i) => {
            const g = svg('g', { class: 'es-g-par' }, raiz);
            if (s.valor > 0) svg('path', { d: barraPath(xc(i) - larg / 2, larg, y(s.valor), y(0), 4), class: 'es-g-barra' }, g);
            // o alvo do mouse é a faixa inteira do dia (bem maior que a barra, que pode ter 0 de altura)
            const alvo = svg('rect', { x: m.l + banda * i, y: m.t, width: banda, height: ph + 6, class: 'es-g-alvo', tabindex: 0, role: 'img', 'aria-label': `${s.dica || s.rotulo}: ${fmt(s.valor)} ${spec.unidade || ''}` }, g);
            const abrir = () => { g.classList.add('ativo'); const [px, py] = naTela(raiz, xc(i), y(Math.max(s.valor, 0))); mostrarDica([{ t: `${fmt(s.valor)} ${spec.unidade || ''}`.trim(), c: 'valor' }, { t: s.dica || s.rotulo, c: 'rotulo' }], px, py); };
            const fechar = () => { g.classList.remove('ativo'); esconderDica(); };
            alvo.addEventListener('pointerenter', abrir); alvo.addEventListener('pointerleave', fechar);
            alvo.addEventListener('focus', abrir); alvo.addEventListener('blur', fechar);
        });
        // rótulo de valor só no pico e no último dia (e só se não esbarrarem)
        const rot = (i) => svg('text', { x: xc(i), y: y(serie[i].valor) - 6, 'text-anchor': 'middle', class: 'es-g-valor' }, raiz, fmt(serie[i].valor));
        if (serie[iMax].valor > 0) rot(iMax);
        if (ult !== iMax && serie[ult].valor > 0 && Math.abs(xc(ult) - xc(iMax)) >= 30) rot(ult);
        el.replaceChildren(raiz);
    }

    // ---------------------------------------------------------------------
    // LINHA (um valor por dia, com mira)
    // ---------------------------------------------------------------------
    function linha(el, spec) {
        const serie = spec.serie || [];
        if (!serie.length) return vazio(el, spec.vazio);
        const W = larguraDe(el), H = 232, m = { t: 24, r: 18, b: 28, l: 40 };
        const pw = W - m.l - m.r, ph = H - m.t - m.b, n = serie.length;
        const max = Math.max(0, ...serie.map((s) => s.valor));
        const { topo, passo } = escala(max);
        const y = (v) => m.t + ph - (v / topo) * ph;
        const passoX = n > 1 ? pw / (n - 1) : 0;
        const xc = (i) => (n > 1 ? m.l + passoX * i : m.l + pw / 2);
        const raiz = svg('svg', { viewBox: `0 0 ${W} ${H}`, width: W, height: H, class: 'es-g-svg', role: 'img', 'aria-label': spec.titulo || 'Gráfico de linha' });
        eixoY(raiz, m, W, y, topo, passo);
        rotulosX(raiz, serie, xc, H - 8, passoX);
        const pontos = serie.map((s, i) => `${xc(i).toFixed(1)},${y(s.valor).toFixed(1)}`);
        if (n > 1) {
            svg('path', { d: `M${xc(0).toFixed(1)},${y(0)} L${pontos.join(' L')} L${xc(n - 1).toFixed(1)},${y(0)} Z`, class: 'es-g-area' }, raiz);
            svg('path', { d: `M${pontos.join(' L')}`, class: 'es-g-linha', fill: 'none' }, raiz);
        }
        const mira = svg('line', { y1: m.t, y2: m.t + ph, class: 'es-g-mira', style: 'display:none' }, raiz);
        const ponto = svg('circle', { r: 4, class: 'es-g-ponto', style: 'display:none' }, raiz);
        svg('circle', { cx: xc(n - 1), cy: y(serie[n - 1].valor), r: 4, class: 'es-g-ponto' }, raiz);   // ponto final: >= 8 px, anel da cor do fundo
        svg('text', { x: xc(n - 1), y: y(serie[n - 1].valor) - 10, 'text-anchor': 'end', class: 'es-g-valor' }, raiz, fmt(serie[n - 1].valor));
        const alvo = svg('rect', { x: m.l, y: m.t, width: pw, height: ph, class: 'es-g-alvo', tabindex: 0, role: 'img', 'aria-label': `${spec.titulo || 'Linha'}: use as setas pra percorrer os dias` }, raiz);
        let atual = n - 1;
        const ver = (i) => {
            i = Math.max(0, Math.min(n - 1, i)); atual = i;
            const s = serie[i], px = xc(i), py = y(s.valor);
            mira.setAttribute('x1', px); mira.setAttribute('x2', px); mira.style.display = '';
            ponto.setAttribute('cx', px); ponto.setAttribute('cy', py); ponto.style.display = '';
            const [tx, ty] = naTela(raiz, px, py);
            const linhas = [{ t: `${fmt(s.valor)} ${spec.unidade || ''}`.trim(), c: 'valor' }];
            (s.detalhe || []).forEach((d) => linhas.push({ t: d, c: 'rotulo' }));
            linhas.push({ t: s.dica || s.rotulo, c: 'rotulo' });
            mostrarDica(linhas, tx, ty);
        };
        const sair = () => { mira.style.display = 'none'; ponto.style.display = 'none'; esconderDica(); };
        alvo.addEventListener('pointermove', (e) => { const r = raiz.getBoundingClientRect(); ver(n > 1 ? Math.round((e.clientX - r.left - m.l) / passoX) : 0); });
        alvo.addEventListener('pointerleave', sair); alvo.addEventListener('blur', sair);
        alvo.addEventListener('focus', () => ver(atual));
        alvo.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') { e.preventDefault(); ver(atual - 1); } else if (e.key === 'ArrowRight') { e.preventDefault(); ver(atual + 1); } else if (e.key === 'Escape') sair();
        });
        el.replaceChildren(raiz);
    }

    // ---------------------------------------------------------------------
    // BARRAS HORIZONTAIS (categorias com nome)
    // ---------------------------------------------------------------------
    function barrasH(el, spec) {
        const serie = spec.serie || [];
        if (!serie.length) return vazio(el, spec.vazio);
        const W = larguraDe(el), linhaH = 34, m = { t: 6, r: 56, b: 6, l: 104 };
        const H = m.t + m.b + linhaH * serie.length, pw = W - m.l - m.r;
        const max = Math.max(1, ...serie.map((s) => s.valor)), total = serie.reduce((a, s) => a + s.valor, 0) || 1;
        const raiz = svg('svg', { viewBox: `0 0 ${W} ${H}`, width: W, height: H, class: 'es-g-svg', role: 'img', 'aria-label': spec.titulo || 'Gráfico de barras' });
        svg('line', { x1: m.l, x2: m.l, y1: m.t, y2: H - m.b, class: 'es-g-grade' }, raiz);
        serie.forEach((s, i) => {
            const cy = m.t + linhaH * i + linhaH / 2, g = svg('g', { class: 'es-g-par' }, raiz);
            svg('text', { x: m.l - 10, y: cy + 4, 'text-anchor': 'end', class: 'es-g-eixo' }, g, s.rotulo);
            const w = s.valor > 0 ? Math.max(4, (s.valor / max) * pw) : 0;
            if (w) svg('path', { d: `M${m.l},${cy - 9} H${m.l + w - 4} Q${m.l + w},${cy - 9} ${m.l + w},${cy - 5} V${cy + 5} Q${m.l + w},${cy + 9} ${m.l + w - 4},${cy + 9} H${m.l} Z`, class: 'es-g-barra' }, g);
            svg('text', { x: m.l + w + 8, y: cy + 4, class: 'es-g-valor' }, g, fmt(s.valor));
            const alvo = svg('rect', { x: 0, y: m.t + linhaH * i, width: W, height: linhaH, class: 'es-g-alvo', tabindex: 0, role: 'img', 'aria-label': `${s.rotulo}: ${fmt(s.valor)} ${spec.unidade || ''}` }, g);
            const abrir = () => { g.classList.add('ativo'); const [px, py] = naTela(raiz, m.l + w, cy - 8); mostrarDica([{ t: `${fmt(s.valor)} ${spec.unidade || ''}`.trim(), c: 'valor' }, { t: `${Math.round((s.valor / total) * 100)}% do total · ${s.dica || s.rotulo}`, c: 'rotulo' }], px, py); };
            const fechar = () => { g.classList.remove('ativo'); esconderDica(); };
            alvo.addEventListener('pointerenter', abrir); alvo.addEventListener('pointerleave', fechar);
            alvo.addEventListener('focus', abrir); alvo.addEventListener('blur', fechar);
        });
        el.replaceChildren(raiz);
    }

    // ---------------------------------------------------------------------
    // TABELA (o mesmo dado, sem depender de cor nem de mouse)
    // ---------------------------------------------------------------------
    function tabela(spec) {
        const t = document.createElement('table');
        t.className = 'es-tabela es-g-tabela';
        const cab = document.createElement('thead'), tr = document.createElement('tr');
        (spec.tabela.cabecalho || []).forEach((c, i) => { const th = document.createElement('th'); th.scope = 'col'; th.textContent = c; if (i) th.className = 'num'; tr.appendChild(th); });
        cab.appendChild(tr); t.appendChild(cab);
        const corpo = document.createElement('tbody');
        (spec.tabela.linhas || []).forEach((l) => {
            const r = document.createElement('tr');
            l.forEach((v, i) => { const td = document.createElement('td'); td.textContent = typeof v === 'number' ? fmt(v) : v; if (i) td.className = 'num'; r.appendChild(td); });
            corpo.appendChild(r);
        });
        t.appendChild(corpo);
        return t;
    }

    // ---------------------------------------------------------------------
    // CARTÃO: título, botão "Ver como tabela" e o gráfico (redesenha quando a largura muda)
    // ---------------------------------------------------------------------
    const FORMAS = { colunas, linha, barrasH };
    const observador = typeof ResizeObserver !== 'undefined' ? new ResizeObserver((lista) => lista.forEach((x) => {
        const c = x.target, larg = Math.floor(x.contentRect.width);
        if (!c.isConnected) { observador.unobserve(c); return; }   // a tela foi refeita: solta o que saiu do documento
        if (c._spec && c._larg !== larg && !c._tabela) { c._larg = larg; desenharCorpo(c); }
    })) : null;

    function desenharCorpo(corpo) {
        const spec = corpo._spec;
        corpo.dataset.larg = corpo.clientWidth;
        if (corpo._tabela) { corpo.replaceChildren(tabela(spec)); return; }
        (FORMAS[spec.tipo] || colunas)(corpo, spec);
    }

    function montar(el, spec) {
        el.replaceChildren();
        const topo = document.createElement('div');
        topo.className = 'es-g-topo';
        const tit = document.createElement('div');
        const h = document.createElement('h2'); h.textContent = spec.titulo;
        const sub = document.createElement('small'); sub.textContent = spec.sub || '';
        tit.append(h, sub);
        const bt = document.createElement('button');
        bt.type = 'button'; bt.className = 'es-btn mini'; bt.textContent = 'Ver como tabela'; bt.setAttribute('aria-pressed', 'false');
        topo.append(tit, bt);
        const corpo = document.createElement('div');
        corpo.className = 'es-g-corpo';
        el.append(topo, corpo);
        corpo._spec = spec; corpo._tabela = false;
        bt.addEventListener('click', () => {
            corpo._tabela = !corpo._tabela; esconderDica();
            bt.textContent = corpo._tabela ? 'Ver gráfico' : 'Ver como tabela';
            bt.setAttribute('aria-pressed', String(corpo._tabela));
            desenharCorpo(corpo);
        });
        desenharCorpo(corpo);
        corpo._larg = Math.floor(corpo.clientWidth);
        if (observador) observador.observe(corpo);
        return corpo;
    }

    /** Troca os dados de um gráfico já montado (mantém a tela: o chamador só baixa a opacidade enquanto carrega). */
    function atualizar(corpo, spec) { corpo._spec = spec; desenharCorpo(corpo); }

    return { montar, atualizar, escala, fmt };
})();
