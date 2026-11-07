/* Pantheon Estúdio (/estudio): a página de CRIAÇÃO de conteúdo. Fala com /estudio/api/* (JSON). Nada aqui é de confiança: o servidor confere
   admin e valida tudo (receita, arquivo, tipo, tamanho). Hoje: Efeitos (camadas por parâmetro + camada "Arquivo": Lottie, GIF, WebP, APNG, MP4, WebM)
   e a Biblioteca de arquivos. O motor que desenha é o js/efeitos.js (o mesmo que roda no app). */
(function () {
    'use strict';
    const $ = (s, r) => (r || document).querySelector(s);
    const main = $('#es-main');
    const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const kb = (n) => (n >= 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB');

    function toast(msg, tipo) {
        const el = document.createElement('div');
        el.className = 'es-toast ' + (tipo || '');
        el.textContent = msg;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 4200);
    }

    async function api(caminho, metodo, corpo) {
        const opt = { method: metodo || 'GET', headers: { 'X-Requested-With': 'fetch' } };
        if (corpo instanceof FormData) opt.body = corpo;
        else if (corpo !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(corpo); }
        let r;
        try { r = await fetch('/estudio/api' + caminho, opt); } catch (e) { toast('Sem conexão com o servidor.', 'erro'); e.avisado = true; throw e; }
        const d = await r.json().catch(() => ({}));
        if (!r.ok) { toast(d.erro || ('Erro ' + r.status), 'erro'); const err = new Error(d.erro || r.status); err.avisado = true; throw err; }
        return d;
    }

    function dialogo(titulo, corpoHtml, acoes, largo) {
        const fundo = document.createElement('div');
        fundo.className = 'es-modal-fundo';
        fundo.innerHTML = `<div class="es-modal ${largo ? 'es-modal-largo' : ''}" role="dialog" aria-modal="true"><h3>${esc(titulo)}</h3><div class="es-corpo">${corpoHtml}</div><div class="es-modal-acoes"></div></div>`;
        const barra = $('.es-modal-acoes', fundo);
        const fechar = () => { fundo.remove(); document.removeEventListener('keydown', tecla); };
        const tecla = (e) => { if (e.key === 'Escape') fechar(); };
        document.addEventListener('keydown', tecla);
        fundo.addEventListener('mousedown', (e) => { if (e.target === fundo) fechar(); });
        (acoes || []).forEach((a) => {
            const b = document.createElement('button');
            b.className = 'es-btn ' + (a.classe || '');
            b.textContent = a.texto;
            b.addEventListener('click', async () => {
                if (b.disabled) return;
                if (a.fn) {
                    const botoes = [...barra.querySelectorAll('button')], rotulo = b.textContent;
                    botoes.forEach((x) => { x.disabled = true; });
                    b.textContent = 'Aguarde...';
                    let r;
                    try { r = await a.fn(fundo); } catch (e) { r = false; }
                    if (r === false) { botoes.forEach((x) => { x.disabled = false; }); b.textContent = rotulo; return; }
                }
                fechar();
            });
            barra.appendChild(b);
        });
        document.body.appendChild(fundo);
        return { fundo, fechar };
    }

    const confirmar = (texto, aoConfirmar, rotulo) => dialogo('Confirmar', `<p>${esc(texto)}</p>`, [{ texto: 'Cancelar' }, { texto: rotulo || 'Confirmar', classe: 'perigo', fn: aoConfirmar }]);

    // ------------------------------------------------------------
    // navegação
    // ------------------------------------------------------------
    const VISTAS = {};
    let vistaAtual = null;
    // soltar um arquivo fora de uma zona não pode fazer o navegador abrir o arquivo e sair da página
    ['dragover', 'drop'].forEach((ev) => window.addEventListener(ev, (e) => { if (e.dataTransfer && [...e.dataTransfer.types].includes('Files')) e.preventDefault(); }));
    function ir(v) {
        vistaAtual = v;
        document.querySelectorAll('.es-item[data-v]').forEach((b) => b.classList.toggle('ativo', b.dataset.v === v));
        if (location.hash.slice(1) !== v) location.hash = v;
        main.innerHTML = '<div class="es-vazio">Carregando...</div>';
        Promise.resolve(VISTAS[v] && VISTAS[v]()).catch((e) => { main.innerHTML = `<div class="es-vazio">Não foi possível carregar: ${esc(e.message)}</div>`; });
    }
    document.querySelectorAll('.es-item[data-v]').forEach((b) => b.addEventListener('click', () => ir(b.dataset.v)));

    // ------------------------------------------------------------
    // BIBLIOTECA DE ARQUIVOS (upload por arrastar; o servidor decide o tipo pelo conteúdo)
    // ------------------------------------------------------------
    const BIB = { lista: [], uso: null, limites: null };
    const ACEITA = '.json,.gif,.webp,.png,.apng,.jpg,.jpeg,.mp4,.webm,application/json,image/gif,image/webp,image/png,image/jpeg,video/mp4,video/webm';
    const ROTULO_K = { lottie: 'Lottie', imagem: 'Imagem', video: 'Vídeo' };
    const ICONE_K = { lottie: 'fa-bezier-curve', imagem: 'fa-image', video: 'fa-film' };

    async function carregarBiblioteca() {
        const d = await api('/arquivos');
        BIB.lista = d.arquivos; BIB.uso = d.uso; BIB.limites = d.limites;
        return BIB;
    }

    /** Tira o 1º quadro e mede o vídeo no navegador (o servidor não tem ffmpeg): a capa vai junto no upload. */
    function lerVideo(arquivo) {
        return new Promise((ok, falha) => {
            const url = URL.createObjectURL(arquivo);
            const v = document.createElement('video');
            v.muted = true; v.playsInline = true; v.preload = 'auto';
            let dur = 0;
            const fim = (erro, r) => { clearTimeout(t); URL.revokeObjectURL(url); v.removeAttribute('src'); v.load(); erro ? falha(erro) : ok(r); };
            const t = setTimeout(() => fim(new Error('Demorou demais pra ler o vídeo. Tente outro arquivo.')), 20000);
            v.onerror = () => fim(new Error('O navegador não conseguiu abrir esse vídeo (codec sem suporte). Exporte em MP4 (H.264) ou WebM.'));
            v.onloadedmetadata = () => {
                dur = v.duration;
                if (!isFinite(dur) || dur <= 0) return fim(new Error('Não consegui medir a duração do vídeo.'));
                v.currentTime = Math.min(0.05, dur / 2);
            };
            v.onseeked = () => {
                const w = v.videoWidth, h = v.videoHeight;
                if (!w || !h) return fim(new Error('O vídeo não tem imagem.'));
                const f = Math.min(1, 512 / Math.max(w, h)), c = document.createElement('canvas');
                c.width = Math.max(1, Math.round(w * f)); c.height = Math.max(1, Math.round(h * f));
                c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
                c.toBlob((b) => (b ? fim(null, { w, h, dur: Math.round(dur * 1000), capa: b }) : fim(new Error('Não consegui gerar a capa do vídeo.'))), 'image/webp', 0.85);
            };
            v.src = url;
        });
    }

    async function enviarArquivo(arquivo) {
        const fd = new FormData();
        fd.append('file', arquivo, arquivo.name);
        if (/^video\//.test(arquivo.type) || /\.(mp4|webm)$/i.test(arquivo.name)) {
            const m = await lerVideo(arquivo);
            fd.append('capa', m.capa, 'capa.webp'); fd.append('w', m.w); fd.append('h', m.h); fd.append('dur', m.dur);
        }
        const d = await api('/arquivos', 'POST', fd);
        BIB.uso = d.uso;
        const i = BIB.lista.findIndex((x) => x.id === d.arquivo.id);
        if (i >= 0) BIB.lista.splice(i, 1);
        BIB.lista.unshift(d.arquivo);
        return d.arquivo;
    }

    /** Liga um elemento como zona de soltar (arrastar arquivo) e de clicar pra escolher. `aoArquivos(File[])` roda com o que a pessoa trouxe. */
    function ligarSoltar(alvo, aoArquivos, opcoes) {
        const entrada = document.createElement('input');
        entrada.type = 'file'; entrada.accept = ACEITA; entrada.multiple = !(opcoes && opcoes.unico); entrada.hidden = true;
        alvo.appendChild(entrada);
        let n = 0;
        alvo.addEventListener('dragenter', (e) => { if (!e.dataTransfer || ![...e.dataTransfer.types].includes('Files')) return; e.preventDefault(); n++; alvo.classList.add('arrastando'); });
        alvo.addEventListener('dragover', (e) => { if (!e.dataTransfer || ![...e.dataTransfer.types].includes('Files')) return; e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; });
        alvo.addEventListener('dragleave', () => { n = Math.max(0, n - 1); if (!n) alvo.classList.remove('arrastando'); });
        alvo.addEventListener('drop', (e) => {
            if (!e.dataTransfer || !e.dataTransfer.files.length) return;
            e.preventDefault(); n = 0; alvo.classList.remove('arrastando');
            aoArquivos([...e.dataTransfer.files]);
        });
        if (!(opcoes && opcoes.semClique)) {
            alvo.addEventListener('click', (e) => { if (e.target.closest('button, a, input, select')) return; entrada.click(); });
        }
        entrada.addEventListener('change', () => { const f = [...entrada.files]; entrada.value = ''; if (f.length) aoArquivos(f); });
        return { escolher: () => entrada.click() };
    }

    /** Envia um por vez, mostrando o estado no elemento `estado`. Devolve os arquivos que deram certo. */
    async function enviarVarios(arquivos, estado) {
        const ok = [];
        for (let i = 0; i < arquivos.length; i++) {
            const f = arquivos[i];
            if (estado) estado.textContent = `Enviando ${i + 1}/${arquivos.length}: ${f.name}...`;
            try { ok.push(await enviarArquivo(f)); } catch (e) { if (!(e && e.avisado)) toast((e && e.message) || 'Não consegui enviar o arquivo.', 'erro'); }      // erro do servidor/rede já virou toast no api()
        }
        if (estado) estado.textContent = '';
        return ok;
    }

    const miniatura = (a) => (a.k === 'lottie'
        ? `<span class="es-mini-icone"><i class="fa-solid ${ICONE_K.lottie}"></i></span>`
        : `<img src="${esc(a.k === 'video' ? a.capa : (a.capa || a.url))}" alt="" loading="lazy" draggable="false">`);

    function cartaoArquivo(a, acoes) {
        return `<div class="es-arq" data-id="${esc(a.id)}"><div class="es-arq-img">${miniatura(a)}<span class="es-arq-tipo"><i class="fa-solid ${ICONE_K[a.k] || 'fa-file'}"></i> ${esc(ROTULO_K[a.k] || a.k)}</span></div>
            <div class="es-arq-info"><b title="${esc(a.nome)}">${esc(a.nome || 'sem nome')}</b><small>${kb(a.bytes)}${a.w ? ` · ${a.w}×${a.h}` : ''}${a.dur ? ` · ${(a.dur / 1000).toFixed(1)} s` : ''}</small></div>${acoes || ''}</div>`;
    }

    async function vArquivos() {
        await carregarBiblioteca();
        desenharBiblioteca();
    }

    function desenharBiblioteca() {
        const uso = BIB.uso, lim = BIB.limites;
        main.innerHTML = `<h1>Biblioteca de arquivos</h1><p class="es-sub">A arte feita fora do site (por você ou pela IA): <b>Lottie</b> (.json), <b>GIF</b>, <b>WebP</b>, <b>APNG/PNG</b>, <b>JPEG</b>, <b>MP4</b> e <b>WebM</b>. Arraste pra cá. Depois, num efeito, é só adicionar a camada <b>Arquivo</b> e ajustar tamanho, posição e velocidade. Cada arquivo é guardado uma vez (o mesmo arquivo enviado duas vezes vira um só).</p>
            <div class="es-solta" id="bib-solta"><i class="fa-solid fa-cloud-arrow-up"></i><div><b>Arraste os arquivos aqui</b> ou clique pra escolher<br><small>Lottie até ${kb(lim.lottie)} · imagem até ${kb(lim.imagem)} (lado até ${lim.lado} px) · vídeo até ${kb(lim.video)} · até ${lim.duracao_s} s por passada · fundo transparente: use WebP, APNG ou Lottie</small></div><span class="es-solta-estado" id="bib-estado"></span></div>
            <p class="es-dica" style="margin:8px 2px 14px">Biblioteca: ${uso.qtd} arquivo(s) · ${kb(uso.bytes)} de ${kb(uso.max_bytes)}.</p>
            <div class="es-arqs" id="bib-lista">${BIB.lista.map((a) => cartaoArquivo(a, '<div class="es-arq-acoes"><button class="es-btn mini perigo" data-apagar="' + esc(a.id) + '">Apagar</button></div>')).join('') || '<div class="es-vazio">Nenhum arquivo ainda.</div>'}</div>`;
        ligarSoltar($('#bib-solta'), async (fs) => { await enviarVarios(fs, $('#bib-estado')); desenharBiblioteca(); });
        main.querySelectorAll('[data-apagar]').forEach((b) => b.addEventListener('click', () => {
            const a = BIB.lista.find((x) => x.id === b.dataset.apagar);
            confirmar(`Apagar o arquivo "${a ? a.nome : ''}" da biblioteca? Se algum efeito usar, o servidor recusa e diz qual.`, async () => {
                try { const d = await api('/arquivos/' + encodeURIComponent(b.dataset.apagar), 'DELETE'); BIB.uso = d.uso; BIB.lista = BIB.lista.filter((x) => x.id !== b.dataset.apagar); toast('Arquivo apagado.', 'ok'); desenharBiblioteca(); } catch (e) { return false; }
            }, 'Apagar');
        }));
    }
    VISTAS.arquivos = vArquivos;

    // ------------------------------------------------------------
    // EFEITOS (receita JSON -> motor js/efeitos.js). O esquema das camadas vem do servidor (a única definição).
    // ------------------------------------------------------------
    const XE = { lista: [], esquema: {}, raridades: [], misturas: [], precos: {}, maxCamadas: 6, atual: null, novo: true, timer: null };
    const PRESETS = {
        efeito_perfil: {
            'Poeira dourada': { pausa: 0, camadas: [{ tipo: 'particulas', cor: '#f2c14e', cor2: '#ffffff', qtd: 22, tam: 5, dur: 6, dir: 'cima', forma: 'circulo', brilho: 70 }, { tipo: 'brilho', cor: '#f2c14e', pos: 'base', forca: 30, dur: 6 }] },
            'Neve': { pausa: 0, camadas: [{ tipo: 'particulas', cor: '#ffffff', cor2: '#bfe3ff', qtd: 30, tam: 5, dur: 9, dir: 'baixo', forma: 'circulo', brilho: 40 }] },
            'Brasas': { pausa: 0, camadas: [{ tipo: 'particulas', cor: '#ff7a1f', cor2: '#ffd23f', qtd: 26, tam: 4, dur: 5, dir: 'cima', forma: 'losango', brilho: 80 }, { tipo: 'brilho', cor: '#ff4d1f', pos: 'base', forca: 40, dur: 4 }] },
            'Tempestade': { pausa: 3, camadas: [{ tipo: 'raios', cor: '#bfe3ff', qtd: 5, dur: 6 }, { tipo: 'brilho', cor: '#7cc4ff', pos: 'topo', forca: 45, dur: 6 }] },
            'Código verde': { pausa: 0, camadas: [{ tipo: 'particulas', cor: '#3dff7a', cor2: '#0f8a3a', qtd: 34, tam: 4, dur: 4, dir: 'baixo', forma: 'quadrado', brilho: 50 }] },
            'Estrelas': { pausa: 6, camadas: [{ tipo: 'particulas', cor: '#fff3b8', cor2: '#d9c8ff', qtd: 14, tam: 7, dur: 7, dir: 'dir', forma: 'estrela', brilho: 80 }] },
        },
        efeito_avatar: {
            'Onda dourada': { pausa: 0, camadas: [{ tipo: 'anel', cor: '#f2c14e', esp: 2, dur: 2.4 }] },
            'Satélites': { pausa: 0, camadas: [{ tipo: 'orbita', cor: '#ffffff', qtd: 3, tam: 4, dur: 4 }] },
            'Aura azul': { pausa: 2, camadas: [{ tipo: 'brilho', cor: '#7cc4ff', pos: 'centro', forca: 60, dur: 3 }, { tipo: 'anel', cor: '#7cc4ff', esp: 2, dur: 3 }] },
            'Brasa viva': { pausa: 0, camadas: [{ tipo: 'brilho', cor: '#ff5a1f', pos: 'centro', forca: 55, dur: 2.2 }, { tipo: 'orbita', cor: '#ffd23f', qtd: 4, tam: 3, dur: 3 }] },
        },
    };

    const novoEfeito = (tipo) => ({ id: '', nome: '', tipo: tipo || 'efeito_perfil', raridade: 'epico', descricao: '', vender: false, receita: { pausa: 0, mistura: 'normal', camadas: [] } });
    const precoVenda = (e) => ((XE.precos[e.raridade] || {})[e.tipo]) || 0;
    const clone = (o) => JSON.parse(JSON.stringify(o));
    const camadaPadrao = (tipo) => { const c = { tipo }; Object.entries(XE.esquema[tipo].params).forEach(([k, p]) => { c[k] = p.padrao; }); return c; };
    /** O que o motor precisa saber do arquivo (os endereços e as medidas) vem da biblioteca. */
    const infoDoArquivo = (a) => ({ id: a.id, k: a.k, url: a.url, capa: a.capa, dur: a.dur, w: a.w, h: a.h, q: a.q });
    const camadaComArquivo = (a) => Object.assign(camadaPadrao('arquivo'), { arq: a.id, a: infoDoArquivo(a) });

    async function vEfeitos() {
        const [d] = await Promise.all([api('/efeitos'), carregarBiblioteca()]);
        XE.lista = d.efeitos; XE.esquema = d.esquema; XE.raridades = d.raridades; XE.maxCamadas = d.max_camadas; XE.misturas = d.misturas; XE.precos = d.precos || {};
        if (!XE.atual) { XE.atual = novoEfeito(); XE.novo = true; }
        desenharEfeitos();
    }
    VISTAS.efeitos = vEfeitos;

    function desenharEfeitos() {
        const lista = XE.lista.map((e) => `<button class="es-ef-item ${!XE.novo && XE.atual && XE.atual.id === e.id ? 'sel' : ''}" data-id="${esc(e.id)}"><b>${esc(e.nome)}</b><small>${e.tipo === 'efeito_perfil' ? 'cartão' : 'avatar'} · ${esc(e.raridade)} · ${esc(e.id)}${e.vender ? ' · <b>à venda</b>' : ''}</small></button>`).join('');
        main.innerHTML = `<h1>Efeitos</h1><p class="es-sub">Crie efeitos de <b>cartão de perfil</b> e de <b>avatar</b>. Monte por camadas (partículas, brilho, raios...) <b>ou arraste um arquivo</b> feito fora do site (Lottie, GIF, WebP, APNG, MP4, WebM) na camada <b>Arquivo</b> e ajuste tamanho, posição e velocidade. Ao salvar, o efeito entra no catálogo: dá pra <b>dar a alguém</b>, usar como <b>recompensa do passe</b> e, depois, vender. Nada de código livre: só valem os controles daqui, por isso é seguro.</p>
            <div class="es-ef-layout"><div class="es-ef-lado"><button class="es-btn primario" id="ef-novo">Novo efeito</button><div class="es-ef-lista">${lista || '<div class="es-vazio">Nenhum efeito ainda.</div>'}</div></div>
            <div class="es-ef-editor" id="ef-editor"></div></div>`;
        $('#ef-novo').addEventListener('click', () => { XE.atual = novoEfeito(); XE.novo = true; desenharEfeitos(); });
        main.querySelectorAll('.es-ef-item').forEach((b) => b.addEventListener('click', () => { const e = XE.lista.find((x) => x.id === b.dataset.id); XE.atual = clone(e); XE.novo = false; desenharEfeitos(); }));
        desenharEditorEfeito();
    }

    function controle(p, valor, i, nome) {
        const id = `c${i}-${nome}`;
        if (p.t === 'num') {
            const amp = p.max - p.min, passo = amp <= 5 ? 0.05 : amp <= 20 ? 0.5 : 1;
            return `<div class="es-campo" data-p="${nome}"><label for="${id}">${esc(p.rotulo)} <b data-v="${id}">${valor}</b></label><input id="${id}" type="range" min="${p.min}" max="${p.max}" step="${passo}" value="${valor}" data-i="${i}" data-p="${nome}" data-t="num"></div>`;
        }
        if (p.t === 'cor') return `<div class="es-campo" data-p="${nome}"><label for="${id}">${esc(p.rotulo)}</label><input id="${id}" type="color" value="${esc(valor)}" data-i="${i}" data-p="${nome}" data-t="cor"></div>`;
        return `<div class="es-campo" data-p="${nome}"><label for="${id}">${esc(p.rotulo)}</label><select id="${id}" data-i="${i}" data-p="${nome}" data-t="opcao">${p.opcoes.map((o) => `<option ${o === valor ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select></div>`;
    }

    /** Quais controles da camada "Arquivo" fazem sentido: imagem parada/animada não muda de velocidade nem se apara; "lugar" só vale em avatar. */
    function controlesVisiveis(c, nome, e) {
        if (c.tipo !== 'arquivo') return true;
        const k = c.a && c.a.k;
        if (nome === 'arq') return false;
        if (nome === 'lugar') return e.tipo === 'efeito_avatar';
        if (nome === 'vel' || nome === 'ini' || nome === 'fim') return k === 'lottie' || k === 'video';
        return true;
    }

    function blocoArquivo(c, i) {
        const a = BIB.lista.find((x) => x.id === c.arq) || (c.a ? Object.assign({ nome: '(arquivo)', bytes: 0 }, c.a) : null);
        if (!a) return `<div class="es-arq-zona es-solta pequeno" data-i="${i}"><i class="fa-solid fa-cloud-arrow-up"></i><div><b>Arraste um arquivo aqui</b> ou clique pra escolher<br><small>Lottie, GIF, WebP, APNG, PNG, JPEG, MP4 ou WebM</small></div><button class="es-btn mini" data-biblioteca="${i}">Usar da biblioteca</button><span class="es-solta-estado"></span></div>`;
        const aviso = c.a && c.a.k === 'imagem' && !c.a.dur ? '<small class="es-dica">Imagem parada (sem animação).</small>' : '';
        return `<div class="es-arq-zona escolhido" data-i="${i}"><div class="es-arq-mini">${miniatura(a)}</div><div class="es-arq-tx"><b>${esc(a.nome || 'sem nome')}</b><small>${esc(ROTULO_K[a.k] || '')}${a.w ? ` · ${a.w}×${a.h}` : ''}${a.dur ? ` · ${(a.dur / 1000).toFixed(1)} s` : ''}</small>${aviso}</div>
            <button class="es-btn mini" data-trocar="${i}">Trocar</button><span class="es-solta-estado"></span></div>`;
    }

    function desenharEditorEfeito() {
        const e = XE.atual, alvo = $('#ef-editor');
        if (!alvo) return;
        const tipos = Object.keys(XE.esquema).filter((t) => XE.esquema[t].slots.includes(e.tipo));
        const presets = Object.keys(PRESETS[e.tipo] || {}).map((n) => `<option>${esc(n)}</option>`).join('');
        const camadas = e.receita.camadas.map((c, i) => `<div class="es-camada"><div class="es-camada-cab"><b>${esc(XE.esquema[c.tipo].nome)}</b><span class="es-dica">${esc(XE.esquema[c.tipo].dica)}</span>
            <span class="es-camada-acoes"><button class="es-btn mini" data-a="sobe" data-i="${i}" title="Subir">↑</button><button class="es-btn mini" data-a="desce" data-i="${i}" title="Descer">↓</button><button class="es-btn mini perigo" data-a="tira" data-i="${i}">Remover</button></span></div>
            ${c.tipo === 'arquivo' ? blocoArquivo(c, i) : ''}
            <div class="es-camada-corpo">${Object.entries(XE.esquema[c.tipo].params).filter(([k, p]) => p.t !== 'arquivo' && controlesVisiveis(c, k, e)).map(([k, p]) => controle(p, c[k], i, k)).join('')}</div></div>`).join('');
        const temArquivo = e.receita.camadas.some((c) => c.tipo === 'arquivo');
        alvo.innerHTML = `<div class="es-cartao"><h2>${XE.novo ? 'Novo efeito' : 'Editando: ' + esc(e.nome)}</h2>
            <div class="es-linha"><div class="es-campo largo"><label>Nome (2 a 40)</label><input id="ef-nome" maxlength="40" value="${esc(e.nome)}"></div>
                <div class="es-campo"><label>Id (letras minúsculas e _)</label><input id="ef-id" maxlength="24" value="${esc(e.id)}" ${XE.novo ? '' : 'disabled'}></div></div>
            <div class="es-linha" style="margin-top:12px"><div class="es-campo"><label>Onde aparece</label><select id="ef-tipo" ${XE.novo ? '' : 'disabled'}><option value="efeito_perfil" ${e.tipo === 'efeito_perfil' ? 'selected' : ''}>Cartão de perfil</option><option value="efeito_avatar" ${e.tipo === 'efeito_avatar' ? 'selected' : ''}>Avatar</option></select></div>
                <div class="es-campo"><label>Raridade</label><select id="ef-rar">${XE.raridades.map((r) => `<option ${r === e.raridade ? 'selected' : ''}>${r}</option>`).join('')}</select></div>
                <div class="es-campo largo"><label>Descrição (aparece pra quem ganhar)</label><input id="ef-desc" maxlength="120" value="${esc(e.descricao)}"></div></div>
            <label class="es-check" style="margin-top:12px"><input type="checkbox" id="ef-vender" ${e.vender ? 'checked' : ''}><span>Vender avulso no Armazém por <b data-v="ef-preco">${precoVenda(e)}</b> DRC <span class="es-dica">(o preço vem da tabela pela raridade e pelo tipo; ele aparece na vitrine no tema "Estúdio". Desmarcado, o efeito só se dá, entra em pacote ou vira recompensa do passe.)</span></span></label></div>
            <div class="es-ef-colunas"><div>
                <div class="es-cartao" id="ef-camadas-cartao"><h2>Camadas</h2><div class="es-linha"><div class="es-campo"><label>Começar de um modelo</label><select id="ef-preset"><option value="">(escolher)</option>${presets}</select></div>
                    <div class="es-campo"><label>Adicionar camada</label><select id="ef-add"><option value="">(escolher)</option>${tipos.map((t) => `<option value="${t}">${esc(XE.esquema[t].nome)}</option>`).join('')}</select></div></div>
                    <div class="es-campo" style="margin-top:12px"><label for="ef-pausa">Pausa entre uma passada e outra <b data-v="ef-pausa">${e.receita.pausa}</b> s</label><input id="ef-pausa" type="range" min="0" max="15" step="0.5" value="${e.receita.pausa}"><small>0 = sem parar. Com pausa, a cena toca e fica parada um tempo antes de recomeçar.</small></div>
                    <div class="es-campo" style="margin-top:12px"><label for="ef-mistura">Mistura com o fundo (o efeito inteiro)</label><select id="ef-mistura">${XE.misturas.map((m) => `<option ${m === (e.receita.mistura || 'normal') ? 'selected' : ''}>${m}</option>`).join('')}</select><small>"tela" e "somar" deixam o fundo PRETO de um vídeo sumir e só a luz aparecer. Funciona sobre o cartão e por cima da foto.</small></div>
                    <div class="es-camadas">${camadas || '<div class="es-vazio">Sem camadas. Escolha um modelo, adicione uma camada ou <b>arraste um arquivo</b> aqui.</div>'}</div>
                    ${temArquivo ? '' : '<div class="es-solta pequeno" id="ef-solta-novo"><i class="fa-solid fa-cloud-arrow-up"></i><div><b>Arraste um arquivo aqui</b> pra criar a camada Arquivo<br><small>Lottie, GIF, WebP, APNG, PNG, JPEG, MP4 ou WebM</small></div><span class="es-solta-estado"></span></div>'}</div></div>
                <div><div class="es-cartao es-prev-caixa"><h2>Prévia ao vivo</h2>
                    <div class="es-prev-cartao"><div class="es-prev-faixa"></div><div class="es-prev-av"><span class="es-prev-img">A</span><i class="ef-av ef-av-custom" id="pv-av" data-pv="1"></i><i class="ef-av-sobre ef-av-custom" id="pv-av2" data-parte="sobre" data-pv="1"></i></div><div class="es-prev-nome">Seu nome</div><div class="es-prev-sub">@voce</div><div class="ef-pf ef-pf-custom" id="pv-pf" data-pv="1"></div></div>
                    <div class="es-linha" style="margin-top:12px"><button class="es-btn primario" id="ef-salvar">${XE.novo ? 'Criar efeito' : 'Salvar alterações'}</button>
                        ${XE.novo ? '' : '<button class="es-btn" id="ef-mim">Dar a mim</button><button class="es-btn" id="ef-dar">Dar a alguém</button><button class="es-btn" id="ef-dup">Duplicar</button><button class="es-btn perigo" id="ef-apagar">Apagar</button>'}</div>
                    ${XE.novo ? '' : `<p class="es-dica" style="margin-top:10px">Item no catálogo: <code>${esc(e.tipo + ':' + e.id)}</code>. No Passe de Batalha (painel do admin), escolha "Item" e procure por ele.</p>`}</div></div></div>`;
        ligarEditorEfeito();
        pintarPrevia();
    }

    function pintarPrevia() {
        const e = XE.atual;
        const alvos = { pf: $('#pv-pf'), av: $('#pv-av'), av2: $('#pv-av2') };
        Object.values(alvos).forEach((x) => { if (x) Efeitos.previa(x, { pausa: 0, camadas: [] }, 'limpo'); });     // zera as três (solta vídeo/animação que estava tocando)
        if (e.tipo === 'efeito_perfil') { if (alvos.pf) Efeitos.previa(alvos.pf, e.receita, e.id || 'previa'); return; }
        if (alvos.av) Efeitos.previa(alvos.av, e.receita, e.id || 'previa');
        if (alvos.av2) Efeitos.previa(alvos.av2, e.receita, e.id || 'previa');
    }

    function agendarPrevia() { clearTimeout(XE.timer); XE.timer = setTimeout(pintarPrevia, 140); }

    async function usarArquivosNaCamada(arquivos, camada, estado) {
        const ok = await enviarVarios(arquivos.slice(0, 1), estado);
        if (!ok.length) return;
        Object.assign(camada, { arq: ok[0].id, a: infoDoArquivo(ok[0]) });
        toast('Arquivo pronto.', 'ok');
        desenharEditorEfeito();
    }

    function abrirBiblioteca(aoEscolher) {
        const d = dialogo('Biblioteca de arquivos', `<div class="es-arqs es-arqs-escolher" id="bi-lista">${BIB.lista.map((a) => `<button class="es-arq-pick" data-id="${esc(a.id)}">${cartaoArquivo(a)}</button>`).join('') || '<div class="es-vazio">A biblioteca está vazia. Arraste um arquivo na camada.</div>'}</div>`, [{ texto: 'Fechar' }], true);
        d.fundo.querySelectorAll('.es-arq-pick').forEach((b) => b.addEventListener('click', () => { const a = BIB.lista.find((x) => x.id === b.dataset.id); if (a) { aoEscolher(a); d.fechar(); } }));
    }

    function ligarEditorEfeito() {
        const e = XE.atual, alvo = $('#ef-editor');
        $('#ef-nome').addEventListener('input', (x) => { e.nome = x.target.value; });
        if (XE.novo) {
            $('#ef-id').addEventListener('input', (x) => { e.id = x.target.value; });
            $('#ef-nome').addEventListener('input', () => { const idc = $('#ef-id'); if (!idc.dataset.tocado) { e.id = e.nome.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 24); idc.value = e.id; } });
            $('#ef-id').addEventListener('input', (x) => { x.target.dataset.tocado = '1'; });
            $('#ef-tipo').addEventListener('change', (x) => { e.tipo = x.target.value; e.receita = { pausa: 0, mistura: 'normal', camadas: [] }; desenharEditorEfeito(); mostrarPreco(); });
        }
        const mostrarPreco = () => { const b = $('[data-v="ef-preco"]'); if (b) b.textContent = precoVenda(e); };
        $('#ef-rar').addEventListener('change', (x) => { e.raridade = x.target.value; mostrarPreco(); });
        $('#ef-vender').addEventListener('change', (x) => { e.vender = x.target.checked; });
        $('#ef-desc').addEventListener('input', (x) => { e.descricao = x.target.value; });
        $('#ef-pausa').addEventListener('input', (x) => { e.receita.pausa = +x.target.value; $('[data-v="ef-pausa"]').textContent = x.target.value; agendarPrevia(); });
        $('#ef-mistura').addEventListener('change', (x) => { e.receita.mistura = x.target.value; agendarPrevia(); });
        $('#ef-preset').addEventListener('change', (x) => { const p = (PRESETS[e.tipo] || {})[x.target.value]; if (!p) return; e.receita = Object.assign({ mistura: 'normal' }, clone(p)); desenharEditorEfeito(); });
        $('#ef-add').addEventListener('change', (x) => {
            if (!x.target.value) return;
            if (e.receita.camadas.length >= XE.maxCamadas) { toast(`No máximo ${XE.maxCamadas} camadas.`, 'erro'); x.target.value = ''; return; }
            e.receita.camadas.push(camadaPadrao(x.target.value)); desenharEditorEfeito();
        });
        alvo.querySelectorAll('.es-camada input[data-p], .es-camada select[data-p]').forEach((c) => c.addEventListener('input', () => {
            const camada = e.receita.camadas[+c.dataset.i], t = c.dataset.t;
            camada[c.dataset.p] = t === 'num' ? +c.value : c.value;
            const rot = alvo.querySelector(`[data-v="${c.id}"]`); if (rot) rot.textContent = c.value;
            agendarPrevia();
        }));
        alvo.querySelectorAll('[data-a]').forEach((b) => b.addEventListener('click', () => {
            const i = +b.dataset.i, cs = e.receita.camadas;
            if (b.dataset.a === 'tira') cs.splice(i, 1);
            else { const j = b.dataset.a === 'sobe' ? i - 1 : i + 1; if (j < 0 || j >= cs.length) return; [cs[i], cs[j]] = [cs[j], cs[i]]; }
            desenharEditorEfeito();
        }));

        // arrastar arquivo: na camada sem arquivo, no "trocar" de uma camada com arquivo, ou na zona de criar camada nova
        alvo.querySelectorAll('.es-arq-zona').forEach((z) => {
            const camada = e.receita.camadas[+z.dataset.i], estado = $('.es-solta-estado', z);
            ligarSoltar(z, (fs) => usarArquivosNaCamada(fs, camada, estado), { unico: true, semClique: z.classList.contains('escolhido') });
        });
        alvo.querySelectorAll('[data-trocar], [data-biblioteca]').forEach((b) => b.addEventListener('click', () => {
            const camada = e.receita.camadas[+(b.dataset.trocar || b.dataset.biblioteca)];
            abrirBiblioteca((a) => { Object.assign(camada, { arq: a.id, a: infoDoArquivo(a) }); desenharEditorEfeito(); });
        }));
        const nova = $('#ef-solta-novo');
        if (nova) {
            ligarSoltar(nova, async (fs) => {
                if (e.receita.camadas.length >= XE.maxCamadas) { toast(`No máximo ${XE.maxCamadas} camadas.`, 'erro'); return; }
                const ok = await enviarVarios(fs.slice(0, 1), $('.es-solta-estado', nova));
                if (!ok.length) return;
                e.receita.camadas.push(camadaComArquivo(ok[0]));
                desenharEditorEfeito();
            }, { unico: true });
        }
        $('#ef-camadas-cartao').addEventListener('dragover', (ev) => { if (ev.dataTransfer && [...ev.dataTransfer.types].includes('Files')) ev.preventDefault(); });

        $('#ef-salvar').addEventListener('click', async () => {
            try {
                const r = await api('/efeitos', 'POST', { id: e.id, nome: e.nome, tipo: e.tipo, raridade: e.raridade, descricao: e.descricao, vender: !!e.vender, receita: e.receita });
                toast(XE.novo ? 'Efeito criado!' : 'Efeito salvo. Quem está conectado já vê a mudança.', 'ok');
                XE.novo = false;
                const d = await api('/efeitos'); XE.lista = d.efeitos; XE.atual = clone(XE.lista.find((x) => x.id === r.id));
                desenharEfeitos();
            } catch (x) { /* o toast já mostrou o motivo */ }
        });
        $('#ef-mim')?.addEventListener('click', async () => { try { await api('/itens/conceder', 'POST', { item_id: e.tipo + ':' + e.id, person_id: window.EU.id }); toast('Entregue pra você: abra o Inventário no app e equipe.', 'ok'); } catch (x) { /* toast */ } });
        $('#ef-dar')?.addEventListener('click', () => darItem(e.tipo + ':' + e.id, e.nome));
        $('#ef-dup')?.addEventListener('click', () => { XE.atual = Object.assign(clone(e), { id: '', nome: e.nome + ' (cópia)' }); XE.novo = true; desenharEfeitos(); });
        $('#ef-apagar')?.addEventListener('click', () => confirmar(`Apagar o efeito "${e.nome}"? Ele some de quem o tem (inventário e perfil) e das recompensas que o usam.`, async () => {
            try { await api('/efeitos/' + encodeURIComponent(e.id), 'DELETE'); toast('Efeito apagado.', 'ok'); XE.atual = null; vEfeitos(); } catch (x) { return false; }
        }, 'Apagar'));
    }

    // ------------------------------------------------------------
    // PACOTES (bundles): juntam itens de QUALQUER tema, um por slot. O servidor (app/pacotes.py) valida e confere o preço; aqui só se monta.
    // ------------------------------------------------------------
    const XP = { lista: [], catalogo: [], porId: {}, estados: [], icones: [], categorias: [], desconto: 30, minItens: 2, atual: null, novo: true };
    const SLOTS_PACOTE = ['moldura', 'nome', 'placa', 'faixa', 'efeito_avatar', 'efeito_perfil', 'efeito_fala', 'efeito_radar', 'efeito_chat', 'som_call', 'pin_nota', 'efeito_pagina'];
    const ROT_SLOT = { moldura: 'Moldura', nome: 'Estilo de nome', placa: 'Placa', faixa: 'Faixa do perfil', efeito_avatar: 'Efeito de avatar', efeito_perfil: 'Efeito de perfil',
        efeito_fala: 'Efeito de fala', efeito_radar: 'Efeito do radar', efeito_chat: 'Efeito do chat', som_call: 'Som de entrada', pin_nota: 'Pin de nota', efeito_pagina: 'Shader da página' };
    const ESTADO_ROT = { rascunho: 'Rascunho (só no Estúdio)', a_venda: 'À venda no Armazém (DRC)', so_dar: 'Só dar (admin ou recompensa do passe)' };
    const norm = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    const novoPacote = () => ({ id: '', nome: '', descricao: '', icone: 'fa-box-open', categoria: 'fantasia', cor1: '#d4a24c', cor2: '#3a2f1c', estado: 'rascunho',
        preco: null, ate: '', itens: [], faltando: [], no_ar: false, _modo: 'auto' });
    const doServidor = (p) => Object.assign(clone(p), { ate: (p.ate || '').slice(0, 10), _modo: p.preco ? 'fixo' : 'auto' });
    const tipoDe = (id) => (XP.porId[id] || {}).tipo;
    const itemDoSlot = (p, tipo) => p.itens.find((id) => tipoDe(id) === tipo);
    const somaDe = (p) => p.itens.reduce((s, id) => s + ((XP.porId[id] || {}).ref || 0), 0);
    /** A mesma conta do servidor (soma menos o desconto, em múltiplos de 50, metade pra cima). O servidor é quem vale. */
    const precoAuto = (soma) => (soma > 0 ? Math.max(50, Math.floor(soma * (1 - XP.desconto / 100) / 50 + 0.5) * 50) : 0);

    async function vPacotes() {
        const d = await api('/pacotes');
        XP.lista = d.pacotes; XP.catalogo = d.catalogo; XP.porId = Object.fromEntries(d.catalogo.map((i) => [i.id, i]));
        XP.estados = d.estados; XP.icones = d.icones; XP.categorias = d.categorias; XP.desconto = d.desconto; XP.minItens = d.min_itens;
        if (!XP.atual) { XP.atual = novoPacote(); XP.novo = true; }
        desenharPacotes();
    }
    VISTAS.pacotes = vPacotes;

    function resumoPreco(p) {
        const soma = somaDe(p), auto = precoAuto(soma), fixo = p._modo === 'fixo' ? Math.min(Math.max(+p.preco || 0, 0), soma) : 0;
        const final = fixo || auto, economia = soma > 0 && final > 0 ? Math.round((1 - final / soma) * 100) : 0;
        return { soma, auto, final, economia };
    }

    function desenharPacotes() {
        const lista = XP.lista.map((p) => `<button class="es-ef-item ${!XP.novo && XP.atual && XP.atual.id === p.id ? 'sel' : ''}" data-id="${esc(p.id)}"><b>${esc(p.nome)}</b>
            <small>${p.estado === 'a_venda' ? '<span class="es-pk-selo venda">à venda</span>' : p.estado === 'so_dar' ? '<span class="es-pk-selo dar">só dar</span>' : '<span class="es-pk-selo">rascunho</span>'} ${p.itens.length} itens${p.preco_final ? ` · <b>${p.preco_final} DRC</b>` : ''}</small></button>`).join('');
        main.innerHTML = `<h1>Pacotes (bundles)</h1><p class="es-sub">Junte itens de <b>qualquer tema</b> (moldura, nome, placa, faixa e os efeitos), <b>um por tipo</b>, e publique: <b>à venda</b> no Armazém (em DRC, com desconto de pacote), <b>só dar</b> (você dá a quem quiser ou o passe entrega como recompensa) ou deixe em <b>rascunho</b>. Quem recebe o pacote leva <b>todos</b> os itens dele, mesmo os que não são vendidos avulsos (como um efeito do Estúdio). Dá pra equipar tudo de uma vez no Inventário.</p>
            <div class="es-ef-layout"><div class="es-ef-lado"><button class="es-btn primario" id="pk-novo">Novo pacote</button><div class="es-ef-lista es-pk-lista">${lista || '<div class="es-vazio">Nenhum pacote ainda.</div>'}</div></div>
            <div class="es-ef-editor" id="pk-editor"></div></div>`;
        $('#pk-novo').addEventListener('click', () => { XP.atual = novoPacote(); XP.novo = true; desenharPacotes(); });
        main.querySelectorAll('.es-ef-item').forEach((b) => b.addEventListener('click', () => { const p = XP.lista.find((x) => x.id === b.dataset.id); XP.atual = doServidor(p); XP.novo = false; desenharPacotes(); }));
        desenharEditorPacote();
    }

    function desenharEditorPacote() {
        const p = XP.atual, alvo = $('#pk-editor');
        if (!alvo) return;
        const slots = SLOTS_PACOTE.map((tipo) => {
            const id = itemDoSlot(p, tipo), it = id && XP.porId[id];
            return `<div class="es-slot ${it ? 'cheio' : ''}" data-tipo="${tipo}"><div class="es-slot-corpo"><span class="es-slot-rot">${esc(ROT_SLOT[tipo])}</span>
                <span class="es-slot-item ${it ? '' : 'vazio'}"><b>${it ? esc(it.nome) : 'nenhum'}</b>${it ? `<small>${esc(it.tema_nome)} · ${esc(it.raridade)} · ${it.ref ? it.ref + ' DRC' : 'sem preço'}${it.avulso ? '' : ' · não vendido avulso'}</small>` : ''}</span></div>
                <button class="es-btn mini" data-escolher="${tipo}">${it ? 'Trocar' : 'Escolher'}</button>${it ? `<button class="es-btn mini perigo" data-tirar="${tipo}">Tirar</button>` : ''}</div>`;
        }).join('');
        const r = resumoPreco(p);
        const semRef = p.itens.filter((id) => XP.porId[id] && !XP.porId[id].ref);
        const naoAvulso = p.itens.filter((id) => XP.porId[id] && !XP.porId[id].avulso);
        const avisos = [];
        if (p.faltando && p.faltando.length) avisos.push(['erro', `${p.faltando.length} item(ns) deste pacote saíram do catálogo (um efeito apagado, por exemplo). Tire do pacote e salve de novo.`]);
        if (semRef.length) avisos.push(['', `Sem preço de referência (conta 0 na soma): ${semRef.map((id) => esc(XP.porId[id].nome)).join(', ')}.`]);
        if (p.itens.length && p.itens.length < XP.minItens) avisos.push(['', `Faltam itens: um pacote precisa de pelo menos ${XP.minItens}.`]);
        if (p.estado === 'a_venda' && p.itens.length >= XP.minItens && r.soma <= 0) avisos.push(['erro', 'Com esses itens a soma é 0, então não dá pra vender. Use "só dar" ou troque algum item.']);
        if (p._modo === 'fixo' && r.soma > 0 && +p.preco > r.soma) avisos.push(['erro', `O preço fixo não pode passar da soma dos itens (${r.soma} DRC).`]);
        const dica = naoAvulso.length ? `<p class="es-dica" style="margin-top:10px">${naoAvulso.length} item(ns) não são vendidos avulsos (${naoAvulso.map((id) => esc(XP.porId[id].nome)).join(', ')}): só chegam a quem comprar ou receber o pacote.</p>` : '';
        alvo.innerHTML = `<div class="es-cartao"><h2>${XP.novo ? 'Novo pacote' : 'Editando: ' + esc(p.nome)}</h2>
            <div class="es-linha"><div class="es-campo largo"><label>Nome (2 a 40)</label><input id="pk-nome" maxlength="40" value="${esc(p.nome)}"></div>
                <div class="es-campo"><label>Id (letras minúsculas e _)</label><input id="pk-id" maxlength="24" value="${esc(p.id)}" ${XP.novo ? '' : 'disabled'}></div></div>
            <div class="es-campo" style="margin-top:12px"><label>Descrição (aparece no Armazém e pra quem ganhar)</label><input id="pk-desc" maxlength="160" value="${esc(p.descricao)}"></div>
            <div class="es-linha" style="margin-top:12px"><div class="es-campo"><label>Categoria no Armazém</label><select id="pk-cat">${XP.categorias.map((c) => `<option value="${esc(c.id)}" ${c.id === p.categoria ? 'selected' : ''}>${esc(c.nome)}</option>`).join('')}</select></div>
                <div class="es-campo"><label>Cor 1</label><input id="pk-cor1" type="color" value="${esc(p.cor1)}"></div><div class="es-campo"><label>Cor 2</label><input id="pk-cor2" type="color" value="${esc(p.cor2)}"></div>
                <div class="es-campo"><label>Ícone</label><div class="es-icones" id="pk-icones">${XP.icones.map((ic) => `<button type="button" data-ic="${esc(ic)}" class="${ic === p.icone ? 'sel' : ''}" title="${esc(ic)}"><i class="fa-solid ${esc(ic)}"></i></button>`).join('')}</div></div></div></div>
            <div class="es-pk-colunas"><div><div class="es-cartao"><h2>Itens do pacote</h2><div class="es-slots">${slots}</div>${dica}</div></div>
            <div><div class="es-cartao"><h2>Publicação e preço</h2>
                <div class="es-campo"><label>Estado</label><select id="pk-estado">${XP.estados.map((e) => `<option value="${e}" ${e === p.estado ? 'selected' : ''}>${esc(ESTADO_ROT[e] || e)}</option>`).join('')}</select></div>
                <div class="es-linha" style="margin-top:12px"><div class="es-campo"><label>Preço</label><select id="pk-modo"><option value="auto" ${p._modo === 'auto' ? 'selected' : ''}>Automático (−${XP.desconto}% da soma)</option><option value="fixo" ${p._modo === 'fixo' ? 'selected' : ''}>Fixo (até a soma)</option></select></div>
                    <div class="es-campo" ${p._modo === 'fixo' ? '' : 'hidden'} id="pk-fixo-caixa"><label>Preço fixo (DRC)</label><input id="pk-fixo" type="number" min="1" max="${r.soma || 1}" value="${p.preco || ''}"></div></div>
                <div class="es-campo" style="margin-top:12px"><label>Fim da venda (opcional)</label><input id="pk-ate" type="date" value="${esc(p.ate)}"><small>Depois desse dia o pacote continua visível, mas não se compra. Vazio = sem fim.</small></div>
                <div class="es-resumo" id="pk-resumo"><div><small>Soma dos itens</small><b>${r.soma} DRC</b></div><div><small>Preço do pacote</small><b class="ouro">${r.final || '—'}${r.final ? ' DRC' : ''}</b></div><div><small>Economia</small><b>${r.economia}%</b></div></div>
                ${avisos.map(([c, t]) => `<div class="es-aviso ${c}">${t}</div>`).join('')}
                <div class="es-linha" style="margin-top:14px"><button class="es-btn primario" id="pk-salvar">${XP.novo ? 'Criar pacote' : 'Salvar alterações'}</button>
                    ${XP.novo ? '' : `<button class="es-btn" id="pk-mim" ${p.no_ar ? '' : 'disabled'}>Dar a mim</button><button class="es-btn" id="pk-dar" ${p.no_ar ? '' : 'disabled'}>Dar a alguém</button><button class="es-btn" id="pk-dup">Duplicar</button><button class="es-btn perigo" id="pk-apagar">Apagar</button>`}</div>
                ${XP.novo ? '' : `<p class="es-dica" style="margin-top:10px">Item no catálogo: <code>pacote:${esc(p.id)}</code>${p.no_ar ? '' : ' (em rascunho o pacote ainda não existe pro app: publique como "só dar" ou "à venda" pra poder dar)'}. No Passe de Batalha (painel do admin), escolha "Item" e procure por ele pra usar de recompensa. Quem já recebeu o pacote antes de uma mudança nos itens fica com o que recebeu.</p>`}</div></div></div>`;
        ligarEditorPacote();
    }

    function abrirSeletor(tipo, aoEscolher) {
        const todos = XP.catalogo.filter((i) => i.tipo === tipo), atual = itemDoSlot(XP.atual, tipo);
        const d = dialogo(`Escolher: ${ROT_SLOT[tipo]}`, '<div class="es-campo es-pick-busca"><input id="pk-busca" placeholder="Procurar por nome ou tema" autocomplete="off"></div><div class="es-pick-lista" id="pk-lista"></div>', [{ texto: 'Fechar' }], true);
        const lista = $('#pk-lista', d.fundo), busca = $('#pk-busca', d.fundo);
        const desenhar = () => {
            const q = norm(busca.value), achados = todos.filter((i) => !q || norm(i.nome + ' ' + i.tema_nome).includes(q)), mostrar = achados.slice(0, 120);
            lista.innerHTML = (mostrar.map((i) => `<button type="button" data-id="${esc(i.id)}" class="${i.id === atual ? 'sel' : ''}"><span>${esc(i.nome)}</span><small>${esc(i.tema_nome)} · ${esc(i.raridade)} · ${i.ref ? i.ref + ' DRC' : 'sem preço'}</small></button>`).join('')
                + (achados.length > mostrar.length ? `<div class="es-pick-mais">Mostrando ${mostrar.length} de ${achados.length}. Refine a busca.</div>` : '')) || '<div class="es-vazio">Nada encontrado.</div>';
        };
        busca.addEventListener('input', desenhar);
        lista.addEventListener('click', (ev) => { const b = ev.target.closest('button[data-id]'); if (b) { aoEscolher(b.dataset.id); d.fechar(); } });
        desenhar();
        busca.focus();
    }

    function ligarEditorPacote() {
        const p = XP.atual, alvo = $('#pk-editor');
        const refazerResumo = () => { const z = $('#pk-resumo'), r = resumoPreco(p); if (z) z.innerHTML = `<div><small>Soma dos itens</small><b>${r.soma} DRC</b></div><div><small>Preço do pacote</small><b class="ouro">${r.final || '—'}${r.final ? ' DRC' : ''}</b></div><div><small>Economia</small><b>${r.economia}%</b></div>`; };
        $('#pk-nome').addEventListener('input', (x) => { p.nome = x.target.value; });
        if (XP.novo) {
            $('#pk-id').addEventListener('input', (x) => { p.id = x.target.value; x.target.dataset.tocado = '1'; });
            $('#pk-nome').addEventListener('input', () => { const idc = $('#pk-id'); if (!idc.dataset.tocado) { p.id = norm(p.nome).replace(/[^a-z]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 24); idc.value = p.id; } });
        }
        $('#pk-desc').addEventListener('input', (x) => { p.descricao = x.target.value; });
        $('#pk-cat').addEventListener('change', (x) => { p.categoria = x.target.value; });
        $('#pk-cor1').addEventListener('input', (x) => { p.cor1 = x.target.value; });
        $('#pk-cor2').addEventListener('input', (x) => { p.cor2 = x.target.value; });
        $('#pk-icones').addEventListener('click', (ev) => { const b = ev.target.closest('button[data-ic]'); if (!b) return; p.icone = b.dataset.ic; alvo.querySelectorAll('#pk-icones button').forEach((x) => x.classList.toggle('sel', x === b)); });
        $('#pk-estado').addEventListener('change', (x) => { p.estado = x.target.value; desenharEditorPacote(); });
        $('#pk-modo').addEventListener('change', (x) => { p._modo = x.target.value; if (p._modo === 'fixo' && !p.preco) p.preco = resumoPreco(p).auto || null; desenharEditorPacote(); });
        $('#pk-fixo').addEventListener('input', (x) => { p.preco = x.target.value ? +x.target.value : null; refazerResumo(); });
        $('#pk-ate').addEventListener('change', (x) => { p.ate = x.target.value; });
        alvo.querySelectorAll('[data-escolher]').forEach((b) => b.addEventListener('click', () => abrirSeletor(b.dataset.escolher, (id) => {
            p.itens = p.itens.filter((x) => tipoDe(x) !== b.dataset.escolher).concat(id);
            desenharEditorPacote();
        })));
        alvo.querySelectorAll('[data-tirar]').forEach((b) => b.addEventListener('click', () => { p.itens = p.itens.filter((x) => tipoDe(x) !== b.dataset.tirar); desenharEditorPacote(); }));
        $('#pk-salvar').addEventListener('click', async () => {
            const itens = p.itens.filter((id) => XP.porId[id]);      // item que saiu do catálogo não vai de novo
            try {
                const r = await api('/pacotes', 'POST', { id: p.id, nome: p.nome, descricao: p.descricao, icone: p.icone, categoria: p.categoria, cor1: p.cor1, cor2: p.cor2,
                    estado: p.estado, itens, preco: p._modo === 'fixo' && p.preco ? +p.preco : null, ate: p.ate || '' });
                toast(XP.novo ? 'Pacote criado!' : 'Pacote salvo.', 'ok');
                XP.novo = false;
                const d = await api('/pacotes'); XP.lista = d.pacotes; XP.atual = doServidor(XP.lista.find((x) => x.id === r.id));
                desenharPacotes();
            } catch (x) { /* o toast já mostrou o motivo */ }
        });
        $('#pk-mim')?.addEventListener('click', async () => { try { await api('/itens/conceder', 'POST', { item_id: 'pacote:' + p.id, person_id: window.EU.id }); toast('Entregue pra você: abra o Inventário no app e equipe tudo.', 'ok'); } catch (x) { /* toast */ } });
        $('#pk-dar')?.addEventListener('click', () => darItem('pacote:' + p.id, p.nome));
        $('#pk-dup')?.addEventListener('click', () => { XP.atual = Object.assign(clone(p), { id: '', nome: p.nome + ' (cópia)', estado: 'rascunho', no_ar: false, faltando: [] }); XP.novo = true; desenharPacotes(); });
        $('#pk-apagar')?.addEventListener('click', () => confirmar(`Apagar o pacote "${p.nome}"? Ele some do Armazém e do catálogo. Quem já recebeu fica com os itens (só o "carimbo" do pacote some).`, async () => {
            try { await api('/pacotes/' + encodeURIComponent(p.id), 'DELETE'); toast('Pacote apagado.', 'ok'); XP.atual = null; vPacotes(); } catch (x) { return false; }
        }, 'Apagar'));
    }

    function darItem(itemId, nome) {
        const d = dialogo(`Dar "${nome}" a alguém`, '<div class="es-campo"><label>Procurar pessoa</label><input id="di-q" placeholder="nome ou @" autocomplete="off"></div><div id="di-r"></div>', [{ texto: 'Fechar' }]);
        let tm;
        $('#di-q', d.fundo).addEventListener('input', (ev) => {
            clearTimeout(tm);
            tm = setTimeout(async () => {
                if (ev.target.value.trim().length < 2) return;
                const r = await api('/pessoas?q=' + encodeURIComponent(ev.target.value));
                const alvo = $('#di-r', d.fundo);
                alvo.innerHTML = `<div class="es-lista">${r.pessoas.map((p) => `<button data-p="${p.id}"><span>${esc(p.nome)}</span><small>@${esc(p.username)}</small></button>`).join('') || '<div class="es-vazio">Ninguém encontrado.</div>'}</div>`;
                alvo.querySelectorAll('button').forEach((b) => b.addEventListener('click', async () => { try { await api('/itens/conceder', 'POST', { item_id: itemId, person_id: +b.dataset.p }); toast('Entregue.', 'ok'); d.fechar(); } catch (e2) { /* toast */ } }));
            }, 300);
        });
    }

    window.addEventListener('hashchange', () => { const v = location.hash.slice(1); if (VISTAS[v] && v !== vistaAtual) ir(v); });
    ir(VISTAS[location.hash.slice(1)] ? location.hash.slice(1) : 'efeitos');
})();
