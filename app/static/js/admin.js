/* Painel do admin (/admin). Fala com /admin/api/* (JSON). Nada aqui é de confiança: o servidor confere admin e valida tudo. */
(function () {
    'use strict';
    const $ = (s, r) => (r || document).querySelector(s);
    const main = $('#ad-main');
    const E = { cat: null, tempo: [], tid: null, recs: new Map(), mudancas: new Map(), filtro: 'todos', jogadores: [] };

    const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    function toast(msg, tipo) {
        const el = document.createElement('div');
        el.className = 'ad-toast ' + (tipo || '');
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
        fundo.className = 'ad-modal-fundo';
        fundo.innerHTML = `<div class="ad-modal" role="dialog" aria-modal="true"><h3>${esc(titulo)}</h3><div class="ad-corpo">${corpoHtml}</div><div class="ad-modal-acoes"></div></div>`;
        const barra = $('.ad-modal-acoes', fundo);
        const fechar = () => { fundo.remove(); document.removeEventListener('keydown', esc_); };
        const esc_ = (e) => { if (e.key === 'Escape') fechar(); };
        document.addEventListener('keydown', esc_);
        fundo.addEventListener('mousedown', (e) => { if (e.target === fundo) fechar(); });
        (acoes || []).forEach((a) => {
            const b = document.createElement('button');
            b.className = 'ad-btn ' + (a.classe || '');
            b.textContent = a.texto;
            b.addEventListener('click', async () => { if (a.fn) { const r = await a.fn(fundo); if (r === false) return; } fechar(); });
            barra.appendChild(b);
        });
        document.body.appendChild(fundo);
        return { fundo, fechar };
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
        document.querySelectorAll('.ad-item[data-v]').forEach((b) => b.classList.toggle('ativo', b.dataset.v === v));
        location.hash = v;
        main.innerHTML = '<div class="ad-vazio">Carregando...</div>';
        Promise.resolve(VISTAS[v] && VISTAS[v]()).catch((e) => { main.innerHTML = `<div class="ad-vazio">Não foi possível carregar: ${esc(e.message)}</div>`; });
    }
    document.querySelectorAll('.ad-item[data-v]').forEach((b) => b.addEventListener('click', () => {
        if (E.mudancas.size && !confirm('Você tem alterações do passe não salvas. Sair mesmo assim?')) return;
        E.mudancas.clear();
        ir(b.dataset.v);
    }));

    // ------------------------------------------------------------
    // visão geral
    // ------------------------------------------------------------
    async function vGeral() {
        const g = await api('/geral');
        main.innerHTML = `<h1>Visão geral</h1><p class="ad-sub">O estúdio de quem cria o app. Aqui você define o passe, os títulos e as missões; o resto das áreas (cosméticos, Armazém, Bazar, denúncias...) entra nas próximas etapas.</p>
            <div class="ad-grade-3">
                <div class="ad-num"><b>${g.pessoas}</b><span>pessoas cadastradas</span></div>
                <div class="ad-num"><b>${g.temporada ? esc(g.temporada.nome) : 'nenhuma'}</b><span>temporada ativa</span></div>
                <div class="ad-num"><b>${g.admins.length}</b><span>administradores</span></div>
            </div>`;
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
            <p class="ad-sub">Defina a temporada (nome, tema, datas, quantos níveis) e, nível por nível, o que a trilha <b>Grátis</b> e a <b>Premium</b> entregam. Sem data de início/fim a temporada fica aberta até você encerrar. Só uma temporada fica ativa por vez.</p>
            <div class="ad-cartao"><div class="ad-linha">
                <div class="ad-campo largo"><label>Temporada</label><select id="p-sel">${opcoes || '<option value="">(nenhuma ainda)</option>'}</select></div>
                <button class="ad-btn" id="p-nova">Nova temporada</button>
                <button class="ad-btn" id="p-modelo-criar" title="Cria a Temporada 1: Deuses já com as 100 recompensas">Criar modelo "Deuses"</button>
            </div></div>`;
        if (t) html += formTemporada(t) + gradeRecompensas(t) + `<div id="p-jogadores"></div>`;
        main.innerHTML = html;
        ligarPasse(t);
        if (t) carregarJogadores();
    }

    function formTemporada(t) {
        const temas = E.cat.temas_passe.map((x) => `<option value="${x.id}" ${x.id === t.tema ? 'selected' : ''}>${esc(x.nome)}</option>`).join('');
        return `<div class="ad-cartao" id="p-form"><h2>Temporada ${t.ativa ? '<span class="ad-selo ativa">ativa</span>' : '<span class="ad-selo">inativa</span>'}</h2>
            <div class="ad-linha">
                <div class="ad-campo largo"><label>Nome</label><input id="t-nome" maxlength="60" value="${esc(t.nome)}"></div>
                <div class="ad-campo largo"><label>Subtítulo</label><input id="t-sub" maxlength="120" value="${esc(t.subtitulo)}"></div>
                <div class="ad-campo"><label>Tema visual</label><select id="t-tema">${temas}</select></div>
            </div>
            <div class="ad-linha" style="margin-top:12px">
                <div class="ad-campo"><label>Níveis</label><input id="t-niveis" type="number" min="1" max="200" value="${t.niveis}"></div>
                <div class="ad-campo"><label>XP por nível</label><input id="t-xp" type="number" min="50" max="100000" value="${t.xp_por_nivel}"><small>Chegar ao último = ${(t.niveis * t.xp_por_nivel).toLocaleString('pt-BR')} XP</small></div>
                <div class="ad-campo"><label>Início (opcional)</label><input id="t-ini" type="datetime-local" value="${esc(t.inicio)}"></div>
                <div class="ad-campo"><label>Fim (opcional)</label><input id="t-fim" type="datetime-local" value="${esc(t.fim)}"></div>
            </div>
            <div class="ad-linha" style="margin-top:12px">
                <div class="ad-campo"><label>Catch-up: nos últimos (dias)</label><input id="t-cdias" type="number" min="0" max="90" value="${t.catchup_dias}"></div>
                <div class="ad-campo"><label>...o XP rende a mais (%)</label><input id="t-cpct" type="number" min="0" max="300" value="${t.catchup_pct}"><small>0 desliga. Ajuda quem entrou tarde.</small></div>
            </div>
            <div class="ad-linha" style="margin-top:16px">
                <button class="ad-btn primario" id="t-salvar">Salvar temporada</button>
                <button class="ad-btn ${t.ativa ? '' : 'ok'}" id="t-ativar">${t.ativa ? 'Encerrar temporada' : 'Ativar temporada'}</button>
                <button class="ad-btn" id="t-modelo">Aplicar modelo "Deuses"</button>
                <button class="ad-btn perigo" id="t-apagar">Apagar</button>
            </div></div>`;
    }

    function ehMarco(n) { return n % 10 === 0 || n % 5 === 0; }

    function gradeRecompensas(t) {
        let linhas = '';
        for (let n = 1; n <= t.niveis; n++) {
            const g = recAtual(n, 'gratis'), p = recAtual(n, 'premium');
            const mostrar = E.filtro === 'todos' || (E.filtro === 'marcos' && (ehMarco(n) || (g && g.tipo !== 'moeda') || (p && p.tipo !== 'moeda'))) || (E.filtro === 'vazios' && (!g || !p));
            if (!mostrar) continue;
            linhas += `<div class="ad-grade-linha ${ehMarco(n) ? 'marco' : ''}"><div class="ad-grade-n">${n}</div>${celula(n, 'gratis', g)}${celula(n, 'premium', p)}</div>`;
        }
        const n = E.mudancas.size;
        return `<div class="ad-barra-fixa"><div class="ad-campo" style="flex:0 0 160px;min-width:0"><select id="g-filtro">
                    <option value="todos" ${E.filtro === 'todos' ? 'selected' : ''}>Todos os níveis</option>
                    <option value="marcos" ${E.filtro === 'marcos' ? 'selected' : ''}>Só marcos e prêmios</option>
                    <option value="vazios" ${E.filtro === 'vazios' ? 'selected' : ''}>Com slot vazio</option></select></div>
                <button class="ad-btn" id="g-preencher">Preencher moedas...</button>
                <span style="flex:1"></span>
                <span class="ad-selo ${n ? 'aviso' : ''}" id="g-cont">${n} alteraç${n === 1 ? 'ão' : 'ões'} não salva${n === 1 ? '' : 's'}</span>
                <button class="ad-btn" id="g-descartar" ${n ? '' : 'disabled'}>Descartar</button>
                <button class="ad-btn primario" id="g-salvar" ${n ? '' : 'disabled'}>Salvar recompensas</button></div>
            <div class="ad-grade"><div class="ad-grade-cab"><div>Nível</div><div>Trilha Grátis</div><div>Trilha Premium</div></div>${linhas || '<div class="ad-vazio">Nada neste filtro.</div>'}</div>`;
    }

    function celula(n, trilha, r) {
        const d = descreverRec(r);
        const mudou = E.mudancas.has(chave(n, trilha));
        if (!r || !r.tipo) return `<button class="ad-cel vazia ${mudou ? 'mudou' : ''}" data-n="${n}" data-t="${trilha}">vazio</button>`;
        return `<button class="ad-cel ${mudou ? 'mudou' : ''}" data-n="${n}" data-t="${trilha}"><span class="ad-cel-ico ${d.ico}"><i class="fa-solid ${iconeTipo[r.tipo]}"></i></span><span><b>${esc(d.nome)}</b>${d.sub ? `<span class="sub">${esc(d.sub)}</span>` : ''}</span></button>`;
    }

    function redesenharGrade() {
        const t = temporadaAtual();
        const barra = $('.ad-barra-fixa');
        const grade = $('.ad-grade');
        if (!t || !barra) return;
        const novo = document.createElement('div');
        novo.innerHTML = gradeRecompensas(t);
        barra.replaceWith(novo.querySelector('.ad-barra-fixa'));
        grade.replaceWith(novo.querySelector('.ad-grade'));
        ligarGrade();
    }

    function ligarGrade() {
        $('#g-filtro').addEventListener('change', (e) => { E.filtro = e.target.value; redesenharGrade(); });
        $('#g-preencher').addEventListener('click', dialogoPreencher);
        $('#g-descartar').addEventListener('click', () => { E.mudancas.clear(); redesenharGrade(); });
        $('#g-salvar').addEventListener('click', salvarRecompensas);
        document.querySelectorAll('.ad-cel').forEach((b) => b.addEventListener('click', () => editarCelula(+b.dataset.n, b.dataset.t)));
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
            <div class="ad-linha"><div class="ad-campo"><label>Trilha</label><select id="f-trilha"><option value="gratis">Grátis</option><option value="premium">Premium</option></select></div>
            <div class="ad-campo"><label>Do nível</label><input id="f-de" type="number" min="1" max="${t.niveis}" value="1"></div>
            <div class="ad-campo"><label>Até o nível</label><input id="f-ate" type="number" min="1" max="${t.niveis}" value="${t.niveis}"></div>
            <div class="ad-campo"><label>Moedas base</label><input id="f-base" type="number" min="1" value="50"></div></div>`,
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
            <div class="ad-campo"><label>O que entrega</label><select id="e-tipo">
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
            if (tipo === 'moeda') corpo.innerHTML = `<div class="ad-campo"><label>Quantidade de moedas</label><input id="e-qtd" type="number" min="1" max="100000" value="${qtd}"></div>`;
            else if (tipo === 'item' || tipo === 'titulo' || tipo === 'tema') {
                const fonte = tipo === 'item' ? E.cat.itens.map((i) => ({ id: i.id, nome: i.nome, sub: `${i.rotulo} · ${i.raridade}` }))
                    : tipo === 'titulo' ? E.cat.titulos.map((t) => ({ id: t.id, nome: t.texto, sub: t.raridade }))
                        : E.cat.temas_app.map((t) => ({ id: t.id, nome: t.nome, sub: 'tema' }));
                corpo.innerHTML = `<div class="ad-campo"><label>Procurar</label><input id="e-busca" placeholder="digite pra filtrar" autocomplete="off"></div><div class="ad-lista" id="e-lista"></div>
                    ${tipo === 'tema' && !fonte.length ? '<p class="ad-sub">Nenhum tema de temporada cadastrado.</p>' : ''}`;
                const lista = $('#e-lista', corpo);
                const pintarLista = () => {
                    const q = $('#e-busca', corpo).value.toLowerCase();
                    const f = fonte.filter((x) => !q || x.nome.toLowerCase().includes(q) || x.id.toLowerCase().includes(q)).slice(0, 80);
                    lista.innerHTML = f.map((x) => `<button type="button" data-id="${esc(x.id)}" class="${x.id === valor ? 'sel' : ''}"><span>${esc(x.nome)}</span><small>${esc(x.sub)} · ${esc(x.id)}</small></button>`).join('') || '<div class="ad-vazio">Nada encontrado.</div>';
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
        $('#p-nova').addEventListener('click', async () => {
            try {
                const r = await api('/passe/temporada', 'POST', { nome: 'Nova temporada', tema: 'neutro', niveis: 100, xp_por_nivel: 800, catchup_dias: 14, catchup_pct: 50 });
                E.tid = r.id; toast('Temporada criada. Ajuste e salve.', 'ok'); vPasse();
            } catch (e) { /* toast já mostrado */ }
        });
        $('#p-modelo-criar').addEventListener('click', async () => {
            try { const r = await api('/passe/modelo', 'POST', {}); E.tid = r.id; E.cat = null; toast('Modelo "Deuses" criado (inativo). Revise e ative.', 'ok'); vPasse(); } catch (e) { /* toast */ }
        });
        if (!t) return;
        $('#t-salvar').addEventListener('click', async () => {
            const corpo = {
                id: t.id, nome: $('#t-nome').value, subtitulo: $('#t-sub').value, tema: $('#t-tema').value, niveis: +$('#t-niveis').value,
                xp_por_nivel: +$('#t-xp').value, inicio: $('#t-ini').value, fim: $('#t-fim').value, catchup_dias: +$('#t-cdias').value, catchup_pct: +$('#t-cpct').value,
            };
            try { await api('/passe/temporada', 'POST', corpo); toast('Temporada salva.', 'ok'); E.mudancas.clear(); vPasse(); } catch (e) { /* toast */ }
        });
        $('#t-ativar').addEventListener('click', async () => {
            try { await api(`/passe/temporada/${t.id}/ativar`, 'POST', { ativa: !t.ativa }); toast(t.ativa ? 'Temporada encerrada.' : 'Temporada ativa. Já vale pra todo mundo.', 'ok'); vPasse(); } catch (e) { /* toast */ }
        });
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
        alvo.innerHTML = `<div class="ad-cartao" style="margin-top:16px"><h2>Quem está jogando</h2>
            <p class="ad-sub" style="margin-bottom:10px">A trilha Premium ainda não tem pagamento: por enquanto é você quem libera (pra testar). ${t && t.ativa ? '' : 'Ative a temporada pra liberar o Premium.'}</p>
            <div class="ad-linha" style="margin-bottom:12px"><div class="ad-campo largo"><label>Liberar Premium pra alguém (procure por nome ou @)</label><input id="j-busca" placeholder="mínimo 2 letras" autocomplete="off"></div></div>
            <div id="j-achados"></div>
            <table class="ad-tabela"><thead><tr><th>Pessoa</th><th>XP</th><th>Premium</th></tr></thead><tbody>
            ${E.jogadores.map((j) => `<tr><td>${esc(j.nome)} <small style="color:var(--muda)">@${esc(j.username)}</small></td><td>${j.xp.toLocaleString('pt-BR')}</td><td><button class="ad-btn mini" data-p="${j.id}" data-a="${j.premium ? 0 : 1}">${j.premium ? 'Tirar Premium' : 'Liberar'}</button></td></tr>`).join('') || '<tr><td colspan="3" class="ad-vazio">Ninguém jogou ainda.</td></tr>'}
            </tbody></table></div>`;
        alvo.querySelectorAll('button[data-p]').forEach((b) => b.addEventListener('click', () => premium(+b.dataset.p, b.dataset.a === '1')));
        const busca = $('#j-busca', alvo);
        let tm;
        busca.addEventListener('input', () => {
            clearTimeout(tm);
            tm = setTimeout(async () => {
                if (busca.value.trim().length < 2) { $('#j-achados', alvo).innerHTML = ''; return; }
                const r = await api('/pessoas?q=' + encodeURIComponent(busca.value));
                $('#j-achados', alvo).innerHTML = `<div class="ad-lista" style="margin-bottom:12px">${r.pessoas.map((p) => `<button data-p="${p.id}"><span>${esc(p.nome)}</span><small>@${esc(p.username)} · liberar Premium</small></button>`).join('') || '<div class="ad-vazio">Ninguém encontrado.</div>'}</div>`;
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
            <td style="white-space:nowrap"><button class="ad-btn mini" data-a="editar" data-id="${esc(t.id)}">Editar</button> <button class="ad-btn mini" data-a="dar" data-id="${esc(t.id)}">Dar a alguém</button> <button class="ad-btn mini perigo" data-a="apagar" data-id="${esc(t.id)}">Apagar</button></td></tr>`).join('');
        main.innerHTML = `<h1>Títulos</h1><p class="ad-sub">Texto que a pessoa equipa e que aparece no cartão ao lado do @ e dos pronomes. Pode vir do passe, de conquistas ou de um presente seu. Alguns podem ter animação.</p>
            <div class="ad-linha" style="margin-bottom:14px"><button class="ad-btn primario" id="ti-novo">Novo título</button></div>
            <div class="ad-cartao"><table class="ad-tabela"><thead><tr><th>Título</th><th>Raridade</th><th>Animação</th><th>Id</th><th>Como se ganha</th><th></th></tr></thead><tbody>${linhas || '<tr><td colspan="6" class="ad-vazio">Nenhum título ainda. Crie um, ou aplique o modelo "Deuses" no passe (ele cria os dele).</td></tr>'}</tbody></table></div>`;
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
            <div class="ad-campo"><label>Texto (2 a 32 caracteres)</label><input id="ft-texto" maxlength="32" value="${esc(t ? t.texto : '')}"></div>
            <div class="ad-campo"><label>Id (letras minúsculas e _)</label><input id="ft-id" maxlength="24" value="${esc(t ? t.id : '')}" ${t ? 'disabled' : ''}><small>${t ? 'O id não muda depois de criado.' : 'Ex.: favorito_dos_deuses'}</small></div>
            <div class="ad-linha"><div class="ad-campo"><label>Raridade</label><select id="ft-rar">${c.raridades_titulo.map((r) => `<option ${t && t.raridade === r ? 'selected' : ''}>${r}</option>`).join('')}</select></div>
            <div class="ad-campo"><label>Animação</label><select id="ft-anim"><option value="">Só texto</option>${c.animacoes_titulo.map((a) => `<option ${t && t.anim === a ? 'selected' : ''}>${a}</option>`).join('')}</select></div></div>
            <div class="ad-campo"><label>Como se ganha (aparece no seletor)</label><input id="ft-desc" maxlength="120" value="${esc(t ? t.descricao : '')}"></div>
            <div class="ad-campo"><label>Prévia</label><div id="ft-prev" style="padding:8px 0"></div></div>`,
        [{ texto: 'Cancelar' }, {
            texto: 'Salvar', classe: 'primario', fn: async (f) => {
                try {
                    await api('/titulos', 'POST', { id: $('#ft-id', f).value, texto: $('#ft-texto', f).value, raridade: $('#ft-rar', f).value, animacao: $('#ft-anim', f).value, descricao: $('#ft-desc', f).value });
                    toast('Título salvo.', 'ok'); E.cat = null; vTitulos();
                } catch (e) { return false; }
            },
        }]);
        const f = document.querySelector('.ad-modal-fundo');
        const prev = () => { $('#ft-prev', f).innerHTML = chipTitulo({ texto: $('#ft-texto', f).value || 'Prévia', raridade: $('#ft-rar', f).value, anim: $('#ft-anim', f).value }); };
        ['ft-texto', 'ft-rar', 'ft-anim'].forEach((id) => $('#' + id, f).addEventListener('input', prev));
        prev();
    }

    function darTitulo(t) {
        const d = dialogo(`Dar "${t.texto}" a alguém`, `<div class="ad-campo"><label>Procurar pessoa</label><input id="dt-q" placeholder="nome ou @" autocomplete="off"></div><div id="dt-r"></div>`, [{ texto: 'Fechar' }]);
        let tm;
        $('#dt-q', d.fundo).addEventListener('input', (e) => {
            clearTimeout(tm);
            tm = setTimeout(async () => {
                if (e.target.value.trim().length < 2) return;
                const r = await api('/pessoas?q=' + encodeURIComponent(e.target.value));
                const alvo = $('#dt-r', d.fundo);
                alvo.innerHTML = `<div class="ad-lista">${r.pessoas.map((p) => `<button data-p="${p.id}"><span>${esc(p.nome)}</span><small>@${esc(p.username)}</small></button>`).join('') || '<div class="ad-vazio">Ninguém encontrado.</div>'}</div>`;
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
        main.innerHTML = `<h1>Missões</h1><p class="ad-sub">Cada pessoa recebe <b>${d.regras.diarias} diárias</b> sorteadas por dia e vê <b>${d.regras.oferta_semanais} semanais</b> por semana, das quais <b>escolhe ${d.regras.escolhas_semanais}</b>. Só conta mensagem de verdade (mínimo de tamanho, sem repetir, com intervalo) e reação a mensagens diferentes. Os valores ainda moram em <code>app/utils.py</code> (MISSOES): a edição por aqui entra numa próxima etapa.</p>
            <div class="ad-cartao"><h2>Diárias (${d.missoes.filter((m) => m.periodo === 'diaria').length})</h2><table class="ad-tabela">${cab}<tbody>${bloco('diaria')}</tbody></table></div>
            <div class="ad-cartao"><h2>Semanais (${d.missoes.filter((m) => m.periodo === 'semanal').length})</h2><table class="ad-tabela">${cab}<tbody>${bloco('semanal')}</tbody></table></div>`;
    }

    // ------------------------------------------------------------
    // ADMINISTRADORES
    // ------------------------------------------------------------
    async function vAdmins() {
        const g = await api('/geral');
        main.innerHTML = `<h1>Administradores</h1><p class="ad-sub">Quem pode abrir este painel e moderar o Bazar. O poder é guardado pelo <b>id</b> da pessoa (trocar o @ não passa o acesso pra outra).</p>
            <div class="ad-cartao"><table class="ad-tabela"><tbody>${g.admins.map((a) => `<tr><td><b>${esc(a.nome)}</b> <small style="color:var(--muda)">@${esc(a.username)}</small></td><td style="text-align:right">${a.id === window.EU.id ? '<span class="ad-selo">você</span>' : `<button class="ad-btn mini perigo" data-id="${a.id}">Remover</button>`}</td></tr>`).join('')}</tbody></table></div>
            <div class="ad-cartao"><h2>Adicionar administrador</h2><div class="ad-campo largo"><label>Procurar pessoa</label><input id="ad-q" placeholder="nome ou @" autocomplete="off"></div><div id="ad-r" style="margin-top:10px"></div></div>`;
        main.querySelectorAll('button[data-id]').forEach((b) => b.addEventListener('click', () => confirmar('Remover o acesso de administrador desta pessoa?', async () => { try { await api('/admins', 'POST', { person_id: +b.dataset.id, ativo: false }); vAdmins(); } catch (e) { return false; } }, 'Remover')));
        let tm;
        $('#ad-q').addEventListener('input', (e) => {
            clearTimeout(tm);
            tm = setTimeout(async () => {
                if (e.target.value.trim().length < 2) return;
                const r = await api('/pessoas?q=' + encodeURIComponent(e.target.value));
                $('#ad-r').innerHTML = `<div class="ad-lista">${r.pessoas.map((p) => `<button data-p="${p.id}"><span>${esc(p.nome)}</span><small>@${esc(p.username)} · tornar admin</small></button>`).join('') || '<div class="ad-vazio">Ninguém encontrado.</div>'}</div>`;
                $('#ad-r').querySelectorAll('button').forEach((b) => b.addEventListener('click', () => confirmar('Dar acesso de administrador a esta pessoa? Ela poderá mexer no passe, nos títulos e moderar o Bazar.', async () => { try { await api('/admins', 'POST', { person_id: +b.dataset.p, ativo: true }); vAdmins(); } catch (e2) { return false; } }, 'Dar acesso')));
            }, 300);
        });
    }

    window.addEventListener('beforeunload', (e) => { if (E.mudancas.size) { e.preventDefault(); e.returnValue = ''; } });
    ir((location.hash || '#geral').slice(1) in VISTAS ? (location.hash || '#geral').slice(1) : 'geral');
})();
