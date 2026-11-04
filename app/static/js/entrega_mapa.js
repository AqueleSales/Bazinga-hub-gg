/* Entrega acompanhada no mapa (Rodada 36): o bloco "Entrega" do pedido (comprador, vendedor e entregador), o mini mapa com o entregador vindo,
   o painel "Entregas" de quem faz entregas e o aceite de compartilhar a posição. Só DESENHA e pede: quem pode o quê, a posição, o tempo e o fim
   automático são do servidor (entregas.py / entregas_events.py). A posição ao vivo chega por `entrega_ao_vivo` e NUNCA fica gravada aqui.
   Objeto global `Entrega`; os ganchos moram em bazar.js (bloco do pedido, aba "Entregas") e no chat.html (iniciar e os eventos). */
const Entrega = (function () {
    'use strict';
    let ctx = null;
    const esc = (v) => (ctx && ctx.esc ? ctx.esc(v) : String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])));
    const reduzMov = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const ICONE = { a_pe: 'fa-person-walking', bicicleta: 'fa-bicycle', moto: 'fa-motorcycle', carro: 'fa-car-side' };
    const NOME = { a_pe: 'A pé', bicicleta: 'Bicicleta', moto: 'Moto', carro: 'Carro' };
    const TRANSPORTES = ['moto', 'bicicleta', 'a_pe', 'carro'];
    const ROTULO_ESTADO = { convidado: 'Convite enviado', aceita: 'Pronto pra sair', a_caminho: 'A caminho', entregue: 'Entregue', recusada: 'Recusou' };

    let painel = { cadastro: { ativo: false, entregas: 0 }, entregas: [], carregado: false };
    const vivos = new Map();              // pedido_id -> { lat, lng, visto (ms local), dist_m, eta_s, chegando, trilha: [[lat,lng]...], semGps }
    const meusAtivos = new Set();         // pedidos em que EU estou levando (compartilhando a posição agora)
    const retomados = new Set();
    let mini = null;                      // o único mini mapa aberto: { pid, el, map, marcas, linhas, livre, prog, dono }
    let timerGps = 0, timerRelogio = 0, avisouSinal = 0;

    // ---------------------------------------------------------------------
    // PEÇAS
    // ---------------------------------------------------------------------
    const fmtDist = (m) => (m == null ? '' : m < 1000 ? `${Math.max(10, Math.round(m / 10) * 10)} m` : `${(m / 1000).toFixed(1).replace('.', ',')} km`);
    function fmtEta(s) {
        if (s == null) return '';
        if (s <= 0) return 'chegando';
        const min = Math.max(1, Math.round(s / 60));
        return min < 60 ? `~${min} min` : `~${Math.floor(min / 60)} h ${String(min % 60).padStart(2, '0')} min`;
    }
    const iconeDe = (t) => ICONE[t] || ICONE.moto;
    const chip = (estado, rotulo) => `<span class="en-chip ${esc(estado || 'sem')}">${esc(rotulo || ROTULO_ESTADO[estado] || 'Sem entregador')}</span>`;
    const pessoa = (q) => (q && q.nome ? esc(q.nome) : 'alguém');

    function selectTransporte(atual, nome = 'transporte') {
        return `<label class="en-campo">Como vai<select class="en-sel" data-en-campo="${nome}">${TRANSPORTES.map((t) => `<option value="${t}" ${t === atual ? 'selected' : ''}>${NOME[t]}</option>`).join('')}</select></label>`;
    }

    const textoConsentimento = '<b>Entendi:</b> enquanto a entrega durar, o comprador e o vendedor veem a minha posição ao vivo, <b>mesmo com o Modo Fantasma ligado</b>, e só eles. '
        + 'Não aparece no mapa de mais ninguém, não fica gravada, e acaba quando eu entrego, paro ou o pedido termina. Posso parar quando quiser.';

    // ---------------------------------------------------------------------
    // MINI MAPA (Leaflet; um só aberto por vez)
    // ---------------------------------------------------------------------
    function icone(classe, fa, extra = '') {
        return L.divIcon({ className: 'en-pino-wrap', iconSize: [38, 38], iconAnchor: [19, 19], html: `<div class="en-pino ${classe}"><i class="fa-solid ${fa}"></i></div>${extra}` });
    }

    function destruir() {
        if (!mini) return;
        try { Object.values(mini.marcas).forEach((m) => { if (m._raf) cancelAnimationFrame(m._raf); }); mini.map.remove(); } catch (e) { /* já foi */ }
        mini = null;
    }

    function dadosDoMapa(pid, fonte) {
        // fonte = entrega_mapa do pedido OU a entrega do painel do entregador (mesmos campos que importam)
        const v = vivos.get(pid);
        const ult = v ? { lat: v.lat, lng: v.lng } : (fonte.ultima ? { lat: fonte.ultima.lat, lng: fonte.ultima.lng } : null);
        return { pid, destino: fonte.destino || null, loja: fonte.loja || null, ent: ult, transporte: fonte.transporte || 'moto', aCaminho: (fonte.estado || '') === 'a_caminho' };
    }

    function montar(slot, d, dono) {
        if (!slot) { if (dono === 'modal') destruir(); return; }
        if (typeof L === 'undefined') { slot.innerHTML = '<div class="en-aviso">O mapa não carregou. Recarregue a página.</div>'; return; }
        if (mini && mini.pid !== d.pid) destruir();
        if (!mini) {
            const el = document.createElement('div');
            el.className = 'en-mapa';
            slot.prepend(el);
            const centro = (d.destino || d.loja || d.ent) || { lat: -23.5505, lng: -46.6333 };
            const map = L.map(el, { zoomControl: false, attributionControl: false, minZoom: 3, maxBounds: [[-85, -180], [85, 180]], maxBoundsViscosity: 1 }).setView([centro.lat, centro.lng], 15);
            L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, maxNativeZoom: 18, noWrap: true, bounds: [[-85, -180], [85, 180]], updateWhenIdle: false, keepBuffer: 3 }).addTo(map);
            L.control.zoom({ position: 'bottomright' }).addTo(map);
            mini = { pid: d.pid, el, map, marcas: {}, linhas: {}, livre: false, prog: false, dono };
            map.on('dragstart zoomstart', () => { if (!mini.prog) mini.livre = true; });
        } else {
            slot.prepend(mini.el);            // o pedido foi redesenhado: o mesmo mapa vai pro lugar novo
            mini.dono = dono;
        }
        desenharMini(d);
        setTimeout(() => { if (mini && mini.el.isConnected) { mini.map.invalidateSize(); ajustar(); } }, 80);
    }

    function marca(chave, ll, ic) {
        if (!mini) return null;
        let m = mini.marcas[chave];
        if (!m) { m = mini.marcas[chave] = L.marker(ll, { icon: ic, interactive: false, keyboard: false }).addTo(mini.map); }
        else if (ic && m._classe !== ic.options.html) m.setIcon(ic);
        m._classe = ic ? ic.options.html : m._classe;
        return m;
    }

    function moverMarca(m, para, animar) {
        if (m._raf) cancelAnimationFrame(m._raf);
        const de = m.getLatLng();
        if (!animar || reduzMov() || document.hidden || (de.lat === para[0] && de.lng === para[1])) { m.setLatLng(para); return; }
        const t0 = performance.now(), dur = 1400;
        const passo = (t) => {
            const k = Math.min(1, (t - t0) / dur);
            m.setLatLng([de.lat + (para[0] - de.lat) * k, de.lng + (para[1] - de.lng) * k]);
            if (k < 1) m._raf = requestAnimationFrame(passo);
        };
        m._raf = requestAnimationFrame(passo);
    }

    function desenharMini(d, animar = false) {
        if (!mini || mini.pid !== d.pid) return;
        mini.d = d;
        const pts = [];
        if (d.loja) { marca('loja', [d.loja.lat, d.loja.lng], icone('loja', 'fa-store')); pts.push([d.loja.lat, d.loja.lng]); }
        if (d.destino) { marca('destino', [d.destino.lat, d.destino.lng], icone('destino', 'fa-house')); pts.push([d.destino.lat, d.destino.lng]); }
        else if (mini.marcas.destino) { mini.map.removeLayer(mini.marcas.destino); delete mini.marcas.destino; }
        const v = vivos.get(d.pid);
        if (d.ent && d.aCaminho) {
            const ll = [d.ent.lat, d.ent.lng];
            const m = marca('ent', ll, icone('ent', iconeDe(d.transporte), '<span class="en-onda"></span>'));
            if (m) moverMarca(m, ll, animar);
            pts.push(ll);
            const trilha = (v && v.trilha) || [ll];
            if (!mini.linhas.trilha) mini.linhas.trilha = L.polyline(trilha, { color: '#3ecf8e', weight: 5, opacity: .9 }).addTo(mini.map);
            else mini.linhas.trilha.setLatLngs(trilha);
            const resto = d.destino ? [ll, [d.destino.lat, d.destino.lng]] : [];
            if (!mini.linhas.resto) mini.linhas.resto = L.polyline(resto, { color: '#ffffff', weight: 4, opacity: .85, dashArray: '2 10', lineCap: 'round' }).addTo(mini.map);
            else mini.linhas.resto.setLatLngs(resto);
        } else {
            if (mini.marcas.ent) { mini.map.removeLayer(mini.marcas.ent); delete mini.marcas.ent; }
            ['trilha', 'resto'].forEach((k) => { if (mini.linhas[k]) { mini.map.removeLayer(mini.linhas[k]); delete mini.linhas[k]; } });
        }
        mini.pts = pts;
    }

    function ajustar() {
        if (!mini || mini.livre || !mini.pts || !mini.pts.length) return;
        mini.prog = true;
        try {
            if (mini.pts.length === 1) mini.map.setView(mini.pts[0], 16, { animate: false });
            else mini.map.fitBounds(L.latLngBounds(mini.pts), { padding: [34, 34], maxZoom: 17, animate: false });
        } finally { setTimeout(() => { if (mini) mini.prog = false; }, 50); }
    }

    // ---------------------------------------------------------------------
    // BLOCO DO PEDIDO (comprador, vendedor e o entregador quando é o próprio vendedor)
    // ---------------------------------------------------------------------
    function infoHtml(pid, aCaminho) {
        const v = vivos.get(pid);
        if (!aCaminho) return '';
        if (!v) return '<div class="en-eta"><i class="fa-solid fa-satellite-dish"></i> Esperando a primeira posição do entregador...</div>';
        const idade = Math.max(0, Math.round((Date.now() - v.visto) / 1000));
        const velho = idade > 45;
        const eta = v.chegando ? 'Chegando!' : (v.eta_s != null ? `Chega em ${fmtEta(v.eta_s)}` : 'A caminho');
        return `<div class="en-eta ${velho ? 'velho' : ''}"><b>${esc(eta)}</b>${v.dist_m != null ? `<span>${esc(fmtDist(v.dist_m))} do destino</span>` : ''}
            <small>${velho ? `<i class="fa-solid fa-signal"></i> Sem sinal há ${idade >= 120 ? Math.round(idade / 60) + ' min' : idade + ' s'}: o entregador pode estar sem internet ou sem GPS.` : (idade < 6 ? 'Posição ao vivo' : `Atualizado há ${idade} s`)}${v.semGps ? ' · sem GPS do aparelho' : ''}</small></div>`;
    }

    function acoesComprador(p, em) {
        if (!em.pode_destino) return '';
        return `<div class="en-linha">${em.destino
            ? `<span><i class="fa-solid fa-location-dot"></i> Ponto de entrega marcado no mapa</span>
               <button type="button" class="bz-btn sec pq" data-a="en-destino" data-id="${Number(p.id)}"><i class="fa-solid fa-crosshairs"></i> Usar onde estou agora</button>
               <button type="button" class="bz-btn sec pq" data-a="en-destino-limpar" data-id="${Number(p.id)}">Apagar o ponto</button>`
            : `<span><i class="fa-regular fa-location-dot"></i> Sem ponto no mapa: o entregador só terá o endereço escrito.</span>
               <button type="button" class="bz-btn pq" data-a="en-destino" data-id="${Number(p.id)}"><i class="fa-solid fa-crosshairs"></i> Marcar onde estou agora</button>`}</div>
            <small class="en-nota">Quem for entregar (a loja, ou alguém que ela chamar) vê o endereço e esse ponto só durante a entrega. Tudo é apagado quando o pedido termina.</small>`;
    }

    function acoesVendedor(p, em) {
        if (!em.pode_designar) return '';
        const ent = em.entregador;
        const status = em.estado === 'convidado' ? `<div class="en-linha"><span><i class="fa-solid fa-hourglass-half"></i> Convite enviado para <b>${pessoa(ent)}</b>. Aguardando a resposta.</span></div>`
            : em.estado === 'recusada' ? `<div class="en-linha aviso"><span><i class="fa-solid fa-circle-xmark"></i> <b>${pessoa(ent)}</b> não vai poder entregar. Escolha outra pessoa.</span></div>`
            : em.estado === 'aceita' && !em.proprio ? `<div class="en-linha"><span><i class="fa-solid fa-circle-check"></i> <b>${pessoa(ent)}</b> aceitou e vai sair pra entregar.</span></div>` : '';
        const tr = (em.transportes || []).length ? selectTransporte(em.transporte || 'moto') : '';
        return `${status}<div class="en-quem"><b>Quem entrega?</b>
            <div class="en-linha">${tr}<button type="button" class="bz-btn pq" data-a="en-eu" data-id="${Number(p.id)}"><i class="fa-solid fa-store"></i> Eu mesmo entrego</button></div>
            <div class="en-linha"><input type="text" class="en-in" maxlength="33" data-en-campo="alvo" placeholder="ou @ de um entregador cadastrado"><button type="button" class="bz-btn sec pq" data-a="en-chamar" data-id="${Number(p.id)}"><i class="fa-solid fa-user-plus"></i> Chamar</button></div>
            <small class="en-nota">O Pantheon não paga nem cobra o entregador: o que combinar com ele é entre vocês. Peça pra ele ligar "Quero fazer entregas" em Bazar &gt; Entregas.</small></div>`;
    }

    function acoesEntregador(p, em) {
        if (em.pode_sair) {
            return `<div class="en-quem"><b>Você vai entregar este pedido</b>
                <div class="en-linha">${selectTransporte(em.transporte || 'moto', 'transporte-saida')}</div>
                <label class="en-consent"><input type="checkbox" data-en-campo="consentimento"><span>${textoConsentimento}</span></label>
                <button type="button" class="bz-btn verde" data-a="en-sair" data-id="${Number(p.id)}"><i class="fa-solid fa-route"></i> Sair para entrega</button></div>`;
        }
        if (em.pode_parar) {
            return `<div class="en-linha"><button type="button" class="bz-btn verde" data-a="en-entregue" data-id="${Number(p.id)}" data-conf="Confirma que entregou o pedido? O compartilhamento da sua posição acaba agora."><i class="fa-solid fa-box-open"></i> Entreguei</button>
                <button type="button" class="bz-btn sec" data-a="en-parar" data-id="${Number(p.id)}" data-conf="Parar de compartilhar a sua posição? O pedido volta a &quot;pronto pra sair&quot; e você pode sair de novo.">Parar de compartilhar</button></div>`;
        }
        return '';
    }

    function htmlPedido(p) {
        const em = p.entrega_mapa;
        if (!em || ['cancelado', 'recusado'].includes(p.status)) return '';
        const antes = ['aguardando', 'aceito', 'pago'].includes(p.status);
        const comprador = p.papel === 'comprador';
        if (antes) return comprador ? `<div class="en-bloco" data-pid="${Number(p.id)}"><div class="en-cab"><b><i class="fa-solid fa-route"></i> Entrega acompanhada no mapa</b></div>
            <p class="en-txt">Depois que o pagamento for confirmado, o vendedor escolhe quem entrega e você acompanha o trajeto e o tempo aqui.</p>${acoesComprador(p, em)}</div>` : '';
        if (p.status === 'concluido') return `<div class="en-bloco fim" data-pid="${Number(p.id)}"><div class="en-cab"><b><i class="fa-solid fa-route"></i> Entrega</b>${chip('entregue')}</div>
            <p class="en-txt">${em.entregador ? `Entregue por <b>${pessoa(em.entregador)}</b>${em.entregue_em ? ` às ${esc(em.entregue_em)}` : ''}.` : 'Pedido concluído.'} O ponto de entrega e o endereço foram apagados.</p></div>`;
        const aCaminho = p.status === 'a_caminho';
        const temMapa = !!(em.destino || em.loja || em.ultima);
        let msg = '';
        if (p.status === 'entregue') msg = comprador ? '<b>O entregador marcou como entregue.</b> Confirme abaixo que você recebeu.' : 'O entregador marcou como entregue. Falta o comprador confirmar.';
        else if (aCaminho) msg = comprador ? `<b>${pessoa(em.entregador)}</b> está levando o seu pedido${em.transporte ? ` de ${esc((NOME[em.transporte] || '').toLowerCase())}` : ''}. Você pode confirmar o recebimento quando ele chegar.` : `<b>${pessoa(em.entregador)}</b> está a caminho com o pedido.`;
        else if (!em.estado) msg = comprador ? 'O vendedor ainda vai escolher quem entrega.' : '';
        else if (em.estado === 'aceita') msg = comprador ? `<b>${pessoa(em.entregador)}</b> vai entregar e ainda não saiu.` : '';
        return `<div class="en-bloco" data-pid="${Number(p.id)}">
            <div class="en-cab"><b><i class="fa-solid fa-route"></i> Entrega acompanhada no mapa</b>${chip(p.status === 'entregue' ? 'entregue' : em.estado)}</div>
            ${msg ? `<p class="en-txt">${msg}</p>` : ''}
            <div class="en-info" data-pid="${Number(p.id)}">${infoHtml(p.id, aCaminho)}</div>
            ${temMapa ? `<div class="en-slot" data-slot="modal"><button type="button" class="en-centro" data-a="en-centro" title="Centralizar o mapa" aria-label="Centralizar o mapa"><i class="fa-solid fa-expand"></i></button>
                <div class="en-legenda"><span><i class="fa-solid fa-store"></i> loja</span><span><i class="fa-solid fa-house"></i> destino</span>${aCaminho ? `<span><i class="fa-solid ${iconeDe(em.transporte)}"></i> entregador</span>` : ''}</div></div>` : ''}
            ${acoesComprador(p, em)}${acoesVendedor(p, em)}${acoesEntregador(p, em)}
        </div>`;
    }

    /** Depois que o Bazar desenha o modal do pedido: liga o mapa no lugar certo (ou desliga se não há mapa). */
    function aposPedido(p, el) {
        const em = p.entrega_mapa;
        const slot = el ? el.querySelector('.en-slot[data-slot="modal"]') : null;
        if (!em || !slot) { if (mini && mini.dono === 'modal') destruir(); return; }
        montar(slot, dadosDoMapa(p.id, { ...em, estado: p.status === 'a_caminho' ? 'a_caminho' : em.estado }), 'modal');
    }

    function fechou(tipo) { if (tipo === 'pedido' && mini && mini.dono === 'modal') destruir(); }

    /** Todo `bazar_pedido` que chega passa por aqui: guarda a última posição e liga/desliga o GPS de quem está entregando. */
    function aoPedido(p) {
        const em = p.entrega_mapa;
        if (!em) return;
        if (em.ultima && em.estado === 'a_caminho') guardarPosicao(p.id, { ...em.ultima, idade_s: em.ultima.idade_s || 0 }, false);
        if (em.estado !== 'a_caminho') vivos.delete(p.id);
        if (em.eu_entrego && em.estado === 'a_caminho' && p.status === 'a_caminho') meusAtivos.add(p.id); else meusAtivos.delete(p.id);
        conferirGps();
    }

    // ---------------------------------------------------------------------
    // POSIÇÃO AO VIVO
    // ---------------------------------------------------------------------
    function guardarPosicao(pid, d, animar) {
        const antes = vivos.get(pid);
        const trilha = antes ? antes.trilha : [];
        const ll = [d.lat, d.lng];
        const ult = trilha[trilha.length - 1];
        if (!ult || ult[0] !== ll[0] || ult[1] !== ll[1]) { trilha.push(ll); if (trilha.length > 150) trilha.shift(); }
        vivos.set(pid, { lat: d.lat, lng: d.lng, visto: Date.now() - (Number(d.idade_s) || 0) * 1000, dist_m: d.dist_m, eta_s: d.eta_s, chegando: !!d.chegando, trilha, semGps: false });
    }

    function aoVivo(d) {
        if (!d || !d.pedido_id) return;
        guardarPosicao(d.pedido_id, d, true);
        atualizarTextos(d.pedido_id);
        if (mini && mini.pid === d.pedido_id) {
            desenharMini({ ...mini.d, ent: { lat: d.lat, lng: d.lng }, aCaminho: true, transporte: d.transporte || mini.d.transporte }, true);
            ajustar();
        }
    }

    function sinal(d) {
        if (!d || !d.pedido_id) return;
        const v = vivos.get(d.pedido_id);
        if (v) v.semGps = !d.ok;
        if (!d.ok && Date.now() - avisouSinal > 30000) { avisouSinal = Date.now(); ctx.toast(d.motivo || 'Sem GPS do aparelho.', 'warning'); }
        atualizarTextos(d.pedido_id);
    }

    function atualizarTextos(pid) {
        document.querySelectorAll(`.en-info[data-pid="${pid}"]`).forEach((el) => { el.innerHTML = infoHtml(pid, true); });
        document.querySelectorAll(`.en-card[data-pid="${pid}"] .en-info-card`).forEach((el) => { el.innerHTML = infoHtml(pid, true); });
    }

    function conferirGps() {
        const precisa = meusAtivos.size > 0;
        try { if (precisa) localStorage.setItem('pnt_entregando', '1'); else localStorage.removeItem('pnt_entregando'); } catch (e) { /* sem armazenamento */ }
        if (precisa && !timerGps) {
            // o mapa só reanuncia a posição a cada 45 s quando você está parado; durante a entrega o servidor quer sinal de poucos em poucos segundos
            timerGps = setInterval(() => { try { ctx.reanunciar(); } catch (e) { /* sem mapa */ } }, 8000);
            try { ctx.reanunciar(); } catch (e) { /* sem mapa */ }
        } else if (!precisa && timerGps) { clearInterval(timerGps); timerGps = 0; }
        if ((precisa || vivos.size) && !timerRelogio) timerRelogio = setInterval(() => { vivos.forEach((_, pid) => atualizarTextos(pid)); if (!vivos.size) { clearInterval(timerRelogio); timerRelogio = 0; } }, 5000);
    }

    // ---------------------------------------------------------------------
    // PAINEL "ENTREGAS" (quem faz entregas)
    // ---------------------------------------------------------------------
    function estado(d) {
        painel = { cadastro: d.cadastro || { ativo: false, entregas: 0 }, entregas: d.entregas || [], carregado: true };
        const vi = new Set();
        painel.entregas.forEach((e) => {
            if (e.estado === 'a_caminho') {
                vi.add(e.pedido_id);
                if (e.ultima) guardarPosicao(e.pedido_id, e.ultima, false);
                if (!retomados.has(e.pedido_id)) { retomados.add(e.pedido_id); ctx.emitir('entrega_retomar', { pedido_id: e.pedido_id }); }
            } else { retomados.delete(e.pedido_id); vivos.delete(e.pedido_id); }
        });
        // mantém os pedidos em que sou o vendedor-entregador (vêm também no painel, então o conjunto é refeito por inteiro)
        meusAtivos.clear(); vi.forEach((x) => meusAtivos.add(x));
        conferirGps();
        if (ctx.aoMudar) ctx.aoMudar();
    }

    const pendentes = () => painel.entregas.filter((e) => e.estado === 'convidado').length;

    function cartaoEntrega(e) {
        const a = e.estado;
        const pid = Number(e.pedido_id);
        const v = e.vendedor;
        let corpo = '';
        if (a === 'convidado') {
            corpo = `<p class="en-txt"><b>${pessoa(v)}</b> (${esc(e.loja_nome)}) quer que você entregue <b>${Number(e.quantidade)}x ${esc(e.produto_nome)}</b>${e.dist_km != null ? `, a uns <b>${esc(String(e.dist_km).replace('.', ','))} km</b> da loja` : ''}.
                    O endereço só aparece depois que você aceitar. O que combinar com a loja pelo trabalho é entre vocês.</p>
                <div class="en-linha"><button type="button" class="bz-btn verde pq" data-a="en-aceitar" data-id="${pid}"><i class="fa-solid fa-check"></i> Aceitar</button>
                <button type="button" class="bz-btn sec pq" data-a="en-recusar" data-id="${pid}">Agora não</button></div>`;
        } else {
            const dest = e.endereco ? `<div class="en-end"><i class="fa-solid fa-location-dot"></i> <span>${esc(e.endereco)}</span></div>` : '';
            const quem = e.comprador ? `<p class="en-txt">Entregar <b>${Number(e.quantidade)}x ${esc(e.produto_nome)}</b> para <b>${pessoa(e.comprador)}</b>, vindo de <b>${esc(e.loja_nome)}</b>.</p>` : '';
            if (a === 'aceita') {
                corpo = `${quem}${dest}<div class="en-slot" data-slot="painel" data-pid="${pid}"><button type="button" class="en-centro" data-a="en-centro" aria-label="Centralizar o mapa"><i class="fa-solid fa-expand"></i></button></div>
                    <div class="en-linha">${selectTransporte(e.transporte || 'moto', 'transporte-saida')}</div>
                    <label class="en-consent"><input type="checkbox" data-en-campo="consentimento"><span>${textoConsentimento}</span></label>
                    <button type="button" class="bz-btn verde" data-a="en-sair" data-id="${pid}"><i class="fa-solid fa-route"></i> Sair para entrega</button>`;
            } else if (a === 'a_caminho') {
                corpo = `${quem}${dest}<div class="en-info-card">${infoHtml(pid, true)}</div>
                    <div class="en-slot" data-slot="painel" data-pid="${pid}"><button type="button" class="en-centro" data-a="en-centro" aria-label="Centralizar o mapa"><i class="fa-solid fa-expand"></i></button></div>
                    <div class="en-linha"><button type="button" class="bz-btn verde" data-a="en-entregue" data-id="${pid}" data-conf="Confirma que entregou o pedido? O compartilhamento da sua posição acaba agora."><i class="fa-solid fa-box-open"></i> Entreguei</button>
                    <button type="button" class="bz-btn sec" data-a="en-parar" data-id="${pid}" data-conf="Parar de compartilhar a sua posição? O pedido volta a &quot;pronto pra sair&quot; e você pode sair de novo.">Parar de compartilhar</button></div>`;
            }
        }
        return `<div class="en-card" data-pid="${pid}"><div class="en-cab"><b>${esc(e.produto_nome)}</b>${chip(a, a === 'convidado' ? 'Convite pra você' : null)}</div>${corpo}</div>`;
    }

    function htmlPainel() {
        const c = painel.cadastro;
        const cad = c.ativo
            ? `<div class="en-bloco"><div class="en-cab"><b><i class="fa-solid fa-motorcycle"></i> Você faz entregas</b><span class="en-chip aceita">Ativo</span></div>
                <p class="en-txt">Lojas podem te chamar pelo seu @. Você só compartilha a sua posição durante uma entrega que você mesmo iniciar${c.entregas ? `. Entregas feitas: <b>${Number(c.entregas)}</b>` : ''}.</p>
                <button type="button" class="bz-btn sec pq" data-a="en-cadastro-off" data-conf="Deixar de fazer entregas? Convites em aberto são cancelados.">Deixar de fazer entregas</button></div>`
            : `<div class="en-bloco"><div class="en-cab"><b><i class="fa-solid fa-motorcycle"></i> Quero fazer entregas</b></div>
                <p class="en-txt">Lojas do Bazar podem te chamar pra levar pedidos. Quem aceita um convite sai quando quiser; <b>nada de posição é compartilhado fora de uma entrega</b>. O Pantheon não paga nem cobra: o combinado é entre você e a loja.</p>
                <label class="en-consent"><input type="checkbox" data-en-campo="cadastro-ok"><span><b>Entendi:</b> quando eu sair para entregar, o comprador e o vendedor daquele pedido veem a minha posição ao vivo, e só durante a entrega. Posso parar quando quiser.</span></label>
                <button type="button" class="bz-btn verde" data-a="en-cadastro-on"><i class="fa-solid fa-check"></i> Me cadastrar como entregador</button></div>`;
        const lista = painel.carregado
            ? (painel.entregas.length ? painel.entregas.map(cartaoEntrega).join('') : '<div class="bz-vazio"><i class="fa-solid fa-route"></i>Nenhuma entrega no momento. Convites e entregas aceitas aparecem aqui.</div>')
            : '<div class="bz-vazio"><i class="fa-solid fa-spinner fa-spin"></i>Carregando suas entregas...</div>';
        return `<div class="en-painel">${cad}<h3 class="en-h">Suas entregas</h3>${lista}</div>`;
    }

    function aposPainel(raiz) {
        if (!raiz) return;
        const slot = raiz.querySelector('.en-slot[data-slot="painel"]');
        if (!slot) { if (mini && mini.dono === 'painel') destruir(); return; }
        if (mini && mini.dono === 'modal' && mini.el.isConnected) return;          // o modal do pedido está na frente: o mapa é dele
        const e = painel.entregas.find((x) => x.pedido_id === Number(slot.dataset.pid));
        if (!e) return;
        montar(slot, dadosDoMapa(e.pedido_id, e), 'painel');
    }

    function carregar() { ctx.emitir('entregador_meu_estado', {}); }

    // ---------------------------------------------------------------------
    // CLIQUES (delegados pelo Bazar: data-a="en-...")
    // ---------------------------------------------------------------------
    function campo(b, nome) {
        const alvo = b.closest('.en-bloco, .en-card') || document;
        return alvo.querySelector(`[data-en-campo="${nome}"]`);
    }

    function clique(b) {
        const a = b.dataset.a, id = Number(b.dataset.id);
        const fazer = () => {
            switch (a) {
                case 'en-eu': ctx.emitir('entrega_designar', { pedido_id: id, quem: 'eu', transporte: (campo(b, 'transporte') || {}).value }); break;
                case 'en-chamar': {
                    const alvo = ((campo(b, 'alvo') || {}).value || '').trim();
                    if (!alvo) { ctx.toast('Escreva o @ do entregador.', 'warning'); return; }
                    ctx.emitir('entrega_designar', { pedido_id: id, quem: 'outro', alvo, transporte: (campo(b, 'transporte') || {}).value }); break;
                }
                case 'en-aceitar': ctx.emitir('entrega_responder', { pedido_id: id, aceitar: true }); break;
                case 'en-recusar': ctx.emitir('entrega_responder', { pedido_id: id, aceitar: false }); break;
                case 'en-sair': {
                    const ok = campo(b, 'consentimento');
                    if (!ok || !ok.checked) { ctx.toast('Marque que você entendeu como funciona o compartilhamento da posição.', 'warning'); return; }
                    ctx.emitir('entrega_sair', { pedido_id: id, consentimento: true, transporte: (campo(b, 'transporte-saida') || {}).value }); break;
                }
                case 'en-parar': ctx.emitir('entrega_parar', { pedido_id: id }); break;
                case 'en-entregue': ctx.emitir('entrega_entregue', { pedido_id: id }); break;
                case 'en-destino': ctx.emitir('entrega_destino', { pedido_id: id }); break;
                case 'en-destino-limpar': ctx.emitir('entrega_destino', { pedido_id: id, limpar: true }); break;
                case 'en-cadastro-on': {
                    const ok = campo(b, 'cadastro-ok');
                    if (!ok || !ok.checked) { ctx.toast('Marque que você entendeu antes de se cadastrar.', 'warning'); return; }
                    ctx.emitir('entregador_cadastrar', { ativo: true, consentimento: true }); break;
                }
                case 'en-cadastro-off': ctx.emitir('entregador_cadastrar', { ativo: false }); break;
                case 'en-centro': if (mini) { mini.livre = false; ajustar(); } break;
                default: break;
            }
        };
        if (b.dataset.conf && ctx.confirmar) ctx.confirmar('Confirmar', b.dataset.conf, fazer); else fazer();
    }

    function iniciar(c) {
        ctx = c;
        // quem estava entregando antes de recarregar a página volta a compartilhar sozinho (o servidor só confere e reabre a entrega)
        try { if (localStorage.getItem('pnt_entregando') === '1') carregar(); } catch (e) { /* sem armazenamento */ }
    }

    return { iniciar, htmlPedido, aposPedido, aoPedido, fechou, aoVivo, sinal, estado, htmlPainel, aposPainel, carregar, clique, pendentes };
})();
