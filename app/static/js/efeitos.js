/* Motor dos efeitos do Estúdio (receitas JSON -> animação). Objeto global `Efeitos`.
   A receita vem do servidor JÁ normalizada (app/efeitos.py), mas aqui os números são limitados DE NOVO: nada da receita vira
   código, só números/cores/opções de listas fechadas. Só `transform`/`opacity` se mexem (Web Animations API), então vão pra GPU.
   Camada nova = entrada no ESQUEMA do servidor (app/efeitos.py) + uma função em CAMADAS aqui.

   Uso: o cosmeticos.js chama Efeitos.tem(id) / htmlPerfil(id) / htmlAvatar(id) no lugar dos efeitos feitos à mão. O HTML sai vazio
   (`<div data-ec="id">`) e um MutationObserver monta as camadas quando o elemento aparece (e de novo se ele mudar de tamanho). */
const Efeitos = (() => {
    const reg = {};                 // id -> { tipo, receita }
    let versao = 0;                 // sobe a cada registrar(): elementos já montados com receita velha são refeitos
    const reduz = () => window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
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
    // MONTAGEM
    // ---------------------------------------------------------------------
    function montar(raiz, receita, id) {
        raiz.replaceChildren();
        raiz.style.overflow = raiz.classList.contains('ef-pf') ? 'hidden' : '';
        if (reduz() || !receita || !Array.isArray(receita.camadas)) return;
        const pausa = lim(receita.pausa, 0, 15, 0);
        receita.camadas.slice(0, 6).forEach((c, i) => {
            const f = c && CAMADAS[c.tipo];
            if (f) { try { f(raiz, c, pausa, semente(`${id}:${i}`)); } catch (e) { /* um erro numa camada não derruba as outras */ } }
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
        }).observe(document.body, { attributes: true, attributeFilter: ['class'] });
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
        htmlAvatar: (id) => idOk(id) ? `<i class="ef-av ef-av-custom" data-ec="${id}" aria-hidden="true"></i>` : '',
        /** Prévia ao vivo do editor: monta `receita` direto num elemento (sem registrar). */
        previa(elemento, receita, id) { versao++; elemento._ec = null; montar(elemento, receita, id || 'previa'); },
        iniciar, CAMADAS_NOMES: Object.keys(CAMADAS),
    };
})();
if (typeof document !== 'undefined') { document.addEventListener('DOMContentLoaded', () => Efeitos.iniciar()); if (document.readyState !== 'loading') Efeitos.iniciar(); }
