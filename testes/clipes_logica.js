// Testes da lógica pura dos clipes da call (detector de momentos e armazém de clipes). Roda no Node, sem navegador:
//   node testes/clipes_logica.js
// O testes/fumaca_clipes.py chama este arquivo. Sai com código 1 se algo falhar.
// Os "áudios" aqui são ENVELOPES sintéticos (nível de volume a cada 50 ms): provam que as regras fazem o que prometem, não que acertam
// com voz de verdade (isso só dá pra afinar ouvindo uma call real).
const path = require('path');
const { ClipesDetector, ClipesArmazem } = require(path.join(__dirname, '..', 'app', 'static', 'js', 'clipes.js'));

let falhas = 0, total = 0;
function ok(cond, nome) { total++; if (cond) console.log('  ok   ' + nome); else { falhas++; console.log('  FALHOU  ' + nome); } }

const PASSO = 50;                                       // ms entre amostras (20 por segundo)
// gerador pseudo-aleatório com semente (resultado igual a cada rodada)
function rnd(semente) { let s = semente >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }

// roda um cenário: gen(t_em_segundos) devolve a lista de {id, v}; devolve os eventos disparados
function rodar(det, segundos, gen, t0 = 0, passo = PASSO) {
    const evs = [];
    for (let t = 0; t < segundos * 1000; t += passo) {
        const ev = det.alimentar(t0 + t, gen(t / 1000));
        if (ev) evs.push(ev);
    }
    return evs;
}
// fala "normal": sílabas de 120 a 280 ms com volumes diferentes, vales rasos entre elas e pausas de respiração, volume em torno de `nivel`
function fala(nivel, semente) {
    const r = rnd(semente);
    let t = 0; const sil = [];
    while (t < 700) {
        if (r() < 0.12) t += 0.5 + r();                       // pausa
        const dur = 0.12 + r() * 0.16, amp = 0.55 + r() * 0.45, vale = 0.3 + r() * 0.5;
        sil.push({ ini: t, fim: t + dur, amp, vale });
        t += dur + 0.01 + r() * 0.05;
    }
    return (tt) => {
        const s = sil.find(x => tt >= x.ini - 0.06 && tt < x.fim + 0.06);
        if (!s) return 0.004;
        const dentro = tt >= s.ini && tt < s.fim;
        const forma = dentro ? Math.sin(((tt - s.ini) / (s.fim - s.ini)) * Math.PI) : 0;
        return nivel * s.amp * (s.vale + (1 - s.vale) * forma) * (0.9 + r() * 0.2);
    };
}
// risada: rajadas de 5 por segundo com vales fundos
function risada(pico) { return (t) => { const f = (t * 5) % 1; return f < 0.45 ? pico * (0.7 + 0.3 * Math.sin(f / 0.45 * Math.PI)) : pico * 0.07; }; }

