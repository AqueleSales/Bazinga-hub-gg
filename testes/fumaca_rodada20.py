"""Rodada 20: aviso de atualização (setinha + pop-up de novidades), temas novos e tema personalizado, "Colar link" do seletor de imagem
(com a proteção contra SSRF) e o editor de imagem na lojinha do Bazar.

Nada aqui acessa a internet: o download de verdade foi testado à mão (ver CLAUDE.md, Rodada 20)."""
import os, re, sys
from io import BytesIO
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, RAIZ)
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app.models import Role, Person
from app import utils, importar, novidades

app = create_app()
falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding='utf-8') as f:
        return f.read()

chat = ler('app/templates/chat.html')
bazar_js = ler('app/static/js/bazar.js')

# ---------------------------------------------------------------- novidades / aviso de atualização
ids = [n['id'] for n in novidades.NOVIDADES]
ok(ids == sorted(ids, reverse=True) and len(set(ids)) == len(ids), 'Novidades: ids únicos e do mais novo pro mais antigo (a nova entrada vai no TOPO)')
ok(all(re.match(r'^fa-[a-z0-9-]+$', i['icone']) and i['titulo'] and i['texto'] for n in novidades.NOVIDADES for i in n['itens']), 'Novidades: todo item tem ícone válido, título e texto')
ok(novidades.novidade_atual() == ids[0], 'Novidades: a página sabe qual é a última')
ok('aviso-versao' not in chat and 'mostrarAvisoNovaVersao' not in chat, 'Atualização: a faixa antiga "Saiu uma versão nova" (que recarregava sozinha) acabou')
ok("if (d && d.versao && d.versao !== VERSAO_PAGINA) anunciarAtualizacao();" in chat, 'Atualização: versão diferente do servidor liga o botão (não recarrega a página sozinha)')
ok(chat.count('HTML_BTN_ATT') >= 3 and 'return HTML_BTN_ATT + ' in chat, 'Atualização: o botão fica ao lado de toda caixa de entrada (radar, canal e cabeçalho da DM refeito)')
ok(re.search(r'\.btn-atualizar \{[^}]*display: none', chat) and 'body.tem-atualizacao .btn-atualizar { display: inline-flex; }' in chat, 'Atualização: o botão só aparece quando há atualização')
ok('translate(0,-460)' in chat and '<svg x="0" y="0" width="512" height="424"' in chat and 'translateY(460px)' in chat, 'Atualização: duas setas em rolo recortadas na borda da barra (some ao atravessar, a próxima entra por cima)')
ok("setTimeout(() => document.body.classList.remove('att-aviso'), 3900)" in chat, 'Atualização: o texto abre, fica uns 3 s e recolhe')
ok(re.search(r'id="att-fechar"', chat) and re.search(r'id="att-atualizar"', chat) and chat.index('id="att-fechar"') < chat.index('id="att-corpo"') < chat.index('id="att-atualizar"'),
   'Atualização: X em cima, novidades no meio, botão "Atualizar agora" embaixo')
ok('openConfirmModal(\'Atualizar agora?\'' in chat, 'Atualização: avisa antes de recarregar numa call ou com mensagem sendo escrita')

with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    pessoas = {}
    for n in ('Ana', 'Beto'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); db.session.commit(); pessoas[n] = p.id

def cliente(nome):
    fc = app.test_client()
    with fc.session_transaction() as s: s['user_id'] = pessoas[nome]
    cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
    return cl, fc

ana, fana = cliente('Ana'); beto, fbeto = cliente('Beto')
ok(app.test_client().get('/api/novidades').status_code == 401, 'Novidades: sem login não lê o log')
j = fana.get('/api/novidades').get_json()
ok(j['atual'] == ids[0] and len(j['itens']) >= 5, 'Novidades: o log vem do servidor')
html = fana.get('/chat').get_data(as_text=True)
ok(f'const NOVIDADE_DA_PAGINA = {ids[0]};' in html, 'Novidades: a página abre sabendo a última novidade')

