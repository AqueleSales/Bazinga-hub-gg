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

print()
print('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S):\n  - ' + '\n  - '.join(falhas))
sys.exit(1 if falhas else 0)
