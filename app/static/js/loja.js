/* ==========================================================================
   ARMAZÉM: a vitrine da loja do app (DRC). Objeto global `Loja`.
   Só DESENHA o que o servidor manda (`loja`, `compra_ok`, `compra_recusada`, `saldo_atualizado`). Preço, posse e saldo são do
   servidor (app/loja.py): o cliente nunca calcula nem confia no que mostra - ele só pede "comprar este item".
   Depende de: Cosm.previaItem (static/js/cosmeticos.js) e das classes .moldura-/.ne-/.placa-/.banner-anim- do app.
   ========================================================================== */
const Loja = (() => {
    const idOk = (v) => /^[a-z_]{1,24}$/.test(String(v || ''));
    const corOk = (v, padrao = '#7289da') => /^#[0-9a-f]{6}$/i.test(String(v || '')) ? v : padrao;
    const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const reduzMov = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    let ctx = null;           // { avatarHtml(), nome(), equipados(), emitir(ev, dados), confirmar(t, msg, ok), toast(msg, tipo), som(), sigla }
    let estado = null;        // último payload 'loja'
    let raiz = null;
    let filtro = 'todos';         // tema ('todos' = qualquer)
    let ftipo = 'todos', frar = 'todos', fanim = 'todos', ordem = 'padrao';   // tipo (grupo), raridade, animação, ordem
    const CHAVE_FILTROS = 'pnt_arm_filtros';
    try { const f = JSON.parse(localStorage.getItem(CHAVE_FILTROS) || '{}'); ftipo = f.tipo || 'todos'; frar = f.rar || 'todos'; fanim = f.anim || 'todos'; ordem = f.ordem || 'padrao'; } catch (e) {}
    const salvarFiltros = () => { try { localStorage.setItem(CHAVE_FILTROS, JSON.stringify({ tipo: ftipo, rar: frar, anim: fanim, ordem })); } catch (e) {} };
    let heroIdx = 0, heroTimer = null;
    let aberto = null;        // id do item no modal
    let comprando = null, comprandoTimer = null;
    let carregadoEm = 0;
    let busca = '';           // texto da busca (filtra as prateleiras; não entra no servidor)
    let extratoAberto = false;
    let confetePara = null;   // item recém-comprado: o confete só sai depois que a vitrine nova redesenhou o modal

    const temaDe = (id) => (estado.temas || []).find((t) => t.id === id);
    // prêmios da coleção não estão à venda (não vêm em `itens`): viram um "item" só pra abrir no mesmo modal
    const premioDe = (id) => {
        const p = ((estado.colecao || {}).premios || []).find((x) => x.item.id === id);
        return p ? { ...p.item, premio: true, meta: p.meta, faltam: p.faltam, possui: p.ganho, preco: 0, preco_final: 0 } : null;
    };
    const itemDe = (id) => (estado.itens || []).find((i) => i.id === id) || premioDe(id);
    // edição limitada que já acabou (prazo ou estoque) e que a pessoa não tem: dá pra ver, não dá pra comprar
    const indisponivel = (i) => !i.possui && !!i.limitado && (i.limitado.encerrado || i.limitado.esgotado);
    const tempoTexto = (s) => {
        s = Math.max(0, Math.floor(s));
        const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
        return d ? `${d}d ${h}h` : h ? `${h}h ${m}min` : `${Math.max(m, 1)} min`;
    };
    const fimDe = (seg) => Date.now() + Number(seg || 0) * 1000;     // instante em que a contagem zera (a tela se atualiza sozinha)
    // edições limitadas e prêmios de coleção não são temas da vitrine, mas têm acento próprio (o modal fica fora do #armazem: sem isto, --c não existe)
    const ACENTOS = { edicao: { cores: ['#ffcc33', '#b8860b'], cor: '#ffcc33' }, colecao: { cores: ['#c0c8d6', '#8f9bb0'], cor: '#c0c8d6' } };
    const ESTILO_PADRAO = '--a:var(--brand-color);--b:var(--brand-color);--c:var(--brand-color)';
    const estiloTema = (t) => t ? `--a:${corOk(t.cores[0])};--b:${corOk(t.cores[1])};--c:${corOk(t.cor)}` : ESTILO_PADRAO;
    const estiloDoItem = (i) => estiloTema(temaDe(i.tema) || ACENTOS[i.tema]);
    const pctx = () => ({ avatarHtml: ctx.avatarHtml(), nome: ctx.nome(), temas: Object.fromEntries((estado.temas || []).map((t) => [t.id, { cor: t.cor }])) });
    const moeda = (n) => `${Number(n || 0).toLocaleString('pt-BR')}`;
    const pctOff = (de, por) => de > 0 ? Math.round((1 - por / de) * 100) : 0;

    // ---------------------------------------------------------------------
    // PRÉVIAS
    // ---------------------------------------------------------------------
    /** O perfil da PESSOA com o tema inteiro aplicado (faixa + moldura + nome + placa). */
    function miniPerfil(tid) {
        if (!idOk(tid)) return '';
        const av = ctx.avatarHtml(), nome = esc(ctx.nome());
        const t = temaDe(tid);
        return `<div class="arm-perfil" style="${estiloTema(t)}">
            <div class="arm-perfil-faixa banner-anim-${tid}"></div>
            <div class="arm-perfil-corpo">
                <span class="pf-tile-av moldura-${tid}">${av}</span>
                <span class="cat-nome ne-${tid}">${nome}</span>
                <span class="pf-placa-linha placa-${tid}"><span class="pf-mini-av">${av}</span><span>${nome}</span></span>
                <small>Assim fica o seu perfil</small>
            </div>
        </div>`;
    }

    function previa(i, grande = false) {
        if (i.tipo === 'pacote') return miniPerfil(i.tema);
        // dentro do cartão (que já é um <button>) não cabe outro botão: o "Ouvir" de verdade fica no modal
        if (i.tipo === 'som_call') return grande
            ? `<button type="button" class="arm-btn sec" data-acao="ouvir" data-som="${esc(i.valor)}"><i class="fa-solid fa-play"></i> Ouvir</button>`
            : '<span class="arm-som"><i class="fa-solid fa-volume-high"></i></span>';
        return Cosm.previaItem(i, pctx());
    }

    // ---------------------------------------------------------------------
    // ARTE DO HERO (CSS/SVG puro; cada tema conta a sua história)
    // ---------------------------------------------------------------------
    function engrenagem(cx, cy, r, n, cor, furo) {
        let d = '';
        for (let k = 0; k < n; k++) {
            const a = (k / n) * Math.PI * 2, w = (Math.PI / n) * 0.55;
            const p = (ang, rad) => `${(cx + Math.cos(ang) * rad).toFixed(1)} ${(cy + Math.sin(ang) * rad).toFixed(1)}`;
            d += `${k ? 'L' : 'M'}${p(a - w, r)} L${p(a - w * 0.7, r * 1.22)} L${p(a + w * 0.7, r * 1.22)} L${p(a + w, r)} `;
        }
        return `<path d="${d}Z" fill="${cor}"/><circle cx="${cx}" cy="${cy}" r="${(r * 0.38).toFixed(1)}" fill="${furo}"/>`;
    }

    const ARTES = {
        dualidade: () => '<div class="arte arte-dual" aria-hidden="true"><i class="o azul"></i><i class="o verm"></i><i class="o roxa"></i><i class="onda"></i><i class="onda b"></i></div>',
        relojoaria: () => {
            let marcas = '';
            for (let h = 0; h < 12; h++) {
                const a = (h / 12) * Math.PI * 2, c = Math.cos(a), s = Math.sin(a), r1 = h % 3 === 0 ? 40 : 46;
                marcas += `<line x1="${(120 + c * r1).toFixed(1)}" y1="${(124 + s * r1).toFixed(1)}" x2="${(120 + c * 52).toFixed(1)}" y2="${(124 + s * 52).toFixed(1)}" stroke="#5a3d12" stroke-width="${h % 3 === 0 ? 3.4 : 2}" stroke-linecap="round"/>`;
            }
            return `<svg class="arte arte-reloj" viewBox="0 0 240 240" aria-hidden="true">
                <g class="engr g1">${engrenagem(46, 168, 30, 10, '#3f5f6b', '#1b2a30')}</g>
                <g class="engr g2">${engrenagem(188, 52, 24, 9, '#b8862f', '#33240f')}</g>
                <rect x="112" y="40" width="16" height="16" rx="3" fill="#b8862f" stroke="#5a3d12" stroke-width="3"/>
                <circle cx="120" cy="34" r="10" fill="none" stroke="#b8862f" stroke-width="5"/>
                <circle cx="120" cy="124" r="70" fill="#d4a24c" stroke="#5a3d12" stroke-width="5"/>
                <circle cx="120" cy="124" r="58" fill="#f5ecd2" stroke="#5a3d12" stroke-width="3"/>
                ${marcas}
                <line class="mao m" x1="120" y1="124" x2="120" y2="84" stroke="#2a1d08" stroke-width="5" stroke-linecap="round"/>
                <line class="mao s" x1="120" y1="136" x2="120" y2="76" stroke="#c0392b" stroke-width="2.4" stroke-linecap="round"/>
                <circle cx="120" cy="124" r="5" fill="#2a1d08"/>
                <g class="tampa"><circle cx="120" cy="124" r="60" fill="#b8862f" stroke="#5a3d12" stroke-width="4"/><circle cx="120" cy="124" r="46" fill="none" stroke="#8a5f1c" stroke-width="3"/><path d="M96 112 Q120 90 144 112" fill="none" stroke="#f6dc92" stroke-width="5" stroke-linecap="round"/></g>
            </svg>`;
        },
        cubos: () => `<svg class="arte arte-cubo" viewBox="0 0 240 240" aria-hidden="true">
            <g class="cubo-flutua">
                <polygon points="120,36 192,76 120,116 48,76" fill="#5fa83a"/><polygon points="48,76 120,116 120,200 48,160" fill="#8b5a2b"/><polygon points="120,116 192,76 192,160 120,200" fill="#6b4220"/>
                <path d="M48 76 L120 116 L120 134 L102 124 L84 136 L66 122 L48 112 Z" fill="#4f8f2e"/><path d="M120 116 L192 76 L192 112 L174 122 L156 134 L138 124 L120 134 Z" fill="#3f7d2a"/>
                <g stroke="rgba(0,0,0,.22)" stroke-width="2" fill="none"><path d="M84 56 L156 96 M156 56 L84 96"/><path d="M84 96 L84 180 M48 118 L120 158"/><path d="M156 96 L156 180 M120 158 L192 118"/></g>
                <polygon points="120,36 192,76 120,116 48,76" fill="none" stroke="#173c0c" stroke-width="3" stroke-linejoin="round"/>
            </g>
            <rect class="px px1" x="28" y="150" width="10" height="10" fill="#8be05a"/><rect class="px px2" x="204" y="120" width="8" height="8" fill="#9b6a36"/><rect class="px px3" x="196" y="40" width="9" height="9" fill="#8be05a"/>
        </svg>`,
        batida: () => {
            let sulcos = '', barras = '';
            for (let r = 40; r <= 90; r += 7) sulcos += `<circle cx="120" cy="108" r="${r}" fill="none" stroke="#2c1942" stroke-width="2"/>`;
            for (let k = 0; k < 7; k++) barras += `<rect class="eq-b" x="${46 + k * 24}" y="206" width="14" height="32" rx="3" fill="${k % 2 ? '#d946ef' : '#22d3ee'}" style="animation-delay:-${(k * 0.23).toFixed(2)}s"/>`;
            return `<svg class="arte arte-vinil" viewBox="0 0 240 240" aria-hidden="true">
                <g class="vinil-gira"><circle cx="120" cy="108" r="96" fill="#1b0f2b"/>${sulcos}<path d="M120 108 L120 12 A96 96 0 0 1 188 40 Z" fill="rgba(255,255,255,.14)"/><path d="M120 108 L120 204 A96 96 0 0 1 52 176 Z" fill="rgba(255,255,255,.1)"/>
                    <circle cx="120" cy="108" r="30" fill="#d946ef"/><circle cx="120" cy="108" r="30" fill="none" stroke="#fff" stroke-width="3"/><circle cx="120" cy="108" r="5" fill="#fff"/></g>
                <g class="eq">${barras}</g></svg>`;
        },
        quadra: () => `<svg class="arte arte-bola" viewBox="0 0 240 240" aria-hidden="true">
            <ellipse class="bola-sombra" cx="120" cy="216" rx="52" ry="9" fill="rgba(0,0,0,.35)"/>
            <g class="bola-pula"><g class="bola-gira"><circle cx="120" cy="120" r="56" fill="#fff" stroke="#1a2b52" stroke-width="5"/>
                <g fill="none" stroke="#e8742c" stroke-width="6" stroke-linecap="round"><path d="M66 112 Q120 78 174 112"/><path d="M120 64 Q86 120 120 176"/><path d="M80 82 Q124 124 160 164"/></g>
                <circle cx="120" cy="120" r="56" fill="none" stroke="#1a2b52" stroke-width="5"/></g></g></svg>`,
        mira: () => `<svg class="arte arte-mira" viewBox="0 0 240 240" aria-hidden="true">
            <circle cx="120" cy="120" r="88" fill="rgba(79,209,197,.06)" stroke="#4fd1c5" stroke-width="4" opacity=".7"/><circle cx="120" cy="120" r="56" fill="none" stroke="#4fd1c5" stroke-width="2" opacity=".45"/>
            <g class="mira-varre"><path d="M120 120 L120 32 A88 88 0 0 1 182 58 Z" fill="rgba(79,209,197,.38)"/></g>
            <g class="mira-trava"><g stroke="#e8483f" stroke-width="5" stroke-linecap="round"><path d="M120 8 L120 54 M120 186 L120 232 M8 120 L54 120 M186 120 L232 120"/></g>
                <circle cx="120" cy="120" r="70" fill="none" stroke="#e8483f" stroke-width="3" stroke-dasharray="26 18"/><circle cx="120" cy="120" r="6" fill="#e8483f"/></g>
            <circle class="mira-alvo" cx="164" cy="82" r="7" fill="#e8483f"/></svg>`,
        cyber: () => {
            let pinos = '';
            for (let k = 0; k < 5; k++) {
                const p = 78 + k * 21;
                pinos += `<rect x="${p - 3}" y="44" width="6" height="16" fill="#22e4ff"/><rect x="${p - 3}" y="180" width="6" height="16" fill="#22e4ff"/><rect x="44" y="${p - 3}" width="16" height="6" fill="#ff2d95"/><rect x="180" y="${p - 3}" width="16" height="6" fill="#ff2d95"/>`;
            }
            return `<svg class="arte arte-cyber" viewBox="0 0 240 240" aria-hidden="true">${pinos}
                <rect x="60" y="60" width="120" height="120" rx="14" fill="#0a0a18" stroke="#22e4ff" stroke-width="5"/>
                <path class="cy-trilha" d="M76 96 H104 V76 M164 96 H136 V76 M76 144 H104 V164 M164 144 H136 V164" fill="none" stroke="#ff2d95" stroke-width="3" stroke-linecap="round"/>
                <rect x="92" y="92" width="56" height="56" rx="8" fill="#12082a" stroke="#ff2d95" stroke-width="4"/>
                <circle class="cy-nucleo" cx="120" cy="120" r="12" fill="#22e4ff"/>
                <line class="cy-varre" x1="60" y1="70" x2="180" y2="70" stroke="#22e4ff" stroke-width="3" opacity=".8"/></svg>`;
        },
        eldoria: () => {
            let runas = '';
            for (let k = 0; k < 12; k++) {
                const a = (k / 12) * Math.PI * 2;
                runas += `<rect x="${(120 + Math.cos(a) * 98 - 3).toFixed(1)}" y="${(120 + Math.sin(a) * 98 - 8).toFixed(1)}" width="6" height="16" rx="2" fill="#d9a520" transform="rotate(${(a * 180 / Math.PI + 90).toFixed(1)} ${(120 + Math.cos(a) * 98).toFixed(1)} ${(120 + Math.sin(a) * 98).toFixed(1)})"/>`;
            }
            return `<svg class="arte arte-eldoria" viewBox="0 0 240 240" aria-hidden="true">
                <g class="el-runas">${runas}<circle cx="120" cy="120" r="98" fill="none" stroke="#d9a520" stroke-width="2" opacity=".6"/></g>
                <g class="el-cristal"><polygon points="120,40 168,100 120,200 72,100" fill="#2f9e6a" stroke="#0f4a30" stroke-width="5" stroke-linejoin="round"/>
                    <polygon points="120,40 168,100 120,100" fill="#8bf0b8" opacity=".75"/><polygon points="120,40 72,100 120,100" fill="#5fd49a" opacity=".8"/><polygon points="120,100 168,100 120,200" fill="#1f7a50" opacity=".9"/>
                    <path d="M120 40 L120 200" stroke="#0f4a30" stroke-width="2" opacity=".5"/></g>
                <circle class="el-fa f1" cx="52" cy="70" r="4" fill="#fff3b8"/><circle class="el-fa f2" cx="196" cy="168" r="3.5" fill="#b9f5c8"/><circle class="el-fa f3" cx="186" cy="62" r="3" fill="#fff3b8"/></svg>`;
        },
        arcade: () => {
            const coracao = ['0110110', '1111111', '1111111', '0111110', '0011100', '0001000'];
            let px = '';
            coracao.forEach((lin, y) => [...lin].forEach((v, x) => { if (v === '1') px += `<rect x="${56 + x * 18}" y="${70 + y * 18}" width="18" height="18" fill="${y < 2 && x < 3 ? '#ff8aa0' : '#ff3b5c'}"/>`; }));
            return `<svg class="arte arte-arcade" viewBox="0 0 240 240" aria-hidden="true" shape-rendering="crispEdges">
                <g class="ar-coracao">${px}</g>
                <g class="ar-moeda"><rect x="168" y="40" width="30" height="36" fill="#ffd23f"/><rect x="162" y="46" width="42" height="24" fill="#ffd23f"/><rect x="176" y="48" width="14" height="20" fill="#e0a800"/></g>
                <rect class="ar-px p1" x="40" y="190" width="8" height="8" fill="#4dd0e1"/><rect class="ar-px p2" x="190" y="196" width="8" height="8" fill="#ff4fa3"/><rect class="ar-px p3" x="108" y="206" width="8" height="8" fill="#ffd23f"/></svg>`;
        },
        gojo: () => {
            // o Vazio Ilimitado: um espaço de estrelas, o anel aceso no centro e seis olhos humanos em volta (as peças vêm do Cosm, as mesmas do domínio do perfil)
            let estrelas = '', luz = '';
            for (let k = 0; k < 16; k++) estrelas += `<circle class="go-est" cx="${(30 + ((k * 53) % 180)).toFixed(0)}" cy="${(30 + ((k * 37) % 180)).toFixed(0)}" r="${(k % 3) + 1}" style="animation-delay:-${(k * 0.37).toFixed(2)}s"/>`;
            for (let k = 0; k < 14; k++) {
                const a = (k * 360) / 14 + 6, c = Math.cos(a * Math.PI / 180), sn = Math.sin(a * Math.PI / 180);
                luz += `<line class="go-est" x1="${(120 + c * 36).toFixed(1)}" y1="${(120 + sn * 36).toFixed(1)}" x2="${(120 + c * (70 + (k % 3) * 12)).toFixed(1)}" y2="${(120 + sn * (70 + (k % 3) * 12)).toFixed(1)}" stroke="#bfe0ff" stroke-width="1.4" stroke-linecap="round" style="animation-delay:-${(k * 0.23).toFixed(2)}s"/>`;
            }
            const olhos = [[80, 60], [160, 60], [46, 120], [194, 120], [80, 180], [160, 180]].map(([x, y], k) =>
                `<g class="go-olho" style="animation-delay:-${(k * 0.45).toFixed(2)}s">${Cosm.svgOlho().replace('<svg ', `<svg x="${x - 21}" y="${y - 12.6}" width="42" height="25.2" `)}</g>`).join('');
            return `<svg class="arte arte-gojo" viewBox="0 0 240 240" aria-hidden="true">
                <circle cx="120" cy="120" r="102" fill="#05061c" stroke="#4aa8ff" stroke-width="3"/><circle cx="120" cy="120" r="100" fill="#2a1c78" opacity=".35"/><g fill="#fff">${estrelas}</g>${luz}
                <circle cx="120" cy="120" r="31" fill="#02030c" fill-opacity=".8"/><circle cx="120" cy="120" r="32.5" fill="none" stroke="#f0b840" stroke-width="1.4"/><circle cx="120" cy="120" r="30" fill="none" stroke="#fff" stroke-width="4"/>
                ${olhos}</svg>`;
        },
        sukuna: () => {
            const lente = (cx, cy, len, ang, th) => {
                const pts = [[-1, 0], [-.8, -.6], [0, -1], [.8, -.6], [1, 0], [.8, .6], [0, 1], [-.8, .6]].map(([x, y]) => {
                    const px = x * len / 2, py = y * th / 2, c = Math.cos(ang * Math.PI / 180), sn = Math.sin(ang * Math.PI / 180);
                    return `${(cx + px * c - py * sn).toFixed(1)},${(cy + px * sn + py * c).toFixed(1)}`;
                });
                return pts.join(' ');
            };
            const cortes = [[96, 100, 170, -24, 8], [138, 132, 160, 18, 8], [112, 150, 140, -52, 7], [140, 90, 130, 60, 7], [120, 120, 200, -8, 9], [100, 70, 150, 34, 6], [150, 168, 140, -36, 6], [90, 176, 130, 12, 6]]
                .map(([cx, cy, len, ang, th], k) => `<polygon class="su-corte" points="${lente(cx, cy, len, ang, th)}" style="animation-delay:${(k * 0.4).toFixed(2)}s"/>`).join('');
            // a lua vermelha com as marcas do rosto (decalcadas da referência) aparecendo e sumindo por baixo dos cortes
            const marcas = Cosm.svgMarcasSukuna('su-marcas').replace('<svg ', '<svg x="62" y="38" width="116" height="141" ');
            return `<svg class="arte arte-sukuna" viewBox="0 0 240 240" aria-hidden="true"><defs><radialGradient id="suLua" cx=".4" cy=".35"><stop offset="0" stop-color="#ff7b6b"/><stop offset=".6" stop-color="#b3122b"/><stop offset="1" stop-color="#4a0a12"/></radialGradient></defs>
                <circle class="su-lua" cx="120" cy="120" r="88" fill="url(#suLua)"/>${marcas}${cortes}</svg>`;
        },
        mahoraga: () => {
            // o timão da Roda Divina (o mesmo desenho do perfil), girando 45° de uma vez e parando duro
            return `<svg class="arte arte-mahoraga" viewBox="0 0 240 240" aria-hidden="true"><circle class="ma-halo" cx="120" cy="120" r="112" fill="none" stroke="#e8bd3a" stroke-width="2" opacity=".5"/>
                <svg x="20" y="20" width="200" height="200" viewBox="0 0 200 200"><g class="ma-giro">${Cosm.svgTimao()}</g></svg></svg>`;
        },
        manga: () => {
            let pts = '';
            for (let k = 0; k < 28; k++) { const a = (k / 28) * Math.PI * 2, r = k % 2 ? 80 : 108; pts += `${(120 + Math.cos(a) * r).toFixed(1)},${(120 + Math.sin(a) * r).toFixed(1)} `; }
            return `<svg class="arte arte-manga" viewBox="0 0 240 240" aria-hidden="true"><g class="manga-gira"><polygon points="${pts}" fill="#e63946" stroke="#111" stroke-width="5" stroke-linejoin="round"/></g>
                <circle cx="120" cy="120" r="58" fill="#f1faee" stroke="#111" stroke-width="5"/>
                <g fill="#111" opacity=".18"><circle cx="100" cy="150" r="3"/><circle cx="112" cy="156" r="3"/><circle cx="124" cy="150" r="3"/><circle cx="136" cy="156" r="3"/><circle cx="148" cy="150" r="3"/><circle cx="106" cy="164" r="3"/><circle cx="130" cy="164" r="3"/></g>
                <text x="120" y="146" text-anchor="middle" font-size="86" font-weight="900" fill="#111" font-family="Impact, 'Arial Black', sans-serif">!</text></svg>`;
        },
    };

    // ---------------------------------------------------------------------
    // PEÇAS DE TELA
    // ---------------------------------------------------------------------
    function htmlPreco(i) {
        if (i.possui) return '<span class="arm-seu"><i class="fa-solid fa-circle-check"></i> Seu</span>';
        if (indisponivel(i)) return `<span class="arm-fora"><i class="fa-solid fa-ban"></i> ${i.limitado.esgotado ? 'Esgotado' : 'Encerrada'}</span>`;
        const curto = i.preco_final > estado.saldo;
        let extra = '';
        if (i.tipo === 'pacote') {
            const t = temaDe(i.tema);
            if (t && t.preco_soma > i.preco_final) extra = `<s>${moeda(t.preco_soma)}</s>`;
        } else if (i.reliquia && i.preco > i.preco_final) {
            extra = `<s>${moeda(i.preco)}</s>`;
        }
        const off = i.tipo === 'pacote' && temaDe(i.tema) ? pctOff(temaDe(i.tema).preco_soma, i.preco_final) : (i.reliquia ? pctOff(i.preco, i.preco_final) : 0);
        return `<span class="arm-preco ${curto ? 'curto' : ''}">${extra}<i class="fa-solid fa-coins"></i> ${moeda(i.preco_final)}</span>${off > 0 ? `<span class="arm-off">-${off}%</span>` : ''}`;
    }

    /** Linha de aviso das edições limitadas: quantas unidades restam e/ou quanto tempo falta. */
    function htmlLimite(i) {
        const l = i.limitado;
        if (!l || i.possui) return '';
        if (l.esgotado) return '<small class="arm-lim fim">Todas as unidades já foram vendidas</small>';
        if (l.encerrado) return '<small class="arm-lim fim">A venda desta edição terminou</small>';
        const partes = [];
        if (l.restam !== null && l.restam !== undefined) partes.push(`<b class="${l.restam <= 10 ? 'ultimas' : ''}">Restam ${moeda(l.restam)} de ${moeda(l.estoque)}</b>`);
        if (l.termina_em !== null && l.termina_em !== undefined) partes.push(`encerra em <span class="arm-tempo" data-fim="${fimDe(l.termina_em)}">${tempoTexto(l.termina_em)}</span>`);
        return `<small class="arm-lim">${partes.join(' · ')}</small>`;
    }

    function htmlRar(i) {
        const r = raridadeDe(i.raridade);
        return r ? `<span class="arm-rar" style="--rar:${corOk(r.cor, '#9aa3b2')}" title="${esc(r.nome)}${i.animado ? '' : ' · sem animação'}">${esc(r.nome)}</span>` : '';
    }

    function htmlCard(i) {
        const t = temaDe(i.tema);
        const pacote = i.tipo === 'pacote';
        const selo = pacote ? '<span class="arm-faixa-pack">Pacote</span>'
            : i.reliquia ? `<span class="arm-faixa-pack reliquia"><i class="fa-solid fa-gem"></i> Relíquia -${pctOff(i.preco, i.preco_final)}%</span>`
            : i.limitado ? '<span class="arm-faixa-pack limitada"><i class="fa-solid fa-hourglass-half"></i> Limitada</span>' : '';
        return `<button type="button" class="arm-card ${pacote ? 'pacote' : ''} ${indisponivel(i) ? 'fora' : ''} ${i.limitado ? 'limitado' : ''}" data-item="${esc(i.id)}" style="${estiloDoItem(i)}" aria-label="${esc(i.nome)}">
            ${selo}
            <div class="arm-card-prev">${previa(i)}</div>
            <div class="arm-card-info">
                <div class="arm-meta"><span class="arm-tag">${esc(i.rotulo)}${t ? ' · ' + esc(t.nome) : ''}</span>${htmlRar(i)}</div>
                <h4>${esc(i.nome)}</h4>
                ${htmlLimite(i)}
                <div class="arm-card-rodape">${htmlPreco(i)}</div>
            </div>
        </button>`;
    }

    function htmlPrateleira(titulo, itens) {
        if (!itens.length) return '';
        return `<section class="arm-prat">
            <div class="arm-prat-topo"><h3>${esc(titulo)}</h3><span class="n">${itens.length}</span>
                <div class="setas"><button type="button" class="arm-seta" data-acao="rolar" data-dir="-1" aria-label="Voltar"><i class="fa-solid fa-chevron-left"></i></button><button type="button" class="arm-seta" data-acao="rolar" data-dir="1" aria-label="Avançar"><i class="fa-solid fa-chevron-right"></i></button></div>
            </div>
            <div class="arm-trilho">${itens.map(htmlCard).join('')}</div>
        </section>`;
    }

    function htmlHero() {
        const slides = (estado.destaques || []).map((d) => ({ d, t: temaDe(d.tema) })).filter((x) => x.t && ARTES[x.t.id]);
        if (!slides.length) return '';
        const html = slides.map(({ d, t }, k) => {
            const pk = t.pacote ? itemDe(t.pacote) : null;
            const preco = pk && !pk.possui
                ? `<span class="arm-hero-preco">Pacote completo <s>${moeda(t.preco_soma)}</s> <b><i class="fa-solid fa-coins"></i> ${moeda(pk.preco_final)}</b></span>`
                : (pk ? '<span class="arm-hero-preco"><i class="fa-solid fa-circle-check"></i> Você já tem o pacote</span>' : '');
            return `<div class="arm-slide" data-slide="${k}" style="${estiloTema(t)}">
                <div class="arm-slide-txt">
                    <span class="arm-selo">${esc(d.selo || 'Novo')}</span>
                    <h2>${esc(d.titulo)}</h2>
                    <p>${esc(d.sub)}</p>
                    <div class="arm-slide-acoes">
                        <button type="button" class="arm-btn" data-acao="ver-tema" data-tema="${esc(t.id)}">Ver coleção <i class="fa-solid fa-arrow-right"></i></button>
                        ${preco}
                    </div>
                </div>
                <div class="arm-slide-arte">${ARTES[t.id]()}${miniPerfil(t.id)}</div>
            </div>`;
        }).join('');
        const pontos = slides.map((_, k) => `<button type="button" class="arm-ponto ${k === heroIdx ? 'on' : ''}" data-acao="slide" data-i="${k}" aria-label="Destaque ${k + 1}"></button>`).join('');
        return `<section class="arm-hero" style="${estiloTema(slides[Math.min(heroIdx, slides.length - 1)].t)}">
            <div class="arm-trilho-hero">${html}</div>
            ${slides.length > 1 ? `<button type="button" class="arm-seta-hero ant" data-acao="hero-seta" data-dir="-1" aria-label="Anterior"><i class="fa-solid fa-chevron-left"></i></button><button type="button" class="arm-seta-hero prox" data-acao="hero-seta" data-dir="1" aria-label="Próximo"><i class="fa-solid fa-chevron-right"></i></button>` : ''}
            <div class="arm-hero-setas">${slides.length > 1 ? pontos : ''}</div>
        </section>`;
    }

    const ORDENS = [['padrao', 'Padrão'], ['menor', 'Menor preço'], ['maior', 'Maior preço'], ['raridade', 'Mais raros']];
    const ANIMS = [['todos', 'Todos'], ['sim', 'Animados'], ['nao', 'Sem animação']];
    const raridadeDe = (id) => (estado.raridades || []).find((r) => r.id === id);
    const filtrando = () => filtro !== 'todos' || ftipo !== 'todos' || frar !== 'todos' || fanim !== 'todos' || ordem !== 'padrao' || !!norm(busca).trim();

    function htmlChips() {
        const contagem = (g) => estado.itens.filter((i) => i.grupo === g).length;
        const chip = (id, nome) => `<button type="button" class="arm-chip ${ftipo === id ? 'on' : ''}" data-acao="tipo" data-tipo="${esc(id)}">${esc(nome)}${id === 'todos' ? '' : `<em>${contagem(id)}</em>`}</button>`;
        const sel = (rotulo, chave, opcoes, atual) => `<label class="arm-sel"><span>${rotulo}</span><select data-filtro="${chave}">${opcoes.map(([v, n]) => `<option value="${esc(v)}" ${v === atual ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select></label>`;
        const temas = [['todos', 'Todos os temas']].concat((estado.temas || []).map((t) => [t.id, t.nome + (t.premium ? ' ★' : '')]));
        const raridades = [['todos', 'Todas']].concat((estado.raridades || []).map((r) => [r.id, r.nome]));
        return `<div class="arm-barra">
            <div class="arm-tipos">${chip('todos', 'Tudo')}${(estado.grupos || []).map((g) => chip(g.id, g.titulo)).join('')}</div>
            <div class="arm-filtros">
                ${sel('Tema', 'tema', temas, filtro)}${sel('Raridade', 'rar', raridades, frar)}${sel('Animação', 'anim', ANIMS, fanim)}${sel('Ordenar', 'ordem', ORDENS, ordem)}
                <label class="arm-busca"><i class="fa-solid fa-magnifying-glass"></i><input type="text" id="arm-busca" maxlength="40" placeholder="Buscar item ou tema..." value="${esc(busca)}"></label>
                <button type="button" class="arm-limpar" data-acao="limpar" ${filtrando() ? '' : 'hidden'}><i class="fa-solid fa-xmark"></i> Limpar filtros</button>
                <button type="button" class="arm-extrato" data-acao="extrato" title="Tudo que você ganhou e gastou. ${esc(ctx.sigla)} só se ganha subindo de nível e cumprindo missões."><i class="fa-solid fa-receipt"></i> Extrato de ${esc(ctx.sigla)}</button>
            </div>
        </div>`;
    }

    // ---------------------------------------------------------------------
    // BUSCA (só filtra o que já veio do servidor; letra maiúscula e acento não importam)
    // ---------------------------------------------------------------------
    const norm = (v) => String(v || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    function bate(i, q) {
        const t = temaDe(i.tema);
        return [i.nome, i.desc, i.rotulo, t && t.nome].some((x) => norm(x).includes(q));
    }

    // ---------------------------------------------------------------------
    // FAIXAS ESPECIAIS DA VITRINE: relíquia da semana, edições limitadas e coleção
    // ---------------------------------------------------------------------
    function htmlReliquia() {
        const r = estado.reliquia, i = r && itemDe(r.item_id);
        if (!i) return '';
        const t = temaDe(i.tema);
        const acao = i.possui
            ? '<span class="arm-seu"><i class="fa-solid fa-circle-check"></i> Você já tem esta relíquia</span>'
            : `<button type="button" class="arm-btn" data-acao="abrir" data-item="${esc(i.id)}">Ver relíquia <i class="fa-solid fa-arrow-right"></i></button>
               <span class="arm-hero-preco"><s>${moeda(i.preco)}</s> <b><i class="fa-solid fa-coins"></i> ${moeda(i.preco_final)}</b></span>`;
        return `<section class="arm-reliquia" style="${estiloTema(t)}">
            <div class="arm-rel-txt">
                <span class="arm-selo"><i class="fa-solid fa-gem"></i> Relíquia da semana</span>
                <h3>${esc(i.nome)}</h3>
                <p>${esc(i.desc)}</p>
                <div class="arm-rel-info"><span class="arm-off">-${Number(r.desconto)}%</span><span>Só até segunda-feira · troca em <b class="arm-tempo" data-fim="${fimDe(r.termina_em)}">${tempoTexto(r.termina_em)}</b></span></div>
                <div class="arm-slide-acoes">${acao}</div>
            </div>
            <div class="arm-rel-prev" data-acao="abrir" data-item="${esc(i.id)}">${previa(i)}</div>
        </section>`;
    }

    function htmlColecao() {
        const c = estado.colecao;
        if (!c || !(c.premios || []).length) return '';
        const ultima = c.premios[c.premios.length - 1].meta;
        const pct = Math.min(100, Math.round((c.comprados / ultima) * 100));
        const prox = c.premios.find((p) => !p.ganho);
        const premio = (p) => `<button type="button" class="arm-premio ${p.ganho ? 'ganho' : ''}" data-acao="abrir" data-item="${esc(p.item.id)}">
            <span class="arm-premio-prev">${previa(p.item)}</span>
            <span class="arm-premio-txt"><b>${esc(p.item.nome)}</b><small>${p.ganho ? '<i class="fa-solid fa-circle-check"></i> Conquistado' : `<i class="fa-solid fa-lock"></i> Faltam ${moeda(p.faltam)} ${p.faltam === 1 ? 'item' : 'itens'}`}</small></span>
        </button>`;
        return `<section class="arm-colecao">
            <div class="arm-col-topo"><div><h3>Coleção do Armazém</h3><p>${prox
                ? `Cada item que você compra aqui conta. Faltam <b>${moeda(prox.faltam)}</b> pra ganhar <b>${esc(prox.item.nome)}</b>.`
                : 'Você completou a coleção inteira. Que estante!'}</p></div>
                <div class="arm-col-num"><b>${moeda(c.comprados)}</b><small>itens comprados</small></div></div>
            <div class="arm-col-barra" role="progressbar" aria-valuemin="0" aria-valuemax="${ultima}" aria-valuenow="${Math.min(c.comprados, ultima)}"><i style="width:${pct}%"></i>${c.premios.map((p) => `<span class="marco ${p.ganho ? 'ganho' : ''}" style="left:${Math.round((p.meta / ultima) * 100)}%"><em>${p.meta}</em></span>`).join('')}</div>
            <div class="arm-col-premios">${c.premios.map(premio).join('')}</div>
        </section>`;
    }

    const pesoRar = (i) => (estado.raridades || []).findIndex((r) => r.id === i.raridade);
    function corpoHtml() {
        const t = filtro === 'todos' ? null : temaDe(filtro);
        const q = norm(busca).trim();
        if (filtrando()) {
            let achados = estado.itens.filter((i) => (!t || i.tema === t.id) && (ftipo === 'todos' || i.grupo === ftipo) && (frar === 'todos' || i.raridade === frar)
                && (fanim === 'todos' || (fanim === 'sim') === !!i.animado) && (!q || bate(i, q)));
            if (ordem === 'menor') achados.sort((a, b) => a.preco_final - b.preco_final);
            else if (ordem === 'maior') achados.sort((a, b) => b.preco_final - a.preco_final);
            else if (ordem === 'raridade') achados.sort((a, b) => pesoRar(b) - pesoRar(a) || b.preco_final - a.preco_final);
            const pk = t && t.pacote ? itemDe(t.pacote) : null;
            const topo = t ? `<section class="arm-tema-topo"><div><h3>${esc(t.nome)}</h3><p>${esc(t.desc)}</p></div>${pk ? `<div class="arm-tema-pack">${htmlCard(pk)}</div>` : ''}</section>` : '';
            const aviso = ftipo === 'pacote' && !achados.length ? 'Nenhum pacote com esses filtros.' : 'Nada com esses filtros. Tente outra raridade ou limpe os filtros.';
            return topo + `<section class="arm-prat"><div class="arm-prat-topo"><h3>${t ? 'Itens' : 'Resultados'}</h3><span class="n">${achados.length}</span></div>${achados.length
                ? `<div class="arm-grade">${achados.map(htmlCard).join('')}</div>` : `<div class="arm-vazio">${aviso}</div>`}</section>`;
        }
        let corpo = htmlReliquia() + htmlColecao();
        corpo += htmlPrateleira('Edição limitada', estado.itens.filter((i) => i.limitado));
        for (const g of (estado.grupos || [])) corpo += htmlPrateleira(g.id === 'pacote' ? 'Pacotes' : g.titulo, estado.itens.filter((i) => i.grupo === g.id && !i.limitado));
        return corpo || '<div class="arm-vazio">Nada por aqui ainda. Volte em breve!</div>';
    }

    function render() {
        if (!raiz || !estado) return;
        const rolagem = raiz.closest('.market-content');
        const topo = rolagem ? rolagem.scrollTop : 0;
        const t = filtro === 'todos' ? null : temaDe(filtro);
        if (filtro !== 'todos' && !t) filtro = 'todos';
        raiz.setAttribute('style', t ? estiloTema(t) : '');
        raiz.innerHTML = (filtrando() ? '' : htmlHero()) + htmlChips() + `<div id="arm-corpo">${corpoHtml()}</div>`;
        if (rolagem) rolagem.scrollTop = topo;
        const tr = raiz.querySelector('.arm-trilho-hero');
        if (tr) { tr.style.scrollBehavior = 'auto'; tr.scrollLeft = heroIdx * tr.clientWidth; tr.style.scrollBehavior = ''; }
        ligarHero();
    }

    let buscaTimer = 0;
    function aoBuscar(valor) {
        const tinhaHero = !busca;
        busca = valor;
        if (!tinhaHero && !busca && !filtrando()) { render(); return; }
        clearTimeout(buscaTimer);
        buscaTimer = setTimeout(() => {
            if (!raiz || !estado) return;
            if (tinhaHero !== !busca) {            // entrou/saiu do modo busca: o hero some/volta, então redesenha tudo e devolve o foco
                render();
                const i = raiz.querySelector('#arm-busca');
                if (i) { i.focus(); i.setSelectionRange(busca.length, busca.length); }
            } else {
                const c = raiz.querySelector('#arm-corpo');
                if (c) c.innerHTML = corpoHtml();
            }
        }, 180);
    }

    // ---------------------------------------------------------------------
    // EXTRATO DE DRC (o livro-razão visto pela própria pessoa)
    // ---------------------------------------------------------------------
    function desenharExtrato(d) {
        let m = document.getElementById('arm-modal-extrato');
        if (!m) {
            m = document.createElement('div');
            m.id = 'arm-modal-extrato'; m.className = 'arm-modal';
            m.addEventListener('click', (e) => { if (e.target === m || e.target.closest('[data-acao="fechar-extrato"]')) { m.remove(); extratoAberto = false; } });
            document.body.appendChild(m);
            document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && extratoAberto) { e.stopImmediatePropagation(); document.getElementById('arm-modal-extrato')?.remove(); extratoAberto = false; } }, true);
        }
        extratoAberto = true;
        const linha = (x) => `<div class="arm-ext-linha"><span class="arm-ext-ico ${x.delta >= 0 ? 'ganho' : 'gasto'}"><i class="fa-solid ${x.motivo === 'compra' ? 'fa-bag-shopping' : 'fa-arrow-up-right-dots'}"></i></span>
            <span class="arm-ext-txt"><b>${esc(x.titulo)}</b><small>${esc(x.rotulo)} · ${esc(x.hora)}</small></span>
            <span class="arm-ext-val ${x.delta >= 0 ? 'ganho' : 'gasto'}">${x.delta >= 0 ? '+' : '−'}${moeda(Math.abs(x.delta))}<small>saldo ${moeda(x.saldo_apos)}</small></span></div>`;
        m.innerHTML = `<div class="arm-modal-card arm-ext-card" style="--a:var(--brand-color);--b:var(--brand-color);--c:var(--brand-color)">
            <button type="button" class="arm-fechar" data-acao="fechar-extrato" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button>
            <div class="arm-ext-corpo"><h3>Extrato de ${esc(ctx.sigla)}</h3>
                <div class="arm-ext-resumo"><div><small>Saldo</small><b><i class="fa-solid fa-coins"></i> ${moeda(d.saldo)}</b></div><div><small>Já ganhou</small><b class="ganho">+${moeda(d.ganho_total)}</b></div><div><small>Já gastou</small><b class="gasto">−${moeda(d.gasto_total)}</b></div></div>
                <div class="arm-ext-lista">${d.itens.map(linha).join('') || '<div class="arm-vazio">Nenhum movimento ainda. Suba de nível e compre algo no Armazém!</div>'}</div>
                <p class="arm-ext-nota">Mostra os últimos ${d.itens.length} movimentos. O ${esc(ctx.sigla)} só se ganha no Panteão (subindo de nível); não dá pra comprar, transferir nem sacar.</p></div></div>`;
    }

    // ---------------------------------------------------------------------
    // HERO: autoplay (pausa com mouse/aba escondida/modal aberto), arrastar de lado (scroll-snap nativo), parallax pelo ponteiro
    // ---------------------------------------------------------------------
    function irPara(i, suave = true) {
        const tr = raiz && raiz.querySelector('.arm-trilho-hero');
        if (!tr) return;
        const n = tr.children.length;
        heroIdx = (i + n) % n;
        if (!suave) tr.style.scrollBehavior = 'auto';
        tr.scrollLeft = heroIdx * tr.clientWidth;
        if (!suave) tr.style.scrollBehavior = '';
        marcarPontos();
    }

    function marcarPontos() {
        if (!raiz) return;
        raiz.querySelectorAll('.arm-ponto').forEach((p, k) => p.classList.toggle('on', k === heroIdx));
        const hero = raiz.querySelector('.arm-hero'), slide = raiz.querySelectorAll('.arm-slide')[heroIdx];
        if (hero && slide) hero.setAttribute('style', slide.getAttribute('style') || '');
    }

    function ligarHero() {
        clearInterval(heroTimer);
        const hero = raiz.querySelector('.arm-hero');
        if (!hero) return;
        const tr = hero.querySelector('.arm-trilho-hero');
        // Peso: o carrossel tem um mini perfil animado em CADA slide. Só anima o slide que está à vista, e nada quando o hero saiu da tela.
        if ('IntersectionObserver' in window) {
            new IntersectionObserver((es) => es.forEach((en) => en.target.classList.toggle('parado', !en.isIntersecting)), { threshold: 0.02 }).observe(hero);
            const ioSlides = new IntersectionObserver((es) => es.forEach((en) => en.target.classList.toggle('parado', en.intersectionRatio < 0.5)), { root: tr, threshold: [0, 0.5, 1] });
            tr.querySelectorAll('.arm-slide').forEach((sl) => ioSlides.observe(sl));
        }
        let pausado = false, rolando = 0;
        tr.addEventListener('scroll', () => {            // arrastar com o dedo/trackpad também troca o ponto
            clearTimeout(rolando);
            rolando = setTimeout(() => { const i = Math.round(tr.scrollLeft / Math.max(tr.clientWidth, 1)); if (i !== heroIdx) { heroIdx = i; marcarPontos(); } }, 90);
        }, { passive: true });
        hero.addEventListener('pointerenter', () => { pausado = true; });
        hero.addEventListener('pointerleave', () => { pausado = false; hero.querySelectorAll('.arm-slide-arte').forEach((a) => { a.style.setProperty('--px', 0); a.style.setProperty('--py', 0); }); });
        let quadro = 0;
        hero.addEventListener('pointermove', (e) => {    // parallax: só transform, e no máximo 1x por quadro
            if (reduzMov() || e.pointerType === 'touch' || quadro) return;
            quadro = requestAnimationFrame(() => {
                quadro = 0;
                const r = hero.getBoundingClientRect();
                const arte = hero.querySelectorAll('.arm-slide-arte')[heroIdx];
                if (!arte) return;
                arte.style.setProperty('--px', (((e.clientX - r.left) / r.width) * 2 - 1).toFixed(3));
                arte.style.setProperty('--py', (((e.clientY - r.top) / r.height) * 2 - 1).toFixed(3));
            });
        });
        if (tr.children.length > 1 && !reduzMov()) {
            heroTimer = setInterval(() => {
                if (pausado || aberto || document.hidden || !raiz.isConnected || raiz.offsetParent === null) return;
                irPara(heroIdx + 1);
            }, 7000);
        }
    }

    // ---------------------------------------------------------------------
    // MODAL DO ITEM / PACOTE
    // ---------------------------------------------------------------------
    function estaEquipado(i) {
        const eq = ctx.equipados() || {};
        if (i.tipo === 'pacote') {
            const t = temaDe(i.tema);
            return !!t && t.itens.length > 0 && t.itens.every((id) => { const f = itemDe(id); return f && eq[f.tipo] === f.valor; });
        }
        return eq[i.tipo] === i.valor;
    }

    function htmlCompra(i) {
        if (i.premio && !i.possui) {
            return `<div class="arm-saldo-linha"><i class="fa-solid fa-lock"></i> Prêmio da coleção: não se compra. Faltam <b>${moeda(i.faltam)} ${i.faltam === 1 ? 'item' : 'itens'}</b> comprados no Armazém (meta: ${moeda(i.meta)}).</div>`;
        }
        if (i.possui && i.tipo === 'efeito_servidor') {      // não é um slot da pessoa: o dono aplica a um servidor dele, no Inventário
            return `<div class="arm-sucesso"><i class="fa-solid fa-circle-check"></i> Este item é seu</div><button type="button" class="arm-btn" data-acao="inventario"><i class="fa-solid fa-server"></i> Aplicar a um servidor</button>`;
        }
        if (i.possui) {
            const eq = estaEquipado(i);
            const rotulo = i.tipo === 'pacote' ? 'tudo' : '';
            return eq
                ? `<div class="arm-sucesso"><i class="fa-solid fa-circle-check"></i> Equipado no seu perfil</div><button type="button" class="arm-btn sec" data-acao="remover" data-item="${esc(i.id)}">Tirar do perfil</button>`
                : `<div class="arm-sucesso"><i class="fa-solid fa-circle-check"></i> Este item é seu</div><button type="button" class="arm-btn" data-acao="equipar" data-item="${esc(i.id)}"><i class="fa-solid fa-wand-magic-sparkles"></i> Equipar ${rotulo}</button>`;
        }
        if (indisponivel(i)) {
            return `<div class="arm-fora-grande"><i class="fa-solid fa-ban"></i> ${i.limitado.esgotado ? 'Esgotado: todas as unidades foram vendidas.' : 'Encerrada: o prazo desta edição acabou.'} Quem comprou fica com o item pra sempre.</div>
                <button type="button" class="arm-btn" disabled>${i.limitado.esgotado ? 'Esgotado' : 'Encerrada'}</button>`;
        }
        const curto = i.preco_final > estado.saldo;
        const t = temaDe(i.tema);
        let precos = `<span class="v"><i class="fa-solid fa-coins"></i> ${moeda(i.preco_final)}</span>`;
        if (i.reliquia && i.preco > i.preco_final) {
            precos += `<s>${moeda(i.preco)}</s><span class="arm-off">-${pctOff(i.preco, i.preco_final)}%</span><span class="arm-saldo-linha">Relíquia da semana: o desconto acaba na segunda-feira.</span>`;
        }
        if (i.limitado) precos += htmlLimite(i);
        if (i.tipo === 'pacote' && t) {
            const off = pctOff(t.preco_soma, i.preco_final);
            if (off > 0) precos += `<s>${moeda(t.preco_soma)}</s><span class="arm-off">-${off}%</span>`;
            const tem = t.itens.filter((id) => (itemDe(id) || {}).possui).length;
            if (tem) precos += `<span class="arm-saldo-linha">Você já tem ${tem} item(ns): abatemos do preço.</span>`;
        }
        const botao = comprando === i.id
            ? '<button type="button" class="arm-btn" disabled><i class="fa-solid fa-spinner fa-spin"></i> Comprando...</button>'
            : curto
                ? `<button type="button" class="arm-btn curto" data-acao="comprar" data-item="${esc(i.id)}">Faltam ${moeda(i.preco_final - estado.saldo)} ${esc(ctx.sigla)}</button>`
                : `<button type="button" class="arm-btn" data-acao="comprar" data-item="${esc(i.id)}"><i class="fa-solid fa-bag-shopping"></i> Comprar por ${moeda(i.preco_final)} ${esc(ctx.sigla)}</button>`;
        return `<div class="arm-preco-grande">${precos}</div>
            <div class="arm-saldo-linha ${curto ? 'curto' : ''}">Seu saldo: <b>${moeda(estado.saldo)} ${esc(ctx.sigla)}</b>${curto ? ' · suba de nível e cumpra missões pra ganhar mais' : ''}</div>${botao}`;
    }

    function htmlModal(i) {
        const t = temaDe(i.tema);
        const pacote = i.tipo === 'pacote';
        let meio = '';
        if (pacote && t) {
            meio = `<div class="arm-conteudo">${t.itens.map((id) => { const f = itemDe(id); return f ? `<button type="button" class="${f.possui ? 'tem' : ''}" data-acao="abrir" data-item="${esc(f.id)}"><span class="mini">${previa(f)}</span>${esc(f.nome)}${f.possui ? '<small><i class="fa-solid fa-check"></i> você já tem</small>' : ''}</button>` : ''; }).join('')}</div>`;
        } else if (t && t.pacote) {
            const pk = itemDe(t.pacote);
            if (pk) meio = `<button type="button" class="arm-parte" data-acao="abrir" data-item="${esc(pk.id)}"><i class="fa-solid fa-box-open" style="color:var(--c)"></i><span>Faz parte do <b>${esc(pk.nome)}</b>${pk.possui ? ' (você já tem)' : ` por ${moeda(pk.preco_final)} ${esc(ctx.sigla)}`}</span></button>`;
        }
        return `<div class="arm-modal-card" style="${estiloDoItem(i)}" role="dialog" aria-modal="true" aria-label="${esc(i.nome)}">
            <button type="button" class="arm-fechar" data-acao="fechar" aria-label="Fechar"><i class="fa-solid fa-xmark"></i></button>
            <div class="arm-modal-palco"><div class="arm-palco-prev">${previa(i, true)}</div><span class="arm-palco-dica">${pacote ? 'Pacote completo' : i.tipo === 'som_call' ? 'Toque pra ouvir' : 'Prévia no seu perfil'}</span></div>
            <div class="arm-modal-lado">
                <div class="arm-meta"><span class="arm-tag" style="color:var(--c)">${esc(i.rotulo)}${t ? ' · ' + esc(t.nome) : ''}</span>${htmlRar(i)}${i.animado ? '' : '<span class="arm-rar" style="--rar:#9aa3b2">Sem animação</span>'}</div>
                <h3>${esc(i.nome)}</h3>
                <p class="desc">${esc(i.desc)}</p>
                ${meio}
                <div class="arm-compra" id="arm-compra">${htmlCompra(i)}</div>
            </div>
        </div>`;
    }

    function abrirItem(id, redesenho = false) {
        const i = estado && itemDe(id);
        if (!i) return;
        aberto = id;
        let m = document.getElementById('arm-modal');
        if (!m) { m = document.createElement('div'); m.id = 'arm-modal'; m.className = 'arm-modal'; document.body.appendChild(m); ligarModal(m); }
        m.classList.toggle('sem-anim', redesenho);      // redesenho por mudança de estado não repete a animação de entrada
        m.innerHTML = htmlModal(i);
        if (!document.__armEsc) {
            document.__armEsc = (e) => { if (e.key === 'Escape' && aberto) { e.stopImmediatePropagation(); e.preventDefault(); fecharModal(); } };
            document.addEventListener('keydown', document.__armEsc, true);
        }
    }

    function fecharModal() {
        aberto = null;
        const m = document.getElementById('arm-modal');
        if (m) m.remove();
    }

    function ligarModal(m) {
        m.addEventListener('click', (e) => {
            if (e.target === m) { fecharModal(); return; }
            const b = e.target.closest('[data-acao]');
            if (!b) return;
            const id = b.dataset.item;
            switch (b.dataset.acao) {
                case 'fechar': fecharModal(); break;
                case 'abrir': abrirItem(id); break;
                case 'comprar': comprar(id); break;
                case 'ouvir': if (ctx.ouvir) ctx.ouvir(b.dataset.som); break;
                case 'inventario': fecharModal(); if (ctx.abrirInventario) ctx.abrirInventario('efeito'); break;
                case 'equipar': ctx.emitir('equipar_item', { item_id: id }); break;
                case 'remover': {
                    const i = itemDe(id);
                    if (!i) break;
                    if (i.tipo === 'pacote') (temaDe(i.tema).itens || []).forEach((f) => { const x = itemDe(f); if (x) ctx.emitir('desequipar_item', { tipo: x.tipo }); });
                    else ctx.emitir('desequipar_item', { tipo: i.tipo });
                    break;
                }
            }
        });
    }

    function atualizarCompra() {
        const i = aberto && estado && itemDe(aberto);
        const m = document.getElementById('arm-modal');
        if (!i || !m) return;
        const alvo = m.querySelector('#arm-compra');
        if (alvo) alvo.innerHTML = htmlCompra(i);
    }

    // ---------------------------------------------------------------------
    // COMPRA
    // ---------------------------------------------------------------------
    function comprar(id) {
        const i = itemDe(id);
        if (!i || i.possui || comprando) return;
        if (i.preco_final > estado.saldo) {
            ctx.toast(`Faltam ${moeda(i.preco_final - estado.saldo)} ${ctx.sigla}. Suba de nível e cumpra missões pra ganhar mais.`, 'info');
            return;
        }
        ctx.confirmar('Confirmar compra', `Comprar "${i.nome}" por ${moeda(i.preco_final)} ${ctx.sigla}?`, () => {
            comprando = id;
            atualizarCompra();
            clearTimeout(comprandoTimer);
            comprandoTimer = setTimeout(() => { if (comprando === id) { comprando = null; atualizarCompra(); ctx.toast('A compra demorou demais. Confira seu inventário antes de tentar de novo.', 'warning'); } }, 9000);
            ctx.emitir('comprar_item', { item_id: id, preco_esperado: i.preco_final });
        });
    }

    function confete(card, cores) {
        if (reduzMov() || !card) return;
        for (let k = 0; k < 44; k++) {
            const c = document.createElement('span');
            c.className = 'bp-confete';
            const ang = Math.random() * Math.PI * 2, dist = 120 + Math.random() * 280;
            c.style.setProperty('--dx', `${Math.cos(ang) * dist}px`);
            c.style.setProperty('--dy', `${Math.sin(ang) * dist + 100}px`);
            c.style.setProperty('--rot', `${Math.random() * 900 - 450}deg`);
            c.style.setProperty('--dur', `${1.2 + Math.random() * 0.9}s`);
            c.style.setProperty('--atraso', `${Math.random() * 0.2}s`);
            c.style.background = cores[k % cores.length];
            card.appendChild(c);
            setTimeout(() => c.remove(), 2600);
        }
    }

    // ---------------------------------------------------------------------
    // API PÚBLICA (chamada pelo chat.html)
    // ---------------------------------------------------------------------
    function iniciar(opcoes) {
        ctx = opcoes;
        raiz = document.getElementById('armazem');
        if (!raiz) return;
        raiz.addEventListener('click', (e) => {
            const card = e.target.closest('.arm-card[data-item]');
            if (card) { abrirItem(card.dataset.item); return; }
            const b = e.target.closest('[data-acao]');
            if (!b) return;
            switch (b.dataset.acao) {
                case 'tema': filtro = b.dataset.tema; render(); break;
                case 'tipo': ftipo = b.dataset.tipo; salvarFiltros(); render(); break;
                case 'limpar': filtro = 'todos'; ftipo = 'todos'; frar = 'todos'; fanim = 'todos'; ordem = 'padrao'; busca = ''; salvarFiltros(); render(); break;
                case 'abrir': abrirItem(b.dataset.item); break;
                case 'extrato': ctx.emitir('listar_movimentos'); break;
                case 'ver-tema': filtro = b.dataset.tema; ftipo = 'todos'; frar = 'todos'; fanim = 'todos'; render(); { const r = raiz.closest('.market-content'); if (r) r.scrollTo({ top: 0, behavior: reduzMov() ? 'auto' : 'smooth' }); } break;
                case 'slide': irPara(Number(b.dataset.i)); break;
                case 'hero-seta': irPara(heroIdx + Number(b.dataset.dir)); break;
                case 'rolar': { const tr = b.closest('.arm-prat').querySelector('.arm-trilho'); tr.scrollBy({ left: Number(b.dataset.dir) * tr.clientWidth * 0.85, behavior: 'smooth' }); break; }
            }
        });
        raiz.addEventListener('input', (e) => { if (e.target.id === 'arm-busca') aoBuscar(e.target.value); });
        raiz.addEventListener('change', (e) => {
            const f = e.target.dataset && e.target.dataset.filtro;
            if (!f) return;
            if (f === 'tema') filtro = e.target.value; else if (f === 'rar') frar = e.target.value; else if (f === 'anim') fanim = e.target.value; else if (f === 'ordem') ordem = e.target.value;
            salvarFiltros(); render();
        });
        setInterval(atualizarContagens, 30000);
        raiz.innerHTML = '<div class="arm-vazio"><i class="fa-solid fa-spinner fa-spin"></i> Abrindo o Armazém...</div>';
    }

    /** Chamado quando a aba da loja aparece: pede a vitrine (no máximo a cada 20 s, o servidor manda tudo de novo se algo mudar). */
    function abrir() {
        if (!ctx) return;
        if (!estado || Date.now() - carregadoEm > 20000) ctx.emitir('listar_loja');
    }

    function receber(vitrine) {
        estado = vitrine;
        carregadoEm = Date.now();
        render();
        if (aberto) { if (itemDe(aberto)) abrirItem(aberto, true); else fecharModal(); }
        dispararConfete();
    }

    function compraOk(d) {
        comprando = null;
        clearTimeout(comprandoTimer);
        if (ctx.som) ctx.som();
        ctx.toast(`"${d.nome}" é seu!`, 'success');
        (d.premios || []).forEach((p, k) => setTimeout(() => ctx.toast(`Conquista da coleção: ${p.nome}! Está no seu inventário.`, 'success'), 700 + k * 600));
        if (estado) {
            estado.saldo = d.saldo;
            (d.entregues || []).forEach((id) => { const f = itemDe(id); if (f) f.possui = true; });   // o servidor já confirmou: sem esperar a vitrine nova
            atualizarCompra();
        }
        confetePara = d.item_id;
        setTimeout(dispararConfete, 1200);               // rede de segurança se a vitrine nova demorar
    }

    /** As contagens ("encerra em 3d 4h") andam sozinhas, sem pedir nada ao servidor. */
    function atualizarContagens() {
        document.querySelectorAll('.arm-tempo[data-fim]').forEach((el) => {
            const resta = (Number(el.dataset.fim) - Date.now()) / 1000;
            el.textContent = resta > 0 ? tempoTexto(resta) : 'agora';
        });
    }

    function dispararConfete() {
        if (!confetePara) return;
        const id = confetePara;
        confetePara = null;
        const card = document.querySelector('#arm-modal .arm-modal-card');
        if (!card || aberto !== id || !estado) return;
        const t = temaDe((itemDe(id) || {}).tema);
        confete(card, t ? [corOk(t.cores[0]), corOk(t.cores[1]), corOk(t.cor), '#ffffff', '#ffd76a'] : ['#ffd76a', '#ffffff', '#7289da']);
    }

    function compraRecusada(d) {
        comprando = null;
        clearTimeout(comprandoTimer);
        ctx.toast((d && d.msg) || 'Não foi possível comprar.', 'error');
        atualizarCompra();
    }

    function saldo(valor) {
        if (estado) { estado.saldo = valor; if (aberto) atualizarCompra(); }
    }

    /** O inventário mudou (equipou/tirou): atualiza só o botão do modal. */
    function inventarioMudou() { if (aberto) atualizarCompra(); }

    return { iniciar, abrir, receber, compraOk, compraRecusada, saldo, inventarioMudou, extrato: desenharExtrato, _estado: () => estado };
})();
