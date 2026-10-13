/* Painel do admin (/admin). Fala com /admin/api/* (JSON). Nada aqui é de confiança: o servidor confere admin e valida tudo. */
(function () {
    'use strict';
    const $ = (s, r) => (r || document).querySelector(s);
    const main = $('#es-main');
    const E = { cat: null, tempo: [], tid: null, recs: new Map(), mudancas: new Map(), filtro: 'todos', jogadores: [] };

    const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    function toast(msg, tipo) {
        const el = document.createElement('div');
        el.className = 'es-toast ' + (tipo || '');
        el.textContent = msg;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 3800);
    }

    async function api(caminho, metodo, corpo) {
        const opt = { method: metodo || 'GET', headers: { 'X-Requested-With': 'fetch' } };
        if (corpo !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(corpo); }
        let r;
        try { r = await fetch('/admin/api' + caminho, opt); } catch (e) { toast('Sem conexão com o servidor.', 'erro'); throw e; }
        const d = await r.json().catch(() => ({}));
        if (!r.ok) { toast(d.erro || ('Erro ' + r.status), 'erro'); throw new Error(d.erro || r.status); }
        return d;
    }

    function dialogo(titulo, corpoHtml, acoes) {
        const fundo = document.createElement('div');
        fundo.className = 'es-modal-fundo';
        fundo.innerHTML = `<div class="es-modal" role="dialog" aria-modal="true"><h3>${esc(titulo)}</h3><div class="es-corpo">${corpoHtml}</div><div class="es-modal-acoes"></div></div>`;
        const barra = $('.es-modal-acoes', fundo);
        const fechar = () => { fundo.remove(); document.removeEventListener('keydown', esc_); };
        const esc_ = (e) => { if (e.key === 'Escape') fechar(); };
        document.addEventListener('keydown', esc_);
        fundo.addEventListener('mousedown', (e) => { if (e.target === fundo) fechar(); });
        (acoes || []).forEach((a) => {
            const b = document.createElement('button');
            b.className = 'es-btn ' + (a.classe || '');
            b.textContent = a.texto;
            // Enquanto a ação roda os botões ficam travados: apagar/aplicar modelo levam alguns segundos e um 2º clique rodava a operação DUAS vezes.
            b.addEventListener('click', async () => {
                if (b.disabled) return;
                if (a.fn) {
                    const botoes = [...barra.querySelectorAll('button')], rotulo = b.textContent;
                    botoes.forEach((x) => { x.disabled = true; });
                    b.textContent = 'Aguarde...';
                    let r;
                    try { r = await a.fn(fundo); } catch (e) { r = false; }
                    if (r === false) { botoes.forEach((x) => { x.disabled = false; }); b.textContent = rotulo; return; }
                }
                fechar();
            });
            barra.appendChild(b);
        });
        document.body.appendChild(fundo);
        return { fundo, fechar };
    }

    // Roda uma ação demorada num botão: trava, mostra "Aguarde..." e destrava no fim (evita clique duplo rodar duas vezes).
    async function trabalhando(btn, fn) {
        if (btn.disabled) return;
        const rotulo = btn.textContent;
        btn.disabled = true; btn.textContent = 'Aguarde...';
        try { return await fn(); } finally { btn.disabled = false; btn.textContent = rotulo; }
    }

    function confirmar(texto, aoConfirmar, rotulo) {
        dialogo('Confirmar', `<p>${esc(texto)}</p>`, [{ texto: 'Cancelar' }, { texto: rotulo || 'Confirmar', classe: 'perigo', fn: aoConfirmar }]);
    }

    async function catalogo() { if (!E.cat) E.cat = await api('/catalogo'); return E.cat; }

    // ------------------------------------------------------------
    // navegação
    // ------------------------------------------------------------
    const VISTAS = { geral: vGeral, passe: vPasse, titulos: vTitulos, missoes: vMissoes, admins: vAdmins };
    function ir(v) {
        document.querySelectorAll('.es-item[data-v]').forEach((b) => b.classList.toggle('ativo', b.dataset.v === v));
        location.hash = v;
        main.innerHTML = '<div class="es-vazio">Carregando...</div>';
        Promise.resolve(VISTAS[v] && VISTAS[v]()).catch((e) => { main.innerHTML = `<div class="es-vazio">Não foi possível carregar: ${esc(e.message)}</div>`; });
    }
    document.querySelectorAll('.es-item[data-v]').forEach((b) => b.addEventListener('click', () => {
        if (E.mudancas.size && !confirm('Você tem alterações do passe não salvas. Sair mesmo assim?')) return;
        E.mudancas.clear();
        ir(b.dataset.v);
    }));

    // ------------------------------------------------------------
    // visão geral: números, gráficos por dia, nível das pessoas e a lista de pessoas
    // ------------------------------------------------------------
    const fmt = (n) => Number(n || 0).toLocaleString('pt-BR');
    const diaCurto = (d) => d.slice(8, 10) + '/' + d.slice(5, 7);
    const diaLongo = (d) => new Date(d + 'T12:00:00').toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit' });
    const fotoOk = (u) => /^(https:\/\/|\/)/.test(u || '');          // foto de perfil: só https ou caminho do site

    function especGraficos(g) {
        const dias = g.dias;
        return {
            contas: {
                tipo: 'colunas', titulo: 'Novas contas por dia', unidade: 'contas',
                sub: `Últimos ${dias} dias · ${fmt(g.novas_periodo)} no período` + (g.contas_sem_data ? ` · ${fmt(g.contas_sem_data)} contas antigas não têm data de entrada e ficam de fora` : ''),
                vazio: 'Nenhuma conta nova nesse período.',
                serie: g.contas_por_dia.map((d) => ({ chave: d.dia, rotulo: diaCurto(d.dia), dica: diaLongo(d.dia), valor: d.n })),
                tabela: { cabecalho: ['Dia', 'Novas contas'], linhas: g.contas_por_dia.map((d) => [diaLongo(d.dia), d.n]) },
            },
            mensagens: {
                tipo: 'linha', titulo: 'Mensagens por dia', unidade: 'mensagens',
                sub: `Últimos ${dias} dias · canais e mensagens diretas somados`,
                serie: g.mensagens_por_dia.map((d) => ({ chave: d.dia, rotulo: diaCurto(d.dia), dica: diaLongo(d.dia), valor: d.n, detalhe: [`Canais: ${fmt(d.canais)}`, `Diretas: ${fmt(d.dms)}`] })),
                tabela: { cabecalho: ['Dia', 'Mensagens', 'Canais', 'Diretas'], linhas: g.mensagens_por_dia.map((d) => [diaLongo(d.dia), d.n, d.canais, d.dms]) },
            },
            niveis: {
                tipo: 'barrasH', titulo: 'Pessoas por nível de conta', unidade: 'pessoas',
                sub: 'O nível da conta cresce com o XP de tudo que a pessoa faz no app',
                serie: g.niveis.map((f) => ({ rotulo: 'Nível ' + f.faixa, dica: 'nível ' + f.faixa, valor: f.n })),
                tabela: { cabecalho: ['Nível', 'Pessoas'], linhas: g.niveis.map((f) => ['Nível ' + f.faixa, f.n]) },
            },
        };
    }

    function pintarTiles(g) {
        const itens = [
            ['Pessoas cadastradas', fmt(g.pessoas), g.contas_sem_data ? `${fmt(g.contas_sem_data)} sem data de entrada` : ''],
            ['Online agora', fmt(g.online_agora), 'conectadas neste momento'],
            ['Novas em 7 dias', fmt(g.novas_7d), ''],
            ['Mensagens hoje', fmt(g.mensagens_hoje), 'canais e diretas'],
            ['Servidores', fmt(g.servidores), `${fmt(g.servidores_publicos)} no Explorar`],
            ['Lojas no Bazar', fmt(g.lojas), ''],
            ['Temporada ativa', g.temporada ? g.temporada.nome : 'nenhuma', g.temporada ? `${fmt(g.jogando_temporada)} jogando` : ''],
            ['Administradores', fmt(g.admins.length), g.admins.map((a) => '@' + a.username).join(', ')],
        ];
        $('#g-tiles').innerHTML = itens.map(([rot, val, sub]) => `<div class="es-num"><span>${esc(rot)}</span><b>${esc(val)}</b>${sub ? `<small>${esc(sub)}</small>` : ''}</div>`).join('');
    }

    function pintarTemporada(g) {
        const c = $('#g-temp');
        if (!g.temporada) {
            c.innerHTML = '<div class="es-g-topo"><div><h2>Temporada ativa</h2><small>Nenhuma temporada ativa agora.</small></div></div><p class="es-temp-sub">Crie ou ative uma em <a href="#passe">Passe de Batalha</a>.</p>';
            return;
        }
        const pct = g.pessoas ? Math.min(100, Math.round((g.jogando_temporada / g.pessoas) * 100)) : 0;
        c.innerHTML = `<div class="es-g-topo"><div><h2>Temporada ativa</h2><small>${esc(g.temporada.nome)}</small></div></div>
            <div class="es-temp-num">${fmt(g.jogando_temporada)}<span class="es-temp-sub"> de ${fmt(g.pessoas)} pessoas já jogam</span></div>
            <div class="es-medidor" role="img" aria-label="${pct}% das pessoas já ganharam XP na temporada"><i style="width:${pct}%"></i></div>
            <div class="es-temp-sub">${pct}% das contas · ${fmt(g.premium_temporada)} com a trilha Premium liberada</div>`;
    }

    async function vGeral() {
        E.dias = E.dias || 30; E.q = ''; E.pag = 1; E.ordem = 'recentes';
        const g = await api('/geral?dias=' + E.dias);
        main.innerHTML = `<h1>Visão geral</h1>
            <p class="es-sub">Como o app está agora: quantas pessoas, quem entrou, quanto se conversa e quem são elas. O resto das áreas (cosméticos, Armazém, Bazar, denúncias...) entra nas próximas etapas.</p>
            <div class="es-grade-3 es-tiles" id="g-tiles"></div>
            <div class="es-filtros"><span>Período dos gráficos</span>
                <div class="es-seg" id="g-dias" role="group" aria-label="Período dos gráficos">${[7, 30, 90].map((d) => `<button type="button" data-d="${d}" aria-pressed="${d === E.dias}">${d} dias</button>`).join('')}</div></div>
            <div class="es-graficos" id="g-viz">
                <section class="es-cartao" id="g-contas"></section><section class="es-cartao" id="g-msgs"></section>
                <section class="es-cartao" id="g-niveis"></section><section class="es-cartao" id="g-temp"></section>
            </div>
            <section class="es-cartao" id="g-pessoas">
                <h2>Pessoas</h2>
                <p class="es-dado-pessoal"><i class="fa-solid fa-user-shield"></i> Dados pessoais (nome, @ e e-mail): só você, como administrador, vê esta lista. Use só pra gerir o app.</p>
                <div class="es-pessoas-barra">
                    <div class="es-campo largo"><label for="gp-busca">Buscar</label><input id="gp-busca" type="search" maxlength="80" placeholder="Nome, @conta ou e-mail" autocomplete="off"></div>
                    <div class="es-campo"><label for="gp-ordem">Ordem</label><select id="gp-ordem"><option value="recentes">Mais recentes</option><option value="nome">Nome (A a Z)</option><option value="nivel">Maior nível</option></select></div>
                </div>
                <div class="es-rolagem-x" id="gp-tabela"><div class="es-vazio">Carregando...</div></div>
                <div class="es-paginas" id="gp-paginas"></div>
            </section>`;
        pintarTiles(g);
        pintarTemporada(g);
        const spec = especGraficos(g);
        E.graf = { contas: Graficos.montar($('#g-contas'), spec.contas), mensagens: Graficos.montar($('#g-msgs'), spec.mensagens), niveis: Graficos.montar($('#g-niveis'), spec.niveis) };

        $('#g-dias').addEventListener('click', async (ev) => {
            const b = ev.target.closest('button[data-d]');
            if (!b || +b.dataset.d === E.dias) return;
            E.dias = +b.dataset.d;
            $('#g-dias').querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(+x.dataset.d === E.dias)));
            $('#g-viz').classList.add('carregando');          // os gráficos seguem na tela, só esmaecem enquanto os números novos chegam
            try {
                const novo = await api('/geral?dias=' + E.dias), sp = especGraficos(novo);
                Graficos.atualizar(E.graf.contas, sp.contas); Graficos.atualizar(E.graf.mensagens, sp.mensagens);
                E.graf.contas.closest('section').querySelector('small').textContent = sp.contas.sub;
                E.graf.mensagens.closest('section').querySelector('small').textContent = sp.mensagens.sub;
            } catch (e) { /* toast já mostrado */ } finally { $('#g-viz').classList.remove('carregando'); }
        });

        let timer = null;
        $('#gp-busca').addEventListener('input', (ev) => { clearTimeout(timer); timer = setTimeout(() => { E.q = ev.target.value.trim(); E.pag = 1; carregarPessoas(); }, 300); });
        $('#gp-ordem').addEventListener('change', (ev) => { E.ordem = ev.target.value; E.pag = 1; carregarPessoas(); });
        $('#g-pessoas').addEventListener('click', (ev) => {
            const cp = ev.target.closest('[data-copiar]');
            if (cp) { navigator.clipboard.writeText(cp.dataset.copiar).then(() => toast('E-mail copiado.', 'ok'), () => toast('Não consegui copiar.', 'erro')); return; }
            const pg = ev.target.closest('[data-pag]');
            if (pg && !pg.disabled) { E.pag = +pg.dataset.pag; carregarPessoas(); }
        });
        await carregarPessoas();
    }

    async function carregarPessoas() {
        const alvo = $('#gp-tabela');
        if (!alvo) return;
        alvo.style.opacity = '.55';
        let d;
        try { d = await api(`/pessoas/lista?q=${encodeURIComponent(E.q)}&pagina=${E.pag}&ordem=${encodeURIComponent(E.ordem)}`); } catch (e) { alvo.style.opacity = ''; return; }
        if (!$('#gp-tabela')) return;                       // trocou de tela enquanto carregava
        E.pag = d.pagina;
        const linhas = d.pessoas.map((p) => {
            const foto = fotoOk(p.avatar) ? `<img src="${esc(p.avatar)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : esc((p.nome || '?').trim().charAt(0).toUpperCase());
            return `<tr><td><div class="es-pessoa"><span class="es-av">${foto}</span><b>${esc(p.nome)}</b></div></td>
                <td>${p.username ? '@' + esc(p.username) : '<span class="es-g-vazio" style="padding:0">sem @</span>'}</td>
                <td><span class="es-email">${esc(p.email)}${p.email ? ` <button type="button" class="es-copiar" data-copiar="${esc(p.email)}" title="Copiar e-mail" aria-label="Copiar o e-mail de ${esc(p.nome)}"><i class="fa-regular fa-copy"></i></button>` : ''}</span></td>
                <td>${p.criado_em ? esc(p.criado_em) : '<span class="es-sub" style="margin:0">conta antiga</span>'}</td>
                <td class="num">${fmt(p.nivel)}</td>
                <td><span class="es-status ${p.online ? 'on' : ''}"><i></i>${p.online ? 'Online' : 'Offline'}</span></td></tr>`;
        }).join('');
        alvo.style.opacity = '';
        alvo.innerHTML = d.pessoas.length
            ? `<table class="es-tabela"><thead><tr><th>Pessoa</th><th>@ da conta</th><th>E-mail</th><th>Entrou em</th><th class="num">Nível</th><th>Agora</th></tr></thead><tbody>${linhas}</tbody></table>`
            : `<div class="es-vazio">${E.q ? 'Ninguém encontrado com essa busca.' : 'Nenhuma pessoa ainda.'}</div>`;
        $('#gp-paginas').innerHTML = `<span>${fmt(d.total)} ${d.total === 1 ? 'pessoa' : 'pessoas'}${E.q ? ' na busca' : ''} · página ${d.pagina} de ${d.paginas}</span>
            <div><button type="button" class="es-btn mini" data-pag="${d.pagina - 1}" ${d.pagina <= 1 ? 'disabled' : ''}>Anterior</button><button type="button" class="es-btn mini" data-pag="${d.pagina + 1}" ${d.pagina >= d.paginas ? 'disabled' : ''}>Próxima</button></div>`;
    }

    // ------------------------------------------------------------
    // PASSE
    // ------------------------------------------------------------
    const rotuloTipo = { moeda: 'Moedas', item: 'Item', titulo: 'Título', tema: 'Tema do app' };
    const iconeTipo = { moeda: 'fa-coins', item: 'fa-gem', titulo: 'fa-signature', tema: 'fa-palette' };

    function descreverRec(r) {
        if (!r || !r.tipo) return { ico: '', nome: 'vazio', sub: '' };
        if (r.tipo === 'moeda') return { ico: 'moeda', nome: `${r.quantidade} moedas`, sub: '' };
        const c = E.cat;
        if (r.tipo === 'item') { const i = c.itens.find((x) => x.id === r.valor); return { ico: 'item', nome: i ? i.nome : r.valor, sub: i ? `${i.rotulo} · ${i.raridade}` : 'item não encontrado' }; }
        if (r.tipo === 'titulo') { const t = c.titulos.find((x) => x.id === r.valor); return { ico: 'titulo', nome: t ? t.texto : r.valor, sub: t ? `título · ${t.raridade}` : 'título não encontrado' }; }
        if (r.tipo === 'tema') { const t = c.temas_app.find((x) => x.id === r.valor); return { ico: 'tema', nome: t ? t.nome : r.valor, sub: 'tema do app' }; }
        return { ico: '', nome: '?', sub: '' };
    }

    const chave = (n, t) => n + '|' + t;
    const recAtual = (n, t) => (E.mudancas.has(chave(n, t)) ? E.mudancas.get(chave(n, t)) : E.recs.get(chave(n, t))) || null;

    function temporadaAtual() { return E.tempo.find((t) => t.id === E.tid) || null; }

    async function vPasse() {
        await catalogo();
        const d = await api('/passe/temporadas');
        E.tempo = d.temporadas;
        if (!E.tempo.find((t) => t.id === E.tid)) E.tid = E.tempo.length ? (E.tempo.find((t) => t.ativa) || E.tempo[0]).id : null;
        if (E.tid) await carregarRecs();
        desenharPasse();
    }

    async function carregarRecs() {
        const d = await api(`/passe/temporada/${E.tid}/recompensas`);
        E.recs = new Map(d.recompensas.map((r) => [chave(r.nivel, r.trilha), r]));
        E.mudancas.clear();
    }

    function desenharPasse() {
        const t = temporadaAtual();
        const opcoes = E.tempo.map((x) => `<option value="${x.id}" ${x.id === E.tid ? 'selected' : ''}>${esc(x.nome)}${x.ativa ? ' (ativa)' : ''}</option>`).join('');
        let html = `<h1>Passe de Batalha</h1>
            <p class="es-sub">Defina a temporada (nome, tema, datas, quantos níveis) e, nível por nível, o que a trilha <b>Grátis</b> e a <b>Premium</b> entregam. Sem data de início/fim a temporada fica aberta até você encerrar. Só uma temporada fica ativa por vez.</p>
            <div class="es-cartao"><div class="es-linha">
                <div class="es-campo largo"><label>Temporada</label><select id="p-sel">${opcoes || '<option value="">(nenhuma ainda)</option>'}</select></div>
                <button class="es-btn" id="p-nova">Nova temporada</button>
                <button class="es-btn" id="p-modelo-criar" title="Cria a Temporada 1: Deuses já com as 100 recompensas">Criar modelo "Deuses"</button>
            </div></div>`;
        if (t) html += formTemporada(t) + gradeRecompensas(t) + `<div id="p-jogadores"></div>`;
        main.innerHTML = html;
        ligarPasse(t);
        if (t) carregarJogadores();
    }

    function formTemporada(t) {
        const temas = E.cat.temas_passe.map((x) => `<option value="${x.id}" ${x.id === t.tema ? 'selected' : ''}>${esc(x.nome)}</option>`).join('');
        return `<div class="es-cartao" id="p-form"><h2>Temporada ${t.ativa ? '<span class="es-selo ativa">ativa</span>' : '<span class="es-selo">inativa</span>'}</h2>
            <div class="es-linha">
                <div class="es-campo largo"><label>Nome</label><input id="t-nome" maxlength="60" value="${esc(t.nome)}"></div>
                <div class="es-campo largo"><label>Subtítulo</label><input id="t-sub" maxlength="120" value="${esc(t.subtitulo)}"></div>
                <div class="es-campo"><label>Tema visual</label><select id="t-tema">${temas}</select></div>
            </div>
            <div class="es-linha" style="margin-top:12px">
                <div class="es-campo"><label>Níveis</label><input id="t-niveis" type="number" min="1" max="200" value="${t.niveis}"></div>
                <div class="es-campo"><label>XP por nível</label><input id="t-xp" type="number" min="50" max="100000" value="${t.xp_por_nivel}"><small>Chegar ao último = ${(t.niveis * t.xp_por_nivel).toLocaleString('pt-BR')} XP</small></div>
                <div class="es-campo"><label>Início (opcional)</label><input id="t-ini" type="datetime-local" value="${esc(t.inicio)}"></div>
                <div class="es-campo"><label>Fim (opcional)</label><input id="t-fim" type="datetime-local" value="${esc(t.fim)}"></div>
            </div>
            <div class="es-linha" style="margin-top:12px">
                <div class="es-campo largo"><label>Capítulos ("cantos"), um nome por linha</label><textarea id="t-caps" rows="5" placeholder="Ítaca&#10;O Mar de Vinho&#10;...">${esc((t.capitulos || []).join('\n'))}</textarea><small>Opcional. Cada capítulo aparece como um bloco na trilha, com o nome em cima.</small></div>
                <div class="es-campo"><label>Níveis por capítulo</label><input id="t-capn" type="number" min="3" max="50" value="${t.capitulo_niveis || 10}"></div>
            </div>
            <div class="es-linha" style="margin-top:12px">
                <div class="es-campo"><label>Catch-up: nos últimos (dias)</label><input id="t-cdias" type="number" min="0" max="90" value="${t.catchup_dias}"></div>
                <div class="es-campo"><label>...o XP rende a mais (%)</label><input id="t-cpct" type="number" min="0" max="300" value="${t.catchup_pct}"><small>0 desliga. Ajuda quem entrou tarde.</small></div>
            </div>
            <div class="es-linha" style="margin-top:16px">
                <button class="es-btn primario" id="t-salvar">Salvar temporada</button>
                <button class="es-btn ${t.ativa ? '' : 'ok'}" id="t-ativar">${t.ativa ? 'Encerrar temporada' : 'Ativar temporada'}</button>
                <button class="es-btn" id="t-modelo">Aplicar modelo "Deuses"</button>
                <button class="es-btn perigo" id="t-apagar">Apagar</button>
            </div></div>`;
    }

    function ehMarco(n) { return n % 10 === 0 || n % 5 === 0; }

    function gradeRecompensas(t) {
        let linhas = '';
        for (let n = 1; n <= t.niveis; n++) {
            const g = recAtual(n, 'gratis'), p = recAtual(n, 'premium');
            const mostrar = E.filtro === 'todos' || (E.filtro === 'marcos' && (ehMarco(n) || (g && g.tipo !== 'moeda') || (p && p.tipo !== 'moeda'))) || (E.filtro === 'vazios' && (!g || !p));
            if (!mostrar) continue;
            linhas += `<div class="es-grade-linha ${ehMarco(n) ? 'marco' : ''}"><div class="es-grade-n">${n}</div>${celula(n, 'gratis', g)}${celula(n, 'premium', p)}</div>`;
        }
        const n = E.mudancas.size;
        return `<div class="es-barra-fixa"><div class="es-campo" style="flex:0 0 160px;min-width:0"><select id="g-filtro">
                    <option value="todos" ${E.filtro === 'todos' ? 'selected' : ''}>Todos os níveis</option>
                    <option value="marcos" ${E.filtro === 'marcos' ? 'selected' : ''}>Só marcos e prêmios</option>
                    <option value="vazios" ${E.filtro === 'vazios' ? 'selected' : ''}>Com slot vazio</option></select></div>
                <button class="es-btn" id="g-preencher">Preencher moedas...</button>
                <span style="flex:1"></span>
                <span class="es-selo ${n ? 'aviso' : ''}" id="g-cont">${n} alteraç${n === 1 ? 'ão' : 'ões'} não salva${n === 1 ? '' : 's'}</span>
                <button class="es-btn" id="g-descartar" ${n ? '' : 'disabled'}>Descartar</button>
                <button class="es-btn primario" id="g-salvar" ${n ? '' : 'disabled'}>Salvar recompensas</button></div>
            <div class="es-grade"><div class="es-grade-cab"><div>Nível</div><div>Trilha Grátis</div><div>Trilha Premium</div></div>${linhas || '<div class="es-vazio">Nada neste filtro.</div>'}</div>`;
    }

    function celula(n, trilha, r) {
        const d = descreverRec(r);
        const mudou = E.mudancas.has(chave(n, trilha));
        if (!r || !r.tipo) return `<button class="es-cel vazia ${mudou ? 'mudou' : ''}" data-n="${n}" data-t="${trilha}">vazio</button>`;
        return `<button class="es-cel ${mudou ? 'mudou' : ''}" data-n="${n}" data-t="${trilha}"><span class="es-cel-ico ${d.ico}"><i class="fa-solid ${iconeTipo[r.tipo]}"></i></span><span><b>${esc(d.nome)}</b>${d.sub ? `<span class="sub">${esc(d.sub)}</span>` : ''}</span></button>`;
    }

    function redesenharGrade() {
        const t = temporadaAtual();
        const barra = $('.es-barra-fixa');
        const grade = $('.es-grade');
        if (!t || !barra) return;
        const novo = document.createElement('div');
        novo.innerHTML = gradeRecompensas(t);
        barra.replaceWith(novo.querySelector('.es-barra-fixa'));
        grade.replaceWith(novo.querySelector('.es-grade'));
        ligarGrade();
    }

    function ligarGrade() {
        $('#g-filtro').addEventListener('change', (e) => { E.filtro = e.target.value; redesenharGrade(); });
        $('#g-preencher').addEventListener('click', dialogoPreencher);
        $('#g-descartar').addEventListener('click', () => { E.mudancas.clear(); redesenharGrade(); });
        $('#g-salvar').addEventListener('click', salvarRecompensas);
        document.querySelectorAll('.es-cel').forEach((b) => b.addEventListener('click', () => editarCelula(+b.dataset.n, b.dataset.t)));
    }

    async function salvarRecompensas() {
        const lista = [...E.mudancas.values()].map((r) => ({ nivel: r.nivel, trilha: r.trilha, tipo: r.tipo || '', valor: r.valor || '', quantidade: r.quantidade || 0 }));
        if (!lista.length) return;
        try {
            await api(`/passe/temporada/${E.tid}/recompensas`, 'POST', { lista });
            toast('Recompensas salvas.', 'ok');
            await carregarRecs();
            redesenharGrade();
        } catch (e) { /* o toast já mostrou o motivo; as alterações ficam pra corrigir */ }
    }

    function dialogoPreencher() {
        const t = temporadaAtual();
        dialogo('Preencher moedas em vários níveis', `
            <p style="color:var(--muda);margin-top:0">Preenche só os slots <b>vazios</b> (não mexe em prêmios que você já definiu). Níveis múltiplos de 5 pagam o dobro e de 10, o triplo.</p>
            <div class="es-linha"><div class="es-campo"><label>Trilha</label><select id="f-trilha"><option value="gratis">Grátis</option><option value="premium">Premium</option></select></div>
            <div class="es-campo"><label>Do nível</label><input id="f-de" type="number" min="1" max="${t.niveis}" value="1"></div>
            <div class="es-campo"><label>Até o nível</label><input id="f-ate" type="number" min="1" max="${t.niveis}" value="${t.niveis}"></div>
            <div class="es-campo"><label>Moedas base</label><input id="f-base" type="number" min="1" value="50"></div></div>`,
        [{ texto: 'Cancelar' }, {
            texto: 'Preencher', classe: 'primario', fn: (f) => {
                const trilha = $('#f-trilha', f).value, de = +$('#f-de', f).value, ate = +$('#f-ate', f).value, base = +$('#f-base', f).value;
                if (!(base >= 1) || !(de >= 1) || ate < de) { toast('Confira os números.', 'erro'); return false; }
                for (let n = de; n <= Math.min(ate, t.niveis); n++) {
                    const a = recAtual(n, trilha);
                    if (a && a.tipo) continue;
                    E.mudancas.set(chave(n, trilha), { nivel: n, trilha, tipo: 'moeda', valor: '', quantidade: base * (n % 10 === 0 ? 3 : n % 5 === 0 ? 2 : 1) });
                }
                redesenharGrade();
            },
        }]);
    }

    function editarCelula(n, trilha) {
        const atual = recAtual(n, trilha) || { tipo: '' };
        let tipo = atual.tipo || '', valor = atual.valor || '', qtd = atual.quantidade || 100;
        const d = dialogo(`Nível ${n} · trilha ${trilha === 'gratis' ? 'Grátis' : 'Premium'}`, `
            <div class="es-campo"><label>O que entrega</label><select id="e-tipo">
                <option value="">Nada (vazio)</option>
                ${Object.keys(rotuloTipo).map((k) => `<option value="${k}" ${k === tipo ? 'selected' : ''}>${rotuloTipo[k]}</option>`).join('')}</select></div>
            <div id="e-corpo"></div>`,
        [{ texto: 'Cancelar' }, {
            texto: 'Aplicar', classe: 'primario', fn: (f) => {
                tipo = $('#e-tipo', f).value;
                let rec;
                if (!tipo) rec = { nivel: n, trilha, tipo: '', valor: '', quantidade: 0 };
                else if (tipo === 'moeda') {
                    const q = +$('#e-qtd', f).value;
                    if (!(q >= 1 && q <= 100000)) { toast('Moedas: de 1 a 100.000.', 'erro'); return false; }
                    rec = { nivel: n, trilha, tipo, valor: '', quantidade: q };
                } else {
                    if (!valor) { toast('Escolha um da lista.', 'erro'); return false; }
                    rec = { nivel: n, trilha, tipo, valor, quantidade: 0 };
                }
                const original = E.recs.get(chave(n, trilha));
                const igual = (!original && !rec.tipo) || (original && original.tipo === rec.tipo && (original.valor || '') === (rec.valor || '') && (original.quantidade || 0) === (rec.quantidade || 0));
                if (igual) E.mudancas.delete(chave(n, trilha)); else E.mudancas.set(chave(n, trilha), rec);
                redesenharGrade();
            },
        }]);
        const corpo = $('#e-corpo', d.fundo);
        function pintar() {
            tipo = $('#e-tipo', d.fundo).value;
            if (tipo === 'moeda') corpo.innerHTML = `<div class="es-campo"><label>Quantidade de moedas</label><input id="e-qtd" type="number" min="1" max="100000" value="${qtd}"></div>`;
            else if (tipo === 'item' || tipo === 'titulo' || tipo === 'tema') {
                const fonte = tipo === 'item' ? E.cat.itens.map((i) => ({ id: i.id, nome: i.nome, sub: `${i.rotulo} · ${i.raridade}` }))
                    : tipo === 'titulo' ? E.cat.titulos.map((t) => ({ id: t.id, nome: t.texto, sub: t.raridade }))
                        : E.cat.temas_app.map((t) => ({ id: t.id, nome: t.nome, sub: 'tema' }));
                corpo.innerHTML = `<div class="es-campo"><label>Procurar</label><input id="e-busca" placeholder="digite pra filtrar" autocomplete="off"></div><div class="es-lista" id="e-lista"></div>
                    ${tipo === 'tema' && !fonte.length ? '<p class="es-sub">Nenhum tema de temporada cadastrado.</p>' : ''}`;
                const lista = $('#e-lista', corpo);
                const pintarLista = () => {
                    const q = $('#e-busca', corpo).value.toLowerCase();
                    const f = fonte.filter((x) => !q || x.nome.toLowerCase().includes(q) || x.id.toLowerCase().includes(q)).slice(0, 80);
                    lista.innerHTML = f.map((x) => `<button type="button" data-id="${esc(x.id)}" class="${x.id === valor ? 'sel' : ''}"><span>${esc(x.nome)}</span><small>${esc(x.sub)} · ${esc(x.id)}</small></button>`).join('') || '<div class="es-vazio">Nada encontrado.</div>';
                    lista.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => { valor = b.dataset.id; pintarLista(); }));
                };
                $('#e-busca', corpo).addEventListener('input', pintarLista);
                pintarLista();
            } else corpo.innerHTML = '';
        }
        $('#e-tipo', d.fundo).addEventListener('change', () => { valor = ''; pintar(); });
        pintar();
    }

    function ligarPasse(t) {
        $('#p-sel').addEventListener('change', async (e) => {
            if (E.mudancas.size && !confirm('Há alterações não salvas. Trocar de temporada descarta.')) { e.target.value = E.tid; return; }
            E.tid = +e.target.value || null;
            if (E.tid) await carregarRecs();
            desenharPasse();
        });
        $('#p-nova').addEventListener('click', (ev) => trabalhando(ev.currentTarget, async () => {
            try {
                const r = await api('/passe/temporada', 'POST', { nome: 'Nova temporada', tema: 'neutro', niveis: 100, xp_por_nivel: 800, catchup_dias: 14, catchup_pct: 50 });
                E.tid = r.id; toast('Temporada criada. Ajuste e salve.', 'ok'); vPasse();
            } catch (e) { /* toast já mostrado */ }
        }));
        $('#p-modelo-criar').addEventListener('click', (ev) => trabalhando(ev.currentTarget, async () => {
            try { const r = await api('/passe/modelo', 'POST', {}); E.tid = r.id; E.cat = null; toast('Modelo "Deuses" criado (inativo). Revise e ative.', 'ok'); vPasse(); } catch (e) { /* toast */ }
        }));
        if (!t) return;
        $('#t-salvar').addEventListener('click', (ev) => trabalhando(ev.currentTarget, async () => {
            const corpo = {
                id: t.id, nome: $('#t-nome').value, subtitulo: $('#t-sub').value, tema: $('#t-tema').value, niveis: +$('#t-niveis').value,
                xp_por_nivel: +$('#t-xp').value, inicio: $('#t-ini').value, fim: $('#t-fim').value, catchup_dias: +$('#t-cdias').value, catchup_pct: +$('#t-cpct').value, capitulos: $('#t-caps').value, capitulo_niveis: +$('#t-capn').value,
            };
            try { await api('/passe/temporada', 'POST', corpo); toast('Temporada salva.', 'ok'); E.mudancas.clear(); vPasse(); } catch (e) { /* toast */ }
        }));
        $('#t-ativar').addEventListener('click', (ev) => trabalhando(ev.currentTarget, async () => {
            try { await api(`/passe/temporada/${t.id}/ativar`, 'POST', { ativa: !t.ativa }); toast(t.ativa ? 'Temporada encerrada.' : 'Temporada ativa. Já vale pra todo mundo.', 'ok'); vPasse(); } catch (e) { /* toast */ }
        }));
        $('#t-modelo').addEventListener('click', () => confirmar('Aplicar o modelo "Deuses" apaga TODAS as recompensas desta temporada e coloca as 100 do modelo. Continuar?', async () => {
            try { const r = await api(`/passe/temporada/${t.id}/modelo`, 'POST', {}); toast(`Modelo aplicado (${r.qtd} recompensas).`, 'ok'); E.cat = null; await catalogo(); vPasse(); } catch (e) { return false; }
        }, 'Aplicar'));
        $('#t-apagar').addEventListener('click', () => confirmar(`Apagar a temporada "${t.nome}" e todas as suas recompensas?`, async () => {
            try { await api(`/passe/temporada/${t.id}`, 'DELETE'); toast('Temporada apagada.', 'ok'); E.tid = null; vPasse(); } catch (e) { return false; }
        }, 'Apagar'));
        ligarGrade();
    }

    async function carregarJogadores() {
        const alvo = $('#p-jogadores');
        if (!alvo) return;
        const d = await api(`/passe/temporada/${E.tid}/jogadores`);
        E.jogadores = d.jogadores;
        const t = temporadaAtual();
        alvo.innerHTML = `<div class="es-cartao" style="margin-top:16px"><h2>Quem está jogando</h2>
            <p class="es-sub" style="margin-bottom:10px">A trilha Premium ainda não tem pagamento: por enquanto é você quem libera (pra testar). ${t && t.ativa ? '' : 'Ative a temporada pra liberar o Premium.'}</p>
            <div class="es-linha" style="margin-bottom:12px"><div class="es-campo largo"><label>Liberar Premium pra alguém (procure por nome ou @)</label><input id="j-busca" placeholder="mínimo 2 letras" autocomplete="off"></div></div>
            <div id="j-achados"></div>
            <table class="es-tabela"><thead><tr><th>Pessoa</th><th>XP</th><th>Premium</th></tr></thead><tbody>
            ${E.jogadores.map((j) => `<tr><td>${esc(j.nome)} <small style="color:var(--muda)">@${esc(j.username)}</small></td><td>${j.xp.toLocaleString('pt-BR')}</td><td><button class="es-btn mini" data-p="${j.id}" data-a="${j.premium ? 0 : 1}">${j.premium ? 'Tirar Premium' : 'Liberar'}</button></td></tr>`).join('') || '<tr><td colspan="3" class="es-vazio">Ninguém jogou ainda.</td></tr>'}
            </tbody></table></div>`;
        alvo.querySelectorAll('button[data-p]').forEach((b) => b.addEventListener('click', () => premium(+b.dataset.p, b.dataset.a === '1')));
        const busca = $('#j-busca', alvo);
        let tm;
        busca.addEventListener('input', () => {
            clearTimeout(tm);
            tm = setTimeout(async () => {
                if (busca.value.trim().length < 2) { $('#j-achados', alvo).innerHTML = ''; return; }
                const r = await api('/pessoas?q=' + encodeURIComponent(busca.value));
                $('#j-achados', alvo).innerHTML = `<div class="es-lista" style="margin-bottom:12px">${r.pessoas.map((p) => `<button data-p="${p.id}"><span>${esc(p.nome)}</span><small>@${esc(p.username)} · liberar Premium</small></button>`).join('') || '<div class="es-vazio">Ninguém encontrado.</div>'}</div>`;
                $('#j-achados', alvo).querySelectorAll('button').forEach((b) => b.addEventListener('click', () => premium(+b.dataset.p, true)));
            }, 300);
        });
    }

    async function premium(id, ativo) {
        try { await api('/passe/premium', 'POST', { person_id: id, ativo }); toast(ativo ? 'Premium liberado.' : 'Premium removido.', 'ok'); carregarJogadores(); } catch (e) { /* toast */ }
    }

    // ------------------------------------------------------------
    // TÍTULOS
    // ------------------------------------------------------------
    function chipTitulo(t) { return `<span class="titulo-chip titulo-rar-${esc(t.raridade)} ${t.anim || t.animacao ? 'titulo-anim-' + esc(t.anim || t.animacao) : ''}">${esc(t.texto)}</span>`; }

    async function vTitulos() {
        const c = await (E.cat = null, catalogo());
        const linhas = c.titulos.map((t) => `<tr><td>${chipTitulo(t)}</td><td>${esc(t.raridade)}</td><td>${esc(t.anim || 'só texto')}</td><td><code>${esc(t.id)}</code></td><td style="color:var(--muda)">${esc(t.descricao)}</td>
            <td style="white-space:nowrap"><button class="es-btn mini" data-a="editar" data-id="${esc(t.id)}">Editar</button> <button class="es-btn mini" data-a="dar" data-id="${esc(t.id)}">Dar a alguém</button> <button class="es-btn mini perigo" data-a="apagar" data-id="${esc(t.id)}">Apagar</button></td></tr>`).join('');
        main.innerHTML = `<h1>Títulos</h1><p class="es-sub">Texto que a pessoa equipa e que aparece no cartão ao lado do @ e dos pronomes. Pode vir do passe, de conquistas ou de um presente seu. Alguns podem ter animação.</p>
            <div class="es-linha" style="margin-bottom:14px"><button class="es-btn primario" id="ti-novo">Novo título</button></div>
            <div class="es-cartao"><table class="es-tabela"><thead><tr><th>Título</th><th>Raridade</th><th>Animação</th><th>Id</th><th>Como se ganha</th><th></th></tr></thead><tbody>${linhas || '<tr><td colspan="6" class="es-vazio">Nenhum título ainda. Crie um, ou aplique o modelo "Deuses" no passe (ele cria os dele).</td></tr>'}</tbody></table></div>`;
        $('#ti-novo').addEventListener('click', () => formTitulo(null));
        main.querySelectorAll('button[data-a]').forEach((b) => b.addEventListener('click', () => {
            const t = c.titulos.find((x) => x.id === b.dataset.id);
            if (b.dataset.a === 'editar') formTitulo(t);
            else if (b.dataset.a === 'dar') darTitulo(t);
            else confirmar(`Apagar o título "${t.texto}"? Ele some de quem o tem e das recompensas que o usam.`, async () => { try { await api('/titulos/' + encodeURIComponent(t.id), 'DELETE'); toast('Título apagado.', 'ok'); vTitulos(); } catch (e) { return false; } }, 'Apagar');
        }));
    }

    function formTitulo(t) {
        const c = E.cat;
        dialogo(t ? 'Editar título' : 'Novo título', `
            <div class="es-campo"><label>Texto (2 a 32 caracteres)</label><input id="ft-texto" maxlength="32" value="${esc(t ? t.texto : '')}"></div>
            <div class="es-campo"><label>Id (letras minúsculas e _)</label><input id="ft-id" maxlength="24" value="${esc(t ? t.id : '')}" ${t ? 'disabled' : ''}><small>${t ? 'O id não muda depois de criado.' : 'Ex.: favorito_dos_deuses'}</small></div>
            <div class="es-linha"><div class="es-campo"><label>Raridade</label><select id="ft-rar">${c.raridades_titulo.map((r) => `<option ${t && t.raridade === r ? 'selected' : ''}>${r}</option>`).join('')}</select></div>
            <div class="es-campo"><label>Animação</label><select id="ft-anim"><option value="">Só texto</option>${c.animacoes_titulo.map((a) => `<option ${t && t.anim === a ? 'selected' : ''}>${a}</option>`).join('')}</select></div></div>
            <div class="es-campo"><label>Como se ganha (aparece no seletor)</label><input id="ft-desc" maxlength="120" value="${esc(t ? t.descricao : '')}"></div>
            <div class="es-campo"><label>Prévia</label><div id="ft-prev" style="padding:8px 0"></div></div>`,
        [{ texto: 'Cancelar' }, {
            texto: 'Salvar', classe: 'primario', fn: async (f) => {
                try {
                    await api('/titulos', 'POST', { id: $('#ft-id', f).value, texto: $('#ft-texto', f).value, raridade: $('#ft-rar', f).value, animacao: $('#ft-anim', f).value, descricao: $('#ft-desc', f).value });
                    toast('Título salvo.', 'ok'); E.cat = null; vTitulos();
                } catch (e) { return false; }
            },
        }]);
        const f = document.querySelector('.es-modal-fundo');
        const prev = () => { $('#ft-prev', f).innerHTML = chipTitulo({ texto: $('#ft-texto', f).value || 'Prévia', raridade: $('#ft-rar', f).value, anim: $('#ft-anim', f).value }); };
        ['ft-texto', 'ft-rar', 'ft-anim'].forEach((id) => $('#' + id, f).addEventListener('input', prev));
        prev();
    }

    function darTitulo(t) {
        const d = dialogo(`Dar "${t.texto}" a alguém`, `<div class="es-campo"><label>Procurar pessoa</label><input id="dt-q" placeholder="nome ou @" autocomplete="off"></div><div id="dt-r"></div>`, [{ texto: 'Fechar' }]);
        let tm;
        $('#dt-q', d.fundo).addEventListener('input', (e) => {
            clearTimeout(tm);
            tm = setTimeout(async () => {
                if (e.target.value.trim().length < 2) return;
                const r = await api('/pessoas?q=' + encodeURIComponent(e.target.value));
                const alvo = $('#dt-r', d.fundo);
                alvo.innerHTML = `<div class="es-lista">${r.pessoas.map((p) => `<button data-p="${p.id}"><span>${esc(p.nome)}</span><small>@${esc(p.username)}</small></button>`).join('') || '<div class="es-vazio">Ninguém encontrado.</div>'}</div>`;
                alvo.querySelectorAll('button').forEach((b) => b.addEventListener('click', async () => { try { await api('/titulos/conceder', 'POST', { titulo_id: t.id, person_id: +b.dataset.p }); toast('Título entregue.', 'ok'); d.fechar(); } catch (e2) { /* toast */ } }));
            }, 300);
        });
    }

    // ------------------------------------------------------------
    // MISSÕES (leitura)
    // ------------------------------------------------------------
    async function vMissoes() {
        const d = await api('/missoes');
        const bloco = (periodo) => d.missoes.filter((m) => m.periodo === periodo).map((m) => `<tr><td><i class="fa-solid fa-${esc(m.icone)}"></i> <b>${esc(m.titulo)}</b></td><td>${esc(m.desc)}</td><td>${m.xp} XP</td><td>${m.drc} moedas</td><td><code>${esc(m.codigo)}</code></td></tr>`).join('');
        const cab = '<thead><tr><th>Missão</th><th>O que pede</th><th>XP</th><th>Prêmio</th><th>Código</th></tr></thead>';
        main.innerHTML = `<h1>Missões</h1><p class="es-sub">Cada pessoa recebe <b>${d.regras.diarias} diárias</b> sorteadas por dia e vê <b>${d.regras.oferta_semanais} semanais</b> por semana, das quais <b>escolhe ${d.regras.escolhas_semanais}</b>. Só conta mensagem de verdade (mínimo de tamanho, sem repetir, com intervalo) e reação a mensagens diferentes. Os valores ainda moram em <code>app/utils.py</code> (MISSOES): a edição por aqui entra numa próxima etapa.</p>
            <div class="es-cartao"><h2>Diárias (${d.missoes.filter((m) => m.periodo === 'diaria').length})</h2><table class="es-tabela">${cab}<tbody>${bloco('diaria')}</tbody></table></div>
            <div class="es-cartao"><h2>Semanais (${d.missoes.filter((m) => m.periodo === 'semanal').length})</h2><table class="es-tabela">${cab}<tbody>${bloco('semanal')}</tbody></table></div>`;
    }

    // ------------------------------------------------------------
    // ADMINISTRADORES
    // ------------------------------------------------------------
    async function vAdmins() {
        const g = await api('/geral');
        main.innerHTML = `<h1>Administradores</h1><p class="es-sub">Quem pode abrir este painel e moderar o Bazar. O poder é guardado pelo <b>id</b> da pessoa (trocar o @ não passa o acesso pra outra).</p>
            <div class="es-cartao"><table class="es-tabela"><tbody>${g.admins.map((a) => `<tr><td><b>${esc(a.nome)}</b> <small style="color:var(--muda)">@${esc(a.username)}</small></td><td style="text-align:right">${a.id === window.EU.id ? '<span class="es-selo">você</span>' : `<button class="es-btn mini perigo" data-id="${a.id}">Remover</button>`}</td></tr>`).join('')}</tbody></table></div>
            <div class="es-cartao"><h2>Adicionar administrador</h2><div class="es-campo largo"><label>Procurar pessoa</label><input id="es-q" placeholder="nome ou @" autocomplete="off"></div><div id="es-r" style="margin-top:10px"></div></div>`;
        main.querySelectorAll('button[data-id]').forEach((b) => b.addEventListener('click', () => confirmar('Remover o acesso de administrador desta pessoa?', async () => { try { await api('/admins', 'POST', { person_id: +b.dataset.id, ativo: false }); vAdmins(); } catch (e) { return false; } }, 'Remover')));
        let tm;
        $('#es-q').addEventListener('input', (e) => {
            clearTimeout(tm);
            tm = setTimeout(async () => {
                if (e.target.value.trim().length < 2) return;
                const r = await api('/pessoas?q=' + encodeURIComponent(e.target.value));
                $('#es-r').innerHTML = `<div class="es-lista">${r.pessoas.map((p) => `<button data-p="${p.id}"><span>${esc(p.nome)}</span><small>@${esc(p.username)} · tornar admin</small></button>`).join('') || '<div class="es-vazio">Ninguém encontrado.</div>'}</div>`;
                $('#es-r').querySelectorAll('button').forEach((b) => b.addEventListener('click', () => confirmar('Dar acesso de administrador a esta pessoa? Ela poderá mexer no passe, nos títulos e moderar o Bazar.', async () => { try { await api('/admins', 'POST', { person_id: +b.dataset.p, ativo: true }); vAdmins(); } catch (e2) { return false; } }, 'Dar acesso')));
            }, 300);
        });
    }

    // ------------------------------------------------------------
    // EFEITOS (Estúdio: receita JSON -> motor js/efeitos.js). O esquema das camadas vem do servidor (a única definição).
    // ------------------------------------------------------------
    const XE = { lista: [], esquema: {}, raridades: [], maxCamadas: 6, atual: null, novo: true, timer: null };
    const PRESETS = {
        efeito_perfil: {
            'Poeira dourada': { pausa: 0, camadas: [{ tipo: 'particulas', cor: '#f2c14e', cor2: '#ffffff', qtd: 22, tam: 5, dur: 6, dir: 'cima', forma: 'circulo', brilho: 70 }, { tipo: 'brilho', cor: '#f2c14e', pos: 'base', forca: 30, dur: 6 }] },
            'Neve': { pausa: 0, camadas: [{ tipo: 'particulas', cor: '#ffffff', cor2: '#bfe3ff', qtd: 30, tam: 5, dur: 9, dir: 'baixo', forma: 'circulo', brilho: 40 }] },
            'Brasas': { pausa: 0, camadas: [{ tipo: 'particulas', cor: '#ff7a1f', cor2: '#ffd23f', qtd: 26, tam: 4, dur: 5, dir: 'cima', forma: 'losango', brilho: 80 }, { tipo: 'brilho', cor: '#ff4d1f', pos: 'base', forca: 40, dur: 4 }] },
            'Tempestade': { pausa: 3, camadas: [{ tipo: 'raios', cor: '#bfe3ff', qtd: 5, dur: 6 }, { tipo: 'brilho', cor: '#7cc4ff', pos: 'topo', forca: 45, dur: 6 }] },
            'Código verde': { pausa: 0, camadas: [{ tipo: 'particulas', cor: '#3dff7a', cor2: '#0f8a3a', qtd: 34, tam: 4, dur: 4, dir: 'baixo', forma: 'quadrado', brilho: 50 }] },
            'Estrelas': { pausa: 6, camadas: [{ tipo: 'particulas', cor: '#fff3b8', cor2: '#d9c8ff', qtd: 14, tam: 7, dur: 7, dir: 'dir', forma: 'estrela', brilho: 80 }] },
        },
        efeito_avatar: {
            'Onda dourada': { pausa: 0, camadas: [{ tipo: 'anel', cor: '#f2c14e', esp: 2, dur: 2.4 }] },
            'Satélites': { pausa: 0, camadas: [{ tipo: 'orbita', cor: '#ffffff', qtd: 3, tam: 4, dur: 4 }] },
            'Aura azul': { pausa: 2, camadas: [{ tipo: 'brilho', cor: '#7cc4ff', pos: 'centro', forca: 60, dur: 3 }, { tipo: 'anel', cor: '#7cc4ff', esp: 2, dur: 3 }] },
            'Brasa viva': { pausa: 0, camadas: [{ tipo: 'brilho', cor: '#ff5a1f', pos: 'centro', forca: 55, dur: 2.2 }, { tipo: 'orbita', cor: '#ffd23f', qtd: 4, tam: 3, dur: 3 }] },
        },
    };

    const novoEfeito = (tipo) => ({ id: '', nome: '', tipo: tipo || 'efeito_perfil', raridade: 'epico', descricao: '', receita: { pausa: 0, camadas: [] } });
    const camadaPadrao = (tipo) => { const c = { tipo }; Object.entries(XE.esquema[tipo].params).forEach(([k, p]) => { c[k] = p.padrao; }); return c; };

    async function vEfeitos() {
        const d = await api('/efeitos');
        XE.lista = d.efeitos; XE.esquema = d.esquema; XE.raridades = d.raridades; XE.maxCamadas = d.max_camadas;
        if (!XE.atual) { XE.atual = novoEfeito(); XE.novo = true; }
        desenharEfeitos();
    }

    function desenharEfeitos() {
        const lista = XE.lista.map((e) => `<button class="es-ef-item ${!XE.novo && XE.atual && XE.atual.id === e.id ? 'sel' : ''}" data-id="${esc(e.id)}"><b>${esc(e.nome)}</b><small>${e.tipo === 'efeito_perfil' ? 'cartão' : 'avatar'} · ${esc(e.raridade)} · ${esc(e.id)}</small></button>`).join('');
        main.innerHTML = `<h1>Efeitos</h1><p class="es-sub">Crie efeitos de <b>cartão de perfil</b> e de <b>avatar</b> montando camadas, sem código. Mexa nos controles e veja a prévia ao vivo. Ao salvar, o efeito entra no catálogo: dá pra <b>dar a alguém</b>, usar como <b>recompensa do passe</b> e, depois, vender. Só vale o que está na lista de camadas (nada de código livre), por isso é seguro.</p>
            <div class="es-ef-layout"><div class="es-ef-lado"><button class="es-btn primario" id="ef-novo">Novo efeito</button><div class="es-ef-lista">${lista || '<div class="es-vazio">Nenhum efeito ainda.</div>'}</div></div>
            <div class="es-ef-editor" id="ef-editor"></div></div>`;
        $('#ef-novo').addEventListener('click', () => { XE.atual = novoEfeito(); XE.novo = true; desenharEfeitos(); });
        main.querySelectorAll('.es-ef-item').forEach((b) => b.addEventListener('click', () => { const e = XE.lista.find((x) => x.id === b.dataset.id); XE.atual = JSON.parse(JSON.stringify(e)); XE.novo = false; desenharEfeitos(); }));
        desenharEditorEfeito();
    }

    function controle(p, valor, i, nome) {
        const id = `c${i}-${nome}`;
        if (p.t === 'num') return `<div class="es-campo"><label for="${id}">${esc(p.rotulo)} <b data-v="${id}">${valor}</b></label><input id="${id}" type="range" min="${p.min}" max="${p.max}" step="${p.max - p.min <= 20 ? 0.5 : 1}" value="${valor}" data-i="${i}" data-p="${nome}" data-t="num"></div>`;
        if (p.t === 'cor') return `<div class="es-campo"><label for="${id}">${esc(p.rotulo)}</label><input id="${id}" type="color" value="${esc(valor)}" data-i="${i}" data-p="${nome}" data-t="cor"></div>`;
        return `<div class="es-campo"><label for="${id}">${esc(p.rotulo)}</label><select id="${id}" data-i="${i}" data-p="${nome}" data-t="opcao">${p.opcoes.map((o) => `<option ${o === valor ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select></div>`;
    }

    function desenharEditorEfeito() {
        const e = XE.atual, alvo = $('#ef-editor');
        if (!alvo) return;
        const tipos = Object.keys(XE.esquema).filter((t) => XE.esquema[t].slots.includes(e.tipo));
        const presets = Object.keys(PRESETS[e.tipo] || {}).map((n) => `<option>${esc(n)}</option>`).join('');
        const camadas = e.receita.camadas.map((c, i) => `<div class="es-camada"><div class="es-camada-cab"><b>${esc(XE.esquema[c.tipo].nome)}</b><span class="es-dica">${esc(XE.esquema[c.tipo].dica)}</span>
            <span class="es-camada-acoes"><button class="es-btn mini" data-a="sobe" data-i="${i}" title="Subir">↑</button><button class="es-btn mini" data-a="desce" data-i="${i}" title="Descer">↓</button><button class="es-btn mini perigo" data-a="tira" data-i="${i}">Remover</button></span></div>
            <div class="es-camada-corpo">${Object.entries(XE.esquema[c.tipo].params).map(([k, p]) => controle(p, c[k], i, k)).join('')}</div></div>`).join('');
        alvo.innerHTML = `<div class="es-cartao"><h2>${XE.novo ? 'Novo efeito' : 'Editando: ' + esc(e.nome)}</h2>
            <div class="es-linha"><div class="es-campo largo"><label>Nome (2 a 40)</label><input id="ef-nome" maxlength="40" value="${esc(e.nome)}"></div>
                <div class="es-campo"><label>Id (letras minúsculas e _)</label><input id="ef-id" maxlength="24" value="${esc(e.id)}" ${XE.novo ? '' : 'disabled'}></div></div>
            <div class="es-linha" style="margin-top:12px"><div class="es-campo"><label>Onde aparece</label><select id="ef-tipo" ${XE.novo ? '' : 'disabled'}><option value="efeito_perfil" ${e.tipo === 'efeito_perfil' ? 'selected' : ''}>Cartão de perfil</option><option value="efeito_avatar" ${e.tipo === 'efeito_avatar' ? 'selected' : ''}>Avatar</option></select></div>
                <div class="es-campo"><label>Raridade</label><select id="ef-rar">${XE.raridades.map((r) => `<option ${r === e.raridade ? 'selected' : ''}>${r}</option>`).join('')}</select></div>
                <div class="es-campo largo"><label>Descrição (aparece pra quem ganhar)</label><input id="ef-desc" maxlength="120" value="${esc(e.descricao)}"></div></div></div>
            <div class="es-ef-colunas"><div>
                <div class="es-cartao"><h2>Camadas</h2><div class="es-linha"><div class="es-campo"><label>Começar de um modelo</label><select id="ef-preset"><option value="">(escolher)</option>${presets}</select></div>
                    <div class="es-campo"><label>Adicionar camada</label><select id="ef-add"><option value="">(escolher)</option>${tipos.map((t) => `<option value="${t}">${esc(XE.esquema[t].nome)}</option>`).join('')}</select></div></div>
                    <div class="es-campo" style="margin-top:12px"><label for="ef-pausa">Pausa entre uma passada e outra <b data-v="ef-pausa">${e.receita.pausa}</b> s</label><input id="ef-pausa" type="range" min="0" max="15" step="0.5" value="${e.receita.pausa}"><small>0 = sem parar. Com pausa, a cena toca e fica parada um tempo antes de recomeçar.</small></div>
                    <div class="es-camadas">${camadas || '<div class="es-vazio">Sem camadas. Escolha um modelo ou adicione uma.</div>'}</div></div></div>
                <div><div class="es-cartao es-prev-caixa"><h2>Prévia ao vivo</h2>
                    <div class="es-prev-cartao"><div class="es-prev-faixa"></div><div class="es-prev-av"><span class="es-prev-img">A</span><i class="ef-av ef-av-custom" id="pv-av" data-pv="1"></i></div><div class="es-prev-nome">Seu nome</div><div class="es-prev-sub">@voce</div><div class="ef-pf ef-pf-custom" id="pv-pf" data-pv="1"></div></div>
                    <div class="es-linha" style="margin-top:12px"><button class="es-btn primario" id="ef-salvar">${XE.novo ? 'Criar efeito' : 'Salvar alterações'}</button>
                        ${XE.novo ? '' : '<button class="es-btn" id="ef-mim">Dar a mim</button><button class="es-btn" id="ef-dar">Dar a alguém</button><button class="es-btn" id="ef-dup">Duplicar</button><button class="es-btn perigo" id="ef-apagar">Apagar</button>'}</div>
                    ${XE.novo ? '' : `<p class="es-dica" style="margin-top:10px">Item no catálogo: <code>${esc(e.tipo + ':' + e.id)}</code>. No Passe de Batalha, escolha "Item" e procure por ele.</p>`}</div></div></div>`;
        ligarEditorEfeito();
        pintarPrevia();
    }

    function pintarPrevia() {
        const e = XE.atual, pv = e.tipo === 'efeito_perfil' ? $('#pv-pf') : $('#pv-av');
        const outro = e.tipo === 'efeito_perfil' ? $('#pv-av') : $('#pv-pf');
        if (outro) outro.replaceChildren();
        if (pv) Efeitos.previa(pv, e.receita, e.id || 'previa');
    }

    function agendarPrevia() { clearTimeout(XE.timer); XE.timer = setTimeout(pintarPrevia, 90); }

    function ligarEditorEfeito() {
        const e = XE.atual, alvo = $('#ef-editor');
        $('#ef-nome').addEventListener('input', (x) => { e.nome = x.target.value; });
        if (XE.novo) {
            $('#ef-id').addEventListener('input', (x) => { e.id = x.target.value; });
            $('#ef-nome').addEventListener('input', () => { const idc = $('#ef-id'); if (!idc.dataset.tocado) { e.id = e.nome.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 24); idc.value = e.id; } });
            $('#ef-id').addEventListener('input', (x) => { x.target.dataset.tocado = '1'; });
            $('#ef-tipo').addEventListener('change', (x) => { e.tipo = x.target.value; e.receita = { pausa: 0, camadas: [] }; desenharEditorEfeito(); });
        }
        $('#ef-rar').addEventListener('change', (x) => { e.raridade = x.target.value; });
        $('#ef-desc').addEventListener('input', (x) => { e.descricao = x.target.value; });
        $('#ef-pausa').addEventListener('input', (x) => { e.receita.pausa = +x.target.value; $('[data-v="ef-pausa"]').textContent = x.target.value; agendarPrevia(); });
        $('#ef-preset').addEventListener('change', (x) => { const p = (PRESETS[e.tipo] || {})[x.target.value]; if (!p) return; e.receita = JSON.parse(JSON.stringify(p)); desenharEditorEfeito(); });
        $('#ef-add').addEventListener('change', (x) => {
            if (!x.target.value) return;
            if (e.receita.camadas.length >= XE.maxCamadas) { toast(`No máximo ${XE.maxCamadas} camadas.`, 'erro'); x.target.value = ''; return; }
            e.receita.camadas.push(camadaPadrao(x.target.value)); desenharEditorEfeito();
        });
        alvo.querySelectorAll('.es-camada input, .es-camada select').forEach((c) => c.addEventListener('input', () => {
            const camada = e.receita.camadas[+c.dataset.i], t = c.dataset.t;
            camada[c.dataset.p] = t === 'num' ? +c.value : c.value;
            const rot = alvo.querySelector(`[data-v="${c.id}"]`); if (rot) rot.textContent = c.value;
            agendarPrevia();
        }));
        alvo.querySelectorAll('[data-a]').forEach((b) => b.addEventListener('click', () => {
            const i = +b.dataset.i, cs = e.receita.camadas;
            if (b.dataset.a === 'tira') cs.splice(i, 1);
            else { const j = b.dataset.a === 'sobe' ? i - 1 : i + 1; if (j < 0 || j >= cs.length) return; [cs[i], cs[j]] = [cs[j], cs[i]]; }
            desenharEditorEfeito();
        }));
        $('#ef-salvar').addEventListener('click', async () => {
            try {
                const r = await api('/efeitos', 'POST', { id: e.id, nome: e.nome, tipo: e.tipo, raridade: e.raridade, descricao: e.descricao, receita: e.receita });
                toast(XE.novo ? 'Efeito criado!' : 'Efeito salvo. Quem está conectado já vê a mudança.', 'ok');
                E.cat = null; XE.novo = false;
                const d = await api('/efeitos'); XE.lista = d.efeitos; XE.atual = JSON.parse(JSON.stringify(XE.lista.find((x) => x.id === r.id)));
                desenharEfeitos();
            } catch (x) { /* o toast já mostrou o motivo */ }
        });
        $('#ef-mim')?.addEventListener('click', async () => { try { await api('/itens/conceder', 'POST', { item_id: e.tipo + ':' + e.id, person_id: window.EU.id }); toast('Entregue pra você: abra o Inventário no app e equipe.', 'ok'); } catch (x) { /* toast */ } });
        $('#ef-dar')?.addEventListener('click', () => darItem(e.tipo + ':' + e.id, e.nome));
        $('#ef-dup')?.addEventListener('click', () => { XE.atual = { ...JSON.parse(JSON.stringify(e)), id: '', nome: e.nome + ' (cópia)' }; XE.novo = true; desenharEfeitos(); });
        $('#ef-apagar')?.addEventListener('click', () => confirmar(`Apagar o efeito "${e.nome}"? Ele some de quem o tem (inventário e perfil) e das recompensas que o usam.`, async () => {
            try { await api('/efeitos/' + encodeURIComponent(e.id), 'DELETE'); toast('Efeito apagado.', 'ok'); E.cat = null; XE.atual = null; vEfeitos(); } catch (x) { return false; }
        }, 'Apagar'));
    }

    function darItem(itemId, nome) {
        const d = dialogo(`Dar "${nome}" a alguém`, '<div class="es-campo"><label>Procurar pessoa</label><input id="di-q" placeholder="nome ou @" autocomplete="off"></div><div id="di-r"></div>', [{ texto: 'Fechar' }]);
        let tm;
        $('#di-q', d.fundo).addEventListener('input', (ev) => {
            clearTimeout(tm);
            tm = setTimeout(async () => {
                if (ev.target.value.trim().length < 2) return;
                const r = await api('/pessoas?q=' + encodeURIComponent(ev.target.value));
                const alvo = $('#di-r', d.fundo);
                alvo.innerHTML = `<div class="es-lista">${r.pessoas.map((p) => `<button data-p="${p.id}"><span>${esc(p.nome)}</span><small>@${esc(p.username)}</small></button>`).join('') || '<div class="es-vazio">Ninguém encontrado.</div>'}</div>`;
                alvo.querySelectorAll('button').forEach((b) => b.addEventListener('click', async () => { try { await api('/itens/conceder', 'POST', { item_id: itemId, person_id: +b.dataset.p }); toast('Entregue.', 'ok'); d.fechar(); } catch (e2) { /* toast */ } }));
            }, 300);
        });
    }
    VISTAS.efeitos = vEfeitos;

    // ------------------------------------------------------------
    // SERVIDORES PÚBLICOS (Explorar): o admin vê e pode tirar do ar
    // ------------------------------------------------------------
    async function vServidores() {
        const d = await api('/servidores');
        main.innerHTML = `<h1>Servidores públicos</h1><p class="es-sub">Os servidores que aparecem no <b>Explorar</b> (o mar de barquinhos). Quem decide aparecer é o dono do servidor, nas configurações dele. Aqui você pode <b>tirar do Explorar</b> o que for inadequado: o servidor continua existindo, só deixa de ser descoberto.</p>
            <div class="es-cartao"><table class="es-tabela"><thead><tr><th>Servidor</th><th>Dono</th><th>Membros</th><th>Tema</th><th>Descrição</th><th></th></tr></thead><tbody>
            ${d.servidores.map((x) => `<tr><td><b>${esc(x.nome)}</b> <small style="color:var(--muda)">#${x.id}</small></td><td>${esc(x.dono)}</td><td>${x.membros}</td><td>${esc(x.tema)}</td><td style="color:var(--muda)">${esc(x.descricao)}</td><td><button class="es-btn mini perigo" data-id="${x.id}" data-nome="${esc(x.nome)}">Tirar do Explorar</button></td></tr>`).join('') || '<tr><td colspan="6" class="es-vazio">Nenhum servidor público ainda.</td></tr>'}
            </tbody></table></div>`;
        main.querySelectorAll('button[data-id]').forEach((b) => b.addEventListener('click', () => confirmar(`Tirar "${b.dataset.nome}" do Explorar? Os membros continuam no servidor.`, async () => {
            try { await api(`/servidores/${b.dataset.id}/despublicar`, 'POST', {}); toast('Servidor tirado do Explorar.', 'ok'); vServidores(); } catch (e) { return false; }
        }, 'Tirar')));
    }
    VISTAS.servidores = vServidores;

    window.addEventListener('beforeunload', (e) => { if (E.mudancas.size) { e.preventDefault(); e.returnValue = ''; } });
    ir((location.hash || '#geral').slice(1) in VISTAS ? (location.hash || '#geral').slice(1) : 'geral');
})();
