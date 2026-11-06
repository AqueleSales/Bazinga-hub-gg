/* Acervo (Rodada 39): figurinhas, soundboard e som de entrada na call. Objeto global `Acervo`. Regras e moderação: app/acervo.py (Guardião olha tudo antes).
 *
 * Contexto (Acervo.iniciar): { socket, esc, escUrl, toast, confirmar(titulo, texto, ok), meuId(), servidorAtivo(), canalDaCall(), emCall(), amSouOuvinte(),
 *   enviarFigurinha(item, destino), abrirEmoji(botao, cb) }
 * Eventos: acervo (a lista) · acervo_mudou · acervo_erro · som_entrada_ok · soundboard_tocou
 * Arquivo entra por POST /api/acervo/upload e sai por GET /api/acervo/<id>/arquivo (só o que está APROVADO; o resto só o dono e os responsáveis).
 */
const Acervo = (() => {
    'use strict';
    const COTA_TEXTO = { figurinha: 'figurinhas', som: 'sons' };
    let C = null, dados = null, pedido = null;
    let figPainel = null, gerJanela = null, sbPainel = null, envio = null;
    const estado = { gerTipo: 'figurinha', gerEscopo: 'pessoa', sbEscopo: 'pessoa', figAba: 'meus', figDestino: 'canal' };
    const $ = (id) => document.getElementById(id);
    const mudo = () => { try { return localStorage.getItem('pnt_sb_mudo') === '1'; } catch (e) { return false; } };
    const volSb = () => { try { const v = parseFloat(localStorage.getItem('pnt_sb_vol')); return isFinite(v) ? Math.max(0, Math.min(1, v)) : .7; } catch (e) { return .7; } };
    const guardar = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
    const esc = (v) => C.esc(v);

    function iniciar(ctx) {
        C = ctx;
        C.socket.on('acervo', (d) => { dados = d; atualizarTudo(); });
        C.socket.on('acervo_mudou', (d) => { if (!d || !d.server_id || Number(d.server_id) === Number((C.servidorAtivo() || {}).id)) carregar(); });
        C.socket.on('acervo_erro', (d) => C.toast((d && d.msg) || 'Não deu certo.', 'warning'));
        C.socket.on('som_entrada_ok', (d) => { if (dados) dados.som_entrada = d.valor; C.aoMudarSomEntrada && C.aoMudarSomEntrada(d.valor); pintarSomEntrada(); });
        C.socket.on('soundboard_tocou', (d) => {
            if (!d) return;
            if (!mudo()) Sons.tocarItem(Number(d.item_id), volSb());
            aviso(d);
        });
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { if (envio) fecharEnvio(); else if (gerJanela) fecharGer(); else if (figPainel) fecharFig(); } }, true);
        document.addEventListener('mousedown', (e) => { if (figPainel && !e.target.closest('#ac-fig') && !e.target.closest('[data-abre-fig]')) fecharFig(); });
    }

    // ---------------------------------------------------------------------
    // dados
    // ---------------------------------------------------------------------
    function carregar() {
        const srv = C.servidorAtivo();
        clearTimeout(pedido);
        pedido = setTimeout(() => C.socket.emit('acervo_listar', { server_id: srv ? srv.id : undefined }), 120);
    }
    const meus = (tipo) => (dados && dados.meus[tipo]) || [];
    const doServidor = (tipo) => (dados && dados.servidor && dados.servidor[tipo]) || [];
    const aprovados = (l) => l.filter(i => i.status === 'aprovado');
    function atualizarTudo() { if (figPainel) pintarFig(); if (gerJanela) pintarGer(); if (sbPainel) pintarSb(); pintarSomEntrada(); }
    function meuSomEntrada() { return dados ? dados.som_entrada || null : (C && C.somEntradaInicial) || null; }

    // ---------------------------------------------------------------------
    // figurinhas: o painel ao lado do campo de mensagem
    // ---------------------------------------------------------------------
    function abrirFiguras(botao, destino) {
        if (figPainel) { fecharFig(); return; }
        estado.figDestino = destino || 'canal';
        figPainel = document.createElement('div');
        figPainel.id = 'ac-fig'; figPainel.className = 'ac-fig';
        document.body.appendChild(figPainel);
        const r = botao.getBoundingClientRect();
        figPainel.style.right = Math.max(8, window.innerWidth - r.right - 8) + 'px';
        figPainel.style.bottom = Math.max(8, window.innerHeight - r.top + 10) + 'px';
        figPainel.addEventListener('click', (e) => {
            const b = e.target.closest('[data-ac]'); if (!b) return;
            const a = b.dataset.ac;
            if (a === 'aba') { estado.figAba = b.dataset.v; pintarFig(); }
            else if (a === 'add') { fecharFig(); abrirEnvio('figurinha', estado.figAba === 'srv' && dados && dados.servidor && dados.servidor.gerencia ? 'servidor' : 'pessoa'); }
            else if (a === 'gerir') { fecharFig(); abrirGer('figurinha', estado.figAba === 'srv' ? 'servidor' : 'pessoa'); }
            else if (a === 'usar') {
                const item = [...meus('figurinha'), ...doServidor('figurinha')].find(i => i.id === Number(b.dataset.id));
                if (!item) return;
                if (item.status !== 'aprovado') { C.toast('Essa figurinha ainda está em análise: só você vê. Quando o Guardião liberar, dá pra mandar.', 'info'); return; }
                fecharFig(); C.enviarFigurinha(item, estado.figDestino);
            }
        });
        pintarFig(); carregar();
    }
    function fecharFig() { if (figPainel) { figPainel.remove(); figPainel = null; } }
    function figItem(i) {
        const analise = i.status !== 'aprovado';
        return `<button type="button" class="ac-fi ${analise ? 'analise' : ''}" data-ac="usar" data-id="${Number(i.id)}" title="${esc(i.nome)}${analise ? ' (em análise)' : ''}">
            <img src="${C.escUrl(i.url)}" alt="${esc(i.nome)}" loading="lazy">${analise ? '<span class="ac-sel">em análise</span>' : ''}</button>`;
    }
    function pintarFig() {
        if (!figPainel) return;
        const tem = !!(dados && dados.servidor);
        if (estado.figAba === 'srv' && !tem) estado.figAba = 'meus';
        const lista = estado.figAba === 'srv' ? doServidor('figurinha') : meus('figurinha');
        figPainel.innerHTML = `<div class="ac-fig-topo">
                <button type="button" class="${estado.figAba === 'meus' ? 'on' : ''}" data-ac="aba" data-v="meus">Minhas</button>
                ${tem ? `<button type="button" class="${estado.figAba === 'srv' ? 'on' : ''}" data-ac="aba" data-v="srv">${esc(dados.servidor.nome || 'Servidor')}</button>` : ''}
                <span class="ac-esp"></span>
                <button type="button" class="ic" data-ac="add" title="Enviar uma figurinha"><i class="fa-solid fa-plus"></i></button>
                <button type="button" class="ic" data-ac="gerir" title="Gerenciar"><i class="fa-solid fa-gear"></i></button></div>
            <div class="ac-fig-grade">${lista.length ? lista.map(figItem).join('') : `<div class="ac-vazio"><i class="fa-regular fa-note-sticky"></i><b>Nenhuma figurinha ainda</b><small>${estado.figAba === 'srv' ? 'O servidor ainda não tem figurinhas.' : 'Toque no + e mande uma imagem (PNG, WebP, GIF ou JPG). O Guardião confere antes de os outros verem.'}</small></div>`}</div>`;
    }

    // ---------------------------------------------------------------------
    // gerenciar (apagar, renomear, enviar)
    // ---------------------------------------------------------------------
    function abrirGer(tipo, escopo) {
        if (tipo) estado.gerTipo = tipo;
        if (escopo) estado.gerEscopo = escopo;
        if (!gerJanela) {
            gerJanela = document.createElement('div');
            gerJanela.id = 'ac-ger'; gerJanela.className = 'modal-overlay ac-fundo'; gerJanela.style.display = 'flex';
            document.body.appendChild(gerJanela);
            gerJanela.addEventListener('mousedown', (e) => { if (e.target === gerJanela) fecharGer(); });
            gerJanela.addEventListener('click', clicarGer);
        }
        pintarGer(); carregar();
    }
    function fecharGer() { if (gerJanela) { gerJanela.remove(); gerJanela = null; } }
    function pintarGer() {
        if (!gerJanela) return;
        const srv = dados && dados.servidor;
        if (estado.gerEscopo === 'servidor' && !srv) estado.gerEscopo = 'pessoa';
        const lista = (estado.gerEscopo === 'servidor' ? doServidor(estado.gerTipo) : meus(estado.gerTipo));
        const cota = dados ? dados.cotas[estado.gerEscopo][estado.gerTipo] : '';
        const pode = estado.gerEscopo === 'pessoa' || (srv && srv.gerencia);
        const sons = estado.gerTipo === 'som';
        gerJanela.innerHTML = `<div class="ac-cartao" role="dialog" aria-modal="true" aria-label="Figurinhas e sons">
            <div class="ac-topo"><h3><i class="fa-solid fa-note-sticky"></i> Figurinhas e sons</h3><button type="button" class="ac-x" data-ac="fechar" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button></div>
            <div class="ac-abas"><button type="button" class="${!sons ? 'on' : ''}" data-ac="tipo" data-v="figurinha">Figurinhas</button><button type="button" class="${sons ? 'on' : ''}" data-ac="tipo" data-v="som">Sons</button>
                <span class="ac-esp"></span>
                <button type="button" class="${estado.gerEscopo === 'pessoa' ? 'on' : ''}" data-ac="escopo" data-v="pessoa">Meus</button>
                ${srv ? `<button type="button" class="${estado.gerEscopo === 'servidor' ? 'on' : ''}" data-ac="escopo" data-v="servidor">${esc(srv.nome || 'Servidor')}</button>` : ''}</div>
            <div class="ac-corpo">
                <p class="ac-dica">${sons ? 'Sons curtos (até 6 s) pro seu soundboard e pra tocar quando você entra na call.' : 'Imagens que você manda no chat e na DM.'} O <b>Guardião confere tudo antes de os outros verem ou ouvirem</b>; enquanto está em análise, só você vê.
                    ${estado.gerEscopo === 'servidor' && !pode ? ' Só quem gerencia o servidor adiciona ou apaga aqui.' : ''}</p>
                <div class="${sons ? 'ac-lista' : 'ac-grade'}">${lista.map(i => sons ? somLinha(i, pode || i.meu) : figCartao(i, pode || i.meu)).join('') || `<div class="ac-vazio"><b>Nada por aqui ainda</b></div>`}</div>
            </div>
            <div class="ac-rodape"><small>${lista.length}${cota ? ' de ' + cota : ''} ${COTA_TEXTO[estado.gerTipo]}</small>
                ${pode ? `<button type="button" class="btn-primary" data-ac="enviar"><i class="fa-solid fa-plus"></i> Enviar ${sons ? 'um som' : 'uma figurinha'}</button>` : ''}</div></div>`;
    }
    function figCartao(i, pode) {
        return `<div class="ac-fc" data-id="${Number(i.id)}"><div class="ac-fc-img"><img src="${C.escUrl(i.url)}" alt="" loading="lazy">${i.status !== 'aprovado' ? '<span class="ac-sel">em análise</span>' : ''}</div>
            <div class="ac-fc-nome" title="${esc(i.nome)}">${esc(i.nome)}</div>${pode ? `<div class="ac-fc-acoes"><button type="button" data-ac="renomear" data-id="${Number(i.id)}" title="Renomear"><i class="fa-solid fa-pen"></i></button><button type="button" data-ac="apagar" data-id="${Number(i.id)}" title="Apagar"><i class="fa-solid fa-trash"></i></button></div>` : ''}</div>`;
    }
    function somLinha(i, pode) {
        return `<div class="ac-sl" data-id="${Number(i.id)}"><button type="button" class="ac-play" data-ac="ouvir" data-id="${Number(i.id)}" title="Ouvir"><i class="fa-solid fa-play"></i></button>
            <span class="ac-sl-emoji">${esc(i.emoji || '🔊')}</span><span class="ac-sl-nome">${esc(i.nome)}</span><small>${i.dur_ms ? (i.dur_ms / 1000).toFixed(1).replace('.', ',') + ' s' : ''}</small>
            ${i.status !== 'aprovado' ? '<span class="ac-sel">em análise</span>' : ''}
            ${pode ? `<button type="button" data-ac="renomear" data-id="${Number(i.id)}" title="Renomear"><i class="fa-solid fa-pen"></i></button><button type="button" data-ac="apagar" data-id="${Number(i.id)}" title="Apagar"><i class="fa-solid fa-trash"></i></button>` : ''}</div>`;
    }
    function acharItem(id) { return [...meus('figurinha'), ...meus('som'), ...doServidor('figurinha'), ...doServidor('som')].find(i => i.id === Number(id)); }
    function clicarGer(e) {
        const b = e.target.closest('[data-ac]'); if (!b) return;
        const a = b.dataset.ac, item = b.dataset.id ? acharItem(b.dataset.id) : null;
        if (a === 'fechar') fecharGer();
        else if (a === 'tipo') { estado.gerTipo = b.dataset.v; pintarGer(); }
        else if (a === 'escopo') { estado.gerEscopo = b.dataset.v; pintarGer(); }
        else if (a === 'enviar') abrirEnvio(estado.gerTipo, estado.gerEscopo);
        else if (a === 'ouvir' && item) { if (!Sons.tocarItem(item.id)) C.toast('Ative o som do app pra ouvir (Configurações > Voz e vídeo > Sons).', 'info'); }
        else if (a === 'apagar' && item) C.confirmar('Apagar?', `"${item.nome}" some pra todo mundo que usava.`, () => C.socket.emit('acervo_apagar', { id: item.id }));
        else if (a === 'renomear' && item) {
            const novo = prompt('Novo nome (até 24 letras):', item.nome);
            if (novo && novo.trim()) C.socket.emit('acervo_renomear', { id: item.id, nome: novo.trim(), emoji: item.emoji || '' });
        }
    }

    // ---------------------------------------------------------------------
    // enviar um arquivo
    // ---------------------------------------------------------------------
    function wavDe(pcm, taxa) {
        const n = pcm.length, buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf);
        const txt = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
        txt(0, 'RIFF'); v.setUint32(4, 36 + n * 2, true); txt(8, 'WAVE'); txt(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
        v.setUint32(24, taxa, true); v.setUint32(28, taxa * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); txt(36, 'data'); v.setUint32(40, n * 2, true);
        for (let i = 0; i < n; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, pcm[i])) * 32767, true);
        return new Blob([buf], { type: 'audio/wav' });
    }
    /** Corta [ini, fim] do áudio, mistura em mono a 22,05 kHz, segura o pico (nada de estourar o ouvido de ninguém) e dá um fade no fim. Sai um WAV de até ~265 KB. */
    async function prepararSom(buf, ini, fim) {
        const taxa = 22050, dur = Math.max(.1, Math.min(Sons.MAX_S, fim - ini));
        const off = new OfflineAudioContext(1, Math.ceil(dur * taxa), taxa);
        const s = off.createBufferSource(); s.buffer = buf; s.connect(off.destination); s.start(0, ini, dur);
        const pcm = (await off.startRendering()).getChannelData(0).slice();
        let pico = 0; for (let i = 0; i < pcm.length; i++) pico = Math.max(pico, Math.abs(pcm[i]));
        const k = pico > .85 ? .85 / pico : 1; for (let i = 0; i < pcm.length; i++) pcm[i] *= k;
        const f = Math.min(pcm.length, Math.floor(taxa * .04)); for (let i = 0; i < f; i++) pcm[pcm.length - 1 - i] *= i / f;
        return { blob: wavDe(pcm, taxa), dur_ms: Math.round(dur * 1000) };
    }
    function abrirEnvio(tipo, escopo) {
        fecharEnvio();
        const sons = tipo === 'som', srv = dados && dados.servidor;
        envio = { tipo, escopo: escopo === 'servidor' && srv && srv.gerencia ? 'servidor' : 'pessoa', arquivo: null, buf: null, ini: 0, fim: 0 };
        const f = document.createElement('div');
        f.id = 'ac-envio'; f.className = 'modal-overlay ac-fundo'; f.style.display = 'flex'; f.style.zIndex = '10560';
        f.innerHTML = `<div class="ac-cartao estreito" role="dialog" aria-modal="true" aria-label="Enviar">
            <div class="ac-topo"><h3><i class="fa-solid ${sons ? 'fa-volume-high' : 'fa-note-sticky'}"></i> Enviar ${sons ? 'um som' : 'uma figurinha'}</h3><button type="button" class="ac-x" data-ac="x" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button></div>
            <div class="ac-corpo">
                <label class="ac-solta" id="ac-solta"><input type="file" id="ac-arq" accept="${sons ? 'audio/*,.mp3,.ogg,.wav,.m4a' : 'image/png,image/webp,image/gif,image/jpeg'}" hidden>
                    <i class="fa-solid fa-cloud-arrow-up"></i><b id="ac-solta-t">Escolher o arquivo</b><small>${sons ? 'MP3, OGG, WAV ou M4A. O som é cortado em até 6 segundos e o volume é limitado.' : 'PNG, WebP, GIF ou JPG até 3 MB. Ela é reduzida pra caber (320 px).'}</small></label>
                <div id="ac-previa" class="ac-previa" hidden></div>
                <div class="ac-campo"><label for="ac-nome">Nome</label><input id="ac-nome" maxlength="24" placeholder="${sons ? 'Ex.: Aplauso' : 'Ex.: Gatinho feliz'}" autocomplete="off"></div>
                ${sons ? `<div class="ac-campo"><label>Ícone do botão <small>(emoji, opcional)</small></label><button type="button" class="ac-emoji" id="ac-emoji" data-abre-emoji><span id="ac-emoji-v">🔊</span></button></div>` : ''}
                ${srv && srv.gerencia ? `<div class="ac-campo"><label>Pra quem</label><div class="ac-seg"><button type="button" data-ac="para" data-v="pessoa" class="${envio.escopo === 'pessoa' ? 'on' : ''}">Só pra mim</button><button type="button" data-ac="para" data-v="servidor" class="${envio.escopo === 'servidor' ? 'on' : ''}">${esc(srv.nome || 'O servidor')}</button></div></div>` : ''}
                <p class="ac-erro" id="ac-erro" hidden></p>
                <p class="ac-nota"><i class="fa-solid fa-shield-halved"></i> O Guardião confere antes de os outros ${sons ? 'ouvirem' : 'verem'}. Sem a análise automática, uma pessoa responsável decide.</p>
            </div>
            <div class="ac-rodape"><button type="button" class="btn-cancel" data-ac="x">Cancelar</button><button type="button" class="btn-primary" data-ac="mandar" id="ac-mandar" disabled><i class="fa-solid fa-paper-plane"></i> Enviar</button></div></div>`;
        document.body.appendChild(f); envio.el = f;
        const erro = (m) => { const e = $('ac-erro'); e.hidden = !m; e.textContent = m || ''; };
        f.addEventListener('mousedown', (e) => { if (e.target === f) fecharEnvio(); });
        f.addEventListener('click', async (e) => {
            const b = e.target.closest('[data-ac]'); if (!b) return;
            const a = b.dataset.ac;
            if (a === 'x') fecharEnvio();
            else if (a === 'para') { envio.escopo = b.dataset.v; f.querySelectorAll('[data-ac="para"]').forEach(x => x.classList.toggle('on', x === b)); }
            else if (a === 'ouvirpedaco' && envio.buf) { const p = await prepararSom(envio.buf, envio.ini, envio.fim); const ac = (C.audioCtx && C.audioCtx()); if (ac) { const d = await p.blob.arrayBuffer(); ac.decodeAudioData(d, (bf) => { const s = ac.createBufferSource(); s.buffer = bf; s.connect(ac.destination); s.start(); }); } }
            else if (a === 'mandar') await mandar(erro);
        });
        if (sons) $('ac-emoji').addEventListener('click', (e) => { e.stopPropagation(); if (C.abrirEmoji) C.abrirEmoji(e.currentTarget, (em) => { $('ac-emoji-v').textContent = em; $('ac-emoji').dataset.v = em; }); });
        $('ac-arq').addEventListener('change', async (e) => {
            const arq = e.target.files && e.target.files[0]; if (!arq) return;
            erro(''); envio.arquivo = arq; $('ac-solta-t').textContent = arq.name;
            if (!$('ac-nome').value) $('ac-nome').value = arq.name.replace(/\.[^.]+$/, '').slice(0, 24);
            const prev = $('ac-previa'); prev.hidden = false;
            if (!sons) { prev.innerHTML = `<img alt="" src="${URL.createObjectURL(arq)}">`; $('ac-mandar').disabled = false; return; }
            prev.innerHTML = '<small>Lendo o áudio...</small>'; $('ac-mandar').disabled = true;
            try {
                const ac = (C.audioCtx && C.audioCtx()) || new (window.AudioContext || window.webkitAudioContext)();
                const bytes = await arq.arrayBuffer();
                envio.buf = await new Promise((ok, no) => ac.decodeAudioData(bytes, ok, no));
            } catch (er) { prev.innerHTML = ''; prev.hidden = true; erro('Não consegui abrir esse áudio. Tente um MP3, OGG ou WAV.'); return; }
            const dur = envio.buf.duration; envio.ini = 0; envio.fim = Math.min(dur, Sons.MAX_S);
            prev.innerHTML = `<div class="ac-corte"><div><label>Começo <b id="ac-i-v">0,0 s</b></label><input type="range" id="ac-ini" min="0" max="${dur.toFixed(2)}" step="0.05" value="0"></div>
                <div><label>Fim <b id="ac-f-v">${envio.fim.toFixed(1).replace('.', ',')} s</b></label><input type="range" id="ac-fim" min="0" max="${dur.toFixed(2)}" step="0.05" value="${envio.fim}"></div>
                <small id="ac-corte-info">${dur.toFixed(1).replace('.', ',')} s no arquivo. Fica no máximo ${Sons.MAX_S} s.</small>
                <button type="button" class="ac-play-g" data-ac="ouvirpedaco"><i class="fa-solid fa-play"></i> Ouvir o pedaço</button></div>`;
            const ajusta = (de) => {
                let i = parseFloat($('ac-ini').value), fi = parseFloat($('ac-fim').value);
                if (de === 'ini' && fi - i > Sons.MAX_S) fi = i + Sons.MAX_S; if (de === 'fim' && fi - i > Sons.MAX_S) i = fi - Sons.MAX_S;
                if (fi - i < .2) { if (de === 'ini') fi = Math.min(dur, i + .2); else i = Math.max(0, fi - .2); }
                envio.ini = Math.max(0, i); envio.fim = Math.min(dur, fi); $('ac-ini').value = envio.ini; $('ac-fim').value = envio.fim;
                $('ac-i-v').textContent = envio.ini.toFixed(1).replace('.', ',') + ' s'; $('ac-f-v').textContent = envio.fim.toFixed(1).replace('.', ',') + ' s';
            };
            $('ac-ini').addEventListener('input', () => ajusta('ini')); $('ac-fim').addEventListener('input', () => ajusta('fim'));
            $('ac-mandar').disabled = false;
        });
    }
    function fecharEnvio() { if (envio && envio.el) envio.el.remove(); envio = null; }
    async function mandar(erro) {
        if (!envio || !envio.arquivo) { erro('Escolha um arquivo primeiro.'); return; }
        const btn = $('ac-mandar'); btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enviando...';
        try {
            const fd = new FormData(), sons = envio.tipo === 'som', srv = C.servidorAtivo();
            fd.append('tipo', envio.tipo); fd.append('escopo', envio.escopo); if (envio.escopo === 'servidor' && srv) fd.append('server_id', srv.id);
            fd.append('nome', $('ac-nome').value || ''); const em = $('ac-emoji'); if (em && em.dataset.v) fd.append('emoji', em.dataset.v);
            if (sons) { const { blob, dur_ms } = await prepararSom(envio.buf, envio.ini, envio.fim); fd.append('arquivo', blob, 'som.wav'); fd.append('dur_ms', dur_ms); }
            else fd.append('arquivo', envio.arquivo, envio.arquivo.name);
            const r = await fetch('/api/acervo/upload', { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } });
            const j = await r.json().catch(() => ({}));
            if (!r.ok) { erro(j.erro || (r.status === 429 ? 'Calma: muitos envios seguidos. Tente de novo daqui a pouco.' : 'Não consegui enviar.')); btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Enviar'; return; }
            C.toast(j.aviso || (sons ? 'Som enviado e aprovado!' : 'Figurinha enviada e aprovada!'), j.item && j.item.status === 'aprovado' ? 'success' : 'info');
            fecharEnvio(); carregar();
        } catch (er) { erro('Algo falhou ao enviar. Confira a conexão.'); btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Enviar'; }
    }

    // ---------------------------------------------------------------------
    // soundboard (uma "atividade" da call: pessoal e do servidor)
    // ---------------------------------------------------------------------
    function abrirSoundboard(escopo) {
        if (!C.emCall()) { C.toast('Entre numa call pra usar o soundboard.', 'info'); return; }
        estado.sbEscopo = escopo === 'servidor' ? 'servidor' : 'pessoa';
        if (!sbPainel) {
            sbPainel = document.createElement('div'); sbPainel.id = 'ac-sb'; sbPainel.className = 'ac-sb'; document.body.appendChild(sbPainel);
            sbPainel.addEventListener('click', (e) => {
                const b = e.target.closest('[data-ac]'); if (!b) return;
                const a = b.dataset.ac;
                if (a === 'x') fecharSb();
                else if (a === 'mudo') { guardar('pnt_sb_mudo', mudo() ? '0' : '1'); pintarSb(); }
                else if (a === 'aba') { estado.sbEscopo = b.dataset.v; pintarSb(); }
                else if (a === 'gerir') abrirGer('som', estado.sbEscopo);
                else if (a === 'tocar') {
                    if (C.amSouOuvinte()) { C.toast('Você está só ouvindo nesta call: não dá pra tocar sons.', 'info'); return; }
                    C.socket.emit('soundboard_tocar', { canal_id: C.canalDaCall(), item_id: Number(b.dataset.id) });
                    sbPainel.querySelectorAll('.ac-pad').forEach(p => { p.classList.add('espera'); setTimeout(() => p.classList.remove('espera'), 2600); });
                }
            });
            sbPainel.addEventListener('input', (e) => { if (e.target.id === 'ac-vol') guardar('pnt_sb_vol', e.target.value); });
        }
        pintarSb(); carregar();
    }
    function fecharSb() { if (sbPainel) { sbPainel.remove(); sbPainel = null; } }
    function pintarSb() {
        if (!sbPainel) return;
        const srv = dados && dados.servidor;
        if (estado.sbEscopo === 'servidor' && !srv) estado.sbEscopo = 'pessoa';
        const lista = aprovados(estado.sbEscopo === 'servidor' ? doServidor('som') : meus('som'));
        sbPainel.innerHTML = `<div class="ac-sb-topo"><i class="fa-solid fa-volume-high"></i><b>Soundboard</b><span class="ac-esp"></span>
                <button type="button" class="ic ${mudo() ? 'off' : ''}" data-ac="mudo" title="${mudo() ? 'Ouvir os sons de todos de novo' : 'Silenciar os sons que os outros tocam (neste aparelho)'}"><i class="fa-solid ${mudo() ? 'fa-volume-xmark' : 'fa-volume-high'}"></i></button>
                <button type="button" class="ic" data-ac="gerir" title="Gerenciar sons"><i class="fa-solid fa-gear"></i></button>
                <button type="button" class="ic" data-ac="x" title="Fechar"><i class="fa-solid fa-xmark"></i></button></div>
            <div class="ac-abas peq"><button type="button" class="${estado.sbEscopo === 'pessoa' ? 'on' : ''}" data-ac="aba" data-v="pessoa">Meus sons</button>${srv ? `<button type="button" class="${estado.sbEscopo === 'servidor' ? 'on' : ''}" data-ac="aba" data-v="servidor">${esc(srv.nome || 'Servidor')}</button>` : ''}</div>
            <div class="ac-pads">${lista.map(i => `<button type="button" class="ac-pad" data-ac="tocar" data-id="${Number(i.id)}" title="${esc(i.nome)}"><span>${esc(i.emoji || '🔊')}</span><small>${esc(i.nome)}</small></button>`).join('')
                || `<div class="ac-vazio"><i class="fa-solid fa-volume-xmark"></i><b>Nenhum som aqui</b><small>${estado.sbEscopo === 'servidor' ? 'O servidor ainda não tem sons liberados.' : 'Abra a engrenagem e envie um som (até 6 s).'}</small></div>`}</div>
            <div class="ac-sb-vol"><i class="fa-solid fa-volume-low"></i><input id="ac-vol" type="range" min="0" max="1" step="0.05" value="${volSb()}" aria-label="Volume dos sons dos outros"></div><div class="ac-feed" id="ac-feed"></div>`;
    }
    function aviso(d) {
        if (!sbPainel) { if (!mudo()) C.toast(`${d.emoji || '🔊'} ${d.por_nome} tocou "${d.nome}"`, 'info'); return; }
        const f = $('ac-feed'); if (!f) return;
        const l = document.createElement('div'); l.className = 'ac-feed-l'; l.textContent = `${d.emoji || '🔊'} ${d.por_nome}: ${d.nome}`;
        f.prepend(l); while (f.children.length > 3) f.lastChild.remove(); setTimeout(() => l.remove(), 5000);
    }

    // ---------------------------------------------------------------------
    // som de entrada na call (Configurações > Meu Perfil)
    // ---------------------------------------------------------------------
    function pintarSomEntrada() {
        const el = $('ac-som-entrada'); if (!el) return;
        const atual = meuSomEntrada();
        const meusSons = meus('som');
        const linha = (valor, emoji, nome, extra) => `<div class="ac-se ${atual === valor ? 'on' : ''}" data-valor="${esc(valor || '')}"><button type="button" class="ac-play" data-ac="prever" data-valor="${esc(valor || '')}" title="Ouvir"${valor ? '' : ' disabled'}><i class="fa-solid fa-play"></i></button>
            <span class="ac-sl-emoji">${esc(emoji)}</span><span class="ac-sl-nome">${esc(nome)}</span>${extra || ''}
            <button type="button" class="ac-escolher" data-ac="escolher" data-valor="${esc(valor || '')}">${atual === valor ? '<i class="fa-solid fa-check"></i> Em uso' : 'Usar'}</button></div>`;
        el.innerHTML = `<div class="ac-se-lista">
            ${linha('', '🔔', 'Padrão do app', '<small>o som do item equipado, ou o bipe</small>')}
            ${Sons.PRESETS.map(p => linha('preset:' + p.id, p.emoji, p.nome)).join('')}
            ${meusSons.map(i => i.status === 'aprovado' ? linha('custom:' + i.id, i.emoji || '🔊', i.nome, '<small>meu som</small>')
                : `<div class="ac-se analise"><span class="ac-sl-emoji">${esc(i.emoji || '🔊')}</span><span class="ac-sl-nome">${esc(i.nome)}</span><span class="ac-sel">em análise</span></div>`).join('')}</div>
            <div class="ac-se-acoes"><button type="button" class="pf-mini" data-ac="meu-som"><i class="fa-solid fa-plus"></i> Enviar o meu som</button>
                <button type="button" class="pf-mini" data-ac="meus-sons"><i class="fa-solid fa-sliders"></i> Meus sons e figurinhas</button></div>`;
        if (!el.dataset.ligado) {
            el.dataset.ligado = '1';
            el.addEventListener('click', (e) => {
                const b = e.target.closest('[data-ac]'); if (!b) return;
                const a = b.dataset.ac;
                if (a === 'prever') { if (!Sons.prever(b.dataset.valor)) C.toast('Ative o som do app pra ouvir (Configurações > Voz e vídeo > Sons).', 'info'); }
                else if (a === 'escolher') C.socket.emit('som_entrada_definir', { valor: b.dataset.valor || null });
                else if (a === 'meu-som') abrirEnvio('som', 'pessoa');
                else if (a === 'meus-sons') abrirGer('som', 'pessoa');
            });
        }
    }

    return { iniciar, carregar, abrirFiguras, abrirGer, abrirEnvio, abrirSoundboard, pintarSomEntrada, meuSomEntrada, fecharSb, _prepararSom: prepararSom, _estado: () => ({ dados, estado }) };
})();
