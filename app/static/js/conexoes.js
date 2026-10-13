/* Conexões do perfil: a aba "Conexões" das Configurações (cadeia de links), a "segunda face" do cartão (GitHub, currículo do LinkedIn, toca-discos, links).
   A pessoa só COLA O LINK: o servidor busca e o cartão vem pronto (pra mudar algo, ela muda no site oficial). Nada de editor. Objeto global `Conexoes`.
   Só desenha e conversa com o servidor: o que é válido, o que foi buscado e quem pode ver são decididos lá (conexoes.py).
   Contexto (Conexoes.iniciar): { emitir, esc, escUrl, toast, confirmar(titulo, texto, ok), abrirLoja(id), aoMudarMinhas(lista) }.
   Tudo que vem do servidor passa por esc()/escUrl() antes do innerHTML; imagem de conexão só carrega de um CDN conhecido (lista que o servidor manda). */
const Conexoes = (() => {
    'use strict';
    let ctx = null, P = {}, minhas = null, MAX = 12, MAXF = 30, IA = false, IMAGENS = [];
    let filaTexto = '', filaMsg = ['', ''];                         // o que a pessoa digitou no campo da playlist e a última mensagem dela (sobrevivem ao redesenho da lista)
    let linhas = [], enviados = [], salvando = false, pedirDeNovo = false, timerSalvar = null, seq = 0, ultimoEnvio = 0, timerResposta = null;
    const INTERVALO_MS = 1700;                                        // o servidor ignora salvar mais de 1 vez a cada 1,5 s
    const $ = (id) => document.getElementById(id);
    const T = (v) => ctx.esc(v == null ? '' : v);
    const num = (n) => Number(n || 0).toLocaleString('pt-BR');
    // Cada empresa com a cara dela: o JS só põe o id da marca no cartão (data-marca); as cores e o visual moram em conexoes.css.
    const MARCAS = new Set(['youtube', 'amazon', 'linkedin', 'instagram', 'tiktok', 'x', 'steam', 'ifood', 'olx', 'twitch', 'spotify', 'github', 'bazar', 'fila']);
    const marca = (tipo) => (MARCAS.has(tipo) ? ` data-marca="${tipo}"` : '');
    // O Font Awesome 6.4 do app ainda não tem o "X" (só a partir da 6.4.2): o logo é desenhado aqui (path do Simple Icons, CC0).
    const LOGO_X = '<svg class="cx-svg" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z"/></svg>';
    const iconeHtml = (tipo, p) => (tipo === 'x' ? LOGO_X : `<i class="${T(p.icone)}"></i>`);

    const HOSTS = [['github', ['github.com']], ['linkedin', ['linkedin.com']], ['youtube', ['youtube.com', 'youtu.be']], ['twitch', ['twitch.tv']], ['spotify', ['spotify.com']],
        ['instagram', ['instagram.com']], ['tiktok', ['tiktok.com']], ['x', ['x.com', 'twitter.com']], ['steam', ['steamcommunity.com', 'steampowered.com']],
        ['ifood', ['ifood.com.br']], ['amazon', ['amazon.com.br', 'amazon.com']], ['olx', ['olx.com.br']]];

    /** Só pro ÍCONE enquanto a pessoa digita (quem decide de verdade é o servidor ao salvar). */
    function tipoPorTexto(txt) {
        const m = /^(?:[a-z]+:\/\/)?([^\s/?#:]+)/i.exec((txt || '').trim());
        if (!m || !m[1].includes('.')) return '';
        const host = m[1].toLowerCase();
        for (const [tipo, hs] of HOSTS) if (hs.some((h) => host === h || host.endsWith('.' + h))) return tipo;
        return 'site';
    }
    const plataforma = (tipo) => P[tipo] || (tipo === '' ? { nome: 'Link', icone: 'fa-solid fa-link', cor: '#7289da' } : { nome: 'Site', icone: 'fa-solid fa-globe', cor: '#7289da' });
    const hostDe = (url) => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch (e) { return ''; } };
    const imgOk = (url) => { try { const u = new URL(url); return u.protocol === 'https:' && IMAGENS.includes(u.hostname); } catch (e) { return false; } };
    const img = (url, cls) => (url && imgOk(url) ? `<img class="${cls}" src="${ctx.escUrl(url)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : '');

    function atras(iso) {
        if (!iso) return '';
        const s = Math.max(0, (Date.now() - new Date(iso + 'Z').getTime() - 3 * 3600 * 1000) / 1000);   // o servidor grava a hora de Brasília (UTC-3) sem fuso: lido como UTC ela vem 3 h ADIANTADA
        if (!isFinite(s) || s < 90) return 'agora há pouco';
        if (s < 3600) return `há ${Math.floor(s / 60)} min`;
        if (s < 86400) return `há ${Math.floor(s / 3600)} h`;
        return `há ${Math.floor(s / 86400)} dia(s)`;
    }

    // ---------------------------------------------------------------------
    // ABRIR UM LINK FORA DO APP (sempre com aviso: o link é de quem montou o perfil, não nosso)
    // ---------------------------------------------------------------------
    function abrirLink(url) {
        if (!/^https:\/\//i.test(url || '')) return;
        const host = hostDe(url);
        ctx.confirmar('Abrir fora do Pantheon?', `Você vai abrir ${host || 'um site'} no seu navegador. O Pantheon não controla esse site: só abra se você confia em quem colocou o link.`,
            () => { window.open(url, '_blank', 'noopener,noreferrer'); });
    }

    // ---------------------------------------------------------------------
    // A SEGUNDA FACE DO CARTÃO
    // ---------------------------------------------------------------------
    function botaoAbrir(url, rotulo) {
        return url ? `<button type="button" class="cx-abrir" data-cx-abrir="${T(url)}" title="Abrir no navegador"><span>${T(rotulo || 'Abrir')}</span> <i class="fa-solid fa-arrow-up-right-from-square"></i></button>` : '';
    }

    function cabecalhoCard(c, extra) {
        const p = plataforma(c.tipo);
        return `<div class="cx-cab"><span class="cx-ico peq" style="--c:${T(p.cor)}">${iconeHtml(c.tipo, p)}</span><span class="cx-cab-nome">${T(p.nome)}${extra ? ` <small>${T(extra)}</small>` : ''}</span></div>`;
    }

    function cartaoLink(c, aviso) {
        const p = plataforma(c.tipo), host = hostDe(c.url);
        const d = c.dados || {};
        const titulo = d.titulo || c.titulo || host;
        return `<article class="cx-card" style="--c:${T(p.cor)}"${marca(c.tipo)}>${cabecalhoCard(c)}
            <div class="cx-link">${d.imagem ? img(d.imagem, 'cx-capa') : ''}<div class="cx-link-t"><b>${T(titulo)}</b>${d.descricao ? `<p>${T(d.descricao)}</p>` : ''}${host && host !== titulo ? `<small>${T(host)}</small>` : ''}${aviso ? `<em>${T(aviso)}</em>` : ''}</div>${botaoAbrir(c.url, 'Abrir')}</div></article>`;
    }

    // ---------------------------------------------------------------------
    // TOCA-DISCOS: música do Spotify (faixa, álbum, playlist, artista, podcast) e vídeo/playlist do YouTube viram um vinil com o player OFICIAL embutido.
    // O player de terceiros só é carregado quando a pessoa aperta "Ouvir" (nada de rede de terceiros ao abrir o perfil) e fica À VISTA (os termos dos dois
    // exigem). O disco gira enquanto toca (o estado vem do próprio player) e a agulha pousa. Controle total: o áudio é do Spotify/YouTube, não nosso.
    // ---------------------------------------------------------------------
    const RE_REF_SPOTIFY = /^(track|album|playlist|artist|episode|show)\/[A-Za-z0-9]{22}$/, RE_REF_YT = /^(v|l):[\w-]{6,40}$/;
    const players = new Map();                                       // cartão (elemento) -> { parar() }

    function refDoVinil(c) {
        const d = c.dados || {};
        if (c.tipo === 'spotify' && d.recurso && d.id && RE_REF_SPOTIFY.test(d.recurso + '/' + d.id)) return d.recurso + '/' + d.id;
        if (c.tipo === 'youtube' && d.video && RE_REF_YT.test('v:' + d.video)) return 'v:' + d.video;
        if (c.tipo === 'youtube' && d.lista && RE_REF_YT.test('l:' + d.lista)) return 'l:' + d.lista;
        return '';
    }

    function cartaoVinil(c, ref) {
        const p = plataforma(c.tipo), d = c.dados || {};
        const tipoRecurso = { track: 'Música', album: 'Álbum', playlist: 'Playlist', artist: 'Artista', episode: 'Episódio', show: 'Podcast' }[d.recurso] || (d.lista ? 'Playlist do YouTube' : 'Vídeo do YouTube');
        const sub = [d.autor, tipoRecurso].filter(Boolean).join(' · ');
        return `<article class="cx-card vinil" style="--c:${T(p.cor)}"${marca(c.tipo)} data-cx-vinil>${cabecalhoCard(c)}
            <div class="cx-vinil-corpo">
                <div class="cx-vinil-cena" aria-hidden="true"><span class="cx-disco"><span class="cx-rotulo">${d.imagem ? img(d.imagem, 'cx-rotulo-img') : iconeHtml(c.tipo, p)}</span><span class="cx-furo"></span></span><span class="cx-braco"><i></i></span></div>
                <div class="cx-vinil-info"><b>${T(d.titulo || c.titulo)}</b>${sub ? `<small>${T(sub)}</small>` : ''}
                    <div class="cx-vinil-bt"><button type="button" class="cx-play" data-cx-tocar="${c.tipo}" data-ref="${T(ref)}"><i class="fa-solid fa-play"></i> <span>Ouvir</span></button>${botaoAbrir(c.url, c.tipo === 'spotify' ? 'No Spotify' : 'No YouTube')}</div>
                    <em class="cx-terc">Ao ouvir, o player ${c.tipo === 'spotify' ? 'do Spotify' : 'do YouTube'} é carregado (serviço de terceiros).</em></div></div>
            <div class="cx-player" hidden></div></article>`;
    }

    function pararPlayers() {
        players.forEach((p, card) => {
            try { p.parar(); } catch (e) { /* o player já saiu */ }
            if (card.isConnected) {                                    // o cartão segue na tela (ex.: a Música começou a tocar): volta o botão pra "Ouvir"
                const alvo = card.querySelector('.cx-player'), b = card.querySelector('[data-cx-tocar]');
                if (alvo) alvo.hidden = true;
                card.classList.remove('aberto', 'tocando');
                if (b) { b.querySelector('span').textContent = 'Ouvir'; b.firstElementChild.className = 'fa-solid fa-play'; }
            }
        });
        players.clear();
    }

    let apiSpotify = null;
    function carregarSpotify() {
        if (apiSpotify) return apiSpotify;
        apiSpotify = new Promise((ok, falha) => {
            if (window.__pntSpotifyApi) { ok(window.__pntSpotifyApi); return; }
            window.onSpotifyIframeApiReady = (api) => { window.__pntSpotifyApi = api; ok(api); };
            const sc = document.createElement('script');
            sc.src = 'https://open.spotify.com/embed/iframe-api/v1'; sc.async = true;
            sc.onerror = () => { apiSpotify = null; falha(new Error('spotify')); };
            document.head.appendChild(sc);
            setTimeout(() => { if (!window.__pntSpotifyApi) { apiSpotify = null; falha(new Error('tempo')); } }, 12000);
        });
        return apiSpotify;
    }

    async function tocarSpotify(card, ref) {
        const [recurso, id] = ref.split('/'), alvo = card.querySelector('.cx-player');
        const api = await carregarSpotify();
        alvo.hidden = false; alvo.replaceChildren(document.createElement('div'));
        api.createController(alvo.firstChild, { uri: `spotify:${recurso}:${id}`, width: '100%', height: recurso === 'track' || recurso === 'episode' ? 80 : 152 }, (ctrl) => {
            players.set(card, { parar: () => { try { ctrl.destroy(); } catch (e) { /* já saiu */ } card.classList.remove('tocando'); } });
            ctrl.addListener('ready', () => { try { ctrl.play(); } catch (e) { /* o navegador pediu um toque no player */ } });
            ctrl.addListener('playback_update', (ev) => { const x = ev && ev.data; card.classList.toggle('tocando', !!x && !x.isPaused && !x.isBuffering); });
        });
    }

    function tocarYoutube(card, ref) {
        const alvo = card.querySelector('.cx-player'), id = ref.slice(2);
        const origem = encodeURIComponent(location.origin);
        const src = ref[0] === 'v' ? `https://www.youtube-nocookie.com/embed/${id}?enablejsapi=1&playsinline=1&rel=0&origin=${origem}`
            : `https://www.youtube-nocookie.com/embed/videoseries?list=${id}&enablejsapi=1&playsinline=1&rel=0&origin=${origem}`;
        const f = document.createElement('iframe');
        f.src = src; f.title = 'Player do YouTube'; f.width = '100%'; f.height = '200'; f.allow = 'autoplay; encrypted-media; picture-in-picture'; f.allowFullscreen = true; f.referrerPolicy = 'strict-origin-when-cross-origin';
        alvo.hidden = false; alvo.replaceChildren(f);
        const ouvir = (ev) => {
            if (ev.source !== f.contentWindow || ev.origin !== 'https://www.youtube-nocookie.com') return;
            let m; try { m = typeof ev.data === 'string' ? JSON.parse(ev.data) : ev.data; } catch (e) { return; }
            if (m && m.event === 'onStateChange') card.classList.toggle('tocando', m.info === 1);
        };
        window.addEventListener('message', ouvir);
        f.addEventListener('load', () => { try { f.contentWindow.postMessage(JSON.stringify({ event: 'listening', id: 1, channel: 'widget' }), 'https://www.youtube-nocookie.com'); f.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'playVideo', args: [] }), 'https://www.youtube-nocookie.com'); } catch (e) { /* sem controle: o player tem os botões dele */ } });
        players.set(card, { parar: () => { window.removeEventListener('message', ouvir); f.remove(); card.classList.remove('tocando'); } });
    }

    // ---------------------------------------------------------------------
    // PLAYLIST DO PERFIL ("fila"): músicas e playlists do YouTube / YouTube Music coladas pela pessoa tocam em sequência no player OFICIAL do YouTube
    // (embed à vista, controles dele inclusos; o nosso só pula de faixa). A API do player só é baixada quando a pessoa aperta Ouvir (ou uma faixa).
    // Uma entrada é uma música (`v:<id>`) ou uma playlist inteira (`l:<id>`, que o próprio player percorre antes de a fila seguir pra próxima entrada).
    // ---------------------------------------------------------------------
    const RE_ID_YT = /^[\w-]{6,40}$/, RE_REFS_FILA = /^[vl]:[\w-]{6,40}(,[vl]:[\w-]{6,40}){0,29}$/;
    const idOk = (x) => typeof x === 'string' && RE_ID_YT.test(x);
    const faixasDe = (c) => { const f = c && c.dados && c.dados.faixas; return Array.isArray(f) ? f.filter((x) => x && (idOk(x.v) || idOk(x.l))) : []; };
    const chaveFaixa = (f) => (idOk(f.v) ? 'v:' + f.v : 'l:' + f.l);              // (o mesmo formato da chave do servidor)
    const capaFaixa = (f) => (idOk(f.v) ? `https://i.ytimg.com/vi/${f.v}/mqdefault.jpg` : (f.i || ''));
    const semCapa = '<span class="cx-fx-capa vazia"><i class="fa-solid fa-music"></i></span>';
    const nomeFaixa = (f) => f.t || (f.x ? 'Música indisponível' : 'Música do YouTube');
    const subFaixa = (f) => [f.a, f.l ? 'playlist' : '', f.x ? 'não toca aqui' : ''].filter(Boolean).join(' · ');

    function linhaFaixa(f, i) {
        return `<li><button type="button" class="cx-faixa${f.x ? ' off' : ''}" data-cx-faixa="${i}" title="${f.x ? 'O dono do vídeo não deixa tocar fora do YouTube, ou ele saiu do ar. Posso tentar mesmo assim.' : 'Tocar'}">
            ${img(capaFaixa(f), 'cx-fx-capa') || semCapa}<span class="cx-fx-t"><b>${T(nomeFaixa(f))}</b><small>${T(subFaixa(f))}</small></span><span class="cx-eq" aria-hidden="true"><i></i><i></i><i></i></span></button></li>`;
    }

    function cartaoFila(c, pf) {
        const p = plataforma('fila'), fx = faixasDe(c);
        const titulo = pf && pf.nome ? `Playlist de ${pf.nome}` : 'Playlist';
        if (!fx.length) {
            return `<article class="cx-card vinil fila" style="--c:${T(p.cor)}"${marca(c.tipo)}>${cabecalhoCard(c, 'no YouTube')}
                <div class="cx-link"><div class="cx-link-t"><b>${T(titulo)}</b><small>Nenhuma música ainda</small>${pf && pf.sou_eu ? '<em>Cole links do YouTube ou do YouTube Music em Configurações > Conexões.</em>' : ''}</div></div></article>`;
        }
        const refs = fx.map(chaveFaixa).join(',');
        return `<article class="cx-card vinil fila" style="--c:${T(p.cor)}"${marca(c.tipo)} data-cx-vinil>${cabecalhoCard(c, 'no YouTube')}
            <div class="cx-vinil-corpo">
                <div class="cx-vinil-cena" aria-hidden="true"><span class="cx-disco"><span class="cx-rotulo">${img(capaFaixa(fx[0]), 'cx-rotulo-img') || iconeHtml(c.tipo, p)}</span><span class="cx-furo"></span></span><span class="cx-braco"><i></i></span></div>
                <div class="cx-vinil-info"><b>${T(titulo)}</b><small data-fila-agora>${fx.length} ${fx.length === 1 ? 'música' : 'músicas'}</small>
                    <div class="cx-vinil-bt"><button type="button" class="cx-play" data-cx-tocar="fila" data-ref="${T(refs)}"><i class="fa-solid fa-play"></i> <span>Ouvir</span></button>
                        <span class="cx-fila-ctl"><button type="button" class="cx-bt ic" data-cx-ant title="Anterior" aria-label="Música anterior"><i class="fa-solid fa-backward-step"></i></button><button type="button" class="cx-bt ic" data-cx-prox title="Próxima" aria-label="Próxima música"><i class="fa-solid fa-forward-step"></i></button></span></div>
                    <em class="cx-terc">Ao ouvir, o player do YouTube é carregado (serviço de terceiros).</em></div></div>
            <div class="cx-player" hidden></div>
            <ol class="cx-faixas">${fx.map(linhaFaixa).join('')}</ol></article>`;
    }

    let apiYt = null;
    function carregarYt() {
        if (window.YT && window.YT.Player) return Promise.resolve(window.YT);
        if (apiYt) return apiYt;
        apiYt = new Promise((ok, falha) => {
            const antes = window.onYouTubeIframeAPIReady;
            window.onYouTubeIframeAPIReady = () => { try { if (typeof antes === 'function') antes(); } catch (e) { /* quem tinha esse gancho antes que se resolva */ } ok(window.YT); };
            const sc = document.createElement('script');
            sc.src = 'https://www.youtube.com/iframe_api'; sc.async = true;
            sc.onerror = () => { apiYt = null; falha(new Error('youtube')); };
            document.head.appendChild(sc);
            setTimeout(() => { if (!(window.YT && window.YT.Player)) { apiYt = null; falha(new Error('tempo')); } }, 12000);
        });
        return apiYt;
    }

    /** Abre o player da playlist e começa na entrada `inicio`. Registra em `players` (quem fecha é o `parar`) um objeto com ir/proxima/anterior pros botões. */
    async function tocarFila(card, refs, inicio) {
        const alvo = card.querySelector('.cx-player');
        const api = await carregarYt();
        if (!card.isConnected || players.has(card)) return;             // a face foi redesenhada (ou outro clique abriu primeiro) enquanto o script baixava
        const entradas = refs.split(','), rotulo = card.querySelector('[data-fila-agora]'), textoInicial = rotulo ? rotulo.textContent : '';
        const origem = encodeURIComponent(location.origin);
        let idx = Math.max(0, Math.min(Number(inicio) || 0, entradas.length - 1)), erros = 0, vivo = true, pl = null;
        const srcDe = (ref) => (ref[0] === 'v' ? `https://www.youtube-nocookie.com/embed/${ref.slice(2)}?` : `https://www.youtube-nocookie.com/embed/videoseries?list=${ref.slice(2)}&`)
            + `enablejsapi=1&autoplay=1&playsinline=1&rel=0&origin=${origem}`;
        const f = document.createElement('iframe');
        f.src = srcDe(entradas[idx]); f.title = 'Player do YouTube'; f.width = '100%'; f.height = '200'; f.allow = 'autoplay; encrypted-media; picture-in-picture'; f.allowFullscreen = true; f.referrerPolicy = 'strict-origin-when-cross-origin';
        alvo.hidden = false; alvo.replaceChildren(f);

        const marcar = () => {                                           // destaca a faixa de agora, deixa ela à vista na lista e troca a capa do disco
            const itens = card.querySelectorAll('.cx-faixas > li'), lista = card.querySelector('.cx-faixas');
            itens.forEach((li, i) => li.classList.toggle('atual', i === idx));
            const li = itens[idx];
            if (li && lista) { const topo = li.offsetTop, base = topo + li.offsetHeight; if (topo < lista.scrollTop) lista.scrollTop = topo; else if (base > lista.scrollTop + lista.clientHeight) lista.scrollTop = base - lista.clientHeight; }
            const capa = li && li.querySelector('img.cx-fx-capa'), rot = card.querySelector('.cx-rotulo');
            if (capa && rot) {
                let im = rot.querySelector('img');
                if (!im) { rot.textContent = ''; im = document.createElement('img'); im.className = 'cx-rotulo-img'; im.alt = ''; im.referrerPolicy = 'no-referrer'; rot.appendChild(im); }
                im.src = capa.src;                                       // (a capa da lista já passou pela checagem de CDN)
            }
        };
        const legenda = () => { try { const v = pl.getVideoData(); if (v && v.title && rotulo) rotulo.textContent = v.author ? `${v.title} · ${v.author}` : v.title; } catch (e) { /* ainda sem dados */ } };
        const carregar = () => {
            marcar(); if (rotulo) rotulo.textContent = 'Carregando...';
            const ref = entradas[idx];
            try { if (ref[0] === 'v') pl.loadVideoById(ref.slice(2)); else pl.loadPlaylist({ listType: 'playlist', list: ref.slice(2) }); } catch (e) { /* o player ainda não está pronto: o onReady toca */ }
        };
        const ir = (i, manual) => { if (!vivo) return; idx = Math.max(0, Math.min(i, entradas.length - 1)); if (manual) erros = 0; carregar(); };
        const fim = () => { card.classList.remove('tocando'); if (rotulo) rotulo.textContent = 'Fim da playlist'; };
        const proxima = () => { if (idx + 1 < entradas.length) ir(idx + 1); else fim(); };
        const dentroDaLista = (delta) => {                               // entrada que é uma playlist: ⏭/⏮ andam dentro dela antes de mudar de entrada
            if (entradas[idx][0] !== 'l') return false;
            try { const lista = pl.getPlaylist() || [], pos = pl.getPlaylistIndex(); if (delta > 0 && pos >= 0 && pos < lista.length - 1) { pl.nextVideo(); return true; } if (delta < 0 && pos > 0) { pl.previousVideo(); return true; } } catch (e) { /* sem controle da lista */ }
            return false;
        };
        const posicaoNaLista = () => { try { const lista = pl.getPlaylist() || []; return { pos: pl.getPlaylistIndex(), total: lista.length }; } catch (e) { return { pos: -1, total: 0 }; } };
        const playlistTemMais = () => { const x = posicaoNaLista(); return entradas[idx][0] === 'l' && x.pos >= 0 && x.pos < x.total - 1; };
        const aoEstado = (e) => {
            if (!vivo) return;
            card.classList.toggle('tocando', e.data === 1);
            if (e.data === 1) { erros = 0; legenda(); }
            else if (e.data === 0 && !playlistTemMais()) proxima();         // (numa playlist com mais músicas o próprio player já segue sozinho)
        };
        const aoErro = () => {
            if (!vivo) return;
            erros += 1;
            if (playlistTemMais()) {                                       // dentro de uma playlist: o player pode pular sozinho; se em 1,5 s ainda parou na mesma, pulo eu
                const antes = posicaoNaLista().pos;
                setTimeout(() => { if (!vivo) return; try { if (pl.getPlaylistIndex() === antes && pl.getPlayerState() !== 1) pl.nextVideo(); } catch (e) { /* sem controle da lista */ } }, 1500);
                return;
            }
            if (erros >= entradas.length) { card.classList.remove('tocando'); if (rotulo) rotulo.textContent = 'Não consegui tocar'; ctx.toast('Nenhuma música dessa playlist tocou aqui. O dono do vídeo pode ter bloqueado o player fora do YouTube.', 'warning'); return; }
            ctx.toast('Essa música não toca fora do YouTube (o dono do vídeo bloqueou) ou saiu do ar. Pulei pra próxima.', 'info');
            proxima();
        };
        try {
            pl = new api.Player(f, { events: { onReady: () => { try { pl.playVideo(); } catch (e) { /* o navegador pediu um toque no player */ } }, onStateChange: aoEstado, onError: aoErro } });
        } catch (e) { f.remove(); alvo.hidden = true; throw e; }
        marcar();
        players.set(card, {
            parar: () => {
                vivo = false;
                try { pl.destroy(); } catch (e) { f.remove(); }
                card.classList.remove('tocando', 'aberto');
                card.querySelectorAll('.cx-faixas > li.atual').forEach((li) => li.classList.remove('atual'));
                if (rotulo) rotulo.textContent = textoInicial;
                alvo.hidden = true;
            },
            ir: (i) => ir(i, true),
            proxima: () => { if (!dentroDaLista(1)) proxima(); },
            anterior: () => { if (!dentroDaLista(-1)) ir(idx - 1, true); },
        });
    }

    async function tocar(botao, inicio) {
        const card = botao.closest('[data-cx-vinil]');
        if (!card) return;
        if (players.has(card)) { players.get(card).parar(); players.delete(card); card.querySelector('.cx-player').hidden = true; card.classList.remove('aberto'); botao.querySelector('span').textContent = 'Ouvir'; botao.firstElementChild.className = 'fa-solid fa-play'; return; }   // 2º clique: fecha
        const ref = botao.dataset.ref, tipo = botao.dataset.cxTocar;
        if (typeof ctx.aoTocar === 'function') ctx.aoTocar();          // o player da Música (janelinha) pausa: dois sons juntos não
        botao.disabled = true;
        try {
            if (tipo === 'spotify' && RE_REF_SPOTIFY.test(ref)) await tocarSpotify(card, ref);
            else if (tipo === 'youtube' && RE_REF_YT.test(ref)) tocarYoutube(card, ref);
            else if (tipo === 'fila' && RE_REFS_FILA.test(ref)) await tocarFila(card, ref, inicio);
            if (players.has(card)) { card.classList.add('aberto'); botao.querySelector('span').textContent = 'Fechar'; botao.firstElementChild.className = 'fa-solid fa-xmark'; }
        } catch (e) { ctx.toast('Não consegui carregar o player agora. Tente de novo ou use o botão de abrir no site.', 'warning'); }
        botao.disabled = false;
    }

    /** Clique numa faixa da lista: se o player já está aberto, pula pra ela; senão abre o player começando nela. */
    function tocarFaixa(linha) {
        const card = linha.closest('[data-cx-vinil]'), i = Number(linha.dataset.cxFaixa);
        if (!card || !Number.isInteger(i)) return;
        const p = players.get(card);
        if (p && p.ir) { p.ir(i); return; }
        const botao = card.querySelector('[data-cx-tocar="fila"]');
        if (botao && !botao.disabled) tocar(botao, i);
    }

    function cartaoMidia(c) {
        const p = plataforma(c.tipo), d = c.dados || {};
        if (!c.dados) return cartaoLink(c, c.erro ? c.erro : 'Buscando os dados...');
        const ref = refDoVinil(c);
        if (ref) return cartaoVinil(c, ref);
        const redonda = c.tipo === 'twitch' || (c.tipo === 'youtube' && !d.video && !d.lista);
        const tipoRecurso = { track: 'Música', album: 'Álbum', playlist: 'Playlist', artist: 'Artista', episode: 'Episódio', show: 'Podcast' }[d.recurso] || '';
        const sub = d.autor || tipoRecurso || (c.tipo === 'twitch' ? 'Canal da Twitch' : c.tipo === 'youtube' ? (d.video ? 'Vídeo' : d.lista ? 'Playlist' : 'Canal') : '');
        return `<article class="cx-card" style="--c:${T(p.cor)}"${marca(c.tipo)}>${cabecalhoCard(c)}
            <div class="cx-midia">${d.imagem ? img(d.imagem, 'cx-capa' + (redonda ? ' redonda' : '')) : `<span class="cx-capa vazia">${iconeHtml(c.tipo, p)}</span>`}
            <div class="cx-midia-t"><b>${T(d.titulo || c.titulo)}</b>${sub ? `<small>${T(sub)}</small>` : ''}</div>${botaoAbrir(c.url, c.tipo === 'spotify' || (c.tipo === 'youtube' && (d.video || d.lista)) ? 'Ouvir' : 'Abrir')}</div></article>`;
    }

    function cartaoLoja(c) {
        const d = c.dados;
        const p = plataforma('bazar');
        if (!d) return '';
        return `<article class="cx-card" style="--c:${T(p.cor)}"${marca(c.tipo)}>${cabecalhoCard(c)}
            <div class="cx-midia">${d.logo ? `<img class="cx-capa" src="${ctx.escUrl(d.logo)}" alt="" loading="lazy">` : `<span class="cx-capa vazia">${iconeHtml(c.tipo, p)}</span>`}
            <div class="cx-midia-t"><b>${T(d.nome)}</b><small>${d.nota ? `★ ${T(d.nota)} · ` : ''}${num(d.vendas)} ${d.vendas === 1 ? 'venda' : 'vendas'}</small>${d.descricao ? `<p>${T(d.descricao)}</p>` : ''}</div>
            <button type="button" class="cx-abrir" data-cx-loja="${Number(d.loja_id)}"><span>Visitar</span> <i class="fa-solid fa-store"></i></button></div></article>`;
    }

    const NIVEL_GRADE = ['g0', 'g1', 'g2', 'g3', 'g4'];
    function cartaoGithub(c, compacto) {
        const d = c.dados, p = plataforma('github');
        if (!d) return cartaoLink(c, c.erro ? c.erro : 'Buscando os dados...');
        const semanas = Array.isArray(d.grade) ? d.grade : [];
        const grade = semanas.length ? `<div class="cx-grade" role="img" aria-label="Contribuições no último ano${d.total ? ': ' + num(d.total) : ''}" style="--sem:${semanas.length}">${semanas.map((col) =>
            `<span>${String(col).split('').map((ch) => `<i class="${ch >= '0' && ch <= '4' ? NIVEL_GRADE[+ch] : 'gx'}"></i>`).join('')}</span>`).join('')}</div>
            <div class="cx-grade-leg"><span>${d.total ? `${num(d.total)} contribuições no último ano` : ''}</span><span class="cx-grade-esc">menos <i class="g0"></i><i class="g1"></i><i class="g2"></i><i class="g3"></i><i class="g4"></i> mais</span></div>` : '';
        const repos = (d.repos || []).slice(0, compacto ? 3 : 6).map((r) => `<button type="button" class="cx-repo" data-cx-abrir="${T(r.url)}" title="Abrir ${T(r.nome)} no GitHub">
            <b>${T(r.nome)}</b>${r.desc ? `<p>${T(r.desc)}</p>` : ''}<small>${r.lang ? `<span class="cx-lang"><i></i>${T(r.lang)}</span>` : ''}${r.estrelas ? `<span><i class="fa-regular fa-star"></i> ${num(r.estrelas)}</span>` : ''}${r.push ? `<span>${T(r.push.split('-').reverse().join('/'))}</span>` : ''}</small></button>`).join('');
        return `<article class="cx-card gh" style="--c:${T(p.cor)}"${marca(c.tipo)}>${cabecalhoCard(c, '@' + d.login)}
            <div class="cx-gh-topo">${img(d.avatar, 'cx-gh-av') || '<span class="cx-gh-av vazio"><i class="fa-brands fa-github"></i></span>'}
                <div><b>${T(d.nome)}</b><small>@${T(d.login)}${d.local ? ' · ' + T(d.local) : ''}</small>${d.bio ? `<p>${T(d.bio)}</p>` : ''}</div></div>
            <div class="cx-nums"><span><b>${num(d.repos_publicos)}</b> repositórios</span><span><b>${num(d.seguidores)}</b> seguidores</span><span><b>${num(d.seguindo)}</b> seguindo</span></div>
            ${grade}${repos ? `<div class="cx-sub">Repositórios recentes</div><div class="cx-repos">${repos}</div>` : ''}
            <div class="cx-rodape">${botaoAbrir(c.url, 'Ver no GitHub')}</div></article>`;
    }

    function cartaoCurriculo(c, pf, compacto) {
        const p = plataforma('linkedin'), dados = c.dados && c.dados.cv;
        if (!dados) {
            return `<article class="cx-card" style="--c:${T(p.cor)}"${marca(c.tipo)}>${cabecalhoCard(c)}<div class="cx-link"><div class="cx-link-t"><b>${T(c.titulo || hostDe(c.url))}</b>${c.titulo ? `<small>${T(hostDe(c.url))}</small>` : ''}
                ${pf && pf.sou_eu ? '<em>Pra mostrar o currículo aqui, solte o PDF do seu LinkedIn em Configurações > Conexões.</em>' : ''}</div>${botaoAbrir(c.url, 'Ver no LinkedIn')}</div></article>`;
        }
        const foto = dados.foto && /^https:\/\//i.test(dados.foto) ? `<img class="cx-cv-foto" src="${ctx.escUrl(dados.foto)}" alt="">` : (pf && pf.avatar ? `<img class="cx-cv-foto" src="${ctx.escUrl(pf.avatar)}" alt="">` : '<span class="cx-cv-foto vazio"><i class="fa-solid fa-user"></i></span>');
        const banner = dados.banner && /^https:\/\//i.test(dados.banner) ? `<img src="${ctx.escUrl(dados.banner)}" alt="">` : '';
        const exps = (dados.experiencias || []).slice(0, compacto ? 2 : 20).map((e) => `<li><span class="cx-bola"></span><div><b>${T(e.cargo || e.empresa)}</b><small>${T([e.cargo ? e.empresa : '', e.periodo, e.local].filter(Boolean).join(' · '))}</small>${e.desc ? `<p>${T(e.desc)}</p>` : ''}</div></li>`).join('');
        const forms = (dados.formacao || []).slice(0, compacto ? 1 : 10).map((e) => `<li><span class="cx-bola"></span><div><b>${T(e.escola || e.curso)}</b><small>${T([e.escola ? e.curso : '', e.periodo].filter(Boolean).join(' · '))}</small></div></li>`).join('');
        const chips = (lista) => (lista || []).slice(0, compacto ? 6 : 40).map((x) => `<span class="cx-chip">${T(x)}</span>`).join('');
        return `<article class="cx-card cv" style="--c:${T(p.cor)}"${marca(c.tipo)}>${cabecalhoCard(c, 'Currículo')}
            <div class="cx-cv-banner">${banner}</div>
            <div class="cx-cv-topo">${foto}<div><b>${T(dados.nome || c.titulo)}</b>${dados.headline ? `<span>${T(dados.headline)}</span>` : ''}${dados.local ? `<small><i class="fa-solid fa-location-dot"></i> ${T(dados.local)}</small>` : ''}</div></div>
            ${dados.sobre ? `<div class="cx-sub">Sobre</div><p class="cx-texto${compacto ? ' cx-clamp' : ''}">${T(dados.sobre)}</p>` : ''}
            ${exps ? `<div class="cx-sub">Experiência</div><ul class="cx-linha-tempo">${exps}</ul>` : ''}
            ${forms ? `<div class="cx-sub">Formação</div><ul class="cx-linha-tempo">${forms}</ul>` : ''}
            ${(dados.competencias || []).length ? `<div class="cx-sub">Competências</div><div class="cx-chips">${chips(dados.competencias)}</div>` : ''}
            ${(dados.idiomas || []).length ? `<div class="cx-sub">Idiomas</div><div class="cx-chips">${chips(dados.idiomas)}</div>` : ''}
            <div class="cx-rodape">${botaoAbrir(c.url, 'Ver no LinkedIn')}</div></article>`;
    }

    function cartao(c, pf, compacto) {
        switch (c.tipo) {
            case 'github': return cartaoGithub(c, compacto);
            case 'linkedin': return cartaoCurriculo(c, pf, compacto);
            case 'youtube': case 'spotify': case 'twitch': return cartaoMidia(c);
            case 'bazar': return cartaoLoja(c);
            case 'fila': return cartaoFila(c, pf);
            default: return cartaoLink(c);
        }
    }

    /** O HTML da segunda face. `dados` = { lista, restrito? } ou null (carregando). */
    function htmlFace(pf, dados, modo) {
        pararPlayers();                                              // a face é redesenhada por inteiro: o player antigo sairia do documento e ficaria tocando sem dono
        const av = pf.avatar ? `<img src="${ctx.escUrl(pf.avatar)}" alt="">` : T((pf.nome || '?')[0].toUpperCase());
        const lista = dados && dados.lista ? dados.lista : [];
        if (dados && !dados.restrito && lista.length && carrossel()) return htmlCarrossel(pf, lista, modo);
        let corpo;
        if (!dados) corpo = '<div class="cx-vazio"><i class="fa-solid fa-circle-notch fa-spin"></i> Carregando as conexões...</div>';
        else if (dados.restrito) corpo = '<div class="cx-vazio">As conexões ficam reservadas pra quem tem servidor em comum ou amizade.</div>';
        else if (!lista.length) corpo = '<div class="cx-vazio">Nenhuma conexão por aqui ainda.</div>';
        else corpo = lista.map((c) => cartao(c, pf, true)).join('') + '<p class="cx-nota">Os links são informados pela própria pessoa: o Pantheon ainda não confirma que a conta é dela.</p>';
        return `<div class="pc pc-conexoes ${modo === 'previa' ? 'pc-previa' : ''}">
            <div class="cx-topo"><button type="button" class="pc-seta volta" data-acao="voltar-cartao" title="Voltar ao perfil" aria-label="Voltar ao perfil"><i class="fa-solid fa-chevron-left"></i></button>
                <span class="cx-mini-av">${av}</span><div class="cx-mini-nome"><b>${T(pf.nome)}</b><small>Conexões${pf.username ? ' · @' + T(pf.username) : ''}</small></div></div>
            <div class="cx-corpo">${corpo}</div></div>`;
    }

    // ---------------------------------------------------------------------
    // CARROSSEL (opcional, Configurações > Conexões): uma conexão por página, com mais detalhes. A página 0 é o próprio perfil: "<" na 1ª conexão volta pra ele.
    // O padrão continua sendo a lista (compacta) com rolagem.
    // ---------------------------------------------------------------------
    const CAR_CHAVE = 'pnt_cx_carrossel';
    const carrossel = () => { try { return localStorage.getItem(CAR_CHAVE) === '1'; } catch (e) { return false; } };
    const cars = new Map();                                          // chave (modo + pessoa) -> { pf, lista, i }
    const chaveCar = (pf, modo) => `${modo || 'p'}:${pf.id != null ? pf.id : (pf.usuario_id != null ? pf.usuario_id : (pf.username || 'x'))}`;
    const NOTA = '<p class="cx-nota">Os links são informados pela própria pessoa: o Pantheon ainda não confirma que a conta é dela.</p>';

    function paginaCarrossel(k) {
        const { pf, lista, i, modo } = cars.get(k), n = lista.length;
        const av = pf.avatar ? `<img src="${ctx.escUrl(pf.avatar)}" alt="">` : T((pf.nome || '?')[0].toUpperCase());
        const pontos = lista.map((c, j) => `<button type="button" class="cx-pt ${j === i ? 'on' : ''}" data-cx-pag="${j}" title="${T(plataforma(c.tipo).nome)}" aria-label="Conexão ${j + 1} de ${n}"></button>`).join('');
        // as setas ficam no MEIO dos lados do retângulo, como a do perfil; a da 1ª conexão volta ao perfil (a página 0 é ele)
        const esq = i === 0
            ? '<button type="button" class="pc-seta cx-fl e" data-acao="voltar-cartao" title="Voltar ao perfil" aria-label="Voltar ao perfil"><i class="fa-solid fa-chevron-left"></i></button>'
            : `<button type="button" class="pc-seta cx-fl e" data-cx-pag="${i - 1}" title="Anterior" aria-label="Conexão anterior"><i class="fa-solid fa-chevron-left"></i></button>`;
        const dir = `<button type="button" class="pc-seta cx-fl d" data-cx-pag="${i + 1}" ${i >= n - 1 ? 'disabled' : ''} title="Próxima" aria-label="Próxima conexão"><i class="fa-solid fa-chevron-right"></i></button>`;
        return `<div class="pc pc-conexoes car ${modo === 'previa' ? 'pc-previa' : ''}">
            <div class="cx-topo"><span class="cx-mini-av">${av}</span><div class="cx-mini-nome"><b>${T(pf.nome)}</b><small>Conexões${pf.username ? ' · @' + T(pf.username) : ''} · ${i + 1}/${n}</small></div></div>
            <div class="cx-car-pag">${cartao(lista[i], pf, false)}</div><div class="cx-pts">${pontos}</div></div>${esq}${dir}`;
    }

    function htmlCarrossel(pf, lista, modo) {
        const k = chaveCar(pf, modo), ant = cars.get(k);
        cars.set(k, { pf, lista, modo, i: Math.min(ant ? ant.i : 0, lista.length - 1) });
        return `<div class="cx-cwrap" data-car="${T(k)}">${paginaCarrossel(k)}</div>`;
    }

    function irPagina(box, j) {
        const s = box && cars.get(box.dataset.car);
        if (!s) return;
        s.i = Math.max(0, Math.min(j, s.lista.length - 1));
        pararPlayers();                                              // a página some: o player dela não pode ficar tocando sem dono
        box.innerHTML = paginaCarrossel(box.dataset.car);
    }

    let toque = null;
    function ligarGestos() {
        if (ligarGestos.feito) return;
        ligarGestos.feito = true;
        document.addEventListener('touchstart', (e) => { const b = e.target.closest && e.target.closest('.cx-cwrap'); toque = b ? { x: e.touches[0].clientX, y: e.touches[0].clientY, b } : null; }, { passive: true });
        document.addEventListener('touchend', (e) => {
            if (!toque) return;
            const t = e.changedTouches[0], dx = t.clientX - toque.x, dy = t.clientY - toque.y, b = toque.b;
            toque = null;
            if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy) * 1.5) return;       // só gesto de lado (rolar pra baixo não vira de página)
            const s = cars.get(b.dataset.car); if (!s) return;
            if (dx < 0) irPagina(b, s.i + 1); else if (s.i > 0) irPagina(b, s.i - 1);
        }, { passive: true });
    }

    function ligarCarrossel() {
        const c = $('cx-car');
        if (!c || c._ligada) return;
        c._ligada = true;
        c.checked = carrossel();
        c.addEventListener('change', () => {
            try { localStorage.setItem(CAR_CHAVE, c.checked ? '1' : '0'); } catch (e) { /* sem armazenamento: vale só até recarregar */ }
            cars.clear();
            if (typeof ctx.aoMudarMinhas === 'function') ctx.aoMudarMinhas(minhas || []);      // repinta a prévia e o cartão aberto
        });
    }

    /** A setinha (parte do cartão da frente): chamada pelo htmlCartao quando a pessoa tem conexões. */
    function htmlSeta(pf) {
        return `<button type="button" class="pc-seta" data-acao="conexoes" title="Ver as conexões" aria-label="Ver as conexões de ${T(pf.nome)}"><i class="fa-solid fa-chevron-right"></i></button>`;
    }

    /** Clique dentro de uma face (delegado pelo popup e pelas prévias). true = tratei. */
    function aoClicar(e) {
        const g = e.target.closest('[data-cx-pag]');
        if (g) { e.stopPropagation(); if (!g.disabled) irPagina(g.closest('.cx-cwrap'), Number(g.dataset.cxPag)); return true; }
        const t = e.target.closest('[data-cx-tocar]');
        if (t) { e.stopPropagation(); tocar(t); return true; }
        const fx = e.target.closest('[data-cx-faixa]');
        if (fx) { e.stopPropagation(); tocarFaixa(fx); return true; }
        const pula = e.target.closest('[data-cx-ant], [data-cx-prox]');
        if (pula) {
            e.stopPropagation();
            const card = pula.closest('[data-cx-vinil]'), p = card && players.get(card);
            if (p && p.proxima) { if (pula.hasAttribute('data-cx-prox')) p.proxima(); else p.anterior(); }
            return true;
        }
        const a = e.target.closest('[data-cx-abrir]');
        if (a) { e.stopPropagation(); abrirLink(a.dataset.cxAbrir); return true; }
        const l = e.target.closest('[data-cx-loja]');
        if (l) { e.stopPropagation(); ctx.abrirLoja(Number(l.dataset.cxLoja)); return true; }
        return false;
    }

    // ---------------------------------------------------------------------
    // A ABA "CONEXÕES" (cadeia de links)
    // ---------------------------------------------------------------------
    const semLink = (l) => l.tipo === 'bazar' || l.tipo === 'fila';                              // itens que não nascem de um link colado
    const novaLinha = (o) => Object.assign({ k: 'n' + (++seq), id: null, tipo: '', url: '', titulo: '', dados: null, erro: '', buscando: false, atualizado: null, salvando: false, sujo: false }, o || {});

    function doServidor(l) {
        return novaLinha({ k: 's' + l.id, id: l.id, tipo: l.tipo, url: l.url || '', titulo: l.titulo || '', dados: l.dados, erro: l.erro || '', buscando: !!l.buscando, atualizado: l.atualizado });
    }

    /** Só pode sobrar UMA caixinha vazia (a do foco, ou a última): escrever e apagar não empilha caixinhas. */
    function compactarVazias(manterK) {
        const vazias = linhas.filter((l) => !l.id && !semLink(l) && !l.url.trim());
        if (vazias.length <= 1) return;
        const fica = vazias.find((l) => l.k === manterK) || vazias[vazias.length - 1];
        vazias.forEach((l) => {
            if (l === fica) return;
            linhas.splice(linhas.indexOf(l), 1);
            const el = document.querySelector(`#cx-lista [data-k="${l.k}"]`); if (el) el.remove();
        });
    }

    function garantirLinhaVazia() {
        compactarVazias();
        if (linhas.length < MAX && !linhas.some((l) => !l.id && !semLink(l) && !l.url.trim())) linhas.push(novaLinha());
    }

    function estadoHtml(l) {
        if (l.tipo === 'fila' && l.id && !l.erro && !l.salvando) {
            const fx = faixasDe(l), falta = fx.some((f) => !f.t && !f.x);
            return `<span class="o"><i class="fa-solid fa-circle-check"></i> Playlist · ${fx.length} ${fx.length === 1 ? 'música' : 'músicas'}${falta ? ' <small>buscando os títulos...</small>' : ''}</span>`;
        }
        if (l.erro) return `<span class="e"><i class="fa-solid fa-circle-exclamation"></i> ${T(l.erro)}</span>`;
        if (l.importando) return '<span class="a"><i class="fa-solid fa-circle-notch fa-spin"></i> Lendo o PDF e montando o currículo...</span>';
        if (l.salvando) return '<span class="a"><i class="fa-solid fa-circle-notch fa-spin"></i> Salvando...</span>';
        if (l.buscando) return '<span class="a"><i class="fa-solid fa-circle-notch fa-spin"></i> Buscando os dados...</span>';
        const p = plataforma(l.tipo);
        const cvPronto = l.tipo === 'linkedin' && l.dados && l.dados.cv;
        if (l.id) {
            const extra = cvPronto ? ` <small>currículo pronto (${(l.dados.cv.experiencias || []).length} experiência(s))</small>`
                : l.tipo === 'linkedin' ? ' <small>solte o PDF do seu LinkedIn pra mostrar o currículo</small>'
                : (l.dados && l.dados.sem_previa) ? ' <small>sem prévia: o site não deixa o app ler a página (aparece só o link)</small>'
                : (l.atualizado ? ` <small>atualizado ${T(atras(l.atualizado))}</small>` : '');
            return `<span class="o"><i class="fa-solid fa-circle-check"></i> ${T(p.nome)}${l.titulo ? ' · ' + T(l.titulo) : ''}${extra}</span>`;
        }
        if (l.url.trim()) return `<span class="d">${T(p.nome)} · tecle Enter ou saia do campo pra adicionar</span>`;
        return '';
    }

    function htmlLinha(l, i, total) {
        const p = plataforma(l.tipo);
        const extra = !l.id ? '' : l.tipo === 'linkedin'
            ? `<button type="button" class="cx-bt" data-cx-pdf="${l.id}" title="O LinkedIn não deixa nenhum app ler o perfil pelo link. Solte aqui o PDF que ele mesmo gera (Mais > Salvar como PDF)."><i class="fa-solid fa-file-pdf"></i> <span>${l.dados && l.dados.cv ? 'Importar o PDF de novo' : 'Importar o PDF do LinkedIn'}</span></button>`
            : (P[l.tipo] && P[l.tipo].busca ? `<button type="button" class="cx-bt" data-cx-atualizar="${l.id}" title="Buscar os dados de novo"><i class="fa-solid fa-rotate"></i></button>` : '');
        const campo = l.tipo === 'bazar'
            ? '<div class="cx-fixo">Minha loja do Bazar</div>'
            : l.tipo === 'fila'
            ? `<div class="cx-fixo">Minha playlist <small>(vira um disco no seu perfil; até ${MAXF} músicas)</small></div>`
            : `<input type="text" class="discord-input" data-cx="url" inputmode="url" maxlength="300" spellcheck="false" autocomplete="off" value="${T(l.url)}" placeholder="Cole um link: GitHub, LinkedIn, YouTube, Twitch, Spotify, loja, site...">`;
        const vazia = !l.id && !l.url.trim() && !semLink(l);
        return `<div class="cx-linha ${l.erro ? 'erro' : ''} ${l.id ? 'salvo' : ''} ${vazia ? 'vazia' : ''}" data-k="${T(l.k)}">
            <span class="cx-ico" style="--c:${T(p.cor)}">${iconeHtml(l.tipo, p)}</span>
            <div class="cx-campo">${campo}<small class="cx-estado">${estadoHtml(l)}</small></div>
            <div class="cx-acoes">${extra}${vazia ? '' : `<button type="button" class="cx-bt ic" data-cx-sobe="${T(l.k)}" ${i === 0 ? 'disabled' : ''} title="Subir" aria-label="Subir"><i class="fa-solid fa-chevron-up"></i></button>
                <button type="button" class="cx-bt ic" data-cx-desce="${T(l.k)}" ${i >= total - 1 || !linhas[i + 1] || (!linhas[i + 1].id && !linhas[i + 1].url.trim()) ? 'disabled' : ''} title="Descer" aria-label="Descer"><i class="fa-solid fa-chevron-down"></i></button>
                <button type="button" class="cx-bt ic perigo" data-cx-tira="${T(l.k)}" title="Remover" aria-label="Remover"><i class="fa-solid fa-trash"></i></button>`}</div>${l.tipo === 'fila' && l.id ? htmlEditorFila(l) : ''}</div>`;
    }

    /** O editor da playlist (dentro da linha dela): as músicas com subir/descer/tirar e o campo de colar links. Quem decide o que entra é o servidor. */
    function htmlItensEditor(fx) {
        if (!fx.length) return '<li class="cx-fila-vazia">Nenhuma música ainda. Cole um link logo abaixo.</li>';
        return fx.map((f, i) => {
            const k = chaveFaixa(f);
            return `<li class="cx-fila-item${f.x ? ' off' : ''}">${img(capaFaixa(f), 'cx-fx-capa') || semCapa}<span class="cx-fx-t"><b>${T(nomeFaixa(f))}</b><small>${T(subFaixa(f))}</small></span>
                <span class="cx-fila-bts"><button type="button" class="cx-bt ic" data-cx-fila-sobe="${T(k)}" ${i === 0 ? 'disabled' : ''} title="Subir" aria-label="Subir"><i class="fa-solid fa-chevron-up"></i></button>
                <button type="button" class="cx-bt ic" data-cx-fila-desce="${T(k)}" ${i === fx.length - 1 ? 'disabled' : ''} title="Descer" aria-label="Descer"><i class="fa-solid fa-chevron-down"></i></button>
                <button type="button" class="cx-bt ic perigo" data-cx-fila-tira="${T(k)}" title="Tirar da playlist" aria-label="Tirar da playlist"><i class="fa-solid fa-xmark"></i></button></span></li>`;
        }).join('');
    }

    function htmlEditorFila(l) {
        const cheia = faixasDe(l).length >= MAXF;
        return `<div class="cx-fila-ed"><ol class="cx-fila-edl">${htmlItensEditor(faixasDe(l))}</ol>
            <div class="cx-fila-add"><input type="text" class="discord-input" data-cx="fila-url" inputmode="url" maxlength="2000" spellcheck="false" autocomplete="off" value="${T(filaTexto)}" placeholder="${cheia ? 'A playlist está cheia' : 'Cole links de músicas ou playlists do YouTube ou do YouTube Music'}"${cheia ? ' disabled' : ''}>
            <button type="button" class="cx-bt primario" data-cx-fila-add><i class="fa-solid fa-plus"></i> Adicionar</button></div>
            <small class="cx-fila-msg${filaMsg[1] ? ' ' + filaMsg[1] : ''}" role="status">${T(filaMsg[0])}</small></div>`;
    }

    function atualizarLinhaNoDom(l) {
        const el = document.querySelector(`#cx-lista [data-k="${l.k}"]`);
        if (!el) return;
        const p = plataforma(l.tipo);
        const ico = el.querySelector('.cx-ico');
        ico.style.setProperty('--c', p.cor); ico.innerHTML = iconeHtml(l.tipo, p);
        el.querySelector('.cx-estado').innerHTML = estadoHtml(l);
        el.classList.toggle('erro', !!l.erro);
        if (l.tipo === 'fila' && l.id) {                                               // a lista de músicas troca por dentro; o campo de colar (e o que a pessoa digita nele) não é recriado
            const ol = el.querySelector('.cx-fila-edl'), campo = el.querySelector('[data-cx="fila-url"]');
            if (ol) ol.innerHTML = htmlItensEditor(faixasDe(l));
            if (campo) campo.disabled = faixasDe(l).length >= MAXF;
        }
    }

    function desenharLinhas() {
        const alvo = $('cx-lista');
        if (!alvo) return;
        const foco = document.activeElement && document.activeElement.matches && document.activeElement.matches('#cx-lista input') ? document.activeElement : null;
        const focoK = foco && foco.closest('[data-k]') ? foco.closest('[data-k]').dataset.k : null;
        const caret = foco ? [foco.selectionStart, foco.selectionEnd] : null;
        garantirLinhaVazia();
        if (foco && [...alvo.querySelectorAll('[data-k]')].map((e) => e.dataset.k).join(',') === linhas.map((l) => l.k).join(',')) {     // está digitando e nada mudou de lugar: só atualiza os textos (não recria o campo)
            linhas.forEach(atualizarLinhaNoDom);
            return;
        }
        const usadas = linhas.filter((l) => l.id || l.url.trim() || semLink(l)).length;
        alvo.innerHTML = linhas.map((l, i) => htmlLinha(l, i, linhas.length)).join('');
        const bz = $('cx-bazar'); if (bz) bz.disabled = !!linhas.some((l) => l.tipo === 'bazar') || usadas >= MAX;
        const fl = $('cx-fila'); if (fl) fl.disabled = !!linhas.some((l) => l.tipo === 'fila') || usadas >= MAX;
        const cont = $('cx-contagem'); if (cont) cont.textContent = `${usadas}/${MAX}`;
        if (foco) {                                                                    // a estrutura mudou (ex.: o link foi confirmado): devolve o cursor ao mesmo campo, ou à próxima caixinha vazia
            const mesmo = focoK && alvo.querySelector(`[data-k="${focoK}"] input`);
            const alvoFoco = mesmo || alvo.querySelector('.cx-linha.vazia input');
            if (alvoFoco) { alvoFoco.focus(); if (mesmo && caret && caret[0] != null) { try { alvoFoco.setSelectionRange(caret[0], caret[1]); } catch (e) { /* tipo sem seleção */ } } }
        }
    }

    function salvar(agora) {
        clearTimeout(timerSalvar);
        const espera = Math.max(agora ? 0 : 450, INTERVALO_MS - (Date.now() - ultimoEnvio));       // respeita o intervalo do servidor em vez de ser ignorado
        timerSalvar = setTimeout(() => {
            if (salvando) { pedirDeNovo = true; return; }
            enviados = linhas.filter((l) => semLink(l) || l.url.trim());
            if (!enviados.length && !(minhas && minhas.length)) return;
            if (!enviados.some((l) => l.sujo) && enviados.length === (minhas || []).length && enviados.every((l, i) => minhas[i] && minhas[i].id === l.id)) return;   // nada mudou
            salvando = true; ultimoEnvio = Date.now();
            enviados.forEach((l) => { l.salvando = true; l.erro = ''; });
            enviados.forEach(atualizarLinhaNoDom);
            clearTimeout(timerResposta);
            timerResposta = setTimeout(() => {                                                     // sem resposta em 12 s: destrava e avisa (nunca fica "Salvando..." pra sempre)
                if (!salvando) return;
                salvando = false;
                enviados.forEach((l) => { l.salvando = false; l.erro = 'O servidor não respondeu. Tente de novo.'; atualizarLinhaNoDom(l); });
            }, 12000);
            ctx.emitir('conexoes_salvar', { itens: enviados.map((l) => (semLink(l) ? { id: l.id || undefined, tipo: l.tipo } : { id: l.id || undefined, url: l.url.trim() })) });
        }, espera);
    }

    function receber(d) {
        P = d.plataformas || P; MAX = d.max || MAX; MAXF = d.max_faixas || MAXF; IA = !!d.ia; IMAGENS = d.imagens_ok || IMAGENS;
        minhas = d.lista || [];
        ligarIa(); ligarCarrossel();
        const pendentes = linhas.filter((l) => !l.id && l.url.trim() && !semLink(l) && !l.salvando);     // digitado e ainda não confirmado: não some
        linhas = minhas.map(doServidor).concat(pendentes);
        desenharLinhas();
        if (typeof ctx.aoMudarMinhas === 'function') ctx.aoMudarMinhas(minhas);
    }

    function aoSalvar() {
        salvando = false; clearTimeout(timerResposta);
        if (pedirDeNovo) { pedirDeNovo = false; salvar(true); }
    }

    function erro(msg, indice) {
        salvando = false; clearTimeout(timerResposta);
        enviados.forEach((l) => { l.salvando = false; });
        const alvo = indice != null ? enviados[indice] : null;
        if (alvo) { alvo.erro = msg; atualizarLinhaNoDom(alvo); enviados.forEach(atualizarLinhaNoDom); } else { ctx.toast(msg, 'warning'); enviados.forEach(atualizarLinhaNoDom); }
        if (pedirDeNovo) pedirDeNovo = false;
    }

    // ---------------------------------------------------------------------
    // COLAR LINKS NA PLAYLIST (o servidor valida, junta, evita repetida e busca os títulos; aqui só o campo e as mensagens)
    // ---------------------------------------------------------------------
    let filaOcupada = false, filaTimer = null;
    function msgFila(texto, tipo) {                                    // a mensagem fica guardada: a lista é redesenhada a cada resposta do servidor e ela não pode sumir junto
        filaMsg = [texto, tipo];
        const m = document.querySelector('#cx-lista .cx-fila-msg');
        if (!m) return false;
        m.textContent = texto; m.className = 'cx-fila-msg' + (tipo ? ' ' + tipo : '');
        return true;
    }

    function adicionarFila(campo) {
        const txt = campo && campo.value.trim();
        if (!txt || filaOcupada) return;
        filaOcupada = true; filaTexto = campo.value;
        clearTimeout(filaTimer); filaTimer = setTimeout(() => { filaOcupada = false; }, 8000);       // sem resposta em 8 s, libera o campo
        msgFila('Adicionando...', '');
        ctx.emitir('fila_adicionar', { url: txt });
    }

    function filaOk(d) {
        filaOcupada = false; clearTimeout(filaTimer); filaTexto = '';
        const campo = document.querySelector('#cx-lista [data-cx="fila-url"]'); if (campo) campo.value = '';
        const n = Number(d && d.adicionadas) || 0, avisos = (d && d.avisos) || [];
        msgFila(`${n} ${n === 1 ? 'música adicionada' : 'músicas adicionadas'}.${avisos.length ? ' ' + avisos.join(' ') : ''}`, avisos.length ? 'a' : 'o');
        if (!avisos.length) setTimeout(() => { if (filaMsg[1] === 'o') msgFila('', ''); }, 6000);
    }

    function filaErro(msg) {
        filaOcupada = false; clearTimeout(filaTimer);
        if (!msgFila(msg || 'Não consegui mexer na playlist.', 'e')) ctx.toast(msg || 'Não consegui mexer na playlist.', 'warning');
    }

    function ligarAba() {
        const lista = $('cx-lista');
        if (!lista || lista._ligada) return;
        lista._ligada = true;
        const achar = (el) => { const d = el.closest('[data-k]'); return d ? linhas.find((l) => l.k === d.dataset.k) : null; };
        lista.addEventListener('input', (e) => {
            if (e.target.matches('[data-cx="fila-url"]')) { filaTexto = e.target.value; msgFila('', ''); return; }
            if (!e.target.matches('[data-cx="url"]')) return;
            const l = achar(e.target); if (!l) return;
            l.url = e.target.value; l.tipo = tipoPorTexto(l.url); l.sujo = true; l.erro = '';
            atualizarLinhaNoDom(l);
            compactarVazias(l.k);
            if (l.url.trim() && linhas.length < MAX && !linhas.some((x) => !x.id && !x.url.trim() && !semLink(x))) {       // "já aparece outro retângulo embaixo"
                const nova = novaLinha(); linhas.push(nova);
                lista.insertAdjacentHTML('beforeend', htmlLinha(nova, linhas.length - 1, linhas.length));
                const el = lista.querySelector(`[data-k="${nova.k}"]`); if (el) el.classList.add('entra');
            }
        });
        lista.addEventListener('paste', (e) => { if (e.target.matches('[data-cx="fila-url"]')) setTimeout(() => adicionarFila(e.target), 60); else if (e.target.matches('[data-cx="url"]')) setTimeout(() => { const l = achar(e.target); if (l && l.url.trim()) salvar(true); }, 60); });
        lista.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.matches('[data-cx="fila-url"]')) { e.preventDefault(); adicionarFila(e.target); } else if (e.key === 'Enter' && e.target.matches('[data-cx="url"]')) { e.preventDefault(); const l = achar(e.target); if (l && l.url.trim()) salvar(true); } });
        lista.addEventListener('focusout', (e) => { if (e.target.matches && e.target.matches('[data-cx="url"]')) { const l = achar(e.target); if (l && l.sujo && l.url.trim()) salvar(false); } });
        lista.addEventListener('click', (e) => {
            const b = e.target.closest('button'); if (!b) return;
            const mover = (k, d) => { const i = linhas.findIndex((x) => x.k === k), j = i + d; if (i < 0 || j < 0 || j >= linhas.length || (!linhas[j].id && !linhas[j].url.trim())) return; [linhas[i], linhas[j]] = [linhas[j], linhas[i]]; linhas[i].sujo = linhas[j].sujo = true; desenharLinhas(); salvar(true); };
            if (b.dataset.cxSobe) mover(b.dataset.cxSobe, -1);
            else if (b.dataset.cxDesce) mover(b.dataset.cxDesce, 1);
            else if (b.dataset.cxTira) {
                const k = b.dataset.cxTira, tinha = linhas.find((x) => x.k === k);
                const tirar = () => { linhas = linhas.filter((x) => x.k !== k); desenharLinhas(); if (tinha && tinha.id) salvar(true); };
                const n = tinha && tinha.tipo === 'fila' ? faixasDe(tinha).length : 0;
                if (n) ctx.confirmar('Apagar a playlist?', `As ${n} ${n === 1 ? 'música sai' : 'músicas saem'} do seu perfil. Você pode criar outra depois.`, tirar); else tirar();
            }
            else if (b.dataset.cxFilaAdd) adicionarFila(b.closest('.cx-fila-ed').querySelector('[data-cx="fila-url"]'));
            else if (b.dataset.cxFilaSobe) ctx.emitir('fila_mover', { chave: b.dataset.cxFilaSobe, delta: -1 });
            else if (b.dataset.cxFilaDesce) ctx.emitir('fila_mover', { chave: b.dataset.cxFilaDesce, delta: 1 });
            else if (b.dataset.cxFilaTira) ctx.emitir('fila_remover', { chave: b.dataset.cxFilaTira });
            else if (b.dataset.cxPdf) escolherPdf(Number(b.dataset.cxPdf));
            else if (b.dataset.cxAtualizar) ctx.emitir('conexao_atualizar', { id: Number(b.dataset.cxAtualizar) });
        });
        const fl = $('cx-fila');
        if (fl) fl.addEventListener('click', () => { if (linhas.some((l) => l.tipo === 'fila')) return; const l = novaLinha({ tipo: 'fila', sujo: true }); const vazia = linhas.findIndex((x) => !x.id && !x.url.trim() && !semLink(x)); if (vazia >= 0) linhas.splice(vazia, 0, l); else linhas.push(l); desenharLinhas(); salvar(true); });
        const bz = $('cx-bazar');
        if (bz) bz.addEventListener('click', () => { if (linhas.some((l) => l.tipo === 'bazar')) return; const l = novaLinha({ tipo: 'bazar', sujo: true }); const vazia = linhas.findIndex((x) => !x.id && !x.url.trim()); if (vazia >= 0) linhas.splice(vazia, 0, l); else linhas.push(l); desenharLinhas(); salvar(true); });
    }

    function abrirAba() {
        ligarAba(); ligarCarrossel();
        if (minhas === null) { const a = $('cx-lista'); if (a) a.innerHTML = '<div class="cx-vazio"><i class="fa-solid fa-circle-notch fa-spin"></i> Carregando...</div>'; }
        else desenharLinhas();
        ctx.emitir('conexoes_listar', {});
    }

    // ---------------------------------------------------------------------
    // IMPORTAR O PDF DO LINKEDIN: automático (lê, confere, PUBLICA). Sem editor: pra mudar algo, a pessoa muda no LinkedIn e solta o PDF de novo.
    // O LinkedIn não deixa nenhum app ler o perfil pelo link, então o PDF que ele mesmo gera é o caminho legítimo mais direto.
    // ---------------------------------------------------------------------
    const IA_CHAVE = 'pnt_cx_ia';
    const usarIa = () => { const c = $('cx-ia'); return !!(IA && c && c.checked); };

    function escolherPdf(id) {
        let inp = $('cx-pdf');
        if (!inp) {
            inp = document.createElement('input');
            inp.type = 'file'; inp.id = 'cx-pdf'; inp.accept = 'application/pdf,.pdf'; inp.hidden = true;
            inp.addEventListener('change', aoEscolherPdf);
            document.body.appendChild(inp);
        }
        inp.dataset.id = String(id);
        inp.click();
    }

    async function aoEscolherPdf(e) {
        const inp = e.target, arq = inp.files && inp.files[0], id = Number(inp.dataset.id);
        inp.value = '';
        const l = linhas.find((x) => x.id === id);
        if (!arq || !l) return;
        l.importando = true; l.erro = ''; atualizarLinhaNoDom(l);
        const fd = new FormData();
        fd.append('arquivo', arq); fd.append('conexao_id', String(id));
        if (usarIa()) fd.append('ia', '1');
        try {
            const r = await fetch('/api/conexoes/importar-cv', { method: 'POST', body: fd });
            const j = await r.json().catch(() => ({}));
            if (!r.ok) l.erro = j.error || 'Não consegui ler esse PDF.';
            else {
                const x = j.resumo || {};
                ctx.toast(`Currículo pronto${x.nome ? ': ' + x.nome : ''} (${x.experiencias || 0} experiência(s), ${x.formacao || 0} formação). Já aparece no seu perfil.${(j.avisos || []).length ? ' ' + j.avisos.join(' ') : ''}`, 'success');
            }
        } catch (er) { l.erro = 'Sem conexão com o servidor.'; }
        l.importando = false;
        const atual = linhas.find((x) => x.id === id) || l;      // (se deu certo, o servidor já mandou a lista nova por `conexoes` e as linhas são OUTROS objetos: atualiza a de agora)
        atual.importando = false;
        atualizarLinhaNoDom(atual);
    }

    function ligarIa() {
        const linha = $('cx-ia-linha'), caixa = $('cx-ia');
        if (!linha || !caixa) return;
        linha.hidden = !IA;
        if (!caixa._ligada) { caixa._ligada = true; try { caixa.checked = localStorage.getItem(IA_CHAVE) === '1'; } catch (e) { /* sem armazenamento: começa desmarcado */ } caixa.addEventListener('change', () => { try { localStorage.setItem(IA_CHAVE, caixa.checked ? '1' : '0'); } catch (e) { /* ignora */ } }); }
    }

    // ---------------------------------------------------------------------
    return {
        iniciar(c) { ctx = c; ligarGestos(); },
        receber, aoSalvar, erro, filaOk, filaErro, carregarYt, abrirAba, htmlFace, htmlSeta, aoClicar, abrirLink, parar() { pararPlayers(); cars.clear(); },
        tocando: () => players.size > 0, modoCarrossel: carrossel,
        minhas: () => minhas, qtdMinhas: () => (minhas ? minhas.length : null), registro: () => P, imagens: () => IMAGENS,
        definirRegistro(d) { P = d.plataformas || P; IMAGENS = d.imagens_ok || IMAGENS; },
        _tipoPorTexto: tipoPorTexto,
    };
})();
