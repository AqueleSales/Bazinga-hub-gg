/* Texto formatado das mensagens (Rodada 39). Objeto global `TextoRico`. Serve canal e DM (as duas passam por appendMessageGrouped).
 *
 * Gramática (parecida com a do Markdown/Discord; tudo escapado ANTES de virar HTML, então nada que a pessoa digita vira tag):
 *   **negrito**  *itálico*  _itálico_  __sublinhado__  ~~riscado~~  ||spoiler||  ==destaque==  ***negrito e itálico***
 *   `código`  ``código``  ```linguagem\n bloco de código com cor e botão de copiar ```
 *   # título  ## subtítulo  ### título pequeno  -# texto miúdo  > citação  >>> citação até o fim
 *   - lista  * lista  1. lista numerada          \* ignora o símbolo
 *   [texto](https://site)  e links soltos (https://...), com cor própria (legível em tema claro e escuro)
 *   prévia: YouTube, Spotify e SoundCloud (só carregam no clique), arquivos de áudio e vídeo (preload="none": nada baixa até apertar play)
 *   menções: <@123> pessoa · <@&7> cargo (com a cor dele) · <@todos> <@aqui> <@staff> <@dono> <@amigos> (resolvidas no SERVIDOR: app/mencoes.py)
 * Segurança: href só http/https sem usuário:senha; link "mascarado" ([https://banco.com](https://outro.com)) mostra o destino de verdade; cor de cargo só #rrggbb;
 * iframe só de YouTube (nocookie), Spotify e SoundCloud, montado a partir de IDs validados (nunca da URL crua) e dentro de sandbox.
 */
