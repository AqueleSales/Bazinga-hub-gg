/* ==========================================================================
   BAZAR DA COMUNIDADE (modelo A: classificados, Pix direto entre as pessoas). Objeto global `Bazar`.
   Só DESENHA o que o servidor manda (`bazar_vitrine`, `bazar_feed`, `bazar_loja`, `bazar_minha`, `bazar_pedido`...). Quem vê a chave Pix,
   quem pode aceitar/cancelar, estoque, preço e a ORDEM do feed são decididos no servidor (app/bazar.py): aqui os botões só pedem a ação.
   O Panteão NÃO guarda nem intermedia o dinheiro: o "copia e cola" é montado com a chave do vendedor e o pagamento vai direto pra ele.

   Organização da tela (as "vistas" trocam dentro do Mercado Elite; a barra lateral do app continua):
     feed   = carrossel de propagandas (lojas parceiras + as do Panteão), faixa "bem avaliadas", filtros e o FEED misturado
              (retângulo de loja grande, caixa de loja média, quadrado de 4 itens de barracas) em ordem embaralhada por seed;
     loja   = a página de uma loja (substitui o feed);
     painel = "Minha lojinha" (abre pelo atalho ao lado das moedas): visão geral, produtos, pedidos, compras, personalizar, dados/Pix, moderação.
   ========================================================================== */
