/* Clipes da call (Rodada 34): clipe automático que aparece de verdade, o sinal (!) no canto da tela da call, o pop-up com os clipes, ver, CORTAR de verdade,
   mandar pra um amigo (DM), mandar num canal ou baixar. Objeto global `Clipes` (+ `ClipesDetector` e `ClipesArmazem`, que são lógica pura e rodam também no Node: testes/clipes_logica.js).
   Tudo acontece no navegador de quem clipa: a mídia da call é P2P, o servidor nunca vê um quadro. O único caminho pra fora é o de sempre (/api/upload -> Cloudinary), e só quando a
   pessoa manda o clipe pra alguém.

   Como funciona:
   - Um "compositor" desenha a grade da call num canvas (480p, 15 fps) e mistura o áudio de TODO mundo (inclusive de quem entrou depois: ele reconcilia a cada 1,5 s).
   - A "janela deslizante" são dois MediaRecorder defasados (cada um vive 40 s, um novo abre a cada 20 s): a qualquer momento o mais velho tem entre 20 e 40 s de vídeo
     e vira um arquivo válido na hora (requestData). Colar pedaços de gravadores diferentes não funciona (cabeçalho Matroska próprio de cada um), então nunca se cola.
   - O detector lê o volume de cada pessoa 20x por segundo e junta 3 sinais num placar que esfria: pico de volume (relativo ao normal DE CADA PESSOA), gente falando junto e risada
     (rajadas regulares com vales fundos). Disparou, espera ~6 s pra pegar o resto do momento e guarda o clipe. Mínimo de 45 s entre clipes.
   - O clipe automático vive 20 min e some quando a call acaba. Cortar = tocar o trecho escondido e gravar de novo (MediaRecorder): sem ffmpeg, leva o tempo do trecho.
   Contexto (Clipes.iniciar): { esc, escUrl, toast, micStream(), emCall(), amigos(), canais(), destinoDaCall(), upload(file), enviarDM(id, dados), enviarCanal(id, dados), aoMudarAuto(on) }.
   Tudo que vem de fora passa por esc()/escUrl() antes do innerHTML. Animações só em transform/opacity, e `body.rolando`/`prefers-reduced-motion` já são respeitados no CSS. */

// ======================================================================================================================
// DETECTOR (lógica pura: recebe níveis de volume e diz quando vale um clipe)
// ======================================================================================================================
const ClipesDetector = (() => {
    'use strict';
    const SENS = { baixa: 0.75, normal: 1, alta: 1.4 };
    const LIMIAR = 4;              // pontos pra disparar (dividido pela sensibilidade)
    const DECAI_S = 5;             // o placar esfria com essa constante de tempo
    const T_FALA = 0.03, T_FALA_SAI = 0.018;   // RMS (0..1) a partir do qual alguém está falando (com histerese)
    const BASE_PADRAO = 0.1;       // "volume normal" de quem ainda não foi medido
    const MIN_AMOSTRAS_BASE = 8;
    const MIN_PICO = 0.09;         // abaixo disso nunca é "pico" (ruído, clique)
    const GRITO = 0.38;            // acima disso é grito/estouro, conta em dobro
    const INTERVALO_MIN_MS = 45000;
    const TAXA = { pico: 3, grito: 6, junto2: 2, junto3: 3 };   // pontos por segundo

    function mediana(a) { const s = a.slice().sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }

    // Risada: rajadas de energia regulares (~3 a 6 por segundo) com vales fundos entre elas (a respiração entre os "ha").
    // Fala também modula, mas com vales rasos e intervalos irregulares. Heurística: não é IA, e erra pros dois lados.
    // `minPico` = quão alto precisa ser: risada costuma ser mais alta que a fala normal da call.
    function detectarRisada(arr, minPico) {
        const n = arr.length;
        if (n < 28) return false;
        const s = arr.map((v, i) => (arr[i - 1] != null ? arr[i - 1] : v) * 0.25 + v * 0.5 + (arr[i + 1] != null ? arr[i + 1] : v) * 0.25);
        let mx = 0; for (const v of s) if (v > mx) mx = v;
        if (mx < (minPico != null ? minPico : 0.06)) return false;
        const corte = mx * 0.4;
        const picos = [];
        for (let i = 1; i < n - 1; i++) {
            if (s[i] >= corte && s[i] > s[i - 1] && s[i] >= s[i + 1]) {
                const ult = picos.length ? picos[picos.length - 1] : -99;
                if (i - ult < 3) { if (s[i] > s[ult]) picos[picos.length - 1] = i; }
                else picos.push(i);
            }
        }
        if (picos.length < 4) return false;
        const iv = []; for (let k = 1; k < picos.length; k++) iv.push(picos[k] - picos[k - 1]);
        const media = iv.reduce((a, b) => a + b, 0) / iv.length;
        if (media < 3.5 || media > 9) return false;                       // 175 a 450 ms entre um "ha" e o próximo
        const dp = Math.sqrt(iv.reduce((a, b) => a + (b - media) * (b - media), 0) / iv.length);
        if (dp / media > 0.3) return false;                                // irregular demais: é fala
        let prof = 0;
        for (let k = 1; k < picos.length; k++) {
            let vale = Infinity; for (let j = picos[k - 1]; j <= picos[k]; j++) if (s[j] < vale) vale = s[j];
            prof += vale / Math.min(s[picos[k - 1]], s[picos[k]]);
        }
        prof /= (picos.length - 1);
        return prof <= 0.4;                                                // vale fundo = respiração entre os "ha"
    }

    function criar(opc) {
        opc = opc || {};
        let sens = SENS[opc.sensibilidade] || 1;
        const intervaloMin = opc.intervaloMinMs != null ? opc.intervaloMinMs : INTERVALO_MIN_MS;
        const pessoas = new Map();
        let env = [];
        let score = 0, pts = { pico: 0, junto: 0, risada: 0 };
        let ultimoT = null, ultimoDisparo = -Infinity, ultimaRisada = -Infinity, bucketIni = 0;

        function pessoa(id) {
            let p = pessoas.get(id);
            if (!p) { p = { ema: 0, falando: false, bucket: 0, picos: [], novo: true }; pessoas.set(id, p); }
            return p;
        }
        function baseDe(p) { return p.picos.length >= MIN_AMOSTRAS_BASE ? mediana(p.picos) : BASE_PADRAO; }
        function limPico(p) { return Math.max(MIN_PICO, baseDe(p) * 2) / sens; }

        function alimentar(t, niveis) {
            if (ultimoT == null) { ultimoT = t; bucketIni = t; }
            let dt = t - ultimoT; ultimoT = t;
            if (dt < 0) dt = 0; if (dt > 2000) dt = 2000;
            const s = dt / 1000;
            const f = Math.exp(-s / DECAI_S);
            score *= f; pts.pico *= f; pts.junto *= f; pts.risada *= f;

            let falando = 0, grito = false, pico = false, bruto = 0;
            for (const n of niveis || []) {
                if (!n || !(n.v >= 0)) continue;
                const p = pessoa(n.id);
                p.ema = p.novo || !dt ? n.v : p.ema + (n.v - p.ema) * (1 - Math.exp(-dt / 100));
                p.novo = false;
                if (p.falando) { if (p.ema < T_FALA_SAI) p.falando = false; } else if (p.ema >= T_FALA) p.falando = true;
                if (p.falando) falando++;
                if (p.ema > p.bucket) p.bucket = p.ema;
                if (n.v > bruto) bruto = n.v;
                if (p.ema >= GRITO / sens) grito = true;
                else if (p.ema >= limPico(p)) pico = true;
            }
            // a cada segundo, o pico de quem falou vira amostra do "volume normal" dele
            if (t - bucketIni >= 1000) {
                for (const p of pessoas.values()) {
                    if (p.bucket >= T_FALA) { p.picos.push(p.bucket); if (p.picos.length > 90) p.picos.shift(); }
                    p.bucket = 0;
                }
                bucketIni = t;
            }

            const soma = (k, v) => { pts[k] += v; score += v; };
            if (grito) soma('pico', TAXA.grito * s);
            else if (pico) soma('pico', TAXA.pico * s);
            if (falando >= 3) soma('junto', TAXA.junto3 * s);
            else if (falando === 2) soma('junto', TAXA.junto2 * s);

            // risada: precisa de amostras bem espaçadas (aba em segundo plano estrangula o relógio: aí não dá pra enxergar rajada)
            if (dt > 0 && dt <= 120) { env.push(bruto); if (env.length > 36) env.shift(); } else env = [];
            let refBase = 0; for (const p of pessoas.values()) refBase = Math.max(refBase, baseDe(p));
            if (t - ultimaRisada > 4000 && detectarRisada(env, Math.max(0.07, (refBase || BASE_PADRAO) * 1.25) / sens)) {
                ultimaRisada = t;
                soma('risada', (LIMIAR / sens) * (sens < 1 ? 0.8 : 1.05));
            }

            if (score >= LIMIAR / sens && t - ultimoDisparo >= intervaloMin) {
                let motivo = 'pico', melhor = -1;
                for (const k of ['risada', 'pico', 'junto']) if (pts[k] > melhor) { melhor = pts[k]; motivo = k; }
                const ev = { motivo, t, pontos: Math.round(score * 10) / 10 };
                score = 0; pts = { pico: 0, junto: 0, risada: 0 }; ultimoDisparo = t; env = [];
                return ev;
            }
            if (score >= LIMIAR / sens) score = LIMIAR / sens;       // em cooldown o placar não passa do limite (senão disparava duas vezes seguidas)
            return null;
        }

        return {
            alimentar,
            definirSensibilidade(nome) { sens = SENS[nome] || 1; },
            reiniciar() { score = 0; pts = { pico: 0, junto: 0, risada: 0 }; env = []; pessoas.clear(); ultimoT = null; },
            estado() { return { score: Math.round(score * 100) / 100, pts: { ...pts }, sens }; },
        };
    }
    return { criar, detectarRisada, SENS, LIMIAR, INTERVALO_MIN_MS };
})();