# ---------------------------------------------------------------- temas
dark_extras = ('meia_noite', 'floresta', 'oceano', 'por_do_sol', 'ametista', 'cafe', 'cereja')
claros_extras = ('sakura', 'menta', 'areia')
ok(set(dark_extras + claros_extras) <= set(utils.TEMAS_VALIDOS) and 'custom' in utils.TEMAS_VALIDOS and len(dark_extras + claros_extras) == 10, 'Temas: 10 temas novos + personalizado são aceitos')
ok(all(len(t) <= 20 for t in utils.TEMAS_VALIDOS), 'Temas: todo id cabe na coluna (String(20))')
for t in utils.TEMAS_VALIDOS:
    if t in ('dark', 'custom'):
        continue
    ok(f':root[data-tema="{t}"]' in chat, f'Temas: "{t}" tem paleta no CSS (primeiro desenho sem piscar)')
    ok(f"id: '{t}'" in chat, f'Temas: "{t}" está no catálogo da tela de Aparência')
catalogo_js = chat[chat.index('const CATALOGO_TEMAS'):chat.index('const TEMAS_CLAROS_JS')]   # (outros catálogos do arquivo usam ids iguais, como "sakura")
ok(all(('claro: true' in re.search(r"\{ id: '%s'[^}]*\}" % t, catalogo_js).group(0)) == (t in utils.TEMAS_CLAROS) for t in utils.TEMAS_VALIDOS if t not in ('custom',)),
   'Temas: os claros do catálogo (JS) são os mesmos de utils.TEMAS_CLAROS (ligam data-claro)')
ok(':root[data-tema="light"] body::' not in chat and ':root[data-claro] body::before' in chat, 'Temas: regras de fundo claro seguem [data-claro] e valem pra todo tema claro')
ok('data-tema="{{ tema_id }}"' in chat and 'data-claro' in chat, 'Temas: o HTML já nasce com o tema e se o fundo é claro')
ok("style=\"color:var(--text-header);font-weight:500;\"" in chat and 'color: var(--text-header);">Bem-vindo ao início do canal!' in chat, 'Temas claros: nome dos membros e "Bem-vindo" não ficam brancos sobre branco')

# mudar_tema: preset, inválido, custom, eco, e conservar o personalizado ao trocar de tema
ana.emit('mudar_tema', {'tema': 'sakura'}); rec = ana.get_received()
ev = [e for e in rec if e['name'] == 'preferencias_carregadas']
ok(ev and ev[-1]['args'][0]['tema'] == 'sakura' and ev[-1]['args'][0]['tema_claro'] is True, 'Tema: salvar um claro devolve tema_claro e avisa todas as abas')
ana.emit('mudar_tema', {'tema': 'dark'}); ana.get_received()
ana.emit('mudar_tema', {'tema': 'rosa_choque'}); ana.get_received()
with app.app_context():
    ok(db.session.get(Person, pessoas['Ana']).tema == 'dark', 'Tema: id inventado é ignorado (nada de texto livre virar classe)')
custom = {'base': 'light', 'cor': '#E0425F', 'img': '/debug-up/abc.webp', 'escuro': 40, 'painel': 55}
ana.emit('mudar_tema', {'tema': 'custom', 'custom': custom}); rec = ana.get_received()
ev = [e for e in rec if e['name'] == 'preferencias_carregadas'][-1]['args'][0]
ok(ev['tema'] == 'custom' and ev['tema_custom']['cor'] == '#e0425f' and ev['tema_custom']['img'] == '/debug-up/abc.webp' and ev['tema_claro'] is True, 'Tema personalizado: salva base, cor, imagem e transparências, e a base clara liga data-claro')
ana.emit('mudar_tema', {'tema': 'amoled'}); ana.get_received()
with app.app_context():
    ok(utils.tema_custom_da_pessoa(db.session.get(Person, pessoas['Ana']))['painel'] == 55, 'Tema personalizado: as escolhas ficam guardadas quando a pessoa troca de tema e volta')
