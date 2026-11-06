/* Dados e moeda em 3D, desenhados num <canvas> sem biblioteca (Rodada 39). Objeto global `Dados3D`.
 *
 * O RESULTADO é sempre o do servidor (app/jogos.py): aqui só se anima. Cada dado cai, quica e gira; no fim a face do número sorteado vira pra câmera
 * (a rotação final é calculada pra isso: o que aparece em cima É o resultado). d4, d6, d8, d10, d12, d20 e d100 (um d10 com o resultado na face) e a moeda.
 * Um poliedro é só vértices e faces; a projeção é uma perspectiva simples e as faces são ordenadas do fundo pra frente (pintor): sem WebGL.
 * Tudo roda só enquanto anima (~1,6 s) e some do laço depois; `prefers-reduced-motion` mostra o resultado parado. Sem estado fora do módulo.
 *
 * API:  Dados3D.criar() -> { mostrar, selecionar, parar }   UMA instância por canvas (o painel dos dados e o aviso da call animam juntos sem se atropelar)
 *       inst.mostrar(canvas, entrada, { animar, aoFim })   entrada = resultado do servidor: {id, tipo:'rolagem'|'d6'..|'moeda', grupos|texto, moedas}
 *       inst.selecionar(canvas, ['d6','d20'])              os dados da seleção, parados e sem número (antes de rolar)
 *       Dados3D.mostrar/selecionar/parar                   a instância "de sempre" (atalho)
 *       Dados3D.geometria(nome) / Dados3D.alvo(geo, face)  (a matemática pura, que os testes do Node exercitam)
 */
