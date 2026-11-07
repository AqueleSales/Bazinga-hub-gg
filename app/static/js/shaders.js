/* ==========================================================================================================
   SHADERS DA PÁGINA (Rodada 40): efeitos de TELA INTEIRA que o mouse, o teclado ou o tempo parado disparam. Só no computador.
   O que é: um cosmético do tipo `efeito_pagina`. O catálogo guarda só { preset, cor, ...parâmetros } (tools/cosm/temas/*.js, kit PAGINA); o desenho mora AQUI, em presets FECHADOS
   (nada de código ou GLSL vindo do servidor/cliente). Um canvas por cima de tudo (pointer-events: none) desenha; nada mexe no DOM do app, exceto o `.discord-app`
   (tremer, desbotar) por alguns segundos e a classe `sh-sem-cursor` no <html> enquanto a serra está ligada.
   Regras de custo e de conforto (valem pra todos os presets):
     * só liga com mouse de verdade (pointer: fine), janela >= 900 px, aba à vista e a opção "Efeitos de tela inteira" ligada (Acessibilidade); respeita "reduzir movimento";
     * o laço de desenho (requestAnimationFrame) só roda enquanto há algo na tela; parado, só um relógio de 250 ms confere o tempo ocioso;
     * os que dependem de ficar parado esperam MUITO (12 a 30 s) e saem na primeira mexida do mouse;
     * som sintetizado (Web Audio), calado com "Não perturbar"/volume zero.
   API: Shaders.iniciar({ shaderDe, somOk, volume }) · Shaders.definir(id) (o equipado) · Shaders.demo(id) (prévia de ~25 s: o ocioso espera 1,5 s) · Shaders.parar().
   ========================================================================================================== */
