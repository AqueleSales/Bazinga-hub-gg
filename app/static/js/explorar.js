/* Explorar servidores: um MAR com barquinhos (cada um é um servidor público), as TERRAS com os recomendados e listas por tema.
   Só desenha: o que é público, quantos membros e quem pode entrar são do servidor (evento 'explorar'). Objeto global `Explorar`.
   Contexto (Explorar.iniciar): { emitir, esc, escUrl, toast }. Tudo que vem do servidor passa por esc()/escUrl() antes do innerHTML.
   Animação: só `transform` (os barcos navegam por translateX e balançam por rotate), pausa ao passar o mouse e com a aba escondida. */
const Explorar = (() => {
    let ctx = null, S = null, seed = '', tema = '', busca = '', timer = null, previa = null;
    const $ = (s, r) => (r || document).querySelector(s);
    const raiz = () => document.getElementById('explorar-modal');
    const num = (n) => Number(n || 0).toLocaleString('pt-BR');
    const corOk = (c, p) => (typeof c === 'string' && /^#[0-9a-fA-F]{6}$/.test(c)) ? c : p;

    // ---------------------------------------------------------------------
    // BARCOS (SVG chapado; quanto maior o servidor, mais barco)
    // ---------------------------------------------------------------------
    function svgBarco(porte, cor) {
        const casco = corOk(cor, '#8b5a2b'), vela = '#f4efe2', mastro = '#4a2f17';
        const velas = {
            1: '',
            2: `<line x1="60" y1="14" x2="60" y2="62" stroke="${mastro}" stroke-width="3"/><path d="M62 16 L62 58 L98 58Z" fill="${vela}"/><path d="M58 22 L58 58 L34 58Z" fill="${vela}" opacity=".85"/><path d="M60 14 L74 18 L60 22Z" fill="#e8483f"/>`,
            3: `<line x1="42" y1="16" x2="42" y2="62" stroke="${mastro}" stroke-width="3"/><line x1="82" y1="10" x2="82" y2="62" stroke="${mastro}" stroke-width="3"/><path d="M44 18 L44 58 L72 58Z" fill="${vela}"/><path d="M84 12 L84 58 L112 58Z" fill="${vela}"/><path d="M40 24 L40 58 L18 58Z" fill="${vela}" opacity=".85"/><path d="M82 10 L96 14 L82 18Z" fill="#e8483f"/>`,
            4: `<line x1="34" y1="18" x2="34" y2="62" stroke="${mastro}" stroke-width="3"/><line x1="64" y1="6" x2="64" y2="62" stroke="${mastro}" stroke-width="3"/><line x1="94" y1="14" x2="94" y2="62" stroke="${mastro}" stroke-width="3"/><path d="M36 20 L36 58 L56 58Z" fill="${vela}"/><path d="M66 8 L66 58 L90 58Z" fill="${vela}"/><path d="M96 16 L96 58 L116 58Z" fill="${vela}"/><path d="M62 54 L62 58 L38 58Z" fill="${vela}" opacity=".8"/><rect x="100" y="48" width="16" height="14" fill="${mastro}"/><path d="M64 6 L80 10 L64 14Z" fill="#e8483f"/>`,
        }[porte];
        const barco = porte === 1
            ? `<path d="M22 66 Q60 96 98 66Z" fill="${casco}"/><path d="M22 66 H98" stroke="${mastro}" stroke-width="3"/>`
            : `<path d="M8 62 H112 L98 84 Q96 88 90 88 H30 Q24 88 22 84Z" fill="${casco}"/><path d="M8 62 H112" stroke="${mastro}" stroke-width="3"/><path d="M14 70 H106" stroke="rgba(255,255,255,.35)" stroke-width="2"/>`;
        return `<svg viewBox="0 0 120 100" aria-hidden="true">${velas}${barco}</svg>`;
    }

    function iconeHtml(it, tam) {
        const u = it.icone ? ctx.escUrl(it.icone) : '';
        const c = corOk(it.cor, '#5865f2');
        return `<span class="ex-ico" style="width:${tam}px;height:${tam}px;background:${c};font-size:${Math.round(tam * 0.42)}px">${u ? `<img src="${u}" alt="" loading="lazy">` : ctx.esc((it.nome || '?')[0].toUpperCase())}</span>`;
    }

    const FATOR = { 1: 0.72, 2: 0.95, 3: 1.2, 4: 1.5 };
    const ROTULO_PORTE = { 1: 'canoa', 2: 'veleiro', 3: 'caravela', 4: 'galeão' };

    function barco(it, i, total) {
        const f = FATOR[it.porte] || 1, larg = Math.round(96 * f);
        const faixa = 0 + (i % 4) * 15;                                  // 4 faixas de água, uma sob a outra
        const dur = 46 + ((i * 37) % 30) - it.porte * 3;                // devagar: dá tempo de clicar
        const atraso = -((i * 53) % 100) / 100 * dur;                    // já espalhados pelo mar
        return `<button type="button" class="ex-barco" data-id="${Number(it.id)}" style="--f:${f};top:${faixa}%;--dur:${dur}s;--atraso:${atraso.toFixed(1)}s" title="${ctx.esc(it.nome)}: ${num(it.membros)} membros (${ROTULO_PORTE[it.porte]})">
            <span class="ex-balanca">${iconeHtml(it, Math.round(34 * Math.max(f, 0.9)))}<span class="ex-vela" style="width:${larg}px">${svgBarco(it.porte, it.cor)}</span><span class="ex-nome-barco">${ctx.esc(it.nome)}</span></span></button>`;
    }

    // ---------------------------------------------------------------------
    // TERRA E LISTAS
    // ---------------------------------------------------------------------
    function cartao(it) {
        const t = ((S && S.temas) || []).find((x) => x.id === it.tema);
        return `<button type="button" class="ex-casa" data-id="${Number(it.id)}" style="--c:${corOk(it.cor, '#5865f2')}">
            ${iconeHtml(it, 48)}<span class="ex-casa-t"><b>${ctx.esc(it.nome)}</b><small><i class="fa-solid fa-user-group"></i> ${num(it.membros)} · ${t ? ctx.esc(t.nome) : ''}</small><span class="ex-casa-d">${ctx.esc(it.descricao || 'Sem descrição.')}</span></span></button>`;
    }

    function desenhar() {
        const r = raiz();
        if (!r || !S) return;
        const sem = !S.mar.length;
        $('#ex-chips', r).innerHTML = `<button type="button" class="ex-chip ${S.tema === '' ? 'ativo' : ''}" data-tema="">Todos</button>` + S.temas.map((t) =>
            `<button type="button" class="ex-chip ${S.tema === t.id ? 'ativo' : ''} ${t.qtd || S.tema === t.id ? '' : 'vazio'}" data-tema="${ctx.esc(t.id)}" style="--c:${ctx.esc(t.cor)}"><i class="fa-solid ${ctx.esc(t.icone)}"></i> ${ctx.esc(t.nome)}${t.qtd ? ` <b>${t.qtd}</b>` : ''}</button>`).join('');
        $('#ex-mar', r).innerHTML = sem ? '' : S.mar.map((it, i) => barco(it, i, S.mar.length)).join('');
        $('#ex-vazio', r).style.display = sem ? 'block' : 'none';
        $('#ex-vazio', r).innerHTML = S.busca || S.tema ? 'Nenhum barco encontrado. Tente outra palavra ou outro tema.' : 'O mar está vazio por enquanto. Seja o primeiro: deixe o seu servidor público nas configurações dele.';
        $('#ex-terra-lista', r).innerHTML = S.terra.map(cartao).join('');
        $('#ex-terra', r).style.display = S.terra.length ? 'block' : 'none';
        const temas = Object.keys(S.por_tema || {});
        $('#ex-temas', r).innerHTML = temas.map((id) => {
            const t = S.temas.find((x) => x.id === id) || {};
            return `<section class="ex-bloco"><h3 style="--c:${ctx.esc(t.cor || '#8ea0ba')}"><i class="fa-solid ${ctx.esc(t.icone || 'fa-ellipsis')}"></i> ${ctx.esc(t.nome || id)} <button type="button" class="ex-ver" data-tema="${ctx.esc(id)}">ver só esse mar</button></h3><div class="ex-fila">${S.por_tema[id].map(cartao).join('')}</div></section>`;
        }).join('');
        $('#ex-contagem', r).textContent = S.total ? `${num(S.total)} servidor${S.total > 1 ? 'es' : ''} ${S.busca ? 'na busca' : 'navegando'}` : '';
    }

    // ---------------------------------------------------------------------
    // PRÉVIA (sem mensagens, sem membros nominais, sem canal privado: vem assim do servidor)
    // ---------------------------------------------------------------------
    function fecharPrevia() { document.getElementById('ex-previa')?.remove(); previa = null; }

    function mostrarPrevia(p) {
        fecharPrevia();
        previa = p;
        const t = ((S && S.temas) || []).find((x) => x.id === p.tema);
        const m = document.createElement('div');
        m.id = 'ex-previa'; m.className = 'ex-previa-fundo';
        m.innerHTML = `<div class="ex-previa" role="dialog" aria-modal="true" aria-label="${ctx.esc(p.nome)}">
            <div class="ex-previa-capa" style="background:${corOk(p.cor, '#5865f2')}"></div>
            <button type="button" class="ex-x" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button>
            <div class="ex-previa-corpo">
                <div class="ex-previa-topo">${iconeHtml(p, 72)}<div><h3>${ctx.esc(p.nome)}</h3>
                    <div class="ex-previa-meta"><span><i class="fa-solid fa-user-group"></i> ${num(p.membros)} ${p.membros === 1 ? 'membro' : 'membros'}</span>${t ? `<span style="--c:${ctx.esc(t.cor)}"><i class="fa-solid ${ctx.esc(t.icone)}"></i> ${ctx.esc(t.nome)}</span>` : ''}<span><i class="fa-solid fa-sailboat"></i> ${ROTULO_PORTE[p.porte]}</span></div></div></div>
                <p class="ex-previa-desc">${ctx.esc(p.descricao || 'Sem descrição.')}</p>
                <div class="ex-previa-info">${p.dono ? `<span><i class="fa-solid fa-crown"></i> ${ctx.esc(p.dono)}</span>` : ''}${p.desde ? `<span><i class="fa-regular fa-calendar"></i> desde ${ctx.esc(p.desde)}</span>` : ''}</div>
                ${p.canais && p.canais.length ? `<div class="ex-canais"><small>Canais de texto abertos</small>${p.canais.map((c) => `<span># ${ctx.esc(c)}</span>`).join('')}${p.canais_voz ? `<span><i class="fa-solid fa-volume-high"></i> ${Number(p.canais_voz)} de voz</span>` : ''}</div>` : ''}
                <p class="ex-aviso">Aqui você só vê o que é público. Não dá pra ler mensagens antes de entrar.</p>
                <div class="ex-previa-acoes"><button type="button" class="ex-btn" data-fechar>Voltar ao mar</button>
                    <button type="button" class="ex-btn primario" id="ex-entrar">${p.meu ? '<i class="fa-solid fa-arrow-right"></i> Abrir meu servidor' : '<i class="fa-solid fa-anchor"></i> Entrar'}</button></div>
            </div></div>`;
        raiz().appendChild(m);
        m.addEventListener('mousedown', (e) => { if (e.target === m) fecharPrevia(); });
        m.querySelector('.ex-x').addEventListener('click', fecharPrevia);
        m.querySelector('[data-fechar]').addEventListener('click', fecharPrevia);
        m.querySelector('#ex-entrar').addEventListener('click', () => { ctx.emitir('explorar_entrar', { server_id: p.id }); });
    }

    // ---------------------------------------------------------------------
    // CASCA
    // ---------------------------------------------------------------------
    function casca() {
        const r = raiz();
        r.innerHTML = `<div class="ex-janela" role="dialog" aria-modal="true" aria-label="Explorar servidores">
            <header class="ex-topo"><div class="ex-titulo"><i class="fa-solid fa-compass"></i> <div><b>Explorar servidores</b><small id="ex-contagem"></small></div></div>
                <div class="ex-busca"><i class="fa-solid fa-magnifying-glass"></i><input id="ex-busca" type="search" maxlength="40" placeholder="Procurar um servidor..." autocomplete="off"></div>
                <button type="button" class="ex-btn" id="ex-surpresa"><i class="fa-solid fa-dice"></i> Surpreenda-me</button>
                <button type="button" class="ex-btn" id="ex-embaralha" title="Chamar outros barcos"><i class="fa-solid fa-shuffle"></i></button>
                <button type="button" class="ex-x fixo" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button></header>
            <div class="ex-corpo">
                <div class="ex-chips" id="ex-chips"></div>
                <div class="ex-cena" aria-label="O mar, com um barquinho por servidor">
                    <div class="ex-sol"></div><div class="ex-nuvem n1"></div><div class="ex-nuvem n2"></div><div class="ex-nuvem n3"></div>
                    <div class="ex-agua"><div class="ex-onda o1"></div><div class="ex-onda o2"></div><div class="ex-mar" id="ex-mar"></div><div class="ex-onda o3"></div></div>
                    <div class="ex-vazio" id="ex-vazio" style="display:none"></div>
                </div>
                <div class="ex-areia"></div>
                <section class="ex-terra" id="ex-terra"><h3><i class="fa-solid fa-mountain-sun"></i> Em terra firme <small>os mais movimentados</small></h3><div class="ex-grade" id="ex-terra-lista"></div></section>
                <div id="ex-temas"></div>
            </div></div>`;
        r.style.display = 'flex';
    }

    function pedir() { ctx.emitir('explorar_pedir', { busca, tema, seed }); }

    function fechar() { fecharPrevia(); const r = raiz(); if (r) { r.style.display = 'none'; r.innerHTML = ''; } }

    function iniciar(contexto) {
        ctx = contexto;
        document.addEventListener('click', (e) => {
            const r = raiz();
            if (!r || r.style.display !== 'flex' || !r.contains(e.target)) return;
            const b = e.target.closest('.ex-barco, .ex-casa');
            if (b) { ctx.emitir('explorar_previa', { server_id: Number(b.dataset.id) }); return; }
            const c = e.target.closest('.ex-chip, .ex-ver');
            if (c) { tema = c.dataset.tema || ''; busca = ''; const i = $('#ex-busca', r); if (i) i.value = ''; pedir(); if (c.classList.contains('ex-ver')) r.querySelector('.ex-corpo').scrollTo({ top: 0, behavior: 'smooth' }); return; }
            if (e.target.closest('#ex-surpresa')) { ctx.emitir('explorar_surpresa', { tema }); return; }
            if (e.target.closest('#ex-embaralha')) { seed = String(Math.floor(Math.random() * 1e6)); pedir(); return; }
            if (e.target.closest('.ex-x.fixo')) { fechar(); }
        });
        document.addEventListener('input', (e) => {
            if (e.target.id !== 'ex-busca') return;
            clearTimeout(timer);
            timer = setTimeout(() => { busca = e.target.value.trim(); pedir(); }, 350);
        });
        document.addEventListener('keydown', (e) => {
            const r = raiz();
            if (e.key !== 'Escape' || !r || r.style.display !== 'flex') return;
            e.stopImmediatePropagation();
            if (previa) fecharPrevia(); else fechar();
        }, true);
        // aba escondida: os barcos não precisam navegar
        document.addEventListener('visibilitychange', () => { const r = raiz(); if (r) r.classList.toggle('ex-parado', document.hidden); });
    }

    return {
        iniciar,
        abrir() { seed = String(Math.floor(Math.random() * 1e6)); tema = ''; busca = ''; casca(); pedir(); },
        receber(d) { S = d; desenhar(); },
        previa(p) { if (raiz() && raiz().style.display === 'flex') mostrarPrevia(p); },
        erro(msg) { ctx.toast(msg, 'warning'); },
        entrou() { fechar(); },
    };
})();