const TextoRico = (() => {
    'use strict';
    const A = '\u0001', B = '\u0002';
    const RE_MARC = /\u0001(\d+)\u0002/g;
    const RE_CTRL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g;     // inclui \u0001 e \u0002: são os marcadores internos, ninguém pode forjá-los
    const esc = (v) => String(v == null ? '' : v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    const MAX_EMBEDS = 2;
    let C = {};

    // ---------------------------------------------------------------------
    // código: realce simples por linguagem (sem biblioteca)
    // ---------------------------------------------------------------------
    const PAL = (s) => new Set(s.split(/\s+/).filter(Boolean));
    const CLIKE = PAL('abstract as async await break case catch class const continue default delete do else enum export extends false final finally for function get if implements import in instanceof interface is let namespace new null of override package private protected public readonly return set static struct super switch this throw true try type typeof undefined using var void while with yield int long float double bool boolean char string byte short unsigned signed fn mut pub impl trait match loop use mod crate self Self where go defer chan select range func nil fun val when object data inline lateinit companion sealed val');
    const LINGS = {
        js: { kw: CLIKE, com: '//[^\\n]*|/\\*[\\s\\S]*?\\*/', str: '`(?:\\\\[\\s\\S]|[^`\\\\])*`|"(?:\\\\.|[^"\\\\\\n])*"|\'(?:\\\\.|[^\'\\\\\\n])*\'' },
        c: { kw: CLIKE, com: '//[^\\n]*|/\\*[\\s\\S]*?\\*/', str: '"(?:\\\\.|[^"\\\\\\n])*"|\'(?:\\\\.|[^\'\\\\\\n])*\'' },
        py: { kw: PAL('def class return if elif else for while in not and or is import from as with try except finally raise pass break continue lambda yield None True False global nonlocal async await del assert self print'), com: '#[^\\n]*', str: '"""[\\s\\S]*?"""|\'\'\'[\\s\\S]*?\'\'\'|"(?:\\\\.|[^"\\\\\\n])*"|\'(?:\\\\.|[^\'\\\\\\n])*\'' },
        sh: { kw: PAL('if then else elif fi for while do done case esac function in echo cd ls cat grep sudo export source return exit set unset local npm pip git docker'), com: '#[^\\n]*', str: '"(?:\\\\.|[^"\\\\])*"|\'[^\']*\'' },
        sql: { kw: PAL('select from where insert into values update set delete create table alter drop index join left right inner outer on group by order having limit offset as and or not null is in like between distinct union all primary key foreign references default unique count sum avg min max case when then else end'), ci: true, com: '--[^\\n]*|/\\*[\\s\\S]*?\\*/', str: '\'(?:[^\']|\'\')*\'|"[^"]*"' },
        json: { kw: PAL('true false null'), com: '(?!)', str: '"(?:\\\\.|[^"\\\\\\n])*"' },
        css: { kw: PAL('important inherit initial unset none auto'), com: '/\\*[\\s\\S]*?\\*/', str: '"[^"\\n]*"|\'[^\'\\n]*\'', extra: ['(?:--|-?)[a-zA-Z][\\w-]*(?=\\s*:)', 'f'] },
        html: { kw: new Set(), com: '<!--[\\s\\S]*?-->', str: '"[^"\\n]*"|\'[^\'\\n]*\'', extra: ['</?[A-Za-z][\\w:-]*', 'k'] },
        lua: { kw: PAL('and break do else elseif end false for function if in local nil not or repeat return then true until while'), com: '--[^\\n]*', str: '"(?:\\\\.|[^"\\\\\\n])*"|\'(?:\\\\.|[^\'\\\\\\n])*\'' },
        php: { kw: CLIKE, com: '//[^\\n]*|#[^\\n]*|/\\*[\\s\\S]*?\\*/', str: '"(?:\\\\.|[^"\\\\])*"|\'(?:\\\\.|[^\'\\\\])*\'', extra: ['\\$[A-Za-z_]\\w*', 'v'] },
    };
    const ALIAS = { js: 'js', javascript: 'js', jsx: 'js', ts: 'js', typescript: 'js', tsx: 'js', node: 'js', mjs: 'js',
        py: 'py', python: 'py', rb: 'py', ruby: 'py', yaml: 'py', yml: 'py', toml: 'py', ini: 'py',
        sh: 'sh', bash: 'sh', shell: 'sh', zsh: 'sh', powershell: 'sh', ps1: 'sh', cmd: 'sh', bat: 'sh',
        sql: 'sql', mysql: 'sql', postgres: 'sql', json: 'json', css: 'css', scss: 'css', html: 'html', xml: 'html', svg: 'html', vue: 'html',
        c: 'c', cpp: 'c', 'c++': 'c', cs: 'c', csharp: 'c', 'c#': 'c', java: 'c', kotlin: 'c', kt: 'c', go: 'c', golang: 'c', rust: 'c', rs: 'c', swift: 'c', dart: 'c', scala: 'c', lua: 'lua', php: 'php' };
    const compilados = {};
    function regexDe(chave) {
        if (compilados[chave]) return compilados[chave];
        const L = LINGS[chave];
        const partes = [`(${L.com})`, `(${L.str})`, '(\\b0x[0-9a-fA-F]+\\b|\\b\\d+(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b)', '([A-Za-z_$][\\w$]*)'];
        if (L.extra) partes.splice(3, 0, `(${L.extra[0]})`);
        return (compilados[chave] = new RegExp(partes.join('|'), 'g'));
    }
    function colorir(cod, lang) {
        const chave = ALIAS[String(lang || '').toLowerCase()];
        if (!chave || cod.length > 8000) return esc(cod);
        const L = LINGS[chave], re = regexDe(chave), temExtra = !!L.extra;
        re.lastIndex = 0;
        let out = '', ult = 0, m;
        while ((m = re.exec(cod))) {
            if (m[0] === '') { re.lastIndex++; continue; }
            out += esc(cod.slice(ult, m.index));
            const t = m[0]; let cls = null;
            if (m[1]) cls = 'c'; else if (m[2]) cls = 's'; else if (m[3]) cls = 'n';
            else if (temExtra && m[4]) cls = L.extra[1];
            else {
                const palavra = temExtra ? m[5] : m[4];
                if (palavra && L.kw.has(L.ci ? palavra.toLowerCase() : palavra)) cls = 'k';
                else if (palavra && cod[re.lastIndex] === '(') cls = 'f';
            }
            out += cls ? `<span class="tk-${cls}">${esc(t)}</span>` : esc(t);
            ult = re.lastIndex;
        }
        return out + esc(cod.slice(ult));
    }
    function blocoCodigo(lang, cod) {
        cod = cod.replace(/^\n/, '').replace(/\n\s*$/, '');
        const nome = (lang || '').slice(0, 20);
        return `<div class="cod"><div class="cod-topo"><span class="cod-lang">${esc(nome || 'código')}</span>`
            + `<button type="button" class="cod-copiar" title="Copiar o código"><i class="fa-regular fa-copy"></i> <span>Copiar</span></button></div>`
            + `<pre class="cod-pre"><code>${colorir(cod, nome)}</code></pre></div>`;
    }

    // ---------------------------------------------------------------------
    // links
    // ---------------------------------------------------------------------
    function urlSegura(bruta) {
        try {
            const u = new URL(bruta);
            if (u.protocol !== 'https:' && u.protocol !== 'http:') return null;
            if (u.username || u.password || !u.hostname) return null;
            return u;
        } catch (e) { return null; }
    }
    const ehIP = (h) => /^\d{1,3}(\.\d{1,3}){3}$/.test(h) || h.includes(':');
    function encurtar(u) {
        const s = u.replace(/^https?:\/\//i, '').replace(/\/$/, '');
        return s.length > 64 ? s.slice(0, 44) + '…' + s.slice(-16) : s;
    }
    function limparFim(url) {
        let u = url;
        for (;;) {
            const c = u.slice(-1);
            if (/[.,;:!?'"]/.test(c)) u = u.slice(0, -1);
            else if (c === ')' && (u.match(/\(/g) || []).length < (u.match(/\)/g) || []).length) u = u.slice(0, -1);
            else if (c === ']' && !u.includes('[')) u = u.slice(0, -1);
            else break;
        }
        return u;
    }
    function linkHtml(u, rotuloHtml, mascarado) {
        const risco = mascarado || ehIP(u.hostname) || u.protocol === 'http:' || /(^|\.)xn--/.test(u.hostname);
        return `<a class="lnk" href="${esc(u.href)}" target="_blank" rel="noopener noreferrer nofollow ugc" data-host="${esc(u.hostname)}"${risco ? ' data-aviso="1"' : ''}>${rotuloHtml}</a>`;
    }

    // ---------------------------------------------------------------------
    // prévias (só YouTube, Spotify, SoundCloud e arquivos de mídia direta)
    // ---------------------------------------------------------------------
    function tempoYt(v) {
        if (!v) return 0;
        if (/^\d{1,6}$/.test(v)) return Number(v);
        const m = /^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/.exec(v);
        return m ? (Number(m[1] || 0) * 3600 + Number(m[2] || 0) * 60 + Number(m[3] || 0)) : 0;
    }
    function embedDe(u) {
        const h = u.hostname.toLowerCase().replace(/^www\.|^m\./, '');
        const p = u.pathname;
        // YouTube / YouTube Music
        let id = null;
        if (h === 'youtu.be') id = p.slice(1).split('/')[0];
        else if (h === 'youtube.com' || h === 'music.youtube.com' || h === 'youtube-nocookie.com') {
            if (p === '/watch') id = u.searchParams.get('v');
            else { const m = /^\/(?:shorts|embed|live|v)\/([\w-]{11})/.exec(p); if (m) id = m[1]; }
        }
        const lista = u.searchParams.get('list');
        const listaOk = lista && /^[\w-]{10,64}$/.test(lista) ? lista : '';
        if (id && /^[\w-]{11}$/.test(id)) {
            const t = Math.min(tempoYt(u.searchParams.get('t') || u.searchParams.get('start')), 86400);
            return { chave: 'yt:' + id, html: `<div class="emb emb-yt" data-emb="yt" data-id="${id}" data-t="${t}" data-lista="${esc(listaOk)}">`
                + `<button type="button" class="emb-capa" aria-label="Assistir aqui no chat"><img src="https://i.ytimg.com/vi/${id}/hqdefault.jpg" alt="" loading="lazy" referrerpolicy="no-referrer">`
                + `<span class="emb-play"><i class="fa-solid fa-play"></i></span><span class="emb-selo"><i class="fa-brands fa-youtube"></i> YouTube${t ? ' · ' + Math.floor(t / 60) + ':' + String(t % 60).padStart(2, '0') : ''}</span></button></div>` };
        }
        if ((h === 'youtube.com') && p === '/playlist' && listaOk) {
            return { chave: 'ytl:' + listaOk, html: `<div class="emb emb-yt lista" data-emb="yt" data-id="" data-t="0" data-lista="${esc(listaOk)}">`
                + `<button type="button" class="emb-capa sem-img" aria-label="Abrir a playlist aqui"><span class="emb-play"><i class="fa-solid fa-list-ul"></i></span><span class="emb-selo"><i class="fa-brands fa-youtube"></i> Playlist do YouTube</span></button></div>` };
        }
        // Spotify
        if (h === 'open.spotify.com') {
            const m = /^\/(?:intl-[a-z-]+\/)?(track|album|playlist|episode|show|artist)\/([A-Za-z0-9]{22})/.exec(p);
            if (m) return { chave: 'sp:' + m[2], html: `<div class="emb emb-sp" data-emb="sp" data-tipo="${m[1]}" data-id="${m[2]}">`
                + `<button type="button" class="emb-capa sem-img baixo" aria-label="Ouvir aqui no chat"><span class="emb-play"><i class="fa-brands fa-spotify"></i></span><span class="emb-selo">Spotify · ${({ track: 'música', album: 'álbum', playlist: 'playlist', episode: 'episódio', show: 'podcast', artist: 'artista' })[m[1]]} · ouvir aqui</span></button></div>` };
        }
        // SoundCloud
        if (h === 'soundcloud.com' && /^\/[\w-]+\/[\w-]+/.test(p) && !/^\/(you|discover|stream|search|upload|pages|settings)\b/.test(p)) {
            return { chave: 'sc:' + h + p, html: `<div class="emb emb-sc" data-emb="sc" data-url="${esc('https://soundcloud.com' + p)}">`
                + `<button type="button" class="emb-capa sem-img baixo" aria-label="Ouvir aqui no chat"><span class="emb-play"><i class="fa-brands fa-soundcloud"></i></span><span class="emb-selo">SoundCloud · ouvir aqui</span></button></div>` };
        }
        // arquivo de áudio / vídeo direto (nada baixa até apertar play)
        if (u.protocol === 'https:' && /\.(mp3|ogg|oga|opus|wav|m4a|aac|flac|weba)$/i.test(p)) {
            const nome = decodeURIComponent(p.split('/').pop() || 'áudio').slice(0, 60);
            return { chave: 'au:' + u.href, html: `<div class="emb emb-au"><i class="fa-solid fa-music"></i><div class="emb-au-corpo"><span class="emb-au-nome">${esc(nome)}</span>`
                + `<audio controls preload="none" src="${esc(u.href)}"></audio></div></div>` };
        }
        if (u.protocol === 'https:' && /\.(mp4|webm|m4v|mov|ogv)$/i.test(p)) {
            return { chave: 'vi:' + u.href, html: `<div class="emb emb-vi"><video controls preload="none" playsinline src="${esc(u.href)}"></video></div>` };
        }
        return null;
    }

    // ---------------------------------------------------------------------
    // menções
    // ---------------------------------------------------------------------
    const ESP = {
        todos: ['@todos', 'Chamou todo mundo que enxerga este canal', 'fa-users'],
        aqui: ['@aqui', 'Chamou quem está online agora', 'fa-circle-dot'],
        staff: ['@staff', 'Chamou a moderação do servidor', 'fa-shield-halved'],
        dono: ['@dono', 'Chamou o dono do servidor', 'fa-crown'],
        amigos: ['@amigos', 'Chamou os amigos de quem escreveu', 'fa-user-group'],
        alguem: ['@alguém', 'Alguém sorteado', 'fa-dice'],
    };
    function mencaoHtml(tok, ctx) {
        const m = /^(&?)(\d{1,10}|todos|aqui|staff|dono|alguem|amigos)$/.exec(tok);
        if (!m) return esc('<@' + tok + '>');
        if (m[1]) {                                     // cargo
            const c = (ctx.cargos ? ctx.cargos() : []).find(x => Number(x.id) === Number(m[2]));
            const cor = c && /^#[0-9a-fA-F]{6}$/.test(c.cor || '') ? c.cor : '#99aab5';
            const meu = c && (ctx.meusCargos || []).map(Number).includes(Number(c.id));
            return `<span class="mencao cargo ${meu ? 'mencao-eu' : ''}" style="--c:${cor}" title="Cargo">${c && c.icone ? esc(c.icone) + ' ' : ''}@${esc(c ? c.nome : 'cargo')}</span>`;
        }
        if (/^\d+$/.test(m[2])) {
            const p = (ctx.membros ? ctx.membros() : []).find(x => Number(x.id) === Number(m[2]));
            const eu = Number(m[2]) === Number(ctx.meuId);
            return `<span class="mencao ${eu ? 'mencao-eu' : ''}" data-perfil-id="${Number(m[2])}">@${esc(p ? p.nome : 'usuário')}</span>`;
        }
        const e = ESP[m[2]];
        const pra_mim = m[2] === 'todos' || m[2] === 'aqui' || (m[2] === 'dono' && ctx.souDono) || (m[2] === 'staff' && ctx.podeGerir);
        return `<span class="mencao esp esp-${m[2]} ${pra_mim ? 'mencao-eu' : ''}" title="${esc(e[1])}"><i class="fa-solid ${e[2]}"></i>${esc(e[0])}</span>`;
    }

    // ---------------------------------------------------------------------
    // o renderizador
    // ---------------------------------------------------------------------
    function render(texto, ctx) {
        ctx = ctx || C;
        const g = [];
        const guarda = (html) => { g.push(html); return A + (g.length - 1) + B; };
        const volta = (s) => { for (let n = 0; n < 6 && s.indexOf(A) >= 0; n++) s = s.replace(RE_MARC, (_, i) => g[Number(i)] || ''); return s; };
        const embeds = [], chaves = new Set();
        const querPrevia = ctx.previas !== false;
        const junta = (u) => {
            if (!querPrevia || embeds.length >= MAX_EMBEDS) return;
            const e = embedDe(u); if (!e || chaves.has(e.chave)) return;
            chaves.add(e.chave); embeds.push(e.html);
        };

        let s = String(texto == null ? '' : texto).replace(RE_CTRL, '').replace(/\r\n?/g, '\n');
        // 1) blocos de código e código em linha (nada de formatação lá dentro)
        s = s.replace(/```(?:([A-Za-z0-9_+#.-]{1,20})[ \t]*\n)?([\s\S]*?)```/g, (_, lang, cod) => guarda(blocoCodigo(lang, cod)));
        s = s.replace(/``([^\n]+?)``/g, (_, c) => guarda(`<code class="cod-i">${esc(c.trim())}</code>`));
        s = s.replace(/`([^`\n]+)`/g, (_, c) => guarda(`<code class="cod-i">${esc(c)}</code>`));
        // 2) \* e companhia: o símbolo vira texto
        s = s.replace(/\\([\\*_~|`>#\[\]()@=:-])/g, (_, c) => guarda(esc(c)));
        // 3) menções
        s = s.replace(/<@(&?\d{1,10}|todos|aqui|staff|dono|alguem|amigos)>/g, (_, tok) => guarda(mencaoHtml(tok, ctx)));
        // 4) [texto](url)
        s = s.replace(/\[([^\]\n]{1,100})\]\((https?:\/\/[^\s)\u0001\u0002]{1,500})\)/gi, (m, rotulo, url) => {
            const u = urlSegura(url); if (!u) return m;
            const pareceUrl = /^(https?:\/\/|www\.)|^[\w-]+(\.[\w-]+)+(\/|$)/i.test(rotulo.trim());
            let mascarado = false, mostrar = esc(rotulo);
            if (pareceUrl) {                        // o texto parece um endereço: mostra o destino de verdade (anti-golpe do "banco.com" que leva a outro lugar)
                const alvo = urlSegura(/^https?:/i.test(rotulo.trim()) ? rotulo.trim() : 'https://' + rotulo.trim());
                if (!alvo || alvo.hostname.replace(/^www\./, '') !== u.hostname.replace(/^www\./, '')) { mostrar = esc(encurtar(u.href)); mascarado = true; }
            } else mascarado = true;
            junta(u);
            return guarda(linkHtml(u, mostrar, mascarado));
        });
        // 5) links soltos
        s = s.replace(/(^|[\s(])(https?:\/\/[^\s<>\u0001\u0002]+)/gi, (m, pre, url) => {
            const limpo = limparFim(url), resto = url.slice(limpo.length);
            const u = urlSegura(limpo); if (!u) return m;
            junta(u);
            return pre + guarda(linkHtml(u, esc(encurtar(limpo)), false)) + resto;
        });

        // 6) blocos por linha: título, citação, lista...
        const linhas = s.split('\n'), saida = [];
        let par = [], quote = null, lista = null;
        const fechaPar = () => { if (par.length) { saida.push(par.join('<br>')); par = []; } };
        const fechaQuote = () => { if (quote) { saida.push(`<blockquote class="rt-q">${quote.map(inline).join('<br>')}</blockquote>`); quote = null; } };
        const fechaLista = () => { if (lista) { const tag = lista.ord ? 'ol' : 'ul'; saida.push(`<${tag} class="rt-l">${lista.itens.map(i => `<li>${inline(i)}</li>`).join('')}</${tag}>`); lista = null; } };
        const fechaTudo = () => { fechaPar(); fechaQuote(); fechaLista(); };
        let aposQuote3 = false;
        for (let i = 0; i < linhas.length; i++) {
            const l = linhas[i];
            let m;
            if (aposQuote3) { quote.push(l); continue; }
            if ((m = /^>>>\s?(.*)$/.exec(l))) { fechaPar(); fechaLista(); quote = quote || []; quote.push(m[1]); aposQuote3 = true; continue; }
            if ((m = /^>\s?(.*)$/.exec(l))) { fechaPar(); fechaLista(); quote = quote || []; quote.push(m[1]); continue; }
            fechaQuote();
            if ((m = /^(#{1,3})[ \t]+(.+)$/.exec(l))) { fechaPar(); fechaLista(); saida.push(`<div class="rt-h rt-h${m[1].length}" role="heading" aria-level="${m[1].length}">${inline(m[2])}</div>`); continue; }
            if ((m = /^-#[ \t]+(.+)$/.exec(l))) { fechaPar(); fechaLista(); saida.push(`<div class="rt-sub">${inline(m[1])}</div>`); continue; }
            if ((m = /^[ \t]*[-*•][ \t]+(.+)$/.exec(l))) { fechaPar(); if (!lista || lista.ord) { fechaLista(); lista = { ord: false, itens: [] }; } lista.itens.push(m[1]); continue; }
            if ((m = /^[ \t]*(\d{1,3})[.)][ \t]+(.+)$/.exec(l))) { fechaPar(); if (!lista || !lista.ord) { fechaLista(); lista = { ord: true, itens: [] }; } lista.itens.push(m[2]); continue; }
            fechaLista();
            if (/^\u0001\d+\u0002$/.test(l.trim()) && /class="cod"/.test(g[Number(l.trim().slice(1, -1))] || '')) { fechaPar(); saida.push(l.trim()); continue; }   // bloco de código sozinho na linha
            par.push(inline(l));
        }
        fechaTudo();
        let html = saida.join('');
        html = html.replace(/^(<br>)+|(<br>)+$/g, '');
        if (embeds.length) html += `<div class="rt-embeds">${embeds.join('')}</div>`;
        return volta(html);
    }

    /** Formatação em linha (o texto ainda tem os marcadores \u0001n\u0002 dos pedaços protegidos). */
    function inline(t) {
        t = esc(t);
        t = t.replace(/\|\|(?=\S)([\s\S]+?)\|\|/g, '<span class="spoiler" tabindex="0" role="button" aria-label="Spoiler: toque para mostrar">$1</span>');
        t = t.replace(/\*\*\*(?=\S)([\s\S]+?)\*\*\*/g, '<strong><em>$1</em></strong>');
        t = t.replace(/\*\*(?=\S)([\s\S]+?)\*\*/g, '<strong>$1</strong>');
        t = t.replace(/__(?=\S)([\s\S]+?)__/g, '<u>$1</u>');
        t = t.replace(/(^|[^*\w])\*([^*\s](?:[^*]*?[^*\s])?)\*(?!\*)/g, '$1<em>$2</em>');
        t = t.replace(/(^|[^_\w])_([^_\s](?:[^_]*?[^_\s])?)_(?![_\w])/g, '$1<em>$2</em>');
        t = t.replace(/~~(?=\S)([\s\S]+?)~~/g, '<s>$1</s>');
        t = t.replace(/==(?=\S)([\s\S]+?)==/g, '<mark class="rt-mark">$1</mark>');
        return t;
    }

    // ---------------------------------------------------------------------
    // autocompletar @ (pessoas, cargos e as menções especiais)
    // ---------------------------------------------------------------------
    const ESPECIAIS_LISTA = [
        { id: 'todos', rotulo: 'todos', apelidos: ['everyone', 'all', 'todomundo'], desc: 'Avisa todo mundo que enxerga este canal', icone: 'fa-users', exige: true },
        { id: 'aqui', rotulo: 'aqui', apelidos: ['here', 'online'], desc: 'Avisa só quem está online agora', icone: 'fa-circle-dot', exige: true },
        { id: 'staff', rotulo: 'staff', apelidos: ['admins', 'mods', 'moderacao'], desc: 'Chama a moderação (1 vez a cada 2 min)', icone: 'fa-shield-halved' },
        { id: 'dono', rotulo: 'dono', apelidos: ['owner'], desc: 'Chama o dono do servidor', icone: 'fa-crown' },
        { id: 'amigos', rotulo: 'amigos', apelidos: ['friends'], desc: 'Avisa só os seus amigos que estão aqui', icone: 'fa-user-group' },
        { id: 'alguem', rotulo: 'alguem', apelidos: ['random', 'qualquer', 'sorteio'], desc: 'Sorteia uma pessoa online e marca', icone: 'fa-dice' },
    ];
    const semAcento = (v) => String(v || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    /** Itens do menu do @. `ctx`: { membros(), cargos(), meuId, podeMencionarTodos, emServidor }. Cada item traz o TOKEN que vai pro texto. */
    function sugestoes(termo, ctx) {
        const t = semAcento(termo);
        const out = [];
        if (ctx.emServidor !== false) {
            ESPECIAIS_LISTA.forEach(e => {
                if (e.exige && !ctx.podeMencionarTodos) return;
                if (!t || [e.rotulo, ...e.apelidos].some(a => a.startsWith(t))) out.push({ tipo: 'esp', id: e.id, nome: e.rotulo, desc: e.desc, icone: e.icone, token: `<@${e.id}>` });
            });
            if (ctx.podeMencionarTodos) (ctx.cargos ? ctx.cargos() : []).forEach(c => {
                if (!t || semAcento(c.nome).includes(t)) out.push({ tipo: 'cargo', id: c.id, nome: c.nome, cor: /^#[0-9a-fA-F]{6}$/.test(c.cor || '') ? c.cor : '#99aab5', desc: 'Cargo', token: `<@&${Number(c.id)}>` });
            });
        }
        (ctx.membros ? ctx.membros() : [])
            .filter(m => Number(m.id) !== Number(ctx.meuId) && (!t || semAcento(m.nome).includes(t) || (m.username || '').includes(t)))
            .sort((a, b) => (b.online ? 1 : 0) - (a.online ? 1 : 0))
            .slice(0, 6)
            .forEach(m => out.push({ tipo: 'pessoa', id: m.id, nome: m.nome, avatar: m.avatar, username: m.username, estilo: m.nome_estilo, token: `<@${Number(m.id)}>` }));
        return out.slice(0, 9);
    }
    /** Converte o que a pessoa digitou à mão (@todos, @everyone, @aqui, @NomeDoCargo...) em tokens. O servidor confere permissão de qualquer jeito. */
    function digitadoParaTokens(texto, ctx) {
        let out = texto;
        ESPECIAIS_LISTA.forEach(e => {
            [e.rotulo, ...e.apelidos].forEach(a => {
                out = out.replace(new RegExp('(^|\\s)@' + a + '(?![\\p{L}\\p{N}_])', 'giu'), `$1<@${e.id}>`);
            });
        });
        (ctx.cargos ? ctx.cargos() : []).slice().sort((x, y) => y.nome.length - x.nome.length).forEach(c => {
            out = out.replace(new RegExp('(^|\\s)@' + c.nome.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?![\\p{L}\\p{N}_])', 'giu'), `$1<@&${Number(c.id)}>`);
        });
        return out;
    }
    /** Contrário (pra editar a mensagem): tokens especiais voltam a ser @palavra. */
    function tokensParaDigitado(texto, ctx) {
        return String(texto || '').replace(/<@(&?)(\d{1,10}|todos|aqui|staff|dono|alguem|amigos)>/g, (tok, r, v) => {
            if (r) { const c = (ctx.cargos ? ctx.cargos() : []).find(x => Number(x.id) === Number(v)); return c ? '@' + c.nome : tok; }
            if (/^\d+$/.test(v)) return tok;           // pessoa: o chat.html converte (precisa lembrar o id)
            return '@' + (ESP[v] ? ESP[v][0].slice(1) : v);
        });
    }

    // ---------------------------------------------------------------------
    // atalhos de teclado no campo (Ctrl+B negrito, Ctrl+I itálico, Ctrl+U sublinhado, Ctrl+Shift+X riscado, Ctrl+E código)
    // ---------------------------------------------------------------------
    function embrulhar(campo, a, b) {
        const ini = campo.selectionStart, fim = campo.selectionEnd, v = campo.value;
        const sel = v.slice(ini, fim);
        campo.value = v.slice(0, ini) + a + sel + b + v.slice(fim);
        const pos = sel ? ini + a.length + sel.length + b.length : ini + a.length;
        campo.setSelectionRange(pos, pos);
        campo.dispatchEvent(new Event('input', { bubbles: true }));
    }
    function ligarAtalhos(campo) {
        if (!campo || campo.dataset.trAtalhos) return;
        campo.dataset.trAtalhos = '1';
        campo.addEventListener('keydown', (e) => {
            if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
            const k = e.key.toLowerCase();
            if (k === 'b' && !e.shiftKey) { e.preventDefault(); embrulhar(campo, '**', '**'); }
            else if (k === 'i' && !e.shiftKey) { e.preventDefault(); embrulhar(campo, '*', '*'); }
            else if (k === 'u' && !e.shiftKey) { e.preventDefault(); embrulhar(campo, '__', '__'); }
            else if (k === 'x' && e.shiftKey) { e.preventDefault(); embrulhar(campo, '~~', '~~'); }
            else if (k === 'e' && !e.shiftKey) { e.preventDefault(); embrulhar(campo, '`', '`'); }
        });
    }

    // ---------------------------------------------------------------------
    // cliques (um ouvinte só no documento: vale pra mensagem desenhada depois)
    // ---------------------------------------------------------------------
    function copiar(texto) {
        if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(texto);
        const ta = document.createElement('textarea'); ta.value = texto; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); } catch (e) {} ta.remove();
        return Promise.resolve();
    }
    function carregarEmbed(host) {
        const tipo = host.dataset.emb;
        let src = '', alt = 200, extra = '';
        if (tipo === 'yt') {
            const id = host.dataset.id, lista = host.dataset.lista, t = Number(host.dataset.t) || 0;
            if (id && /^[\w-]{11}$/.test(id)) src = `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0${t ? '&start=' + t : ''}${lista && /^[\w-]{10,64}$/.test(lista) ? '&list=' + encodeURIComponent(lista) : ''}`;
            else if (lista && /^[\w-]{10,64}$/.test(lista)) src = `https://www.youtube-nocookie.com/embed/videoseries?list=${encodeURIComponent(lista)}&autoplay=1`;
            alt = 0; extra = 'aspect-ratio:16/9;';
        } else if (tipo === 'sp') {
            const t = host.dataset.tipo, id = host.dataset.id;
            if (/^(track|album|playlist|episode|show|artist)$/.test(t) && /^[A-Za-z0-9]{22}$/.test(id)) { src = `https://open.spotify.com/embed/${t}/${id}?theme=0`; alt = (t === 'track' || t === 'episode') ? 152 : 352; }
        } else if (tipo === 'sc') {
            const u = host.dataset.url;
            if (/^https:\/\/soundcloud\.com\/[\w-]+\/[\w-]+/.test(u || '')) { src = `https://w.soundcloud.com/player/?url=${encodeURIComponent(u)}&auto_play=true&visual=false`; alt = 166; }
        }
        if (!src) return;
        const f = document.createElement('iframe');
        f.src = src; f.loading = 'lazy'; f.allow = 'autoplay; encrypted-media; fullscreen; picture-in-picture; clipboard-write';
        f.setAttribute('allowfullscreen', ''); f.referrerPolicy = 'strict-origin-when-cross-origin';
        f.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation allow-popups allow-popups-to-escape-sandbox');
        f.title = 'Prévia incorporada'; f.className = 'emb-iframe';
        f.style.cssText = `width:100%;border:0;border-radius:10px;${alt ? 'height:' + alt + 'px;' : ''}${extra}`;
        host.innerHTML = ''; host.appendChild(f); host.classList.add('aberto');
    }
    function iniciar(ctx) {
        C = ctx || {};
        document.addEventListener('click', (e) => {
            const sp = e.target.closest('.spoiler');
            if (sp) { sp.classList.toggle('aberto'); return; }
            const cp = e.target.closest('.cod-copiar');
            if (cp) {
                const cod = cp.closest('.cod'); if (!cod) return;
                copiar(cod.querySelector('code').textContent).then(() => {
                    const rot = cp.querySelector('span'); if (!rot) return;
                    rot.textContent = 'Copiado!'; cp.classList.add('ok');
                    setTimeout(() => { rot.textContent = 'Copiar'; cp.classList.remove('ok'); }, 1500);
                });
                return;
            }
            const cap = e.target.closest('.emb .emb-capa');
            if (cap) { const host = cap.closest('.emb'); if (host) carregarEmbed(host); return; }
            const a = e.target.closest('a.lnk');
            if (a && a.dataset.aviso === '1' && C.confirmarLink) {            // só link "suspeito" pergunta (mascarado, IP, http puro, punycode)
                e.preventDefault();
                C.confirmarLink(a.href, a.dataset.host, () => window.open(a.href, '_blank', 'noopener,noreferrer'));
            }
        });
        document.addEventListener('keydown', (e) => {
            if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('spoiler')) { e.preventDefault(); e.target.classList.toggle('aberto'); }
        });
    }

    return { iniciar, render, sugestoes, digitadoParaTokens, tokensParaDigitado, ligarAtalhos, colorir, _embedDe: embedDe, _esc: esc };
})();