const Shaders = (() => {
    'use strict';
    const PRESETS = {};
    let hooks = { shaderDe: () => null, somOk: () => true, volume: () => 1 };
    let equipado = null, ativoId = null, cfg = null, inst = null, demoTimer = 0;
    let cv = null, g = null, W = 0, H = 0, DPR = 1, raf = 0, ultimoTs = 0, quer = false, acumFps = 0, relogio = 0, dicaEl = null, dicaTimer = 0;
    const E = { x: -100, y: -100, px: -100, py: -100, vel: 0, btn: 0, ultimaAtiv: performance.now(), ultimoMov: 0, inversoes: [], dx: 0, dy: 0, chord: 0 };
    const html = document.documentElement;
    const rnd = (a, b) => a + Math.random() * (b - a);
    const pick = (a) => a[Math.floor(Math.random() * a.length)];
    const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
    const agora = () => performance.now();

    // ------------------------------------------------------------------ guardas
    function permitido() {
        if (html.hasAttribute('data-sem-shaders') || html.hasAttribute('data-reduz-mov')) return false;
        try { if (matchMedia('(prefers-reduced-motion: reduce)').matches) return false; if (!matchMedia('(pointer: fine)').matches) return false; } catch (e) { /* sem matchMedia: deixa */ }
        return innerWidth >= 900;
    }
    const visivel = () => document.visibilityState === 'visible';

    // ------------------------------------------------------------------ canvas
    function garantirCanvas() {
        if (cv) return;
        cv = document.createElement('canvas'); cv.id = 'sh-canvas'; cv.setAttribute('aria-hidden', 'true');
        cv.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;z-index:2147483000;pointer-events:none;display:none';
        document.body.appendChild(cv); g = cv.getContext('2d'); redimensionar();
    }
    function redimensionar() {
        if (!cv) return;
        DPR = Math.min(devicePixelRatio || 1, 1.25); W = innerWidth; H = innerHeight;
        cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR); g.setTransform(DPR, 0, 0, DPR, 0, 0);
    }
    function mostrarCanvas(on) { if (cv) cv.style.display = on ? 'block' : 'none'; if (!on && g) g.clearRect(0, 0, W, H); }

    // ------------------------------------------------------------------ laço
    function quadros(on) {
        quer = !!on;
        if (quer && !raf && inst) { garantirCanvas(); mostrarCanvas(true); ultimoTs = agora(); raf = requestAnimationFrame(laco); }
    }
    function laco(ts) {
        raf = 0;
        if (!inst || !quer) { mostrarCanvas(false); return; }
        const dt = Math.min(.05, (ts - ultimoTs) / 1000); ultimoTs = ts;
        const passo = 1000 / (inst.fps || 60);
        acumFps += dt * 1000;
        if (acumFps >= passo - 1) {
            const dd = acumFps / 1000; acumFps = 0;
            g.setTransform(DPR, 0, 0, DPR, 0, 0); g.clearRect(0, 0, W, H);
            try { inst.desenhar(g, dd, ts / 1000); } catch (e) { console.error('[shaders]', e); parar(); return; }
        }
        if (quer) raf = requestAnimationFrame(laco); else mostrarCanvas(false);
    }

    // ------------------------------------------------------------------ áudio (tudo sintetizado)
    let AC = null, MESTRE = null, RUIDO = null;
    function audio() {
        if (!hooks.somOk()) return null;
        if (!AC) { try { AC = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { return null; } }
        if (AC.state === 'suspended') AC.resume().catch(() => {});
        if (AC.state !== 'running') return null;
        if (!MESTRE) { MESTRE = AC.createGain(); MESTRE.connect(AC.destination); }
        MESTRE.gain.value = .5 * clamp(hooks.volume(), 0, 1);
        return AC;
    }
    function bufRuido() {
        if (RUIDO || !AC) return RUIDO;
        RUIDO = AC.createBuffer(1, AC.sampleRate * 2, AC.sampleRate);
        const d = RUIDO.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
        return RUIDO;
    }
    /** um chiado filtrado: { d, f, f2, tipo, v, q, atraso } */
    function chiado(o) {
        const a = audio(); if (!a) return;
        const t0 = a.currentTime + (o.atraso || 0), s = a.createBufferSource(), fl = a.createBiquadFilter(), gn = a.createGain();
        s.buffer = bufRuido(); s.loop = true; fl.type = o.tipo || 'bandpass'; fl.Q.value = o.q || 1;
        fl.frequency.setValueAtTime(o.f, t0); if (o.f2) fl.frequency.exponentialRampToValueAtTime(o.f2, t0 + o.d);
        gn.gain.setValueAtTime(.0001, t0); gn.gain.exponentialRampToValueAtTime(o.v || .4, t0 + Math.min(.02, o.d / 3)); gn.gain.exponentialRampToValueAtTime(.0001, t0 + o.d);
        s.connect(fl); fl.connect(gn); gn.connect(MESTRE); s.start(t0, Math.random()); s.stop(t0 + o.d + .05);
    }
    /** um tom: { d, f, f2, tipo, v, atraso } */
    function tom(o) {
        const a = audio(); if (!a) return;
        const t0 = a.currentTime + (o.atraso || 0), os = a.createOscillator(), gn = a.createGain();
        os.type = o.tipo || 'sine'; os.frequency.setValueAtTime(o.f, t0); if (o.f2) os.frequency.exponentialRampToValueAtTime(o.f2, t0 + o.d);
        gn.gain.setValueAtTime(.0001, t0); gn.gain.exponentialRampToValueAtTime(o.v || .3, t0 + Math.min(.02, o.d / 3)); gn.gain.exponentialRampToValueAtTime(.0001, t0 + o.d);
        os.connect(gn); gn.connect(MESTRE); os.start(t0); os.stop(t0 + o.d + .05);
    }

    // ------------------------------------------------------------------ utilidades visuais
    const imgs = {};
    function imagem(url) {
        if (!imgs[url]) { const im = new Image(); im.decoding = 'async'; im.src = url; imgs[url] = im; }
        return imgs[url];
    }
    const pronta = (im) => im && im.complete && im.naturalWidth > 0;
    function tremerApp(on, amp = 3) {
        const app = document.querySelector('.discord-app'); if (!app) return;
        if (tremerApp.anim) { try { tremerApp.anim.cancel(); } catch (e) { /* já foi */ } tremerApp.anim = null; }
        if (!on) return;
        const k = []; for (let i = 0; i < 9; i++) k.push({ transform: `translate(${rnd(-amp, amp).toFixed(1)}px,${rnd(-amp, amp).toFixed(1)}px)` }); k.push({ transform: 'translate(0,0)' });
        tremerApp.anim = app.animate(k, { duration: 280, iterations: Infinity });
    }
    function filtroApp(css, opac, instante) {
        const app = document.querySelector('.discord-app'); if (!app) return;
        app.style.transition = instante ? 'none' : 'filter .25s, opacity .25s'; app.style.filter = css || ''; app.style.opacity = opac === undefined ? '' : opac;
    }
    function dica(txt, ms = 6000) {
        if (!dicaEl) { dicaEl = document.createElement('div'); dicaEl.id = 'sh-dica'; dicaEl.setAttribute('role', 'status'); document.body.appendChild(dicaEl); }
        dicaEl.textContent = txt; dicaEl.classList.add('on');
        clearTimeout(dicaTimer); dicaTimer = setTimeout(() => dicaEl && dicaEl.classList.remove('on'), ms);
    }
    const ocioso = () => (agora() - E.ultimaAtiv) / 1000;
    const api = { get W() { return W; }, get H() { return H; }, E, rnd, pick, clamp, quadros, chiado, tom, audio, imagem, pronta, tremerApp, filtroApp, dica, ocioso, agora, hooks: () => hooks, get cfg() { return cfg; } };

    // ==================================================================================================
    // PRESETS. Cada um é uma função fábrica (api, cfg) -> { fps?, dica?, aoMover?, aoDown?, aoUp?, aoTecla?, relogio?(), desenhar(g, dt, t), parar(), demo?() }
    // ==================================================================================================

    // ---- ondinhas: cada clique solta anéis ------------------------------------------------------------
    PRESETS.ondinhas = (a, c) => {
        const an = [], cor = c.cor || '#7ad7ff', cor2 = c.cor2 || '#ffffff';
        return {
            dica: 'Clique em qualquer lugar.',
            aoDown(e) { if (e.button !== 0) return; for (let k = 0; k < 3; k++) an.push({ x: e.clientX, y: e.clientY, t0: a.agora() + k * 110, r: rnd(70, 120) }); a.chiado({ d: .12, f: 1800, f2: 600, v: .12, q: 2 }); a.quadros(true); },
            desenhar(g) {
                const t = a.agora();
                for (let i = an.length - 1; i >= 0; i--) {
                    const r = an[i], k = (t - r.t0) / 900; if (k < 0) continue; if (k >= 1) { an.splice(i, 1); continue; }
                    const e = 1 - Math.pow(1 - k, 3);
                    g.globalAlpha = (1 - k) * .85; g.lineWidth = 3.2 * (1 - k) + .6; g.strokeStyle = i % 2 ? cor2 : cor;
                    g.beginPath(); g.arc(r.x, r.y, 6 + r.r * e, 0, 6.2832); g.stroke();
                }
                g.globalAlpha = 1; if (!an.length) a.quadros(false);
            },
            parar() { an.length = 0; },
        };
    };

    // ---- arcoiris: rastro de arco-íris atrás do mouse -------------------------------------------------
    PRESETS.arcoiris = (a, c) => {
        const pts = [];
        return {
            dica: 'Mexa o mouse.',
            aoMover(e) { pts.push({ x: e.clientX, y: e.clientY, t: a.agora() }); if (pts.length > 90) pts.shift(); a.quadros(true); },
            desenhar(g) {
                const t = a.agora(); while (pts.length && t - pts[0].t > 700) pts.shift();
                g.globalCompositeOperation = 'lighter'; g.lineCap = 'round'; g.lineJoin = 'round';
                for (let i = 1; i < pts.length; i++) {
                    const p = pts[i - 1], q = pts[i], idade = (t - q.t) / 700;
                    if (Math.hypot(q.x - p.x, q.y - p.y) > 220) continue;
                    g.strokeStyle = `hsla(${(q.t * .35 + i * 9) % 360},100%,62%,${(1 - idade) * .85})`; g.lineWidth = 3 + 12 * (1 - idade);
                    g.beginPath(); g.moveTo(p.x, p.y); g.lineTo(q.x, q.y); g.stroke();
                }
                g.globalCompositeOperation = 'source-over'; if (!pts.length) a.quadros(false);
            },
            parar() { pts.length = 0; },
        };
    };

    // ---- matrix: parado há um tempo, a tela escurece e chove código verde -----------------------------
    PRESETS.matrix = (a, c) => {
        const espera = c.espera || 12, GL = 'ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789Z:.=*+-<>¦'.split('');
        let on = false, fade = 0, saindo = false, cols = [];
        const TAM = 17;
        const montar = () => { cols = []; const n = Math.ceil(a.W / TAM); for (let i = 0; i < n; i++) cols.push({ y: rnd(-a.H / TAM, 0), v: rnd(7, 20), len: Math.floor(rnd(10, 30)), gl: Array.from({ length: 40 }, () => pick(GL)) }); };
        return {
            fps: 30,
            relogio() { if (!on && a.ocioso() >= (c.demo ? 1.5 : espera)) { on = true; saindo = false; fade = 0; montar(); a.quadros(true); } },
            aoMover() { if (on && !saindo) saindo = true; },
            aoDown() { if (on && !saindo) saindo = true; },
            aoTecla() { if (on && !saindo) saindo = true; },
            desenhar(g, dt) {
                if (!on) { a.quadros(false); return; }
                fade = clamp(fade + dt * (saindo ? -3.2 : .9), 0, 1);
                if (saindo && fade <= 0) { on = false; saindo = false; a.quadros(false); return; }
                g.fillStyle = `rgba(0,6,2,${.9 * fade})`; g.fillRect(0, 0, a.W, a.H);
                g.font = `${TAM - 2}px "MS Gothic","Yu Gothic",monospace`; g.textBaseline = 'top';
                for (let i = 0; i < cols.length; i++) {
                    const co = cols[i], x = i * TAM; co.y += co.v * dt;
                    for (let k = 0; k < co.len; k++) {
                        const yy = (co.y - k) * TAM; if (yy < -TAM || yy > a.H) continue;
                        if (Math.random() < .02) co.gl[(Math.random() * co.gl.length) | 0] = pick(GL);
                        const al = (1 - k / co.len) * fade;
                        g.fillStyle = k === 0 ? `rgba(220,255,225,${al})` : `rgba(0,${Math.round(210 - k * 4)},70,${al * .9})`;
                        g.fillText(co.gl[k % co.gl.length], x, yy);
                    }
                    if ((co.y - co.len) * TAM > a.H) { co.y = rnd(-12, 0); co.v = rnd(7, 20); co.len = Math.floor(rnd(10, 30)); }
                }
            },
            parar() { on = false; saindo = false; },
        };
    };

    // ---- cyberpsicose: surtos de glitch e HUD de alerta, de vez em quando e quando o mouse é sacudido -------
    PRESETS.cyber = (a, c) => {
        let prox = a.agora() + (c.demo ? 1500 : rnd(c.min || 20, c.max || 45) * 1000), surto = null, ultimo = 0;
        const c1 = c.cor || '#ff1744', c2 = c.cor2 || '#00e5ff';
        const comecar = (forte) => { ultimo = a.agora(); surto = { t0: a.agora(), dur: forte ? rnd(1500, 2400) : rnd(800, 1300), forte }; a.tremerApp(true, forte ? 5 : 3); a.quadros(true); a.chiado({ d: surto.dur / 1000, f: 3000, f2: 800, v: .16, q: .6 }); a.tom({ d: .5, f: 90, f2: 40, tipo: 'sawtooth', v: .14 }); };
        return {
            fps: 30, dica: 'O surto vem sozinho de vez em quando. Sacuda o mouse com força pra provocar um.',
            relogio() { if (!surto && a.agora() >= prox) comecar(false); },
            aoMover() { if (!surto && a.E.inversoes.length >= 7 && a.agora() - ultimo > 10000) { a.E.inversoes.length = 0; comecar(true); } },
            desenhar(g) {
                if (!surto) { a.quadros(false); return; }
                const t = a.agora() - surto.t0, k = t / surto.dur;
                if (k >= 1) { surto = null; prox = a.agora() + rnd(c.min || 20, c.max || 45) * 1000; a.tremerApp(false); a.quadros(false); return; }
                const inten = Math.sin(Math.min(1, k) * Math.PI) * (surto.forte ? 1 : .7);
                g.globalCompositeOperation = 'screen';
                for (let i = 0, n = Math.round(6 + 14 * inten); i < n; i++) {                      // faixas coloridas deslocadas (rasgo de sinal)
                    const y = rnd(0, a.H), h = rnd(3, 46) * inten, x = rnd(-60, 60) * inten;
                    g.fillStyle = Math.random() < .5 ? c1 : c2; g.globalAlpha = rnd(.08, .3) * inten; g.fillRect(x, y, a.W, h);
                }
                g.globalCompositeOperation = 'source-over'; g.globalAlpha = .1 * inten; g.fillStyle = '#000';
                for (let y = 0; y < a.H; y += 4) g.fillRect(0, y, a.W, 1.5);                       // linhas de varredura
                g.globalAlpha = 1;
                if (Math.random() < .5 * inten) { g.fillStyle = `rgba(255,255,255,${rnd(.04, .14) * inten})`; g.fillRect(0, 0, a.W, a.H); }    // clarão de interferência
                for (let i = 0; i < 6 * inten; i++) { g.fillStyle = `rgba(${Math.random() < .5 ? '255,23,68' : '0,229,255'},${rnd(.2, .6)})`; g.fillRect(rnd(0, a.W), rnd(0, a.H), rnd(10, 120), rnd(2, 8)); }   // blocos de pixel
                if (inten > .35) {                                                                      // HUD
                    g.font = '700 26px "Courier New",monospace'; g.textBaseline = 'top';
                    const tx = a.W / 2 - 150 + rnd(-6, 6), ty = 38 + rnd(-3, 3), s = 'CYBERPSYCHOSIS';
                    g.fillStyle = 'rgba(255,23,68,.85)'; g.fillText(s, tx - 2, ty); g.fillStyle = 'rgba(0,229,255,.85)'; g.fillText(s, tx + 2, ty); g.fillStyle = '#fff'; g.fillText(s, tx, ty);
                    g.font = '12px "Courier New",monospace'; g.fillStyle = 'rgba(255,255,255,.8)'; g.fillText(`SYSTEM INTEGRITY ${Math.max(3, Math.round(100 - 96 * inten))}%  //  NEURAL LINK UNSTABLE`, tx - 40, ty + 34);
                }
            },
            parar() { surto = null; a.tremerApp(false); },
        };
    };

    // ---- serra (Chainsaw Man): cliques rápidos ligam a motosserra; com ela ligada o mouse corta a página -------
    PRESETS.serra = (a, c) => {
        const N = c.cliques || 6, cor = c.cor || '#e5001f';
        let cliques = [], on = false, motor = null, trilha = [], gotas = [], manchas = [], ang = 0, parando = 0, ligadoEm = 0, mexeu = false;
        const puxar = () => { a.chiado({ d: .22, f: 2600, f2: 500, v: .22, q: 1.6 }); a.tom({ d: .2, f: 70 + cliques.length * 14, f2: 40, tipo: 'sawtooth', v: .12 }); };
        function ligarMotor() {
            const au = a.audio(); if (!au) return;
            const o1 = au.createOscillator(), o2 = au.createOscillator(), lfo = au.createOscillator(), lg = au.createGain(), gn = au.createGain(), s = au.createBufferSource(), fl = au.createBiquadFilter(), ng = au.createGain();
            o1.type = 'sawtooth'; o2.type = 'square'; o1.frequency.value = 64; o2.frequency.value = 127; lfo.frequency.value = 27; lg.gain.value = .1; const vol = clamp(a.hooks().volume(), 0, 1);
            gn.gain.value = .0001; gn.gain.exponentialRampToValueAtTime(Math.max(.0002, .3 * vol), au.currentTime + .35);
            s.buffer = (function () { const b = au.createBuffer(1, au.sampleRate * 2, au.sampleRate), d = b.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; return b; })(); s.loop = true;
            fl.type = 'bandpass'; fl.frequency.value = 1500; fl.Q.value = .9; ng.gain.value = .12;
            lfo.connect(lg); lg.connect(gn.gain); o1.connect(gn); o2.connect(gn); s.connect(fl); fl.connect(ng); ng.connect(gn); gn.connect(au.destination);
            [o1, o2, lfo, s].forEach((n) => n.start());
            motor = { au, o1, o2, gn, parar() { const t = au.currentTime; try { gn.gain.cancelScheduledValues(t); gn.gain.setValueAtTime(Math.max(.0001, gn.gain.value), t); gn.gain.exponentialRampToValueAtTime(.0001, t + .5); o1.frequency.exponentialRampToValueAtTime(30, t + .5); [o1, o2, lfo, s].forEach((n) => n.stop(t + .55)); } catch (e) { /* já parou */ } } };
        }
        function ligar() {
            on = true; parando = 0; cliques = []; ligadoEm = a.agora(); mexeu = false; html.classList.add('sh-sem-cursor'); ligarMotor(); a.tremerApp(false); a.quadros(true);
            a.dica('Motosserra ligada. Passe o mouse pela página. Parou de mexer, ela desliga.', 4500);
        }
        function desligar() {
            if (!on) return; on = false; parando = a.agora(); html.classList.remove('sh-sem-cursor'); if (motor) { motor.parar(); motor = null; }
        }
        function moto(g, x, y, ang) {                    // a motosserra do cursor (vetor): corpo, cabo, lâmina com corrente; a ponta é o ponto do mouse
            g.save(); g.translate(x + rnd(-1.8, 1.8), y + rnd(-1.8, 1.8)); g.rotate(ang);
            g.fillStyle = '#16161e'; g.beginPath(); g.roundRect(-58, -11, 36, 22, 5); g.fill();
            g.fillStyle = '#e5001f'; g.fillRect(-52, -8, 20, 5); g.strokeStyle = '#16161e'; g.lineWidth = 6; g.beginPath(); g.moveTo(-50, -10); g.quadraticCurveTo(-60, -28, -38, -26); g.stroke();
            const grad = g.createLinearGradient(0, -8, 0, 8); grad.addColorStop(0, '#f3f7fc'); grad.addColorStop(.5, '#a9b6cb'); grad.addColorStop(1, '#69768e');
            g.fillStyle = grad; g.beginPath(); g.moveTo(-22, -7); g.lineTo(2, -7); g.arc(2, 0, 7, -Math.PI / 2, Math.PI / 2); g.lineTo(-22, 7); g.closePath(); g.fill();
            g.strokeStyle = '#101018'; g.lineWidth = 3.4; g.setLineDash([3, 2.4]); g.lineDashOffset = -(a.agora() / 18) % 5.4; g.beginPath(); g.moveTo(-22, -8); g.lineTo(2, -8); g.arc(2, 0, 8, -Math.PI / 2, Math.PI / 2); g.lineTo(-22, 8); g.stroke(); g.setLineDash([]);
            g.restore();
        }
        return {
            dica: 'Clique várias vezes seguidas pra ligar a motosserra.',
            aoDown(e) {
                if (on || e.button !== 0) return;
                const t = a.agora(); cliques = cliques.filter((x) => t - x < 3500); cliques.push(t); puxar();
                if (cliques.length >= N) ligar();
            },
            aoMover(e) {
                if (!on) return; mexeu = true;
                const E = a.E, v = Math.min(1800, E.vel * 1000);
                trilha.push({ x: e.clientX, y: e.clientY, t: a.agora() }); if (trilha.length > 80) trilha.shift();
                if (motor) { motor.o1.frequency.value = 62 + v * .06; motor.o2.frequency.value = 124 + v * .12; }
                if (v > 40) { const n = Math.min(10, 2 + (v / 200) | 0); for (let i = 0; i < n; i++) gotas.push({ x: e.clientX, y: e.clientY, vx: -E.dx * 7 + rnd(-160, 160), vy: -E.dy * 7 + rnd(-300, -30), t: a.agora(), r: rnd(1.6, 5.2) }); if (Math.random() < .25) gotas.push({ x: e.clientX, y: e.clientY, vx: rnd(-60, 60), vy: rnd(-120, -40), t: a.agora(), r: rnd(6, 10) }); manchas.push({ x: e.clientX, y: e.clientY, t: a.agora(), w: rnd(4, 11) }); if (manchas.length > 160) manchas.shift(); }
                a.quadros(true);
            },
            relogio() { if (on && a.agora() - Math.max(a.E.ultimoMov, ligadoEm) > (mexeu ? 1100 : 3500)) desligar(); },
            aoTecla(e) { if (e.key === 'Escape' && on) desligar(); },
            desenhar(g, dt) {
                const t = a.agora();
                while (trilha.length && t - trilha[0].t > 1300) trilha.shift();
                while (manchas.length && t - manchas[0].t > 3200) manchas.shift();
                for (let i = gotas.length - 1; i >= 0; i--) { const d = gotas[i]; d.vy += 900 * dt; d.x += d.vx * dt; d.y += d.vy * dt; if (t - d.t > 1100 || d.y > a.H + 20) gotas.splice(i, 1); }
                g.lineCap = 'round'; g.lineJoin = 'round';
                for (let i = 1; i < manchas.length; i++) {                         // manchas de sangue que vão sumindo devagar
                    const p = manchas[i - 1], q = manchas[i]; if (Math.hypot(q.x - p.x, q.y - p.y) > 90) continue;
                    const k = (t - q.t) / 3200; g.strokeStyle = `rgba(${130 - 50 * k | 0},0,${14 + 6 * k | 0},${(1 - k) * .72})`; g.lineWidth = q.w * (1 - k * .5); g.beginPath(); g.moveTo(p.x, p.y); g.lineTo(q.x, q.y); g.stroke();
                }
                for (let i = 1; i < trilha.length; i++) {                          // o corte: linha clara com brilho vermelho
                    const p = trilha[i - 1], q = trilha[i], k = (t - q.t) / 1300; if (Math.hypot(q.x - p.x, q.y - p.y) > 160) continue;
                    g.strokeStyle = `rgba(255,40,50,${(1 - k) * .55})`; g.lineWidth = 9 * (1 - k) + 1; g.beginPath(); g.moveTo(p.x, p.y); g.lineTo(q.x, q.y); g.stroke();
                    g.strokeStyle = `rgba(255,246,230,${(1 - k) * .95})`; g.lineWidth = 2.4 * (1 - k) + .4; g.beginPath(); g.moveTo(p.x, p.y); g.lineTo(q.x, q.y); g.stroke();
                }
                for (const d of gotas) { const k = (t - d.t) / 1100; g.fillStyle = `rgba(180,0,22,${1 - k * .8})`; g.beginPath(); g.arc(d.x, d.y, d.r, 0, 6.2832); g.fill(); }
                if (on) {
                    const q = trilha[trilha.length - 1], p = trilha[Math.max(0, trilha.length - 6)];
                    if (q && p && (q.x !== p.x || q.y !== p.y)) { const alvo = Math.atan2(q.y - p.y, q.x - p.x); ang += Math.atan2(Math.sin(alvo - ang), Math.cos(alvo - ang)) * .25; }
                    moto(g, a.E.x, a.E.y, ang);
                } else if (!trilha.length && !gotas.length && !manchas.length && t - parando > 300) a.quadros(false);
            },
            parar() { desligar(); trilha = []; gotas = []; manchas = []; cliques = []; html.classList.remove('sh-sem-cursor'); },
        };
    };

    // ---- aranha (Homem-Aranha): sentido de aranha quando o mouse fica parado; os dois botões soltam teia ----------
    PRESETS.aranha = (a, c) => {
        const espera = c.espera || 18, cor = c.cor || '#ffffff';
        let sentido = null, proximo = a.agora(), teias = [], fios = [], livre = 0;
        const origem = (x) => ({ x: x < a.W / 2 ? 0 : a.W, y: a.H });
        function teia(x, y) {
            const o = origem(x), t = a.agora(); const n = 9 + Math.floor(Math.random() * 3), R = rnd(70, 105), rot = rnd(0, 6.28);
            fios.push({ ox: o.x, oy: o.y, x, y, t0: t }); a.tom({ d: .12, f: 1500, f2: 300, tipo: 'square', v: .1 }); a.chiado({ d: .2, f: 4000, tipo: 'highpass', v: .25 });
            setTimeout(() => { teias.push({ x, y, n, R, rot, t0: a.agora(), sag: rnd(.18, .3) }); if (teias.length > 8) teias.shift(); a.chiado({ d: .1, f: 900, f2: 300, v: .2, q: 1.5 }); a.quadros(true); }, 200);
            a.quadros(true);
        }
        function sent() { sentido = { t0: a.agora(), dur: 3400 }; a.tremerApp(true, 2.2); a.quadros(true); a.tom({ d: .45, f: 1400, f2: 2200, tipo: 'sine', v: .09 }); a.tom({ d: .45, f: 1410, f2: 2210, tipo: 'sine', v: .09, atraso: .12 }); }
        return {
            dica: 'Fique um tempo parado pro sentido de aranha. Segure o botão esquerdo e o direito juntos pra soltar teia.',
            aoDown(e) { if ((e.buttons & 3) === 3 && a.agora() > livre) { livre = a.agora() + 450; teia(e.clientX, e.clientY); } },
            relogio() { if (!sentido && a.agora() > proximo && a.ocioso() >= (c.demo ? 1.5 : espera)) { sent(); proximo = a.agora() + 28000; } },
            aoMover() { if (sentido) { sentido.dur = Math.min(sentido.dur, a.agora() - sentido.t0 + 350); } },
            desenhar(g, dt) {
                const t = a.agora();
                // fios disparados
                for (let i = fios.length - 1; i >= 0; i--) {
                    const f = fios[i], k = (t - f.t0) / 220; if (k >= 1.4) { fios.splice(i, 1); continue; }
                    const e = Math.min(1, 1 - Math.pow(1 - Math.min(1, k), 3)), x2 = f.ox + (f.x - f.ox) * e, y2 = f.oy + (f.y - f.oy) * e, cx = (f.ox + x2) / 2, cy = (f.oy + y2) / 2 + 30 * (1 - e);
                    g.strokeStyle = 'rgba(0,0,0,.35)'; g.lineWidth = 3.4; g.beginPath(); g.moveTo(f.ox, f.oy); g.quadraticCurveTo(cx, cy, x2, y2); g.stroke();
                    g.strokeStyle = `rgba(250,250,255,${k > 1 ? Math.max(0, 1.4 - k) / .4 : .95})`; g.lineWidth = 1.7; g.beginPath(); g.moveTo(f.ox, f.oy); g.quadraticCurveTo(cx, cy, x2, y2); g.stroke();
                }
                // teias coladas
                for (let i = teias.length - 1; i >= 0; i--) {
                    const w = teias[i], idade = (t - w.t0) / 1000; if (idade > 6.5) { teias.splice(i, 1); continue; }
                    const al = idade > 5.2 ? (6.5 - idade) / 1.3 : 1, p = Math.min(1, idade / .28);
                    const R = w.R * p;
                    const pt = (ang, r) => [w.x + r * Math.cos(ang), w.y + r * Math.sin(ang)];
                    for (let passo = 0; passo < 2; passo++) {
                        g.strokeStyle = passo ? `rgba(248,248,255,${.92 * al})` : `rgba(0,0,0,${.3 * al})`; g.lineWidth = passo ? 1.5 : 3.2;
                        g.beginPath();
                        for (let k = 0; k < w.n; k++) { const ang = w.rot + k / w.n * 6.2832, [x1, y1] = pt(ang, R); g.moveTo(w.x, w.y); g.lineTo(x1, y1); }
                        for (const f of [.28, .5, .72, .95]) {
                            for (let k = 0; k < w.n; k++) {
                                const a1 = w.rot + k / w.n * 6.2832, a2 = w.rot + (k + 1) / w.n * 6.2832, [xa, ya] = pt(a1, R * f), [xb, yb] = pt(a2, R * f), [xm, ym] = pt((a1 + a2) / 2, R * f * (1 - w.sag * .55));
                                g.moveTo(xa, ya); g.quadraticCurveTo(xm, ym, xb, yb);
                            }
                        }
                        g.stroke();
                    }
                }
                // sentido de aranha
                if (sentido) {
                    const k = (t - sentido.t0) / sentido.dur;
                    if (k >= 1) { sentido = null; a.tremerApp(false); }
                    else {
                        const inten = Math.sin(k * Math.PI);
                        const vig = g.createRadialGradient(a.W / 2, a.H / 2, Math.min(a.W, a.H) * .3, a.W / 2, a.H / 2, Math.max(a.W, a.H) * .75);
                        vig.addColorStop(0, 'rgba(255,255,255,0)'); vig.addColorStop(1, `rgba(220,240,255,${.5 * inten})`); g.fillStyle = vig; g.fillRect(0, 0, a.W, a.H);
                        for (let i = 0; i < 3; i++) { g.strokeStyle = `rgba(255,255,255,${.38 * inten})`; g.lineWidth = 2; g.strokeRect(rnd(-5, 5) + 8, rnd(-5, 5) + 8, a.W - 16, a.H - 16); }
                        for (let i = 0; i < 3; i++) { const r = ((t / 700 + i / 3) % 1); g.strokeStyle = `rgba(255,255,255,${(1 - r) * .55 * inten})`; g.lineWidth = 2.5 * (1 - r) + .5; g.beginPath(); g.arc(a.W / 2, 60, 30 + r * Math.max(a.W, a.H) * .7, 0, 6.2832); g.stroke(); }
                        g.strokeStyle = `rgba(255,255,255,${.8 * inten})`; g.lineWidth = 2.4; g.lineCap = 'round';
                        for (let i = -3; i <= 3; i++) { const ang = -Math.PI / 2 + i * .22, r0 = 52, r1 = 52 + 24 + (i % 2 ? 8 : 0) + rnd(-3, 3); g.beginPath(); g.moveTo(a.W / 2 + r0 * Math.cos(ang), 60 + r0 * Math.sin(ang) * .6); g.lineTo(a.W / 2 + r1 * Math.cos(ang), 60 + r1 * Math.sin(ang) * .6); g.stroke(); }
                    }
                }
                if (!sentido && !teias.length && !fios.length) a.quadros(false);
            },
            parar() { sentido = null; teias = []; fios = []; a.tremerApp(false); },
        };
    };

    // ---- eva (Evangelion): os dois botões lançam a Lança de Longinus; parado, vem o alerta de Anjo -------------------
    PRESETS.eva = (a, c) => {
        const espera = c.espera || 30, LIM = c.limite || 60, laranja = '#ff8a2a';
        let lancas = [], campos = [], alerta = null, livre = 0, shake = 0;
        const LANCA = '/static/img/cosm/eva/lanca.png';
        a.imagem(LANCA);
        function lancar(x, y) {
            const lado = Math.floor(rnd(0, 4)), ox = lado === 0 ? -60 : lado === 1 ? a.W + 60 : rnd(0, a.W), oy = lado === 2 ? -60 : lado === 3 ? a.H + 60 : rnd(0, a.H);
            lancas.push({ ox, oy, x, y, t0: a.agora() }); a.chiado({ d: .35, f: 400, f2: 3000, v: .3, q: .8 }); a.quadros(true);
        }
        function impacto(x, y) {
            const t = a.agora(); campos.push({ x, y, t0: t, sh: Array.from({ length: 8 }, (_, k) => ({ a: k / 8 * 6.2832 + Math.PI / 8, v: rnd(80, 220), r: rnd(0, 6.28) })) });
            shake = t; a.tremerApp(true, 5); setTimeout(() => a.tremerApp(false), 340);
            a.tom({ d: .5, f: 110, f2: 38, tipo: 'sine', v: .4 }); a.chiado({ d: .45, f: 5000, f2: 600, v: .35, q: .6 }); a.tom({ d: .7, f: 1500, f2: 700, tipo: 'triangle', v: .12, atraso: .05 });
        }
        const oct = (g, x, y, r, rot) => { g.beginPath(); for (let i = 0; i < 8; i++) { const an = rot + i / 8 * 6.2832 + Math.PI / 8; i ? g.lineTo(x + r * Math.cos(an), y + r * Math.sin(an)) : g.moveTo(x + r * Math.cos(an), y + r * Math.sin(an)); } g.closePath(); };
        function hexa(g, x, y, r) { g.beginPath(); for (let i = 0; i < 6; i++) { const an = i / 6 * 6.2832 + Math.PI / 6; i ? g.lineTo(x + r * Math.cos(an), y + r * Math.sin(an)) : g.moveTo(x + r * Math.cos(an), y + r * Math.sin(an)); } g.closePath(); }
        return {
            dica: 'Segure o botão esquerdo e o direito juntos pra lançar a Lança de Longinus. Fique parado pra ouvir o alerta de Anjo.',
            aoDown(e) { if ((e.buttons & 3) === 3 && a.agora() > livre) { livre = a.agora() + 600; lancar(e.clientX, e.clientY); } },
            relogio() { if (!alerta && a.ocioso() >= (c.demo ? 1.5 : espera)) { alerta = { t0: a.agora(), fim: 0 }; a.quadros(true); } },
            aoMover() { if (alerta && !alerta.fim) alerta.fim = a.agora(); },
            desenhar(g, dt) {
                const t = a.agora();
                // lanças em voo
                for (let i = lancas.length - 1; i >= 0; i--) {
                    const l = lancas[i], k = (t - l.t0) / 300; if (k >= 1) { impacto(l.x, l.y); lancas.splice(i, 1); continue; }
                    const e = k * k, x = l.ox + (l.x - l.ox) * e, y = l.oy + (l.y - l.oy) * e, ang = Math.atan2(l.y - l.oy, l.x - l.ox), im = a.imagem(LANCA);
                    g.save(); g.translate(x, y); g.rotate(ang);
                    if (a.pronta(im)) { const L = 440, h = Math.max(14, L * im.naturalHeight / im.naturalWidth); g.shadowColor = '#ff8a2a'; g.shadowBlur = 14; g.drawImage(im, -L + 30, -h / 2, L, h); g.shadowBlur = 0; }
                    else { g.strokeStyle = '#9a1c1c'; g.lineWidth = 4; g.beginPath(); g.moveTo(-300, 0); g.lineTo(26, 0); g.stroke(); }
                    g.restore();
                    g.strokeStyle = `rgba(255,200,160,${.4 * k})`; g.lineWidth = 2; g.beginPath(); g.moveTo(x - 330 * Math.cos(ang), y - 330 * Math.sin(ang)); g.lineTo(x, y); g.stroke();
                }
                // o campo AT quebrando: octógonos que se abrem e estilhaçam
                for (let i = campos.length - 1; i >= 0; i--) {
                    const f = campos[i], k = (t - f.t0) / 1500; if (k >= 1) { campos.splice(i, 1); continue; }
                    if (k < .12) { g.fillStyle = `rgba(255,236,210,${(1 - k / .12) * .7})`; g.fillRect(0, 0, a.W, a.H); }
                    for (let j = 0; j < 4; j++) {
                        const kk = clamp(k * 1.5 - j * .1, 0, 1); if (kk <= 0) continue; const r = 30 + 250 * (1 - Math.pow(1 - kk, 3)) + j * 34;
                        g.lineWidth = 7 * (1 - kk) + 1.2; g.strokeStyle = `rgba(255,${138 + j * 24},42,${(1 - kk) * .9})`; g.fillStyle = `rgba(255,138,42,${(1 - kk) * .12})`; oct(g, f.x, f.y, r, 0); g.fill(); g.stroke();
                    }
                    for (const s of f.sh) { const d = s.v * k * 1.3 + 40, x = f.x + d * Math.cos(s.a), y = f.y + d * Math.sin(s.a) + 90 * k * k; g.save(); g.translate(x, y); g.rotate(s.r + k * 3); g.fillStyle = `rgba(255,150,60,${(1 - k) * .75})`; g.beginPath(); g.moveTo(0, -16); g.lineTo(11, 9); g.lineTo(-9, 11); g.closePath(); g.fill(); g.restore(); }
                }
                // alerta de Anjo
                if (alerta) {
                    const tt = (t - alerta.t0) / 1000, saiu = alerta.fim ? (t - alerta.fim) / 350 : 0, rest = LIM - tt;
                    if (saiu >= 1 || rest <= -1.2) { alerta = null; a.tremerApp(false); }
                    else {
                        const al = alerta.fim ? 1 - saiu : Math.min(1, tt / .5), apagao = rest <= 0 ? Math.min(1, -rest / .4) : 0, pisca = (Math.sin(tt * 9) + 1) / 2;
                        g.globalAlpha = al; g.fillStyle = `rgba(90,0,0,${.2 + .14 * pisca})`; g.fillRect(0, 0, a.W, a.H);
                        g.strokeStyle = `rgba(255,40,30,${.2 + .15 * pisca})`; g.lineWidth = 1.6; for (let y = -20, row = 0; y < a.H + 40; y += 26, row++) for (let x = (row % 2) * 22; x < a.W + 44; x += 44) { hexa(g, x, y, 22); g.stroke(); }
                        const bh = 54; g.fillStyle = 'rgba(210,10,10,.92)'; g.fillRect(0, 0, a.W, bh); g.fillRect(0, a.H - bh, a.W, bh);
                        g.fillStyle = '#16050a'; for (let x = ((tt * 90) % 60) - 60; x < a.W; x += 60) { g.beginPath(); g.moveTo(x, 5); g.lineTo(x + 30, 5); g.lineTo(x + 10, bh - 5); g.lineTo(x - 20, bh - 5); g.fill(); g.beginPath(); g.moveTo(x, a.H - bh + 5); g.lineTo(x + 30, a.H - bh + 5); g.lineTo(x + 10, a.H - 5); g.lineTo(x - 20, a.H - 5); g.fill(); }
                        g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = '#fff'; g.font = '900 54px "Times New Roman",serif'; g.fillText('EMERGENCY', a.W / 2, a.H / 2 - 40); g.font = '700 22px "Courier New",monospace'; g.fillText('警報  //  ANGEL APPROACHING  //  PATTERN BLUE', a.W / 2, a.H / 2 + 10);
                        const s = Math.max(0, rest), mm = String(Math.floor(s / 60)).padStart(2, '0'), ss = String(Math.floor(s % 60)).padStart(2, '0'), cc = String(Math.floor((s % 1) * 100)).padStart(2, '0');
                        g.fillStyle = '#000'; g.fillRect(a.W / 2 - 172, a.H / 2 + 38, 344, 78); g.strokeStyle = '#ff2a1a'; g.lineWidth = 2; g.strokeRect(a.W / 2 - 172, a.H / 2 + 38, 344, 78);
                        g.fillStyle = '#ff6a3a'; g.font = '700 14px "Courier New",monospace'; g.fillText('ACTIVITY LIMIT', a.W / 2, a.H / 2 + 52); g.fillStyle = rest < 10 ? '#ff2a1a' : '#fff'; g.font = '900 48px "Courier New",monospace'; g.fillText(`${mm}:${ss}:${cc}`, a.W / 2, a.H / 2 + 88);
                        g.textAlign = 'start'; g.globalAlpha = 1;
                        if (apagao) { g.fillStyle = `rgba(0,0,0,${apagao})`; g.fillRect(0, 0, a.W, a.H); }
                        if (Math.floor(tt * 2) !== Math.floor((tt - .03) * 2) && !alerta.fim && rest > 0) { a.tom({ d: .18, f: 880, tipo: 'square', v: .06 }); a.tom({ d: .18, f: 660, tipo: 'square', v: .06, atraso: .2 }); }
                    }
                }
                if (!alerta && !lancas.length && !campos.length) a.quadros(false);
            },
            parar() { lancas = []; campos = []; alerta = null; a.tremerApp(false); },
        };
    };

    // ---- jojo_tempo (JoJo): parado muito tempo, aparecem os ゴゴゴ e o tempo é apagado; mexeu, volta num piscar --------
    PRESETS.jojo_tempo = (a, c) => {
        const espera = c.espera || 25, GOGO = '/static/img/cosm/jojo/gogogo.png';
        a.imagem(GOGO);
        let fase = 0, t0 = 0, sim = [], rosa = 0;
        const comecar = () => { fase = 1; t0 = a.agora(); sim = []; rosa = 0; a.quadros(true); a.tom({ d: 4, f: 42, f2: 55, tipo: 'sawtooth', v: .12 }); };
        const voltar = (rapido) => {
            if (!fase) return; fase = 0; a.filtroApp('', '', true); a.quadros(true);
            if (rapido) { sim.flash = a.agora(); a.chiado({ d: .12, f: 4000, f2: 400, v: .25, tipo: 'highpass' }); }
        };
        return {
            dica: 'Fique parado um bom tempo. Quando mexer, tudo volta num piscar.',
            relogio() { if (!fase && a.ocioso() >= (c.demo ? 1.5 : espera)) comecar(); },
            aoMover() { voltar(true); }, aoDown() { voltar(true); }, aoTecla() { voltar(true); },
            desenhar(g, dt) {
                const t = a.agora(), el = (t - t0) / 1000;
                if (sim.flash !== undefined && !fase) {                                    // piscar de volta
                    const k = (t - sim.flash) / 140; if (k >= 1) { sim = []; a.quadros(false); return; }
                    g.fillStyle = `rgba(255,255,255,${1 - k})`; g.fillRect(0, 0, a.W, a.H); return;
                }
                if (!fase) { a.quadros(false); return; }
                // 1) os ゴゴゴ crescem do nada
                if (sim.length < 16 && Math.random() < dt * (fase === 1 ? 3.2 : 1.2)) sim.push({ x: rnd(0, a.W), y: rnd(0, a.H), s: rnd(70, 190), r: rnd(-.25, .25), born: t, cor: Math.random() < .5 ? 0 : 1 });
                // 2) depois de ~8 s a barra rosa varre a tela e o tempo é apagado
                if (fase === 1 && el > 8) { fase = 2; rosa = t; a.filtroApp('grayscale(1) contrast(1.8) brightness(.55)', .35); a.chiado({ d: 1.2, f: 200, f2: 4000, v: .3, q: .5 }); a.tom({ d: 1.2, f: 900, f2: 80, tipo: 'sawtooth', v: .15 }); }
                const im = a.imagem(GOGO), sk = fase === 2 ? clamp((t - rosa) / 1300, 0, 1) : 0;
                if (fase === 2) {
                    const xb = a.W * sk;
                    g.fillStyle = 'rgba(14,0,10,.93)'; g.fillRect(0, 0, xb, a.H);
                    g.fillStyle = 'rgba(255,0,110,.55)'; for (let i = 0; i < 40; i++) { const y = rnd(0, a.H); g.fillRect(rnd(0, xb), y, rnd(20, 240), rnd(1, 3)); }
                    g.fillStyle = '#ff1493'; g.fillRect(xb - 40, 0, 40, a.H); g.fillStyle = '#ffd0ec'; g.fillRect(xb - 6, 0, 6, a.H);
                    if (sk >= 1) { g.fillStyle = 'rgba(14,0,10,.93)'; g.fillRect(0, 0, a.W, a.H); g.fillStyle = 'rgba(255,0,110,.5)'; for (let i = 0; i < 24; i++) g.fillRect(rnd(0, a.W), rnd(0, a.H), rnd(10, 90), 2); g.font = '900 38px "Yu Gothic","MS Gothic",sans-serif'; g.fillStyle = 'rgba(255,20,130,.85)'; g.textAlign = 'center'; g.fillText('時は消し飛ぶ', a.W / 2, a.H / 2); g.textAlign = 'start'; }
                }
                for (const s of sim) {
                    const k = clamp((t - s.born) / 700, 0, 1), x = s.x + rnd(-1.5, 1.5), y = s.y + rnd(-1.5, 1.5);
                    if (a.pronta(im)) { const w = s.s, h = w * im.naturalHeight / im.naturalWidth; g.save(); g.globalAlpha = k * .92; g.translate(x, y); g.rotate(s.r); g.drawImage(im, -w / 2, -h / 2, w, h); g.restore(); }
                    else { g.font = `900 ${s.s * .6}px "Yu Gothic",sans-serif`; g.fillStyle = `rgba(150,60,190,${k})`; g.fillText('ゴ', x, y); }
                }
                g.globalAlpha = 1;
            },
            parar() { fase = 0; sim = []; a.filtroApp('', ''); },
        };
    };

    // ---- sapos: parado, chove leve, nascem vitórias-régias com sapinhos pixelados; mexeu, a chuva para e os sapos vão embora ----
    PRESETS.sapos = (a, c) => {
        const espera = c.espera || 15, PX = 4;
        const paleta = { K: '#10331a', G: '#46bd58', g: '#80e88a', D: '#2a8a3a', W: '#ffffff', B: '#111111', R: '#ff6f8f', Y: '#d4f27a', P: '#ff9ad0', p: '#ffd1ea', L: '#2e9e44', l: '#58c46a', M: '#1f7a30' };
        const sprite = (linhas) => { const cv2 = document.createElement('canvas'); cv2.width = linhas[0].length; cv2.height = linhas.length; const x = cv2.getContext('2d'); linhas.forEach((ln, y) => [...ln].forEach((ch, xx) => { if (paleta[ch]) { x.fillStyle = paleta[ch]; x.fillRect(xx, y, 1, 1); } })); return cv2; };
        const FROG = sprite([
            '..KKK....KKK..', '.KWWBK..KBWWK.', '.KWBBK..KBBWK.', '.KGGGKKKKGGGK.', 'KGgGGGGGGGGgGK', 'KGGKKKKKKKKGGK', 'KGGGGRRRRGGGGK', '.KGGGGGGGGGGK.', '.KDGGYYYYGGDK.', 'KGGDKYYYYKDGGK', 'KGGK.KKKK.KGGK', '.KK........KK.']);
        const PAD = sprite([
            '....KKKKKKKKKKKKKKKK....', '..KKLLLLLLLLLLLLLLLLKK..', '.KLLllllllllllllllllLLK.', 'KLLllllllllMMllllllllLLK', 'KLlllllllllMMlllllllllLK', 'KLLlllllllllMMllllllllLK', '.KLLLlllllllllMLLLLLLK..', '..KKLLLLLLLLLLLLLLKK....', '....KKKKKKKKKKKKKK......']);
        const FLOR = sprite(['..P..', '.PpP.', 'PpYpP', '.PpP.', '..P..']);
        let chovendo = false, chuva = 0, gotas = [], aguas = [], pads = [], prox = 0, ativo = false, ondas = [];
        const pulo = (p) => { if (p.saindo) return; p.saindo = a.agora(); const dx = p.x < a.W / 2 ? -1 : 1; p.alvoX = dx < 0 ? -80 : a.W + 80; a.chiado({ d: .09, f: 700, f2: 250, v: .18, q: 2 }); a.tom({ d: .12, f: 190, f2: 120, tipo: 'square', v: .06 }); };
        function surgir() { if (pads.length >= 6) return; const x = rnd(70, a.W - 70), y = rnd(a.H * .55, a.H - 60); if (pads.some((p) => Math.hypot(p.x - x, p.y - y) < 120)) return; pads.push({ x, y, born: a.agora(), vida: rnd(9000, 22000), rot: 0, sapo: Math.random() < .85, flor: Math.random() < .5, saindo: 0, alvoX: 0, croa: a.agora() + rnd(2000, 6000) }); }
        return {
            fps: 45, dica: 'Fique parado um tempo. Quando mexer, a chuva para, mas os sapinhos ficam. Clique neles pra pularem.',
            aoClique(e) { for (const p of pads) if (p.sapo && !p.saindo && Math.abs(e.clientX - p.x) < 30 && Math.abs(e.clientY - (p.y - 22)) < 30) { pulo(p); return true; } return false; },
            relogio() {
                if (!chovendo && a.ocioso() >= (c.demo ? 1.5 : espera)) { chovendo = true; ativo = true; prox = a.agora(); a.quadros(true); }
                if (chovendo && a.ocioso() < 1) chovendo = false;
            },
            aoMover() { chovendo = false; }, aoDown() { chovendo = false; },
            desenhar(g, dt) {
                const t = a.agora();
                chuva = clamp(chuva + dt * (chovendo ? .6 : -1.4), 0, 1);
                if (chuva > 0) {
                    const baixo = a.H * .5; g.fillStyle = `rgba(40,120,170,${.16 * chuva})`; g.fillRect(0, a.H * .6, a.W, a.H * .4);
                    if (Math.random() < dt * 60 * chuva) gotas.push({ x: rnd(0, a.W), y: -10, v: rnd(500, 800) });
                    for (let i = gotas.length - 1; i >= 0; i--) {
                        const d = gotas[i]; d.y += d.v * dt; g.strokeStyle = `rgba(190,225,255,${.45 * chuva})`; g.lineWidth = 1.2; g.beginPath(); g.moveTo(d.x, d.y); g.lineTo(d.x - 2, d.y - 14); g.stroke();
                        if (d.y > rnd(baixo + 80, a.H)) { gotas.splice(i, 1); if (d.y > a.H * .6) ondas.push({ x: d.x, y: d.y, t0: t }); }
                    }
                    for (let i = ondas.length - 1; i >= 0; i--) { const o = ondas[i], k = (t - o.t0) / 800; if (k >= 1) { ondas.splice(i, 1); continue; } g.strokeStyle = `rgba(210,238,255,${(1 - k) * .5 * chuva})`; g.lineWidth = 1.2; g.beginPath(); g.ellipse(o.x, o.y, 4 + 14 * k, 1.6 + 5 * k, 0, 0, 6.2832); g.stroke(); }
                    if (chovendo && t > prox) { surgir(); prox = t + 2600; }
                } else { gotas.length = 0; ondas.length = 0; }
                g.imageSmoothingEnabled = false;
                for (let i = pads.length - 1; i >= 0; i--) {
                    const p = pads[i], idade = t - p.born;
                    if (!p.saindo && idade > p.vida) pulo(p);
                    let al = clamp(idade / 1200, 0, 1), sx = 0, sy = 0, sapoX = p.x, sapoY = p.y - 22;
                    if (p.saindo) {
                        const k = (t - p.saindo) / 1500; al = Math.max(0, 1 - k * 1.1);
                        const e = clamp(k / .9, 0, 1); sapoX = p.x + (p.alvoX - p.x) * e; sapoY = p.y - 22 - Math.sin(e * Math.PI * 3) * 44 * (1 - e * .4) - 18 * e;
                        if (k >= 1.05 || (p.sapo && (sapoX < -70 || sapoX > a.W + 70) && al <= 0)) { pads.splice(i, 1); continue; }
                    }
                    g.save(); g.globalAlpha = al; const bob = Math.sin(t / 700 + i) * 1.5;
                    g.drawImage(PAD, p.x - 12 * PX / 1, p.y - 4 * PX + bob, 24 * PX / 1, 9 * PX / 1);
                    if (p.flor) g.drawImage(FLOR, p.x + 22, p.y - 14 + bob, 5 * PX / 1, 5 * PX / 1);
                    g.restore();
                    if (p.sapo) {
                        g.save(); g.globalAlpha = p.saindo ? Math.max(0, 1 - (t - p.saindo) / 1500) : al;
                        const resp = p.saindo ? 0 : Math.sin(t / 420 + i * 2) * 1; g.translate(sapoX, sapoY + bob + resp);
                        if (p.saindo && sapoX > p.x) g.scale(1, 1);
                        g.drawImage(FROG, -7 * PX, -6 * PX, 14 * PX, 12 * PX); g.restore();
                        if (!p.saindo && t > p.croa) { p.croa = t + rnd(5000, 12000); a.tom({ d: .16, f: 120, f2: 170, tipo: 'square', v: .07 }); a.tom({ d: .12, f: 110, f2: 90, tipo: 'square', v: .07, atraso: .17 }); }
                    }
                }
                g.imageSmoothingEnabled = true;
                if (!chovendo && chuva <= 0 && !pads.length) { ativo = false; a.quadros(false); }
            },
            parar() { chovendo = false; pads = []; gotas = []; ondas = []; chuva = 0; },
        };
    };

    // ------------------------------------------------------------------ ciclo de vida
    function criar(id, extra) {
        const base = hooks.shaderDe(id); if (!base || !PRESETS[base.preset]) return false;
        parar();
        cfg = { ...base, ...(extra || {}) }; ativoId = id; inst = PRESETS[cfg.preset](api, cfg);
        garantirCanvas(); E.ultimaAtiv = agora(); acumFps = 0;
        relogio = setInterval(() => { if (!inst) return; if (!visivel() || !document.hasFocus()) return; try { inst.relogio && inst.relogio(); } catch (e) { console.error('[shaders]', e); } }, 250);
        return true;
    }
    function parar() {
        if (relogio) { clearInterval(relogio); relogio = 0; }
        if (inst) { try { inst.parar && inst.parar(); } catch (e) { /* segue */ } }
        inst = null; ativoId = null; cfg = null; quer = false; if (raf) { cancelAnimationFrame(raf); raf = 0; }
        html.classList.remove('sh-sem-cursor'); tremerApp(false); filtroApp('', ''); mostrarCanvas(false);
    }
    function definir(id) {
        equipado = id || null;
        if (demoTimer) return;                          // uma prévia em curso volta pro equipado quando acabar
        if (!equipado || !permitido()) { parar(); return; }
        if (ativoId === equipado) return;
        criar(equipado);
    }
    function demo(id) {
        if (!permitido()) { dica('Os efeitos de tela inteira só rodam no computador, com a opção ligada em Acessibilidade e sem "reduzir movimento".', 5500); return; }
        if (!hooks.shaderDe(id)) return;
        clearTimeout(demoTimer); criar(id, { demo: true });
        if (inst && inst.dica) dica(inst.dica, 8000);
        demoTimer = setTimeout(() => { demoTimer = 0; parar(); definir(equipado); }, 25000);
        if (inst && inst.demoInicio) inst.demoInicio();
    }

    // ------------------------------------------------------------------ entradas (um conjunto de ouvintes pra tudo)
    function atividade() { E.ultimaAtiv = agora(); }
    function aoMover(e) {
        const t = agora(), dt = Math.max(1, t - (E.ultimoMov || t - 16));
        E.px = E.x; E.py = E.y; E.x = e.clientX; E.y = e.clientY; E.dx = E.x - E.px; E.dy = E.y - E.py;
        E.vel = Math.hypot(E.dx, E.dy) / dt; E.ultimoMov = t; E.ultimaAtiv = t;
        const sx = Math.sign(E.dx); E.inversoes = E.inversoes.filter((x) => t - x < 700);
        if (sx && E.ultSx && sx !== E.ultSx && Math.abs(E.dx) > 14) E.inversoes.push(t); if (sx) E.ultSx = sx;
        if (inst && inst.aoMover) inst.aoMover(e);
    }
    function aoDown(e) {
        atividade(); E.x = e.clientX; E.y = e.clientY; E.btn = e.buttons;
        if (inst && inst.aoClique && inst.aoClique(e)) { e.preventDefault(); e.stopPropagation(); return; }
        if (inst && inst.aoDown) inst.aoDown(e);
    }
    function aoTecla(e) { atividade(); if (inst && inst.aoTecla) inst.aoTecla(e); }
    function iniciar(h) {
        hooks = { ...hooks, ...(h || {}) };
        addEventListener('mousemove', aoMover, { capture: true, passive: true });
        addEventListener('mousedown', aoDown, true);
        addEventListener('mouseup', () => { E.btn = 0; atividade(); }, { capture: true, passive: true });
        addEventListener('keydown', aoTecla, { capture: true, passive: true });
        addEventListener('wheel', atividade, { capture: true, passive: true });
        addEventListener('contextmenu', (e) => { if (inst && (cfg.preset === 'aranha' || cfg.preset === 'eva') && (E.btn & 1)) { e.preventDefault(); e.stopPropagation(); } }, true);
        addEventListener('resize', () => { redimensionar(); if (equipado && !ativoId) definir(equipado); else if (!permitido()) parar(); });
        try { new MutationObserver(() => { if (equipado && !demoTimer) { if (permitido()) { if (!ativoId) definir(equipado); } else parar(); } }).observe(html, { attributes: true, attributeFilter: ['data-sem-shaders', 'data-reduz-mov'] }); } catch (e) { /* sem observer: vale na próxima troca */ }
        document.addEventListener('click', (e) => { const b = e.target.closest && e.target.closest('[data-shader-demo]'); if (b) { e.preventDefault(); demo(b.dataset.shaderDemo); } });
    }
    return { iniciar, definir, demo, parar, PRESETS, _ocioso: (seg) => { E.ultimaAtiv = agora() - seg * 1000; }, _estado: () => ({ ativoId, quer, raf, ocioso: ocioso(), inst: !!inst, relogio: !!relogio, demoTimer: !!demoTimer }) };
})();
