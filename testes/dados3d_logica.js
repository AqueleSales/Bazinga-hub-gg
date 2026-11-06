// Dados 3D (static/js/dados3d.js) e as contas puras do painel de dados (static/js/dados.js) no Node, sem navegador. Chamado por testes/fumaca_dados.py.
const fs = require('fs'), path = require('path');
const raiz = path.join(__dirname, '..', 'app', 'static', 'js');
let falhas = 0;
const ok = (c, m) => { console.log((c ? 'OK   ' : 'FALHA') + ' ' + m); if (!c) falhas++; };

// ---- ambiente mínimo de navegador ----
const filaRaf = [];
global.window = { matchMedia: () => ({ matches: false }), devicePixelRatio: 1 };
global.requestAnimationFrame = (f) => { filaRaf.push(f); return filaRaf.length; };
global.cancelAnimationFrame = () => {};
let relogio = 0; global.performance = { now: () => relogio };
function contexto() {
    const chamadas = { fill: 0, texto: 0, elipse: 0 };
    const g = new Proxy({}, { get(_, k) {
        if (k === '_chamadas') return chamadas;
        if (k === 'fill') return () => { chamadas.fill++; };
        if (k === 'fillText') return () => { chamadas.texto++; };
        if (k === 'ellipse') return () => { chamadas.elipse++; };
        if (k === 'createLinearGradient') return () => ({ addColorStop() {} });
        return () => {};
    }, set() { return true; } });
    return g;
}
function canvasFalso() { const g = contexto(); return { width: 300, height: 150, clientWidth: 300, clientHeight: 150, isConnected: true, getContext: () => g, _g: g }; }

const D = new Function(fs.readFileSync(path.join(raiz, 'dados3d.js'), 'utf8') + '\nreturn Dados3D;')();
const { _q: Q, _v: V } = D;

// ---- geometria: cada sólido tem o número certo de faces, planas e com a normal pra fora ----
const esperado = { d4: 4, d6: 6, d8: 8, d10: 10, d12: 12, d20: 20, d100: 10 };
const lados = { d4: 3, d6: 4, d8: 3, d10: 4, d12: 5, d20: 3, d100: 4 };
Object.keys(esperado).forEach((n) => {
    const g = D.geometria(n);
    ok(g.faces.length === esperado[n], `${n}: ${g.faces.length} faces (esperado ${esperado[n]})`);
    ok(g.faces.every(f => f.idx.length === lados[n]), `${n}: todas as faces têm ${lados[n]} vértices`);
    const planas = g.faces.every(f => { const pts = f.idx.map(i => g.verts[i]); return pts.every(p => Math.abs(V.dot(V.sub(p, pts[0]), f.n)) < 1e-6); });
    ok(planas, `${n}: faces planas (o polígono não fica torto)`);
    ok(g.faces.every(f => V.dot(f.n, f.c) > 0), `${n}: normais apontam pra fora`);
    ok(Math.abs(V.norma(f0(g).n) - 1) < 1e-9, `${n}: normal unitária`);
    // fechado: toda aresta é compartilhada por exatamente 2 faces
    const arestas = {};
    g.faces.forEach(f => f.idx.forEach((a, i) => { const b = f.idx[(i + 1) % f.idx.length], k = a < b ? a + '-' + b : b + '-' + a; arestas[k] = (arestas[k] || 0) + 1; }));
    ok(Object.values(arestas).every(c => c === 2), `${n}: sólido fechado (cada aresta tem 2 faces)`);
});
function f0(g) { return g.faces[0]; }

