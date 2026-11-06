/* Avisos de mensagem nova nos servidores e canais (Rodada 39). Objeto global `Avisos`.
 *
 * O servidor guarda até onde cada pessoa leu cada canal (app/avisos.py) e avisa ao vivo (`canal_atividade`). Aqui só se desenha:
 *   - ícone do servidor: número VERMELHO = quantas vezes te citaram; sem citação, uma pílula BRANCA na borda = tem coisa nova
 *   - pasta de servidores: soma dos de dentro
 *   - lista de canais: nome em destaque + número vermelho (citações) ou bolinha (não lida)
 *   - servidor silenciado (por aparelho): só as citações contam
 * Quem está olhando o canal (aba visível) não acumula nada: marca como lido na hora.
 */
const Avisos = (() => {
    'use strict';
    const MUDOS_CHAVE = 'pnt_srv_mudos';
    let ctx = null;
    let naoLidas = {};            // canalId -> quantidade (só mensagem de outras pessoas)
    let citacoes = {};            // canalId -> quantidade (vem da caixa de entrada: menções não lidas)
    const canalServidor = {};     // canalId -> serverId
    let agenda = 0, observador = null;

    const lerMudos = () => { try { return new Set(JSON.parse(localStorage.getItem(MUDOS_CHAVE) || '[]').map(Number)); } catch (e) { return new Set(); } };
    const gravarMudos = (s) => { try { localStorage.setItem(MUDOS_CHAVE, JSON.stringify([...s])); } catch (e) {} };

    function iniciar(c) {
        ctx = c;
        const socket = c.socket;
        socket.on('canais_nao_lidos', (mapa) => { naoLidas = {}; Object.entries(mapa || {}).forEach(([id, n]) => { naoLidas[Number(id)] = Number(n) || 0; }); pintar(); });
        socket.on('canal_atividade', (d) => {
            if (!d || Number(d.autor_id) === Number(ctx.meuId())) return;
            const canal = Number(d.canal_id);
            canalServidor[canal] = Number(d.server_id);
            if (olhando(canal)) { avisarLido(canal); return; }
            naoLidas[canal] = Math.min(99, (naoLidas[canal] || 0) + 1);
            pintar();
        });
        // outra aba ou aparelho meu leu: zera aqui também
        socket.on('canal_lido', (d) => {
            if (!d) return;
            const canal = Number(d.canal_id);
            delete naoLidas[canal];
            ctx.marcarMencoesLidas(canal);
            pintar();
        });
        // montar o mapa canal -> servidor sempre que a lista de servidores mudar, e repintar quando a barra lateral for redesenhada
        observador = new MutationObserver(() => agendar());
        const alvos = ['dynamic-servers-container', 'bazinga-sidebar'].map(i => document.getElementById(i)).filter(Boolean);
        alvos.forEach(a => observador.observe(a, { childList: true, subtree: true }));
        document.addEventListener('visibilitychange', () => { if (!document.hidden) lerAtual(); });
        window.addEventListener('focus', lerAtual);
    }

    function agendar() { if (!agenda) agenda = requestAnimationFrame(() => { agenda = 0; pintar(); }); }

    /** Estou com este canal aberto e olhando a tela agora? */
    function olhando(canal) {
        return ctx && String(ctx.canalAtual()) === String(canal) && ctx.vistaAtual() === 'server' && !document.hidden && document.hasFocus();
    }
    function avisarLido(canal) {
        if (!canal || !canalServidor[canal]) return;
        delete naoLidas[canal];
        ctx.socket.emit('canal_lido', { canal_id: Number(canal) });
        pintar();
    }
    function lerAtual() { const c = ctx && ctx.canalAtual(); if (c && olhando(c)) avisarLido(Number(c)); }

    /** O chat.html chama quando abre um canal de servidor. */
    function abriuCanal(canalId) {
        const c = Number(canalId);
        if (!c) return;
        if (!canalServidor[c]) montarMapa();
        avisarLido(c);     // sempre avisa o servidor: leva o ponto de leitura ao topo e dá por lidas as citações do canal
    }
    /** O chat.html chama a cada mensagem que chega no canal aberto (as que vêm pela sala do canal, não por canal_atividade). */
    function chegouNoAberto(canalId, autorId) {
        if (Number(autorId) === Number(ctx.meuId())) return;
        const c = Number(canalId);
        if (olhando(c)) avisarLido(c);
    }

    function montarMapa() {
        (ctx.servidores() || []).forEach(s => (s.channels || []).forEach(c => { canalServidor[Number(c.id)] = Number(s.id); }));
    }

    /** Recalcula as citações (menções não lidas) a partir da caixa de entrada: ref = "<servidor>:<canal>". */
    function contarCitacoes() {
        citacoes = {};
        (ctx.notificacoes() || []).forEach(n => {
            if (n.tipo !== 'mencao' || n.lida || !n.ref) return;
            const canal = Number(String(n.ref).split(':')[1]);
            if (canal) citacoes[canal] = (citacoes[canal] || 0) + (Number(n.quantidade) || 1);
        });
    }

    function pintar() {
        if (!ctx) return;
        montarMapa();
        contarCitacoes();
        const mudos = lerMudos();
        const porServidor = {};     // serverId -> {nao, cit}
        const todos = new Set([...Object.keys(naoLidas), ...Object.keys(citacoes)].map(Number));
        todos.forEach(canal => {
            const srv = canalServidor[canal]; if (!srv) return;
            const o = porServidor[srv] || (porServidor[srv] = { nao: 0, cit: 0 });
            o.cit += citacoes[canal] || 0;
            if (!mudos.has(srv)) o.nao += naoLidas[canal] || 0;
        });
        // ícones dos servidores
        document.querySelectorAll('.server-icon[id^="my-server-icon-"]').forEach(el => {
            const id = Number(el.id.replace('my-server-icon-', ''));
            aplicarNoIcone(el.closest('.server-wrapper') || el.parentElement, porServidor[id], mudos.has(id));
        });
        // pastas: soma dos servidores de dentro
        document.querySelectorAll('.pasta').forEach(p => {
            let nao = 0, cit = 0;
            p.querySelectorAll('.server-icon[id^="my-server-icon-"]').forEach(el => {
                const o = porServidor[Number(el.id.replace('my-server-icon-', ''))];
                if (o) { nao += o.nao; cit += o.cit; }
            });
            const cab = p.querySelector('.pasta-cabeca'); if (cab) aplicarBolha(cab, nao || cit ? { nao, cit } : null, 'pasta');
        });
        // lista de canais do servidor aberto
        document.querySelectorAll('.channels-list .text-channel[data-id], .channels-list .voice-channel[data-tipo="stream"][data-id]').forEach(el => {
            const id = Number(el.dataset.id), n = naoLidas[id] || 0, c = citacoes[id] || 0;
            el.classList.toggle('av-nova', (n > 0 || c > 0) && !el.classList.contains('active'));
            let b = el.querySelector(':scope > .av-canal');
            if (c > 0 && !el.classList.contains('active')) {
                if (!b) { b = document.createElement('span'); b.className = 'av-canal'; el.insertBefore(b, el.querySelector('.btn-config-channel')); }
                b.textContent = c > 99 ? '99+' : String(c); b.classList.add('cit');
            } else if (b) b.remove();
        });
        atualizarTitulo(porServidor);
        if (ctx.aoPintar) ctx.aoPintar({ porServidor });
    }

    function aplicarNoIcone(wrapper, o, mudo) {
        if (!wrapper) return;
        aplicarBolha(wrapper, o, 'icone', mudo);
    }
    function aplicarBolha(host, o, tipo, mudo) {
        let pil = host.querySelector(':scope > .av-pilula'), num = host.querySelector(':scope > .av-num');
        const nao = o ? o.nao : 0, cit = o ? o.cit : 0;
        // pílula branca (borda esquerda): tem mensagem nova, sem citação
        if (nao > 0 && cit === 0) { if (!pil) { pil = document.createElement('i'); pil.className = 'av-pilula'; host.prepend(pil); } }
        else if (pil) pil.remove();
        // número vermelho: te citaram
        if (cit > 0) {
            if (!num) { num = document.createElement('b'); num.className = 'av-num'; host.appendChild(num); }
            const t = cit > 99 ? '99+' : String(cit);
            if (num.textContent !== t) { num.textContent = t; num.classList.remove('pulo'); void num.offsetWidth; num.classList.add('pulo'); }
        } else if (num) num.remove();
        host.classList.toggle('av-tem', nao > 0 || cit > 0);
        host.classList.toggle('av-mudo', !!mudo);
    }

    function atualizarTitulo(porServidor) {
        let cit = 0; Object.values(porServidor).forEach(o => { cit += o.cit; });
        document.body.dataset.avCitacoes = String(cit);
    }

    // ---- silenciar servidor (neste aparelho) ----
    function silenciado(id) { return lerMudos().has(Number(id)); }
    function alternarMudo(id) {
        const s = lerMudos(), n = Number(id);
        if (s.has(n)) s.delete(n); else s.add(n);
        gravarMudos(s); pintar();
        return s.has(n);
    }
    function totalNaoLidas() { return Object.values(naoLidas).reduce((a, b) => a + b, 0); }

    return { iniciar, abriuCanal, chegouNoAberto, pintar, silenciado, alternarMudo, totalNaoLidas, _estado: () => ({ naoLidas, citacoes, canalServidor }) };
})();
