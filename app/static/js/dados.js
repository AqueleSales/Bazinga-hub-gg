/* Dados e sorteio PESSOAIS (Rodada 40). Objeto global `Dados`. Regras e sorteio: app/dados.py e dados_events.py (o servidor sorteia; aqui só se escolhe e se anima).
 *
 * É um painel SEU, não uma atividade da call: abrir não ocupa a vaga de atividade (dá pra jogar xadrez ao mesmo tempo) e as rolagens ficam só com você.
 * Tela no espírito do widget de dados do Google: um palco com os dados 3D, uma fileira de botões (d4 a d20, cada um com a sua forma e cor, toque pra somar
 * mais um), "±" pro modificador, "Rolar" e "Limpar", e o "Total" no canto. Moeda e "sortear alguém da call" ficam discretos embaixo.
 *
 * Os dois botões ao lado do título:  OLHO  = quem vê as suas rolagens (fechado: só você; aberto: a call e/ou um canal; a escolha fica na conta)
 *                                    ENGRENAGEM = ONDE aparece quando o olho está aberto (aviso na call e/ou mensagem num canal de texto; fica neste aparelho)
 *
 * Contexto (Dados.iniciar): { socket, esc, toast, emCall(), canais(): [{servidor, canais: [{id, name}]}], som?(tipo),
 *                             prefs: { publico(): bool, definirPublico(bool), aoMudar(fn) } }
 * Eventos: dados_resultado (só pra mim) · dados_publico (alguém da call mostrou uma rolagem) · dados_erro
 */
