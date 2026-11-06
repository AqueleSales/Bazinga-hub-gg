/* Opções ao compartilhar a tela (Rodada 39). Objeto global `Compartilhar`.
 * Antes o botão ia direto pro seletor do navegador e só dava pra compartilhar "a tela". Agora, antes do seletor, a pessoa escolhe:
 *   - o que quer mostrar (tela inteira / uma janela / uma aba), que vira dica pro navegador (no app do Windows o seletor próprio já lista os monitores e as janelas);
 *   - a qualidade (automática, texto e código, equilibrada, jogos e vídeo, muito fluida);
 *   - o som do computador (desligado por padrão: ligado, quem assiste pode ouvir a própria voz de volta) e o cursor.
 * "Não perguntar de novo" guarda as escolhas neste aparelho (Shift + clique no botão traz esta janela de volta).
 * Só monta o pedido do navegador: nenhuma decisão de segurança mora aqui.
 */
const Compartilhar = (() => {
    'use strict';
    const CHAVE = 'pnt_tela_opc';
    const PRESETS = {
        auto: { nome: 'Automática', desc: 'Segue a qualidade da call e diminui sozinha se tiver muita gente assistindo.', alvo: null },
        texto: { nome: 'Texto e código', desc: 'Nítida, pra ler. 1080p a 15 quadros por segundo.', alvo: { h: 1080, fps: 15 }, hint: 'detail' },
        equilibrada: { nome: 'Equilibrada', desc: '720p a 30 quadros por segundo: serve pra quase tudo.', alvo: { h: 720, fps: 30 }, hint: 'motion' },
        jogo: { nome: 'Jogos e vídeo', desc: 'Mais detalhe em movimento. 1080p a 30 quadros por segundo.', alvo: { h: 1080, fps: 30 }, hint: 'motion' },
        fluida: { nome: 'Muito fluida', desc: 'Pra jogo rápido. 720p a 60 quadros por segundo (pesa mais no seu PC).', alvo: { h: 720, fps: 60 }, hint: 'motion' },
    };
    const SUPERFICIES = [['qualquer', 'fa-display', 'Qualquer', 'Você escolhe na próxima janela'], ['monitor', 'fa-desktop', 'Tela inteira', 'Um monitor completo'],
                         ['window', 'fa-window-maximize', 'Uma janela', 'Só um programa'], ['browser', 'fa-globe', 'Uma aba', 'Uma aba do navegador (com o som dela)']];
    const PADRAO = { qualidade: 'auto', superficie: 'qualquer', audio: false, cursor: true, lembrar: false };
    let ctx = {};

    const ler = () => { try { return { ...PADRAO, ...(JSON.parse(localStorage.getItem(CHAVE) || '{}')) }; } catch (e) { return { ...PADRAO }; } };
    const gravar = (o) => { try { localStorage.setItem(CHAVE, JSON.stringify(o)); } catch (e) {} };
    const limpar = (o) => ({
        qualidade: PRESETS[o.qualidade] ? o.qualidade : 'auto',
        superficie: SUPERFICIES.some(s => s[0] === o.superficie) ? o.superficie : 'qualquer',
        audio: o.audio === true, cursor: o.cursor !== false, lembrar: o.lembrar === true,
    });
    const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    function iniciar(c) { ctx = c || {}; }

    /** Abre a janela e devolve as escolhas (ou null se cancelou). Com "não perguntar de novo" ligado e sem Shift, devolve as guardadas na hora. */
    function perguntar({ forcar, stream } = {}) {
        const salvo = limpar(ler());
        if (salvo.lembrar && !forcar) return Promise.resolve(salvo);
        return new Promise((resolve) => {
            const antigo = document.getElementById('cp-fundo'); if (antigo) antigo.remove();
            const f = document.createElement('div');
            f.id = 'cp-fundo'; f.className = 'modal-overlay cp-fundo';
            f.style.cssText = 'display:flex;';
            f.innerHTML = `<div class="cp-cartao" role="dialog" aria-modal="true" aria-label="Compartilhar tela">
                <div class="cp-topo"><h3><i class="fa-solid fa-display"></i> Compartilhar tela</h3><button type="button" class="cp-x" data-cp="x" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button></div>
                ${stream ? '<div class="cp-aviso"><i class="fa-solid fa-tower-broadcast"></i> Canal de transmissão: uma pessoa por vez. Se alguém já estiver no ar, você entra na vez quando ele parar.</div>' : ''}
                <div class="cp-corpo">
                    <div class="cp-sec">O que mostrar</div>
                    <div class="cp-grade" id="cp-sup">${SUPERFICIES.map(([id, ic, nome, d]) => `<button type="button" class="cp-op" data-sup="${id}"><i class="fa-solid ${ic}"></i><b>${esc(nome)}</b><small>${esc(d)}</small></button>`).join('')}</div>
                    <div class="cp-sec">Qualidade</div>
                    <div class="cp-lista" id="cp-qual">${Object.entries(PRESETS).map(([id, p]) => `<button type="button" class="cp-linha" data-q="${id}"><span class="cp-bolinha"></span><span><b>${esc(p.nome)}</b><small>${esc(p.desc)}</small></span></button>`).join('')}</div>
                    <div class="cp-sec">Som e cursor</div>
                    <label class="cp-chave"><input type="checkbox" id="cp-audio"><span><b>Compartilhar o som do computador</b><small>Ligado, quem assiste ouve o que toca aí. Se você usa caixa de som, a voz da call pode voltar como eco: prefira fone.</small></span></label>
                    <label class="cp-chave"><input type="checkbox" id="cp-cursor"><span><b>Mostrar o cursor do mouse</b></span></label>
                    <label class="cp-chave"><input type="checkbox" id="cp-lembrar"><span><b>Não perguntar de novo</b><small>Usa estas escolhas toda vez. Segure Shift ao clicar no botão de compartilhar pra ver esta janela de novo.</small></span></label>
                </div>
                <div class="cp-rodape"><button type="button" class="btn-cancel" data-cp="x">Cancelar</button><button type="button" class="btn-primary" data-cp="ok"><i class="fa-solid fa-play"></i> Escolher o que compartilhar</button></div></div>`;
            document.body.appendChild(f);
            const estado = { ...salvo };
            const pintar = () => {
                f.querySelectorAll('[data-sup]').forEach(b => b.classList.toggle('on', b.dataset.sup === estado.superficie));
                f.querySelectorAll('[data-q]').forEach(b => b.classList.toggle('on', b.dataset.q === estado.qualidade));
                f.querySelector('#cp-audio').checked = estado.audio; f.querySelector('#cp-cursor').checked = estado.cursor; f.querySelector('#cp-lembrar').checked = estado.lembrar;
            };
            pintar();
            const fechar = (res) => { document.removeEventListener('keydown', tecla, true); f.remove(); resolve(res); };
            const tecla = (e) => { if (e.key === 'Escape') { e.stopPropagation(); fechar(null); } };
            document.addEventListener('keydown', tecla, true);
            f.addEventListener('click', (e) => {
                if (e.target === f) return fechar(null);
                const sup = e.target.closest('[data-sup]'); if (sup) { estado.superficie = sup.dataset.sup; return pintar(); }
                const q = e.target.closest('[data-q]'); if (q) { estado.qualidade = q.dataset.q; return pintar(); }
                const a = e.target.closest('[data-cp]'); if (!a) return;
                if (a.dataset.cp === 'x') return fechar(null);
                estado.audio = f.querySelector('#cp-audio').checked; estado.cursor = f.querySelector('#cp-cursor').checked; estado.lembrar = f.querySelector('#cp-lembrar').checked;
                const final = limpar(estado); gravar(final); fechar(final);
            });
            setTimeout(() => { const ok = f.querySelector('[data-cp="ok"]'); if (ok) ok.focus(); }, 30);
        });
    }

    /** Altura e fps que valem: o preset escolhido, ou (automática) o que a call já calculou. */
    function alvo(op, automatico) {
        const p = PRESETS[op.qualidade] || PRESETS.auto;
        return p.alvo ? { ...p.alvo } : { ...automatico };
    }
    function dica(op) { return (PRESETS[op.qualidade] || {}).hint || null; }
    /** O pedido do getDisplayMedia. `alvoTela` = {h, fps}. */
    function constraints(op, alvoTela) {
        const video = { height: { ideal: alvoTela.h, max: alvoTela.h }, frameRate: { ideal: alvoTela.fps, max: alvoTela.fps }, cursor: op.cursor ? 'always' : 'never' };
        if (op.superficie && op.superficie !== 'qualquer') video.displaySurface = op.superficie;
        return {
            video,
            audio: op.audio ? { echoCancellation: false, noiseSuppression: false, autoGainControl: false, suppressLocalAudioPlayback: true } : false,
            systemAudio: op.audio ? 'include' : 'exclude',
            selfBrowserSurface: 'exclude',           // não oferece esta própria aba (a que gera o espelho infinito)
            surfaceSwitching: 'include',
            monitorTypeSurfaces: 'include',
            preferCurrentTab: false,
        };
    }
    return { iniciar, perguntar, alvo, dica, constraints, PRESETS, _limpar: limpar };
})();
