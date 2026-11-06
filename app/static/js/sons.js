/* Sons da call (Rodada 39): som de entrada pronto ou do acervo da pessoa, e os sons do soundboard. Objeto global `Sons`.
 *
 * Valores (os mesmos que o servidor guarda e repassa, app/acervo.py):  'preset:<id>' (um dos prontos, sintetizados aqui, sem arquivo)  ·  'custom:<id do acervo>'
 * (arquivo do acervo, buscado em /api/acervo/<id>/arquivo e decodificado uma vez).
 * Tudo que toca por aqui passa por um LIMITADOR (compressor) e por um corte de 6 s: som de OUTRA pessoa nunca estoura o ouvido nem toca pra sempre,
 * mesmo que o arquivo seja alto ou comprido. O volume final é o dos sons do app (Configurações > Voz e vídeo > Sons).
 *
 * Contexto (Sons.iniciar): { audioCtx(): o AudioContext do app (pode estar suspenso: o Sons o acorda), volume(): 0..1, aoBloquear?(): o navegador segurou o som }
 * Soundboard: `precarregar(ids)` baixa e decodifica os sons antes do toque; `tocarItem(id, vol, {expira})` toca do cache na hora (ver soundboard_aquecer em acervo_events.py).
 */
const Sons = (() => {
    'use strict';
    const MAX_S = 6;
    let C = { audioCtx: () => null, volume: () => 1 };
    const buffers = new Map();       // id do acervo -> Promise<AudioBuffer>

    // ---------------------------------------------------------------------
    // os prontos (sintetizados)
    // ---------------------------------------------------------------------
    const PRESETS = [
        { id: 'sino', nome: 'Sino', emoji: '🔔' }, { id: 'moeda', nome: 'Moeda', emoji: '🪙' }, { id: 'gota', nome: 'Gota', emoji: '💧' },
        { id: 'arpejo', nome: 'Harpa', emoji: '🎶' }, { id: 'laser', nome: 'Laser', emoji: '🔫' }, { id: 'tambor', nome: 'Tambor', emoji: '🥁' },
        { id: 'aplauso', nome: 'Aplauso', emoji: '👏' }, { id: 'boasvindas', nome: 'Boas-vindas', emoji: '🎺' }, { id: 'pop', nome: 'Pop', emoji: '🫧' },
        { id: 'teclado', nome: 'Teclado', emoji: '⌨️' },
    ];
    function nota(ac, saida, t0, f, ini, dur, vol, tipo, f2) {
        const o = ac.createOscillator(), g = ac.createGain(), t = t0 + ini;
        o.type = tipo || 'sine'; o.frequency.setValueAtTime(f, t);
        if (f2) o.frequency.exponentialRampToValueAtTime(f2, t + dur);
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(Math.max(.001, vol), t + Math.min(.015, dur / 3)); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        o.connect(g); g.connect(saida); o.start(t); o.stop(t + dur + .03);
    }
    function ruido(ac, saida, t0, ini, dur, filtro, f, vol, q) {
        const len = Math.max(1, Math.floor(ac.sampleRate * (dur + .03))), buf = ac.createBuffer(1, len, ac.sampleRate), d = buf.getChannelData(0);
        for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
        const s = ac.createBufferSource(), fl = ac.createBiquadFilter(), g = ac.createGain(), t = t0 + ini;
        s.buffer = buf; fl.type = filtro; fl.frequency.value = f; fl.Q.value = q || 1;
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(Math.max(.001, vol), t + .004); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        s.connect(fl); fl.connect(g); g.connect(saida); s.start(t); s.stop(t + dur + .03);
    }
    const SINT = {
        sino: (ac, s, t) => { [[880, .5], [1760, .25], [2637, .15]].forEach(([f, v]) => nota(ac, s, t, f, 0, 1.3, v)); return 1.4; },
        moeda: (ac, s, t) => { nota(ac, s, t, 988, 0, .08, .35, 'square'); nota(ac, s, t, 1319, .08, .45, .35, 'square'); return .6; },
        gota: (ac, s, t) => { nota(ac, s, t, 1300, 0, .16, .6, 'sine', 320); nota(ac, s, t, 700, .2, .12, .25, 'sine', 240); return .5; },
        arpejo: (ac, s, t) => { [523.25, 659.25, 783.99, 1046.5, 1318.5].forEach((f, i) => nota(ac, s, t, f, i * .09, .5, .35, 'triangle')); return 1; },
        laser: (ac, s, t) => { nota(ac, s, t, 2200, 0, .28, .3, 'sawtooth', 160); nota(ac, s, t, 1100, .02, .22, .2, 'square', 90); return .4; },
        tambor: (ac, s, t) => { nota(ac, s, t, 170, 0, .3, .9, 'sine', 48); ruido(ac, s, t, 0, .14, 'lowpass', 900, .5); nota(ac, s, t, 150, .28, .3, .8, 'sine', 45); return .7; },
        aplauso: (ac, s, t) => { for (let i = 0; i < 22; i++) ruido(ac, s, t, Math.random() * .9, .012 + Math.random() * .03, 'bandpass', 1400 + Math.random() * 1600, .45, 1.2); return 1.1; },
        boasvindas: (ac, s, t) => { [[523.25, 0], [659.25, .13], [783.99, .26]].forEach(([f, i]) => nota(ac, s, t, f, i, .22, .4, 'triangle')); [783.99, 1046.5, 1318.5].forEach(f => nota(ac, s, t, f, .42, .7, .28, 'triangle')); return 1.2; },
        pop: (ac, s, t) => { nota(ac, s, t, 260, 0, .09, .7, 'sine', 950); ruido(ac, s, t, .07, .03, 'highpass', 3000, .25); return .2; },
        teclado: (ac, s, t) => { let x = 0; for (let i = 0; i < 7; i++) { ruido(ac, s, t, x, .035, 'highpass', 3200, .5, 2); x += .05 + Math.random() * .05; } return .8; },
    };

    // ---------------------------------------------------------------------
    // reprodução
    // ---------------------------------------------------------------------
    /** Cadeia final: ganho do usuário -> limitador. Devolve o nó onde ligar a fonte. */
    function cadeia(ac, volume) {
        const g = ac.createGain(); g.gain.value = Math.max(0, Math.min(1, volume));
        const lim = ac.createDynamicsCompressor();
        lim.threshold.value = -18; lim.knee.value = 10; lim.ratio.value = 14; lim.attack.value = .002; lim.release.value = .2;
        g.connect(lim); lim.connect(ac.destination);
        return g;
    }
    // Cada som do acervo é baixado e DECODIFICADO uma vez só; depois toca do cache na hora. O atraso que o soundboard tinha vinha daqui: o ouvinte só baixava
    // o arquivo (e o decodificava) no instante do primeiro toque, e o contexto de áudio suspenso engolia o toque. Agora quem abre o soundboard avisa a call
    // (`soundboard_aquecer`) e todo mundo já tem os sons prontos (`precarregar`), e o toque espera o contexto acordar em vez de se perder.
    const MAX_BUFFERS = 80;
    const prontos = new Map();       // id -> AudioBuffer já decodificado (toque síncrono)
    const fila = [];                 // ids esperando pra serem pré-carregados
    let bombeando = false;
    function buffer(ac, id) {
        id = Number(id);
        if (!buffers.has(id)) {
            const p = fetch(`/api/acervo/${id}/arquivo`, { credentials: 'same-origin', priority: 'low' })
                .then(r => { if (!r.ok) throw new Error('arquivo'); return r.arrayBuffer(); })
                .then(b => new Promise((ok, no) => ac.decodeAudioData(b, ok, no)));
            p.then(buf => { prontos.set(id, buf); }, () => { buffers.delete(id); prontos.delete(id); });
            buffers.set(id, p);
            while (buffers.size > MAX_BUFFERS) { const velho = buffers.keys().next().value; buffers.delete(velho); prontos.delete(velho); }
        }
        return buffers.get(id);
    }
    /** Baixa e decodifica esses sons em segundo plano, um de cada vez (decodeAudioData funciona mesmo com o contexto suspenso). */
    function precarregar(ids) {
        const ac = C.audioCtx(); if (!ac || !Array.isArray(ids)) return;
        ids.slice(0, 40).forEach(i => { const id = Number(i); if (id > 0 && !buffers.has(id) && !fila.includes(id)) fila.push(id); });
        if (bombeando) return;
        bombeando = true;
        (async () => {
            while (fila.length) {
                const id = fila.shift();
                try { await buffer(C.audioCtx(), id); } catch (e) { /* arquivo sumiu: o toque trata */ }
                await new Promise(r => setTimeout(r, 40));
            }
            bombeando = false;
        })();
    }
    /** Acorda o contexto (política de autoplay) e espera um instante: antes o toque que chegava com o contexto ainda "suspended" era descartado em silêncio. */
    function acordar(ac) {
        if (ac.state === 'running') return Promise.resolve(true);
        let p; try { p = ac.resume(); } catch (e) { p = null; }
        return Promise.race([Promise.resolve(p).catch(() => {}), new Promise(r => setTimeout(r, 450))]).then(() => ac.state === 'running');
    }
    let esperandoGesto = false;
    function bloqueado(ac) {
        if (C.aoBloquear) C.aoBloquear();
        if (esperandoGesto) return;
        esperandoGesto = true;
        const volta = () => { esperandoGesto = false; ['pointerdown', 'keydown', 'touchend'].forEach(e => document.removeEventListener(e, volta, true)); try { ac.resume(); } catch (e) {} };
        ['pointerdown', 'keydown', 'touchend'].forEach(e => document.addEventListener(e, volta, true));
    }
    function tocarBuffer(ac, buf, vol) {
        const src = ac.createBufferSource(); src.buffer = buf;
        src.connect(cadeia(ac, vol != null ? vol : C.volume()));
        src.start(); src.stop(ac.currentTime + Math.min(MAX_S, buf.duration + .05));      // nunca passa de 6 s, seja qual for o arquivo
    }
    /** Toca um valor ('preset:x' | 'custom:id'). Devolve true se começou (ou vai começar). `volume` opcional (0..1); sem ele vale o dos sons do app. */
    function tocar(valor, volume) {
        const ac = C.audioCtx(); if (!ac || typeof valor !== 'string') return false;
        const vol = volume != null ? volume : C.volume();
        if (vol <= 0) return false;
        let m = /^preset:([a-z]+)$/.exec(valor);
        if (m && SINT[m[1]]) {
            const f = SINT[m[1]];
            if (ac.state === 'running') { f(ac, cadeia(ac, vol * .9), ac.currentTime + .005); return true; }
            acordar(ac).then(ok => { if (ok) f(ac, cadeia(ac, vol * .9), ac.currentTime + .005); else bloqueado(ac); });
            return true;
        }
        m = /^custom:(\d{1,9})$/.exec(valor);
        if (m) return tocarItem(Number(m[1]), vol);
        return false;
    }
    /** Toca um som do acervo. `opc.expira` (ms): se o som só ficar pronto depois disso, não toca (um aplauso 10 s atrasado só atrapalha). */
    function tocarItem(id, vol, opc) {
        const ac = C.audioCtx(); if (!ac) return false;
        id = Number(id);
        const v = vol != null ? vol : C.volume();
        if (v <= 0) return false;
        if (ac.state === 'running' && prontos.has(id)) { tocarBuffer(ac, prontos.get(id), v); return true; }          // o caminho rápido: já está baixado e decodificado
        const t0 = performance.now(), expira = opc && opc.expira;
        acordar(ac).then(ok => {
            if (!ok) { bloqueado(ac); return null; }
            return buffer(ac, id).then(buf => { if (!expira || performance.now() - t0 <= expira) tocarBuffer(ac, buf, v); });
        }).catch(() => {});
        return true;
    }
    /** Pra "ouvir antes" na tela de escolha: ignora o "não perturbe", usa o volume dos sons. */
    function prever(valor) { return tocar(valor); }

    function iniciar(c) { C = Object.assign(C, c || {}); }
    return { iniciar, tocar, tocarItem, precarregar, prever, PRESETS, MAX_S, _SINT: SINT, _estado: () => ({ prontos: prontos.size, baixando: buffers.size, fila: fila.length }) };
})();
