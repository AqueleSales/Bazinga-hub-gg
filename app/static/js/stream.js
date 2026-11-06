/* Canal de STREAM (tipo `stream`, Rodada 39): voz com chat ao lado e UMA tela por vez. Objeto global `Stream`.
 * A vez de transmitir é decidida no servidor (app/stream_events.py); aqui só se pede, se mostra quem é e se arruma o chat ao lado da call.
 *
 * Contexto (Stream.iniciar): { socket, meuId(), toast(msg, tipo), canalPorId(id), abrirChat(canal), fecharChat(), pararTelas(), souGerente(canalId) }
 * Eventos: stream_apresentador {canal_id, usuario_id|null, nome, peer_id?} · stream_tela_ok · stream_tela_negada {motivo} · stream_tela_cortada {por}
 * Segurança leve: o vídeo da call é P2P, então o servidor não corta a mídia: quem está num canal de stream só ACEITA tela de quem o servidor diz que é o apresentador.
 */
const Stream = (() => {
    'use strict';
    let ctx = null, canalId = null, ap = null, pendente = null;
    const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const $ = (id) => document.getElementById(id);

    function iniciar(c) {
        ctx = c;
        c.socket.on('stream_apresentador', (d) => {
            if (!d) return;
            pintarNaLista(d);
            if (String(d.canal_id) !== String(canalId)) return;
            // Quem está na call recebe DOIS avisos do mesmo apresentador: o completo (com peer_id) e o da prévia do servidor (só o nome).
            // O segundo não pode apagar o peer_id que o primeiro trouxe.
            const peerAntes = ap && Number(ap.usuario_id) === Number(d.usuario_id) ? ap.peer_id : null;
            ap = d.usuario_id ? { usuario_id: Number(d.usuario_id), nome: d.nome || '', peer_id: d.peer_id || peerAntes || null } : null;
            pintarBarra();
        });
        c.socket.on('stream_tela_ok', (d) => { if (pendente && String(d.canal_id) === String(canalId)) { const r = pendente; pendente = null; r(true); } });
        c.socket.on('stream_tela_negada', (d) => {
            if (d && d.motivo) c.toast(d.motivo, 'warning');
            if (pendente) { const r = pendente; pendente = null; r(false); }
        });
        c.socket.on('stream_tela_cortada', (d) => { c.pararTelas(); c.toast(`${(d && d.por) || 'A moderação'} tirou a sua transmissão do ar.`, 'warning'); });
    }

    const ativo = () => canalId != null;

    /** Entrou na call de um canal de stream: guarda, mostra a faixa e põe o chat do canal ao lado. */
    function aoEntrar(canal) {
        if (!ctx || !canal || canal.type !== 'stream') { aoSair(); return; }
        canalId = String(canal.id); ap = null;
        pintarBarra();
        ctx.abrirChat(canal);
    }
    function aoSair() {
        if (canalId == null) return;
        if (pendente) { const r = pendente; pendente = null; r(false); }
        canalId = null; ap = null;
        const b = $('st-barra'); if (b) b.remove();
        ctx.fecharChat();
    }
    /** A janela da call voltou pra tela cheia (ou foi minimizada): o chat acompanha. */
    function aoMostrar(modo) {
        if (!ativo()) return;
        if (modo === 'cheia') { const c = ctx.canalPorId(canalId); if (c) ctx.abrirChat(c, true); }
    }
    /** Quanto a janela cheia da call deixa livre pro chat (px). */
    function largura() { return ativo() ? 350 : 0; }

    /** Pede a vez de transmitir. Resolve true se o servidor liberou. Fora de canal de stream não há vez: sempre true. */
    function pedirTela() {
        if (!ativo()) return Promise.resolve(true);
        if (ap && Number(ap.usuario_id) === Number(ctx.meuId())) return Promise.resolve(true);
        return new Promise((resolve) => {
            pendente = resolve;
            ctx.socket.emit('stream_pedir_tela', { canal_id: canalId });
            setTimeout(() => { if (pendente === resolve) { pendente = null; resolve(false); ctx.toast('O servidor não respondeu. Tente de novo.', 'warning'); } }, 6000);
        });
    }
    function liberarTela(forcar) {
        if (!ativo()) return;
        ctx.socket.emit('stream_liberar_tela', { canal_id: canalId, forcar: !!forcar });
    }
    /** O peer é o apresentador? Espera um pouco o aviso do servidor (ele e a ligação P2P chegam por caminhos diferentes). */
    function aceitaTelaDe(peerId, ms = 4000) {
        if (!ativo()) return Promise.resolve(true);
        return new Promise((resolve) => {
            const fim = Date.now() + ms;
            (function olhar() {
                if (ap && ap.peer_id === peerId) return resolve(true);
                if (Date.now() >= fim || !ativo()) return resolve(false);
                setTimeout(olhar, 150);
            })();
        });
    }

    // ---------------------------------------------------------------------
    // desenho
    // ---------------------------------------------------------------------
    function pintarBarra() {
        const topo = $('cj-topo'); if (!topo) return;
        let b = $('st-barra');
        if (!b) {
            b = document.createElement('div'); b.id = 'st-barra'; b.className = 'st-barra';
            const titulo = $('cj-titulo'); topo.insertBefore(b, titulo ? titulo.nextSibling : topo.firstChild);
            b.addEventListener('click', (e) => {
                const x = e.target.closest('[data-st]'); if (!x) return;
                if (x.dataset.st === 'parar') ctx.pararTelas();
                else if (x.dataset.st === 'tirar') liberarTela(true);
            });
        }
        if (!ap) { b.innerHTML = '<span class="st-livre"><i class="fa-solid fa-tower-broadcast"></i> Ninguém transmitindo · compartilhe a sua tela</span>'; return; }
        const eu = Number(ap.usuario_id) === Number(ctx.meuId());
        b.innerHTML = `<span class="st-ao-vivo"><i class="fa-solid fa-circle"></i> AO VIVO</span><span class="st-quem">${eu ? 'Você está transmitindo' : esc(ap.nome) + ' está transmitindo'}</span>`
            + (eu ? '<button type="button" data-st="parar">Parar</button>' : (ctx.souGerente(canalId) ? '<button type="button" data-st="tirar" title="Tirar a transmissão do ar">Tirar do ar</button>' : ''));
    }
    /** O canal na lista do servidor mostra "ao vivo" mesmo pra quem não entrou. */
    function pintarNaLista(d) {
        const el = document.querySelector(`.voice-channel[data-id="${Number(d.canal_id)}"]`);
        if (!el) return;
        el.classList.toggle('st-no-ar', !!d.usuario_id);
        let tag = el.querySelector(':scope > .st-tag');
        if (d.usuario_id) {
            if (!tag) { tag = document.createElement('span'); tag.className = 'st-tag'; tag.textContent = 'AO VIVO'; el.insertBefore(tag, el.querySelector('.btn-config-channel')); }
            tag.title = `${d.nome || 'Alguém'} está transmitindo`;
        } else if (tag) tag.remove();
    }

    return { iniciar, ativo, aoEntrar, aoSair, aoMostrar, largura, pedirTela, liberarTela, aceitaTelaDe, _estado: () => ({ canalId, ap }) };
})();