ana.emit('mudar_tema', {'tema': 'custom', 'custom': {'base': 'dark', 'cor': 'vermelho', 'img': 'https://evil.example/x.png', 'escuro': 999, 'painel': -5}}); rec = ana.get_received()
ev = [e for e in rec if e['name'] == 'preferencias_carregadas'][-1]['args'][0]['tema_custom']
ok(ev['cor'] == '#7289da' and ev['img'] == '' and ev['escuro'] == 90 and ev['painel'] == 30, 'Tema personalizado: cor ruim, imagem de fora e números absurdos viram valores seguros')
ana.emit('mudar_tema', {'tema': 'custom', 'custom': 'x'}); rec = ana.get_received()
ok(any(e['name'] == 'erro_bazinga' for e in rec), 'Tema personalizado: dado inválido vira aviso, não quebra')
with app.app_context():
    ok(db.session.get(Person, pessoas['Beto']).tema == 'dark', 'Tema: o tema de uma pessoa não muda o da outra')

# validação direta
v = utils.tema_custom_valido
ok(v(None) is None and v('x') is None and v([]) is None, 'Validação: só aceita dicionário')
ok(v({'img': "/a'b.png"})['img'] == '' and v({'img': '/a(b).png'})['img'] == '' and v({'img': '/a b.png'})['img'] == '' and v({'img': '/ok/a.png'})['img'] == '/ok/a.png', 'Validação: a imagem não pode fechar aspas/parênteses (vai dentro de url("..."))')
ok(v({'img': 'https://res.cloudinary.com/x/y.webp'})['img'].startswith('https://res.cloudinary.com/') and v({'img': 'https://media2.giphy.com/a.gif'})['img'] != '' and v({'img': 'http://res.cloudinary.com/x'})['img'] == '', 'Validação: só imagem do próprio app, Cloudinary ou Giphy')
ok(v({'base': 'neon'})['base'] == 'dark' and v({'escuro': 'abc'})['escuro'] == 0, 'Validação: base desconhecida e número quebrado voltam ao padrão')
# /chat com tema personalizado + imagem: primeiro desenho já traz as variáveis
html = fana.get('/chat').get_data(as_text=True)
ok('data-tema="custom"' in html, 'Tema: o /chat de quem tem personalizado já abre nele')
ana.emit('mudar_tema', {'tema': 'custom', 'custom': {'base': 'light', 'cor': '#112233', 'img': '/debug-up/f.webp', 'escuro': 20, 'painel': 70}}); ana.get_received()
html = fana.get('/chat').get_data(as_text=True)
ok(re.search(r'<html[^>]*data-tema="custom"[^>]*data-claro', html) is not None, 'Tema personalizado: base clara nasce com data-claro')
ok("--fundo-img: url('/debug-up/f.webp')" in html and '--painel-opac: 70%' in html and '--fundo-escuro: 0.2' in html and 'data-fundo' in html, 'Tema personalizado: imagem, escurecimento e opacidade já vêm no HTML')

# ---------------------------------------------------------------- imagem por link (SSRF)
def recusa(url, trecho=''):
    try:
        importar.baixar_imagem_externa(url)
    except importar.ErroImportar as e:
        return trecho in str(e)
    except Exception:
        return False
    return False
ok(recusa('http://exemplo.com/a.png', 'https'), 'Link: só https')
ok(recusa('https://localhost/a.png') and recusa('https://127.0.0.1/a.png') and recusa('https://[::1]/a.png') and recusa('https://10.0.0.5/a.png') and recusa('https://169.254.169.254/latest/'), 'Link: nada de localhost nem IP direto')
ok(recusa('https://u:p@exemplo.com/a.png') and recusa('https://exemplo.com:8443/a.png') and recusa('ftp://exemplo.com/a.png') and recusa('') and recusa(None) and recusa('https://' + 'a' * 300 + '.com/x'), 'Link: sem usuário/senha, sem outra porta, sem outro protocolo')
import socket
getaddrinfo_original = socket.getaddrinfo
socket.getaddrinfo = lambda host, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]
ok(recusa('https://parece-publico.exemplo.com/a.png', 'não é um site público'), 'Link: domínio que aponta pra IP interno é recusado (SSRF)')
socket.getaddrinfo = lambda host, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443)), (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.168.1.10', 443))]
ok(recusa('https://misto.exemplo.com/a.png', 'não é um site público'), 'Link: basta UM IP interno entre as respostas pra recusar')
socket.getaddrinfo = lambda host, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))]

# resposta simulada do site: redirecionamento, conteúdo e tamanho
class FalsaResp:
    def __init__(self, status=200, headers=None, corpo=b''):
        self.status, self.headers, self._corpo = status, headers or {}, corpo
    def stream(self, n):
        for i in range(0, len(self._corpo), n): yield self._corpo[i:i + n]
    def release_conn(self): pass
