"""Ferramenta de olho (NAO e teste): gera qa_itens.html, uma galeria dos cosmeticos usando o CSS REAL do chat.html (os <style> dele sao copiados)
+ cosm_base/cosmeticos/cosm_temas/cosm_<categoria>.css. Serve pra olhar cada item grande e congelar as animacoes. Ver docs/ARTE_TEMAS.md.

Uso:  python testes/qa_itens.py <pasta de saida>
Depois sirva a pasta numa rota /debug-pag/ do servidor de teste (fora do repo) e abra:
  /debug-pag/qa_itens.html?m=gosma&n=simbionte&p=olhos&f=invasao&a=simbionte&e=invasao&t=8     (um item de cada tipo, grande)
  /debug-pag/qa_itens.html?tema=gatinhos&t=4                                                  (todos os itens de um tema GERADO, em ordem)
  /debug-pag/qa_itens.html?temas=gatinhos,docinhos&t=4                                        (faixa compacta por tema: varios temas numa tela so)
(m = moldura, n = nome, p = placa, f = faixa, a = efeito de avatar, e = efeito de perfil, t = congelar em N segundos)."""
import json, os, re, sys

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')
SAIDA = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
chat = open(os.path.join(RAIZ, 'templates', 'chat.html'), encoding='utf-8').read()
estilos = re.findall(r'<style[^>]*>(.*?)</style>', chat, flags=re.S)
css = '\n'.join(e for e in estilos if '{{' not in e and '{%' not in e)
try:
    GEN = json.load(open(os.path.join(RAIZ, 'cosm_gen.json'), encoding='utf-8'))
except OSError:
    GEN = {'arquivos': [], 'temas': [], 'itens': []}
