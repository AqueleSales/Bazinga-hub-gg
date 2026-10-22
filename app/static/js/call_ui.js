/* Call (Rodada 34): a parte de tela da call que saiu do chat.html.
   - botão "+" da barra: abre em leque (tela, clipe, convidar, atividades, 3 pontinhos), como o "+" do mapa no celular;
   - menu dos 3 pontinhos (exibição em grade, minha câmera, participantes sem vídeo, prévia de mensagens, ruído, sons, qualidade);
   - convidar um amigo pra voz (o servidor decide quem recebe) e o aviso de quem te chamou;
   - grade que se ajusta ao nº de pessoas, quadro principal (clique, tela compartilhada ou quem fala) e faixa embaixo;
   - zoom na câmera/tela dos outros (roda, arrastar, pinça, botões, "preencher") com o nível à vista;
   - a janela da call não cobre mais a janela de Música.
   Quem sabe da call (peers, mídia, sons) continua sendo o chat.html: ele entrega o que precisamos em CallUI.iniciar(ctx). */
const CallUI = (function () {
    'use strict';
    let ctx = null;
    const CH_OPC = 'pnt_call_opc';
    const PADRAO = { grade: true, minha: true, semVideo: true, previa: true, sons: true, otimizar: 'nitidez', qualidade: 'auto' };
    const opc = Object.assign({}, PADRAO);
    try { Object.assign(opc, JSON.parse(localStorage.getItem(CH_OPC) || '{}')); } catch (e) {}
    if (!['nitidez', 'fluidez'].includes(opc.otimizar)) opc.otimizar = PADRAO.otimizar;
    if (!['economia', 'auto', 'alta'].includes(opc.qualidade)) opc.qualidade = PADRAO.qualidade;
    ['grade', 'minha', 'semVideo', 'previa', 'sons'].forEach((k) => { opc[k] = !!opc[k]; });

    const SVG_ESPADAS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        + '<path d="M3.5 3.5l11 11M12 17l5-5M14.5 14.5L19 19"/><circle cx="20" cy="20" r="1.1"/>'
        + '<path d="M20.5 3.5l-11 11M12 17l-5-5M9.5 14.5L5 19"/><circle cx="4" cy="20" r="1.1"/></svg>';

    let camada, main, barra, menu, popupClipe;
    let leque = false, menuAberto = false;

    function salvar() { try { localStorage.setItem(CH_OPC, JSON.stringify(opc)); } catch (e) {} }
    function $(id) { return document.getElementById(id); }
    function esc(v) { return ctx.esc(v); }
    function visivel(el) { return !!el && getComputedStyle(el).display !== 'none'; }

    // =============================================================================================================
    // Leque do "+"
    // =============================================================================================================
    function opsDoLeque() {
        return [...camada.querySelectorAll('.cf-op')].filter(visivel);
    }

    // Posições dos botões em arco acima do "+" (ou abaixo, se não couber): tenta raios menores antes de desistir.
    function calcularLeque(cx, cy, n) {
        const vw = innerWidth, vh = innerHeight;
        const tentativas = [[124, 38, 142, -1], [104, 34, 146, -1], [86, 30, 150, -1], [124, 38, 142, 1], [104, 34, 146, 1], [86, 30, 150, 1]];
        const dentro = (p) => p.x >= 30 && p.x <= vw - 30 && p.y >= 52 && p.y <= vh - 50;
        let primeira = null;
        for (const [R, a0, a1, dir] of tentativas) {
            const pts = [];
            for (let i = 0; i < n; i++) {
                const ang = (n === 1 ? 90 : a1 - ((a1 - a0) * i) / (n - 1)) * Math.PI / 180;
                pts.push({ x: cx + R * Math.cos(ang), y: cy + dir * R * Math.sin(ang) });
            }
            if (!primeira) primeira = pts;
            if (pts.every(dentro)) return pts;
        }
        return primeira.map((p) => ({ x: Math.min(vw - 30, Math.max(30, p.x)), y: Math.min(vh - 50, Math.max(30, p.y)) }));
    }

    function posicionarLeque() {
        const r = main.getBoundingClientRect();
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const ops = opsDoLeque();
        const pts = calcularLeque(cx, cy, ops.length);
        ops.forEach((el, i) => {
            el.style.setProperty('--x0', cx + 'px'); el.style.setProperty('--y0', cy + 'px');
            el.style.setProperty('--x', pts[i].x + 'px'); el.style.setProperty('--y', pts[i].y + 'px');
            el.style.setProperty('--atraso', (i * 22) + 'ms');
        });
        camada.style.setProperty('--cf-cx', cx + 'px'); camada.style.setProperty('--cf-cy', cy + 'px');
        camada.dataset.cx = cx; camada.dataset.cy = cy;
    }

    function popupAberto() { return !!popupClipe && popupClipe.classList.contains('aberto'); }
    // a barra de controles some quando o mouse sai; enquanto o leque, o menu ou o popup do clipe estiverem abertos ela fica
    function atualizarBarra() { barra.classList.toggle('cf-aberto', leque || menuAberto || popupAberto()); }

    function abrirLeque(v, manterPopup) {
        if (v === leque) { if (!v && !manterPopup) fecharPopupClipe(); return; }
        if (v && !ctx.emCall()) return;
        leque = v;
        main.classList.toggle('aberto', v);
        main.setAttribute('aria-expanded', v ? 'true' : 'false');
        main.querySelector('i').className = 'fa-solid ' + (v ? 'fa-xmark' : 'fa-plus');
        if (v) { fecharMenu(); fecharPopupClipe(); posicionarLeque(); }
        camada.classList.toggle('leque', v);
        if (!v && !manterPopup) fecharPopupClipe();
        atualizarBarra();
    }

    function fecharPopupClipe() { if (popupClipe) { popupClipe.classList.remove('aberto'); atualizarBarra(); } }

    // O popup do clipe (Gravar / Clipar / automático) é do chat.html; aqui só o ancoramos acima do "+".
    function ancorarPopupClipe() {
        if (!popupClipe) return;
        const cx = Number(camada.dataset.cx), cy = Number(camada.dataset.cy);
        const r = main.getBoundingClientRect();
        popupClipe.style.left = Math.min(innerWidth - 100, Math.max(100, cx || r.left)) + 'px';
        popupClipe.style.top = Math.max(60, (r.top || cy) - 8) + 'px';
    }

    // =============================================================================================================
    // Menu dos 3 pontinhos
    // =============================================================================================================
    function itemSwitch(chave, icone, titulo, ajuda) {
        return `<button type="button" class="cf-it" role="menuitemcheckbox" data-sw="${chave}" aria-checked="false"><i class="fa-solid ${icone}"></i><span>${titulo}${ajuda ? `<small>${ajuda}</small>` : ''}</span><i class="cf-sw"></i></button>`;
    }
    function construirMenu() {
        menu = document.createElement('div');
        menu.className = 'cf-menu'; menu.id = 'cf-menu'; menu.setAttribute('role', 'menu'); menu.setAttribute('aria-label', 'Configurações da call');
        menu.innerHTML = `
            ${itemSwitch('grade', 'fa-table-cells-large', 'Exibição em grade', 'Desligada: o quadro principal acompanha quem fala')}
            ${itemSwitch('minha', 'fa-video', 'Mostrar minha própria câmera')}
            ${itemSwitch('semVideo', 'fa-user', 'Mostrar participantes sem vídeo')}
            ${itemSwitch('previa', 'fa-comment-dots', 'Mostrar prévia de novas mensagens', 'Aparece aqui enquanto a call está em tela cheia')}
            <hr><h6>Áudio</h6>
            ${itemSwitch('ruido', 'fa-wave-square', 'Supressão de ruído', 'Filtro do navegador; funciona melhor com fone')}
            ${itemSwitch('sons', 'fa-bell', 'Sons de entrada e saída')}
            <hr><h6>Transmissão e câmera</h6>
            <div class="cf-seg" data-seg="otimizar" role="group" aria-label="Otimizar a tela compartilhada para">
                <button type="button" data-v="nitidez" title="Texto e código ficam nítidos; cai a fluidez se a rede apertar">Nitidez</button>
                <button type="button" data-v="fluidez" title="Jogos e vídeos ficam fluidos; a nitidez cai se a rede apertar">Fluidez</button>
            </div>
            <div class="cf-seg" data-seg="qualidade" role="group" aria-label="Qualidade da call">
                <button type="button" data-v="economia" title="Gasta menos internet">Economia</button>
                <button type="button" data-v="auto" title="Equilibrado; sobe e desce sozinho conforme a rede">Automática</button>
                <button type="button" data-v="alta" title="Mais qualidade, gasta mais internet">Alta</button>
            </div>
            <div class="cf-nota">Automática ajusta sozinha conforme a sua rede. Vale para a câmera e para a tela que você compartilhar.</div>
            <hr>
            <button type="button" class="cf-it" data-a="voz"><i class="fa-solid fa-sliders"></i><span>Configurações de voz e vídeo</span></button>
            <button type="button" class="cf-it" data-a="convidar"><i class="fa-solid fa-user-plus"></i><span>Convidar para voz</span></button>`;
        camada.appendChild(menu);
        menu.addEventListener('click', (e) => {
            const sw = e.target.closest('[data-sw]');
            if (sw) { alternar(sw.dataset.sw); return; }
            const seg = e.target.closest('.cf-seg button');
            if (seg) { definirSeg(seg.parentElement.dataset.seg, seg.dataset.v); return; }
            const a = e.target.closest('[data-a]');
            if (!a) return;
            fecharMenu();
            if (a.dataset.a === 'voz') ctx.abrirConfigVoz();
            else if (a.dataset.a === 'convidar') abrirConvite();
        });
    }

    function alternar(chave) {
        if (chave === 'ruido') { ctx.ruido.alternar(); pintarMenu(); return; }
        opc[chave] = !opc[chave];
        salvar(); pintarMenu();
        if (['grade', 'minha', 'semVideo'].includes(chave)) recalcular(true);
        if (chave === 'previa' && !opc.previa) limparPrevias();
    }
    function definirSeg(chave, valor) {
        opc[chave] = valor; salvar(); pintarMenu();
        try { ctx.aoMudarQualidade(Object.assign({}, opc)); } catch (e) {}
    }
    function pintarMenu() {
        if (!menu) return;
        menu.querySelectorAll('[data-sw]').forEach((b) => {
            const c = b.dataset.sw;
            b.setAttribute('aria-checked', (c === 'ruido' ? ctx.ruido.ligado() : opc[c]) ? 'true' : 'false');
        });
        menu.querySelectorAll('.cf-seg').forEach((s) => s.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', opc[s.dataset.seg] === b.dataset.v ? 'true' : 'false')));
        const conv = menu.querySelector('[data-a="convidar"]');
        if (conv) conv.style.display = ctx.ehDM() ? 'none' : '';
    }
    function abrirMenu() {
        if (!ctx.emCall()) return;
        abrirLeque(false);
        pintarMenu();
        menuAberto = true;
        const r = main.getBoundingClientRect();
        const acima = r.top - 14, abaixo = innerHeight - r.bottom - 14;
        const usaAcima = acima >= 260 || acima >= abaixo;
        menu.style.maxHeight = Math.max(160, (usaAcima ? acima : abaixo)) + 'px';
        menu.classList.add('aberto');
        const w = menu.offsetWidth, h = menu.offsetHeight;
        const left = Math.min(innerWidth - w - 8, Math.max(8, r.left + r.width / 2 - w / 2));
        const top = usaAcima ? Math.max(8, r.top - 10 - h) : Math.min(innerHeight - h - 8, r.bottom + 10);
        menu.style.transformOrigin = usaAcima ? 'bottom center' : 'top center';
        menu.style.left = left + 'px'; menu.style.top = top + 'px';
        atualizarBarra();
    }
    function fecharMenu() {
        if (!menuAberto) return;
        menuAberto = false;
        menu.classList.remove('aberto');
        atualizarBarra();
    }
    function fecharTudo() { abrirLeque(false); fecharMenu(); fecharPopupClipe(); }

    // =============================================================================================================
    // Convidar pra voz
    // =============================================================================================================
    let conv = null;
    const chamados = new Map();   // id do amigo -> hora do chamado (o botão fica "Chamado" por 20 s)
    function abrirConvite() {
        if (!ctx.emCall()) return;
        if (ctx.ehDM()) { ctx.toast('Essa é uma ligação só entre vocês dois. Convide pra um canal de voz de um servidor.', 'info'); return; }
        if (!conv) {
            conv = document.createElement('div');
            conv.className = 'cf-conv'; conv.id = 'cf-conv';
            conv.innerHTML = `<div class="cf-conv-card" role="dialog" aria-modal="true" aria-label="Convidar para voz">
                <div class="cf-conv-topo"><h3>Convidar para a call</h3><button type="button" data-fechar title="Fechar"><i class="fa-solid fa-xmark"></i></button></div>
                <input type="search" class="cf-conv-busca" placeholder="Procurar um amigo" maxlength="40" autocomplete="off">
                <div class="cf-conv-lista"></div>
                <div class="cf-conv-rodape"><span style="flex:1;font-size:11.5px;color:var(--text-muted);align-self:center;">Só quem já está neste servidor recebe o chamado.</span></div></div>`;
            document.body.appendChild(conv);
            conv.addEventListener('mousedown', (e) => { if (e.target === conv) fecharConvite(); });
            conv.querySelector('[data-fechar]').addEventListener('click', fecharConvite);
            conv.querySelector('.cf-conv-busca').addEventListener('input', pintarConvite);
            conv.querySelector('.cf-conv-lista').addEventListener('click', (e) => {
                const b = e.target.closest('button[data-amigo]');
                if (!b || b.disabled) return;
                const id = Number(b.dataset.amigo);
                chamados.set(id, Date.now());
                ctx.emitir('convidar_voz', { canal_id: ctx.canalId(), amigo_id: id });
                b.disabled = true; b.textContent = 'Chamando...';
                setTimeout(pintarConvite, 20500);
            });
        }
        conv.classList.add('aberto');
        const campo = conv.querySelector('.cf-conv-busca');
        campo.value = '';
        pintarConvite();
        setTimeout(() => campo.focus(), 30);
    }
    function fecharConvite() { if (conv) conv.classList.remove('aberto'); }
    function pintarConvite() {
        if (!conv || !conv.classList.contains('aberto')) return;
        const termo = conv.querySelector('.cf-conv-busca').value.trim().toLowerCase();
        const lista = ctx.amigos().filter((a) => !termo || String(a.nome).toLowerCase().includes(termo)).sort((a, b) => (b.online - a.online) || String(a.nome).localeCompare(String(b.nome)));
        const caixa = conv.querySelector('.cf-conv-lista');
        if (!lista.length) {
            caixa.innerHTML = `<div class="cf-conv-vazio">${termo ? 'Nenhum amigo com esse nome.' : 'Você ainda não tem amigos adicionados. Adicione alguém pela tela de Amigos pra chamar pra call.'}</div>`;
            return;
        }
        const agora = Date.now();
        caixa.innerHTML = lista.map((a) => {
            const av = ctx.escUrl(a.avatar);
            const recente = chamados.has(a.id) && agora - chamados.get(a.id) < 20000;
            return `<div class="cf-conv-lin"><div class="cf-conv-av">${av ? `<img src="${av}" alt="">` : esc(String(a.nome || '?')[0].toUpperCase())}</div>
                <div class="nome">${esc(a.nome)}<small>${a.online ? 'Online' : 'Offline (recebe um aviso no aparelho)'}</small></div>
                <button type="button" data-amigo="${Number(a.id)}"${recente ? ' disabled' : ''}>${recente ? 'Chamado' : 'Chamar'}</button></div>`;
        }).join('');
    }
    // resposta do servidor ao chamado (a recusa vem como erro_bazinga e já aparece como aviso)
    function aoConvidadoEnviado(d) {
        if (d && d.ja_na_call) ctx.toast('Essa pessoa já está na call.', 'info');
        else ctx.toast('Chamado enviado.', 'success');
        pintarConvite();
    }

    // quem te chamou pra uma call
    let chamado = null, chamadoTimer = 0;
    function convidado(d) {
        if (!d || !d.canal_id) return;
        if (chamado) chamado.remove();
        clearTimeout(chamadoTimer);
        const av = ctx.escUrl(d.de_avatar);
        chamado = document.createElement('div');
        chamado.className = 'cf-chamado'; chamado.setAttribute('role', 'alert');
        chamado.innerHTML = `<div class="cf-conv-av">${av ? `<img src="${av}" alt="">` : esc(String(d.de_nome || '?')[0].toUpperCase())}</div>
            <div class="txt"><b>${esc(d.de_nome)}</b> te chamou pra call <b>${esc(d.canal_nome)}</b> em ${esc(d.server_nome)}.</div>
            <div class="acoes"><button type="button" data-entrar>Entrar</button><button type="button" class="nao" data-nao>Agora não</button></div>`;
        document.body.appendChild(chamado);
        requestAnimationFrame(() => chamado && chamado.classList.add('aberto'));
        const fechar = () => { if (!chamado) return; const c = chamado; chamado = null; c.classList.remove('aberto'); setTimeout(() => c.remove(), 300); };
        chamado.querySelector('[data-nao]').addEventListener('click', fechar);
        chamado.querySelector('[data-entrar]').addEventListener('click', () => { fechar(); ctx.entrarNaCall(d.server_id, d.canal_id, d.canal_nome); });
        chamadoTimer = setTimeout(fechar, 40000);
        try { ctx.som('amizade'); } catch (e) {}
    }

    // =============================================================================================================
    // Prévia de novas mensagens (só com a call em tela cheia: é quando o chat não está à vista)
    // =============================================================================================================
    let caixaPrevias = null;
    function limparPrevias() { if (caixaPrevias) caixaPrevias.innerHTML = ''; }
    function previaMensagem(m) {
        if (!opc.previa || !ctx.emCall() || ctx.modo() !== 'cheia') return;
        const texto = String(m.texto || '').trim() || (m.anexo ? '📎 Anexo' : '');
        if (!texto) return;
        if (!caixaPrevias) {
            caixaPrevias = document.createElement('div');
            caixaPrevias.className = 'cf-previas'; caixaPrevias.setAttribute('aria-live', 'polite');
            ctx.view.appendChild(caixaPrevias);
        }
        const el = document.createElement('div');
        el.className = 'cf-previa';
        el.innerHTML = `<div><b>${esc(m.nome || 'Alguém')}${m.onde ? ' · ' + esc(m.onde) : ''}</b><span>${esc(texto.slice(0, 160))}</span></div>`;
        caixaPrevias.appendChild(el);
        while (caixaPrevias.children.length > 3) caixaPrevias.firstChild.remove();
        setTimeout(() => { el.classList.add('saindo'); setTimeout(() => el.remove(), 320); }, 5500);
    }

    // =============================================================================================================
    // Grade que se ajusta, quadro principal e faixa
    // =============================================================================================================
    let agendado = 0, assinatura = '', autoId = null, falanteCand = null, falanteTimer = 0;

    function temVideo(card) {
        const id = card.id || '';
        if (id.includes('-screen-') || id.startsWith('screen-card-')) return true;
        const v = card.querySelector('video');
        return !!v && v.style.display !== 'none';
    }
    function ehTela(card) { const id = card.id || ''; return id.includes('-screen-') && !id.startsWith('screen-card-'); }

    // Melhor nº de colunas pra encher a área com quadros do mesmo tamanho (testa 16:9, 4:3 e quadrado; prefere 16:9)
    function melhorGrade(n, W, H, gap) {
        let melhor = { w: 0, h: 0, score: 0 };
        for (const [razao, peso] of [[16 / 9, 1], [4 / 3, 0.9], [1, 0.78]]) {
            for (let cols = 1; cols <= n; cols++) {
                const rows = Math.ceil(n / cols);
                const cw = (W - gap * (cols - 1)) / cols, ch = (H - gap * (rows - 1)) / rows;
                if (cw <= 0 || ch <= 0) continue;
                const w = Math.min(cw, ch * razao), h = w / razao;
                const score = w * h * peso;
                if (score > melhor.score) melhor = { w, h, score };
            }
        }
        return melhor;
    }

    function escolherPrincipal(cards) {
        const focada = cards.find((c) => c.classList.contains('focused'));
        if (focada) return focada;
        if (opc.grade || cards.length < 2) return null;
        const tela = cards.find(ehTela);
        if (tela) return tela;
        // sem "Exibição em grade": o principal acompanha quem fala, mas só troca depois de 1,2 s seguidos (não fica pulando)
        const falando = cards.find((c) => c.classList.contains('is-speaking') && c.id !== 'my-video-card');
        if (falando && falando.id !== autoId) {
            if (falanteCand !== falando.id) {
                falanteCand = falando.id; clearTimeout(falanteTimer);
                falanteTimer = setTimeout(() => {
                    const c = document.getElementById(falanteCand);
                    if (c && c.classList.contains('is-speaking')) { autoId = falanteCand; recalcular(true); }
                }, 1200);
            }
        } else if (!falando) { falanteCand = null; clearTimeout(falanteTimer); }
        let atual = autoId && cards.find((c) => c.id === autoId);
        if (!atual) { atual = cards.find((c) => c.id !== 'my-video-card') || null; autoId = atual ? atual.id : null; }
        return atual;
    }

    function recalcular(forcar) {
        if (!ctx) return;
        if (agendado && !forcar) return;
        cancelAnimationFrame(agendado);
        agendado = requestAnimationFrame(() => { agendado = 0; calcular(); });
    }

    function calcular() {
        const grade = ctx.grade;
        if (!grade.isConnected || !grade.offsetParent) return;
        const todos = [...grade.querySelectorAll(':scope > .video-card')];
        let semVideoOculto = 0;
        todos.forEach((c) => {
            const sem = !temVideo(c);
            let ocultar = false;
            if (c.id === 'my-video-card' && !opc.minha) ocultar = true;
            else if (sem && !opc.semVideo) { ocultar = true; semVideoOculto++; }
            c.classList.toggle('cu-sem-video', sem);
            c.classList.toggle('cu-oculto', ocultar);
        });
        const cards = todos.filter((c) => !c.classList.contains('cu-oculto'));
        const n = cards.length;
        const vazia = n === 0;
        ctx.view.classList.toggle('cu-grade-vazia', vazia);
        const msgVazio = ctx.view.querySelector('.cu-vazio');
        if (msgVazio && vazia) msgVazio.textContent = semVideoOculto ? 'Ninguém está com a câmera ou a tela ligada. Ligue "Mostrar participantes sem vídeo" nos 3 pontinhos pra ver todo mundo.' : 'Não tem ninguém pra mostrar. Ligue "Mostrar minha própria câmera" nos 3 pontinhos.';

        const principal = n ? escolherPrincipal(cards) : null;
        cards.forEach((c) => c.classList.toggle('cu-principal', c === principal));

        const cs = getComputedStyle(grade);
        const pl = parseFloat(cs.paddingLeft) || 0, pr = parseFloat(cs.paddingRight) || 0, pt = parseFloat(cs.paddingTop) || 0, pb = parseFloat(cs.paddingBottom) || 0;
        const gap = parseFloat(cs.columnGap) || 12;
        const W = Math.max(60, grade.clientWidth - pl - pr), H = Math.max(60, grade.clientHeight - pt - pb);
        const mini = ctx.modo() === 'mini';
        const sig = [W | 0, H | 0, gap, n, principal ? principal.id : '-', cards.map((c) => c.id).join(','), mini ? 'm' : 'c'].join('|');
        if (sig === assinatura) return;
        assinatura = sig;

        grade.classList.toggle('cu-auto', true);
        grade.classList.toggle('cu-foco', !!principal && n > 1);
        const set = (k, v) => grade.style.setProperty(k, v);
        let rolar = false;
        if (!n) { grade.classList.remove('cu-rolar'); return; }
        if (principal && n > 1) {
            const outros = n - 1;
            let sh = Math.min(150, Math.max(mini ? 40 : 72, H * 0.22)), rows = 1;
            for (let i = 0; i < 10; i++) {
                const sw = sh * 16 / 9;
                const porLinha = Math.max(1, Math.floor((W + gap) / (sw + gap)));
                rows = Math.ceil(outros / porLinha);
                if (rows * (sh + gap) <= H * 0.45 || sh <= (mini ? 34 : 56)) break;
                sh -= 8;
            }
            const fh = Math.max(mini ? 60 : 120, H - rows * (sh + gap));
            if (fh + rows * (sh + gap) > H + 2) rolar = true;
            set('--cu-fh', fh + 'px'); set('--cu-fh-px', String(fh)); set('--cu-sh', sh + 'px'); set('--cu-sw', (sh * 16 / 9) + 'px');
        } else {
            const g = melhorGrade(n, W, H, gap);
            const minW = mini ? 88 : 150;
            let w = g.w, h = g.h;
            if (w < minW) { w = minW; h = w * 9 / 16; rolar = true; }
            set('--cu-w', Math.floor(w) + 'px'); set('--cu-h', Math.floor(h) + 'px');
        }
        grade.classList.toggle('cu-rolar', rolar);
    }

    function ligarLayout() {
        const grade = ctx.grade;
        grade.classList.toggle('cu-auto', true);
        const vazio = document.createElement('div');
        vazio.className = 'cu-vazio';
        ctx.view.appendChild(vazio);
        if (window.ResizeObserver) new ResizeObserver(() => recalcular()).observe(grade);
        new MutationObserver((recs) => {
            for (const r of recs) {
                const t = r.target;
                if (t === grade) { recalcular(); return; }
                if (t.nodeType === 1 && (t.classList.contains('video-card') || t.tagName === 'VIDEO' || t.classList.contains('video-avatar'))) { recalcular(); return; }
            }
        }).observe(grade, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'style'] });
        window.addEventListener('resize', () => { assinatura = ''; recalcular(); });
        recalcular(true);
    }

    // =============================================================================================================
    // Zoom na câmera/tela dos outros: roda do mouse (no ponto do cursor), arrastar, pinça, botões, "preencher"
    // =============================================================================================================
    const Z_MIN = 1, Z_MAX = 6;
    function zoom(card) {
        const v = card && card.querySelector('video');
        if (!v || card._cuZoom) return;
        card._cuZoom = true;
        card.classList.add('zoomavel');
        const barraZ = document.createElement('div');
        barraZ.className = 'cu-zoom'; barraZ.setAttribute('role', 'group'); barraZ.setAttribute('aria-label', 'Zoom');
        barraZ.innerHTML = `<button type="button" data-z="menos" title="Diminuir o zoom" aria-label="Diminuir o zoom"><i class="fa-solid fa-minus"></i></button>
            <span class="nivel" aria-live="polite">100%</span>
            <button type="button" data-z="mais" title="Aumentar o zoom" aria-label="Aumentar o zoom"><i class="fa-solid fa-plus"></i></button>
            <button type="button" data-z="preencher" title="Preencher o quadro (corta as bordas)" aria-label="Preencher o quadro" aria-pressed="false"><i class="fa-solid fa-expand"></i></button>
            <span class="modo">Ajustado</span>
            <button type="button" data-z="reset" title="Voltar ao normal (2 cliques)" aria-label="Voltar ao normal"><i class="fa-solid fa-rotate-left"></i></button>`;
        card.appendChild(barraZ);
        let z = 1, tx = 0, ty = 0, preencher = false, arr = null, moveu = false, pinca = null;
        const nivelEl = barraZ.querySelector('.nivel'), modoEl = barraZ.querySelector('.modo'), btnPreencher = barraZ.querySelector('[data-z="preencher"]');
        function aplicar() {
            const r = card.getBoundingClientRect();
            const mx = (r.width * (z - 1)) / 2, my = (r.height * (z - 1)) / 2;
            tx = Math.min(mx, Math.max(-mx, tx)); ty = Math.min(my, Math.max(-my, ty));
            v.style.transform = z === 1 ? '' : `translate(${tx}px, ${ty}px) scale(${z})`;
            card.classList.toggle('com-zoom', z > 1);
            card.classList.toggle('cu-preencher', preencher);
            card.classList.toggle('cu-zoom-ativo', z > 1 || preencher);
            nivelEl.textContent = Math.round(z * 100) + '%';
            modoEl.textContent = preencher ? 'Preenchendo' : 'Ajustado';
            btnPreencher.setAttribute('aria-pressed', preencher ? 'true' : 'false');
        }
        function zoomEm(novo, cx, cy) {
            novo = Math.min(Z_MAX, Math.max(Z_MIN, novo));
            const r = card.getBoundingClientRect();
            const px = (cx === undefined ? r.left + r.width / 2 : cx) - r.left - r.width / 2;
            const py = (cy === undefined ? r.top + r.height / 2 : cy) - r.top - r.height / 2;
            tx = px - (px - tx) * (novo / z); ty = py - (py - ty) * (novo / z);
            z = novo; if (z === 1) { tx = ty = 0; }
            aplicar();
        }
        barraZ.addEventListener('click', (e) => {
            e.stopPropagation();
            const b = e.target.closest('button[data-z]'); if (!b) return;
            const a = b.dataset.z;
            if (a === 'mais') zoomEm(z * 1.25);
            else if (a === 'menos') zoomEm(z / 1.25);
            else if (a === 'preencher') { preencher = !preencher; aplicar(); }
            else { z = 1; tx = ty = 0; preencher = false; aplicar(); }
        });
        barraZ.addEventListener('dblclick', (e) => e.stopPropagation());
        card.addEventListener('wheel', (e) => { e.preventDefault(); zoomEm(z * (e.deltaY < 0 ? 1.15 : 1 / 1.15), e.clientX, e.clientY); }, { passive: false });
        card.addEventListener('mousedown', (e) => { if (z > 1 && !e.target.closest('.cu-zoom')) { arr = { x: e.clientX - tx, y: e.clientY - ty }; moveu = false; e.preventDefault(); } });
        window.addEventListener('mousemove', (e) => { if (!arr) return; moveu = true; tx = e.clientX - arr.x; ty = e.clientY - arr.y; aplicar(); });
        window.addEventListener('mouseup', () => { arr = null; });
        card.addEventListener('click', (e) => { if (moveu) { e.stopPropagation(); moveu = false; } }, true);
        card.addEventListener('dblclick', () => { z = 1; tx = ty = 0; preencher = false; aplicar(); });
        // pinça com dois dedos (celular): a rolagem da grade com um dedo só continua normal
        const dist = (t) => Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);
        card.addEventListener('touchstart', (e) => { if (e.touches.length === 2) pinca = { d: dist(e.touches), z }; }, { passive: true });
        card.addEventListener('touchmove', (e) => {
            if (e.touches.length === 2 && pinca) {
                e.preventDefault();
                const t = e.touches;
                zoomEm(pinca.z * dist(t) / pinca.d, (t[0].clientX + t[1].clientX) / 2, (t[0].clientY + t[1].clientY) / 2);
            }
        }, { passive: false });
        card.addEventListener('touchend', () => { pinca = null; }, { passive: true });
        aplicar();
    }

    // =============================================================================================================
    // A janela da call e a janela de Música não se cobrem
    // =============================================================================================================
    function retang(a, b, folga) {
        return a.left < b.right + folga && a.right > b.left - folga && a.top < b.bottom + folga && a.bottom > b.top - folga;
    }
    function evitarSobreposicao() {
        if (!ctx || !ctx.emCall() || ctx.modo() !== 'mini') return;
        const mu = document.getElementById('musica-janela');
        const j = ctx.janela;
        if (!mu || mu.hidden || !j.classList.contains('ativa')) return;
        const m = mu.getBoundingClientRect(), c = j.getBoundingClientRect();
        if (!m.width || !c.width || !retang(c, m, 6)) return;
        const vw = innerWidth, vh = innerHeight, w = c.width, h = c.height;
        const cand = [
            [m.left - w - 12, c.top],                 // ao lado esquerdo da Música
            [m.left - w - 12, 64],
            [12, 64], [12, vh - h - 12],              // cantos livres da esquerda
            [m.left - w - 12, vh - h - 12],
            [vw - w - 12, 64],
        ];
        for (const [x, y] of cand) {
            if (x < 0 || y < 0 || x + w > vw || y + h > vh) continue;
            const alvo = { left: x, top: y, right: x + w, bottom: y + h };
            if (!retang(alvo, m, 6)) { ctx.moverCall(x, y); return; }
        }
    }

    // =============================================================================================================
    // Início
    // =============================================================================================================
    function iniciar(c) {
        ctx = c;
        barra = ctx.view.querySelector('.call-controls-bar');
        main = $('cf-main');
        camada = document.createElement('div'); camada.id = 'cf-camada';
        document.body.appendChild(camada);

        // os botões que já existiam no chat.html (tela e clipe, com id e ouvintes) vão pra camada do leque
        const rotulos = { 'btn-main-screen': 'Tela', 'btn-main-clip': 'Clipe' };
        popupClipe = $('media-popup');
        if (popupClipe) camada.appendChild(popupClipe);
        ['btn-main-screen', 'btn-main-clip'].forEach((id) => {
            const el = $(id); if (!el) return;
            el.classList.add('cf-op');
            el.insertAdjacentHTML('beforeend', `<span class="cf-rotulo">${rotulos[id]}</span>`);
            camada.appendChild(el);
        });
        const novo = (id, rotulo, html, titulo, fn) => {
            const b = document.createElement('button');
            b.type = 'button'; b.id = id; b.className = 'cf-op'; b.title = titulo; b.setAttribute('aria-label', titulo);
            b.innerHTML = `${html}<span class="cf-rotulo">${rotulo}</span>`;
            b.addEventListener('click', (e) => { e.stopPropagation(); fn(); });
            camada.appendChild(b);
            return b;
        };
        novo('cf-op-convidar', 'Convidar', '<i class="fa-solid fa-user-plus"></i>', 'Convidar um amigo para a voz', () => { fecharTudo(); abrirConvite(); });
        novo('cf-op-atividades', 'Atividades', SVG_ESPADAS, 'Atividades da call (jogos)', () => { fecharTudo(); if (typeof Atividades !== 'undefined') Atividades.abrirSeletor(); });
        novo('cf-op-mais', 'Mais', '<i class="fa-solid fa-ellipsis"></i>', 'Mais configurações da call', () => abrirMenu());
        // ordem do leque (esquerda -> direita): tela, clipe, convidar, atividades, mais
        ['btn-main-screen', 'btn-main-clip', 'cf-op-convidar', 'cf-op-atividades', 'cf-op-mais'].forEach((id) => { const el = $(id); if (el) camada.appendChild(el); });

        construirMenu();
        main.addEventListener('click', (e) => { e.stopPropagation(); if (menuAberto) { fecharMenu(); return; } abrirLeque(!leque); });
        camada.addEventListener('click', (e) => {
            // qualquer botão do leque, menos o clipe (que abre o popup dele) e os itens do popup, fecha o leque depois do clique
            const op = e.target.closest('.cf-op');
            if (!op || op.id === 'btn-main-clip') return;
            if (op.id !== 'cf-op-mais') setTimeout(() => abrirLeque(false), 0);
        });
        document.addEventListener('pointerdown', (e) => {
            if (!leque && !menuAberto && !(popupClipe && popupClipe.classList.contains('aberto'))) return;
            if (!e.target.closest) return;
            if (e.target.closest('#cf-camada') || e.target.closest('#cf-main')) return;
            fecharTudo();
        }, true);
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape') return;
            if (conv && conv.classList.contains('aberto')) { fecharConvite(); e.stopPropagation(); return; }
            if (leque || menuAberto) { fecharTudo(); main.focus(); e.stopPropagation(); }
        }, true);
        addEventListener('resize', fecharTudo);
        // ao escolher Gravar/Clipar o popup some e o leque também
        ['pop-btn-gravar', 'pop-btn-clipar'].forEach((id) => { const b = $(id); if (b) b.addEventListener('click', () => setTimeout(fecharTudo, 0)); });
        // clique no clipe: o popup abre (código do chat.html) e a gente o ancora; sem o leque aberto, não fica nada solto
        const clipe = $('btn-main-clip');
        if (clipe) clipe.addEventListener('click', () => setTimeout(() => {
            if (popupAberto()) { abrirLeque(false, true); ancorarPopupClipe(); }
            atualizarBarra();
        }, 0));

        ligarLayout();

        // Música: reposiciona a call se as duas se cobrirem (Música abriu, mudou de tamanho ou a call apareceu).
        // A janela da Música só nasce na primeira vez que alguém a abre, então espera ela aparecer no <body>.
        const vigiarMusica = (mu) => {
            new MutationObserver(() => setTimeout(evitarSobreposicao, 60)).observe(mu, { attributes: true, attributeFilter: ['hidden', 'class'] });
            if (window.ResizeObserver) new ResizeObserver(() => setTimeout(evitarSobreposicao, 60)).observe(mu);
            setTimeout(evitarSobreposicao, 60);
        };
        const jaExiste = $('musica-janela');
        if (jaExiste) vigiarMusica(jaExiste);
        else {
            const espera = new MutationObserver(() => { const mu = $('musica-janela'); if (mu) { espera.disconnect(); vigiarMusica(mu); } });
            espera.observe(document.body, { childList: true });
        }
        addEventListener('resize', () => setTimeout(evitarSobreposicao, 100));
        pintarMenu();
    }

    return {
        iniciar,
        opcao: (k) => opc[k],
        opcoes: () => Object.assign({}, opc),
        sonsLigados: () => opc.sons !== false,
        pintarRuido: () => { if (ctx && menu) pintarMenu(); },
        zoom, recalcular: () => { assinatura = ''; recalcular(true); },
        previaMensagem: (m) => { if (ctx) previaMensagem(m); }, convidado: (d) => { if (ctx) convidado(d); }, aoConvidadoEnviado: (d) => { if (ctx) aoConvidadoEnviado(d); },
        aoMostrar() { if (!ctx) return; fecharTudo(); assinatura = ''; recalcular(true); setTimeout(evitarSobreposicao, 80); },
        aoSair() { if (!ctx) return; fecharTudo(); fecharConvite(); limparPrevias(); autoId = null; assinatura = ''; },
        evitarSobreposicao,
        _teste: { melhorGrade },
    };
})();
