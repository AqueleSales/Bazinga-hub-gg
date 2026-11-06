/* Call híbrida P2P + SFU (Rodada 39): PREPARAÇÃO. Global `CallTransporte`. Veja app/sfu.py e docs/PLANO_SFU.md.
 *
 * O que este arquivo FAZ hoje: guarda a política que o servidor mandou (CALL_POLITICA, entregue no iniciar({ socket, politica })), escuta o aviso "esta call mudou de transporte" (`call_transporte`),
 * sabe pedir o token de entrada do SFU (`sfu_pedir_token` -> `sfu_token`) e define o CONTRATO do adaptador que vai falar com o SFU.
 * O que NÃO faz: conectar no SFU. Ninguém registrou um adaptador ainda (precisa da biblioteca livekit-client + um SFU de verdade pra testar), então
 * `transporteDaCall()` responde SEMPRE 'p2p' e a call segue exatamente como era: ligar as variáveis do servidor sem o adaptador não muda nada.
 *
 * Contrato do adaptador (`CallTransporte.registrar('sfu', adaptador)`):
 *   conectar({ url, token, sala, identidade, aoFaixaRemota(identidade, tipo, stream), aoFaixaRemovida(identidade, tipo), aoFalando(identidades) }) -> Promise
 *   publicar(tipo, mediaStreamTrack)   // tipo: 'microphone' | 'camera' | 'screen_share' | 'screen_share_audio'
 *   parar(tipo)
 *   desconectar() -> Promise
 * Quando o adaptador existir, quem liga a call chama `CallTransporte.transporteDaCall(canalId)` ANTES de abrir o PeerJS: 'sfu' = conectar() com o token de
 * `pedirToken()`; 'p2p' = o fluxo de sempre. O servidor só manda 'sfu' depois de passar do limite de pessoas (ou com CALL_MODE=sfu).
 */
const CallTransporte = (function () {
    'use strict';
    const PADRAO = { modo: 'p2p', sfu: false, limite_p2p: 4, url: '' };
    // A política vem do servidor pelo iniciar() (o <script> deste arquivo carrega ANTES da constante CALL_POLITICA do chat.html: ler aqui em cima daria sempre o padrão).
    let POLITICA = PADRAO;
    const adaptadores = {};
    const porCall = {};            // canal_id -> 'p2p' | 'sfu' (o que o SERVIDOR decidiu)
    const esperando = {};          // canal_id -> { ok(), erro(), timer }
    let ctx = null, avisou = false;

    function pronto() { return !!(POLITICA.sfu && adaptadores.sfu); }

    /** 'sfu' só se o servidor mandou E existe um adaptador pra falar com ele. Senão 'p2p' (o único que existe hoje). */
    function transporteDaCall(canalId) {
        return pronto() && porCall[String(canalId)] === 'sfu' ? 'sfu' : 'p2p';
    }

    function registrar(nome, adaptador) {
        if (nome !== 'sfu' || !adaptador) return false;
        for (const f of ['conectar', 'publicar', 'parar', 'desconectar']) {
            if (typeof adaptador[f] !== 'function') { console.warn('[call] adaptador de SFU incompleto: falta ' + f + '()'); return false; }
        }
        adaptadores.sfu = adaptador;
        return true;
    }

    /** Pede ao servidor a entrada na sala do SFU. Resolve com { ok, url, token, sala, identidade, publica, tela } ou { ok: false, motivo }. */
    function pedirToken(canalId) {
        const chave = String(canalId);
        return new Promise((resolve) => {
            if (!ctx || !POLITICA.sfu) { resolve({ ok: false, motivo: 'desligado' }); return; }
            if (esperando[chave]) { clearTimeout(esperando[chave].timer); }
            esperando[chave] = {
                ok: resolve,
                timer: setTimeout(() => { delete esperando[chave]; resolve({ ok: false, motivo: 'sem_resposta' }); }, 8000)
            };
            ctx.socket.emit('sfu_pedir_token', { canal_id: chave });
        });
    }

    function iniciar(c) {
        ctx = c;
        POLITICA = (c.politica && typeof c.politica === 'object') ? Object.assign({}, PADRAO, c.politica, { sfu: c.politica.sfu === true }) : PADRAO;
        c.socket.on('call_transporte', (d) => {
            if (!d || typeof d !== 'object') return;
            porCall[String(d.canal_id)] = d.transporte === 'sfu' ? 'sfu' : 'p2p';
            if (d.transporte === 'sfu' && !pronto() && !avisou) {
                avisou = true;      // uma vez só, e só no console: o usuário não precisa saber, a call continua como era
                console.info('[call] o servidor pediu o SFU, mas este navegador ainda não tem o adaptador: a call segue em P2P.');
            }
        });
        c.socket.on('sfu_token', (d) => {
            if (!d || typeof d !== 'object') return;
            const e = esperando[String(d.canal_id)];
            if (!e) return;
            clearTimeout(e.timer);
            delete esperando[String(d.canal_id)];
            e.ok(d.ok ? { ok: true, url: String(d.url || ''), token: String(d.token || ''), sala: String(d.sala || ''), identidade: String(d.identidade || ''),
                          publica: !!d.publica, tela: !!d.tela, expira_em: Number(d.expira_em) || 0 } : { ok: false, motivo: String(d.motivo || 'erro') });
        });
    }

    /** A call acabou (saí ou esvaziou): esquece o que o servidor tinha dito dela. */
    function aoSairDaCall(canalId) { delete porCall[String(canalId)]; }

    function estado() { return { politica: POLITICA, adaptador: !!adaptadores.sfu, porCall: Object.assign({}, porCall) }; }

    return { iniciar, registrar, pedirToken, transporteDaCall, aoSairDaCall, estado, pronto };
})();
