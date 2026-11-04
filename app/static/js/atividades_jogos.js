/* Jogos leves da call, além do xadrez: jogo da velha, pedra-papel-tesoura, forca e dados/sorteio (objeto global AtividadesJogos).
   O servidor (app/jogos.py) decide tudo; aqui só se desenha e se pede. Quem desenha o painel e liga os eventos é static/js/atividades.js,
   que chama `corpo()` (HTML do painel) e `clique()` (botões com data-j). Cadeiras e convite usam os mesmos botões do xadrez (data-t).
   Jogo novo: classe em app/jogos.py + id em JOGOS (python) + entrada em INFO e uma função em CORPOS aqui + cartão no CATALOGO de atividades.js. */
const AtividadesJogos = (function () {
    'use strict';

    const INFO = {
        velha: { nome: 'Jogo da velha', icone: 'fa-hashtag', lados: { x: 'X', o: 'O' } },
        ppt: { nome: 'Pedra, papel e tesoura', icone: 'fa-hand-back-fist', lados: { a: 'Jogador 1', b: 'Jogador 2' } },
        forca: { nome: 'Forca', icone: 'fa-spell-check', lados: {} },
        dados: { nome: 'Dados e sorteio', icone: 'fa-dice', lados: {} },
    };
    const MAO = { pedra: ['fa-hand-back-fist', 'Pedra'], papel: ['fa-hand', 'Papel'], tesoura: ['fa-hand-scissors', 'Tesoura'] };
    const NOME_DADO = { d6: 'D6', d20: 'D20', d100: 'D100' };

    let abrirConvite = false;       // lista de "quem chamar" aberta
    let minhaMao = null;            // o que EU escolhi nesta rodada de pedra-papel-tesoura (só pra mostrar; o servidor guarda o segredo)

    const ehJogo = (tipo) => Object.prototype.hasOwnProperty.call(INFO, tipo);

    function nomeDe(est, id) {
        const p = (est.presentes || []).find((x) => Number(x.id) === Number(id));
        if (p) return p.nome;
        for (const j of Object.values(est.jogadores || {})) if (j && Number(j.id) === Number(id)) return j.nome;
        return 'a pessoa';
    }
    function meuLado(est, h) {
        for (const [l, j] of Object.entries(est.jogadores || {})) if (j && Number(j.id) === h.meuId()) return l;
        return null;
    }
    function avatar(j, h) {
        if (!j) return '<i class="fa-solid fa-chair"></i>';
        const u = h.escUrl(j.avatar);
        return u ? `<img src="${u}" alt="">` : h.esc(String(j.nome || '?')[0].toUpperCase());
    }

    // ---------------------------------------------------------------------------------------------------------------
    // Cadeiras + convite (jogos de assento)
    // ---------------------------------------------------------------------------------------------------------------
    function cadeiras(est, h) {
        const eu = meuLado(est, h);
        const info = INFO[est.tipo];
        const reservado = est.reserva_restante > 0 ? est.reservado_para : null;
        let html = '<div class="aj-mesa">';
        est.lados.forEach((l) => {
            const j = est.jogadores[l];
            const vez = est.situacao === 'jogando' && est.vez === l;
            const guardada = !j && reservado;
            html += `<div class="at-j${vez ? ' vez' : ''}${j && j.presente === false ? ' ausente' : ''}">
                <div class="at-av">${avatar(j, h)}</div>
                <div class="at-jn"><b>${j ? h.esc(j.nome) : (guardada ? 'Guardada pra ' + h.esc(nomeDe(est, reservado)) : 'Cadeira livre')}</b>
                <small>${h.esc(info.lados[l] || l)}${j && j.presente === false ? ' · saiu da call' : ''}${vez ? ' · jogando agora' : ''}</small></div>
                ${!j && !eu && est.situacao === 'aguardando' && (!guardada || Number(reservado) === h.meuId()) ? `<button type="button" data-t="sentar" data-lado="${l}">Sentar aqui</button>` : ''}
            </div>`;
        });
        html += '</div>';
        // convidar: quem está na mesa (ou abriu o jogo) escolhe quem chamar; a cadeira livre fica guardada pra pessoa por 1 minuto
        const livres = est.lados.filter((l) => !est.jogadores[l]).length;
        const podeChamar = est.situacao === 'aguardando' && livres > 0 && (eu || Number(est.iniciador_id) === h.meuId());
        if (podeChamar) {
            const fora = (est.presentes || []).filter((p) => Number(p.id) !== h.meuId() && !p.ouvinte && !Object.values(est.jogadores).some((j) => j && Number(j.id) === Number(p.id)));
            html += `<div class="aj-conv">
                ${reservado ? `<div class="at-banner"><i class="fa-solid fa-paper-plane"></i>Convite enviado a ${h.esc(nomeDe(est, reservado))}. A cadeira fica guardada por até 1 minuto.</div>` : ''}
                <button type="button" class="sec" data-j="convidar-abrir"${fora.length ? '' : ' disabled'}>${fora.length ? (abrirConvite ? 'Fechar a lista' : 'Convidar alguém da call') : 'Ninguém mais na call pra chamar'}</button>
                ${abrirConvite && fora.length ? `<div class="aj-lista">${fora.map((p) => `<button type="button" class="aj-pessoa" data-j="convidar" data-id="${Number(p.id)}"><span class="at-av">${avatar(p, h)}</span><b>${h.esc(p.nome)}</b><small>Chamar</small></button>`).join('')}</div>` : ''}
            </div>`;
        }
        return html;
    }

    function acoesMesa(est, h, extra) {
        const eu = meuLado(est, h);
        let a = extra || '';
        if (est.situacao === 'aguardando') {
            if (eu) a += '<button type="button" class="sec" data-t="sair">Levantar da cadeira</button>';
            else if (est.lados.some((l) => !est.jogadores[l]) && !(est.reserva_restante > 0 && Number(est.reservado_para) !== h.meuId())) a += '<button type="button" data-t="sentar" data-lado="qualquer">Jogar também</button>';
        } else if (est.situacao === 'jogando' && eu) a += '<button type="button" class="perigo" data-j="desistir">Desistir</button>';
        else if (est.situacao === 'fim' && eu) a += '<button type="button" data-j="revanche">Revanche</button>';
        return a ? `<div class="at-acoes">${a}</div>` : '';
    }

    function banner(texto, icone, cls) {
        return `<div class="at-banner${cls ? ' ' + cls : ''}"><i class="fa-solid ${icone}"></i>${texto}</div>`;
    }

    // ---------------------------------------------------------------------------------------------------------------
    // Jogo da velha
    // ---------------------------------------------------------------------------------------------------------------
    function corpoVelha(est, h) {
        const eu = meuLado(est, h);
        const r = est.resultado;
        const venc = r && r.vencedor ? est.jogadores[r.vencedor] : null;
        let b;
        if (est.situacao === 'aguardando') b = banner(eu ? 'Esperando mais um jogador sentar.' : 'Esperando os dois jogadores sentarem.', 'fa-hourglass-half');
        else if (r) b = banner(r.vencedor ? `${h.esc(venc ? venc.nome : r.vencedor.toUpperCase())} venceu${r.motivo === 'desistencia' ? ' (desistência)' : ''}!` : 'Deu velha: empate.', 'fa-flag-checkered', 'fim');
        else if (eu && est.vez === eu) b = banner('Sua vez.', 'fa-hand-pointer', 'vez');
        else if (!eu) b = banner('Você está assistindo.', 'fa-eye');
        else b = banner('Vez de quem joga do outro lado…', 'fa-hourglass-half');
        const linha = est.linha || [];
        const grade = est.casas.map((c, i) => `<button type="button" class="aj-casa${c ? ' ' + c : ''}${linha.includes(i) ? ' ganha' : ''}" data-j="velha" data-casa="${i}" aria-label="Casa ${i + 1}${c ? ': ' + c.toUpperCase() : ''}"${c || r || est.situacao !== 'jogando' || est.vez !== eu ? ' disabled' : ''}>${c ? c.toUpperCase() : ''}</button>`).join('');
        return `${cadeiras(est, h)}<div class="aj-velha" role="grid" aria-label="Jogo da velha">${grade}</div>${b}${acoesMesa(est, h)}`;
    }

    // ---------------------------------------------------------------------------------------------------------------
    // Pedra, papel e tesoura
    // ---------------------------------------------------------------------------------------------------------------
    function corpoPpt(est, h) {
        const eu = meuLado(est, h);
        const nome = (l) => (est.jogadores[l] ? h.esc(est.jogadores[l].nome) : INFO.ppt.lados[l]);
        let meio = '', b = '', extra = '';
        if (est.situacao === 'aguardando') b = banner(eu ? 'Esperando mais um jogador sentar.' : 'Esperando os dois jogadores sentarem.', 'fa-hourglass-half');
        else {
            const placar = `<div class="aj-placar"><span>${nome('a')}</span><b>${est.placar.a}</b><i>×</i><b>${est.placar.b}</b><span>${nome('b')}</span></div>`;
            const rev = est.revelado;
            if (rev) {
                const maos = ['a', 'b'].map((l) => `<div class="aj-mao ${rev.vencedor === l ? 'venceu' : ''}"><i class="fa-solid ${MAO[rev[l]][0]}"></i><small>${MAO[rev[l]][1]}</small></div>`).join('');
                meio = `${placar}<div class="aj-revelacao">${maos}</div>`;
                const rv = rev.vencedor ? `${nome(rev.vencedor)} ganhou a rodada ${est.rodada}.` : `Rodada ${est.rodada}: empate.`;
                b = est.resultado ? banner(`${nome(est.resultado.vencedor)} venceu a partida${est.resultado.motivo === 'desistencia' ? ' (desistência)' : ''}!`, 'fa-flag-checkered', 'fim') : banner(rv, 'fa-bolt');
                if (eu && !est.resultado) extra = '<button type="button" data-j="ppt-proxima">Próxima rodada</button>';
            } else if (est.resultado) {
                meio = placar;
                b = banner(`${nome(est.resultado.vencedor)} venceu a partida${est.resultado.motivo === 'desistencia' ? ' (desistência)' : ''}!`, 'fa-flag-checkered', 'fim');
            } else {
                const jaEscolhi = eu && est.escolheu[eu];
                const botoes = Object.keys(MAO).map((k) => `<button type="button" class="aj-escolha${minhaMao === k && jaEscolhi ? ' marcada' : ''}" data-j="ppt" data-valor="${k}"${!eu || jaEscolhi ? ' disabled' : ''}><i class="fa-solid ${MAO[k][0]}"></i><small>${MAO[k][1]}</small></button>`).join('');
                meio = `${placar}<div class="aj-escolhas">${botoes}</div>`;
                if (!eu) b = banner('Você está assistindo. As escolhas aparecem quando os dois jogarem.', 'fa-eye');
                else if (jaEscolhi) b = banner('Escolha feita. Esperando o outro jogador…', 'fa-hourglass-half');
                else b = banner(`Rodada ${est.rodada} (quem fizer 2 pontos ganha). Escolha!`, 'fa-hand-pointer', 'vez');
            }
        }
        if (est.situacao === 'fim' && !est.revelado) { /* fim por desistência */ }
        return `${cadeiras(est, h)}${meio}${b}${acoesMesa(est, h, extra)}`;
    }

    // ---------------------------------------------------------------------------------------------------------------
    // Forca
    // ---------------------------------------------------------------------------------------------------------------
    function desenhoForca(erros) {
        const partes = [
            '<circle cx="110" cy="52" r="14"/>',
            '<line x1="110" y1="66" x2="110" y2="108"/>',
            '<line x1="110" y1="76" x2="90" y2="96"/>',
            '<line x1="110" y1="76" x2="130" y2="96"/>',
            '<line x1="110" y1="108" x2="94" y2="136"/>',
            '<line x1="110" y1="108" x2="126" y2="136"/>',
        ];
        return `<svg class="aj-forca-svg" viewBox="0 0 180 160" role="img" aria-label="${erros} de 6 erros" fill="none" stroke-linecap="round" stroke-width="5">
            <g stroke="currentColor" opacity=".85"><line x1="20" y1="150" x2="120" y2="150"/><line x1="50" y1="150" x2="50" y2="14"/><line x1="50" y1="14" x2="110" y2="14"/><line x1="110" y1="14" x2="110" y2="38"/></g>
            <g stroke="var(--red-color, #da373c)">${partes.slice(0, erros).join('')}</g></svg>`;
    }
    function corpoForca(est, h) {
        const r = est.resultado;
        const mascara = est.mascara.map((c) => `<span class="aj-letra${c === null ? ' vazia' : ''}">${c === null ? '' : h.esc(String(c).toUpperCase())}</span>`).join('');
        const teclas = 'abcdefghijklmnopqrstuvwxyz'.split('').map((l) => {
            const certa = est.acertos.includes(l), errada = est.erradas.includes(l);
            const quem = est.quem && est.quem[l];
            return `<button type="button" class="aj-tecla${certa ? ' certa' : ''}${errada ? ' errada' : ''}" data-j="letra" data-l="${l}"${certa || errada || r ? ' disabled' : ''}${quem ? ` data-tip="Chutada por ${h.esc(quem)}"` : ''}>${l.toUpperCase()}</button>`;
        }).join('');
        let b;
        if (r) b = banner(r.venceu ? 'Vocês acertaram a palavra!' : `Acabaram as chances. A palavra era ${h.esc(String(est.palavra || '').toUpperCase())}.`, 'fa-flag-checkered', 'fim');
        else b = banner(`Todo mundo da call pode chutar. Erros: ${est.erradas.length} de ${est.max_erros}.`, 'fa-users');
        return `<div class="aj-forca">${desenhoForca(est.erradas.length)}
            <div class="aj-forca-dir"><small class="aj-dica">Dica: ${h.esc(est.dica)}</small><div class="aj-palavra">${mascara}</div>
            <div class="aj-erradas">${est.erradas.length ? 'Erradas: ' + est.erradas.map((x) => h.esc(x.toUpperCase())).join(' ') : 'Nenhum erro ainda.'}</div></div></div>
            <div class="aj-teclado">${teclas}</div>${b}${r ? '<div class="at-acoes"><button type="button" data-j="forca-nova">Nova palavra</button></div>' : ''}`;
    }

    // ---------------------------------------------------------------------------------------------------------------
    // Dados e sorteio
    // ---------------------------------------------------------------------------------------------------------------
    function linhaHistorico(e, h) {
        const nome = h.esc(e.quem.nome);
        if (e.tipo === 'moeda') return `<i class="fa-solid fa-coins"></i><span><b>${nome}</b> jogou a moeda: <b>${h.esc(e.texto)}</b></span>`;
        if (e.tipo === 'sorteio') return `<i class="fa-solid fa-hat-wizard"></i><span><b>${nome}</b> sorteou: <b>${h.esc(e.texto)}</b></span>`;
        return `<i class="fa-solid fa-dice"></i><span><b>${nome}</b> rolou ${h.esc(NOME_DADO[e.tipo] || e.tipo)}: <b>${h.esc(e.texto)}</b></span>`;
    }
    function corpoDados(est, h) {
        const ult = est.historico[0];
        const grande = ult
            ? `<div class="aj-resultado"><small>${h.esc(ult.quem.nome)} · ${ult.tipo === 'moeda' ? 'Cara ou coroa' : ult.tipo === 'sorteio' ? 'Sorteio' : h.esc(NOME_DADO[ult.tipo] || ult.tipo)}</small><b>${h.esc(ult.texto)}</b></div>`
            : '<div class="aj-resultado vazio"><small>Nada rolou ainda</small><b>?</b></div>';
        return `${grande}
            <div class="aj-dados">
                <button type="button" data-j="dado" data-d="d6"><i class="fa-solid fa-dice-d6"></i>D6</button>
                <button type="button" data-j="dado" data-d="d20"><i class="fa-solid fa-dice-d20"></i>D20</button>
                <button type="button" data-j="dado" data-d="d100"><i class="fa-solid fa-percent"></i>D100</button>
                <button type="button" data-j="moeda"><i class="fa-solid fa-coins"></i>Moeda</button>
                <button type="button" class="largo" data-j="sortear"><i class="fa-solid fa-hat-wizard"></i>Sortear alguém da call</button>
            </div>
            <div class="aj-hist">${est.historico.length ? est.historico.map((e) => `<div class="aj-h">${linhaHistorico(e, h)}</div>`).join('') : '<div class="at-vazio">O histórico aparece aqui pra todo mundo ver.</div>'}</div>
            ${est.historico.length ? '<div class="at-acoes"><button type="button" class="sec" data-j="dados-limpar">Limpar histórico</button></div>' : ''}`;
    }

    const CORPOS = { velha: corpoVelha, ppt: corpoPpt, forca: corpoForca, dados: corpoDados };

    function corpo(est, h) {
        if (!ehJogo(est.tipo)) return '';
        if (est.tipo === 'ppt' && est.situacao === 'aguardando') minhaMao = null;
        return CORPOS[est.tipo](est, h);
    }

    // Clique num botão com data-j. Devolve true se tratou (e se precisa redesenhar o painel).
    function clique(btn, est, h) {
        const a = btn.dataset.j;
        if (a === 'convidar-abrir') { abrirConvite = !abrirConvite; return true; }
        if (a === 'convidar') { abrirConvite = false; h.emitir('atividade_convidar', { alvo_id: Number(btn.dataset.id) }); return true; }
        if (a === 'velha') { h.acao({ acao: 'jogar', casa: Number(btn.dataset.casa) }); return false; }
        if (a === 'ppt') { minhaMao = btn.dataset.valor; h.acao({ acao: 'escolher', valor: btn.dataset.valor }); return false; }
        if (a === 'ppt-proxima') { minhaMao = null; h.acao({ acao: 'proxima' }); return false; }
        if (a === 'letra') { h.acao({ acao: 'letra', letra: btn.dataset.l }); return false; }
        if (a === 'forca-nova') { h.acao({ acao: 'nova' }); return false; }
        if (a === 'dado') { h.acao({ acao: 'rolar', dado: btn.dataset.d }); return false; }
        if (a === 'moeda') { h.acao({ acao: 'moeda' }); return false; }
        if (a === 'sortear') { h.acao({ acao: 'sortear' }); return false; }
        if (a === 'dados-limpar') { h.acao({ acao: 'limpar' }); return false; }
        if (a === 'desistir') { h.confirmar('Desistir da partida?', 'A vitória fica com o adversário.', () => h.acao({ acao: 'desistir' })); return false; }
        if (a === 'revanche') { minhaMao = null; h.acao({ acao: 'revanche' }); return false; }
        return false;
    }

    return { ehJogo, info: (tipo) => INFO[tipo], corpo, clique, meuLado, nomeDe, _esquecer() { abrirConvite = false; minhaMao = null; } };
})();
