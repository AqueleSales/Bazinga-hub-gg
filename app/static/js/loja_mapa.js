/* Loja no mapa (Rodada 32): o botão "Plantar" (servidor OU loja), o pino da loja e o cartão de prévia que leva ao Bazar.
   Só DESENHA: quem pode plantar, o alcance e o arredondamento do ponto são do servidor (bazar_events.py / bazar.py).
   Objeto global `LojaMapa`; os ganchos moram no chat.html (iniciar, sincronizar, clique do mapa, botão Plantar). */
const LojaMapa = (function () {
    'use strict';
    let ctx = null;
    const pinos = new Map();          // id da loja -> { marker, dados }
    let esperando = false;            // pedi "tenho loja?" e aguardo a resposta
    let aprox = true;                 // preferência da pessoa na hora de plantar (padrão: só a área, por privacidade)
    let overlay = null;

    const esc = (v) => (ctx && ctx.esc ? ctx.esc(v) : String(v == null ? '' : v));
    const urlOk = (u) => (ctx && ctx.escUrl ? ctx.escUrl(u) : '');
    const inicial = (nome) => esc(String(nome || '?').trim().charAt(0).toUpperCase() || '?');

    function iniciar(c) {
        ctx = c;
        const s = ctx.socket;
        s.on('loja_mapa_minha', (d) => {
            if (!esperando) return;
            esperando = false;
            if (!d || !d.tem) { ctx.abrirServidor(); return; }      // sem loja: o Plantar é só de servidor, como sempre foi
            escolha(d);
        });
        s.on('loja_mapa_nova', (l) => pintar(l));
        s.on('loja_mapa_removida', (d) => tirar(d && d.id));
        s.on('loja_mapa_ok', (d) => {
            if (d && d.removida) ctx.toast('Sua loja saiu do mapa.', 'info');
            else ctx.toast(d && d.aprox ? 'Loja plantada! No mapa aparece só a área aproximada (~300 m).' : 'Loja plantada no ponto escolhido!', 'success');
        });
        document.addEventListener('click', (e) => {
            const a = e.target.closest('[data-lm]');
            if (!a) return;
            const acao = a.dataset.lm;
            if (acao === 'abrir') { ctx.abrirLoja(Number(a.dataset.id)); }
            else if (acao === 'tirar') { ctx.socket.emit('tirar_loja_do_mapa', {}); fechar(); }
            else if (acao === 'servidor') { fechar(); ctx.abrirServidor(); }
            else if (acao === 'loja') { fechar(); ctx.preparar(); ctx.toast('Clique no mapa onde fica a sua loja' + (aprox ? ' (só a área aproximada vai aparecer).' : '.'), 'info'); }
            else if (acao === 'fechar') fechar();
        });
    }

    // ---------------------------------------------------------------------
    // o botão "Plantar": pergunta ao servidor se a pessoa tem loja; só então oferece as duas opções
    // ---------------------------------------------------------------------
    function abrirPlantar() {
        if (!ctx.socket.connected) { ctx.toast('Sem conexão com o servidor. Recarregue a página e tente de novo.', 'error'); return; }
        if (!ctx.exigirLocalizacao()) return;
        esperando = true;
        ctx.socket.emit('loja_mapa_minha', {});
        // se a resposta não vier, cai no caminho antigo (servidor) em vez de deixar o botão mudo
        setTimeout(() => { if (esperando) { esperando = false; ctx.abrirServidor(); } }, 4000);
    }

    function escolha(d) {
        fechar();
        const l = d.loja || {};
        overlay = document.createElement('div');
        overlay.className = 'lm-overlay';
        overlay.innerHTML = `<div class="lm-card" role="dialog" aria-label="Plantar no mapa">
            <button type="button" class="lm-x" data-lm="fechar" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button>
            <h3>O que você quer plantar?</h3>
            <div class="lm-opcoes">
                <button type="button" class="lm-op" data-lm="servidor"><i class="fa-solid fa-tower-broadcast"></i><b>Servidor</b><span>Deixe o seu servidor no mapa para as pessoas por perto entrarem.</span></button>
                <button type="button" class="lm-op loja" data-lm="loja" ${d.pode ? '' : 'disabled'} style="--lj:${esc(l.cor || '#d9822b')}">
                    <span class="lm-logo">${urlOk(l.logo_url) ? `<img src="${esc(urlOk(l.logo_url))}" alt="">` : inicial(l.nome)}</span><b>Loja: ${esc(l.nome || '')}</b>
                    <span>${d.pode ? (d.no_mapa ? 'Já está no mapa. Escolha outro ponto pra mudar de lugar.' : 'Mostre a sua loja do Bazar no mapa: quem passar por perto vê, abre e compra.') : 'A sua loja está fechada ou em análise.'}</span></button>
            </div>
            <label class="lm-aprox"><input type="checkbox" id="lm-aprox" ${aprox ? 'checked' : ''}> Mostrar só a <b>área aproximada</b> (~300 m), não o ponto exato.<small>Recomendado se você vende de casa: ninguém precisa saber a porta.</small></label>
            ${d.no_mapa ? '<button type="button" class="lm-tirar" data-lm="tirar"><i class="fa-solid fa-trash"></i> Tirar a minha loja do mapa</button>' : ''}
        </div>`;
        overlay.addEventListener('click', (e) => { if (e.target === overlay) fechar(); });
        overlay.querySelector('#lm-aprox').addEventListener('change', (e) => { aprox = e.target.checked; });
        document.body.appendChild(overlay);
    }

    function fechar() { if (overlay) { overlay.remove(); overlay = null; } }

    // chamado pelo clique no mapa (chat.html) quando o modo de plantio é "loja"
    function plantarEm(latlng) {
        ctx.socket.emit('plantar_loja', { lat: latlng.lat, lng: latlng.lng, aprox });
        ctx.toast('Plantando a sua loja...', 'info');
    }

    // ---------------------------------------------------------------------
    // pinos e cartão de prévia
    // ---------------------------------------------------------------------
    function cartao(l) {
        const meu = Number(l.dono_id) === Number(ctx.meuId());
        const nota = l.nota ? `<span class="lm-nota"><i class="fa-solid fa-star"></i> ${String(l.nota).replace('.', ',')} <small>(${Number(l.nota_qtd) || 0})</small></span>` : '<span class="lm-nota"><small>Loja nova</small></span>';
        return `<div class="lm-prev" style="--lj:${esc(l.cor)}">
            <div class="lm-capa"><span class="lm-logo grande">${urlOk(l.logo_url) ? `<img src="${esc(urlOk(l.logo_url))}" alt="">` : inicial(l.nome)}</span></div>
            <div class="lm-corpo">
                <h3>${esc(l.nome)}</h3>
                <div class="lm-sub">${nota}${l.regiao ? ` · ${esc(l.regiao)}` : ''}</div>
                <div class="lm-sel">${l.pague_no_app ? '<span class="lm-chip"><i class="fa-solid fa-qrcode"></i> Pague pelo app</span>' : ''}${l.aprox ? '<span class="lm-chip suave"><i class="fa-solid fa-location-crosshairs"></i> área aproximada</span>' : ''}</div>
                <button type="button" class="lm-abrir" data-lm="abrir" data-id="${Number(l.id)}"><i class="fa-solid fa-store"></i> Abrir a loja</button>
                ${meu ? '<button type="button" class="lm-tirar peq" data-lm="tirar"><i class="fa-solid fa-trash"></i> Tirar do mapa</button>' : ''}
            </div></div>`;
    }

    function pintar(l) {
        const mapa = ctx.mapa();
        if (!mapa || !l || l.lat == null) return;
        tirar(l.id);
        const icone = L.divIcon({
            className: '',
            html: `<div class="pino-loja" style="--lj:${esc(l.cor)}"><span class="pl-toldo"></span><span class="pl-corpo">${urlOk(l.logo_url) ? `<img src="${esc(urlOk(l.logo_url))}" alt="">` : inicial(l.nome)}</span><span class="pl-nome">${esc(l.nome)}</span></div>`,
            iconSize: [64, 74], iconAnchor: [32, 74],
        });
        const marker = L.marker([l.lat, l.lng], { icon: icone }).addTo(mapa);
        marker.bindPopup(cartao(l), { minWidth: 240, maxWidth: 240, closeButton: true, className: 'balao-wrap', autoPanPadding: [30, 30] });
        pinos.set(Number(l.id), { marker, dados: l });
    }

    function tirar(id) {
        const p = pinos.get(Number(id));
        if (!p) return;
        const mapa = ctx.mapa();
        if (mapa) mapa.removeLayer(p.marker);
        pinos.delete(Number(id));
    }

    // o servidor é a verdade do que está no alcance (andou, reconectou): tira o que sumiu e põe o que chegou
    function sincronizar(lojas) {
        const lista = Array.isArray(lojas) ? lojas : [];
        const ids = new Set(lista.map((l) => Number(l.id)));
        [...pinos.keys()].filter((id) => !ids.has(id)).forEach(tirar);
        lista.forEach((l) => {
            const ja = pinos.get(Number(l.id));
            if (!ja || ja.dados.lat !== l.lat || ja.dados.lng !== l.lng || ja.dados.nome !== l.nome || ja.dados.pague_no_app !== l.pague_no_app || ja.dados.logo_url !== l.logo_url) pintar(l);
        });
    }

    return { iniciar, abrirPlantar, plantarEm, sincronizar, pinos: () => pinos };
})();
