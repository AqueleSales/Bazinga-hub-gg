/* Dicas próprias, botão direito do app e controles das transmissões (objeto global UiExtra).

   O que resolve (feedback do teste com amigos, 03/11/2026):
   - O botão direito não fazia nada em cima de uma pessoa ou de uma transmissão (não dava pra mexer no volume de ninguém) e, na maior parte do
     app, abria o menu do Chrome. Agora: quadro da call = menu com volume, "silenciar pra mim", ver perfil, parar de assistir, tela cheia e janela
     flutuante; campo de texto = Cortar/Copiar/Colar/Selecionar tudo; link e imagem = menu pequeno; o resto não abre menu nenhum.
   - As "dicas" (atributo title) saíam no balãozinho cinza do navegador. Viram uma dica do tema do app (ver #ux-tip).
   - Não dava pra deixar de ver uma transmissão. "Parar de assistir" solta o vídeo (para de desenhar e de decodificar), cala o som da tela e deixa um
     quadro pequeno com o botão "Assistir". A ligação segue de pé, então voltar é instantâneo.

   Nada aqui manda coisa pro servidor: volume e silêncio por pessoa ficam só neste aparelho (localStorage, conveniência de UI).
   Quem usa: chat.html chama UiExtra.iniciar({...}) no fim do script principal, ligarAudioRemoto() chama UiExtra.audioDoCard() e registrarVisual() chama
   UiExtra.reaplicarPeer(). Os testes de fumaça conferem esses ganchos (testes/fumaca_ui_extra.py). */
