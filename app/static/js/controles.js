/* Controles de formulário (Rodada 40): mantém o `--p` (quanto da barra está cheia) de todo input[type=range], pra o estilo único de css/controles.css pintar a parte cheia
 * (o WebKit não tem "progresso" nativo). Objeto global `Controles`.
 * `--p` é atualizado: ao arrastar (evento input/change), quando uma barra nasce no DOM, quando min/max/value mudam por atributo e quando o código faz `slider.value = x`
 * (o setter de `value` dos inputs é envolvido só pra barras: o resto do app continua igual e nenhuma tela precisa lembrar de chamar nada). */
const Controles = (() => {
    'use strict';
    function pct(el) {
        const min = el.min === '' ? 0 : Number(el.min), max = el.max === '' ? 100 : Number(el.max), v = Number(el.value);
        return max > min ? Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100)) : 0;
    }
    function atualizar(el) { if (el && el.tagName === 'INPUT' && el.type === 'range') el.style.setProperty('--p', pct(el).toFixed(2) + '%'); }
    function varrer(raiz) {
        if (!raiz || raiz.nodeType !== 1) return;
        if (raiz.tagName === 'INPUT') { atualizar(raiz); return; }
        if (raiz.firstElementChild) raiz.querySelectorAll('input[type="range"]').forEach(atualizar);
    }
    document.addEventListener('input', (e) => atualizar(e.target), true);
    document.addEventListener('change', (e) => atualizar(e.target), true);
    new MutationObserver((muts) => {
        for (const m of muts) {
            if (m.type === 'attributes') atualizar(m.target);
            else m.addedNodes.forEach(varrer);
        }
    }).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['value', 'min', 'max'] });
    try {
        const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
        if (d && d.configurable && d.set && d.get) {
            Object.defineProperty(HTMLInputElement.prototype, 'value', {
                configurable: true, enumerable: d.enumerable, get: d.get,
                set(v) { d.set.call(this, v); if (this.type === 'range') atualizar(this); },
            });
        }
    } catch (e) { /* sem o setter envolvido, a barra se acerta no próximo arrastar */ }
    varrer(document.body || document.documentElement);
    document.addEventListener('DOMContentLoaded', () => varrer(document.body));
    return { atualizar, varrer, pct };
})();