console.log('--- detector ---');
{
    const d = ClipesDetector.criar();
    ok(rodar(d, 90, () => [{ id: 'a', v: 0.003 }]).length === 0, 'silêncio de 90 s não dispara nada');
}
{
    const d = ClipesDetector.criar();
    const f = fala(0.08, 1);
    ok(rodar(d, 120, (t) => [{ id: 'a', v: f(t) }]).length === 0, 'uma pessoa falando normal por 2 minutos não dispara');
}
{
    const d = ClipesDetector.criar();
    const f1 = fala(0.08, 2), f2 = fala(0.07, 3);
    let n = 0, id = 0;
    // conversa de duas pessoas que se alternam (sem falar junto): não é momento
    const evs = rodar(d, 120, (t) => { const vez = Math.floor(t / 4) % 2; return [{ id: 'a', v: vez ? 0.004 : f1(t) }, { id: 'b', v: vez ? f2(t) : 0.004 }]; });
    ok(evs.length === 0, 'duas pessoas se alternando (sem falar junto) não disparam');
}
{
    const d = ClipesDetector.criar();
    const f = fala(0.08, 4);
    // 30 s normais pra o detector aprender o "normal" dela, depois 4 s gritando
    const evs = rodar(d, 40, (t) => [{ id: 'a', v: t < 30 ? f(t) : (t < 34 ? 0.5 : f(t)) }]);
    ok(evs.length === 1 && evs[0].motivo === 'pico', 'grito depois de 30 s de fala normal dispara 1 pico');
    ok(evs.length && evs[0].t >= 30000 && evs[0].t <= 33000, 'o pico dispara em até 3 s depois do grito começar');
}
{
    const d = ClipesDetector.criar();
    const f = fala(0.06, 5);
    // pessoa de voz BAIXA: o "normal" dela é 0.06; levantar a voz pra 0.2 tem que contar (mais que o dobro do normal)
    const evs = rodar(d, 45, (t) => [{ id: 'a', v: t < 30 ? f(t) : (t < 36 ? 0.2 : f(t)) }]);
    ok(evs.length >= 1 && evs[0].motivo === 'pico', 'voz baixa que levanta a voz (mais que o dobro do normal) dispara');
}
{
    const d = ClipesDetector.criar();
    const f1 = fala(0.07, 6), f2 = fala(0.07, 7);
    const evs = rodar(d, 30, (t) => [{ id: 'a', v: t > 8 && t < 15 ? 0.07 + 0.01 * Math.sin(t) : 0.004 }, { id: 'b', v: t > 8 && t < 15 ? 0.065 : 0.004 }]);
    ok(evs.length === 1 && evs[0].motivo === 'junto', 'duas pessoas falando juntas por 7 s disparam "junto"');
}
{
    const d = ClipesDetector.criar();
    const evs = rodar(d, 30, (t) => [{ id: 'a', v: t > 8 && t < 9.2 ? 0.07 : 0.004 }, { id: 'b', v: t > 8 && t < 9.2 ? 0.065 : 0.004 }]);
    ok(evs.length === 0, 'falar junto por apenas 1 s (atropelo normal de conversa) não dispara');
}
{
    const d = ClipesDetector.criar();
    const l = risada(0.22);
    const evs = rodar(d, 14, (t) => [{ id: 'a', v: t > 5 && t < 8 ? l(t) : 0.004 }]);
    ok(evs.length === 1 && evs[0].motivo === 'risada', 'risada (rajadas regulares com vale fundo) dispara "risada"');
}
{
    // fala ANIMADA no mesmo volume da risada, mas sem rajadas regulares: não pode ser confundida com risada
    const d = ClipesDetector.criar();
    const r = rnd(9);
    const irregular = (t) => (0.07 + 0.05 * r()) * (0.75 + 0.25 * Math.sin(t * 7.3));
    const det = ClipesDetector.detectarRisada;
    const amostras = []; for (let i = 0; i < 36; i++) amostras.push(irregular(i * 0.05));
    ok(det(amostras) === false, 'fala sem rajadas regulares não é detectada como risada');
    const amostras2 = []; const l = risada(0.2); for (let i = 0; i < 36; i++) amostras2.push(l(i * 0.05));
    ok(det(amostras2) === true, 'o detector de risada reconhece a rajada regular sozinho');
    const lisa = []; for (let i = 0; i < 36; i++) lisa.push(0.2);
    ok(det(lisa) === false, 'volume constante não é risada');
}
{
    // tempo mínimo entre clipes: dois gritos com 20 s de intervalo viram UM disparo; o terceiro, 60 s depois, dispara de novo
    const d = ClipesDetector.criar();
    const f = fala(0.08, 10);
    const grita = (t) => (t >= 30 && t < 33) || (t >= 50 && t < 53) || (t >= 100 && t < 103);
    const evs = rodar(d, 110, (t) => [{ id: 'a', v: grita(t) ? 0.5 : f(t) }]);
    ok(evs.length === 2, 'dois gritos a 20 s de distância = 1 clipe só (mínimo de 45 s entre clipes); o do minuto seguinte dispara de novo (' + evs.length + ')');
    ok(evs.length === 2 && evs[1].t - evs[0].t >= 45000, 'intervalo entre os disparos respeita 45 s');
}
{
    // aba em segundo plano: o relógio estrangula pra 1 amostra por segundo. Pico continua sendo detectado; risada não (não dá pra ver rajada)
    const d = ClipesDetector.criar();
    const evs = rodar(d, 60, (t) => [{ id: 'a', v: t >= 20 && t < 26 ? 0.5 : 0.08 }], 0, 1000);
    ok(evs.length === 1 && evs[0].motivo === 'pico', 'amostras de 1 s (aba em segundo plano) ainda pegam um grito longo');
}
{
    // sensibilidade: um momento "mais ou menos" (voz um pouco acima do normal) só dispara na sensibilidade alta
    const sc = (sens) => { const d = ClipesDetector.criar({ sensibilidade: sens }); const f = fala(0.07, 12); return rodar(d, 60, (t) => [{ id: 'a', v: t >= 30 && t < 40 ? 0.17 : f(t) }]).length; };
    ok(sc('alta') >= 1, 'sensibilidade alta dispara com a voz 2,4x acima do normal');
    ok(sc('baixa') <= sc('normal') && sc('normal') <= sc('alta'), 'baixa dispara no máximo o que a normal dispara, que dispara no máximo o que a alta dispara (' + sc('baixa') + '/' + sc('normal') + '/' + sc('alta') + ')');
}
{
    const d = ClipesDetector.criar();
    ok(d.alimentar(0, null) === null && d.alimentar(50, []) === null && d.alimentar(100, [{ id: 'a', v: NaN }, null, { id: 'b' }]) === null, 'entradas estranhas (null, NaN, vazio) não quebram nem disparam');
    ok(typeof d.estado().score === 'number', 'estado() devolve o placar');
}

