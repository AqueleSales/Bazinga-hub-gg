"""Rodada 33: cargo com ícone, cargo dado sozinho a quem entra (convite, link, Explorar, mapa), banner do servidor no cartão do mapa e o que o
cliente de Cargos promete (interruptores, permissões agrupadas, arrastar sem setinhas). SQLite em memória + socketio.test_client."""
import os, re, sys
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, RAIZ)
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app import cargos
from app.models import Role, Person, Server, Channel, ServerRole, MemberRole, MapServer
from app.utils import servidor_mapa_para_json

app = create_app()
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ev(cli, nome=None):
    return [m for m in cli.get_received() if nome is None or m['name'] == nome]


def erro(cli):
    e = ev(cli, 'erro_bazinga')
    return e[0]['args'][0]['msg'] if e else None


with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Dono', 'Gerente', 'Novo1', 'Novo2', 'Novo3', 'Novo4'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); db.session.commit(); ids[n] = p.id

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc

    dono, fdono = cliente('Dono')
    dono.emit('criar_servidor_discord', {'nome': 'Reino'})
    sid = ev(dono, 'servidor_discord_criado')[-1]['args'][0]['id']
    ev(dono)

    # ---------- ícone do cargo ----------
    dono.emit('cargo_criar', {'server_id': sid, 'nome': 'Boas-vindas', 'icone': '🎉', 'permissoes': ['fixar_mensagens']}); ev(dono)
    cargo = ServerRole.query.filter_by(server_id=sid, nome='Boas-vindas').one()
    ok(cargo.icone == '🎉', 'o cargo nasce com o emoji escolhido')
    dono.emit('cargo_editar', {'server_id': sid, 'cargo_id': cargo.id, 'icone': '<img src=x onerror=1>'}); ev(dono)
    ok(ServerRole.query.get(cargo.id).icone is None, 'texto, HTML ou aspas no ícone viram vazio (nunca chegam ao navegador)')
    dono.emit('cargo_editar', {'server_id': sid, 'cargo_id': cargo.id, 'icone': '⭐'}); ev(dono)
    ok(ServerRole.query.get(cargo.id).icone == '⭐', 'e o emoji de verdade volta a valer')
    est = cargos.carregar_estruturas([Server.query.get(sid)]).get(sid)
    ok(est and est['cargos'][0]['icone'] == '⭐', 'o ícone vai na estrutura do servidor')
    dono.emit('cargo_editar', {'server_id': sid, 'cargo_id': cargo.id, 'nome': 'Boas-vindas'})
    rec = ev(dono, 'servidor_estrutura')[-1]['args'][0]
    item = next(x for x in rec['cargos'] if x['id'] == cargo.id)
    ok(item['icone'] == '⭐' and item['auto'] is False, 'quem gerencia cargos recebe o ícone e se o cargo é automático')

    # ---------- cargo automático ----------
    dono.emit('cargo_editar', {'server_id': sid, 'cargo_id': cargo.id, 'automatico': True}); ev(dono)
    ok(ServerRole.query.get(cargo.id).automatico is True, 'o dono marca o cargo pra ser dado a quem entrar')
    dono.emit('cargo_criar', {'server_id': sid, 'nome': 'Chefe', 'permissoes': ['administrador'], 'automatico': True})
    ok('Administrador' in (erro(dono) or ''), 'cargo com Administrador não pode ser automático (criando)')
    ok(ServerRole.query.filter_by(server_id=sid, nome='Chefe').count() == 0, '...e nada foi criado')
    dono.emit('cargo_editar', {'server_id': sid, 'cargo_id': cargo.id, 'permissoes': ['administrador']})
    ok('Administrador' in (erro(dono) or '') and not (ServerRole.query.get(cargo.id).permissoes or 0) & cargos.BIT['administrador'],
       'dar Administrador a um cargo automático é recusado (editando) e nada muda')

    dono.emit('criar_convite', {'server_id': sid})
    codigo = ev(dono, 'convite_criado')[-1]['args'][0]['code']
    novo1, fnovo1 = cliente('Novo1')
    novo1.emit('entrar_por_convite', {'code': codigo}); ev(novo1)
    ok(MemberRole.query.filter_by(person_id=ids['Novo1'], role_id=cargo.id).count() == 1, 'entrar por convite (código): recebe o cargo automático')
    ok(ids['Novo1'] in cargos.cargos_dos_membros(Server.query.get(sid)) and cargo.id in cargos.cargos_dos_membros(Server.query.get(sid))[ids['Novo1']],
       '...e o cache de cargos já enxerga (invalidado depois do commit)')
    novo1.emit('entrar_por_convite', {'code': codigo}); ev(novo1)
    ok(MemberRole.query.filter_by(person_id=ids['Novo1'], role_id=cargo.id).count() == 1, 'entrar de novo não duplica o cargo')

    resp = fnovo1.get('/convite/' + codigo)              # a rota HTTP também é um caminho de entrada
    novo2, fnovo2 = cliente('Novo2')
    resp = fnovo2.get('/convite/' + codigo)
    ok(MemberRole.query.filter_by(person_id=ids['Novo2'], role_id=cargo.id).count() == 1, 'entrar pelo link do convite: recebe o cargo automático')

    srv = Server.query.get(sid); srv.publico = True; srv.description = 'Um reino de teste para o Explorar.'; srv.tema_explorar = 'outros'; db.session.commit()
    novo3, _ = cliente('Novo3')
    novo3.emit('explorar_entrar', {'server_id': sid}); ev(novo3)
    ok(MemberRole.query.filter_by(person_id=ids['Novo3'], role_id=cargo.id).count() == 1, 'entrar pelo Explorar: recebe o cargo automático')

    ok(MemberRole.query.filter_by(person_id=ids['Dono']).count() == 0, 'o dono não ganha cargo automático (ele já pode tudo)')

    # servidor SEM estrutura nem consulta a tabela de cargos na entrada
    dono.emit('criar_servidor_discord', {'nome': 'Simples'})
    sid2 = ev(dono, 'servidor_discord_criado')[-1]['args'][0]['id']; ev(dono)
    dono.emit('criar_convite', {'server_id': sid2}); cod2 = ev(dono, 'convite_criado')[-1]['args'][0]['code']
    from sqlalchemy import event
    consultas = []
    def conta(conn, cur, stmt, *a): consultas.append(stmt)
    event.listen(db.engine, 'before_cursor_execute', conta)
    novo4, _ = cliente('Novo4')
    consultas.clear()
    novo4.emit('entrar_por_convite', {'code': cod2}); ev(novo4)
    event.remove(db.engine, 'before_cursor_execute', conta)
    ok(not any('server_role' in q or 'member_role' in q for q in consultas), 'servidor que nunca teve cargo não consulta cargos ao entrar (custo igual ao de antes)')

    # ---------- banner no cartão do servidor no mapa ----------
    dono.emit('editar_servidor', {'server_id': sid, 'banner_url': '/static/uploads/banner.png'}); ev(dono)
    ok(Server.query.get(sid).banner_url == '/static/uploads/banner.png', 'o banner é salvo pelo popup do servidor')
    pino = MapServer(server_id=sid, owner_id=ids['Dono'], name='Reino', lat=-15.8, lng=-47.9); db.session.add(pino); db.session.commit()
    j = servidor_mapa_para_json(pino)
    ok(j['banner_url'] == '/static/uploads/banner.png', 'o cartão do mapa recebe o banner')
    dono.emit('editar_servidor', {'server_id': sid, 'banner_url': 'javascript:alert(1)'}); ev(dono)
    ok(not Server.query.get(sid).banner_url or Server.query.get(sid).banner_url.startswith('/'), 'banner com endereço perigoso não vale')
    dono.emit('editar_servidor', {'server_id': sid, 'nome': 'Reino 2', 'banner_url': '/static/uploads/banner.png', 'descricao': 'nova descrição'})
    editado = [m for m in dono.get_received() if m['name'] == 'servidor_mapa_editado']
    ok(editado and editado[-1]['args'][0].get('banner_url') == '/static/uploads/banner.png' and editado[-1]['args'][0].get('description') == 'nova descrição',
       'editar o servidor atualiza o cartão do mapa com banner, descrição e cor (antes perdia a descrição)')

    # ---------- o que o cliente de Cargos promete ----------
    js = open(os.path.join(RAIZ, 'app', 'static', 'js', 'cargos.js'), encoding='utf-8').read()
    css = open(os.path.join(RAIZ, 'app', 'static', 'css', 'cargos.css'), encoding='utf-8').read()
    grupos = re.search(r"const GRUPOS_PERM = \[(.*?)\n    \];", js, re.S).group(1)
    ids_grupos = [i for i in re.findall(r"'([a-z_]+)'", grupos) if i in cargos.IDS_PERMISSAO]
    ok(sorted(ids_grupos) == sorted(cargos.IDS_PERMISSAO), 'toda permissão aparece em UM grupo da tela de cargos (nenhuma some, nenhuma repete)')
    ok('class="cg-sw"' in js and '.cg-sw' in css and 'appearance: none' in css, 'permissões são interruptores (não caixinhas brancas)')
    ok('cg-setas' not in js and 'cg-setas' not in css and 'data-desce="${Number(r.id)}"' not in js, 'as setinhas de ordem dos cargos saíram')
    ok('cg-grip' in js and 'ligarArrastoDeCargos' in js and "'cargos_reordenar'" in js and 'dataset.arrasto' in js, 'a ordem dos cargos se muda segurando e arrastando (ligado uma vez só)')
    ok(js.count("document.addEventListener('pointermove'") == 1 or js.count("document.addEventListener('pointermove', (e) => {\n            if (!s || e.pointerId !== s.id) return;\n            s.y") == 1,
       'os ouvintes do arrasto não se acumulam a cada redesenho')
    ok('pedirMembros' in js and 'idsAntes' in js, 'a lista de membros só é pedida de novo quando o conjunto de cargos muda')
    ok('cfg-banner-linha' in open(os.path.join(RAIZ, 'app', 'templates', 'chat.html'), encoding='utf-8').read() and 'cx-banner-escolher-r' in js,
       'o banner também se escolhe no popup rápido do servidor')
    ok('mask-image' in css and 'to left' in css, 'o banner do cabeçalho some da direita pra esquerda (o nome não fica sobre a imagem)')

print()
print('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S):\n  - ' + '\n  - '.join(falhas))
sys.exit(1 if falhas else 0)