const Bazar = (() => {
    const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    // mesma regra do servidor (url_de_imagem_ok): caminho do site, Cloudinary ou Giphy
    const urlOk = (u) => { u = String(u || ''); return (u.startsWith('/') || u.startsWith('https://res.cloudinary.com/') || /^https:\/\/media\d*\.giphy\.com\//.test(u)) ? u : ''; };
    // URL que vai dentro de url('...') num style: troca o que poderia fechar o url() ou a aspa (o servidor também recusa essas URLs)
    const urlCss = (u) => String(u).replace(/['"()\\\s]/g, (c) => '%' + c.charCodeAt(0).toString(16).toUpperCase().padStart(2, '0'));
    const brl = (c) => (Number(c || 0) / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    const paraReais = (c) => (Number(c || 0) / 100).toFixed(2).replace('.', ',');
    const lerReais = (txt) => {
        let t = String(txt || '').replace(/[^\d.,]/g, '');
        if (!t) return null;
        if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.');
        const n = parseFloat(t);
        return Number.isFinite(n) ? Math.round(n * 100) : null;
    };
    const reduzMov = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const ICONE_TIPO = { fisico: 'fa-box', digital: 'fa-cloud-arrow-down', servico: 'fa-handshake-angle' };
    const ROTULO_TIPO = { fisico: 'Produto físico', digital: 'Digital', servico: 'Serviço' };
    const novaSeed = () => Math.random().toString(36).slice(2, 10);

    let ctx = null, raiz = null, vistaEl = {};
    let cat = null, eAdmin = false, minha, minhaLojaId = null, pend = 0;
    let vista = 'feed', feedScroll = 0;
    let seed = novaSeed(), filtro = 'todas', tipoFiltro = '', busca = '', buscaTimer = 0;
    let feed = { itens: [], pagina: 0, temMais: false, carregando: false, carregado: false };
    let props = [], dest = [], adIdx = 0, adTimer = 0, observador = null;
    let carregadoEm = 0, desatualizada = false;
    const produtos = new Map(), pedCache = new Map();
    let lojaAtual = null, prodAtual = null, ed = null, moderacao = null, secao = 'inicio';
    let pedidos = { comprando: [], vendendo: [], carregado: false };
    let ed_aval = { nota: 0, texto: '' };
    const pilha = [];

    // ---------------------------------------------------------------------
    // PEÇAS
    // ---------------------------------------------------------------------
    const corDe = (id) => (cat && cat.cores[id]) || '#d9822b';
    function estiloLoja(l) {
        const t = (cat && cat.toldos[l.toldo]) || null, cor = corDe(l.cor);
        return `--bz-cor:${cor};--bz-t1:${t ? t[0] : cor};--bz-t2:${t ? t[1] : cor}`;
    }
    const nomeCat = (id) => ((cat && cat.categorias.find((c) => c.id === id)) || {}).nome || 'Outros';
    const inicial = (l) => esc((l.nome || '?').trim().charAt(0).toUpperCase());
    const logoHtml = (l) => urlOk(l.logo_url) ? `<img class="bz-logo" src="${esc(urlOk(l.logo_url))}" alt="" loading="lazy">` : `<span class="bz-logo ini">${inicial(l)}</span>`;
    const notaHtml = (l) => l.nota ? `<span class="bz-nota"><i class="fa-solid fa-star"></i> ${String(l.nota).replace('.', ',')} <small>(${Number(l.nota_qtd)})</small></span>` : '<span class="bz-nota"><small>Loja nova</small></span>';
    const tagDoFeed = () => `${seed}|${filtro}|${tipoFiltro}|${busca}`;

    function tileProduto(p, extra = '') {
        const img = urlOk((p.imagens || [])[0]);
        return `<button type="button" class="bz-prod" data-a="prod" data-id="${Number(p.id)}" ${extra}>
            ${p.estoque === 0 ? '<span class="bz-esgotado">Esgotado</span>' : ''}
            <span class="bz-prod-img">${img ? `<img src="${esc(img)}" alt="" loading="lazy">` : `<i class="fa-solid ${ICONE_TIPO[p.tipo] || 'fa-box'}"></i>`}</span>
            <span class="bz-prod-nome">${esc(p.nome)}</span>
            <span class="bz-prod-preco">${brl(p.preco_cent)}</span>
            ${(p.combo_itens || []).length ? '<span class="bz-tag">Combo</span>' : ''}
        </button>`;
    }

    function htmlLoja(l, semAcao = false) {
        const grande = l.porte === 'grande';
        const prods = (l.produtos || []).slice(0, 4);
        const placa = `<div class="bz-placa">${logoHtml(l)}<div><b>${esc(l.nome)}</b><small>${esc(nomeCat(l.categoria))}${l.regiao ? ' · ' + esc(l.regiao) : ''}</small>${notaHtml(l)}</div></div>`;
        const anuncio = l.anuncio_titulo || l.anuncio_texto ? `<div class="bz-anuncio"><b>${esc(l.anuncio_titulo)}</b>${esc(l.anuncio_texto)}</div>` : '';
        return `<article class="bz-loja ${grande ? 'grande' : 'media'} ${l.toldo === 'sem' ? 'bz-sem-toldo' : ''}" style="${estiloLoja(l)}" ${semAcao ? '' : `data-a="loja" data-id="${Number(l.id)}"`}>
            ${grande ? '<span class="bz-parceira"><i class="fa-solid fa-circle-check"></i> Parceira</span>' : ''}
            <div class="bz-toldo"></div>
            <div class="bz-loja-corpo">
                ${grande ? `<div class="bz-topo-grande">${placa}${anuncio}</div>` : placa + anuncio}
                <div class="bz-vitrine">${prods.map((p) => tileProduto(p)).join('') || '<div class="bz-vazio" style="grid-column:1/-1;padding:14px">Ainda sem produtos.</div>'}</div>
                <div class="bz-loja-rodape"><span>${Number(l.total_produtos || (l.produtos || []).length)} produto(s)${l.vendas ? ' · ' + Number(l.vendas) + ' venda(s)' : ''}</span><span class="ir">Entrar na loja <i class="fa-solid fa-arrow-right"></i></span></div>
            </div>
        </article>`;
    }

    /** O "quadrado de 4 divisões": itens de barracas pequenas diferentes, lado a lado. */
    function htmlQuad(ps) {
        return `<article class="bz-quad"><div class="bz-quad-topo"><i class="fa-solid fa-table-cells-large"></i><div><b>Feira dos aldeões</b><small>itens de barracas pequenas</small></div></div>
            <div class="bz-quad-grade">${ps.map((p) => tileProduto(p, `style="--c:${esc(corDe(p.loja_cor))}"`).replace('</button>', `<small>${esc(p.loja_nome)}</small></button>`)).join('')}</div></article>`;
    }

    // ---------------------------------------------------------------------
    // MODAIS (só produto e pedido; ESC fecha o de cima, clicar fora fecha)
    // ---------------------------------------------------------------------
    const modalDe = (tipo) => pilha.find((e) => e.dataset.tipo === tipo);

    function fecharModal(tipo) {
        const i = pilha.findIndex((e) => e.dataset.tipo === tipo);
        if (i < 0) return;
        pilha[i].remove();
        pilha.splice(i, 1);
        if (tipo === 'produto') prodAtual = null;
    }

    /** Abre (ou redesenha, preservando a rolagem) um modal. `html` = conteúdo do cartão. */
    function modal(tipo, html, { classe = '', estilo = '' } = {}) {
        let el = modalDe(tipo);
        if (el) {
            const corpo = el.querySelector('.bz-card-corpo, .bz-prod-lado');
            const rolagem = corpo ? corpo.scrollTop : 0;
            const card = el.querySelector('.bz-card');
            card.className = `bz-card ${classe}`; card.setAttribute('style', estilo);
            card.innerHTML = html;
            card.style.animation = 'none';
            const novo = card.querySelector('.bz-card-corpo, .bz-prod-lado');
            if (novo) novo.scrollTop = rolagem;
            return el;
        }
        el = document.createElement('div');
        el.className = 'bz-modal'; el.dataset.tipo = tipo;
        el.innerHTML = `<div class="bz-card ${classe}" style="${estilo}">${html}</div>`;
        el.addEventListener('click', (e) => { if (e.target === el) fecharModal(tipo); else clique(e, tipo); });
        el.addEventListener('input', (e) => digitou(e, tipo));
        el.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey && e.target.matches('[data-enviar]')) { e.preventDefault(); clique({ target: el.querySelector('[data-a="enviar-msg"]') || e.target }, tipo); } });
        document.body.appendChild(el);
        pilha.push(el);
        if (!document.__bzEsc) {
            document.__bzEsc = (e) => { if (e.key === 'Escape' && pilha.length) { e.stopImmediatePropagation(); e.preventDefault(); fecharModal(pilha[pilha.length - 1].dataset.tipo); } };
            document.addEventListener('keydown', document.__bzEsc, true);
        }
        return el;
    }

    const topoModal = (titulo, sub) => `<button type="button" class="bz-fechar" data-a="fechar" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button><div class="bz-card-topo"><h3>${esc(titulo)}</h3>${sub ? `<p>${esc(sub)}</p>` : ''}</div>`;

    // ---------------------------------------------------------------------
    // VISTAS (feed / loja / painel)
    // ---------------------------------------------------------------------
    const rolador = () => raiz && raiz.closest('.market-content');

    function irPara(nome) {
        const r = rolador();
        if (vista === 'feed' && nome !== 'feed' && r) feedScroll = r.scrollTop;
        vista = nome;
        Object.entries(vistaEl).forEach(([k, el]) => { el.hidden = k !== nome; });
        if (r) r.scrollTop = nome === 'feed' ? feedScroll : 0;
        if (nome !== 'feed') clearInterval(adTimer); else ligarAds();
    }

    function esqueleto() {
        raiz.innerHTML = `
            <div id="bz-v-feed">
                <div id="bz-ads"></div>
                <details class="bz-aviso" id="bz-aviso"><summary><i class="fa-solid fa-shield-halved"></i> Como o Bazar funciona (leia antes de comprar)</summary>
                    <ul>
                        <li>O pagamento é <b>Pix direto para o vendedor</b>. O Panteão não guarda dinheiro, não intermedia e <b>não devolve</b> pagamento.</li>
                        <li>Só pague por aqui, depois que o vendedor <b>aceitar o pedido</b>. Confira no app do banco se o nome do recebedor é o mesmo da tela.</li>
                        <li>Desconfie de pressa, de preço bom demais e de quem pede pra pagar fora do pedido. Links não são permitidos nos textos.</li>
                        <li>Algo errado? Use <b>Denunciar</b> na loja ou no produto. Com várias denúncias a loja some até um administrador revisar.</li>
                    </ul></details>
                <div id="bz-dest"></div>
                <div class="bz-filtros" id="bz-filtros"></div>
                <div id="bz-novidade"></div>
                <div class="bz-feed" id="bz-feed"></div>
                <div id="bz-mais"></div>
            </div>
            <div id="bz-v-loja" hidden></div>
            <div id="bz-v-painel" hidden></div>`;
        vistaEl = { feed: raiz.querySelector('#bz-v-feed'), loja: raiz.querySelector('#bz-v-loja'), painel: raiz.querySelector('#bz-v-painel') };
        irPara(vista);
    }

    // ---------- carrossel de propagandas ----------
    const PROPAGANDAS_CASA = [
        { casa: true, cor: '#7d6bb8', selo: 'Panteão', titulo: 'Monte a sua loja', texto: 'Abra a sua barraca em poucos minutos: escolha a cor e o toldo, cadastre os produtos e receba por Pix direto.', cta: 'Abrir a minha lojinha', acao: 'painel', icone: 'fa-store' },
        { casa: true, cor: '#2f6f9f', selo: 'Dica', titulo: 'Pix direto, sem taxa do Panteão', texto: 'Confira o nome do recebedor antes de pagar e só pague depois que o vendedor aceitar o pedido.', cta: 'Como funciona', acao: 'aviso', icone: 'fa-shield-halved' },
        { casa: true, cor: '#d9822b', selo: 'Armazém', titulo: 'Personalize o seu perfil', texto: 'Molduras, nomes e placas animadas, pagos em DRC. Combine com a sua loja.', cta: 'Ir ao Armazém', acao: 'armazem', icone: 'fa-wand-magic-sparkles' },
    ];

    function slidesDeAds() {
        const parceiras = props.map((a) => ({ casa: false, ...a }));
        const out = [];
        for (let i = 0; i < Math.max(parceiras.length, PROPAGANDAS_CASA.length); i++) {
            if (parceiras[i]) out.push(parceiras[i]);
            if (PROPAGANDAS_CASA[i]) out.push(PROPAGANDAS_CASA[i]);
        }
        return out;
    }

    function desenharAds() {
        const alvo = document.getElementById('bz-ads');
        if (!alvo) return;
        const slides = slidesDeAds();
        adIdx = Math.min(adIdx, slides.length - 1);
        const html = slides.map((s, k) => {
            const cor = s.casa ? s.cor : corDe(s.cor);
            const banner = !s.casa && urlOk(s.banner_url);
            const arte = banner ? `<div class="bz-ad-arte" style="background-image:url('${esc(urlCss(banner))}')"></div>`
                : `<div class="bz-ad-arte sem"><i class="fa-solid ${s.casa ? s.icone : 'fa-store'}"></i></div>`;
            return `<div class="bz-ad" data-i="${k}" style="--bz-cor:${esc(cor)}">
                <div class="bz-ad-txt"><span class="bz-ad-selo">${s.casa ? esc(s.selo) : 'Propaganda · Parceira'}</span><h3>${esc(s.titulo)}</h3><p>${esc(s.texto)}</p>
                    <button type="button" class="bz-btn sec" data-a="ad" data-i="${k}">${esc(s.casa ? s.cta : 'Visitar a loja')} <i class="fa-solid fa-arrow-right"></i></button></div>
                ${arte}</div>`;
        }).join('');
        alvo.innerHTML = `<section class="bz-ads" aria-label="Propagandas"><div class="bz-ads-trilho">${html}</div>
            <div class="bz-ads-nav"><button type="button" class="bz-seta" data-a="ad-seta" data-d="-1" aria-label="Anterior"><i class="fa-solid fa-chevron-left"></i></button>
            ${slides.map((_, k) => `<button type="button" class="bz-ponto ${k === adIdx ? 'on' : ''}" data-a="ad-ponto" data-i="${k}" aria-label="Propaganda ${k + 1}"></button>`).join('')}
            <button type="button" class="bz-seta" data-a="ad-seta" data-d="1" aria-label="Próxima"><i class="fa-solid fa-chevron-right"></i></button></div></section>`;
        const tr = alvo.querySelector('.bz-ads-trilho');
        tr.style.scrollBehavior = 'auto'; tr.scrollLeft = adIdx * tr.clientWidth; tr.style.scrollBehavior = '';
        let rolando = 0;
        tr.addEventListener('scroll', () => {
            clearTimeout(rolando);
            rolando = setTimeout(() => { const i = Math.round(tr.scrollLeft / Math.max(tr.clientWidth, 1)); if (i !== adIdx) { adIdx = i; marcarPontosAds(); } }, 90);
        }, { passive: true });
        ligarAds();
    }

    function irParaAd(i, suave = true) {
        const tr = document.querySelector('#bz-ads .bz-ads-trilho');
        if (!tr) return;
        const n = tr.children.length;
        adIdx = (i + n) % n;
        if (!suave) tr.style.scrollBehavior = 'auto';
        tr.scrollLeft = adIdx * tr.clientWidth;
        if (!suave) tr.style.scrollBehavior = '';
        marcarPontosAds();
    }
    const marcarPontosAds = () => document.querySelectorAll('#bz-ads .bz-ponto').forEach((p, k) => p.classList.toggle('on', k === adIdx));

    function ligarAds() {
        clearInterval(adTimer);
        const box = document.getElementById('bz-ads');
        if (!box || reduzMov() || slidesDeAds().length < 2) return;
        let pausado = false;
        box.onpointerenter = () => { pausado = true; };
        box.onpointerleave = () => { pausado = false; };
        adTimer = setInterval(() => {
            if (pausado || document.hidden || !raiz.isConnected || raiz.offsetParent === null || vista !== 'feed' || pilha.length) return;
            irParaAd(adIdx + 1);
        }, 6500);
    }

    function acaoDoAd(i) {
        const s = slidesDeAds()[Number(i)];
        if (!s) return;
        if (!s.casa) { abrirLoja(s.loja_id); return; }
        if (s.acao === 'painel') abrirPainel(minhaLojaId ? 'inicio' : 'dados');
        else if (s.acao === 'aviso') { const d = document.getElementById('bz-aviso'); if (d) { d.open = true; d.scrollIntoView({ behavior: reduzMov() ? 'auto' : 'smooth', block: 'center' }); } }
        else if (s.acao === 'armazem') document.querySelector('.market-tab[data-tab="tab-loja"]')?.click();
    }

    // ---------- bem avaliadas / filtros / feed ----------
    function desenharDestaques() {
        const alvo = document.getElementById('bz-dest');
        if (!alvo) return;
        alvo.innerHTML = dest.length ? `<div class="bz-dest"><div class="bz-sec-topo" style="margin:0 0 10px"><h3 style="font-size:17px">Bem avaliadas</h3><small>pela nota de quem comprou</small></div>
            <div class="bz-dest-lista">${dest.map((l) => `<button type="button" class="bz-dest-item" data-a="loja" data-id="${Number(l.id)}" style="${estiloLoja(l)}">${logoHtml(l)}<span><b>${esc(l.nome)}</b>${notaHtml(l)}</span></button>`).join('')}</div></div>` : '';
    }

    function desenharFiltros() {
        const alvo = document.getElementById('bz-filtros');
        if (!alvo || !cat) return;
        const antes = alvo.querySelector('#bz-busca');
        const foco = antes && document.activeElement === antes, valor = antes ? antes.value : busca;
        const chips = [{ id: 'todas', nome: 'Tudo' }].concat(cat.categorias);
        alvo.innerHTML = chips.map((c) => `<button type="button" class="bz-chip ${filtro === c.id ? 'on' : ''}" data-a="cat" data-id="${esc(c.id)}">${esc(c.nome)}</button>`).join('')
            + `<div class="bz-filtros-lado"><select id="bz-tipo" aria-label="Tipo de produto"><option value="">Todos os tipos</option><option value="fisico" ${tipoFiltro === 'fisico' ? 'selected' : ''}>Físico</option><option value="digital" ${tipoFiltro === 'digital' ? 'selected' : ''}>Digital</option><option value="servico" ${tipoFiltro === 'servico' ? 'selected' : ''}>Serviço</option></select>
               <label class="bz-busca"><i class="fa-solid fa-magnifying-glass"></i><input type="text" id="bz-busca" maxlength="40" placeholder="Buscar loja ou produto..." value="${esc(valor)}"></label>
               <button type="button" class="bz-btn sec pq" data-a="embaralhar" title="Mostra o feed em outra ordem"><i class="fa-solid fa-shuffle"></i> Embaralhar</button></div>`;
        if (foco) { const i = alvo.querySelector('#bz-busca'); i.focus(); i.setSelectionRange(valor.length, valor.length); }
    }

    function desenharFeed() {
        const alvo = document.getElementById('bz-feed');
        if (!alvo) return;
        alvo.innerHTML = feed.itens.map((i) => i.t === 'quad' ? htmlQuad(i.produtos) : htmlLoja(i.loja)).join('')
            || (feed.carregado ? `<div class="bz-vazio" style="grid-column:1/-1"><i class="fa-solid fa-store-slash"></i>${busca || filtro !== 'todas' || tipoFiltro ? 'Nada encontrado com esse filtro.' : 'A vila ainda está vazia. Seja o primeiro: abra a sua lojinha!'}</div>` : '<div class="bz-vazio" style="grid-column:1/-1"><i class="fa-solid fa-spinner fa-spin"></i>Abrindo o Bazar...</div>');
        const mais = document.getElementById('bz-mais');
        if (mais) mais.innerHTML = feed.temMais ? `<button type="button" class="bz-btn sec" data-a="mais" ${feed.carregando ? 'disabled' : ''}>${feed.carregando ? '<i class="fa-solid fa-spinner fa-spin"></i> Carregando...' : 'Ver mais lojas'}</button>` : (feed.itens.length ? '<div class="bz-fim">Isso é tudo por enquanto.</div>' : '');
        observarMais();
    }

    function observarMais() {
        if (observador) { observador.disconnect(); observador = null; }
        const botao = document.querySelector('#bz-mais [data-a="mais"]');
        if (!botao || !('IntersectionObserver' in window)) return;
        observador = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) pedirFeed(false); }, { root: rolador(), rootMargin: '400px' });
        observador.observe(botao);
    }

    /** Pede o feed. `tag` volta junto na resposta: resposta de um filtro/seed que já não vale é ignorada (sem misturar páginas). */
    function pedirFeed(zerar) {
        if (!zerar && (feed.carregando || !feed.temMais)) return;
        if (zerar) { desatualizada = false; const n = document.getElementById('bz-novidade'); if (n) n.innerHTML = ''; }
        feed.carregando = true;
        ctx.emitir('bazar_listar', { busca, categoria: filtro === 'todas' ? null : filtro, tipo: tipoFiltro || null, seed, pagina: zerar ? 0 : feed.pagina + 1, tag: tagDoFeed() });
        if (!zerar) desenharFeed();
    }

    function mostrarNovidade() {
        const alvo = document.getElementById('bz-novidade');
        if (alvo) alvo.innerHTML = desatualizada && feed.itens.length ? '<div class="bz-novidade"><button type="button" class="bz-btn pq" data-a="atualizar"><i class="fa-solid fa-rotate"></i> Há novidades na vila: atualizar</button></div>' : '';
    }

    // ---------------------------------------------------------------------
    // PÁGINA DA LOJA (substitui o feed)
    // ---------------------------------------------------------------------
    function desenharLoja() {
        const l = lojaAtual, alvo = vistaEl.loja;
        if (!alvo) return;
        const voltar = '<div class="bz-voltar"><button type="button" class="bz-btn sec pq" data-a="voltar"><i class="fa-solid fa-arrow-left"></i> Voltar ao Bazar</button></div>';
        if (!l) { alvo.innerHTML = `${voltar}<div class="bz-vazio"><i class="fa-solid fa-spinner fa-spin"></i>Abrindo a loja...</div>`; return; }
        const capa = urlOk(l.banner_url);
        (l.produtos || []).forEach((p) => produtos.set(p.id, { ...p, loja_nome: l.nome, loja_cor: l.cor }));
        alvo.innerHTML = `${voltar}
            <div class="bz-loja-pagina" style="${estiloLoja(l)}">
                <div class="bz-loja-capa" style="${capa ? `background-image:url('${esc(urlCss(capa))}')` : ''}"><div class="bz-toldo"></div></div>
                <div class="bz-loja-id">${logoHtml(l)}<h3>${esc(l.nome)}</h3></div>
                <div class="bz-loja-meta">${notaHtml(l)}<span><i class="fa-solid fa-tag"></i> ${esc(nomeCat(l.categoria))}</span>${l.regiao ? `<span><i class="fa-solid fa-location-dot"></i> ${esc(l.regiao)}</span>` : ''}<span>${Number(l.vendas)} venda(s)</span><span>por ${esc(l.dono_nome)}</span>${!l.aberta ? '<span style="color:var(--red-color)">Fechada</span>' : ''}</div>
                <div class="bz-loja-conteudo">
                    ${l.descricao ? `<p style="margin:0;line-height:1.5">${esc(l.descricao)}</p>` : ''}
                    ${l.anuncio_titulo || l.anuncio_texto ? `<div class="bz-anuncio"><b>${esc(l.anuncio_titulo)}</b>${esc(l.anuncio_texto)}</div>` : ''}
                    <div class="bz-sec-topo" style="margin:0"><h3 style="font-size:18px">Produtos</h3></div>
                    <div class="bz-grade-prod">${l.produtos.map((p) => tileProduto(p)).join('') || '<div class="bz-vazio" style="grid-column:1/-1">Essa loja ainda não tem produtos à venda.</div>'}</div>
                    ${l.avaliacoes.length ? `<div class="bz-sec-topo" style="margin:0"><h3 style="font-size:18px">Avaliações</h3></div>${l.avaliacoes.map((a) => `<div class="bz-aval"><b>${esc(a.nome)}</b> · ${'★'.repeat(a.nota)}${'☆'.repeat(5 - a.nota)}${a.texto ? `<br>${esc(a.texto)}` : ''}</div>`).join('')}` : ''}
                    <div style="display:flex;gap:10px;flex-wrap:wrap">${l.eh_dono ? '<button type="button" class="bz-btn sec" data-a="painel-ir" data-id="visual"><i class="fa-solid fa-pen"></i> Editar minha loja</button>' : `<button type="button" class="bz-link" data-a="denunciar" data-t="loja" data-id="${Number(l.id)}" data-nome="${esc(l.nome)}"><i class="fa-solid fa-flag"></i> Denunciar loja</button>`}</div>
                </div>
            </div>`;
    }

    function abrirLoja(id) {
        fecharModal('produto');
        lojaAtual = null;
        irPara('loja');
        desenharLoja();
        ctx.emitir('bazar_abrir_loja', { loja_id: Number(id) });
    }

    // ---------------------------------------------------------------------
    // PRODUTO (modal sobre a vista atual)
    // ---------------------------------------------------------------------
    function desenharProduto() {
        const s = prodAtual;
        if (!s) return;
        const p = s.p, l = lojaAtual && lojaAtual.id === p.loja_id ? lojaAtual : null;
        const midias = (p.imagens || []).map(urlOk).filter(Boolean).map((u) => ({ t: 'img', u }));
        if (p.video_url) midias.push({ t: 'video', u: p.video_url });
        s.idx = Math.min(s.idx, Math.max(midias.length - 1, 0));
        const atual = midias[s.idx];
        const principal = !atual ? `<i class="fa-solid ${ICONE_TIPO[p.tipo] || 'fa-box'}"></i>`
            : atual.t === 'video' ? `<video src="${esc(atual.u)}" controls preload="metadata" playsinline></video>` : `<img src="${esc(atual.u)}" alt="">`;
        const mini = midias.length > 1 ? `<div class="bz-miniaturas">${midias.map((m, i) => `<button type="button" class="bz-mini ${i === s.idx ? 'on' : ''}" data-a="midia" data-i="${i}">${m.t === 'video' ? '<i class="fa-solid fa-play"></i>' : `<img src="${esc(m.u)}" alt="">`}</button>`).join('')}</div>` : '';
        const combo = (p.combo_itens || []).length ? `<div class="bz-combo"><b>Combo inclui:</b><ul>${p.combo_itens.map((i) => `<li>${esc(i)}</li>`).join('')}</ul>${p.preco_avulso_cent > p.preco_cent ? `<small>Avulso: ${brl(p.preco_avulso_cent)}. Você economiza ${brl(p.preco_avulso_cent - p.preco_cent)}.</small>` : ''}</div>` : '';
        const dono = (l && l.eh_dono) || (minhaLojaId && p.loja_id === minhaLojaId);
        const esgotado = p.estoque === 0;
        const vendedor = `<button type="button" class="bz-vendedor" data-a="loja" data-id="${Number(p.loja_id)}">${l ? logoHtml(l) : '<span class="bz-logo ini"><i class="fa-solid fa-store"></i></span>'}<span><b>${esc(l ? l.nome : p.loja_nome || 'Ver a loja')}</b><small>${l ? esc(l.dono_nome) : 'Ver a loja e as avaliações'}</small></span></button>`;
        const compra = dono ? '<div class="bz-como">Este produto é da sua loja.</div>'
            : esgotado ? '<button type="button" class="bz-btn" disabled>Esgotado</button>'
            : `<div class="bz-qtd">Quantidade <button type="button" data-a="qtd" data-d="-1">−</button><span>${s.qtd}</span><button type="button" data-a="qtd" data-d="1">+</button>${p.estoque != null ? `<small style="color:var(--text-muted)">restam ${Number(p.estoque)}</small>` : ''}</div>
               <label class="bz-campo">Recado pro vendedor (opcional)<textarea id="bz-nota-ped" maxlength="${(cat.limites || {}).nota_pedido || 200}" style="min-height:54px" data-campo="nota">${esc(s.nota)}</textarea></label>
               <button type="button" class="bz-btn verde" data-a="pedir" ${s.enviando ? 'disabled' : ''}>${s.enviando ? '<i class="fa-solid fa-spinner fa-spin"></i> Enviando...' : `<i class="fa-solid fa-bag-shopping"></i> Quero comprar · ${brl(p.preco_cent * s.qtd)}`}</button>`;
        modal('produto', `
            <button type="button" class="bz-fechar" data-a="fechar" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button>
            <div class="bz-prod-det" style="overflow-y:auto">
                <div class="bz-galeria"><div class="bz-galeria-main">${principal}</div>${mini}</div>
                <div class="bz-prod-lado">
                    <span class="bz-tag" style="align-self:flex-start">${esc(ROTULO_TIPO[p.tipo] || 'Produto')}</span>
                    <h3>${esc(p.nome)}</h3>
                    <div class="bz-preco-grande">${brl(p.preco_cent)}${p.preco_avulso_cent > p.preco_cent ? `<s>${brl(p.preco_avulso_cent)}</s>` : ''}</div>
                    ${p.descricao ? `<p style="margin:0;line-height:1.5;white-space:pre-wrap">${esc(p.descricao)}</p>` : ''}
                    ${combo}${vendedor}${compra}
                    <div class="bz-como"><b>Como funciona:</b> 1) você faz o pedido, 2) o vendedor aceita, 3) você paga por Pix direto a ele, 4) ele confirma e você recebe. O Panteão não intermedia o pagamento.</div>
                    ${dono ? '' : `<button type="button" class="bz-link" data-a="denunciar" data-t="produto" data-id="${Number(p.id)}" data-nome="${esc(p.nome)}"><i class="fa-solid fa-flag"></i> Denunciar produto</button>`}
                </div>
            </div>`, { classe: 'larga', estilo: l ? estiloLoja(l) : (p.loja_cor ? `--bz-cor:${corDe(p.loja_cor)}` : '') });
    }

    function abrirProduto(id) {
        const p = produtos.get(Number(id));
        if (!p) return;
        prodAtual = { p, idx: 0, qtd: 1, nota: '', enviando: false };
        desenharProduto();
        if (!lojaAtual || lojaAtual.id !== p.loja_id) ctx.emitir('bazar_abrir_loja', { loja_id: p.loja_id });   // traz logo/cor/avaliação do vendedor
    }

    // ---------------------------------------------------------------------
    // PEDIDOS (detalhe em modal; as listas moram no painel)
    // ---------------------------------------------------------------------
    const PASSOS = [['aguardando', 'Pedido'], ['aceito', 'Aceito'], ['pago', 'Pago'], ['confirmado', 'Confirmado'], ['concluido', 'Concluído']];

    function htmlPasso(status) {
        if (status === 'recusado' || status === 'cancelado') return `<span class="bz-status ${status}">${status === 'recusado' ? 'Recusado' : 'Cancelado'}</span>`;
        const i = PASSOS.findIndex((x) => x[0] === status);
        return `<div class="bz-passos">${PASSOS.map(([id, nome], k) => `<span class="bz-passo ${k < i ? 'feito' : k === i ? 'atual' : ''}">${k < i ? '✓ ' : ''}${nome}</span>`).join('')}</div>`;
    }

    function acoesDoPedido(p) {
        const b = (acao, rot, cls = '', conf = '') => `<button type="button" class="bz-btn ${cls}" data-a="agir" data-acao="${acao}" data-id="${Number(p.id)}" ${conf ? `data-conf="${esc(conf)}"` : ''}>${rot}</button>`;
        const v = p.papel === 'vendedor';
        switch (p.status) {
            case 'aguardando': return v ? b('aceitar', '<i class="fa-solid fa-check"></i> Aceitar pedido', 'verde') + b('recusar', 'Recusar', 'perigo', 'Recusar este pedido?') : b('cancelar', 'Cancelar pedido', 'sec', 'Cancelar o pedido?');
            case 'aceito': return v ? b('cancelar', 'Cancelar pedido', 'sec', 'Cancelar o pedido? O estoque reservado volta.') : b('paguei', '<i class="fa-solid fa-circle-check"></i> Já paguei', 'verde', 'Confirma que você já fez o Pix? O vendedor vai conferir.') + b('cancelar', 'Cancelar', 'sec', 'Cancelar o pedido?');
            case 'pago': return v ? b('confirmar', '<i class="fa-solid fa-circle-check"></i> Recebi o Pix', 'verde', 'Confirma que o Pix caiu na sua conta? Isso libera a entrega.') + b('nao_recebi', 'Não recebi', 'perigo', 'O Pix não apareceu? O pedido volta pra "aceito".') : '';
            case 'confirmado': return v ? '' : b('recebi', '<i class="fa-solid fa-box-open"></i> Recebi o produto', 'verde', 'Confirma que recebeu? Isso conclui o pedido.');
            default: return '';
        }
    }

    function htmlPedido(p) {
        const v = p.papel === 'vendedor';
        let dica = '';
        if (p.status === 'aguardando') dica = v ? 'Aceite pra liberar o Pix pro comprador (a sua chave Pix da loja precisa estar cadastrada).' : 'Aguardando o vendedor aceitar. Você será avisado.';
        else if (p.status === 'aceito') dica = v ? 'Aguardando o comprador pagar.' : '';
        else if (p.status === 'pago') dica = v ? 'O comprador diz que pagou. Confira no app do seu banco e confirme.' : 'Aguardando o vendedor conferir o Pix.';
        else if (p.status === 'confirmado') dica = v ? 'Pix confirmado. Entregue e aguarde o comprador confirmar o recebimento.' : '';
        const pix = p.pix && p.status === 'aceito' ? `<div class="bz-pix"><div class="qr" id="bz-qr"></div><div>
                <h4>Pague ${brl(p.pix.valor_cent)} por Pix</h4>
                <p>Recebedor: <b>${esc(p.pix.nome)}</b> · chave ${esc(p.pix.chave_mascarada)}.<br>Abra o app do seu banco, escolha <b>Pix copia e cola</b> (ou leia o QR) e <b>confira se o nome do recebedor bate</b> antes de pagar.</p>
                <textarea readonly id="bz-cc">${esc(p.pix.copia_cola)}</textarea>
                <div style="margin-top:8px"><button type="button" class="bz-btn pq" data-a="copiar"><i class="fa-regular fa-copy"></i> Copiar código</button></div></div></div>` : '';
        const entrega = p.entrega ? `<div class="bz-entrega"><b><i class="fa-solid fa-gift"></i> ${v ? 'Instrução de entrega (só o comprador de um pedido confirmado vê)' : 'Sua entrega'}</b>${esc(p.entrega)}</div>` : '';
        const aval = p.status === 'concluido' ? (p.pode_avaliar
            ? `<div class="bz-como"><b>Como foi a compra?</b><div class="bz-estrelas" id="bz-estrelas">${[1, 2, 3, 4, 5].map((n) => `<button type="button" data-a="estrela" data-n="${n}" class="${n <= (ed_aval.nota || 0) ? 'on' : ''}">★</button>`).join('')}</div>
               <label class="bz-campo"><textarea maxlength="${(cat.limites || {}).avaliacao || 200}" data-campo="aval-texto" placeholder="Comentário (opcional, sem links)" style="min-height:54px">${esc(ed_aval.texto || '')}</textarea></label>
               <button type="button" class="bz-btn pq" data-a="avaliar" data-id="${Number(p.id)}" ${ed_aval.nota ? '' : 'disabled'}>Enviar avaliação</button></div>`
            : (p.avaliado ? '<div class="bz-como">Você já avaliou este pedido. Obrigado!</div>' : '')) : '';
        const msgs = (p.mensagens || []);
        const conversa = `<div class="bz-conversa"><b style="font-size:13px;color:var(--text-header)">Conversa do pedido <small style="color:var(--text-muted);font-weight:700">(só texto, sem links; só vocês dois leem)</small></b>
            <div class="bz-msgs" id="bz-msgs">${msgs.length ? msgs.map((m) => `<div class="bz-msg ${m.autor_id === ctx.meuId() ? 'eu' : ''}">${esc(m.texto)}<small>${esc(m.hora)}</small></div>`).join('') : '<div style="color:var(--text-muted);font-size:12.5px;text-align:center;padding:8px">Nenhuma mensagem ainda.</div>'}</div>
            <div class="bz-enviar"><input type="text" id="bz-msg-in" data-enviar maxlength="${(cat.limites || {}).msg || 300}" placeholder="Escreva uma mensagem..."><button type="button" class="bz-btn pq" data-a="enviar-msg" data-id="${Number(p.id)}"><i class="fa-solid fa-paper-plane"></i></button></div></div>`;
        const outro = p.contraparte || {};
        return `${topoModal(p.produto_nome, `${v ? 'Comprador' : 'Vendedor'}: ${outro.nome || '?'} · ${p.quantidade}x · ${brl(p.total_cent)} · ${p.loja_nome}`)}
            <div class="bz-card-corpo">
                ${htmlPasso(p.status)}
                ${dica ? `<div class="bz-como">${esc(dica)}</div>` : ''}
                ${p.nota ? `<div class="bz-como"><b>Recado do comprador:</b> ${esc(p.nota)}</div>` : ''}
                ${pix}${entrega}
                <div style="display:flex;gap:10px;flex-wrap:wrap">${acoesDoPedido(p)}</div>
                ${aval}${conversa}
            </div>`;
    }

    const brand = () => (getComputedStyle(document.documentElement).getPropertyValue('--brand-color') || '#7289da').trim();

    function desenharPedido(id) {
        const p = pedCache.get(Number(id));
        if (!p) return;
        const el = modal('pedido', htmlPedido(p), { classe: 'larga', estilo: `--bz-cor:${brand()}` });
        el.dataset.pedido = p.id;
        const m = el.querySelector('#bz-msgs'); if (m) m.scrollTop = m.scrollHeight;
        if (p.pix && p.status === 'aceito' && ctx.qr) { const q = el.querySelector('#bz-qr'); if (q) ctx.qr(q, p.pix.copia_cola); }
    }

    function abrirPedido(id) {
        ed_aval = { nota: 0, texto: '' };
        const p = pedCache.get(Number(id));
        if (p) desenharPedido(id);
        ctx.emitir('bazar_abrir_pedido', { pedido_id: Number(id) });
        if (!p) { const m = modal('pedido', `<button type="button" class="bz-fechar" data-a="fechar"><i class="fa-solid fa-xmark"></i></button><div class="bz-vazio"><i class="fa-solid fa-spinner fa-spin"></i>Abrindo o pedido...</div>`, { classe: 'estreita' }); m.dataset.pedido = id; }
    }

    const pedePraMim = (p) => (p.papel === 'vendedor' && ['aguardando', 'pago'].includes(p.status)) || (p.papel === 'comprador' && ['aceito', 'confirmado'].includes(p.status));

    function linhaPedido(p) {
        const outro = p.contraparte || {};
        return `<button type="button" class="bz-ped-linha ${pedePraMim(p) ? 'pede' : ''}" data-a="ver-pedido" data-id="${Number(p.id)}">
            <span class="bz-linha-prod" style="border:0;background:none;padding:0;flex:1"><span class="img">${urlOk(p.imagem) ? `<img src="${esc(urlOk(p.imagem))}" alt="">` : '<i class="fa-solid fa-box"></i>'}</span>
            <span class="txt"><b>${esc(p.produto_nome)}</b><small>${p.quantidade}x · ${brl(p.total_cent)} · ${esc(outro.nome || '?')} · ${esc(p.atualizado_em)}</small></span></span>
            <span class="bz-status ${esc(p.status)}">${esc(p.rotulo)}</span></button>`;
    }

    // ---------------------------------------------------------------------
    // PAINEL "MINHA LOJINHA" (página que ocupa o Mercado Elite)
    // ---------------------------------------------------------------------
    const rascunhoLoja = () => minha ? {
        nome: minha.nome, descricao: minha.descricao, categoria: minha.categoria, porte: minha.porte === 'grande' ? 'media' : minha.porte, regiao: minha.regiao, cor: minha.cor, toldo: minha.toldo,
        logo_url: minha.logo_url || '', banner_url: minha.banner_url || '', anuncio_titulo: minha.anuncio_titulo, anuncio_texto: minha.anuncio_texto,
        pix_chave: minha.pix_chave, pix_nome: minha.pix_nome, pix_cidade: minha.pix_cidade, aberta: minha.aberta,
    } : { nome: '', descricao: '', categoria: 'outros', porte: 'micro', regiao: '', cor: 'ambar', toldo: 'vermelho', logo_url: '', banner_url: '', anuncio_titulo: '', anuncio_texto: '', pix_chave: '', pix_nome: ctx.nome(), pix_cidade: '', aberta: true };

    const rascunhoProduto = (p) => p ? {
        id: p.id, nome: p.nome, descricao: p.descricao, tipo: p.tipo, preco: paraReais(p.preco_cent), estoque: p.estoque == null ? '' : String(p.estoque), imagens: (p.imagens || []).slice(), video_url: p.video_url || '',
        combo: (p.combo_itens || []).length > 0, combo_itens: (p.combo_itens || []).slice(), preco_avulso: p.preco_avulso_cent ? paraReais(p.preco_avulso_cent) : '', entrega: p.entrega || '', ativo: p.ativo,
    } : { nome: '', descricao: '', tipo: 'fisico', preco: '', estoque: '', imagens: [], video_url: '', combo: false, combo_itens: [''], preco_avulso: '', entrega: '', ativo: true };

    const campo = (rot, nome, valor, max, dica, tipo = 'text', extra = '') => `<label class="bz-campo ${extra}">${rot}
        ${tipo === 'area' ? `<textarea data-campo="${nome}" maxlength="${max}">${esc(valor)}</textarea>` : `<input type="text" data-campo="${nome}" maxlength="${max}" value="${esc(valor)}">`}
        ${max ? `<span class="bz-contador" data-cont="${nome}">${String(valor || '').length}/${max}</span>` : ''}${dica ? `<small>${dica}</small>` : ''}</label>`;

    const previaLoja = () => ({ ...ed.loja, id: 0, nota: null, nota_qtd: 0, vendas: 0, total_produtos: minha ? minha.produtos.length : 0, dono_nome: ctx.nome(),
        produtos: (minha ? minha.produtos : []).filter((p) => p.ativo).slice(0, 4) });
    const previaHtml = () => `<div class="bz-ed-prev"><div class="bz-campo" style="margin-bottom:8px">Como o feed mostra a sua loja</div><div id="bz-previa">${htmlLoja(previaLoja(), true)}</div></div>`;
    const botaoSalvarLoja = () => `<div class="cheio"><button type="button" class="bz-btn" data-a="ed-salvar-loja" ${ed.salvando ? 'disabled' : ''}>${ed.salvando ? '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...' : `<i class="fa-solid fa-floppy-disk"></i> ${minha ? 'Salvar' : 'Abrir minha lojinha'}`}</button></div>`;

    function formDados() {
        const d = ed.loja, L = cat.limites;
        return `<div class="bz-ed-grid"><div class="bz-form">
            ${campo('Nome da loja', 'nome', d.nome, L.nome_loja, '', 'text', 'cheio')}
            ${campo('Descrição', 'descricao', d.descricao, L.desc_loja, 'Sem links (golpe costuma vir por link).', 'area', 'cheio')}
            <label class="bz-campo">Categoria<select data-campo="categoria">${cat.categorias.map((c) => `<option value="${c.id}" ${d.categoria === c.id ? 'selected' : ''}>${esc(c.nome)}</option>`).join('')}</select></label>
            ${campo('Região (opcional)', 'regiao', d.regiao, L.regiao, 'Ex.: Samambaia, DF. Ajuda quem compra produto físico.')}
            <div class="bz-campo cheio" style="border-top:2px solid var(--bg-tertiary);padding-top:12px">Pix (como você recebe)<small>Só quem tem um pedido ACEITO com você vê o "copia e cola". O dinheiro vai direto pra sua conta; o Panteão não toca nele.</small></div>
            ${campo('Chave Pix', 'pix_chave', d.pix_chave, 80, 'CPF, CNPJ, telefone (+55...), e-mail ou chave aleatória.')}
            ${campo('Nome do recebedor', 'pix_nome', d.pix_nome, 25, 'Como aparece no banco do comprador.')}
            ${campo('Cidade do recebedor', 'pix_cidade', d.pix_cidade, 15, '')}
            <label class="bz-campo" style="flex-direction:row;align-items:center;gap:10px;text-transform:none;font-size:14px"><input type="checkbox" data-campo="aberta" ${d.aberta ? 'checked' : ''}> Loja aberta (desmarque pra sair do feed sem apagar nada)</label>
            ${botaoSalvarLoja()}
        </div>${previaHtml()}</div>`;
    }

    function formVisual() {
        const d = ed.loja, L = cat.limites;
        const cores = Object.keys(cat.cores).map((id) => `<button type="button" class="bz-amostra ${d.cor === id ? 'on' : ''}" data-a="ed-cor" data-id="${id}" style="background:${cat.cores[id]}" title="${id}"></button>`).join('');
        const toldos = Object.keys(cat.toldos).map((id) => { const t = cat.toldos[id]; return t ? `<button type="button" class="bz-amostra toldo ${d.toldo === id ? 'on' : ''}" data-a="ed-toldo" data-id="${id}" style="--t1:${t[0]};--t2:${t[1]}" title="${id}"></button>` : `<button type="button" class="bz-amostra toldo sem ${d.toldo === id ? 'on' : ''}" data-a="ed-toldo" data-id="${id}">sem</button>`; }).join('');
        const upl = (campoNome, rot) => `<div class="bz-campo">${rot}<div class="bz-upl">${urlOk(d[campoNome]) ? `<span class="bz-upl-img"><img src="${esc(urlOk(d[campoNome]))}" alt=""><button type="button" data-a="ed-tirar" data-id="${campoNome}">×</button></span>` : ''}<button type="button" class="bz-btn sec pq" data-a="ed-subir" data-id="${campoNome}"><i class="fa-solid fa-image"></i> ${urlOk(d[campoNome]) ? 'Trocar' : 'Enviar imagem'}</button></div></div>`;
        return `<div class="bz-ed-grid"><div class="bz-form">
            <div class="bz-campo cheio">Tamanho da loja<div class="bz-form" style="gap:10px">
                <button type="button" class="bz-opcao ${d.porte === 'micro' ? 'on' : ''}" data-a="ed-porte" data-id="micro"><b>Barraca de feira</b><span>Poucos itens. Eles entram nos quadrados da "Feira dos aldeões".</span></button>
                <button type="button" class="bz-opcao ${d.porte === 'media' ? 'on' : ''}" data-a="ed-porte" data-id="media"><b>Loja com fachada</b><span>Toldo, placa e vitrine própria no feed.</span></button></div></div>
            <div class="bz-campo">Cor da loja<div class="bz-amostras">${cores}</div></div>
            <div class="bz-campo">Toldo<div class="bz-amostras">${toldos}</div></div>
            ${upl('logo_url', 'Logo (quadrada)')}${upl('banner_url', 'Banner da página da loja')}
            ${campo('Propaganda: título', 'anuncio_titulo', d.anuncio_titulo, L.anuncio_titulo, 'Aparece destacado na sua fachada e na página da loja.')}
            ${campo('Propaganda: texto', 'anuncio_texto', d.anuncio_texto, L.anuncio_texto, '')}
            ${botaoSalvarLoja()}
        </div>${previaHtml()}</div>`;
    }

    function formProduto() {
        const d = ed.prod, L = cat.limites;
        const imgs = d.imagens.map((u, i) => `<span class="bz-upl-img"><img src="${esc(urlOk(u))}" alt=""><button type="button" data-a="pd-tirar-img" data-i="${i}">×</button></span>`).join('');
        return `<div class="bz-form">
            ${campo('Nome do produto', 'nome', d.nome, L.nome_prod, '', 'text', 'cheio')}
            ${campo('Descrição', 'descricao', d.descricao, L.desc_prod, 'Sem links.', 'area', 'cheio')}
            <label class="bz-campo">Tipo<select data-campo="tipo"><option value="fisico" ${d.tipo === 'fisico' ? 'selected' : ''}>Produto físico</option><option value="digital" ${d.tipo === 'digital' ? 'selected' : ''}>Digital (arquivo, código...)</option><option value="servico" ${d.tipo === 'servico' ? 'selected' : ''}>Serviço (comissão, aula...)</option></select></label>
            ${campo('Preço (R$)', 'preco', d.preco, 12, `De ${brl(L.preco_min_cent)} a ${brl(L.preco_max_cent)}.`)}
            ${campo('Estoque', 'estoque', d.estoque, 4, 'Deixe vazio pra sem limite. Aceitar um pedido reserva o estoque.')}
            <div class="bz-campo">Fotos (até ${L.imagens})<div class="bz-upl">${imgs}${d.imagens.length < L.imagens ? `<button type="button" class="bz-btn sec pq" data-a="pd-subir-img"><i class="fa-solid fa-image"></i> Adicionar foto</button>` : ''}</div></div>
            <div class="bz-campo">Vídeo (opcional)<div class="bz-upl">${d.video_url ? '<span style="font-size:13px;font-weight:700;text-transform:none;color:var(--text-normal)"><i class="fa-solid fa-film"></i> Vídeo enviado</span><button type="button" class="bz-btn sec pq" data-a="pd-tirar-video">Tirar</button>' : '<button type="button" class="bz-btn sec pq" data-a="pd-subir-video"><i class="fa-solid fa-film"></i> Enviar vídeo (até 25 MB)</button>'}</div></div>
            <label class="bz-campo cheio" style="flex-direction:row;align-items:center;gap:10px;text-transform:none;font-size:14px"><input type="checkbox" data-campo="combo" ${d.combo ? 'checked' : ''}> É um combo (vários itens por um preço)</label>
            ${d.combo ? `<div class="bz-campo cheio">O que vem no combo<div style="display:flex;flex-direction:column;gap:6px">${d.combo_itens.map((c, i) => `<div style="display:flex;gap:6px"><input type="text" class="bz-in-combo" data-combo="${i}" maxlength="${L.combo_item}" value="${esc(c)}" style="flex:1;padding:8px 10px;border-radius:10px;border:2px solid var(--bg-tertiary);background:var(--bg-secondary);color:var(--text-header)"><button type="button" class="bz-btn sec pq" data-a="pd-tirar-combo" data-i="${i}">×</button></div>`).join('')}${d.combo_itens.length < L.combo ? '<button type="button" class="bz-btn sec pq" style="align-self:flex-start" data-a="pd-add-combo">+ Item</button>' : ''}</div></div>
            ${campo('Preço dos itens avulsos (R$)', 'preco_avulso', d.preco_avulso, 12, 'Opcional: mostra "Avulso R$ X, você economiza Y".')}` : ''}
            ${campo('Instrução de entrega (privado)', 'entrega', d.entrega, L.entrega, 'Link, código ou combinado de entrega. SÓ o comprador de um pedido com Pix confirmado vê. Aqui link é permitido.', 'area', 'cheio')}
            <label class="bz-campo cheio" style="flex-direction:row;align-items:center;gap:10px;text-transform:none;font-size:14px"><input type="checkbox" data-campo="ativo" ${d.ativo ? 'checked' : ''}> À venda (desmarque pra pausar)</label>
            <div class="cheio" style="display:flex;gap:10px;flex-wrap:wrap"><button type="button" class="bz-btn" data-a="pd-salvar" ${ed.salvando ? 'disabled' : ''}>${ed.salvando ? '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...' : '<i class="fa-solid fa-floppy-disk"></i> Salvar produto'}</button><button type="button" class="bz-btn sec" data-a="pd-voltar">Voltar</button></div></div>`;
    }

    function listaProdutos() {
        const ps = minha ? minha.produtos : [];
        return `<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px"><b style="color:var(--text-header)">${ps.length} produto(s)</b><button type="button" class="bz-btn" data-a="pd-novo"><i class="fa-solid fa-plus"></i> Novo produto</button></div>
            <div style="display:flex;flex-direction:column;gap:10px">${ps.map((p) => `<div class="bz-linha-prod ${p.ativo ? '' : 'bz-pausado'}"><span class="img">${urlOk((p.imagens || [])[0]) ? `<img src="${esc(urlOk(p.imagens[0]))}" alt="">` : `<i class="fa-solid ${ICONE_TIPO[p.tipo] || 'fa-box'}"></i>`}</span>
                <span class="txt"><b>${esc(p.nome)}</b><small>${brl(p.preco_cent)} · ${p.estoque == null ? 'sem limite' : p.estoque + ' em estoque'} · ${p.vendidos} vendido(s)${p.ativo ? '' : ' · PAUSADO'}${p.oculta ? ' · OCULTO por denúncias' : ''}</small></span>
                <span class="acoes"><button type="button" class="bz-btn sec pq" data-a="pd-editar" data-id="${p.id}">Editar</button><button type="button" class="bz-btn sec pq" data-a="pd-pausar" data-id="${p.id}">${p.ativo ? 'Pausar' : 'Ativar'}</button><button type="button" class="bz-btn perigo pq" data-a="pd-apagar" data-id="${p.id}">Apagar</button></span></div>`).join('') || '<div class="bz-vazio"><i class="fa-solid fa-box-open"></i>Nenhum produto ainda. Cadastre o primeiro!</div>'}</div>`;
    }

    function secaoInicio() {
        if (!minha) return `<div class="bz-onboard"><i class="fa-solid fa-store"></i><h3>Abra a sua lojinha</h3>
            <p>É rápido: dê um nome, escolha a cor e o toldo, cadastre sua chave Pix e depois os produtos. Quando estiver pronta, ela entra no feed do Bazar misturada com todas as outras, sem ninguém na frente de ninguém.</p>
            <button type="button" class="bz-btn" data-a="painel-ir" data-id="dados"><i class="fa-solid fa-hammer"></i> Começar</button></div>`;
        const st = minha.stats || {}, ativos = minha.produtos.filter((p) => p.ativo).length;
        const card = (n, rot, icone, ir) => `<button type="button" class="bz-stat" ${ir ? `data-a="painel-ir" data-id="${ir}"` : 'disabled'}><i class="fa-solid ${icone}"></i><b>${n}</b><small>${rot}</small></button>`;
        const item = (ok, txt, ir, rot) => `<div class="bz-check ${ok ? 'ok' : ''}"><i class="fa-solid ${ok ? 'fa-circle-check' : 'fa-circle'}"></i><span>${txt}</span>${ok ? '' : `<button type="button" class="bz-btn sec pq" data-a="painel-ir" data-id="${ir}">${rot}</button>`}</div>`;
        return `<div class="bz-ini-topo"><div><h3 style="margin:0 0 6px;font-size:24px;color:var(--text-header)">${esc(minha.nome)}</h3>
                <span class="bz-status ${minha.oculta ? 'cancelado' : minha.aberta ? 'concluido' : 'aguardando'}">${minha.oculta ? 'Oculta por denúncias' : minha.aberta ? 'Aberta' : 'Fechada'}</span></div>
            <div style="display:flex;gap:10px;flex-wrap:wrap"><button type="button" class="bz-btn sec" data-a="ver-minha"><i class="fa-solid fa-eye"></i> Ver como cliente</button>
                <button type="button" class="bz-btn sec" data-a="alternar-aberta">${minha.aberta ? 'Fechar a loja' : 'Abrir a loja'}</button></div></div>
            <div class="bz-stats">${card(pend, 'precisam de você', 'fa-bell', 'pedidos')}${card(st.abertos || 0, 'pedidos abertos', 'fa-hourglass-half', 'pedidos')}${card(st.concluidos || 0, 'vendas concluídas', 'fa-circle-check', 'pedidos')}
                ${card(brl(st.receita_cent || 0), 'concluído (Pix direto)', 'fa-coins')}${card(minha.nota ? String(minha.nota).replace('.', ',') + ' ★' : '—', `${minha.nota_qtd} avaliação(ões)`, 'fa-star')}${card(ativos, 'produtos à venda', 'fa-box-open', 'produtos')}</div>
            <div class="bz-ed-grid"><div><div class="bz-campo" style="margin-bottom:8px">Para a sua loja ficar completa</div><div class="bz-checks">
                ${item(!!minha.pix_configurado, 'Chave Pix cadastrada (sem ela você não consegue aceitar pedidos)', 'dados', 'Cadastrar')}
                ${item(ativos > 0, 'Pelo menos um produto à venda', 'produtos', 'Cadastrar')}
                ${item(!!urlOk(minha.logo_url), 'Logo da loja', 'visual', 'Enviar')}
                ${item(!!(minha.anuncio_titulo || minha.anuncio_texto), 'Propaganda na fachada', 'visual', 'Escrever')}</div></div>
                <div class="bz-ed-prev"><div class="bz-campo" style="margin-bottom:8px">Sua fachada no feed</div>${htmlLoja({ ...minha, produtos: minha.produtos.filter((p) => p.ativo).slice(0, 4), total_produtos: ativos }, true)}</div></div>`;
    }

    function secaoPedidos(lista, vazio) {
        if (!pedidos.carregado) return '<div class="bz-vazio"><i class="fa-solid fa-spinner fa-spin"></i>Carregando...</div>';
        if (!lista.length) return `<div class="bz-vazio"><i class="fa-regular fa-face-smile"></i>${vazio}</div>`;
        const pedem = lista.filter(pedePraMim), outros = lista.filter((p) => !pedePraMim(p));
        return `${pedem.length ? `<div class="bz-campo" style="margin-bottom:8px">Precisam de você (${pedem.length})</div><div class="bz-lista">${pedem.map(linhaPedido).join('')}</div>` : ''}
            ${outros.length ? `<div class="bz-campo" style="margin:16px 0 8px">${pedem.length ? 'Os outros' : 'Pedidos'}</div><div class="bz-lista">${outros.map(linhaPedido).join('')}</div>` : ''}`;
    }

    function secaoModeracao() {
        const TIPO = { loja: 'Loja', produto: 'Produto', nota: 'Nota do mapa', servidor: 'Servidor do mapa', usuario: 'Pessoa' };
        if (moderacao === null) return '<div class="bz-vazio"><i class="fa-solid fa-spinner fa-spin"></i>Carregando...</div>';
        return `<p style="margin:0 0 12px;color:var(--text-muted);font-size:13.5px">Denúncias ainda não revisadas. "Restaurar" dispensa as denúncias e devolve o item; "Remover" derruba.</p>
            <div class="bz-lista">${moderacao.map((f) => `<div class="bz-mod ${f.alvo.oculta ? 'oculta' : ''}">
                <h4>${esc(TIPO[f.tipo] || f.tipo)}: ${esc(f.alvo.titulo)} <small style="color:var(--text-muted)">· ${f.total} denúncia(s)${f.alvo.oculta ? ' · OCULTO' : ''}</small></h4>
                <small style="color:var(--text-muted)">${esc(f.alvo.sub)}</small>
                ${f.denuncias.map((d) => `<div style="font-size:12.5px"><b>${esc(d.por)}</b> · ${esc(d.motivo)}${d.detalhe ? ': ' + esc(d.detalhe) : ''}</div>`).join('')}
                <div style="display:flex;gap:8px;flex-wrap:wrap"><button type="button" class="bz-btn ${f.alvo.oculta ? 'verde' : 'sec'} pq" data-a="moderar" data-t="${esc(f.tipo)}" data-id="${Number(f.alvo_id)}" data-acao="restaurar">${f.alvo.oculta ? 'Restaurar (denúncia sem fundamento)' : 'Dispensar denúncia'}</button>${f.tipo === 'usuario' ? '' : `<button type="button" class="bz-btn perigo pq" data-a="moderar" data-t="${esc(f.tipo)}" data-id="${Number(f.alvo_id)}" data-acao="remover">Remover</button>`}</div></div>`).join('') || '<div class="bz-vazio"><i class="fa-regular fa-face-smile"></i>Nada pra revisar. Tudo em paz!</div>'}</div>`;
    }

    function desenharPainel() {
        const alvo = vistaEl.painel;
        if (!alvo || !ed) return;
        const voltar = '<div class="bz-voltar"><button type="button" class="bz-btn sec pq" data-a="voltar"><i class="fa-solid fa-arrow-left"></i> Voltar ao Bazar</button></div>';
        if (!cat || minha === undefined) { alvo.innerHTML = `${voltar}<div class="bz-vazio"><i class="fa-solid fa-spinner fa-spin"></i>Abrindo a sua lojinha...</div>`; return; }
        const tem = !!minha;
        const aba = (id, icone, rot, extra = '', precisaLoja = false) => `<button type="button" class="bz-p-aba ${secao === id ? 'on' : ''}" data-a="painel-ir" data-id="${id}" ${precisaLoja && !tem ? 'disabled' : ''}><i class="fa-solid ${icone}"></i><span>${rot}</span>${extra}</button>`;
        const badge = pend ? `<span class="bz-contagem">${pend}</span>` : '';
        let corpo, titulo;
        switch (secao) {
            case 'produtos': titulo = ed.prod ? (ed.prod.id ? 'Editar produto' : 'Novo produto') : 'Meus produtos'; corpo = ed.prod ? formProduto() : listaProdutos(); break;
            case 'pedidos': titulo = 'Pedidos recebidos'; corpo = secaoPedidos(pedidos.vendendo, 'Nenhum pedido chegou na sua loja ainda.'); break;
            case 'compras': titulo = 'Minhas compras'; corpo = secaoPedidos(pedidos.comprando, 'Você ainda não fez nenhum pedido. Dê uma volta pelo Bazar!'); break;
            case 'visual': titulo = 'Personalizar a fachada'; corpo = formVisual(); break;
            case 'dados': titulo = tem ? 'Dados da loja e Pix' : 'Abrir a minha lojinha'; corpo = formDados(); break;
            case 'moderacao': titulo = 'Moderação'; corpo = eAdmin ? secaoModeracao() : '<div class="bz-vazio">Só administradores.</div>'; break;
            default: titulo = 'Minha lojinha'; corpo = secaoInicio();
        }
        const rolagem = (rolador() || {}).scrollTop || 0;
        alvo.innerHTML = `${voltar}
            <div class="bz-painel" style="${estiloLoja(ed.loja)}">
                <nav class="bz-p-nav"><div class="bz-p-id">${tem ? logoHtml(minha) : '<span class="bz-logo ini"><i class="fa-solid fa-store"></i></span>'}<div><b>${tem ? esc(minha.nome) : 'Minha lojinha'}</b><small>${tem ? 'seu painel' : 'ainda sem loja'}</small></div></div>
                    ${aba('inicio', 'fa-house', 'Visão geral')}${aba('produtos', 'fa-box-open', 'Produtos', tem ? `<small class="bz-p-n">${minha.produtos.length}</small>` : '', true)}${aba('pedidos', 'fa-inbox', 'Pedidos recebidos', badge, true)}
                    ${aba('compras', 'fa-bag-shopping', 'Minhas compras')}${aba('visual', 'fa-palette', 'Personalizar')}${aba('dados', 'fa-id-card', 'Dados e Pix')}${eAdmin ? aba('moderacao', 'fa-gavel', 'Moderação') : ''}</nav>
                <section class="bz-p-corpo"><h2 class="bz-p-titulo">${esc(titulo)}</h2>${corpo}</section></div>`;
        const r = rolador(); if (r) r.scrollTop = rolagem;
    }

    function abrirPainel(sec = 'inicio') {
        secao = sec;
        ed = { loja: rascunhoLoja(), prod: null, salvando: false };
        irPara('painel');
        if (!cat) ctx.emitir('bazar_listar', { seed, pagina: 0, tag: tagDoFeed() });
        ctx.emitir('bazar_minha_loja');
        pedidos.carregado = false;
        ctx.emitir('bazar_meus_pedidos');
        if (sec === 'moderacao') ctx.emitir('bazar_moderacao_listar');
        desenharPainel();
    }

    function irSecao(sec) {
        if (!ed) return;
        secao = sec;
        if (sec !== 'produtos') ed.prod = null;
        if (sec === 'moderacao') { moderacao = null; ctx.emitir('bazar_moderacao_listar'); }
        if (sec === 'pedidos' || sec === 'compras') ctx.emitir('bazar_meus_pedidos');
        desenharPainel();
        const r = rolador(); if (r) r.scrollTop = 0;
    }

    // ---------------------------------------------------------------------
    // CLIQUES e DIGITAÇÃO
    // ---------------------------------------------------------------------
    function escolher(accept, aoEscolher) {
        const i = document.createElement('input');
        i.type = 'file'; i.accept = accept;
        i.onchange = () => { if (i.files[0]) aoEscolher(i.files[0]); };
        i.click();
    }
    async function subir(file, aoSubir) {
        ed.salvando = true; desenharPainel();
        try { const r = await ctx.upload(file); aoSubir(r.url); } catch (e) { ctx.toast(e.message || 'Não foi possível enviar o arquivo.', 'error'); }
        if (ed) { ed.salvando = false; desenharPainel(); }
    }

    function payloadProduto(d) {
        return { id: d.id, nome: d.nome, descricao: d.descricao, tipo: d.tipo, preco_cent: lerReais(d.preco), estoque: d.estoque === '' ? null : Number(d.estoque), imagens: d.imagens, video_url: d.video_url,
                 combo_itens: d.combo ? d.combo_itens : [], preco_avulso_cent: d.combo && d.preco_avulso ? lerReais(d.preco_avulso) : null, entrega: d.entrega, ativo: d.ativo };
    }

    function clique(e, tipo) {
        const b = e.target && e.target.closest ? e.target.closest('[data-a]') : null;
        if (!b || b.disabled) return;
        const id = b.dataset.id, a = b.dataset.a;
        switch (a) {
            case 'fechar': fecharModal(tipo); break;
            case 'voltar': irPara('feed'); mostrarNovidade(); break;
            case 'loja': abrirLoja(Number(id)); break;
            case 'prod': abrirProduto(id); break;
            case 'cat': filtro = id; desenharFiltros(); pedirFeed(true); break;
            case 'embaralhar': seed = novaSeed(); pedirFeed(true); break;
            case 'atualizar': pedirFeed(true); break;
            case 'mais': pedirFeed(false); break;
            case 'ad': acaoDoAd(b.dataset.i); break;
            case 'ad-seta': irParaAd(adIdx + Number(b.dataset.d)); break;
            case 'ad-ponto': irParaAd(Number(b.dataset.i)); break;
            case 'midia': prodAtual.idx = Number(b.dataset.i); desenharProduto(); break;
            case 'qtd': { const p = prodAtual.p, max = Math.min(p.estoque == null ? 20 : p.estoque, 20); prodAtual.qtd = Math.max(1, Math.min(max, prodAtual.qtd + Number(b.dataset.d))); desenharProduto(); break; }
            case 'pedir':
                if (!ctx.exigirLocalizacao()) break;
                prodAtual.enviando = true; desenharProduto();
                ctx.emitir('bazar_pedir', { produto_id: prodAtual.p.id, quantidade: prodAtual.qtd, nota: prodAtual.nota });
                break;
            case 'denunciar': ctx.denunciar(b.dataset.t, Number(id), b.dataset.nome); break;
            case 'ver-pedido': abrirPedido(id); break;
            case 'moderar': ctx.confirmar(b.dataset.acao === 'remover' ? 'Remover?' : 'Restaurar?', b.dataset.acao === 'remover' ? 'Isso derruba o item e dispensa as denúncias.' : 'O item volta a aparecer e as denúncias são dispensadas.',
                () => ctx.emitir('bazar_moderar', { tipo: b.dataset.t, alvo_id: Number(id), acao: b.dataset.acao })); break;
            case 'copiar': { const t = modalDe('pedido').querySelector('#bz-cc'); if (t) { navigator.clipboard.writeText(t.value).then(() => ctx.toast('Código Pix copiado! Cole no app do banco.', 'success')).catch(() => { t.select(); ctx.toast('Copie com Ctrl+C.', 'info'); }); } break; }
            case 'agir': {
                const rodar = () => ctx.emitir('bazar_agir', { pedido_id: Number(id), acao: b.dataset.acao });
                if (b.dataset.conf) ctx.confirmar('Confirmar', b.dataset.conf, rodar); else rodar();
                break;
            }
            case 'enviar-msg': {
                const i = modalDe('pedido').querySelector('#bz-msg-in'), t = (i.value || '').trim();
                if (!t) break;
                ctx.emitir('bazar_mensagem', { pedido_id: Number(id), texto: t });
                i.value = '';
                break;
            }
            case 'estrela': ed_aval.nota = Number(b.dataset.n); desenharPedido(modalDe('pedido').dataset.pedido); break;
            case 'avaliar': ctx.emitir('bazar_avaliar', { pedido_id: Number(id), nota: ed_aval.nota, texto: ed_aval.texto }); break;
            // painel
            case 'painel-ir': if (vista !== 'painel') abrirPainel(id); else irSecao(id); break;
            case 'ver-minha': if (minha) abrirLoja(minha.id); break;
            case 'alternar-aberta': if (minha && ctx.exigirLocalizacao()) ctx.emitir('bazar_salvar_loja', { ...rascunhoLoja(), aberta: !minha.aberta }); break;
            case 'ed-cor': ed.loja.cor = id; desenharPainel(); break;
            case 'ed-toldo': ed.loja.toldo = id; desenharPainel(); break;
            case 'ed-porte': ed.loja.porte = id; desenharPainel(); break;
            case 'ed-subir': escolher('image/*', (f) => subir(f, (url) => { ed.loja[id] = url; })); break;
            case 'ed-tirar': ed.loja[id] = ''; desenharPainel(); break;
            case 'ed-salvar-loja':
                if (!ctx.exigirLocalizacao()) break;
                ed.salvando = true; desenharPainel(); ctx.emitir('bazar_salvar_loja', ed.loja); break;
            case 'pd-novo': ed.prod = rascunhoProduto(); desenharPainel(); break;
            case 'pd-editar': ed.prod = rascunhoProduto(minha.produtos.find((p) => p.id === Number(id))); desenharPainel(); break;
            case 'pd-voltar': ed.prod = null; desenharPainel(); break;
            case 'pd-subir-img': escolher('image/*', (f) => subir(f, (url) => { ed.prod.imagens.push(url); })); break;
            case 'pd-tirar-img': ed.prod.imagens.splice(Number(b.dataset.i), 1); desenharPainel(); break;
            case 'pd-subir-video': escolher('video/*', (f) => subir(f, (url) => { ed.prod.video_url = url; })); break;
            case 'pd-tirar-video': ed.prod.video_url = ''; desenharPainel(); break;
            case 'pd-add-combo': ed.prod.combo_itens.push(''); desenharPainel(); break;
            case 'pd-tirar-combo': ed.prod.combo_itens.splice(Number(b.dataset.i), 1); desenharPainel(); break;
            case 'pd-salvar': {
                if (!ctx.exigirLocalizacao()) break;
                const pay = payloadProduto(ed.prod);
                if (pay.preco_cent == null) { ctx.toast('Preencha o preço (ex.: 45,90).', 'warning'); break; }
                if (ed.prod.estoque !== '' && !/^\d+$/.test(ed.prod.estoque)) { ctx.toast('Estoque: só números inteiros (ou deixe vazio pra sem limite).', 'warning'); break; }
                if (ed.prod.combo && ed.prod.preco_avulso && lerReais(ed.prod.preco_avulso) == null) { ctx.toast('Preço avulso inválido (ex.: 80,00).', 'warning'); break; }
                ed.salvando = true; desenharPainel(); ctx.emitir('bazar_salvar_produto', pay); break;
            }
            case 'pd-pausar': { const p = minha.produtos.find((x) => x.id === Number(id)); if (p) ctx.emitir('bazar_salvar_produto', { ...payloadProduto(rascunhoProduto(p)), ativo: !p.ativo }); break; }
            case 'pd-apagar': ctx.confirmar('Apagar produto?', 'Se ele já teve pedido, só fica desativado (o histórico depende dele).', () => ctx.emitir('bazar_apagar_produto', { id: Number(id) })); break;
        }
    }

    function digitou(e, tipo) {
        const t = e.target;
        if (tipo === 'produto' && t.dataset.campo === 'nota') { prodAtual.nota = t.value; return; }
        if (tipo === 'pedido' && t.dataset.campo === 'aval-texto') { ed_aval.texto = t.value; return; }
        if (tipo !== 'raiz') return;
        if (t.id === 'bz-busca') {
            if (e.type !== 'input') return;
            busca = t.value.trim();
            clearTimeout(buscaTimer);
            buscaTimer = setTimeout(() => pedirFeed(true), 350);
            return;
        }
        if (t.id === 'bz-tipo') { tipoFiltro = t.value; pedirFeed(true); return; }
        if (!ed || vista !== 'painel') return;
        const k = t.dataset.campo, alvo = secao === 'produtos' ? ed.prod : ed.loja;
        if (t.classList.contains('bz-in-combo')) { ed.prod.combo_itens[Number(t.dataset.combo)] = t.value; return; }
        if (!k || !alvo) return;
        alvo[k] = t.type === 'checkbox' ? t.checked : t.value;
        const cont = vistaEl.painel.querySelector(`[data-cont="${k}"]`);
        if (cont) cont.textContent = `${String(t.value).length}/${t.maxLength}`;
        if (t.type === 'checkbox' && secao === 'produtos') {
            if (k === 'combo' && ed.prod.combo && !ed.prod.combo_itens.length) ed.prod.combo_itens = [''];
            if (e.type === 'change' && k === 'combo') desenharPainel();
            return;
        }
        if (secao === 'dados' || secao === 'visual') {
            const p = vistaEl.painel.querySelector('#bz-previa');
            if (p) p.innerHTML = htmlLoja(previaLoja(), true);
        }
    }

    // ---------------------------------------------------------------------
    // CHIP "MINHA LOJINHA" (ao lado das moedas, no cabeçalho do Mercado Elite)
    // ---------------------------------------------------------------------
    function desenharChip() {
        const chip = document.getElementById('bz-meu-chip');
        if (!chip) return;
        chip.innerHTML = `${minha ? logoHtml(minha) : '<span class="bz-logo ini"><i class="fa-solid fa-store"></i></span>'}<span class="bz-chip-txt"><b>Minha lojinha</b><small>${minha ? esc(minha.nome) : (minhaLojaId ? 'abrir painel' : 'abra a sua')}</small></span>${pend ? `<span class="bz-contagem">${pend}</span>` : ''}`;
        chip.setAttribute('style', minha ? estiloLoja(minha) : '');
    }

    // ---------------------------------------------------------------------
    // API PÚBLICA (chamada pelo chat.html)
    // ---------------------------------------------------------------------
    function iniciar(opcoes) {
        ctx = opcoes;
        raiz = document.getElementById('bazar');
        if (!raiz) return;
        esqueleto();
        desenharAds();
        desenharFeed();
        raiz.addEventListener('click', (e) => clique(e, 'raiz'));
        raiz.addEventListener('input', (e) => digitou(e, 'raiz'));
        raiz.addEventListener('change', (e) => digitou(e, 'raiz'));
        const chip = document.getElementById('bz-meu-chip');
        if (chip) chip.addEventListener('click', () => { ctx.irParaBazar(); abrirPainel('inicio'); });
        desenharChip();
    }

    function abrir() {
        if (!ctx) return;
        if (!feed.carregado || desatualizada || Date.now() - carregadoEm > 20000) pedirFeed(true);
        if (vista === 'feed') ligarAds();
    }

    function indexar(itens) {
        itens.forEach((i) => { if (i.t === 'quad') i.produtos.forEach((p) => produtos.set(p.id, p)); else (i.loja.produtos || []).forEach((p) => produtos.set(p.id, { ...p, loja_nome: i.loja.nome, loja_cor: i.loja.cor })); });
    }

    function vitrine(d) {
        cat = d.catalogos; eAdmin = !!d.eh_admin; minhaLojaId = d.minha_loja_id; pend = d.pendencias || 0;
        props = d.propagandas || []; dest = d.destaques || [];
        if (d.feed.tag === tagDoFeed()) {          // resposta de um filtro/seed que já não vale: não troca o feed (a mais nova está a caminho)
            feed = { itens: d.feed.itens, pagina: 0, temMais: d.feed.tem_mais, carregando: false, carregado: true };
            carregadoEm = Date.now(); desatualizada = false;
            indexar(d.feed.itens);
            desenharFeed(); mostrarNovidade();
        }
        desenharAds(); desenharDestaques(); desenharFiltros(); desenharChip();
        if (ctx.aoPendencias) ctx.aoPendencias(pend);
        if (vista === 'painel') desenharPainel();
    }

    function feedMais(d) {
        if (d.tag !== tagDoFeed()) return;
        feed.itens = feed.itens.concat(d.itens);
        feed.pagina = d.pagina; feed.temMais = d.tem_mais; feed.carregando = false;
        indexar(d.itens);
        desenharFeed();
    }

    function loja(l) {
        lojaAtual = l;
        if (vista === 'loja') desenharLoja();
        if (prodAtual && prodAtual.p.loja_id === l.id) {
            const novo = l.produtos.find((p) => p.id === prodAtual.p.id);
            if (novo) prodAtual.p = { ...prodAtual.p, ...novo };
            desenharProduto();
        }
    }

    function minhaLoja(d) {
        minha = d.loja || null;
        minhaLojaId = minha ? minha.id : null;
        if (ed) {
            ed.salvando = false;
            if (d.salvo === 'loja') {
                ctx.toast('Loja salva!', 'success');
                ed.loja = rascunhoLoja();
                if (secao === 'dados' && minha && !minha.produtos.length) secao = 'produtos';
            } else if (d.salvo === 'produto') { ctx.toast('Produto salvo!', 'success'); ed.prod = null; }
            else if (d.salvo === 'apagado') ctx.toast('Produto removido.', 'info');
            else if (!ed.loja.nome && minha) ed.loja = rascunhoLoja();
            if (vista === 'painel') desenharPainel();
        }
        desenharChip();
    }

    function pedido(p) {
        pedCache.set(p.id, p);
        const lista = p.papel === 'vendedor' ? pedidos.vendendo : pedidos.comprando;
        const i = lista.findIndex((x) => x.id === p.id);
        const resumo = { ...p }; delete resumo.mensagens; delete resumo.pix; delete resumo.entrega;
        if (i >= 0) lista[i] = resumo; else lista.unshift(resumo);
        const m = modalDe('pedido');
        if (m) {
            m.dataset.pedido = p.id;
            desenharPedido(p.id);
            // abriu pela notificação sem saber o papel: se eu sou o vendedor, a seção certa é "Pedidos recebidos"
            if (vista === 'painel' && secao === 'compras' && p.papel === 'vendedor') secao = 'pedidos';
        }
        if (vista === 'painel' && ['inicio', 'pedidos', 'compras'].includes(secao)) desenharPainel();
    }

    function pedidoAberto(d) {
        fecharModal('produto');
        ctx.toast('Pedido enviado! Acompanhe em "Minha lojinha > Minhas compras".', 'success');
        abrirPedido(d.pedido_id);
    }

    function listaPedidos(d) {
        pedidos = { comprando: d.comprando, vendendo: d.vendendo, carregado: true };
        d.comprando.concat(d.vendendo).forEach((p) => { if (!pedCache.has(p.id)) pedCache.set(p.id, p); });
        pend = d.precisam_de_voce; desenharChip();
        if (ctx.aoPendencias) ctx.aoPendencias(pend);
        if (vista === 'painel') desenharPainel();
    }

    function pendencias(n) { pend = n; desenharChip(); if (ctx.aoPendencias) ctx.aoPendencias(n); if (vista === 'painel') desenharPainel(); }

    function mudou() {
        desatualizada = true;
        if (vista === 'feed' && raiz && raiz.offsetParent !== null) mostrarNovidade();
        if (vista === 'loja' && lojaAtual) ctx.emitir('bazar_abrir_loja', { loja_id: lojaAtual.id });
        if (vista === 'painel' && minha) ctx.emitir('bazar_minha_loja');
    }

    function erro(d) {
        ctx.toast(d.msg, 'error');
        if (prodAtual && prodAtual.enviando) { prodAtual.enviando = false; desenharProduto(); }
        if (ed && ed.salvando) { ed.salvando = false; if (vista === 'painel') desenharPainel(); }
        if (d.ref === 'loja' && vista === 'loja' && !lojaAtual) irPara('feed');
    }

    function moderacaoFila(d) { moderacao = d.fila; if (vista === 'painel' && secao === 'moderacao') desenharPainel(); }

    function abrirLojaDe(id) { if (id) abrirLoja(Number(id)); }
    function abrirPedidos(ref) {
        abrirPainel('compras');
        if (ref) abrirPedido(ref);
    }

    return { iniciar, abrir, vitrine, feedMais, loja, minhaLoja, pedido, pedidoAberto, listaPedidos, pendencias, mudou, erro, moderacaoFila, abrirLojaDe, abrirPedidos, abrirPainel };
})();
