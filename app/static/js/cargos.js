/* Cargos por servidor, categorias e separadores da lista de canais, tipos de canal, palco e personalização do servidor (Rodada 29). Objeto global `Cargos`.
   Quem decide é o servidor (app/cargos.py): aqui só se desenha e se manda o pedido. O cliente recebe, em cada servidor, as permissões da PRÓPRIA pessoa
   (`minhasPerms`, `meuNivel`), os cargos, as categorias e os canais que ela enxerga, e usa isso só para mostrar ou esconder botões.
   Contexto (Cargos.iniciar): { socket, esc, escUrl, toast, confirmar(titulo, texto, ok), pedirTexto(titulo, desc, dica, cb), meuId(), servidores(), servidorAtivo(),
     trocarServidor(srv), canalAtualId(), religarCanais(container), abrirCriarCanal(dados), abrirEditarCanal(canal), selecionarTipo(tipo), membros(), emojificar(el),
     emCall(canalId), travarMic(), escolherImagem(cfg), uploadMidia(arquivo), configAberta(), pedirMembros(), trocarSecao(nome), abrirConfigCompleta(),
     fecharConfigCompleta() }
   Os ids de permissão e de tipo espelham app/cargos.py (PERMISSOES e TIPOS_CANAL): o teste testes/fumaca_cargos.py confere que as listas batem. */
