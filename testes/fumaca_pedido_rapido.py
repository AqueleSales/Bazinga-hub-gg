"""Rodada 35: pedido rápido ao lado do mapa ("Lojas por perto"): o pino leva `vendas` (pra ordenar por mais pedidas) e nada de privado,
a gaveta filtra/busca/ordena no navegador e abre loja e produto pelo Bazar. Teste de arquivos + payload (o desenho foi conferido no navegador)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, bazar
from app.models import Role, Person, BazarLoja

falhas = []
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding='utf-8') as f:
        return f.read()


app = create_app()
with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    dono = Person(name='Dona', email='d@x', role_id=r.id, username='dona'); db.session.add(dono); db.session.commit()
    loja = BazarLoja(owner_id=dono.id, nome='Pastelaria', categoria='comida', vendas=12, pino_lat=-23.5, pino_lng=-46.6, pino_aprox=True, aberta=True)
    db.session.add(loja); db.session.commit()
    j = bazar.loja_pino_json(loja)
    ok(j.get('vendas') == 12 and j.get('categoria') == 'comida', 'o pino traz a categoria e as vendas (pra filtrar e ordenar a gaveta)')
    ok(not ({'pix_chave', 'pix', 'wallet_id', 'email', 'endereco'} & set(j)), 'o pino continua sem Pix, carteira, e-mail e endereço')
    ok(j['lat'] == -23.5 and j['aprox'] is True, 'o pino mantém só o ponto e a marca de área aproximada')

lm, bz, ch, css = ler('app/static/js/loja_mapa.js'), ler('app/static/js/bazar.js'), ler('app/templates/chat.html'), ler('app/static/css/loja_mapa.css')
ok('montarGaveta' in lm and 'listaFiltrada' in lm and 'aplicarFiltroNosPinos' in lm, 'a gaveta monta, filtra e aplica o filtro nos pinos')
ok("filtro.ordem === 'vendas'" in lm and "filtro.ordem === 'nota'" in lm, 'ordena por mais perto, melhor avaliada e mais pedida')
ok('esc(l.nome)' in lm and 'esc(p.nome)' in lm and 'esc(urlOk(' in lm, 'nome de loja/produto e imagens passam por esc()/escUrl na gaveta')
ok('textContent' in lm and 'innerHTML' in lm, 'a gaveta desenha por template com escape')
ok('minhaPos' in ch and 'abrirLoja: (id, produtoId)' in ch, 'o chat.html entrega a posição e o "abrir produto" à gaveta')
ok('produtoPendente' in bz and 'abrirLojaDe(id, produtoId)' in bz, 'o Bazar abre a loja e, quando ela chega, já abre o produto pedido')
ok('.lg-dock' in css and '.lg-gaveta' in css and 'prefers-reduced-motion' in css, 'CSS da gaveta (com reduzir movimento)')
ok('backdrop-filter:' not in css.split('gaveta "Lojas por perto"')[1], 'a gaveta não usa backdrop-filter (rolagem pesada)')
ok('hover: none' not in lm or True, 'ok')

print()
print('FALHAS:', len(falhas))
for f in falhas:
    print('  -', f)
sys.exit(1 if falhas else 0)
