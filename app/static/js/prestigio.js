/* Prestígio (impulso) de servidor: a janela com o nível, o que cada nível libera e o botão de impulsionar.
   Só desenha e pede: o nível, a Brasa de quem impulsiona e o limite de impulsos são decididos no SERVIDOR (app/prestigio.py).
   Uso (chat.html):  Prestigio.iniciar({ emitir, esc, toast, servidorAtivo, abrirBrasa });  Prestigio.menu(menuEl, srv) (chamado pelo cargos.js ao abrir o menu do servidor)
   Eventos do servidor: prestigio_estado, prestigio_mudou, prestigio_erro.                                                                 */
const Prestigio = (() => {
    let ctx = null, srvAberto = null, ultimo = null;
    const NOMES = ['Comum', 'Em alta', 'Destaque', 'Prestigiado', 'Lendário'];
    const ICONES = ['fa-seedling', 'fa-fire', 'fa-star', 'fa-crown', 'fa-gem'];

    const $ = (id) => document.getElementById(id);
    const E = (v) => ctx.esc(v == null ? '' : v);

    function iniciar(c) { ctx = c; }

    function km(m) {
        if (m >= 15_000_000) return 'o mundo todo';
        return m >= 1000 ? `${Math.round(m / 1000).toLocaleString('pt-BR')} km` : `${m} m`;
    }

    // ---------------------------------------------------------------------
    // item no menu do servidor (aparece pra todo membro)
    // ---------------------------------------------------------------------
    function menu(menuEl, srv) {
        if (!ctx || !menuEl) return;
        let it = $('srv-menu-prestigio');
        if (!it) {
            const ref = $('srv-menu-config-completa') || $('srv-menu-config');
            if (!ref) return;
            ref.insertAdjacentHTML('afterend', '<div class="context-menu-item" id="srv-menu-prestigio">Prestígio e impulso <i class="fa-solid fa-rocket"></i></div>');
            it = $('srv-menu-prestigio');
            it.addEventListener('click', () => { menuEl.style.display = 'none'; const s = ctx.servidorAtivo(); if (s) abrir(s.id); });
        }
        it.style.display = srv ? '' : 'none';
    }

    // ---------------------------------------------------------------------
    // janela
    // ---------------------------------------------------------------------
    function fechar() { const f = $('pr-fundo'); if (f) f.remove(); srvAberto = null; document.removeEventListener('keydown', teclado, true); }
    function teclado(e) { if (e.key === 'Escape') { e.stopPropagation(); fechar(); } }

    function abrir(serverId) {
        fechar();
        srvAberto = Number(serverId);
        const f = document.createElement('div');
        f.id = 'pr-fundo'; f.className = 'pr-fundo';
        f.innerHTML = `<div class="pr-card" role="dialog" aria-modal="true" aria-label="Prestígio do servidor">
            <button type="button" class="pr-x" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button>
            <div id="pr-corpo" class="pr-corpo"><div class="pr-carregando"><i class="fa-solid fa-spinner fa-spin"></i> Carregando…</div></div></div>`;
        document.body.appendChild(f);
        f.addEventListener('mousedown', (e) => { if (e.target === f) fechar(); });
        f.querySelector('.pr-x').addEventListener('click', fechar);
        document.addEventListener('keydown', teclado, true);
        ctx.emitir('prestigio_pedir', { server_id: srvAberto });
    }

    function desenhar(d) {
        const corpo = $('pr-corpo');
        if (!corpo) return;
        ultimo = d;
        const srv = (ctx.servidorAtivo() || {});
        const nome = Number(srv.id) === Number(d.server_id) ? srv.name : '';
        const n = Math.max(0, Math.min(4, Number(d.nivel) || 0));
        const faixa = (d.proximo_pontos != null) ? Math.max(0, Math.min(100, Math.round(d.pontos / d.proximo_pontos * 100))) : 100;
        const niveis = (d.tabela || []).map((t) => `<li class="pr-nivel ${t.nivel === n ? 'atual' : ''} ${t.nivel < n ? 'feito' : ''}" data-n="${Number(t.nivel)}">
            <span class="pr-ico"><i class="fa-solid ${ICONES[t.nivel] || 'fa-star'}"></i></span>
            <div><b>Nível ${Number(t.nivel)} · ${E(t.nome)}</b><small>${Number(t.pontos)} pontos</small>
                <ul><li>Pino no mapa visível a até <b>${E(km(t.alcance_m))}</b></li>${t.cargos_extra ? `<li>+${Number(t.cargos_extra)} cargos</li>` : ''}${t.nivel ? `<li>Barquinho de porte ${Number(t.porte)} no Explorar</li>` : ''}</ul></div></li>`).join('');
        const quem = (d.quem || []).length
            ? `<div class="pr-quem"><small>Quem impulsiona</small>${d.quem.map((q) => `<span class="${q.vale ? '' : 'inativo'}" title="${q.vale ? '' : 'A Brasa dessa pessoa venceu: o impulso volta a contar se ela renovar.'}">${E(q.nome)}</span>`).join('')}</div>`
            : '<div class="pr-quem"><small>Ninguém impulsionou ainda. Seja o primeiro!</small></div>';
        let acao;
        if (d.eu_impulsiono) {
            acao = `<button type="button" class="pr-btn" data-acao="tirar"><i class="fa-solid fa-rocket"></i> Tirar o meu impulso</button><small>Você usa ${Number(d.meus_usados)} de ${Number(d.meus_total)} impulsos.</small>`;
        } else if (!d.brasa_ativa) {
            acao = `<button type="button" class="pr-btn primario" data-acao="brasa"><i class="fa-solid fa-fire"></i> Ativar a ${E(d.brasa_nome)}${d.brasa_gratis ? ' (grátis por enquanto)' : ''}</button><small>Impulsionar um servidor é um benefício da ${E(d.brasa_nome)}.</small>`;
        } else if (d.meus_usados >= d.meus_total) {
            acao = `<button type="button" class="pr-btn" disabled><i class="fa-solid fa-rocket"></i> Impulsionar este servidor</button><small>Você já usou os seus ${Number(d.meus_total)} impulsos. Tire um de outro servidor pra usar aqui.</small>`;
        } else {
            acao = `<button type="button" class="pr-btn primario" data-acao="dar"><i class="fa-solid fa-rocket"></i> Impulsionar este servidor</button><small>Você tem ${Number(d.meus_total) - Number(d.meus_usados)} de ${Number(d.meus_total)} impulsos livres.</small>`;
        }
        corpo.innerHTML = `
            <header class="pr-topo n${n}"><div class="pr-selo"><i class="fa-solid ${ICONES[n]}"></i></div>
                <div><small>Prestígio${nome ? ' de ' + E(nome) : ' do servidor'}</small><h3>Nível ${n} · ${E(NOMES[n])}</h3>
                    <div class="pr-barra" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${faixa}"><i style="width:${faixa}%"></i></div>
                    <small class="pr-pontos">${Number(d.pontos)} pontos${d.proximo_pontos != null ? ` · faltam ${Number(d.faltam)} pro próximo nível` : ' · nível máximo'}</small></div></header>
            <p class="pr-conta">Cada impulso vale <b>${Number(d.pontos_por_impulso)}</b> pontos e cada <b>${Number(d.membros_por_ponto)}</b> membros valem <b>1</b> (até 100 membros).
                Hoje são <b>${Number(d.impulsos)}</b> ${d.impulsos === 1 ? 'impulso' : 'impulsos'} e <b>${Number(d.membros)}</b> membros.</p>
            <div class="pr-acao">${acao}</div>
            ${quem}
            <ol class="pr-niveis">${niveis}</ol>
            <p class="pr-aviso"><i class="fa-solid fa-shield-halved"></i> O nível só estica o alcance do <b>pino do servidor</b> no mapa (de longe, a posição dele aparece aproximada, ~1 km) e
                <b>entrar pelo mapa continua exigindo estar a menos de ${E(km(d.raio_normal_m))}</b>. Ele nunca mostra onde as pessoas estão.</p>`;
        const btn = corpo.querySelector('[data-acao]');
        if (btn) btn.addEventListener('click', () => {
            const a = btn.dataset.acao;
            if (a === 'brasa') { fechar(); if (ctx.abrirBrasa) ctx.abrirBrasa(); return; }
            btn.disabled = true;
            ctx.emitir('prestigio_impulsionar', { server_id: d.server_id, ativo: a === 'dar' });
        });
    }

    function estado(d) {
        if (!d || Number(d.server_id) !== srvAberto) return;
        desenhar(d);
    }

    /** Alguém impulsionou/tirou o impulso: todo membro vê o nível novo (e, com a janela aberta, ela se atualiza). */
    function mudou(d) {
        if (!d) return;
        if (d.subiu) ctx.toast(`${d.por ? d.por + ' impulsionou o servidor: ' : ''}ele chegou ao nível ${Number(d.nivel)} (${NOMES[d.nivel] || ''})!`, 'success');
        else if (d.por) ctx.toast(`${d.por} impulsionou o servidor.`, 'info');
        if (srvAberto === Number(d.server_id)) ctx.emitir('prestigio_pedir', { server_id: srvAberto });
    }

    function erro(d) {
        ctx.toast((d && d.msg) || 'Não foi possível fazer isso agora.', 'warning');
        if (srvAberto) ctx.emitir('prestigio_pedir', { server_id: srvAberto });     // destrava o botão com o estado de verdade
    }

    return { iniciar, menu, abrir, estado, mudou, erro, fechar, nomes: NOMES };
})();