const UiExtra = (() => {
    'use strict';
    let ctx = null;
    let ligado = false;

    const LS_VOL = 'pnt_vol_pessoas', LS_MUDO = 'pnt_mudo_pessoas';
    const lsLer = (k, pad) => { try { const v = JSON.parse(localStorage.getItem(k)); return v == null ? pad : v; } catch (e) { return pad; } };
    const lsGravar = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* modo privado: vale só nesta sessão */ } };
    const chaveSalvavel = (k) => /^[ut]\d+$/.test(k);

    let vol = {};                 // chave -> volume em % (0 a 100). Chave: u<id da pessoa> (voz), t<id da pessoa> (tela dela)
    let mudos = new Set();        // chaves silenciadas pra mim
    const paradas = new Set();    // ids de quadros de transmissão em que parei de assistir (vale enquanto a call durar)

    function salvar() {
        const v = {}; Object.keys(vol).forEach((k) => { if (chaveSalvavel(k) && vol[k] !== 100) v[k] = vol[k]; });
        lsGravar(LS_VOL, v);
        lsGravar(LS_MUDO, [...mudos].filter(chaveSalvavel));
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Quadros da call: quem é quem, volume e silêncio
    // -----------------------------------------------------------------------------------------------------------------
    const ehQuadroDeTela = (card) => /^vc-.+-screen-/.test(card.id || '');
    const labelDe = (card) => (((card.querySelector('.video-label') || {}).textContent) || '').trim();
    function peerDe(card) { const id = card.id || ''; return id.startsWith('vc-') ? id.slice(3).split('-screen-')[0] : ''; }
    function uidDe(card) {
        const peer = peerDe(card);
        try { const u = ctx && ctx.uidDoPeer && ctx.uidDoPeer(peer); return u ? String(u) : ''; } catch (e) { return ''; }
    }
    function chaveDe(card) {
        if (!card || !card.id || card.id === 'my-video-card' || !card.id.startsWith('vc-')) return null;
        const uid = uidDe(card);
        return (ehQuadroDeTela(card) ? 't' : 'u') + (uid || ('p' + peerDe(card)));
    }
    const pct = (k) => (vol[k] == null ? 100 : vol[k]);

    // Aplica volume/silêncio ao <audio> do quadro. O volume final = volume geral das Configurações x o desta pessoa.
    function aplicarAudio(card, audio) {
        const a = audio || card.querySelector('audio.audio-remoto');
        if (!a) return;
        const k = chaveDe(card);
        const fator = k ? pct(k) / 100 : 1;
        const calado = !!(k && mudos.has(k)) || card.classList.contains('ux-parado');
        a.dataset.fator = String(fator);
        a.dataset.mudo = calado ? '1' : '0';
        let geral = 1; try { geral = ctx.volumeSaida(); } catch (e) { /* usa 1 */ }
        a.volume = Math.max(0, Math.min(1, geral * fator));
        let surdo = false; try { surdo = !!ctx.surdo(); } catch (e) { /* ignora */ }
        a.muted = surdo || calado;
    }
    function definirVolume(card, v) {
        const k = chaveDe(card); if (!k) return;
        vol[k] = Math.max(0, Math.min(100, Math.round(v)));
        if (v > 0) mudos.delete(k);
        salvar(); aplicarAudio(card);
    }
    function alternarMudo(card) {
        const k = chaveDe(card); if (!k) return;
        if (mudos.has(k)) mudos.delete(k); else mudos.add(k);
        salvar(); aplicarAudio(card);
    }
    // quando o servidor diz quem é o dono de um peer (registrarVisual), o volume guardado dessa pessoa vale
    function reaplicarPeer(peerId) {
        if (!ctx || !ctx.grade) return;
        ctx.grade.querySelectorAll('.video-card').forEach((c) => { if (peerDe(c) === String(peerId)) aplicarAudio(c); });
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Parar de assistir
    // -----------------------------------------------------------------------------------------------------------------
    function parar(card, deixar, silencioso) {
        if (!card) return;
        const v = card.querySelector('video');
        if (deixar) {
            if (card.classList.contains('ux-parado')) return;
            card._uxStream = v ? v.srcObject : null;
            if (v) { try { v.pause(); } catch (e) { /* já parado */ } v.srcObject = null; }
            card.classList.add('ux-parado');
            card.classList.remove('focused', 'cu-principal');
            paradas.add(card.id);
            if (ctx.grade && !ctx.grade.querySelector('.video-card.focused')) ctx.grade.classList.remove('focused-mode');
            if (document.fullscreenElement === card) { try { document.exitFullscreen(); } catch (e) { /* ignora */ } }
        } else {
            if (!card.classList.contains('ux-parado')) return;
            card.classList.remove('ux-parado');
            paradas.delete(card.id);
            if (v && card._uxStream) { v.srcObject = card._uxStream; const p = v.play(); if (p && p.catch) p.catch(() => {}); }
            card._uxStream = null;
        }
        aplicarAudio(card);
        try { if (window.CallUI) CallUI.recalcular(); } catch (e) { /* a grade se acerta no próximo evento */ }
        if (!silencioso && deixar) { try { ctx.toast('Você parou de assistir. É só tocar em "Assistir" pra voltar.', 'info'); } catch (e) { /* sem toast */ } }
    }

    function telaCheia(card) {
        const f = card.requestFullscreen || card.webkitRequestFullscreen;
        if (f) { try { const p = f.call(card); if (p && p.catch) p.catch(() => {}); } catch (e) { /* o navegador recusou */ } }
    }
    function janelaFlutuante(card) {
        const v = card.querySelector('video');
        if (v && document.pictureInPictureEnabled && v.requestPictureInPicture) v.requestPictureInPicture().catch(() => ctx.toast('O navegador não abriu a janela flutuante.', 'warning'));
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Menu (um só, desenhado por nós)
    // -----------------------------------------------------------------------------------------------------------------
    let menu = null, fecharMenuFn = null;
    function fecharMenu() { if (fecharMenuFn) { const f = fecharMenuFn; fecharMenuFn = null; f(); } }

    function montarItem(it) {
        if (it.sep) { const d = document.createElement('div'); d.className = 'ux-sep'; d.setAttribute('role', 'separator'); return d; }
        if (it.titulo) { const d = document.createElement('div'); d.className = 'ux-ti'; d.textContent = it.titulo; return d; }
        if (it.slider) {
            const s = it.slider, d = document.createElement('div'); d.className = 'ux-sl';
            const fmt = s.fmt || ((v) => v + '%');
            const topo = document.createElement('div'); topo.className = 'ux-sl-topo';
            const rot = document.createElement('span'); rot.textContent = s.rot;
            const num = document.createElement('span'); num.className = 'ux-pct'; num.textContent = fmt(s.valor);
            topo.append(rot, num);
            const r = document.createElement('input'); r.type = 'range'; r.min = s.min; r.max = s.max; r.step = 1; r.value = s.valor;
            r.setAttribute('aria-label', s.rot);
            r.addEventListener('input', () => { num.textContent = fmt(Number(r.value)); s.aoMudar(Number(r.value)); });
            d.append(topo, r);
            return d;
        }
        const b = document.createElement('button'); b.type = 'button'; b.className = 'ux-it' + (it.perigo ? ' perigo' : ''); b.setAttribute('role', 'menuitem');
        if (it.desativado) b.disabled = true;
        const i = document.createElement('i'); i.className = 'fa-solid ' + (it.icone || 'fa-circle'); b.appendChild(i);
        const t = document.createElement('span'); t.textContent = it.rot; b.appendChild(t);
        b.addEventListener('click', () => { fecharMenu(); try { it.acao && it.acao(); } catch (e) { console.warn('[menu]', e); } });
        return b;
    }

    function abrirMenu(x, y, itens) {
        fecharMenu(); esconderTip();
        const el = document.createElement('div');
        el.id = 'ux-menu'; el.setAttribute('role', 'menu');
        itens.forEach((it) => el.appendChild(montarItem(it)));
        document.body.appendChild(el);
        const r = el.getBoundingClientRect();
        let px = x, py = y;
        if (px + r.width > innerWidth - 8) px = Math.max(8, innerWidth - r.width - 8);
        if (py + r.height > innerHeight - 8) py = Math.max(8, innerHeight - r.height - 8);
        el.style.left = px + 'px'; el.style.top = py + 'px';
        setTimeout(() => el.classList.add('on'), 0);
        menu = el;

        const fora = (e) => { if (!el.contains(e.target)) fecharMenu(); };
        const tecla = (e) => {
            if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); fecharMenu(); return; }
            if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
            const bts = [...el.querySelectorAll('.ux-it:not([disabled])')]; if (!bts.length) return;
            e.preventDefault();
            let i = bts.indexOf(document.activeElement);
            i = e.key === 'ArrowDown' ? (i + 1) % bts.length : (i <= 0 ? bts.length - 1 : i - 1);
            bts[i].focus();
        };
        const rolou = (e) => { if (!el.contains(e.target)) fecharMenu(); };
        document.addEventListener('pointerdown', fora, true);
        document.addEventListener('contextmenu', fora, true);
        document.addEventListener('keydown', tecla, true);
        document.addEventListener('scroll', rolou, true);
        window.addEventListener('blur', fecharMenu);
        window.addEventListener('resize', fecharMenu);
        fecharMenuFn = () => {
            document.removeEventListener('pointerdown', fora, true);
            document.removeEventListener('contextmenu', fora, true);
            document.removeEventListener('keydown', tecla, true);
            document.removeEventListener('scroll', rolou, true);
            window.removeEventListener('blur', fecharMenu);
            window.removeEventListener('resize', fecharMenu);
            if (el.parentNode) el.remove();
            if (menu === el) menu = null;
        };
        const primeiro = el.querySelector('.ux-it:not([disabled])');
        if (primeiro && ctx && ctx.focarMenu) primeiro.focus();
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Menus de cada coisa
    // -----------------------------------------------------------------------------------------------------------------
    function menuQuadro(x, y, card) {
        const k = chaveDe(card); if (!k) return;
        const tela = ehQuadroDeTela(card);
        const nome = labelDe(card) || (tela ? 'Transmissão' : 'Participante');
        const parado = card.classList.contains('ux-parado');
        const calado = mudos.has(k);
        const itens = [{ titulo: nome }];
        itens.push({ slider: { rot: tela ? 'Volume da transmissão' : 'Volume', min: 0, max: 100, valor: calado ? 0 : pct(k), aoMudar: (v) => definirVolume(card, v) } });
        itens.push({ rot: calado ? 'Ativar o som' : 'Silenciar pra mim', icone: calado ? 'fa-volume-high' : 'fa-volume-xmark', acao: () => alternarMudo(card) });
        itens.push({ rot: 'Voltar o volume pra 100%', icone: 'fa-rotate-left', desativado: pct(k) === 100 && !calado, acao: () => { mudos.delete(k); definirVolume(card, 100); } });
        if (tela) {
            itens.push({ sep: true });
            itens.push({ rot: parado ? 'Voltar a assistir' : 'Parar de assistir', icone: parado ? 'fa-eye' : 'fa-eye-slash', acao: () => parar(card, !parado) });
            if (!parado) {
                itens.push({ rot: 'Tela cheia', icone: 'fa-expand', acao: () => telaCheia(card) });
                if (document.pictureInPictureEnabled) itens.push({ rot: 'Janela flutuante', icone: 'fa-window-restore', acao: () => janelaFlutuante(card) });
            }
        } else if (uidDe(card)) {
            itens.push({ sep: true });
            itens.push({ rot: 'Ver perfil', icone: 'fa-id-card', acao: () => { try { ctx.abrirPerfil(Number(uidDe(card)), card); } catch (e) { /* sem perfil */ } } });
        }
        abrirMenu(x, y, itens);
    }

    function selecaoDoCampo(c) {
        if (typeof c.selectionStart === 'number' && c.tagName !== 'DIV') { try { return c.value.substring(c.selectionStart, c.selectionEnd); } catch (e) { return ''; } }
        return String(window.getSelection ? window.getSelection() : '');
    }
    function copiarTexto(t) {
        if (!t) return;
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).catch(() => { try { document.execCommand('copy'); } catch (e) { /* sem área de transferência */ } });
        else { try { document.execCommand('copy'); } catch (e) { /* sem área de transferência */ } }
    }
    function menuCampo(x, y, campo) {
        const senha = campo.type === 'password';
        const sel = selecaoDoCampo(campo);
        const so = !!(campo.readOnly || campo.disabled);
        abrirMenu(x, y, [
            { rot: 'Cortar', icone: 'fa-scissors', desativado: !sel || senha || so, acao: () => { campo.focus(); document.execCommand('cut'); } },
            { rot: 'Copiar', icone: 'fa-copy', desativado: !sel || senha, acao: () => { campo.focus(); if (!document.execCommand('copy')) copiarTexto(sel); } },
            { rot: 'Colar', icone: 'fa-paste', desativado: so, acao: () => {
                campo.focus();
                if (!(navigator.clipboard && navigator.clipboard.readText)) { ctx.toast('Use Ctrl+V pra colar.', 'info'); return; }
                navigator.clipboard.readText().then((t) => { campo.focus(); if (t) document.execCommand('insertText', false, t); }).catch(() => ctx.toast('O navegador não deixou colar daqui. Use Ctrl+V.', 'info'));
            } },
            { sep: true },
            { rot: 'Selecionar tudo', icone: 'fa-object-group', acao: () => { campo.focus(); if (typeof campo.select === 'function') campo.select(); else document.execCommand('selectAll'); } },
        ]);
    }
    const urlSegura = (u) => { try { const x = new URL(u, location.href); return (x.protocol === 'http:' || x.protocol === 'https:') ? x.href : ''; } catch (e) { return ''; } };
    function menuLink(x, y, a, selecionado) {
        const href = urlSegura(a.href); if (!href) return false;
        const itens = [];
        if (selecionado) itens.push({ rot: 'Copiar texto', icone: 'fa-copy', acao: () => copiarTexto(selecionado) });
        itens.push({ rot: 'Abrir o link', icone: 'fa-arrow-up-right-from-square', acao: () => window.open(href, '_blank', 'noopener,noreferrer') });
        itens.push({ rot: 'Copiar o endereço do link', icone: 'fa-link', acao: () => copiarTexto(href) });
        abrirMenu(x, y, itens); return true;
    }
    function menuImagem(x, y, img) {
        const src = urlSegura(img.currentSrc || img.src); if (!src) return false;
        abrirMenu(x, y, [
            { rot: 'Abrir a imagem em outra aba', icone: 'fa-arrow-up-right-from-square', acao: () => window.open(src, '_blank', 'noopener,noreferrer') },
            { rot: 'Copiar o endereço da imagem', icone: 'fa-link', acao: () => copiarTexto(src) },
            { rot: 'Baixar a imagem', icone: 'fa-download', acao: () => { const a = document.createElement('a'); a.href = src; a.download = ''; a.rel = 'noopener'; document.body.appendChild(a); a.click(); a.remove(); } },
        ]); return true;
    }

    // Botão direito em QUALQUER lugar: o app decide. Quem já tratou (mensagem, contato, servidor...) chama preventDefault antes; este ouvinte fica no
    // window, que só roda depois de todos os do document. Ctrl+Shift+botão direito deixa o menu do navegador (pra quem desenvolve/inspeciona).
    function aoBotaoDireito(e) {
        if (e.defaultPrevented) return;
        if (e.ctrlKey && e.shiftKey) return;
        const alvo = e.target && e.target.nodeType === 1 ? e.target : (e.target && e.target.parentElement);
        e.preventDefault();
        if (!alvo || !alvo.closest) return;
        const x = e.clientX, y = e.clientY;
        const card = alvo.closest('#video-grid .video-card');
        if (card && chaveDe(card)) { menuQuadro(x, y, card); return; }
        const campo = alvo.closest('input, textarea, [contenteditable]:not([contenteditable="false"])');
        if (campo) {
            const t = (campo.type || 'text').toLowerCase();
            if (campo.tagName !== 'INPUT' || ['text', 'search', 'email', 'url', 'tel', 'number', 'password'].includes(t)) { menuCampo(x, y, campo); return; }
        }
        const sel = String(window.getSelection ? window.getSelection() : '').trim();
        const link = alvo.closest('a[href]');
        if (link && menuLink(x, y, link, sel)) return;
        const img = alvo.closest('img:not(.emoji)');
        if (img && menuImagem(x, y, img)) return;
        if (sel) abrirMenu(x, y, [{ rot: 'Copiar', icone: 'fa-copy', acao: () => copiarTexto(sel) }]);
        else fecharMenu();
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Dicas
    // -----------------------------------------------------------------------------------------------------------------
    let tip = null, tipAlvo = null, tipTimer = 0;
    function criarTip() {
        if (tip) return tip;
        tip = document.createElement('div'); tip.id = 'ux-tip'; tip.setAttribute('role', 'tooltip'); tip.setAttribute('aria-hidden', 'true');
        document.body.appendChild(tip);
        return tip;
    }
    function esconderTip() {
        clearTimeout(tipTimer); tipAlvo = null;
        if (tip) tip.classList.remove('on');
    }
    // Lê o texto da dica e tira o atributo title (o navegador não pode mostrar o dele). Se o botão só tem ícone, o texto vira o nome acessível.
    function textoDaDica(el) {
        if (el.hasAttribute('title')) {
            const t = (el.getAttribute('title') || '').trim();
            el.removeAttribute('title');
            if (t) {
                el.setAttribute('data-tip', t);
                if (!el.hasAttribute('aria-label') && !el.hasAttribute('aria-labelledby') && !(el.textContent || '').trim()) el.setAttribute('aria-label', t);
            }
        }
        return el.getAttribute('data-tip') || '';
    }
    function mostrarTip(el, texto) {
        if (!el.isConnected || tipAlvo !== el) return;
        const t = criarTip();
        t.textContent = texto;
        t.style.left = '0px'; t.style.top = '0px';
        const r = el.getBoundingClientRect(), w = t.offsetWidth, h = t.offsetHeight;
        let top = r.top - h - 9, lado = 'acima';
        if (top < 6) { top = r.bottom + 9; lado = 'abaixo'; }
        let left = r.left + r.width / 2 - w / 2;
        left = Math.max(6, Math.min(innerWidth - w - 6, left));
        t.style.left = Math.round(left) + 'px'; t.style.top = Math.round(top) + 'px';
        t.style.setProperty('--seta', Math.round(Math.max(12, Math.min(w - 12, r.left + r.width / 2 - left))) + 'px');
        t.classList.toggle('acima', lado === 'acima'); t.classList.toggle('abaixo', lado === 'abaixo');
        t.classList.add('on');
    }
    function ligarDicas() {
        const sobMouse = window.matchMedia && window.matchMedia('(hover: hover)').matches;
        const candidato = (n) => (n && n.nodeType === 1 && n.closest) ? n.closest('[title]:not(iframe), [data-tip]') : null;
        if (sobMouse) {
            document.addEventListener('mouseover', (e) => {
                const el = candidato(e.target);
                if (!el) { if (tipAlvo) esconderTip(); return; }
                if (el === tipAlvo) return;
                const txt = textoDaDica(el);            // tira o title na hora, antes do navegador mostrar o dele
                esconderTip();
                if (!txt) return;
                tipAlvo = el;
                tipTimer = setTimeout(() => mostrarTip(el, txt), 380);
            }, true);
            document.addEventListener('mouseout', (e) => { if (tipAlvo && !(e.relatedTarget && tipAlvo.contains(e.relatedTarget))) esconderTip(); }, true);
        }
        document.addEventListener('focusin', (e) => {          // teclado: mostra ao focar
            const el = candidato(e.target); if (!el) return;
            let visivel = false; try { visivel = el.matches(':focus-visible'); } catch (err) { visivel = false; }
            if (!visivel) return;
            const txt = textoDaDica(el); if (!txt) return;
            esconderTip(); tipAlvo = el; mostrarTip(el, txt);
        }, true);
        document.addEventListener('focusout', esconderTip, true);
        ['pointerdown', 'keydown', 'wheel', 'contextmenu'].forEach((ev) => document.addEventListener(ev, esconderTip, true));
        window.addEventListener('scroll', esconderTip, true);
        window.addEventListener('blur', esconderTip);
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Botões nos quadros da call
    // -----------------------------------------------------------------------------------------------------------------
    function botao(icone, dica, aoClicar, extra) {
        const b = document.createElement('button'); b.type = 'button';
        if (extra) b.className = extra;
        b.setAttribute('data-tip', dica); b.setAttribute('aria-label', dica);
        b.innerHTML = '<i class="fa-solid ' + icone + '"></i>';
        ['pointerdown', 'mousedown', 'dblclick', 'touchstart'].forEach((ev) => b.addEventListener(ev, (e) => e.stopPropagation(), { passive: true }));
        b.addEventListener('click', (e) => { e.stopPropagation(); aoClicar(e); });
        return b;
    }
    function prepararQuadro(card) {
        if (!card || card._ux || !chaveDe(card)) return;       // o meu quadro e a prévia da minha tela ficam de fora
        card._ux = true;
        const tela = ehQuadroDeTela(card);
        const barra = document.createElement('div'); barra.className = 'ux-barra';
        if (tela) barra.appendChild(botao('fa-eye-slash', 'Parar de assistir', () => parar(card, true), 'vermelho'));
        barra.appendChild(botao('fa-ellipsis-vertical', tela ? 'Volume e opções da transmissão' : 'Volume e opções', (e) => {
            const r = e.currentTarget.getBoundingClientRect(); menuQuadro(r.left, r.bottom + 6, card);
        }));
        card.appendChild(barra);
        if (tela) {
            const caixa = document.createElement('div'); caixa.className = 'ux-parado-box';
            caixa.innerHTML = '<i class="fa-solid fa-eye-slash"></i><b>Você parou de assistir</b><span></span>';
            caixa.querySelector('span').textContent = labelDe(card);
            const b = document.createElement('button'); b.type = 'button'; b.textContent = 'Assistir';
            ['pointerdown', 'mousedown', 'dblclick'].forEach((ev) => b.addEventListener(ev, (e) => e.stopPropagation()));
            b.addEventListener('click', (e) => { e.stopPropagation(); parar(card, false); });
            caixa.appendChild(b);
            card.appendChild(caixa);
            if (paradas.has(card.id)) parar(card, true, true);   // a tela voltou (reconexão): continua parada
        }
        aplicarAudio(card);
    }

    function iniciar(c) {
        ctx = Object.assign({
            esc: (s) => String(s), escUrl: (s) => s, toast: () => {}, grade: document.getElementById('video-grid'),
            volumeSaida: () => 1, surdo: () => false, uidDoPeer: () => null, abrirPerfil: () => {},
        }, c || {});
        vol = {}; const salvo = lsLer(LS_VOL, {});
        Object.keys(salvo).forEach((k) => { if (chaveSalvavel(k) && Number.isFinite(salvo[k])) vol[k] = Math.max(0, Math.min(100, salvo[k])); });
        mudos = new Set((lsLer(LS_MUDO, []) || []).filter(chaveSalvavel));
        if (ligado) return;
        ligado = true;
        ligarDicas();
        window.addEventListener('contextmenu', aoBotaoDireito, false);
        const grade = ctx.grade;
        if (grade) {
            grade.querySelectorAll('.video-card').forEach(prepararQuadro);
            new MutationObserver((recs) => recs.forEach((r) => r.addedNodes.forEach((n) => { if (n.nodeType === 1 && n.classList.contains('video-card')) prepararQuadro(n); }))).observe(grade, { childList: true });
        }
    }

    return {
        iniciar,
        audioDoCard: (card, audio) => { if (ctx) aplicarAudio(card, audio); },
        reaplicarPeer, abrirMenu, fecharMenu,
        parar, aplicarAudio,
        _teste: { chaveSalvavel, textoDaDica },
    };
})();
