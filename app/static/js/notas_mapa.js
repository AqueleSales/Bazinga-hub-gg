/* Respostas e reações nas notas do mapa (Rodada 29). Só desenha e conversa com o servidor: quem pode responder (todos / só amigos / desligado),
   o alcance, o bloqueio, os limites e a lista de reações são decididos e conferidos NO SERVIDOR (notas_mapa.py); o que está aqui é só aviso de interface.
   Objeto global `NotasMapa`. Contexto (NotasMapa.iniciar):
     { emitir(nome, dados), esc, toast(msg, tipo), notas() -> geoNotesAtivas, meuId(), amigos() -> [{id}], noAlcance(nota) -> true|false|null,
       fixarAberta(nota), garantirVisivel(nota), denunciar(tipo, id, texto), confirmar(titulo, texto, ok), emojificar(el), exigirLocalizacao(), abrirNota(nota), irParaMapa() }
   Estado em cada `nota` (o objeto de geoNotesAtivas): respostas [{id, autor, autor_id, texto, ha_s, t0}], reacoes [{emoji, total}], minhas [emoji], modo.
   Tudo que vem do servidor passa por esc() antes do innerHTML. Os eventos recebidos são idempotentes (a mesma resposta pode chegar por duas salas). */
const NotasMapa = (() => {
    let ctx = null;
    let reacoesPermitidas = ['❤️', '😂', '👍', '🔥', '😮', '😢'];   // o servidor manda a lista de verdade em mapa_arredores
    const LIM = 140;
    const MAX_RESPOSTAS = 30;

    const num = (v) => Number(v) || 0;
    const sou = (id) => num(id) === num(ctx.meuId());
    const ehAmigo = (id) => (ctx.amigos() || []).some((a) => num(a.id) === num(id));
    const achar = (id) => (ctx.notas() || []).find((n) => n.id === num(id));
    const elThread = (nota) => { const el = nota.marker && nota.marker.getElement && nota.marker.getElement(); return el ? el.querySelector('.nota-thread') : null; };

    function quando(r) {
        const s = Math.max(0, Math.floor((Date.now() - r.t0) / 1000));
        if (s < 45) return 'agora';
        if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min`;
        if (s < 86400) return `${Math.round(s / 3600)} h`;
        return `${Math.round(s / 86400)} d`;
    }

    // O que a interface mostra e deixa fazer. O servidor repete todas essas regras: aqui é só pra não oferecer botão que vai dar erro.
    function estado(nota) {
        const souAutor = sou(nota.autorId), amigo = ehAmigo(nota.autorId);
        if (nota.modo === 'ninguem') return { ver: false, resp: false, aviso: 'O autor desligou as respostas desta nota.' };
        if (nota.modo === 'amigos' && !souAutor && !amigo) return { ver: false, resp: false, aviso: `Só os amigos de ${nota.autor} respondem a esta nota.` };
        if (ctx.noAlcance(nota) === false) return { ver: true, resp: false, aviso: 'Chegue mais perto da nota pra responder.' };
        return { ver: true, resp: true, aviso: '' };
    }

    // ---------------------------------------------------------------------
    // DESENHO
    // ---------------------------------------------------------------------
    function pintarReacoes(nota, th) {
        const caixa = th.querySelector('.nt-reacoes');
        if (!caixa) return;
        const tot = {};
        (nota.reacoes || []).forEach((r) => { tot[r.emoji] = num(r.total); });
        const minhas = nota.minhas || [];
        caixa.innerHTML = reacoesPermitidas.map((e) => {
            const n = tot[e] || 0, minha = minhas.includes(e);
            return `<button type="button" class="nt-r${minha ? ' minha' : ''}${n ? '' : ' vazio'}" data-e="${ctx.esc(e)}" aria-pressed="${minha}" aria-label="Reagir com ${ctx.esc(e)}${n ? ' (' + n + ')' : ''}">` +
                `<span class="nt-e">${ctx.esc(e)}</span>${n ? `<b>${n}</b>` : ''}</button>`;
        }).join('');
        ctx.emojificar(caixa);
    }

    function pintarRespostas(nota, th) {
        const lista = th.querySelector('.nt-respostas');
        if (!lista) return;
        const st = estado(nota);
        const rs = st.ver ? (nota.respostas || []) : [];
        const noFim = lista.scrollHeight - lista.scrollTop - lista.clientHeight < 24;
        lista.hidden = !rs.length;
        lista.innerHTML = rs.map((r) => {
            const minha = sou(r.autor_id), autor = num(r.autor_id) === num(nota.autorId), amigo = !minha && ehAmigo(r.autor_id);
            const apagar = minha || sou(nota.autorId);
            return `<div class="nt-resp${amigo ? ' amigo' : ''}${minha ? ' minha' : ''}" role="listitem" data-id="${num(r.id)}">` +
                `<div class="nt-cab"><span class="nt-nome">${ctx.esc(r.autor)}</span>` +
                `${autor ? '<span class="nt-tag" title="Quem deixou a nota">autor</span>' : ''}` +
                `${amigo ? '<i class="fa-solid fa-user-group nt-amigo" title="Amigo" aria-label="Amigo"></i>' : ''}` +
                `<span class="nt-quando">${ctx.esc(quando(r))}</span>` +
                `${apagar ? `<button type="button" class="nt-bt" data-a="apagar" title="Apagar esta resposta" aria-label="Apagar esta resposta"><i class="fa-solid fa-xmark"></i></button>` : ''}` +
                `${!minha ? `<button type="button" class="nt-bt" data-a="denunciar" title="Denunciar esta resposta" aria-label="Denunciar esta resposta"><i class="fa-solid fa-flag"></i></button>` : ''}` +
                `</div><div class="nt-txt">${ctx.esc(r.texto)}</div></div>`;
        }).join('');
        ctx.emojificar(lista);
        if (noFim) lista.scrollTop = lista.scrollHeight;
    }

    function pintarForm(nota, th) {
        const st = estado(nota);
        const form = th.querySelector('.nt-form'), aviso = th.querySelector('.nt-aviso');
        form.hidden = !st.resp;
        aviso.hidden = !st.aviso;
        aviso.innerHTML = st.aviso ? `<i class="fa-solid fa-lock" aria-hidden="true"></i> ${ctx.esc(st.aviso)}` : '';
        const cont = th.querySelector('.nt-cont');
        if (cont) cont.textContent = `${nota.respostas.length}/${MAX_RESPOSTAS}`;
    }

    function pintar(nota) {
        const th = elThread(nota);
        if (!th || !th.dataset.pronto) return;
        // A conversa ocupa a largura inteira do balão (por baixo do emoji também): senão as 6 reações quebram em duas linhas.
        const em = th.parentElement && th.parentElement.parentElement && th.parentElement.parentElement.querySelector('.note-emoji');
        if (em && em.offsetWidth) th.style.marginLeft = `-${em.offsetWidth + 10}px`;
        pintarReacoes(nota, th);
        pintarRespostas(nota, th);
        pintarForm(nota, th);
    }

    function esqueleto() { return '<div class="nota-thread"></div>'; }

    // ---------------------------------------------------------------------
    // LIGAÇÃO (uma vez por balão desenhado; o balão é refeito quando a nota é editada)
    // ---------------------------------------------------------------------
    function montar(nota) {
        const th = elThread(nota);
        if (!th) return;
        nota.respostas = nota.respostas || [];
        nota.reacoes = nota.reacoes || [];
        nota.minhas = nota.minhas || [];
        nota.modo = nota.modo || 'todos';
        nota.respostas.forEach((r) => { if (!r.t0) r.t0 = Date.now() - num(r.ha_s) * 1000; });
        th.dataset.pronto = '1';
        th.innerHTML =
            '<div class="nt-reacoes" role="group" aria-label="Reações à nota"></div>' +
            '<div class="nt-respostas" role="list" aria-live="polite" aria-label="Respostas"></div>' +
            `<form class="nt-form" autocomplete="off"><input type="text" maxlength="${LIM}" placeholder="Responder…" aria-label="Responder à nota" enterkeyhint="send">` +
            '<button type="submit" class="nt-envia" title="Enviar resposta" aria-label="Enviar resposta"><i class="fa-solid fa-paper-plane"></i></button></form>' +
            '<div class="nt-aviso" role="note"></div>';
        if (window.L) {
            L.DomEvent.disableClickPropagation(th);
            L.DomEvent.disableScrollPropagation(th.querySelector('.nt-respostas'));
        }
        // Teclado dentro do balão não pode virar atalho do mapa nem "clique" do marcador (o Leaflet trata Enter no ícone como clique).
        ['keydown', 'keypress', 'keyup'].forEach((t) => th.addEventListener(t, (e) => e.stopPropagation()));
        const input = th.querySelector('.nt-form input');
        input.addEventListener('focus', () => ctx.fixarAberta(nota));
        th.addEventListener('click', (e) => {
            const r = e.target.closest('.nt-r');
            if (r) { reagir(nota, r.dataset.e); return; }
            const b = e.target.closest('.nt-bt');
            if (!b) return;
            const linha = b.closest('.nt-resp'), rid = linha ? num(linha.dataset.id) : 0;
            const resp = nota.respostas.find((x) => x.id === rid);
            if (!resp) return;
            if (b.dataset.a === 'apagar') ctx.emitir('geonote_resposta_apagar', { id: rid });
            else if (b.dataset.a === 'denunciar') ctx.denunciar('resposta', rid, resp.texto);
        });
        th.querySelector('.nt-form').addEventListener('submit', (e) => { e.preventDefault(); responder(nota, th); });
        pintar(nota);
    }

    function responder(nota, th) {
        const input = th.querySelector('.nt-form input');
        const texto = input.value.replace(/\s+/g, ' ').trim();
        if (!texto || nota.enviando) return;
        if (!ctx.exigirLocalizacao()) return;
        if (estado(nota).resp !== true) { pintar(nota); return; }
        nota.enviando = true;
        input.readOnly = true;
        th.classList.add('enviando');
        ctx.emitir('geonote_responder', { id: nota.id, texto });
        clearTimeout(nota._timerEnvio);
        nota._timerEnvio = setTimeout(() => liberarForm(nota), 6000);   // sem resposta do servidor: devolve o campo (o texto fica)
    }

    function liberarForm(nota, limpar) {
        nota.enviando = false;
        clearTimeout(nota._timerEnvio);
        const th = elThread(nota);
        if (!th) return;
        th.classList.remove('enviando');
        const input = th.querySelector('.nt-form input');
        if (!input) return;
        input.readOnly = false;
        if (limpar) input.value = '';
    }

    function reagir(nota, emoji) {
        if (!emoji || !ctx.exigirLocalizacao()) return;
        const ativo = !(nota.minhas || []).includes(emoji);
        // Otimista: muda na hora; o servidor corrige (evento geonote_reacoes) ou desfaz (geonote_erro).
        nota._antes = { reacoes: JSON.parse(JSON.stringify(nota.reacoes || [])), minhas: (nota.minhas || []).slice() };
        const r = (nota.reacoes || []).find((x) => x.emoji === emoji);
        if (ativo) {
            nota.minhas = (nota.minhas || []).concat(emoji);
            if (r) r.total = num(r.total) + 1; else (nota.reacoes = nota.reacoes || []).push({ emoji, total: 1 });
        } else {
            nota.minhas = (nota.minhas || []).filter((e) => e !== emoji);
            if (r) { r.total = Math.max(0, num(r.total) - 1); if (!r.total) nota.reacoes = nota.reacoes.filter((x) => x !== r); }
        }
        pintar(nota);
        ctx.emitir('geonote_reagir', { id: nota.id, emoji, ativo });
    }

    // ---------------------------------------------------------------------
    // O QUE CHEGA DO SERVIDOR
    // ---------------------------------------------------------------------
    function receberResposta(d) {
        const nota = achar(d && d.note_id);
        if (!nota || !d.resposta) return;
        const r = d.resposta;
        if (sou(r.autor_id)) liberarForm(nota, true);
        nota.respostas = nota.respostas || [];
        if (nota.respostas.some((x) => x.id === r.id)) return;
        r.t0 = Date.now() - num(r.ha_s) * 1000;
        nota.respostas.push(r);
        nota.respostas.sort((a, b) => a.id - b.id);
        if (nota.respostas.length > MAX_RESPOSTAS) nota.respostas = nota.respostas.slice(-MAX_RESPOSTAS);
        pintar(nota);
        const th = elThread(nota), lista = th && th.querySelector('.nt-respostas');
        if (lista) lista.scrollTop = lista.scrollHeight;
        // Resposta de outra pessoa na MINHA nota: avisa e abre o balão um instante.
        if (sou(nota.autorId) && !sou(r.autor_id)) {
            ctx.toast(`${r.autor} respondeu sua nota.`, 'info');
            ctx.abrirNota(nota);
        }
    }

    function receberReacoes(d) {
        const nota = achar(d && d.id);
        if (!nota) return;
        nota.reacoes = Array.isArray(d.reacoes) ? d.reacoes : [];
        if (Array.isArray(d.minhas)) nota.minhas = d.minhas;   // só vem pras abas de quem reagiu
        nota._antes = null;
        pintar(nota);
    }

    function respostaApagada(d) {
        if (!d) return;
        const alvo = d.note_id != null ? [achar(d.note_id)] : (ctx.notas() || []);
        alvo.forEach((nota) => {
            if (!nota || !(nota.respostas || []).some((x) => x.id === num(d.id))) return;
            nota.respostas = nota.respostas.filter((x) => x.id !== num(d.id));
            pintar(nota);
        });
    }

    function erro(d) {
        const nota = d && d.id != null ? achar(d.id) : null;
        if (nota) {
            liberarForm(nota);
            if (nota._antes) { nota.reacoes = nota._antes.reacoes; nota.minhas = nota._antes.minhas; nota._antes = null; pintar(nota); }
        }
        ctx.toast((d && d.msg) || 'Não deu certo.', 'warning');
    }

    // O mapa chegou de novo (andou 150 m, reconectou): o servidor é a verdade. Só repinta se algo mudou.
    function sincronizar(nota, n) {
        const antes = JSON.stringify([nota.respostas, nota.reacoes, nota.minhas, nota.modo]);
        nota.modo = n.respostas_modo || 'todos';
        nota.respostas = (n.respostas || []).map((r) => Object.assign({ t0: Date.now() - num(r.ha_s) * 1000 }, r));
        nota.reacoes = n.reacoes || [];
        nota.minhas = n.minhas || [];
        if (JSON.stringify([nota.respostas, nota.reacoes, nota.minhas, nota.modo]) !== antes) pintar(nota);
    }

    function definirReacoes(lista) {
        if (Array.isArray(lista) && lista.length) reacoesPermitidas = lista.slice(0, 12).map(String);
    }

    // Clicou no aviso "fulano respondeu à sua nota": leva até a nota (se ela está no alcance do mapa agora).
    function abrirDaNotificacao(id) {
        ctx.irParaMapa();
        setTimeout(() => {
            const nota = achar(id);
            if (!nota) { ctx.toast('Essa nota não está no seu alcance agora (ou já venceu).', 'info'); return; }
            ctx.abrirNota(nota, true);
        }, 250);
    }

    function iniciar(contexto) { ctx = contexto; }

    return { iniciar, esqueleto, montar, pintar, sincronizar, receberResposta, receberReacoes, respostaApagada, erro, definirReacoes, abrirDaNotificacao };
})();
