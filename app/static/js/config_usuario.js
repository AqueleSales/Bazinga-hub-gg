/* Configurações do usuário (Rodada 34): busca, abas novas (Dados e privacidade, Notificações, Cobrança, Brasa, Acessibilidade, Idioma e horário),
   sub-abas de Voz e vídeo e as preferências da conta aplicadas ao app todo.

   O que vale na CONTA (n_<tipo> de notificação, texto, densidade, sublinhar, reduz_mov, hora12) é validado e guardado pelo servidor
   (app/preferencias.py); aqui só se desenha, se manda `salvar_preferencias` e se aplica o resultado em atributos do <html>.
   O que vale só no APARELHO (volume dos sons, sons de call e de XP, volume da call) fica no localStorage de propósito.
   Depende de: socket (do app), esc/escUrl (do app) e, na aba Brasa, Cosm.svgBadge e Passe.abrirBrasa. */
const ConfigUsuario = (() => {
    'use strict';
    let ctx = null;

    // Espelho de preferencias.py (o teste confere ids e padrões). Valores fora da lista o servidor descarta.
    const PADRAO = { texto: 'm', densidade: 'padrao', sublinhar: false, reduz_mov: false, hora12: false,
                     n_dm: true, n_mencao: true, n_amizade: true, n_ligacao: true, n_bazar: true, n_nota: true };
    const TIPOS_AVISO = [
        ['dm', 'Mensagens diretas', 'fa-envelope', 'Quando alguém te escreve numa conversa privada.'],
        ['mencao', 'Menções', 'fa-at', 'Quando alguém cita você com @ num canal.'],
        ['amizade', 'Pedidos de amizade', 'fa-user-plus', 'Quando alguém quer ser seu amigo ou aceita o seu pedido.'],
        ['ligacao', 'Ligações', 'fa-phone', 'Toque e aviso quando um amigo te liga. O cartão da chamada continua aparecendo se você estiver com o app aberto.'],
        ['bazar', 'Bazar', 'fa-store', 'Pedidos, pagamentos e conversas das suas compras e vendas.'],
        ['nota', 'Notas do mapa', 'fa-note-sticky', 'Quando alguém responde a uma nota que você deixou.'],
    ];
    const TAMANHOS = [['p', 'Pequeno'], ['m', 'Padrão'], ['g', 'Grande'], ['gg', 'Muito grande']];
    const DENSIDADES = [['compacta', 'Compacta', 'Mais mensagens na tela.'], ['padrao', 'Padrão', 'O espaçamento de sempre.'], ['ampla', 'Confortável', 'Mais respiro entre as mensagens.']];
    const LS = { somCall: 'pnt_som_call', somXp: 'pnt_som_xp', somVol: 'pnt_som_vol', volSaida: 'pnt_vol_saida' };

    let prefs = Object.assign({}, PADRAO);
    let tocouEm = 0;                      // o eco do que ACABEI de mexer não pode puxar o controle de volta
    let cobranca = null, privacidade = null, brasa = null, cobAba = 'drc';
    let conta = { ghost: false, loc: null, radar: false };   // espelho do que já chega em preferencias_carregadas (pra aba Dados e privacidade)

    const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const $ = (id) => document.getElementById(id);
    const norm = (t) => String(t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    const brl = (c) => 'R$ ' + (Number(c || 0) / 100).toFixed(2).replace('.', ',');
    const num = (n) => Number(n || 0).toLocaleString('pt-BR');
    const reduzMov = () => document.documentElement.hasAttribute('data-reduz-mov') || (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);

    function lsGet(k, padrao) { try { const v = localStorage.getItem(k); return v === null ? padrao : v; } catch (e) { return padrao; } }
    function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* conveniência do aparelho: sem armazenamento, fica no padrão */ } }
    const pctLs = (k) => { const n = Number(lsGet(k, '100')); return Number.isFinite(n) ? Math.max(0, Math.min(100, n)) : 100; };

    // ---------------------------------------------------------------------
    // O que o resto do app consulta
    // ---------------------------------------------------------------------
    function avisa(tipo) { return prefs['n_' + tipo] !== false; }
    function volumeSons() { return pctLs(LS.somVol) / 100; }
    function volumeSaida() { return pctLs(LS.volSaida) / 100; }
    function somCallLigado() { return lsGet(LS.somCall, '1') !== '0'; }
    function somXpLigado() { return lsGet(LS.somXp, '1') !== '0'; }
    const SOM_DO_AVISO = { msg: 'dm', mencao: 'mencao', amizade: 'amizade', toque: 'ligacao' };
    /** O som `tipo` (da tabela SONS do app) pode tocar? Considera o tipo de aviso desligado, os sons de call/XP e o volume zerado. */
    function somPermitido(tipo) {
        if (volumeSons() <= 0) return false;
        if (SOM_DO_AVISO[tipo]) return avisa(SOM_DO_AVISO[tipo]);
        if (tipo === 'call_entrar' || tipo === 'call_sair') return somCallLigado();
        if (tipo === 'xp' || tipo === 'nivel' || tipo === 'missao') return somXpLigado();
        return true;
    }

    /** "Hoje às 19:34" / "19:34" / "7:34 PM" -> no formato escolhido (12 h ou 24 h). Idempotente: dá pra aplicar de novo sem estragar. */
    function horaFmt(txt) {
        if (txt == null) return '';
        const t = String(txt);
        const m = t.match(/(\d{1,2}):(\d{2})(?:\s?([AaPp])\.?[Mm]\.?)?\s*$/);
        if (!m) return t;
        let h = Number(m[1]);
        if (m[3]) h = (h % 12) + (m[3].toLowerCase() === 'p' ? 12 : 0);
        const nova = prefs.hora12 ? `${h % 12 || 12}:${m[2]} ${h >= 12 ? 'PM' : 'AM'}` : `${String(h).padStart(2, '0')}:${m[2]}`;
        return t.slice(0, m.index) + nova;
    }
    function refazerHoras() {
        document.querySelectorAll('.message-timestamp, .grouped-timestamp, .ac-previa .message-timestamp').forEach((el) => {
            const novo = horaFmt(el.textContent);
            if (novo !== el.textContent) el.textContent = novo;
        });
    }

    // ---------------------------------------------------------------------
    // Preferências da conta: aplica, salva, recebe
    // ---------------------------------------------------------------------
    function aplicar() {
        const h = document.documentElement;
        h.dataset.texto = prefs.texto; h.dataset.densidade = prefs.densidade;
        h.toggleAttribute('data-sublinhar', !!prefs.sublinhar);
        h.toggleAttribute('data-reduz-mov', !!prefs.reduz_mov);
        h.toggleAttribute('data-hora12', !!prefs.hora12);
        refazerHoras();
        pintarPrefs();
    }
    function salvar(mudanca) {
        Object.assign(prefs, mudanca);
        tocouEm = Date.now();
        aplicar();
        if (ctx) ctx.socket.emit('salvar_preferencias', mudanca);
    }
    function receber(p) {
        if (!p || Date.now() - tocouEm < 1500) return;
        prefs = Object.assign({}, PADRAO, p);
        aplicar();
    }

    function aplicarVolumeSaida() {
        const v = volumeSaida();
        document.querySelectorAll('#video-grid audio.audio-remoto').forEach((a) => { a.volume = v; });
    }

    // ---------------------------------------------------------------------
    // Peças de HTML repetidas
    // ---------------------------------------------------------------------
    const linha = (titulo, desc, controle, extra) => `<div class="cfg-linha${extra || ''}"><div class="cfg-txt"><h4>${titulo}</h4>${desc ? `<p>${desc}</p>` : ''}</div>${controle || ''}</div>`;
    const interruptor = (id, ligado, extra) => `<div class="toggle-switch tg-app${ligado ? ' active' : ''}" ${id ? `id="${id}"` : ''} ${extra || ''} role="switch" aria-checked="${ligado ? 'true' : 'false'}" tabindex="0"></div>`;
    const vazio = (t) => `<div class="cfg-vazio">${t}</div>`;
    const marcarInt = (el, ligado) => { if (el) { el.classList.toggle('active', !!ligado); el.setAttribute('aria-checked', ligado ? 'true' : 'false'); } };

    // ---------------------------------------------------------------------
    // NOTIFICAÇÕES (por tipo, na conta)
    // ---------------------------------------------------------------------
    function montarNotificacoes() {
        const alvo = $('nt-tipos');
        if (!alvo) return;
        alvo.innerHTML = TIPOS_AVISO.map(([id, nome, icone, desc]) =>
            `<div class="cfg-linha"><i class="fa-solid ${icone} cfg-ico"></i><div class="cfg-txt"><h4>${esc(nome)}</h4><p>${esc(desc)}</p></div>${interruptor('', avisa(id), `data-nt="${id}"`)}</div>`).join('');
    }

    // ---------------------------------------------------------------------
    // ACESSIBILIDADE
    // ---------------------------------------------------------------------
    function montarAcessibilidade() {
        const alvo = $('ac-corpo');
        if (!alvo) return;
        const seg = (chave, lista) => `<div class="cfg-seg" role="radiogroup" data-seg="${chave}">${lista.map(([v, nome]) =>
            `<button type="button" class="cfg-seg-bt" role="radio" data-k="${chave}" data-v="${v}" ${chave === 'texto' ? `style="font-size:${{ p: 12, m: 14, g: 16.5, gg: 19 }[v]}px"` : ''}>${esc(nome)}</button>`).join('')}</div>`;
        alvo.innerHTML = `
            <p class="cfg-lede">Ajustes de leitura e de movimento. Ficam salvos na sua conta e valem em todos os aparelhos.</p>
            <h3 class="cfg-h">Tamanho do texto do chat</h3>
            ${seg('texto', TAMANHOS)}
            <h3 class="cfg-h">Densidade da interface</h3>
            ${seg('densidade', DENSIDADES.map((d) => [d[0], d[1]]))}
            <p class="cfg-dica" id="ac-dens-dica"></p>
            ${linha('Sublinhar links e menções', 'Links e @menções ficam sempre sublinhados, sem depender de passar o mouse em cima.', interruptor('ac-sublinhar', prefs.sublinhar))}
            ${linha('Reduzir movimento', 'Desliga as animações do app (efeitos de perfil, molduras animadas, brilhos e transições). O app também respeita a opção "reduzir movimento" do seu sistema.', interruptor('ac-reduz', prefs.reduz_mov))}
            <h3 class="cfg-h">Como fica</h3>
            <div class="ac-previa"><div class="message first"><div class="message-content">
                <div class="message-header"><span class="message-author">Atena</span><span class="message-timestamp">Hoje às 19:34</span></div>
                <p class="message-text">Bora jogar hoje à noite? Já chamei o <a class="mencao" href="#" onclick="return false">@Ícaro</a> também.</p></div></div>
                <div class="message"><div class="message-content"><p class="message-text">Fechado! Mando o link da <a href="#" onclick="return false">sala</a> daqui a pouco.</p></div></div></div>`;
        pintarPrefs();
    }

    function pintarPrefs() {
        document.querySelectorAll('.cfg-seg-bt').forEach((b) => {
            const ativo = String(prefs[b.dataset.k]) === b.dataset.v;
            b.classList.toggle('active', ativo); b.setAttribute('aria-checked', ativo ? 'true' : 'false');
        });
        marcarInt($('ac-sublinhar'), prefs.sublinhar);
        marcarInt($('ac-reduz'), prefs.reduz_mov);
        const dica = $('ac-dens-dica');
        if (dica) dica.textContent = (DENSIDADES.find((d) => d[0] === prefs.densidade) || DENSIDADES[1])[2];
        document.querySelectorAll('[data-nt]').forEach((el) => marcarInt(el, avisa(el.dataset.nt)));
        document.querySelectorAll('.id-formato').forEach((c) => c.classList.toggle('active', (c.dataset.h === '12') === !!prefs.hora12));
        const ex = $('id-exemplo');
        if (ex) ex.textContent = horaFmt('19:34');
        document.querySelectorAll('.ac-previa .message-timestamp').forEach((el) => { el.textContent = horaFmt('Hoje às 19:34'); });
    }

    // ---------------------------------------------------------------------
    // IDIOMA E HORÁRIO
    // ---------------------------------------------------------------------
    function montarIdioma() {
        const alvo = $('id-corpo');
        if (!alvo) return;
        alvo.innerHTML = `
            <h3 class="cfg-h">Idioma</h3>
            ${linha('Português (Brasil)', 'É o único idioma do Pantheon por enquanto. Quando houver outros, a escolha aparece aqui.', '<span class="cfg-chip">Em uso</span>')}
            <h3 class="cfg-h">Formato da hora</h3>
            <p class="cfg-dica">Vale pra hora das mensagens. Exemplo: <b id="id-exemplo"></b>.</p>
            <div class="radio-card id-formato" data-h="24"><div class="radio-circle"></div><div class="radio-text"><h4>24 horas</h4><p>19:34</p></div></div>
            <div class="radio-card id-formato" data-h="12"><div class="radio-circle"></div><div class="radio-text"><h4>12 horas (AM/PM)</h4><p>7:34 PM</p></div></div>
            <h3 class="cfg-h">Fuso horário</h3>
            ${linha('Horário de Brasília (UTC−3)', 'Todas as horas do Pantheon seguem Brasília, onde quer que você esteja.', '<span class="cfg-chip">Fixo</span>')}`;
        pintarPrefs();
    }

    // ---------------------------------------------------------------------
    // COBRANÇA
    // ---------------------------------------------------------------------
    const ST_PIX = { paga: 'ok', aberta: 'aviso', expirada: 'mudo', cancelada: 'mudo' };
    function linhaPix(x) {
        return `<div class="cb-item"><div class="cb-t"><b>${esc(x.titulo)}</b><small>${esc(x.quando)}${x.teste ? ' · <span class="cfg-chip teste">TESTE</span>' : ''}</small></div>
            <span class="cfg-chip ${ST_PIX[x.status] || 'mudo'}">${esc(x.status_rotulo)}</span><b class="cb-v">${brl(x.valor_cent)}</b></div>`;
    }
    function montarCobranca() {
        const alvo = $('cb-corpo');
        if (!alvo) return;
        const d = cobranca;
        let lista = vazio('Carregando o seu histórico...');
        let resumo = '';
        if (d) {
            const drc = d.drc || { itens: [] };
            resumo = `<div class="cb-resumo">
                <div><small>Saldo</small><b>${num(drc.saldo)} DRC</b></div>
                <div><small>Já ganhou</small><b class="pos">+${num(drc.ganho_total)}</b></div>
                <div><small>Já gastou</small><b class="neg">−${num(drc.gasto_total)}</b></div>
                <div><small>Pix pagos pelo app</small><b>${brl(d.total_pago_cent)}</b></div></div>`;
            if (cobAba === 'drc') {
                lista = (drc.itens || []).length ? (drc.itens || []).map((m) => `<div class="cb-item"><div class="cb-t"><b>${esc(m.titulo)}</b><small>${esc(m.rotulo)} · ${esc(m.hora)}</small></div>
                    <span class="cb-saldo">saldo ${num(m.saldo_apos)}</span><b class="cb-v ${m.delta >= 0 ? 'pos' : 'neg'}">${m.delta >= 0 ? '+' : '−'}${num(Math.abs(m.delta))}</b></div>`).join('')
                    : vazio('Nenhum movimento ainda. Você ganha dracmas subindo de nível, concluindo missões e resgatando o Passe.');
            } else if (cobAba === 'pagos') {
                lista = (d.pix_pagos || []).length ? d.pix_pagos.map(linhaPix).join('') : vazio('Você ainda não pagou nada por Pix pelo app.');
            } else {
                lista = (d.pix_recebidos || []).length ? d.pix_recebidos.map(linhaPix).join('')
                    : vazio('Nenhuma venda paga pelo app nas suas lojas.');
            }
        }
        const g = d && d.gateway;
        const gwTxt = !g ? '' : (!g.ligado ? 'O pagamento pelo app está desligado neste momento.'
            : (g.modo_teste ? 'Pagamento pelo app em <b>modo teste</b>: ninguém é cobrado de verdade.' : 'Pagamento pelo app ligado.'));
        alvo.innerHTML = `
            ${resumo}
            <div class="cfg-seg cb-seg" role="tablist">
                <button type="button" class="cfg-seg-bt${cobAba === 'drc' ? ' active' : ''}" data-cb="drc">Dracmas (DRC)</button>
                <button type="button" class="cfg-seg-bt${cobAba === 'pagos' ? ' active' : ''}" data-cb="pagos">Pix que paguei</button>
                <button type="button" class="cfg-seg-bt${cobAba === 'recebidos' ? ' active' : ''}" data-cb="recebidos">Pix das minhas vendas</button>
            </div>
            <div class="cb-lista">${lista}</div>
            ${cobAba === 'recebidos' ? '<p class="cfg-dica">Aqui aparece o valor cobrado do comprador. O repasse pra você é feito pelo gateway de pagamento; o Pantheon não guarda dinheiro.</p>' : ''}
            <h3 class="cfg-h">Métodos de pagamento</h3>
            ${linha('Dracmas (DRC)', 'A moeda do Armazém. Só se ganha no app (níveis, missões, Passe) e se gasta no app: não se compra com dinheiro, não se transfere e não se saca.')}
            ${linha('Pix pelo app', `Gerado na hora, em cada pedido de loja liberada ou assinatura. Você paga no aplicativo do seu banco e a confirmação é automática. ${gwTxt}`)}
            ${linha('Pix direto ao vendedor', 'Nas lojas que ainda não recebem pelo app, a chave Pix é do vendedor. O Pantheon não guarda nem devolve esse dinheiro.')}
            ${linha('Cartão de crédito', 'Ainda não existe. Nenhum cartão ou dado bancário seu fica salvo no Pantheon.')}
            <h3 class="cfg-h">Assinaturas</h3>
            ${linha(esc((d && d.brasa && d.brasa.nome) || 'Brasa'), d && d.brasa ? (d.brasa.ativo ? `Ativa até ${esc(d.brasa.ate)}.` : 'Você não tem assinatura ativa.') : '', '<button type="button" class="btn cfg-ir" data-ir="set-brasa">Ver</button>')}`;
    }

    // ---------------------------------------------------------------------
    // BRASA (a assinatura; id interno "olimpo")
    // ---------------------------------------------------------------------
    function montarBrasa() {
        const alvo = $('br-corpo');
        if (!alvo) return;
        const b = brasa || (typeof Passe !== 'undefined' && Passe.estadoBrasa ? Passe.estadoBrasa() : null) || {};
        const nome = esc(b.nome || 'Brasa');
        const omega = (typeof Cosm !== 'undefined' && Cosm.svgBadge) ? Cosm.svgBadge('olimpo') : '';
        let status, botao;
        if (!b.nome) { status = 'Carregando...'; botao = ''; }
        else if (b.ativo) {
            status = `Ativa até <b>${esc(b.ate)}</b> (${Number(b.dias) || 0} dia${b.dias === 1 ? '' : 's'}).`;
            botao = b.gratis ? `<button type="button" class="btn btn-primary" data-br="ativar"><i class="fa-solid fa-bolt"></i> Renovar +${Number(b.dias_por_periodo) || 30} dias (grátis)</button>`
                : `<button type="button" class="btn btn-primary" data-br="abrir"><i class="fa-solid fa-qrcode"></i> Renovar por ${brl(b.preco_cent)}</button>`;
        } else {
            status = b.gratis ? 'Você ainda não ativou. Por enquanto é <b>grátis</b>.' : 'Você ainda não assinou.';
            botao = b.gratis ? `<button type="button" class="btn btn-primary" data-br="ativar"><i class="fa-solid fa-bolt"></i> Ativar por ${Number(b.dias_por_periodo) || 30} dias (grátis)</button>`
                : `<button type="button" class="btn btn-primary" data-br="abrir"><i class="fa-solid fa-qrcode"></i> Assinar por ${brl(b.preco_cent)} / ${Number(b.dias_por_periodo) || 30} dias</button>`;
        }
        alvo.innerHTML = `
            <div class="br-heroi">
                <div class="orb-ico bd bd-wrap-olimpo orb-grande br-omega" style="--pt-tam:132px;--bd-cor:#ff7a18">${omega}</div>
                <div class="br-heroi-txt">
                    <h3>${nome}</h3>
                    <p class="br-status">${status}</p>
                    <div class="br-acoes">${botao}</div>
                </div>
            </div>
            <h3 class="cfg-h">O que a ${nome} dá hoje</h3>
            ${linha('Trilha Premium do Passe de Batalha', 'Enquanto a assinatura vale, as recompensas dos dois lados da trilha da temporada ficam liberadas. O que você já resgatou fica com você quando vence.')}
            ${linha('Insígnia Ômega de lava', 'Aparece no seu cartão de perfil: as peças se juntam, a lava esfria e raios correm por dentro. Some quando a assinatura vence.')}
            <p class="cfg-dica">É só isso por enquanto. Quando a ${nome} der mais coisas, elas passam a aparecer aqui.</p>
            <h3 class="cfg-h">Como funciona</h3>
            ${linha('Períodos de ' + (Number(b.dias_por_periodo) || 30) + ' dias', 'Renovar soma os dias ao fim do período atual, sem perder os que sobravam.')}
            ${linha('Pagamento', b.gratis ? 'Hoje a ' + nome + ' é grátis: é só ativar, sem cobrança nenhuma. Se um dia passar a ser paga, o pagamento é por Pix e só vale depois da confirmação.'
                : 'Por Pix, gerado na hora. A ' + nome + ' só liga depois que o pagamento for confirmado.' + (b.modo_teste ? ' <b>Modo teste</b>: ninguém é cobrado de verdade.' : ''))}`;
    }

    // ---------------------------------------------------------------------
    // DADOS E PRIVACIDADE
    // ---------------------------------------------------------------------
    function montarPrivacidade() {
        const alvo = $('pv-corpo');
        if (!alvo) return;
        let am = {};
        try { am = (ctx && ctx.amizades && ctx.amizades()) || {}; } catch (e) { /* a lista de amizades ainda nem foi declarada na página (primeiro desenho, no início) */ }
        const nBloq = (am.bloqueados || []).length, nSil = (am.silenciados || []).length;
        const loc = conta.loc === null ? '' : (conta.loc ? 'ligada' : 'desligada');
        const p = privacidade;
        const contato = p && p.contato ? (/^[^\s@<>]+@[^\s@<>]+\.[a-z]{2,}$/i.test(p.contato) ? `<a href="mailto:${esc(p.contato)}">${esc(p.contato)}</a>` : esc(p.contato)) : '';
        const termos = !p ? 'Carregando...' : (p.termos_em_dia ? `Você aceitou a versão <b>${esc(p.termos_versao)}</b>${p.termos_aceitos_em ? ' em ' + esc(p.termos_aceitos_em) : ''}.`
            : 'Há uma versão dos Termos que você ainda não aceitou.');
        alvo.innerHTML = `
            <p class="cfg-lede">Quem vê o quê, o que o Pantheon guarda e como pegar uma cópia dos seus dados.</p>
            <h3 class="cfg-h">Quem vê o quê</h3>
            ${linha('Modo Fantasma', 'Você some do mapa e do radar de todo mundo, e seus amigos deixam de ver onde você está.', interruptor('pv-fantasma', conta.ghost))}
            ${linha('Localização e radar de pessoas', `Localização ${loc || '...'} · radar ${conta.radar ? 'ligado' : 'desligado'}. Sem localização você não compra, não vende nem planta nada no mapa.`, '<button type="button" class="btn cfg-ir" data-ir="set-geral">Ajustar</button>')}
            ${linha('O seu perfil', 'Amigos e quem divide um servidor com você veem bio, status e links. Quem não tem nada em comum com você vê só nome e foto. O seu e-mail nunca aparece pra outras pessoas.')}
            ${linha('Pessoas bloqueadas e silenciadas', `${nBloq} bloqueada${nBloq === 1 ? '' : 's'} · ${nSil} silenciada${nSil === 1 ? '' : 's'}. Pessoa bloqueada não consegue te chamar nem ver o que você deixa no mapa.`, '<button type="button" class="btn" data-pv="amigos">Gerenciar</button>')}
            ${linha('Seus links', 'Os links que você conectou aparecem no seu perfil pra amigos e pra quem divide servidor com você.', '<button type="button" class="btn cfg-ir" data-ir="set-conexoes">Ver</button>')}
            <h3 class="cfg-h">O que o Pantheon guarda e analisa</h3>
            ${linha('Termos de Uso e Privacidade', termos, '<button type="button" class="btn" data-pv="termos">Ler</button>')}
            ${linha('Análise de segurança', `Mensagens e imagens que parecem perigosas (ameaça, golpe, conteúdo impróprio) são olhadas por uma IA nos bastidores. O que ela segura fica em análise até uma pessoa responsável decidir, e os casos já decididos são apagados em até ${p ? Number(p.retencao_meses) || 12 : 12} meses.${p && !p.guardiao_ligado ? ' <b>Hoje a análise está desligada.</b>' : ''}`)}
            <h3 class="cfg-h">Seus direitos (LGPD)</h3>
            ${linha('Cópia dos seus dados', 'Baixe um arquivo com o que o Pantheon guarda da sua conta: perfil, preferências, amigos, servidores, conexões, itens, movimentos de dracmas, pedidos e cobranças. <b>Não inclui</b> o texto das suas mensagens (só quantas você enviou), a chave Pix da sua loja nem dados de outras pessoas.', '<button type="button" class="btn btn-primary" data-pv="copia"><i class="fa-solid fa-download"></i> Baixar cópia</button>')}
            ${linha('Corrigir seus dados', 'Nome, foto, bio, pronomes e @ você corrige em Meu Perfil.', '<button type="button" class="btn cfg-ir" data-ir="set-perfil">Abrir</button>')}
            ${linha('Excluir a conta', `Ainda não existe um botão de excluir a conta. Pra pedir a exclusão dos seus dados, ${contato ? 'fale com o responsável: ' + contato : 'fale com o responsável pelo Pantheon (o contato fica na página dos Termos)'}.`)}`;
    }

    function baixarCopia(botao) {
        if (botao) botao.disabled = true;
        fetch('/api/meus-dados', { credentials: 'same-origin' })
            .then((r) => r.ok ? r.blob() : r.json().catch(() => ({})).then((j) => { throw new Error(j.error || 'Não consegui montar a cópia agora.'); }))
            .then((blob) => {
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = 'meus-dados-pantheon.json';
                document.body.appendChild(a); a.click(); a.remove();
                setTimeout(() => URL.revokeObjectURL(url), 4000);
                ctx.toast('Cópia dos seus dados baixada.', 'success');
            })
            .catch((e) => ctx.toast(e.message || 'Não consegui baixar agora.', 'error'))
            .finally(() => { if (botao) botao.disabled = false; });
    }

    // ---------------------------------------------------------------------
    // VOZ E VÍDEO: sub-abas e sons
    // ---------------------------------------------------------------------
    function sub(nome) {
        document.querySelectorAll('#voz-subs .cfg-sub-bt').forEach((b) => b.classList.toggle('active', b.dataset.sub === nome));
        document.querySelectorAll('#set-voz .cfg-sub-pagina').forEach((p) => p.classList.toggle('active', p.dataset.sub === nome));
    }
    function pintarSons() {
        marcarInt($('tg-som-call'), somCallLigado());
        marcarInt($('tg-som-xp'), somXpLigado());
        const v = $('som-vol'), s = $('vol-saida');
        if (v) { v.value = pctLs(LS.somVol); $('som-vol-v').textContent = v.value + '%'; }
        if (s) { s.value = pctLs(LS.volSaida); $('vol-saida-v').textContent = s.value + '%'; }
    }

    // ---------------------------------------------------------------------
    // Ir pra uma aba (e sub-aba) / busca
    // ---------------------------------------------------------------------
    function irPara(alvoId, subNome) {
        const tab = document.querySelector(`.set-tab[data-target="${alvoId}"]`);
        if (tab) tab.click();
        if (subNome) sub(subNome);
    }
    const GRUPOS = { 'set-perfil': 'Configurações de usuário', 'set-privacidade': 'Configurações de usuário', 'set-notificacoes': 'Configurações de usuário', 'set-inventario': 'Configurações de usuário',
                     'set-cobranca': 'Cobrança', 'set-brasa': 'Cobrança', 'set-aparencia': 'Configurações do app', 'set-acessibilidade': 'Configurações do app', 'set-voz': 'Configurações do app',
                     'set-idioma': 'Configurações do app', 'set-geral': 'Configurações do app', 'set-conexoes': 'Apps' };
    const SEL_ITEM = '.cfg-linha, .discord-toggle, .pf-bloco-tit, .cfg-h, .cfg-info-item, .radio-card, .cfg-campo, .tc-linha, .pf-grupo, details.cfg-detalhes, .cfg-seg';
    let restaurar = null;                 // {secao, tab}: o que estava aberto antes da busca

    function tituloDe(el) {
        const t = el.querySelector('h4, summary, .control-label, label, b') || el;
        return (t.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 70);
    }
    function indice() {
        const itens = [];
        document.querySelectorAll('#settings-modal .settings-content > .set-section').forEach((sec) => {
            if (sec.id === 'set-busca-res') return;
            const tab = document.querySelector(`.set-tab[data-target="${sec.id}"]`);
            if (!tab) return;
            const aba = tab.textContent.trim();
            itens.push({ sec: sec.id, aba, titulo: aba, texto: norm(aba + ' ' + (GRUPOS[sec.id] || '')), el: null, tipoAba: true });
            const vistos = new Set();
            sec.querySelectorAll(SEL_ITEM).forEach((el) => {
                const titulo = el.classList.contains('cfg-seg') ? ((el.previousElementSibling && el.previousElementSibling.textContent) || '').trim() : tituloDe(el);
                if (!titulo || vistos.has(titulo)) return;
                vistos.add(titulo);
                const pagina = el.closest('.cfg-sub-pagina');
                const todo = el.textContent.replace(/\s+/g, ' ').trim();
                const corpo = todo.startsWith(titulo) ? todo.slice(titulo.length).trim() : todo;       // o título já aparece em cima: o trecho é só a descrição
                itens.push({ sec: sec.id, aba, titulo, sub: pagina ? pagina.dataset.sub : null, texto: norm(titulo + ' ' + todo), corpo, el });
            });
        });
        return itens;
    }
    function buscar(consulta) {
        const q = norm(consulta).trim();
        const res = $('set-busca-res');
        if (!res) return;
        if (!q) { limparBusca(); return; }
        if (!restaurar) restaurar = { secao: (document.querySelector('.settings-content > .set-section.active') || {}).id || 'set-perfil' };
        const palavras = q.split(/\s+/).filter(Boolean);
        const achados = indice().filter((i) => palavras.every((p) => i.texto.includes(p)));
        achados.sort((a, b) => (b.tipoAba ? 1 : 0) - (a.tipoAba ? 1 : 0));
        document.querySelectorAll('.settings-content > .set-section').forEach((s) => s.classList.remove('active'));
        document.querySelectorAll('.set-tab').forEach((t) => t.classList.remove('active'));
        res.classList.add('active');
        resultados = achados.slice(0, 40);
        res.innerHTML = `<h2 class="set-title">Resultados para “${esc(consulta.trim())}”</h2>` + (resultados.length
            ? `<div class="bs-lista">${resultados.map((i, n) => `<button type="button" class="bs-item" data-bs="${n}">
                <span class="bs-t">${i.tipoAba ? '<i class="fa-solid fa-arrow-right"></i> Abrir a aba ' : ''}${esc(i.titulo)}</span>
                <span class="bs-c">${esc(i.aba)}${i.sub ? ' › ' + esc(({ voz: 'Voz', avancado: 'Avançado', sons: 'Sons', transmissao: 'Transmissão' })[i.sub] || '') : ''}</span>
                ${!i.tipoAba && i.corpo ? `<span class="bs-d">${esc(i.corpo.slice(0, 130))}${i.corpo.length > 130 ? '…' : ''}</span>` : ''}</button>`).join('')}</div>`
            : '<div class="cfg-vazio">Nada encontrado. Tente outra palavra, como “som”, “texto”, “localização” ou “pagamento”.</div>');
    }
    let resultados = [];
    function limparBusca(voltar) {
        const campo = $('set-busca-campo');
        if (campo) campo.value = '';
        const res = $('set-busca-res');
        if (res) res.classList.remove('active');
        if (restaurar && voltar !== false) {
            const sec = $(restaurar.secao);
            const tab = document.querySelector(`.set-tab[data-target="${restaurar.secao}"]`);
            if (sec) sec.classList.add('active');
            if (tab) tab.classList.add('active');
        }
        restaurar = null;
    }
    function abrirResultado(n) {
        const i = resultados[n];
        if (!i) return;
        const el = i.el;
        limparBusca(false);
        irPara(i.sec, i.sub);
        if (!el) return;
        setTimeout(() => {
            el.scrollIntoView({ block: 'center', behavior: reduzMov() ? 'auto' : 'smooth' });
            el.classList.add('set-achado');
            setTimeout(() => el.classList.remove('set-achado'), 2400);
        }, 60);
    }

    // ---------------------------------------------------------------------
    // Cliques (um ouvinte só, nas Configurações)
    // ---------------------------------------------------------------------
    function aoClicar(e) {
        const alvo = e.target;
        const ir = alvo.closest('.cfg-ir[data-ir]');
        if (ir) { e.preventDefault(); irPara(ir.dataset.ir, ir.dataset.sub); return; }
        const subBt = alvo.closest('#voz-subs .cfg-sub-bt');
        if (subBt) { sub(subBt.dataset.sub); return; }
        const res = alvo.closest('.bs-item[data-bs]');
        if (res) { abrirResultado(Number(res.dataset.bs)); return; }

        const nt = alvo.closest('[data-nt]');
        if (nt) { salvar({ ['n_' + nt.dataset.nt]: !avisa(nt.dataset.nt) }); return; }
        const seg = alvo.closest('.cfg-seg-bt[data-k]');
        if (seg) {
            const v = seg.dataset.v;
            salvar({ [seg.dataset.k]: v === 'true' ? true : v === 'false' ? false : v });
            return;
        }
        const cb = alvo.closest('[data-cb]');
        if (cb) { cobAba = cb.dataset.cb; montarCobranca(); return; }
        const fmt = alvo.closest('.id-formato');
        if (fmt) { salvar({ hora12: fmt.dataset.h === '12' }); return; }
        if (alvo.closest('#ac-sublinhar')) { salvar({ sublinhar: !prefs.sublinhar }); return; }
        if (alvo.closest('#ac-reduz')) { salvar({ reduz_mov: !prefs.reduz_mov }); return; }

        if (alvo.closest('#pv-fantasma')) { ctx.socket.emit('alternar_fantasma', { ativo: !conta.ghost }); return; }
        const pv = alvo.closest('[data-pv]');
        if (pv) {
            if (pv.dataset.pv === 'copia') baixarCopia(pv);
            else if (pv.dataset.pv === 'termos') window.open('/termos', '_blank', 'noopener');
            else if (pv.dataset.pv === 'amigos' && ctx.irParaAmigos) ctx.irParaAmigos('bloqueados');
            return;
        }
        const br = alvo.closest('[data-br]');
        if (br) {
            if (br.dataset.br === 'ativar') ctx.socket.emit('olimpo_ativar', {});
            else if (typeof Passe !== 'undefined' && Passe.abrirBrasa) Passe.abrirBrasa();
            return;
        }
        if (alvo.closest('#tg-som-call')) { lsSet(LS.somCall, somCallLigado() ? '0' : '1'); pintarSons(); if (somCallLigado() && ctx.tocar) ctx.tocar('call_entrar'); return; }
        if (alvo.closest('#tg-som-xp')) { lsSet(LS.somXp, somXpLigado() ? '0' : '1'); pintarSons(); if (somXpLigado() && ctx.tocar) ctx.tocar('xp'); return; }
        if (alvo.closest('#som-vol-testar') && ctx.tocar) { ctx.tocar('msg', true); return; }
    }

    function aoMexerNoControle(e) {
        const t = e.target;
        if (t.id === 'som-vol') { lsSet(LS.somVol, t.value); $('som-vol-v').textContent = t.value + '%'; }
        else if (t.id === 'vol-saida') { lsSet(LS.volSaida, t.value); $('vol-saida-v').textContent = t.value + '%'; aplicarVolumeSaida(); }
    }

    // Interruptores são <div>: Enter e Espaço também acionam (teclado)
    function aoTeclar(e) {
        if ((e.key === 'Enter' || e.key === ' ') && e.target.matches && e.target.matches('.toggle-switch.tg-app[role="switch"][tabindex]')) {
            e.preventDefault(); e.target.click();
        }
    }

    // ---------------------------------------------------------------------
    // Início
    // ---------------------------------------------------------------------
    function iniciar(contexto) {
        ctx = contexto;
        const raiz = $('settings-modal');
        if (!raiz) return;
        // a página já nasce com os atributos certos (texto, densidade...); aqui só se lê de volta o que o servidor mandou no HTML
        const h = document.documentElement;
        prefs.texto = h.dataset.texto || prefs.texto; prefs.densidade = h.dataset.densidade || prefs.densidade;
        prefs.sublinhar = h.hasAttribute('data-sublinhar'); prefs.reduz_mov = h.hasAttribute('data-reduz-mov'); prefs.hora12 = h.hasAttribute('data-hora12');

        const conteudo = raiz.querySelector('.settings-content');
        if (conteudo && !$('set-busca-res')) { const r = document.createElement('div'); r.className = 'set-section'; r.id = 'set-busca-res'; conteudo.appendChild(r); }

        montarNotificacoes(); montarAcessibilidade(); montarIdioma(); montarCobranca(); montarBrasa(); montarPrivacidade(); pintarSons();

        raiz.addEventListener('click', aoClicar);
        raiz.addEventListener('input', aoMexerNoControle);
        raiz.addEventListener('keydown', aoTeclar);

        // trocar de aba: limpa a busca e pede os dados da aba (cobrança, privacidade e Brasa vêm do servidor)
        document.querySelectorAll('.set-tab[data-target]').forEach((tab) => tab.addEventListener('click', () => {
            if ($('set-busca-res').classList.contains('active') || restaurar) limparBusca(false);
            try { tab.scrollIntoView({ inline: 'center', block: 'nearest', behavior: reduzMov() ? 'auto' : 'smooth' }); } catch (e) { /* celular: a pílula escolhida aparece no meio da fileira */ }
            const alvo = tab.dataset.target;
            if (alvo === 'set-cobranca') { ctx.socket.emit('cobranca_historico', {}); }
            else if (alvo === 'set-privacidade') { ctx.socket.emit('dados_privacidade', {}); montarPrivacidade(); }
            else if (alvo === 'set-brasa') { ctx.socket.emit('olimpo_estado', {}); }
            else if (alvo === 'set-voz') pintarSons();
        }));
        // fechar as Configurações também fecha a busca
        new MutationObserver(() => { if (!raiz.classList.contains('active')) limparBusca(false); }).observe(raiz, { attributes: true, attributeFilter: ['class'] });

        const campo = $('set-busca-campo');
        let t = null;
        if (campo) {
            campo.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => buscar(campo.value), 110); });
            campo.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && (campo.value || restaurar)) { e.stopPropagation(); limparBusca(); }
                else if (e.key === 'Enter' && resultados[0]) { e.preventDefault(); abrirResultado(0); }
            });
        }

        const s = ctx.socket;
        s.on('preferencias_carregadas', (p) => {
            if (!p) return;
            if (p.prefs) receber(p.prefs);
            let repintar = false;
            if (typeof p.ghost_mode === 'boolean') { conta.ghost = p.ghost_mode; repintar = true; }
            if (typeof p.localizacao_ativa === 'boolean') { conta.loc = p.localizacao_ativa; repintar = true; }
            if (typeof p.radar_estranhos === 'boolean') { conta.radar = p.radar_estranhos; repintar = true; }
            if (repintar) { marcarInt($('pv-fantasma'), conta.ghost); if ($('set-privacidade').classList.contains('active')) montarPrivacidade(); }
        });
        s.on('cobranca_historico', (d) => { cobranca = d; if (d && d.brasa) brasa = d.brasa; montarCobranca(); });
        s.on('dados_privacidade', (d) => { privacidade = d; montarPrivacidade(); });
        s.on('olimpo_estado', (d) => { if (d && d.estado) { brasa = d.estado; montarBrasa(); if (cobranca) { cobranca.brasa = d.estado; montarCobranca(); } } });
        s.on('amizades', () => { if ($('set-privacidade').classList.contains('active')) montarPrivacidade(); });

        // o som da call respeita o volume escolhido, inclusive nas pessoas que entrarem depois (ligarAudioRemoto lê volumeSaida())
        aplicarVolumeSaida();
        aplicar();
    }

    return { iniciar, avisa, somPermitido, volumeSons, volumeSaida, horaFmt, receber, prefs: () => Object.assign({}, prefs), sub, irPara };
})();
