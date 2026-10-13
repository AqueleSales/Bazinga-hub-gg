/* Mapa social: localizar um amigo, a lista de amigos e a de servidores no alcance, e o radar de pessoas por perto.
   Só desenha e mexe no mapa: quem aparece, o ruído da posição (radar) e a prévia segura (servidores) são decididos no SERVIDOR.
   Objeto global `MapaSocial`. Contexto (MapaSocial.iniciar):
     { emitir, esc, escUrl, toast, mapa(), eu(), pinos(), servidores(), amigos(), distancia(a,b,c,d), soltarLimites(), restaurarLimites(),
       irParaRadar(), explorando(), sairDoExplorar(), mapaVisivel() }
   Tudo que vem do servidor passa por esc()/escUrl() antes do innerHTML. Animações: só transform/opacity (e o círculo do radar, por poucos segundos). */
const MapaSocial = (() => {
    let ctx = null;
    let voltarTimer = null, contagemTimer = null, faixa = null, pinoDestacado = null, ocupado = false;
    let radarLigado = false, timerRadar = null, camadasRadar = [], avisouMotivo = {};

    const $ = (id) => document.getElementById(id);
    const dist = (m) => m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(m < 10000 ? 1 : 0).replace('.', ',')} km`;
    const inicial = (n) => ((n || '?').trim()[0] || '?').toUpperCase();

    // ---------------------------------------------------------------------
    // IR ATÉ UM PONTO por alguns segundos e voltar pra mim ("Localizar" / "Ver no mapa")
    // ---------------------------------------------------------------------
    function limparDestaque() {
        if (pinoDestacado) { const el = pinoDestacado.getElement && pinoDestacado.getElement(); if (el) el.classList.remove('ms-destaque'); try { pinoDestacado.closePopup(); } catch (e) {} }
        pinoDestacado = null;
    }

    function fecharFaixa() { clearInterval(contagemTimer); if (faixa) { faixa.remove(); faixa = null; } }

    function voltar() {
        clearTimeout(voltarTimer); fecharFaixa(); limparDestaque();
        if (!ocupado) return;
        ocupado = false;
        const m = ctx.mapa(), eu = ctx.eu();
        ctx.restaurarLimites();
        if (m && eu) m.flyTo(eu.getLatLng(), 16, { duration: 0.9 });
    }

    function irAte(latlng, rotulo, pino, segundos) {
        const m = ctx.mapa();
        if (!m) return;
        segundos = segundos || 8;
        if (ctx.explorando()) ctx.sairDoExplorar();
        ctx.irParaRadar();
        setTimeout(() => {
            m.invalidateSize();
            clearTimeout(voltarTimer); fecharFaixa(); limparDestaque();
            ocupado = true;
            ctx.soltarLimites();
            m.flyTo(latlng, Math.max(m.getZoom(), 16), { duration: 1.1 });
            if (pino && pino.getElement) {
                const el = pino.getElement();
                if (el) el.classList.add('ms-destaque');
                pinoDestacado = pino;
                m.once('moveend', () => { try { if (pinoDestacado === pino) pino.openPopup(); } catch (e) {} });
            }
            let resta = segundos;
            faixa = document.createElement('div');
            faixa.className = 'ms-faixa';
            faixa.innerHTML = `<span><i class="fa-solid fa-location-crosshairs"></i> <b></b> · voltando em <u>${resta}</u>s</span><button type="button">Voltar agora</button>`;
            faixa.querySelector('b').textContent = rotulo;
            faixa.querySelector('button').addEventListener('click', voltar);
            if (window.L) L.DomEvent.disableClickPropagation(faixa);
            m.getContainer().appendChild(faixa);
            contagemTimer = setInterval(() => { resta -= 1; const u = faixa && faixa.querySelector('u'); if (u) u.textContent = Math.max(resta, 0); }, 1000);
            voltarTimer = setTimeout(voltar, (segundos + 1.2) * 1000);   // a viagem de ida leva ~1 s: os 8 s contam depois de chegar
        }, 160);
    }

    function localizar(id, nome) {
        const pino = (ctx.pinos() || {})[id];
        if (!pino) {
            ctx.toast(`${nome || 'Essa pessoa'} não aparece no mapa agora (pode estar offline, com o Modo Fantasma ou com a localização desligada).`, 'info');
            return;
        }
        irAte(pino.getLatLng(), nome || 'amigo', pino, 8);
    }

    // ---------------------------------------------------------------------
    // PAINÉIS (popup no computador, folha de baixo no celular)
    // ---------------------------------------------------------------------
    function fecharPainel() { const f = $('ms-fundo'); if (f) f.remove(); }

    function abrirPainel(titulo, sub, icone, corpo) {
        fecharPainel();
        const f = document.createElement('div');
        f.id = 'ms-fundo'; f.className = 'ms-fundo';
        f.innerHTML = `<div class="ms-card" role="dialog" aria-modal="true" aria-label="${ctx.esc(titulo)}">
            <header><i class="fa-solid ${icone}"></i><div><b>${ctx.esc(titulo)}</b><small>${ctx.esc(sub)}</small></div>
                <button type="button" class="ms-x" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button></header>
            <div class="ms-lista">${corpo}</div></div>`;
        document.body.appendChild(f);
        f.addEventListener('mousedown', (e) => { if (e.target === f) fecharPainel(); });
        f.querySelector('.ms-x').addEventListener('click', fecharPainel);
        return f;
    }

    function precisoDePosicao() {
        if (ctx.eu()) return false;
        ctx.toast('Ainda estou achando a sua posição. Espere o mapa te encontrar.', 'info');
        return true;
    }

    function abrirAmigos() {
        const pinos = ctx.pinos() || {}, eu = ctx.eu();
        const linhas = (ctx.amigos() || []).map((a) => {
            const p = pinos[a.id];
            let d = null;
            if (p && eu) { const l = eu.getLatLng(), q = p.getLatLng(); d = ctx.distancia(l.lat, l.lng, q.lat, q.lng); }
            return { a, no: !!p, d };
        }).sort((x, y) => (y.no - x.no) || ((x.d ?? 1e12) - (y.d ?? 1e12)) || String(x.a.nome).localeCompare(String(y.a.nome)));
        const noMapa = linhas.filter((l) => l.no).length;
        const corpo = linhas.length ? linhas.map(({ a, no, d }) => {
            const foto = a.avatar ? ctx.escUrl(a.avatar) : '';
            return `<button type="button" class="ms-linha ${no ? '' : 'fora'}" data-amigo="${Number(a.id)}" ${no ? '' : 'aria-disabled="true"'}>
                <span class="ms-av ${a.online ? 'on' : ''}">${foto ? `<img src="${foto}" alt="" loading="lazy">` : ctx.esc(inicial(a.nome))}</span>
                <span class="ms-txt"><b>${ctx.esc(a.nome)}</b><small>${no ? (d != null ? `a ${dist(d)} de você` : 'no mapa') : 'fora do mapa agora'}</small></span>
                <i class="fa-solid ${no ? 'fa-location-crosshairs' : 'fa-ghost'} ms-ico"></i></button>`;
        }).join('') : '<div class="ms-vazio">Você ainda não tem amigos por aqui. Adicione alguém na tela de Amigos.</div>';
        const f = abrirPainel('Amigos no mapa', linhas.length ? `${noMapa} de ${linhas.length} aparecem agora. Toque num amigo: o mapa vai até ele e volta pra você em 8 s.` : 'Veja onde seus amigos estão.', 'fa-user-group', corpo);
        f.addEventListener('click', (e) => {
            const b = e.target.closest('[data-amigo]'); if (!b) return;
            const id = Number(b.dataset.amigo), l = linhas.find((x) => Number(x.a.id) === id);
            if (!l || !l.no) { ctx.toast(`${l ? l.a.nome : 'Essa pessoa'} não aparece no mapa agora.`, 'info'); return; }
            fecharPainel(); localizar(id, l.a.nome);
        });
    }

    function abrirServidores() {
        if (precisoDePosicao()) return;
        const eu = ctx.eu().getLatLng();
        const linhas = (ctx.servidores() || []).map((s) => ({ s, d: ctx.distancia(eu.lat, eu.lng, s.lat, s.lng) })).sort((x, y) => x.d - y.d);
        const corpo = linhas.length ? linhas.map(({ s, d }) => {
            const foto = s.iconUrl ? ctx.escUrl(s.iconUrl) : '';
            const vagas = s.vagas === 'ilimitado' ? 'sem limite de vagas' : `${Number(s.online) || 0}/${Number(s.vagas)} vagas`;
            const ini = ctx.esc(((s.nome || '?').trim()[0] || '?').toUpperCase());
            return `<div class="ms-linha servidor" data-srv="${Number(s.serverId) || 0}" data-pino="${Number(s.id)}" role="button" tabindex="0">
                <span class="ms-av quadrado">${foto ? `<img src="${foto}" alt="" loading="lazy">` : ini}</span>
                <span class="ms-txt"><b>${ctx.esc(s.nome)}</b><small>${Number(s.online) || 0} ${Number(s.online) === 1 ? 'membro' : 'membros'} · ${vagas} · a ${dist(d)}</small></span>
                <button type="button" class="ms-mini" data-ver="${Number(s.id)}" title="Ver no mapa"><i class="fa-solid fa-map-pin"></i></button>
                <i class="fa-solid fa-chevron-right ms-ico"></i></div>`;
        }).join('') : '<div class="ms-vazio">Nenhum servidor plantado no seu alcance. Dá pra plantar o seu pelo botão “Plantar Servidor”.</div>';
        const f = abrirPainel('Servidores no seu alcance', linhas.length ? `${linhas.length} ${linhas.length === 1 ? 'servidor plantado' : 'servidores plantados'} por perto. Toque num pra ver a prévia.` : 'Servidores plantados por perto aparecem aqui.', 'fa-tower-broadcast', corpo);
        const abrir = (el) => {
            const id = Number(el.dataset.srv);
            if (!id) { ctx.toast('Esse pino ainda não está ligado a um servidor de chat.', 'warning'); return; }
            ctx.emitir('mapa_servidor_previa', { server_id: id });
        };
        f.addEventListener('click', (e) => {
            const ver = e.target.closest('[data-ver]');
            if (ver) {
                e.stopPropagation();
                const s = (ctx.servidores() || []).find((x) => Number(x.id) === Number(ver.dataset.ver));
                if (s) { fecharPainel(); irAte({ lat: s.lat, lng: s.lng }, s.nome, s.marker, 8); }
                return;
            }
            const l = e.target.closest('.ms-linha.servidor'); if (l) abrir(l);
        });
        f.addEventListener('keydown', (e) => { if (e.key === 'Enter') { const l = e.target.closest('.ms-linha.servidor'); if (l) abrir(l); } });
    }

    // ---------------------------------------------------------------------
    // RADAR DE PESSOAS POR PERTO: sinais anônimos e aproximados (o servidor borra a posição e só entrega quem também ligou)
    // ---------------------------------------------------------------------
    function limparBlips() { camadasRadar.forEach((c) => { try { c.remove(); } catch (e) {} }); camadasRadar = []; }

    function piscar(lat, lng, grade) {
        const m = ctx.mapa();
        if (!m || !window.L) return;
        const anel = L.circle([lat, lng], { radius: (grade || 200) / 2, className: 'ms-blip', interactive: false, color: '#9ff3e6', weight: 1.5, fillColor: '#9ff3e6', fillOpacity: .18 }).addTo(m);
        const ponto = L.circleMarker([lat, lng], { radius: 4, className: 'ms-blip-ponto', interactive: false, color: '#e9fffb', weight: 1, fillColor: '#e9fffb', fillOpacity: .9 }).addTo(m);
        camadasRadar.push(anel, ponto);
        setTimeout(() => { try { anel.remove(); ponto.remove(); } catch (e) {} camadasRadar = camadasRadar.filter((c) => c !== anel && c !== ponto); }, 4300);
    }

    function pedirRadar() {
        if (!radarLigado || document.hidden || !ctx.eu() || ctx.explorando() || !ctx.mapaVisivel()) return;
        ctx.emitir('mapa_radar_pedir', {});
    }

    const MOTIVOS = {
        fantasma: 'Radar de pessoas pausado: o Modo Fantasma está ligado. Quem quer ver precisa poder ser visto.',
        sem_localizacao: 'Radar de pessoas pausado: a localização está desligada.',
        sem_posicao: 'Radar de pessoas esperando a posição do aparelho (GPS ou Wi-Fi). Por IP ele não funciona.',
    };

    function ligarRadar(ativo) {
        ativo = !!ativo;
        if (ativo === radarLigado) return;
        radarLigado = ativo;
        clearInterval(timerRadar); timerRadar = null;
        if (ativo) { avisouMotivo = {}; setTimeout(pedirRadar, 600); timerRadar = setInterval(pedirRadar, 20000); }
        else limparBlips();
    }

    function receberRadar(d) {
        if (!radarLigado) return;
        if (!d.ativo) {
            const t = MOTIVOS[d.motivo];
            if (t && !avisouMotivo[d.motivo]) { avisouMotivo[d.motivo] = true; ctx.toast(t, 'info'); }
            return;
        }
        (d.blips || []).forEach((b) => piscar(b.lat, b.lng, d.grade_m));
    }

    // ---------------------------------------------------------------------
    return {
        iniciar(c) {
            ctx = c;
            document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && $('ms-fundo')) { e.stopImmediatePropagation(); fecharPainel(); } }, true);
        },
        localizar, irAte, abrirAmigos, abrirServidores, ligarRadar, receberRadar, fecharPainel, voltar,
        /** A 1ª posição chegou: com o radar ligado, o 1º sinal já vem (senão esperava o próximo ciclo de 20 s). */
        aoTerPosicao() { if (radarLigado) setTimeout(pedirRadar, 900); },
        ocupado: () => ocupado,
        radarLigado: () => radarLigado,
        _piscar: piscar,
    };
})();