// ======================================================================================================================
// ARMAZÉM (lógica pura: onde os clipes ficam, o que é novo e quando expiram)
// ======================================================================================================================
const ClipesArmazem = (() => {
    'use strict';
    const TTL_MS = 20 * 60 * 1000;     // cada clipe vive 20 minutos
    const MAX = 12;

    function criar(opc) {
        opc = opc || {};
        const ttl = opc.ttlMs != null ? opc.ttlMs : TTL_MS;
        const max = opc.max || MAX;
        const agora = opc.agora || (() => Date.now());
        const aoSair = opc.aoSair || (() => {});
        let itens = [], seq = 0;

        function adicionar(c) {
            c = Object.assign({ visto: false, acoes: [] }, c);
            c.id = ++seq; c.criadoEm = agora(); c.expiraEm = c.criadoEm + ttl;
            itens.unshift(c);
            while (itens.length > max) aoSair(itens.pop(), 'limite');
            return c;
        }
        function varrer() {
            const t = agora(), saem = itens.filter(c => c.expiraEm <= t);
            if (saem.length) { itens = itens.filter(c => c.expiraEm > t); saem.forEach(c => aoSair(c, 'expirou')); }
            return saem;
        }
        function remover(id, motivo) {
            const c = itens.find(x => x.id === id);
            if (!c) return null;
            itens = itens.filter(x => x.id !== id); aoSair(c, motivo || 'apagado');
            return c;
        }
        function limpar(motivo) { const todos = itens; itens = []; todos.forEach(c => aoSair(c, motivo || 'fim')); return todos; }
        return {
            adicionar, varrer, remover, limpar,
            listar() { return itens.slice(); },
            obter(id) { return itens.find(x => x.id === id) || null; },
            marcarVisto(id) { const c = itens.find(x => x.id === id); if (c) c.visto = true; return c; },
            novos() { return itens.filter(c => !c.visto).length; },
            total() { return itens.length; },
            restante(c) { return Math.max(0, c.expiraEm - agora()); },
            fracao(c) { return Math.max(0, Math.min(1, (c.expiraEm - agora()) / ttl)); },
        };
    }
    return { criar, TTL_MS, MAX };
})();

