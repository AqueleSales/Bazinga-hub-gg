/* Passe de Batalha (temporadas) e seletor de títulos. Só DESENHA: nível, direito à trilha premium e o que cai vêm do servidor
   (evento 'passe'); o cliente só pede o resgate (passe_resgatar) e o servidor decide.
   Depende de: Cosm.previaItem (static/js/cosmeticos.js) e das classes .titulo-* (static/css/titulos.css).
   O app entrega o contexto em Passe.iniciar({ emitir, toast, avatarHtml, nome, somResgate }). */
const Passe = (() => {
    let ctx = null, S = null, T = null, desenhando = false, timerXp = null, adminLink = false;
    const raiz = () => document.getElementById('passe');
    const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const idOk = (v) => /^[a-z_]{1,24}$/.test(v || '');
    const num = (n) => Number(n || 0).toLocaleString('pt-BR');
    const visivel = () => { const r = raiz(); return !!(r && r.offsetParent !== null); };

    function tempoTexto(seg) {
        const d = Math.floor(seg / 86400), h = Math.floor((seg % 86400) / 3600), m = Math.floor((seg % 3600) / 60);
        return d > 0 ? `${d}d ${h}h` : (h > 0 ? `${h}h ${m}min` : `${Math.max(m, 1)}min`);
    }

    // ---------------------------------------------------------------------
    // ARTE DA TEMPORADA (chapada: uma cor, sem gradiente)
    // ---------------------------------------------------------------------
    const ARTE = {
        deuses: '<svg viewBox="0 0 240 150" aria-hidden="true"><path d="M120 6 226 52H14z"/><rect x="22" y="60" width="196" height="10" rx="3"/><rect x="34" y="78" width="22" height="58" rx="5"/><rect x="74" y="78" width="22" height="58" rx="5"/><rect x="114" y="78" width="22" height="58" rx="5"/><rect x="154" y="78" width="22" height="58" rx="5"/><rect x="194" y="78" width="12" height="58" rx="4" opacity=".6"/><rect x="18" y="142" width="204" height="8" rx="3"/></svg>',
    };

    // ---------------------------------------------------------------------
    // RECOMPENSA (cartão da trilha)
    // ---------------------------------------------------------------------
    function previaRec(r) {
        if (!r) return '';
        if (r.tipo === 'moeda') return `<span class="pz-moeda"><i class="fa-solid fa-coins"></i><b>${num(r.quantidade)}</b></span>`;
        if (r.tipo === 'titulo') return `<span class="titulo-chip titulo-rar-${esc(r.titulo.raridade)} ${r.titulo.anim ? 'titulo-anim-' + esc(r.titulo.anim) : ''}">${esc(r.titulo.texto)}</span>`;
        if (r.tipo === 'tema') {
            const c = (r.cores || []).slice(0, 4);
            return `<span class="pz-tema">${c.map((x) => `<i style="background:${esc(x)}"></i>`).join('')}</span>`;
        }
        if (r.tipo === 'item' && r.item && idOk(r.item.valor)) {
            try { return `<span class="pz-item">${Cosm.previaItem(r.item, { avatarHtml: ctx.avatarHtml(), nome: ctx.nome(), temas: {} })}</span>`; } catch (e) { return ''; }
        }
        return '<span class="pz-moeda"><i class="fa-solid fa-gift"></i></span>';
    }

    function estadoCel(r, trilha, n) {
        if (!r) return 'vazia';
        if (r.invalido) return 'invalida';
        if (r.resgatado) return 'resgatada';
        if (r.liberado) return 'pronta';
        if (trilha === 'premium' && !S.premium) return 'trancada';
        return 'futura';
    }

    function celula(r, trilha, n) {
        const est = estadoCel(r, trilha, n);
        if (est === 'vazia') return '<span class="pz-cel vazia" aria-hidden="true"></span>';
        const selo = est === 'resgatada' ? '<span class="pz-selo ok"><i class="fa-solid fa-check"></i></span>'
            : est === 'trancada' ? '<span class="pz-selo"><i class="fa-solid fa-lock"></i></span>'
                : est === 'pronta' ? '<span class="pz-selo pronta"><i class="fa-solid fa-gift"></i></span>' : '';
        const rar = r.raridade ? `rar-${esc(r.raridade)}` : (r.tipo === 'moeda' ? 'rar-moeda' : '');
        return `<button type="button" class="pz-cel ${est} ${rar} ${r.tipo === 'moeda' ? '' : 'marco'}" data-n="${n}" data-t="${trilha}" title="${esc(r.nome)}">
            <span class="pz-prev">${previaRec(r)}</span><span class="pz-nome">${r.tipo === 'moeda' ? 'Moedas' : esc(r.nome)}</span>${selo}</button>`;
    }

    // ---------------------------------------------------------------------
    // PÁGINA
    // ---------------------------------------------------------------------
    function desenhar() {
        const r = raiz();
        if (!r) return;
        if (!S) { r.innerHTML = '<div class="pz-vazio">Carregando o passe...</div>'; return; }
        if (!S.ativa) {
            r.innerHTML = `<div class="pz-vazio"><i class="fa-solid fa-landmark"></i><b>Nenhuma temporada ativa agora</b><span>Uma nova temporada do passe vem por aí. Enquanto isso, suas missões e o seu nível de conta seguem valendo.</span>
                ${S.admin ? '<a class="pz-btn" href="/admin#passe" target="_blank" rel="noopener">Criar uma temporada no Estúdio</a>' : ''}</div>`;
            return;
        }
        const v = S.visual || {};
        const pct = S.nivel >= S.niveis_total ? 100 : Math.round((S.xp_no_nivel / S.xp_por_nivel) * 100);
        const fim = S.segundos_restantes != null ? `Termina em ${tempoTexto(S.segundos_restantes)}` : 'Sem data de fim';
        const comeca = S.comeca_em ? `<span class="pz-chip aviso"><i class="fa-regular fa-clock"></i> Começa em ${tempoTexto(S.comeca_em)}</span>` : '';
        const colunas = S.niveis.map((l) => `<div class="pz-col ${l.n <= S.nivel ? 'alcancado' : ''} ${l.n === S.nivel ? 'atual' : ''}" data-n="${l.n}">
            ${celula(l.premium, 'premium', l.n)}<div class="pz-no"><b>${l.n}</b></div>${celula(l.gratis, 'gratis', l.n)}</div>`).join('');
        r.setAttribute('data-passe', S.tema);
        r.style.setProperty('--pz-cor', v.cor || '#d4a24c');
        r.style.setProperty('--pz-cor2', v.cor2 || '#e9d9a6');
        r.innerHTML = `<section class="pz-hero">
                <div class="pz-arte" aria-hidden="true">${ARTE[S.tema] || `<i class="fa-solid ${esc(v.icone || 'fa-ranking-star')}"></i>`}</div>
                <div class="pz-hero-info">
                    <div class="pz-sobre"><span class="pz-selo-temp"><i class="fa-solid ${esc(v.icone || 'fa-ranking-star')}"></i> Temporada</span>
                        <span class="pz-chip"><i class="fa-regular fa-hourglass-half"></i> ${esc(fim)}</span>${comeca}
                        ${S.catchup ? `<span class="pz-chip ok" title="Reta final: quem entrou tarde alcança"><i class="fa-solid fa-forward"></i> XP +${Number(S.catchup_pct)}%</span>` : ''}
                        ${S.janela_aberta ? '' : '<span class="pz-chip aviso"><i class="fa-solid fa-pause"></i> XP pausado</span>'}</div>
                    <h2 class="pz-titulo">${esc(S.nome)}</h2>
                    ${S.subtitulo ? `<p class="pz-sub">${esc(S.subtitulo)}</p>` : v.lema ? `<p class="pz-sub">${esc(v.lema)}</p>` : ''}
                    <div class="pz-prog"><div class="pz-prog-nivel"><small>NÍVEL</small><b>${S.nivel}</b><small>/ ${S.niveis_total}</small></div>
                        <div class="pz-barra-col"><div class="pz-barra"><i style="width:${pct}%"></i></div>
                            <div class="pz-barra-txt">${S.nivel >= S.niveis_total ? 'Passe completo' : `${num(S.xp_no_nivel)} / ${num(S.xp_por_nivel)} XP para o nível ${S.nivel + 1}`}</div></div></div>
                    <div class="pz-acoes">
                        <button type="button" class="pz-btn primario" id="pz-tudo" ${S.pendentes ? '' : 'disabled'}><i class="fa-solid fa-gift"></i> ${S.pendentes ? `Resgatar tudo (${S.pendentes})` : 'Nada novo pra resgatar'}</button>
                        <button type="button" class="pz-btn" id="pz-titulos"><i class="fa-solid fa-signature"></i> Meus títulos</button>
                        <button type="button" class="pz-btn" id="pz-ir"><i class="fa-solid fa-crosshairs"></i> Ir pro meu nível</button>
                        ${S.admin ? '<a class="pz-btn" href="/admin#passe" target="_blank" rel="noopener"><i class="fa-solid fa-screwdriver-wrench"></i> Estúdio</a>' : ''}
                        ${S.premium ? '<span class="pz-chip ok"><i class="fa-solid fa-crown"></i> Trilha Premium liberada</span>' : '<span class="pz-chip" title="A trilha Premium chega junto com a assinatura"><i class="fa-solid fa-lock"></i> Trilha Premium: em breve</span>'}
                    </div>
                </div></section>
            <div class="pz-trilha-caixa"><div class="pz-rotulos"><span class="premium"><i class="fa-solid fa-crown"></i> Premium</span><span class="nivel">Nível</span><span class="gratis">Grátis</span></div>
                <div class="pz-trilha" id="pz-trilha">${colunas}</div></div>`;
        if (!desenhando) { desenhando = true; irParaNivel(true); }
    }

    function irParaNivel(instantaneo) {
        const t = document.getElementById('pz-trilha');
        const alvo = t && (t.querySelector('.pz-col.atual') || t.querySelector('.pz-col'));
        if (!alvo) return;
        t.scrollTo({ left: Math.max(alvo.offsetLeft - t.clientWidth / 2 + alvo.offsetWidth / 2, 0), behavior: instantaneo ? 'auto' : 'smooth' });
    }

    // ---------------------------------------------------------------------
    // DETALHE DA RECOMPENSA
    // ---------------------------------------------------------------------
    function fecharModal() { document.getElementById('pz-modal')?.remove(); }

    function abrirDetalhe(n, trilha) {
        const l = S && S.niveis.find((x) => x.n === n);
        const r = l && l[trilha];
        if (!r) return;
        const est = estadoCel(r, trilha, n);
        const msg = { resgatada: 'Você já resgatou.', pronta: 'Pronta pra resgatar!', trancada: 'Essa recompensa é da trilha Premium (em breve).', futura: `Disponível no nível ${n} do passe.`, invalida: 'Esta recompensa foi removida pela equipe.' }[est];
        const desc = r.tipo === 'item' && r.item ? r.item.desc : r.tipo === 'titulo' ? (r.titulo.descricao || 'Um título pra equipar ao lado do seu nome.') : r.tipo === 'tema' ? 'Um tema exclusivo da temporada, pra usar no app inteiro.' : `${num(r.quantidade)} moedas na sua carteira.`;
        fecharModal();
        const m = document.createElement('div');
        m.id = 'pz-modal'; m.className = 'modal-overlay pz-modal-fundo';
        m.innerHTML = `<div class="pz-modal" role="dialog" aria-modal="true"><button type="button" class="pz-x" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button>
            <small class="pz-modal-trilha ${trilha}">${trilha === 'premium' ? 'Trilha Premium' : 'Trilha Grátis'} · Nível ${n}</small>
            <div class="pz-modal-prev">${previaRec(r)}</div>
            <h3>${r.tipo === 'moeda' ? `${num(r.quantidade)} moedas` : esc(r.nome)}</h3>
            <span class="pz-modal-tipo">${esc(r.rotulo || '')}${r.raridade ? ' · ' + esc(r.raridade) : ''}</span>
            <p>${esc(desc)}</p><p class="pz-modal-estado ${est}">${esc(msg)}</p>
            ${est === 'pronta' ? '<button type="button" class="pz-btn primario" id="pz-pegar"><i class="fa-solid fa-gift"></i> Resgatar</button>' : ''}</div>`;
        document.body.appendChild(m);
        m.addEventListener('mousedown', (e) => { if (e.target === m) fecharModal(); });
        m.querySelector('.pz-x').addEventListener('click', fecharModal);
        m.querySelector('#pz-pegar')?.addEventListener('click', () => { ctx.emitir('passe_resgatar', { nivel: n, trilha }); fecharModal(); });
    }

    // ---------------------------------------------------------------------
    // TÍTULOS (seletor)
    // ---------------------------------------------------------------------
    function chip(t) { return `<span class="titulo-chip titulo-rar-${esc(t.raridade)} ${t.anim ? 'titulo-anim-' + esc(t.anim) : ''}">${esc(t.texto)}</span>`; }

    function desenharTitulos() {
        const m = document.getElementById('pz-titulos-modal');
        if (!m || !T) return;
        const lista = T.lista.map((t) => `<button type="button" class="pz-ti ${T.equipado === t.id ? 'eq' : ''}" data-id="${esc(t.id)}">${chip(t)}<small>${esc(t.descricao || t.raridade)}</small>${T.equipado === t.id ? '<i class="fa-solid fa-circle-check"></i>' : ''}</button>`).join('');
        m.querySelector('.pz-ti-lista').innerHTML = (lista || '<div class="pz-vazio-mini">Você ainda não ganhou nenhum título. Eles vêm do passe de temporada e de conquistas.</div>')
            + (T.equipado ? '<button type="button" class="pz-btn" id="pz-ti-tirar">Tirar título</button>' : '');
        m.querySelectorAll('.pz-ti').forEach((b) => b.addEventListener('click', () => ctx.emitir('equipar_titulo', { titulo_id: b.dataset.id })));
        m.querySelector('#pz-ti-tirar')?.addEventListener('click', () => ctx.emitir('equipar_titulo', { titulo_id: null }));
    }

    function abrirTitulos() {
        document.getElementById('pz-titulos-modal')?.remove();
        const m = document.createElement('div');
        m.id = 'pz-titulos-modal'; m.className = 'modal-overlay pz-modal-fundo';
        m.innerHTML = '<div class="pz-modal pz-ti-modal" role="dialog" aria-modal="true" aria-label="Meus títulos"><button type="button" class="pz-x" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button><h3>Meus títulos</h3><p class="pz-modal-sub">O título aparece no seu cartão, ao lado do @ e dos pronomes.</p><div class="pz-ti-lista"><div class="pz-vazio-mini">Carregando...</div></div></div>';
        document.body.appendChild(m);
        const fechar = () => m.remove();
        m.addEventListener('mousedown', (e) => { if (e.target === m) fechar(); });
        m.querySelector('.pz-x').addEventListener('click', fechar);
        ctx.emitir('listar_titulos', {});
        desenharTitulos();
    }

    // ---------------------------------------------------------------------
    // API
    // ---------------------------------------------------------------------
    function iniciar(contexto) {
        ctx = contexto;
        document.addEventListener('click', (e) => {
            const cel = e.target.closest('#passe .pz-cel[data-n]');
            if (cel) { abrirDetalhe(+cel.dataset.n, cel.dataset.t); return; }
            if (e.target.closest('#pz-tudo')) { ctx.emitir('passe_resgatar', { todos: true }); return; }
            if (e.target.closest('#pz-titulos')) { abrirTitulos(); return; }
            if (e.target.closest('#pz-ir')) { irParaNivel(false); }
        });
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape') return;
            const m = document.getElementById('pz-modal') || document.getElementById('pz-titulos-modal');
            if (m) { e.stopImmediatePropagation(); m.remove(); }
        }, true);
    }

    return {
        iniciar,
        abrir() { ctx && ctx.emitir('passe_pedir', {}); },
        receber(d) { S = d; desenhar(); },
        /** O XP mudou (qualquer fonte): se a aba do passe está à vista, pede o estado de novo (com respiro). */
        xpMudou() { if (!ctx || !visivel()) return; clearTimeout(timerXp); timerXp = setTimeout(() => ctx.emitir('passe_pedir', {}), 1200); },
        resgatado(r) {
            const partes = [];
            if (r.moedas) partes.push(`+${num(r.moedas)} moedas`);
            (r.itens || []).forEach((i) => partes.push(i.nome));
            ctx.toast(partes.length ? `Resgatado: ${partes.join(' · ')}` : 'Resgatado!', 'success');
            try { ctx.somResgate && ctx.somResgate(); } catch (e) { /* som é enfeite */ }
        },
        titulosRecebidos(d) { T = d; desenharTitulos(); },
        abrirTitulos,
    };
})();
