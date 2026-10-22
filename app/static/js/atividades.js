/* Atividades da call (Rodada 34): jogos leves que duas pessoas jogam DENTRO da call enquanto o resto assiste.
   Hoje: xadrez. O servidor (app/atividades.py) é quem decide se um lance vale; aqui só desenhamos e pedimos.
   O chess.js (CDN, versão fixa e SRI) só ajuda a mostrar os lances possíveis e a escrever a notação: se não carregar, o
   tabuleiro continua funcionando e o servidor continua recusando lance ilegal.
   Para criar outra atividade: um tipo novo em atividades.TIPOS_ATIVIDADE (python), um cartão em CATALOGO e uma função que
   desenhe o corpo do painel (hoje `desenharXadrez`). Reprodutor de música e bots já aparecem como "em breve". */
const Atividades = (function () {
    'use strict';
    let ctx = null;
    let estado = null;          // último estado vindo do servidor (null = nenhuma atividade na call)
    let chess = null;           // instância do chess.js com a posição do estado (ou null)
    let sans = [];              // notação (e4, Nf3...) dos lances do estado
    let sansDe = '';            // chave dos lances que geraram `sans`
    let selecionada = null, destinos = null;
    let virado = false;         // quem assiste pode virar o tabuleiro
    let painel = null, seletor = null, chip = null;
    let escondidoPorMim = null; // id da atividade que eu fechei só pra mim
    let promocao = null;        // {de, para} esperando a escolha da peça
    let pendente = false;       // lance enviado, esperando o servidor confirmar
    let carregandoChess = false;

    const CATALOGO = [
        { tipo: 'xadrez', nome: 'Xadrez', icone: 'chess', desc: 'Duas pessoas da call jogam; todo mundo assiste.', pronto: true },
        { tipo: 'musica', nome: 'Música na call', icone: 'music', desc: 'Todo mundo ouvindo a mesma playlist, sincronizado.', pronto: false },
        { tipo: 'bots', nome: 'Bots', icone: 'robot', desc: 'Dados, trívia e outros ajudantes pra animar a call.', pronto: false },
    ];
    const ICONES = { chess: 'fa-chess-knight', music: 'fa-music', robot: 'fa-robot' };

    // Peças: usamos as formas cheias (♚♛♜♝♞♟) nas duas cores; a cor vem do CSS. O ︎ impede o emoji colorido.
    const GLIFO = { k: '♚', q: '♛', r: '♜', b: '♝', n: '♞', p: '♟︎' };
    const MOTIVO = {
        xequemate: 'Xeque-mate', desistencia: 'Desistência', acordo: 'Empate por acordo', afogamento: 'Empate por afogamento (rei sem lances)',
        material: 'Empate: não há peças suficientes pra dar mate', repeticao: 'Empate por repetição de posição', cinquenta: 'Empate pela regra dos 50 lances',
    };
    const FILES = 'abcdefgh';

    function $(id) { return document.getElementById(id); }
    function esc(v) { return ctx.esc(v); }
    const meuId = () => Number(ctx.meuId());
    function meuLado() {
        if (!estado) return null;
        const j = estado.jogadores;
        if (j.w && Number(j.w.id) === meuId()) return 'w';
        if (j.b && Number(j.b.id) === meuId()) return 'b';
        return null;
    }
    function nomeDoLado(l) { const j = estado && estado.jogadores[l]; return j ? j.nome : (l === 'w' ? 'Brancas' : 'Pretas'); }

    // =============================================================================================================
    // Seletor
    // =============================================================================================================
    function abrirSeletor() {
        if (!ctx.emCall()) { ctx.toast('Entre numa call pra começar uma atividade.', 'info'); return; }
        if (!seletor) {
            seletor = document.createElement('div');
            seletor.className = 'at-modal'; seletor.id = 'at-seletor';
            seletor.addEventListener('mousedown', (e) => { if (e.target === seletor) fecharSeletor(); });
            seletor.addEventListener('click', (e) => {
                const b = e.target.closest('[data-at]');
                if (!b) return;
                const a = b.dataset.at;
                if (a === 'fechar') fecharSeletor();
                else if (a === 'iniciar') { ctx.emitir('atividade_iniciar', { canal_id: ctx.canalId(), tipo: b.dataset.tipo }); fecharSeletor(); escondidoPorMim = null; }
                else if (a === 'abrir') { fecharSeletor(); escondidoPorMim = null; mostrarPainel(true); }
                else if (a === 'encerrar') { fecharSeletor(); confirmarEncerrar(); }
            });
            document.body.appendChild(seletor);
        }
        pintarSeletor();
        seletor.classList.add('aberto');
        const primeiro = seletor.querySelector('button:not([disabled])');
        if (primeiro) setTimeout(() => primeiro.focus(), 30);
    }
    function fecharSeletor() { if (seletor) seletor.classList.remove('aberto'); }
    function pintarSeletor() {
        if (!seletor) return;
        const emAndamento = estado ? CATALOGO.find((c) => c.tipo === estado.tipo) : null;
        seletor.innerHTML = `<div class="at-card" role="dialog" aria-modal="true" aria-label="Atividades">
            <div class="at-topo"><h3>Atividades</h3><button type="button" data-at="fechar" title="Fechar" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button></div>
            <p class="at-sub">Coisas pra fazer juntos enquanto vocês conversam na call.</p>
            ${emAndamento ? `<div class="at-andamento"><i class="fa-solid ${ICONES[emAndamento.icone]}"></i><div><b>${esc(emAndamento.nome)} em andamento</b><small>${resumoEstado()}</small></div>
                <button type="button" data-at="abrir">Abrir</button><button type="button" class="sec" data-at="encerrar">Encerrar</button></div>` : ''}
            <div class="at-grade">${CATALOGO.map((c) => `<div class="at-op${c.pronto ? '' : ' breve'}">
                <div class="at-ic"><i class="fa-solid ${ICONES[c.icone]}"></i></div>
                <div class="at-txt"><b>${esc(c.nome)}</b><small>${esc(c.desc)}</small></div>
                ${c.pronto ? `<button type="button" data-at="iniciar" data-tipo="${c.tipo}"${estado ? ' disabled title="Já tem uma atividade na call"' : ''}>Começar</button>` : '<span class="em-breve">Em breve</span>'}</div>`).join('')}</div>
            </div>`;
    }
    function resumoEstado() {
        if (!estado) return '';
        const j = estado.jogadores;
        if (estado.situacao === 'aguardando') return 'Esperando o segundo jogador sentar.';
        if (estado.situacao === 'fim') return 'Partida terminada.';
        return `${esc(j.w ? j.w.nome : '?')} (brancas) × ${esc(j.b ? j.b.nome : '?')} (pretas)`;
    }
    function confirmarEncerrar() {
        ctx.confirmar('Encerrar a atividade?', 'Ela fecha pra todo mundo da call.', () => ctx.emitir('atividade_encerrar', { canal_id: ctx.canalId() }));
    }

    // =============================================================================================================
    // Painel flutuante
    // =============================================================================================================
    const CH_POS = 'pnt_at_pos';
    function criarPainel() {
        painel = document.createElement('div');
        painel.className = 'at-painel'; painel.id = 'at-painel'; painel.hidden = true;
        painel.setAttribute('role', 'dialog'); painel.setAttribute('aria-label', 'Atividade da call');
        painel.innerHTML = `<div class="at-p-topo" id="at-p-topo"><i class="fa-solid fa-chess-knight"></i><b>Xadrez</b><span class="at-esp"></span>
                <button type="button" data-p="virar" title="Virar o tabuleiro" aria-label="Virar o tabuleiro"><i class="fa-solid fa-rotate"></i></button>
                <button type="button" data-p="esconder" title="Esconder só pra mim (continua rolando)" aria-label="Esconder só pra mim"><i class="fa-solid fa-window-minimize"></i></button>
                <button type="button" data-p="encerrar" title="Encerrar a atividade pra todos" aria-label="Encerrar a atividade"><i class="fa-solid fa-xmark"></i></button></div>
            <div class="at-p-corpo" id="at-p-corpo"></div>`;
        document.body.appendChild(painel);
        painel.addEventListener('click', aoClicarPainel);
        // arrastar pelo topo
        let arr = null;
        const topo = painel.querySelector('#at-p-topo');
        topo.addEventListener('pointerdown', (e) => {
            if (e.target.closest('button')) return;
            const r = painel.getBoundingClientRect();
            arr = { dx: e.clientX - r.left, dy: e.clientY - r.top };
            try { topo.setPointerCapture(e.pointerId); } catch (er) {}
        });
        topo.addEventListener('pointermove', (e) => {
            if (!arr) return;
            const x = Math.min(innerWidth - 80, Math.max(-200, e.clientX - arr.dx)), y = Math.min(innerHeight - 50, Math.max(0, e.clientY - arr.dy));
            painel.style.left = x + 'px'; painel.style.top = y + 'px'; painel.style.right = 'auto'; painel.style.bottom = 'auto';
        });
        topo.addEventListener('pointerup', () => {
            if (!arr) return; arr = null;
            try { localStorage.setItem(CH_POS, JSON.stringify({ x: parseFloat(painel.style.left), y: parseFloat(painel.style.top) })); } catch (e) {}
        });
        // clicar no tabuleiro: delegado
        painel.addEventListener('click', aoClicarTabuleiro);
    }
    function posicionarPainel() {
        let pos = null;
        try { pos = JSON.parse(localStorage.getItem(CH_POS) || 'null'); } catch (e) {}
        const w = painel.offsetWidth || 400, h = painel.offsetHeight || 560;
        let x = pos && isFinite(pos.x) ? pos.x : Math.max(12, (innerWidth - w) / 2);
        let y = pos && isFinite(pos.y) ? pos.y : Math.max(12, (innerHeight - h) / 2 - 20);
        x = Math.min(Math.max(-w + 80, x), innerWidth - 80); y = Math.min(Math.max(0, y), Math.max(0, innerHeight - 60));
        painel.style.left = x + 'px'; painel.style.top = y + 'px';
    }
    function mostrarPainel(v) {
        if (!painel) criarPainel();
        if (v && !estado) return;
        const ja = !painel.hidden;
        painel.hidden = !v;
        if (v) { desenhar(); if (!ja) posicionarPainel(); }
        pintarChip();
    }
    function aoClicarPainel(e) {
        const b = e.target.closest('button[data-p]');
        if (!b) return;
        const a = b.dataset.p;
        if (a === 'virar') { virado = !virado; desenhar(); }
        else if (a === 'esconder') { escondidoPorMim = estado && estado.id; mostrarPainel(false); }
        else if (a === 'encerrar') confirmarEncerrar();
    }

    // chip na barra de cima da janela da call: reabre o painel
    function pintarChip() {
        if (!ctx) return;
        const topo = $('cj-topo');
        if (!topo) return;
        if (!estado) { if (chip) { chip.remove(); chip = null; } return; }
        if (!chip) {
            chip = document.createElement('button');
            chip.type = 'button'; chip.id = 'at-chip'; chip.className = 'at-chip';
            chip.addEventListener('click', () => { escondidoPorMim = null; mostrarPainel(painel ? painel.hidden : true); });
            const alvo = $('cj-expandir');
            topo.insertBefore(chip, alvo || null);
        }
        const visivel = painel && !painel.hidden;
        chip.innerHTML = '<i class="fa-solid fa-chess-knight"></i><span>Xadrez</span>';
        chip.title = visivel ? 'Esconder o xadrez' : 'Mostrar o xadrez';
        chip.classList.toggle('vez', !!(estado && estado.situacao === 'jogando' && meuLado() && estado.vez === meuLado()));
    }

    // =============================================================================================================
    // Estado vindo do servidor
    // =============================================================================================================
    function aoEstado(d) {
        if (!d || String(d.canal_id) !== String(ctx.canalId())) return;
        if (!d.ativa) {
            const tinha = !!estado;
            estado = null; chess = null; sans = []; sansDe = ''; selecionada = destinos = promocao = null; pendente = false; escondidoPorMim = null;
            if (painel) painel.hidden = true;
            pintarChip(); pintarSeletor();
            if (tinha) ctx.toast('A atividade terminou.', 'info');
            return;
        }
        if (estado && d.id === estado.id && d.seq < estado.seq) return;       // estado mais velho que o que já tenho
        const nova = !estado || estado.id !== d.id;
        const antes = estado;
        estado = d;
        pendente = false; selecionada = destinos = promocao = null;
        sincronizarChess();
        if (nova) { virado = false; escondidoPorMim = null; }
        // o painel abre sozinho pra todo mundo da call quando a atividade começa (quem fechou só pra si, não é incomodado de novo)
        if (escondidoPorMim !== d.id) mostrarPainel(true); else pintarChip();
        // o adversário jogou e agora é a minha vez: um bipe discreto
        if (antes && antes.id === d.id && d.lances.length > antes.lances.length && d.vez === meuLado() && d.situacao === 'jogando') { try { ctx.som('msg'); } catch (e) {} }
        pintarSeletor();
    }

    function carregarChess() {
        if (window.Chess || carregandoChess) return;
        carregandoChess = true;
        Promise.resolve(ctx.carregarChess()).then(() => { carregandoChess = false; sincronizarChess(); if (painel && !painel.hidden) desenhar(); })
            .catch(() => { carregandoChess = false; ctx.toast('Não consegui carregar o tabuleiro inteligente. Dá pra jogar, mas sem a ajuda dos lances possíveis.', 'warning'); });
    }
    function sincronizarChess() {
        if (!estado) return;
        if (!window.Chess) { chess = null; carregarChess(); return; }
        try { chess = new window.Chess(estado.fen); } catch (e) { chess = null; }
        const chave = estado.id + ':' + estado.lances.join(',');
        if (chave !== sansDe) {
            sansDe = chave;
            sans = [];
            try {
                const h = new window.Chess();
                estado.lances.forEach((l) => { const m = h.move({ from: l.slice(0, 2), to: l.slice(2, 4), promotion: l[4] }); sans.push(m ? m.san : l); });
            } catch (e) { sans = estado.lances.slice(); }
        }
    }

    // =============================================================================================================
    // Desenho
    // =============================================================================================================
    function jogador(l, emBaixo) {
        const j = estado.jogadores[l];
        const av = j ? ctx.escUrl(j.avatar) : '';
        const vez = estado.situacao === 'jogando' && estado.vez === l;
        return `<div class="at-j${vez ? ' vez' : ''}${j && j.presente === false ? ' ausente' : ''}">
            <div class="at-av">${j ? (av ? `<img src="${av}" alt="">` : esc(String(j.nome || '?')[0].toUpperCase())) : '<i class="fa-solid fa-chair"></i>'}</div>
            <div class="at-jn"><b>${j ? esc(j.nome) : 'Cadeira livre'}</b><small>${l === 'w' ? 'Brancas' : 'Pretas'}${j && j.presente === false ? ' · saiu da call' : ''}${vez ? ' · jogando agora' : ''}</small></div>
            ${!j && !meuLado() && estado.situacao === 'aguardando' ? `<button type="button" data-t="sentar" data-lado="${l}">Sentar aqui</button>` : ''}
        </div>`;
    }

    function textoResultado() {
        const r = estado.resultado;
        if (!r) return '';
        if (r.vencedor) return `${esc(nomeDoLado(r.vencedor))} venceu — ${MOTIVO[r.motivo] ? MOTIVO[r.motivo].toLowerCase() : esc(r.motivo)}.`;
        return MOTIVO[r.motivo] || 'Empate.';
    }

    function tabuleiroHtml() {
        const orient = meuLado() === 'b' ? 'b' : 'w';
        const lado = virado ? (orient === 'w' ? 'b' : 'w') : orient;
        const pecas = {};
        const linhas = estado.fen.split(' ')[0].split('/');
        linhas.forEach((ln, i) => {
            let f = 0;
            for (const ch of ln) {
                if (/\d/.test(ch)) f += Number(ch); else { pecas[FILES[f] + (8 - i)] = ch; f++; }
            }
        });
        let reiEmXeque = null;
        if (estado.xeque) { const r = estado.vez === 'w' ? 'K' : 'k'; reiEmXeque = Object.keys(pecas).find((k) => pecas[k] === r) || null; }
        const ult = estado.ultimo || [];
        let html = '';
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                const rank = lado === 'w' ? 8 - r : r + 1;
                const file = lado === 'w' ? c : 7 - c;
                const sq = FILES[file] + rank;
                const clara = (file + rank) % 2 === 1;
                const p = pecas[sq];
                const cls = ['at-sq', clara ? 'clara' : 'escura'];
                if (selecionada === sq) cls.push('sel');
                if (ult.includes(sq)) cls.push('ult');
                if (reiEmXeque === sq) cls.push('xeq');
                const dest = destinos && destinos.find((m) => m.to === sq);
                if (dest) cls.push(p || (dest.flags && dest.flags.includes('e')) ? 'dest-cap' : 'dest');
                html += `<div class="${cls.join(' ')}" data-sq="${sq}" role="gridcell" aria-label="${sq}${p ? ' ' + p : ''}">`
                    + (c === 0 ? `<i class="at-rk">${rank}</i>` : '') + (r === 7 ? `<i class="at-fl">${FILES[file]}</i>` : '')
                    + (p ? `<span class="at-p ${p === p.toUpperCase() ? 'b' : 'p'}">${GLIFO[p.toLowerCase()]}</span>` : '') + '</div>';
            }
        }
        return { html, lado };
    }

    function listaDeLances() {
        const lista = sans.length ? sans : (estado.lances || []);
        if (!lista.length) return '<div class="at-vazio">Os lances aparecem aqui.</div>';
        let s = '';
        for (let i = 0; i < lista.length; i += 2) {
            s += `<div class="at-l"><i>${i / 2 + 1}.</i><span>${esc(lista[i])}</span><span>${lista[i + 1] ? esc(lista[i + 1]) : ''}</span></div>`;
        }
        return s;
    }

    function acoes() {
        const eu = meuLado();
        const e = estado;
        let h = '';
        if (e.situacao === 'aguardando') {
            if (eu) h += '<button type="button" class="sec" data-t="sair">Levantar da cadeira</button>';
            else if (!e.jogadores.w || !e.jogadores.b) h += '<button type="button" data-t="sentar" data-lado="qualquer">Jogar também</button>';
        } else if (e.situacao === 'jogando' && eu) {
            if (e.empate_de && e.empate_de !== eu) h += '<button type="button" data-t="empate_aceitar">Aceitar empate</button><button type="button" class="sec" data-t="empate_recusar">Recusar</button>';
            else if (e.empate_de === eu) h += '<span class="at-nota">Empate proposto…</span>';
            else h += '<button type="button" class="sec" data-t="empate">Propor empate</button>';
            h += '<button type="button" class="perigo" data-t="desistir">Desistir</button>';
        } else if (e.situacao === 'fim' && eu) {
            h += '<button type="button" data-t="revanche">Revanche (troca as cores)</button>';
        }
        return h;
    }

    function desenhar() {
        if (!painel || painel.hidden || !estado) return;
        const corpo = $('at-p-corpo');
        const eu = meuLado();
        const orient = eu === 'b' ? 'b' : 'w';
        const lado = virado ? (orient === 'w' ? 'b' : 'w') : orient;
        const t = tabuleiroHtml();
        const emCima = lado === 'w' ? 'b' : 'w', emBaixo = lado;
        let banner = '';
        if (estado.situacao === 'fim') banner = `<div class="at-banner fim"><i class="fa-solid fa-flag-checkered"></i>${textoResultado()}</div>`;
        else if (estado.situacao === 'aguardando') banner = `<div class="at-banner"><i class="fa-solid fa-hourglass-half"></i>${eu ? 'Esperando mais um jogador sentar. Quem está na call pode entrar na cadeira livre.' : 'Esperando os dois jogadores sentarem.'}</div>`;
        else if (estado.xeque) banner = '<div class="at-banner xeq"><i class="fa-solid fa-triangle-exclamation"></i>Xeque!</div>';
        else if (eu && estado.vez === eu) banner = '<div class="at-banner vez"><i class="fa-solid fa-hand-pointer"></i>Sua vez.</div>';
        else if (!eu) banner = '<div class="at-banner"><i class="fa-solid fa-eye"></i>Você está assistindo.</div>';
        else banner = '<div class="at-banner"><i class="fa-solid fa-hourglass-half"></i>Vez de quem joga do outro lado…</div>';
        corpo.innerHTML = `${jogador(emCima)}
            <div class="at-tab${pendente ? ' pendente' : ''}" role="grid" aria-label="Tabuleiro de xadrez">${t.html}</div>
            ${jogador(emBaixo)}
            ${banner}
            <div class="at-acoes">${acoes()}</div>
            <details class="at-lances"${estado.lances.length ? ' open' : ''}><summary>Lances (${estado.lances.length})</summary><div class="at-lista">${listaDeLances()}</div></details>
            ${promocao ? promocaoHtml() : ''}`;
        const lista = corpo.querySelector('.at-lista');
        if (lista) lista.scrollTop = lista.scrollHeight;
        pintarChip();
    }
    function promocaoHtml() {
        const cor = meuLado() === 'w' ? 'b' : 'p';
        return `<div class="at-promo" role="dialog" aria-label="Escolha a peça"><b>Promover o peão para:</b><div>${['q', 'r', 'b', 'n'].map((x) => `<button type="button" data-t="promover" data-p="${x}" aria-label="${x}"><span class="at-p ${cor}">${GLIFO[x]}</span></button>`).join('')}</div>
            <button type="button" class="sec" data-t="cancelar-promo">Cancelar</button></div>`;
    }

    // =============================================================================================================
    // Jogar
    // =============================================================================================================
    function aoClicarTabuleiro(e) {
        const t = e.target.closest('[data-t]');
        if (t) {
            const a = t.dataset.t;
            const base = { canal_id: ctx.canalId() };
            if (a === 'sentar') ctx.emitir('atividade_sentar', Object.assign(base, { lado: t.dataset.lado }));
            else if (a === 'sair') ctx.emitir('atividade_sentar', Object.assign(base, { lado: 'sair' }));
            else if (a === 'desistir') ctx.confirmar('Desistir da partida?', 'A vitória fica com o adversário.', () => ctx.emitir('atividade_acao', Object.assign(base, { acao: 'desistir' })));
            else if (['empate', 'empate_aceitar', 'empate_recusar', 'revanche'].includes(a)) ctx.emitir('atividade_acao', Object.assign(base, { acao: a }));
            else if (a === 'promover' && promocao) { const p = promocao; promocao = null; enviarLance(p.de, p.para, t.dataset.p); }
            else if (a === 'cancelar-promo') { promocao = null; selecionada = destinos = null; desenhar(); }
            return;
        }
        const sqEl = e.target.closest('.at-sq');
        if (!sqEl || !estado || estado.situacao !== 'jogando' || promocao) return;
        const eu = meuLado();
        if (!eu || estado.vez !== eu || pendente) return;
        const sq = sqEl.dataset.sq;
        const peca = pecaEm(sq);
        const minha = peca && (peca === peca.toUpperCase()) === (eu === 'w');
        if (selecionada && selecionada !== sq && (destinos === null || destinos.some((m) => m.to === sq))) {
            // segundo clique num destino
            const origem = selecionada;
            const pa = pecaEm(origem);
            const ehPromo = pa && pa.toLowerCase() === 'p' && (sq[1] === '8' || sq[1] === '1');
            if (ehPromo) { promocao = { de: origem, para: sq }; desenhar(); return; }
            enviarLance(origem, sq, null);
            return;
        }
        if (minha && selecionada !== sq) {
            selecionada = sq;
            destinos = chess ? chess.moves({ square: sq, verbose: true }) : null;
            if (destinos && !destinos.length) { destinos = []; }
        } else { selecionada = destinos = null; }
        desenhar();
    }
    function pecaEm(sq) {
        const linhas = estado.fen.split(' ')[0].split('/');
        const linha = linhas[8 - Number(sq[1])];
        let f = 0;
        for (const ch of linha) {
            if (/\d/.test(ch)) f += Number(ch); else { if (FILES[f] === sq[0]) return ch; f++; }
        }
        return null;
    }
    function enviarLance(de, para, promo) {
        selecionada = destinos = null;
        pendente = true;
        // mostra o lance na hora; o servidor confirma (ou recusa e manda o estado de volta)
        if (chess) {
            try {
                const m = chess.move({ from: de, to: para, promotion: promo || undefined });
                if (m) {
                    estado = Object.assign({}, estado, { fen: chess.fen(), vez: estado.vez === 'w' ? 'b' : 'w', ultimo: [de, para], lances: estado.lances.concat([de + para + (promo || '')]), xeque: chess.in_check() });
                    sans = sans.concat([m.san]);
                    sansDe = '';
                }
            } catch (e) {}
        }
        desenhar();
        const dados = { canal_id: ctx.canalId(), acao: 'lance', de, para };
        if (promo) dados.promocao = promo;
        ctx.emitir('atividade_acao', dados);
        // se o servidor não responder em 5 s (queda), pede o estado de novo
        const id = estado.id;
        setTimeout(() => { if (pendente && estado && estado.id === id) { pendente = false; ctx.emitir('atividade_pedir', { canal_id: ctx.canalId() }); } }, 5000);
    }
    function aoErro(d) {
        if (!d || String(d.canal_id) !== String(ctx.canalId())) return;
        ctx.toast(d.msg || 'Não deu certo.', 'warning');
        pendente = false; promocao = null; selecionada = destinos = null;
    }

    // =============================================================================================================
    function iniciar(c) {
        ctx = c;
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && seletor && seletor.classList.contains('aberto')) { fecharSeletor(); e.stopPropagation(); }
        }, true);
        addEventListener('resize', () => { if (painel && !painel.hidden) posicionarPainel(); });
    }
    return {
        iniciar, abrirSeletor, aoEstado, aoErro,
        // chamado ao entrar numa call: pede a atividade que já está rolando (reconexão também)
        aoEntrarNaCall() { if (ctx) ctx.emitir('atividade_pedir', { canal_id: ctx.canalId() }); },
        // sair da call fecha tudo (a atividade é da call)
        aoSairDaCall() {
            estado = null; chess = null; sans = []; sansDe = ''; selecionada = destinos = promocao = null; pendente = false; escondidoPorMim = null;
            if (painel) painel.hidden = true; fecharSeletor(); pintarChip();
        },
        estado: () => estado,
    };
})();