// ======================================================================================================================
// A PARTE DO NAVEGADOR
// ======================================================================================================================
const Clipes = (() => {
    'use strict';
    let ctx = null;
    const C = { pos: 6000, minMs: 8000, vida: 40000, passo: 20000, fps: 15, altura: 480, sinalMs: 4500, ttl: ClipesArmazem.TTL_MS };
    const CH_AUTO = 'pnt_clip_auto', CH_SENS = 'pnt_clip_sens';
    const MOTIVOS = {
        risada: ['face-laugh-beam', 'Risada'],
        pico: ['bolt', 'Pico de empolgação'],
        junto: ['users', 'Todo mundo falando junto'],
        manual: ['scissors', 'Clipe manual'],
    };
    const LIMITE_MB = 25;

    let emCall = false, auto = true, sens = 'normal', capturando = false, avisouSemSuporte = false;
    let comp = null, janela = null, detector = null, armazem = null;
    let timerSensor = null, timerSync = null, timerVarre = null, timerDica = null;
    let sinal = null, modal = null;
    let vista = 'lista', abertoId = null, urlAberto = null, destacar = null, entrando = null, cortando = null, sheet = null;
    let sel = { ini: 0, fim: 0 }, durAtual = 0, arrasto = null;

    const T = (v) => ctx.esc(v == null ? '' : v);
    const $ = (s) => (modal ? modal.querySelector(s) : null);
    const lerPref = (k, pad) => { try { const v = localStorage.getItem(k); return v == null ? pad : v; } catch (e) { return pad; } };
    const gravarPref = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* sem armazenamento: vale até recarregar */ } };
    const fmt = (s) => { s = Math.max(0, Number(s) || 0); return Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0'); };
    const horaDe = (ms) => new Date(ms).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    const restanteTxt = (ms) => { const m = Math.ceil(ms / 60000); return m <= 1 ? 'menos de 1 min' : m + ' min'; };
    const mimeEscolhido = () => ['video/webm;codecs=vp8,opus', 'video/webm'].find(t => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || '';
    const ACAO_ROTULO = (c) => {
        const a = c.acoes[c.acoes.length - 1];
        if (!a) return '';
        const nome = String(a.alvo || '').slice(0, 14);
        return a.tipo === 'dm' ? 'Mandado pra ' + nome : a.tipo === 'canal' ? 'Mandado em #' + nome : 'Baixado';
    };
    const esperar = (el, nome, ms) => new Promise((ok, falha) => {
        const t = setTimeout(() => { el.removeEventListener(nome, f); falha(new Error('tempo esgotado em ' + nome)); }, ms || 8000);
        const f = () => { clearTimeout(t); ok(); };
        el.addEventListener(nome, f, { once: true });
    });

    // ------------------------------------------------------------------------------------------------------------------
    // compositor: grade da call num canvas + áudio de todo mundo + níveis de volume por pessoa
    // ------------------------------------------------------------------------------------------------------------------
    function criarComp() {
        const canvas = document.createElement('canvas');
        canvas.height = C.altura; canvas.width = Math.round(C.altura * 16 / 9);
        const g = canvas.getContext('2d');
        const ac = new (window.AudioContext || window.webkitAudioContext)({ latencyHint: 'playback' });
        if (ac.state === 'suspended') ac.resume().catch(() => {});
        const destino = ac.createMediaStreamDestination();
        const fontes = new Map();        // MediaStream -> { src, an, buf, id }
        let ativo = true, timerDesenho = null;

        function ligar(stream, id) {
            if (!stream || fontes.has(stream) || !stream.getAudioTracks || !stream.getAudioTracks().length) return;
            try {
                const src = ac.createMediaStreamSource(stream);
                src.connect(destino);
                const an = ac.createAnalyser(); an.fftSize = 1024; an.smoothingTimeConstant = 0;
                src.connect(an);          // o analisador só precisa de entrada
                fontes.set(stream, { src, an, buf: new Float32Array(an.fftSize), id });
            } catch (e) { /* faixa sem áudio ou já morta: tenta de novo na próxima volta */ }
        }
        function sincronizar() {
            const mic = ctx.micStream && ctx.micStream();
            if (mic) ligar(mic, 'eu');
            document.querySelectorAll('#video-grid .video-card').forEach(card => {
                if (card.id === 'my-video-card') return;
                const v = card.querySelector('video'), s = v && v.srcObject;
                if (s) ligar(s, card.id || 'remoto');
            });
            for (const [s, f] of fontes) {
                if (s.getAudioTracks().every(t => t.readyState === 'ended')) { try { f.src.disconnect(); } catch (e) { /* já solto */ } fontes.delete(s); }
            }
        }
        function niveis() {
            const r = [];
            for (const f of fontes.values()) {
                f.an.getFloatTimeDomainData(f.buf);
                let q = 0; for (let i = 0; i < f.buf.length; i++) q += f.buf[i] * f.buf[i];
                r.push({ id: f.id, v: Math.sqrt(q / f.buf.length) });
            }
            return r;
        }

        function desenharCard(card, x, y, w, h) {
            const v = card.querySelector('video');
            const propria = card.classList.contains('tela-propria');
            if (v && !propria && v.style.display !== 'none' && v.readyState >= 2 && v.videoWidth) {
                const k = Math.min(w / v.videoWidth, h / v.videoHeight), dw = v.videoWidth * k, dh = v.videoHeight * k;
                g.fillStyle = '#000'; g.fillRect(x, y, w, h);
                g.drawImage(v, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh);
            } else {
                g.fillStyle = '#1e1f22'; g.fillRect(x, y, w, h);
                const nome = ((card.querySelector('.video-label') || {}).textContent || '?').trim();
                const r = Math.max(14, Math.min(w, h) / 5);
                g.fillStyle = '#5865f2'; g.beginPath(); g.arc(x + w / 2, y + h / 2 - r * 0.2, r, 0, Math.PI * 2); g.fill();
                g.fillStyle = '#fff'; g.font = `bold ${Math.round(r * 1.1)}px sans-serif`; g.textAlign = 'center'; g.textBaseline = 'middle';
                g.fillText(nome.charAt(0).toUpperCase() || '?', x + w / 2, y + h / 2 - r * 0.2);
            }
            const nome = ((card.querySelector('.video-label') || {}).textContent || '').trim();
            if (nome) {
                g.font = `${Math.max(11, Math.round(h / 14))}px sans-serif`; g.textAlign = 'left'; g.textBaseline = 'alphabetic';
                const tw = Math.min(w - 12, g.measureText(nome).width + 12);
                g.fillStyle = 'rgba(0,0,0,.6)'; g.fillRect(x + 6, y + h - 6 - Math.max(18, h / 10), tw, Math.max(18, h / 10));
                g.fillStyle = '#fff'; g.fillText(nome, x + 12, y + h - 12);
            }
            if (card.classList.contains('is-speaking')) { g.strokeStyle = '#23a559'; g.lineWidth = 3; g.strokeRect(x + 1.5, y + 1.5, w - 3, h - 3); }
        }
        // Desenha por setInterval e NÃO por requestAnimationFrame: o rAF para quando a janela está escondida/coberta (jogando com a call de lado),
        // e sem quadros novos o MediaRecorder nem começa a gravar. O setInterval segue (o navegador só o estrangula pra ~1 quadro por segundo).
        function desenhar() {
            if (!ativo) return;
            const W = canvas.width, H = canvas.height;
            g.fillStyle = '#111214'; g.fillRect(0, 0, W, H);
            const cards = Array.from(document.querySelectorAll('#video-grid .video-card'));
            if (!cards.length) return;
            const foco = cards.find(k => k.classList.contains('focused')) || cards.find(k => /^screen-card-/.test(k.id) && !k.classList.contains('tela-propria'));
            if (foco && cards.length > 1) {                       // tela compartilhada (ou card em foco) grande, o resto numa coluna
                const resto = cards.filter(k => k !== foco).slice(0, 5), gap = 6, lado = Math.round(W * 0.22);
                desenharCard(foco, 0, 0, W - lado - gap, H);
                const h = Math.min((H - gap * (resto.length - 1)) / resto.length, lado * 9 / 16);
                resto.forEach((k, i) => desenharCard(k, W - lado, i * (h + gap), lado, h));
                return;
            }
            const cols = Math.ceil(Math.sqrt(cards.length)), rows = Math.ceil(cards.length / cols);
            const cw = W / cols, ch = H / rows;
            cards.forEach((k, i) => desenharCard(k, (i % cols) * cw + 2, Math.floor(i / cols) * ch + 2, cw - 4, ch - 4));
        }
        desenhar();
        timerDesenho = setInterval(desenhar, Math.round(1000 / C.fps));

        const stream = new MediaStream([...canvas.captureStream(C.fps).getVideoTracks(), ...destino.stream.getAudioTracks()]);
        function foto() {                                          // miniatura do momento (aparece na lista de clipes)
            try {
                const mini = document.createElement('canvas'); mini.width = 320; mini.height = 180;
                mini.getContext('2d').drawImage(canvas, 0, 0, 320, 180);
                const u = mini.toDataURL('image/jpeg', 0.6);
                return /^data:image\/jpeg;base64,[A-Za-z0-9+/=]+$/.test(u) ? u : null;
            } catch (e) { return null; }
        }
        sincronizar();
        return { stream, sincronizar, niveis, foto, parar() { ativo = false; clearInterval(timerDesenho); fontes.clear(); ac.close().catch(() => {}); } };
    }

    // ------------------------------------------------------------------------------------------------------------------
    // janela deslizante: dois gravadores defasados; o mais velho vira o clipe
    // ------------------------------------------------------------------------------------------------------------------
    function criarJanela(stream) {
        const mime = mimeEscolhido();
        let itens = [], timerPasso = null, ligada = false;

        function abrir() {
            if (!ligada) return;
            let rec;
            try { rec = new MediaRecorder(stream, Object.assign(mime ? { mimeType: mime } : {}, { videoBitsPerSecond: 700000, audioBitsPerSecond: 64000 })); }
            catch (e) { return; }
            const it = { rec, t0: performance.now(), chunks: [] };
            rec.ondataavailable = (e) => { if (e.data && e.data.size) it.chunks.push(e.data); };
            rec.onerror = () => fechar(it);
            try { rec.start(2000); } catch (e) { return; }
            it.timer = setTimeout(() => fechar(it), C.vida);
            itens.push(it);
        }
        function fechar(it) {
            clearTimeout(it.timer);
            itens = itens.filter(x => x !== it);
            try { if (it.rec.state !== 'inactive') it.rec.stop(); } catch (e) { /* já parado */ }
            it.chunks = [];
        }
        async function cortar() {
            const t = performance.now();
            const vivos = itens.filter(x => x.rec.state === 'recording' && t - x.t0 >= C.minMs);
            if (!vivos.length) return null;
            const it = vivos.reduce((a, b) => (a.t0 <= b.t0 ? a : b));
            await new Promise((ok) => {
                let feito = false; const f = () => { if (!feito) { feito = true; ok(); } };
                it.rec.addEventListener('dataavailable', f, { once: true });
                try { it.rec.requestData(); } catch (e) { f(); }
                setTimeout(f, 1500);
            });
            if (!it.chunks.length) return null;
            return { blob: new Blob(it.chunks, { type: 'video/webm' }), dur: (performance.now() - it.t0) / 1000 };
        }
        return {
            iniciar() { ligada = true; abrir(); timerPasso = setInterval(abrir, C.passo); },
            parar() { ligada = false; clearInterval(timerPasso); itens.slice().forEach(fechar); },
            cortar,
            idadeMs() { return itens.length ? performance.now() - Math.min(...itens.map(x => x.t0)) : 0; },
            info() { const t = performance.now(); return itens.map(x => ({ estado: x.rec.state, idadeMs: Math.round(t - x.t0), pedacos: x.chunks.length })); },
        };
    }

    // ------------------------------------------------------------------------------------------------------------------
    // cortar de verdade (sem ffmpeg): toca o trecho num <video> escondido e grava de novo. Leva o tempo do trecho.
    // ------------------------------------------------------------------------------------------------------------------
    async function medirDuracao(video, reserva) {
        if (isFinite(video.duration) && video.duration > 0) return video.duration;
        // webm do MediaRecorder não traz duração: pular pro "fim do mundo" faz o Chrome descobrir
        try {
            const mudou = esperar(video, 'durationchange', 2500);
            video.currentTime = 1e101;
            await mudou;
        } catch (e) { /* cai na reserva */ }
        const d = isFinite(video.duration) && video.duration > 0 ? video.duration : reserva;
        try { video.currentTime = 0; } catch (e) { /* ignora */ }
        return d;
    }

    async function cortarArquivo(blob, ini, fim, prog, abortar) {
        const url = URL.createObjectURL(blob);
        const v = document.createElement('video');
        v.playsInline = true; v.preload = 'auto'; v.src = url;
        let ac = null, rec = null;
        try {
            if (v.readyState < 2) await esperar(v, 'loadeddata', 8000);       // precisa de um quadro pronto pra desenhar
            const w = v.videoWidth || 854, h = v.videoHeight || 480;
            const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
            const g = cv.getContext('2d');
            ac = new (window.AudioContext || window.webkitAudioContext)();
            if (ac.state === 'suspended') await ac.resume().catch(() => {});
            const dest = ac.createMediaStreamDestination();
            ac.createMediaElementSource(v).connect(dest);          // o som vai pra gravação, não pra caixa de som
            const stream = new MediaStream([...cv.captureStream(25).getVideoTracks(), ...dest.stream.getAudioTracks()]);
            const mime = mimeEscolhido();
            rec = new MediaRecorder(stream, Object.assign(mime ? { mimeType: mime } : {}, { videoBitsPerSecond: 1000000, audioBitsPerSecond: 64000 }));
            const pedacos = [];
            rec.ondataavailable = (e) => { if (e.data && e.data.size) pedacos.push(e.data); };
            const parou = new Promise((ok) => { rec.onstop = ok; });
            if (Math.abs(v.currentTime - ini) > 0.02) {               // se já está lá, o navegador não dispara "seeked"
                v.currentTime = ini;
                await esperar(v, 'seeked', 5000);
            }
            g.drawImage(v, 0, 0, w, h);
            rec.start(500);
            await v.play();
            await new Promise((ok, falha) => {
                const t0 = performance.now();
                const iv = setInterval(() => {
                    g.drawImage(v, 0, 0, w, h);
                    const feito = Math.max(0, Math.min(1, (v.currentTime - ini) / Math.max(0.1, fim - ini)));
                    prog(feito, Math.max(0, v.currentTime - ini));
                    if (abortar()) { clearInterval(iv); falha(new Error('cancelado')); return; }
                    if (v.currentTime >= fim - 0.03 || v.ended || performance.now() - t0 > (fim - ini) * 1000 + 10000) { clearInterval(iv); ok(); }
                }, 40);
            });
            v.pause();
            rec.stop();
            await parou;
            const novo = new Blob(pedacos, { type: 'video/webm' });
            if (!novo.size) throw new Error('o corte saiu vazio');
            return novo;
        } finally {
            try { v.pause(); } catch (e) { /* ignora */ }
            try { if (rec && rec.state !== 'inactive') rec.stop(); } catch (e) { /* ignora */ }
            if (ac) ac.close().catch(() => {});
            v.removeAttribute('src'); try { v.load(); } catch (e) { /* ignora */ }
            URL.revokeObjectURL(url);
        }
    }

    // ------------------------------------------------------------------------------------------------------------------
    // sensor: lê o volume 20x por segundo e pergunta ao detector
    // ------------------------------------------------------------------------------------------------------------------
    function ligarSensor() {
        if (timerSensor || !emCall) return;
        detector.reiniciar();
        timerSensor = setInterval(() => {
            if (!emCall || !comp || !auto) return;
            const ev = detector.alimentar(performance.now(), comp.niveis());
            if (ev) aoMomento(ev);
        }, 50);
    }
    function desligarSensor() { if (timerSensor) { clearInterval(timerSensor); timerSensor = null; } }

    function aoMomento(ev) {
        if (capturando || !emCall || !janela) return;
        capturando = true;
        const foto = comp ? comp.foto() : null;
        setTimeout(async () => {
            try {
                const r = emCall && janela ? await janela.cortar() : null;
                if (r && emCall) novoClipe({ blob: r.blob, dur: r.dur, motivo: ev.motivo, auto: true, foto });
            } catch (e) { /* um clipe perdido não derruba a call */ }
            finally { capturando = false; }
        }, C.pos);
    }

    function novoClipe(d) {
        const c = armazem.adicionar({ blob: d.blob, dur: d.dur, durOriginal: d.dur, motivo: d.motivo, auto: !!d.auto, foto: d.foto || null, original: null, nuvem: null });
        if (d.visto) c.visto = true;
        pintarSinal(!d.visto ? c : null);
        entrando = c.id;                                          // se o pop-up já está aberto, o cartão novo entra com animação
        if (modal && modal.classList.contains('aberto') && vista === 'lista') pintarLista();
        entrando = null;
        return c;
    }

    // ------------------------------------------------------------------------------------------------------------------
    // o sinal (!) no canto da tela da call
    // ------------------------------------------------------------------------------------------------------------------
    function montarSinal() {
        if (sinal) return;
        const velha = document.getElementById('clip-gaveta');           // a gaveta antiga não existe mais
        if (velha) velha.remove();
        sinal = document.getElementById('clip-alerta');
        if (!sinal) {
            const vv = document.getElementById('video-view');
            if (!vv) return;
            sinal = document.createElement('div'); sinal.id = 'clip-alerta'; vv.appendChild(sinal);
        }
        sinal.className = 'clip-alerta';
        sinal.setAttribute('role', 'button'); sinal.setAttribute('tabindex', '0');
        sinal.setAttribute('aria-label', 'Clipes da call'); sinal.title = 'Clipes da call';
        sinal.innerHTML = '<i class="fa-solid fa-exclamation"></i><b class="cl-n" hidden></b><span class="cl-dica"></span>';
        sinal.addEventListener('click', (e) => { e.stopPropagation(); abrirModal(); });
        sinal.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); abrirModal(); } });
    }
    function pintarSinal(chegou) {
        if (!sinal) return;
        const total = armazem ? armazem.total() : 0, novos = armazem ? armazem.novos() : 0;
        sinal.classList.toggle('visivel', total > 0);
        sinal.classList.toggle('tem-novos', novos > 0);
        const n = sinal.querySelector('.cl-n');
        n.hidden = novos <= 0; n.textContent = novos > 9 ? '9+' : String(novos);
        sinal.title = novos ? `${novos} clipe${novos > 1 ? 's' : ''} novo${novos > 1 ? 's' : ''}` : 'Clipes da call';
        if (chegou) {
            const m = MOTIVOS[chegou.motivo] || MOTIVOS.pico;
            const dica = sinal.querySelector('.cl-dica');
            dica.textContent = 'Novo clipe · ' + m[1];
            sinal.classList.remove('chegou', 'dica'); void sinal.offsetWidth;      // reinicia a animação
            sinal.classList.add('chegou', 'dica');
            clearTimeout(timerDica);
            timerDica = setTimeout(() => sinal && sinal.classList.remove('chegou', 'dica'), C.sinalMs);
        }
    }

    // ------------------------------------------------------------------------------------------------------------------
    // o pop-up: lista de clipes <-> ver/cortar/mandar
    // ------------------------------------------------------------------------------------------------------------------
    function montarModal() {
        if (modal) return;
        modal = document.createElement('div');
        modal.id = 'clipes-modal'; modal.className = 'modal-overlay cl-overlay';
        modal.setAttribute('role', 'dialog'); modal.setAttribute('aria-modal', 'true'); modal.setAttribute('aria-label', 'Clipes da call');
        modal.innerHTML = `<div class="cl-caixa">
            <header class="cl-topo">
                <button type="button" class="cl-ic" data-cl="voltar" hidden aria-label="Voltar pros clipes" title="Voltar"><i class="fa-solid fa-arrow-left"></i></button>
                <div class="cl-titulos"><h2 id="cl-h">Clipes da call</h2><p id="cl-sub"></p></div>
                <button type="button" class="cl-ic" data-cl="fechar" aria-label="Fechar" title="Fechar"><i class="fa-solid fa-xmark"></i></button>
            </header>
            <section class="cl-lista" id="cl-lista">
                <div class="cl-opcoes">
                    <label class="cl-chave"><input type="checkbox" id="cl-auto"><span class="cl-trilho"></span><span>Clipe automático</span></label>
                    <div class="cl-seg" id="cl-sens" role="group" aria-label="Sensibilidade do clipe automático">
                        <span>Sensibilidade</span>
                        <button type="button" data-sens="baixa">Baixa</button><button type="button" data-sens="normal">Normal</button><button type="button" data-sens="alta">Alta</button>
                    </div>
                    <button type="button" class="cl-btn" data-cl="clipar"><i class="fa-solid fa-scissors"></i> Clipar agora</button>
                </div>
                <div class="cl-grade" id="cl-grade"></div>
            </section>
            <section class="cl-ver" id="cl-ver" hidden>
                <div class="cl-palco" id="cl-palco">
                    <video id="cl-video" playsinline></video>
                    <button type="button" class="cl-grande" data-cl="tocar" aria-label="Tocar ou pausar"><i class="fa-solid fa-play"></i></button>
                    <div class="cl-cortando" id="cl-cortando" hidden>
                        <div class="cl-giro"><i class="fa-solid fa-scissors"></i></div>
                        <b id="cl-cort-txt">Cortando...</b>
                        <div class="cl-prog"><i id="cl-cort-barra"></i></div>
                        <small>Cortar de verdade leva o tempo do trecho. Pode esperar aqui.</small>
                        <button type="button" class="cl-btn" data-cl="cancelar-corte">Cancelar</button>
                    </div>
                </div>
                <div class="cl-ctrl">
                    <button type="button" class="cl-ic" data-cl="tocar" aria-label="Tocar ou pausar" id="cl-tocar"><i class="fa-solid fa-play"></i></button>
                    <span class="cl-tempo" id="cl-tempo">0:00 / 0:00</span>
                    <button type="button" class="cl-ic" data-cl="mudo" aria-label="Som" id="cl-mudo"><i class="fa-solid fa-volume-high"></i></button>
                </div>
                <div class="cl-trilha" id="cl-trilha" aria-label="Linha do tempo do clipe">
                    <div class="cl-barra"></div><div class="cl-sel" id="cl-sel"></div><div class="cl-agulha" id="cl-agulha"></div>
                    <button type="button" class="cl-alca ini" id="cl-a-ini" role="slider" aria-label="Início do corte"></button>
                    <button type="button" class="cl-alca fim" id="cl-a-fim" role="slider" aria-label="Fim do corte"></button>
                </div>
                <div class="cl-tempos"><span>Início <b id="cl-t-ini">0:00</b></span><span>Trecho <b id="cl-t-dur">0:00</b></span><span>Fim <b id="cl-t-fim">0:00</b></span></div>
                <div class="cl-corte-acoes">
                    <button type="button" class="cl-btn" data-cl="ouvir-trecho"><i class="fa-solid fa-headphones"></i> Ouvir o trecho</button>
                    <button type="button" class="cl-btn" data-cl="cortar" id="cl-b-cortar"><i class="fa-solid fa-scissors"></i> Cortar o trecho</button>
                    <button type="button" class="cl-btn" data-cl="desfazer" id="cl-b-desfazer" hidden><i class="fa-solid fa-rotate-left"></i> Desfazer o corte</button>
                </div>
                <div class="cl-acoes">
                    <button type="button" class="cl-btn forte" data-cl="pessoa"><i class="fa-solid fa-paper-plane"></i> Mandar pra alguém</button>
                    <button type="button" class="cl-btn forte" data-cl="canal"><i class="fa-solid fa-hashtag"></i> Mandar no chat</button>
                    <button type="button" class="cl-btn forte" data-cl="baixar"><i class="fa-solid fa-download"></i> Baixar no PC</button>
                    <button type="button" class="cl-btn perigo" data-cl="apagar-aberto"><i class="fa-solid fa-trash"></i> Apagar</button>
                </div>
            </section>
                <div class="cl-sheet" id="cl-sheet" hidden>
                    <div class="cl-sheet-topo"><b id="cl-sheet-t"></b><button type="button" class="cl-ic" data-cl="sheet-fechar" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button></div>
                    <input type="search" id="cl-busca" class="cl-busca" placeholder="Procurar..." autocomplete="off" maxlength="40">
                    <div class="cl-sheet-lista" id="cl-sheet-lista"></div>
                    <small class="cl-sheet-nota" id="cl-sheet-nota"></small>
                </div>
        </div>`;
        document.body.appendChild(modal);

        modal.addEventListener('mousedown', (e) => { if (e.target === modal && !cortando) fecharModal(); });
        modal.addEventListener('click', aoClicar);
        modal.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                const card = e.target.closest && e.target.closest('.cl-card');
                if (card && e.target === card) { e.preventDefault(); abrirViewer(Number(card.dataset.id)); }
            }
        });
        $('#cl-auto').addEventListener('change', (e) => definirAuto(e.target.checked));
        $('#cl-sens').addEventListener('click', (e) => {
            const b = e.target.closest('[data-sens]'); if (!b) return;
            sens = b.dataset.sens; gravarPref(CH_SENS, sens); if (detector) detector.definirSensibilidade(sens); pintarOpcoes();
        });
        $('#cl-busca').addEventListener('input', pintarSheet);
        const video = $('#cl-video');
        video.addEventListener('timeupdate', aoTempo);
        video.addEventListener('play', pintarTocar); video.addEventListener('pause', pintarTocar); video.addEventListener('ended', pintarTocar);
        video.addEventListener('click', () => alternarTocar());
        // alças do corte
        ['ini', 'fim'].forEach(qual => {
            const a = $('#cl-a-' + qual);
            a.addEventListener('pointerdown', (e) => { e.preventDefault(); a.setPointerCapture(e.pointerId); arrasto = qual; a.classList.add('segurando'); });
            a.addEventListener('pointermove', (e) => { if (arrasto === qual) moverAlca(qual, e.clientX); });
            const solta = () => { arrasto = null; a.classList.remove('segurando'); };
            a.addEventListener('pointerup', solta); a.addEventListener('pointercancel', solta);
            a.addEventListener('keydown', (e) => {
                const passo = e.shiftKey ? 5 : 0.5;
                if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') { e.preventDefault(); ajustar(qual, -passo); }
                else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') { e.preventDefault(); ajustar(qual, passo); }
            });
        });
        $('#cl-trilha').addEventListener('pointerdown', (e) => {
            if (e.target.closest('.cl-alca') || !durAtual) return;
            const r = $('#cl-trilha').getBoundingClientRect();
            const t = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * durAtual;
            $('#cl-video').currentTime = Math.max(sel.ini, Math.min(sel.fim, t));
        });
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape' || !modal.classList.contains('aberto')) return;
            e.stopImmediatePropagation();
            if (sheet) { fecharSheet(); return; }
            if (vista === 'ver' && !cortando) { voltarLista(); return; }
            if (!cortando) fecharModal();
        }, true);
    }

    function abrirModal() {
        if (!emCall || !armazem) return;
        montarModal();
        modal.style.display = 'flex'; void modal.offsetWidth; modal.classList.add('aberto');
        vista = 'lista'; mostrarVista();
        pintarOpcoes(); pintarLista();
        const x = $('[data-cl="fechar"]'); if (x) x.focus({ preventScroll: true });
    }
    function fecharModal() {
        if (!modal) return;
        if (cortando) cortando.abortar = true;
        soltarVideo(); fecharSheet();
        modal.classList.remove('aberto'); modal.style.display = 'none';
        vista = 'lista'; abertoId = null;
    }
    function mostrarVista() {
        $('#cl-lista').hidden = vista !== 'lista';
        $('#cl-ver').hidden = vista !== 'ver';
        $('[data-cl="voltar"]').hidden = vista !== 'ver';
        $('#cl-h').textContent = vista === 'lista' ? 'Clipes da call' : (MOTIVOS[(armazem.obter(abertoId) || {}).motivo] || MOTIVOS.pico)[1];
        $('#cl-sub').textContent = vista === 'lista'
            ? 'Cada clipe some em 20 minutos e todos somem quando a call acaba. Ficam só no seu navegador.'
            : 'Corte o trecho que quiser, depois mande ou baixe.';
    }
    function pintarOpcoes() {
        if (!modal) return;
        $('#cl-auto').checked = auto;
        modal.querySelectorAll('#cl-sens [data-sens]').forEach(b => b.classList.toggle('ativo', b.dataset.sens === sens));
        $('#cl-sens').classList.toggle('desligado', !auto);
    }

    function htmlCard(c, i) {
        const m = MOTIVOS[c.motivo] || MOTIVOS.pico;
        const estado = c.acoes.length ? 'feito' : (c.visto ? 'visto' : 'novo');
        const chip = estado === 'novo' ? '<span class="cl-chip novo"><i></i>Novo</span>'
            : estado === 'visto' ? '<span class="cl-chip visto"><i class="fa-solid fa-eye"></i> Visto</span>'
            : `<span class="cl-chip feito"><i class="fa-solid fa-check"></i> ${T(ACAO_ROTULO(c))}</span>`;
        const foto = c.foto && /^data:image\/jpeg;base64,[A-Za-z0-9+/=]+$/.test(c.foto) ? `<img src="${c.foto}" alt="">` : '<i class="cl-sem-foto fa-solid fa-film"></i>';
        return `<div class="cl-card ${estado}${destacar === c.id ? ' cl-destaca' : ''}${entrando === c.id ? ' cl-chegou' : ''}" data-id="${c.id}" style="--i:${i}" tabindex="0" role="button" aria-label="Abrir clipe: ${T(m[1])} às ${horaDe(c.criadoEm)}">
            <div class="cl-thumb">${foto}<span class="cl-dur">${fmt(c.dur)}</span><span class="cl-play"><i class="fa-solid fa-play"></i></span>${chip}</div>
            <div class="cl-info"><b><i class="fa-solid fa-${m[0]}"></i> ${T(m[1])}</b><small>${c.auto ? 'Automático' : 'Manual'} · às ${horaDe(c.criadoEm)} · some em <span data-vida>${restanteTxt(armazem.restante(c))}</span></small></div>
            <div class="cl-vida"><i style="transform:scaleX(${armazem.fracao(c).toFixed(3)})"></i></div>
            <button type="button" class="cl-apaga" data-cl="apagar" aria-label="Apagar este clipe" title="Apagar"><i class="fa-solid fa-trash"></i></button>
        </div>`;
    }
    function pintarLista() {
        if (!modal || !armazem) return;
        const lista = armazem.listar();
        const grade = $('#cl-grade');
        grade.innerHTML = lista.length
            ? lista.map(htmlCard).join('')
            : `<div class="cl-vazio"><i class="fa-solid fa-film"></i><b>Nenhum clipe por enquanto</b><span>${auto ? 'Quando a call esquentar (risada, empolgação, todo mundo falando junto) eu guardo o momento aqui.' : 'O clipe automático está desligado. Ligue lá em cima ou use "Clipar agora".'}</span></div>`;
        const novos = armazem.novos();
        $('#cl-sub').textContent = vista === 'lista'
            ? (lista.length ? `${lista.length} clipe${lista.length > 1 ? 's' : ''}${novos ? ` · ${novos} novo${novos > 1 ? 's' : ''}` : ' · todos vistos'}. Cada um some em 20 minutos; todos somem quando a call acaba.` : 'Cada clipe some em 20 minutos e todos somem quando a call acaba. Ficam só no seu navegador.')
            : $('#cl-sub').textContent;
        destacar = null; entrando = null;
    }
    function pintarVidas() {
        if (!modal || !armazem || vista !== 'lista') return;
        modal.querySelectorAll('.cl-card').forEach(card => {
            const c = armazem.obter(Number(card.dataset.id)); if (!c) return;
            const v = card.querySelector('[data-vida]'); if (v) v.textContent = restanteTxt(armazem.restante(c));
            const b = card.querySelector('.cl-vida i'); if (b) b.style.transform = `scaleX(${armazem.fracao(c).toFixed(3)})`;
        });
    }

    function aoClicar(e) {
        const alvo = e.target.closest('[data-cl]');
        if (alvo) {
            const a = alvo.dataset.cl;
            if (a === 'fechar') return fecharModal();
            if (a === 'voltar') return voltarLista();
            if (a === 'clipar') return clipar();
            if (a === 'apagar') { e.stopPropagation(); const card = alvo.closest('.cl-card'); if (card) apagarClipe(Number(card.dataset.id)); return; }
            if (a === 'tocar') return alternarTocar();
            if (a === 'mudo') { const v = $('#cl-video'); v.muted = !v.muted; $('#cl-mudo').innerHTML = `<i class="fa-solid fa-volume-${v.muted ? 'xmark' : 'high'}"></i>`; return; }
            if (a === 'ouvir-trecho') return ouvirTrecho();
            if (a === 'cortar') return cortarSelecao();
            if (a === 'cancelar-corte') { if (cortando) cortando.abortar = true; return; }
            if (a === 'desfazer') return desfazerCorte();
            if (a === 'pessoa') return abrirSheet('pessoas');
            if (a === 'canal') return abrirSheet('canais');
            if (a === 'baixar') return baixar();
            if (a === 'apagar-aberto') return apagarClipe(abertoId, true);
            if (a === 'sheet-fechar') return fecharSheet();
            if (a === 'mandar') return mandarPara(alvo.dataset.tipo, Number(alvo.dataset.alvo), alvo.dataset.nome || '');
        }
        const card = e.target.closest('.cl-card');
        if (card) abrirViewer(Number(card.dataset.id));
    }

    function apagarClipe(id, voltar) {
        if (id == null || !armazem) return;
        if (voltar) { soltarVideo(); fecharSheet(); }
        armazem.remover(id, 'apagado');
        pintarSinal();
        if (voltar) { vista = 'lista'; abertoId = null; mostrarVista(); }
        if (modal && modal.classList.contains('aberto') && vista === 'lista') pintarLista();
    }

    // ---- ver / cortar ----
    function soltarVideo() {
        const v = modal && $('#cl-video');
        if (v) { try { v.pause(); } catch (e) { /* ignora */ } v.removeAttribute('src'); try { v.load(); } catch (e) { /* ignora */ } }
        if (urlAberto) { URL.revokeObjectURL(urlAberto); urlAberto = null; }
    }
    async function carregarNoVideo(c, tocar) {
        soltarVideo();
        const v = $('#cl-video');
        urlAberto = URL.createObjectURL(c.blob);
        v.src = urlAberto; v.muted = false;
        try { await esperar(v, 'loadedmetadata', 8000); } catch (e) { ctx.toast('Não consegui abrir esse clipe.', 'error'); return; }
        durAtual = await medirDuracao(v, c.dur);
        c.dur = durAtual;
        sel = { ini: 0, fim: durAtual };
        pintarTrilha(); pintarTocar();
        if (tocar) v.play().catch(() => {});
    }
    async function abrirViewer(id) {
        const c = armazem && armazem.obter(id);
        if (!c) return;
        armazem.marcarVisto(id);
        pintarSinal();
        abertoId = id; vista = 'ver';
        mostrarVista();
        $('#cl-cortando').hidden = true;
        $('#cl-b-desfazer').hidden = !c.original;
        fecharSheet();
        await carregarNoVideo(c, true);
        const b = $('[data-cl="voltar"]'); if (b) b.focus({ preventScroll: true });
    }
    function voltarLista(destaque) {
        if (cortando) return;
        soltarVideo(); fecharSheet();
        vista = 'lista'; abertoId = null;
        mostrarVista();
        destacar = destaque || null;
        const grade = $('#cl-grade'); grade.classList.remove('cl-volta'); void grade.offsetWidth; grade.classList.add('cl-volta');
        pintarLista();
        pintarOpcoes();
    }
    function alternarTocar() {
        const v = $('#cl-video'); if (!v.src) return;
        if (v.paused) {
            if (v.currentTime < sel.ini - 0.05 || v.currentTime >= sel.fim - 0.05) v.currentTime = sel.ini;
            v.play().catch(() => {});
        } else v.pause();
    }
    function ouvirTrecho() { const v = $('#cl-video'); v.currentTime = sel.ini; v.play().catch(() => {}); }
    function aoTempo() {
        const v = $('#cl-video');
        if (!v.paused && sel.fim < durAtual - 0.05 && v.currentTime >= sel.fim) { v.pause(); v.currentTime = sel.ini; }
        pintarAgulha();
    }
    function pintarTocar() {
        const v = $('#cl-video'); if (!v) return;
        const toca = !v.paused && !v.ended;
        $('#cl-tocar').innerHTML = `<i class="fa-solid fa-${toca ? 'pause' : 'play'}"></i>`;
        $('#cl-palco').classList.toggle('tocando', toca);
        $('.cl-grande i').className = `fa-solid fa-${toca ? 'pause' : 'play'}`;
        pintarAgulha();
    }
    function pintarAgulha() {
        const v = $('#cl-video'); if (!v || !durAtual) return;
        const p = Math.max(0, Math.min(1, v.currentTime / durAtual));
        $('#cl-agulha').style.left = (p * 100) + '%';
        $('#cl-tempo').textContent = `${fmt(v.currentTime)} / ${fmt(durAtual)}`;
    }
    function selecaoCheia() { return sel.ini <= 0.15 && sel.fim >= durAtual - 0.15; }
    function pintarTrilha() {
        if (!durAtual) return;
        const a = (sel.ini / durAtual) * 100, b = (sel.fim / durAtual) * 100;
        $('#cl-sel').style.left = a + '%'; $('#cl-sel').style.width = Math.max(0, b - a) + '%';
        $('#cl-a-ini').style.left = a + '%'; $('#cl-a-fim').style.left = b + '%';
        $('#cl-a-ini').setAttribute('aria-valuenow', sel.ini.toFixed(1)); $('#cl-a-fim').setAttribute('aria-valuenow', sel.fim.toFixed(1));
        $('#cl-a-ini').setAttribute('aria-valuemin', '0'); $('#cl-a-ini').setAttribute('aria-valuemax', durAtual.toFixed(1));
        $('#cl-a-fim').setAttribute('aria-valuemin', '0'); $('#cl-a-fim').setAttribute('aria-valuemax', durAtual.toFixed(1));
        $('#cl-t-ini').textContent = fmt(sel.ini); $('#cl-t-fim').textContent = fmt(sel.fim); $('#cl-t-dur').textContent = fmt(sel.fim - sel.ini);
        const cheia = selecaoCheia();
        $('#cl-b-cortar').disabled = cheia;
        $('#cl-b-cortar').innerHTML = cheia ? '<i class="fa-solid fa-scissors"></i> Cortar o trecho' : `<i class="fa-solid fa-scissors"></i> Cortar o trecho (leva ~${Math.max(1, Math.round(sel.fim - sel.ini))} s)`;
        pintarAgulha();
    }
    function moverAlca(qual, clientX) {
        const r = $('#cl-trilha').getBoundingClientRect();
        const t = Math.max(0, Math.min(1, (clientX - r.left) / r.width)) * durAtual;
        definirAlca(qual, t);
    }
    function ajustar(qual, d) { definirAlca(qual, (qual === 'ini' ? sel.ini : sel.fim) + d); }
    function definirAlca(qual, t) {
        const MIN = 1;                                               // trecho de pelo menos 1 s
        if (qual === 'ini') sel.ini = Math.max(0, Math.min(t, sel.fim - MIN));
        else sel.fim = Math.min(durAtual, Math.max(t, sel.ini + MIN));
        const v = $('#cl-video');
        v.currentTime = qual === 'ini' ? sel.ini : Math.max(sel.ini, sel.fim - 0.4);
        pintarTrilha();
    }

    async function cortarSelecao() {
        const c = armazem.obter(abertoId);
        if (!c || cortando || selecaoCheia()) return false;
        const ini = sel.ini, fim = sel.fim;
        $('#cl-video').pause();
        cortando = { abortar: false };
        $('#cl-cortando').hidden = false;
        $('#cl-cort-txt').textContent = 'Cortando... 0 de ' + Math.round(fim - ini) + ' s';
        $('#cl-cort-barra').style.transform = 'scaleX(0)';
        const estado = cortando;
        try {
            const novo = await cortarArquivo(c.blob, ini, fim, (p, t) => {
                $('#cl-cort-barra').style.transform = `scaleX(${p.toFixed(3)})`;
                $('#cl-cort-txt').textContent = `Cortando... ${Math.round(t)} de ${Math.round(fim - ini)} s`;
            }, () => estado.abortar);
            if (!armazem.obter(c.id)) return false;                  // o clipe sumiu (venceu, call acabou) durante o corte
            if (!c.original) c.original = c.blob;
            c.blob = novo; c.dur = fim - ini; c.nuvem = null;
            $('#cl-b-desfazer').hidden = false;
            cortando = null; $('#cl-cortando').hidden = true;
            await carregarNoVideo(c, false);
            ctx.toast('Corte feito!', 'success');
            return true;
        } catch (err) {
            if (String(err && err.message) !== 'cancelado') ctx.toast('Não consegui cortar: ' + (err && err.message ? err.message : 'erro'), 'error');
            return false;
        } finally {
            cortando = null;
            if (modal) $('#cl-cortando').hidden = true;
        }
    }
    async function desfazerCorte() {
        const c = armazem.obter(abertoId);
        if (!c || !c.original || cortando) return;
        c.blob = c.original; c.original = null; c.dur = c.durOriginal; c.nuvem = null;
        $('#cl-b-desfazer').hidden = true;
        await carregarNoVideo(c, false);
    }
    // antes de mandar/baixar, o trecho escolhido (se não for o clipe inteiro) vira o arquivo
    async function prepararArquivo() {
        const c = armazem.obter(abertoId);
        if (!c) return null;
        if (!selecaoCheia()) { const ok = await cortarSelecao(); if (!ok) return null; }
        return armazem.obter(abertoId);
    }

    // ---- destinos ----
    function abrirSheet(modo) {
        sheet = modo;
        $('#cl-sheet').hidden = false;
        $('#cl-sheet-t').textContent = modo === 'pessoas' ? 'Mandar pra quem?' : 'Mandar em qual chat?';
        $('#cl-busca').value = '';
        pintarSheet();
        if (!window.matchMedia('(pointer: coarse)').matches) $('#cl-busca').focus({ preventScroll: true });   // no celular o teclado não abre sozinho
    }
    function fecharSheet() { sheet = null; if (modal) $('#cl-sheet').hidden = true; }
    function pintarSheet() {
        if (!sheet) return;
        const q = ($('#cl-busca').value || '').trim().toLowerCase();
        const lista = $('#cl-sheet-lista'), nota = $('#cl-sheet-nota');
        if (sheet === 'pessoas') {
            const dest = ctx.destinoDaCall() || {};
            let amigos = (ctx.amigos() || []).filter(a => !q || String(a.nome || '').toLowerCase().includes(q));
            amigos = amigos.slice().sort((a, b) => (Number(b.id) === dest.amigo) - (Number(a.id) === dest.amigo) || (b.online ? 1 : 0) - (a.online ? 1 : 0) || String(a.nome || '').localeCompare(String(b.nome || '')));
            lista.innerHTML = amigos.length ? amigos.map(a => {
                const av = ctx.escUrl(a.avatar);
                return `<div class="cl-linha"><span class="cl-av">${av ? `<img src="${av}" alt="">` : T(String(a.nome || '?').charAt(0).toUpperCase())}${a.online ? '<i class="on"></i>' : ''}</span>
                    <span class="cl-nome">${T(a.nome)}${Number(a.id) === dest.amigo ? ' <small>(está na call)</small>' : ''}</span>
                    <button type="button" class="cl-btn forte" data-cl="mandar" data-tipo="dm" data-alvo="${Number(a.id)}" data-nome="${T(a.nome)}">Mandar</button></div>`;
            }).join('') : '<div class="cl-vazio pequeno"><span>Nenhum amigo encontrado.</span></div>';
            nota.textContent = 'O clipe chega na conversa dela como uma mensagem com vídeo.';
        } else {
            const grupos = (ctx.canais() || []).map(g => ({ servidor: g.servidor, canais: g.canais.filter(c => !q || String(c.name || '').toLowerCase().includes(q)) })).filter(g => g.canais.length);
            lista.innerHTML = grupos.length ? grupos.map(g => `<div class="cl-grupo">${T(g.servidor)}</div>` + g.canais.map(c =>
                `<div class="cl-linha"><span class="cl-av canal"><i class="fa-solid fa-hashtag"></i></span><span class="cl-nome">${T(c.name)}</span>
                    <button type="button" class="cl-btn forte" data-cl="mandar" data-tipo="canal" data-alvo="${Number(c.id)}" data-nome="${T(c.name)}">Mandar</button></div>`).join('')).join('')
                : '<div class="cl-vazio pequeno"><span>Nenhum canal de texto encontrado.</span></div>';
            nota.textContent = 'Só aparecem canais onde dá pra mandar vídeo. Se você não tiver permissão, o servidor avisa.';
        }
    }

    async function subirParaNuvem(c) {
        if (c.nuvem) return c.nuvem;
        if (c.blob.size > LIMITE_MB * 1024 * 1024) throw new Error(`O clipe tem ${(c.blob.size / 1048576).toFixed(1)} MB e o limite é ${LIMITE_MB} MB. Corte um trecho menor.`);
        const arq = new File([c.blob], `clipe-${Date.now()}.webm`, { type: 'video/webm' });
        c.nuvem = await ctx.upload(arq);
        return c.nuvem;
    }
    async function mandarPara(tipo, alvo, nome) {
        if (!alvo || (tipo !== 'dm' && tipo !== 'canal')) return;
        const botoes = modal.querySelectorAll('.cl-sheet-lista button'); botoes.forEach(b => { b.disabled = true; });
        const clicado = Array.from(botoes).find(b => Number(b.dataset.alvo) === alvo && b.dataset.tipo === tipo);
        if (clicado) clicado.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Enviando';
        try {
            const c = await prepararArquivo();
            if (!c) { botoes.forEach(b => { b.disabled = false; }); pintarSheet(); return; }
            const up = await subirParaNuvem(c);
            const dados = { texto: '', anexo_url: up.url, anexo_tipo: up.tipo || 'video', anexo_nome: up.nome || 'clipe.webm' };
            if (tipo === 'dm') ctx.enviarDM(alvo, dados); else ctx.enviarCanal(alvo, dados);
            c.acoes.push({ tipo, alvo: nome, em: Date.now() });
            ctx.toast(tipo === 'dm' ? `Clipe mandado pra ${nome}!` : `Clipe mandado em #${nome}!`, 'success');
            voltarLista(c.id);
        } catch (err) {
            ctx.toast(err && err.message ? err.message : 'Não consegui mandar o clipe.', 'error');
            botoes.forEach(b => { b.disabled = false; }); pintarSheet();
        }
    }
    async function baixar() {
        const c = await prepararArquivo();
        if (!c) return;
        const d = new Date(), z = (n) => String(n).padStart(2, '0');
        const a = document.createElement('a');
        a.href = URL.createObjectURL(c.blob);
        a.download = `pantheon-clipe-${d.getFullYear()}${z(d.getMonth() + 1)}${z(d.getDate())}-${z(d.getHours())}${z(d.getMinutes())}${z(d.getSeconds())}.webm`;
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 4000);
        c.acoes.push({ tipo: 'pc', alvo: 'PC', em: Date.now() });
        ctx.toast('Clipe baixado!', 'success');
        voltarLista(c.id);
    }

    // ------------------------------------------------------------------------------------------------------------------
    // clipe manual, ligar/desligar o automático e ciclo de vida da call
    // ------------------------------------------------------------------------------------------------------------------
    async function clipar() {
        if (!emCall || !janela) { ctx.toast('Entre numa call pra clipar.', 'warning'); return; }
        const r = await janela.cortar();
        if (!r) { ctx.toast('Ainda estou juntando os primeiros segundos da call. Espere um pouquinho.', 'warning'); return; }
        const c = novoClipe({ blob: r.blob, dur: r.dur, motivo: 'manual', auto: false, foto: comp ? comp.foto() : null, visto: true });
        if (!modal || !modal.classList.contains('aberto')) abrirModal();
        abrirViewer(c.id);
    }
    function definirAuto(on, silencioso) {
        auto = !!on;
        gravarPref(CH_AUTO, auto ? '1' : '0');
        if (auto && emCall) ligarSensor(); else desligarSensor();
        if (ctx.aoMudarAuto) ctx.aoMudarAuto(auto);
        if (modal) { pintarOpcoes(); if (vista === 'lista') pintarLista(); }
        if (!silencioso) ctx.toast(auto ? 'Clipe automático ligado.' : 'Clipe automático desligado.', 'info');
    }

    function aoEntrarNaCall() {
        if (emCall) return;
        if (!window.MediaRecorder || !(window.AudioContext || window.webkitAudioContext)) {
            if (!avisouSemSuporte) { avisouSemSuporte = true; ctx.toast('Seu navegador não sabe guardar clipes da call (tente pelo Chrome ou Edge).', 'warning'); }
            return;
        }
        try { comp = criarComp(); } catch (e) { comp = null; return; }
        janela = criarJanela(comp.stream);
        armazem = ClipesArmazem.criar({ ttlMs: C.ttl, aoSair: (c) => { c.blob = c.original = null; c.nuvem = null; if (abertoId === c.id) { soltarVideo(); vista = 'lista'; abertoId = null; if (modal) mostrarVista(); } } });
        sens = lerPref(CH_SENS, 'normal'); if (!ClipesDetector.SENS[sens]) sens = 'normal';
        auto = lerPref(CH_AUTO, '1') !== '0';
        detector = ClipesDetector.criar({ sensibilidade: sens });
        emCall = true; capturando = false;
        montarSinal();
        janela.iniciar();
        timerSync = setInterval(() => { if (comp) comp.sincronizar(); }, 1500);
        timerVarre = setInterval(varrer, 5000);
        if (ctx.aoMudarAuto) ctx.aoMudarAuto(auto);
        if (auto) ligarSensor();
        pintarSinal();
    }
    function varrer() {
        if (!armazem) return;
        const saiu = armazem.varrer();
        if (saiu.length) { pintarSinal(); if (modal && modal.classList.contains('aberto') && vista === 'lista') pintarLista(); }
        else pintarVidas();
    }
    function aoSairDaCall() {
        desligarSensor();
        clearInterval(timerSync); clearInterval(timerVarre); clearTimeout(timerDica); timerSync = timerVarre = timerDica = null;
        if (cortando) cortando.abortar = true;
        emCall = false;
        if (modal) fecharModal();
        if (janela) { janela.parar(); janela = null; }
        if (comp) { comp.parar(); comp = null; }
        if (armazem) { armazem.limpar('fim'); }
        if (modal) { const gr = $('#cl-grade'); if (gr) gr.innerHTML = ''; }
        if (sinal) { sinal.classList.remove('visivel', 'tem-novos', 'chegou', 'dica'); }
        capturando = false;
    }

    function iniciar(contexto) {
        ctx = contexto;
        montarSinal();
    }

    return {
        iniciar, aoEntrarNaCall, aoSairDaCall, clipar, definirAuto, abrir: abrirModal,
        automatico: () => auto,
        // ganchos só pra teste no navegador
        _cfg: (o) => Object.assign(C, o || {}),
        _forcar: (motivo) => aoMomento({ motivo: motivo || 'pico', t: performance.now(), pontos: 9 }),
        _estado: () => ({ emCall, auto, sens, total: armazem ? armazem.total() : 0, novos: armazem ? armazem.novos() : 0, idadeMs: janela ? janela.idadeMs() : 0, detector: detector ? detector.estado() : null }),
        _cortarArquivo: cortarArquivo,
        _gravadores: () => (janela ? janela.info() : []),
    };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = { ClipesDetector, ClipesArmazem };
