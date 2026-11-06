/* Canal de LOJAS (tipo de canal `lojas`): no lugar da conversa, uma vitrine com as lojas do Bazar das pessoas do servidor e as parceiras,
   com busca, filtro por categoria/origem e o botão "Pedir" (que abre o produto no Bazar: lá valem as regras de pedido).
   Só desenha e pede: quem pode ver o canal e o que aparece nele é decidido no SERVIDOR (app/lojas_canal.py).
   Uso (chat.html):  LojasCanal.iniciar({ emitir, esc, escUrl, toast, abrirLoja(lojaId, produtoId) });
                     Cargos.aoAbrirCanal chama LojasCanal.abrir(canal) / LojasCanal.fechar();  eventos: lojas_canal, lojas_canal_erro.            */
const LojasCanal = (() => {
    let ctx = null, canalId = null, nomeCanal = '', pedidoTimer = null, buscaTimer = null, dados = null;
    const f = { busca: '', categoria: '', origem: 'todas', seed: novaSeed() };
    const CORES = { ambar: '#d9822b', vinho: '#a8323e', floresta: '#3f7d4e', oceano: '#2f6f9f', lavanda: '#7d6bb8', tijolo: '#b5532f', petroleo: '#2f6670', mostarda: '#c9a227', rosa: '#c4577f', grafite: '#5a606b' };
    const urlCss = (u) => String(u == null ? '' : u).replace(/['"()\\\s]/g, (c) => '%' + c.charCodeAt(0).toString(16).toUpperCase().padStart(2, '0'));
    const brl = (c) => (Number(c || 0) / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    const $ = (id) => document.getElementById(id);

    function novaSeed() { return Math.random().toString(36).slice(2, 10); }
    function iniciar(c) { ctx = c; }
    const aberto = () => canalId != null;

    // ---------------------------------------------------------------------
    // abrir / fechar (troca a conversa do canal pela vitrine)
    // ---------------------------------------------------------------------
    function abrir(canal) {
        if (!ctx || !canal) return;
        const view = $('text-view');
        if (!view) return;
        const mudou = Number(canalId) !== Number(canal.id);
        canalId = Number(canal.id);
        nomeCanal = canal.name || 'lojas';
        view.classList.add('lojas-aberto');
        if (!$('lc-painel')) {
            const p = document.createElement('div');
            p.id = 'lc-painel'; p.className = 'lc-painel';
            p.innerHTML = `<div class="lc-topo">
                    <div class="lc-titulo"><i class="fa-solid fa-store"></i><div><b id="lc-nome"></b><small id="lc-sub">Lojas do Bazar das pessoas deste servidor e as parceiras do Pantheon.</small></div></div>
                    <div class="lc-busca"><i class="fa-solid fa-magnifying-glass"></i><input id="lc-busca" type="search" maxlength="40" placeholder="Procurar loja ou produto…" autocomplete="off"></div>
                    <button type="button" class="lc-btn" id="lc-embaralhar" title="Embaralhar a ordem"><i class="fa-solid fa-shuffle"></i></button>
                </div>
                <div class="lc-filtros"><div class="lc-chips" id="lc-origem" role="group" aria-label="De quem"></div><div class="lc-chips" id="lc-cats" role="group" aria-label="Categoria"></div></div>
                <div class="lc-grade" id="lc-grade"><div class="lc-vazio"><i class="fa-solid fa-spinner fa-spin"></i> Carregando as lojas…</div></div>`;
            view.insertBefore(p, view.firstChild);
            $('lc-busca').addEventListener('input', (e) => { clearTimeout(buscaTimer); buscaTimer = setTimeout(() => { f.busca = e.target.value.trim(); pedir(); }, 350); });
            $('lc-embaralhar').addEventListener('click', () => { f.seed = novaSeed(); pedir(); });
            p.addEventListener('click', clique);
        }
        $('lc-nome').textContent = nomeCanal;
        if (mudou) { dados = null; f.busca = ''; f.categoria = ''; f.origem = 'todas'; f.seed = novaSeed(); const b = $('lc-busca'); if (b) b.value = ''; }
        pedir();
    }

    function fechar() {
        const view = $('text-view');
        if (view) view.classList.remove('lojas-aberto');
        const p = $('lc-painel');
        if (p) p.remove();
        canalId = null; dados = null;
        clearTimeout(pedidoTimer); clearTimeout(buscaTimer);
    }

    function pedir() {
        if (!aberto()) return;
        ctx.emitir('lojas_canal_pedir', { canal_id: canalId, busca: f.busca, categoria: f.categoria, origem: f.origem, seed: f.seed });
    }

    /** A vitrine muda quando o Bazar muda (loja aberta/fechada, produto novo) ou quando alguém entra/sai do servidor: pede de novo, sem rajada. */
    function mudou() {
        if (!aberto()) return;
        clearTimeout(pedidoTimer);
        pedidoTimer = setTimeout(pedir, 700);
    }

    // ---------------------------------------------------------------------
    // desenho
    // ---------------------------------------------------------------------
    function receber(d) {
        if (!d || Number(d.canal_id) !== canalId || !$('lc-grade')) return;
        dados = d;
        f.origem = d.origem || f.origem;
        const o = [['todas', 'Todas'], ['servidor', 'Do servidor'], ['parceiras', 'Parceiras']];
        $('lc-origem').innerHTML = o.map(([id, n]) => `<button type="button" class="lc-chip ${f.origem === id ? 'on' : ''}" data-origem="${id}">${ctx.esc(n)}</button>`).join('');
        $('lc-cats').innerHTML = `<button type="button" class="lc-chip ${!f.categoria ? 'on' : ''}" data-cat="">Tudo</button>` +
            (d.categorias || []).map((c) => `<button type="button" class="lc-chip ${f.categoria === c.id ? 'on' : ''}" data-cat="${ctx.esc(c.id)}">${ctx.esc(c.nome)}${c.qtd ? ` <small>${Number(c.qtd)}</small>` : ''}</button>`).join('');
        const itens = d.itens || [];
        $('lc-sub').textContent = itens.length
            ? `${Number(d.total)} ${d.total === 1 ? 'loja' : 'lojas'}${d.truncado ? ' (mostrando as primeiras)' : ''} · toque num produto pra pedir`
            : 'Lojas do Bazar das pessoas deste servidor e as parceiras do Pantheon.';
        $('lc-grade').innerHTML = itens.length ? itens.map(cartao).join('')
            : `<div class="lc-vazio"><i class="fa-solid fa-store-slash"></i><b>${f.busca || f.categoria || f.origem !== 'todas' ? 'Nenhuma loja bate com esse filtro.' : 'Ainda não tem loja por aqui.'}</b>
                <small>${f.busca || f.categoria || f.origem !== 'todas' ? 'Tire um filtro ou procure outra coisa.' : 'Quem do servidor abrir uma loja no Bazar (Mercado > Bazar > Minha lojinha) aparece nesta vitrine.'}</small></div>`;
    }

    function cartao(l) {
        const cor = CORES[l.cor] || CORES.ambar;
        const logo = l.logo_url ? ctx.escUrl(l.logo_url) : '';
        const banner = l.banner_url ? ctx.escUrl(urlCss(l.banner_url)) : '';
        const ini = ctx.esc(((l.nome || '?').trim()[0] || '?').toUpperCase());
        const nota = l.nota ? `<span class="lc-nota" title="${Number(l.nota_qtd)} avaliações"><i class="fa-solid fa-star"></i> ${String(l.nota).replace('.', ',')}</span>` : '<span class="lc-nota nova">nova</span>';
        const selo = l.verificada ? '<span class="lc-selo" title="Loja verificada"><i class="fa-solid fa-circle-check"></i></span>' : '';
        const origem = l.origem === 'parceira' ? '<span class="lc-origem parceira"><i class="fa-solid fa-handshake"></i> Parceira</span>' : '<span class="lc-origem"><i class="fa-solid fa-house-user"></i> Do servidor</span>';
        const prods = (l.produtos || []).map((p) => `<li><span class="lc-pnome">${ctx.esc(p.nome)}</span><b>${ctx.esc(brl(p.preco_cent))}</b>
            <button type="button" class="lc-pedir" data-loja="${Number(l.id)}" data-produto="${Number(p.id)}" aria-label="Pedir ${ctx.esc(p.nome)}">Pedir</button></li>`).join('');
        const mais = Number(l.total_produtos) > (l.produtos || []).length ? `<small class="lc-mais">+${Number(l.total_produtos) - l.produtos.length} no Bazar</small>` : '';
        return `<article class="lc-loja" style="--lc-cor:${cor}">
            <div class="lc-capa" ${banner ? `style="background-image:url('${banner}')"` : ''}><span class="lc-logo">${logo ? `<img src="${logo}" alt="" loading="lazy" onerror="this.remove()">` : ini}</span></div>
            <div class="lc-corpo"><h4>${ctx.esc(l.nome)} ${selo}</h4>
                <div class="lc-meta">${origem}${nota}${l.pague_no_app ? '<span class="lc-app" title="Dá pra pagar pelo app"><i class="fa-solid fa-bolt"></i> Pague no app</span>' : ''}</div>
                ${l.descricao ? `<p>${ctx.esc(l.descricao)}</p>` : ''}
                <ul class="lc-prods">${prods}</ul>${mais}
                <button type="button" class="lc-abrir" data-loja="${Number(l.id)}"><i class="fa-solid fa-store"></i> Abrir a loja</button></div></article>`;
    }

    function clique(e) {
        const ped = e.target.closest('.lc-pedir');
        if (ped) { ctx.abrirLoja(Number(ped.dataset.loja), Number(ped.dataset.produto)); return; }
        const ab = e.target.closest('.lc-abrir');
        if (ab) { ctx.abrirLoja(Number(ab.dataset.loja), null); return; }
        const o = e.target.closest('[data-origem]');
        if (o) { f.origem = o.dataset.origem; pedir(); return; }
        const c = e.target.closest('[data-cat]');
        if (c) { f.categoria = c.dataset.cat; pedir(); }
    }

    function erro(d) {
        if (!aberto() || (d && d.canal_id != null && Number(d.canal_id) !== canalId)) return;
        const g = $('lc-grade');
        if (g) g.innerHTML = `<div class="lc-vazio"><i class="fa-solid fa-triangle-exclamation"></i><b>${ctx.esc((d && d.msg) || 'Não foi possível abrir a vitrine.')}</b></div>`;
    }

    return { iniciar, abrir, fechar, mudou, receber, erro, aberto };
})();
