/* Música: pesquisar e tocar dentro do Pantheon. Uma janelinha flutuante (arrastável; vira folha no celular) com o player OFICIAL do YouTube, a pesquisa, a fila de
   tocar e a "Minha playlist" (a playlist do perfil, que mora nas Conexões). Objeto global `Musica`.
   O que vale aqui: o player do YouTube fica SEMPRE à vista enquanto toca (os termos do player proíbem esconder o vídeo e tocar só o áudio): por isso "minimizar" só
   esconde a pesquisa e a fila, nunca o vídeo, e fechar a janela PARA a música. Quem pesquisa é o servidor (a chave da API nunca chega aqui); a fila é do navegador
   da pessoa (localStorage, só conveniência); a playlist do perfil é a das Conexões (`fila_adicionar`).
   Contexto (Musica.iniciar): { emitir, esc, toast, confirmar(titulo, texto, ok), carregarYt(), pararPerfil(), minhas(), listarConexoes() }.
   Tudo que vem do servidor passa por esc() antes do innerHTML; a capa vem sempre do CDN fixo do YouTube (i.ytimg.com) montada a partir do id validado. */
const Musica = (() => {
    'use strict';
    let ctx = null, janela = null, yt = null, ytPronto = false, pendente = null, seqToca = 0;
    let sp = null, spPronto = false, spUri = null, spFim = false, spPos = 0, fonte = 'yt', tile = false;        // sp = player do Spotify; tile = recolhida (celular)
    let fila = [], idx = -1, aberta = false, mini = false, aba = 'buscar', tocando = false, repetir = false, aleatorio = false, errosSeguidos = 0;
    let estado = { disponivel: null, restantes: null, spotify: false }, resultados = [], resMeta = { origem: '' }, status = ['', ''], tagAtual = '', seqBusca = 0, timerBusca = null, soMusica = true;
    let pos = null, arrasto = null, adicionando = new Set();
    const MAX_FILA = 100;
    const CH_FILA = 'pnt_musica_fila', CH_POS = 'pnt_musica_pos', CH_OPC = 'pnt_musica_opc';
    const MOBILE = '(max-width: 720px), (pointer: coarse) and (max-device-width: 820px)';
    const RE_ID = /^[\w-]{6,40}$/;
    const $ = (s) => (janela ? janela.querySelector(s) : null);
    const T = (v) => ctx.esc(v == null ? '' : v);
    const idOk = (x) => typeof x === 'string' && RE_ID.test(x);
    const capaUrl = (v) => `https://i.ytimg.com/vi/${v}/mqdefault.jpg`;
    const celular = () => window.matchMedia(MOBILE).matches;
    const dur = (s) => { s = Number(s); if (!isFinite(s) || s <= 0) return ''; const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = Math.floor(s % 60); return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(x).padStart(2, '0'); };
    const RE_SP = /^[A-Za-z0-9]{22}$/;
    const ehSp = (it) => !!it && it.s === 'sp';
    const imgSp = (u) => typeof u === 'string' && /^https:\/\/i\.scdn\.co\//.test(u) && u.length <= 200;
    const capaDe = (it) => (ehSp(it) ? (imgSp(it.i) ? it.i : '') : (idOk(it.v) ? capaUrl(it.v) : ''));
    const capa = (it) => { const u = capaDe(it); return u ? `<img class="mu-capa" src="${T(u)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : '<span class="mu-capa vazia"><i class="fa-solid fa-music"></i></span>'; };
    const limpo = (it) => { const o = { v: it.v, t: String(it.t || '').slice(0, 100), a: String(it.a || '').slice(0, 60), d: Number(it.d) > 0 ? Number(it.d) : null }; if (ehSp(it)) { o.s = 'sp'; if (imgSp(it.i)) o.i = it.i; } return o; };
    const valido = (it) => !!it && typeof it === 'object' && (ehSp(it) ? RE_SP.test(it.v || '') : idOk(it.v));
    const mesmo = (a, b) => !!a && !!b && a.v === b.v && ehSp(a) === ehSp(b);

    // ---------------------------------------------------------------------
    // guardar no navegador (conveniência: a fila e a posição da janela)
    // ---------------------------------------------------------------------
    function guardar() { try { localStorage.setItem(CH_FILA, JSON.stringify({ fila, idx })); } catch (e) { /* sem armazenamento: a fila vale até recarregar */ } }
    function restaurar() {
        try {
            const d = JSON.parse(localStorage.getItem(CH_FILA) || 'null');
            if (d && Array.isArray(d.fila)) { fila = d.fila.filter(valido).slice(0, MAX_FILA).map(limpo); idx = Number.isInteger(d.idx) && d.idx >= 0 && d.idx < fila.length ? d.idx : (fila.length ? 0 : -1); }
            const p = JSON.parse(localStorage.getItem(CH_POS) || 'null');
            if (p && isFinite(p.x) && isFinite(p.y)) pos = { x: Number(p.x), y: Number(p.y) };
            const o = JSON.parse(localStorage.getItem(CH_OPC) || 'null');
            if (o) { soMusica = o.so !== false; repetir = !!o.rep; aleatorio = !!o.ale; }
        } catch (e) { /* dado estragado: começa do zero */ }
    }
    const guardarOpc = () => { try { localStorage.setItem(CH_OPC, JSON.stringify({ so: soMusica, rep: repetir, ale: aleatorio })); } catch (e) { /* ignora */ } };

    // ---------------------------------------------------------------------
    // a janela
    // ---------------------------------------------------------------------
    function montar() {
        if (janela) return;
        janela = document.createElement('div');
        janela.id = 'musica-janela'; janela.className = 'musica-janela'; janela.hidden = true;
        janela.setAttribute('role', 'dialog'); janela.setAttribute('aria-label', 'Música');
        janela.innerHTML = `<div class="mu-topo"><i class="fa-solid fa-music"></i><b>Música</b><span class="mu-esp"></span>
                <button type="button" class="mu-ic" data-mu="expandir" title="Abrir a pesquisa e a fila" aria-label="Expandir"><i class="fa-solid fa-up-right-and-down-left-from-center"></i></button>
                <button type="button" class="mu-ic" data-mu="mini" title="Recolher (a música continua)" aria-label="Recolher"><i class="fa-solid fa-window-minimize"></i></button>
                <button type="button" class="mu-ic" data-mu="fechar" title="Fechar (a música para)" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button></div>
            <div class="mu-player" hidden><div class="mu-yt"></div></div>
            <div class="mu-agora" hidden><div class="mu-agora-t"><b></b><small></small></div>
                <div class="mu-ctl"><button type="button" class="mu-ic tg" data-mu="aleatorio" title="Aleatório" aria-label="Aleatório"><i class="fa-solid fa-shuffle"></i></button>
                    <button type="button" class="mu-ic" data-mu="ant" title="Anterior" aria-label="Anterior"><i class="fa-solid fa-backward-step"></i></button>
                    <button type="button" class="mu-ic grande" data-mu="play" title="Tocar/pausar" aria-label="Tocar ou pausar"><i class="fa-solid fa-play"></i></button>
                    <button type="button" class="mu-ic" data-mu="prox" title="Próxima" aria-label="Próxima"><i class="fa-solid fa-forward-step"></i></button>
                    <button type="button" class="mu-ic tg" data-mu="repetir" title="Repetir a fila" aria-label="Repetir a fila"><i class="fa-solid fa-repeat"></i></button></div></div>
            <div class="mu-corpo">
                <nav class="mu-abas"><button type="button" data-aba="buscar" class="on">Pesquisar</button><button type="button" data-aba="fila">Fila <span class="mu-n" data-n="fila"></span></button><button type="button" data-aba="playlist">Minha playlist</button></nav>
                <section data-sec="buscar">
                    <div class="mu-fonte" hidden><button type="button" data-fonte="yt" class="on">YouTube</button><button type="button" data-fonte="sp">Spotify</button></div>
                    <form class="mu-busca" autocomplete="off"><input type="search" id="mu-q" maxlength="300" placeholder="Pesquisar música ou colar link do YouTube" aria-label="Pesquisar música"><button type="submit" class="mu-ic" aria-label="Pesquisar"><i class="fa-solid fa-magnifying-glass"></i></button></form>
                    <label class="mu-opc"><input type="checkbox" id="mu-so"> <span>Só música</span></label><p class="mu-aviso-sp" hidden>Sem login no Spotify neste aparelho, cada música toca só 30 segundos (regra do Spotify). Entre no Spotify no navegador pra ouvir inteira.</p>
                    <p class="mu-status" role="status"></p><div class="mu-lote" hidden></div><ul class="mu-lista" data-lista="res"></ul></section>
                <section data-sec="fila" hidden><div class="mu-lote" data-lote="fila"></div><ul class="mu-lista" data-lista="fila"></ul></section>
                <section data-sec="playlist" hidden><div class="mu-lote" data-lote="playlist"></div><ul class="mu-lista" data-lista="playlist"></ul></section>
                <p class="mu-termos">Pesquisa e player do YouTube e do Spotify (serviços de terceiros). Ao usar, você aceita os <a href="https://www.youtube.com/t/terms" target="_blank" rel="noopener noreferrer">Termos de Serviço do YouTube</a>.</p></div>`;
        document.body.appendChild(janela);
        $('#mu-so').checked = soMusica;
        janela.addEventListener('click', aoClicar);
        $('.mu-busca').addEventListener('submit', (e) => { e.preventDefault(); pesquisar(); });
        $('#mu-so').addEventListener('change', (e) => { soMusica = e.target.checked; guardarOpc(); });
        ligarArrasto();
        window.addEventListener('resize', () => { if (pos && !celular()) posicionar(pos.x, pos.y, false); });
        sessaoMidia();
    }

    function ligarArrasto() {
        const topo = $('.mu-topo');
        topo.addEventListener('pointerdown', (e) => {
            if (e.target.closest('button') || celular()) return;
            const r = janela.getBoundingClientRect();
            arrasto = { dx: e.clientX - r.left, dy: e.clientY - r.top };
            try { topo.setPointerCapture(e.pointerId); } catch (er) { /* sem captura: segue assim mesmo */ }
        });
        topo.addEventListener('pointermove', (e) => { if (arrasto) posicionar(e.clientX - arrasto.dx, e.clientY - arrasto.dy, true); });
        const soltar = () => { if (!arrasto) return; arrasto = null; try { localStorage.setItem(CH_POS, JSON.stringify(pos)); } catch (e) { /* ignora */ } };
        topo.addEventListener('pointerup', soltar); topo.addEventListener('pointercancel', soltar);
    }

    function posicionar(x, y, mudou) {
        const w = janela.offsetWidth, h = janela.offsetHeight;
        x = Math.max(0, Math.min(x, window.innerWidth - w)); y = Math.max(0, Math.min(y, window.innerHeight - Math.min(h, 60)));
        janela.style.left = x + 'px'; janela.style.top = y + 'px'; janela.style.right = 'auto'; janela.style.bottom = 'auto';
        if (mudou) pos = { x, y };
    }

    function abrir() {
        montar();
        aberta = true; janela.hidden = false; janela.classList.toggle('mini', mini);
        if (pos && !celular()) posicionar(pos.x, pos.y, false);
        if (estado.disponivel === null) ctx.emitir('musica_estado', {});
        desenharTudo();
        marcarBotao();
        const q = $('#mu-q'); if (q && !celular() && aba === 'buscar' && !mini) setTimeout(() => q.focus(), 60);
    }
    function fechar() {
        tile = false;
        pararTudo();
        aberta = false; if (janela) janela.hidden = true;
        marcarBotao();
    }
    const alternar = () => { if (aberta && tile) { tile = false; desenharAbas(); } else if (aberta) fechar(); else abrir(); };
    const playerVisivel = () => !!janela && !!$('.mu-player') && !$('.mu-player').hidden;

    function marcarBotao() {
        const b = document.getElementById('btn-musica');
        if (!b) return;
        b.classList.toggle('aberto', aberta); b.classList.toggle('tocando', tocando);
        const n = b.querySelector('.mu-badge'); if (n) { n.textContent = fila.length ? String(fila.length) : ''; n.hidden = !fila.length; }
    }

    // ---------------------------------------------------------------------
    // desenhar
    // ---------------------------------------------------------------------
    function acao(nome, i, icone, titulo, extra) { return `<button type="button" class="mu-ic peq ${extra || ''}" data-mu="${nome}" data-i="${i}" title="${T(titulo)}" aria-label="${T(titulo)}"><i class="fa-solid ${icone}"></i></button>`; }

    function linha(it, acoes, classe, i, padrao) {
        const sub = [it.a, dur(it.d)].filter(Boolean).join(' · ');
        return `<li class="mu-it ${classe || ''}" data-mu-linha="${padrao}" data-i="${i}">${capa(it)}<span class="mu-it-t"><b>${T(it.t || 'Música do YouTube')}</b><small>${T(sub)}</small></span><span class="mu-it-bt">${acoes}</span><span class="mu-eq" aria-hidden="true"><i></i><i></i><i></i></span></li>`;
    }

    function desenharStatus() {
        const s = $('.mu-status'); if (!s) return;
        let txt = status[0], tipo = status[1];
        if (!txt && estado.disponivel === false && fonte === 'yt') { txt = 'A pesquisa por nome ainda não foi ligada neste servidor. Cole o link de uma música ou playlist do YouTube.'; tipo = 'a'; }
        s.textContent = txt; s.className = 'mu-status' + (tipo ? ' ' + tipo : '');
    }

    function desenharResultados() {
        const ul = $('[data-lista="res"]'), lote = $('[data-sec="buscar"] .mu-lote');
        if (!ul) return;
        ul.innerHTML = resultados.map((it, i) => linha(it,
            acao('res-tocar', i, 'fa-play', 'Tocar agora') + acao('res-fila', i, 'fa-list-ol', 'Adicionar à fila') + (ehSp(it) ? '' : acao('res-lista', i, adicionando.has(it.v) ? 'fa-circle-notch fa-spin' : 'fa-compact-disc', 'Adicionar à playlist do meu perfil')),
            mesmo(fila[idx], it) ? 'atual' : '', i, 'res-tocar')).join('');
        const tudo = resMeta.origem === 'playlist' && resultados.length > 1;
        lote.hidden = !tudo;
        lote.innerHTML = tudo ? `<button type="button" class="mu-bt" data-mu="res-tudo-tocar"><i class="fa-solid fa-play"></i> Tocar tudo</button><button type="button" class="mu-bt" data-mu="res-tudo-fila"><i class="fa-solid fa-list-ol"></i> Adicionar tudo à fila</button>` : '';
    }

    function desenharFila() {
        const ul = $('[data-lista="fila"]'), lote = $('[data-lote="fila"]');
        if (!ul) return;
        lote.innerHTML = fila.length ? `<span class="mu-lote-t">${fila.length} ${fila.length === 1 ? 'música' : 'músicas'} na fila</span><button type="button" class="mu-bt perigo" data-mu="fila-limpar"><i class="fa-solid fa-trash"></i> Limpar</button>` : '';
        ul.innerHTML = fila.length ? fila.map((it, i) => linha(it,
            acao('fila-sobe', i, 'fa-chevron-up', 'Subir', i === 0 ? 'off' : '') + acao('fila-desce', i, 'fa-chevron-down', 'Descer', i === fila.length - 1 ? 'off' : '') + acao('fila-tira', i, 'fa-xmark', 'Tirar da fila', 'perigo'),
            i === idx ? 'atual' : '', i, 'fila-tocar')).join('')
            : '<li class="mu-vazio">A fila está vazia. Pesquise uma música e toque em <i class="fa-solid fa-list-ol"></i> pra juntar aqui.</li>';
    }

    function filaDoPerfil() {
        const m = ctx.minhas();
        if (m === null || m === undefined) return null;
        const f = (m || []).find((c) => c.tipo === 'fila');
        return { existe: !!f, faixas: f && f.dados && Array.isArray(f.dados.faixas) ? f.dados.faixas.filter((x) => x && (idOk(x.v) || idOk(x.l))) : [] };
    }

    function desenharPlaylist() {
        const ul = $('[data-lista="playlist"]'), lote = $('[data-lote="playlist"]');
        if (!ul) return;
        const p = filaDoPerfil();
        if (p === null) { lote.innerHTML = ''; ul.innerHTML = '<li class="mu-vazio"><i class="fa-solid fa-circle-notch fa-spin"></i> Carregando a sua playlist...</li>'; return; }
        const toc = p.faixas.filter((f) => idOk(f.v));
        lote.innerHTML = toc.length ? `<button type="button" class="mu-bt" data-mu="pl-tocar"><i class="fa-solid fa-play"></i> Tocar a playlist</button><button type="button" class="mu-bt" data-mu="pl-fila"><i class="fa-solid fa-list-ol"></i> Juntar à fila</button>` : '';
        ul.innerHTML = p.faixas.length ? p.faixas.map((f, i) => {
            const it = { v: f.v, t: f.t || (f.x ? 'Música indisponível' : 'Música do YouTube'), a: f.a || (f.l ? 'playlist' : ''), d: null };
            if (!idOk(f.v)) return `<li class="mu-it" data-i="${i}"><span class="mu-capa vazia"><i class="fa-solid fa-compact-disc"></i></span><span class="mu-it-t"><b>${T(f.t || 'Playlist do YouTube')}</b><small>${T([f.a, 'playlist inteira'].filter(Boolean).join(' · '))}</small></span><span class="mu-it-bt">${acao('pl-abrir', i, 'fa-folder-open', 'Ver as músicas dessa playlist')}${acao('pl-tira', i, 'fa-xmark', 'Tirar da playlist', 'perigo')}</span></li>`;
            return linha(it, acao('pl-tocar-uma', i, 'fa-play', 'Tocar agora') + acao('pl-fila-uma', i, 'fa-list-ol', 'Adicionar à fila') + acao('pl-tira', i, 'fa-xmark', 'Tirar da playlist', 'perigo'), mesmo(fila[idx], { v: f.v }) ? 'atual' : '', i, 'pl-tocar-uma');
        }).join('') : `<li class="mu-vazio">${p.existe ? 'A sua playlist está vazia.' : 'Você ainda não tem uma playlist no perfil.'} Pesquise e toque em <i class="fa-solid fa-compact-disc"></i> pra guardar aqui (e mostrar no seu perfil).</li>`;
    }

    function desenharAgora() {
        const caixa = $('.mu-agora'), it = fila[idx];
        const visivel = !!it && (yt || sp || tocando || fila.length);
        caixa.hidden = !visivel;
        if (it) { caixa.querySelector('b').textContent = it.t || 'Música do YouTube'; caixa.querySelector('small').textContent = [it.a, `${idx + 1} de ${fila.length}`].filter(Boolean).join(' · '); }
        const play = caixa.querySelector('[data-mu="play"] i'); if (play) play.className = 'fa-solid ' + (tocando ? 'fa-pause' : 'fa-play');
        caixa.querySelector('[data-mu="aleatorio"]').classList.toggle('on', aleatorio);
        caixa.querySelector('[data-mu="repetir"]').classList.toggle('on', repetir);
        janela.classList.toggle('tocando', tocando);
        marcarBotao();
    }

    function desenharAbas() {
        janela.querySelectorAll('.mu-abas button').forEach((b) => b.classList.toggle('on', b.dataset.aba === aba));
        janela.querySelectorAll('[data-sec]').forEach((s) => { s.hidden = s.dataset.sec !== aba; });
        const n = $('[data-n="fila"]'); if (n) n.textContent = fila.length ? `(${fila.length})` : '';
        janela.classList.toggle('mini', mini && playerVisivel());
        if (mini && !playerVisivel()) { mini = false; janela.classList.remove('mini'); }
        if (tile && !playerVisivel()) tile = false;
        janela.classList.toggle('tile', tile);
        const f = $('.mu-fonte'); if (f) { f.hidden = !estado.spotify; f.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b.dataset.fonte === fonte)); }
        const so = $('.mu-opc'); if (so) so.hidden = fonte === 'sp';
        const av = $('.mu-aviso-sp'); if (av) av.hidden = fonte !== 'sp';
    }

    function desenharTudo() {
        if (!janela) return;
        desenharAbas(); desenharAgora(); desenharStatus(); desenharResultados(); desenharFila(); desenharPlaylist();
    }

    // ---------------------------------------------------------------------
    // pesquisar
    // ---------------------------------------------------------------------
    function pesquisar() {
        const txt = ($('#mu-q').value || '').trim();
        if (!txt) return;
        tagAtual = 'b' + (++seqBusca);
        status = ['Pesquisando...', '']; desenharStatus();
        clearTimeout(timerBusca);
        const minha = tagAtual;
        timerBusca = setTimeout(() => { if (tagAtual === minha) { status = ['O servidor demorou pra responder. Tente de novo.', 'e']; desenharStatus(); } }, 20000);
        ctx.emitir('musica_buscar', { q: txt, so_musica: soMusica, tag: tagAtual, fonte: fonte === 'sp' ? 'spotify' : 'youtube' });
    }

    function aoResultados(d) {
        if (!d || d.tag !== tagAtual) return;                         // resposta de uma pesquisa antiga
        clearTimeout(timerBusca);
        resultados = (d.itens || []).filter(valido).map(limpo); resMeta = { origem: d.origem || '' };
        if (d.restantes != null) estado.restantes = d.restantes;
        const n = resultados.length;
        let txt = !n ? 'Não achei nada com esse nome. Tente outras palavras (ou desmarque "Só música").'
            : d.origem === 'link' ? 'Pronto: toque na música abaixo.' : d.origem === 'playlist' ? `${n} ${n === 1 ? 'música' : 'músicas'} dessa playlist.` : `${n} ${n === 1 ? 'resultado' : 'resultados'}${d.cache ? ' (já pesquisado há pouco)' : ''}`;
        const aviso = d.origem === 'busca' && !d.cache && estado.restantes != null && estado.restantes <= 5;
        if (aviso) txt += ` · você ainda tem ${estado.restantes} ${estado.restantes === 1 ? 'pesquisa' : 'pesquisas'} hoje`;
        status = [txt, aviso || !n ? 'a' : '']; aba = 'buscar';
        desenharTudo();
    }
    function aoErro(d) {
        if (d && d.tag && d.tag !== tagAtual) return;
        clearTimeout(timerBusca);
        status = [(d && d.msg) || 'Não consegui pesquisar agora.', 'e']; desenharStatus();
    }
    function aoEstado(d) { estado = { disponivel: !!(d && d.disponivel), restantes: d ? d.restantes : null, spotify: !!(d && d.spotify) }; desenharStatus(); if (janela) desenharAbas(); }

    // ---------------------------------------------------------------------
    // a fila (do navegador)
    // ---------------------------------------------------------------------
    function juntar(it) {
        if (!valido(it)) return false;
        if (fila.some((x) => mesmo(x, it))) return 'ja';
        if (fila.length >= MAX_FILA) { ctx.toast(`A fila aceita até ${MAX_FILA} músicas.`, 'warning'); return false; }
        fila.push(limpo(it)); return true;
    }
    function filaMudou() { guardar(); desenharTudo(); }

    function tocarAgora(it) {
        if (!valido(it)) return;
        const ja = fila.findIndex((x) => mesmo(x, it));
        if (ja >= 0) { tocarIndice(ja); return; }
        if (fila.length >= MAX_FILA) { ctx.toast(`A fila aceita até ${MAX_FILA} músicas.`, 'warning'); return; }
        const p = idx >= 0 ? idx + 1 : fila.length;                       // entra logo depois da que toca: a fila continua depois dela
        fila.splice(p, 0, limpo(it));
        tocarIndice(p);
    }

    function tocarLista(itens, inicio) {
        const l = itens.filter(valido).slice(0, MAX_FILA).map(limpo);
        if (!l.length) return;
        fila = l; tocarIndice(Math.max(0, Math.min(inicio || 0, l.length - 1)));
    }

    function remover(i) {
        if (i < 0 || i >= fila.length) return;
        const eraAtual = i === idx;
        fila.splice(i, 1);
        if (!fila.length) { idx = -1; pararTudo(); filaMudou(); return; }
        if (i < idx) idx--;
        if (eraAtual) { idx = Math.min(i, fila.length - 1); if (yt || sp || tocando) { filaMudou(); tocarIndice(idx); return; } }
        filaMudou();
    }
    function mover(i, d) {
        const j = i + d;
        if (i < 0 || j < 0 || j >= fila.length) return;
        [fila[i], fila[j]] = [fila[j], fila[i]];
        if (idx === i) idx = j; else if (idx === j) idx = i;
        filaMudou();
    }

    // ---------------------------------------------------------------------
    // o player (iframe oficial do YouTube, sempre à vista)
    // ---------------------------------------------------------------------
    function destruirYt() {
        if (yt) { try { yt.destroy(); } catch (e) { const f = $('.mu-yt iframe'); if (f) f.remove(); } }
        yt = null; ytPronto = false; pendente = null;
    }
    function destruirSp() {
        if (sp) { try { sp.destroy(); } catch (e) { /* já saiu */ } }
        sp = null; spPronto = false; spUri = null; spFim = false;
    }

    async function tocarIndice(i) {
        const it = fila[i];
        if (!it) return;
        idx = i; guardar();
        ctx.pararPerfil();                                            // o player do cartão de perfil não toca junto
        if (!aberta) abrir();
        const player = $('.mu-player'); player.hidden = false;
        desenharTudo();
        const meu = ++seqToca;
        if (ehSp(it)) { await tocarSpotify(it, meu); sessaoMidia(); return; }
        destruirSp(); $('.mu-yt').classList.remove('sp');
        let api;
        try { api = await ctx.carregarYt(); } catch (e) { ctx.toast('Não consegui carregar o player do YouTube agora. Tente de novo.', 'warning'); return; }
        if (meu !== seqToca || !aberta) return;                       // outra troca (ou fechar) aconteceu enquanto o script baixava
        if (!yt) {
            const f = document.createElement('iframe');
            f.src = `https://www.youtube-nocookie.com/embed/${it.v}?enablejsapi=1&autoplay=1&playsinline=1&rel=0&origin=${encodeURIComponent(location.origin)}`;
            f.title = 'Player do YouTube'; f.allow = 'autoplay; encrypted-media; picture-in-picture'; f.allowFullscreen = true; f.referrerPolicy = 'strict-origin-when-cross-origin';
            $('.mu-yt').replaceChildren(f);
            ytPronto = false; pendente = null;
            yt = new api.Player(f, { events: {
                onReady: () => { ytPronto = true; try { if (pendente) { const v = pendente; pendente = null; yt.loadVideoById(v); } else yt.playVideo(); } catch (e) { /* o navegador pediu um toque no player */ } },
                onStateChange: aoEstadoPlayer, onError: aoErroPlayer } });
        } else if (ytPronto) {
            try { yt.loadVideoById(it.v); } catch (e) { /* o player caiu: o próximo toque recria */ }
        } else pendente = it.v;
        sessaoMidia();
    }

    /** Spotify: player embutido OFICIAL (à vista). Música inteira só com login no Spotify neste aparelho; sem login toca 30 s e a fila segue pra próxima. */
    async function tocarSpotify(it, meu) {
        destruirYt();
        let api;
        try { api = await ctx.carregarSpotify(); } catch (e) { ctx.toast('Não consegui carregar o player do Spotify agora. Tente de novo.', 'warning'); return; }
        if (meu !== seqToca || !aberta) return;
        const uri = `spotify:track:${it.v}`;
        spFim = false; spUri = uri;
        const cont = $('.mu-yt'); cont.classList.add('sp');
        if (sp) { try { sp.loadUri(uri); sp.play(); } catch (e) { /* o player caiu: o próximo toque recria */ } return; }
        const alvo = document.createElement('div'); cont.replaceChildren(alvo);
        api.createController(alvo, { uri, width: '100%', height: 152 }, (ctrl) => {
            if (meu !== seqToca || !aberta || !janela || !cont.isConnected) { try { ctrl.destroy(); } catch (e) { /* ignora */ } return; }
            sp = ctrl;
            ctrl.addListener('ready', () => { spPronto = true; try { if (spUri && spUri !== uri) ctrl.loadUri(spUri); ctrl.play(); } catch (e) { /* o navegador pediu um toque no player */ } });
            ctrl.addListener('playback_update', (ev) => {
                const d = ev && ev.data; if (!d) return;
                spPos = d.position || 0;
                if (!d.isPaused) spFim = false;
                tocando = !d.isPaused && !d.isBuffering ? true : (d.isBuffering && !d.isPaused);
                if (d.duration > 0 && d.isPaused && d.position >= d.duration - 800 && !spFim) { spFim = true; tocando = false; proxima(true); return; }
                desenharAgora(); desenharFila(); desenharResultados(); desenharPlaylist();
            });
        });
    }

    function aoEstadoPlayer(e) {
        const s = e.data;
        tocando = s === 1 || s === 3;
        if (s === 1) errosSeguidos = 0;
        if (s === 0) { tocando = false; proxima(true); }
        desenharAgora(); desenharFila(); desenharResultados(); desenharPlaylist();
    }
    function aoErroPlayer() {
        errosSeguidos++;
        const limite = Math.min(Math.max(fila.length, 1), 5);
        if (errosSeguidos >= limite) {
            tocando = false; desenharAgora();
            ctx.toast(fila.length > 1 ? 'Nenhuma dessas músicas tocou aqui: o dono do vídeo pode ter bloqueado o player fora do YouTube.' : 'Essa música não toca fora do YouTube (o dono do vídeo bloqueou) ou saiu do ar.', 'warning');
            return;
        }
        ctx.toast('Essa música não toca fora do YouTube (o dono do vídeo bloqueou) ou saiu do ar. Pulei pra próxima.', 'info');
        proxima(true);
    }

    function proxima(auto) {
        if (!fila.length) return;
        let n = idx + 1;
        if (aleatorio && fila.length > 1) { do { n = Math.floor(Math.random() * fila.length); } while (n === idx); }
        if (n >= fila.length) {
            if (repetir) n = 0;
            else { if (auto) { tocando = false; status = ['Fim da fila.', '']; desenharTudo(); } return; }
        }
        tocarIndice(n);
    }
    function anterior() {
        if (ehSp(fila[idx])) { if (sp && (spPos > 4000 || idx <= 0)) { try { sp.seek(0); } catch (e) { /* ignora */ } } else tocarIndice(Math.max(idx - 1, 0)); return; }
        let t = 0; try { t = yt && ytPronto ? yt.getCurrentTime() : 0; } catch (e) { t = 0; }
        if (t > 4 || idx <= 0) { if (yt && ytPronto) { try { yt.seekTo(0, true); } catch (e) { /* ignora */ } } else if (fila.length) tocarIndice(Math.max(idx, 0)); return; }
        tocarIndice(idx - 1);
    }
    function tocarPausar() {
        if (!fila.length) return;
        if (ehSp(fila[idx])) {
            if (!sp) { tocarIndice(idx); return; }
            if (!tocando) ctx.pararPerfil();
            try { sp.togglePlay(); } catch (e) { /* player ainda subindo */ }
            return;
        }
        if (!yt) { tocarIndice(idx >= 0 ? idx : 0); return; }
        if (!tocando) ctx.pararPerfil();                              // voltar a tocar também silencia o player do cartão de perfil
        try { if (tocando) yt.pauseVideo(); else yt.playVideo(); } catch (e) { /* player ainda subindo */ }
    }
    function pausar() { try { if (yt && ytPronto && tocando) yt.pauseVideo(); if (sp && tocando) sp.pause(); } catch (e) { /* ignora */ } }

    function pararTudo() {
        seqToca++;
        destruirYt(); destruirSp();
        tocando = false; errosSeguidos = 0; mini = false; tile = false;
        if (janela) { const p = $('.mu-player'); p.hidden = true; const c = $('.mu-yt'); c.replaceChildren(); c.classList.remove('sp'); janela.classList.remove('mini', 'tocando', 'tile'); desenharAgora(); }
    }

    function sessaoMidia() {                                          // teclas de mídia e tela de bloqueio do celular
        if (!('mediaSession' in navigator)) return;
        try {
            const it = fila[idx];
            navigator.mediaSession.metadata = it ? new MediaMetadata({ title: it.t || 'Música', artist: it.a || '', artwork: capaDe(it) ? [{ src: capaDe(it), sizes: '320x180', type: 'image/jpeg' }] : [] }) : null;
            navigator.mediaSession.setActionHandler('nexttrack', () => proxima(false));
            navigator.mediaSession.setActionHandler('previoustrack', anterior);
            navigator.mediaSession.setActionHandler('play', tocarPausar);
            navigator.mediaSession.setActionHandler('pause', tocarPausar);
        } catch (e) { /* o navegador não deixa: segue sem */ }
    }

    // ---------------------------------------------------------------------
    // cliques
    // ---------------------------------------------------------------------
    function addPerfil(it) {
        if (!valido(it) || adicionando.has(it.v)) return;
        adicionando.add(it.v); desenharResultados();
        ctx.emitir('fila_adicionar', { url: `https://www.youtube.com/watch?v=${it.v}`, criar: true, origem: 'musica' });
        setTimeout(() => { if (adicionando.delete(it.v)) desenharResultados(); }, 8000);
    }
    function aoAdicionar(d) {
        adicionando.clear(); desenharResultados();
        const n = Number(d && d.adicionadas) || 0, avisos = (d && d.avisos) || [];
        ctx.toast(n ? 'Adicionada à playlist do seu perfil.' : (avisos[0] || 'Não adicionei.'), n ? 'success' : 'info');
    }
    function aoErroPlaylist(msg) { adicionando.clear(); desenharResultados(); ctx.toast(msg || 'Não consegui mexer na playlist.', 'warning'); }
    function aoMudarPlaylist() { if (aberta) desenharPlaylist(); }

    function aoClicar(e) {
        const fonte_ = e.target.closest('[data-fonte]');
        if (fonte_) { fonte = fonte_.dataset.fonte === 'sp' && estado.spotify ? 'sp' : 'yt'; resultados = []; resMeta = { origem: '' }; status = ['', '']; desenharAbas(); desenharStatus(); desenharResultados(); const q = $('#mu-q'); if (q) q.placeholder = fonte === 'sp' ? 'Pesquisar música no Spotify' : 'Pesquisar música ou colar link do YouTube'; return; }
        const aba_ = e.target.closest('[data-aba]');
        if (aba_) { aba = aba_.dataset.aba; if (aba === 'playlist' && ctx.minhas() === null) ctx.listarConexoes(); desenharAbas(); desenharFila(); desenharPlaylist(); return; }
        const b = e.target.closest('[data-mu]');
        const l = !b && e.target.closest('[data-mu-linha]');
        const nome = b ? b.dataset.mu : l ? l.dataset.muLinha : null;
        if (!nome || (b && b.classList.contains('off'))) return;
        const el = b || l, i = Number(el.dataset.i);
        const res = resultados[i], perfil = filaDoPerfil(), pf = perfil && perfil.faixas[i];
        switch (nome) {
            case 'fechar': fechar(); break;
            case 'mini': if (celular() && playerVisivel()) tile = true; else mini = !mini; desenharAbas(); break;      // no celular recolhe num quadradinho que continua tocando
            case 'expandir': tile = false; desenharAbas(); break;
            case 'play': tocarPausar(); break;
            case 'prox': proxima(false); break;
            case 'ant': anterior(); break;
            case 'aleatorio': aleatorio = !aleatorio; guardarOpc(); desenharAgora(); break;
            case 'repetir': repetir = !repetir; guardarOpc(); desenharAgora(); break;
            case 'res-tocar': tocarAgora(res); break;
            case 'res-fila': { const r = juntar(res); if (r === 'ja') ctx.toast('Essa música já está na fila.', 'info'); else if (r) { filaMudou(); ctx.toast('Adicionada à fila.', 'success'); } break; }
            case 'res-lista': addPerfil(res); break;
            case 'res-tudo-tocar': tocarLista(resultados, 0); break;
            case 'res-tudo-fila': { let n = 0; resultados.forEach((it) => { if (juntar(it) === true) n++; }); filaMudou(); ctx.toast(n ? `${n} ${n === 1 ? 'música adicionada' : 'músicas adicionadas'} à fila.` : 'Elas já estão na fila.', n ? 'success' : 'info'); break; }
            case 'fila-tocar': tocarIndice(i); break;
            case 'fila-sobe': mover(i, -1); break;
            case 'fila-desce': mover(i, 1); break;
            case 'fila-tira': remover(i); break;
            case 'fila-limpar': {
                const feito = () => { fila = []; idx = -1; pararTudo(); filaMudou(); };
                if (fila.length > 3) ctx.confirmar('Limpar a fila?', `As ${fila.length} músicas saem da fila (a sua playlist do perfil não muda).`, feito); else feito();
                break;
            }
            case 'pl-tocar': tocarLista((perfil ? perfil.faixas : []).filter((f) => idOk(f.v)).map((f) => ({ v: f.v, t: f.t, a: f.a })), 0); break;
            case 'pl-fila': { let n = 0; (perfil ? perfil.faixas : []).filter((f) => idOk(f.v)).forEach((f) => { if (juntar({ v: f.v, t: f.t, a: f.a }) === true) n++; }); filaMudou(); ctx.toast(n ? `${n} ${n === 1 ? 'música adicionada' : 'músicas adicionadas'} à fila.` : 'Elas já estão na fila.', n ? 'success' : 'info'); break; }
            case 'pl-tocar-uma': if (pf && idOk(pf.v)) tocarAgora({ v: pf.v, t: pf.t, a: pf.a }); break;
            case 'pl-fila-uma': if (pf && idOk(pf.v)) { const r = juntar({ v: pf.v, t: pf.t, a: pf.a }); if (r === 'ja') ctx.toast('Essa música já está na fila.', 'info'); else if (r) { filaMudou(); ctx.toast('Adicionada à fila.', 'success'); } } break;
            case 'pl-tira': if (pf) ctx.emitir('fila_remover', { chave: idOk(pf.v) ? 'v:' + pf.v : 'l:' + pf.l }); break;
            case 'pl-abrir': if (pf && idOk(pf.l)) { aba = 'buscar'; $('#mu-q').value = `https://www.youtube.com/playlist?list=${pf.l}`; desenharAbas(); pesquisar(); } break;
            default: break;
        }
    }

    // ---------------------------------------------------------------------
    return {
        iniciar(c) { ctx = c; restaurar(); marcarBotao(); },
        alternar, abrir, fechar, pausar, aoEstado, aoResultados, aoErro, aoAdicionar, aoErroPlaylist, aoMudarPlaylist,
        tocando: () => tocando, aberta: () => aberta,
        _fila: () => fila.map((x) => x.v),
    };
})();