html = '''<!doctype html>
<html lang="pt-BR" data-tema="dark">
<meta charset="utf-8">
<title>QA itens</title>
<style>''' + css + '''</style>
<style>
  body { background: #17181c; color: #ddd; padding: 12px; overflow: auto; height: auto; display: block; }
  h4 { margin: 14px 0 6px; color: #9aa3b2; font: 700 12px sans-serif; text-transform: uppercase; letter-spacing: .08em; }
  h4 small { color: #6b7385; text-transform: none; letter-spacing: 0; font-weight: 400; }
  .qa-linha { display: flex; gap: 28px; align-items: flex-end; flex-wrap: wrap; }
  .qa-av { position: relative; border-radius: 50%; background: var(--brand-color); isolation: isolate; }
  .qa-av img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; display: block; position: relative; z-index: 1; }
  .qa-ctl { position: sticky; top: 0; z-index: 99; background: #23262e; padding: 6px 10px; border-radius: 8px; margin-bottom: 8px; font: 12px sans-serif; }
  .qa-ctl button { background: #333845; color: #fff; border: 0; padding: 4px 8px; border-radius: 6px; cursor: pointer; margin-right: 3px; }
  .qa-card { width: 340px; }
  .qa-tema { display: flex; gap: 14px; align-items: center; padding: 8px 10px; margin: 6px 0; background: #1f2127; border-radius: 10px; }
  .qa-tema h5 { margin: 0; width: 70px; font: 700 12px sans-serif; color: #fff; }
  .qa-mini { transform-origin: 0 0; flex: none; }
  .qa-cartao-escala { width: 170px; height: 220px; flex: none; overflow: hidden; border-radius: 12px; }
</style>
<body>
<div class="qa-ctl">congelar em (s): <span id="qa-bt"></span> <button onclick="qaPlay()">rodar</button> <input id="qa-seg" size="3" placeholder="s"><button onclick="qaT(Number(document.getElementById('qa-seg').value))">ir</button></div>
<div id="qa-raiz"></div>
<script>
  const GEN = ''' + json.dumps(GEN, ensure_ascii=False) + ''';
  const V = Date.now();   // o service worker do app guarda /static pela URL: sem ?v= novo a pagina mostra arquivo velho
  const CSS = ['cosmeticos', 'cosm_base', 'cosm_temas', 'efeitos'].concat(GEN.arquivos.map(c => 'cosm_' + c));
  for (const c of CSS) document.head.insertAdjacentHTML('beforeend', `<link rel="stylesheet" href="/static/css/${c}.css?v=${V}">`);
  const carrega = (src) => new Promise(r => { const e = document.createElement('script'); e.src = src + '?v=' + V; e.onload = r; e.onerror = r; document.body.appendChild(e); });
  window.qaT = (s) => { document.getAnimations().forEach(a => { try { a.pause(); a.currentTime = s * 1000; } catch (e) {} }); };
  window.qaPlay = () => document.getAnimations().forEach(a => a.play());
  (async () => {
    await carrega('/static/js/cosmeticos.js'); await carrega('/static/js/cosm_temas.js');
    for (const c of GEN.arquivos) await carrega('/static/js/cosm_' + c + '.js');
    Cosm.iniciar();
    const q = new URLSearchParams(location.search);
    const foto = '/static/img/icone-192.png';
    const av = (px, cls, ef) => `<div class="qa-av ${ef ? 'com-ef ' : ''}${cls}" style="width:${px}px;height:${px}px;margin:${Math.round(px * .3)}px">${ef ? Cosm.htmlEfeitoAvatar(ef) : ''}<img src="${foto}"></div>`;
    const tile = (px, cls) => `<div class="pf-tile-av ${cls}" style="width:${px}px;height:${px}px;margin:12px"><img src="${foto}"></div>`;
    const blocoMoldura = (m) => `<div class="qa-linha">${tile(120, 'moldura-' + m)}${tile(92, 'moldura-' + m)}${tile(52, 'moldura-' + m)}<div class="chat-avatar moldura-${m}" style="position:relative;width:40px;height:40px;margin:12px;border-radius:50%;background:#5865f2;overflow:visible"><img src="${foto}" style="width:100%;height:100%;border-radius:50%"></div></div>`;
    const blocoNome = (n) => `<div class="qa-linha" style="background:#2b2d31;padding:12px;border-radius:8px"><span class="cat-nome ne-${n}" style="font-size:26px">Aquele Sales</span><span class="ne-${n}" style="font-size:15px">Aquele Sales</span><span class="ne-${n}" style="font-size:13px">Aquele Sales</span></div>`;
    const blocoPlaca = (p) => `<div class="qa-linha"><div class="pf-placa-linha placa-${p}" style="width:260px"><span class="pf-mini-av"><img src="${foto}"></span><span>Aquele Sales</span></div><div class="pf-placa-linha placa-${p}" style="width:160px"><span class="pf-mini-av"><img src="${foto}"></span><span>Ana</span></div><div class="user-profile-bar placa-${p}" style="width:240px;height:52px;position:relative;display:flex;align-items:center;padding:0 10px;gap:8px"><span class="pf-mini-av"><img src="${foto}"></span><span>Aquele Sales</span><span style="margin-left:auto">&#127908; &#127911; &#9881;</span></div></div>`;
    const blocoFaixa = (f) => `<div class="qa-linha"><div class="banner-anim-${f}" style="width:340px;height:112px;border-radius:12px"></div><div class="banner-anim-${f}" style="width:200px;height:60px;border-radius:10px"></div><div class="inv-faixa banner-anim-${f}" style="width:120px;height:56px;border-radius:8px"></div></div>`;
    const blocoAvatar = (a) => `<div class="qa-linha">${av(200, '', a)}${av(92, '', a)}${av(52, '', a)}${av(40, '', a)}</div>`;
    const cartao = (m, n, p, f, a, e, extra = '') => `<div class="qa-card"><div class="pc com-tema" style="position:relative;width:340px;border-radius:22px;background:#1b1c22;overflow:hidden;min-height:440px"><div class="pc-banner ${f ? 'banner-anim-' + f : ''}" style="height:112px"></div><div class="pc-topo" style="padding:0 16px;margin-top:-46px;display:flex;align-items:flex-end;gap:10px"><div class="pc-avatar ${m ? 'moldura-' + m : ''} ${a ? 'com-ef' : ''}">${a ? Cosm.htmlEfeitoAvatar(a) : ''}<div class="pc-avatar-img"><img src="${foto}"></div></div></div><div class="pc-corpo"><div class="pc-nome ${n ? 'ne-' + n : ''}" style="font-size:22px;font-weight:800">Aquele Sales</div><div style="color:#9aa3b2;font-size:13px">@aquele.sales</div><div class="pf-placa-linha ${p ? 'placa-' + p : ''}" style="margin:12px 0"><span class="pf-mini-av"><img src="${foto}"></span><span>Aquele Sales</span></div><div style="color:#9aa3b2;font-size:12px;margin-top:20px">BIO<br><span style="color:#ddd">Texto de exemplo da bio.</span></div></div>${e ? Cosm.htmlEfeitoPerfil(e) : ''}</div></div>`;
    let h = '';
    const tema = q.get('tema'), temas = q.get('temas');
    if (tema) {
      const its = GEN.itens.filter(i => i.tema === tema), por = (t) => its.filter(i => i.tipo === t);
      const t = GEN.temas.find(x => x.id === tema);
      h += `<h4>${t ? t.nome : tema} <small>${its.length} itens</small></h4>`;
      por('moldura').forEach(i => h += `<h4>moldura <small>${i.id} - ${i.nome}</small></h4>` + blocoMoldura(i.id));
      por('nome').forEach(i => h += `<h4>nome <small>${i.id} - ${i.nome}</small></h4>` + blocoNome(i.id));
      por('placa').forEach(i => h += `<h4>placa <small>${i.id} - ${i.nome}</small></h4>` + blocoPlaca(i.id));
      por('faixa').forEach(i => h += `<h4>faixa <small>${i.id} - ${i.nome}</small></h4>` + blocoFaixa(i.id));
      por('efeito_avatar').forEach(i => h += `<h4>efeito de avatar <small>${i.id} - ${i.nome}</small></h4>` + blocoAvatar(i.id));
      const eps = por('efeito_perfil'), m0 = (por('moldura')[0] || {}).id, n0 = (por('nome')[0] || {}).id, p0 = (por('placa')[0] || {}).id, f0 = (por('faixa')[0] || {}).id, a0 = (por('efeito_avatar')[0] || {}).id;
      h += `<h4>cartao inteiro <small>tema todo equipado</small></h4><div class="qa-linha">${cartao(m0, n0, p0, f0, a0, (eps[0] || {}).id)}${eps.slice(1).map(i => cartao('', '', '', '', '', i.id)).join('')}</div>`;
    } else if (temas) {
      h += temas.split(',').map(id => {
        const its = GEN.itens.filter(i => i.tema === id), d = (t) => (its.find(i => i.tipo === t) || {}).id;
        const m = d('moldura'), n = d('nome'), p = d('placa'), f = d('faixa'), a = d('efeito_avatar'), e = d('efeito_perfil');
        return `<div class="qa-tema"><h5>${id}</h5>${m ? `<div class="pf-tile-av moldura-${m}" style="width:56px;height:56px;margin:14px"><img src="${foto}"></div>` : ''}<div style="display:flex;flex-direction:column;gap:6px">${n ? `<span class="ne-${n}" style="font-size:20px">Aquele Sales</span>` : ''}${p ? `<div class="pf-placa-linha placa-${p}" style="width:190px"><span class="pf-mini-av"><img src="${foto}"></span><span>Aquele Sales</span></div>` : ''}${f ? `<div class="banner-anim-${f}" style="width:190px;height:62px;border-radius:8px"></div>` : ''}</div>${a ? av(70, '', a) : ''}${e ? `<div class="qa-cartao-escala"><div style="transform:scale(.5);transform-origin:0 0;width:340px">${cartao('', '', '', '', '', e)}</div></div>` : ''}</div>`;
      }).join('');
    } else {
      const m = q.get('m') || '', n = q.get('n') || '', p = q.get('p') || '', f = q.get('f') || '', a = q.get('a') || '', e = q.get('e') || '';
      if (m) h += `<h4>moldura ${m}</h4>` + blocoMoldura(m);
      if (n) h += `<h4>nome ${n}</h4>` + blocoNome(n);
      if (p) h += `<h4>placa ${p}</h4>` + blocoPlaca(p);
      if (f) h += `<h4>faixa ${f}</h4>` + blocoFaixa(f);
      if (a) h += `<h4>efeito de avatar ${a}</h4>` + blocoAvatar(a);
      if (e || m || n || p || f || a) h += `<h4>cartao inteiro</h4><div class="qa-linha">${cartao(m, n, p, f, a, e)}</div>`;
    }
    document.getElementById('qa-raiz').innerHTML = h;
    document.getElementById('qa-bt').innerHTML = [0, 2, 4, 6, 8, 10, 12, 14].map(s => `<button onclick="qaT(${s})">${s}</button>`).join('');
    const t = Number(q.get('t')); if (t || q.get('t') === '0') setTimeout(() => qaT(t), 400);
  })();
</script>
</html>'''
open(os.path.join(SAIDA, 'qa_itens.html'), 'w', encoding='utf-8').write(html)
print('gerado em', os.path.join(SAIDA, 'qa_itens.html'))
