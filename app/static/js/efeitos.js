/* Motor dos efeitos do Estúdio (receitas JSON -> animação). Objeto global `Efeitos`.
   A receita vem do servidor JÁ normalizada (app/efeitos.py), mas aqui os números são limitados DE NOVO: nada da receita vira
   código, só números/cores/opções de listas fechadas. Só `transform`/`opacity` se mexem (Web Animations API), então vão pra GPU.
   Camada nova = entrada no ESQUEMA do servidor (app/efeitos.py) + uma função em CAMADAS aqui.

   Uso: o cosmeticos.js chama Efeitos.tem(id) / htmlPerfil(id) / htmlAvatar(id) no lugar dos efeitos feitos à mão. O HTML sai vazio
   (`<div data-ec="id">`) e um MutationObserver monta as camadas quando o elemento aparece (e de novo se ele mudar de tamanho). */
const Efeitos = (() => {
    const reg = {};                 // id -> { tipo, receita }
    let versao = 0;                 // sobe a cada registrar(): elementos já montados com receita velha são refeitos
    const reduz = () => (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) || document.documentElement.hasAttribute('data-reduz-mov');   // sistema OU Configurações > Acessibilidade
    const lim = (v, mn, mx, p) => { const x = Number(v); return Number.isFinite(x) ? Math.max(mn, Math.min(mx, x)) : p; };
    const cor = (v, p) => (typeof v === 'string' && /^#[0-9a-fA-F]{6}$/.test(v)) ? v : p;
    const opc = (v, lista, p) => lista.includes(v) ? v : p;
    const idOk = (v) => /^[a-z_]{2,24}$/.test(v || '');

    // pseudo-aleatório com semente: o cartão redesenha sem "pular"
    function semente(txt) {
        let h = 1779033703 ^ txt.length;
        for (let i = 0; i < txt.length; i++) { h = Math.imul(h ^ txt.charCodeAt(i), 3432918353); h = (h << 13) | (h >>> 19); }
        return () => { h = Math.imul(h ^ (h >>> 16), 2246822507); h = Math.imul(h ^ (h >>> 13), 3266489909); h ^= h >>> 16; return (h >>> 0) / 4294967296; };
    }

    /** Linha do tempo com PAUSA: a cena ocupa `dur` e o resto do ciclo fica parado. Devolve o `offset` (0..1) do fim da cena. */
    const ciclo = (dur, pausa) => ({ total: (dur + pausa) * 1000, fim: dur / (dur + pausa) });

    function el(tag, css, pai) {
        const e = document.createElement(tag);
        if (css) e.style.cssText = css;
        if (pai) pai.appendChild(e);
        return e;
    }

    const FORMAS = {
        circulo: 'border-radius:50%;',
        quadrado: 'border-radius:1px;',
        losango: 'border-radius:1px;rotate:45deg;',
        estrela: 'clip-path:polygon(50% 0,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%);',
    };

    // ---------------------------------------------------------------------
    // CAMADAS (cada uma recebe o elemento raiz, os parâmetros já limitados, a pausa e a semente)
    // ---------------------------------------------------------------------
    const CAMADAS = {
        particulas(raiz, p, pausa, rnd) {
            const W = raiz.clientWidth, H = raiz.clientHeight;
            if (!W || !H) return;
            const qtd = Math.round(lim(p.qtd, 3, 40, 16)), tam = lim(p.tam, 2, 12, 5), dur = lim(p.dur, 2, 14, 6);
            const dir = opc(p.dir, ['cima', 'baixo', 'esq', 'dir'], 'cima'), forma = opc(p.forma, Object.keys(FORMAS), 'circulo');
            const c1 = cor(p.cor, '#f2c14e'), c2 = cor(p.cor2, '#ffffff'), halo = lim(p.brilho, 0, 100, 60) / 100;
            const cc = ciclo(dur, pausa), vertical = dir === 'cima' || dir === 'baixo';
            for (let i = 0; i < qtd; i++) {
                const c = i % 2 ? c2 : c1, t = tam * (0.6 + rnd() * 0.8);
                const pos = rnd() * 100;
                const e = el('i', `position:absolute;display:block;width:${t}px;height:${t}px;background:${c};opacity:0;will-change:transform,opacity;${FORMAS[forma]}` +
                    (halo ? `box-shadow:0 0 ${(t * 2.2 * halo).toFixed(1)}px ${(t * 0.5 * halo).toFixed(1)}px ${c};` : '') +
                    (vertical ? `left:${pos}%;top:0;` : `top:${pos}%;left:0;`), raiz);
                const deriva = (rnd() - 0.5) * 36, per = vertical ? H : W;
                const ini = dir === 'cima' || dir === 'esq' ? per + t : -t, fim = dir === 'cima' || dir === 'esq' ? -t : per + t;
                const mov = (v, d) => vertical ? `translate(${d}px, ${v}px)` : `translate(${v}px, ${d}px)`;
                const k = cc.fim;
                e.animate([
                    { transform: mov(ini, 0), opacity: 0, offset: 0 },
                    { transform: mov(ini + (fim - ini) * 0.12, deriva * 0.3), opacity: 1, offset: 0.12 * k },
                    { transform: mov(ini + (fim - ini) * 0.7, deriva), opacity: 0.9, offset: 0.7 * k },
                    { transform: mov(fim, deriva * 0.6), opacity: 0, offset: k },
                    { transform: mov(fim, deriva * 0.6), opacity: 0, offset: 1 },
                ], { duration: cc.total, iterations: Infinity, delay: -rnd() * cc.total, easing: 'linear' });
            }
        },

        brilho(raiz, p, pausa) {
            const c = cor(p.cor, '#7cc4ff'), forca = lim(p.forca, 10, 100, 55, 55) / 100, dur = lim(p.dur, 2, 14, 5);
            const pos = opc(p.pos, ['topo', 'centro', 'base'], 'topo');
            const at = pos === 'topo' ? '50% 0%' : pos === 'base' ? '50% 100%' : '50% 50%';
            const e = el('div', `position:absolute;inset:0;pointer-events:none;opacity:0;will-change:transform,opacity;background:radial-gradient(ellipse 85% 60% at ${at}, ${c}, transparent 70%);`, raiz);
            const cc = ciclo(dur, pausa);
            e.animate([
                { opacity: 0, transform: 'scale(.92)', offset: 0 },
                { opacity: forca, transform: 'scale(1.04)', offset: cc.fim * 0.5 },
                { opacity: 0, transform: 'scale(.92)', offset: cc.fim },
                { opacity: 0, transform: 'scale(.92)', offset: 1 },
            ], { duration: cc.total, iterations: Infinity, easing: 'ease-in-out' });
        },

        raios(raiz, p, pausa, rnd) {
            const W = raiz.clientWidth, H = raiz.clientHeight;
            if (!W || !H) return;
            const qtd = Math.round(lim(p.qtd, 1, 8, 4)), dur = lim(p.dur, 3, 12, 5), c = cor(p.cor, '#bfe3ff');
            const caminhos = ['M12 0 L7 22 L15 24 L6 52 L16 54 L4 96', 'M10 0 L14 18 L6 30 L13 46 L5 70', 'M14 0 L8 16 L16 30 L9 44 L17 62 L10 84'];
            const cc = ciclo(dur, pausa);
            for (let i = 0; i < qtd; i++) {
                const larg = 22 + rnd() * 16, alt = 40 + rnd() * 36;
                const s = el('div', `position:absolute;top:0;left:${(6 + (88 / qtd) * i + rnd() * (60 / qtd)).toFixed(1)}%;height:${alt.toFixed(0)}%;width:${larg.toFixed(0)}px;opacity:0;transform-origin:50% 0;will-change:transform,opacity;filter:drop-shadow(0 0 6px ${c});`, raiz);
                s.innerHTML = `<svg viewBox="0 0 24 100" preserveAspectRatio="none" width="100%" height="100%"><path d="${caminhos[i % 3]}" fill="none" stroke="${c}" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
                const k = cc.fim, t0 = (0.8 + rnd() * 0.1) * k;
                s.animate([
                    { opacity: 0, transform: 'scaleY(.05)', offset: 0 }, { opacity: 0, transform: 'scaleY(.05)', offset: t0 },
                    { opacity: 1, transform: 'scaleY(1)', offset: t0 + 0.02 * k }, { opacity: 0.2, transform: 'scaleY(1)', offset: t0 + 0.04 * k },
                    { opacity: 1, transform: 'scaleY(1)', offset: t0 + 0.06 * k }, { opacity: 0, transform: 'scaleY(1)', offset: Math.min(t0 + 0.1 * k, k) },
                    { opacity: 0, transform: 'scaleY(.05)', offset: 1 },
                ], { duration: cc.total, iterations: Infinity, delay: -rnd() * cc.total });
            }
        },

        anel(raiz, p, pausa) {
            const c = cor(p.cor, '#f2c14e'), esp = lim(p.esp, 1, 6, 2), dur = lim(p.dur, 1, 8, 2.4);
            const e = el('div', `position:absolute;inset:18.75%;border-radius:50%;border:${esp}px solid ${c};box-shadow:0 0 ${esp * 4}px ${c};opacity:0;will-change:transform,opacity;`, raiz);
            const cc = ciclo(dur, pausa);
            e.animate([
                { transform: 'scale(1)', opacity: 0.9, offset: 0 }, { transform: 'scale(1.55)', opacity: 0, offset: cc.fim }, { transform: 'scale(1.55)', opacity: 0, offset: 1 },
            ], { duration: cc.total, iterations: Infinity, easing: 'ease-out' });
        },

        orbita(raiz, p, pausa) {
            const c = cor(p.cor, '#ffffff'), qtd = Math.round(lim(p.qtd, 1, 6, 3)), tam = lim(p.tam, 2, 10, 4), dur = lim(p.dur, 1, 12, 4);
            const g = el('div', 'position:absolute;inset:12%;will-change:transform;', raiz);
            for (let i = 0; i < qtd; i++) {
                const a = (360 / qtd) * i;
                const arm = el('div', `position:absolute;inset:0;transform:rotate(${a}deg);`, g);
                el('i', `position:absolute;left:50%;top:0;width:${tam}px;height:${tam}px;margin-left:${-tam / 2}px;border-radius:50%;background:${c};box-shadow:0 0 ${tam * 2}px ${c};`, arm);
            }
            const cc = ciclo(dur, pausa);
            g.animate([{ transform: 'rotate(0deg)', offset: 0 }, { transform: 'rotate(360deg)', offset: cc.fim }, { transform: 'rotate(360deg)', offset: 1 }],
                { duration: cc.total, iterations: Infinity, easing: 'linear' });
        },
    };

    // ---------------------------------------------------------------------
    // CAMADA "ARQUIVO": Lottie, imagem (GIF, WebP, APNG, PNG, JPEG) ou vídeo (MP4, WebM) enviado na biblioteca do Estúdio (/estudio).
    // O servidor manda em `p.a` os endereços e as medidas do arquivo (a receita guardada só tem o id); aqui só se aceita endereço do próprio
    // servidor (`/estudio/arquivo/<id>`). O arquivo é só desenhado: tamanho, posição, giro, espelho, opacidade, velocidade e trecho.
    // Custo: no máximo MAX_MIDIAS_ANIMADAS tocam juntas, e onde o efeito é pequeno (foto de mensagem/lista) ou rolando a página mostra a imagem parada.
    // ---------------------------------------------------------------------
    const LOTTIE_URL = '/static/js/vendor/lottie_light.min.js?v=5.12.2';      // a versão "light": não tem motor de expressões (não roda código)
    const RE_ARQ = /^\/estudio\/arquivo\/[0-9a-f]{12}(\/capa)?$/;
    const MAX_MIDIAS_ANIMADAS = 6;
    const LARGURA_MIN_ANIMADA = 96;                       // caixa do efeito de avatar menor que isto (mensagens, listas): imagem parada
    const ativas = new Set();                             // animações pesadas tocando agora
    const midias = new Set();                             // { raiz, pausar(), retomar(), destruir() }: o que a rolagem/aba escondida pausam
    let lottiePromessa = null;

    function carregarLottie() {
        if (window.lottie) return Promise.resolve(window.lottie);
        if (!lottiePromessa) {
            lottiePromessa = new Promise((ok, falha) => {
                const s = document.createElement('script');
                s.src = LOTTIE_URL; s.async = true;
                s.onload = () => (window.lottie ? ok(window.lottie) : falha(new Error('lottie')));
                s.onerror = () => { lottiePromessa = null; falha(new Error('lottie')); };
                document.head.appendChild(s);
            });
        }
        return lottiePromessa;
    }

    function pausarMidias(parar) { midias.forEach((m) => { try { parar ? m.pausar() : m.retomar(); } catch (e) { /* ignora */ } }); }

    /** Solta o que ficou de montagens que sumiram da página (cartão fechado, lista refeita): animação de Lottie e timers não podem ficar vivos. */
    function varrerMidias() {
        midias.forEach((m) => { if (!m.raiz.isConnected) { try { m.destruir(); } catch (e) { /* ignora */ } midias.delete(m); } });
    }

    CAMADAS.arquivo = function (raiz, p, pausa, rnd, ctx) {
        const a = p.a;
        if (!a || !RE_ARQ.test(a.url || '') || (a.capa && !RE_ARQ.test(a.capa))) return;      // arquivo apagado da biblioteca (a:null) ou endereço estranho: pula a camada
        const k = opc(a.k, ['lottie', 'imagem', 'video'], '');
        if (!k) return;
        const escala = lim(p.escala, 10, 400, 100) / 100, x = lim(p.x, -100, 100, 0), y = lim(p.y, -100, 100, 0), giro = lim(p.giro, -180, 180, 0);
        const esp = opc(p.espelho, ['nao', 'horizontal', 'vertical'], 'nao');
        const sx = escala * (esp === 'horizontal' ? -1 : 1), sy = escala * (esp === 'vertical' ? -1 : 1);
        const opac = lim(p.opac, 0, 100, 100) / 100, vel = lim(p.vel, 0.25, 3, 1);
        const ini = lim(p.ini, 0, 95, 0) / 100, fim = Math.max(lim(p.fim, 5, 100, 100) / 100, ini + 0.05);
        const ajuste = opc(p.ajuste, ['conter', 'cobrir', 'esticar'], 'conter');
        const fit = { conter: 'contain', cobrir: 'cover', esticar: 'fill' }[ajuste];
        const wrap = el('div', `position:absolute;inset:0;pointer-events:none;opacity:${opac};transform:translate(${x}%,${y}%) rotate(${giro}deg) scale(${sx},${sy});`, raiz);
        const pequeno = !raiz.classList.contains('ef-pf') && raiz.clientWidth < LARGURA_MIN_ANIMADA;
        const parado = pequeno || ativas.size >= MAX_MIDIAS_ANIMADAS;
        const ficha = {};                                  // identidade desta animação em `ativas`/`midias`
        const registro = { raiz, pausar() {}, retomar() {}, destruir() {} };
        let tm = null;

        const imagem = (src) => {
            const i = new Image();
            i.alt = ''; i.decoding = 'async'; i.draggable = false; i.src = src;
            i.style.cssText = `position:absolute;inset:0;width:100%;height:100%;object-fit:${fit};display:block;`;
            return i;
        };
        const ligar = () => { ativas.add(ficha); midias.add(registro); };
        const soltar = () => { clearTimeout(tm); ativas.delete(ficha); midias.delete(registro); };
        ctx.limpar(soltar);
        registro.destruir = soltar;

        if (k === 'imagem') {
            const animada = !!a.dur && !!a.capa;
            if (!animada || parado) { wrap.appendChild(imagem(a.capa || a.url)); return; }
            ligar();
            let atual = null;
            const mostrar = (src) => { if (atual) atual.remove(); atual = imagem(src); wrap.appendChild(atual); };   // nó novo = a animação recomeça do 1º quadro
            const passada = () => {
                if (!wrap.isConnected) return soltar();
                mostrar(a.url);
                if (pausa > 0) tm = setTimeout(() => { mostrar(a.capa); tm = setTimeout(passada, pausa * 1000); }, Math.max(a.dur, 200));
            };
            passada();
            return;
        }

        if (k === 'video') {
            if (parado) { if (a.capa) wrap.appendChild(imagem(a.capa)); return; }
            ligar();
            const v = document.createElement('video');
            v.muted = true; v.defaultMuted = true; v.playsInline = true; v.preload = 'auto'; v.disablePictureInPicture = true;
            v.setAttribute('aria-hidden', 'true');
            v.style.cssText = `position:absolute;inset:0;width:100%;height:100%;object-fit:${fit};display:block;`;
            if (a.capa) v.poster = a.capa;
            v.playbackRate = vel;
            let dur = 0, t0 = 0, t1 = 0, esperando = false;
            const inteiro = ini === 0 && fim === 1 && pausa === 0;
            v.loop = inteiro;                                            // sem aparar nem pausa: o laço nativo (sem emenda)
            const reiniciar = () => { esperando = false; if (!wrap.isConnected) return soltar(); v.currentTime = t0; v.play().catch(() => {}); };
            const fimDaPassada = () => { if (esperando) return; esperando = true; v.pause(); tm = setTimeout(reiniciar, pausa * 1000); };
            v.addEventListener('loadedmetadata', () => { dur = v.duration || 0; t0 = ini * dur; t1 = fim * dur; if (t0 > 0) v.currentTime = t0; });
            v.addEventListener('loadeddata', () => { v.play().catch(() => {}); });
            if (!inteiro) {
                v.addEventListener('ended', fimDaPassada);
                const vigia = setInterval(() => {
                    if (!wrap.isConnected) { clearInterval(vigia); return soltar(); }
                    if (dur && !esperando && !v.paused && v.currentTime >= t1 - 0.04) fimDaPassada();
                }, 50);
                ctx.limpar(() => clearInterval(vigia));
            }
            registro.pausar = () => { if (!esperando) v.pause(); };
            registro.retomar = () => { if (!esperando && wrap.isConnected) v.play().catch(() => {}); };
            const antes = registro.destruir;
            registro.destruir = () => { antes(); try { v.pause(); v.removeAttribute('src'); v.load(); } catch (e) { /* ignora */ } };
            ctx.limpar(registro.destruir);
            v.src = a.url;
            wrap.appendChild(v);
            return;
        }

        // Lottie: a biblioteca só baixa na 1ª vez que aparece um (nada pesa em quem nunca vê um efeito assim)
        carregarLottie().then((lottie) => {
            if (!wrap.isConnected || !ctx.valido()) return;
            const anim = lottie.loadAnimation({
                container: wrap, renderer: 'svg', loop: false, autoplay: false, path: a.url,
                rendererSettings: { preserveAspectRatio: { conter: 'xMidYMid meet', cobrir: 'xMidYMid slice', esticar: 'none' }[ajuste], progressiveLoad: true, hideOnTransparent: true },
            });
            anim.setSpeed(vel);
            let esperando = false;
            anim.addEventListener('DOMLoaded', () => {
                const total = anim.totalFrames, f0 = Math.floor(ini * total), f1 = Math.max(f0 + 1, Math.floor(fim * total));
                if (parado) { anim.goToAndStop(f0 + Math.floor((f1 - f0) * 0.45), true); return; }      // pequeno ou muita coisa tocando: um quadro bonito parado
                ligar();
                const tocar = () => { esperando = false; if (!wrap.isConnected) return soltar(); anim.playSegments([f0, f1], true); };
                anim.addEventListener('complete', () => { esperando = true; tm = setTimeout(tocar, pausa * 1000); });
                registro.pausar = () => { if (!esperando) anim.pause(); };
                registro.retomar = () => { if (!esperando && wrap.isConnected) anim.play(); };
                tocar();
            });
            const antes = registro.destruir;
            registro.destruir = () => { antes(); try { anim.destroy(); } catch (e) { /* ignora */ } };
            ctx.limpar(() => { try { anim.destroy(); } catch (e) { /* ignora */ } });
        }).catch(() => { /* sem a biblioteca (rede) o efeito simplesmente não aparece */ });
    };

    // ---------------------------------------------------------------------
    // MONTAGEM
    // ---------------------------------------------------------------------
    // Um efeito de avatar pode ter DUAS partes: atrás da foto (`.ef-av`) e por cima dela (`.ef-av-sobre`, só camadas "arquivo" com lugar = sobre).
    function camadasDaParte(raiz, camadas) {
        const avatar = raiz.classList.contains('ef-av') || raiz.classList.contains('ef-av-sobre');
        if (!avatar) return camadas;
        const sobre = raiz.dataset.parte === 'sobre';
        return camadas.filter((c) => {
            const porCima = c && c.tipo === 'arquivo' && c.lugar === 'sobre';
            return sobre ? porCima : !porCima;
        });
    }

    function montar(raiz, receita, id) {
        (raiz._ecLimpa || []).splice(0).forEach((f) => { try { f(); } catch (e) { /* ignora */ } });      // solta animação/timers da montagem anterior
        raiz._ecLimpa = raiz._ecLimpa || [];
        raiz._ecGen = (raiz._ecGen || 0) + 1;
        const gen = raiz._ecGen;
        raiz.replaceChildren();
        raiz.style.overflow = raiz.classList.contains('ef-pf') ? 'hidden' : '';
        raiz.style.mixBlendMode = '';
        if (reduz() || !receita || !Array.isArray(receita.camadas)) return;
        const pausa = lim(receita.pausa, 0, 15, 0);
        raiz.style.mixBlendMode = { tela: 'screen', somar: 'plus-lighter' }[receita.mistura] || '';       // o efeito inteiro se mistura com o cartão/foto atrás
        const ctx = { limpar: (f) => raiz._ecLimpa.push(f), valido: () => raiz._ecGen === gen };
        camadasDaParte(raiz, receita.camadas.slice(0, 6)).forEach((c, i) => {
            const f = c && CAMADAS[c.tipo];
            if (f) { try { f(raiz, c, pausa, semente(`${id}:${i}`), ctx); } catch (e) { /* um erro numa camada não derruba as outras */ } }
        });
    }

    function montarElemento(e) {
        const id = e.dataset.ec, r = reg[id];
        if (!idOk(id) || !r) return;
        const w = e.clientWidth, h = e.clientHeight;
        if (!w || !h) return;                               // escondido: o ResizeObserver chama de novo quando aparecer
        if (e._ec && e._ec.v === versao && e._ec.w === w && e._ec.h === h) return;
        e._ec = { v: versao, w, h };
        montar(e, r.receita, id);
    }

    let ro = null;
    function varrer(raizBusca) {
        (raizBusca || document).querySelectorAll('[data-ec]').forEach((e) => {
            if (!e._ecObs) {
                e._ecObs = true;
                if (ro) ro.observe(e);
            }
            montarElemento(e);
        });
    }

    let agendado = false;
    function agendar() {
        if (agendado) return;
        agendado = true;
        requestAnimationFrame(() => { agendado = false; varrer(); });
    }

    function iniciar() {
        if (ro || !window.MutationObserver) return;
        ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver((lista) => lista.forEach((x) => montarElemento(x.target))) : null;
        new MutationObserver((muts) => {
            for (const m of muts) { if (m.addedNodes.length) { agendar(); break; } }
        }).observe(document.documentElement, { childList: true, subtree: true });
        // rolando a página: pausa tudo (mesma regra do resto do app: animação não disputa com a rolagem)
        new MutationObserver(() => {
            const parar = document.body.classList.contains('rolando');
            document.querySelectorAll('[data-ec]').forEach((e) => e.getAnimations({ subtree: true }).forEach((a) => { try { parar ? a.pause() : a.play(); } catch (x) { /* ignora */ } }));
            pausarMidias(parar || document.hidden);      // vídeo e Lottie também (imagem animada não dá pra pausar: por isso o limite de quantas tocam juntas)
        }).observe(document.body, { attributes: true, attributeFilter: ['class'] });
        document.addEventListener('visibilitychange', () => pausarMidias(document.hidden || document.body.classList.contains('rolando')));
        setInterval(varrerMidias, 3000);
        varrer();
    }

    // ---------------------------------------------------------------------
    // API
    // ---------------------------------------------------------------------
    return {
        /** Recebe o mapa {id: {tipo, receita}} do servidor (HTML do /chat e evento `efeitos_custom`). Substitui tudo e refaz o que está na tela. */
        registrar(mapa) {
            Object.keys(reg).forEach((k) => delete reg[k]);
            Object.keys(mapa || {}).forEach((k) => { if (idOk(k) && mapa[k] && mapa[k].receita) reg[k] = mapa[k]; });
            versao++;
            agendar();
        },
        tem: (id, tipo) => !!reg[id] && (!tipo || reg[id].tipo === tipo),
        htmlPerfil: (id) => idOk(id) ? `<div class="ef-pf ef-pf-custom" data-ec="${id}" aria-hidden="true"></div>` : '',
        htmlAvatar: (id) => {
            if (!idOk(id)) return '';
            const r = reg[id];
            const porCima = !!r && (r.receita.camadas || []).some((c) => c && c.tipo === 'arquivo' && c.lugar === 'sobre');
            return `<i class="ef-av ef-av-custom" data-ec="${id}" aria-hidden="true"></i>` +
                (porCima ? `<i class="ef-av-sobre ef-av-custom" data-ec="${id}" data-parte="sobre" aria-hidden="true"></i>` : '');     // a 2ª parte: por cima da foto
        },
        /** Prévia ao vivo do editor: monta `receita` direto num elemento (sem registrar). Pro avatar, chame também com o elemento `.ef-av-sobre`. */
        previa(elemento, receita, id) { versao++; elemento._ec = null; montar(elemento, receita, id || 'previa'); },
        iniciar, CAMADAS_NOMES: Object.keys(CAMADAS),
    };
})();
if (typeof document !== 'undefined') { document.addEventListener('DOMContentLoaded', () => Efeitos.iniciar()); if (document.readyState !== 'loading') Efeitos.iniciar(); }
