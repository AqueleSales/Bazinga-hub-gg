"""Insígnias por regra: Beta pra todo mundo, BAZINGA pra quem é do servidor Bazinga (por ID), Alpha pela lista de nomes."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db
from app.models import Role, Person, Server, Posse, ConfigApp
from app import cosmeticos as cos

app = create_app()
falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    def pessoa(nome, user):
        p = Person(name=nome, email=f'{user}@x', role_id=r.id, username=user); db.session.add(p); db.session.commit(); return p
    ana, fil, gabs = pessoa('Ana', 'ana'), pessoa('Filippo', 'filippo.chiarion'), pessoa('Gabriel Silva', 'gabs')
    dup1, dup2 = pessoa('Juarez', 'juarez1'), pessoa('juarez', 'juarez2')
    falso = pessoa('Impostor', 'imp')
    real = Server(name='Bazinga', owner_id=ana.id); real.members.extend([ana, gabs]); db.session.add(real)
    fake = Server(name='bazinga', owner_id=falso.id); fake.members.append(falso); db.session.add(fake); db.session.commit()

    # antes de definir o servidor: beta vale, bazinga não
    cos._cache_bazinga.clear()
    posses = cos.posses_com_regras(ana)
    ok('badge:beta_tester' in posses and 'badge:bazinga' not in posses, 'Beta automático; BAZINGA espera o servidor ser definido')

    # passo do atualizar_banco
    linhas = []
    cos.conceder_insignias_iniciais(linhas.append)
    cos._cache_bazinga.clear()
    tem = lambda p, i: Posse.query.filter_by(person_id=p.id, item_id=i).count() == 1
    ok(all(tem(p, 'badge:beta_tester') for p in (ana, fil, gabs, dup1, dup2, falso)), 'Beta pra todas as contas')
    ok(ConfigApp.query.get('servidor_bazinga_id').valor == str(real.id), 'Servidor Bazinga = o mais antigo com esse nome')
    ok(tem(ana, 'badge:bazinga') and tem(gabs, 'badge:bazinga'), 'Membros do Bazinga recebem BAZINGA')
    ok(not tem(falso, 'badge:bazinga') and not tem(fil, 'badge:bazinga'), 'Servidor de mesmo nome (outro id) e quem não é membro NÃO recebem')
    ok(tem(fil, 'badge:alpha_tester') and tem(gabs, 'badge:alpha_tester'), 'Alpha pra quem está na lista (por nome)')
    ok(not tem(ana, 'badge:alpha_tester'), 'Alpha não vai pra quem não está na lista')
    ok(not tem(dup1, 'badge:alpha_tester') and not tem(dup2, 'badge:alpha_tester') and any('2 contas' in l for l in linhas),
       'Nome repetido não concede e avisa')

    # entrou no servidor depois: recebe no próximo /chat
    nova = pessoa('Nova', 'nova')
    ok('badge:bazinga' not in cos.posses_com_regras(nova), 'Fora do servidor: sem BAZINGA')
    real.members.append(nova); db.session.commit()
    ok('badge:bazinga' in cos.posses_com_regras(nova), 'Entrou no servidor: recebe no próximo carregamento')
    n = Posse.query.filter_by(person_id=nova.id).count()
    cos.posses_com_regras(nova)
    ok(Posse.query.filter_by(person_id=nova.id).count() == n, 'Rodar de novo não duplica')

    ordem = cos.badges_do_conjunto({'badge:so_nos', 'badge:bazinga', 'badge:alpha_tester', 'badge:criador'})
    ok(ordem == ['criador', 'alpha_tester', 'bazinga', 'so_nos'], 'Ordem das insígnias no cartão')

print()
print('FALHAS:', falhas if falhas else 'nenhuma')
sys.exit(1 if falhas else 0)