// ---- a rotação final põe a face sorteada de frente pra câmera ----
Object.keys(esperado).forEach((n) => {
    const g = D.geometria(n); let pior = 0;
    for (let v = 1; v <= (n === 'd100' ? 100 : esperado[n]); v++) {
        const f = D.faceDoValor(n, v), q = D.alvo(g, f, (v % 7) * .1);
        const normal = Q.qGira(q, g.faces[f].n);
        pior = Math.max(pior, Math.hypot(normal[0], normal[1], normal[2] + 1));
    }
    ok(pior < 1e-6, `${n}: em todo valor possível, a face do resultado fica virada pra câmera (erro ${pior.toExponential(1)})`);
});
ok(D.faceDoValor('d20', 20) === 19 && D.faceDoValor('d6', 1) === 0 && D.faceDoValor('d10', 10) === 9, 'o valor 1..N vai pra face N-1');
ok(D.faceDoValor('d100', 47) === 6 && D.faceDoValor('d100', 100) === 9, 'd100: o resultado aparece numa face do d10');
ok(D.faceDoValor('d20', 999) === 19 && D.faceDoValor('d20', -3) === 0, 'valor fora da faixa não quebra');
const qa = Q.qEixo([0, 1, 0], 1.0), qb = Q.qEixo([1, 0, 0], 2.0);
ok(V.norma(Q.qSlerp(qa, qb, .5)) > .999 && V.norma(Q.qSlerp(qa, qb, .5)) < 1.001, 'slerp mantém o quaternion unitário');
const s0 = Q.qSlerp(qa, qb, 0), s1 = Q.qSlerp(qa, qb, 1);
ok(s0.every((x, i) => Math.abs(x - qa[i]) < 1e-9) && s1.every((x, i) => Math.abs(Math.abs(x) - Math.abs(qb[i])) < 1e-9), 'slerp começa e termina nos extremos');

// ---- do histórico do servidor para os dados a desenhar ----
const d1 = D.descrever({ id: 1, tipo: 'rolagem', grupos: [{ dado: 'd20', valores: [17, 4], mantidos: [0], sinal: 1 }, { dado: 'd6', valores: [3], mantidos: [0], sinal: -1 }] });
ok(d1.length === 3 && d1[0].mantido && !d1[1].mantido && d1[2].sinal === -1, 'rolagem: um desenho por dado, o que ficou de fora marcado');
ok(D.descrever({ id: 2, tipo: 'd6', texto: '4' })[0].valor === 4, 'formato antigo (um dado só) também desenha');
ok(D.descrever({ id: 3, tipo: 'moeda', texto: 'Cara', moedas: ['Cara', 'Coroa', 'Coroa'] }).length === 3, 'moedas');
ok(D.descrever({ id: 4, tipo: 'sorteio', texto: 'Ana' }).length === 0 && D.descrever(null).length === 0, 'sorteio e vazio não desenham dado');
ok(D.descrever({ id: 5, tipo: 'rolagem', grupos: [{ dado: 'x99', valores: [1], mantidos: [0], sinal: 1 }] }).length === 0, 'dado inventado é ignorado');
ok(D.descrever({ id: 6, tipo: 'rolagem', grupos: [{ dado: 'd6', valores: Array(500).fill(1), mantidos: [], sinal: 1 }] }).length === 30, 'no máximo 30 dados na tela');