class FalsoPool:
    def close(self): pass
respostas = {}
def pedir_falso(host, ip, caminho):
    return FalsoPool(), respostas[(host, caminho)]
importar._pedir = pedir_falso
from PIL import Image
def bytes_de(formato, tam=(40, 30)):
    b = BytesIO(); Image.new('RGB', tam, (200, 50, 50)).save(b, format=formato); return b.getvalue()
png = bytes_de('PNG')
respostas[('img.exemplo.com', '/a.png')] = FalsaResp(200, {'Content-Type': 'image/png'}, png)
d, mime = importar.baixar_imagem_externa('https://img.exemplo.com/a.png')
ok(d == png and mime == 'image/png', 'Link: imagem de verdade é baixada e conferida pelo Pillow')
respostas[('img.exemplo.com', '/falso.png')] = FalsaResp(200, {'Content-Type': 'image/png'}, b'<html>nao sou imagem</html>')
ok(recusa('https://img.exemplo.com/falso.png', 'não é de uma imagem'), 'Link: conteúdo que não é imagem é recusado mesmo dizendo ser png')
respostas[('img.exemplo.com', '/v.svg')] = FalsaResp(200, {'Content-Type': 'image/svg+xml'}, b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
ok(recusa('https://img.exemplo.com/v.svg'), 'Link: SVG (pode ter script) é recusado')
respostas[('img.exemplo.com', '/grande.png')] = FalsaResp(200, {'Content-Type': 'image/png', 'Content-Length': str(importar.LIMITE_BYTES + 1)}, b'x')
ok(recusa('https://img.exemplo.com/grande.png', '8 MB'), 'Link: imagem acima de 8 MB é recusada pelo cabeçalho')
respostas[('img.exemplo.com', '/escondida.png')] = FalsaResp(200, {'Content-Type': 'image/png'}, b'\x89PNG' + b'0' * (importar.LIMITE_BYTES + 10))
ok(recusa('https://img.exemplo.com/escondida.png', '8 MB'), 'Link: tamanho mentido no cabeçalho não passa (leitura com teto)')
respostas[('img.exemplo.com', '/redir')] = FalsaResp(302, {'Location': 'https://localhost/segredo.png'})
ok(recusa('https://img.exemplo.com/redir'), 'Link: redirecionamento pra endereço interno é recusado')
respostas[('img.exemplo.com', '/r1')] = FalsaResp(302, {'Location': '/a.png'})
d, _ = importar.baixar_imagem_externa('https://img.exemplo.com/r1')
ok(d == png, 'Link: redirecionamento normal (caminho relativo) é seguido')
respostas[('img.exemplo.com', '/laco')] = FalsaResp(302, {'Location': '/laco'})
ok(recusa('https://img.exemplo.com/laco', 'redireciona demais'), 'Link: laço de redirecionamento tem teto')
respostas[('img.exemplo.com', '/err')] = FalsaResp(403, {})
ok(recusa('https://img.exemplo.com/err', 'recusou'), 'Link: site que recusa (403) vira mensagem clara')
pagina = b'<html><head><meta property="og:image" content="https://img.exemplo.com/a.png"><title>x</title></head></html>'
respostas[('pin.exemplo.com', '/pin/1')] = FalsaResp(200, {'Content-Type': 'text/html; charset=utf-8'}, pagina)
d, _ = importar.baixar_imagem_externa('https://pin.exemplo.com/pin/1')
ok(d == png, 'Link: link de PÁGINA (ex.: pin do Pinterest) pega a imagem declarada em og:image')
respostas[('pin.exemplo.com', '/sem')] = FalsaResp(200, {'Content-Type': 'text/html'}, b'<html><body>sem imagem</body></html>')
ok(recusa('https://pin.exemplo.com/sem', 'Copiar endereço da imagem'), 'Link: página sem imagem orienta a copiar o endereço da imagem')
respostas[('pin.exemplo.com', '/dupla')] = FalsaResp(200, {'Content-Type': 'text/html'}, b'<meta property="og:image" content="https://pin.exemplo.com/sem">')
ok(recusa('https://pin.exemplo.com/dupla'), 'Link: página que aponta pra outra página não vira laço (1 nível só)')
socket.getaddrinfo = getaddrinfo_original

# rota
import app.main.routes as rotas
chamadas = []
rotas.baixar_imagem_externa = lambda url: (chamadas.append(url) or (png, 'image/png'))
ok(app.test_client().post('/api/imagem/importar', json={'url': 'https://a.com/x.png'}).status_code == 401, 'Rota: sem login não baixa nada')
rotas._ultimo_importar.clear()
resp = fana.post('/api/imagem/importar', json={'url': 'https://a.com/x.png'})
ok(resp.status_code == 200 and resp.mimetype == 'image/png' and resp.data == png and resp.headers.get('Cache-Control') == 'no-store', 'Rota: devolve os bytes da imagem')
ok(fana.post('/api/imagem/importar', json={'url': 'https://a.com/y.png'}).status_code == 429, 'Rota: freio de 2 s por pessoa')
rotas._ultimo_importar.clear()
def explode(url): raise importar.ErroImportar('Esse link não é de uma imagem.')
rotas.baixar_imagem_externa = explode
resp = fana.post('/api/imagem/importar', json={'url': 'https://a.com/z'})
ok(resp.status_code == 400 and 'não é de uma imagem' in resp.get_json()['error'], 'Rota: erro de link vira JSON legível')
ok('/api/imagem/importar' in chat and 'id="sm-link"' in chat and 'importarLinkDaImagem' in chat, 'Seletor: campo "Colar link" ligado à rota')

# ---------------------------------------------------------------- formatos novos do editor / recorte de animação
ok({'tela', 'produto', 'anuncio'} <= set(utils.FORMATOS_ANIMADOS), 'Editor: formatos tela, produto e anúncio existem também no recorte de animação do servidor')
for fmt, (w, h) in (('tela', (640, 360)), ('produto', (600, 450)), ('anuncio', (660, 440))):
    b = BytesIO(); quadros = [Image.new('RGB', (120, 80), cor) for cor in ((255, 0, 0), (0, 255, 0))]
    quadros[0].save(b, format='GIF', save_all=True, append_images=quadros[1:], duration=100, loop=0)
    saida = Image.open(BytesIO(utils.recortar_animacao(b.getvalue(), fmt)))
    ok(saida.size == (w, h) and getattr(saida, 'n_frames', 1) == 2, f'Editor: GIF no formato "{fmt}" sai {w}x{h} e continua animado')
ok("['quadrado', 'faixa', 'painel', 'tela', 'produto', 'anuncio']" in chat and 'PW = 300; PH = 225; SW = 1200; SH = 900' in chat, 'Editor: formatos tela (16:9), produto (4:3) e anúncio (3:2) no editor do navegador')

# ---------------------------------------------------------------- lojinha do Bazar com o editor
ok('escolherImagem: (cfg) => abrirSeletorMidia(cfg)' in chat, 'Bazar: o seletor de imagem do app é entregue ao Bazar')
ok("escolherImagem(id === 'logo_url' ? 'quadrado' : 'faixa'" in bazar_js, 'Bazar: logo (quadrado) e banner (faixa) passam pelo editor')
ok("escolherImagem('produto'" in bazar_js and "escolherImagem('anuncio'" in bazar_js, 'Bazar: foto de produto (4:3) e arte de anúncio (3:2) passam pelo editor')
ok("escolher('image/*', (f) => subir(f, (url) => { ed.loja" not in bazar_js and "escolher('image/*', (f) => subir(f, (url) => { ed.prod.imagens" not in bazar_js, 'Bazar: acabou o "só escolher arquivo" nos slots de imagem da lojinha')
ok('Adicionar foto, GIF ou vídeo curto' in bazar_js and 'Vídeo completo (opcional)' in bazar_js, 'Bazar: vídeo curto vira animação pelo botão de foto; o vídeo completo segue sem edição (e diz isso)')

# ---------------------------------------------------------------- tema POR TIPO DE APARELHO (computador x celular)
UA_IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
UA_ANDROID = 'Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36'
UA_PC = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
UA_APP = UA_PC + ' PanteaoDesktop/0.3.1'
ok(all(utils.aparelho_pelo_user_agent(u) == a for u, a in ((UA_IPHONE, 'celular'), (UA_ANDROID, 'celular'), (UA_PC, 'computador'), (UA_APP, 'computador'), ('', 'computador'), (None, 'computador'))),
   'Aparelho: iPhone/Android caem em "celular"; PC, app do Windows e User-Agent vazio em "computador"')

with app.app_context():
    cx = Person(name='Caio', email='caio@x', role_id=db.session.query(Role).first().id, username='caio'); db.session.add(cx); db.session.commit(); pessoas['Caio'] = cx.id
caio, fcaio = cliente('Caio')

def pagina(ua):
    return fcaio.get('/chat', headers={'User-Agent': ua}).get_data(as_text=True)
def html_tag(html):
    return html[html.index('<html'):html.index('<head>')]

caio.emit('mudar_tema', {'tema': 'sakura', 'aparelho': 'computador'}); caio.get_received()
ok('data-tema="sakura"' in html_tag(pagina(UA_PC)) and 'data-tema="sakura"' in html_tag(pagina(UA_IPHONE)), 'Aparelho: celular que ainda não escolheu usa o tema do computador')
caio.emit('mudar_tema', {'tema': 'ametista', 'aparelho': 'celular'}); rec = caio.get_received()
ev = [e for e in rec if e['name'] == 'preferencias_carregadas'][-1]['args'][0]
ok(ev['aparelho'] == 'celular' and ev['tema'] == 'ametista', 'Aparelho: o aviso de mudança diz de qual tipo de aparelho foi (o outro tipo ignora)')
with app.app_context():
    cp = db.session.get(Person, pessoas['Caio'])
    ok(cp.tema == 'sakura' and cp.tema_mobile == 'ametista', 'Aparelho: mexer no celular não muda o tema do computador (cada um tem o seu espaço na conta)')
ok('data-tema="sakura"' in html_tag(pagina(UA_PC)) and 'data-tema="ametista"' in html_tag(pagina(UA_ANDROID)), 'Aparelho: cada tipo de aparelho abre com o seu tema')
caio.emit('mudar_tema', {'tema': 'cafe', 'aparelho': 'computador'}); caio.get_received()
ok('data-tema="cafe"' in html_tag(pagina(UA_PC)) and 'data-tema="ametista"' in html_tag(pagina(UA_IPHONE)), 'Aparelho: depois que o celular escolheu, mudar o do computador não mexe mais nele')

# fundo (personalizado) separado
caio.emit('mudar_tema', {'tema': 'custom', 'aparelho': 'computador', 'custom': {'base': 'dark', 'cor': '#112233', 'img': '/debug-up/so_pc.webp', 'escuro': 20, 'painel': 70}}); caio.get_received()
caio.emit('mudar_tema', {'tema': 'custom', 'aparelho': 'celular', 'custom': {'base': 'light', 'cor': '#445566', 'img': '/debug-up/so_celular.webp', 'escuro': 50, 'painel': 40}}); caio.get_received()
h_pc, h_cel = pagina(UA_PC), pagina(UA_IPHONE)
ok('/debug-up/so_pc.webp' in html_tag(h_pc) and '/debug-up/so_celular.webp' not in h_pc, 'Fundo: o computador carrega a imagem DELE e a do celular não aparece nem na página')
ok('/debug-up/so_celular.webp' in html_tag(h_cel) and '/debug-up/so_pc.webp' not in h_cel and 'data-claro' in html_tag(h_cel), 'Fundo: o celular carrega a imagem DELE (e a base clara dele) e a do computador não aparece nem na página')
ok('"img":"/debug-up/so_pc.webp"' in h_pc.replace(' ', '') or "'/debug-up/so_pc.webp'" in h_pc or '/debug-up/so_pc.webp' in h_pc, 'Fundo: a página do computador sabe o personalizado do computador')
# quem muda o tema (qualquer aba) devolve o fundo só do espaço mexido; ao conectar chegam os dois
cl_novo = socketio.test_client(app, flask_test_client=fcaio)
conexao = [e for e in cl_novo.get_received() if e['name'] == 'preferencias_carregadas']
temas = conexao[0]['args'][0].get('temas') if conexao else None
ok(temas and set(temas) == {'computador', 'celular'} and temas['computador']['tema_custom']['img'] == '/debug-up/so_pc.webp' and temas['celular']['tema_custom']['img'] == '/debug-up/so_celular.webp',
   'Conexão: o servidor manda os dois temas e cada aparelho pega o seu')
caio.emit('mudar_tema', {'tema': 'dark', 'aparelho': 'computador'}); caio.get_received()
with app.app_context():
    cp = db.session.get(Person, pessoas['Caio'])
    ok(utils.tema_do_aparelho(cp, 'celular')[0] == 'custom' and utils.tema_do_aparelho(cp, 'celular')[1]['img'] == '/debug-up/so_celular.webp' and utils.tema_do_aparelho(cp, 'computador')[0] == 'dark',
       'Fundo: trocar o tema do computador guarda o personalizado dele e não toca no do celular')
caio.emit('mudar_tema', {'tema': 'amoled'}); caio.get_received()    # sem aparelho no pedido: vale o User-Agent da conexão (o teste não manda: computador)
with app.app_context():
    ok(db.session.get(Person, pessoas['Caio']).tema == 'amoled', 'Aparelho: sem o tipo no pedido, o servidor decide pelo User-Agent')
# o navegador
ok("const APARELHO = (/Mobi|iPhone|iPod/i.test(navigator.userAgent)" in chat and "aparelho: APARELHO" in chat, 'Navegador: sabe o tipo do aparelho e manda junto ao salvar o tema')
ok("prefs.temas ? prefs.temas[APARELHO] : (prefs.aparelho === APARELHO ? prefs : null)" in chat, 'Navegador: só aplica o tema do SEU tipo de aparelho (o aviso do outro tipo é ignorado)')
ok('Tema do ${aqui}' in chat and 'vale só pro ${aqui}' in chat, 'Aparência: a tela diz que o tema escolhido vale só pra este tipo de aparelho')
ok('tema_mobile' in ler('app/models.py') and 'tema_custom_mobile' in ler('atualizar_banco.py'), 'Banco: colunas do tema do celular existem no modelo e na migração')

# ---------------------------------------------------------------- app do Windows: "Procurar atualizações" instala sozinho
main = ler('desktop/main.js')
ok('autoUpdater.quitAndInstall(true, true)' in main, 'Desktop: instalar é silencioso e reabre o app (o instalador troca a versão antiga pela nova)')
ok("if (procuraManual) { instalarAtualizacao(); return; }" in main, 'Desktop: achou versão nova depois de "Procurar atualizações" = instala na hora')
ok("click: () => procurarAtualizacao(true)" in main and "procurarAtualizacao(true);" in main, 'Desktop: "Procurar atualizações" (aba Geral e bandeja) é o pedido manual')
ok("setInterval(() => procurarAtualizacao(), 4 * 60 * 60 * 1000)" in main and 'autoInstallOnAppQuit = true' in main, 'Desktop: a procura automática (4 h) só baixa e avisa (instala ao sair), pra não derrubar uma call')
ok("fase: 'instalando'" in main and "est.fase === 'instalando'" in chat and 'Instalando a versão' in chat, 'Desktop: a tela mostra "Instalando e reiniciando..."')
ok('migrarInicioComWindows' in main and "['electron.app.Panteão', 'Panteão']" in main and "'reg', ['delete'" in main.replace("execFile('reg', ['delete'", "'reg', ['delete'"), 'Desktop: "Iniciar com o Windows" é migrado (o executável mudou de nome com o novo nome do app)')
ok("openConfirmModal('Procurar atualizações?'" in chat, 'Desktop: procurar atualização numa call pergunta antes (instalar derruba a ligação)')

nsh = ler('desktop/build/installer.nsh')
ok('!macro customInstall' in nsh and 'StrCpy $launchLink "$appExe"' in nsh and 'FileExists} "$newStartMenuLink"' in nsh,
   'Instalador: ao atualizar o app abre pelo .exe (não pelo atalho renomeado, que dava "Windows não pode encontrar Pantheon.lnk") e recria o atalho se faltar')

print('\nFALHAS:', 'nenhuma' if not falhas else falhas)
sys.exit(1 if falhas else 0)
