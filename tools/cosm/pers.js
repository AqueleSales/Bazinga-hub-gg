'use strict';
/* Construtor dos itens "de apoio" de um personagem (Rodada 40): nome, placa, faixa, fala, radar, chat, som, pin e servidor,
   a partir de uma especificação curta. Moldura, efeito de avatar e de perfil são sempre arte própria (cada personagem os escreve). */
const { N, Pl, F } = require('./kit');
const { FALA, RADAR, CHAT, SOM, PIN, SERV, PAGINA } = require('./extras_kit');
const R = require('./raster');

/** c = { tema:'pasta das imagens', r:'lendario', cores:[c1,c2],
 *    nome:{ grad, contorno, cw, fonte, mov, dur, espaco, img:'recorte depois do nome', nomeItem },
 *    placa:{ nomeItem, base, pad, mov, dur, borda, img:{ nome, lado, tam, y }, brilho },
 *    faixa:{ nomeItem, fundo, fixo, longe, perto, css (usa $ID) },
 *    fala:{ nomeItem, cores, dur, passos }, radar:{ nomeItem, cor, estilo, glow },
 *    chat:{ nomeItem, cor, cor2, particula }, som:{ nomeItem, notas, ruidos, arquivo },
 *    pin:{ nomeItem, img, bal }, serv:{ nomeItem, cores, dur, passos }, pagina:{ nomeItem, desc, ...preset } } */
function apoio(c) {
    const r = c.r || 'lendario', T = c.tema, out = [];
    const d = (k, padrao) => (c[k] && c[k].desc) || padrao;
    if (c.nome) {
        const n = c.nome, extra = n.img ? `.ne-$ID::after{content:'';display:inline-block;width:${n.imgW || 1.1}em;height:${n.imgH || 1.3}em;margin-left:.25em;vertical-align:-.3em;background:${R.css(T, n.img)} center/contain no-repeat;-webkit-text-stroke:0}` : undefined;
        out.push(N(n.nomeItem, n.desc, { grad: n.grad, cor: n.cor, mov: n.mov || 'desliza', dur: n.dur || 4, contorno: n.contorno, cw: n.cw || 1.1, fonte: n.fonte || 'impacto', espaco: n.espaco === undefined ? .8 : n.espaco, peso: 900, brilho: n.brilho, passos: n.passos, g1: n.g1, g2: n.g2 }, { r, css: extra }));
    }
    if (c.placa) {
        const p = c.placa;
        out.push(Pl(p.nomeItem, p.desc, { base: p.base, pad: p.pad, mov: p.mov, dur: p.dur, borda: p.borda, brilho: p.brilho, texto: p.texto, img: p.img && { url: R.url(T, p.img.nome), lado: p.img.lado || 'dir', tam: p.img.tam || 150, y: p.img.y === undefined ? 50 : p.img.y, barOculta: true } }, { r }));
    }
    if (c.faixa) { const f = c.faixa; out.push(F(f.nomeItem, f.desc, { fundo: f.fundo, angulo: f.angulo, fixo: f.fixo, longe: f.longe, perto: f.perto }, { r, css: f.css })); }
    if (c.fala) out.push(FALA(c.fala.nomeItem, c.fala.desc, { cores: c.fala.cores, passos: c.fala.passos, dur: c.fala.dur }, { r }));
    if (c.radar) out.push(RADAR(c.radar.nomeItem, c.radar.desc, { cor: c.radar.cor, estilo: c.radar.estilo, glow: c.radar.glow, fundo: c.radar.fundo }, { r }));
    if (c.chat) out.push(CHAT(c.chat.nomeItem, c.chat.desc, { cor: c.chat.cor, cor2: c.chat.cor2, particula: c.chat.particula }, { r }));
    if (c.som) out.push(SOM(c.som.nomeItem, c.som.desc, { notas: c.som.notas, ruidos: c.som.ruidos, arquivo: c.som.arquivo, vol: c.som.vol }, { r }));
    if (c.pin) out.push(PIN(c.pin.nomeItem, c.pin.desc, { img: c.pin.img ? R.url(T, c.pin.img) : undefined, icone: c.pin.icone, pal: c.pin.pal, bal: c.pin.bal === undefined ? 2 : c.pin.bal }, { r }));
    if (c.serv) out.push(SERV(c.serv.nomeItem, c.serv.desc, { cores: c.serv.cores, passos: c.serv.passos, dur: c.serv.dur }, { r }));
    if (c.pagina) { const { nomeItem, desc, ...preset } = c.pagina; out.push(PAGINA(nomeItem, desc, preset, { r })); }
    return out;
}

module.exports = { apoio };