console.log('--- armazém ---');
{
    let agora = 1000000; const saiu = [];
    const a = ClipesArmazem.criar({ agora: () => agora, aoSair: (c, m) => saiu.push([c.id, m]) });
    ok(ClipesArmazem.TTL_MS === 20 * 60 * 1000, 'cada clipe vive 20 minutos');
    const c1 = a.adicionar({ motivo: 'risada' });
    agora += 5 * 60000;
    const c2 = a.adicionar({ motivo: 'pico' });
    ok(a.total() === 2 && a.novos() === 2, 'dois clipes novos');
    ok(a.listar()[0].id === c2.id, 'o mais novo vem primeiro');
    a.marcarVisto(c1.id);
    ok(a.novos() === 1 && a.obter(c1.id).visto === true, 'marcar como visto tira da conta dos novos');
    agora += 14 * 60000 + 59000;                           // c1 tem 19 min 59 s de vida
    ok(a.varrer().length === 0 && a.total() === 2, 'com 19 min 59 s o primeiro ainda não expirou');
    agora += 2000;                                          // passou de 20 min
    const venceu = a.varrer();
    ok(venceu.length === 1 && venceu[0].id === c1.id && a.total() === 1, 'passou de 20 min: só o primeiro some');
    ok(saiu.length === 1 && saiu[0][1] === 'expirou', 'quem some avisa o motivo (para soltar o arquivo da memória)');
    ok(a.restante(c2) > 0 && a.fracao(c2) > 0 && a.fracao(c2) < 1, 'o segundo ainda tem tempo e a fração de vida está entre 0 e 1');
    a.remover(c2.id, 'apagado');
    ok(a.total() === 0 && saiu[saiu.length - 1][1] === 'apagado', 'apagar tira na hora');
    a.adicionar({}); a.adicionar({}); a.adicionar({});
    const todos = a.limpar('fim');
    ok(todos.length === 3 && a.total() === 0 && saiu.filter(x => x[1] === 'fim').length === 3, 'a call acabou: todos somem, cada um avisando');
}
{
    const saiu = [];
    const a = ClipesArmazem.criar({ max: 3, aoSair: (c, m) => saiu.push(m) });
    for (let i = 0; i < 5; i++) a.adicionar({ n: i });
    ok(a.total() === 3 && saiu.filter(m => m === 'limite').length === 2, 'passou do limite: os mais antigos saem');
    ok(a.listar().map(c => c.n).join() === '4,3,2', 'ficam os 3 mais novos');
}

console.log(falhas ? `\n${falhas} de ${total} verificações FALHARAM` : `\nTudo certo: ${total} verificações`);
process.exit(falhas ? 1 : 0);
