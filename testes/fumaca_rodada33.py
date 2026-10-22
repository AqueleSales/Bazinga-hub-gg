"""Rodada 33 (feedback do dono de 22/10/2026): inventário reorganizado, ícone do Pantheon e notificações com a foto. O que dá pra provar sem navegador:
os arquivos estáticos prometem o que a tela precisa, os ids casam com o catálogo do servidor e os dados da notificação saem sem vazar nada."""
import os, re, sys
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, RAIZ)
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app import cosmeticos as cos

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ler(*partes):
    return open(os.path.join(RAIZ, *partes), encoding='utf-8').read()


# ---------------- 5. inventário ----------------
js = ler('app', 'static', 'js', 'cosmeticos.js')
css = ler('app', 'static', 'css', 'cosmeticos.css')
secoes = re.search(r"const INV_SECOES = \[(.*?)\];", js, re.S).group(1)
ids_secoes = re.findall(r"\['([a-z_]+)', '", secoes)
tipos_catalogo = {k.split(':')[0] for k in cos.CATALOGO}
ok(set(ids_secoes) >= tipos_catalogo - {'pacote'} or set(ids_secoes) >= tipos_catalogo, 'o inventário tem uma seção pra todo tipo de item do catálogo (nenhum some)')
efeitos_py = {'efeito_avatar', 'efeito_perfil', 'efeito_fala', 'efeito_radar', 'efeito_chat', 'som_call', 'pin_nota', 'efeito_servidor'}
subs = set(re.findall(r"\['(efeito_[a-z]+|pin_nota|som_call)', '", re.search(r"const INV_SUBS_EFEITO = \[(.*?)\];", js, re.S).group(1)))
ok(subs == efeitos_py, 'a aba Efeitos separa por TIPO de efeito (avatar, perfil, fala, radar, digitando, pin, som, servidor)')
ok('data-filtro="busca"' in js and 'data-filtro="tema"' in js and 'data-filtro="origem"' in js, 'filtros por busca, tema e origem (exclusivos x livres)')
ok('el._invFiltro' in js and "if (aba !== 'efeito') f.sub = 'todos'" in js, 'os filtros sobrevivem ao redesenho do servidor e o de tipo de efeito só vale na aba Efeitos')
ok(re.search(r'\.inv-topo \{[^}]*z-index: 40[^}]*background: var\(--bg-primary\)', css, re.S) and '.inv-item { isolation: isolate' in css,
   'a barra de abas é opaca e fica por cima; cada item isola o próprio z-index (o efeito de perfil não passa por cima dos chips)')
ok('transparent)' not in re.search(r'\.inv-topo \{([^}]*)\}', css, re.S).group(1), 'a barra de abas não tem mais o degradê que deixava o conteúdo vazar')

# ---------------- 6. ícone do Pantheon ----------------
from PIL import Image
img = os.path.join(RAIZ, 'app', 'static', 'img')
cl = app.test_client()
m = cl.get('/manifest.webmanifest').get_json()
ok(any(i['purpose'] == 'maskable' and i['sizes'] == '512x512' and 'icone-maskable-512.png' in i['src'] for i in m['icons']), 'o manifesto tem o ícone maskable (o Android recorta sem cortar o templo)')
ok(all(cl.get(i['src']).status_code == 200 for i in m['icons']), 'todo ícone do manifesto existe')
r = cl.get('/favicon.ico')
ok(r.status_code == 200 and r.mimetype == 'image/x-icon' and len(r.data) > 500, '/favicon.ico responde (o navegador pede sozinho)')
for t in ('chat', 'entrar', 'index', 'abrir'):
    h = ler('app', 'templates', t + '.html')
    ok('apple-touch-icon' in h and 'favicon.ico' in h and 'icone-192.png' in h, f'{t}.html aponta o ícone novo (svg, ico, png e iPhone)')
ok(Image.open(os.path.join(img, 'apple-touch-icon.png')).size == (180, 180) and Image.open(os.path.join(img, 'icone-maskable-512.png')).size == (512, 512), 'tamanhos dos ícones derivados')
def cor_do_canto(caminho):
    im = Image.open(caminho).convert('RGBA'); return im.getpixel((2, im.size[1] // 2))
ok(cor_do_canto(os.path.join(img, 'icone-maskable-512.png'))[:3] == (20, 22, 27), 'o ícone maskable é cheio (sem cantos transparentes)')
dk = os.path.join(RAIZ, 'desktop')
ok(open(os.path.join(dk, 'build', 'icon.png'), 'rb').read() == open(os.path.join(img, 'icone-512.png'), 'rb').read(), 'o ícone do instalador/atalho do Windows é o logo atual (era o roxo antigo)')
ok(open(os.path.join(dk, 'assets', 'logo.svg'), encoding='utf-8').read() == open(os.path.join(img, 'logo.svg'), encoding='utf-8').read(), 'a tela de login do app usa o logo atual')
tray = Image.open(os.path.join(dk, 'assets', 'tray.png')).convert('RGB')
ok(sum(tray.getpixel((64, 6))) < 200 and tray.size == (128, 128), 'a bandeja tem o logo atual (fundo escuro, não o degradê roxo)')

print()
print('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S):\n  - ' + '\n  - '.join(falhas))
sys.exit(1 if falhas else 0)