const Dados = (() => {
    'use strict';
    const DADOS = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20'];
    const MAX_NA_TELA = 12;                  // no palco cabem 12 dados sem ficar ilegível (o servidor aceita 30)
    const MAX_MOD = 99;
    // cada dado com a sua forma (viewBox 24) e o seu número; as cores moram no CSS (--c) e batem com as do palco 3D
    const FORMA = {
        d4: { pts: '12,3 22,21 2,21', y: 18.2 }, d6: { rect: true, y: 15.6 }, d8: { pts: '12,2 22,12 12,22 2,12', y: 15.8 },
        d10: { pts: '12,2.5 21.5,9.6 18,21 6,21 2.5,9.6', y: 16.4 }, d12: { pts: '8,3 16,3 21,8 21,16 16,21 8,21 3,16 3,8', y: 15.8 }, d20: { pts: '12,2 21,7 21,17 12,22 3,17 3,7', y: 15.8 },
    };
    const LADOS = { d4: '4', d6: '6', d8: '8', d10: '10', d12: '12', d20: '20' };
    let C = null, painel = null, d3 = null, avisos = null;
    const sel = {};                          // {d6: 2, d20: 1}
    let ordem = [];                          // a ordem em que os tipos entraram na seleção (o palco mostra nessa ordem)
    let mod = 0, modAberto = false, configAberta = false, esperando = false, tempoEsperando = 0;
    let total = { rotulo: 'Total', valor: '0' }, idTotal = null;     // idTotal: o resultado cujo total ainda vai aparecer (mexer na seleção cancela)
    let hist = [];
    const $ = (s) => (painel ? painel.querySelector(s) : null);
    const LS = { dest: 'pnt_dados_dest', pos: 'pnt_dados_pos' };

    // ---- o que fica neste aparelho: onde mostrar (a call e/ou um canal) ----
    function destino() {
        let d = {};
        try { d = JSON.parse(localStorage.getItem(LS.dest) || '{}') || {}; } catch (e) { d = {}; }
        return { naCall: d.naCall !== false, canal: Number(d.canal) > 0 ? Number(d.canal) : null };
    }
    function guardarDestino(d) { try { localStorage.setItem(LS.dest, JSON.stringify({ naCall: !!d.naCall, canal: d.canal || null })); } catch (e) { /* sem armazenamento: vale só nesta sessão */ } }
    const publico = () => !!(C && C.prefs.publico());
    /** O que o servidor vai receber de "quem vê": só vale se há pra onde mostrar. */
    function visibilidade() {
        const dest = destino();
        const call = publico() && dest.naCall && C.emCall();
        const canal = publico() && dest.canal && canalExiste(dest.canal) ? dest.canal : null;
        return { publico: !!(call || canal), naCall: dest.naCall, canal };
    }
    function canalExiste(id) { return gruposDeCanais().some((g) => g.canais.some((c) => Number(c.id) === Number(id))); }
    function gruposDeCanais() { try { return (C.canais() || []).filter((g) => g && g.canais && g.canais.length); } catch (e) { return []; } }

    // ---- desenho ----
    function svgDado(d) {
        const f = FORMA[d];
        const forma = f.rect ? '<rect x="3" y="3" width="18" height="18" rx="3.5"/>' : `<polygon points="${f.pts}" stroke-linejoin="round"/>`;
        return `<svg viewBox="0 0 24 24" aria-hidden="true">${forma}<text x="12" y="${f.y}" text-anchor="middle">${LADOS[d]}</text></svg>`;
    }
    function montar() {
        painel = document.createElement('div');
        painel.className = 'dd'; painel.id = 'dd-painel'; painel.setAttribute('role', 'dialog'); painel.setAttribute('aria-label', 'Dados e sorteio');
        painel.innerHTML = `<div class="dd-topo" id="dd-topo"><i class="fa-solid fa-dice-d20 dd-logo" aria-hidden="true"></i><b>Dados e sorteio</b>
                <button type="button" class="dd-ic" data-dd="olho" id="dd-olho"><i class="fa-solid fa-eye-slash"></i></button>
                <button type="button" class="dd-ic" data-dd="config" id="dd-engrenagem" aria-haspopup="true" aria-expanded="false" title="Onde mostrar o resultado" aria-label="Onde mostrar o resultado"><i class="fa-solid fa-gear"></i></button>
                <span class="dd-esp"></span>
                <button type="button" class="dd-ic" data-dd="x" title="Fechar" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button></div>
            <div class="dd-config" id="dd-config" hidden></div>
            <div class="dd-palco" id="dd-palco"><canvas class="dd-canvas" aria-hidden="true"></canvas><div class="dd-sorteado" hidden></div>
                <div class="dd-total" aria-live="polite"><small id="dd-total-r">Total</small><b id="dd-total-v">0</b></div></div>
            <div class="dd-fileira" id="dd-fileira">${DADOS.map((d) => `<div class="dd-dw" data-d="${d}"><button type="button" class="dd-d dd-${d}" data-dd="add" data-d="${d}" aria-label="Somar um ${d.toUpperCase()}" title="${d.toUpperCase()}">${svgDado(d)}</button>
                    <button type="button" class="dd-menos" data-dd="tirar" data-d="${d}" aria-label="Tirar um ${d.toUpperCase()}" title="Tirar um" hidden>−</button><span class="dd-qtd" hidden></span></div>`).join('')}
                <span class="dd-barra" aria-hidden="true"></span>
                <div class="dd-dw"><button type="button" class="dd-d dd-mod" data-dd="mod" id="dd-mod" aria-label="Modificador" title="Modificador (somar ou tirar um valor fixo)" aria-expanded="false">±</button><span class="dd-qtd dd-modq" hidden></span></div></div>
            <div class="dd-modbar" id="dd-modbar" hidden><button type="button" data-dd="mod-" aria-label="Menos 1">−</button><output id="dd-mod-v">+0</output><button type="button" data-dd="mod+" aria-label="Mais 1">+</button><small>somado ao total</small></div>
            <div class="dd-acoes"><button type="button" class="dd-rolar" data-dd="rolar" id="dd-rolar">Rolar</button><button type="button" class="dd-limpar" data-dd="limpar">Limpar</button></div>
            <div class="dd-mais"><button type="button" data-dd="moeda"><i class="fa-solid fa-coins" aria-hidden="true"></i> Jogar a moeda</button><button type="button" data-dd="sortear"><i class="fa-solid fa-hat-wizard" aria-hidden="true"></i> Sortear alguém da call</button></div>
            <div class="dd-hist" id="dd-hist"></div>
            <div class="dd-vis" id="dd-vis"></div>`;
        document.body.appendChild(painel);
        painel.addEventListener('click', aoClicar);
        painel.addEventListener('contextmenu', (e) => {                        // botão direito num dado também tira um (igual ao "−" do canto)
            const b = e.target.closest('.dd-d[data-d]'); if (!b || !sel[b.dataset.d]) return;
            e.preventDefault(); tirar(b.dataset.d);
        });
        painel.addEventListener('change', (e) => {
            if (e.target.id === 'dd-na-call') { guardarDestino({ ...destino(), naCall: e.target.checked }); pintarVis(); }
            else if (e.target.id === 'dd-canal') { guardarDestino({ ...destino(), canal: Number(e.target.value) || null }); pintarVis(); }
        });
        arrastavel();
        d3 = Dados3D.criar();
    }
    function arrastavel() {
        let arr = null;
        const topo = $('#dd-topo');
        topo.addEventListener('pointerdown', (e) => {
            if (e.target.closest('button')) return;
            const r = painel.getBoundingClientRect(); arr = { dx: e.clientX - r.left, dy: e.clientY - r.top };
            try { topo.setPointerCapture(e.pointerId); } catch (er) { /* sem captura: o arrasto ainda funciona dentro do cabeçalho */ }
        });
        topo.addEventListener('pointermove', (e) => {
            if (!arr) return;
            painel.style.left = Math.min(innerWidth - 80, Math.max(-200, e.clientX - arr.dx)) + 'px'; painel.style.top = Math.min(innerHeight - 50, Math.max(0, e.clientY - arr.dy)) + 'px';
            painel.style.right = painel.style.bottom = 'auto';
        });
        topo.addEventListener('pointerup', () => {
            if (!arr) return; arr = null;
            try { localStorage.setItem(LS.pos, JSON.stringify({ x: parseFloat(painel.style.left), y: parseFloat(painel.style.top) })); } catch (e) { /* conveniência */ }
        });
    }
    function posicionar() {
        let pos = null;
        try { pos = JSON.parse(localStorage.getItem(LS.pos) || 'null'); } catch (e) { pos = null; }
        if (innerWidth <= 720) { painel.style.left = painel.style.top = painel.style.right = painel.style.bottom = ''; return; }
        const w = painel.offsetWidth || 340, h = painel.offsetHeight || 520;
        const x = pos && isFinite(pos.x) ? pos.x : Math.max(12, (innerWidth - w) / 2 + 40), y = pos && isFinite(pos.y) ? pos.y : Math.max(12, (innerHeight - h) / 2 - 10);
        painel.style.left = Math.min(Math.max(-w + 80, x), innerWidth - 80) + 'px'; painel.style.top = Math.min(Math.max(0, y), Math.max(0, innerHeight - 60)) + 'px';
        painel.style.right = painel.style.bottom = 'auto';
    }

    function qtdTotal() { return ordem.reduce((a, d) => a + (sel[d] || 0), 0); }
    function listaParaPalco() { const l = []; ordem.forEach((d) => { for (let i = 0; i < sel[d]; i++) l.push(d); }); return l; }
    function pintarSelecao() {
        if (!painel) return;
        DADOS.forEach((d) => {
            const dw = painel.querySelector(`.dd-dw[data-d="${d}"]`), n = sel[d] || 0;
            dw.classList.toggle('on', n > 0);
            const q = dw.querySelector('.dd-qtd'); q.hidden = n < 2; q.textContent = '×' + n;
            dw.querySelector('.dd-menos').hidden = n < 1;
        });
        const mq = painel.querySelector('.dd-modq'); mq.hidden = !mod; mq.textContent = (mod > 0 ? '+' : '') + mod;
        $('#dd-mod-v').textContent = (mod >= 0 ? '+' : '') + mod;
        $('#dd-mod').classList.toggle('on', modAberto || !!mod);
        $('#dd-mod').setAttribute('aria-expanded', modAberto ? 'true' : 'false');
        $('#dd-modbar').hidden = !modAberto;
        $('#dd-rolar').disabled = esperando;
        $('#dd-rolar').textContent = esperando ? 'Rolando…' : 'Rolar';
    }
    function pintarPalco(manterTotal) {
        $('.dd-sorteado').hidden = true;
        $('.dd-canvas').hidden = false;
        d3.selecionar($('.dd-canvas'), listaParaPalco());
        if (!manterTotal) { total = { rotulo: 'Total', valor: '0' }; idTotal = null; pintarTotal(); }
    }
    function pintarTotal() { $('#dd-total-r').textContent = total.rotulo; $('#dd-total-v').textContent = total.valor; }
    function pintarOlho() {
        if (!painel) return;
        const b = $('#dd-olho'), v = publico();
        b.innerHTML = `<i class="fa-solid ${v ? 'fa-eye' : 'fa-eye-slash'}"></i>`;
        b.classList.toggle('on', v); b.setAttribute('aria-pressed', v ? 'true' : 'false');
        const t = v ? 'A call (ou o canal que você escolheu) vê as suas rolagens. Clique pra só você ver.' : 'Só você vê as suas rolagens. Clique pra mostrar pra call ou pra um canal.';
        b.title = t; b.setAttribute('aria-label', t);
        pintarVis();
    }
    function pintarVis() {
        if (!painel) return;
        const dest = destino(), vis = visibilidade();
        let t;
        if (!publico()) t = '<i class="fa-solid fa-lock"></i> Só você vê estas rolagens.';
        else {
            const onde = [];
            if (dest.naCall) onde.push(C.emCall() ? 'na call' : 'na call (quando você estiver em uma)');
            if (vis.canal) { const c = gruposDeCanais().flatMap((g) => g.canais).find((x) => Number(x.id) === vis.canal); onde.push(c ? `em #${C.esc(c.name)}` : 'num canal'); }
            t = onde.length ? `<i class="fa-solid fa-eye"></i> Mostrando ${onde.join(' e ')}.` : '<i class="fa-solid fa-triangle-exclamation"></i> Escolha onde mostrar na engrenagem.';
        }
        $('#dd-vis').innerHTML = t;
        if (configAberta) pintarConfig();
    }
    function pintarConfig() {
        const dest = destino(), grupos = gruposDeCanais(), el = $('#dd-config');
        const opcoes = grupos.map((g) => `<optgroup label="${C.esc(g.servidor || 'Servidor')}">${g.canais.map((c) => `<option value="${Number(c.id)}"${Number(c.id) === dest.canal ? ' selected' : ''}>#${C.esc(c.name)}</option>`).join('')}</optgroup>`).join('');
        el.innerHTML = `<b>Onde mostrar</b><p>Vale quando o olho está aberto. Com o olho fechado, nada sai daqui: só você vê.</p>
            <label class="dd-cfg-l"><input type="checkbox" id="dd-na-call"${dest.naCall ? ' checked' : ''}><span>Pra quem está na call <small>(um aviso curto com o resultado)</small></span></label>
            <label class="dd-cfg-l col"><span>Também num canal de texto <small>(o resultado vira uma mensagem lá)</small></span>
                <select id="dd-canal"><option value="0">Nenhum</option>${opcoes}</select></label>`;
    }
    function pintarHist() {
        const el = $('#dd-hist'); if (!el) return;
        el.innerHTML = hist.map((h) => `<div class="dd-h"><i class="fa-solid ${h.icone}" aria-hidden="true"></i><span>${C.esc(h.texto)}</span>${h.visto ? '<i class="fa-solid fa-eye dd-h-v" title="Outras pessoas viram"></i>' : ''}</div>`).join('');
    }

    // ---- ações ----
    function somar(d) {
        if (esperando) return;
        if (qtdTotal() >= MAX_NA_TELA) { C.toast(`No máximo ${MAX_NA_TELA} dados de uma vez aqui.`, 'info'); return; }
        if (!sel[d]) ordem.push(d);
        sel[d] = (sel[d] || 0) + 1;
        pintarSelecao(); pintarPalco();
    }
    function tirar(d) {
        if (esperando || !sel[d]) return;
        sel[d]--;
        if (!sel[d]) { delete sel[d]; ordem = ordem.filter((x) => x !== d); }
        pintarSelecao(); pintarPalco();
    }
    function limpar() {
        if (esperando) return;
        Object.keys(sel).forEach((k) => delete sel[k]); ordem = []; mod = 0; modAberto = false;
        pintarSelecao(); pintarPalco();
    }
    function pedir(corpo) {
        if (esperando) return;
        esperando = true; tempoEsperando = Date.now(); pintarSelecao();
        const v = visibilidade();
        C.socket.emit('dados_rolar', { ...corpo, publico: v.publico, na_call: v.naCall, canal_id: v.canal || undefined });
        setTimeout(() => { if (esperando && Date.now() - tempoEsperando >= 4500) { esperando = false; pintarSelecao(); } }, 4600);       // o servidor não respondeu: destrava o botão
    }
    function rolar() {
        if (!qtdTotal()) { C.toast('Toque num dado pra escolher o que rolar.', 'info'); const f = $('#dd-fileira'); f.classList.add('dd-tremer'); setTimeout(() => f.classList.remove('dd-tremer'), 450); return; }
        pedir({ grupos: ordem.map((d) => ({ dado: d, qtd: sel[d] })), mod });
    }
    function moeda() { pedir({ tipo: 'moeda', qtd: 1 }); }
    function sortear() {
        if (!C.emCall()) { C.toast('Entre numa call pra sortear alguém.', 'info'); return; }
        pedir({ tipo: 'sorteio' });
    }
    function aoClicar(e) {
        const b = e.target.closest('[data-dd]');
        if (!b) { if (configAberta && !e.target.closest('#dd-config')) fecharConfig(); return; }
        const a = b.dataset.dd;
        if (a !== 'config' && configAberta && !e.target.closest('#dd-config')) fecharConfig();
        if (a === 'x') fechar();
        else if (a === 'olho') C.prefs.definirPublico(!publico());
        else if (a === 'config') { configAberta ? fecharConfig() : abrirConfig(); }
        else if (a === 'add') somar(b.dataset.d);
        else if (a === 'tirar') tirar(b.dataset.d);
        else if (a === 'mod') { modAberto = !modAberto; pintarSelecao(); }
        else if (a === 'mod-') { mod = Math.max(-MAX_MOD, mod - 1); pintarSelecao(); pintarPalco(); }
        else if (a === 'mod+') { mod = Math.min(MAX_MOD, mod + 1); pintarSelecao(); pintarPalco(); }
        else if (a === 'rolar') rolar();
        else if (a === 'limpar') limpar();
        else if (a === 'moeda') moeda();
        else if (a === 'sortear') sortear();
    }
    function abrirConfig() { configAberta = true; const el = $('#dd-config'); el.hidden = false; pintarConfig(); $('#dd-engrenagem').setAttribute('aria-expanded', 'true'); $('#dd-engrenagem').classList.add('on'); }
    function fecharConfig() { configAberta = false; const el = $('#dd-config'); if (el) el.hidden = true; const g = $('#dd-engrenagem'); if (g) { g.setAttribute('aria-expanded', 'false'); g.classList.remove('on'); } }

    // ---- o resultado do servidor ----
    function descreve(e) {
        if (e.tipo === 'moeda') return { rotulo: e.moedas && e.moedas.length > 1 ? `${e.moedas.length} moedas` : 'Moeda', icone: 'fa-coins', texto: `${e.moedas && e.moedas.length > 1 ? 'Moedas' : 'Moeda'}: ${e.texto}` };
        if (e.tipo === 'sorteio') return { rotulo: 'Sorteado', icone: 'fa-hat-wizard', texto: `Sorteio: ${e.texto}` };
        const g = (e.grupos || []).map((x, i) => `${i ? (x.sinal < 0 ? ' − ' : ' + ') : (x.sinal < 0 ? '−' : '')}[${x.valores.map((v, k) => (x.mantidos.includes(k) ? v : `(${v})`)).join(' ')}]`).join('');
        return { rotulo: 'Total', icone: 'fa-dice-d20', texto: `${e.expr}: ${g}${e.mod ? (e.mod > 0 ? ' + ' : ' − ') + Math.abs(e.mod) : ''} = ${e.texto}` };
    }
    function aoResultado(e) {
        esperando = false;
        if (!e || e.tipo == null) { pintarSelecao(); return; }
        const d = descreve(e);
        const v = e.visivel || {};
        hist.unshift({ texto: d.texto, icone: d.icone, visto: !!(v.call || v.canal) }); hist = hist.slice(0, 4);
        if (v.aviso) C.toast(v.aviso, 'info');
        if (!painel) return;                                    // o painel foi fechado enquanto o servidor sorteava: o resultado só vai pro histórico
        pintarSelecao(); pintarHist();
        const palco = $('.dd-sorteado'), cv = $('.dd-canvas');
        if (e.tipo === 'sorteio') {
            d3.parar(); cv.hidden = true; palco.hidden = false; palco.innerHTML = `<i class="fa-solid fa-hat-wizard" aria-hidden="true"></i><b>${C.esc(e.texto)}</b>`;
            total = { rotulo: 'Sorteado', valor: e.texto }; pintarTotal(); return;
        }
        palco.hidden = true; cv.hidden = false;
        total = { rotulo: d.rotulo, valor: '…' }; idTotal = e.id; pintarTotal();
        // o total aparece quando os dados assentam; o prazo é a rede de segurança (aba em segundo plano não anima: o resultado não pode ficar em "…")
        const mostrarTotal = () => { if (idTotal !== e.id || !painel) return; idTotal = null; total = { rotulo: d.rotulo, valor: e.texto }; pintarTotal(); };
        d3.mostrar(cv, e, { animar: true, aoFim: mostrarTotal });
        setTimeout(mostrarTotal, 3000);
    }

    // ---- a rolagem que OUTRA pessoa da call mostrou: um aviso curto por cima da call ----
    function aviso(e) {
        if (!e || !e.quem) return;
        if (!avisos) { avisos = document.createElement('div'); avisos.className = 'dd-avisos'; avisos.setAttribute('aria-live', 'polite'); document.body.appendChild(avisos); }
        const d = descreve(e);
        const el = document.createElement('div'); el.className = 'dd-aviso';
        const temDado = e.tipo !== 'sorteio';
        el.innerHTML = `${temDado ? '<canvas class="dd-aviso-cv" aria-hidden="true"></canvas>' : '<i class="fa-solid fa-hat-wizard dd-aviso-ic" aria-hidden="true"></i>'}
            <div class="dd-aviso-txt"><small><b>${C.esc(e.quem.nome)}</b> ${e.tipo === 'moeda' ? 'jogou a moeda' : e.tipo === 'sorteio' ? 'sorteou' : 'rolou'}${e.tipo === 'rolagem' ? ` <code>${C.esc(e.expr)}</code>` : ''}</small><b class="dd-aviso-v">${C.esc(e.texto)}</b></div>`;
        avisos.prepend(el);
        while (avisos.children.length > 3) avisos.lastChild.remove();
        if (temDado) { const inst = Dados3D.criar(); const cv = el.querySelector('canvas'); requestAnimationFrame(() => inst.mostrar(cv, e, { animar: true })); el._d3 = inst; }
        if (C.som) { try { C.som('msg'); } catch (er) { /* sem som */ } }
        setTimeout(() => { el.classList.add('saindo'); setTimeout(() => { if (el._d3) el._d3.parar(); el.remove(); }, 400); }, 6500);
    }

    // ---- abrir e fechar ----
    function abrir() {
        if (painel) { const b = painel.querySelector('.dd-d'); if (b) b.focus({ preventScroll: true }); return; }           // já está aberto: só leva o foco pra ele
        montar(); posicionar(); pintarSelecao(); pintarPalco(); pintarOlho(); pintarHist();
        setTimeout(() => { const b = painel && painel.querySelector('.dd-d'); if (b) b.focus({ preventScroll: true }); }, 30);
    }
    function fechar() {
        if (!painel) return;
        if (d3) d3.parar();
        painel.remove(); painel = null; configAberta = false;
    }
    function iniciar(ctx) {
        C = ctx;
        C.socket.on('dados_resultado', aoResultado);
        C.socket.on('dados_publico', aviso);
        C.socket.on('dados_erro', (d) => { esperando = false; if (painel) pintarSelecao(); C.toast((d && d.msg) || 'Não deu pra rolar.', 'warning'); });
        C.prefs.aoMudar(() => pintarOlho());
        addEventListener('resize', () => { if (painel) posicionar(); });
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape' || !painel) return;
            if (configAberta) { fecharConfig(); e.stopPropagation(); return; }
            if (painel.contains(document.activeElement)) { fechar(); e.stopPropagation(); }
        }, true);
    }
    return { iniciar, abrir, fechar, aberto: () => !!painel, _estado: () => ({ sel: Object.assign({}, sel), ordem: ordem.slice(), mod, total, hist: hist.slice(), esperando }), _descreve: descreve };
})();
