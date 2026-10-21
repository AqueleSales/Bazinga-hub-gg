/* Rodada 29 - Ordem dos servidores (barra lateral), pastinhas e DMs fixadas.

   O QUE FAZ
   - Servidores: SEGURE o ícone (~350 ms) e ele "se mexe querendo sair"; solto, sobe com sombra e segue o dedo/mouse. Os vizinhos abrem
     espaço com animação (FLIP: só transform). Segurar EM CIMA de outro por ~2,4 s faz um anel crescer e junta os dois numa PASTINHA
     (nome e cor editáveis, abre e fecha; arrastar pra fora da barra tira da pasta; pasta com 1 servidor se desfaz).
   - DMs: segurar e arrastar reordena. A conversa que a pessoa solta ACIMA da linha vira "fixada" (fica onde foi posta, mensagem nova
     NÃO a move); as outras seguem a ordem de mensagem recente (a que acabou de falar sobe pra primeira vaga logo abaixo da linha).
   - Tudo fica na CONTA: o servidor valida e devolve (`preferencias_carregadas.ordem_servidores/ordem_dms`), então vale em todas as abas.
   - Sem mouse: Alt+setas no ícone/conversa focado, ou o botão direito / tecla de menu ("Mover para cima", "Tirar da pasta"...).

   REGRAS DO PROJETO QUE ESTE ARQUIVO SEGUE
   - só transform/opacity se mexem; prefers-reduced-motion desliga o balanço e o FLIP; dado de usuário (nome da pasta, nome do servidor)
     entra no DOM por textContent/atributo, nunca por innerHTML. */