const Cargos = (() => {
    'use strict';
    let C = null;

    // ---------------------------------------------------------------------
    // listas fechadas (espelho do servidor)
    // ---------------------------------------------------------------------
    const PERMISSOES = [
        ['administrador', 'Administrador', 'Pode tudo, menos apagar o servidor e passar a posse. Dê só a quem você confia como a você.'],
        ['gerenciar_servidor', 'Gerenciar o servidor', 'Nome, ícone, descrição, banner, boas-vindas, Explorar, efeitos e convites.'],
        ['gerenciar_canais', 'Gerenciar canais', 'Criar, editar, apagar e organizar canais, categorias e separadores.'],
        ['gerenciar_cargos', 'Gerenciar cargos', 'Criar e editar cargos abaixo do seu e dá-los aos membros.'],
        ['expulsar', 'Remover membros', 'Tirar do servidor quem está abaixo do seu cargo.'],
        ['gerenciar_eventos', 'Gerenciar eventos', 'Criar, editar e apagar eventos do calendário.'],
        ['criar_convite', 'Criar convites', 'Gerar links de convite (sem gerenciar o servidor: no máximo 7 dias e 25 usos).'],
        ['apagar_mensagens', 'Apagar mensagens dos outros', 'Apagar a mensagem de qualquer pessoa nos canais que enxerga.'],
        ['fixar_mensagens', 'Fixar mensagens', 'Fixar e desafixar mensagens.'],
        ['ver_canais_privados', 'Ver canais privados', 'Enxergar todos os canais privados, mesmo sem ter sido convidado a eles.'],
        ['falar_voz', 'Falar nos canais de voz', 'Sem isso a pessoa entra em voz só como ouvinte (microfone travado).'],
        ['enviar_anuncios', 'Publicar em anúncios e regras', 'Escrever em canais de anúncios e de regras (todo mundo pode ler).'],
        ['falar_palco', 'Falar no palco', 'Ser orador em canal de palco e chamar ouvintes pro palco.'],
    ];
    const TIPOS = {
        text: { fam: 'texto', nome: 'Texto', fa: 'fa-hashtag', desc: 'Conversa livre, com mensagens, fotos e GIFs.' },
        anuncios: { fam: 'texto', nome: 'Anúncios', fa: 'fa-bullhorn', desc: 'Todo mundo lê; só quem tem permissão escreve.' },
        regras: { fam: 'texto', nome: 'Regras', fa: 'fa-scroll', desc: 'Somente leitura, pras regras e avisos fixos.' },
        midia: { fam: 'texto', nome: 'Mídia', fa: 'fa-photo-film', desc: 'Só vale mensagem com foto, vídeo ou GIF.' },
        voice: { fam: 'voz', nome: 'Voz', fa: 'fa-volume-high', desc: 'Voz, vídeo e tela, com limite de pessoas opcional.' },
        palco: { fam: 'voz', nome: 'Palco', fa: 'fa-microphone-lines', desc: 'Poucos falam e o resto escuta; quem fala chama os outros.' },
        separador: { fam: 'estrutura', nome: 'Separador', fa: 'fa-grip-lines', desc: 'Uma linha na lista, com título ou sem.' },
    };
    const CORES = ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#1abc9c', '#3498db', '#5865f2', '#9b59b6', '#e91e63', '#95a5a6', '#ecf0f1', '#34495e'];
    const GESTAO = ['gerenciar_servidor', 'gerenciar_canais', 'gerenciar_cargos', 'expulsar', 'gerenciar_eventos'];
    const NIVEL_DONO = 1e9;

    const familia = (t) => (TIPOS[t] || TIPOS.text).fam;
    const tipoValido = (t) => (TIPOS[t] ? t : null);
    const E = (v) => C.esc(v == null ? '' : v);
    const nome = (id) => (PERMISSOES.find(p => p[0] === id) || [])[1] || id;

    // ---------------------------------------------------------------------
    // o que EU posso (só pra mostrar/esconder; o servidor confere de novo)
    // ---------------------------------------------------------------------
    const ehDono = (srv) => !!srv && Number(srv.owner_id) === Number(C.meuId());
    const pode = (srv, perm) => !!srv && (ehDono(srv) || (srv.minhasPerms || []).includes(perm));
    const podeGerir = (srv) => ehDono(srv) || GESTAO.some(p => pode(srv, p));
    const meuNivel = (srv) => (ehDono(srv) ? NIVEL_DONO : (srv.meuNivel || 0));
    const cargoPorId = (srv, id) => (srv.cargos || []).find(c => Number(c.id) === Number(id));
    const nivelDe = (srv, cargosIds) => (cargosIds || []).reduce((n, id) => Math.max(n, (cargoPorId(srv, id) || {}).pos || 0), 0);
    const editavel = (srv, cargo) => ehDono(srv) || (cargo.pos || 0) < meuNivel(srv);
    const permsDoCargo = (c) => c.perms || [];

    // ---------------------------------------------------------------------
    // agrupar canais por categoria
    // ---------------------------------------------------------------------
    const porPos = (a, b) => ((a.pos || 0) - (b.pos || 0)) || (a.id - b.id);

    /** [{id, nome, virtual, itens}] na ordem de desenho. id 0 = canais soltos (só existe com categorias de verdade). */
    function montarGrupos(srv) {
        const canais = (srv.channels || []).slice().sort(porPos);
        const cats = srv.categorias || [];
        if (!cats.length) {   // servidor que nunca organizou: as duas seções de sempre, sem linha no banco (viram reais na 1ª edição)
            return [
                { id: 'padrao_text', nome: 'CANAIS DE TEXTO', virtual: true, itens: canais.filter(c => familia(c.type) !== 'voz') },
                { id: 'padrao_voice', nome: 'CANAIS DE VOZ', virtual: true, itens: canais.filter(c => familia(c.type) === 'voz') },
            ];
        }
        const conhecidas = new Set(cats.map(c => c.id));
        const grupos = [{ id: 0, nome: null, itens: canais.filter(c => !c.categoria_id || !conhecidas.has(c.categoria_id)) }];
        cats.forEach(k => grupos.push({ id: k.id, nome: k.nome, itens: canais.filter(c => c.categoria_id === k.id) }));
        return grupos;
    }

    /** O mesmo desenho como pedido de organização: {categorias:[ids], grupos:{id:[canais]}} */
    function layoutDoServidor(srv) {
        const grupos = montarGrupos(srv), saida = { categorias: [], grupos: {} };
        grupos.forEach(g => { if (g.id !== 0) saida.categorias.push(g.id); saida.grupos[g.id] = g.itens.map(c => c.id); });
        return saida;
    }
    function emitirLayout(srv, lay) {
        C.socket.emit('canais_organizar', { server_id: srv.id, categorias: lay.categorias, grupos: lay.grupos });
    }

    // ---------------------------------------------------------------------
    // recolher / expandir categoria (preferência do navegador, por servidor)
    // ---------------------------------------------------------------------
    const chFechadas = (srvId) => 'pnt_cat_fechadas_' + srvId;
    function fechadas(srvId) { try { return JSON.parse(localStorage.getItem(chFechadas(srvId)) || '{}') || {}; } catch (e) { return {}; } }
    function guardarFechada(srvId, catId, fechada) {
        try { const o = fechadas(srvId); if (fechada) o[catId] = 1; else delete o[catId]; localStorage.setItem(chFechadas(srvId), JSON.stringify(o)); } catch (e) { /* sem armazenamento: vale até recarregar */ }
    }

    // ---------------------------------------------------------------------
    // lista de canais
    // ---------------------------------------------------------------------
    function iconeDoCanal(c) {
        if (c.icone) return `<span class="canal-emoji channel-icon">${E(c.icone)}</span>`;
        const t = TIPOS[c.type] || TIPOS.text;
        return `<i class="fa-solid ${t.fa} channel-icon" style="font-size:${t.fam === 'voz' ? 16 : 17}px;${t.fam === 'voz' ? '' : 'color:var(--text-muted);'}"></i>`;
    }

    function htmlCanal(c, srv, arrastavel) {
        if (c.type === 'separador') return htmlSeparador(c, srv, arrastavel);
        const voz = familia(c.type) === 'voz';
        const classes = `channel-item ${voz ? 'voice-channel' : 'text-channel'} tipo-${E(c.type)}`;
        const cadeado = c.is_private ? '<i class="fa-solid fa-lock" style="font-size:10px;color:var(--text-muted);margin-left:4px;" title="Canal privado"></i>' : '';
        const lim = voz && c.limite ? `<span class="canal-lim" title="Limite de pessoas">máx ${Number(c.limite)}</span>` : '';
        const engrenagem = pode(srv, 'gerenciar_canais')
            ? `<i class="fa-solid fa-gear btn-config-channel" data-id="${Number(c.id)}" style="margin-left:auto;font-size:13px;cursor:pointer;opacity:0;transition:.15s;" title="Editar canal"></i>` : '';
        const tip = (TIPOS[c.type] || TIPOS.text).nome + (c.topic ? ' — ' + c.topic : '');
        const linha = `<div class="${classes}" data-id="${Number(c.id)}" data-name="${E(c.name)}" data-tipo="${E(c.type)}" title="${E(c.topic || tip)}"
                    ${arrastavel ? `draggable="true" data-arrasta="canal"` : ''}>${iconeDoCanal(c)} <span class="channel-name-text">${E(c.name)}</span>${lim}${cadeado}${engrenagem}</div>`;
        return `<div class="canal-bloco" data-id="${Number(c.id)}">${linha}${voz ? `<div id="voice-users-${Number(c.id)}" class="voice-users-box" style="padding-left:24px;display:none;margin-bottom:8px;"></div>` : ''}</div>`;
    }

    function htmlSeparador(c, srv, arrastavel) {
        const gerencia = pode(srv, 'gerenciar_canais');
        const acoes = gerencia ? `<span class="sep-acoes"><i class="fa-solid fa-pen sep-editar" data-id="${Number(c.id)}" title="Renomear separador"></i><i class="fa-solid fa-trash sep-apagar" data-id="${Number(c.id)}" title="Apagar separador"></i></span>` : '';
        return `<div class="sep-item ${c.name ? 'com-titulo' : ''}" data-id="${Number(c.id)}" ${arrastavel ? 'draggable="true" data-arrasta="canal"' : ''}>
                    <span class="sep-linha"></span>${c.name ? `<span class="sep-titulo">${E(c.name)}</span><span class="sep-linha"></span>` : ''}${acoes}</div>`;
    }

    function htmlGrupo(srv, g, gerencia, arrastavel, fechado) {
        const corpo = g.itens.map(c => htmlCanal(c, srv, arrastavel)).join('');
        if (g.id === 0) return `<div class="cat-bloco sem-cat" data-cat="0"><div class="cat-corpo" data-grupo="0">${corpo}</div></div>`;
        const idAttr = E(g.id);
        const acoes = gerencia ? `<span class="cat-acoes">
                <i class="fa-solid fa-plus cat-add" title="Criar canal aqui"></i>
                <i class="fa-solid fa-grip-lines cat-sep" title="Adicionar separador"></i>
                <i class="fa-solid fa-pen cat-ren" title="Renomear"></i>
                ${g.virtual ? '' : '<i class="fa-solid fa-trash cat-del" title="Apagar categoria (os canais ficam)"></i>'}</span>` : '';
        return `<div class="cat-bloco ${fechado ? 'fechada' : ''}" data-cat="${idAttr}">
                <div class="channel-category cat-cab" data-cat="${idAttr}" ${arrastavel ? 'draggable="true" data-arrasta="cat"' : ''}>
                    <i class="fa-solid fa-chevron-down cat-seta"></i> <span class="cat-nome">${E(g.nome)}</span>${acoes}</div>
                <div class="cat-corpo" data-grupo="${idAttr}">${corpo}</div></div>`;
    }

    const toqueGrosso = () => window.matchMedia('(pointer: coarse)').matches;

    /** HTML de tudo que vem DEPOIS do atalho de Eventos na barra lateral. */
    function htmlLista(srv) {
        const gerencia = pode(srv, 'gerenciar_canais'), arrastavel = gerencia && !toqueGrosso(), fch = fechadas(srv.id);
        return montarGrupos(srv).map(g => htmlGrupo(srv, g, gerencia, arrastavel, !!fch[g.id])).join('');
    }

    /** Liga cliques da lista (recolher, criar, renomear, apagar, separadores) e o arrastar. Os cliques por canal já são do chat.html (religarCanais). */
    function ligarLista(lista) {
        const srv = C.servidorAtivo();
        if (!srv) return;
        lista.querySelectorAll('.cat-cab').forEach(cab => {
            const cat = cab.dataset.cat;
            cab.addEventListener('click', (e) => {
                if (e.target.closest('.cat-acoes')) return;
                const bloco = cab.closest('.cat-bloco');
                const fechar = !bloco.classList.contains('fechada');
                bloco.classList.toggle('fechada', fechar);
                guardarFechada(srv.id, cat, fechar);
            });
            const g = montarGrupos(srv).find(x => String(x.id) === String(cat));
            cab.querySelector('.cat-add')?.addEventListener('click', (e) => {
                e.stopPropagation();
                const voz = g && g.virtual ? cat === 'padrao_voice' : (g && g.itens.length && g.itens.every(c => familia(c.type) === 'voz'));
                C.abrirCriarCanal({ tipo: voz ? 'voice' : 'text', categoria_id: g && g.virtual ? undefined : Number(cat) });
            });
            cab.querySelector('.cat-sep')?.addEventListener('click', (e) => {
                e.stopPropagation();
                C.socket.emit('criar_canal', { server_id: srv.id, nome: '', tipo: 'separador', categoria_id: cat });
            });
            cab.querySelector('.cat-ren')?.addEventListener('click', (e) => { e.stopPropagation(); renomearCategoria(srv, cat, g && g.nome); });
            cab.querySelector('.cat-del')?.addEventListener('click', (e) => { e.stopPropagation(); apagarCategoria(srv, cat, g && g.nome); });
        });
        lista.querySelectorAll('.sep-editar').forEach(b => b.addEventListener('click', (e) => { e.stopPropagation(); renomearSeparador(srv, Number(b.dataset.id)); }));
        lista.querySelectorAll('.sep-apagar').forEach(b => b.addEventListener('click', (e) => {
            e.stopPropagation();
            C.socket.emit('apagar_canal', { canal_id: Number(b.dataset.id) });
        }));
        ligarArrastar(lista);
    }

    function renomearCategoria(srv, cat, atual) {
        C.pedirTexto('Renomear categoria', atual ? `Hoje: ${atual}` : '', 'Nome da categoria', (v) => {
            v = (v || '').trim();
            if (v) C.socket.emit('categoria_renomear', { server_id: srv.id, categoria_id: cat, nome: v });
        });
    }
    function apagarCategoria(srv, cat, atual) {
        C.confirmar(`Apagar a categoria ${atual || ''}?`, 'Os canais dela não somem: ficam soltos no topo da lista.',
            () => C.socket.emit('categoria_apagar', { server_id: srv.id, categoria_id: cat }));
    }
    function renomearSeparador(srv, canalId) {
        const c = (srv.channels || []).find(x => Number(x.id) === canalId);
        C.pedirTexto('Título do separador', 'Deixe em branco pra ficar só a linha.', 'Título (opcional)',
            (v) => C.socket.emit('editar_canal', { canal_id: canalId, nome: (v || '').trim() }));
        const campo = document.getElementById('g-input-field');
        if (campo && c) campo.value = c.name || '';
    }

    /** Redesenha só a lista de canais (sem recarregar a conversa aberta), preservando o canal ativo. */
    function redesenhar(srv) {
        const barra = document.getElementById('bazinga-sidebar');
        if (!barra || !srv) return;
        const lista = barra.querySelector('.channels-list');
        const sep = lista && lista.querySelector('.atalho-sep');
        if (!sep) return;
        const rolagem = lista.scrollTop;
        while (sep.nextSibling) sep.nextSibling.remove();
        sep.insertAdjacentHTML('afterend', htmlLista(srv));
        depoisDeDesenhar(lista, srv, true);
        lista.scrollTop = rolagem;
        const ativo = String(C.canalAtualId() || '');
        const el = lista.querySelector(`.text-channel[data-id="${ativo}"]`);
        if (el) el.classList.add('active');
        else if (ativo) lista.querySelector('.text-channel')?.click();   // o canal aberto foi apagado (ou ficou escondido): cai no primeiro
        srv.channels.filter(c => familia(c.type) === 'voz').forEach(c => C.socket.emit('listar_participantes_call', { canal_id: Number(c.id) }));
    }

    function depoisDeDesenhar(lista, srv, refresh) {
        lista.classList.toggle('sem-anim', !!refresh);   // redesenho por atualização não repete a animação de entrada; trocar de servidor repete
        C.religarCanais(lista);
        ligarLista(lista);
        C.emojificar(lista);
    }

    // ---------------------------------------------------------------------
    // arrastar e soltar (computador; no celular a organização é pelas setas das Configurações)
    // ---------------------------------------------------------------------
    let arrasto = null;
    function limparIndicadores(lista) {
        lista.querySelectorAll('.drop-antes, .drop-depois, .drop-dentro').forEach(e => e.classList.remove('drop-antes', 'drop-depois', 'drop-dentro'));
    }
    function layoutDoDom(lista) {
        const categorias = [...lista.querySelectorAll('.cat-bloco[data-cat]')].map(b => b.dataset.cat).filter(c => c !== '0');
        const grupos = {};
        lista.querySelectorAll('.cat-corpo[data-grupo]').forEach(corpo => {
            grupos[corpo.dataset.grupo] = [...corpo.children].map(x => Number(x.dataset.id)).filter(Boolean);
        });
        return { categorias, grupos };
    }
    function ligarArrastar(lista) {
        if (lista.dataset.dnd === '1') return;       // a lista é a mesma entre redesenhos: liga uma vez só
        lista.dataset.dnd = '1';
        lista.addEventListener('dragstart', (e) => {
            const alvo = e.target.closest && e.target.closest('[data-arrasta]');
            if (!alvo) return;
            arrasto = { tipo: alvo.dataset.arrasta, el: alvo.closest('.canal-bloco, .sep-item, .cat-bloco') };
            if (!arrasto.el) { arrasto = null; return; }
            e.dataTransfer.effectAllowed = 'move';
            try { e.dataTransfer.setData('text/plain', 'pnt-canal'); } catch (err) { /* alguns navegadores exigem; outros não */ }
            setTimeout(() => arrasto && arrasto.el.classList.add('arrastando'), 0);
            lista.classList.add('organizando');
        });
        lista.addEventListener('dragover', (e) => {
            if (!arrasto) return;
            const alvo = destinoDoArrasto(lista, e);
            if (!alvo) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            limparIndicadores(lista);
            alvo.marca.classList.add(alvo.modo);
        });
        lista.addEventListener('drop', (e) => {
            if (!arrasto) return;
            const alvo = destinoDoArrasto(lista, e);
            if (!alvo) return;
            e.preventDefault();
            const { modo, marca, corpo } = alvo;
            if (modo === 'drop-dentro') corpo.appendChild(arrasto.el);
            else if (modo === 'drop-antes') marca.parentNode.insertBefore(arrasto.el, marca);
            else marca.parentNode.insertBefore(arrasto.el, marca.nextSibling);
            const srv = C.servidorAtivo();
            const lay = layoutDoDom(lista);
            if (srv) emitirLayout(srv, lay);
        });
        lista.addEventListener('dragend', () => {
            if (arrasto) arrasto.el.classList.remove('arrastando');
            arrasto = null;
            limparIndicadores(lista);
            lista.classList.remove('organizando');
        });
    }
    /** Onde o item cairia: { modo: 'drop-antes'|'drop-depois'|'drop-dentro', marca: elemento de referência, corpo } ou null. */
    function destinoDoArrasto(lista, e) {
        const t = e.target;
        if (!t || !t.closest) return null;
        const metade = (el) => { const r = el.getBoundingClientRect(); return e.clientY < r.top + r.height / 2 ? 'drop-antes' : 'drop-depois'; };
        if (arrasto.tipo === 'cat') {
            const bloco = t.closest('.cat-bloco:not(.sem-cat)');
            if (!bloco || bloco === arrasto.el) return null;
            return { modo: metade(bloco), marca: bloco };
        }
        const linha = t.closest('.canal-bloco, .sep-item');
        if (linha && linha !== arrasto.el && !arrasto.el.contains(linha)) return { modo: metade(linha), marca: linha };
        if (linha === arrasto.el) return null;
        const corpo = t.closest('.cat-corpo') || (t.closest('.cat-cab') && t.closest('.cat-bloco').querySelector('.cat-corpo'));
        if (corpo) return { modo: 'drop-dentro', marca: corpo, corpo };
        return null;
    }

    // ---------------------------------------------------------------------
    // modal de criar/editar canal: tipos, ícone, categoria e limite
    // ---------------------------------------------------------------------
    let modalPronto = false, modalTipoInicial = 'text';
    function prepararModal() {
        if (modalPronto) return;
        const grupo = document.getElementById('channel-type-group');
        const nomeInput = document.getElementById('channel-name-input');
        if (!grupo || !nomeInput) return;
        modalPronto = true;
        grupo.innerHTML = `<label class="bz-label">Tipo de canal</label><div class="tipo-grade" id="cx-tipos"></div>`;
        const blocoNome = nomeInput.closest('.bz-input-wrap').parentElement;
        blocoNome.insertAdjacentHTML('afterend', `
            <div class="cx-extra" id="cx-extra">
                <div id="cx-icone-box"><label class="bz-label">Ícone <span class="cx-op">(emoji, opcional)</span></label>
                    <input type="text" id="cx-icone" class="bz-input" maxlength="8" placeholder="😀" style="padding-left:12px;"></div>
                <div id="cx-cat-box"><label class="bz-label">Categoria</label>
                    <select id="cx-categoria" class="bz-input" style="padding-left:12px;"></select></div>
                <div id="cx-limite-box"><label class="bz-label">Limite de pessoas <span class="cx-op">(vazio = sem limite)</span></label>
                    <input type="number" id="cx-limite" class="bz-input" min="1" max="99" placeholder="Sem limite" style="padding-left:12px;"></div>
            </div>`);
        const rotuloNome = blocoNome.querySelector('.bz-label');
        if (rotuloNome) rotuloNome.id = 'cx-rotulo-nome';
    }

    function desenharCartasDeTipo(tipos, atual) {
        const grade = document.getElementById('cx-tipos');
        if (!grade) return;
        grade.innerHTML = tipos.map(t => {
            const i = TIPOS[t];
            return `<div class="tipo-card ${t === atual ? 'selected' : ''}" data-tipo="${t}" title="${E(i.desc)}">
                <i class="fa-solid ${i.fa}"></i><div><b>${E(i.nome)}</b><span>${E(i.desc)}</span></div></div>`;
        }).join('');
        grade.querySelectorAll('.tipo-card').forEach(card => card.addEventListener('click', () => C.selecionarTipo(card.dataset.tipo)));
    }

    /** Chamado pelo chat.html ao abrir o modal (depois dele preencher o que já fazia). */
    function preencherModal(editando, canal, dados) {
        prepararModal();
        const srv = C.servidorAtivo();
        if (!srv) return;
        const grupo = document.getElementById('channel-type-group');
        const tipos = editando ? Object.keys(TIPOS).filter(t => TIPOS[t].fam === familia(canal.type)) : Object.keys(TIPOS);
        modalTipoInicial = editando ? canal.type : (tipoValido(dados.tipo) || 'text');
        grupo.style.display = editando && tipos.length <= 1 ? 'none' : 'block';
        desenharCartasDeTipo(tipos, modalTipoInicial);
        document.getElementById('cx-icone').value = editando ? (canal.icone || '') : '';
        document.getElementById('cx-limite').value = editando && canal.limite ? canal.limite : '';
        // categoria: só quando já existem categorias de verdade (servidor antigo mostra as duas seções "virtuais")
        const sel = document.getElementById('cx-categoria');
        const cats = srv.categorias || [];
        sel.innerHTML = (editando ? '' : '<option value="auto">Automática (junto dos canais do mesmo tipo)</option>') + '<option value="0">Sem categoria</option>'
            + cats.map(k => `<option value="${Number(k.id)}">${E(k.nome)}</option>`).join('');
        sel.value = editando ? String(canal.categoria_id || 0) : (dados.categoria_id ? String(Number(dados.categoria_id)) : 'auto');
        sel.dataset.mexeu = '0';
        sel.onchange = () => { sel.dataset.mexeu = '1'; };
        aoMudarTipo(modalTipoInicial);
    }

    /** Liga/desliga os campos conforme o tipo escolhido (chamado pelo selecionarTipoCanal do chat.html). */
    function aoMudarTipo(tipo) {
        prepararModal();
        const t = TIPOS[tipo] || TIPOS.text, fam = t.fam, srv = C.servidorAtivo();
        document.querySelectorAll('#cx-tipos .tipo-card').forEach(c => c.classList.toggle('selected', c.dataset.tipo === tipo));
        const sep = fam === 'estrutura';
        document.getElementById('channel-name-prefix').textContent = sep ? '—' : (fam === 'voz' ? '🔊' : '#');
        document.getElementById('channel-modal-sub').textContent = sep ? 'uma linha na lista de canais' : (fam === 'voz' ? 'em Canais de Voz' : 'em Canais de Texto');
        document.getElementById('channel-name-input').placeholder = sep ? 'Título (opcional)' : (fam === 'voz' ? 'sala-de-voz' : 'novo-canal');
        const rot = document.getElementById('cx-rotulo-nome'); if (rot) rot.textContent = sep ? 'Título do separador' : 'Nome do canal';
        const topico = document.getElementById('channel-topic-input').parentElement;
        const privado = document.querySelector('#channel-modal .bz-switch-row');
        const membros = document.getElementById('channel-members-area');
        [topico, privado].forEach(el => { if (el) el.style.display = sep ? 'none' : ''; });
        if (membros && sep) membros.style.display = 'none';
        if (!sep) { const p = document.getElementById('channel-private-input'); if (p && membros) membros.style.display = p.checked ? 'block' : 'none'; }
        document.getElementById('cx-icone-box').style.display = sep ? 'none' : '';
        document.getElementById('cx-limite-box').style.display = fam === 'voz' ? '' : 'none';
        document.getElementById('cx-cat-box').style.display = (srv && (srv.categorias || []).length) ? '' : 'none';
    }

    /** Campos extras que o salvarCanal() junta ao pedido. */
    function camposDoModal(editando) {
        const out = {};
        const tipo = document.querySelector('#cx-tipos .tipo-card.selected')?.dataset.tipo;
        if (tipo && (!editando || tipo !== modalTipoInicial)) out.tipo = tipo;
        const sep = tipo && familia(tipo) === 'estrutura';
        if (!sep) {
            out.icone = (document.getElementById('cx-icone').value || '').trim();
            if (familia(tipo) === 'voz') out.limite = document.getElementById('cx-limite').value || 0;
        }
        const sel = document.getElementById('cx-categoria');
        if (sel && sel.parentElement.style.display !== 'none' && sel.value !== 'auto' && (!editando || sel.dataset.mexeu === '1')) out.categoria_id = Number(sel.value) || 0;
        return out;
    }

    // ---------------------------------------------------------------------
    // compositor por tipo de canal (anúncios/regras só leitura; mídia exige anexo)
    // ---------------------------------------------------------------------
    function aoAbrirCanal(canal) {
        const srv = C.servidorAtivo();
        const wrap = document.querySelector('#text-view .chat-input-wrapper');
        const campo = document.getElementById('message-input');
        if (!srv || !canal || !campo) return;
        const t = canal.type || 'text';
        const leitura = (t === 'anuncios' || t === 'regras') && !pode(srv, 'enviar_anuncios');
        campo.disabled = leitura;
        if (wrap) wrap.classList.toggle('so-leitura', leitura);
        if (leitura) campo.placeholder = t === 'regras' ? 'Este canal é só pra ler as regras' : 'Só quem tem permissão publica aqui';
        else if (t === 'midia') campo.placeholder = `Envie uma foto, vídeo ou GIF em ${canal.name} (o texto vira legenda)`;
        else campo.placeholder = `Conversar em #${canal.name}`;
        const cab = document.getElementById('current-channel-header');
        if (cab && (canal.icone || t !== 'text')) {
            const i = TIPOS[t] || TIPOS.text;
            cab.innerHTML = `${canal.icone ? `<span class="canal-emoji">${E(canal.icone)}</span>` : `<i class="fa-solid ${i.fa}" style="color:var(--text-muted);font-size:20px;"></i>`} ${E(canal.name)}`;
            C.emojificar(cab);
        }
    }
    /** O chat.html pergunta antes de enviar. Devolve false (e avisa) se este canal não aceita o que a pessoa vai mandar. */
    function podeEnviar(texto, qtdAnexos) {
        const srv = C.servidorAtivo();
        const canal = srv && (srv.channels || []).find(c => String(c.id) === String(C.canalAtualId()));
        if (!canal) return true;
        if ((canal.type === 'anuncios' || canal.type === 'regras') && !pode(srv, 'enviar_anuncios')) { C.toast('Só quem tem permissão publica nesse canal.', 'warning'); return false; }
        if (canal.type === 'midia' && !qtdAnexos) { C.toast('Esse canal é só de mídia: anexe uma foto, vídeo ou GIF.', 'warning'); return false; }
        return true;
    }
    function mensagemRecusada(d) {
        if (!d || !d.temp_id) return;
        const el = document.querySelector(`.message[data-msg-id="${String(d.temp_id).replace(/[^\w-]/g, '')}"]`);
        if (el) el.remove();
    }

    // ---------------------------------------------------------------------
    // menus (dropdown do servidor, botão direito do canal e da mensagem)
    // ---------------------------------------------------------------------
    function ajustarMenuServidor(menu, srv) {
        menu.classList.remove('nao-sou-dono');
        const mostrar = (id, ok) => { const el = document.getElementById(id); if (el) el.style.display = ok ? '' : 'none'; };
        garantirItemMenu(menu);
        mostrar('srv-menu-config', pode(srv, 'gerenciar_servidor'));
        mostrar('srv-menu-config-completa', podeGerir(srv));
        mostrar('srv-menu-new-text', pode(srv, 'gerenciar_canais'));
        mostrar('srv-menu-new-voice', pode(srv, 'gerenciar_canais'));
        mostrar('srv-menu-new-cat', pode(srv, 'gerenciar_canais'));
        menu.querySelectorAll('.context-menu-separator.owner-only').forEach(s => { s.style.display = podeGerir(srv) ? '' : 'none'; });
        const convidar = document.getElementById('srv-menu-invite'); if (convidar) convidar.style.display = pode(srv, 'criar_convite') ? '' : 'none';
    }
    function garantirItemMenu(menu) {
        if (document.getElementById('srv-menu-config-completa')) return;
        const ref = document.getElementById('srv-menu-new-voice');
        if (!ref) return;
        ref.insertAdjacentHTML('afterend', '<div class="context-menu-item" id="srv-menu-new-cat">Criar categoria <i class="fa-solid fa-folder-plus"></i></div>');
        const cfg = document.getElementById('srv-menu-config');
        cfg.insertAdjacentHTML('afterend', '<div class="context-menu-item" id="srv-menu-config-completa">Cargos e configurações completas <i class="fa-solid fa-user-shield"></i></div>');
        cfg.classList.remove('owner-only');
        ['srv-menu-new-text', 'srv-menu-new-voice'].forEach(id => document.getElementById(id)?.classList.remove('owner-only'));
        document.getElementById('srv-menu-config-completa').addEventListener('click', () => { menu.style.display = 'none'; C.abrirConfigCompleta(); });
        document.getElementById('srv-menu-new-cat').addEventListener('click', () => {
            menu.style.display = 'none';
            const srv = C.servidorAtivo();
            if (srv) C.pedirTexto('Nova categoria', 'Ela agrupa canais na lista, e dá pra recolher e arrastar.', 'Nome da categoria',
                (v) => { v = (v || '').trim(); if (v) C.socket.emit('categoria_criar', { server_id: srv.id, nome: v }); });
        });
    }
    function ajustarMenuCanal(menu, srv) {
        menu.classList.toggle('nao-sou-dono', !pode(srv, 'gerenciar_canais'));
    }
    function ajustarMenuMensagem(menu, srv, dm) {
        const fixar = document.getElementById('ctx-pin');
        if (fixar) fixar.style.display = (dm || (srv && !pode(srv, 'fixar_mensagens'))) ? 'none' : '';
    }
    function podeApagarMensagem(srv) { return pode(srv, 'apagar_mensagens'); }

    // ---------------------------------------------------------------------
    // configurações completas: abas novas e permissões por aba
    // ---------------------------------------------------------------------
    const ABAS = { perfil: 'gerenciar_servidor', canais: 'gerenciar_canais', cargos: 'gerenciar_cargos', membros: '*gestao', convites: 'gerenciar_servidor', eventos: 'gerenciar_eventos' };
    let configPronta = false, cargoSel = null;

    function prepararConfig() {
        if (configPronta) return;
        const menu = document.querySelector('#server-full-settings .sf-menu');
        const conteudo = document.querySelector('#server-full-settings .sf-conteudo');
        if (!menu || !conteudo) return;
        configPronta = true;
        const itemMembros = menu.querySelector('.sf-item[data-secao="membros"]');
        itemMembros.insertAdjacentHTML('beforebegin', '<div class="sf-item" data-secao="cargos"><i class="fa-solid fa-user-shield"></i> Cargos</div>');
        menu.querySelector('.sf-item[data-secao="cargos"]').addEventListener('click', () => C.trocarSecao('cargos'));
        const secMembros = conteudo.querySelector('.sf-secao[data-secao="membros"]');
        secMembros.insertAdjacentHTML('beforebegin', `
            <section class="sf-secao" data-secao="cargos">
                <h2>Cargos</h2>
                <p class="sf-desc">Cada cargo tem cor e permissões. Quem tem vários soma as permissões, e o de cima vale pra hierarquia: ninguém mexe em cargo do seu nível ou acima.</p>
                <div class="cg-layout">
                    <div class="cg-lista" id="cg-lista"></div>
                    <div class="cg-editor" id="cg-editor"></div>
                </div>
            </section>`);
        // Perfil: boas-vindas e banner
        const perfil = conteudo.querySelector('.sf-secao[data-secao="perfil"]');
        const salvar = perfil.querySelector('button.btn-primary');
        salvar.insertAdjacentHTML('beforebegin', `
            <div class="sf-campo"><label class="bz-label">Banner do servidor <span class="cx-op">(imagem opcional no topo da lista de canais)</span></label>
                <div class="cx-banner"><div class="cx-banner-previa" id="cx-banner-previa"></div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;"><button class="btn-cancel" id="cx-banner-escolher" type="button" style="padding:8px 12px;font-size:13px;"><i class="fa-solid fa-image"></i> Escolher imagem</button>
                <button class="btn-cancel" id="cx-banner-tirar" type="button" style="padding:8px 12px;font-size:13px;color:var(--red-color);">Remover</button></div></div></div>
            <div class="sf-campo"><label class="bz-label">Mensagem de boas-vindas <span class="cx-op">(cada pessoa vê uma vez ao abrir o servidor)</span></label>
                <textarea id="cx-bv-texto" class="bz-input" maxlength="500" rows="3" style="padding:12px;resize:vertical;font-family:inherit;" placeholder="Ex.: Bem-vindo! Leia as regras e apresente-se no #geral."></textarea></div>
            <div class="sf-campo"><label class="bz-label">Canal que abre primeiro</label>
                <select id="cx-bv-canal" class="bz-input" style="padding-left:12px;"></select></div>`);
        document.getElementById('cx-banner-escolher').addEventListener('click', () => C.escolherImagem({
            titulo: 'Banner do servidor', formato: 'faixa', sub: 'Aparece no topo da lista de canais.',
            aoArquivo: async (f) => { try { C.toast('Enviando o banner...', 'info'); bannerNovo = await C.uploadMidia(f); pintarBanner(bannerNovo); C.toast('Pronto! Clique em Salvar alterações.', 'success'); } catch (e) { C.toast(e.message || 'Não deu pra enviar.', 'error'); } },
            aoUrl: (url) => { bannerNovo = url; pintarBanner(url); C.toast('Clique em Salvar alterações.', 'info'); },
        }));
        document.getElementById('cx-banner-tirar').addEventListener('click', () => { bannerNovo = ''; pintarBanner(''); });
        // Canais: botões novos
        const secCanais = conteudo.querySelector('.sf-secao[data-secao="canais"]');
        const botoes = secCanais.querySelector('div[style*="display:flex"]');
        if (botoes) botoes.insertAdjacentHTML('beforeend', `
            <button class="btn-cancel" id="cx-nova-cat" style="font-size:13px;"><i class="fa-solid fa-folder-plus"></i> Nova categoria</button>
            <button class="btn-cancel" id="cx-novo-sep" style="font-size:13px;"><i class="fa-solid fa-grip-lines"></i> Novo separador</button>`);
        document.getElementById('cx-nova-cat')?.addEventListener('click', () => {
            const srv = C.servidorAtivo();
            C.pedirTexto('Nova categoria', 'Ela agrupa canais na lista.', 'Nome da categoria', (v) => { v = (v || '').trim(); if (v && srv) C.socket.emit('categoria_criar', { server_id: srv.id, nome: v }); });
        });
        document.getElementById('cx-novo-sep')?.addEventListener('click', () => {
            const srv = C.servidorAtivo();
            if (!srv) return;
            const cats = srv.categorias || [];
            C.socket.emit('criar_canal', { server_id: srv.id, nome: '', tipo: 'separador', categoria_id: cats.length ? cats[0].id : 'padrao_text' });
        });
    }
    let bannerNovo;      // undefined = não mexeu; '' = tirou
    function pintarBanner(url) {
        const box = document.getElementById('cx-banner-previa');
        const u = C.escUrl(url);
        if (box) { box.style.backgroundImage = u ? `url('${u}')` : ''; box.classList.toggle('vazio', !u); box.textContent = u ? '' : 'Sem banner'; }
    }

    /** Mostra só as abas que a pessoa pode usar. Devolve a 1ª dessas abas. */
    function ajustarAbas(srv) {
        const menu = document.querySelector('#server-full-settings .sf-menu');
        let primeira = null;
        menu.querySelectorAll('.sf-item[data-secao]').forEach(it => {
            const exig = ABAS[it.dataset.secao];
            const ok = exig === '*gestao' ? (pode(srv, 'expulsar') || pode(srv, 'gerenciar_cargos')) : pode(srv, exig);
            it.style.display = ok ? '' : 'none';
            if (ok && !primeira) primeira = it.dataset.secao;
        });
        const apagar = document.getElementById('sf-apagar'); if (apagar) apagar.style.display = ehDono(srv) ? '' : 'none';
        const sep = menu.querySelector('.sf-sep'); if (sep) sep.style.display = ehDono(srv) ? '' : 'none';
        return primeira || 'membros';
    }
    /** Chamado ao abrir as configurações completas: prepara as abas novas, preenche o que é novo e devolve a aba onde começar. */
    function aoAbrirConfig(srv) {
        prepararConfig();
        bannerNovo = undefined;
        preencherPerfil(srv);
        desenharCargos(srv);
        return ajustarAbas(srv);
    }
    function preencherPerfil(srv) {
        pintarBanner(srv.bannerUrl || '');
        const t = document.getElementById('cx-bv-texto'); if (t) t.value = srv.boasVindas || '';
        const sel = document.getElementById('cx-bv-canal');
        if (sel) {
            sel.innerHTML = '<option value="0">O primeiro canal de texto</option>' + (srv.channels || [])
                .filter(c => familia(c.type) === 'texto' && !c.is_private).sort(porPos)
                .map(c => `<option value="${Number(c.id)}">#${E(c.name)}</option>`).join('');
            sel.value = String(srv.canalBoasVindas || 0);
        }
    }
    /** O salvarPerfilCompleto() junta isto ao pedido. */
    function camposDoPerfil() {
        const out = {};
        const t = document.getElementById('cx-bv-texto'), sel = document.getElementById('cx-bv-canal');
        if (t) out.boas_vindas = t.value;
        if (sel) out.canal_boas_vindas_id = Number(sel.value) || 0;
        if (bannerNovo !== undefined) out.banner_url = bannerNovo;
        return out;
    }

    // ----- aba CARGOS -----
    function chipCargo(c) { return `<span class="cg-bolinha" style="background:${E(c.cor || '#99aab5')}"></span>`; }

    function desenharCargos(srv) {
        const lista = document.getElementById('cg-lista'), ed = document.getElementById('cg-editor');
        if (!lista || !ed) return;
        const roles = (srv.cargos || []).slice().sort((a, b) => b.pos - a.pos);
        const pg = pode(srv, 'gerenciar_cargos');
        const contagem = {};
        (C.membros() || []).forEach(m => (m.cargos || []).forEach(id => { contagem[id] = (contagem[id] || 0) + 1; }));
        if (cargoSel !== 'membro' && !roles.some(r => r.id === cargoSel)) cargoSel = roles.length ? roles[0].id : 'membro';
        lista.innerHTML = (pg ? '<button class="btn btn-primary cg-novo" id="cg-novo"><i class="fa-solid fa-plus"></i> Novo cargo</button>' : '')
            + roles.map((r, i) => `<div class="cg-item ${r.id === cargoSel ? 'ativo' : ''} ${editavel(srv, r) ? '' : 'travado'}" data-id="${Number(r.id)}">
                    ${chipCargo(r)}<span class="cg-nome">${E(r.nome)}</span><span class="cg-qtd">${contagem[r.id] || 0}</span>
                    ${pg && editavel(srv, r) ? `<span class="cg-setas"><i class="fa-solid fa-arrow-up ${i === 0 ? 'off' : ''}" data-sobe="${Number(r.id)}"></i><i class="fa-solid fa-arrow-down ${i === roles.length - 1 ? 'off' : ''}" data-desce="${Number(r.id)}"></i></span>` : ''}</div>`).join('')
            + `<div class="cg-item membro ${cargoSel === 'membro' ? 'ativo' : ''}" data-id="membro"><span class="cg-bolinha" style="background:#99aab5"></span><span class="cg-nome">Membro</span><span class="cg-qtd">todos</span></div>`;
        lista.querySelector('#cg-novo')?.addEventListener('click', () => C.pedirTexto('Novo cargo', 'Ele nasce no fundo da lista, sem permissões. Depois é só ajustar.', 'Nome do cargo',
            (v) => { v = (v || '').trim(); if (v) C.socket.emit('cargo_criar', { server_id: srv.id, nome: v }); }));
        lista.querySelectorAll('.cg-item').forEach(el => el.addEventListener('click', (e) => {
            if (e.target.closest('.cg-setas')) return;
            cargoSel = el.dataset.id === 'membro' ? 'membro' : Number(el.dataset.id);
            desenharCargos(srv);
        }));
        lista.querySelectorAll('[data-sobe],[data-desce]').forEach(b => b.addEventListener('click', (e) => {
            e.stopPropagation();
            if (b.classList.contains('off')) return;
            const id = Number(b.dataset.sobe || b.dataset.desce), sobe = !!b.dataset.sobe;
            const mexiveis = roles.filter(r => editavel(srv, r)).map(r => r.id);
            const i = mexiveis.indexOf(id), j = sobe ? i - 1 : i + 1;
            if (i < 0 || j < 0 || j >= mexiveis.length) return;
            [mexiveis[i], mexiveis[j]] = [mexiveis[j], mexiveis[i]];
            C.socket.emit('cargos_reordenar', { server_id: srv.id, ordem: mexiveis });
        }));
        desenharEditorDeCargo(srv, ed, roles);
    }

    function caixasDePermissao(srv, marcadas, travadoTudo, semAdmin) {
        return PERMISSOES.filter(p => !(semAdmin && p[0] === 'administrador')).map(([id, nm, desc]) => {
            const eu = ehDono(srv) || (srv.minhasPerms || []).includes(id);
            const off = travadoTudo || !eu;
            return `<label class="cg-perm ${off ? 'off' : ''}" title="${E(off && !travadoTudo ? 'Você não tem essa permissão, então não pode dá-la' : desc)}">
                <input type="checkbox" data-perm="${id}" ${marcadas.has(id) ? 'checked' : ''} ${off ? 'disabled' : ''}>
                <span><b>${E(nm)}</b><em>${E(desc)}</em></span></label>`;
        }).join('');
    }

    function desenharEditorDeCargo(srv, ed, roles) {
        const pg = pode(srv, 'gerenciar_cargos');
        if (cargoSel === 'membro') {
            const marc = new Set(srv.permsMembro || []);
            ed.innerHTML = `<h3>Membro <small>(todo mundo)</small></h3>
                <p class="sf-desc" style="margin-bottom:12px;">O que qualquer pessoa do servidor pode fazer, tenha cargo ou não. Os outros cargos somam em cima disso.</p>
                <div class="cg-perms">${caixasDePermissao(srv, marc, !pg, true)}</div>
                ${pg ? '<button class="btn btn-primary" id="cg-salvar-membro" style="margin-top:14px;">Salvar permissões de Membro</button>' : ''}`;
            ed.querySelector('#cg-salvar-membro')?.addEventListener('click', () => {
                const perms = [...ed.querySelectorAll('input[data-perm]:checked')].map(i => i.dataset.perm);
                C.socket.emit('cargo_padrao', { server_id: srv.id, permissoes: perms });
            });
            return;
        }
        const r = roles.find(x => x.id === cargoSel);
        if (!r) { ed.innerHTML = '<div class="sf-vazio">Nenhum cargo ainda. Crie o primeiro em "Novo cargo".</div>'; return; }
        const pode_editar = pg && editavel(srv, r);
        const marc = new Set(permsDoCargo(r));
        const cores = CORES.map(c => `<button type="button" class="cg-cor ${(r.cor || '') === c ? 'sel' : ''}" style="background:${c}" data-cor="${c}" ${pode_editar ? '' : 'disabled'}></button>`).join('');
        ed.innerHTML = `<h3>${chipCargo(r)} ${E(r.nome)}</h3>
            ${pode_editar ? '' : '<p class="cg-aviso"><i class="fa-solid fa-lock"></i> Cargo do seu nível ou acima: você só pode olhar.</p>'}
            <label class="bz-label">Nome</label>
            <input type="text" id="cg-nome" class="bz-input" maxlength="24" value="${E(r.nome)}" ${pode_editar ? '' : 'disabled'} style="padding-left:12px;">
            <label class="bz-label" style="margin-top:14px;">Cor do nome</label>
            <div class="cg-cores">${cores}<input type="color" id="cg-cor-livre" value="${E(r.cor || '#99aab5')}" ${pode_editar ? '' : 'disabled'} title="Outra cor">
                <button type="button" class="cg-cor semcor ${r.cor ? '' : 'sel'}" data-cor="" title="Sem cor" ${pode_editar ? '' : 'disabled'}>∅</button></div>
            <label class="cg-perm" style="margin-top:14px;"><input type="checkbox" id="cg-destacar" ${r.destacar ? 'checked' : ''} ${pode_editar ? '' : 'disabled'}>
                <span><b>Mostrar os membros deste cargo separados</b><em>Na lista de membros eles ganham um grupo com o nome do cargo.</em></span></label>
            <label class="bz-label" style="margin-top:14px;">Permissões</label>
            <div class="cg-perms">${caixasDePermissao(srv, marc, !pode_editar)}</div>
            ${pode_editar ? `<div style="display:flex;gap:10px;margin-top:16px;"><button class="btn btn-primary" id="cg-salvar">Salvar cargo</button>
                <button class="btn-cancel" id="cg-apagar" style="color:var(--red-color);">Apagar cargo</button></div>` : ''}`;
        let corAtual = r.cor || '';
        ed.querySelectorAll('.cg-cor').forEach(b => b.addEventListener('click', () => {
            corAtual = b.dataset.cor; ed.querySelectorAll('.cg-cor').forEach(x => x.classList.toggle('sel', x === b));
        }));
        ed.querySelector('#cg-cor-livre')?.addEventListener('input', (e) => { corAtual = e.target.value; ed.querySelectorAll('.cg-cor').forEach(x => x.classList.remove('sel')); });
        ed.querySelector('#cg-salvar')?.addEventListener('click', () => {
            const perms = [...ed.querySelectorAll('input[data-perm]:checked')].map(i => i.dataset.perm);
            C.socket.emit('cargo_editar', { server_id: srv.id, cargo_id: r.id, nome: ed.querySelector('#cg-nome').value, cor: corAtual,
                destacar: ed.querySelector('#cg-destacar').checked, permissoes: perms });
            C.toast('Salvando cargo...', 'info');
        });
        ed.querySelector('#cg-apagar')?.addEventListener('click', () => C.confirmar(`Apagar o cargo ${r.nome}?`,
            'Quem tem esse cargo perde as permissões dele na hora. Isso não tem volta.', () => C.socket.emit('cargo_apagar', { server_id: srv.id, cargo_id: r.id })));
    }

    // ----- aba CANAIS: categorias e canais organizados, com setas e "mover para" -----
    function desenharConfigCanais(srv, lista) {
        if (!lista || !srv) return;
        const grupos = montarGrupos(srv);
        const gerencia = pode(srv, 'gerenciar_canais');
        const opcoes = (atualId) => grupos.map(g => `<option value="${E(g.id)}" ${String(g.id) === String(atualId) ? 'selected' : ''}>${E(g.nome || 'Sem categoria')}</option>`).join('');
        const html = [];
        grupos.forEach((g, gi) => {
            if (g.id !== 0) {
                html.push(`<div class="sf-linha cx-cat-linha" data-cat="${E(g.id)}"><div class="av" style="background:rgba(255,255,255,.07);border-radius:9px;"><i class="fa-solid fa-folder" style="color:var(--text-muted);font-size:13px;"></i></div>
                    <div class="txt"><div class="nm">${E(g.nome)}</div><div class="sub">${g.itens.length} ${g.itens.length === 1 ? 'item' : 'itens'}${g.virtual ? ' · seção padrão' : ''}</div></div>
                    ${gerencia ? `<div class="acoes"><button class="sf-mini" data-cat-sobe="${E(g.id)}" ${gi === 0 || (grupos[0].id === 0 && gi === 1) ? 'disabled' : ''}>▲</button><button class="sf-mini" data-cat-desce="${E(g.id)}" ${gi === grupos.length - 1 ? 'disabled' : ''}>▼</button>
                        <button class="sf-mini" data-cat-ren="${E(g.id)}">Renomear</button>${g.virtual ? '' : `<button class="sf-mini perigo" data-cat-del="${E(g.id)}">Apagar</button>`}</div>` : ''}</div>`);
            }
            g.itens.forEach((c, ci) => {
                const t = TIPOS[c.type] || TIPOS.text;
                const sub = c.type === 'separador' ? 'Separador' : (c.topic ? c.topic : t.nome);
                html.push(`<div class="sf-linha cx-canal-linha" data-id="${Number(c.id)}" style="margin-left:${g.id === 0 ? 0 : 22}px;">
                    <div class="av" style="background:rgba(255,255,255,.07);border-radius:9px;">${c.icone ? `<span>${E(c.icone)}</span>` : `<i class="fa-solid ${t.fa}" style="color:var(--text-muted);font-size:13px;"></i>`}</div>
                    <div class="txt"><div class="nm">${E(c.name || '(separador sem título)')}</div><div class="sub">${E(sub)}</div></div>
                    ${c.is_private ? '<span class="sf-etiqueta"><i class="fa-solid fa-lock"></i> privado</span>' : ''}
                    ${gerencia ? `<div class="acoes"><button class="sf-mini" data-sobe="${Number(c.id)}" ${ci === 0 ? 'disabled' : ''}>▲</button><button class="sf-mini" data-desce="${Number(c.id)}" ${ci === g.itens.length - 1 ? 'disabled' : ''}>▼</button>
                        <select class="sf-mini cx-mover" data-mover="${Number(c.id)}" title="Mover para outra categoria">${opcoes(g.id)}</select>
                        <button class="sf-mini" data-editar="${Number(c.id)}">Editar</button></div>` : ''}</div>`);
            });
        });
        lista.innerHTML = html.length ? html.join('') : '<div class="sf-vazio">Nenhum canal ainda.</div>';
        const lay = () => layoutDoServidor(srv);
        lista.querySelectorAll('[data-sobe],[data-desce]').forEach(b => b.addEventListener('click', () => {
            const id = Number(b.dataset.sobe || b.dataset.desce), d = b.dataset.sobe ? -1 : 1, l = lay();
            for (const k of Object.keys(l.grupos)) { const a = l.grupos[k], i = a.indexOf(id); if (i >= 0 && a[i + d] !== undefined) { [a[i], a[i + d]] = [a[i + d], a[i]]; emitirLayout(srv, l); return; } }
        }));
        lista.querySelectorAll('[data-mover]').forEach(s => s.addEventListener('change', () => {
            const id = Number(s.dataset.mover), l = lay();
            for (const k of Object.keys(l.grupos)) l.grupos[k] = l.grupos[k].filter(x => x !== id);
            (l.grupos[s.value] = l.grupos[s.value] || []).push(id);
            emitirLayout(srv, l);
        }));
        lista.querySelectorAll('[data-cat-sobe],[data-cat-desce]').forEach(b => b.addEventListener('click', () => {
            const id = String(b.dataset.catSobe || b.dataset.catDesce), d = b.dataset.catSobe ? -1 : 1, l = lay();
            const cats = l.categorias.map(String), i = cats.indexOf(id);
            if (i < 0 || cats[i + d] === undefined) return;
            [cats[i], cats[i + d]] = [cats[i + d], cats[i]];
            l.categorias = cats; emitirLayout(srv, l);
        }));
        lista.querySelectorAll('[data-cat-ren]').forEach(b => b.addEventListener('click', () => { const g = grupos.find(x => String(x.id) === b.dataset.catRen); renomearCategoria(srv, b.dataset.catRen, g && g.nome); }));
        lista.querySelectorAll('[data-cat-del]').forEach(b => b.addEventListener('click', () => { const g = grupos.find(x => String(x.id) === b.dataset.catDel); apagarCategoria(srv, b.dataset.catDel, g && g.nome); }));
        lista.querySelectorAll('[data-editar]').forEach(b => b.addEventListener('click', () => {
            const c = (srv.channels || []).find(x => Number(x.id) === Number(b.dataset.editar));
            if (!c) return;
            if (c.type === 'separador') { renomearSeparador(srv, c.id); return; }
            C.fecharConfigCompleta(); C.abrirEditarCanal(c);
        }));
    }

    // ----- aba MEMBROS: cargos de cada um, remover e passar posse -----
    function desenharMembrosConfig(srv, lista) {
        if (!lista || !srv) return;
        const membros = C.membros() || [];
        const meuN = meuNivel(srv);
        const roles = (srv.cargos || []).slice().sort((a, b) => b.pos - a.pos);
        const euId = Number(C.meuId());
        lista.innerHTML = membros.map(m => {
            const av = C.escUrl(m.avatar), souEu = Number(m.id) === euId;
            const meus = (m.cargos || []).map(id => cargoPorId(srv, id)).filter(Boolean).sort((a, b) => b.pos - a.pos);
            const nivelAlvo = nivelDe(srv, m.cargos);
            const posso_cargos = pode(srv, 'gerenciar_cargos') && !m.dono && (ehDono(srv) || souEu || nivelAlvo < meuN) && roles.some(r => editavel(srv, r));
            const posso_remover = pode(srv, 'expulsar') && !m.dono && !souEu && (ehDono(srv) || nivelAlvo < meuN);
            const chips = meus.map(r => `<span class="cg-chip" style="--c:${E(r.cor || '#99aab5')}">${E(r.nome)}</span>`).join('');
            return `<div class="sf-linha" data-membro="${Number(m.id)}">
                <div class="av">${av ? `<img src="${av}">` : E((m.nome || '?')[0].toUpperCase())}</div>
                <div class="txt"><div class="nm">${E(m.nome)}${souEu ? ' <span style="color:var(--text-muted);font-weight:500;">(você)</span>' : ''}</div>
                    <div class="sub">${m.dono ? 'Dono do servidor' : (chips || 'Membro')}</div></div>
                ${m.dono ? '<span class="sf-etiqueta">👑 dono</span>' : `<div class="acoes">
                    ${posso_cargos ? `<button class="sf-mini" data-cargos="${Number(m.id)}">Cargos</button>` : ''}
                    ${ehDono(srv) && !souEu ? `<button class="sf-mini" data-posse="${Number(m.id)}" title="Passar a posse do servidor">Passar posse</button>` : ''}
                    ${posso_remover ? `<button class="sf-mini perigo" data-expulsar="${Number(m.id)}">Remover</button>` : ''}</div>`}</div>`;
        }).join('');
        lista.querySelectorAll('[data-expulsar]').forEach(b => b.addEventListener('click', () => {
            const id = Number(b.dataset.expulsar), m = membros.find(x => Number(x.id) === id);
            C.confirmar(`Remover ${m ? m.nome : 'este membro'}?`, 'A pessoa perde acesso aos canais e some do servidor. Ela pode voltar com um convite novo.',
                () => C.socket.emit('expulsar_membro', { server_id: srv.id, person_id: id }));
        }));
        lista.querySelectorAll('[data-posse]').forEach(b => b.addEventListener('click', () => {
            const id = Number(b.dataset.posse), m = membros.find(x => Number(x.id) === id);
            C.confirmar(`Passar a posse para ${m ? m.nome : 'esta pessoa'}?`, 'Ela vira dona do servidor e você vira membro comum. Só ela poderá desfazer isso.',
                () => C.socket.emit('transferir_posse', { server_id: srv.id, person_id: id }));
        }));
        lista.querySelectorAll('[data-cargos]').forEach(b => b.addEventListener('click', (e) => { e.stopPropagation(); abrirSeletorDeCargos(srv, Number(b.dataset.cargos), b); }));
    }

    function abrirSeletorDeCargos(srv, pessoaId, ancora) {
        document.getElementById('cg-pop')?.remove();
        const m = (C.membros() || []).find(x => Number(x.id) === pessoaId);
        if (!m) return;
        const roles = (srv.cargos || []).slice().sort((a, b) => b.pos - a.pos).filter(r => editavel(srv, r));
        if (!roles.length) { C.toast('Não há cargos abaixo do seu pra dar.', 'info'); return; }
        const pop = document.createElement('div');
        pop.id = 'cg-pop'; pop.className = 'cg-pop';
        pop.innerHTML = `<div class="cg-pop-t">Cargos de ${E(m.nome)}</div>` + roles.map(r => {
            const tem = (m.cargos || []).includes(r.id);
            const fora = !ehDono(srv) && permsDoCargo(r).some(p => !(srv.minhasPerms || []).includes(p));
            return `<label class="cg-pop-i ${fora ? 'off' : ''}" title="${fora ? 'Esse cargo tem permissão que você não tem' : ''}"><input type="checkbox" data-cargo="${Number(r.id)}" ${tem ? 'checked' : ''} ${fora ? 'disabled' : ''}>${chipCargo(r)} ${E(r.nome)}</label>`;
        }).join('');
        document.body.appendChild(pop);
        const r = ancora.getBoundingClientRect();
        pop.style.top = Math.min(window.innerHeight - pop.offsetHeight - 8, r.bottom + 4) + 'px';
        pop.style.left = Math.max(8, Math.min(window.innerWidth - pop.offsetWidth - 8, r.right - pop.offsetWidth)) + 'px';
        pop.querySelectorAll('input[data-cargo]').forEach(i => i.addEventListener('change', () => {
            C.socket.emit('cargo_membro', { server_id: srv.id, person_id: pessoaId, cargo_id: Number(i.dataset.cargo), ativo: i.checked });
        }));
        setTimeout(() => document.addEventListener('click', function fechar(ev) {
            if (!pop.contains(ev.target)) { pop.remove(); document.removeEventListener('click', fechar); }
        }), 0);
    }

    // ---------------------------------------------------------------------
    // lista de membros do servidor: cor do cargo mais alto e grupos de cargos "destacados"
    // ---------------------------------------------------------------------
    function cargoTopo(srv, m, soComCor) {
        let topo = null;
        (m.cargos || []).forEach(id => { const c = cargoPorId(srv, id); if (c && (!soComCor || c.cor) && (!topo || c.pos > topo.pos)) topo = c; });
        return topo;
    }
    /** Cor do nome na lista de membros (só se a pessoa não usa um estilo de nome do Armazém, que já tem a própria cor). */
    function corDoMembro(m) {
        const srv = C.servidorAtivo();
        if (!srv || m.nome_estilo) return null;
        const c = cargoTopo(srv, m, true);
        return c ? c.cor : null;
    }
    /** Devolve o HTML dos grupos por cargo destacado, ou null se não há nenhum a mostrar. */
    function agruparMembros(online, offline, linha) {
        const srv = C.servidorAtivo();
        if (!srv) return null;
        const destacados = (srv.cargos || []).filter(c => c.destacar).sort((a, b) => b.pos - a.pos);
        if (!destacados.length) return null;
        const resto = online.slice(), grupos = [];
        destacados.forEach(c => {
            const doGrupo = resto.filter(m => (m.cargos || []).includes(c.id) && !destacados.some(o => o.pos > c.pos && (m.cargos || []).includes(o.id)));
            doGrupo.forEach(m => resto.splice(resto.indexOf(m), 1));
            if (doGrupo.length) grupos.push(`<div class="channel-category" style="margin-top:12px;">${E(c.nome)} — ${doGrupo.length}</div>${doGrupo.map(linha).join('')}`);
        });
        if (!grupos.length) return null;
        return grupos.join('')
            + `<div class="channel-category" style="margin-top:12px;">ONLINE — ${resto.length}</div>` + resto.map(linha).join('')
            + (offline.length ? `<div class="channel-category" style="margin-top:14px;">OFFLINE — ${offline.length}</div>${offline.map(linha).join('')}` : '');
    }

    // ---------------------------------------------------------------------
    // boas-vindas (uma vez por texto) e canal que abre primeiro
    // ---------------------------------------------------------------------
    function resumo(s) { let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0; return (h >>> 0).toString(36); }
    function aoEntrarNoServidor(srv) {
        if (!srv || !srv.boasVindas) return;
        const chave = `pnt_bv_${srv.id}_${resumo(srv.boasVindas)}`;
        try { if (localStorage.getItem(chave)) return; localStorage.setItem(chave, '1'); } catch (e) { /* sem armazenamento: aparece de novo, sem dano */ }
        document.getElementById('cx-bv')?.remove();
        const el = document.createElement('div');
        el.id = 'cx-bv'; el.className = 'modal-overlay'; el.style.display = 'flex';
        const banner = C.escUrl(srv.bannerUrl);
        el.innerHTML = `<div class="bazinga-modal cx-bv-card" style="width:440px;">
            ${banner ? `<div class="cx-bv-banner" style="background-image:url('${banner}')"></div>` : ''}
            <div class="modal-header"><h2>Bem-vindo(a) a ${E(srv.name)}</h2></div>
            <div class="modal-content"><div class="cx-bv-texto">${E(srv.boasVindas).replace(/\n/g, '<br>')}</div></div>
            <div class="modal-footer"><button class="btn btn-primary" id="cx-bv-ok">Entendi</button></div></div>`;
        document.body.appendChild(el);
        C.emojificar(el);
        el.addEventListener('click', (e) => { if (e.target === el) el.remove(); });
        el.querySelector('#cx-bv-ok').addEventListener('click', () => el.remove());
    }
    /** Dos canais de texto da lista (elementos), o que deve abrir primeiro ao entrar no servidor. */
    function canalInicial(srv, elementos) {
        if (!srv || !srv.canalBoasVindas) return null;
        return elementos.find(el => Number(el.getAttribute('data-id')) === Number(srv.canalBoasVindas)) || null;
    }
    /** Faixa de banner no cabeçalho do servidor. */
    function pintarCabecalho(srv) {
        const cab = document.querySelector('#bazinga-sidebar .channels-header');
        if (!cab) return;
        const u = C.escUrl(srv && srv.bannerUrl);
        cab.classList.toggle('com-banner', !!u);
        cab.style.backgroundImage = u ? `linear-gradient(rgba(0,0,0,.35), rgba(0,0,0,.55)), url('${u}')` : '';
    }

    // ---------------------------------------------------------------------
    // voz: orador x ouvinte (palco e "Falar nos canais de voz")
    // ---------------------------------------------------------------------
    let papel = { canal: null, ouvinte: false };
    function receberPapel(d) {
        if (!d) return;
        const antes = papel.canal === String(d.canal_id) ? papel.ouvinte : null;
        papel = { canal: String(d.canal_id), ouvinte: !!d.ouvinte };
        if (papel.ouvinte) {
            if (C.emCall(papel.canal)) { C.travarMic(); C.toast(d.palco ? 'Você entrou como ouvinte: o microfone fica desligado até alguém te chamar pro palco.' : 'Você entrou só como ouvinte: sem a permissão de falar nesta voz.', 'info'); }
        } else if (antes === true) {
            C.toast('Você foi chamado pro palco! Pode ligar o microfone.', 'success');
        }
    }
    const micTravado = () => !!papel.ouvinte && !!papel.canal && C.emCall(papel.canal);
    /** Texto depois do nome de quem está numa voz (aparece na lista de canais): ouvinte e, se eu posso, o botão de chamar pro palco. */
    function marcaParticipante(canalId, p) {
        const srv = C.servidorAtivo();
        const canal = srv && (srv.channels || []).find(c => Number(c.id) === Number(canalId));
        if (!canal) return '';
        let out = '';
        if (p.ouvinte) out += ' <i class="fa-solid fa-ear-listen part-ouvinte" title="Ouvinte"></i>';
        else if (canal.type === 'palco') out += ' <i class="fa-solid fa-microphone-lines part-orador" title="No palco"></i>';
        if (canal.type === 'palco' && pode(srv, 'falar_palco') && Number(p.usuario_id) !== Number(C.meuId()) && p.usuario_id != null) {
            out += ` <button type="button" class="part-palco" data-palco="${Number(canalId)}:${Number(p.usuario_id)}:${p.ouvinte ? 1 : 0}" title="${p.ouvinte ? 'Chamar pro palco' : 'Mandar de volta pra plateia'}"><i class="fa-solid ${p.ouvinte ? 'fa-hand' : 'fa-arrow-down'}"></i></button>`;
        }
        return out;
    }

    // ---------------------------------------------------------------------
    // eventos do servidor
    // ---------------------------------------------------------------------
    function aoReceberEstrutura(novo) {
        if (!novo || !novo.id) return;
        C.trocarServidor(novo);
        const ativo = C.servidorAtivo();
        if (!ativo || ativo.id !== novo.id) return;
        redesenhar(novo);
        pintarCabecalho(novo);
        const canal = (novo.channels || []).find(c => String(c.id) === String(C.canalAtualId()));
        if (canal) aoAbrirCanal(canal);
        C.pedirMembros();
        if (C.configAberta()) { aoAtualizarConfig(novo); }
    }
    function aoAtualizarConfig(srv) {
        desenharCargos(srv);
        desenharConfigCanais(srv, document.getElementById('sf-lista-canais'));
        // perdi a permissão da aba onde estou? pula pra uma que eu ainda possa usar
        const ativa = document.querySelector('#server-full-settings .sf-item.ativo');
        const primeira = ajustarAbas(srv);
        if (ativa && ativa.style.display === 'none') C.trocarSecao(primeira);
    }

    function iniciar(ctx) {
        C = ctx;
        const s = C.socket;
        s.on('servidor_estrutura', aoReceberEstrutura);
        s.on('mensagem_recusada', mensagemRecusada);
        s.on('palco_papel', receberPapel);
        s.on('cargos_dos_membros_mudou', (d) => { const a = C.servidorAtivo(); if (a && d && a.id === d.server_id) C.pedirMembros(); });
        s.on('cargo_criado', (d) => { const a = C.servidorAtivo(); if (a && d && a.id === d.server_id) cargoSel = d.cargo_id; });
        s.on('entrada_call_recusada', () => { /* o texto já veio no erro_bazinga */ });
        document.addEventListener('click', (e) => {
            const b = e.target.closest && e.target.closest('[data-palco]');
            if (!b) return;
            e.stopPropagation();
            const [canal, pessoa, ouvinte] = b.dataset.palco.split(':').map(Number);
            s.emit('palco_promover', { canal_id: canal, person_id: pessoa, ativo: !!ouvinte });
        }, true);
        prepararModal();
    }

    return {
        iniciar, pode, podeGerir, ehDono, familia, tipoValido, TIPOS, PERMISSOES,
        htmlLista, depoisDeDesenhar, redesenhar, pintarCabecalho,
        preencherModal, aoMudarTipo, camposDoModal, aoAbrirCanal, podeEnviar,
        ajustarMenuServidor, ajustarMenuCanal, ajustarMenuMensagem, podeApagarMensagem,
        aoAbrirConfig, camposDoPerfil, desenharConfigCanais, desenharMembrosConfig, desenharCargos,
        corDoMembro, agruparMembros, aoEntrarNoServidor, canalInicial,
        micTravado, marcaParticipante, ehOuvinte: () => papel.ouvinte,
    };
})();
