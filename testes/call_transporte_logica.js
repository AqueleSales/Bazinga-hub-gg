// Rodada 39: o módulo call_transporte.js rodando no Node, com um "socket" de mentira. Imprime OK/FALHA por verificação.
const fs = require('fs');
const path = require('path');
const fonte = fs.readFileSync(path.join(__dirname, '..', 'app', 'static', 'js', 'call_transporte.js'), 'utf8');
let falhas = 0;
const ok = (c, m) => { console.log((c ? 'OK   ' : 'FALHA') + ' ' + m); if (!c) falhas++; };

function socketFalso() {
    const ouvintes = {}, enviados = [];
    return { on: (n, f) => { ouvintes[n] = f; }, emit: (n, d) => enviados.push([n, d]), disparar: (n, d) => ouvintes[n] && ouvintes[n](d), enviados };
}
function carregar() {
    const logs = [];
    const consola = { info: (...a) => logs.push(['info', a.join(' ')]), warn: (...a) => logs.push(['warn', a.join(' ')]), log() {} };
    const f = new Function('console', fonte + '\n; return CallTransporte;');   // CALL_POLITICA NÃO existe quando o arquivo carrega: a política entra pelo iniciar()
    return { T: f(consola), logs };
}
const adaptadorOk = { conectar: async () => {}, publicar() {}, parar() {}, desconectar: async () => {} };

(async () => {
    // --- sem política (página velha ou SFU desligado) ---
    let { T, logs } = carregar();
    let s = socketFalso(); T.iniciar({ socket: s });
    ok(T.transporteDaCall('4') === 'p2p' && T.pronto() === false, 'sem política: tudo P2P');
    s.disparar('call_transporte', { canal_id: '4', transporte: 'sfu' });
    ok(T.transporteDaCall('4') === 'p2p' && logs.filter(l => l[0] === 'info').length === 1, 'o servidor pede SFU mas não há adaptador nem política: segue P2P e só avisa no console (1x)');
    s.disparar('call_transporte', { canal_id: '5', transporte: 'sfu' });
    ok(logs.filter(l => l[0] === 'info').length === 1, 'o aviso do console não se repete');
    ok((await T.pedirToken('4')).motivo === 'desligado' && s.enviados.length === 0, 'pedir token com o SFU desligado nem chega a falar com o servidor');

    // --- SFU ligado no servidor, mas o navegador ainda não tem adaptador ---
    ({ T, logs } = carregar());
    s = socketFalso(); T.iniciar({ socket: s, politica: { modo: 'auto', sfu: true, limite_p2p: 4, url: 'wss://sfu.exemplo.com' } });
    s.disparar('call_transporte', { canal_id: '4', transporte: 'sfu' });
    ok(T.pronto() === false && T.transporteDaCall('4') === 'p2p', 'com SFU configurado mas SEM adaptador, a call continua P2P');

    // --- adaptador ---
    ok(T.registrar('sfu', { conectar() {} }) === false && T.pronto() === false, 'adaptador incompleto é recusado (e avisa o que falta)');
    ok(logs.some(l => l[0] === 'warn' && /publicar/.test(l[1])), '  ...dizendo qual função falta');
    ok(T.registrar('outro', adaptadorOk) === false && T.registrar('sfu', null) === false, 'só o nome "sfu" e só com um adaptador');
    ok(T.registrar('sfu', adaptadorOk) === true && T.pronto() === true, 'adaptador completo é aceito');
    ok(T.transporteDaCall('4') === 'sfu' && T.transporteDaCall('9') === 'p2p', 'SFU só pra call que o servidor marcou; as outras seguem P2P');
    s.disparar('call_transporte', { canal_id: '4', transporte: 'qualquer coisa' });
    ok(T.transporteDaCall('4') === 'p2p', 'transporte desconhecido vira P2P');
    s.disparar('call_transporte', { canal_id: '4', transporte: 'sfu' }); s.disparar('call_transporte', null); s.disparar('call_transporte', 'texto'); s.disparar('call_transporte', 7);
    ok(T.transporteDaCall('4') === 'sfu', 'aviso malformado não derruba nem muda nada');
    T.aoSairDaCall('4');
    ok(T.transporteDaCall('4') === 'p2p', 'saiu da call: esquece o transporte');

    // --- token ---
    const p = T.pedirToken('4');
    ok(s.enviados.length === 1 && s.enviados[0][0] === 'sfu_pedir_token' && s.enviados[0][1].canal_id === '4', 'pedirToken fala com o servidor (só o id da call)');
    s.disparar('sfu_token', { ok: true, canal_id: '4', url: 'wss://sfu.exemplo.com', token: 'a.b.c', sala: 'pantheon-4', identidade: 'u7', publica: true, tela: false, expira_em: 600, intruso: 'x' });
    const r = await p;
    ok(r.ok && r.token === 'a.b.c' && r.sala === 'pantheon-4' && r.identidade === 'u7' && r.expira_em === 600 && !('intruso' in r), 'o token chega e só os campos conhecidos passam');
    const p2 = T.pedirToken('4');
    s.disparar('sfu_token', { ok: false, canal_id: '4', motivo: 'p2p' });
    ok((await p2).ok === false && (await p2).motivo === 'p2p', 'recusa do servidor chega com o motivo');
    s.disparar('sfu_token', { ok: true, canal_id: '77', token: 'x' });
    ok(true, 'token que ninguém pediu é ignorado sem erro');
    const e = T.estado();
    ok(e.adaptador === true && e.politica.sfu === true && !JSON.stringify(e).includes('token'), 'estado() não carrega token');

    // política torta (texto, sfu como texto "true") nunca liga o SFU
    ({ T } = carregar()); T.iniciar({ socket: socketFalso(), politica: { sfu: 'true', modo: 'sfu' } }); T.registrar('sfu', adaptadorOk);
    ok(T.pronto() === false, 'política com sfu como TEXTO não liga o SFU (só o booleano true)');
    ({ T } = carregar()); T.iniciar({ socket: socketFalso(), politica: 'sfu' });
    ok(T.estado().politica.sfu === false, 'política que não é objeto vira o padrão');

    ok(!/eval\(|new Function|innerHTML|document\.write/.test(fonte), 'o módulo não usa eval, innerHTML nem document.write');
    console.log(falhas ? falhas + ' FALHA(S)' : 'TUDO OK');
    process.exit(falhas ? 1 : 0);
})();