const Ordem = (() => {
    'use strict';

    const SEGURAR_MS = 350, TREMOR_MS = 120, CANCELA_PX = 9, JUNTAR_MS = 2400, FLIP_MS = 230;
    const EASE = 'cubic-bezier(.2,.8,.2,1)';
    const CORES = ['#5865f2', '#3ba55d', '#faa61a', '#ed4245', '#eb459e', '#00b0f4', '#9b59b6', '#e67e22', '#1abc9c', '#8e9297'];
    const COR_PADRAO = '#5865f2', NOME_PADRAO = 'Pasta', MAX_NOME = 24;
    const RE_COR = /^#[0-9a-fA-F]{6}$/;
    const LS_ABERTAS = 'pnt_pastas_abertas';

    let ctx = null;
    const reduzido = () => !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    const ehCelular = () => !!(window.matchMedia && window.matchMedia('(max-width: 720px), (pointer: coarse) and (max-device-width: 820px)').matches);
    const vibrar = (p) => { try { if (navigator.vibrate && (!navigator.userActivation || navigator.userActivation.hasBeenActive)) navigator.vibrate(p); } catch (e) { /* sem vibração: tudo bem */ } };
    const json = (v) => JSON.stringify(v);

    // ---------- pequenos utilitários ----------
    function mover(pai, el, ref) {
        if (el.parentNode === pai && el.nextElementSibling === ref) return;
        try { if (pai.moveBefore) { pai.moveBefore(el, ref); return; } } catch (e) { /* cai no insertBefore */ }
        pai.insertBefore(el, ref);
    }

    function nomeLimpo(v) {
        if (typeof v !== 'string') return NOME_PADRAO;
        const t = v.replace(/[\u0000-\u001f\u007f​-‏‪-‮⁦-⁩﻿]/g, '').replace(/\s+/g, ' ').trim().slice(0, MAX_NOME).trim();
        return t || NOME_PADRAO;
    }
    const corLimpa = (v) => (typeof v === 'string' && RE_COR.test(v)) ? v.toLowerCase() : COR_PADRAO;

    function lerAbertas() {
        try { const v = JSON.parse(localStorage.getItem(LS_ABERTAS) || '[]'); return Array.isArray(v) ? v.filter(x => typeof x === 'string').slice(0, 60) : []; } catch (e) { return []; }
    }
    function guardarAbertas(set) {
        try { localStorage.setItem(LS_ABERTAS, JSON.stringify([...set].slice(0, 60))); } catch (e) { /* sem armazenamento: só não lembra */ }
    }

    let anuncio = null;
    function anunciar(texto) {
        if (!anuncio) {
            anuncio = document.createElement('div');
            anuncio.className = 'ordem-anuncio'; anuncio.setAttribute('role', 'status'); anuncio.setAttribute('aria-live', 'polite');
            document.body.appendChild(anuncio);
        }
        anuncio.textContent = '';
        setTimeout(() => { anuncio.textContent = texto; }, 30);
    }

    // ---------- FLIP: mede onde cada coisa ESTÁ (com a animação em curso), muda o DOM e anima da posição velha pra nova ----------
    function flip(listar, chave, mutar, opcoes) {
        if (reduzido()) { mutar(); return; }
        const antes = new Map();
        listar().forEach(el => { const k = chave(el); if (k) { const r = el.getBoundingClientRect(); if (r.width && r.height) antes.set(k, r); } });
        listar().forEach(el => el.getAnimations().forEach(a => { if (a.id === 'flip') a.cancel(); }));
        mutar();
        listar().forEach(el => {
            const k = chave(el); if (!k) return;
            const b = el.getBoundingClientRect(); if (!b.width || !b.height) return;
            const a = antes.get(k);
            if (!a) {
                if (antes.size && opcoes && opcoes.entrada) {
                    const an = el.animate([{ opacity: 0, transform: 'scale(.7)' }, { opacity: 1, transform: 'none' }], { duration: 200, easing: EASE });
                    an.id = 'flip';
                }
                return;
            }
            const dx = a.left - b.left, dy = a.top - b.top, sx = a.width / b.width, sy = a.height / b.height;
            if (Math.abs(dx) < .5 && Math.abs(dy) < .5 && Math.abs(sx - 1) < .01 && Math.abs(sy - 1) < .01) return;
            const an = el.animate(
                [{ transformOrigin: '0 0', transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})` }, { transformOrigin: '0 0', transform: 'none' }],
                { duration: FLIP_MS, easing: EASE });
            an.id = 'flip';
        });
    }

    // ==================================================================
    // MOTOR DE ARRASTO (serve a barra de servidores e a lista de DMs)
    // ==================================================================
    function criarMotor(cfg) {
        let s = null;               // o gesto em andamento
        let suprimirAte = 0;

        cfg.raiz.addEventListener('pointerdown', (e) => {
            if (s || e.isPrimary === false) return;
            if (e.pointerType === 'mouse' && e.button !== 0) return;
            if (cfg.bloqueado && cfg.bloqueado()) return;
            const unidade = cfg.achar(e);
            if (!unidade) return;
            s = { unidade, id: e.pointerId, toque: e.pointerType !== 'mouse', x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, fase: 'segurando', quadro: 0, juntar: null };
            s.tTremor = setTimeout(() => { if (s && s.fase === 'segurando' && !reduzido()) unidade.classList.add('arr-segurando'); }, TREMOR_MS);
            s.tPega = setTimeout(pegar, SEGURAR_MS);
        });

        document.addEventListener('pointermove', (e) => {
            if (!s || e.pointerId !== s.id) return;
            s.x = e.clientX; s.y = e.clientY;
            if (s.fase === 'segurando') { if (Math.hypot(s.x - s.x0, s.y - s.y0) > CANCELA_PX) desistir(); return; }
            if (s.fase === 'arrastando') agendar();
        }, { passive: true });
        // no toque, depois de segurar, o dedo não pode rolar a lista: cancela o gesto de rolagem do navegador
        document.addEventListener('touchmove', (e) => { if (s && s.fase !== 'segurando' && e.cancelable) e.preventDefault(); }, { passive: false });
        document.addEventListener('pointerup', (e) => { if (s && e.pointerId === s.id) terminar(false); });
        document.addEventListener('pointercancel', (e) => { if (s && e.pointerId === s.id) terminar(true); });
        document.addEventListener('keydown', (e) => {
            if (s && s.fase === 'arrastando' && e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); terminar(true); }
        }, true);
        // o clique que o navegador dispara ao soltar não pode entrar no servidor/conversa que acabou de ser arrastado
        cfg.raiz.addEventListener('click', (e) => { if (performance.now() < suprimirAte) { e.stopPropagation(); e.preventDefault(); } }, true);
        // o menu de "salvar imagem" do toque longo (Android) não pode abrir por cima do gesto
        cfg.raiz.addEventListener('contextmenu', (e) => { if (s && s.toque) e.preventDefault(); }, true);

        function desistir() {
            if (!s) return;
            clearTimeout(s.tPega); clearTimeout(s.tTremor);
            s.unidade.classList.remove('arr-segurando');
            s = null;
        }

        function pegar() {
            if (!s || s.fase !== 'segurando') return;
            const u = s.unidade;
            if (!u.isConnected) { desistir(); return; }
            u.classList.remove('arr-segurando');
            const alvo = cfg.iconeDe(u);
            const r = alvo.getBoundingClientRect();
            const voo = document.createElement('div');
            voo.className = 'arr-voando ' + (cfg.classeVoo || '');
            voo.style.left = r.left + 'px'; voo.style.top = r.top + 'px'; voo.style.width = r.width + 'px'; voo.style.height = r.height + 'px';
            const copia = alvo.cloneNode(true);
            copia.removeAttribute('id'); copia.removeAttribute('tabindex'); copia.removeAttribute('title');
            copia.querySelectorAll('[id]').forEach(n => n.removeAttribute('id'));
            copia.classList.remove('arr-buraco', 'arr-segurando');
            voo.appendChild(copia);
            document.body.appendChild(voo);
            s.voo = voo; s.r0 = r; s.fase = 'arrastando';
            const marcar = () => { u.classList.add('arr-buraco'); document.body.classList.add('arr-ativo', cfg.classeCorpo); };
            if (cfg.envolver) cfg.envolver(marcar); else marcar();          // a lista de DMs cresce (a zona de "fixar") e anima isso, em vez de pular
            try { window.getSelection().removeAllRanges(); } catch (e) { /* sem seleção */ }
            requestAnimationFrame(() => { if (s && s.voo === voo) voo.classList.add('levantado'); });
            vibrar(12);
            if (cfg.aoPegar) cfg.aoPegar(u);
            agendar();
        }

        function agendar() { if (s && !s.quadro) s.quadro = requestAnimationFrame(quadro); }

        function quadro() {
            if (!s) return;
            s.quadro = 0;
            if (s.fase !== 'arrastando') return;
            s.voo.style.transform = `translate3d(${s.x - s.x0}px, ${s.y - s.y0}px, 0)`;
            const rolou = autoRolar();
            if (rolou) cancelarJuntar();
            const d = cfg.decidir(s.x, s.y, s.unidade);
            if (d && d.juntar) iniciarJuntar(d.juntar);
            else { cancelarJuntar(); if (d && d.inserir) cfg.aplicar(s.unidade, d.inserir); }
            if (rolou) agendar();
        }

        function autoRolar() {
            const sc = cfg.rolavel && cfg.rolavel();
            if (!sc) return false;
            const r = sc.getBoundingClientRect(), borda = 46;
            let v = 0;
            if (s.y < r.top + borda) v = -Math.ceil((r.top + borda - s.y) / 4);
            else if (s.y > r.bottom - borda) v = Math.ceil((s.y - (r.bottom - borda)) / 4);
            v = Math.max(-16, Math.min(16, v));
            if (!v) return false;
            const antes = sc.scrollTop;
            sc.scrollTop += v;
            return sc.scrollTop !== antes;
        }

        // ---- segurar EM CIMA de outro: o anel cresce e, completo, vira pasta ----
        function iniciarJuntar(j) {
            if (s.juntar && s.juntar.el === j.el) return;
            cancelarJuntar();
            const ic = cfg.iconeDe(j.el);
            const r = ic.getBoundingClientRect();
            const anel = document.createElement('div');
            anel.className = 'arr-anel';
            anel.style.cssText = `left:${r.left - 8}px;top:${r.top - 8}px;width:${r.width + 16}px;height:${r.height + 16}px;--juntar-ms:${JUNTAR_MS}ms`;
            anel.innerHTML = '<svg viewBox="0 0 100 100" aria-hidden="true"><circle class="fundo" cx="50" cy="50" r="46" pathLength="100"></circle><circle class="prog" cx="50" cy="50" r="46" pathLength="100"></circle></svg>';
            document.body.appendChild(anel);
            j.el.classList.add('arr-alvo');
            anel.getBoundingClientRect();           // força o estilo inicial antes de ligar a transição
            anel.classList.add('cheio');
            s.juntar = { el: j.el, anel, t: setTimeout(completarJuntar, JUNTAR_MS) };
        }
        function cancelarJuntar() {
            if (!s || !s.juntar) return;
            clearTimeout(s.juntar.t);
            s.juntar.anel.remove();
            s.juntar.el.classList.remove('arr-alvo');
            s.juntar = null;
        }
        function completarJuntar() {
            if (!s || !s.juntar || s.fase !== 'arrastando') return;
            const j = s.juntar; s.juntar = null;
            j.anel.classList.add('pronto');
            setTimeout(() => j.anel.remove(), 300);
            j.el.classList.remove('arr-alvo');
            s.fase = 'juntando';
            vibrar([14, 36, 14]);
            const u = s.unidade, voo = s.voo, rt = cfg.iconeDe(j.el).getBoundingClientRect();
            const fim = () => { limpar(); if (cfg.aoJuntar) cfg.aoJuntar(u, j.el); };
            if (reduzido()) { fim(); return; }
            voo.classList.remove('levantado');
            voo.style.transition = 'transform .24s ease-in, opacity .24s ease-in, scale .24s ease-in';
            voo.style.transform = `translate3d(${rt.left + rt.width / 2 - (s.r0.left + s.r0.width / 2)}px, ${rt.top + rt.height / 2 - (s.r0.top + s.r0.height / 2)}px, 0)`;
            voo.style.scale = '.5';
            voo.style.opacity = '0';
            setTimeout(fim, 250);
        }

        function limpar() {
            if (!s) return;
            if (s.voo) s.voo.remove();
            s.unidade.classList.remove('arr-buraco', 'arr-segurando');
            document.body.classList.remove('arr-ativo', cfg.classeCorpo);
            cancelarJuntar();
            cancelAnimationFrame(s.quadro);
            suprimirAte = performance.now() + 450;
            s = null;
        }

        function terminar(cancelar) {
            if (!s) return;
            clearTimeout(s.tPega); clearTimeout(s.tTremor);
            if (s.fase === 'segurando') { s.unidade.classList.remove('arr-segurando'); s = null; return; }   // foi só um clique/toque
            if (s.fase !== 'arrastando') return;
            cancelarJuntar();
            s.fase = 'voltando';
            cancelAnimationFrame(s.quadro);
            const u = s.unidade, voo = s.voo;
            const fim = () => { limpar(); if (cancelar) { if (cfg.aoCancelar) cfg.aoCancelar(u); } else if (cfg.aoSoltar) cfg.aoSoltar(u); };
            if (reduzido()) { fim(); return; }
            let dx = 0, dy = 0;
            if (!cancelar) { const r = cfg.iconeDe(u).getBoundingClientRect(); dx = r.left - s.r0.left; dy = r.top - s.r0.top; }
            voo.classList.remove('levantado');
            voo.style.transition = 'transform .18s cubic-bezier(.2,.8,.2,1), scale .18s ease-out';
            voo.style.transform = `translate3d(${dx}px, ${dy}px, 0)`;
            setTimeout(fim, 185);
        }

        return { ativo: () => !!s };
    }

    // ==================================================================
    // SERVIDORES (barra lateral) + PASTAS
    // ==================================================================
    const S = { container: null, servidores: [], criarIcone: null, base: [], layout: [], abertas: new Set(), motor: null, pendente: false,
                pendenteLayout: null, aguardando: 0, tAguarda: 0, tSalvar: 0, foco: null, editor: null };

    // ---- regras do layout (as mesmas de app/ordem.py; o servidor sempre revalida) ----
    function limpar(bruto, ids) {
        const validos = new Set(ids), vistos = new Set(), pastas = new Set(), out = [];
        for (const it of (Array.isArray(bruto) ? bruto : [])) {
            if (typeof it === 'number') { if (validos.has(it) && !vistos.has(it)) { vistos.add(it); out.push(it); } continue; }
            if (!it || typeof it !== 'object' || !Array.isArray(it.ids) || typeof it.pasta !== 'string' || pastas.has(it.pasta)) continue;
            pastas.add(it.pasta);
            const lista = [];
            for (const x of it.ids) if (validos.has(x) && !vistos.has(x)) { vistos.add(x); lista.push(x); }
            if (lista.length >= 2) out.push({ pasta: it.pasta, nome: nomeLimpo(it.nome), cor: corLimpa(it.cor), ids: lista });
            else out.push(...lista);                       // pasta com 1 servidor (ou nenhum) se desfaz
        }
        return out;
    }
    function completar(layout, ids) {
        const presentes = new Set();
        layout.forEach(it => { if (typeof it === 'number') presentes.add(it); else it.ids.forEach(x => presentes.add(x)); });
        return layout.concat(ids.filter(i => !presentes.has(i)));
    }
    const copiar = (l) => JSON.parse(JSON.stringify(l));
    function acharNoLayout(l, id) {
        for (let i = 0; i < l.length; i++) {
            const it = l[i];
            if (it === id) return { i, k: -1, dentro: false };
            if (typeof it === 'object' && it.ids.includes(id)) return { i, k: it.ids.indexOf(id), dentro: true };
        }
        return null;
    }
    function tirarDoLayout(l, id) {
        const p = acharNoLayout(l, id);
        if (!p) return;
        if (p.dentro) l[p.i].ids.splice(p.k, 1); else l.splice(p.i, 1);
    }
    function moverDelta(layout, id, d) {                   // id de servidor (number) ou de pasta (string)
        const l = copiar(layout);
        if (typeof id === 'string') {
            const i = l.findIndex(it => typeof it === 'object' && it.pasta === id), j = i + d;
            if (i < 0 || j < 0 || j >= l.length) return l;
            const [x] = l.splice(i, 1); l.splice(j, 0, x);
            return l;
        }
        const p = acharNoLayout(l, id);
        if (!p) return l;
        if (p.dentro) {
            const f = l[p.i], j = p.k + d;
            if (j >= 0 && j < f.ids.length) { [f.ids[p.k], f.ids[j]] = [f.ids[j], f.ids[p.k]]; return l; }
            f.ids.splice(p.k, 1);
            l.splice(d < 0 ? p.i : p.i + 1, 0, id);        // saiu da pasta pelo lado de cima/baixo
            return l;
        }
        const j = p.i + d;
        if (j < 0 || j >= l.length) return l;
        const [x] = l.splice(p.i, 1); l.splice(j, 0, x);
        return l;
    }
    function moverExtremo(layout, id, fim) {
        const l = copiar(layout);
        if (typeof id === 'string') {
            const i = l.findIndex(it => typeof it === 'object' && it.pasta === id);
            if (i < 0) return l;
            const [x] = l.splice(i, 1); fim ? l.push(x) : l.unshift(x);
            return l;
        }
        tirarDoLayout(l, id);
        fim ? l.push(id) : l.unshift(id);
        return l;
    }
    const novoIdPasta = () => 'p' + Math.random().toString(36).slice(2, 9).replace(/[^a-z0-9]/g, 'x').padEnd(7, 'x');
    function proximaCor(l) { return CORES[l.filter(it => typeof it === 'object').length % CORES.length]; }
    function pastaNova(layout, alvoId, movidoId) {
        const l = copiar(layout);
        tirarDoLayout(l, movidoId);
        const p = acharNoLayout(l, alvoId);
        if (!p || p.dentro) return { layout, pid: null };
        const pid = novoIdPasta();
        l.splice(p.i, 1, { pasta: pid, nome: NOME_PADRAO, cor: proximaCor(l), ids: [alvoId, movidoId] });
        return { layout: l, pid };
    }
    function entrarNaPasta(layout, pid, movidoId) {
        const l = copiar(layout);
        tirarDoLayout(l, movidoId);
        const f = l.find(it => typeof it === 'object' && it.pasta === pid);
        if (!f) return layout;
        f.ids.push(movidoId);
        return l;
    }
    function desfazerPastaNoLayout(layout, pid) {
        const l = copiar(layout), i = l.findIndex(it => typeof it === 'object' && it.pasta === pid);
        if (i < 0) return l;
        const f = l[i];
        l.splice(i, 1, ...f.ids);
        return l;
    }

    // ---- desenho ----
    const ids = () => S.servidores.map(s => s.id);

    function desenharServidores(container, servidores, criarIcone) {
        S.container = container; S.servidores = servidores; S.criarIcone = criarIcone;
        if (S.motor && S.motor.ativo()) { S.pendente = true; return; }       // não troca o DOM debaixo de um arrasto
        renderizar(container.children.length > 0);
    }

    function wrapperDe(srv) {
        const w = S.criarIcone(srv);
        w.dataset.sid = String(srv.id);
        const ic = w.querySelector('.server-icon');
        if (ic) { ic.tabIndex = 0; ic.setAttribute('role', 'button'); ic.setAttribute('aria-label', srv.name || 'Servidor'); }
        w.querySelectorAll('img').forEach(i => { i.draggable = false; i.alt = ''; });
        return w;
    }

    function miniDe(srv) {
        const sp = document.createElement('span');
        const url = srv && ctx.escUrl(srv.iconUrl);
        if (url) { const im = document.createElement('img'); im.src = url; im.alt = ''; im.draggable = false; sp.appendChild(im); }
        else sp.textContent = srv ? (srv.name || '?').trim().slice(0, 1).toUpperCase() : '';
        return sp;
    }

    function elementoPasta(p, porId) {
        const el = document.createElement('div');
        el.className = 'pasta' + (S.abertas.has(p.pasta) ? ' aberta' : '');
        el.dataset.pasta = p.pasta; el.dataset.nome = p.nome; el.dataset.cor = p.cor;
        el.style.setProperty('--pc', p.cor);
        const fundo = document.createElement('div'); fundo.className = 'pasta-fundo';
        const cab = document.createElement('div'); cab.className = 'server-wrapper pasta-cabeca';
        const ic = document.createElement('div');
        ic.className = 'server-icon pasta-icone'; ic.tabIndex = 0; ic.setAttribute('role', 'button');
        const mini = document.createElement('div'); mini.className = 'pasta-mini';
        p.ids.slice(0, 4).forEach(id => mini.appendChild(miniDe(porId.get(id))));
        ic.appendChild(mini);
        const aberta = document.createElement('i'); aberta.className = 'fa-solid fa-folder-open'; aberta.setAttribute('aria-hidden', 'true');
        ic.appendChild(aberta);
        cab.appendChild(ic);
        const ed = document.createElement('button');
        ed.type = 'button'; ed.className = 'pasta-editar'; ed.setAttribute('aria-label', 'Nome e cor da pasta'); ed.title = 'Nome e cor da pasta';
        ed.innerHTML = '<i class="fa-solid fa-pen" aria-hidden="true"></i>';
        cab.appendChild(ed);
        const nome = document.createElement('div'); nome.className = 'pasta-nome';
        const envolve = document.createElement('div'); envolve.className = 'pasta-envolve';
        const lista = document.createElement('div'); lista.className = 'pasta-lista';
        p.ids.forEach(id => { const srv = porId.get(id); if (srv) lista.appendChild(wrapperDe(srv)); });
        envolve.appendChild(lista);
        el.append(fundo, cab, nome, envolve);
        rotularPasta(el);
        return el;
    }

    function rotularPasta(el) {
        const n = el.querySelectorAll('.pasta-lista > [data-sid]').length, nome = el.dataset.nome;
        const ic = el.querySelector('.pasta-icone');
        ic.title = nome;
        ic.setAttribute('aria-label', `Pasta ${nome}, ${n} servidores`);
        ic.setAttribute('aria-expanded', el.classList.contains('aberta') ? 'true' : 'false');
        el.querySelector('.pasta-nome').textContent = nome;
    }

    function renderizar(comFlip) {
        const c = S.container; if (!c) return;
        const idsAtuais = ids();
        S.layout = completar(limpar(S.base, idsAtuais), idsAtuais);
        const porId = new Map(S.servidores.map(s => [s.id, s]));
        if (S.servidores.length) {          // esquece pasta que não existe mais (o que sobra no localStorage nunca cresce)
            const vivas = new Set(S.layout.filter(it => typeof it === 'object').map(it => it.pasta));
            const sobra = [...S.abertas].filter(p => !vivas.has(p));
            if (sobra.length) { sobra.forEach(p => S.abertas.delete(p)); guardarAbertas(S.abertas); }
        }
        const montar = () => {
            c.textContent = '';
            S.layout.forEach(it => {
                if (typeof it === 'number') { const srv = porId.get(it); if (srv) c.appendChild(wrapperDe(srv)); }
                else c.appendChild(elementoPasta(it, porId));
            });
            marcarAtivo();
            restaurarFoco();
        };
        if (comFlip) flip(elementosFlipServidores, chaveServidor, montar, { entrada: true }); else montar();
    }

    const elementosFlipServidores = () => [...S.container.querySelectorAll('[data-sid], .pasta-cabeca, .pasta-fundo')];
    function chaveServidor(el) {
        if (el.dataset.sid) return 's' + el.dataset.sid;
        const pid = el.parentNode && el.parentNode.dataset && el.parentNode.dataset.pasta;
        if (!pid) return null;
        return (el.classList.contains('pasta-cabeca') ? 'p' : 'f') + pid;
    }

    function marcarAtivo() {
        if (!S.container) return;
        S.container.querySelectorAll('.pasta').forEach(p => p.classList.toggle('tem-ativo', !!p.querySelector('.server-icon.active')));
    }

    function restaurarFoco() {
        if (!S.foco) return;
        const f = S.foco; S.foco = null;
        const el = typeof f === 'number' ? S.container.querySelector(`[data-sid="${f}"] .server-icon`) : S.container.querySelector(`.pasta[data-pasta="${CSS.escape(f)}"] .pasta-icone`);
        if (el) el.focus({ preventScroll: false });
    }

    // ---- salvar na conta ----
    function salvarLayout() {
        clearTimeout(S.tSalvar);
        S.tSalvar = setTimeout(() => {
            S.aguardando++;
            clearTimeout(S.tAguarda);
            S.tAguarda = setTimeout(() => { S.aguardando = 0; }, 5000);       // o servidor não respondeu (erro): não ignora o próximo aviso pra sempre
            ctx.socket.emit('salvar_ordem_servidores', { layout: S.layout });
        }, 220);
    }

    function aplicarLayout(novo, opcoes) {
        const idsAtuais = ids();
        const l = completar(limpar(novo, idsAtuais), idsAtuais);
        const mudou = json(l) !== json(S.layout);
        S.base = l; S.layout = l;
        if (!opcoes || opcoes.renderizar !== false) renderizar(true);
        if (mudou) salvarLayout();
        return l;
    }

    function receberLayout(lista) {
        if (S.aguardando > 0) { S.aguardando--; if (S.aguardando > 0) return; }       // eco de um salvamento meu que já foi superado
        if (S.motor && S.motor.ativo()) { S.pendenteLayout = lista; return; }
        if (!S.container || !S.servidores.length) { S.base = lista; return; }
        const idsAtuais = ids();
        const novo = completar(limpar(lista, idsAtuais), idsAtuais);
        if (json(novo) === json(S.layout)) return;
        S.base = novo;
        renderizar(true);
    }

    // ---- arrastar ----
    function decidirBlocos(y, u) {
        let ref = null;
        for (const k of S.container.children) {
            if (k === u) continue;
            const r = k.getBoundingClientRect();
            if (!r.height) continue;
            if (y < r.top + r.height / 2) { ref = k; break; }
        }
        return { inserir: { pai: S.container, ref } };
    }
    const seguinte = (el, u) => { let n = el.nextElementSibling; if (n === u) n = n.nextElementSibling; return n; };

    function decidirServidor(x, y, u) {
        const c = S.container;
        const barra = c.closest('.servers-sidebar') || c;
        const fora = x > barra.getBoundingClientRect().right + 12;     // arrastou pra fora da barra: decide entre os blocos de cima (assim se tira da pasta)
        if (u.classList.contains('pasta') || fora) return decidirBlocos(y, u);
        const meu = u.getBoundingClientRect();
        if (y >= meu.top && y <= meu.bottom) return null;              // em cima do próprio buraco: nada muda
        let melhor = null, dist = Infinity;
        c.querySelectorAll('.server-wrapper[data-sid], .pasta-cabeca').forEach(row => {
            if (row === u) return;
            const r = row.getBoundingClientRect();
            if (!r.height || !r.width) return;
            const d = y < r.top ? r.top - y : (y > r.bottom ? y - r.bottom : 0);
            if (d < dist) { dist = d; melhor = { row, r }; }
        });
        if (!melhor) return { inserir: { pai: c, ref: null } };
        const { row, r } = melhor, f = (y - r.top) / r.height;
        if (row.classList.contains('pasta-cabeca')) {
            const pasta = row.parentNode;
            if (!pasta.classList.contains('aberta')) {
                if (f > .25 && f < .75) return { juntar: { el: pasta } };
                return { inserir: { pai: c, ref: f <= .25 ? pasta : seguinte(pasta, u) } };
            }
            if (f < .35) return { inserir: { pai: c, ref: pasta } };
            const lista = pasta.querySelector('.pasta-lista');
            return { inserir: { pai: lista, ref: [...lista.children].find(k => k !== u) || null } };
        }
        if (row.parentNode === c) {
            if (f > .25 && f < .75) return { juntar: { el: row } };
            return { inserir: { pai: c, ref: f <= .25 ? row : seguinte(row, u) } };
        }
        return { inserir: { pai: row.parentNode, ref: f < .5 ? row : seguinte(row, u) } };
    }

    function aplicarServidor(u, ins) {
        let { pai, ref } = ins;
        if (ref === u) ref = u.nextElementSibling;
        if (u.parentNode === pai && u.nextElementSibling === ref) return;
        flip(elementosFlipServidores, chaveServidor, () => mover(pai, u, ref));
    }

    function lerLayoutDoDom() {
        const out = [];
        for (const k of S.container.children) {
            if (k.classList.contains('pasta')) {
                out.push({ pasta: k.dataset.pasta, nome: k.dataset.nome, cor: k.dataset.cor,
                           ids: [...k.querySelectorAll('.pasta-lista > [data-sid]')].map(w => Number(w.dataset.sid)) });
            } else if (k.dataset.sid) out.push(Number(k.dataset.sid));
        }
        return out;
    }

    function depoisDoArrasto() {
        if (S.pendenteLayout) { const l = S.pendenteLayout; S.pendenteLayout = null; receberLayout(l); }
        if (S.pendente) { S.pendente = false; renderizar(true); }
    }

    function aoSoltarServidor() {
        const lido = lerLayoutDoDom(), idsAtuais = ids();
        const l = completar(limpar(lido, idsAtuais), idsAtuais);
        aplicarLayout(l, { renderizar: json(l) !== json(lido) });       // se uma pasta ficou com 1, ela se desfaz aqui
        depoisDoArrasto();
    }

    function aoJuntar(u, alvo) {
        const id = u.classList.contains('pasta') ? null : Number(u.dataset.sid);
        if (id === null) { depoisDoArrasto(); return; }
        const base = completar(limpar(lerLayoutDoDom(), ids()), ids());
        if (alvo.classList.contains('pasta')) {
            const pid = alvo.dataset.pasta;
            aplicarLayout(entrarNaPasta(base, pid, id));
            setTimeout(() => { const ic = S.container.querySelector(`.pasta[data-pasta="${CSS.escape(pid)}"] .pasta-icone`); if (ic) ic.classList.add('pulsa'); }, 60);
        } else {
            const r = pastaNova(base, Number(alvo.dataset.sid), id);
            if (!r.pid) { depoisDoArrasto(); return; }
            S.abertas.add(r.pid); guardarAbertas(S.abertas);
            aplicarLayout(r.layout);
            setTimeout(() => {
                const el = S.container.querySelector(`.pasta[data-pasta="${CSS.escape(r.pid)}"]`);
                if (el) abrirEditorPasta(el, { nova: true });
            }, 90);
        }
        depoisDoArrasto();
    }

    // ---- abrir/fechar, editar, desfazer ----
    function alternarPasta(el) {
        const abre = !el.classList.contains('aberta');
        el.classList.toggle('aberta', abre);
        abre ? S.abertas.add(el.dataset.pasta) : S.abertas.delete(el.dataset.pasta);
        guardarAbertas(S.abertas);
        rotularPasta(el);
    }

    function desfazerPasta(pid) {
        fecharEditor(false);
        S.abertas.delete(pid); guardarAbertas(S.abertas);
        aplicarLayout(desfazerPastaNoLayout(S.layout, pid));
    }

    function atualizarPasta(pid, campos) {
        const l = copiar(S.layout), f = l.find(it => typeof it === 'object' && it.pasta === pid);
        if (!f) return;
        if (campos.nome !== undefined) f.nome = nomeLimpo(campos.nome);
        if (campos.cor !== undefined) f.cor = corLimpa(campos.cor);
        aplicarLayout(l, { renderizar: false });
    }

    function fecharEditor(gravar) {
        const e = S.editor; if (!e) return;
        S.editor = null;
        document.removeEventListener('pointerdown', e.fora, true);
        document.removeEventListener('keydown', e.tecla, true);
        e.pop.remove();
        if (gravar !== false) {
            const nome = nomeLimpo(e.nome), cor = corLimpa(e.cor);
            if (nome !== e.nomeOriginal || cor !== e.corOriginal) atualizarPasta(e.pid, { nome, cor });
        }
        if (e.devolveFoco && e.devolveFoco.isConnected) e.devolveFoco.focus();
    }

    function abrirEditorPasta(el, opcoes) {
        fecharEditor();
        const pid = el.dataset.pasta;
        const e = { pid, el, nome: el.dataset.nome, cor: el.dataset.cor, nomeOriginal: el.dataset.nome, corOriginal: el.dataset.cor, devolveFoco: document.activeElement };
        const pop = document.createElement('div');
        pop.className = 'pasta-pop'; pop.setAttribute('role', 'dialog'); pop.setAttribute('aria-label', 'Nome e cor da pasta');
        pop.style.setProperty('--pc', e.cor);
        pop.innerHTML = '<div class="pp-titulo"><i class="fa-solid fa-folder" aria-hidden="true"></i> Pasta</div>' +
            '<label class="pp-rotulo" for="pp-nome">Nome</label><input id="pp-nome" class="pp-nome" type="text" maxlength="' + MAX_NOME + '" autocomplete="off" spellcheck="false">' +
            '<div class="pp-rotulo">Cor</div><div class="pp-cores" role="group" aria-label="Cor da pasta"></div>' +
            '<div class="pp-acoes"><button type="button" class="pp-desfazer"><i class="fa-solid fa-folder-minus" aria-hidden="true"></i> Desfazer pasta</button><button type="button" class="pp-ok">Pronto</button></div>';
        const entrada = pop.querySelector('.pp-nome');
        entrada.value = e.nome;
        const cores = pop.querySelector('.pp-cores');
        const aplicar = () => {
            el.dataset.nome = nomeLimpo(e.nome); el.dataset.cor = corLimpa(e.cor);
            el.style.setProperty('--pc', el.dataset.cor); pop.style.setProperty('--pc', el.dataset.cor);
            rotularPasta(el);
            cores.querySelectorAll('.pp-cor').forEach(b => b.classList.toggle('sel', b.dataset.cor === e.cor.toLowerCase()));
        };
        CORES.forEach(cor => {
            const b = document.createElement('button');
            b.type = 'button'; b.className = 'pp-cor'; b.dataset.cor = cor; b.style.setProperty('--c', cor); b.setAttribute('aria-label', 'Cor ' + cor);
            b.addEventListener('click', () => { e.cor = cor; aplicar(); });
            cores.appendChild(b);
        });
        const livre = document.createElement('input');
        livre.type = 'color'; livre.className = 'pp-cor-livre'; livre.value = corLimpa(e.cor); livre.setAttribute('aria-label', 'Outra cor');
        livre.addEventListener('input', () => { e.cor = livre.value; aplicar(); });
        cores.appendChild(livre);
        entrada.addEventListener('input', () => { e.nome = entrada.value; aplicar(); });
        entrada.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); fecharEditor(); } });
        pop.querySelector('.pp-ok').addEventListener('click', () => fecharEditor());
        pop.querySelector('.pp-desfazer').addEventListener('click', () => desfazerPasta(pid));
        e.pop = pop;
        e.fora = (ev) => { if (!pop.contains(ev.target)) fecharEditor(); };
        e.tecla = (ev) => { if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); fecharEditor(); } };
        document.body.appendChild(pop);
        if (!ehCelular()) {
            const r = (el.querySelector('.pasta-cabeca') || el).getBoundingClientRect(), barra = S.container.closest('.servers-sidebar') || S.container;
            const w = pop.offsetWidth, h = pop.offsetHeight;
            pop.style.left = Math.min(barra.getBoundingClientRect().right + 12, window.innerWidth - w - 8) + 'px';
            pop.style.top = Math.max(8, Math.min(r.top, window.innerHeight - h - 8)) + 'px';
        }
        S.editor = e;
        aplicar();
        setTimeout(() => { document.addEventListener('pointerdown', e.fora, true); document.addEventListener('keydown', e.tecla, true); }, 0);
        entrada.focus(); if (opcoes && opcoes.nova) entrada.select();
    }

    // ---- menu (botão direito / tecla de menu) ----
    let menuAberto = null;
    function fecharMenu() {
        if (!menuAberto) return;
        document.removeEventListener('pointerdown', menuAberto.fora, true);
        document.removeEventListener('keydown', menuAberto.tecla, true);
        window.removeEventListener('blur', menuAberto.sair);
        menuAberto.el.remove();
        const volta = menuAberto.devolve; menuAberto = null;
        if (volta && volta.isConnected) volta.focus();
    }
    function abrirMenu(x, y, itens) {
        fecharMenu();
        const el = document.createElement('div');
        el.className = 'ordem-menu'; el.setAttribute('role', 'menu');
        itens.forEach(it => {
            if (it === '-') { el.appendChild(document.createElement('hr')); return; }
            const b = document.createElement('button');
            b.type = 'button'; b.setAttribute('role', 'menuitem'); if (it.perigo) b.className = 'perigo'; if (it.desativado) b.disabled = true;
            const ic = document.createElement('i'); ic.className = 'fa-solid ' + it.icone; ic.setAttribute('aria-hidden', 'true');
            b.append(ic, document.createTextNode(it.rotulo));
            b.addEventListener('click', () => { fecharMenu(); it.acao(); });
            el.appendChild(b);
        });
        document.body.appendChild(el);
        const w = el.offsetWidth, h = el.offsetHeight;
        el.style.left = Math.max(8, Math.min(x, window.innerWidth - w - 8)) + 'px';
        el.style.top = Math.max(8, Math.min(y, window.innerHeight - h - 8)) + 'px';
        const botoes = [...el.querySelectorAll('button:not(:disabled)')];
        const m = { el, devolve: document.activeElement };
        m.fora = (ev) => { if (!el.contains(ev.target)) fecharMenu(); };
        m.tecla = (ev) => {
            if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); fecharMenu(); return; }
            if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
                ev.preventDefault();
                const i = botoes.indexOf(document.activeElement);
                botoes[(i + (ev.key === 'ArrowDown' ? 1 : botoes.length - 1)) % botoes.length].focus();
            }
        };
        m.sair = () => fecharMenu();
        document.addEventListener('pointerdown', m.fora, true);
        document.addEventListener('keydown', m.tecla, true);
        window.addEventListener('blur', m.sair);
        menuAberto = m;
        if (botoes[0]) botoes[0].focus();
    }

    function menuDoServidor(unid, x, y) {
        const ehPasta = unid.classList.contains('pasta');
        const id = ehPasta ? unid.dataset.pasta : Number(unid.dataset.sid);
        const igual = (novo) => json(novo) === json(S.layout);
        const sobe = igual(moverDelta(S.layout, id, -1)), desce = igual(moverDelta(S.layout, id, 1));
        const itens = [];
        if (ehPasta) {
            itens.push({ rotulo: unid.classList.contains('aberta') ? 'Fechar a pasta' : 'Abrir a pasta', icone: 'fa-folder-open', acao: () => alternarPasta(unid) });
            itens.push({ rotulo: 'Nome e cor...', icone: 'fa-pen', acao: () => abrirEditorPasta(unid) });
            itens.push('-');
        }
        itens.push({ rotulo: 'Mover para cima', icone: 'fa-arrow-up', desativado: sobe && !(!ehPasta && acharNoLayout(S.layout, id)?.dentro), acao: () => moverPorTeclado(unid, 'ArrowUp') });
        itens.push({ rotulo: 'Mover para baixo', icone: 'fa-arrow-down', desativado: desce && !(!ehPasta && acharNoLayout(S.layout, id)?.dentro), acao: () => moverPorTeclado(unid, 'ArrowDown') });
        itens.push({ rotulo: 'Mover para o topo', icone: 'fa-angles-up', acao: () => moverPorTeclado(unid, 'Home') });
        itens.push({ rotulo: 'Mover para o fim', icone: 'fa-angles-down', acao: () => moverPorTeclado(unid, 'End') });
        if (!ehPasta) {
            const p = acharNoLayout(S.layout, id);
            if (p && p.dentro) {
                itens.push('-');
                itens.push({ rotulo: 'Tirar da pasta', icone: 'fa-folder-minus', acao: () => { S.foco = id; aplicarLayout(tirarParaForaDaPasta(S.layout, id)); } });
            } else if (p) {
                const prox = S.layout[p.i + 1];
                if (typeof prox === 'number') {
                    itens.push('-');
                    itens.push({ rotulo: 'Juntar com o de baixo numa pasta', icone: 'fa-folder-plus', acao: () => criarPastaPorMenu(id, prox) });
                }
            }
        } else {
            itens.push('-');
            itens.push({ rotulo: 'Desfazer a pasta', icone: 'fa-folder-minus', perigo: true, acao: () => desfazerPasta(id) });
        }
        abrirMenu(x, y, itens);
    }

    function tirarParaForaDaPasta(layout, id) {         // sai da pasta e fica logo depois dela
        const l = copiar(layout), p = acharNoLayout(l, id);
        if (!p || !p.dentro) return l;
        l[p.i].ids.splice(p.k, 1);
        l.splice(p.i + 1, 0, id);
        return l;
    }
    function criarPastaPorMenu(idA, idB) {
        const r = pastaNova(S.layout, idA, idB);
        if (!r.pid) return;
        S.abertas.add(r.pid); guardarAbertas(S.abertas);
        aplicarLayout(r.layout);
        setTimeout(() => {
            const el = S.container.querySelector(`.pasta[data-pasta="${CSS.escape(r.pid)}"]`);
            if (el) abrirEditorPasta(el, { nova: true });
        }, 90);
    }

    // ---- teclado: Alt + setas / Home / End no ícone focado ----
    function moverPorTeclado(unid, tecla) {
        const ehPasta = unid.classList.contains('pasta');
        const id = ehPasta ? unid.dataset.pasta : Number(unid.dataset.sid);
        let novo;
        if (tecla === 'ArrowUp') novo = moverDelta(S.layout, id, -1);
        else if (tecla === 'ArrowDown') novo = moverDelta(S.layout, id, 1);
        else novo = moverExtremo(S.layout, id, tecla === 'End');
        if (json(novo) === json(S.layout)) return;
        S.foco = id;
        const l = aplicarLayout(novo);
        const nome = ehPasta ? unid.dataset.nome : (S.servidores.find(s => s.id === id) || {}).name || 'Servidor';
        const topo = l.findIndex(it => (typeof it === 'object' ? it.pasta === id : it === id));
        if (topo >= 0) anunciar(`${nome} movido para a posição ${topo + 1} de ${l.length}.`);
        else { const f = l.find(it => typeof it === 'object' && it.ids.includes(id)); anunciar(`${nome} movido para a posição ${f.ids.indexOf(id) + 1} de ${f.ids.length} na pasta ${f.nome}.`); }
    }

    function ligarServidores() {
        const c = document.getElementById('dynamic-servers-container');
        if (!c) return;
        S.container = c;

        S.motor = criarMotor({
            raiz: c, classeCorpo: 'arr-servidores',
            achar: (e) => {
                const w = e.target.closest('.server-wrapper[data-sid], .pasta-cabeca');
                if (!w || !c.contains(w) || e.target.closest('.pasta-editar')) return null;
                return w.classList.contains('pasta-cabeca') ? w.parentNode : w;
            },
            bloqueado: () => !!S.editor || !!menuAberto,
            iconeDe: (u) => u.classList.contains('pasta') ? u.querySelector('.pasta-icone') : u.querySelector('.server-icon'),
            rolavel: () => c.closest('.servers-sidebar'),
            decidir: decidirServidor, aplicar: aplicarServidor, aoSoltar: aoSoltarServidor, aoJuntar,
            aoCancelar: () => { renderizar(true); depoisDoArrasto(); }
        });

        c.addEventListener('click', (e) => {
            const cab = e.target.closest('.pasta-cabeca');
            if (!cab) return;
            const pasta = cab.parentNode;
            if (e.target.closest('.pasta-editar')) { abrirEditorPasta(pasta); return; }
            alternarPasta(pasta);
        });
        c.addEventListener('keydown', (e) => {
            const ic = e.target.closest('.server-icon'); if (!ic) return;
            const unid = ic.closest('.pasta-cabeca') ? ic.closest('.pasta') : ic.closest('[data-sid]');
            if (!unid) return;
            if ((e.key === 'Enter' || e.key === ' ') && !e.altKey && e.target === ic) { e.preventDefault(); ic.click(); return; }
            if (e.altKey && ['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(e.key)) { e.preventDefault(); moverPorTeclado(unid, e.key); }
        });
        c.addEventListener('contextmenu', (e) => {
            const w = e.target.closest('.server-wrapper[data-sid], .pasta-cabeca');
            if (!w || !c.contains(w) || (S.motor && S.motor.ativo())) return;
            e.preventDefault();
            const r = e.clientX || e.clientY ? null : w.getBoundingClientRect();     // tecla de menu: sem coordenada, abre no ícone
            menuDoServidor(w.classList.contains('pasta-cabeca') ? w.parentNode : w, r ? r.right + 6 : e.clientX, r ? r.top : e.clientY);
        });
        new MutationObserver(marcarAtivo).observe(c, { subtree: true, attributes: true, attributeFilter: ['class'] });
    }

    // ==================================================================
    // DMs: fixadas no topo + o resto por mensagem recente
    // ==================================================================
    const D = { lista: null, divisor: null, fixas: [], motor: null, aguardando: 0, tAguarda: 0, tSalvar: 0 };

    const cartoesDM = () => D.lista ? [...D.lista.children].filter(k => k.classList.contains('user-dm-item') && k.id !== 'dm-me' && !k.classList.contains('temp-dm')) : [];
    const chaveDM = (el) => el === D.divisor ? 'divisor' : (el.id || null);
    const elementosFlipDM = () => D.lista ? [...D.lista.children].filter(k => k.classList.contains('dm-card') || k === D.divisor) : [];
    const ehFixa = (c) => c.dataset.fixa === '1';
    const idDe = (c) => Number(c.dataset.userId);

    function marcarDMs() {
        if (!D.lista) return;
        let alguma = false;
        D.lista.querySelectorAll('.user-dm-item').forEach(c => {
            if (c.id === 'dm-me') return;
            const fixa = ehFixa(c); alguma = alguma || fixa;
            let pino = c.querySelector(':scope > .dm-pino');
            if (fixa && !pino) {
                pino = document.createElement('i'); pino.className = 'fa-solid fa-thumbtack dm-pino'; pino.setAttribute('aria-hidden', 'true');
                const badge = c.querySelector(':scope > .dm-notification-badge');
                c.insertBefore(pino, badge || null);
            } else if (!fixa && pino) pino.remove();
            c.tabIndex = 0; c.setAttribute('role', 'button');
        });
        D.lista.classList.toggle('tem-fixas', alguma);
        D.lista.classList.toggle('sem-fixas', !alguma);
    }

    // [Anotações] [conversas rápidas/pedidos] [fixadas] [linha] [as outras, por mensagem recente]
    function normalizarDM(flipar, ordemFixas) {
        const kids = [...D.lista.children];
        const eu = kids.find(k => k.id === 'dm-me');
        const temps = kids.filter(k => k.classList.contains('user-dm-item') && k.classList.contains('temp-dm'));
        const cartoes = kids.filter(k => k.classList.contains('user-dm-item') && k.id !== 'dm-me' && !k.classList.contains('temp-dm'));
        let fixas = cartoes.filter(ehFixa);
        if (ordemFixas) fixas.sort((a, b) => ordemFixas.indexOf(idDe(a)) - ordemFixas.indexOf(idDe(b)));
        const resto = cartoes.filter(c => !ehFixa(c));
        const alvo = [eu, ...temps, ...fixas, D.divisor, ...resto].filter(Boolean);
        alvo.push(...kids.filter(k => !alvo.includes(k)));
        if (alvo.every((el, i) => el === kids[i])) return;
        const aplicar = () => { alvo.forEach((el, i) => { const atual = D.lista.children[i]; if (atual !== el) mover(D.lista, el, atual || null); }); };
        D.lista.classList.add('arr-mexendo');
        clearTimeout(D.tMexendo); D.tMexendo = setTimeout(() => D.lista.classList.remove('arr-mexendo'), 60);
        flipar === false ? aplicar() : flip(elementosFlipDM, chaveDM, aplicar);
    }

    function fixasDoDom() { return cartoesDM().filter(ehFixa).map(idDe); }

    function salvarFixas() {
        const atual = fixasDoDom();
        if (json(atual) === json(D.fixas)) return;
        D.fixas = atual;
        clearTimeout(D.tSalvar);
        D.tSalvar = setTimeout(() => {
            D.aguardando++;
            clearTimeout(D.tAguarda);
            D.tAguarda = setTimeout(() => { D.aguardando = 0; }, 5000);
            ctx.socket.emit('salvar_ordem_dms', { fixas: D.fixas });
        }, 220);
    }

    function receberFixas(lista) {
        if (D.aguardando > 0) { D.aguardando--; if (D.aguardando > 0) return; }
        if (!D.lista) { D.fixas = lista; return; }
        if (D.motor && D.motor.ativo()) { D.pendente = lista; return; }
        if (json(lista) === json(fixasDoDom())) { D.fixas = lista; return; }
        D.fixas = lista;
        cartoesDM().forEach(c => { if (lista.includes(idDe(c))) c.dataset.fixa = '1'; else delete c.dataset.fixa; });
        marcarDMs();
        normalizarDM(true, lista);
    }

    function decidirDM(x, y, u) {
        const meu = u.getBoundingClientRect();
        if (y >= meu.top && y <= meu.bottom) return null;
        let melhor = null, dist = Infinity;
        [...cartoesDM(), D.divisor].forEach(row => {
            if (row === u) return;
            const r = row.getBoundingClientRect();
            if (!r.height || !r.width) return;
            const d = y < r.top ? r.top - y : (y > r.bottom ? y - r.bottom : 0);
            if (d < dist) { dist = d; melhor = { row, r }; }
        });
        if (!melhor) return null;
        const { row, r } = melhor;
        if (row === D.divisor) return { inserir: { pai: D.lista, ref: row } };           // em cima da linha = fim das fixadas
        const f = (y - r.top) / r.height;
        return { inserir: { pai: D.lista, ref: f < .5 ? row : seguinte(row, u) } };
    }
    function aplicarDM(u, ins) {
        let { pai, ref } = ins;
        if (ref === u) ref = u.nextElementSibling;
        if (u.parentNode === pai && u.nextElementSibling === ref) return;
        flip(elementosFlipDM, chaveDM, () => mover(pai, u, ref));
    }
    function fimMexendo() {
        clearTimeout(D.tMexendo);
        D.tMexendo = setTimeout(() => D.lista.classList.remove('arr-mexendo'), 120);
    }
    function aoSoltarDM(u) {
        const antes = !!(u.compareDocumentPosition(D.divisor) & Node.DOCUMENT_POSITION_FOLLOWING);      // a linha vem depois dele = ele está acima dela
        if (antes) u.dataset.fixa = '1'; else delete u.dataset.fixa;
        marcarDMs();
        normalizarDM(true);
        salvarFixas();
        fimMexendo();
        if (D.pendente) { const l = D.pendente; D.pendente = null; receberFixas(l); }
    }

    // A conversa que acabou de receber/enviar mensagem sobe pra primeira vaga LIVRE (logo abaixo da linha). Fixada não se mexe.
    function subirDM(card) {
        if (!D.lista || !card || card.id === 'dm-me' || ehFixa(card)) return false;
        const ref = card.classList.contains('temp-dm') ? D.lista.children[1] : D.divisor.nextElementSibling;
        if (!ref || ref === card) return false;
        mover(D.lista, card, ref);
        return true;
    }

    function fixarDM(card, fixar) {
        if (!card) return;
        if (fixar) { card.dataset.fixa = '1'; } else delete card.dataset.fixa;
        // fixar = vai pro FIM das fixadas; soltar = vai pra primeira vaga livre
        if (fixar) { const fixas = cartoesDM().filter(c => ehFixa(c) && c !== card); const ultimo = fixas[fixas.length - 1]; mover(D.lista, card, (ultimo ? ultimo.nextElementSibling : D.divisor)); }
        marcarDMs();
        normalizarDM(true);
        if (!fixar) { const antes = D.divisor.nextElementSibling; if (antes && antes !== card) flip(elementosFlipDM, chaveDM, () => mover(D.lista, card, antes)); }
        salvarFixas();
    }
    function moverFixaDM(card, delta) {
        const fixas = cartoesDM().filter(ehFixa), i = fixas.indexOf(card), j = i + delta;
        if (i < 0) { if (delta < 0) fixarDM(card, true); return; }
        if (j < 0) return;
        if (j >= fixas.length) { fixarDM(card, false); return; }
        flip(elementosFlipDM, chaveDM, () => mover(D.lista, card, delta < 0 ? fixas[j] : seguinte(fixas[j], card)));
        marcarDMs();
        salvarFixas();
        anunciar(`Conversa movida para a posição ${j + 1} das fixadas.`);
    }

    function ligarDMs() {
        const lista = document.getElementById('dm-list-container');
        if (!lista) return;
        D.lista = lista;
        D.divisor = document.getElementById('dm-divisor') || (() => { const d = document.createElement('div'); d.id = 'dm-divisor'; d.className = 'dm-divisor'; d.setAttribute('aria-hidden', 'true'); return d; })();
        cartoesDM().forEach(c => { if (D.fixas.includes(idDe(c))) c.dataset.fixa = '1'; });
        lista.appendChild(D.divisor);
        normalizarDM(false, D.fixas);
        marcarDMs();

        D.motor = criarMotor({
            raiz: lista, classeCorpo: 'arr-dms', classeVoo: 'dm',
            achar: (e) => {
                const c = e.target.closest('.user-dm-item');
                return (c && c.parentNode === lista && c.id !== 'dm-me' && !c.classList.contains('temp-dm')) ? c : null;
            },
            iconeDe: (u) => u,
            envolver: (f) => flip(elementosFlipDM, chaveDM, f),
            rolavel: () => { for (let n = lista; n; n = n.parentElement) { const oy = getComputedStyle(n).overflowY; if ((oy === 'auto' || oy === 'scroll') && n.scrollHeight > n.clientHeight) return n; } return null; },
            decidir: decidirDM, aplicar: aplicarDM, aoSoltar: aoSoltarDM,
            aoPegar: () => { D.snap = [...lista.children]; lista.classList.add('arr-mexendo'); },
            aoCancelar: () => {
                // volta tudo pra onde estava quando a pessoa pegou (a lista de baixo é por mensagem recente, então o DOM de antes é a verdade)
                const snap = (D.snap || []).filter(el => el.parentNode === lista);
                flip(elementosFlipDM, chaveDM, () => snap.forEach((el, i) => { const atual = lista.children[i]; if (atual !== el) mover(lista, el, atual || null); }));
                fimMexendo();
            }
        });
        // cartão novo (amigo aceito, conversa rápida...) também fica focável e com o pino certo
        new MutationObserver((muts) => { if (muts.some(m => m.addedNodes.length)) marcarDMs(); }).observe(lista, { childList: true });

        lista.addEventListener('keydown', (e) => {
            const c = e.target.closest('.user-dm-item');
            if (!c || c.parentNode !== lista || e.target !== c) return;
            if ((e.key === 'Enter' || e.key === ' ') && !e.altKey) { e.preventDefault(); c.click(); return; }
            if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown') && c.id !== 'dm-me' && !c.classList.contains('temp-dm')) {
                e.preventDefault(); moverFixaDM(c, e.key === 'ArrowUp' ? -1 : 1);
            }
        });
    }

    // itens do menu do contato (clique-direito numa conversa) que o chat.html desenha por cima do menu que já existia
    function htmlMenuDM(id) {
        const c = D.lista && document.getElementById('dm-' + id);
        if (!c || c.classList.contains('temp-dm') || c.id === 'dm-me') return '';
        if (!ehFixa(c)) return '<hr><button data-mc="ordem-fixar"><i class="fa-solid fa-thumbtack"></i> Fixar no topo</button>';
        return '<hr><button data-mc="ordem-soltar"><i class="fa-solid fa-thumbtack"></i> Soltar do topo</button>' +
            '<button data-mc="ordem-cima"><i class="fa-solid fa-arrow-up"></i> Mover para cima</button>' +
            '<button data-mc="ordem-baixo"><i class="fa-solid fa-arrow-down"></i> Mover para baixo</button>';
    }
    function acaoMenuDM(acao, id) {
        const c = document.getElementById('dm-' + id);
        if (!c) return;
        if (acao === 'ordem-fixar') fixarDM(c, true);
        else if (acao === 'ordem-soltar') fixarDM(c, false);
        else if (acao === 'ordem-cima') moverFixaDM(c, -1);
        else if (acao === 'ordem-baixo') moverFixaDM(c, 1);
    }

    // ==================================================================
    function iniciar(opcoes) {
        ctx = opcoes;
        S.base = Array.isArray(opcoes.layout) ? opcoes.layout : [];
        D.fixas = (Array.isArray(opcoes.fixas) ? opcoes.fixas : []).filter(n => Number.isInteger(n));
        S.abertas = new Set(lerAbertas());
        ligarServidores();
        ligarDMs();
        ctx.socket.on('preferencias_carregadas', (p) => {
            if (!p || typeof p !== 'object') return;
            if (Array.isArray(p.ordem_servidores)) receberLayout(p.ordem_servidores);
            if (Array.isArray(p.ordem_dms)) receberFixas(p.ordem_dms.filter(n => Number.isInteger(n)));
        });
    }

    return { iniciar, desenharServidores, subirDM, htmlMenuDM, acaoMenuDM,
             // só pros testes de navegador
             _layout: () => copiar(S.layout), _fixas: () => D.fixas.slice(), _moverDelta: moverDelta, _limpar: limpar };
})();