const Dados3D = (() => {
    'use strict';
    const PHI = (1 + Math.sqrt(5)) / 2;
    const soma = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
    const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
    const mul = (a, k) => [a[0] * k, a[1] * k, a[2] * k];
    const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    const cruz = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
    const norma = (a) => Math.hypot(a[0], a[1], a[2]);
    const unit = (a) => { const n = norma(a) || 1; return [a[0] / n, a[1] / n, a[2] / n]; };

    // ---- quaternions [w, x, y, z] ----
    const qMul = (a, b) => [a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3], a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
        a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1], a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0]];
    const qEixo = (eixo, ang) => { const e = unit(eixo), s = Math.sin(ang / 2); return [Math.cos(ang / 2), e[0] * s, e[1] * s, e[2] * s]; };
    function qGira(q, v) {                                     // gira o vetor v pelo quaternion q
        const u = [q[1], q[2], q[3]], t = mul(cruz(u, v), 2);
        return soma(soma(v, mul(t, q[0])), cruz(u, t));
    }
    function qSlerp(a, b, t) {
        let c = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3];
        if (c < 0) { b = [-b[0], -b[1], -b[2], -b[3]]; c = -c; }
        if (c > 0.9995) { const r = a.map((x, i) => x + (b[i] - x) * t); const n = Math.hypot(...r); return r.map(x => x / n); }
        const th = Math.acos(c), s = Math.sin(th), k1 = Math.sin((1 - t) * th) / s, k2 = Math.sin(t * th) / s;
        return a.map((x, i) => x * k1 + b[i] * k2);
    }
    function qDe(de, para) {                                   // a menor rotação que leva o vetor `de` até `para`
        const a = unit(de), b = unit(para), c = dot(a, b);
        if (c > 0.999999) return [1, 0, 0, 0];
        if (c < -0.999999) { const p = Math.abs(a[0]) < .9 ? [1, 0, 0] : [0, 1, 0]; return qEixo(cruz(a, p), Math.PI); }
        return qEixo(cruz(a, b), Math.acos(c));
    }

    // ---------------------------------------------------------------------
    // geometria: vértices e faces de cada sólido (faces com normal pra fora)
    // ---------------------------------------------------------------------
    function construir(verts, faces) {
        const fs = faces.map((idx) => {
            const pts = idx.map(i => verts[i]);
            const c = mul(pts.reduce(soma, [0, 0, 0]), 1 / pts.length);
            let n = unit(cruz(sub(pts[1], pts[0]), sub(pts[2], pts[0])));
            let ordem = idx;
            if (dot(n, c) < 0) { n = mul(n, -1); ordem = idx.slice().reverse(); }
            return { idx: ordem, n, c };
        });
        return { verts, faces: fs };
    }
    function ordenarEmTorno(verts, idx, eixo) {                // vértices de uma face em ordem de ângulo ao redor do eixo (pra formar o polígono certo)
        const u = unit(cruz(eixo, Math.abs(eixo[0]) < .9 ? [1, 0, 0] : [0, 1, 0])), v = cruz(eixo, u);
        return idx.slice().sort((i, j) => Math.atan2(dot(verts[i], v), dot(verts[i], u)) - Math.atan2(dot(verts[j], v), dot(verts[j], u)));
    }
    const GEO = {
        d4() { const v = [[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]]; return construir(v, [[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]]); },
        d6() {
            const v = [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]];
            return construir(v, [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [3, 7, 6, 2], [0, 4, 7, 3], [1, 2, 6, 5]]);
        },
        d8() {
            const v = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]];
            return construir(v, [[0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4], [2, 0, 5], [1, 2, 5], [3, 1, 5], [0, 3, 5]]);
        },
        d10() {                                                // trapezoedro pentagonal: 2 polos e 2 anéis de 5 (a altura do anel faz as faces ficarem planas)
            const a = 1.15, c = Math.cos(Math.PI / 5), b = a * (1 - c) / (1 + c), v = [[0, a, 0], [0, -a, 0]];
            for (let k = 0; k < 5; k++) { const t = 2 * Math.PI * k / 5; v.push([Math.cos(t), b, Math.sin(t)]); }                       // 2..6 anel de cima
            for (let k = 0; k < 5; k++) { const t = 2 * Math.PI * k / 5 + Math.PI / 5; v.push([Math.cos(t), -b, Math.sin(t)]); }       // 7..11 anel de baixo
            const faces = [];
            for (let k = 0; k < 5; k++) faces.push([0, 2 + k, 7 + k, 2 + (k + 1) % 5]);
            for (let k = 0; k < 5; k++) faces.push([1, 7 + k, 2 + (k + 1) % 5, 7 + (k + 1) % 5]);
            return construir(v, faces);
        },
        d12() {
            const f = 1 / PHI, v = [];
            [-1, 1].forEach(x => [-1, 1].forEach(y => [-1, 1].forEach(z => v.push([x, y, z]))));
            [-1, 1].forEach(a => [-1, 1].forEach(b => { v.push([0, a * f, b * PHI]); v.push([a * f, b * PHI, 0]); v.push([a * PHI, 0, b * f]); }));
            const dirs = [];                                   // centros das faces = vértices do icosaedro "par" deste dodecaedro
            [-1, 1].forEach(a => [-1, 1].forEach(b => { dirs.push([0, a * PHI, b]); dirs.push([a * PHI, b, 0]); dirs.push([a, 0, b * PHI]); }));
            const faces = dirs.map(d => ordenarEmTorno(v, v.map((p, i) => [dot(p, d), i]).sort((p, q) => q[0] - p[0]).slice(0, 5).map(x => x[1]), d));
            return construir(v, faces);
        },
        d20() {
            const v = [];
            [-1, 1].forEach(a => [-1, 1].forEach(b => { v.push([0, a, b * PHI]); v.push([a, b * PHI, 0]); v.push([a * PHI, 0, b]); }));
            const faces = [];
            for (let i = 0; i < 12; i++) for (let j = i + 1; j < 12; j++) for (let k = j + 1; k < 12; k++) {
                const ok = [[i, j], [j, k], [i, k]].every(([p, q]) => Math.abs(norma(sub(v[p], v[q])) - 2) < 1e-6);
                if (ok) faces.push([i, j, k]);
            }
            return construir(v, faces);
        },
    };
    GEO.d100 = GEO.d10;
    const NOMES = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100'];
    const cache = {};
    function geometria(nome) { if (!GEO[nome]) return null; return cache[nome] || (cache[nome] = GEO[nome]()); }
    /** A rotação que põe a face `f` de frente pra câmera (a câmera está em -z, olhando +z), com um giro extra `roll` em volta do eixo da câmera. */
    function alvo(geo, f, roll) { return qMul(qEixo([0, 0, -1], roll || 0), qDe(geo.faces[f].n, [0, 0, -1])); }
    /** Qual face mostra o valor v: d4 a d20 = a face (v-1); d10 mostra 1..10; d100 mostra o valor na face (v-1)%10 (o rótulo é o próprio valor). */
    const faceDoValor = (nome, v) => nome === 'd100' ? ((Math.max(1, v) - 1) % 10) : Math.max(0, Math.min(geometria(nome).faces.length - 1, v - 1));

    // ---------------------------------------------------------------------
    // aparência
    // ---------------------------------------------------------------------
    // as cores dos botões do painel de dados (static/css/dados.css usa as mesmas): d4 verde, d6 turquesa, d8 roxo, d10 rosa, d12 vermelho, d20 laranja
    const COR = { d4: [46, 160, 84], d6: [34, 168, 190], d8: [140, 76, 222], d10: [226, 62, 150], d12: [222, 60, 52], d20: [242, 124, 24], d100: [142, 106, 79] };
    const ESCALA_TEXTO = { d4: 1.1, d6: 1.3, d8: 1.05, d10: .9, d12: .95, d20: .8, d100: .85 };       // (o dado agora é desenhado numa esfera padrão: o número acompanha, pra continuar legível com vários dados)
    const LUZ = unit([-.4, -.7, -.6]);
    const reduzMov = () => !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

    /** Os dados (e moedas) a desenhar, a partir de um item do histórico do servidor. */
    function descrever(e) {
        if (!e) return [];
        if (e.tipo === 'moeda') return (e.moedas && e.moedas.length ? e.moedas : [e.texto]).slice(0, 10).map(f => ({ moeda: true, face: f === 'Cara' ? 'Cara' : 'Coroa', mantido: true }));
        if (e.tipo === 'rolagem') {
            const out = [];
            (e.grupos || []).forEach(g => (g.valores || []).forEach((v, i) => { if (NOMES.includes(g.dado)) out.push({ dado: g.dado, valor: Number(v), mantido: (g.mantidos || []).includes(i), sinal: g.sinal }); }));
            return out.slice(0, 30);
        }
        if (NOMES.includes(e.tipo)) return [{ dado: e.tipo, valor: Number(e.texto), mantido: true, sinal: 1 }];
        return [];
    }
    function preparar(desc, seed) {                            // o "sorteio" visual de cada dado: eixo, velocidade e roll; o valor já é do servidor
        let s = (seed || 1) * 9301 + 49297;
        const rnd = () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
        return desc.map((d, i) => {
            const geo = d.dado ? geometria(d.dado) : null;
            return Object.assign({}, d, {
                geo, atraso: i * 0.05, eixo: [rnd() - .5, rnd() - .5, rnd() - .5], w0: 9 + rnd() * 7, q0: qEixo([rnd() - .5, rnd() - .5, rnd() - .5], rnd() * 6.28), roll: (rnd() - .5) * .9,
                alvoQ: d.dado ? alvo(geo, faceDoValor(d.dado, d.valor), (rnd() - .5) * .9) : null, quedas: 2 + rnd(), giros: 2 + Math.floor(rnd() * 3),
            });
        });
    }

    // ---------------------------------------------------------------------
    // desenho
    // ---------------------------------------------------------------------
    function desenharDado(g, d, cx, cy, R, q, alfa) {
        // todo dado cabe na mesma esfera: sem isso um d8 (vértices a 1) saía minúsculo ao lado de um d20 (a 1,9)
        R = R * 1.7 / (d.geo.raio || (d.geo.raio = Math.max(...d.geo.verts.map(norma))));
        const cam = 7.5, proj = (p) => { const k = cam / (cam + p[2]); return [cx + p[0] * R * k, cy + p[1] * R * k, p[2]]; };
        const vs = d.geo.verts.map(v => qGira(q, v)), P = vs.map(proj);
        const cor = COR[d.dado], apagado = !d.mantido;
        const visiveis = d.geo.faces.map((f, i) => ({ i, n: qGira(q, f.n), z: f.idx.reduce((a, k) => a + vs[k][2], 0) / f.idx.length })).filter(f => f.n[2] < 0).sort((a, b) => b.z - a.z);
        g.save(); g.globalAlpha = alfa * (apagado ? .35 : 1); g.lineJoin = 'round';
        const melhor = visiveis.reduce((m, f) => (!m || f.n[2] < m.n[2] ? f : m), null);          // a face mais virada pra câmera: só ela leva número (como no dado do Google), não todas as visíveis
        visiveis.forEach(f => {
            const luz = Math.max(0, -dot(f.n, LUZ)), t = .42 + .58 * luz;
            g.beginPath(); d.geo.faces[f.i].idx.forEach((k, j) => j ? g.lineTo(P[k][0], P[k][1]) : g.moveTo(P[k][0], P[k][1])); g.closePath();
            g.fillStyle = `rgb(${Math.round(cor[0] * t + 30 * luz)},${Math.round(cor[1] * t + 30 * luz)},${Math.round(cor[2] * t + 30 * luz)})`; g.fill();
            g.strokeStyle = 'rgba(0,0,0,.45)'; g.lineWidth = Math.max(1, R * .03); g.stroke();
            const frente = -f.n[2];
            if (frente > .4 && !d.semNumero && melhor && f.i === melhor.i) {   // o número, no centro da face de frente (some quando ela fica de lado; dado ainda não rolado não tem número)
                const ce = proj(qGira(q, d.geo.faces[f.i].c)), fim = d.dado === 'd100' ? String(d.valor) : String(d.dado === 'd10' ? f.i + 1 : f.i + 1);
                const rotulo = d.dado === 'd100' ? (f.i === faceDoValor('d100', d.valor) ? String(d.valor) : String((f.i + 1) * 10)) : fim;
                g.fillStyle = `rgba(255,255,255,${Math.min(1, (frente - .4) * 2.2)})`; g.textAlign = 'center'; g.textBaseline = 'middle';
                g.font = `800 ${Math.max(7, R * ESCALA_TEXTO[d.dado] * (rotulo.length > 2 ? .7 : rotulo.length > 1 ? .85 : 1))}px system-ui, sans-serif`;
                g.fillText(rotulo, ce[0], ce[1] + R * .02);
            }
        });
        g.restore();
    }
    function desenharMoeda(g, d, cx, cy, R, ang, alfa, fimAng) {
        const esc = Math.abs(Math.cos(ang)), frente = Math.cos(ang) >= 0, mostraCara = frente ? d.face === 'Cara' : d.face !== 'Cara';
        g.save(); g.globalAlpha = alfa; g.translate(cx, cy);
        const grosso = R * .16, rx = R * .95, ry = Math.max(R * .07, rx * esc);
        g.fillStyle = '#9a7416'; g.beginPath(); g.ellipse(0, grosso * (1 - esc * .5), rx, ry, 0, 0, 7); g.fill();             // a borda (aparece quando a moeda está de lado)
        const gr = g.createLinearGradient(-rx, -ry, rx, ry); gr.addColorStop(0, '#fff0a6'); gr.addColorStop(.55, '#f0c53a'); gr.addColorStop(1, '#b8861a');
        g.fillStyle = gr; g.beginPath(); g.ellipse(0, 0, rx, ry, 0, 0, 7); g.fill(); g.strokeStyle = 'rgba(0,0,0,.4)'; g.lineWidth = Math.max(1, R * .04); g.stroke();
        if (esc > .3) {
            g.scale(1, esc); g.fillStyle = 'rgba(90,60,0,.85)'; g.textAlign = 'center'; g.textBaseline = 'middle';
            g.font = `800 ${R * .5}px system-ui, sans-serif`; g.fillText(mostraCara ? '♛' : '●', 0, -R * .1);
            g.font = `800 ${R * .2}px system-ui, sans-serif`; g.fillText(mostraCara ? 'CARA' : 'COROA', 0, R * .38);
        }
        g.restore();
    }
    const suave = (t) => t * t * (3 - 2 * t);

    // ---------------------------------------------------------------------
    // animação: UMA POR CANVAS (`criar()`), pra o painel dos dados e o aviso da call rolarem ao mesmo tempo sem se atropelar.
    // O canvas pode ser trocado no meio, porque o painel redesenha o HTML.
    // ---------------------------------------------------------------------
    function layout(n, w, h) {
        const cols = Math.min(n, n <= 3 ? n : n <= 8 ? 4 : n <= 15 ? 6 : 8), linhas = Math.ceil(n / cols);
        const R = Math.min(w / (cols * 4.8), h / (linhas * 4.6), 44);          // o vértice mais longo (d20) chega a ~2,5 R com a perspectiva: com isso os dados não se cobrem nem passam da borda do palco
        return { cols, linhas, R, pos: (i) => ({ x: w * ((i % cols) + .5) / cols, y: h * (Math.floor(i / cols) + .56) / linhas }) };
    }
    function ajustarCanvas(c) {
        const dpr = Math.min(2, window.devicePixelRatio || 1), w = c.clientWidth || 300, h = c.clientHeight || 150;
        if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); }
    }
    /** Os dados PARADOS de uma seleção (ainda sem rolar): cada um num ângulo agradável e sem número, como o palco do widget de dados do Google. */
    function repouso(lista) {
        return lista.slice(0, 30).map((nome, i) => {
            const geo = geometria(nome);
            return { dado: nome, geo, valor: 1, mantido: true, semNumero: true, q: qMul(qEixo([1, 0, 0], .55 + (i % 3) * .08), qEixo([0, 1, 0], .7 + i * .85)) };
        });
    }
    function criar() {
        const A = { id: null, itens: [], inicio: 0, dur: 1600, canvas: null, raf: 0, fim: true, parados: null, aoFim: null };
        function limpar(c) { const g = c.getContext('2d'); g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, c.width, c.height); }
        function quadro(agora) {
            const c = A.canvas; if (!c || !c.isConnected) { A.raf = 0; return; }
            ajustarCanvas(c);                                        // o painel pode ter sido medido antes do layout (largura 0): confere a cada quadro
            const g = c.getContext('2d'), dpr = c.width / (c.clientWidth || c.width), w = c.clientWidth || 300, h = c.clientHeight || 150;
            g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
            if (A.parados) {                                          // sem rolagem: só os dados da seleção, parados
                const L = layout(A.parados.length, w, h);
                A.parados.forEach((d, i) => { const p = L.pos(i); desenharDado(g, d, p.x, p.y, L.R, d.q, 1); });
                A.raf = 0; return;
            }
            const t = A.fim ? 1 : Math.min(1, (agora - A.inicio) / A.dur), L = layout(A.itens.length, w, h);
            A.itens.forEach((d, i) => {
                const p = L.pos(i), loc = Math.max(0, Math.min(1, (t * A.dur - d.atraso * 1000) / (A.dur - 400))), fim = suave(Math.max(0, (loc - .55) / .45));
                const queda = Math.exp(-3.2 * loc) * Math.abs(Math.cos(Math.PI * d.quedas * loc));
                const altura = (h * .55) * (loc >= 1 ? 0 : queda * (1 - fim)), y = p.y - altura;
                if (d.moeda) {
                    const ang = d.giros * Math.PI * 2 * (1 - Math.exp(-3 * loc)) * (1 - fim) + (d.face === 'Cara' ? 0 : Math.PI) * fim;
                    desenharMoeda(g, d, p.x, y, L.R, loc >= 1 ? (d.face === 'Cara' ? 0 : Math.PI) : ang, 1, 0);
                } else {
                    const livre = qMul(d.q0, qEixo(d.eixo, (d.w0 / 3.2) * (1 - Math.exp(-3.2 * loc))));
                    desenharDado(g, d, p.x, y, L.R, loc >= 1 ? d.alvoQ : qSlerp(livre, d.alvoQ, fim), 1);
                }
            });
            if (t < 1) A.raf = requestAnimationFrame(quadro);
            else { A.raf = 0; A.fim = true; const f = A.aoFim; A.aoFim = null; if (f) { try { f(); } catch (e) { /* o aviso de fim não derruba o desenho */ } } }
        }
        /** Mostra os dados desse resultado no canvas. `animar` só vale se a entrada for NOVA (id diferente da última animada) e o movimento estiver permitido.
         *  `aoFim` roda quando os dados assentam (na hora, se não há animação): é o gancho pro "Total" aparecer só depois da rolagem. */
        function mostrar(canvas, entrada, opc) {
            if (!canvas) return;
            const desc = descrever(entrada);
            A.canvas = canvas; A.parados = null; ajustarCanvas(canvas);
            if (opc && opc.aoFim) A.aoFim = opc.aoFim;
            if (!desc.length) { limpar(canvas); const f = A.aoFim; A.aoFim = null; if (f) f(); return; }
            const novo = entrada.id !== A.id;
            if (novo) {
                A.id = entrada.id; A.itens = preparar(desc, entrada.id);
                A.dur = Math.min(2300, 1500 + desc.length * 35); A.inicio = performance.now();
                A.fim = !(opc && opc.animar !== false) || reduzMov();
            }
            if (A.fim) { cancelAnimationFrame(A.raf); A.raf = 0; quadro(performance.now()); const f = A.aoFim; A.aoFim = null; if (f) f(); return; }
            if (!A.raf) A.raf = requestAnimationFrame(quadro);
        }
        /** Os dados da seleção, parados e sem número (ainda não rolou). Cancela uma animação em curso (a seleção mudou). */
        function selecionar(canvas, nomes) {
            if (!canvas) return;
            cancelAnimationFrame(A.raf); A.raf = 0; A.id = null; A.fim = true; A.aoFim = null; A.canvas = canvas;
            ajustarCanvas(canvas);
            const lista = (nomes || []).filter((n) => NOMES.includes(n));
            if (!lista.length) { A.parados = null; limpar(canvas); return; }
            A.parados = repouso(lista); quadro(performance.now());
        }
        function parar() { cancelAnimationFrame(A.raf); A.raf = 0; A.id = null; A.fim = true; A.parados = null; A.aoFim = null; }
        return { mostrar, selecionar, parar };
    }
    const padrao = criar();      // a instância "de sempre" (a API antiga: mostrar/parar sem escolher instância)

    return { criar, mostrar: padrao.mostrar, selecionar: padrao.selecionar, parar: padrao.parar, geometria, alvo, faceDoValor, descrever, repouso, NOMES, COR,
             _q: { qMul, qEixo, qGira, qDe, qSlerp }, _v: { dot, unit, cruz, sub, norma } };
})();