// ---- a animação roda quadro a quadro sem quebrar, com todos os sólidos e a moeda ----
const entradas = [
    { id: 10, tipo: 'rolagem', grupos: ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100'].map((d, i) => ({ dado: d, valores: [d === 'd4' ? 3 : d === 'd100' ? 47 : 5], mantidos: i % 2 ? [] : [0], sinal: 1 })) },
    { id: 11, tipo: 'moeda', texto: '2 caras e 1 coroa', moedas: ['Cara', 'Cara', 'Coroa'] },
    { id: 12, tipo: 'rolagem', grupos: [{ dado: 'd6', valores: Array.from({ length: 30 }, (_, i) => 1 + i % 6), mantidos: Array.from({ length: 30 }, (_, i) => i), sinal: 1 }] },
];
entradas.forEach((e) => {
    const c = canvasFalso(); let erro = null;
    try {
        relogio = 0; filaRaf.length = 0; D.mostrar(c, e, { animar: true });
        for (const t of [0, 100, 400, 800, 1200, 1600, 2400]) { relogio = t; const f = filaRaf.splice(0); f.forEach(fn => fn(t)); }
    } catch (x) { erro = x; }
    ok(!erro, `animação do item ${e.id} roda sem erro${erro ? ': ' + erro.stack.split('\n')[1] : ''}`);
    ok(c._g._chamadas.fill > 0 && (e.tipo === 'moeda' ? c._g._chamadas.elipse > 0 : c._g._chamadas.texto > 0), `item ${e.id}: desenhou (${JSON.stringify(c._g._chamadas)})`);
    ok(filaRaf.length === 0, `item ${e.id}: o laço de animação termina (não fica rodando pra sempre)`);
});
// resultado parado (abrir o painel com histórico) = nada de laço
const c2 = canvasFalso(); filaRaf.length = 0; D.parar(); D.mostrar(c2, entradas[0], { animar: false });
ok(filaRaf.length === 0 && c2._g._chamadas.fill > 0, 'sem animar: desenha o resultado de uma vez e não agenda quadro');
// movimento reduzido
global.window.matchMedia = () => ({ matches: true });
const c3 = canvasFalso(); filaRaf.length = 0; D.parar(); D.mostrar(c3, { ...entradas[0], id: 99 }, { animar: true });
ok(filaRaf.length === 0 && c3._g._chamadas.fill > 0, 'com "reduzir movimento": mostra parado, sem animação');
global.window.matchMedia = () => ({ matches: false });
// canvas que saiu da página no meio da animação
const c4 = canvasFalso(); filaRaf.length = 0; D.parar(); D.mostrar(c4, { ...entradas[0], id: 120 }, { animar: true }); c4.isConnected = false;
relogio = 300; filaRaf.splice(0).forEach(fn => fn(300));
ok(filaRaf.length === 0, 'se o canvas sai da tela, o laço para sozinho');
// painel redesenhado no meio da rolagem: troca o canvas e a mesma animação continua
const c5 = canvasFalso(), c6 = canvasFalso(); filaRaf.length = 0; D.parar(); relogio = 0; D.mostrar(c5, { ...entradas[0], id: 130 }, { animar: true });
relogio = 400; filaRaf.splice(0).forEach(fn => fn(400)); D.mostrar(c6, { ...entradas[0], id: 130 }, { animar: false });
relogio = 800; filaRaf.splice(0).forEach(fn => fn(800));
ok(c6._g._chamadas.fill > 0, 'o painel redesenhou no meio: a animação segue no canvas novo (sem recomeçar nem sumir)');

// ---- instâncias independentes (Rodada 40): o painel e o aviso da call animam ao mesmo tempo, cada um no seu canvas ----
{
    const a = D.criar(), b = D.criar(), ca = canvasFalso(), cb = canvasFalso();
    relogio = 0; filaRaf.length = 0; global.window.matchMedia = () => ({ matches: false });
    let fimA = 0, fimB = 0;
    a.mostrar(ca, { id: 201, tipo: 'rolagem', grupos: [{ dado: 'd20', valores: [14], mantidos: [0], sinal: 1 }] }, { animar: true, aoFim: () => { fimA++; } });
    b.mostrar(cb, { id: 202, tipo: 'rolagem', grupos: [{ dado: 'd6', valores: [3, 5], mantidos: [0, 1], sinal: 1 }] }, { animar: true, aoFim: () => { fimB++; } });
    ok(filaRaf.length === 2, 'duas instâncias agendam o próprio quadro (uma não cancela a outra)');
    for (const t of [100, 500, 900, 1300, 1700, 2500]) { relogio = t; filaRaf.splice(0).forEach(fn => fn(t)); }
    ok(fimA === 1 && fimB === 1, `cada uma avisa o seu fim uma vez só (A=${fimA}, B=${fimB})`);
    ok(ca._g._chamadas.fill > 0 && cb._g._chamadas.fill > 0 && filaRaf.length === 0, 'as duas desenharam e os laços terminaram');
    // sem animação: o aoFim sai na hora
    let fimC = 0; const cc = canvasFalso(); a.mostrar(cc, { id: 203, tipo: 'rolagem', grupos: [{ dado: 'd8', valores: [2], mantidos: [0], sinal: 1 }] }, { animar: false, aoFim: () => { fimC++; } });
    ok(fimC === 1 && filaRaf.length === 0, 'sem animar o "total" aparece na hora (aoFim chamado)');
    // movimento reduzido: idem
    global.window.matchMedia = () => ({ matches: true });
    let fimR = 0; const cr = canvasFalso(); filaRaf.length = 0; a.mostrar(cr, { id: 204, tipo: 'rolagem', grupos: [{ dado: 'd12', valores: [9], mantidos: [0], sinal: 1 }] }, { animar: true, aoFim: () => { fimR++; } });
    ok(fimR === 1 && filaRaf.length === 0, 'com "reduzir movimento" o resultado aparece parado e o total na hora');
    global.window.matchMedia = () => ({ matches: false });
    // entrada vazia (sorteio): limpa e avisa o fim
    let fimV = 0; a.mostrar(canvasFalso(), { id: 205, tipo: 'sorteio', texto: 'Ana' }, { aoFim: () => { fimV++; } });
    ok(fimV === 1, 'resultado sem dado (sorteio) não trava o aoFim');
}

// ---- os dados parados da seleção (sem rolar): sem número, sem laço, na ordem pedida ----
{
    const i = D.criar(), c = canvasFalso(); filaRaf.length = 0;
    i.selecionar(c, ['d6', 'd6', 'd20']);
    ok(c._g._chamadas.fill > 0 && c._g._chamadas.texto === 0, `seleção desenha os dados sem número (preenchimentos ${c._g._chamadas.fill}, textos ${c._g._chamadas.texto})`);
    ok(filaRaf.length === 0, 'a seleção é parada: nenhum laço de animação');
    const r = D.repouso(['d4', 'd6', 'd8', 'd10', 'd12', 'd20']);
    ok(r.length === 6 && r.every(x => x.semNumero && x.geo && x.geo.faces.length > 0) && new Set(r.map(x => x.q.join())).size === 6, 'cada dado da seleção tem a sua geometria e um ângulo próprio');
    const c2 = canvasFalso(); i.selecionar(c2, ['d99', 'x']); ok(c2._g._chamadas.fill === 0, 'nome de dado inventado é ignorado');
    const c3 = canvasFalso(); i.selecionar(c3, []); ok(c3._g._chamadas.fill === 0, 'seleção vazia limpa o palco');
    // trocar a seleção no meio da rolagem cancela a animação
    const c4 = canvasFalso(); relogio = 0; filaRaf.length = 0; let fimX = 0;
    i.mostrar(c4, { id: 301, tipo: 'rolagem', grupos: [{ dado: 'd20', valores: [7], mantidos: [0], sinal: 1 }] }, { animar: true, aoFim: () => { fimX++; } });
    i.selecionar(c4, ['d6']); relogio = 2500; filaRaf.splice(0).forEach(fn => fn(2500));
    ok(fimX === 0, 'mexer na seleção durante a rolagem cancela a animação (e o aoFim dela não dispara depois)');
}
ok(D.NOMES.includes('d100') && D.COR.d4[1] > D.COR.d4[0] && D.COR.d20[0] > D.COR.d20[2], 'as cores do palco existem pra todos os dados (d4 verde, d20 laranja)');

// ---- o painel de dados (dados.js): as contas que não precisam de tela ----
const P = new Function(fs.readFileSync(path.join(raiz, 'dados.js'), 'utf8') + '\nreturn Dados;')();
{
    const e1 = P._descreve({ id: 1, tipo: 'rolagem', expr: '2d20kh1+5', texto: '22', mod: 5, grupos: [{ dado: 'd20', valores: [17, 4], mantidos: [0], sinal: 1 }] });
    ok(e1.rotulo === 'Total' && e1.texto.includes('2d20kh1+5') && e1.texto.includes('[17 (4)]') && e1.texto.endsWith('= 22') && e1.texto.includes('+ 5'), `rolagem vira uma linha: ${e1.texto}`);
    const e2 = P._descreve({ id: 2, tipo: 'rolagem', expr: '1d20-1d4', texto: '10', mod: 0, grupos: [{ dado: 'd20', valores: [14], mantidos: [0], sinal: 1 }, { dado: 'd4', valores: [4], mantidos: [0], sinal: -1 }] });
    ok(e2.texto.includes('[14] − [4]') && !e2.texto.includes('+ 0'), `termo com sinal de menos: ${e2.texto}`);
    const e3 = P._descreve({ id: 3, tipo: 'moeda', texto: '2 caras e 1 coroa', moedas: ['Cara', 'Cara', 'Coroa'] });
    ok(e3.rotulo === '3 moedas' && e3.icone === 'fa-coins', 'várias moedas');
    ok(P._descreve({ id: 4, tipo: 'moeda', texto: 'Cara', moedas: ['Cara'] }).rotulo === 'Moeda', 'uma moeda');
    const e5 = P._descreve({ id: 5, tipo: 'sorteio', texto: 'Ana' });
    ok(e5.rotulo === 'Sorteado' && e5.texto === 'Sorteio: Ana', 'sorteio');
    const e6 = P._estado();
    ok(Object.keys(e6.sel).length === 0 && e6.mod === 0 && e6.esperando === false && e6.total.valor === '0', 'o painel nasce vazio, com total 0');
    ok(P.aberto() === false, 'e fechado');
}

console.log(falhas ? `\n${falhas} FALHA(S)` : '\nTUDO OK');
process.exit(falhas ? 1 : 0);
