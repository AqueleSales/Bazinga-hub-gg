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
        // a aba "Lojas" fica na borda do mapa; o mapa só nasce uns instantes depois do resto da página
        let tentativas = 0;
        const espera = setInterval(() => { if (ctx.mapa() || ++tentativas > 40) { clearInterval(espera); montarGaveta(); } }, 250);
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
    const brl = (c) => 'R$ ' + (Number(c || 0) / 100).toFixed(2).replace('.', ',');
    let relogio = null;

    // vitrine de produtos do cartão: um por vez, trocando sozinha (pausa com o mouse em cima), com setas, pontinhos e arrastar de lado
    function vitrine(l) {
        const ps = Array.isArray(l.produtos) ? l.produtos : [];
        if (!ps.length) return '';
        const slides = ps.map((p) => `<button type="button" class="lm-prod" data-lm="abrir" data-id="${Number(l.id)}" tabindex="-1" aria-label="${esc(p.nome)}, ${brl(p.preco_cent)}">
            <span class="lm-foto">${urlOk(p.capa) ? `<img src="${esc(urlOk(p.capa))}" alt="" loading="lazy">` : '<i class="fa-solid fa-bag-shopping"></i>'}</span>
            <span class="lm-ptxt"><b>${esc(p.nome)}</b><em>${brl(p.preco_cent)}</em></span></button>`).join('');
        const mais = ps.length > 1;
        return `<div class="lm-vit" data-n="${ps.length}" data-i="0">
            <div class="lm-vit-trilho">${slides}</div>
            ${mais ? `<button type="button" class="lm-seta e" data-lmv="-1" aria-label="Produto anterior"><i class="fa-solid fa-chevron-left"></i></button>
            <button type="button" class="lm-seta d" data-lmv="1" aria-label="Próximo produto"><i class="fa-solid fa-chevron-right"></i></button>
            <div class="lm-pts">${ps.map((_, i) => `<i data-p="${i}"${i ? '' : ' class="on"'}></i>`).join('')}</div>` : ''}
        </div>`;
    }

    function irPara(vit, i) {
        const n = Number(vit.dataset.n) || 1;
        i = ((i % n) + n) % n;
        vit.dataset.i = i;
        vit.querySelector('.lm-vit-trilho').style.transform = `translateX(${-100 * i}%)`;
        vit.querySelectorAll('.lm-pts i').forEach((p, k) => p.classList.toggle('on', k === i));
    }

    function ligarVitrine(el) {
        const vit = el && el.querySelector('.lm-vit');
        clearInterval(relogio);
        if (!vit) return;
        const n = Number(vit.dataset.n) || 1;
        if (n < 2) return;
        // começa num produto sorteado: duas pessoas olhando a mesma loja não veem a mesma primeira coisa
        irPara(vit, Math.floor(Math.random() * n));
        let parado = false, x0 = null;
        vit.addEventListener('mouseenter', () => { parado = true; });
        vit.addEventListener('mouseleave', () => { parado = false; });
        vit.addEventListener('click', (e) => { const b = e.target.closest('[data-lmv]'); if (b) { e.stopPropagation(); irPara(vit, Number(vit.dataset.i) + Number(b.dataset.lmv)); } });
        vit.addEventListener('pointerdown', (e) => { x0 = e.clientX; });
        vit.addEventListener('pointerup', (e) => {
            if (x0 == null) return;
            const dx = e.clientX - x0; x0 = null;
            if (Math.abs(dx) > 36) irPara(vit, Number(vit.dataset.i) + (dx < 0 ? 1 : -1));
        });
        if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        relogio = setInterval(() => { if (!parado && !document.hidden) irPara(vit, Number(vit.dataset.i) + 1); }, 3200);
    }

    function cartao(l) {
        const meu = Number(l.dono_id) === Number(ctx.meuId());
        const nota = l.nota ? `<span class="lm-nota"><i class="fa-solid fa-star"></i> ${String(l.nota).replace('.', ',')} <small>(${Number(l.nota_qtd) || 0})</small></span>` : '<span class="lm-nota"><small>Loja nova</small></span>';
        const capa = urlOk(l.banner_url) ? ` style="background-image:url('${esc(urlOk(l.banner_url))}')"` : '';
        return `<div class="lm-prev" style="--lj:${esc(l.cor)}">
            <div class="lm-capa${capa ? ' com-img' : ''}"${capa}><span class="lm-logo grande">${urlOk(l.logo_url) ? `<img src="${esc(urlOk(l.logo_url))}" alt="">` : inicial(l.nome)}</span></div>
            <div class="lm-corpo">
                <h3>${esc(l.nome)}</h3>
                <div class="lm-sub">${nota}${l.regiao ? ` · ${esc(l.regiao)}` : ''}</div>
                <div class="lm-sel">${l.pague_no_app ? '<span class="lm-chip"><i class="fa-solid fa-qrcode"></i> Pague pelo app</span>' : ''}${l.aprox ? '<span class="lm-chip suave"><i class="fa-solid fa-location-crosshairs"></i> área aproximada</span>' : ''}</div>
                ${vitrine(l)}
                <button type="button" class="lm-abrir" data-lm="abrir" data-id="${Number(l.id)}"><i class="fa-solid fa-store"></i> Abrir a loja</button>
                ${meu ? '<button type="button" class="lm-tirar peq" data-lm="tirar"><i class="fa-solid fa-trash"></i> Tirar do mapa</button>' : ''}
            </div></div>`;
    }

    function pintar(l) {
        const mapa = ctx.mapa();
        if (!mapa || !l || l.lat == null) return;
        tirar(l.id);
        // o ponto do mapa é a BASE da lojinha (o chão do corpo): o nome fica solto embaixo, fora da caixa, pra não empurrar o ponto
        const icone = L.divIcon({
            className: '',
            html: `<div class="pino-loja" style="--lj:${esc(l.cor)}"><span class="pl-toldo"></span><span class="pl-corpo">${urlOk(l.logo_url) ? `<img src="${esc(urlOk(l.logo_url))}" alt="">` : inicial(l.nome)}</span><span class="pl-nome">${esc(l.nome)}</span></div>`,
            iconSize: [64, 46], iconAnchor: [32, 46],
        });
        const marker = L.marker([l.lat, l.lng], { icon: icone });
        if (passa(l)) marker.addTo(mapa);               // o filtro da gaveta vale também pro pino
        marker.bindPopup(() => cartao(pinos.get(Number(l.id))?.dados || l), { minWidth: 240, maxWidth: 240, closeButton: true, className: 'balao-wrap lm-balao', autoPanPadding: [30, 30], offset: [0, -4] });
        marker.on('popupopen', (e) => ligarVitrine(e.popup.getElement()));
        marker.on('popupclose', () => clearInterval(relogio));
        pinos.set(Number(l.id), { marker, dados: l });
        pedirRedesenho();
    }

    function tirar(id) {
        const p = pinos.get(Number(id));
        if (!p) return;
        const mapa = ctx.mapa();
        if (mapa) mapa.removeLayer(p.marker);
        pinos.delete(Number(id));
        pedirRedesenho();
    }

    // o servidor é a verdade do que está no alcance (andou, reconectou): tira o que sumiu e põe o que chegou
    function sincronizar(lojas) {
        const lista = Array.isArray(lojas) ? lojas : [];
        const ids = new Set(lista.map((l) => Number(l.id)));
        [...pinos.keys()].filter((id) => !ids.has(id)).forEach(tirar);
        lista.forEach((l) => {
            const ja = pinos.get(Number(l.id));
            if (!ja || ja.dados.lat !== l.lat || ja.dados.lng !== l.lng || ja.dados.nome !== l.nome || ja.dados.pague_no_app !== l.pague_no_app || ja.dados.logo_url !== l.logo_url || ja.dados.banner_url !== l.banner_url) pintar(l);
            else ja.dados = l;   // mesmo pino, produtos sorteados de novo: o próximo cartão aberto já usa a lista nova
        });
        pedirRedesenho();
    }
    // ---------------------------------------------------------------------
    // "Lojas por perto": o pedido rápido ao lado do mapa (aba na borda, abre ao passar o mouse ou ao tocar)
    // Tudo sai dos pinos que o servidor já mandou (o que está no alcance): filtrar, buscar e ordenar não vai ao servidor.
    // ---------------------------------------------------------------------
    const CATEGORIAS = { comida: ['Comida', 'fa-utensils'], arte: ['Arte', 'fa-palette'], digital: ['Digital', 'fa-gamepad'], moda: ['Moda', 'fa-shirt'],
                         casa: ['Casa', 'fa-couch'], servicos: ['Serviços', 'fa-screwdriver-wrench'], outros: ['Outros', 'fa-bag-shopping'] };
    const ORDENS = [['perto', 'Mais perto'], ['nota', 'Melhor avaliadas'], ['vendas', 'Mais pedidas']];
    const filtro = { cat: '', q: '', ordem: 'perto' };
    let dock = null, fixa = false, redesenho = 0, relogioDock = null;

    function minhaPos() { try { const p = ctx.minhaPos && ctx.minhaPos(); return p && isFinite(p.lat) && isFinite(p.lng) ? p : null; } catch (e) { return null; } }
    function distM(a, b) {
        const R = 6371000, rad = Math.PI / 180, dLa = (b.lat - a.lat) * rad, dLo = (b.lng - a.lng) * rad;
        const x = Math.sin(dLa / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLo / 2) ** 2;
        return 2 * R * Math.asin(Math.sqrt(x));
    }
    function fmtDist(m) { return m < 1000 ? `${Math.max(10, Math.round(m / 10) * 10)} m` : `${(m / 1000).toFixed(1).replace('.', ',')} km`; }

    function passa(l) {
        if (filtro.cat && l.categoria !== filtro.cat) return false;
        const q = filtro.q.trim().toLowerCase();
        if (!q) return true;
        const texto = `${l.nome || ''} ${(l.produtos || []).map((p) => p.nome).join(' ')}`.toLowerCase();
        return texto.includes(q);
    }
    // o filtro vale também pros pinos: o que não passa sai do mapa (e volta quando a pessoa limpa o filtro)
    function aplicarFiltroNosPinos() {
        const mapa = ctx.mapa();
        if (!mapa) return;
        pinos.forEach((p) => {
            const mostrar = passa(p.dados);
            if (mostrar && !mapa.hasLayer(p.marker)) p.marker.addTo(mapa);
            else if (!mostrar && mapa.hasLayer(p.marker)) { p.marker.closePopup(); mapa.removeLayer(p.marker); }
        });
    }
    function listaFiltrada() {
        const pos = minhaPos();
        const itens = [...pinos.values()].map((p) => p.dados).filter(passa).map((l) => ({ l, d: pos ? distM(pos, l) : null }));
        const porDist = (a, b) => (a.d == null ? 1 : b.d == null ? -1 : a.d - b.d);
        if (filtro.ordem === 'nota') itens.sort((a, b) => (Number(b.l.nota) || 0) - (Number(a.l.nota) || 0) || porDist(a, b));
        else if (filtro.ordem === 'vendas') itens.sort((a, b) => (Number(b.l.vendas) || 0) - (Number(a.l.vendas) || 0) || porDist(a, b));
        else itens.sort(porDist);
        return itens;
    }

    function cardLoja(it) {
        const l = it.l, cat = CATEGORIAS[l.categoria];
        const nota = l.nota ? `<i class="fa-solid fa-star"></i> ${String(l.nota).replace('.', ',')}` : 'Loja nova';
        const dist = it.d == null ? '' : ` · ${l.aprox ? '~' : ''}${fmtDist(it.d)}`;
        const prods = (l.produtos || []).slice(0, 3).map((p) => `<button type="button" class="lg-prod" data-lmp="prod" data-id="${Number(p.id)}" data-loja="${Number(l.id)}">
            <span class="lg-foto">${urlOk(p.capa) ? `<img src="${esc(urlOk(p.capa))}" alt="" loading="lazy">` : '<i class="fa-solid fa-bag-shopping"></i>'}</span>
            <span class="lg-pt"><b>${esc(p.nome)}</b><em>${brl(p.preco_cent)}</em></span><span class="lg-pedir">Pedir</span></button>`).join('');
        return `<article class="lg-loja" style="--lj:${esc(l.cor)}">
            <header><span class="lm-logo">${urlOk(l.logo_url) ? `<img src="${esc(urlOk(l.logo_url))}" alt="">` : inicial(l.nome)}</span>
                <div class="lg-id"><b>${esc(l.nome)}</b><small>${nota}${dist}${cat ? ` · ${esc(cat[0])}` : ''}</small></div>
                <button type="button" class="lg-mapa" data-lmp="ver" data-id="${Number(l.id)}" data-tip="Ver no mapa" aria-label="Ver ${esc(l.nome)} no mapa"><i class="fa-solid fa-location-crosshairs"></i></button></header>
            ${l.pague_no_app ? '<div class="lg-chips"><span class="lm-chip"><i class="fa-solid fa-qrcode"></i> Pague pelo app</span></div>' : ''}
            ${prods ? `<div class="lg-prods">${prods}</div>` : '<div class="lg-semprod">Sem produtos em destaque agora.</div>'}
            <button type="button" class="lg-abrir" data-lmp="loja" data-id="${Number(l.id)}"><i class="fa-solid fa-store"></i> Abrir a loja e conversar</button>
        </article>`;
    }

    function chipsDeCategoria() {
        const cats = [...new Set([...pinos.values()].map((p) => p.dados.categoria).filter(Boolean))];
        return `<button type="button" class="lg-chip${filtro.cat ? '' : ' on'}" data-lmp="cat" data-v="">Todas</button>` + cats.map((c) => {
            const info = CATEGORIAS[c] || [c, 'fa-tag'];
            return `<button type="button" class="lg-chip${filtro.cat === c ? ' on' : ''}" data-lmp="cat" data-v="${esc(c)}"><i class="fa-solid ${info[1]}"></i> ${esc(info[0])}</button>`;
        }).join('');
    }

    function desenharGaveta(manterBusca) {
        if (!dock) return;
        const itens = listaFiltrada();
        const total = pinos.size;
        dock.querySelector('.lg-conta').textContent = String(total);
        dock.classList.toggle('vazio', !total);
        dock.querySelector('.lg-chips-cat').innerHTML = chipsDeCategoria();
        dock.querySelectorAll('[data-lmp="ordem"]').forEach((b) => b.classList.toggle('on', b.dataset.v === filtro.ordem));
        const lista = dock.querySelector('.lg-lista');
        const rolagem = lista.scrollTop;
        lista.innerHTML = itens.length ? itens.map(cardLoja).join('')
            : `<div class="lg-vazio"><i class="fa-solid fa-store-slash"></i><b>${total ? 'Nenhuma loja com esse filtro' : 'Nenhuma loja por perto'}</b><span>${total ? 'Limpe a busca ou escolha outra categoria.' : 'Quando alguém plantar uma loja no seu alcance, ela aparece aqui.'}</span></div>`;
        lista.scrollTop = rolagem;
        if (!manterBusca) { const q = dock.querySelector('#lg-q'); if (q && q.value !== filtro.q) q.value = filtro.q; }
    }
    function pedirRedesenho() {
        if (!dock) return;
        clearTimeout(redesenho);
        redesenho = setTimeout(() => { aplicarFiltroNosPinos(); desenharGaveta(true); }, 120);
    }

    function montarGaveta() {
        const mapaEl = document.getElementById('bazinga-map');
        if (!mapaEl || !mapaEl.parentElement || dock) return;
        dock = document.createElement('aside');
        dock.className = 'lg-dock'; dock.id = 'lg-dock';
        dock.innerHTML = `<button type="button" class="lg-aba" data-lmp="alternar" aria-label="Lojas por perto" aria-expanded="false"><i class="fa-solid fa-store"></i><span class="lg-conta">0</span><b>Lojas</b></button>
            <div class="lg-gaveta" role="region" aria-label="Lojas por perto">
                <div class="lg-topo"><div><b>Lojas por perto</b><small>Pedido rápido, sem sair do mapa</small></div><button type="button" class="lg-x" data-lmp="fechar" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button></div>
                <label class="lg-busca"><i class="fa-solid fa-magnifying-glass"></i><input type="search" id="lg-q" placeholder="Buscar loja ou produto" maxlength="40" autocomplete="off" spellcheck="false"></label>
                <div class="lg-chips-cat"></div>
                <div class="lg-ordem" role="group" aria-label="Ordenar">${ORDENS.map(([v, n]) => `<button type="button" data-lmp="ordem" data-v="${v}">${n}</button>`).join('')}</div>
                <div class="lg-lista"></div>
            </div>`;
        mapaEl.parentElement.appendChild(dock);
        // tocar nos controles do mapa por baixo não pode mexer o mapa
        if (window.L && L.DomEvent) { L.DomEvent.disableClickPropagation(dock); L.DomEvent.disableScrollPropagation(dock); }
        dock.addEventListener('click', (e) => {
            const b = e.target.closest('[data-lmp]'); if (!b) return;
            const a = b.dataset.lmp;
            if (a === 'alternar') { fixa = !fixa; dock.classList.toggle('fixa', fixa); b.setAttribute('aria-expanded', fixa ? 'true' : 'false'); if (fixa) desenharGaveta(); }
            else if (a === 'fechar') { fixa = false; dock.classList.remove('fixa', 'tocado'); dock.querySelector('.lg-aba').setAttribute('aria-expanded', 'false'); }
            else if (a === 'cat') { filtro.cat = b.dataset.v || ''; aplicarFiltroNosPinos(); desenharGaveta(); }
            else if (a === 'ordem') { filtro.ordem = b.dataset.v; desenharGaveta(); }
            else if (a === 'ver') verNoMapa(Number(b.dataset.id));
            else if (a === 'loja') { ctx.abrirLoja(Number(b.dataset.id)); }
            else if (a === 'prod') { ctx.abrirLoja(Number(b.dataset.loja), Number(b.dataset.id)); }
        });
        dock.querySelector('#lg-q').addEventListener('input', (e) => { filtro.q = e.target.value; aplicarFiltroNosPinos(); desenharGaveta(true); });
        dock.addEventListener('mouseenter', () => { desenharGaveta(true); });
        // a distância muda quando a pessoa anda
        relogioDock = setInterval(() => { if (dock && (fixa || dock.matches(':hover')) && !document.hidden) desenharGaveta(true); }, 20000);
        desenharGaveta();
    }
    function verNoMapa(id) {
        const p = pinos.get(Number(id)), mapa = ctx.mapa();
        if (!p || !mapa) return;
        if (!mapa.hasLayer(p.marker)) p.marker.addTo(mapa);
        mapa.flyTo([p.dados.lat, p.dados.lng], Math.max(mapa.getZoom(), 16), { duration: .8 });
        setTimeout(() => p.marker.openPopup(), 850);
    }


    return { iniciar, abrirPlantar, plantarEm, sincronizar, pinos: () => pinos };
})();
